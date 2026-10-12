import json
from copy import deepcopy

import pytest

from promptsmith.m1 import M1Assets, apply_m1_response, build_m1_input, parse_m1_response
from promptsmith.m2 import build_m2_input
from promptsmith.session import SessionState, SessionStateError
from promptsmith.storage import load_session, save_session
from promptsmith.api import ApiResult, ApiError
from promptsmith.workflow import Phase12Workflow, M1CallFailure
from tests.test_m1_model_authority_v11 import _base
from tests.test_m2 import confirmed_session


TASK = "重新设计现有 Python + tkinter 软件的 UI，保留现有功能，优化布局与样式。"
TOPICS = [("use_context", "使用场景"), ("deliverable", "交付形式"), ("existing_code", "源码和启动材料"),
          ("runtime", "运行环境"), ("features", "重构边界"), ("preferences", "视觉风格"),
          ("success_criteria", "验收方式")]


def batch_result(payload, count=7, suffix=""):
    result = _base(payload)
    result["category"]["primary"] = "coding"
    result["category"]["reason"] = "软件 UI 重构"
    result["next_action"] = "ask"
    for i, (field, topic) in enumerate(TOPICS[:count]):
        gap_id = f"g-{suffix}{i}"
        result["gaps"].append({"gap_id": gap_id, "field": field, "scope": topic + suffix,
                              "description": topic + suffix + "待补充", "importance": "can_defer", "origin": "missing",
                              "source_refs": [], "depends_on": []})
        result["questions"].append({"question_id": f"q-{suffix}{i}", "gap_id": gap_id, "field": field,
                                  "scope": topic + suffix, "text": "请说明" + topic + suffix + "？", "options": [],
                                  "reason": "在需求阶段核对，减少方案返工", "depends_on": []})
    return result


def test_first_round_can_collect_more_than_three_related_questions():
    session = SessionState.new()
    session.set_task(TASK)
    payload = build_m1_input(session, "wide-first-round")
    result = parse_m1_response(json.dumps(batch_result(payload), ensure_ascii=False), payload, M1Assets.load().output_schema)
    apply_m1_response(session, payload, result)
    assert len(session.questions_for_review()) == 7
    assert payload["control"]["interview_policy"] == "comprehensive_batch"
    assert payload["control"]["interview_round_limit"] == 5
    assert session.control["interview_rounds_used"] == 1


def test_five_question_rounds_survive_restart_without_automatic_sixth(tmp_path):
    session = SessionState.new()
    session.set_task(TASK)
    for index in range(5):
        payload = build_m1_input(session, f"round-{index}")
        result = parse_m1_response(json.dumps(batch_result(payload, count=1, suffix=str(index))), payload, M1Assets.load().output_schema)
        apply_m1_response(session, payload, result)
        assert session.control["interview_rounds_used"] == index + 1
        for question in session.questions_for_review():
            session.record_question(question["question_id"], "skipped")
    session = load_session(save_session(session, tmp_path / "five-rounds.json"))
    assert session.control["interview_rounds_used"] == 5
    payload = build_m1_input(session, "final-summary")
    assert payload["control"]["interview_rounds_remaining"] == 0
    result = parse_m1_response(json.dumps(batch_result(payload, suffix="sixth")), payload, M1Assets.load().output_schema)
    apply_m1_response(session, payload, result)
    assert not session.questions_for_review()
    assert session.control["interview_rounds_used"] == 5
    assert session.last_next_action == "pause_with_unknowns"
    assert session.questions_for_review(respect_interview_limit=False)
    with pytest.raises(SessionStateError):
        session.validate_unknown_reviews()
    assert not session.confirmed_requirements_version
    session.set_task("新的学习任务")
    assert session.control["interview_rounds_used"] == 0
    assert session.control["interview_round_limit"] == 5


def closed_interview():
    session = SessionState.new()
    session.set_task(TASK)
    session.control["interview_rounds_used"] = 5
    payload = build_m1_input(session, "unrequested-sixth")
    result = parse_m1_response(json.dumps(batch_result(payload), ensure_ascii=False), payload, M1Assets.load().output_schema)
    apply_m1_response(session, payload, result)
    return session


def test_each_extra_round_requires_separate_user_choice_and_survives_restart(tmp_path):
    session = closed_interview()
    for used in (5, 6, 7):
        assert session.control["interview_rounds_used"] == used
        assert not session.questions_for_review()
        assert session.questions_for_review(respect_interview_limit=False)
        with pytest.raises(SessionStateError):
            session.validate_unknown_reviews()
        assert session.authorize_next_interview_round() == used + 1
        with pytest.raises(SessionStateError):
            session.authorize_next_interview_round()
        session = load_session(save_session(session, tmp_path / f"consent-{used}.json"))
        payload = build_m1_input(session, f"authorized-{used + 1}")
        assert payload["control"]["interview_rounds_remaining"] == 1
        response = batch_result(payload, count=1, suffix=str(used))
        apply_m1_response(session, payload, parse_m1_response(json.dumps(response), payload, M1Assets.load().output_schema))
        # The whole related batch, including existing gaps, remains answerable.
        for q in session.questions_for_review():
            session.record_question(q["question_id"], "unsure")
        payload = build_m1_input(session, f"summary-{used + 1}")
        assert payload["control"]["interview_rounds_remaining"] == 0
        response = batch_result(payload, count=1, suffix=f"still-{used}")
        apply_m1_response(session, payload, parse_m1_response(json.dumps(response), payload, M1Assets.load().output_schema))
        assert session.control["interview_rounds_used"] == used + 1
        assert not session.questions_for_review()
    before = deepcopy(session.to_dict())
    assert session.defer_remaining_interview_unknowns() > 0
    assert not session.questions_for_review(respect_interview_limit=False)
    assert [g["description"] for g in session.gaps] == [g["description"] for g in before["gaps"]]
    assert session.confirmed_requirements_version is None
    assert session.plan["status"] == "not_started"


def test_fifth_round_with_only_derived_questions_remains_answerable(tmp_path):
    session = SessionState.new()
    session.set_task(TASK)
    session.control["interview_rounds_used"] = 4
    payload = build_m1_input(session, "derived-fifth")
    response = batch_result(payload)
    response["questions"] = []
    response["next_action"] = "pause_with_unknowns"
    apply_m1_response(session, payload, parse_m1_response(json.dumps(response), payload, M1Assets.load().output_schema))
    assert session.control["interview_rounds_used"] == 5
    assert len(session.pending_questions) == 7
    for i, q in enumerate(session.questions_for_review()):
        session.record_question(q["question_id"], "skipped")
        assert len(session.questions_for_review()) == 6 - i
        session = load_session(save_session(session, tmp_path / "fifth-progress.json"))
    assert not session.questions_for_review(respect_interview_limit=False)
    assert session.control["interview_rounds_used"] == 5


def test_exhausted_rounds_keep_critical_unknowns_and_existing_conflicts():
    from tests.test_m1_model_authority_v11 import _jgs_partial
    from tests.test_conflict_participant_integrity import conflict_session
    session = SessionState.new()
    session.set_task("讲解 JGS，面向零基础学生")
    session.control["interview_rounds_used"] = 5
    payload = build_m1_input(session, "critical-unknown")
    response = _jgs_partial(payload)
    parsed = parse_m1_response(json.dumps(response), payload, M1Assets.load().output_schema)
    apply_m1_response(session, payload, parsed)
    assert session.last_next_action == "pause_with_unknowns"
    assert session.gaps[0]["importance"] == "blocking_direction"
    assert session.last_model_judgment["answer_assessment"] == "partial"
    assert not session.pending_questions
    assert session.questions_for_review(respect_interview_limit=False)
    session = conflict_session()
    session.control["interview_rounds_used"] = 5
    payload = build_m1_input(session, "keep-conflicts")
    response = _base(payload)
    response["conflicts"] = [{"conflict_id": row["conflict_id"], "existing_item_ids": row["existing_item_ids"],
        "proposal_ids": [], "description": row["description"], "change_intent": "unclear"} for row in session.open_conflicts]
    response["next_action"] = "resolve_conflict"
    parsed = parse_m1_response(json.dumps(response), payload, M1Assets.load().output_schema)
    apply_m1_response(session, payload, parsed)
    assert session.open_conflicts
    assert not session.pending_questions
    assert session.last_next_action == "resolve_conflict"
    assert session.confirmed_requirements_version is None


class InterviewClient:
    def __init__(self, responder):
        self.responder = responder
        self.calls = []

    def complete_json(self, prompt, payload, schema):
        self.calls.append((prompt, deepcopy(payload), deepcopy(schema)))
        response = self.responder(payload, len(self.calls))
        return ApiResult(content=json.dumps(response, ensure_ascii=False), latency_ms=1,
                         usage={"total_tokens": 1}, response_id="offline-interview", model="offline")


def test_real_workflow_request_uses_wide_first_and_incremental_batches(tmp_path, caplog):
    session = SessionState.new()
    session.set_task(TASK)
    workflow = Phase12Workflow(session, M1Assets.load(), evidence_root=tmp_path)
    payload = workflow.prepare_m1("wide-request")
    client = InterviewClient(lambda p, _: batch_result(p))
    with caplog.at_level("INFO"):
        outcome = workflow.invoke_m1(payload, client, protocol="offline", configured_model="offline")
        apply_m1_response(session, payload, outcome.parsed)
    assert len(client.calls) == 1
    assert len(session.pending_questions) == 7
    assert "comprehensive_batch" in caplog.text and "rounds=0/5" in caplog.text
    for q in session.questions_for_review():
        session.record_question(q["question_id"], "answered", "已提供" + q["scope"])
    assert session.control["interview_rounds_used"] == 1
    payload = workflow.prepare_m1("all-answers")
    def summarize(p, _):
        result = _base(p)
        result["gap_updates"] = [{"update_id": "u-" + row["answer_id"], "target_gap_id": row["gap_id"],
            "answer_id": row["answer_id"], "action": "resolved", "source_ref": {
                "source_id": row["answer_source_id"], "quote": row["answer_text"]},
            "remaining_description": None, "reason": "用户已答"} for row in p["state"]["question_history"]]
        return result
    incremental = InterviewClient(summarize)
    outcome = workflow.invoke_m1(payload, incremental, protocol="offline", configured_model="offline")
    apply_m1_response(session, payload, outcome.parsed)
    assert len(incremental.calls) == 1
    prompt, request, _ = incremental.calls[0]
    assert "前期全面访谈" in prompt
    assert len(request["state"]["question_history"]) == 7
    assert session.control["interview_rounds_used"] == 1  # Sufficient: no forced extra rounds.
    assert not session.questions_for_review()
    assert all(q["assessment_status"] == "applied" for q in session.question_history)


def test_repair_and_failure_do_not_consume_interview_rounds(tmp_path):
    session = SessionState.new()
    session.set_task(TASK)
    workflow = Phase12Workflow(session, M1Assets.load(), evidence_root=tmp_path)
    payload = workflow.prepare_m1("repair")
    def repair(p, call):
        result = batch_result(p)
        if call == 1:
            result["questions"][0]["gap_id"] = "nonexistent"
        return result
    client = InterviewClient(repair)
    outcome = workflow.invoke_m1(payload, client, protocol="offline", configured_model="offline")
    apply_m1_response(session, payload, outcome.parsed)
    assert len(client.calls) == 2 and session.control["interview_rounds_used"] == 1
    assert "每批需用户明确继续" in client.calls[1][0]
    payload = workflow.prepare_m1("timeout")
    class FailingClient:
        def complete_json(self, *_):
            raise ApiError("timeout", "离线模拟超时")
    with pytest.raises(M1CallFailure):
        workflow.invoke_m1(payload, FailingClient(), protocol="offline", configured_model="offline")
    assert session.control["interview_rounds_used"] == 1
    assert len(session.pending_questions) == 7


def test_recovery_keeps_entire_modern_batch(tmp_path):
    session = SessionState.new()
    session.set_task(TASK)
    payload = build_m1_input(session, "batch")
    apply_m1_response(session, payload, batch_result(payload))
    workflow = Phase12Workflow(session, M1Assets.load(), evidence_root=tmp_path)
    payload = workflow.prepare_m1("fallback")
    result = workflow._build_m1_recovery_candidate(payload, reason="offline failure")
    assert len(result["questions"]) == 7


def test_plan_receives_prior_answers_once_even_if_not_promoted_to_requirement():
    session = confirmed_session(with_unknown=False)
    source = session._add_source("源码由执行任务的 AI 在本地读取，运行入口是 run.bat")
    session.question_history.append({"question_id": "q-materials", "field": "existing_code", "scope": "项目材料",
        "text": "源码与启动方式如何提供？", "disposition": "answered", "answer_id": "a-materials",
        "answer_source_id": source, "answer_text": session.sources[-1]["text"], "assessment_status": "applied"})
    payload = build_m2_input(session, "reuse-interview")
    context = payload["interview_context"][0]
    assert context["answer_source_id"] == source
    assert context["assessment_status"] == "applied"
    assert "answer_text" not in context
    assert [row["source_id"] for row in payload["relevant_materials"]].count(source) == 1
    assert not any(row["field"] == "existing_code" for row in payload["requirements"])


def test_m2_workflow_reuses_latest_real_answer_without_duplicate_body(tmp_path, caplog):
    from tests.test_m2 import valid_result
    session = confirmed_session(with_unknown=False)
    previous = session._add_source("旧的材料安排")
    latest = session._add_source("下游 AI 在本地读取源码，运行 run.bat")
    session.question_history.extend([
        {"question_id": "q-material", "field": "existing_code", "scope": "项目材料", "text": "怎样提供材料？",
         "disposition": "answered", "answer_id": "a-old", "answer_source_id": previous,
         "assessment_status": "applied", "superseded_by_answer_id": "a-new"},
        {"question_id": "q-material", "field": "existing_code", "scope": "项目材料", "text": "怎样提供材料？",
         "disposition": "answered", "answer_id": "a-new", "answer_source_id": latest, "assessment_status": "applied"},
    ])
    workflow = Phase12Workflow(session, M1Assets.load(), evidence_root=tmp_path)
    payload = build_m2_input(session, "reuse-latest")
    client = InterviewClient(lambda p, _: valid_result(p))
    with caplog.at_level("INFO"):
        workflow.invoke_m2(payload, client, protocol="offline", configured_model="offline")
    assert len(client.calls) == 1
    prompt, request, _ = client.calls[0]
    assert "承接前期访谈" in prompt
    assert len(request["interview_context"]) == 1
    assert request["interview_context"][0]["answer_source_id"] == latest
    body = json.dumps(request, ensure_ascii=False)
    assert body.count("下游 AI 在本地读取源码，运行 run.bat") == 1
    assert "旧的材料安排" not in body
    assert "questions=1" in caplog.text and "M2 planning request" in caplog.text
