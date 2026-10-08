from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from promptsmith.m3 import M3Assets, M3ValidationError, build_m3_input, parse_m3_response
from promptsmith.m4 import M4Assets, M4ValidationError, build_m4_input, parse_m4_response
from promptsmith.skill_catalog import SkillCatalog


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "resources" / "prompts"
FIXTURES = DESIGN / "fixtures_m3_m4"


def fixture(stem: str) -> dict:
    return json.loads((FIXTURES / stem).read_text(encoding="utf-8"))


def test_m3_manual_normal_fixture_parses_and_maps_only_real_input_references() -> None:
    payload = fixture("m3_normal.manual_fixture.input.json")
    output = fixture("m3_normal.manual_fixture.output.json")

    parsed = parse_m3_response(
        json.dumps(output, ensure_ascii=False), payload, M3Assets.load(DESIGN).output_schema
    )

    assert parsed["assessments"][0]["candidate_id"] == "candidate-fixture-spec-01"
    assert parsed["unmatched_key_work_ids"] == []


def test_m3_manual_no_match_fixture_marks_the_real_work_unmatched() -> None:
    payload = fixture("m3_no_match.manual_fixture.input.json")
    output = fixture("m3_no_match.manual_fixture.output.json")

    parsed = parse_m3_response(
        json.dumps(output, ensure_ascii=False), payload, M3Assets.load(DESIGN).output_schema
    )

    assert parsed["assessments"][0]["decision"] == "no_match"
    assert parsed["unmatched_key_work_ids"] == ["kw-notice-01"]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("omit", "遗漏"),
        ("duplicate", "重复"),
        ("candidate", "候选"),
        ("capability", "能力"),
        ("prerequisite", "前提"),
        ("unmatched", "无匹配"),
        ("request", "request_id"),
    ],
)
def test_m3_rejects_invalid_candidate_coverage_and_references(mutation: str, message: str) -> None:
    payload = fixture("m3_normal.manual_fixture.input.json")
    output = fixture("m3_normal.manual_fixture.output.json")
    if mutation == "omit":
        output["assessments"] = []
    elif mutation == "duplicate":
        output["assessments"].append(deepcopy(output["assessments"][0]))
    elif mutation == "candidate":
        output["assessments"][0]["candidate_id"] = "outside-batch"
    elif mutation == "capability":
        output["assessments"][0]["capability_ids"] = ["cap-not-in-candidate"]
    elif mutation == "prerequisite":
        output["assessments"][0]["prerequisite_ids"] = ["prereq-not-in-candidate"]
    elif mutation == "unmatched":
        output["unmatched_key_work_ids"] = ["kw-other"]
    elif mutation == "request":
        output["request_id"] = "another-request"

    with pytest.raises(M3ValidationError, match=message):
        parse_m3_response(json.dumps(output, ensure_ascii=False), payload, M3Assets.load(DESIGN).output_schema)


def test_m3_error_branch_is_exclusive_and_has_no_fake_http_details() -> None:
    payload = fixture("m3_normal.manual_fixture.input.json")
    output = fixture("m3_error.manual_fixture.output.json")
    parsed = parse_m3_response(
        json.dumps(output, ensure_ascii=False), payload, M3Assets.load(DESIGN).output_schema
    )
    assert parsed["status"] == "error"

    mixed = deepcopy(output)
    mixed["assessments"] = deepcopy(fixture("m3_normal.manual_fixture.output.json")["assessments"])
    with pytest.raises(M3ValidationError, match="错误分支"):
        parse_m3_response(json.dumps(mixed, ensure_ascii=False), payload, M3Assets.load(DESIGN).output_schema)


def test_build_m3_input_uses_candidate_snapshot_and_validates_payload() -> None:
    source = fixture("m3_normal.manual_fixture.input.json")
    candidate = source["candidates"][0]

    payload = build_m3_input(
        source["request_id"],
        source["task_id"],
        source["source_basis"],
        source["key_work"],
        [candidate],
        source["target_environment"],
    )

    assert payload == source
    assert M3Assets.load(DESIGN).input_schema["required"]


def test_build_m3_input_converts_a_real_local_catalog_match() -> None:
    catalog = SkillCatalog.load(
        ROOT / "resources" / "skill_catalog" / "catalog_v0.1.json",
        source_root=ROOT,
        verify_sources=True,
    )
    work = {
        "key_work_id": "kw-spec",
        "title": "整理软件开发规格",
        "goal": "把需求整理成软件开发规格",
        "inputs": ["已确认需求"],
        "outputs": ["本地规格"],
        "checkpoints": ["测试决定覆盖需求"],
        "step_ids": ["step-spec"],
    }
    match = catalog.match([work])

    payload = build_m3_input(
        "request-catalog-test",
        "task-catalog-test",
        {"plan_id": "plan-test", "plan_version": 1, "requirement_version": 1},
        [work],
        match.candidates,
        {"known": [], "unknown": [], "forbidden_actions": []},
    )

    assert match.candidates
    assert payload["candidates"][0]["skill_id"] == "to-spec"
    assert "record_snapshot" not in payload["candidates"][0]
    assert payload["candidates"][0]["capabilities"][0]["capability_id"] == "cap-spec-structure"


def test_build_m3_input_preserves_remote_source_provenance() -> None:
    source = fixture("m3_normal.manual_fixture.input.json")
    candidate = deepcopy(source["candidates"][0])
    candidate["origin"] = "remote"
    candidate["record_snapshot"] = {
        "origin": "remote",
        "source_url": "https://github.com/example/skill/blob/abc/SKILL.md",
        "fixed_commit": "unresolved",
        "content_hash_kind": "api_metadata",
        "content_sha256": "a" * 64,
        "verification": {
            "verification_status": "network_unverified",
            "source_read": False,
            "installed": False,
            "execution_tested": False,
        },
    }

    payload = build_m3_input(
        source["request_id"],
        source["task_id"],
        source["source_basis"],
        source["key_work"],
        [candidate],
        source["target_environment"],
    )

    assert payload["candidates"][0]["provenance"] == {
        "origin": "remote",
        "source_url": "https://github.com/example/skill/blob/abc/SKILL.md",
        "fixed_commit": "unresolved",
        "content_hash_kind": "api_metadata",
        "content_sha256": "a" * 64,
        "verification_status": "network_unverified",
        "source_read": False,
        "installed": False,
        "execution_tested": False,
    }


def test_build_m4_input_accepts_optional_remote_source_provenance() -> None:
    payload = fixture("m4_normal.manual_fixture.input.json")
    provenance = {
        "origin": "remote",
        "source_url": "https://github.com/example/skill/blob/abc/SKILL.md",
        "fixed_commit": "unresolved",
        "content_hash_kind": "api_metadata",
        "content_sha256": "b" * 64,
        "verification_status": "network_unverified",
        "source_read": False,
        "installed": False,
        "execution_tested": False,
    }
    payload["bindings"][0]["provenance"] = provenance

    prepared = build_m4_input(payload)

    assert prepared["bindings"][0]["provenance"] == provenance

    payload["bindings"][0]["prerequisite_assessments"][0]["source"] = "catalog_evidence"
    with pytest.raises(M4ValidationError, match="远程 Skill 前提"):
        build_m4_input(payload)


def test_build_m4_input_accepts_search_metadata_provenance() -> None:
    payload = fixture("m4_normal.manual_fixture.input.json")
    payload["bindings"][0]["provenance"] = {
        "origin": "remote",
        "source_url": "https://github.com/example/skill/blob/main/SKILL.md",
        "fixed_commit": "unresolved",
        "content_hash_kind": "search_metadata",
        "content_sha256": "c" * 64,
        "verification_status": "network_unverified",
        "source_read": False,
        "installed": False,
        "execution_tested": False,
    }

    prepared = build_m4_input(payload)

    assert prepared["bindings"][0]["provenance"]["content_hash_kind"] == "search_metadata"


def test_m4_manual_normal_fixture_requires_complete_selected_binding_coverage() -> None:
    payload = fixture("m4_normal.manual_fixture.input.json")
    output = fixture("m4_normal.manual_fixture.output.json")

    parsed = parse_m4_response(
        json.dumps(output, ensure_ascii=False), payload, M4Assets.load(DESIGN).output_schema
    )

    assert parsed["contributions"][0]["binding_id"] == "binding-fixture-spec-01"


def test_m4_no_binding_fixture_allows_a_zero_contribution_result() -> None:
    payload = fixture("m4_no_match.manual_fixture.input.json")
    output = fixture("m4_no_match.manual_fixture.output.json")

    parsed = parse_m4_response(
        json.dumps(output, ensure_ascii=False), payload, M4Assets.load(DESIGN).output_schema
    )

    assert parsed["status"] == "ok"
    assert parsed["contributions"] == []


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing_binding", "绑定"),
        ("unselected_binding", "绑定"),
        ("step", "步骤"),
        ("capability", "能力"),
        ("prerequisite", "前提"),
        ("duplicate_pair", "重复"),
        ("unknown_change", "变化"),
        ("duplicate_change", "重复"),
        ("baseline_rewrite", "不符合契约"),
        ("accepted_field", "不符合契约"),
    ],
)
def test_m4_rejects_missing_coverage_and_unknown_or_duplicate_references(
    mutation: str, message: str
) -> None:
    payload = fixture("m4_normal.manual_fixture.input.json")
    output = fixture("m4_normal.manual_fixture.output.json")
    contribution = output["contributions"][0]
    if mutation == "missing_binding":
        output["contributions"] = []
    elif mutation == "unselected_binding":
        contribution["binding_id"] = "binding-not-selected"
    elif mutation == "step":
        contribution["step_id"] = "step-not-allowed"
    elif mutation == "capability":
        contribution["capability_ids"] = ["cap-not-in-binding"]
    elif mutation == "prerequisite":
        contribution["prerequisite_ids"] = ["prereq-not-in-binding"]
    elif mutation == "duplicate_pair":
        output["contributions"].append(deepcopy(contribution))
    elif mutation == "unknown_change":
        contribution["proposed_change_ids"] = ["change-missing"]
    elif mutation == "duplicate_change":
        change = {
            "change_id": "change-optional-scope",
            "binding_ids": ["binding-fixture-spec-01"],
            "kind": "scope",
            "description": "可选补充一个术语表。",
            "reason": "便于一致使用领域名称。",
            "affects_hard_constraints": False,
        }
        output["proposed_changes"] = [deepcopy(change), deepcopy(change)]
    elif mutation == "baseline_rewrite":
        output["baseline"] = {"requirements": []}
    elif mutation == "accepted_field":
        output["accepted"] = True

    with pytest.raises(M4ValidationError, match=message):
        parse_m4_response(json.dumps(output, ensure_ascii=False), payload, M4Assets.load(DESIGN).output_schema)


def test_m4_error_branch_is_exclusive() -> None:
    payload = fixture("m4_normal.manual_fixture.input.json")
    output = fixture("m4_error.manual_fixture.output.json")
    parsed = parse_m4_response(
        json.dumps(output, ensure_ascii=False), payload, M4Assets.load(DESIGN).output_schema
    )
    assert parsed["error"]["code"] == "constraint_conflict"

    mixed = deepcopy(output)
    mixed["contributions"] = deepcopy(fixture("m4_normal.manual_fixture.output.json")["contributions"])
    with pytest.raises(M4ValidationError, match="错误分支"):
        parse_m4_response(json.dumps(mixed, ensure_ascii=False), payload, M4Assets.load(DESIGN).output_schema)


def test_build_m4_input_is_a_validated_deep_copy() -> None:
    source = fixture("m4_normal.manual_fixture.input.json")

    payload = build_m4_input(source)

    assert payload == source
    assert payload is not source
    assert payload["baseline"] is not source["baseline"]


@pytest.mark.parametrize("mutation", ["omitted_prerequisite", "missing_fallback"])
def test_m4_unknown_blocking_prerequisite_requires_reference_and_fallback(mutation: str) -> None:
    payload = fixture("m4_normal.manual_fixture.input.json")
    output = fixture("m4_normal.manual_fixture.output.json")
    prerequisite = payload["bindings"][0]["prerequisite_assessments"][0]
    prerequisite["status"] = "unknown"
    contribution = output["contributions"][0]
    contribution["fallback_actions"] = []
    if mutation == "missing_fallback":
        contribution["prerequisite_ids"] = [prerequisite["prerequisite_id"]]

    with pytest.raises(M4ValidationError, match="阻断性未知前提|fallback"):
        parse_m4_response(
            json.dumps(output, ensure_ascii=False), payload, M4Assets.load(DESIGN).output_schema
        )


def test_m4_unknown_blocking_prerequisite_accepts_an_explicit_fallback() -> None:
    payload = fixture("m4_normal.manual_fixture.input.json")
    output = fixture("m4_normal.manual_fixture.output.json")
    prerequisite = payload["bindings"][0]["prerequisite_assessments"][0]
    prerequisite["status"] = "unknown"
    contribution = output["contributions"][0]
    contribution["prerequisite_ids"] = [prerequisite["prerequisite_id"]]
    contribution["fallback_actions"] = ["缺少已确认需求时，停止采用本方法并保留待补充状态。"]

    parsed = parse_m4_response(
        json.dumps(output, ensure_ascii=False), payload, M4Assets.load(DESIGN).output_schema
    )

    assert parsed["contributions"][0]["prerequisite_ids"] == [prerequisite["prerequisite_id"]]


def test_m4_input_schema_has_local_environment_definition() -> None:
    schema = M4Assets.load(DESIGN).input_schema

    assert schema["properties"]["target_environment"]["$ref"] == "#/$defs/environment"
    assert "known" in schema["$defs"]["environment"]["properties"]
