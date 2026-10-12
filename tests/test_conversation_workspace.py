"""Unified Tk workspace checks; model content is synthetic and offline."""
from copy import deepcopy
from threading import Event
import tkinter as tk

import pytest

from promptsmith.conversation import conversation_cards
from promptsmith.m1 import build_m1_input
from promptsmith.storage import load_session, save_session
from promptsmith.ui import PromptSmithApp
from tests.test_final_delivery import confirmed_plan_session
from tests.test_guided_jgs_chain import NOTICE, scenario_app
from tests.test_ui_delivery_interactions import _candidate, _DeliveryUiClient, _configure_delivery_client, _pump_until
from tests.test_ui_reliability import pump


@pytest.fixture
def app(tk_root, tmp_path, monkeypatch):
    window = tk.Toplevel(tk_root)
    window.withdraw()
    application = PromptSmithApp(window, evidence_root=tmp_path / "calls")
    application.api_base_var.set("https://example.invalid/v1")
    application.api_model_var.set("offline-fixture")
    application.api_key_var.set("offline-key")
    application.confirm_model_settings()
    application.dialogs = []
    application.callback_errors = []
    window.report_callback_exception = lambda *args: application.callback_errors.append(args)
    monkeypatch.setattr("tkinter.messagebox.showerror", lambda *args, **kw: application.dialogs.append(args))
    monkeypatch.setattr("tkinter.messagebox.showinfo", lambda *args, **kw: application.dialogs.append(args))
    monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *args, **kw: True)
    yield application
    application.shutdown(wait=True)
    window.destroy()
    assert not application.callback_errors


def install_session(app, session):
    app.session = session
    app.workflow.session = session
    app.delivery_workflow.session = session
    app.widgets["task_text"].delete("1.0", "end")
    app.widgets["task_text"].insert("1.0", session.task_text)
    app.category_var.set(next(label for label, value in app.category_by_label.items() if value == session.selected_category))
    app.refresh()


def send(app, text):
    app.widgets["conversation_input"].insert("1.0", text)
    app.widgets["conversation_send_button"].invoke()


def test_goal_is_recorded_once_and_busy_send_preserves_draft(app, monkeypatch):
    requests = []
    monkeypatch.setattr(app, "_submit", lambda *args: requests.append(args))
    send(app, "给项目做一个清晰的用户界面")
    assert app.session.task_text == "给项目做一个清晰的用户界面"
    assert len(requests) == 1 and app.busy
    assert app.widgets["conversation_input"].get("1.0", "end-1c") == ""
    send(app, "希望使用浅色主题")
    assert len(requests) == 1
    assert app.widgets["conversation_input"].get("1.0", "end-1c") == "希望使用浅色主题"
    assert app.session.question_history == []


def test_unconfirmed_settings_keep_sent_goal_without_request(app, monkeypatch):
    app.api_model_var.set("changed-model")
    requests = []
    monkeypatch.setattr(app, "_submit", lambda *args: requests.append(args))
    send(app, "准备一个课堂演示")
    assert not requests
    assert app.session.task_text == "准备一个课堂演示"
    assert app.notebook.index(app.notebook.select()) == 4
    app.confirm_model_settings()
    app.return_from_settings()
    assert app._primary_action().kind == "analyze"


def test_inline_answers_are_recorded_individually_and_all_reach_m1(app, monkeypatch):
    app.widgets["task_text"].insert("1.0", "改进UI")
    app._sync_input()
    app.session.pending_questions = [
        {"question_id": "q1", "gap_id": None, "field": "audience", "scope": "用户",
         "text": "谁会使用？", "options": ["个人", "团队"], "reason": "不应该出现在问题卡片", "depends_on": []},
        {"question_id": "q2", "gap_id": None, "field": "deliverable", "scope": "成果",
         "text": "希望得到什么？", "options": [], "reason": "内部说明", "depends_on": []},
    ]
    app.refresh()
    requests = []
    monkeypatch.setattr(app, "start_analysis", lambda: requests.append(build_m1_input(app.session, "combined")))
    assert "option:1" not in app._conversation_buttons
    app._question_inputs["q1"].insert("1.0", "团队")
    app.root.update()
    assert app._question_inputs["q1"].get("1.0", "end-1c") == "团队"
    assert app.widgets["conversation_input"].get("1.0", "end-1c") == ""
    app._conversation_buttons["submit:q1"].invoke()
    assert not requests
    assert len(app.session.question_history) == 1
    assert conversation_cards(app.session)[-1]["question"]["question_id"] == "q2"
    app._question_inputs["q2"].insert("1.0", "可运行的重构代码")
    app.root.update()
    app._conversation_buttons["submit:q2"].invoke()
    assert len(requests) == 1
    assert [row["answer_text"] for row in requests[0]["state"]["question_history"]] == ["团队", "可运行的重构代码"]
    assert all("内部说明" not in str(label.cget("text")) for label in app._conversation_labels)
    assert app.session.confirmed_requirements_version is None


def test_supplement_invalidates_old_result_and_survives_reopen(app, monkeypatch, tmp_path):
    install_session(app, confirmed_plan_session())
    app._conversation_buttons["skip_skills"].invoke()
    original_goal = app.session.task_text
    requests = []
    monkeypatch.setattr(app, "start_analysis", lambda: requests.append(build_m1_input(app.session, "revision")))
    send(app, "把计划改成14天，每天20分钟")
    assert app.session.task_text == original_goal
    assert app.session.plan["status"] == "stale"
    assert app.session.final_result["status"] == "stale"
    assert app.session.confirmed_requirements_version is None
    assert app.session.question_history[-1]["answer_text"] == "把计划改成14天，每天20分钟"
    assert len(requests) == 1
    assert str(app._conversation_buttons["copy"].cget("state")) == "disabled"
    before = conversation_cards(app.session)
    path = save_session(app.session, tmp_path / "conversation.json")
    loaded = load_session(path)
    assert conversation_cards(loaded) == before
    assert "offline-key" not in path.read_text(encoding="utf-8")


def test_projection_and_summary_are_read_only_and_old_actions_are_rejected(app):
    install_session(app, confirmed_plan_session())
    before = deepcopy(app.session.to_dict())
    token = app._conversation_token()
    conversation_cards(app.session)
    app.toggle_conversation_summary()
    app.refresh()
    assert app.session.to_dict() == before
    app.session.edit_plan_goal("修订后的目标")
    invoked = []
    app._conversation_action(token, lambda: invoked.append(True))
    assert not invoked
    assert "内容已变化" in app.status_var.get()


def test_plan_can_be_edited_and_confirmed_in_conversation(app, monkeypatch):
    install_session(app, confirmed_plan_session())
    app._conversation_buttons["back_stage"].invoke()
    # Complete editing remains available; the one-off goal shortcut was removed.
    app._conversation_buttons["edit_plan"].invoke()
    app.session.edit_plan_goal("14天的入门计划")
    app.show_workspace(0)
    app.refresh()
    assert app.session.plan["content"]["goal"]["summary"] == "14天的入门计划"
    assert app.session.plan["status"] == "draft"
    app._conversation_buttons["review_plan"].invoke()
    app._conversation_buttons["confirm_plan"].invoke()
    assert app.session.plan["status"] == "confirmed"
    assert app.session.final_result["canonical_body"]
    assert app.notebook.index(app.notebook.select()) == 0
    assert not app.dialogs


def test_entire_no_skill_http_flow_uses_only_conversation_cards(scenario_app, tmp_path, monkeypatch):
    app, scenario = scenario_app("writing")
    send(app, NOTICE)
    pump(app.root, app, timeout=8)
    assert app.notebook.index(app.notebook.select()) == 0
    app.toggle_requirements_review()
    app._conversation_buttons["confirm_requirements"].invoke()
    pump(app.root, app, timeout=8)
    assert not app.probe_errors, app.probe_errors
    assert app.session.plan["status"] == "draft"
    assert app.notebook.index(app.notebook.select()) == 0
    app.toggle_plan_review()
    app._conversation_buttons["confirm_plan"].invoke()
    assert app.notebook.index(app.notebook.select()) == 0
    assert len(scenario.received) == 2
    assert app.session.skill_state["status"] == "skipped"
    app._conversation_buttons["copy"].invoke()
    assert "摄影社招新通知" in app.root.clipboard_get()
    path = tmp_path / "prompt.md"
    monkeypatch.setattr("tkinter.filedialog.asksaveasfilename", lambda **k: str(path))
    app._conversation_buttons["export"].invoke()
    assert "摄影社招新通知" in path.read_text(encoding="utf-8")
    saved = tmp_path / "session.json"
    monkeypatch.setattr("tkinter.filedialog.asksaveasfilename", lambda **k: str(saved))
    app._conversation_buttons["save"].invoke()
    before = conversation_cards(app.session)
    monkeypatch.setattr("tkinter.filedialog.askopenfilename", lambda **k: str(saved))
    app.open_session()
    assert conversation_cards(app.session) == before
    assert not app.probe_errors


def test_skill_selection_integration_and_cancel_are_inline(app, monkeypatch):
    install_session(app, confirmed_plan_session())
    candidate, _binding = _candidate()
    app.session.set_skill_state(status="candidates_ready", basis=app._delivery_basis(),
                               candidate_batch={"result": {"candidates": [candidate]}}, bindings=[])
    client = _DeliveryUiClient()
    _configure_delivery_client(app, monkeypatch, client)
    app.refresh()
    app.widgets["conversation_skill_candidates_tree"].selection_set("candidate-1")
    app.root.update()
    app._conversation_buttons["select_skills"].invoke()
    binding_id = app.session.skill_state["bindings"][0]["binding_id"]
    app._conversation_buttons["integrate"].invoke()
    _pump_until(app.root, lambda: not app.delivery_busy)
    assert app.notebook.index(app.notebook.select()) == 0
    assert client.payloads[0]["schema_version"] == "m4.v0.1"
    body = app.session.final_result["canonical_body"]
    assert "to-spec" in body and candidate["record_snapshot"]["source_path"] in body
    app.widgets["conversation_skill_candidates_tree"].selection_set("candidate-1")
    app.root.update()
    app._conversation_buttons["cancel_skills"].invoke()
    assert app.session.skill_state["bindings"] == []
    assert app.session.final_result["status"] == "stale"
    assert not app.dialogs


def test_cancel_integration_discards_late_response_and_retains_typed_draft(app, monkeypatch):
    install_session(app, confirmed_plan_session())
    candidate, binding = _candidate()
    app.session.set_skill_state(status="selected", basis=app._delivery_basis(),
                               candidate_batch={"result": {"candidates": [candidate]}}, bindings=[binding])
    entered, release = Event(), Event()
    client = _DeliveryUiClient(entered=entered, release=release)
    _configure_delivery_client(app, monkeypatch, client)
    app.refresh()
    try:
        app._conversation_buttons["integrate"].invoke()
        _pump_until(app.root, entered.is_set)
        app.widgets["conversation_input"].insert("1.0", "晚一点再生成")
        app.widgets["conversation_send_button"].invoke()
        release.set()
        _pump_until(app.root, lambda: not app.delivery_busy)
        app.executor.submit(lambda: None).result(timeout=3)
        app._poll_completions()
        assert app.session.final_result["status"] == "not_started"
        assert app.widgets["conversation_input"].get("1.0", "end-1c") == "晚一点再生成"
        assert not app.session.question_history
    finally:
        release.set()


@pytest.mark.parametrize("size", ["1440x810", "720x405"])
def test_composer_and_header_remain_visible_while_timeline_scrolls(app, size):
    install_session(app, confirmed_plan_session())
    app.root.minsize(1, 1)
    app.root.geometry(size)
    app.root.deiconify()
    app.root.update()
    canvas = app.widgets["requirements_page_canvas"]
    composer = app.widgets["conversation_input"]
    before_y = composer.winfo_rooty()
    canvas.yview_moveto(1)
    app.root.update()
    assert composer.winfo_rooty() == before_y
    for name in ("conversation_input", "conversation_send_button", "settings_button", "task_summary_button"):
        widget = app.widgets[name]
        assert widget.winfo_ismapped()
        assert widget.winfo_rootx() + widget.winfo_width() <= app.root.winfo_rootx() + app.root.winfo_width()
        assert widget.winfo_rooty() + widget.winfo_height() <= app.root.winfo_rooty() + app.root.winfo_height()
    assert canvas.winfo_height() > 30
    app.toggle_conversation_summary()
    app.root.update()
    assert composer.winfo_rooty() == before_y
