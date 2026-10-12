"""Deterministic compatibility repairs at model response boundaries."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from typing import Any


def json_text(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```") and text.endswith("```"):
        return "\n".join(text.splitlines()[1:-1]).strip()
    return text


def string_list(value: Any) -> list[str]:
    values = [value] if isinstance(value, str) else value if isinstance(value, list) else []
    return list(dict.fromkeys(item.strip() for item in values if isinstance(item, str) and item.strip()))


def object_list(value: Any, path: str, report: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict):
        report.append({"action": "object_to_list", "path": path})
        value = [value]
    elif not isinstance(value, list):
        report.append({"action": "extra_field", "path": path, "value": value})
        return []
    result = []
    for row in value:
        if isinstance(row, dict):
            result.append(row)
        else:
            report.append({"action": "extra_field", "path": path, "value": row})
    return result


def normalize_shape(value: Any, schema: dict[str, Any], report: list[dict[str, Any]] | None = None) -> Any:
    """Accept extra fields and string/list drift without inventing required facts."""
    events = report if report is not None else []

    def visit(item: Any, spec: dict[str, Any], path: str) -> Any:
        if "$ref" in spec and spec["$ref"].startswith("#/"):
            target = schema
            for part in spec["$ref"][2:].split("/"):
                target = target[part]
            return visit(item, target, path)
        for choice in spec.get("oneOf", []):
            if choice.get("type") == "null" and item is None:
                return None
            if "$ref" in choice and isinstance(item, dict):
                return visit(item, choice, path)
        if isinstance(item, dict) and "properties" in spec:
            result = deepcopy(item)
            if spec.get("additionalProperties") is False:
                for key in list(result):
                    if key not in spec["properties"]:
                        events.append({"action": "extra_field", "path": f"{path}.{key}", "value": result.pop(key)})
            for key, child in spec["properties"].items():
                if key in result:
                    result[key] = visit(result[key], child, f"{path}.{key}")
                elif child.get("type") == "array" and not child.get("minItems"):
                    result[key] = []
                    events.append({"action": "empty_collection", "path": f"{path}.{key}"})
            return result
        if spec.get("type") == "array":
            child = spec.get("items", {})
            if isinstance(item, str) and child.get("type") == "string":
                events.append({"action": "string_to_list", "path": path})
                item = [item] if item.strip() else []
            if isinstance(item, list):
                result = [visit(row, child, f"{path}[{index}]") for index, row in enumerate(item)]
                if spec.get("uniqueItems") and all(isinstance(row, str) for row in result):
                    unique = list(dict.fromkeys(result))
                    if unique != result:
                        events.append({"action": "deduplicate", "path": path})
                    return unique
                return result
        return deepcopy(item)

    return visit(value, schema, "$")


def log_repairs(stage: str, request_id: str, report: list[dict[str, Any]]) -> None:
    if report:
        summary = [{key: value for key, value in event.items() if key != "value"} for event in report]
        logging.getLogger(__name__).warning(
            "%s accepted with compatibility repairs; request=%s; details=%s",
            stage, request_id, json.dumps(summary, ensure_ascii=False),
        )


def extra_notes(report: list[dict[str, Any]]) -> list[str]:
    return [
        f"模型补充内容（尚未核对，{event['path']}）：{json.dumps(event['value'], ensure_ascii=False)}"
        for event in report if event.get("action") == "extra_field" and event.get("value") not in (None, [], {}, "")
    ]


def reference_contribution(binding: dict[str, Any], work: dict[str, Any]) -> dict[str, Any]:
    record = binding.get("record_snapshot") or {}
    name = record.get("name") or binding.get("skill_id") or "所选 Skill"
    goal = work.get("goal") or work.get("title") or "当前关键工作"
    raw_assessments = binding.get("prerequisite_assessments", binding.get("precondition_assessments", []))
    assessments = [row for row in raw_assessments if isinstance(row, dict)] if isinstance(raw_assessments, list) else []
    expected = {row["prerequisite_id"]: row for row in record.get("adaptation_prerequisites", []) if isinstance(row, dict) and row.get("prerequisite_id")}
    assessed = {row["prerequisite_id"]: row for row in assessments if row.get("prerequisite_id")}
    unknown = [row for row in assessments if row.get("status") != "satisfied"]
    unknown.extend({**row, "status": "unknown"} for key, row in expected.items() if key not in assessed)
    if not record.get("method_adaptation_allowed", binding.get("method_adaptation_allowed", True)):
        unknown.append({"description": "该 Skill 的方法适配未获确认，先读取其适用范围。", "status": "unknown"})
    caveats = [
        "Skill 的实际格式、工具及环境适用性尚未完整验证；请先读取入口，再确认能否使用。",
        "缺少材料或 Skill 不适用时，说明原因、询问必要信息，并先完成不依赖它的工作。",
        *[f"待核对前提：{row.get('description') or row.get('prerequisite_id')}（{row.get('status', 'unknown')}）。" for row in unknown],
    ]
    return {
        "binding_id": binding["binding_id"],
        "step_id": binding["step_ids"][0],
        "capability_ids": list(binding.get("capability_ids", [])),
        "method_actions": [f"读取 {name} 的 SKILL.md 或来源说明，结合当前任务用于：{goal}。"],
        "planned_inputs": string_list(work.get("inputs")) or ["当前任务、已确认需求和方案；缺失材料请向用户询问。"],
        "expected_outputs": string_list(work.get("outputs")) or [f"完成与“{goal}”对应的任务产物，具体形式按用户要求核对。"],
        "checkpoints": string_list(work.get("checkpoints")) or ["核对用户目标与约束，注明未验证的内容。"],
        "prerequisite_ids": [row["prerequisite_id"] for row in unknown if row.get("prerequisite_id")],
        "fallback_actions": caveats,
        "proposed_change_ids": [],
    }
