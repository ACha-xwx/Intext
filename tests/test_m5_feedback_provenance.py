from copy import deepcopy
import json

import pytest

from promptsmith.m1 import build_m1_input
from promptsmith.m5 import build_m5_input, parse_m5_response, apply_m5_response, record_m5_feedback
from promptsmith.session import SessionState, SessionStateError
from promptsmith.storage import save_session, load_session


def staged_feedback(text="喜欢 B 的直接，但不要口号"):
    session = SessionState.new()
    session.set_task("写摄影社通知，语气的活泼程度尚未确定。")
    payload = build_m5_input(session, "m5-provenance", criterion_description="活泼程度")
    raw = json.dumps({
        "schema_version": "m5.v0.1", "request_id": payload["request_id"],
        "task_id": session.task_id, "base_version": payload["base_version"],
        "status": "ok", "error": None, "example": {
            "dimension": "活泼程度", "shared_assumptions": ["示例中的日期与联系人是假设"],
            "option_a": "王老师邀请你于2026-11-02参加，来一起定格精彩！",
            "option_b": "王老师邀请你于2026-11-02参加摄影体验。",
            "difference_summary": "A更活泼，B更平实。",
            "unsupported_assumptions": ["王老师", "2026-11-02"],
        },
    }, ensure_ascii=False)
    example = apply_m5_response(session, payload, parse_m5_response(raw, payload))
    feedback = record_m5_feedback(session, example["example_id"], "b", text)
    candidate = deepcopy(feedback["candidate"])
    candidate["proposal_id"] = candidate.pop("candidate_id")
    candidate["source_request_id"] = example["example_id"]
    candidate["source_base_version"] = session.requirement_version
    candidate["valid_for_version"] = session.requirement_version
    session.pending_proposals.append(candidate)
    return session, candidate["proposal_id"], feedback


def test_accepted_m5_feedback_has_user_source_in_m1_and_saved_session(tmp_path):
    session, proposal_id, feedback = staged_feedback()
    before = deepcopy(session.sources)
    accepted = session.accept_proposals([proposal_id])[0]
    assert accepted["source_refs"], "M5反馈被接受后缺少用户原话来源"
    ref = accepted["source_refs"][0]
    assert ref["quote"] == feedback["feedback_text"]
    new_source = next(row for row in session.sources if row["source_id"] == ref["source_id"])
    assert new_source["role"] == "user"
    assert new_source["text"] == feedback["feedback_text"]
    assert session.sources[:len(before)] == before
    assert not any(term in json.dumps(accepted, ensure_ascii=False) for term in ["王老师", "2026-11-02"])
    assert session.m5_feedback[-1]["accepted_item_id"] == accepted["item_id"]
    payload = build_m1_input(session, "after-m5")
    assert payload["state"]["requirements"][0]["source_refs"] == [ref]
    save_session(session, tmp_path / "saved.json")
    restored = load_session(tmp_path / "saved.json")
    assert restored.requirements == session.requirements
    assert restored.sources == session.sources
    assert restored.m5_feedback == session.m5_feedback


def test_m5_choice_only_source_does_not_claim_example_details():
    session, proposal_id, feedback = staged_feedback("")
    accepted = session.accept_proposals([proposal_id])[0]
    assert accepted["source_refs"]
    quote = accepted["source_refs"][0]["quote"]
    assert "B" in quote and "待确认" in quote
    assert "王老师" not in quote and "2026-11-02" not in quote
    assert accepted["kind"] == "pending_interpretation"


def test_m5_candidate_with_no_feedback_origin_is_rejected_atomically():
    session, proposal_id, feedback = staged_feedback()
    session.m5_feedback.clear()
    before = deepcopy(session.to_dict())
    with pytest.raises(SessionStateError, match="M5.*来源"):
        session.accept_proposals([proposal_id])
    assert session.to_dict() == before


def test_accepting_m5_feedback_invalidates_prior_m1_readiness():
    session, proposal_id, feedback = staged_feedback()
    session.analysis_basis_version = session.requirement_version
    session.accept_proposals([proposal_id])
    assert session.analysis_basis_version is None, "M1尚未分析新反馈，不能沿用此前充分性判断"


def test_m5_batch_failure_rolls_back_new_sources_and_feedback_links():
    session, proposal_id, feedback = staged_feedback()
    orphan = deepcopy(session.pending_proposals[0])
    orphan["proposal_id"] = "m5-orphan"
    session.pending_proposals.append(orphan)
    before = deepcopy(session.to_dict())
    with pytest.raises(SessionStateError, match="M5.*来源"):
        session.accept_proposals([proposal_id, "m5-orphan"])
    assert session.to_dict() == before
