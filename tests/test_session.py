from __future__ import annotations

import pytest

from promptsmith.session import SessionState, StaleResponseError


def proposal(
    pid: str,
    text: str,
    operation: str = "new",
    target: str | None = None,
    *,
    field: str = "constraints",
) -> dict:
    return {
        "proposal_id": pid,
        "operation": operation,
        "target_item_id": target,
        "field": field,
        "text": text,
        "kind": "user_decision",
        "strength": "hard",
        "scope": "报名网站",
        "source_refs": [{"source_id": "u1", "quote": "不做付款"}],
        "depends_on": [],
        "reason": "用户明确说明。",
    }


def m1_result(*, proposals: list[dict] | None = None, questions: list[dict] | None = None) -> dict:
    return {
        "category": {"primary": "coding", "secondary": [], "reason": "交付物是网站。"},
        "proposals": proposals or [],
        "conflicts": [],
        "review_item_ids": [],
        "gaps": [],
        "questions": questions or [],
        "readiness": {
            "goal_identified": True,
            "deliverable_identified": True,
            "blocking_gap_ids": [],
            "reason": "方向清楚。",
        },
        "next_action": "review_requirements",
        "assistant_text": "请核对需求卡。",
    }


def test_new_session_records_task_as_user_source_and_invalidates_downstream() -> None:
    session = SessionState.new()
    assert session.schema_version == "promptsmith.session.v0.2"
    assert session.requirement_version == 0

    session.plan = {"version": 3, "status": "confirmed", "content": "old"}
    session.final_result = {"status": "ready", "content": "old"}
    session.set_task("帮我做一个活动报名网站，不做付款。")

    assert session.requirement_version == 1
    assert session.task_text.endswith("不做付款。")
    assert session.sources[-1]["role"] == "user"
    assert session.sources[-1]["text"] == session.task_text
    assert session.current_source_id == session.sources[-1]["source_id"]
    assert session.plan["status"] == "stale"
    assert session.final_result["status"] == "stale"


def test_skill_search_url_is_persisted_in_session_control() -> None:
    session = SessionState.new()
    session.control["skill_search_url"] = "https://search.example.test/api"

    restored = SessionState.from_dict(session.to_dict())

    assert restored.control["skill_search_url"] == "https://search.example.test/api"


def test_staging_questions_does_not_consume_legacy_round_budget() -> None:
    session = SessionState.new()
    session.set_task("做报名网站")
    question = {
        "question_id": "q1",
        "gap_id": "g1",
        "field": "use_context",
        "scope": "报名网站",
        "text": "实际使用还是演示？",
        "options": ["实际使用", "演示"],
        "reason": "影响范围。",
        "depends_on": [],
    }
    request = session.begin_request("req-1")

    session.stage_m1_result("req-1", request["base_version"], m1_result(questions=[question]))

    # The legacy counter is retained for saved-session compatibility.  Model
    # quality, not this counter, decides whether another question is useful.
    assert session.control["remaining_rounds"] == 2
    assert session.pending_questions[0]["question_id"] == "q1"
    with pytest.raises(StaleResponseError):
        session.stage_m1_result("req-1", request["base_version"], m1_result(questions=[question]))
    assert session.control["remaining_rounds"] == 2


def test_late_response_is_rejected_after_task_change() -> None:
    session = SessionState.new()
    session.set_task("旧任务")
    request = session.begin_request("req-old")
    session.set_task("新任务")

    with pytest.raises(StaleResponseError):
        session.stage_m1_result("req-old", request["base_version"], m1_result())

    assert session.pending_proposals == []
    assert session.task_text == "新任务"


def test_model_candidate_never_confirms_until_user_event() -> None:
    session = SessionState.new()
    session.set_task("帮我做一个活动报名网站，不做付款。")
    request = session.begin_request("req-1")
    session.stage_m1_result(
        "req-1",
        request["base_version"],
        m1_result(
            proposals=[
                proposal("p0", "交付一个活动报名网站。", field="deliverable"),
                proposal("p1", "本次不做付款。"),
            ]
        ),
    )

    assert session.requirements == []
    assert session.confirmed_requirements_version is None

    created = session.accept_proposals(["p0", "p1"])
    assert all(item["confirmation"] == "pending" for item in created)
    assert session.confirmed_requirements_version is None

    confirmed_version = session.confirm_requirements()
    assert confirmed_version == session.requirement_version
    assert all(item["confirmation"] == "confirmed" for item in session.requirements)


def test_answer_skip_and_unsure_are_recorded_without_inventing_answers() -> None:
    session = SessionState.new()
    session.set_task("做报名网站")
    questions = []
    for qid, field in (("q1", "use_context"), ("q2", "features")):
        questions.append(
            {
                "question_id": qid,
                "gap_id": f"g-{qid}",
                "field": field,
                "scope": "报名网站",
                "text": f"问题 {qid}",
                "options": [],
                "reason": "待明确。",
                "depends_on": [],
            }
        )
    request = session.begin_request("req-1")
    session.stage_m1_result("req-1", request["base_version"], m1_result(questions=questions))

    source_id = session.record_question("q1", "answered", "先做课堂演示")
    session.record_question("q2", "skipped")

    assert source_id is not None
    assert session.sources[-1]["text"] == "先做课堂演示"
    assert [row["disposition"] for row in session.question_history] == ["answered", "skipped"]
    assert all("answer" not in row for row in session.question_history)


def test_manual_edit_replaces_item_and_invalidates_confirmation() -> None:
    session = SessionState.new()
    session.set_task("做报名网站")
    request = session.begin_request("req-1")
    session.stage_m1_result(
        "req-1",
        request["base_version"],
        m1_result(
            proposals=[
                proposal("p0", "交付一个报名网站", field="deliverable"),
                proposal("p1", "不做付款"),
            ]
        ),
    )
    item = next(
        row for row in session.accept_proposals(["p0", "p1"]) if row["field"] == "constraints"
    )
    session.confirm_requirements()

    edited = session.edit_requirement(item["item_id"], "支持在线付款")

    assert edited["item_id"] != item["item_id"]
    assert edited["confirmation"] == "pending"
    assert session.confirmed_requirements_version is None
    assert session.requirement_archive[-1]["item_id"] == item["item_id"]
    assert edited["source_refs"] == [{"source_id": session.current_source_id, "quote": "支持在线付款"}]
    assert session.sources[-1]["text"] == "支持在线付款"


def test_user_can_dismiss_model_candidates_without_changing_requirements() -> None:
    session = SessionState.new()
    session.set_task("做报名网站")
    request = session.begin_request("req-1")
    session.stage_m1_result(
        "req-1", request["base_version"], m1_result(proposals=[proposal("p1", "不做付款")])
    )
    version = session.requirement_version

    session.dismiss_proposals()

    assert session.pending_proposals == []
    assert session.requirements == []
    assert session.requirement_version == version
