from __future__ import annotations

import json
import threading
import time
import tkinter as tk
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from promptsmith.m1 import M1Assets, M1ValidationError, apply_m1_response, build_m1_input, parse_m1_response
from promptsmith.m2 import apply_m2_response
from promptsmith.session import SessionState, SessionStateError
from promptsmith.ui import PromptSmithApp
from test_m2 import parse_for


@pytest.fixture
def tk_window(tk_root):
    window = tk.Toplevel(tk_root)
    window.withdraw()
    yield window
    window.destroy()


def _checked_m1(session: SessionState, request_id: str, **changes):
    payload = build_m1_input(session, request_id, current_date="2026-09-23")
    result = {
        **{key: payload[key] for key in ("schema_version", "request_id", "task_id", "base_version")},
        "status": "ok",
        "error": None,
        "category": {"primary": "writing", "secondary": [], "reason": "写作任务。"},
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
            "reason": "请核对需求。",
        },
        "next_action": "review_requirements",
        "assistant_text": "请核对需求。",
    }
    result.update(changes)
    parsed = parse_m1_response(
        json.dumps(result, ensure_ascii=False), payload, M1Assets.load().output_schema
    )
    apply_m1_response(session, payload, parsed)
    return payload, result


def _resolved_audience_session() -> SessionState:
    session = SessionState.new()
    session.set_task("写一份活动邀请邮件，收件对象还不确定。")
    gap = {
        "gap_id": "g-audience",
        "field": "audience",
        "scope": "整体任务",
        "description": "收件对象尚未明确。",
        "importance": "blocking_direction",
        "origin": "missing",
        "source_refs": [],
        "depends_on": [],
    }
    question = {
        "question_id": "q-audience",
        "gap_id": "g-audience",
        "field": "audience",
        "scope": "整体任务",
        "text": "这封邀请邮件准备发给谁？",
        "options": [],
        "reason": "受众影响语气和内容。",
        "depends_on": [],
    }
    _checked_m1(
        session,
        "first",
        gaps=[gap],
        questions=[question],
        readiness={
            "goal_identified": True,
            "deliverable_identified": True,
            "blocking_gap_ids": ["g-audience"],
            "reason": "受众尚未明确。",
        },
        next_action="ask",
    )
    session.record_question("q-audience", "answered", "发给大一新生")
    answer = session.question_history[-1]
    _checked_m1(
        session,
        "resolve",
        gap_updates=[
            {
                "update_id": "gu1",
                "target_gap_id": "g-audience",
                "answer_id": answer["answer_id"],
                "action": "resolved",
                "source_ref": {
                    "source_id": answer["answer_source_id"],
                    "quote": answer["answer_text"],
                },
                "remaining_description": None,
                "reason": "用户明确了收件对象。",
            }
        ],
    )
    assert not session.gaps
    applied = next(row for row in session.question_history if row["answer_id"] == answer["answer_id"])
    assert applied["assessment_status"] == "applied"
    return session


def test_primary_button_routes_pending_answer_to_analysis(tk_window, monkeypatch) -> None:
    session = SessionState.new()
    session.set_task("写一份活动邀请邮件")
    session.requirements = [
        {
            "item_id": "r1",
            "field": "deliverable",
            "text": "一份邀请邮件",
            "kind": "user_decision",
            "strength": "hard",
            "scope": "整体任务",
            "source_refs": [],
            "depends_on": [],
            "confirmation": "pending",
        }
    ]
    session.question_history = [
        {
            "question_id": "q1",
            "gap_id": "g1",
            "field": "audience",
            "scope": "整体任务",
            "text": "发给谁？",
            "disposition": "answered",
            "answer_id": "a1",
            "answer_source_id": session.current_source_id,
            "answer_text": "大一新生",
            "state_version": session.requirement_version,
            "recorded_source_count": len(session.sources),
            "assessment_status": "pending",
        }
    ]
    session.analysis_basis_version = session.requirement_version
    app = PromptSmithApp(tk_window, session=session)
    calls = {"analysis": 0, "confirm": 0}
    try:
        app.api_base_var.set("http://127.0.0.1:9000")
        app.api_model_var.set("fixture-model")
        app.api_key_var.set("fixture-key")
        app.confirm_model_settings()
        app.widgets["task_text"].insert("1.0", session.task_text)
        monkeypatch.setattr(app, "start_analysis", lambda: calls.__setitem__("analysis", calls["analysis"] + 1))
        monkeypatch.setattr(app, "confirm_requirements", lambda: calls.__setitem__("confirm", calls["confirm"] + 1))
        app.refresh()

        app.widgets["analyze_button"].invoke()

        assert app.primary_action_var.get() == "继续整理回答"
        assert calls == {"analysis": 1, "confirm": 0}
    finally:
        app.shutdown(wait=True)


def test_resolved_question_cannot_be_reasked_with_new_ids_without_new_evidence() -> None:
    session = _resolved_audience_session()
    payload = build_m1_input(session, "reask", current_date="2026-09-23")
    result = {
        **{key: payload[key] for key in ("schema_version", "request_id", "task_id", "base_version")},
        "status": "ok",
        "error": None,
        "category": {"primary": "writing", "secondary": [], "reason": "写作任务。"},
        "proposals": [],
        "conflicts": [],
        "review_item_ids": [],
        "gap_updates": [],
        "question_reopens": [],
        "gaps": [
            {
                "gap_id": "g-audience-new",
                "field": "audience",
                "scope": "整体任务",
                "description": "收件对象尚未明确。",
                "importance": "blocking_direction",
                "origin": "missing",
                "source_refs": [],
                "depends_on": [],
            }
        ],
        "questions": [
            {
                "question_id": "q-audience-new",
                "gap_id": "g-audience-new",
                "field": "audience",
                "scope": "整体任务",
                "text": "这封邀请邮件准备发给谁？",
                "options": [],
                "reason": "受众影响语气和内容。",
                "depends_on": [],
            }
        ],
        "readiness": {
            "goal_identified": True,
            "deliverable_identified": True,
            "blocking_gap_ids": ["g-audience-new"],
            "reason": "再次询问受众。",
        },
        "next_action": "ask",
        "assistant_text": "请再次说明受众。",
    }

    with pytest.raises(M1ValidationError, match="已解决|重复"):
        parse_m1_response(
            json.dumps(result, ensure_ascii=False), payload, M1Assets.load().output_schema
        )


def test_incomplete_new_plan_step_blocks_confirmation() -> None:
    from test_m2 import confirmed_session

    session = confirmed_session(with_unknown=False)
    payload, parsed = parse_for(session)
    apply_m2_response(session, payload, parsed)
    session.add_plan_step("补充审阅", "核对交付内容")
    session.mark_key_work_reviewed(list(session.plan["pending_key_work_review_ids"]))

    with pytest.raises(SessionStateError, match="步骤.*行动|输出|完成标准"):
        session.confirm_plan()


def test_full_step_edit_persists_actions_outputs_criteria_and_links(tmp_path) -> None:
    from promptsmith.storage import load_session, save_session
    from test_m2 import confirmed_session

    session = confirmed_session(with_unknown=False)
    payload, parsed = parse_for(session)
    apply_m2_response(session, payload, parsed)
    added = session.add_plan_step("补充审阅", "核对交付内容")

    session.edit_plan_step(
        added,
        title="补充审阅",
        purpose="核对交付内容",
        inputs=["方案草稿"],
        actions=["逐项核对需求覆盖"],
        outputs=["审阅记录"],
        completion_criteria=["所有硬约束均有对应结果"],
        depends_on_step_ids=["s1"],
        requirement_ids=["r1"],
    )

    path = save_session(session, tmp_path / "full-step.json")
    reopened = load_session(path)
    step = next(row for row in reopened.plan["content"]["steps"] if row["step_id"] == added)
    assert step["actions"] == ["逐项核对需求覆盖"]
    assert step["outputs"] == ["审阅记录"]
    assert step["completion_criteria"] == ["所有硬约束均有对应结果"]
    assert step["depends_on_step_ids"] == ["s1"]
    assert step["requirement_ids"] == ["r1"]


def test_step_editor_is_one_multifield_dialog_with_context_menu(tk_window, monkeypatch) -> None:
    from test_m2 import confirmed_session

    session = confirmed_session(with_unknown=False)
    payload, parsed = parse_for(session)
    apply_m2_response(session, payload, parsed)
    app = PromptSmithApp(tk_window, session=session)
    observations: list[dict] = []
    callback_errors: list[BaseException] = []
    try:
        app.notebook.select(1)
        app.refresh()
        app.widgets["plan_steps_tree"].selection_set("s1")

        def inspect_and_cancel() -> None:
            dialogs = [child for child in tk_window.winfo_children() if isinstance(child, tk.Toplevel)]
            dialog = dialogs[0] if dialogs else None
            try:
                assert len(dialogs) == 1
                descendants = []
                pending = list(dialog.winfo_children())
                while pending:
                    child = pending.pop()
                    descendants.append(child)
                    pending.extend(child.winfo_children())
                text_widgets = [child for child in descendants if isinstance(child, tk.Text)]
                listboxes = [child for child in descendants if isinstance(child, tk.Listbox)]
                observations.append(
                    {
                        "text_count": len(text_widgets),
                        "listbox_count": len(listboxes),
                        "all_text_bound": all(bool(widget.bind("<Button-3>")) for widget in text_widgets),
                    }
                )
            except BaseException as exc:
                callback_errors.append(exc)
            finally:
                if dialog is not None and dialog.winfo_exists():
                    dialog.destroy()

        tk_window.after(100, inspect_and_cancel)
        app.edit_selected_plan_step()

        assert not callback_errors
        assert observations == [{"text_count": 6, "listbox_count": 2, "all_text_bound": True}]
    finally:
        app.shutdown(wait=True)


def test_full_key_work_edit_persists_links_and_checkpoints(tmp_path) -> None:
    from promptsmith.storage import load_session, save_session
    from test_m2 import confirmed_session

    session = confirmed_session(with_unknown=False)
    payload, parsed = parse_for(session)
    apply_m2_response(session, payload, parsed)

    session.edit_plan_section(
        "key_work",
        "k1",
        {
            "title": "报名主流程复核",
            "goal": "确认课堂演示可以完整进行",
            "inputs": ["已确认需求", "方案草稿"],
            "outputs": ["可演示网站", "复核记录"],
            "checkpoints": ["报名成功", "没有付款入口"],
            "step_ids": ["s1"],
            "requirement_ids": ["r1", "r2"],
            "depends_on_key_work_ids": [],
        },
    )

    path = save_session(session, tmp_path / "key-work.json")
    reopened = load_session(path)
    row = reopened.plan["content"]["key_work"][0]
    assert row["inputs"] == ["已确认需求", "方案草稿"]
    assert row["outputs"] == ["可演示网站", "复核记录"]
    assert row["checkpoints"] == ["报名成功", "没有付款入口"]
    assert row["step_ids"] == ["s1"]
    assert row["requirement_ids"] == ["r1", "r2"]
    assert reopened.plan["pending_key_work_review_ids"] == ["k1"]


def test_selecting_step_shows_complete_step_details(tk_window) -> None:
    from test_m2 import confirmed_session

    session = confirmed_session(with_unknown=False)
    payload, parsed = parse_for(session)
    apply_m2_response(session, payload, parsed)
    app = PromptSmithApp(tk_window, session=session)
    try:
        app.notebook.select(1)
        app.refresh()
        app.widgets["plan_steps_tree"].selection_set("s1")
        app.widgets["plan_steps_tree"].event_generate("<<TreeviewSelect>>")
        tk_window.update()

        text = app.widgets["plan_overview_text"].get("1.0", "end-1c")
        assert "实现并检查报名流程" in text
        assert "实现活动列表" in text
        assert "可运行网站" in text
        assert "能够完成一次报名演示" in text
        assert "需求关联" in text
    finally:
        app.shutdown(wait=True)


def test_main_page_scroll_keeps_details_reachable_at_150_percent_scaling(tk_window) -> None:
    app = PromptSmithApp(tk_window)
    try:
        old_scaling = float(tk_window.tk.call("tk", "scaling"))
        tk_window.deiconify()
        tk_window.tk.call("tk", "scaling", 2.0)
        tk_window.geometry("1120x780")
        tk_window.update_idletasks()
        tk_window.update()

        canvas = app.widgets["requirements_page_canvas"]
        details = app.widgets["details_text"]
        app.widgets["advanced_requirements_panel"]._show(True)
        canvas.update_idletasks()
        canvas.yview_moveto(1.0)
        tk_window.update_idletasks()
        tk_window.update()

        canvas_top = canvas.winfo_rooty()
        canvas_bottom = canvas_top + canvas.winfo_height()
        details_top = details.winfo_rooty()
        details_bottom = details_top + details.winfo_height()
        assert details.winfo_ismapped()
        assert details_top >= canvas_top
        assert details_bottom <= canvas_bottom, {
            "root": (tk_window.winfo_width(), tk_window.winfo_height(), tk_window.winfo_ismapped()),
            "canvas": (canvas.winfo_width(), canvas.winfo_height(), canvas.winfo_rooty(), canvas.cget("scrollregion"), canvas.yview()),
            "details": (details.winfo_width(), details.winfo_height(), details.winfo_rooty()),
        }
        assert float(canvas.yview()[0]) > 0
    finally:
        app.shutdown(wait=True)
        tk_window.tk.call("tk", "scaling", old_scaling)


def test_model_list_a_to_b_to_a_rejects_old_generation(tk_window) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            time.sleep(0.15)
            raw = json.dumps({"data": [{"id": "stale-model"}]}).encode("utf-8")
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
    app = PromptSmithApp(tk_window)
    try:
        original = f"http://127.0.0.1:{server.server_port}"
        app.api_base_var.set(original)
        app.api_key_var.set("key-a")
        app.fetch_models()
        app.api_base_var.set("http://127.0.0.1:9")
        app.api_base_var.set(original)
        deadline = time.time() + 3
        while app.busy and time.time() < deadline:
            tk_window.update()
            time.sleep(0.01)

        assert "stale-model" not in list(app.widgets["api_model_combo"].cget("values"))
        assert "配置已变化" in app.status_var.get()
    finally:
        app.shutdown(wait=True)
        server.shutdown()
        thread.join(timeout=2)


def test_ui_exposes_service_and_protocol_selectors_and_uses_selected_adapter(tk_window) -> None:
    from promptsmith.api import ANTHROPIC_MESSAGES_PROTOCOL, AnthropicMessagesClient

    app = PromptSmithApp(tk_window)
    try:
        assert str(app.widgets["provider_combo"].cget("state")) == "normal"
        assert str(app.widgets["protocol_combo"].cget("state")) == "readonly"
        assert set(app.widgets["protocol_combo"].cget("values")) == {
            "OpenAI Chat Completions",
            "OpenAI Responses",
            "Anthropic Messages",
        }

        app.provider_var.set("自定义服务 A")
        app.protocol_var.set("Anthropic Messages")
        app.api_base_var.set("http://127.0.0.1:9000/v1")
        app.api_model_var.set("unlisted-custom-model")
        app.api_key_var.set("custom-key")
        app.confirm_model_settings()
        config = app._api_config()
        client = app._client(config)

        assert config.provider == "自定义服务 A"
        assert config.protocol == ANTHROPIC_MESSAGES_PROTOCOL
        assert config.model == "unlisted-custom-model"
        assert isinstance(client, AnthropicMessagesClient)
    finally:
        app.shutdown(wait=True)


def test_switching_service_clears_key_and_model_directory_values(tk_window) -> None:
    app = PromptSmithApp(tk_window)
    try:
        app.api_key_var.set("service-a-secret")
        app.widgets["api_model_combo"].configure(values=("service-a-model",))

        app.provider_var.set("OpenAI")
        tk_window.update()

        assert app.api_key_var.get() == ""
        assert list(app.widgets["api_model_combo"].cget("values")) == []
    finally:
        app.shutdown(wait=True)
