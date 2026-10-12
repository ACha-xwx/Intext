from __future__ import annotations

import json
from copy import deepcopy

import pytest

from promptsmith.m1 import (
    M1Assets, M1ValidationError, apply_m1_response, build_m1_input,
    m1_request_mode, m1_system_prompt, parse_m1_response,
)
from promptsmith.session import SessionState, SessionStateError
from promptsmith.storage import load_session, save_session
from tests.test_conflict_participant_integrity import conflict, conflict_session
from tests.test_generation_timeout_ui import jgs_response
from tests.test_ui_reliability import base_result


def answered_session() -> SessionState:
    """Exercise the normal first round before recording both user answers."""
    session = SessionState.new()
    session.set_task("讲解JGS")
    payload = build_m1_input(session, "first-round")
    parsed = parse_m1_response(
        json.dumps(jgs_response(payload), ensure_ascii=False), payload, M1Assets.load().output_schema,
    )
    apply_m1_response(session, payload, parsed)
    session.accept_proposals([row["proposal_id"] for row in session.pending_proposals])
    session.record_question("q1", "answered", "数值分析里面的")
    session.record_question("q2", "answered", "就是学生学习的讲解")
    return session


def delta_result(payload: dict) -> dict:
    response = base_result(payload)
    response["category"] = {"primary": "learning", "secondary": [], "reason": "学习讲解。"}
    response["gap_updates"] = [
        {
            "update_id": f"update-{row['answer_id']}", "target_gap_id": row["gap_id"],
            "answer_id": row["answer_id"], "action": "resolved",
            "source_ref": {"source_id": row["answer_source_id"], "quote": row["answer_text"]},
            "remaining_description": None, "reason": "用户已回答。",
        }
        for row in payload["state"]["question_history"] if row["assessment_status"] == "pending"
    ]
    return response


def parse_delta(payload: dict, response: dict) -> dict:
    return parse_m1_response(
        json.dumps(response, ensure_ascii=False), payload, M1Assets.load().output_schema,
        incremental=True,
    )


def old_gap(*, blocking: bool = False) -> dict:
    return {
        "gap_id": "g-old", "field": "constraints", "scope": "当前讲解",
        "description": "讲解时长未知。", "importance": "blocking_direction" if blocking else "can_defer",
        "origin": "user_skipped", "source_refs": [], "depends_on": [],
    }


def test_two_pending_answers_apply_only_updates_and_keep_omitted_unknown(tmp_path) -> None:
    session = answered_session()
    session.gaps.append(old_gap())
    before_requirements = deepcopy(session.requirements)
    payload = build_m1_input(session, "second-round")
    raw_result = delta_result(payload)
    before_raw = deepcopy(raw_result)
    parsed = parse_delta(payload, raw_result)
    apply_m1_response(session, payload, parsed)
    assert raw_result == before_raw
    assert session.requirements == before_requirements
    assert session.pending_proposals == []
    assert session.gaps == [old_gap()]
    assert [row["assessment_status"] for row in session.question_history] == ["applied", "applied"]
    assert [row["answer_text"] for row in session.question_history] == ["数值分析里面的", "就是学生学习的讲解"]
    saved = save_session(session, tmp_path / "delta.json")
    assert load_session(saved).to_dict() == session.to_dict()


@pytest.mark.parametrize("action", ["partial", "unresolved", "resolved", "not_applicable"])
def test_delta_gap_update_keeps_or_closes_only_its_evidenced_gap(action: str) -> None:
    session = answered_session()
    session.gaps.append(old_gap())
    payload = build_m1_input(session, f"gap-{action}")
    response = delta_result(payload)
    update = response["gap_updates"][0]
    update["action"] = action
    remaining = "具体算法范围仍未说明。" if action in {"partial", "unresolved"} else None
    update["remaining_description"] = remaining
    if remaining:
        response["readiness"]["blocking_gap_ids"] = ["g1"]
        response["next_action"] = "pause_with_unknowns"
    parsed = parse_delta(payload, response)
    apply_m1_response(session, payload, parsed)
    gaps = {row["gap_id"]: row for row in session.gaps}
    assert "g-old" in gaps and "g2" not in gaps
    if remaining:
        assert gaps["g1"]["description"] == remaining
        assert gaps["g1"]["origin"] == ("ambiguous" if action == "partial" else "user_unsure")
    else:
        assert "g1" not in gaps


def test_omitted_blocking_gap_still_blocks_false_ready_delta() -> None:
    session = answered_session()
    # Unknown is retained; explicit user_skipped is now an exclusion.
    session.gaps.append({**old_gap(blocking=True), "origin": "user_unsure"})
    payload = build_m1_input(session, "blocking-omitted")
    response = delta_result(payload)
    before = deepcopy(session.to_dict())
    with pytest.raises(M1ValidationError, match="阻断|门槛"):
        parse_delta(payload, response)
    assert session.to_dict() == before


def test_invalid_gap_resolution_cannot_remove_old_gap() -> None:
    session = answered_session()
    payload = build_m1_input(session, "invalid-gap-answer")
    response = delta_result(payload)
    response["gap_updates"][0]["source_ref"] = {"source_id": "u1", "quote": "讲解JGS"}
    with pytest.raises(M1ValidationError, match="回答|来源"):
        parse_delta(payload, response)
    assert {row["gap_id"] for row in session.gaps} == {"g1", "g2"}
    assert all(row["assessment_status"] == "pending" for row in session.question_history)


def test_omitted_conflict_is_restored_and_still_blocks_confirmation(tmp_path) -> None:
    session = conflict_session()
    payload = build_m1_input(session, "delta-omitted-conflict")
    response = base_result(payload)
    response["next_action"] = "resolve_conflict"
    parsed = parse_delta(payload, response)
    assert parsed["conflicts"] == [conflict(["r2", "r3"])]
    apply_m1_response(session, payload, parsed)
    with pytest.raises(SessionStateError, match="冲突"):
        session.confirm_requirements()
    restored = load_session(save_session(session, tmp_path / "conflict.json"))
    assert restored.open_conflicts == [conflict(["r2", "r3"])]


@pytest.mark.parametrize("participants", [["r3"], ["r3", "r4"]])
def test_returned_conflict_cannot_drop_or_replace_existing_participant(participants) -> None:
    session = conflict_session()
    payload = build_m1_input(session, "delta-broken-conflict")
    response = base_result(payload)
    response["conflicts"] = [conflict(participants)]
    response["next_action"] = "resolve_conflict"
    with pytest.raises(M1ValidationError, match="参与方"):
        parse_delta(payload, response)
    assert session.open_conflicts == [conflict(["r2", "r3"])]


def test_omitted_conflict_cannot_be_claimed_ready_and_default_mode_remains_strict() -> None:
    session = conflict_session()
    payload = build_m1_input(session, "conflict-omitted")
    response = base_result(payload)
    with pytest.raises(M1ValidationError, match="冲突"):
        parse_delta(payload, response)
    response["next_action"] = "resolve_conflict"
    with pytest.raises(M1ValidationError, match="历史未解决冲突"):
        parse_m1_response(json.dumps(response), payload, M1Assets.load().output_schema)


def test_user_withdrawn_conflict_party_can_close_after_delta_reanalysis() -> None:
    session = conflict_session()
    session.withdraw_requirement("r3")
    assert not session.open_conflicts
    payload = build_m1_input(session, "withdrawn-conflict")
    response = base_result(payload)
    apply_m1_response(session, payload, parse_delta(payload, response))
    assert session.confirm_requirements() == session.requirement_version


def test_delta_cannot_readd_an_unchanged_existing_requirement() -> None:
    session = answered_session()
    payload = build_m1_input(session, "duplicate-old")
    response = delta_result(payload)
    old = session.requirements[0]
    response["proposals"] = [{
        **{key: deepcopy(old[key]) for key in ("field", "text", "kind", "strength", "scope", "source_refs", "depends_on")},
        "proposal_id": "p-repeat", "operation": "new", "target_item_id": None,
        "reason": "重复提取历史需求。",
    }]
    with pytest.raises(M1ValidationError, match="重复|已有需求"):
        parse_delta(payload, response)


def test_delta_user_proposal_requires_current_answer_evidence() -> None:
    session = answered_session()
    payload = build_m1_input(session, "historical-reextraction")
    response = delta_result(payload)
    response["proposals"] = [{
        "proposal_id": "p-old-source", "operation": "new", "target_item_id": None,
        "field": "goal", "text": "JGS讲解", "kind": "user_decision", "strength": "hard", "scope": "整体任务",
        "source_refs": [{"source_id": "u1", "quote": "讲解JGS"}], "depends_on": [], "reason": "重新提取旧任务。",
    }]
    with pytest.raises(M1ValidationError, match="本轮|回答"):
        parse_delta(payload, response)
    response["proposals"][0].update(
        field="audience", text="用于学生学习", source_refs=[{"source_id": "u3", "quote": "学生学习"}],
    )
    assert parse_delta(payload, response)["proposals"][0]["text"] == "用于学生学习"


@pytest.mark.parametrize("missing", ["gaps", "conflicts", "proposals", "gap_updates"])
def test_delta_accepts_missing_collections_but_keeps_unassessed_gaps(missing: str) -> None:
    session = answered_session()
    payload = build_m1_input(session, "missing-field")
    response = delta_result(payload)
    response.pop(missing)
    if missing == "gap_updates":
        with pytest.raises(M1ValidationError, match="阻断|复核|门槛"):
            parse_delta(payload, response)
        return
    parsed = parse_delta(payload, response)
    apply_m1_response(session, payload, parsed)
    assert session.question_history and all(row["answer_text"] for row in session.question_history)


def test_delta_merge_does_not_hide_duplicate_gap_ids() -> None:
    session = answered_session()
    session.gaps.append(old_gap())
    payload = build_m1_input(session, "duplicate-gap-id")
    response = delta_result(payload)
    response["gaps"] = [old_gap(), old_gap()]
    before = deepcopy(session.to_dict())

    with pytest.raises(M1ValidationError, match="gap ID在响应内重复"):
        parse_delta(payload, response)

    assert session.to_dict() == before


def test_delta_merge_does_not_hide_duplicate_conflict_ids() -> None:
    session = conflict_session()
    payload = build_m1_input(session, "duplicate-conflict-id")
    response = base_result(payload)
    response["conflicts"] = [conflict(["r2", "r3"]), conflict(["r2", "r3"])]
    response["next_action"] = "resolve_conflict"
    before = deepcopy(session.to_dict())

    with pytest.raises(M1ValidationError, match="conflict ID在响应内重复"):
        parse_delta(payload, response)

    assert session.to_dict() == before


def test_delta_input_error_does_not_expand_old_conflicts_or_mutate_session() -> None:
    session = conflict_session()
    payload = build_m1_input(session, "delta-input-error")
    response = base_result(payload)
    response.update(
        status="input_error",
        error={"code": "invalid_input", "message": "无法按契约处理本轮输入。"},
        category={"primary": "general", "secondary": [], "reason": "输入错误。"},
        readiness={
            "goal_identified": False,
            "deliverable_identified": False,
            "blocking_gap_ids": [],
            "reason": "输入错误。",
        },
        next_action="pause_with_unknowns",
    )
    before = deepcopy(session.to_dict())

    parsed = parse_delta(payload, response)

    assert parsed == response
    assert parsed["conflicts"] == []
    assert session.to_dict() == before


@pytest.mark.parametrize("raw", ['{"a":', '{"a":1,"a":2}', '{"a":NaN}', '[]'])
def test_json_errors_have_their_own_compatible_exception_type(raw: str) -> None:
    from promptsmith.m1 import M1JsonError
    session = answered_session()
    payload = build_m1_input(session, "invalid-json")
    with pytest.raises(M1JsonError) as captured:
        parse_m1_response(raw, payload, M1Assets.load().output_schema, incremental=True)
    assert isinstance(captured.value, M1ValidationError)


def test_modes_use_separate_short_prompt_and_full_prompt_is_unchanged() -> None:
    assets = M1Assets.load()
    assert m1_request_mode(has_pending_answers=True) == "incremental"
    assert m1_request_mode(has_pending_answers=True, compact_retry=True) == "compact_retry"
    assert m1_request_mode(has_pending_answers=False) == "full"
    assert m1_system_prompt(assets.system_prompt, mode="full") == assets.system_prompt
    incremental = m1_system_prompt(assets.system_prompt, mode="incremental")
    compact = m1_system_prompt(assets.system_prompt, mode="compact_retry")
    assert "本轮只处理新增用户回答" in incremental
    assert assets.system_prompt not in incremental
    assert len(incremental) < len(assets.system_prompt)  # Both now share one concise current contract.
    assert "精简重试" in compact and "非必要建议" in compact
    with pytest.raises(ValueError, match="模式"):
        m1_system_prompt(assets.system_prompt, mode="invalid")
