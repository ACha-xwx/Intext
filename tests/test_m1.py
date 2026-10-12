from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from promptsmith.m1 import M1Assets, M1ValidationError, build_m1_input, parse_m1_response
from promptsmith.session import SessionState


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "resources" / "prompts"


def fixture(name: str) -> dict:
    return json.loads((DESIGN / "examples" / name).read_text(encoding="utf-8"))


def test_assets_load_exact_current_versions() -> None:
    assets = M1Assets.load(DESIGN)

    assert "需求访谈模块" in assets.system_prompt
    assert assets.prompt_version == "M1_system_v0.11"
    assert "use_context尚未明确" in assets.system_prompt
    assert "不要在assistant_text里换一种说法再次询问" in assets.system_prompt
    assert "不能只返回重复的question而省略question_reopens" in assets.system_prompt
    assert "必须保持该gap为未决但questions=[]" in assets.system_prompt
    assert "gap_updates" in assets.system_prompt
    assert "readiness只能包含goal_identified、deliverable_identified、blocking_gap_ids、reason" in assets.system_prompt
    assert (DESIGN / "M1_system_v0.5.txt").is_file()
    assert assets.input_schema["properties"]["schema_version"]["const"] == "m1.v0.2"
    assert assets.output_schema["properties"]["schema_version"]["const"] == "m1.v0.2"


def test_build_input_maps_session_to_existing_schema() -> None:
    assets = M1Assets.load(DESIGN)
    session = SessionState.new()
    session.set_task("帮我做一个活动报名网站，不做付款。")

    payload = build_m1_input(session, "req-live", current_date="2026-09-23")

    Draft202012Validator(assets.input_schema).validate(payload)
    assert payload["base_version"] == session.requirement_version
    assert payload["sources"][-1]["text"].endswith("不做付款。")
    assert payload["state"]["requirements"] == []
    assert payload["category_config"]["category_fields"]["coding"][0] == "use_context"
    assert session.pending_requests["req-live"]["base_version"] == payload["base_version"]


@pytest.mark.parametrize(
    ("input_name", "output_name"),
    [
        ("01_报名网站.input.json", "01_报名网站.expected.json"),
        ("02_冲突且预算耗尽.input.json", "02_冲突且预算耗尽.expected.json"),
    ],
)
def test_existing_manual_fixtures_pass_contract(input_name: str, output_name: str) -> None:
    assets = M1Assets.load(DESIGN, legacy=True)
    payload = fixture(input_name)
    raw = (DESIGN / "examples" / output_name).read_text(encoding="utf-8")

    parsed = parse_m1_response(raw, payload, assets.output_schema)

    assert parsed["request_id"] == payload["request_id"]


def test_duplicate_json_keys_are_rejected() -> None:
    assets = M1Assets.load(DESIGN, legacy=True)
    payload = fixture("01_报名网站.input.json")
    raw = '{"schema_version":"m1.v0.1","schema_version":"m1.v0.1"}'

    with pytest.raises(M1ValidationError, match="重复键"):
        parse_m1_response(raw, payload, assets.output_schema)


def test_nonliteral_quote_is_rejected_even_when_schema_passes() -> None:
    assets = M1Assets.load(DESIGN, legacy=True)
    payload = fixture("01_报名网站.input.json")
    result = fixture("01_报名网站.expected.json")
    result["proposals"][0]["source_refs"][0]["quote"] = "用户没说过的句子"

    with pytest.raises(M1ValidationError, match="逐字片段"):
        parse_m1_response(json.dumps(result, ensure_ascii=False), payload, assets.output_schema)


def test_questions_are_rejected_when_budget_is_zero() -> None:
    assets = M1Assets.load(DESIGN, legacy=True)
    payload = fixture("02_冲突且预算耗尽.input.json")
    result = fixture("02_冲突且预算耗尽.expected.json")
    result["questions"] = [
        {
            "question_id": "q1",
            "gap_id": "g1",
            "field": "constraints",
            "scope": "报名网站",
            "text": "你确定要改吗？",
            "options": [],
            "reason": "重复确认。",
            "depends_on": [],
        }
    ]

    with pytest.raises(M1ValidationError, match="预算"):
        parse_m1_response(json.dumps(result, ensure_ascii=False), payload, assets.output_schema)


def test_explicit_change_is_not_asked_again_when_budget_exists() -> None:
    assets = M1Assets.load(DESIGN, legacy=True)
    payload = fixture("02_冲突且预算耗尽.input.json")
    payload["control"].update({"remaining_rounds": 1, "allow_questions": True})
    result = fixture("02_冲突且预算耗尽.expected.json")
    result["questions"] = [
        {
            "question_id": "q1",
            "gap_id": "g1",
            "field": "constraints",
            "scope": "报名网站",
            "text": "你确定要改吗？",
            "options": [],
            "reason": "重复确认。",
            "depends_on": [],
        }
    ]

    with pytest.raises(M1ValidationError, match="明确修改"):
        parse_m1_response(json.dumps(result, ensure_ascii=False), payload, assets.output_schema)


def test_selected_category_cannot_be_silently_changed() -> None:
    assets = M1Assets.load(DESIGN, legacy=True)
    payload = fixture("02_冲突且预算耗尽.input.json")
    result = fixture("02_冲突且预算耗尽.expected.json")
    result["category"]["primary"] = "general"

    with pytest.raises(M1ValidationError, match="已选类别"):
        parse_m1_response(json.dumps(result, ensure_ascii=False), payload, assets.output_schema)


def test_invalid_input_fallback_must_be_empty_and_unready() -> None:
    assets = M1Assets.load(DESIGN, legacy=True)
    payload = fixture("01_报名网站.input.json")
    result = fixture("01_报名网站.expected.json")
    result["status"] = "input_error"
    result["error"] = {"code": "invalid_input", "message": "invalid"}

    with pytest.raises(M1ValidationError, match="input_error"):
        parse_m1_response(json.dumps(result, ensure_ascii=False), payload, assets.output_schema)


def test_readiness_accepts_extra_note_without_changing_readiness() -> None:
    assets = M1Assets.load(DESIGN, legacy=True)
    payload = fixture("01_报名网站.input.json")
    result = fixture("01_报名网站.expected.json")
    result["request_id"] = payload["request_id"]
    result["task_id"] = payload["task_id"]
    result["base_version"] = payload["base_version"]
    result["gap_updates"] = []
    result["question_reopens"] = []
    result["readiness"]["blocking_gap_ids_note"] = "需在下游任务中继续核对"

    parsed = parse_m1_response(json.dumps(result, ensure_ascii=False), payload, assets.output_schema)
    assert "blocking_gap_ids_note" not in parsed["readiness"]
    assert "需在下游任务中继续核对" in parsed["assistant_text"]
