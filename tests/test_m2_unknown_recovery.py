"""Synthetic regressions for planning unknowns; no personal diagnostic data."""
import json
from copy import deepcopy

import pytest

from promptsmith.m1 import M1Assets
from promptsmith.m2 import M2Assets, M2ValidationError, apply_m2_response, build_m2_input, parse_m2_response
from promptsmith.finalization import build_final_draft, confirm_final, render_task_prompt
from promptsmith.exporter import export_markdown
from promptsmith.storage import load_session, save_session
from promptsmith.workflow import M2CallFailure, Phase12Workflow
from promptsmith.ui import generation_failure_message
from tests.test_m2 import confirmed_session, valid_result
from tests.test_m2_workflow import Client


def unknown(identifier="new", source=None, description="设计稿格式尚未决定。"):
    return {"unresolved_id": identifier, "source_gap_id": source, "description": description,
            "impact": "影响交付格式。", "continuable_work": "先整理结构。", "confirm_by": "交付前"}


def parse(session, rows):
    payload = build_m2_input(session, "recovery-test")
    result = valid_result(payload)
    result["plan"]["unresolved_items"] = rows
    report = []
    parsed = parse_m2_response(json.dumps(result, ensure_ascii=False), payload,
                               M2Assets.load().output_schema, normalization_report=report)
    return payload, parsed, report


@pytest.mark.parametrize("sources", [["r2", "r1", "r3"],
                                    ["r2-deliverable", "existing-code", "environment", "ui-preference"]])
def test_new_unknowns_from_both_reported_shapes_are_retained(sources):
    session = confirmed_session(with_unknown=False)
    rows = [unknown(f"u{i}", source, f"待确认事项 {i}") for i, source in enumerate(sources)]
    original = deepcopy(rows)
    payload, parsed, report = parse(session, rows)
    output = parsed["plan"]["unresolved_items"]
    assert len(output) == len(rows)
    assert all(row["source_gap_id"] is None for row in output)
    assert output[0].get("related_requirement_ids", []) == (["r2"] if sources[0] == "r2" else [])
    assert rows == original and report
    apply_m2_response(session, payload, parsed)
    session.validate_plan()
    assert not session.gaps


def test_missing_original_and_duplicate_ids_recover_without_dropping_distinct_questions():
    session = confirmed_session()
    rows = [unknown("same", "r2"), unknown("same", "r2"),
            unknown("same", "r2", "设计稿精细度尚未决定。")]
    payload, parsed, report = parse(session, rows)
    items = parsed["plan"]["unresolved_items"]
    assert len(items) == 3
    assert len({row["unresolved_id"] for row in items}) == 3
    assert {row["source_gap_id"] for row in items} == {None, "g1"}
    assert any(row["description"] == payload["unresolved_items"][0]["description"] for row in items)
    assert report
    # Normalization is stable, including reassigned IDs and recovered source text.
    repeated = []
    again = parse_m2_response(json.dumps(parsed), payload, M2Assets.load().output_schema,
                             normalization_report=repeated)
    assert again == parsed and not repeated


def test_same_gap_can_have_distinct_impact_questions():
    session = confirmed_session()
    _, parsed, _ = parse(session, [unknown("one", "g1", "部署平台待确认。"),
                                  unknown("two", "g1", "部署权限待确认。")])
    assert len(parsed["plan"]["unresolved_items"]) == 2


def test_invalid_new_requirement_references_are_not_promoted_to_facts():
    session = confirmed_session(with_unknown=False)
    row = unknown()
    row["related_requirement_ids"] = ["r1", "invented"]
    _, parsed, report = parse(session, [row])
    assert parsed["plan"]["unresolved_items"][0]["related_requirement_ids"] == ["r1"]
    assert report and len(session.requirements) == 3


def test_unknowns_survive_edit_confirm_save_reopen_and_final_export(tmp_path):
    session = confirmed_session()
    payload, parsed, _ = parse(session, [unknown(source="r2")])
    apply_m2_response(session, payload, parsed)
    session.edit_plan_step("s1", title="核对并实现主流程", purpose="先完成确定的部分。")
    for question in session.questions_for_review():
        session.record_question(question["question_id"], "skipped")
    session.confirm_plan_preview(session.plan_preview())
    session = load_session(save_session(session, tmp_path / "plan.json"))
    draft = build_final_draft(session)
    session.final_result = draft
    confirm_final(session)
    text = render_task_prompt(session.final_result["canonical_body"])
    assert "最终部署位置尚未决定" in text and "设计稿格式尚未决定" in text
    assert "AI 规划时提出" in text
    exported = export_markdown(session, tmp_path / "final.md", mode="final").read_text(encoding="utf-8")
    assert "设计稿格式尚未决定" in exported
    reopened = load_session(save_session(session, tmp_path / "final.json"))
    assert reopened.final_result["status"] == "confirmed"
    assert reopened.final_result["canonical_body"] == session.final_result["canonical_body"]


def test_workflow_records_recovery_and_original_response(tmp_path):
    session = confirmed_session()
    workflow = Phase12Workflow(session, M1Assets.load(), tmp_path)
    payload = workflow.prepare_m2("recovered")

    def response(payload):
        result = valid_result(payload)
        result["plan"]["unresolved_items"] = [unknown(source="r2")]
        return result

    outcome = workflow.invoke_m2(payload, Client(response), protocol="offline", configured_model="fixture")
    check = json.loads((outcome.evidence_dir / "check.json").read_text(encoding="utf-8"))
    assert check["schema"] == "passed" and check["normalization"]
    assert outcome.normalization_report
    assert json.loads((outcome.evidence_dir / "response.raw.txt").read_text(encoding="utf-8"))["plan"]["unresolved_items"][0]["source_gap_id"] == "r2"
    workflow.apply_m2(payload, outcome)
    assert session.api_runs[-1]["normalization"]


def test_recoverable_plan_reference_keeps_warning_and_returns_draft(tmp_path):
    session = confirmed_session()
    workflow = Phase12Workflow(session, M1Assets.load(), tmp_path)
    payload = workflow.prepare_m2("bad-step")

    def response(payload):
        result = valid_result(payload)
        result["plan"]["steps"][0]["depends_on_step_ids"] = ["missing"]
        return result

    outcome = workflow.invoke_m2(payload, Client(response), protocol="offline", configured_model="fixture")
    check = json.loads((outcome.evidence_dir / "check.json").read_text(encoding="utf-8"))
    assert check["valid"] and check["normalization"]
    workflow.apply_m2(payload, outcome)
    assert session.plan["status"] == "draft"
    assert any("missing" in row["description"] for row in session.plan["content"]["unresolved_items"])


@pytest.mark.parametrize("field", ["request_id", "task_id", "source_requirements_version"])
def test_identity_guards_remain_with_new_unknowns(field):
    session = confirmed_session()
    payload = build_m2_input(session, "identity-guard")
    response = valid_result(payload)
    response["plan"]["unresolved_items"] = [unknown()]
    response[field] = 999 if field.endswith("version") else "other-task"
    with pytest.raises(M2ValidationError):
        parse_m2_response(json.dumps(response), payload, M2Assets.load().output_schema)


def test_recovered_unknowns_survive_m3_and_m4(tmp_path):
    from promptsmith.delivery_workflow import DeliveryWorkflow
    from tests.test_delivery_workflow import make_session, DeliveryHandler, _StaticClient

    session = confirmed_session()
    payload, parsed, _ = parse(session, [unknown(source="r2")])
    apply_m2_response(session, payload, parsed)
    for question in session.questions_for_review():
        session.record_question(question["question_id"], "skipped")
    session.confirm_plan_preview(session.plan_preview())
    basis = {"task_id": session.task_id, "requirement_version": session.requirement_version,
             "plan_id": session.plan["plan_id"], "plan_version": session.plan["plan_version"]}
    session.set_skill_state(status="candidates_ready", basis=basis,
                            candidate_batch=make_session().skill_state["candidate_batch"])
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path)
    m3 = workflow.prepare_m3("m3-unknown", connection_version=1)
    assert "设计稿格式尚未决定" in json.dumps(m3, ensure_ascii=False)
    assert "最终部署位置尚未决定" in json.dumps(m3, ensure_ascii=False)
    outcome = workflow.invoke_m3(m3, _StaticClient(DeliveryHandler._m3_output(m3)),
                                 protocol="offline", configured_model="fixture")
    workflow.apply_m3(m3, outcome, connection_version=1)
    session.set_skill_state(status="selected", basis=basis,
                            bindings=make_session(with_binding=True).skill_state["bindings"])
    m4 = workflow.prepare_m4("m4-unknown", connection_version=1)
    assert len(m4["baseline"]["unknowns"]) == 2
    outcome = workflow.invoke_m4(m4, _StaticClient(DeliveryHandler._m4_output(m4)),
                                 protocol="offline", configured_model="fixture")
    workflow.apply_m4(m4, outcome, connection_version=1)
    confirm_final(session)
    exported = export_markdown(session, tmp_path / "m4.md", mode="final").read_text(encoding="utf-8")
    assert all(row["description"] in exported for row in m4["baseline"]["unknowns"])
    reopened = load_session(save_session(session, tmp_path / "m4.json"))
    assert reopened.final_result["status"] == "confirmed"


def test_delivery_union_preserves_source_wording_and_new_suggestions():
    session = confirmed_session()
    payload, parsed, _ = parse(session, [unknown(source="r2")])
    apply_m2_response(session, payload, parsed)
    for question in session.questions_for_review():
        session.record_question(question["question_id"], "skipped")
    session.confirm_plan_preview(session.plan_preview())
    # Legacy/incomplete delivery content must not hide the source snapshot.
    session.plan["content"]["unresolved_items"] = [row for row in session.plan["content"]["unresolved_items"]
                                                   if row["source_gap_id"] is None]
    result = build_final_draft(session)
    assert "最终部署位置尚未决定" in result["canonical_body"]
    assert "设计稿格式尚未决定" in result["canonical_body"]


def test_old_confirmed_final_without_new_guidance_keeps_confirmation(tmp_path):
    from promptsmith.finalization import render_canonical_body, _content_hash, _baseline

    session = confirmed_session()
    payload, parsed, _ = parse(session, [])
    apply_m2_response(session, payload, parsed)
    session.confirm_plan_preview(session.plan_preview())
    session.final_result = build_final_draft(session)
    # Pre-fix final snapshots had no policy marker; do not change their body on load.
    session.final_result["content"]["baseline"] = _baseline(session, legacy=True)
    body = render_canonical_body(session.final_result["content"])
    session.final_result.update(canonical_body=body, body_sha256=_content_hash(body))
    confirm_final(session)
    reopened = load_session(save_session(session, tmp_path / "old-final.json"))
    assert reopened.final_result["status"] == "confirmed"
    assert reopened.final_result["canonical_body"] == body


@pytest.mark.parametrize("status, expected", [(401, "密钥"), (403, "权限"), (429, "额度"), (400, "接口类型")])
def test_api_guidance_survives_workflow_error_wrapper(tmp_path, status, expected):
    from promptsmith.api import ApiError

    class FailedClient:
        def complete_json(self, *_args):
            raise ApiError("http_error", "HTTP failure", status_code=status)

    session = confirmed_session()
    workflow = Phase12Workflow(session, M1Assets.load(), tmp_path)
    with pytest.raises(M2CallFailure) as error:
        workflow.invoke_m2(workflow.prepare_m2("http-guidance"), FailedClient(),
                           protocol="offline", configured_model="fixture")
    text = generation_failure_message("m2", error.value, None)
    assert expected in text and "已保留" in text


def test_unreadable_service_response_has_actionable_guidance():
    from promptsmith.api import ApiError

    message = generation_failure_message("m2", ApiError("invalid_response", "raw service failure"), None)
    assert "内容格式" in message and "重新生成方案" in message and "不用重新回答" in message


@pytest.mark.parametrize("raw, schema_status, stage", [('not json', 'not_reached', 'json'),
                                                       ('{}', 'failed', 'schema')])
def test_bad_responses_log_precise_stage_and_preserve_plan(tmp_path, raw, schema_status, stage):
    from promptsmith.api import ApiResult

    class RawClient:
        def complete_json(self, *_args):
            return ApiResult(raw, 1, None, None, "fixture")

    session = confirmed_session()
    old = deepcopy(session.plan)
    workflow = Phase12Workflow(session, M1Assets.load(), tmp_path)
    with pytest.raises(M2CallFailure) as error:
        workflow.invoke_m2(workflow.prepare_m2("bad-response"), RawClient(), protocol="offline", configured_model="fixture")
    check = json.loads((error.value.evidence_dir / "check.json").read_text(encoding="utf-8"))
    assert check["schema"] == schema_status and check["failure_stage"] == stage
    assert check["semantic"] == "not_reached" and session.plan == old
