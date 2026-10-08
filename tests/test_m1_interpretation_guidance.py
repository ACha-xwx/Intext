from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from promptsmith.m1 import M1Assets, M1ValidationError, apply_m1_response, build_m1_input, parse_m1_response
from promptsmith.session import SessionState
from promptsmith.storage import load_session, save_session
from tests.test_ui_reliability import base_result


def interpretation_case() -> tuple[SessionState, dict, dict]:
    session = SessionState.new()
    session.set_task("讲一下JGS，给学生学习，属于数值分析。")
    payload = build_m1_input(session, "interpretation-first")
    result = base_result(payload)
    result["category"] = {"primary": "learning", "secondary": [], "reason": "学生讲义。"}
    result["gaps"] = [{
        "gap_id": "g-term", "field": "goal", "scope": "讲解对象",
        "description": "JGS具体指什么尚未明确。", "importance": "blocking_direction",
        "origin": "ambiguous", "source_refs": [{"source_id": "u1", "quote": "JGS"}],
        "depends_on": [],
    }]
    result["questions"] = [{
        "question_id": "q-term", "gap_id": "g-term", "field": "goal", "scope": "讲解对象",
        "text": "JGS具体指什么？", "options": [], "reason": "确认讲解对象。", "depends_on": [],
    }]
    result["proposals"] = [{
        "proposal_id": "p-interpret", "operation": "new", "target_item_id": None,
        "field": "goal", "scope": "讲解对象", "text": "讲解Jacobi与Gauss–Seidel这两种迭代方法。",
        "kind": "pending_interpretation", "strength": "unspecified",
        "source_refs": [{"source_id": "u1", "quote": "数值分析"}], "depends_on": [],
        "reason": "根据用户提供的领域推测，仍需用户确认。",
        "interpretation_for": {
            "gap_id": "g-term", "question_id": "q-term", "reason": "你提到数值分析，我猜你可能指这两种方法。",
        },
    }]
    result["next_action"] = "ask"
    result["readiness"]["blocking_gap_ids"] = ["g-term"]
    return session, payload, result


def parse(payload: dict, result: dict) -> dict:
    return parse_m1_response(json.dumps(result, ensure_ascii=False), payload, M1Assets.load().output_schema)


def test_linked_contextual_interpretation_is_a_suggestion_with_concrete_gap() -> None:
    session, payload, result = interpretation_case()
    before = deepcopy(session.to_dict())
    parsed = parse(payload, result)
    assert parsed["proposals"][0]["kind"] == "pending_interpretation"
    assert parsed["proposals"][0]["interpretation_for"]["gap_id"] == "g-term"
    assert session.to_dict() == before


@pytest.mark.parametrize("change, message", [
    (lambda r: r["proposals"][0].update(kind="user_decision"), "解释|推测"),
    (lambda r: r["proposals"][0]["interpretation_for"].update(gap_id="missing-gap"), "缺口"),
    (lambda r: r["proposals"][0]["interpretation_for"].update(question_id="missing-question"), "问题"),
    (lambda r: r["proposals"][0].update(scope="无关预算"), "范围|对齐"),
    (lambda r: r["proposals"][0].update(source_refs=[]), "来源"),
    (lambda r: r["gaps"][0].update(importance="can_defer"), "方向|关键"),
])
def test_interpretation_cannot_claim_user_decision_or_bind_unrelated_object(change, message) -> None:
    session, payload, result = interpretation_case()
    change(result)
    with pytest.raises(M1ValidationError, match=message):
        parse(payload, result)
    assert not session.requirements


def test_at_most_two_distinct_explanations_for_one_gap() -> None:
    _, payload, result = interpretation_case()
    second = deepcopy(result["proposals"][0])
    second.update(proposal_id="p-interpret-two", text="讲解教材中以JGS标记的一组数值方法。")
    result["proposals"].append(second)
    assert len(parse(payload, result)["proposals"]) == 2
    third = deepcopy(second)
    third.update(proposal_id="p-interpret-three", text="第三种猜测。")
    result["proposals"].append(third)
    with pytest.raises(M1ValidationError, match="两个|2"):
        parse(payload, result)


def test_interpretation_can_reference_skipped_history_without_repeating_question() -> None:
    _, payload, result = interpretation_case()
    result["questions"] = []
    result["next_action"] = "pause_with_unknowns"
    payload["state"]["question_history"] = [{
        "question_id": "q-term", "gap_id": "g-term", "field": "goal", "scope": "讲解对象",
        "text": "JGS具体指什么？", "disposition": "skipped", "recorded_source_count": 1,
        "assessment_status": "not_applicable",
    }]
    assert parse(payload, result)["questions"] == []


@pytest.mark.parametrize("decision", ["skipped", "rejected"])
def test_declined_interpretation_is_not_automatically_offered_again(decision: str) -> None:
    _, payload, result = interpretation_case()
    payload["state"]["interpretation_history"] = [{
        "proposal_id": "previous", "gap_id": "g-term", "question_id": "q-term",
        "decision": decision, "text": result["proposals"][0]["text"], "source_id": None,
        "recorded_at": "2026-10-01T00:00:00+08:00",
    }]
    with pytest.raises(M1ValidationError, match="跳过|拒绝|重复"):
        parse(payload, result)


def test_pending_drafts_and_interpretation_choices_are_in_model_input_without_runtime_fields() -> None:
    session, _, result = interpretation_case()
    session.pending_proposals = deepcopy(result["proposals"])
    session.pending_proposals[0].update(source_request_id="old", source_base_version=1, valid_for_version=1)
    session.gaps = deepcopy(result["gaps"])
    session.pending_questions = deepcopy(result["questions"])
    session.interpretation_history = []
    payload = build_m1_input(session, "next")
    assert payload["state"]["pending_proposals"] == result["proposals"]
    assert payload["state"]["pending_questions"] == result["questions"]
    assert payload["state"]["interpretation_history"] == []
    Draft202012Validator(M1Assets.load().input_schema).validate(payload)


def test_existing_output_without_interpretation_extension_remains_valid() -> None:
    _, payload, result = interpretation_case()
    result["proposals"][0].pop("interpretation_for")
    assert parse(payload, result) == result


def test_interpretation_cannot_repeat_an_existing_draft() -> None:
    _, payload, result = interpretation_case()
    payload["state"]["pending_proposals"] = deepcopy(result["proposals"])
    result["proposals"][0]["proposal_id"] = "renamed-copy"
    with pytest.raises(M1ValidationError, match="草稿|重复"):
        parse(payload, result)


def test_new_resources_keep_legacy_contract_and_do_not_encode_jgs_answer() -> None:
    assets = M1Assets.load()
    assert assets.contract_version == "m1.v0.2"
    assert assets.prompt_version == "M1_system_v0.11"
    assert "interpretation_for" in assets.system_prompt
    assert "JGS" not in assets.system_prompt
    assert "Jacobi" not in assets.system_prompt
    assert M1Assets.load(legacy=True).contract_version == "m1.v0.1"
    design = Path(__file__).resolve().parents[1] / "resources/prompts"
    old_schema = json.loads((design / "M1_output_v0.2.schema.json").read_text(encoding="utf-8-sig"))
    assert "interpretation_for" not in old_schema["properties"]["proposals"]["items"]["properties"]
    assert (design / "M1_system_v0.8.txt").is_file()
    assert (design / "M1_incremental_v0.1.txt").is_file()


def draft_conflict_session() -> SessionState:
    session = SessionState.new()
    session.set_task("整理学习讲义；不加练习题，又要有练习题。")
    payload = build_m1_input(session, "draft-conflict-first")
    response = base_result(payload)
    response["category"] = {"primary": "learning", "secondary": [], "reason": "学习讲义。"}
    response["proposals"] = [{
        "proposal_id": pid, "operation": "new", "target_item_id": None,
        "field": "constraints", "scope": "讲义", "text": text,
        "kind": "user_decision", "strength": "hard", "depends_on": [],
        "source_refs": [{"source_id": "u1", "quote": text}], "reason": "保留用户原话。",
    } for pid, text in [("p-no", "不加练习题"), ("p-yes", "要有练习题")]]
    response["conflicts"] = [{
        "conflict_id": "c-exercise", "existing_item_ids": [], "proposal_ids": ["p-no", "p-yes"],
        "description": "是否加入练习题尚有冲突。", "change_intent": "unclear",
    }]
    response["next_action"] = "resolve_conflict"
    apply_m1_response(session, payload, parse(payload, response))
    return session


def test_pending_conflict_parties_survive_incremental_round_without_repeating_drafts() -> None:
    session = draft_conflict_session()
    payload = build_m1_input(session, "draft-conflict-next")
    assert payload["state"]["open_conflicts"][0]["proposal_ids"] == ["p-no", "p-yes"]
    result = base_result(payload)
    result["next_action"] = "resolve_conflict"
    parsed = parse_m1_response(json.dumps(result), payload, M1Assets.load().output_schema, incremental=True)
    assert parsed["conflicts"][0]["proposal_ids"] == ["p-no", "p-yes"]
    apply_m1_response(session, payload, parsed)
    assert len(session.pending_proposals) == 2
    assert session.open_conflicts[0]["proposal_ids"] == ["p-no", "p-yes"]


def test_model_cannot_remove_still_pending_conflict_party() -> None:
    session = draft_conflict_session()
    payload = build_m1_input(session, "draft-conflict-reduced")
    response = base_result(payload)
    response["conflicts"] = deepcopy(session.open_conflicts)
    response["conflicts"][0]["proposal_ids"] = ["p-no"]
    response["next_action"] = "resolve_conflict"
    with pytest.raises(M1ValidationError, match="参与方"):
        parse(payload, response)


def test_user_accepts_exactly_one_interpretation_through_validated_flow_and_save(tmp_path) -> None:
    session, payload, response = interpretation_case()
    unrelated = {
        "proposal_id": "p-budget", "operation": "new", "target_item_id": None,
        "field": "constraints", "scope": "整体任务", "text": "使用付费资料，预算为100元。",
        "kind": "system_suggestion", "strength": "unspecified", "source_refs": [],
        "depends_on": [], "reason": "仅为另一个可选建议，用户尚未接受。",
    }
    response["proposals"].append(unrelated)
    other_gap = deepcopy(response["gaps"][0])
    other_gap.update(gap_id="g-length", field="constraints", scope="讲义篇幅",
                     description="字数尚未确定。", importance="can_defer")
    response["gaps"].append(other_gap)
    apply_m1_response(session, payload, parse(payload, response))
    requirement = session.decide_interpretation("p-interpret", "accepted")
    assert requirement["kind"] == "user_decision"
    assert {row["gap_id"] for row in session.gaps} == {"g-length"}
    assert [row["proposal_id"] for row in session.pending_proposals] == ["p-budget"]
    assert len(session.requirements) == 1
    assert not any("100" in row["text"] for row in session.requirements)
    chosen_source = requirement["source_refs"][0]
    assert chosen_source["source_id"] != "u1"
    assert chosen_source["quote"] == session.sources[-1]["text"]
    assert response["proposals"][0]["text"] in chosen_source["quote"]
    assert session.question_history[-1]["gap_id"] == "g-term"
    assert session.interpretation_history[-1]["decision"] == "accepted"
    restored = load_session(save_session(session, tmp_path / "chosen.json"))
    assert restored.to_dict() == session.to_dict()
    assert build_m1_input(restored, "after-choice")["state"]["interpretation_history"][-1]["decision"] == "accepted"


def test_correction_keeps_old_question_history_and_does_not_adopt_guess(tmp_path) -> None:
    session, payload, response = interpretation_case()
    apply_m1_response(session, payload, parse(payload, response))
    session.record_question("q-term", "skipped")
    skipped = deepcopy(session.question_history[-1])
    session.decide_interpretation("p-interpret", "rejected")
    session.reopen_question("q-term")
    session.record_question("q-term", "answered", "不是这两种方法，是老师讲义里的一个自定义缩写。")
    assert session.question_history[0] == skipped
    assert session.question_history[-1]["assessment_status"] == "pending"
    assert not session.requirements
    assert session.gaps[0]["gap_id"] == "g-term"
    restored = load_session(save_session(session, tmp_path / "correction.json"))
    next_input = build_m1_input(restored, "correction-next")
    assert next_input["state"]["interpretation_history"][-1]["decision"] == "rejected"
    assert next_input["state"]["question_history"][-1]["answer_text"].startswith("不是这两种方法")
