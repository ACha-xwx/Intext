"""Real Tk controls + local HTTP, with deliberately synthetic model content.

These checks exercise production request construction, protocol decoding, schema,
semantic validation, state application and export. They are not provider tests.
"""
from __future__ import annotations

from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import tkinter as tk
from tkinter import ttk

import pytest

from promptsmith.storage import load_session
from promptsmith.ui import PromptSmithApp
from tests.test_ui_reliability import base_result, envelope, pump


TASK = "讲一下JGS"
BACKGROUND = "数值分析领域，学生学习讲义"
CORRECTION = "JGS 在这里指 Jacobi 与 Gauss–Seidel 两种迭代方法的比较"
NOTICE = "写一则给大一学生的摄影社招新通知，300字以内，周六下午两点在活动中心集合，报名联系社长，语气自然。"


def proposal(pid, field, text, source_id, quote, *, scope="当前任务", kind="user_decision", strength="hard"):
    return {
        "proposal_id": pid, "operation": "new", "target_item_id": None,
        "field": field, "text": text, "kind": kind, "strength": strength, "scope": scope,
        "source_refs": [{"source_id": source_id, "quote": quote}] if source_id else [],
        "depends_on": [], "reason": "按用户提供的内容整理；测试用合成返回。",
    }


def gap(gid, field, scope, description, *, importance="blocking_direction"):
    return {"gap_id": gid, "field": field, "scope": scope, "description": description,
            "importance": importance, "origin": "missing", "source_refs": [], "depends_on": []}


def question(qid, item, text):
    return {"question_id": qid, "gap_id": item["gap_id"], "field": item["field"],
            "scope": item["scope"], "text": text, "options": [],
            "reason": "需要明确当前讲解对象。", "depends_on": []}


def resolve_pending(payload):
    return [{"update_id": f"update-{row['answer_id']}", "target_gap_id": row["gap_id"],
             "answer_id": row["answer_id"], "action": "resolved",
             "source_ref": {"source_id": row["answer_source_id"], "quote": row["answer_text"]},
             "remaining_description": None, "reason": "当前回答已提供对应信息；合成案例判定。"}
            for row in payload["state"]["question_history"]
            if row.get("assessment_status") == "pending" and row.get("gap_id")]


def make_plan(payload):
    jgs = "JGS" in payload["task"]["text"]
    unknown = bool(payload["unresolved_items"])
    title = "学生学习讲义结构" if jgs else "摄影社招新通知写作方案"
    audience = "学生" if jgs else "大一学生"
    actions = (["整理已知的学习背景与讲义目标", "安排概念、例子和比较栏目", "术语没有确定时只保留相关栏目的说明，不编造具体算法"]
               if jgs else ["把集合时间、地点、报名联系人写入通知", "调整语气自然并将篇幅控制在300字以内"])
    ids = [row["item_id"] for row in payload["requirements"]]
    scope = "先整理已知部分，具体术语的讲解等用户说明后再完善" if unknown else "按当前明确的对象和约束整理内容"
    return {
        "schema_version": "m2.v0.1", "request_id": payload["request_id"], "task_id": payload["task_id"],
        "source_requirements_version": payload["source_requirements_version"], "status": "ok", "error": None,
        "plan": {
            "goal": {"summary": title, "audience": audience, "scope": scope},
            "requirement_coverage": [{"requirement_id": item, "summary": "落实当前要求", "step_ids": ["s1"], "deliverable_ids": ["d1"], "criterion_ids": ["c1"]} for item in ids],
            "steps": [{"step_id": "s1", "order": 1, "title": "组织内容", "purpose": "形成便于核对的内容结构", "inputs": ["当前用户要求"], "actions": actions,
                       "outputs": [title], "completion_criteria": ["来源明确，未知内容有清楚的影响说明"], "depends_on_step_ids": [], "requirement_ids": ids}],
            "deliverables": [{"deliverable_id": "d1", "name": title, "description": "可编辑的内容结构与任务提示", "step_ids": ["s1"], "requirement_ids": ids}],
            "completion_criteria": [{"criterion_id": "c1", "text": "逐项承接用户要求，不把未知或猜测当成事实", "requirement_ids": ids}],
            "unresolved_items": [{"unresolved_id": f"u-{row['unresolved_id']}", "source_gap_id": row["unresolved_id"], "description": row["description"],
                                  "impact": "影响相关术语的具体解释和例子", "continuable_work": "先整理讲义结构和已经明确的学习背景", "confirm_by": "开始具体术语讲解前"}
                                 for row in payload["unresolved_items"]],
            "suggestions": [],
            "key_work": [{"key_work_id": "k1", "title": "组织写作结构", "step_ids": ["s1"], "goal": "让内容符合受众和用途", "inputs": ["当前用户要求"],
                          "outputs": [title], "requirement_ids": ids, "depends_on_key_work_ids": [], "checkpoints": ["约束有来源", "未知有影响说明"]}],
        },
    }


class Scenario:
    def __init__(self, name):
        self.name = name
        self.received = []
        self.m1_count = 0

    def respond(self, payload):
        self.received.append(deepcopy(payload))
        if payload["schema_version"].startswith("m2."):
            return make_plan(payload)
        self.m1_count += 1
        response = base_result(payload)
        source_id = payload["current_source_id"]
        if self.name == "writing":
            response["category"] = {"primary": "writing", "secondary": [], "reason": "社团通知写作。"}
            response["proposals"] = [proposal("p-notice", "deliverable", NOTICE, source_id, NOTICE)]
            response["assistant_text"] = "已按你的说明整理通知要求，可以一起核对。"
            return response
        response["category"] = {"primary": "learning", "secondary": [], "reason": "学习讲解。"}
        if self.m1_count == 1:
            response["proposals"] = [proposal("p-deliverable", "deliverable", "关于JGS的讲解材料", source_id, TASK)]
            response["gaps"] = [gap("g-domain", "context", "所指领域", "JGS 所在领域未说明"), gap("g-audience", "audience", "讲解受众", "讲解给谁学习尚未说明")]
            response["questions"] = [question("q-domain", response["gaps"][0], "JGS 属于哪个领域？"), question("q-audience", response["gaps"][1], "这份讲解主要给谁学习？")]
            response["readiness"]["blocking_gap_ids"] = ["g-domain", "g-audience"]
            response["next_action"] = "ask"
            response["assistant_text"] = "先补充所属领域和学习对象，就能缩小讲解范围。"
        elif self.m1_count == 2:
            response["gap_updates"] = resolve_pending(payload)
            response["proposals"] = [proposal("p-domain", "context", "属于数值分析领域", source_id, "数值分析领域"), proposal("p-audience", "audience", "学生学习讲义", source_id, "学生学习讲义")]
            term = gap("g-term", "goal", "术语所指", "JGS 的具体含义还没有确定")
            response["gaps"] = [term]
            response["questions"] = [question("q-term", term, "你这里说的 JGS 具体指什么？")]
            response["readiness"]["blocking_gap_ids"] = ["g-term"]
            response["next_action"] = "ask"
            response["assistant_text"] = "已记录数值分析和学生学习讲义，还需说明术语所指。"
            if self.name == "guess":
                inferred = proposal("p-guess", "goal", "比较 Jacobi 与 Gauss–Seidel 这两种迭代方法", source_id, "数值分析领域", scope="术语所指", kind="pending_interpretation", strength="unspecified")
                inferred["interpretation_for"] = {"gap_id": "g-term", "question_id": "q-term", "reason": "你提到数值分析，这是一种可能解释，需要你核对。"}
                response["proposals"].extend([inferred, proposal("p-budget", "constraints", "可以考虑购买100元参考资料", None, None, kind="system_suggestion", strength="unspecified")])
        else:
            response["gap_updates"] = resolve_pending(payload)
            text = next(row["text"] for row in payload["sources"] if row["source_id"] == source_id)
            response["proposals"] = [proposal("p-meaning", "goal", text, source_id, text, scope="术语所指")]
            response["assistant_text"] = "已按你的补充整理讲解对象，请核对这份要求。"
        return response


@pytest.fixture
def scenario_app(tk_root, tmp_path, monkeypatch):
    active = []

    def create(name="jgs"):
        scenario = Scenario(name)
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
                payload = json.loads(body["messages"][1]["content"])
                raw = envelope(scenario.respond(payload))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            def log_message(self, *_args):
                return
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        window = tk.Toplevel(tk_root)
        window.withdraw()
        app = PromptSmithApp(window, evidence_root=tmp_path / name / "calls")
        app.api_base_var.set(f"http://127.0.0.1:{server.server_port}")
        app.api_model_var.set("synthetic-guided-fixture")
        app.api_key_var.set("offline-test-value")
        app.confirm_model_settings()
        app.probe_errors = []
        monkeypatch.setattr("tkinter.messagebox.showerror", lambda title, message, **_kwargs: app.probe_errors.append({"title": title, "message": message}))
        active.append((app, server, thread))
        return app, scenario

    yield create
    for app, server, thread in active:
        app.shutdown(wait=True)
        app.root.destroy()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def click_primary(app):
    app.widgets["analyze_button"].invoke()
    pump(app.root, app, timeout=8)
    assert not app.probe_errors, app.probe_errors


def get_button(parent, text):
    for child in parent.winfo_children():
        if isinstance(child, (tk.Button, ttk.Button)) and child.cget("text") == text:
            return child
        found = get_button(child, text)
        if found is not None:
            return found
    return None


def state_evidence(app, scenario, path, label):
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{label}.session.json").write_text(json.dumps(app.session.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "evidence_kind": "offline_real_tk_controls_local_http_synthetic_responses",
        "real_provider_calls": 0,
        "local_requests": len(scenario.received),
        "task_text": app.session.task_text,
        "primary_label": app.primary_action_var.get(),
        "guidance": app.guidance_var.get(),
        "page": app.notebook.index(app.notebook.select()),
        "gaps": deepcopy(app.session.gaps),
        "question_history": deepcopy(app.session.question_history),
        "plan_status": app.session.plan.get("status"),
        "confirmed_plan_version": app.session.plan.get("confirmed_plan_version"),
        "final_status": app.session.final_result.get("status"),
        "errors": app.probe_errors,
    }
    (path / f"{label}.summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def go_to_term_question(app, scenario):
    app.widgets["task_text"].insert("1.0", TASK)
    app.refresh()
    click_primary(app)
    assert len(app.session.pending_questions) == 2
    initial_candidates = {row["proposal_id"] for row in app.session.pending_proposals}
    app.widgets["answer_entry"].insert(0, BACKGROUND)
    click_primary(app)
    assert len(scenario.received) == 2
    assert len(scenario.received[1]["state"]["question_history"]) == 2
    assert all(row["assessment_status"] == "pending" for row in scenario.received[1]["state"]["question_history"])
    assert initial_candidates <= {row["proposal_id"] for row in app.session.pending_proposals}
    assert [q["question_id"] for q in app.session.pending_questions] == ["q-term"]


def test_jgs_skip_then_same_region_supplement_closes_gap_without_rewriting_task(scenario_app, tmp_path):
    app, scenario = scenario_app()
    go_to_term_question(app, scenario)
    state_evidence(app, scenario, tmp_path, "before_skip")
    app.widgets["skip_question_button"].invoke()
    assert not app.session.pending_questions
    assert app._primary_action().kind == "focus_question"
    assert "确认需求" not in app.primary_action_var.get()
    history = deepcopy(app.session.question_history)
    state_evidence(app, scenario, tmp_path, "after_skip")
    app.widgets["answer_entry"].insert(0, CORRECTION)
    click_primary(app)
    assert len(scenario.received) == 3
    pending = [row for row in scenario.received[-1]["state"]["question_history"] if row.get("assessment_status") == "pending"]
    assert len(pending) == 1 and pending[0]["gap_id"] == "g-term"
    assert app.session.question_history[:len(history)] == history
    assert app.session.task_text == TASK
    assert not app.session.gaps
    assert app.primary_action_var.get() == "确认需求并生成方案"
    click_primary(app)
    assert app.session.plan["status"] == "draft"
    click_primary(app)
    assert app.session.plan["status"] == "confirmed"
    assert app.session.final_result["canonical_body"]
    assert app.session.skill_state["status"] == "skipped"
    state_evidence(app, scenario, tmp_path, "resolved_final")


def test_jgs_skip_then_one_draft_click_produces_copyable_exportable_reopenable_result(scenario_app, tmp_path, monkeypatch):
    app, scenario = scenario_app()
    go_to_term_question(app, scenario)
    app.widgets["skip_question_button"].invoke()
    state_evidence(app, scenario, tmp_path, "before_draft_click")
    assert "JGS" in app.draft_explanation_var.get()
    button = app.widgets["draft_continue_button"]
    assert str(button["state"]) == "normal"
    button.invoke()
    pump(app.root, app, timeout=8)
    assert not app.probe_errors, app.probe_errors
    assert len(scenario.received) == 3
    assert scenario.received[-1]["schema_version"] == "m2.v0.1"
    assert app.session.plan["status"] == "draft"
    assert app.session.plan["confirmed_plan_version"] is None
    assert app.session.final_result["status"] == "draft"
    assert app.session.final_result["content"]["plan_review_pending"] is True
    assert app.notebook.index(app.notebook.select()) == 3
    assert "方案尚未核对" in app.session.final_result["canonical_body"]
    get_button(app.widgets["result_simple_controls"], "复制提示").invoke()
    assert "JGS 的具体含义还没有确定" in app.root.clipboard_get()
    monkeypatch.setattr("tkinter.simpledialog.askstring", lambda *_args, **_kwargs: "请优先用直观的结构说明。")
    app.add_final_note()
    exported = tmp_path / "draft_result.md"
    monkeypatch.setattr("tkinter.filedialog.asksaveasfilename", lambda **_kwargs: str(exported))
    get_button(app.widgets["result_simple_controls"], "导出方案和提示").invoke()
    assert exported.is_file(), app.probe_errors
    assert "请优先用直观的结构说明" in exported.read_text(encoding="utf-8")
    saved = tmp_path / "draft_session.json"
    monkeypatch.setattr("tkinter.filedialog.asksaveasfilename", lambda **_kwargs: str(saved))
    get_button(app.widgets["result_simple_controls"], "保存会话").invoke()
    before = app.session.to_dict()
    assert load_session(saved).to_dict() == before
    monkeypatch.setattr("tkinter.filedialog.askopenfilename", lambda **_kwargs: str(saved))
    app.open_session()
    assert app.session.to_dict() == before
    assert app.session.current_draft_authorization()
    assert app.session.gaps[0]["importance"] == "blocking_direction"
    state_evidence(app, scenario, tmp_path, "after_draft_export_reopen")


@pytest.mark.parametrize("decision", ["accept", "correct"])
def test_deciding_interpretation_reclaims_space_for_requirements(scenario_app, decision):
    app, scenario = scenario_app("guess")
    app.root.deiconify()
    app.root.geometry("1100x650")
    go_to_term_question(app, scenario)
    app.root.update()
    question_panel = app.widgets["question_panel"]
    before = question_panel.winfo_reqheight()
    explanation_height = app.widgets["interpretation_panel"].winfo_reqheight()
    answer_y_before = app.widgets["answer_entry"].winfo_y()
    context = app.question_context_var.get()
    assert explanation_height > 0
    assert "AI 可能的理解" in context
    assert "Jacobi" in context
    assert "数值分析" in context
    button = get_button(question_panel, "是这个意思" if decision == "accept" else "我来说明")
    button.invoke()
    app.root.update()
    assert "AI 可能的理解" not in app.question_context_var.get()
    assert app.widgets["answer_entry"].winfo_y() <= answer_y_before
    assert question_panel.winfo_reqheight() < before
    assert app.widgets["answer_entry"].winfo_ismapped()
    assert app.widgets["preview_panel"].winfo_ismapped()
    assert not app.probe_errors


@pytest.mark.parametrize("decision", ["accept", "correct"])
def test_explicit_guess_choice_leaves_unrelated_budget_unadopted(scenario_app, tmp_path, decision):
    app, scenario = scenario_app("guess")
    go_to_term_question(app, scenario)
    state_evidence(app, scenario, tmp_path, "before_guess_choice")
    if decision == "accept":
        button = get_button(app.widgets["interpretation_panel"], "是这个意思")
        assert button is not None
        button.invoke()
        assert len(scenario.received) == 2
        assert not app.session.gaps
        assert app.session.interpretation_history[-1]["decision"] == "accepted"
        assert len(app.session.requirements) == 1
        assert app.session.requirements[0]["kind"] == "user_decision"
    else:
        button = get_button(app.widgets["question_panel"], "我来说明")
        assert button is not None
        button.invoke()
        assert app.session.interpretation_history[-1]["decision"] == "rejected"
        assert not any(row.get("interpretation_for") for row in app.session.pending_proposals)
        app.widgets["answer_entry"].insert(0, "不是这两种方法；JGS是老师为讲义中的一种练习流程取的代号")
        click_primary(app)
        assert not app.session.gaps
        assert not any("Jacobi" in row["text"] for row in app.session.requirements)
    assert any(row["proposal_id"] == "p-budget" for row in app.session.pending_proposals)
    assert not any("100元" in row["text"] for row in app.session.requirements)
    assert not app.probe_errors
    state_evidence(app, scenario, tmp_path, f"guess_{decision}")


def test_complete_writing_task_follows_default_no_skill_path_to_export(scenario_app, tmp_path, monkeypatch):
    app, scenario = scenario_app("writing")
    app.widgets["task_text"].insert("1.0", NOTICE)
    app.refresh()
    click_primary(app)
    assert not app.session.pending_questions
    assert app.primary_action_var.get() == "确认需求并生成方案"
    click_primary(app)
    assert app.notebook.index(app.notebook.select()) == 1
    assert app.primary_action_var.get() == "确认方案并生成提示"
    click_primary(app)
    assert len(scenario.received) == 2
    assert app.notebook.index(app.notebook.select()) == 3
    assert app.session.skill_state["status"] == "skipped"
    assert not app.session.skill_state.get("bindings")
    assert app.session.final_result["canonical_body"]
    target = tmp_path / "notice.md"
    monkeypatch.setattr("tkinter.filedialog.asksaveasfilename", lambda **_kwargs: str(target))
    get_button(app.widgets["result_simple_controls"], "导出方案和提示").invoke()
    assert target.is_file()
    assert "摄影社招新通知" in target.read_text(encoding="utf-8")
    assert not app.probe_errors
    state_evidence(app, scenario, tmp_path, "default_writing_result")
