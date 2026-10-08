from __future__ import annotations

import json
import threading
import time
import tkinter as tk
from tkinter import ttk
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from promptsmith.api import ApiResult
from promptsmith.session import SessionState
from promptsmith.ui import PromptSmithApp
from promptsmith.workflow import M1CallOutcome


@pytest.fixture
def tk_window(tk_root):
    window = tk.Toplevel(tk_root)
    window.withdraw()
    yield window
    window.destroy()


def pump(window: tk.Misc, app: PromptSmithApp, timeout: float = 5) -> None:
    deadline = time.time() + timeout
    while app.busy and time.time() < deadline:
        window.update()
        time.sleep(0.01)
    window.update()
    assert app.busy is False


def model_server(*, response: dict, delay: float = 0):
    class Handler(BaseHTTPRequestHandler):
        seen = {}

        def do_GET(self) -> None:  # noqa: N802
            type(self).seen = {
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
            }
            if delay:
                time.sleep(delay)
            raw = json.dumps(response).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format: str, *args) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, Handler


def failing_model_server(status: int, *, delay: float = 0, raw: bytes = b"{}"):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if delay:
                time.sleep(delay)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format: str, *args) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_connection_panel_separates_provider_protocol_and_keeps_manual_model_entry(tk_window) -> None:
    app = PromptSmithApp(tk_window)
    try:
        assert app.provider_var.get() == "DeepSeek"
        assert app.protocol_var.get() == "OpenAI Chat Completions"
        assert app.api_model_var.get() == "deepseek-flash"
        assert str(app.widgets["api_model_combo"].cget("state")) == "normal"
        assert "model_list_button" in app.widgets
    finally:
        app.shutdown(wait=True)


def test_connection_probe_truncation_is_reported_as_unverified_generation(tk_window) -> None:
    app = PromptSmithApp(tk_window)
    try:
        app._connection_ok(ApiResult("", 42, None, "probe-1", "test-model", probe_truncated=True))
        assert "接口已响应" in app.status_var.get()
        assert "生成未验证" in app.status_var.get()
        assert "连接失败" not in app.status_var.get()
    finally:
        app.shutdown(wait=True)


def test_model_list_fetch_populates_choices_without_overwriting_manual_model(tmp_path, tk_window) -> None:
    server, thread, handler = model_server(
        response={
            "object": "list",
            "data": [
                {"id": "deepseek-flash", "object": "model", "owned_by": "deepseek"},
                {"id": "deepseek-v4-pro", "object": "model", "owned_by": "deepseek"},
            ],
        }
    )
    app = PromptSmithApp(tk_window, evidence_root=tmp_path)
    try:
        app.api_base_var.set(f"http://127.0.0.1:{server.server_port}")
        app.api_key_var.set("model-list-secret")
        app.api_model_var.set("my-manual-model")

        app.fetch_models()
        pump(tk_window, app)

        assert app.api_model_var.get() == "my-manual-model"
        assert list(app.widgets["api_model_combo"].cget("values")) == [
            "deepseek-flash",
            "deepseek-v4-pro",
        ]
        assert handler.seen["path"] == "/models"
        assert handler.seen["authorization"] == "Bearer model-list-secret"
        assert "2" in app.status_var.get()
    finally:
        app.shutdown(wait=True)
        server.shutdown()
        thread.join(timeout=2)


def test_stale_model_list_result_does_not_update_changed_connection(tk_window) -> None:
    server, thread, _handler = model_server(
        response={
            "object": "list",
            "data": [{"id": "stale-model", "object": "model", "owned_by": "deepseek"}],
        },
        delay=0.15,
    )
    app = PromptSmithApp(tk_window)
    try:
        app.api_base_var.set(f"http://127.0.0.1:{server.server_port}")
        app.api_key_var.set("old-key")
        app.api_model_var.set("manual-before")

        app.fetch_models()
        app.api_key_var.set("new-key")
        app.api_model_var.set("manual-after")
        pump(tk_window, app)

        assert app.api_model_var.get() == "manual-after"
        assert "stale-model" not in list(app.widgets["api_model_combo"].cget("values"))
        assert "配置已变化" in app.status_var.get()
    finally:
        app.shutdown(wait=True)
        server.shutdown()
        thread.join(timeout=2)


def test_stale_model_list_result_is_rejected_after_a_to_b_to_a(tk_window) -> None:
    server, thread, _handler = model_server(
        response={
            "object": "list",
            "data": [{"id": "old-a-model", "object": "model", "owned_by": "service-a"}],
        },
        delay=0.15,
    )
    app = PromptSmithApp(tk_window)
    try:
        service_a = f"http://127.0.0.1:{server.server_port}/service-a"
        app.api_base_var.set(service_a)
        app.api_key_var.set("service-a-key")
        app.fetch_models()

        app.api_base_var.set("https://service-b.example/v1")
        app.api_base_var.set(service_a)
        pump(tk_window, app)

        assert "old-a-model" not in list(app.widgets["api_model_combo"].cget("values"))
        assert "配置已变化" in app.status_var.get()
    finally:
        app.shutdown(wait=True)
        server.shutdown()
        thread.join(timeout=2)


def test_model_list_result_survives_manual_model_id_edit(tk_window) -> None:
    server, thread, _handler = model_server(
        response={
            "object": "list",
            "data": [{"id": "directory-model", "object": "model", "owned_by": "custom"}],
        },
        delay=0.12,
    )
    app = PromptSmithApp(tk_window)
    try:
        app.api_base_var.set(f"http://127.0.0.1:{server.server_port}")
        app.api_key_var.set("directory-key")
        app.api_model_var.set("manual-before")

        app.fetch_models()
        app.api_model_var.set("manual-after")
        pump(tk_window, app)

        assert app.api_model_var.get() == "manual-after"
        assert list(app.widgets["api_model_combo"].cget("values")) == ["directory-model"]
        assert "已获取 1 个" in app.status_var.get()
    finally:
        app.shutdown(wait=True)
        server.shutdown()
        thread.join(timeout=2)


def test_changing_api_host_clears_key_and_model_directory(tk_window) -> None:
    app = PromptSmithApp(tk_window)
    try:
        app.api_base_var.set("https://service-a.example/v1")
        app.api_key_var.set("service-a-key")
        app.widgets["api_model_combo"].configure(values=("service-a-model",))

        app.api_base_var.set("https://service-b.example/v1")

        assert app.api_key_var.get() == ""
        assert list(app.widgets["api_model_combo"].cget("values")) == []
    finally:
        app.shutdown(wait=True)


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ({"object": "list", "data": []}, "空模型列表"),
        ({"unexpected": []}, "响应格式"),
    ],
)
def test_model_list_ui_reports_empty_and_invalid_format(
    response: dict, expected: str, tk_window, monkeypatch
) -> None:
    server, thread, _handler = model_server(response=response)
    monkeypatch.setattr("promptsmith.ui.messagebox.showerror", lambda *args, **kwargs: None)
    app = PromptSmithApp(tk_window)
    try:
        app.api_base_var.set(f"http://127.0.0.1:{server.server_port}")
        app.api_key_var.set("fixture-key")
        app.fetch_models()
        pump(tk_window, app)
        assert expected in app.status_var.get()
    finally:
        app.shutdown(wait=True)
        server.shutdown()
        thread.join(timeout=2)


@pytest.mark.parametrize(
    ("status", "expected"),
    [(401, "鉴权失败"), (403, "鉴权失败"), (404, "不支持模型目录")],
)
def test_model_list_ui_reports_http_failures(
    status: int, expected: str, tk_window, monkeypatch
) -> None:
    server, thread = failing_model_server(status)
    monkeypatch.setattr("promptsmith.ui.messagebox.showerror", lambda *args, **kwargs: None)
    app = PromptSmithApp(tk_window)
    try:
        app.api_base_var.set(f"http://127.0.0.1:{server.server_port}")
        app.api_key_var.set("fixture-key")
        app.fetch_models()
        pump(tk_window, app)
        assert expected in app.status_var.get()
    finally:
        app.shutdown(wait=True)
        server.shutdown()
        thread.join(timeout=2)


def test_model_list_ui_reports_timeout_and_network_failure(tk_window, monkeypatch) -> None:
    messages: list[str] = []
    monkeypatch.setattr(
        "promptsmith.ui.messagebox.showerror",
        lambda _title, message, **_kwargs: messages.append(message),
    )
    app = PromptSmithApp(tk_window)
    try:
        monkeypatch.setattr(
            app,
            "_model_directory_config",
            lambda: __import__("promptsmith.api", fromlist=["ApiConfig"]).ApiConfig(
                base_url="http://127.0.0.1:9", model="fixture", api_key="key", timeout_seconds=0.05
            ),
        )
        app.fetch_models()
        pump(tk_window, app)
        assert "无法连接" in app.status_var.get() or "超时" in app.status_var.get()
        assert messages
    finally:
        app.shutdown(wait=True)


def test_context_menu_capabilities_cover_editable_and_read_only_text(tk_window) -> None:
    app = PromptSmithApp(tk_window)
    try:
        editable = app._context_menu_capabilities(app.widgets["task_text"])
        readonly = app._context_menu_capabilities(app.widgets["details_text"])

        assert editable["copy"] is True
        assert editable["cut"] is True
        assert editable["paste"] is True
        assert editable["select_all"] is True
        assert editable["undo"] is True
        assert readonly["copy"] is True
        assert readonly["cut"] is False
        assert readonly["paste"] is False
        assert readonly["select_all"] is True
        assert readonly["undo"] is False
    finally:
        app.shutdown(wait=True)


def test_read_only_requirement_list_context_menu_copies_complete_selected_text(tk_window, monkeypatch) -> None:
    monkeypatch.setattr(tk.Menu, "tk_popup", lambda *_args, **_kwargs: None)
    long_text = "面向新生提供报名入口，支持无账号报名并保留管理员导出名单。" * 8
    session = SessionState.new()
    session.requirements.append(
        {
            "item_id": "req-long",
            "field": "goal",
            "text": long_text,
            "kind": "user_fact",
            "strength": "hard",
            "scope": "完整任务",
            "source_refs": [],
            "confirmation": "confirmed",
        }
    )
    app = PromptSmithApp(tk_window, session=session)
    original_clipboard: str | None
    try:
        try:
            original_clipboard = tk_window.clipboard_get()
        except tk.TclError:
            original_clipboard = None
        tree = app.widgets["requirements_tree"]
        tree.selection_set("req-long")
        tree.focus_set()
        menu = app._show_tree_context_menu(
            type("Event", (), {"x_root": 0, "y_root": 0, "y": 0})(), tree
        )

        labels = [menu.entrycget(index, "label") for index in range(menu.index("end") + 1)]
        assert labels[0] == "复制选中内容"
        assert "剪切" not in labels
        menu.invoke(0)
        assert long_text in tk_window.clipboard_get()
    finally:
        if "original_clipboard" in locals():
            try:
                tk_window.clipboard_clear()
                if original_clipboard is not None:
                    tk_window.clipboard_append(original_clipboard)
            except tk.TclError:
                pass
        app.shutdown(wait=True)


def test_requirement_table_scrollbars_scroll_both_axes_with_long_content(tk_window) -> None:
    session = SessionState.new()
    session.requirements = [
        {
            "item_id": f"r{index}",
            "field": "deliverable",
            "text": f"第 {index} 条完整需求内容：" + ("需要可完整查看的中文文本。" * 8),
            "kind": "user_fact",
            "strength": "hard",
            "scope": "全部任务",
            "source_refs": [],
            "depends_on": [],
            "confirmation": "confirmed",
        }
        for index in range(1, 31)
    ]
    app = PromptSmithApp(tk_window, session=session)
    try:
        tk_window.deiconify()
        tk_window.geometry("1120x780")
        app.notebook.select(0)
        app.widgets["advanced_requirements_panel"]._show(True)
        tk_window.update_idletasks()
        tk_window.update()

        tree = app.widgets["requirements_tree"]
        scrollbars = [child for child in tree._promptsmith_container.winfo_children() if isinstance(child, ttk.Scrollbar)]
        assert {str(bar.cget("orient")) for bar in scrollbars} == {"horizontal", "vertical"}
        assert tree.yview()[1] < 1.0
        # Treeview does not size a column from cell text. Enlarge one column
        # to create real horizontal overflow and exercise the wired scrollbar.
        tree.column("text", width=900, stretch=False)
        tk_window.update_idletasks()
        assert tree.xview()[1] < 1.0

        tree.yview_scroll(10, "units")
        tree.xview_moveto(1.0)
        tk_window.update_idletasks()
        assert tree.yview()[0] > 0
        assert tree.xview()[0] > 0
    finally:
        app.shutdown(wait=True)
        tk_window.withdraw()


def test_requirement_editor_is_multiline_and_context_menu_paste_works(tk_window, monkeypatch) -> None:
    monkeypatch.setattr(tk.Menu, "tk_popup", lambda *_args, **_kwargs: None)
    session = SessionState.new()
    session.requirements.append(
        {
            "item_id": "req-edit",
            "field": "goal",
            "text": "原始需求文本",
            "kind": "user_fact",
            "strength": "hard",
            "scope": "完整任务",
            "source_refs": [],
            "confirmation": "confirmed",
        }
    )
    app = PromptSmithApp(tk_window, session=session)
    tree = app.widgets["requirements_tree"]
    tree.selection_set("req-edit")
    failure: list[BaseException] = []
    original_clipboard: str | None
    try:
        try:
            original_clipboard = tk_window.clipboard_get()
        except tk.TclError:
            original_clipboard = None

        def drive_dialog() -> None:
            dialogs = [
                child
                for child in tk_window.winfo_children()
                if isinstance(child, tk.Toplevel) and child.title() == "编辑需求"
            ]
            if not dialogs:
                return
            dialog = dialogs[0]
            try:
                editors = []
                pending = list(dialog.winfo_children())
                while pending:
                    child = pending.pop()
                    if isinstance(child, tk.Text):
                        editors.append(child)
                    pending.extend(child.winfo_children())
                assert editors, "编辑需求应使用可阅读的多行文本框"
                editor = editors[0]
                assert editor.bind("<Button-3>")
                editor.delete("1.0", "end")
                editor.insert("1.0", "原文\n用户选中的内容")
                editor.tag_add("sel", "2.0", "2.end")
                menu = app._show_context_menu(type("Event", (), {"x_root": 0, "y_root": 0})(), editor)
                command_indexes = {
                    menu.entrycget(index, "label"): index
                    for index in range(menu.index("end") + 1)
                    if menu.type(index) == "command"
                }
                menu.invoke(command_indexes["复制"])
                editor.update()
                assert tk_window.clipboard_get() == "用户选中的内容"
                editor.mark_set("insert", "end-1c")
                menu.invoke(command_indexes["粘贴"])
                editor.update()
                assert editor.get("1.0", "end-1c").endswith("用户选中的内容")
                save_buttons = [
                    child
                    for child in dialog.winfo_children()
                    if isinstance(child, ttk.Button) and child.cget("text") in {"保存", "保存修改"}
                ]
                if not save_buttons:
                    pending = list(dialog.winfo_children())
                    while pending:
                        child = pending.pop()
                        if isinstance(child, ttk.Button) and child.cget("text") in {"保存", "保存修改"}:
                            save_buttons.append(child)
                        pending.extend(child.winfo_children())
                assert save_buttons
                save_buttons[0].invoke()
            except BaseException as exc:
                failure.append(exc)
                dialog.destroy()

        tk_window.after(50, drive_dialog)
        app.edit_selected_requirement()
        assert not failure, str(failure[0]) if failure else ""
        assert "用户选中的内容" in app.session.requirements[0]["text"]
    finally:
        if "original_clipboard" in locals():
            try:
                tk_window.clipboard_clear()
                if original_clipboard is not None:
                    tk_window.clipboard_append(original_clipboard)
            except tk.TclError:
                pass
        app.shutdown(wait=True)


@pytest.mark.parametrize(
    ("mutate", "expected_label"),
    [
        (lambda session: None, "先输入任务"),
        (
            lambda session: session.pending_questions.append(
                {"question_id": "q1", "field": "goal", "scope": "整体", "text": "目标是什么？"}
            ),
            "回答问题",
        ),
        (
            lambda session: session.pending_proposals.append(
                {
                    "proposal_id": "p1",
                    "operation": "new",
                    "field": "goal",
                    "text": "明确目标",
                }
            ),
            "核对当前需求",
        ),
        (
            lambda session: session.open_conflicts.append(
                {"conflict_id": "c1", "description": "两项要求互相矛盾。"}
            ),
            "处理互相矛盾的要求",
        ),
        (lambda session: session.pending_review_item_ids.append("r1"), "核对当前需求"),
    ],
)
def test_primary_action_label_reflects_program_state(tk_window, mutate, expected_label: str) -> None:
    session = SessionState.new()
    if expected_label != "先输入任务":
        session.set_task("当前已有任务")
    mutate(session)
    app = PromptSmithApp(tk_window, session=session)
    try:
        # Mirror Open Session: both the stored state and editable input are visible.
        app.widgets["task_text"].insert("1.0", session.task_text)
        app.refresh()
        assert expected_label in app.primary_action_var.get()
    finally:
        app.shutdown(wait=True)


@pytest.mark.parametrize(
    ("case", "expected_action", "tab_index", "focus_widget"),
    [
        ("no_skill", "生成提示", 3, None),
        ("selected_skill", "整合所选 Agent Skill", 2, "skill_integrate_button"),
        ("final_review", "查看方案和提示", 3, None),
        ("upstream_stale", "补全模型连接", 0, "api_key_entry"),
    ],
)
def test_primary_action_navigates_to_current_delivery_work_without_model_call(
    case: str,
    expected_action: str,
    tab_index: int,
    focus_widget: str | None,
    tk_window,
    monkeypatch,
) -> None:
    from tests.test_final_delivery import confirmed_plan_session

    session = confirmed_plan_session()
    if case == "selected_skill":
        from tests.test_ui_delivery_interactions import _candidate

        _candidate_row, binding_row = _candidate()
        session.skill_state.update(
            {
                "status": "selected",
                "basis": {
                    "task_id": session.task_id,
                    "requirement_version": session.requirement_version,
                    "plan_id": session.plan["plan_id"],
                    "plan_version": session.plan["plan_version"],
                },
                "bindings": [binding_row],
            }
        )
    elif case == "final_review":
        session.final_result.update(
            {
                "revision": 1,
                "status": "draft",
                "canonical_body": "待复核的最终草稿",
                "content": {"pending_changes": []},
                "review_required_ids": ["review-fixture"],
            }
        )
    elif case == "upstream_stale":
        session.confirmed_requirements_version = None
        session.requirements[0]["confirmation"] = "review_needed"
        session.pending_review_item_ids = ["r1"]
        session.plan["status"] = "stale"
        session.final_result["status"] = "stale"

    app = PromptSmithApp(tk_window, session=session)
    try:
        calls: list[tuple[object, ...]] = []
        app.widgets["task_text"].insert("1.0", session.task_text)
        monkeypatch.setattr(app, "_submit", lambda *args: calls.append(args))
        tk_window.deiconify()
        tk_window.focus_force()
        tk_window.update_idletasks()
        tk_window.update()

        action = app._primary_action()
        assert expected_action in action.label
        assert action.kind in {"generate_final", "focus_skills", "focus_final", "focus_connection"}

        app.run_primary_action()
        tk_window.update_idletasks()
        tk_window.update()

        selected_tab = app.notebook.tabs().index(app.notebook.select())
        assert selected_tab == tab_index
        if focus_widget is not None:
            assert app.root.focus_get() == app.widgets[focus_widget]
        if case == "final_review":
            assert app.widgets["final_review_items_tree"].exists("final:review-fixture")
            assert session.final_result["review_required_ids"] == ["review-fixture"]
        if case == "upstream_stale":
            assert session.confirmed_requirements_version is None
            assert session.pending_review_item_ids == ["r1"]

        app.run_primary_action()
        tk_window.update_idletasks()
        tk_window.update()

        assert app.notebook.tabs().index(app.notebook.select()) == tab_index
        assert calls == []
        assert app.busy is False
        assert session.pending_requests == {}
    finally:
        app.shutdown(wait=True)
        tk_window.withdraw()


def test_confirmed_plan_primary_action_leads_to_no_skill_final_draft(tk_window, monkeypatch) -> None:
    from tests.test_final_delivery import confirmed_plan_session

    app = PromptSmithApp(tk_window, session=confirmed_plan_session())
    app.widgets["task_text"].insert("1.0", app.session.task_text)
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(app, "_submit", lambda *args: calls.append(args))
    try:
        tk_window.deiconify()
        tk_window.focus_force()
        tk_window.update()

        app.run_primary_action()
        tk_window.update()

        assert app.session.skill_state["status"] == "skipped"
        assert app.session.final_result["status"] == "draft"
        assert app.notebook.tabs().index(app.notebook.select()) == 3
        assert app.session.final_result["canonical_body"]
        assert calls == []
    finally:
        app.shutdown(wait=True)
        tk_window.withdraw()


def test_successful_m1_response_without_visible_business_progress_is_reported(tk_window, tmp_path) -> None:
    session = SessionState.new()
    session.set_task("整理一个已经明确的任务")
    session.requirements = [
        {
            "item_id": "r1",
            "field": "deliverable",
            "text": "一份任务说明",
            "kind": "user_decision",
            "strength": "hard",
            "scope": "整体任务",
            "source_refs": [],
            "depends_on": [],
            "confirmation": "pending",
        }
    ]
    session.analysis_basis_version = session.requirement_version
    app = PromptSmithApp(tk_window, session=session, evidence_root=tmp_path)
    try:
        app.widgets["task_text"].insert("1.0", session.task_text)
        payload = app.workflow.prepare_m1("no-visible-progress", current_date="2026-09-23")
        result = {
            "schema_version": payload["schema_version"],
            "request_id": payload["request_id"],
            "task_id": payload["task_id"],
            "base_version": payload["base_version"],
            "status": "ok",
            "error": None,
            "category": {"primary": "general", "secondary": [], "reason": "通用任务。"},
            "proposals": [],
            "conflicts": [],
            "review_item_ids": [],
            "gap_updates": [],
            "question_reopens": [],
            "gaps": [],
            "questions": [],
            "readiness": {
                "goal_identified": True,
                "deliverable_identified": True,
                "blocking_gap_ids": [],
                "reason": "现有要求没有变化。",
            },
            "next_action": "review_requirements",
            "assistant_text": "请继续核对。",
        }
        outcome = M1CallOutcome(
            raw_response=json.dumps(result, ensure_ascii=False),
            parsed=result,
            api_result=ApiResult("", 12, None, "fixture", "fixture-model"),
            evidence_dir=tmp_path,
        )

        app._analysis_ok(payload, outcome)

        assert "没有形成新进展" in app.status_var.get()
        assert app.busy is False
        assert session.requirements[0]["text"] == "一份任务说明"
    finally:
        app.shutdown(wait=True)
