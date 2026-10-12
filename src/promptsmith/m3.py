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
    *,
    normalization_report: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    _schema_error(payload, M3Assets.load().input_schema, "M3输入")
    _validate_input_references(payload)
    from .model_output import json_text, normalize_shape, string_list, object_list, extra_notes, log_repairs
    repairs = normalization_report if normalization_report is not None else []
    parsed = normalize_shape(_strict_json_loads(json_text(raw)), output_schema, repairs)
    for key in ("request_id", "task_id"):
        if key in parsed and parsed[key] != payload[key]:
            raise M3ValidationError(f"模型返回的{key}与请求不一致。")

    if parsed["status"] == "error":
        if parsed.get("assessments") or parsed.get("unmatched_key_work_ids"):
            raise M3ValidationError("M3错误分支不能包含正常评估内容。")
        _schema_error(parsed, output_schema, "M3输出")
        return parsed

    candidates = {row["candidate_id"]: row for row in payload["candidates"]}
    works = {row["key_work_id"] for row in payload["key_work"]}
    assessments: list[dict[str, Any]] = []
    seen: set[str] = set()
    has_recommendation: set[str] = set()
    rows = object_list(parsed.get("assessments"), "$.assessments", repairs)
    for original in rows:
        if not isinstance(original, dict):
            repairs.append({"action": "extra_field", "path": "$.assessments", "value": original})
            continue
        candidate_id = original.get("candidate_id")
        if not isinstance(candidate_id, str) or candidate_id not in candidates or candidate_id in seen:
            repairs.append({"action": "extra_field", "path": "$.assessments", "value": original})
            continue
        seen.add(candidate_id)
        candidate = candidates[candidate_id]
        allowed_capabilities = {row["capability_id"] for row in candidate["capabilities"]}
        allowed_prerequisites = {
            row["prerequisite_id"] for row in candidate["adaptation_prerequisites"]
        }
        assessment = {"candidate_id": candidate_id,
            "decision": original.get("decision") if original.get("decision") in ("recommend", "conditional", "no_match") else "conditional",
            "capability_ids": [value for value in string_list(original.get("capability_ids")) if value in allowed_capabilities],
            "prerequisite_ids": [value for value in string_list(original.get("prerequisite_ids")) if value in allowed_prerequisites],
            "reason": original.get("reason") if isinstance(original.get("reason"), str) and original["reason"].strip() else "适用性尚待用户或下游 AI 核对。",
            "planned_inputs": string_list(original.get("planned_inputs")),
            "expected_outputs": string_list(original.get("expected_outputs")),
            "limitations": string_list(original.get("limitations")),
        }
        if assessment["decision"] == "no_match":
            for key in ("capability_ids", "planned_inputs", "expected_outputs", "prerequisite_ids"):
                assessment[key] = []
        else:
            if not assessment["capability_ids"]:
                assessment["capability_ids"] = list(sorted(allowed_capabilities))[:1]
                assessment["decision"] = "conditional"
            assessment["planned_inputs"] = assessment["planned_inputs"] or ["当前需求与关键工作，具体材料由下游 AI 核对。"]
            assessment["expected_outputs"] = assessment["expected_outputs"] or ["与当前关键工作相符的任务产物，具体形式待核对。"]
            has_recommendation.add(candidate["key_work_id"])
        if assessment != original:
            assessment["limitations"].append("模型评估格式或引用不完整，已整理为参考内容；实际适用性请继续核对。")
            repairs.append({"action": "conditional_assessment", "candidate_id": candidate_id})
            repairs.append({"action": "extra_field", "path": "$.original_assessment", "value": original})
        assessments.append(assessment)
    for candidate_id, candidate in candidates.items():
        if candidate_id not in seen:
            assessments.append({"candidate_id": candidate_id, "decision": "conditional",
                "capability_ids": [row["capability_id"] for row in candidate["capabilities"]][:1],
                "reason": "模型未返回此项评估，可保留为待核对参考。", "planned_inputs": ["当前需求和方案"],
                "expected_outputs": ["当前关键工作的任务产物"], "prerequisite_ids": [],
                "limitations": ["尚未完成模型适配分析，使用前请读取 Skill 并核对。"]})
            has_recommendation.add(candidate["key_work_id"])
            repairs.append({"action": "unassessed_candidate", "candidate_id": candidate_id})
    expected_unmatched = works - has_recommendation
    if set(string_list(parsed.get("unmatched_key_work_ids"))) != expected_unmatched:
        repairs.append({"action": "align_unmatched_work"})
    parsed["assessments"] = assessments
    parsed["unmatched_key_work_ids"] = sorted(expected_unmatched)
    if assessments:
        assessments[0]["limitations"].extend(extra_notes(repairs))
    _schema_error(parsed, output_schema, "M3兼容结果")
    log_repairs("M3", payload["request_id"], repairs)
    return parsed
