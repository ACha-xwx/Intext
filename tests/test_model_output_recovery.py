"""Prompt handoff recovery, tested with synthetic responses and no paid API."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from promptsmith.api import ApiResult
from promptsmith.delivery_workflow import DeliveryWorkflow, DeliveryStaleResponseError
from promptsmith.exporter import export_markdown
from promptsmith.finalization import build_final_draft, stage_final_draft, validate_current_final
from promptsmith.m1 import M1Assets, M1ValidationError, apply_m1_response, build_m1_input, parse_m1_response
from promptsmith.m4 import M4Assets, M4ValidationError, parse_m4_response
from promptsmith.storage import save_session, load_session
from promptsmith.skill_catalog import SkillCatalog
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


def test_m4_malformed_json_never_reaches_final_prompt_or_export(tmp_path, caplog):
    session = persisted_selected_session()
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "runs")
    payload = workflow.prepare_m4("malformed-integration", connection_version=1)
    original_bindings = deepcopy(session.skill_state["bindings"])
    # A missing closing delimiter exercises the same compatibility branch as
    # the reported raw response in the final prompt, without a paid model call.
    raw = json.dumps(DeliveryHandler._m4_output(payload), ensure_ascii=False)[:-1]
    client = ResponseClient(raw)
    outcome = workflow.invoke_m4(payload, client, protocol="offline", configured_model="offline-model")
    workflow.apply_m4(payload, outcome, connection_version=1)
    validate_current_final(session)
    body = session.final_result["canonical_body"]
    assert '"schema_version"' not in body
    assert '"contributions"' not in body
    assert '"proposed_changes"' not in body
    assert "to-spec" in body and "仓库结构尚未提供" in body
    assert session.skill_state["bindings"] == original_bindings
    assert client.calls == 1
    exported = export_markdown(session, tmp_path / "prompt.md", mode="draft").read_text(encoding="utf-8")
    assert body in exported
    assert '"schema_version"' not in exported
    restored = load_session(save_session(session, tmp_path / "saved.json"))
    validate_current_final(restored)
    assert restored.final_result["canonical_body"] == body
    assert (outcome.evidence_dir / "response.raw.txt").read_text(encoding="utf-8") == raw
    check = json.loads((outcome.evidence_dir / "check.json").read_text(encoding="utf-8"))
    assert check["normalization"] and check["valid"]
    assert "compatibility repairs" in caplog.text
    assert raw not in caplog.text


def test_m4_wrapped_json_preserves_model_guidance_without_exporting_envelope(tmp_path):
    session = persisted_selected_session()
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "runs")
    payload = workflow.prepare_m4("wrapped-integration", connection_version=1)
    response = DeliveryHandler._m4_output(payload)
    response["contributions"][0]["method_actions"] = ["先逐项核对需求，再整理验收标准。"]
    raw = "整合结果如下：\n```json\n" + json.dumps(response, ensure_ascii=False) + "\n```\n以上是整合结果。"
    client = ResponseClient(raw)
    outcome = workflow.invoke_m4(payload, client, protocol="offline", configured_model="offline-model")
    assert outcome.parsed["contributions"][0]["method_actions"] == ["先逐项核对需求，再整理验收标准。"]
    workflow.apply_m4(payload, outcome, connection_version=1)
    body = session.final_result["canonical_body"]
    assert "先逐项核对需求，再整理验收标准。" in body
    assert '"schema_version"' not in body
    assert "整合结果如下" not in body
    assert "以上是整合结果" not in body
    assert client.calls == 1
    exported = export_markdown(session, tmp_path / "prompt.md", mode="draft").read_text(encoding="utf-8")
    assert body in exported and '"schema_version"' not in exported


@pytest.mark.parametrize("mode", ["extra_object", "advisory_error", "malformed_explanation", "single_quote_wrapped", "single_quote_incomplete"])
def test_m4_recovery_keeps_readable_notes_without_serialized_technical_fields(tmp_path, mode):
    session = persisted_selected_session()
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "runs")
    payload = workflow.prepare_m4("readable-notes-" + mode, connection_version=1)
    response = DeliveryHandler._m4_output(payload)
    useful_note = "使用时核对交付文档的目录结构。"
    if mode == "extra_object":
        response["diagnostics"] = {"schema_version": "m4.v0.1", "contributions": response["contributions"]}
        response["notes"] = [useful_note]
    elif mode == "advisory_error":
        response.update(status="error", contributions=[], error={
            "code": "constraint_conflict", "message": "所选方法与当前约束有冲突。",
            "recovery_action": useful_note,
            "details": {"schema_version": "m4.v0.1", "proposed_changes": []},
        })
    raw = json.dumps(response, ensure_ascii=False)
    if mode == "malformed_explanation":
        raw = "整合结果如下：\n" + raw[:-1]
    elif mode in {"single_quote_wrapped", "single_quote_incomplete"}:
        raw = "整合结果如下：\n" + repr(response)
        if mode == "single_quote_incomplete":
            raw = raw[:-1]
    client = ResponseClient(raw)
    outcome = workflow.invoke_m4(payload, client, protocol="offline", configured_model="offline-model")
    workflow.apply_m4(payload, outcome, connection_version=1)
    body = session.final_result["canonical_body"]
    assert "schema_version" not in body
    assert '"binding_id"' not in body
    assert '"proposed_changes"' not in body
    assert '{"code":' not in body
    assert "to-spec" in body
    if mode in {"extra_object", "advisory_error"}:
        assert useful_note in body
    if mode == "advisory_error":
        assert "constraint_conflict" in body
        assert "所选方法与当前约束有冲突。" in body
    exported = export_markdown(session, tmp_path / "prompt.md", mode="draft").read_text(encoding="utf-8")
    assert body in exported and '"schema_version"' not in exported
    assert client.calls == 1


@pytest.mark.parametrize("mode", ["valid", "wrapped", "malformed", "plain_text"])
def test_m4_multiple_selected_skills_survive_clean_export_and_reload(tmp_path, mode):
    session = persisted_selected_session()
    root = Path(__file__).resolve().parents[1]
    catalog = SkillCatalog.load(root / "resources/skill_catalog/catalog_v0.1.json", source_root=root, verify_sources=True)
    bindings = []
    for record in catalog.records:
        binding = deepcopy(session.skill_state["bindings"][0])
        binding.update(
            binding_id="selected-" + record["skill_id"], skill_id=record["skill_id"],
            record_hash=record["record_hash"], record_snapshot=record,
            capability_ids=[row["capability_id"] for row in record["capabilities"]],
            precondition_assessments=[],
        )
        bindings.append(binding)
    session.set_skill_state(status="selected", basis=session.skill_state["basis"], bindings=bindings)
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "runs")
    payload = workflow.prepare_m4("multiple-skills-" + mode, connection_version=1)
    response = DeliveryHandler._m4_output(payload)
    raw = json.dumps(response, ensure_ascii=False)
    if mode == "wrapped":
        raw = "整合如下：\n```json\n" + raw + "\n```"
    elif mode == "malformed":
        raw = raw[:-1]
    elif mode == "plain_text":
        raw = "请先核对术语定义，再逐项整理验收标准。"
    client = ResponseClient(raw)
    outcome = workflow.invoke_m4(payload, client, protocol="offline", configured_model="offline-model")
    workflow.apply_m4(payload, outcome, connection_version=1)
    validate_current_final(session)
    body = session.final_result["canonical_body"]
    assert {row["binding_id"] for row in outcome.parsed["contributions"]} == {row["binding_id"] for row in bindings}
    for name in ("to-spec", "domain-modeling", "goal-prompt"):
        assert name in body
    assert '"schema_version"' not in body
    if mode == "plain_text":
        assert raw in body
    else:
        assert raw not in body
    assert client.calls == 1 and session.skill_state["bindings"] == bindings
    restored = load_session(save_session(session, tmp_path / "saved.json"))
    validate_current_final(restored)
    assert restored.final_result["canonical_body"] == body
    exported = export_markdown(restored, tmp_path / "prompt.md", mode="draft").read_text(encoding="utf-8")
    assert body in exported and '"schema_version"' not in exported


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
@pytest.mark.parametrize("wrapped", [False, True])
def test_m4_other_request_identity_remains_rejected(key, wrapped):
    payload = fixture("m4_normal.manual_fixture.input.json")
    response = fixture("m4_normal.manual_fixture.output.json")
    response[key] = "another-task-or-request"
    raw = json.dumps(response)
    if wrapped:
        raw = "结果：\n```json\n" + raw + "\n```"
    with pytest.raises(M4ValidationError, match=key):
        parse_m4_response(raw, payload, M4Assets.load().output_schema)


@pytest.mark.parametrize("raw", [
    '{"request_id":"other","request_id":"current"}', "",
    '结果：\n```json\n{"request_id":"other","request_id":"current"}\n```',
    '结果：\n```json\n{"contributions": NaN}\n```',
])
def test_m4_duplicate_identity_and_empty_response_remain_errors(raw):
    payload = fixture("m4_normal.manual_fixture.input.json")
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
