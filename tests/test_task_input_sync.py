from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
import gc
import tkinter as tk

import pytest

from promptsmith.session import SessionState
from promptsmith.finalization import build_final_draft, confirm_final
from promptsmith.storage import save_session
from promptsmith.ui import PromptSmithApp
from tests.test_final_delivery import confirmed_plan_session


@pytest.fixture
def app(tk_root, tmp_path, monkeypatch):
    window = tk.Toplevel(tk_root)
    window.withdraw()
    application = PromptSmithApp(window, evidence_root=tmp_path / "runs")
    application.api_base_var.set("https://example.invalid/v1")
    application.api_model_var.set("test-model")
    application.api_key_var.set("test-only-key")
    application.confirm_model_settings()
    # Capture submissions; none of these UI checks may access a real service.
    application.test_submissions = []
    monkeypatch.setattr(application, "_submit", lambda *args: application.test_submissions.append(args))
    yield application
    application.shutdown(wait=True)
    gc.collect()
    window.destroy()


def replace_text(app, value):
    app.widgets["task_text"].delete("1.0", "end")
    app.widgets["task_text"].insert("1.0", value)


def test_refresh_uses_visible_task_without_writing_session(app):
    before = deepcopy(app.session.to_dict())
    replace_text(app, "讲一下JGS")
    app.refresh()
    assert app.primary_action_var.get() == "开始整理"
    assert app._primary_action().kind == "analyze"
    assert app.session.to_dict() == before


def test_primary_click_syncs_text_and_category_before_dispatch(app, monkeypatch):
    called = []
    monkeypatch.setattr(app, "start_analysis", lambda: called.append(
        (app.session.task_text, app.session.selected_category)))
    replace_text(app, "讲一下JGS")
    app.category_var.set(next(label for label, key in app.category_by_label.items() if key == "learning"))
    app.run_primary_action()
    assert called == [("讲一下JGS", "learning")]
    assert app.session.task_text == "讲一下JGS"


def test_button_enters_existing_workflow_with_synced_task(app):
    replace_text(app, "讲一下JGS")
    app.widgets["analyze_button"].invoke()
    assert app.session.task_text == "讲一下JGS"
    assert app.busy_kind == "m1"
    assert len(app.test_submissions) == 1
    request = next(iter(app.session.pending_requests.values()))
    assert request["task_text"] == "讲一下JGS"
    before = app.session.requirement_version
    app.run_primary_action()
    assert app.session.requirement_version == before
    assert len(app.test_submissions) == 1


@pytest.mark.parametrize("previous_task", ["", "此前已经分析的任务"])
def test_empty_visible_task_focuses_without_sync_or_request(app, previous_task, monkeypatch):
    if previous_task:
        app.session.set_task(previous_task)
        app.session.pending_questions = [{"question_id": "q1", "field": "goal", "text": "旧问题"}]
    before = deepcopy(app.session.to_dict())
    replace_text(app, "  \n ")
    setter_calls = []
    monkeypatch.setattr(app.session, "set_task", lambda value: setter_calls.append(value))
    app.root.deiconify()
    app.root.focus_force()
    app.root.update()
    app.refresh()
    assert app.primary_action_var.get() == "先输入任务"
    app.widgets["analyze_button"].invoke()
    app.root.update()
    assert app.root.focus_get() == app.widgets["task_text"]
    assert setter_calls == []
    assert app.test_submissions == []
    assert app.session.to_dict() == before


def test_typing_updates_label_and_connection_changes_without_sync(app):
    app.api_key_var.set("")
    app.root.deiconify()
    app.root.focus_force()
    text = app.widgets["task_text"]
    text.focus_set()
    app.root.update()
    text.focus_force()
    app.root.update()
    before = deepcopy(app.session.to_dict())
    text.event_generate("<KeyPress-j>")
    app.root.update()
    assert text.get("1.0", "end-1c") == "j"
    assert app.primary_action_var.get() == "补全模型连接"
    app.api_key_var.set("test-only-key")
    app.confirm_model_settings()
    assert app.primary_action_var.get() == "开始整理"
    text.event_generate("<KeyPress-g>")
    app.root.update()
    text.delete("1.0", "end")
    app.root.update()
    assert app.primary_action_var.get() == "先输入任务"
    assert app.session.to_dict() == before


@pytest.mark.parametrize("method", ["right_click", "ctrl_v"])
def test_paste_cut_and_undo_refresh_without_mutating_session(app, method, monkeypatch):
    text = app.widgets["task_text"]
    app.root.deiconify()
    app.root.focus_force()
    text.focus_set()
    app.root.update()
    text.focus_force()
    app.root.update()
    try:
        original_clipboard = text.clipboard_get()
    except tk.TclError:
        original_clipboard = None
    before = deepcopy(app.session.to_dict())
    try:
        text.clipboard_clear()
        text.clipboard_append("讲一下JGS")
        if method == "right_click":
            monkeypatch.setattr(tk.Menu, "tk_popup", lambda *_args: None)
            menu = app._show_context_menu(SimpleNamespace(x_root=0, y_root=0), text)
            paste_index = next(i for i in range(menu.index("end") + 1)
                               if menu.type(i) == "command" and menu.entrycget(i, "label") == "粘贴")
            menu.invoke(paste_index)
            menu.destroy()
        else:
            text.event_generate("<Control-v>")
        app.root.update()
        assert text.get("1.0", "end-1c") == "讲一下JGS"
        assert app.primary_action_var.get() == "开始整理"
        text.edit_separator()
        text.event_generate("<Control-a>")
        text.event_generate("<Control-x>")
        app.root.update()
        assert text.get("1.0", "end-1c") == ""
        assert app.primary_action_var.get() == "先输入任务"
        text.event_generate("<Control-z>")
        app.root.update()
        assert text.get("1.0", "end-1c") == "讲一下JGS"
        assert app.primary_action_var.get() == "开始整理"
        assert app.session.to_dict() == before
    finally:
        text.clipboard_clear()
        if original_clipboard is not None:
            text.clipboard_append(original_clipboard)


def test_questions_remain_primary_for_unchanged_visible_task(app):
    app.session.set_task("讲一下JGS")
    replace_text(app, app.session.task_text)
    app.session.pending_questions = [{"question_id": "q1", "field": "goal", "text": "哪方面？"}]
    app.root.update()
    app.refresh()
    assert app.primary_action_var.get() == "回答问题"
    before = deepcopy(app.session.to_dict())
    app.widgets["analyze_button"].invoke()
    assert app.session.to_dict() == before
    assert app.test_submissions == []


def test_edit_opened_task_invalidates_once_and_new_session_clears_label(app, tmp_path, monkeypatch):
    session = confirmed_plan_session()
    session.final_result = build_final_draft(session)
    confirm_final(session)
    path = tmp_path / "session.json"
    save_session(session, path)
    monkeypatch.setattr("promptsmith.ui.filedialog.askopenfilename", lambda **_kwargs: str(path))
    monkeypatch.setattr("promptsmith.ui.messagebox.askyesno", lambda *_args, **_kwargs: True)
    app.open_session()
    app.root.update()
    assert app.widgets["task_text"].get("1.0", "end-1c") == session.task_text
    assert app.primary_action_var.get() == "查看方案和提示"
    # Isolate task invalidation from asynchronous generation; configured first
    # clicks and duplicate-submit protection are exercised in separate tests.
    app.api_key_var.set("")
    before_version = app.session.requirement_version
    replace_text(app, "讲一下JGS")
    app.root.update()
    assert app.session.requirement_version == before_version
    app.run_primary_action()
    assert app.session.task_text == "讲一下JGS"
    assert app.session.requirement_version == before_version + 1
    assert app.session.confirmed_requirements_version is None
    assert app.session.analysis_basis_version is None
    assert all(row["confirmation"] == "review_needed" for row in app.session.requirements)
    assert app.session.pending_review_item_ids
    assert app.session.plan["status"] == "stale"
    assert app.session.final_result["status"] == "stale"
    assert app.notebook.index(app.notebook.select()) == 4
    assert app.primary_action_var.get() == "返回工作区"
    app.run_primary_action()
    assert app.notebook.index(app.notebook.select()) == 0
    assert app.primary_action_var.get() == "补全模型连接"
    after = deepcopy(app.session.to_dict())
    app.run_primary_action()
    assert app.session.to_dict() == after
    assert app.test_submissions == []
    app.new_session()
    app.root.update()
    assert app.primary_action_var.get() == "先输入任务"
    assert app.widgets["task_text"].get("1.0", "end-1c") == ""
    assert app.session.task_text == ""
