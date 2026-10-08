from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from promptsmith.m1 import M1Assets, M1ValidationError, build_m1_input, parse_m1_response
from promptsmith.session import SessionState, SessionStateError, StaleResponseError
from promptsmith.storage import load_session, save_session


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "resources" / "prompts"


def candidate(
    proposal_id: str,
    field: str,
    text: str,
    *,
    operation: str = "new",
    target: str | None = None,
    depends_on: list[str] | None = None,
    scope: str = "整体任务",
) -> dict:
    return {
        "proposal_id": proposal_id,
        "operation": operation,
        "target_item_id": target,
        "field": field,
        "text": text,
        "kind": "user_decision",
        "strength": "hard",
        "scope": scope,
        "source_refs": [{"source_id": "u1", "quote": "做一个活动报名网站，不做付款"}],
        "depends_on": depends_on or [],
        "reason": "用户明确说明。",
    }


def result(
    *,
    proposals: list[dict] | None = None,
    conflicts: list[dict] | None = None,
    review_item_ids: list[str] | None = None,
    gaps: list[dict] | None = None,
    questions: list[dict] | None = None,
    next_action: str = "review_requirements",
) -> dict:
    gaps = gaps or []
    return {
        "status": "ok",
        "error": None,
        "category": {"primary": "coding", "secondary": [], "reason": "交付物是网站。"},
        "proposals": proposals or [],
        "conflicts": conflicts or [],
        "review_item_ids": review_item_ids or [],
        "gap_updates": [],
        "question_reopens": [],
        "gaps": gaps,
        "questions": questions or [],
        "readiness": {
            "goal_identified": True,
            "deliverable_identified": True,
            "blocking_gap_ids": [
                row["gap_id"] for row in gaps if row["importance"] == "blocking_direction"
            ],
            "reason": "方向清楚。",
        },
        "next_action": next_action,
        "assistant_text": "请核对当前内容。",
    }


def gap(
    gap_id: str = "g1",
    field: str = "use_context",
    *,
    origin: str = "missing",
    scope: str = "整体任务",
    depends_on: list[str] | None = None,
) -> dict:
    return {
        "gap_id": gap_id,
        "field": field,
        "scope": scope,
        "description": "该信息尚未明确。",
        "importance": "can_defer",
        "origin": origin,
        "source_refs": [{"source_id": "u1", "quote": "做一个活动报名网站"}],
        "depends_on": depends_on or [],
    }


def question(
    question_id: str = "q1",
    gap_id: str = "g1",
    field: str = "use_context",
    *,
    scope: str = "整体任务",
    options: list[str] | None = None,
    depends_on: list[str] | None = None,
) -> dict:
    return {
        "question_id": question_id,
        "gap_id": gap_id,
        "field": field,
        "scope": scope,
        "text": "这是实际使用还是课堂演示？",
        "options": options if options is not None else ["实际使用", "课堂演示"],
        "reason": "用途影响实现深度。",
        "depends_on": depends_on or [],
    }


def staged_session() -> SessionState:
    session = SessionState.new()
    session.set_task("做一个活动报名网站，不做付款")
    request = session.begin_request("req-initial")
    session.stage_m1_result(
        "req-initial",
        request["base_version"],
        result(
            proposals=[
                candidate("p-deliverable", "deliverable", "做一个活动报名网站"),
                candidate("p-constraint", "constraints", "不做付款功能"),
            ]
        ),
    )
    session.accept_proposals(["p-deliverable", "p-constraint"])
    return session


def test_task_change_invalidates_analysis_and_blocks_old_requirement_confirmation() -> None:
    session = staged_session()
    session.confirm_requirements()

    session.set_task("改为写一篇社团招新文章，读者和篇幅还没想好。")

    assert all(row["confirmation"] == "review_needed" for row in session.requirements)
    assert set(session.pending_review_item_ids) == {row["item_id"] for row in session.requirements}
    with pytest.raises(SessionStateError, match="重新分析|复核"):
        session.confirm_requirements()


def test_withdrawing_only_directional_requirement_blocks_confirmation() -> None:
    session = staged_session()
    deliverable_id = next(row["item_id"] for row in session.requirements if row["field"] == "deliverable")

    session.withdraw_requirement(deliverable_id)

    with pytest.raises(SessionStateError, match="想完成什么|想要的结果"):
        session.confirm_requirements()


def test_batch_accept_is_atomic_when_one_candidate_is_stale() -> None:
    session = staged_session()
    target = next(row["item_id"] for row in session.requirements if row["field"] == "constraints")
    request = session.begin_request("req-batch")
    session.stage_m1_result(
        "req-batch",
        request["base_version"],
        result(
            proposals=[
                candidate("p-new", "preferences", "使用表格展示"),
                candidate("p-replace", "constraints", "允许付款", operation="replace", target=target),
            ]
        ),
    )
    session.edit_requirement(target, "付款仍不在本次范围")
    before = deepcopy(session.to_dict())

    with pytest.raises(SessionStateError):
        session.accept_proposals(["p-new", "p-replace"])

    assert session.to_dict() == before


def test_repeated_accept_never_adds_duplicate_requirement() -> None:
    session = SessionState.new()
    session.set_task("做一个活动报名网站，不做付款")
    request = session.begin_request("req-repeat")
    session.stage_m1_result(
        "req-repeat", request["base_version"], result(proposals=[candidate("p1", "deliverable", "活动网站")])
    )

    session.accept_proposals(["p1"])
    count = len(session.requirements)
    with pytest.raises(SessionStateError):
        session.accept_proposals(["p1"])

    assert len(session.requirements) == count


def test_accepting_new_conflicting_requirement_keeps_conflict_open() -> None:
    session = staged_session()
    old_id = next(row["item_id"] for row in session.requirements if row["field"] == "constraints")
    request = session.begin_request("req-conflict")
    session.stage_m1_result(
        "req-conflict",
        request["base_version"],
        result(
            proposals=[candidate("p-pay", "constraints", "加入在线付款")],
            conflicts=[
                {
                    "conflict_id": "c1",
                    "existing_item_ids": [old_id],
                    "proposal_ids": ["p-pay"],
                    "description": "付款要求互相冲突。",
                    "change_intent": "explicit_change",
                }
            ],
            next_action="resolve_conflict",
        ),
    )

    created = session.accept_proposals(["p-pay"])

    assert session.open_conflicts
    assert created[0]["item_id"] in session.open_conflicts[0]["existing_item_ids"]
    with pytest.raises(SessionStateError, match="冲突"):
        session.confirm_requirements()


def test_partial_multi_candidate_conflict_does_not_close_early() -> None:
    session = staged_session()
    old_id = next(row["item_id"] for row in session.requirements if row["field"] == "constraints")
    request = session.begin_request("req-multi-conflict")
    session.stage_m1_result(
        "req-multi-conflict",
        request["base_version"],
        result(
            proposals=[
                candidate("p-pay", "constraints", "加入在线付款"),
                candidate("p-refund", "constraints", "支持自动退款"),
            ],
            conflicts=[
                {
                    "conflict_id": "c1",
                    "existing_item_ids": [old_id],
                    "proposal_ids": ["p-pay", "p-refund"],
                    "description": "付款范围仍需处理。",
                    "change_intent": "explicit_change",
                }
            ],
            next_action="resolve_conflict",
        ),
    )

    session.accept_proposals(["p-pay"])

    assert session.open_conflicts[0]["proposal_ids"] == ["p-refund"]


def test_skipped_gap_survives_when_model_omits_it() -> None:
    session = SessionState.new()
    session.set_task("做一个活动报名网站")
    request = session.begin_request("req-gap")
    session.stage_m1_result(
        "req-gap",
        request["base_version"],
        result(gaps=[gap()], questions=[question()], next_action="ask"),
    )
    session.record_question("q1", "skipped")
    assert session.gaps[0]["origin"] == "user_skipped"
    request = session.begin_request("req-gap-next")

    session.stage_m1_result("req-gap-next", request["base_version"], result(gaps=[]))

    assert [row["gap_id"] for row in session.gaps] == ["g1"]
    assert session.gaps[0]["origin"] == "user_skipped"


def test_old_gap_survives_new_same_field_scope_gap_with_a_different_id() -> None:
    session = SessionState.new()
    session.set_task("做一个活动报名网站")
    request = session.begin_request("req-gap-original")
    session.stage_m1_result(
        "req-gap-original",
        request["base_version"],
        result(gaps=[gap("g-budget", "constraints")]),
    )
    request = session.begin_request("req-gap-same-scope")

    session.stage_m1_result(
        "req-gap-same-scope",
        request["base_version"],
        result(gaps=[gap("g-legal", "constraints")]),
    )

    assert {row["gap_id"] for row in session.gaps} == {"g-budget", "g-legal"}


def test_answer_keeps_the_corresponding_gap_pending_until_model_assessment() -> None:
    session = SessionState.new()
    session.set_task("做一个活动报名网站")
    request = session.begin_request("req-answer")
    session.stage_m1_result(
        "req-answer",
        request["base_version"],
        result(gaps=[gap(), gap("g2", "runtime")], questions=[question()], next_action="ask"),
    )

    session.record_question("q1", "answered", "先做课堂演示")

    assert [row["gap_id"] for row in session.gaps] == ["g1", "g2"]
    assert session.question_history[-1]["assessment_status"] == "pending"


def test_edit_redirects_dependencies_and_marks_dependents_for_review() -> None:
    session = staged_session()
    deliverable = next(row for row in session.requirements if row["field"] == "deliverable")
    constraint = next(row for row in session.requirements if row["field"] == "constraints")
    constraint["depends_on"] = [deliverable["item_id"]]

    edited = session.edit_requirement(deliverable["item_id"], "改为真实上线的活动网站")

    live_ids = {row["item_id"] for row in session.requirements}
    assert constraint["depends_on"] == [edited["item_id"]]
    assert all(dep in live_ids for row in session.requirements for dep in row["depends_on"])
    assert constraint["confirmation"] == "review_needed"
    assert constraint["item_id"] in session.pending_review_item_ids


def test_missing_review_item_id_is_rejected() -> None:
    assets = M1Assets.load(DESIGN, legacy=True)
    payload = json.loads((DESIGN / "examples" / "01_报名网站.input.json").read_text(encoding="utf-8"))
    response = json.loads((DESIGN / "examples" / "01_报名网站.expected.json").read_text(encoding="utf-8"))
    response["review_item_ids"] = ["missing-r999"]

    with pytest.raises(M1ValidationError, match="复核"):
        parse_m1_response(json.dumps(response, ensure_ascii=False), payload, assets.output_schema)


def test_repeating_skipped_question_without_new_context_is_rejected() -> None:
    assets = M1Assets.load(DESIGN, legacy=True)
    payload = json.loads((DESIGN / "examples" / "01_报名网站.input.json").read_text(encoding="utf-8"))
    payload["state"]["question_history"] = [
        {
            "question_id": "q-old",
            "field": "use_context",
            "scope": "报名网站",
            "text": "实际使用还是演示？",
            "disposition": "skipped",
        }
    ]
    response = json.loads((DESIGN / "examples" / "01_报名网站.expected.json").read_text(encoding="utf-8"))

    with pytest.raises(M1ValidationError, match="跳过|不确定|重复"):
        parse_m1_response(json.dumps(response, ensure_ascii=False), payload, assets.output_schema)


def test_edit_while_request_is_running_rejects_late_response() -> None:
    session = staged_session()
    request = session.begin_request("req-late-edit")
    target = session.requirements[0]["item_id"]
    session.edit_requirement(target, "改成另一个交付物")

    with pytest.raises(StaleResponseError):
        session.stage_m1_result("req-late-edit", request["base_version"], result())


def test_round_trip_preserves_reliability_state(tmp_path) -> None:
    session = staged_session()
    request = session.begin_request("req-persist")
    session.stage_m1_result(
        "req-persist",
        request["base_version"],
        result(gaps=[gap()], questions=[question()], review_item_ids=[session.requirements[0]["item_id"]], next_action="ask"),
    )
    path = save_session(session, tmp_path / "reliability.json")

    loaded = load_session(path)

    assert loaded.to_dict() == session.to_dict()
    assert loaded.analysis_basis_version == session.analysis_basis_version
    assert loaded.pending_proposals == session.pending_proposals
    assert loaded.open_conflicts == session.open_conflicts
    assert loaded.gaps == session.gaps
    assert loaded.pending_review_item_ids == session.pending_review_item_ids


def test_build_input_never_contains_archived_dependency() -> None:
    session = staged_session()
    deliverable = next(row for row in session.requirements if row["field"] == "deliverable")
    constraint = next(row for row in session.requirements if row["field"] == "constraints")
    constraint["depends_on"] = [deliverable["item_id"]]
    session.withdraw_requirement(deliverable["item_id"])

    payload = build_m1_input(session, "req-clean-dependencies", current_date="2026-09-23")

    live_ids = {row["item_id"] for row in payload["state"]["requirements"]}
    assert all(dep in live_ids for row in payload["state"]["requirements"] for dep in row["depends_on"])


def test_build_input_rejects_any_dangling_active_reference_before_starting_request() -> None:
    session = staged_session()
    session.gaps = [gap("g-broken", "runtime", depends_on=["retired-r999"])]

    with pytest.raises(SessionStateError, match="失效|引用"):
        build_m1_input(session, "req-broken-reference", current_date="2026-09-23")

    assert "req-broken-reference" not in session.pending_requests


def test_edit_redirects_safe_candidate_dependency_but_invalidates_old_target() -> None:
    session = staged_session()
    deliverable = next(row for row in session.requirements if row["field"] == "deliverable")
    constraint = next(row for row in session.requirements if row["field"] == "constraints")
    request = session.begin_request("req-candidate-references")
    session.stage_m1_result(
        "req-candidate-references",
        request["base_version"],
        result(
            proposals=[
                candidate("p-dependent", "runtime", "使用浏览器运行", depends_on=[deliverable["item_id"]]),
                candidate(
                    "p-old-target",
                    "constraints",
                    "重新表述付款范围",
                    operation="replace",
                    target=constraint["item_id"],
                ),
            ]
        ),
    )

    edited = session.edit_requirement(deliverable["item_id"], "活动报名应用")

    proposals = {row["proposal_id"]: row for row in session.pending_proposals}
    assert proposals["p-dependent"]["depends_on"] == [edited["item_id"]]
    assert "p-old-target" in proposals

    session.withdraw_requirement(constraint["item_id"])
    assert [row["proposal_id"] for row in session.pending_proposals] == ["p-dependent"]


def test_same_field_scope_known_requirement_does_not_close_budget_unknown() -> None:
    session = SessionState.new()
    session.set_task("做一个活动报名网站，不做付款")
    request = session.begin_request("req-same-scope-gap")
    session.stage_m1_result(
        "req-same-scope-gap",
        request["base_version"],
        result(
            proposals=[
                candidate("p-deliverable", "deliverable", "活动报名网站"),
                candidate("p-payment", "constraints", "不做付款"),
            ],
            gaps=[gap("g-budget", "constraints")],
            questions=[question("q-budget", "g-budget", "constraints")],
            next_action="ask",
        ),
    )

    session.accept_proposals(["p-deliverable", "p-payment"])

    assert [row["gap_id"] for row in session.gaps] == ["g-budget"]
    assert session.confirm_requirements() == session.requirement_version


@pytest.mark.parametrize(
    ("disposition", "answer", "should_remain"),
    [
        ("answered", "我不知道", True),
        ("answered", "姓名和电话，其他字段以后再定", True),
        ("skipped", "", True),
        ("answered", "课堂演示", True),
    ],
)
def test_question_answers_only_close_a_clear_answer(
    disposition: str, answer: str, should_remain: bool
) -> None:
    session = SessionState.new()
    session.set_task("做一个活动报名网站")
    request = session.begin_request(f"req-answer-{disposition}-{should_remain}")
    session.stage_m1_result(
        request["request_id"],
        request["base_version"],
        result(
            gaps=[gap("g-answer", "features")],
            questions=[question("q-answer", "g-answer", "features")],
            next_action="ask",
        ),
    )

    session.record_question("q-answer", disposition, answer)

    assert bool(session.gaps) is should_remain
    if disposition == "skipped":
        assert session.gaps[0]["origin"] == "user_skipped"
    elif disposition == "answered":
        assert session.gaps[0]["origin"] == "ambiguous"
    if disposition == "answered":
        assert session.question_history[-1]["assessment_status"] == "pending"


def test_program_review_survives_empty_model_review_list_until_user_review() -> None:
    session = staged_session()
    deliverable = next(row for row in session.requirements if row["field"] == "deliverable")
    dependent = next(row for row in session.requirements if row["field"] == "constraints")
    dependent["depends_on"] = [deliverable["item_id"]]
    edited = session.edit_requirement(deliverable["item_id"], "供社团实际上线的活动报名网站")
    assert dependent["item_id"] in session.pending_review_item_ids
    assert edited["item_id"] not in session.pending_review_item_ids

    request = session.begin_request("req-review-omission")
    session.stage_m1_result("req-review-omission", request["base_version"], result())

    assert dependent["item_id"] in session.pending_review_item_ids
    with pytest.raises(SessionStateError, match="复核"):
        session.confirm_requirements()

    session.mark_requirements_reviewed([dependent["item_id"]])
    assert session.confirm_requirements() == session.requirement_version


@pytest.mark.parametrize("operation", ["replace", "withdraw"])
def test_replacement_or_withdrawal_removes_archived_ids_from_review_list(operation: str) -> None:
    session = staged_session()
    target = next(row for row in session.requirements if row["field"] == "constraints")
    request = session.begin_request(f"req-{operation}-review")
    replacement = candidate(
        f"p-{operation}",
        "constraints",
        "付款范围待重新确定",
        operation=operation,
        target=target["item_id"],
    )
    session.stage_m1_result(
        f"req-{operation}-review",
        request["base_version"],
        result(proposals=[replacement], review_item_ids=[target["item_id"]]),
    )
    session.accept_proposals([f"p-{operation}"])

    live_ids = {row["item_id"] for row in session.requirements}
    assert set(session.pending_review_item_ids).issubset(live_ids)
    assert target["item_id"] not in session.pending_review_item_ids


def test_edit_updates_gap_and_question_dependencies_and_legal_next_response() -> None:
    session = staged_session()
    deliverable = next(row for row in session.requirements if row["field"] == "deliverable")
    request = session.begin_request("req-dependent-gap")
    session.stage_m1_result(
        "req-dependent-gap",
        request["base_version"],
        result(
            gaps=[gap("g-runtime", "runtime", depends_on=[deliverable["item_id"]])],
            questions=[
                question(
                    "q-runtime",
                    "g-runtime",
                    "runtime",
                    depends_on=[deliverable["item_id"]],
                )
            ],
            next_action="ask",
        ),
    )

    edited = session.edit_requirement(deliverable["item_id"], "活动报名应用")
    payload = build_m1_input(session, "req-after-edit")
    live_ids = {row["item_id"] for row in session.requirements}
    assert all(
        dependency in live_ids
        for row in [*payload["state"]["requirements"], *payload["state"]["gaps"]]
        for dependency in row["depends_on"]
    )
    assert all(dependency in live_ids for dependency in session.pending_questions[0]["depends_on"])

    response = result(
        gaps=deepcopy(payload["state"]["gaps"]),
        questions=deepcopy(session.pending_questions),
        next_action="ask",
    )
    response.update({key: payload[key] for key in ("schema_version", "request_id", "task_id", "base_version")})
    parsed = parse_m1_response(json.dumps(response, ensure_ascii=False), payload, M1Assets.load(DESIGN).output_schema)
    assert parsed["questions"][0]["depends_on"] == [edited["item_id"]]


def test_different_scopes_can_repeat_field_but_same_scope_cannot() -> None:
    assets = M1Assets.load(DESIGN)
    session = SessionState.new()
    session.set_task("做一个活动报名网站和一份介绍PPT")
    session.control["remaining_rounds"] = 4
    first_gap = gap("g-site", "audience", scope="活动报名网站")
    request = session.begin_request("req-scope-first")
    session.stage_m1_result(
        "req-scope-first",
        request["base_version"],
        result(
            gaps=[first_gap],
            questions=[question("q-site", "g-site", "audience", scope="活动报名网站")],
            next_action="ask",
        ),
    )
    session.record_question("q-site", "skipped")
    payload = build_m1_input(session, "req-scope-second")
    second_gap = gap("g-ppt", "audience", scope="PPT汇报")
    response = result(
        gaps=[deepcopy(first_gap), second_gap],
        questions=[question("q-ppt", "g-ppt", "audience", scope="PPT汇报")],
        next_action="ask",
    )
    response.update({key: payload[key] for key in ("schema_version", "request_id", "task_id", "base_version")})
    parse_m1_response(json.dumps(response, ensure_ascii=False), payload, assets.output_schema)

    same_scope = deepcopy(response)
    same_scope["questions"] = [question("q-site-again", "g-site", "audience", scope="活动报名网站")]
    with pytest.raises(M1ValidationError, match="跳过|不确定|重复"):
        parse_m1_response(json.dumps(same_scope, ensure_ascii=False), payload, assets.output_schema)


def test_confirmation_rejects_truncated_context_and_readiness_mismatch() -> None:
    session = staged_session()
    session.control["context_coverage"] = "truncated"
    with pytest.raises(SessionStateError, match="上下文|完整"):
        session.confirm_requirements()

    session.control["context_coverage"] = "complete"
    request = session.begin_request("req-readiness-mismatch")
    contradictory = result()
    contradictory["readiness"]["deliverable_identified"] = False
    session.stage_m1_result("req-readiness-mismatch", request["base_version"], contradictory)
    with pytest.raises(SessionStateError, match="交付物|充分性|readiness"):
        session.confirm_requirements()
