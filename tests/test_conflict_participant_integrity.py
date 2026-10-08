from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from promptsmith.m1 import M1Assets, M1ValidationError, apply_m1_response, build_m1_input, parse_m1_response
from promptsmith.session import SessionState, SessionStateError
from promptsmith.storage import load_session, save_session


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "resources" / "prompts"
ASSETS = M1Assets.load(DESIGN)


def requirement(item_id: str, field: str, text: str) -> dict:
    return {
        "item_id": item_id,
        "field": field,
        "text": text,
        "kind": "user_decision",
        "strength": "hard",
        "scope": "overall task",
        "source_refs": [],
        "depends_on": [],
        "confirmation": "pending",
    }


def conflict(existing_item_ids: list[str]) -> dict:
    return {
        "conflict_id": "c-payment",
        "existing_item_ids": existing_item_ids,
        "proposal_ids": [],
        "description": "Payment requirements contradict each other.",
        "change_intent": "unclear",
    }


def conflict_session() -> SessionState:
    session = SessionState.new()
    session.set_task("Create an event registration website and settle its payment scope.")
    session.requirements = [
        requirement("r1", "deliverable", "An event registration website"),
        requirement("r2", "constraints", "Do not include payment functionality"),
        requirement("r3", "constraints", "Include online payment functionality"),
        requirement("r4", "preferences", "Use a concise visual style"),
    ]
    session.open_conflicts = [conflict(["r2", "r3"])]
    return session


def response(conflicts: list[dict]) -> dict:
    return {
        "status": "ok",
        "error": None,
        "category": {"primary": "coding", "secondary": [], "reason": "The deliverable is a website."},
        "proposals": [],
        "conflicts": deepcopy(conflicts),
        "review_item_ids": [],
        "gap_updates": [],
        "question_reopens": [],
        "gaps": [],
        "questions": [],
        "readiness": {
            "goal_identified": True,
            "deliverable_identified": True,
            "blocking_gap_ids": [],
            "reason": "The goal and deliverable are present.",
        },
        "next_action": "resolve_conflict" if conflicts else "review_requirements",
        "assistant_text": "Review the current requirements.",
    }


def build_response(session: SessionState, request_id: str, conflicts: list[dict]) -> tuple[dict, dict]:
    payload = build_m1_input(session, request_id, current_date="2026-09-23")
    result = response(conflicts)
    result.update({key: payload[key] for key in ("schema_version", "request_id", "task_id", "base_version")})
    return payload, result


def parse_and_apply(session: SessionState, request_id: str, conflicts: list[dict]) -> None:
    payload, result = build_response(session, request_id, conflicts)
    parsed = parse_m1_response(json.dumps(result, ensure_ascii=False), payload, ASSETS.output_schema)
    apply_m1_response(session, payload, parsed)


@pytest.mark.parametrize(
    "returned_participants",
    [["r3"], ["r3", "r4"]],
    ids=["participant-omitted", "participant-replaced"],
)
def test_existing_conflict_cannot_omit_or_replace_a_live_participant(
    returned_participants: list[str], tmp_path: Path
) -> None:
    session = conflict_session()
    payload, result = build_response(session, "reduced-participants", [conflict(returned_participants)])
    before = deepcopy(session.to_dict())

    with pytest.raises(M1ValidationError, match="冲突|参与方"):
        parse_m1_response(json.dumps(result, ensure_ascii=False), payload, ASSETS.output_schema)

    assert session.to_dict() == before
    assert session.open_conflicts == [conflict(["r2", "r3"])]
    with pytest.raises(SessionStateError, match="冲突"):
        session.confirm_requirements()

    saved = save_session(session, tmp_path / "rejected-conflict-response.json")
    reopened = load_session(saved)
    assert reopened.open_conflicts == [conflict(["r2", "r3"])]
    assert reopened.confirmed_requirements_version is None


def test_state_application_rejects_reduced_conflict_before_business_state_changes() -> None:
    session = conflict_session()
    request = session.begin_request("direct-stage-reduced-conflict")
    before = {
        "requirements": deepcopy(session.requirements),
        "open_conflicts": deepcopy(session.open_conflicts),
        "analysis_basis_version": session.analysis_basis_version,
        "confirmed_requirements_version": session.confirmed_requirements_version,
        "category_suggestion": deepcopy(session.category_suggestion),
    }

    with pytest.raises(SessionStateError, match="冲突|参与方"):
        session.stage_m1_result(request["request_id"], request["base_version"], response([conflict(["r3"])]))

    assert session.requirements == before["requirements"]
    assert session.open_conflicts == before["open_conflicts"]
    assert session.analysis_basis_version == before["analysis_basis_version"]
    assert session.confirmed_requirements_version == before["confirmed_requirements_version"]
    assert session.category_suggestion == before["category_suggestion"]


def test_complete_existing_conflict_is_applied_and_still_blocks_confirmation() -> None:
    session = conflict_session()

    parse_and_apply(session, "complete-conflict", [conflict(["r2", "r3"])])

    assert session.open_conflicts == [conflict(["r2", "r3"])]
    with pytest.raises(SessionStateError, match="冲突"):
        session.confirm_requirements()


def test_omitting_the_entire_existing_conflict_remains_rejected() -> None:
    session = conflict_session()
    payload, result = build_response(session, "missing-entire-conflict", [])

    with pytest.raises(M1ValidationError, match="历史未解决冲突"):
        parse_m1_response(json.dumps(result, ensure_ascii=False), payload, ASSETS.output_schema)

    assert session.open_conflicts == [conflict(["r2", "r3"])]


def test_user_withdrawal_closes_conflict_and_can_confirm_after_reanalysis(tmp_path: Path) -> None:
    session = conflict_session()

    session.withdraw_requirement("r3")
    assert session.open_conflicts == []

    parse_and_apply(session, "after-real-withdrawal", [])
    confirmed_version = session.confirm_requirements()
    saved = save_session(session, tmp_path / "confirmed-after-withdrawal.json")
    reopened = load_session(saved)

    assert confirmed_version == session.requirement_version
    assert reopened.open_conflicts == []
    assert reopened.confirmed_requirements_version == confirmed_version
    assert all(item["item_id"] != "r3" for item in reopened.requirements)


def test_user_can_mark_a_false_conflict_compatible_without_model_restoring_it(tmp_path: Path) -> None:
    session = conflict_session()
    session.requirements[1]["text"] = "已掌握基本积分运算"
    session.requirements[2]["text"] = "直接从分部积分法开始讲解"

    session.mark_conflict_compatible("c-payment")
    assert session.open_conflicts == []

    reopened = load_session(save_session(session, tmp_path / "compatible.json"))
    parse_and_apply(reopened, "reanalysis", [conflict(["r2", "r3"])])
    assert reopened.open_conflicts == []
    assert reopened.confirm_requirements() == reopened.requirement_version


def test_compatibility_decision_expires_when_requirement_text_changes() -> None:
    session = conflict_session()
    session.mark_conflict_compatible("c-payment")
    edited = session.edit_requirement("r3", "Include online payment and mandatory refunds")
    parse_and_apply(session, "new-content", [conflict(["r2", edited["item_id"]])])
    assert session.open_conflicts
