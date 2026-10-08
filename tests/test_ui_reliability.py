from __future__ import annotations

import json
import threading
import time
import tkinter as tk
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import promptsmith.ui as ui_module
from promptsmith.session import SessionState
from promptsmith.storage import load_session
from promptsmith.ui import PromptSmithApp


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


def envelope(result: dict) -> bytes:
    return json.dumps(
        {
            "id": "local-reliability-fixture",
            "model": "fixture-model",
            "choices": [{"message": {"content": json.dumps(result, ensure_ascii=False)}}],
            "usage": {"total_tokens": 120},
        },
        ensure_ascii=False,
    ).encode("utf-8")


def serve(responder):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers["Content-Length"])
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            payload = json.loads(body["messages"][1]["content"])
            raw = envelope(responder(payload))
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
    return server, thread


def base_result(payload: dict) -> dict:
    return {
        "schema_version": payload["schema_version"],
        "request_id": payload["request_id"],
        "task_id": payload["task_id"],
        "base_version": payload["base_version"],
        "status": "ok",
        "error": None,
        "category": {"primary": "coding", "secondary": [], "reason": "交付物是网站。"},
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
            "reason": "可进入需求复核。",
        },
        "next_action": "review_requirements",
        "assistant_text": "请核对当前有效需求。",
    }


def m2_result(payload: dict) -> dict:
    requirement_ids = [row["item_id"] for row in payload["requirements"]]
    return {
        "schema_version": "m2.v0.1",
        "request_id": payload["request_id"],
        "task_id": payload["task_id"],
        "source_requirements_version": payload["source_requirements_version"],
        "status": "ok",
        "error": None,
        "plan": {
            "goal": {"summary": "完成课堂演示报名网站", "audience": "课堂师生", "scope": "报名主流程，不含付款"},
            "requirement_coverage": [
                {"requirement_id": item_id, "summary": f"覆盖 {item_id}", "step_ids": ["s1"], "deliverable_ids": ["d1"], "criterion_ids": ["c1"]}
                for item_id in requirement_ids
            ],
            "steps": [{"step_id": "s1", "order": 1, "title": "实现演示主流程", "purpose": "完成活动浏览和报名演示", "inputs": ["已确认需求"], "actions": ["实现页面", "检查范围"], "outputs": ["可运行网站"], "completion_criteria": ["能完成报名演示"], "depends_on_step_ids": [], "requirement_ids": requirement_ids}],
            "deliverables": [{"deliverable_id": "d1", "name": "报名网站", "description": "课堂演示版本", "step_ids": ["s1"], "requirement_ids": requirement_ids}],
            "completion_criteria": [{"criterion_id": "c1", "text": "报名流程可演示且无付款入口", "requirement_ids": requirement_ids}],
            "unresolved_items": [
                {"unresolved_id": f"u-{row['unresolved_id']}", "source_gap_id": row["unresolved_id"], "description": row["description"], "impact": "影响后续部署", "continuable_work": "先完成本地演示", "confirm_by": "部署前"}
                for row in payload["unresolved_items"]
            ],
            "suggestions": [],
            "key_work": [{"key_work_id": "k1", "title": "报名主流程", "step_ids": ["s1"], "goal": "保证演示链路完整", "inputs": ["已确认需求"], "outputs": ["可演示网站"], "requirement_ids": requirement_ids, "depends_on_key_work_ids": [], "checkpoints": ["报名成功", "无付款入口"]}],
        },
    }


def configure_local_api(app: PromptSmithApp, server: ThreadingHTTPServer) -> None:
    app.api_base_var.set(f"http://127.0.0.1:{server.server_port}")
    app.api_model_var.set("fixture-model")
    app.api_key_var.set("fixture-key")
    app.confirm_model_settings()


def test_input_error_reaches_ui_as_failure_without_erasing_state(tmp_path, tk_window, monkeypatch) -> None:
    session = SessionState.new()
    session.set_task("做一个活动报名网站")
    session.requirements = [
        {
            "item_id": "r1",
            "field": "deliverable",
            "text": "活动报名网站",
            "kind": "user_decision",
            "strength": "hard",
            "scope": "整体任务",
            "source_refs": [{"source_id": "u1", "quote": "活动报名网站"}],
            "depends_on": [],
            "confirmation": "pending",
        }
    ]
    session.gaps = [
        {
            "gap_id": "g-old",
            "field": "use_context",
            "scope": "整体任务",
            "description": "旧未知",
            "importance": "can_defer",
            "origin": "missing",
            "source_refs": [{"source_id": "u1", "quote": "活动报名网站"}],
            "depends_on": [],
        }
    ]
    session.open_conflicts = [
        {"conflict_id": "c-old", "existing_item_ids": [], "proposal_ids": [], "description": "旧冲突"}
    ]

    def responder(payload: dict) -> dict:
        result = base_result(payload)
        result.update(
            status="input_error",
            error={"code": "invalid_input", "message": "输入无法处理"},
            category={"primary": "general", "secondary": [], "reason": "输入错误"},
            readiness={
                "goal_identified": False,
                "deliverable_identified": False,
                "blocking_gap_ids": [],
                "reason": "输入错误",
            },
            next_action="pause_with_unknowns",
            assistant_text="请修改输入后重试。",
        )
        return result

    server, thread = serve(responder)
    monkeypatch.setattr(ui_module.messagebox, "showerror", lambda *args, **kwargs: None)
    app = PromptSmithApp(tk_window, session=session, evidence_root=tmp_path)
    try:
        configure_local_api(app, server)
        app.widgets["task_text"].insert("1.0", session.task_text)
        before = deepcopy(session.to_dict())

        app.start_analysis()
        pump(tk_window, app)

        assert session.requirements == before["requirements"]
        assert session.gaps == before["gaps"]
        assert session.open_conflicts == before["open_conflicts"]
        assert "分析失败" in app.status_var.get()
        assert session.api_runs[-1]["status"] == "input_error"
        assert session.api_runs[-1]["usage"] == {"total_tokens": 120}
    finally:
        app.shutdown(wait=True)
        server.shutdown()
        thread.join(timeout=2)


def test_semantic_input_error_returns_to_interview_without_failure_dialog(tmp_path, tk_window, monkeypatch) -> None:
    session = SessionState.new()
    session.set_task("讲解 JGS，面向零基础学习者")

    def responder(payload: dict) -> dict:
        result = base_result(payload)
        result.update(
            status="input_error",
            error={"code": "context_incomplete", "message": "无法确定简称含义"},
            category={"primary": "general", "secondary": [], "reason": "需要继续核对"},
            readiness={
                "goal_identified": False,
                "deliverable_identified": False,
                "blocking_gap_ids": [],
                "reason": "需要继续核对",
            },
            next_action="pause_with_unknowns",
            assistant_text="我还需要继续核对。",
        )
        return result

    server, thread = serve(responder)
    errors = []
    monkeypatch.setattr(ui_module.messagebox, "showerror", lambda title, message, **kwargs: errors.append(message))
    app = PromptSmithApp(tk_window, session=session, evidence_root=tmp_path)
    try:
        configure_local_api(app, server)
        app.widgets["task_text"].insert("1.0", session.task_text)
        app.start_analysis()
        pump(tk_window, app)

        assert not errors
        assert "分析失败" not in app.status_var.get()
        assert "已保留当前信息" in app.status_var.get()
        assert "没有形成可靠判断" in app.status_var.get()
        assert session.api_runs[-1]["recovery_mode"] == "program_recovery"
        assert session.pending_questions
    finally:
        app.shutdown(wait=True)
        server.shutdown()
        thread.join(timeout=2)


def test_selection_details_show_origin_strength_scope_source_and_change(tmp_path, tk_window) -> None:
    session = SessionState.new()
    session.set_task("做一个活动报名网站，不做付款")
    session.requirements = [
        {
            "item_id": "r1",
            "field": "constraints",
            "text": "不做付款功能，并且不得收集身份证号码。",
            "kind": "user_decision",
            "strength": "hard",
            "scope": "报名流程",
            "source_refs": [{"source_id": "u1", "quote": "不做付款"}],
            "depends_on": [],
            "confirmation": "pending",
        }
    ]
    session.pending_proposals = [
        {
            "proposal_id": "p1",
            "operation": "replace",
            "target_item_id": "r1",
            "field": "constraints",
            "text": "允许现场付款，但仍不收集身份证号码。",
            "kind": "system_suggestion",
            "strength": "preference",
            "scope": "报名流程",
            "source_refs": [],
            "depends_on": [],
            "reason": "用于展示修改前后差异。",
        }
    ]
    app = PromptSmithApp(tk_window, session=session, evidence_root=tmp_path)
    try:
        app.widgets["requirements_tree"].selection_set("r1")
        app.widgets["requirements_tree"].event_generate("<<TreeviewSelect>>")
        tk_window.update()
        requirement_detail = app.widgets["details_text"].get("1.0", "end-1c")
        assert "用户决定" in requirement_detail
        assert "硬约束" in requirement_detail
        assert "报名流程" in requirement_detail
        assert "不做付款" in requirement_detail

        app.widgets["proposals_tree"].selection_set("p1")
        app.widgets["proposals_tree"].event_generate("<<TreeviewSelect>>")
        tk_window.update()
        proposal_detail = app.widgets["details_text"].get("1.0", "end-1c")
        assert "修改前" in proposal_detail
        assert "修改后" in proposal_detail
        assert "系统建议" in proposal_detail
    finally:
        app.shutdown(wait=True)


def test_new_analysis_does_not_overwrite_unreviewed_candidates(tmp_path, tk_window, monkeypatch) -> None:
    session = SessionState.new()
    session.set_task("做一个活动报名网站")
    session.pending_proposals = [
        {
            "proposal_id": "p-draft",
            "operation": "new",
            "target_item_id": None,
            "field": "deliverable",
            "text": "活动报名网站",
            "kind": "user_decision",
            "strength": "hard",
            "scope": "整体任务",
            "source_refs": [],
            "depends_on": [],
            "reason": "待用户处理。",
        }
    ]
    before = deepcopy(session.pending_proposals)
    messages = []
    monkeypatch.setattr(ui_module.messagebox, "showerror", lambda title, message, **kwargs: messages.append(message))
    app = PromptSmithApp(tk_window, session=session, evidence_root=tmp_path)
    try:
        app.widgets["task_text"].insert("1.0", session.task_text)

        server, thread = serve(base_result)
        try:
            configure_local_api(app, server)
            app.start_analysis()
            pump(tk_window, app)
        finally:
            server.shutdown()
            thread.join(timeout=2)

        assert app.busy is False
        # Continuing no longer requires accepting/ignoring drafts first.
        # The next valid response must preserve those unreviewed candidates.
        assert len(session.pending_proposals) == 1
        for key, value in before[0].items():
            assert session.pending_proposals[0][key] == value
        assert session.api_runs[-1]["status"] == "accepted_as_candidate"
        assert not messages
    finally:
        app.shutdown(wait=True)


def test_complete_ui_path_allows_answer_before_draft_review_and_round_trips(
    tmp_path, tk_window, monkeypatch
) -> None:
    calls = 0

    def responder(payload: dict) -> dict:
        nonlocal calls
        if payload["schema_version"] == "m2.v0.1":
            return m2_result(payload)
        calls += 1
        result = base_result(payload)
        if calls == 1:
            result["proposals"] = [
                {
                    "proposal_id": "p1",
                    "operation": "new",
                    "target_item_id": None,
                    "field": "deliverable",
                    "text": "做一个活动报名网站",
                    "kind": "user_decision",
                    "strength": "hard",
                    "scope": "整体任务",
                    "source_refs": [{"source_id": payload["current_source_id"], "quote": "活动报名网站"}],
                    "depends_on": [],
                    "reason": "用户明确了交付物。",
                },
                {
                    "proposal_id": "p2",
                    "operation": "new",
                    "target_item_id": None,
                    "field": "constraints",
                    "text": "不做付款功能",
                    "kind": "user_decision",
                    "strength": "hard",
                    "scope": "功能范围",
                    "source_refs": [{"source_id": payload["current_source_id"], "quote": "不做付款"}],
                    "depends_on": [],
                    "reason": "用户明确排除付款。",
                },
            ]
            result["gaps"] = [
                {
                    "gap_id": "g1",
                    "field": "use_context",
                    "scope": "整体任务",
                    "description": "实际使用还是课堂演示尚未明确。",
                    "importance": "blocking_direction",
                    "origin": "missing",
                    "source_refs": [
                        {"source_id": payload["current_source_id"], "quote": "活动报名网站"}
                    ],
                    "depends_on": [],
                }
            ]
            result["questions"] = [
                {
                    "question_id": "q1",
                    "gap_id": "g1",
                    "field": "use_context",
                    "scope": "整体任务",
                    "text": "这是实际使用还是课堂演示？",
                    "options": ["实际使用", "课堂演示"],
                    "reason": "用途影响实现深度。",
                    "depends_on": [],
                }
            ]
            result["readiness"]["blocking_gap_ids"] = ["g1"]
            result["next_action"] = "ask"
        elif calls == 2:
            answer = payload["state"]["question_history"][-1]
            result["gap_updates"] = [
                {
                    "update_id": "gu-use-context",
                    "target_gap_id": "g1",
                    "answer_id": answer["answer_id"],
                    "action": "resolved",
                    "source_ref": {
                        "source_id": answer["answer_source_id"],
                        "quote": answer["answer_text"],
                    },
                    "remaining_description": None,
                    "reason": "用户已明确为课堂演示。",
                }
            ]
        elif calls >= 3:
            result["review_item_ids"] = [payload["state"]["requirements"][0]["item_id"]]
        return result

    server, thread = serve(responder)
    monkeypatch.setattr(ui_module.messagebox, "showerror", lambda *args, **kwargs: None)
    monkeypatch.setattr(ui_module.messagebox, "showinfo", lambda *args, **kwargs: None)
    monkeypatch.setattr(ui_module.messagebox, "askyesno", lambda *args, **kwargs: True)
    app = PromptSmithApp(tk_window, evidence_root=tmp_path / "runs")
    try:
        configure_local_api(app, server)
        app.widgets["task_text"].insert("1.0", "做一个活动报名网站，不做付款")
        app.start_analysis()
        pump(tk_window, app)

        app.widgets["questions_tree"].selection_set("q1")
        app.answer_var.set("先做课堂演示")
        app.record_question("answered")
        assert session_question_dispositions(app) == ["answered"]
        assert len(app.session.pending_proposals) == 2

        app.accept_all_proposals()
        app.start_analysis()
        pump(tk_window, app)

        target_id = next(row["item_id"] for row in app.session.requirements if row["field"] == "constraints")
        app.widgets["requirements_tree"].selection_set(target_id)
        monkeypatch.setattr(
            app,
            "_multi_text_dialog",
            lambda _title, _fields: {"text": "演示版仍不做付款"},
        )
        app.edit_selected_requirement()
        edited_id = next(row["item_id"] for row in app.session.requirements if row["field"] == "constraints")

        app.start_analysis()
        pump(tk_window, app)
        review_id = app.session.pending_review_item_ids[0]
        app.widgets["requirements_tree"].selection_set(review_id)
        app.review_selected_requirements()
        app.confirm_requirements()

        app.start_plan_generation()
        pump(tk_window, app)
        assert app.session.plan["status"] == "draft"
        assert app.notebook.index(app.notebook.select()) == 1
        goal = app.widgets["plan_goal_text"]
        goal.delete("1.0", "end")
        goal.insert("1.0", "完成一个更清楚的课堂演示报名网站")
        goal.edit_modified(True)
        app.save_plan_goal()
        assert app.session.plan["modified"] is True
        app.widgets["plan_key_work_tree"].selection_set("k1")
        app.review_selected_key_work()
        app.confirm_plan()
        assert app.session.plan["status"] == "confirmed"

        save_path = tmp_path / "complete-ui-path.json"
        app.session_path = save_path
        app.save()
        before = app.session.to_dict()
        assert before["confirmed_requirements_version"] == before["requirement_version"]
        assert before["plan"]["confirmed_plan_version"] == before["plan"]["plan_version"]
        assert any(row["item_id"] == edited_id for row in before["requirements"])

        monkeypatch.setattr(ui_module.filedialog, "askopenfilename", lambda **kwargs: str(save_path))
        app.open_session()
        assert app.session.to_dict() == before
        assert app.session.confirmed_requirements_version == app.session.requirement_version
        assert app.session.plan["status"] == "confirmed"

        # Return to M1, actually change one requirement, and recover by regenerating M2.
        old_plan_id = app.session.plan["plan_id"]
        app.go_to_requirements()
        app.widgets["requirements_tree"].selection_set(edited_id)
        monkeypatch.setattr(
            app,
            "_multi_text_dialog",
            lambda _title, _fields: {"text": "课堂演示版不做付款，也不收集身份证"},
        )
        app.edit_selected_requirement()
        assert app.session.plan["status"] == "stale"
        app.start_analysis()
        pump(tk_window, app)
        review_id = app.session.pending_review_item_ids[0]
        app.widgets["requirements_tree"].selection_set(review_id)
        app.review_selected_requirements()
        app.confirm_requirements()
        app.start_plan_generation()
        pump(tk_window, app)
        assert app.session.plan["plan_id"] != old_plan_id
        assert app.session.plan_archive[-1]["plan_id"] == old_plan_id
    finally:
        app.shutdown(wait=True)
        server.shutdown()
        thread.join(timeout=2)


def session_question_dispositions(app: PromptSmithApp) -> list[str]:
    return [row["disposition"] for row in app.session.question_history]
