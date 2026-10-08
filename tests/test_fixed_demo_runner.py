from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from copy import deepcopy

import pytest

from promptsmith.api import ApiConfig, ApiResult, ApiError

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "fixed_demo_runner", ROOT / "scripts" / "run_fixed_d1_d2_real_check.py"
)
runner = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(runner)


class InvalidClient:
    def complete_json(self, *_args):
        return ApiResult("{}", 2, None, "offline-invalid", "fixture")


def config():
    return ApiConfig(api_key="offline-test-only", base_url="https://example.invalid", model="fixture")


def test_failure_retains_manifest_session_and_raw_reference(tmp_path):
    run = runner.DemoRun(config(), tmp_path / "new-evidence", ["D1"],
                         client=InvalidClient(), evidence_mode="offline_fixture")
    result = run.advance()
    assert result["status"] == "failed"
    assert result["calls_used"] == 1
    case = result["cases"]["D1"]
    assert case["calls"][0]["usage"] is None
    assert Path(case["calls"][0]["evidence_dir"]).joinpath("response.raw.txt").exists()
    assert (tmp_path / "new-evidence" / "D1" / "session.json").exists()


def test_new_run_refuses_existing_evidence_and_budget_includes_prior_calls(tmp_path):
    out = tmp_path / "prior"
    out.mkdir()
    with pytest.raises(FileExistsError):
        runner.DemoRun(config(), out, ["D1"], client=InvalidClient())
    run = runner.DemoRun(config(), tmp_path / "new", ["D1"],
                         client=InvalidClient(), prior_call_count=14, evidence_mode="offline_fixture")
    result = run.advance()
    assert result["status"] == "budget_exhausted"
    assert result["calls_used"] == 14
    assert result["cases"]["D1"]["calls"] == []


class FixedClient:
    """Offline responses; no product state is injected or validator bypassed."""
    def __init__(self, *, m4_change=False, m1_question=False):
        self.payloads = []
        self.m4_change = m4_change
        self.m1_question = m1_question

    def complete_json(self, _system, payload, schema):
        self.payloads.append(deepcopy(payload))
        module = schema["properties"]["schema_version"]["const"].split(".")[0]
        result = getattr(self, module)(payload)
        return ApiResult(json.dumps(result, ensure_ascii=False), 3, None, f"offline-{module}", "fixture")

    def m1(self, p):
        source = p["sources"][0]
        is_writing = p["state"]["selected_category"] == "writing"
        proposals = []
        if not p["state"]["requirements"]:
            for index, text in enumerate(source["text"].split("。")):
                if not text:
                    continue
                proposals.append({"proposal_id": f"p{index}", "operation": "new",
                    "target_item_id": None, "field": "deliverable" if index == 0 else "constraints",
                    "text": text, "kind": "user_decision", "strength": "hard", "scope": "当前任务",
                    "source_refs": [{"source_id": source["source_id"], "quote": text}],
                    "depends_on": [], "reason": "测试夹具按固定原文提取"})
        gaps, questions, updates = [], [], []
        if not is_writing:
            gaps = [{"gap_id": f"g{index}", "field": "constraints", "scope": "当前规格",
                     "description": text + "未确定", "importance": "can_defer", "origin": "missing",
                     "source_refs": [], "depends_on": []}
                    for index, text in enumerate(["技术栈", "登录方式", "导出格式"])]
        elif self.m1_question and not p["state"]["question_history"]:
            gaps = [{"gap_id": "g-tone", "field": "style", "scope": "当前通知",
                     "description": "活泼程度未明确", "importance": "can_defer", "origin": "ambiguous",
                     "source_refs": [], "depends_on": []}]
            questions = [{"question_id": "q-tone", "gap_id": "g-tone", "field": "style",
                          "scope": "当前通知", "text": "语气活泼程度是什么？", "options": [],
                          "reason": "细化风格", "depends_on": []}]
        elif self.m1_question:
            answer = p["state"]["question_history"][-1]
            updates = [{"update_id": "update-tone", "target_gap_id": "g-tone", "answer_id": answer["answer_id"],
                        "action": "resolved", "source_ref": {"source_id": answer["answer_source_id"],
                        "quote": answer["answer_text"]}, "remaining_description": None, "reason": "用户给出明确窄反馈"}]
        return {"schema_version": p["schema_version"], "request_id": p["request_id"],
                "task_id": p["task_id"], "base_version": p["base_version"], "status": "ok", "error": None,
                "category": {"primary": p["state"]["selected_category"], "secondary": [], "reason": "沿用已选类别"},
                "proposals": proposals, "conflicts": [], "review_item_ids": [], "gap_updates": updates,
                "question_reopens": [], "gaps": gaps, "questions": questions,
                "readiness": {"goal_identified": True, "deliverable_identified": True,
                              "blocking_gap_ids": [], "reason": "现有信息可以形成交付物"},
                "next_action": "ask" if questions else "review_requirements", "assistant_text": "请核对"}

    def m2(self, p):
        ids = [row["item_id"] for row in p["requirements"]]
        title = "整理软件需求规格" if p["category"]["primary"] == "coding" else "编写摄影社招新通知"
        return {"schema_version": "m2.v0.1", "request_id": p["request_id"], "task_id": p["task_id"],
                "source_requirements_version": p["source_requirements_version"], "status": "ok", "error": None,
                "plan": {"goal": {"summary": title, "audience": "固定任务读者", "scope": "仅固定任务所述范围"},
                    "requirement_coverage": [{"requirement_id": rid, "summary": "保留原要求",
                        "step_ids": ["s1"], "deliverable_ids": ["d1"], "criterion_ids": ["c1"]} for rid in ids],
                    "steps": [{"step_id": "s1", "order": 1, "title": title, "purpose": "形成所需文稿",
                        "inputs": ["已确认需求"], "actions": ["逐项保留原文中的事实和边界"],
                        "outputs": [title], "completion_criteria": ["已知信息完整且未知保留"],
                        "depends_on_step_ids": [], "requirement_ids": ids}],
                    "deliverables": [{"deliverable_id": "d1", "name": title, "description": title,
                        "step_ids": ["s1"], "requirement_ids": ids}],
                    "completion_criteria": [{"criterion_id": "c1", "text": "保留全部事实与限制", "requirement_ids": ids}],
                    "unresolved_items": [{"unresolved_id": f"u{i}", "source_gap_id": row["unresolved_id"],
                        "description": row["description"], "impact": "后续细节待定",
                        "continuable_work": "可先整理已有信息", "confirm_by": "对应细节实施前"}
                        for i, row in enumerate(p["unresolved_items"])], "suggestions": [],
                    "key_work": [{"key_work_id": "k1", "title": title, "step_ids": ["s1"], "goal": title,
                        "inputs": ["已确认需求"], "outputs": [title], "requirement_ids": ids,
                        "depends_on_key_work_ids": [], "checkpoints": ["范围与未知均保留"]}]}}

    def m5(self, p):
        return {"schema_version": p["schema_version"], "request_id": p["request_id"], "task_id": p["task_id"],
                "base_version": p["base_version"], "status": "ok", "error": None,
                "example": {"dimension": "语气", "shared_assumptions": ["摄影社通知"],
                    "option_a": "摄影社将开展手机摄影体验，欢迎新生报名。",
                    "option_b": "想试试手机摄影？欢迎报名摄影社这次体验。",
                    "difference_summary": "B使用更直接的问句。", "unsupported_assumptions": []}}

    def m3(self, p):
        return {"schema_version": p["schema_version"], "request_id": p["request_id"], "task_id": p["task_id"],
                "status": "ok", "error": None, "unmatched_key_work_ids": [],
                "assessments": [{"candidate_id": row["candidate_id"], "decision": "recommend",
                    "capability_ids": [row["capabilities"][0]["capability_id"]], "reason": "符合规格整理关键工作",
                    "planned_inputs": ["已确认需求"], "expected_outputs": ["规格"], "prerequisite_ids": [],
                    "limitations": ["只适配方法，不执行原版"]} for row in p["candidates"]]}

    def m4(self, p):
        contributions = [{"binding_id": b["binding_id"], "step_id": b["step_ids"][0],
            "capability_ids": [b["capability_ids"][0]], "method_actions": ["按规格方法分层组织需求"],
            "planned_inputs": ["已确认需求"], "expected_outputs": ["需求规格"], "checkpoints": ["未知仍未知"],
            "prerequisite_ids": [r["prerequisite_id"] for r in b["prerequisite_assessments"] if r["status"] == "unknown" and r["blocking"]],
            "fallback_actions": ["只整理已有事实并保留未知"],
            "proposed_change_ids": ["change-optional"] if self.m4_change else []} for b in p["bindings"]]
        return {"schema_version": p["schema_version"], "request_id": p["request_id"], "task_id": p["task_id"],
                "status": "ok", "error": None, "contributions": contributions,
                "proposed_changes": [{"change_id": "change-optional", "binding_ids": [p["bindings"][0]["binding_id"]],
                    "kind": "scope", "description": "可附加术语表", "reason": "帮助理解", "affects_hard_constraints": False}] if self.m4_change else []}

    def complete_text(self, _system, user_text, *, max_output_tokens):
        text = ("摄影社招新：2026年10月10日14:00–16:00在校园南广场体验手机摄影。"
                "报名截止2026年10月8日：https://example.com/photo-signup。") if "摄影" in user_text else (
                    "需求规格与测试要点：查看、报名、取消；人数上限、导出名单；禁止重复报名、满额禁止新增。"
                    "技术栈、登录方式、导出格式待定。此处不编码、部署、创建 issue 或发布。")
        return ApiResult(text, 4, None, "offline-trial", "fixture")


def decide(run, case_id, actions):
    checkpoint = run.manifest["cases"][case_id]["checkpoint"]
    run.apply_decision({"case_id": case_id, "checkpoint_id": checkpoint["checkpoint_id"],
        "snapshot_sha256": checkpoint["snapshot_sha256"], "reviewer": "offline-test-operator",
        "rationale": "仅核验测试夹具的生产状态链；不冒充真实内容评审。", "actions": actions})


def fixture_decision(run, case_id):
    case = run.manifest["cases"][case_id]
    stage = case["stage"]
    session = run.sessions[case_id]
    if stage == "m1_review":
        return {"accept_proposal_ids": [r["proposal_id"] for r in session.pending_proposals],
                "confirm_requirements": case_id != "D1" or case["m5_done"]}
    if stage == "m5_review":
        return {"accept_fixed_m5_feedback": True, "tone_question_id": "q-tone" if session.pending_questions else None}
    if stage == "plan_review":
        return {"review_key_work_ids": [r["key_work_id"] for r in session.plan["content"]["key_work"]], "confirm_plan": True}
    if stage == "skill_review":
        if case_id == "D1":
            return {"skip_skill": True}
        candidates = session.skill_state["candidate_batch"]["result"]["candidates"]
        return {"select_candidate_id": next(r["candidate_id"] for r in candidates if r["skill_id"] == "to-spec")}
    if stage == "final_review":
        return {"m4_change_decisions": {r["change_id"]: "rejected" for r in session.final_result["content"]["pending_changes"] if r.get("change_id")}, "confirm_final": True}
    return {"content_verdict": "passed", "findings": ["仅离线fixture流程结果"]}


@pytest.mark.parametrize("case_id", ["D1", "D2"])
def test_fixed_case_uses_full_production_contract_then_trial_save_reopen_export(tmp_path, case_id):
    client = FixedClient(m1_question=case_id == "D1", m4_change=case_id == "D2")
    run = runner.DemoRun(config(), tmp_path / case_id, [case_id], client=client, evidence_mode="offline_fixture")
    stages = []
    for _ in range(12):
        result = run.advance()
        assert result["status"] != "failed", result["cases"][case_id].get("failure")
        if result["status"] == "completed":
            break
        stages.append(result["cases"][case_id]["stage"])
        assert result["status"] == "needs_review"
        decide(run, case_id, fixture_decision(run, case_id))
        # Resume from the persisted production state rather than preserving objects.
        run = runner.DemoRun(config(), tmp_path / case_id, [case_id], client=client,
                             evidence_mode="offline_fixture", resume=True)
    else:
        pytest.fail("Fixed fixture did not complete within its expected checkpoints")
    case = result["cases"][case_id]
    assert result["evidence_mode"] == "offline_fixture"
    assert case["final"]["status"] == "confirmed"
    assert all(case["persistence"]["checks"].values())
    assert Path(case["persistence"]["export_path"]).exists()
    assert case["trial"]["status"] == "completed"
    assert case["trial"]["usage"] is None
    modules = [r["module"] for r in case["calls"]]
    assert modules == (["m1", "m5", "m1", "m2", "trial"] if case_id == "D1" else ["m1", "m2", "m3", "m4", "trial"])
    if case_id == "D1":
        assert not run.sessions[case_id].gaps
        assert runner.FIXED_FEEDBACK in run.sessions[case_id].question_history[0]["answer_text"]
        assert runner.FIXED_FEEDBACK in str(case["final"])
    else:
        assert len(run.sessions[case_id].gaps) == 3
        assert case["actual_mode"] == "skill"
        assert case["final"]["generation_request_id"]
        assert case["final"]["change_decisions"][0]["decision"] == "rejected"


def test_checkpoint_does_not_accept_candidates_until_content_bound_decision(tmp_path):
    run = runner.DemoRun(config(), tmp_path / "r", ["D1"], client=FixedClient(), evidence_mode="offline_fixture")
    result = run.advance()
    assert result["status"] == "needs_review"
    assert not run.sessions["D1"].requirements
    before = run.sessions["D1"].to_dict()
    with pytest.raises(ValueError, match="exact current checkpoint"):
        run.apply_decision({"case_id": "D1", "checkpoint_id": "stale", "snapshot_sha256": "stale",
                            "reviewer": "test", "rationale": "test", "actions": {"accept_proposal_ids": ["p0"]}})
    assert before == run.sessions["D1"].to_dict()


def test_fixed_runner_matches_generic_spec_work_using_confirmed_task_context(tmp_path):
    class ContextOnlyClient(FixedClient):
        def m2(self, payload):
            result = super().m2(payload)
            work = result["plan"]["key_work"][0]
            work.update(title="功能需求规格编写", goal="整理已确认的功能和规则",
                        outputs=["功能需求规格"])
            return result

    run = runner.DemoRun(config(), tmp_path / "context", ["D2"],
                         client=ContextOnlyClient(), evidence_mode="offline_fixture")
    for _ in range(4):
        result = run.advance()
        assert result["status"] == "needs_review", result
        if result["cases"]["D2"]["stage"] == "skill_review":
            break
        decide(run, "D2", fixture_decision(run, "D2"))
    else:
        pytest.fail("Did not reach Skill review")
    batch = run.sessions["D2"].skill_state["candidate_batch"]["result"]
    assert batch["status"] == "ok"
    candidate = next(row for row in batch["candidates"] if row["skill_id"] == "to-spec")
    assert "任务描述：报名工具" in candidate["match_reason"]


def test_resume_waiting_checkpoint_never_repeats_completed_call(tmp_path):
    client = FixedClient()
    out = tmp_path / "resume"
    run = runner.DemoRun(config(), out, ["D1"], client=client, evidence_mode="offline_fixture")
    result = run.advance()
    assert len(client.payloads) == 1
    checkpoint = result["cases"]["D1"]["checkpoint"]
    run = runner.DemoRun(config(), out, ["D1"], client=client, resume=True, evidence_mode="offline_fixture")
    again = run.advance()
    assert len(client.payloads) == 1
    assert again["cases"]["D1"]["checkpoint"] == checkpoint
    assert again["status"] == "needs_review"
    assert runner.exit_code(again) == 2


def test_m4_pending_change_cannot_be_bypassed_by_final_confirmation(tmp_path):
    run = runner.DemoRun(config(), tmp_path / "pending", ["D2"],
                         client=FixedClient(m4_change=True), evidence_mode="offline_fixture")
    for _ in range(5):
        result = run.advance()
        assert result["status"] == "needs_review", result
        if result["cases"]["D2"]["stage"] == "final_review":
            break
        decide(run, "D2", fixture_decision(run, "D2"))
    before = run.sessions["D2"].to_dict()
    with pytest.raises(Exception, match="复核|变化|确认"):
        decide(run, "D2", {"confirm_final": True})
    assert run.sessions["D2"].to_dict() == before
    assert run.sessions["D2"].final_result["review_required_ids"]
    assert run.sessions["D2"].final_result["generation_request_id"]


def test_failed_same_task_retry_retains_previous_raw_evidence(tmp_path):
    out = tmp_path / "retry"
    run = runner.DemoRun(config(), out, ["D1"], client=InvalidClient(), evidence_mode="offline_fixture")
    result = run.advance()
    evidence = Path(result["cases"]["D1"]["calls"][0]["evidence_dir"]) / "response.raw.txt"
    prior_raw = evidence.read_bytes()
    run = runner.DemoRun(config(), out, ["D1"], client=FixedClient(), resume=True, evidence_mode="offline_fixture")
    assert run.advance()["status"] == "failed"
    run.allow_retry(reviewer="offline-operator", rationale="First fixture deliberately failed Schema validation.")
    result = run.advance()
    assert result["status"] == "needs_review"
    assert result["calls_used"] == 2
    assert evidence.read_bytes() == prior_raw
    calls = result["cases"]["D1"]["calls"]
    assert calls[0]["input"]["sources"] == calls[1]["input"]["sources"]
    assert calls[0]["evidence_dir"] != calls[1]["evidence_dir"]


def test_higher_call_limit_needs_explicit_reason_and_preserves_prior_budget(tmp_path):
    with pytest.raises(ValueError, match="reason"):
        runner.DemoRun(config(), tmp_path / "no-reason", ["D1"], client=FixedClient(),
                       prior_call_count=8, max_calls=20, evidence_mode="offline_fixture")
    run = runner.DemoRun(config(), tmp_path / "with-reason", ["D1"], client=FixedClient(),
                         prior_call_count=8, max_calls=20, budget_reason="Explicit re-run to include missing production steps.",
                         evidence_mode="offline_fixture")
    result = run.advance()
    assert result["calls_used"] == 9
    assert result["call_limit"] == 20
    assert result["budget_adjustments"][0]["reason"]


def test_failed_content_review_is_not_success_exit():
    assert runner.exit_code({"status": "completed_with_findings"}) != 0


def test_explicit_higher_budget_resumes_an_exhausted_run_without_resetting_count(tmp_path):
    out = tmp_path / "budget"
    run = runner.DemoRun(config(), out, ["D1"], client=FixedClient(), prior_call_count=14,
                         evidence_mode="offline_fixture")
    assert run.advance()["status"] == "budget_exhausted"
    run = runner.DemoRun(config(), out, ["D1"], client=FixedClient(), resume=True,
                         max_calls=15, budget_reason="One explicitly justified offline fixture call.",
                         evidence_mode="offline_fixture")
    result = run.advance()
    assert result["status"] == "needs_review"
    assert result["calls_used"] == 15
    assert result["prior_call_count"] == 14


def test_resume_of_interrupted_call_demands_explicit_recovery(tmp_path):
    out = tmp_path / "interrupted"
    client = FixedClient()
    run = runner.DemoRun(config(), out, ["D1"], client=client, evidence_mode="offline_fixture")
    run.advance()
    # Simulate the on-disk boundary after reserving a request but before its
    # response/progress became durable; this is runner state, not model output.
    case = run.manifest["cases"]["D1"]
    case.update(stage="m1_call", checkpoint=None, status="running")
    case["calls"][-1]["status"] = "started"
    run._save()
    run = runner.DemoRun(config(), out, ["D1"], client=client, resume=True, evidence_mode="offline_fixture")
    result = run.advance()
    assert result["status"] == "failed"
    assert result["cases"]["D1"]["failure"]["error_type"] == "InterruptedProgress"
    assert len(client.payloads) == 1


def test_trial_failure_preserves_actual_input_raw_and_missing_usage(tmp_path):
    class FailingTrialClient(FixedClient):
        def complete_text(self, *_args, **_kwargs):
            raise ApiError("network", "Offline network failure fixture", latency_ms=7)
    run = runner.DemoRun(config(), tmp_path / "trial-failure", ["D2"],
                         client=FailingTrialClient(), evidence_mode="offline_fixture")
    for _ in range(7):
        result = run.advance()
        if result["status"] == "failed":
            break
        decide(run, "D2", fixture_decision(run, "D2"))
    case = result["cases"]["D2"]
    assert case["failure"]["stage"] == "trial_call"
    call = case["calls"][-1]
    evidence = Path(call["evidence_dir"])
    assert (evidence / "input.json").exists()
    assert (evidence / "response.raw.txt").read_text(encoding="utf-8") == ""
    metadata = json.loads((evidence / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["usage"] is None
    assert metadata["response_available"] is False
    assert run.sessions["D2"].final_result["status"] == "confirmed"
    assert run.sessions["D2"].trial_runs[-1]["status"] == "failed"


def test_checkpoint_refuses_decision_if_business_state_changed_after_review(tmp_path):
    run = runner.DemoRun(config(), tmp_path / "changed", ["D1"],
                         client=FixedClient(), evidence_mode="offline_fixture")
    run.advance()
    run.sessions["D1"].set_task("改成完全不同的新任务")
    with pytest.raises(ValueError, match="changed"):
        decide(run, "D1", {"dismiss_remaining": True})
