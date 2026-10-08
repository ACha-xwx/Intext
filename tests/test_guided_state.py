from __future__ import annotations

from copy import deepcopy

import pytest

from promptsmith.exporter import export_markdown
from promptsmith.finalization import build_final_draft, stage_final_draft, validate_delivery_entry
from promptsmith.m2 import M2Assets, apply_m2_response, build_m2_input, parse_m2_response
from promptsmith.session import SessionState, SessionStateError
from promptsmith.storage import load_session, save_session
from test_m2 import valid_result
from test_session import m1_result, proposal
import json


def staged_session(*, blocking: bool = False) -> SessionState:
    state = SessionState.new()
    state.set_task("讲一下 JGS，数值分析领域，给学生的学习讲义")
    state.choose_category("learning")
    response = m1_result(proposals=[proposal("p1", "给学生的数值分析学习讲义", field="deliverable")])
    if blocking:
        response["gaps"] = [{"gap_id": "g1", "field": "topic", "scope": "讲解对象", "description": "JGS 的具体含义还没有确定", "importance": "blocking_direction", "origin": "ambiguous", "source_refs": [], "depends_on": []}]
        response["readiness"]["blocking_gap_ids"] = ["g1"]
        response["questions"] = [{"question_id": "q1", "gap_id": "g1", "field": "topic", "scope": "讲解对象", "text": "JGS 具体指什么？", "options": [], "reason": "影响讲解对象", "depends_on": []}]
    request = state.begin_request("first")
    state.stage_m1_result("first", request["base_version"], response)
    return state


def make_plan(state: SessionState) -> None:
    payload = build_m2_input(state, "plan")
    parsed = parse_m2_response(json.dumps(valid_result(payload), ensure_ascii=False), payload, M2Assets.load().output_schema)
    apply_m2_response(state, payload, parsed)


def test_preview_confirmation_is_one_atomic_user_action() -> None:
    state = staged_session()
    preview = state.requirements_preview()
    version = state.confirm_requirements_preview(preview)
    assert state.confirmed_requirements_version == version
    assert not state.pending_proposals
    assert state.requirements[0]["confirmation"] == "confirmed"
    assert state.analysis_basis_version == version


def test_old_or_changed_preview_cannot_confirm_unseen_content() -> None:
    state = staged_session()
    preview = state.requirements_preview()
    state.pending_proposals[0]["text"] = "用户尚未看过的新内容"
    before = state.to_dict()
    with pytest.raises(SessionStateError, match="预览|变化"):
        state.confirm_requirements_preview(preview)
    assert state.to_dict() == before


def test_preview_conflict_failure_does_not_partially_accept() -> None:
    state = staged_session()
    state.pending_proposals.append(proposal("p2", "不要提供讲义", field="deliverable"))
    state.open_conflicts = [{"conflict_id": "c1", "existing_item_ids": [], "proposal_ids": ["p1", "p2"], "description": "交付物矛盾"}]
    before = state.to_dict()
    with pytest.raises(SessionStateError, match="冲突"):
        state.confirm_requirements_preview(state.requirements_preview())
    assert state.to_dict() == before


def test_draft_authorization_keeps_direction_unknown_and_survives_export(tmp_path) -> None:
    state = staged_session(blocking=True)
    with pytest.raises(SessionStateError):
        state.confirm_requirements_preview(state.requirements_preview())
    preview = state.requirements_preview()
    assert "JGS" in preview["draft_explanation"]
    state.confirm_requirements_preview(preview, allow_draft=True)
    assert state.gaps[0]["importance"] == "blocking_direction"
    assert state.current_draft_authorization() is not None
    with pytest.raises(SessionStateError, match="未决"):
        state.confirm_requirements()
    make_plan(state)
    assert state.plan["source_snapshot"]["unresolved_items"][0]["gap_id"] == "g1"
    state.confirm_plan_preview(state.plan_preview())
    validate_delivery_entry(state)
    stage_final_draft(state, build_final_draft(state))
    path = tmp_path / "draft.json"
    save_session(state, path)
    reopened = load_session(path)
    assert reopened.gaps == state.gaps
    assert reopened.current_draft_authorization() == state.current_draft_authorization()
    exported = export_markdown(reopened, tmp_path / "draft.md", mode="draft").read_text(encoding="utf-8")
    assert "JGS 的具体含义还没有确定" in exported
    assert "先做草稿" in exported
    assert "不代表" in exported


def test_draft_authorization_does_not_bypass_conflict_or_stale_analysis() -> None:
    state = staged_session(blocking=True)
    state.analysis_basis_version = None
    before = state.to_dict()
    with pytest.raises(SessionStateError, match="分析"):
        state.confirm_requirements_preview(state.requirements_preview(), allow_draft=True)
    assert state.to_dict() == before


def test_draft_authorization_is_invalidated_after_upstream_change() -> None:
    state = staged_session(blocking=True)
    state.confirm_requirements_preview(state.requirements_preview(), allow_draft=True)
    state.edit_requirement(state.requirements[0]["item_id"], "改为面向研究者的技术文章")
    assert state.current_draft_authorization() is None
    with pytest.raises(SessionStateError):
        state.validate_m2_entry()


def test_draft_can_keep_model_goal_uncertain_when_known_deliverable_exists():
    state = staged_session(blocking=True)
    state.last_readiness['goal_identified'] = False
    state.confirm_requirements_preview(state.requirements_preview(), allow_draft=True)
    assert state.current_draft_authorization()
    assert state.last_readiness['goal_identified'] is False
    assert state.gaps[0]['importance'] == 'blocking_direction'
    state.validate_m2_entry()
    with pytest.raises(SessionStateError):
        state.confirm_requirements()


def test_accepting_goal_interpretation_refreshes_only_corresponding_readiness():
    state = staged_session(blocking=True)
    state.last_readiness['goal_identified'] = False
    state.gaps[0]['field'] = 'goal'
    state.pending_questions[0]['field'] = 'goal'
    guess = proposal('guess', '比较两种迭代方法', field='goal')
    guess.update(kind='pending_interpretation', scope='讲解对象', interpretation_for={'gap_id':'g1', 'question_id':'q1', 'reason':'待用户核对'})
    state.pending_proposals.append(guess)
    state.decide_interpretation('guess', 'accepted')
    assert state.last_readiness['goal_identified'] is True
    state.confirm_requirements_preview(state.requirements_preview())
    state.validate_m2_entry()


def test_plan_preview_confirms_all_shown_key_work_atomically() -> None:
    state = staged_session()
    state.confirm_requirements_preview(state.requirements_preview())
    make_plan(state)
    with pytest.raises(SessionStateError, match="复核"):
        state.confirm_plan()
    preview = state.plan_preview()
    version = state.confirm_plan_preview(preview)
    assert state.plan["confirmed_plan_version"] == version
    assert state.plan["reviewed_key_work_ids"] == ["k1"]
    assert not state.plan["pending_key_work_review_ids"]


def test_changed_plan_preview_is_rejected_without_review_mutations() -> None:
    state = staged_session()
    state.confirm_requirements_preview(state.requirements_preview())
    make_plan(state)
    preview = state.plan_preview()
    state.edit_plan_goal("已经更改的方案目标")
    before = state.to_dict()
    with pytest.raises(SessionStateError):
        state.confirm_plan_preview(preview)
    assert state.to_dict() == before


def test_supplement_preserves_task_history_candidates_and_deduplicates_retry() -> None:
    state = staged_session(blocking=True)
    state.record_question("q1", "skipped")
    task, history, candidates = state.task_text, deepcopy(state.question_history), deepcopy(state.pending_proposals)
    source = state.record_supplement("我想先讲基本概念")
    version = state.requirement_version
    assert state.record_supplement("我想先讲基本概念") == source
    assert state.requirement_version == version
    assert state.task_text == task
    assert state.question_history[:-1] == history
    assert state.question_history[-1]["assessment_status"] == "pending"
    assert [row["proposal_id"] for row in state.pending_proposals] == [row["proposal_id"] for row in candidates]


def test_reopen_skipped_question_preserves_history_and_analysis_until_answer() -> None:
    state = staged_session(blocking=True)
    state.record_question("q1", "skipped")
    before = deepcopy(state.question_history)
    version = state.requirement_version
    question = state.reopen_question("q1")
    assert question["gap_id"] == "g1"
    assert state.question_history == before
    assert state.requirement_version == version
    state.record_question("q1", "answered", "我指的是两种迭代方法的比较")
    assert len(state.question_history) == len(before) + 1
    assert state.question_history[-1]["answer_text"] == "我指的是两种迭代方法的比较"


def test_new_analysis_preserves_pending_candidates_and_source_versions() -> None:
    state = staged_session()
    state.record_supplement("讲义里要有一个例子")
    request = state.begin_request("second")
    state.stage_m1_result("second", request["base_version"], m1_result(proposals=[proposal("p1", "包含一个例子")]))
    assert len(state.pending_proposals) == 2
    assert len({row["proposal_id"] for row in state.pending_proposals}) == 2
    assert {row["source_request_id"] for row in state.pending_proposals} == {"first", "second"}


def test_guess_requires_separate_explicit_choice_and_resolves_only_its_gap() -> None:
    state = staged_session(blocking=True)
    guess = proposal("guess", "比较 Jacobi 与 Gauss–Seidel 迭代法", field="topic")
    guess.update(kind="pending_interpretation", scope="讲解对象", interpretation_for={"gap_id": "g1", "question_id": "q1", "reason": "结合数值分析背景提出的可能解释"}, source_request_id="first", source_base_version=state.requirement_version, valid_for_version=state.requirement_version)
    state.pending_proposals.append(guess)
    state.pending_proposals.append(proposal("extra", "新增付费教材"))
    with pytest.raises(SessionStateError, match="推测|解释"):
        state.confirm_requirements_preview(state.requirements_preview())
    item = state.decide_interpretation("guess", "accepted")
    assert item["kind"] == "user_decision"
    assert not state.gaps
    assert {row["proposal_id"] for row in state.pending_proposals} == {"p1", "extra"}
    assert state.question_history[-1]["assessment_status"] == "applied"
    assert state.interpretation_history[-1]["decision"] == "accepted"


def test_skipping_guess_keeps_unknown_and_records_no_user_fact() -> None:
    state = staged_session(blocking=True)
    guess = proposal("guess", "一种可能解释", field="topic")
    guess.update(kind="pending_interpretation", scope="讲解对象", interpretation_for={"gap_id": "g1", "question_id": "q1", "reason": "已有信息"})
    state.pending_proposals.append(guess)
    state.decide_interpretation("guess", "skipped")
    assert state.gaps[0]["gap_id"] == "g1"
    assert not state.requirements
    assert state.interpretation_history[-1]["decision"] == "skipped"


def test_linked_guess_cannot_bypass_explicit_choice_via_bulk_accept() -> None:
    state = staged_session(blocking=True)
    guess = proposal("guess", "一种有上下文的解释", field="topic")
    guess.update(kind="pending_interpretation", scope="讲解对象", interpretation_for={"gap_id": "g1", "question_id": "q1", "reason": "已有信息"})
    state.pending_proposals.append(guess)
    before = state.to_dict()
    with pytest.raises(SessionStateError, match="解释|推测"):
        state.accept_proposals(["guess"])
    assert state.to_dict() == before


def test_ordinary_skip_can_proceed_without_extra_analysis() -> None:
    state = staged_session(blocking=True)
    state.gaps[0]["importance"] = "can_defer"
    state.last_readiness["blocking_gap_ids"] = []
    state.record_question("q1", "skipped")
    assert state.analysis_basis_version == state.requirement_version
    state.confirm_requirements_preview(state.requirements_preview())
    state.validate_m2_entry()
    assert state.gaps[0]["origin"] == "user_skipped"


def test_authorized_draft_can_pass_optional_skill_entry_without_resolving_unknown(tmp_path) -> None:
    from promptsmith.skill_catalog import SkillCatalog
    state = staged_session(blocking=True)
    state.confirm_requirements_preview(state.requirements_preview(), allow_draft=True)
    make_plan(state)
    state.confirm_plan_preview(state.plan_preview())
    validate_delivery_entry(state)
    catalog = SkillCatalog.load()
    result = catalog.match(state.plan["content"]["key_work"])
    assert result.status in {"ok", "no_match"}
    state.set_skill_state(status="candidates_ready" if result.status == "ok" else "no_match", candidate_batch={"batch_id": "guided", "catalog_hash": catalog.snapshot_hash, "result": result.to_dict()})
    assert state.gaps[0]["importance"] == "blocking_direction"
    stage_final_draft(state, build_final_draft(state))
    export_markdown(state, tmp_path / "optional.md", mode="draft")


def test_rejecting_interpretation_cancels_inflight_analysis_without_extra_question() -> None:
    state = staged_session(blocking=True)
    guess = proposal("guess", "一种有上下文的解释", field="topic")
    guess.update(kind="pending_interpretation", scope="讲解对象", interpretation_for={"gap_id": "g1", "question_id": "q1", "reason": "已有信息"})
    state.pending_proposals.append(guess)
    state.begin_request("late")
    state.decide_interpretation("guess", "rejected")
    assert not state.pending_requests
    assert state.analysis_basis_version == state.requirement_version
    assert len(state.pending_questions) == 1


def test_correction_preserves_old_answer_but_only_new_answer_is_pending() -> None:
    state = staged_session(blocking=True)
    state.record_question("q1", "answered", "是某种矩阵算法")
    old_answer_id = state.question_history[-1]["answer_id"]
    state.reopen_question("q1")
    state.record_question("q1", "answered", "更正：需要比较两种不同的迭代方法")
    assert len(state.question_history) == 2
    assert state.question_history[0]["answer_id"] == old_answer_id
    assert state.question_history[0]["answer_text"] == "是某种矩阵算法"
    pending = [row for row in state.question_history if row["assessment_status"] == "pending"]
    assert [row["answer_text"] for row in pending] == ["更正：需要比较两种不同的迭代方法"]


def test_direct_supplement_can_target_a_shown_skipped_gap_and_retry_once() -> None:
    state = staged_session(blocking=True)
    state.record_question("q1", "skipped")
    old_history = deepcopy(state.question_history)
    source = state.record_supplement("指两种迭代方法的比较", gap_ids=["g1"])
    assert state.question_history[:-1] == old_history
    answer = state.question_history[-1]
    assert answer["gap_id"] == "g1"
    assert answer["answer_source_id"] == source
    before = state.to_dict()
    assert state.record_supplement("指两种迭代方法的比较", gap_ids=["g1"]) == source
    assert state.to_dict() == before


def test_targeted_supplement_validation_failure_is_atomic() -> None:
    state = staged_session(blocking=True)
    before = state.to_dict()
    with pytest.raises(SessionStateError):
        state.record_supplement("更正说明", gap_ids=["g1", "missing"])
    assert state.to_dict() == before


def test_answer_resolution_retires_stale_guess_without_adopting_it() -> None:
    state = staged_session(blocking=True)
    guess = proposal("guess", "模型提出的错误解释", field="topic")
    guess.update(kind="pending_interpretation", scope="讲解对象", interpretation_for={"gap_id": "g1", "question_id": "q1", "reason": "已有信息"})
    state.pending_proposals.append(guess)
    state.record_question("q1", "answered", "不是这个意思，讲义要比较两种独立迭代方法")
    answer = state.question_history[-1]
    response = m1_result()
    response["gap_updates"] = [{"update_id": "update-1", "target_gap_id": "g1", "answer_id": answer["answer_id"], "action": "resolved", "source_ref": {"source_id": answer["answer_source_id"], "quote": answer["answer_text"]}, "remaining_description": None, "reason": "用户已明确说明讲解对象"}]
    request = state.begin_request("correction")
    state.stage_m1_result("correction", request["base_version"], response)
    assert not state.gaps
    assert not any(row.get("interpretation_for") for row in state.pending_proposals)
    assert not any("错误解释" in row["text"] for row in state.requirements)
    assert state.deferred_proposals[-1]["deferred_reason"] == "gap_resolved_by_answer"


def test_explicit_draft_is_immediately_editable_saveable_and_exportable_before_plan_confirmation(tmp_path) -> None:
    from promptsmith.finalization import confirm_final, edit_final_note
    state = staged_session(blocking=True)
    state.confirm_requirements_preview(state.requirements_preview(), allow_draft=True)
    make_plan(state)
    assert state.plan["status"] == "draft"
    assert state.plan["confirmed_plan_version"] is None
    draft = build_final_draft(state, allow_unconfirmed_plan=True)
    stage_final_draft(state, draft)
    assert state.plan["status"] == "draft"
    assert "方案尚未核对" in state.final_result["canonical_body"]
    edit_final_note(state, "note1", "希望优先整理直觉解释")
    path = tmp_path / "unreviewed.json"
    save_session(state, path)
    reopened = load_session(path)
    assert reopened.plan["confirmed_plan_version"] is None
    text = export_markdown(reopened, tmp_path / "first-draft.md", mode="draft").read_text(encoding="utf-8")
    assert "希望优先整理直觉解释" in text
    assert "JGS 的具体含义还没有确定" in text
    with pytest.raises(SessionStateError, match="方案"):
        confirm_final(reopened)
    with pytest.raises(SessionStateError):
        export_markdown(reopened, tmp_path / "not-final.md", mode="final")


def test_interim_draft_entry_cannot_bypass_authorization_or_conflicts() -> None:
    state = staged_session()
    state.confirm_requirements_preview(state.requirements_preview())
    make_plan(state)
    with pytest.raises(SessionStateError):
        build_final_draft(state, allow_unconfirmed_plan=True)
    authorized = staged_session(blocking=True)
    authorized.confirm_requirements_preview(authorized.requirements_preview(), allow_draft=True)
    make_plan(authorized)
    authorized.open_conflicts.append({"conflict_id": "unresolved"})
    with pytest.raises(SessionStateError, match="冲突"):
        build_final_draft(authorized, allow_unconfirmed_plan=True)


def test_reviewing_plan_rebuilds_interim_draft_as_normal_result() -> None:
    from promptsmith.finalization import confirm_final
    state = staged_session(blocking=True)
    state.confirm_requirements_preview(state.requirements_preview(), allow_draft=True)
    make_plan(state)
    stage_final_draft(state, build_final_draft(state, allow_unconfirmed_plan=True))
    state.confirm_plan_preview(state.plan_preview())
    stage_final_draft(state, build_final_draft(state))
    assert not state.final_result["content"].get("plan_review_pending")
    assert "方案尚未核对" not in state.final_result["canonical_body"]
    confirm_final(state)


def test_legacy_unlinked_guess_accepts_one_explicit_choice_with_user_provenance() -> None:
    state = staged_session()
    guess = proposal("legacy", "我需要直观的概念解释", field="learning_goal")
    guess["kind"] = "pending_interpretation"
    state.pending_proposals.append(guess)
    with pytest.raises(SessionStateError, match="推测|解释"):
        state.confirm_requirements_preview(state.requirements_preview())
    selected = state.accept_generic_interpretation("legacy")
    assert selected["kind"] == "user_decision"
    assert "用户确认这段理解" in selected["source_refs"][-1]["quote"]
    assert [row["proposal_id"] for row in state.pending_proposals] == ["p1"]
    state.confirm_requirements_preview(state.requirements_preview())
