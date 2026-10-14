"""Pure input construction and semantic validation for M4 method contributions."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from .paths import m1_asset_dir
from .model_output import json_text, string_list, object_list, normalize_shape, log_repairs, reference_contribution


class M4ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class M4Assets:
    system_prompt: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    prompt_version: str = "M4_system_v0.2"
    contract_version: str = "m4.v0.1"

    @classmethod
    def load(cls, directory: str | Path | None = None) -> "M4Assets":
        root = Path(directory) if directory else m1_asset_dir()
        return cls(
            system_prompt=(root / "M4_system_v0.2.txt").read_text(encoding="utf-8-sig"),
            input_schema=json.loads((root / "M4_input_v0.1.schema.json").read_text(encoding="utf-8-sig")),
            output_schema=json.loads((root / "M4_output_v0.1.schema.json").read_text(encoding="utf-8-sig")),
        )


def _schema_error(value: dict[str, Any], schema: dict[str, Any], label: str) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        path = ".".join(str(part) for part in errors[0].path) or "$"
        raise M4ValidationError(f"{label}不符合契约（{path}）：{errors[0].message}")


def _strict_json_loads(raw: str) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise M4ValidationError(f"模型JSON包含重复键：{key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> Any:
        raise M4ValidationError(f"模型JSON包含非法数值：{value}")

    try:
        parsed = json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid_constant)
    except M4ValidationError:
        raise
    except json.JSONDecodeError as exc:
        raise M4ValidationError(f"模型未返回有效JSON：第{exc.lineno}行第{exc.colno}列") from None
    if not isinstance(parsed, dict):
        raise M4ValidationError("模型JSON根节点必须是对象。")
    return parsed


def build_m4_input(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(payload))
    _schema_error(result, M4Assets.load().input_schema, "M4输入")
    _validate_input(result)
    return result


def _id_map(rows: list[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row[key]
        if value in result:
            raise M4ValidationError(f"{label}包含重复编号：{value}")
        result[value] = row
    return result


def _validate_input(payload: dict[str, Any]) -> None:
    baseline = payload["baseline"]
    requirement_ids = [row["item_id"] for row in baseline["requirements"]]
    unknown_ids = [row["unknown_id"] for row in baseline["unknowns"]]
    if len(requirement_ids) != len(set(requirement_ids)):
        raise M4ValidationError("M4基线包含重复正式需求编号。")
    if len(unknown_ids) != len(set(unknown_ids)):
        raise M4ValidationError("M4基线包含重复未知项编号。")
    key_work = _id_map(payload["key_work"], "key_work_id", "M4关键工作")
    steps = _id_map(payload["steps"], "step_id", "M4步骤")
    bindings = _id_map(payload["bindings"], "binding_id", "M4绑定")
    for binding in bindings.values():
        work = key_work.get(binding["key_work_id"])
        if work is None:
            raise M4ValidationError("绑定引用了不存在的关键工作。")
        if not binding["step_ids"] or not set(binding["step_ids"]).issubset(set(work["step_ids"])):
            raise M4ValidationError("绑定允许步骤不属于对应关键工作。")
        if not set(binding["step_ids"]).issubset(steps):
            raise M4ValidationError("绑定允许步骤引用了不存在的方案步骤。")
        prereqs = _id_map(binding["prerequisite_assessments"], "prerequisite_id", "绑定前提")
        if binding.get("provenance", {}).get("origin") == "remote" and any(
            row["source"] == "catalog_evidence" for row in prereqs.values()
        ):
            raise M4ValidationError("远程 Skill 前提不能标记为本地目录证据。")
    _id_map(payload["suggestion_decisions"], "suggestion_id", "建议决策")


def _structured_response_text(text: str) -> bool:
    return text.lstrip("\ufeff \t\r\n").startswith(("{", "[", "```")) or bool(re.search(
        r"[\"'](?:schema_version|request_id|task_id|contributions|proposed_changes|binding_id)[\"']\s*:", text,
    ))


def _recovery_notes(report: list[dict[str, Any]]) -> list[str]:
    """Keep task prose; response metadata belongs only in run evidence."""
    notes = []
    for event in list(report):
        action = event["action"]
        if action == "model_advisory_error":
            value = event.get("value")
            values = [value.get(key) for key in ("code", "message", "recovery_action")] if isinstance(value, dict) else [value]
            prefix = "模型整合尚待核对："
        elif action in {"extra_field", "unstructured_guidance"}:
            values = string_list(event.get("value"))
            prefix = "模型补充内容（尚未核对）：" if action == "extra_field" else "模型整合尚待核对："
        else:
            continue
        readable = [value for value in string_list(values) if not _structured_response_text(value)]
        notes.extend(prefix + value for value in readable)
        if event.get("value") and not readable:
            report.append({"action": "structured_note_omitted", "path": event["path"]})
    if any(event["action"] == "structured_response_omitted" for event in report):
        notes.append("模型整合响应格式无法解析；已保留所选 Skill 的引用指导，使用时请读取其入口核对具体用法。")
    return notes


def parse_m4_response(
    raw: str,
    payload: dict[str, Any],
    output_schema: dict[str, Any],
    *,
    normalization_report: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    _schema_error(payload, M4Assets.load().input_schema, "M4输入")
    _validate_input(payload)
    repairs = normalization_report if normalization_report is not None else []
    text = json_text(raw).lstrip("\ufeff")
    # Strip only an outer explanation/code fence around one complete object.
    # The enclosed JSON still goes through strict parsing and identity checks.
    wrapped = re.fullmatch(r"[^{}\[\]]*(\{.*\})[^{}\[\]]*", text, re.DOTALL)
    if wrapped and wrapped.group(1) != text:
        text = wrapped.group(1)
        repairs.append({"action": "unwrap_json", "path": "$"})
    try:
        parsed = _strict_json_loads(text)
    except M4ValidationError as exc:
        if not raw.strip() or "重复键" in str(exc) or "非法数值" in str(exc):
            raise
        parsed = {"contributions": [], "proposed_changes": []}
        if _structured_response_text(text) or _structured_response_text(raw):
            repairs.append({"action": "structured_response_omitted", "path": "$", "reason": str(exc)})
        else:
            repairs.append({"action": "unstructured_guidance", "path": "$", "value": raw})
    for key in ("request_id", "task_id"):
        if key in parsed and parsed[key] != payload[key]:
            raise M4ValidationError(f"模型返回的{key}与请求不一致。")
    if parsed.get("status") == "error":
        repairs.append({"action": "model_advisory_error", "path": "$.error", "value": parsed.get("error")})
    parsed = normalize_shape(parsed, output_schema, repairs)
    bindings = {row["binding_id"]: row for row in payload["bindings"]}
    works = {row["key_work_id"]: row for row in payload["key_work"]}
    changes: dict[str, dict[str, Any]] = {}
    change_rows = object_list(parsed.get("proposed_changes"), "$.proposed_changes", repairs)
    for index, row in enumerate(change_rows):
        if not isinstance(row.get("description"), str) or not row["description"].strip():
            repairs.append({"action": "extra_field", "path": "$.proposed_changes", "value": row})
            continue
        change_id = row.get("change_id")
        if not isinstance(change_id, str) or not change_id.strip():
            change_id = f"change-{index + 1}"
        while change_id in changes:
            change_id += "-recovered"
        origins = [item for item in string_list(row.get("binding_ids")) if item in bindings]
        if not origins:
            repairs.append({"action": "extra_field", "path": "$.proposed_changes", "value": row})
            continue
        changes[change_id] = {
            "change_id": change_id, "binding_ids": origins,
            "kind": row.get("kind") if row.get("kind") in ("scope", "cost", "permission", "assumption") else "assumption",
            "description": row["description"], "reason": row.get("reason") if isinstance(row.get("reason"), str) and row["reason"].strip() else "模型提出的待核对建议。",
            "affects_hard_constraints": row.get("affects_hard_constraints") is True,
        }
    contributions: list[dict[str, Any]] = []
    contribution_rows = object_list(parsed.get("contributions"), "$.contributions", repairs)
    for row in contribution_rows:
        binding_id = row.get("binding_id")
        binding = bindings.get(binding_id) if isinstance(binding_id, str) else None
        if binding is None:
            repairs.append({"action": "extra_field", "path": "$.unmatched_contribution", "value": row})
            continue
        item = reference_contribution(binding, works[binding["key_work_id"]])
        if (set(string_list(row.get("capability_ids"))) - set(binding["capability_ids"])
                or set(string_list(row.get("prerequisite_ids"))) - {p["prerequisite_id"] for p in binding["prerequisite_assessments"]}
                or set(string_list(row.get("proposed_change_ids"))) - set(changes)):
            repairs.append({"action": "extra_field", "path": "$.unverified_references", "value": row})
        for key in ("method_actions", "planned_inputs", "expected_outputs", "checkpoints"):
            values = string_list(row.get(key))
            if values:
                item[key] = values
            else:
                repairs.append({"action": "reference_default", "binding_id": binding_id, "field": key})
        if row.get("step_id") in binding["step_ids"]:
            item["step_id"] = row["step_id"]
        else:
            repairs.append({"action": "align_step", "binding_id": binding_id})
        item["fallback_actions"] = list(dict.fromkeys([*string_list(row.get("fallback_actions")), *item["fallback_actions"]]))
        item["proposed_change_ids"] = [key for key, change in changes.items() if binding_id in change["binding_ids"]]
        contributions.append(item)
    represented = {row["binding_id"] for row in contributions}
    for key, binding in bindings.items():
        if key not in represented:
            contributions.append(reference_contribution(binding, works[binding["key_work_id"]]))
            repairs.append({"action": "reference_default", "binding_id": key})
    notes = _recovery_notes(repairs)
    if notes and contributions:
        contributions[0]["fallback_actions"].extend(notes)
    for item in contributions:
        item["fallback_actions"] = list(dict.fromkeys(item["fallback_actions"]))
        item["proposed_change_ids"] = [key for key, change in changes.items() if item["binding_id"] in change["binding_ids"]]
    effective = {
        "schema_version": "m4.v0.1", "request_id": payload["request_id"], "task_id": payload["task_id"],
        "status": "ok", "contributions": contributions, "proposed_changes": list(changes.values()), "error": None,
    }
    _schema_error(effective, output_schema, "M4兼容结果")
    log_repairs("M4", payload["request_id"], repairs)
    return effective
