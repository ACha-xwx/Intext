"""Prompt handoff recovery, tested with synthetic responses and no paid API."""
import json
from copy import deepcopy

import pytest

from promptsmith.api import ApiResult
from promptsmith.delivery_workflow import DeliveryWorkflow, DeliveryStaleResponseError
from promptsmith.finalization import build_final_draft, stage_final_draft, validate_current_final
from promptsmith.m1 import M1Assets, M1ValidationError, apply_m1_response, build_m1_input, parse_m1_response
from promptsmith.m4 import M4Assets, M4ValidationError, parse_m4_response
from promptsmith.storage import save_session, load_session
from promptsmith.ui import generation_failure_message
from tests.test_delivery_workflow import make_session, DeliveryHandler
from tests.test_m1_incremental_retry import answered_session, delta_result
from tests.test_m3_m4 import fixture


def persisted_selected_session():
    session = make_session(with_binding=True)
    for row in session.requirements:
        row.update(field="goal", kind="user_decision", scope="当前任务", source_refs=[], depends_on=[], confirmation="confirmed")
    session.plan["source_snapshot"] = {"requirements": deepcopy(session.requirements), "unresolved_items": []}
    session.plan["content"]["unresolved_items"][0].update(
        unresolved_id="u1", source_gap_id=None, confirm_by="开始执行前")
    for question in session.questions_for_review():
        session.record_question(question["question_id"], "skipped")
    return session


class ResponseClient:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def complete_json(self, *args):
        self.calls += 1
        return ApiResult(self.response, "offline-model", None, None, 1)


def test_historical_gap_answer_is_applied_and_preserved_after_reload(tmp_path, caplog):
    session = answered_session()
    session.gaps = []
    payload = build_m1_input(session, "historical-answer")
    result = delta_result(payload)
    parsed = parse_m1_response(json.dumps(result), payload, M1Assets.load().output_schema, incremental=True)
    apply_m1_response(session, payload, parsed)
    assert session.gaps == []
    assert all(row["assessment_status"] == "applied" for row in session.question_history)
    assert all(row["answer_text"] for row in session.question_history)
    restored = load_session(save_session(session, tmp_path / "session.json"))
    assert restored.question_history == session.question_history
    assert "assess_historical_answer" in caplog.text


def test_historical_gap_cannot_be_closed_by_another_answer():
    session = answered_session()
    session.gaps = []
    payload = build_m1_input(session, "wrong-answer")
    result = delta_result(payload)
    result["gap_updates"][0]["target_gap_id"] = "invented-gap"
    with pytest.raises(M1ValidationError):
        parse_m1_response(json.dumps(result), payload, M1Assets.load().output_schema, incremental=True)


@pytest.mark.parametrize("mode", ["extra", "missing", "plain_text", "content_error"])
def test_m4_invoke_apply_exportable_prompt_preserves_selection_and_evidence(tmp_path, caplog, mode):
    session = persisted_selected_session()
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "runs")
    payload = workflow.prepare_m4("recovery-" + mode, connection_version=1)
    original_bindings = deepcopy(session.skill_state["bindings"])
    response = DeliveryHandler._m4_output(payload)
    if mode == "extra":
        response["contributions"][0]["outputs"] = []
        response["contributions"][0]["method_actions"] = "读取 Skill，整理任务文档。"
    elif mode == "missing":
        response["contributions"] = []
    elif mode == "content_error":
        response.update(status="error", contributions=[], error={"code": "contract_issue", "message": "格式未知", "recovery_action": "下游读取原文"})
    raw = "使用所选 Skill 整理文档，实际材料待补充。" if mode == "plain_text" else json.dumps(response)
    outcome = workflow.invoke_m4(payload, ResponseClient(raw), protocol="offline", configured_model="offline-model")
    assert outcome.failure_kind is None
    workflow.apply_m4(payload, outcome, connection_version=1)
    validate_current_final(session)
    body = session.final_result["canonical_body"]
    assert "to-spec" in body
    assert "尚未完整验证" in body
    assert "仓库结构尚未提供" in body
    assert session.skill_state["bindings"] == original_bindings
    effective = json.loads((outcome.evidence_dir / "response.effective.json").read_text(encoding="utf-8"))
    assert effective == outcome.parsed
    check = json.loads((outcome.evidence_dir / "check.json").read_text(encoding="utf-8"))
    assert check["normalization"] and check["valid"]
    assert "compatibility repairs" in caplog.text
    restored = load_session(save_session(session, tmp_path / "saved.json"))
    validate_current_final(restored)
    assert restored.final_result["canonical_body"] == body


def test_direct_selected_skill_prompt_needs_no_model_and_keeps_incompatible_caveat():
    session = make_session(with_binding=True)
    binding = session.skill_state["bindings"][0]
    binding["precondition_assessments"][0]["status"] = "incompatible"
    draft = build_final_draft(session)
    stage_final_draft(session, draft, expected_basis=draft["basis"])
    validate_current_final(session)
    assert "to-spec" in session.final_result["canonical_body"]
    assert "incompatible" in session.final_result["canonical_body"]


@pytest.mark.parametrize("mutation", ["cancel", "version", "connection"])
def test_recovered_m4_still_rejects_cancelled_or_stale_request(tmp_path, mutation):
    session = make_session(with_binding=True)
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path)
    payload = workflow.prepare_m4("stale-recovery", connection_version=1)
    outcome = workflow.invoke_m4(payload, ResponseClient("读取所选 Skill，细节待核对。"), protocol="offline", configured_model="offline")
    if mutation == "cancel":
        workflow.cancel(payload["request_id"])
    elif mutation == "version":
        session.requirement_version += 1
    before = deepcopy(session.final_result)
    with pytest.raises(DeliveryStaleResponseError):
        workflow.apply_m4(payload, outcome, connection_version=2 if mutation == "connection" else 1)
    assert session.final_result == before


@pytest.mark.parametrize("key", ["request_id", "task_id"])
def test_m4_other_request_identity_remains_rejected(key):
    payload = fixture("m4_normal.manual_fixture.input.json")
    response = fixture("m4_normal.manual_fixture.output.json")
    response[key] = "another-task-or-request"
    with pytest.raises(M4ValidationError, match=key):
        parse_m4_response(json.dumps(response), payload, M4Assets.load().output_schema)


def test_m4_duplicate_identity_and_empty_response_remain_errors():
    payload = fixture("m4_normal.manual_fixture.input.json")
    for raw in ('{"request_id":"other","request_id":"current"}', ""):
        with pytest.raises(M4ValidationError):
            parse_m4_response(raw, payload, M4Assets.load().output_schema)


@pytest.mark.parametrize("stage,action", [("m1", "重试分析"), ("m2", "重新生成方案"), ("m3", "直接选用"), ("m4", "直接生成提示词"), ("m5", "直接回答")])
def test_every_stage_error_has_actionable_next_step(stage, action):
    message = generation_failure_message(stage, ValueError("响应格式未识别"), 60)
    assert "下一步" in message and action in message


def test_sparse_m2_model_plan_keeps_unknowns_and_can_be_confirmed():
    from promptsmith.m2 import M2Assets, build_m2_input, parse_m2_response, apply_m2_response
    from tests.test_m2 import confirmed_session, valid_result
    session = confirmed_session()
    payload = build_m2_input(session, "sparse-model")
    response = valid_result(payload)
    response["plan"]["goal"].pop("audience")
    for key in ("actions", "outputs", "completion_criteria"):
        response["plan"]["steps"][0].pop(key)
    parsed = parse_m2_response(json.dumps(response), payload, M2Assets.load().output_schema)
    apply_m2_response(session, payload, parsed)
    session.mark_key_work_reviewed(session.plan["pending_key_work_review_ids"])
    for question in session.questions_for_review():
        session.record_question(question["question_id"], "skipped")
    session.confirm_plan()
    draft = build_final_draft(session)
    assert "受众尚未明确" in draft["canonical_body"]
    assert "尚待细化" in draft["canonical_body"]


def test_m2_valid_forward_dependency_remains_unchanged():
    from promptsmith.m2 import M2Assets, build_m2_input, parse_m2_response
    from tests.test_m2 import confirmed_session, valid_result
    session = confirmed_session()
    payload = build_m2_input(session, "forward-links")
    response = valid_result(payload)
    second = deepcopy(response["plan"]["steps"][0])
    second.update(step_id="s2", order=2)
    response["plan"]["steps"].append(second)
    response["plan"]["steps"][0]["depends_on_step_ids"] = ["s2"]
    parsed = parse_m2_response(json.dumps(response), payload, M2Assets.load().output_schema)
    assert parsed["plan"] == response["plan"]


def test_m5_advisory_differences_are_visible_and_never_confirm_requirements(tmp_path, caplog):
    from promptsmith.m5 import parse_m5_response, record_m5_feedback, apply_m5_response, build_m5_input
    from tests.test_m5_workflow import session_with_task, valid_response
    session = session_with_task()
    session.requirements.append({"item_id": "r1", "text": "禁止收费", "strength": "hard"})
    before = deepcopy(session.requirements)
    payload = build_m5_input(session, "m5-advisory", criterion_description="语气")
    response = valid_response(payload)
    example = response["example"]
    example.update(dimension="视觉节奏", option_a="收费。" * 250, option_b="收费。" * 250)
    example.pop("difference_summary")
    parsed = parse_m5_response(json.dumps(response), payload)
    notes = parsed["example"]["unsupported_assumptions"]
    assert any("对应关系尚待核对" in text for text in notes)
    assert any("两个示例相同" in text for text in notes)
    assert any("约束冲突" in text for text in notes)
    assert any("超出建议显示长度" in text for text in notes)
    assert parsed["example"]["option_a"] == example["option_a"]
    row = apply_m5_response(session, payload, parsed)
    feedback = record_m5_feedback(session, row["example_id"], "a")
    assert feedback["candidate"]["confirmation"] == "pending"
    assert session.requirements == before
    assert "compatibility repairs" in caplog.text


@pytest.mark.parametrize("mode", ["object", "malformed_id", "scalar", "duplicate_notes"])
def test_m4_nonstandard_advisory_shapes_keep_actual_bindings(mode):
    payload = fixture("m4_normal.manual_fixture.input.json")
    response = fixture("m4_normal.manual_fixture.output.json")
    if mode == "object":
        response["contributions"] = response["contributions"][0]
    elif mode == "malformed_id":
        response["contributions"][0]["binding_id"] = ["unrecognized-id"]
    elif mode == "scalar":
        response["contributions"] = 7
        response["proposed_changes"] = True
    else:
        response["contributions"] = [{"binding_id": "outside", "notes": "待核对"}] * 2
    parsed = parse_m4_response(json.dumps(response), payload, M4Assets.load().output_schema)
    assert {row["binding_id"] for row in parsed["contributions"]} == {row["binding_id"] for row in payload["bindings"]}


def test_m3_nonstandard_advisory_shape_preserves_candidate_identity():
    from promptsmith.m3 import M3Assets, parse_m3_response
    payload = fixture("m3_normal.manual_fixture.input.json")
    response = fixture("m3_normal.manual_fixture.output.json")
    response["assessments"] = {"candidate_id": ["unrecognized"], "reason": 123}
    response["unmatched_key_work_ids"] = [{"work": "unrecognized"}]
    parsed = parse_m3_response(json.dumps(response), payload, M3Assets.load().output_schema)
    assert {row["candidate_id"] for row in parsed["assessments"]} == {row["candidate_id"] for row in payload["candidates"]}
    assert parsed["assessments"][0]["decision"] == "conditional"


def test_m1_extra_advisory_content_reaches_final_prompt_as_unknown():
    session = answered_session()
    payload = build_m1_input(session, "extra-advisory")
    response = delta_result(payload)
    response["extra_context"] = "部署平台尚待核对"
    parsed = parse_m1_response(json.dumps(response), payload, M1Assets.load().output_schema, incremental=True)
    apply_m1_response(session, payload, parsed)
    assert any("部署平台尚待核对" in row["description"] and row["importance"] == "can_defer" for row in session.gaps)
    final_session = make_session(with_binding=False)
    final_session.gaps = deepcopy(session.gaps)
    final_session.plan["source_snapshot"] = {"requirements": deepcopy(final_session.requirements), "unresolved_items": deepcopy(session.gaps)}
    for question in final_session.questions_for_review():
        final_session.record_question(question["question_id"], "skipped")
    assert "部署平台尚待核对" in build_final_draft(final_session)["canonical_body"]
