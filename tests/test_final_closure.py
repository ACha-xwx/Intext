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


def gap(gap_id: str, field: str, scope: str, description: str) -> dict:
    return {
        "gap_id": gap_id,
        "field": field,
        "scope": scope,
        "description": description,
        "importance": "can_defer",
        "origin": "missing",
        "source_refs": [],
        "depends_on": [],
    }


def question(question_id: str, target_gap: dict, text: str) -> dict:
    return {
        "question_id": question_id,
        "gap_id": target_gap["gap_id"],
        "field": target_gap["field"],
        "scope": target_gap["scope"],
        "text": text,
        "options": [],
        "reason": "该信息影响后续需求。",
        "depends_on": [],
    }


def result(
    *,
    gaps: list[dict] | None = None,
    questions: list[dict] | None = None,
    gap_updates: list[dict] | None = None,
    question_reopens: list[dict] | None = None,
    next_action: str | None = None,
) -> dict:
    gaps = gaps or []
    questions = questions or []
    return {
        "status": "ok",
        "error": None,
        "category": {"primary": "coding", "secondary": [], "reason": "交付物包含网站。"},
        "proposals": [],
        "conflicts": [],
        "review_item_ids": [],
        "gap_updates": gap_updates or [],
        "question_reopens": question_reopens or [],
        "gaps": gaps,
        "questions": questions,
        "readiness": {
            "goal_identified": True,
            "deliverable_identified": True,
            "blocking_gap_ids": [row["gap_id"] for row in gaps if row["importance"] == "blocking_direction"],
            "reason": "任务方向可识别。",
        },
        "next_action": next_action or ("ask" if questions else "review_requirements"),
        "assistant_text": "请核对当前需求。",
    }


def question_session() -> SessionState:
    session = SessionState.new()
    session.control["remaining_rounds"] = 5
    session.set_task("做一个课堂演示的活动报名网站")
    form_gap = gap("g-form", "features", "报名表单", "报名表单字段尚未明确。")
    request = session.begin_request("initial-question")
    session.stage_m1_result(
        request["request_id"],
        request["base_version"],
        result(
            gaps=[form_gap],
            questions=[question("q-form", form_gap, "报名表单需要填写哪些信息？")],
        ),
    )
    return session


@pytest.mark.parametrize(
    "answer",
    ["这个要问负责报名的老师", "先收姓名，联系方式等老师确认后再补"],
)
def test_free_answer_is_saved_but_does_not_close_gap_before_model_assessment(answer: str) -> None:
    session = question_session()

    source_id = session.record_question("q-form", "answered", answer)

    assert [row["gap_id"] for row in session.gaps] == ["g-form"]
    history = session.question_history[-1]
    assert history["gap_id"] == "g-form"
    assert history["answer_source_id"] == source_id
    assert history["answer_text"] == answer
    assert history["assessment_status"] == "pending"


def checked_apply(session: SessionState, request_id: str, response: dict) -> None:
    assets = M1Assets.load(DESIGN)
    payload = build_m1_input(session, request_id, current_date="2026-09-23")
    response = deepcopy(response)
    response.update({key: payload[key] for key in ("schema_version", "request_id", "task_id", "base_version")})
    parsed = parse_m1_response(json.dumps(response, ensure_ascii=False), payload, assets.output_schema)
    apply_m1_response(session, payload, parsed)


def gap_update(session: SessionState, action: str, *, remaining: str | None = None) -> dict:
    history = session.question_history[-1]
    return {
        "update_id": f"gu-{action}",
        "target_gap_id": history["gap_id"],
        "answer_id": history["answer_id"],
        "action": action,
        "source_ref": {
            "source_id": history["answer_source_id"],
            "quote": history["answer_text"],
        },
        "remaining_description": remaining,
        "reason": "依据用户本轮回答判断。",
    }


def test_valid_gap_update_closes_only_the_target_gap_and_is_persisted(tmp_path) -> None:
    session = question_session()
    other = gap("g-deploy", "runtime", "部署", "部署位置尚未明确。")
    session.gaps.append(other)
    session.record_question("q-form", "answered", "仅收姓名和手机号，两项必填")

    checked_apply(
        session,
        "resolve-form-gap",
        result(gaps=[deepcopy(other)], gap_updates=[gap_update(session, "resolved")]),
    )

    assert [row["gap_id"] for row in session.gaps] == ["g-deploy"]
    assert session.question_history[-1]["assessment_status"] == "applied"
    assert session.question_history[-1]["assessment_action"] == "resolved"
    assert session.gap_update_history[-1]["target_gap_id"] == "g-form"
    path = save_session(session, tmp_path / "resolved.json")
    assert load_session(path).to_dict() == session.to_dict()


def test_partial_gap_update_keeps_only_the_remaining_unknown() -> None:
    session = question_session()
    session.record_question("q-form", "answered", "先收姓名，联系方式等老师确认后再补")
    remaining = "联系方式的具体类型和是否必填仍待负责老师确认。"

    checked_apply(
        session,
        "partial-form-gap",
        result(
            gaps=deepcopy(session.gaps),
            gap_updates=[gap_update(session, "partial", remaining=remaining)],
        ),
    )

    assert session.gaps[0]["description"] == remaining
    assert session.gaps[0]["origin"] == "ambiguous"
    assert session.question_history[-1]["assessment_action"] == "partial"


def test_model_omission_does_not_close_an_answered_gap() -> None:
    session = question_session()
    session.record_question("q-form", "answered", "这个要问负责报名的老师")

    checked_apply(session, "omit-form-gap", result())

    assert [row["gap_id"] for row in session.gaps] == ["g-form"]
    assert session.question_history[-1]["assessment_status"] == "pending"


def test_model_cannot_close_and_reask_the_same_gap_in_one_response() -> None:
    session = question_session()
    session.record_question("q-form", "answered", "仅收姓名和手机号，两项必填")
    payload = build_m1_input(session, "close-and-reask", current_date="2026-09-23")
    target = deepcopy(session.gaps[0])
    response = result(
        gaps=[target],
        questions=[question("q-form-again", target, "报名表单需要填写哪些信息？")],
        gap_updates=[gap_update(session, "resolved")],
    )
    response.update({key: payload[key] for key in ("schema_version", "request_id", "task_id", "base_version")})

    with pytest.raises(M1ValidationError, match="关闭|提问"):
        parse_m1_response(
            json.dumps(response, ensure_ascii=False), payload, M1Assets.load(DESIGN).output_schema
        )


def test_pending_answer_cannot_be_reasked_under_a_new_gap_id_with_same_field_and_scope() -> None:
    session = question_session()
    session.record_question("q-form", "answered", "先收姓名，联系方式之后确认")
    payload = build_m1_input(session, "repeat-under-new-gap", current_date="2026-09-23")
    renamed = gap("g-form-renamed", "features", "报名表单", "报名字段仍未明确。")
    response = result(
        gaps=[renamed],
        questions=[question("q-form-rephrased", renamed, "请再说明报名表单包含哪些字段？")],
    )
    response.update({key: payload[key] for key in ("schema_version", "request_id", "task_id", "base_version")})

    with pytest.raises(M1ValidationError, match="重复|回答"):
        parse_m1_response(
            json.dumps(response, ensure_ascii=False), payload, M1Assets.load(DESIGN).output_schema
        )


@pytest.mark.parametrize("tamper", ["gap", "source", "answer"])
def test_invalid_gap_update_is_rejected_without_partial_state_change(tamper: str) -> None:
    session = question_session()
    session.record_question("q-form", "answered", "仅收姓名和手机号，两项必填")
    before = deepcopy(session.to_dict())
    update = gap_update(session, "resolved")
    if tamper == "gap":
        update["target_gap_id"] = "g-missing"
    elif tamper == "source":
        update["source_ref"]["source_id"] = "u1"
    else:
        update["answer_id"] = "a-missing"

    assets = M1Assets.load(DESIGN)
    payload = build_m1_input(session, f"invalid-{tamper}", current_date="2026-09-23")
    response = result(gaps=deepcopy(session.gaps), gap_updates=[update])
    response.update({key: payload[key] for key in ("schema_version", "request_id", "task_id", "base_version")})
    with pytest.raises(M1ValidationError, match="缺口|来源|回答"):
        parse_m1_response(json.dumps(response, ensure_ascii=False), payload, assets.output_schema)

    session.pending_requests.pop(payload["request_id"], None)
    after = session.to_dict()
    before["updated_at"] = after["updated_at"]
    before["pending_requests"] = after["pending_requests"]
    assert after == before


def requirement(item_id: str, text: str) -> dict:
    return {
        "item_id": item_id,
        "field": "constraints",
        "text": text,
        "kind": "user_decision",
        "strength": "hard",
        "scope": "报名网站",
        "source_refs": [],
        "depends_on": [],
        "confirmation": "pending",
    }


def test_conflict_survives_edit_that_invalidates_a_pending_candidate_then_can_resolve() -> None:
    session = SessionState.new()
    session.set_task("做一个活动报名网站")
    session.requirements = [
        requirement("r1", "不做付款功能"),
        requirement("r2", "加入在线付款功能"),
    ]
    session.pending_proposals = [
        {
            "proposal_id": "p-rewrite",
            "operation": "replace",
            "target_item_id": "r1",
            "field": "constraints",
            "text": "首版不做付款",
            "kind": "user_decision",
            "strength": "hard",
            "scope": "报名网站",
            "source_refs": [],
            "depends_on": [],
            "reason": "修改旧限制。",
            "valid_for_version": session.requirement_version,
        }
    ]
    session.open_conflicts = [
        {
            "conflict_id": "c-payment",
            "existing_item_ids": ["r1", "r2"],
            "proposal_ids": ["p-rewrite"],
            "description": "付款功能要求互相矛盾。",
            "change_intent": "explicit_change",
        }
    ]

    edited = session.edit_requirement("r1", "任何版本都不做付款功能")

    assert session.pending_proposals == []
    assert session.open_conflicts[0]["existing_item_ids"] == [edited["item_id"], "r2"]
    with pytest.raises(SessionStateError, match="冲突"):
        session.confirm_requirements()

    session.withdraw_requirement("r2")
    assert session.open_conflicts == []


def skipped_website_then_reopen_message() -> SessionState:
    session = SessionState.new()
    session.control["remaining_rounds"] = 6
    session.set_task("做一个活动报名网站和一份介绍网站的PPT")
    website = gap("g-web", "audience", "活动报名网站", "网站使用者尚未明确。")
    first = session.begin_request("ask-website")
    session.stage_m1_result(
        first["request_id"],
        first["base_version"],
        result(gaps=[website], questions=[question("q-web", website, "网站主要给哪些人使用？")]),
    )
    session.record_question("q-web", "skipped")
    ppt = gap("g-ppt", "audience", "PPT汇报", "PPT听众尚未明确。")
    second = session.begin_request("ask-ppt")
    session.stage_m1_result(
        second["request_id"],
        second["base_version"],
        result(
            gaps=[deepcopy(website), ppt],
            questions=[question("q-ppt", ppt, "PPT主要讲给哪些人听？")],
        ),
    )
    session.record_question("q-ppt", "answered", "PPT讲给同学听。现在可以聊网站受众了，请重新问我。")
    return session


def reopen_for_latest_source(session: SessionState, *, quote: str) -> dict:
    return {
        "reopen_id": "qr-web",
        "target_gap_id": "g-web",
        "source_ref": {"source_id": session.current_source_id, "quote": quote},
        "reason": "用户明确要求重新询问网站受众。",
    }


def test_explicit_latest_user_evidence_can_reopen_skipped_question_and_persists(tmp_path) -> None:
    session = skipped_website_then_reopen_message()
    source_text = session.sources[-1]["text"]
    website = next(row for row in session.gaps if row["gap_id"] == "g-web")
    reopened = question("q-web-reopened", website, "网站主要给哪些人使用？")

    checked_apply(
        session,
        "reopen-website",
        result(
            gaps=deepcopy(session.gaps),
            questions=[reopened],
            question_reopens=[reopen_for_latest_source(session, quote=source_text)],
        ),
    )

    assert session.pending_questions[0]["question_id"] == "q-web-reopened"
    assert any(row["disposition"] == "skipped" and row["gap_id"] == "g-web" for row in session.question_history)
    assert session.question_reopen_history[-1]["target_gap_id"] == "g-web"
    path = save_session(session, tmp_path / "reopened.json")
    assert load_session(path).question_reopen_history == session.question_reopen_history


def test_unrelated_latest_message_cannot_reopen_skipped_question() -> None:
    session = skipped_website_then_reopen_message()
    session.sources[-1]["text"] = "PPT讲给同学听。"
    website = next(row for row in session.gaps if row["gap_id"] == "g-web")
    payload = build_m1_input(session, "false-reopen", current_date="2026-09-23")
    response = result(
        gaps=deepcopy(session.gaps),
        questions=[question("q-web-reopened", website, "网站主要给哪些人使用？")],
        question_reopens=[reopen_for_latest_source(session, quote="PPT讲给同学听。")],
    )
    response.update({key: payload[key] for key in ("schema_version", "request_id", "task_id", "base_version")})

    with pytest.raises(M1ValidationError, match="重开|依据"):
        parse_m1_response(
            json.dumps(response, ensure_ascii=False), payload, M1Assets.load(DESIGN).output_schema
        )
