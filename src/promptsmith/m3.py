"""Pure input construction and response validation for M3 candidate analysis."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

from .paths import m1_asset_dir


class M3ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class M3Assets:
    system_prompt: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    prompt_version: str = "M3_system_v0.1"
    contract_version: str = "m3.v0.1"

    @classmethod
    def load(cls, directory: str | Path | None = None) -> "M3Assets":
        root = Path(directory) if directory else m1_asset_dir()
        return cls(
            system_prompt=(root / "M3_system_v0.1.txt").read_text(encoding="utf-8-sig"),
            input_schema=json.loads((root / "M3_input_v0.1.schema.json").read_text(encoding="utf-8-sig")),
            output_schema=json.loads((root / "M3_output_v0.1.schema.json").read_text(encoding="utf-8-sig")),
        )


def _schema_error(value: dict[str, Any], schema: dict[str, Any], label: str) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        path = ".".join(str(part) for part in errors[0].path) or "$"
        raise M3ValidationError(f"{label}不符合契约（{path}）：{errors[0].message}")


def _strict_json_loads(raw: str) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise M3ValidationError(f"模型JSON包含重复键：{key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> Any:
        raise M3ValidationError(f"模型JSON包含非法数值：{value}")

    try:
        parsed = json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid_constant)
    except M3ValidationError:
        raise
    except json.JSONDecodeError as exc:
        raise M3ValidationError(f"模型未返回有效JSON：第{exc.lineno}行第{exc.colno}列") from None
    if not isinstance(parsed, dict):
        raise M3ValidationError("模型JSON根节点必须是对象。")
    return parsed


def _remote_provenance(record: Mapping[str, Any]) -> dict[str, Any] | None:
    if record.get("origin") != "remote":
        return None
    verification = record.get("verification")
    verification = verification if isinstance(verification, Mapping) else {}
    return {
        "origin": "remote",
        "source_url": record.get("source_url", ""),
        "fixed_commit": record.get("fixed_commit", "unresolved"),
        "content_hash_kind": record.get("content_hash_kind", "api_metadata"),
        "content_sha256": record.get("content_sha256", ""),
        "verification_status": verification.get("verification_status", "network_unverified"),
        "source_read": bool(verification.get("source_read", False)),
        "installed": bool(verification.get("installed", False)),
        "execution_tested": bool(verification.get("execution_tested", False)),
    }


def _candidate_for_model(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Reduce a local catalog candidate to its approved evidence snapshot."""
    row = deepcopy(dict(candidate))
    record = row.pop("record_snapshot", None)
    if not isinstance(record, dict):
        return row
    provenance = _remote_provenance(record)
    if provenance is not None and not isinstance(record.get("capabilities"), list):
        row.pop("origin", None)
        row["provenance"] = provenance
        return row
    selected_capabilities = set(row.get("capability_ids", []))
    capabilities = []
    for capability in record.get("capabilities", []):
        if capability.get("capability_id") not in selected_capabilities:
            continue
        capabilities.append(
            {
                key: deepcopy(capability[key])
                for key in ("capability_id", "summary", "inputs", "outputs", "limitations", "evidence")
                if key in capability
            }
        )

    def prerequisites(name: str) -> list[dict[str, Any]]:
        return [
            {
                "prerequisite_id": item["prerequisite_id"],
                "description": item["description"],
                "status": item.get("status", "unknown"),
            }
            for item in record.get(name, [])
        ]

    result = {
        "candidate_id": row["candidate_id"],
        "skill_id": row["skill_id"],
        "key_work_id": row["key_work_id"],
        "record_hash": row["record_hash"],
        "usage_mode": row.get("usage_mode", "method_adaptation"),
        "method_adaptation_allowed": bool(record.get("method_adaptation_allowed", False)),
        "step_ids": deepcopy(row.get("step_ids", [])),
        "capabilities": capabilities,
        "original_prerequisites": prerequisites("original_prerequisites"),
        "adaptation_prerequisites": prerequisites("adaptation_prerequisites"),
        "limitations": deepcopy(row.get("limitations", [])),
    }
    if provenance is not None:
        result["provenance"] = provenance
    return result


def build_m3_input(
    request_id: str,
    task_id: str,
    source_basis: Mapping[str, Any],
    key_work: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    target_environment: Mapping[str, Any],
) -> dict[str, Any]:
    payload = {
        "schema_version": "m3.v0.1",
        "request_id": request_id,
        "task_id": task_id,
        "source_basis": deepcopy(dict(source_basis)),
        "key_work": deepcopy(list(key_work)),
        "candidates": [_candidate_for_model(candidate) for candidate in candidates],
        "target_environment": deepcopy(dict(target_environment)),
    }
    _schema_error(payload, M3Assets.load().input_schema, "M3输入")
    _validate_input_references(payload)
    return payload


def _unique_map(rows: list[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row[key]
        if value in result:
            raise M3ValidationError(f"{label}包含重复编号：{value}")
        result[value] = row
    return result


def _validate_input_references(payload: dict[str, Any]) -> None:
    works = _unique_map(payload["key_work"], "key_work_id", "M3关键工作")
    candidates = _unique_map(payload["candidates"], "candidate_id", "M3候选")
    pairs: set[tuple[str, str]] = set()
    for candidate in candidates.values():
        work_id = candidate["key_work_id"]
        if work_id not in works:
            raise M3ValidationError(f"候选引用了输入外关键工作：{work_id}")
        pair = (candidate["skill_id"], work_id)
        if pair in pairs:
            raise M3ValidationError("候选批次包含重复的 Skill／关键工作组合。")
        pairs.add(pair)
        work_steps = set(works[work_id]["step_ids"])
        if not set(candidate["step_ids"]).issubset(work_steps):
            raise M3ValidationError("候选允许步骤超出对应关键工作的步骤。")
        _unique_map(candidate["capabilities"], "capability_id", "候选能力")
        _unique_map(candidate["original_prerequisites"], "prerequisite_id", "原版前提")
        _unique_map(candidate["adaptation_prerequisites"], "prerequisite_id", "适配前提")


def parse_m3_response(
    raw: str,
    payload: dict[str, Any],
    output_schema: dict[str, Any],
) -> dict[str, Any]:
    _schema_error(payload, M3Assets.load().input_schema, "M3输入")
    _validate_input_references(payload)
    parsed = _strict_json_loads(raw)
    if parsed.get("status") == "error" and (
        parsed.get("assessments") or parsed.get("unmatched_key_work_ids")
    ):
        raise M3ValidationError("M3错误分支不能包含正常评估内容。")
    _schema_error(parsed, output_schema, "M3输出")
    for key in ("request_id", "task_id"):
        if parsed[key] != payload[key]:
            raise M3ValidationError(f"模型返回的{key}与请求不一致。")

    if parsed["status"] == "error":
        return parsed

    candidates = {row["candidate_id"]: row for row in payload["candidates"]}
    works = {row["key_work_id"] for row in payload["key_work"]}
    assessments = parsed["assessments"]
    seen: set[str] = set()
    has_recommendation: set[str] = set()
    for assessment in assessments:
        candidate_id = assessment["candidate_id"]
        if candidate_id not in candidates:
            raise M3ValidationError(f"评估引用了候选批次外编号：{candidate_id}")
        if candidate_id in seen:
            raise M3ValidationError(f"候选评估包含重复编号：{candidate_id}")
        seen.add(candidate_id)
        candidate = candidates[candidate_id]
        allowed_capabilities = {row["capability_id"] for row in candidate["capabilities"]}
        allowed_prerequisites = {
            row["prerequisite_id"] for row in candidate["adaptation_prerequisites"]
        }
        if not set(assessment["capability_ids"]).issubset(allowed_capabilities):
            raise M3ValidationError("评估引用了候选未声明的能力。")
        if not set(assessment["prerequisite_ids"]).issubset(allowed_prerequisites):
            raise M3ValidationError("评估引用了候选未声明的适配前提。")
        if assessment["decision"] == "no_match":
            if any(assessment[key] for key in ("capability_ids", "planned_inputs", "expected_outputs", "prerequisite_ids")):
                raise M3ValidationError("no_match 评估不得携带能力、输入、输出或前提引用。")
        else:
            if not assessment["capability_ids"]:
                raise M3ValidationError("recommend／conditional 必须引用至少一项候选能力。")
            if not assessment["planned_inputs"] or not assessment["expected_outputs"]:
                raise M3ValidationError("recommend／conditional 必须说明对应输入和预期输出。")
            has_recommendation.add(candidate["key_work_id"])

    if seen != set(candidates):
        missing = sorted(set(candidates) - seen)
        raise M3ValidationError(f"候选评估有遗漏：{', '.join(missing)}")
    if not set(parsed["unmatched_key_work_ids"]).issubset(works):
        raise M3ValidationError("无匹配关键工作列表包含请求外编号。")
    expected_unmatched = works - has_recommendation
    if set(parsed["unmatched_key_work_ids"]) != expected_unmatched:
        raise M3ValidationError("无匹配关键工作列表与 recommend／conditional 评估不一致。")
    return parsed
