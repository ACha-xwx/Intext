"""Pure input construction and semantic validation for M4 method contributions."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from .paths import m1_asset_dir


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
        if not binding["method_adaptation_allowed"]:
            raise M4ValidationError(f"绑定 {binding['binding_id']} 不允许方法适配。")
        work = key_work.get(binding["key_work_id"])
        if work is None:
            raise M4ValidationError("绑定引用了不存在的关键工作。")
        if not binding["step_ids"] or not set(binding["step_ids"]).issubset(set(work["step_ids"])):
            raise M4ValidationError("绑定允许步骤不属于对应关键工作。")
        if not set(binding["step_ids"]).issubset(steps):
            raise M4ValidationError("绑定允许步骤引用了不存在的方案步骤。")
        if not binding["capability_ids"] or len(binding["capability_ids"]) != len(set(binding["capability_ids"])):
            raise M4ValidationError("绑定能力编号为空或重复。")
        prereqs = _id_map(binding["prerequisite_assessments"], "prerequisite_id", "绑定前提")
        if binding.get("provenance", {}).get("origin") == "remote" and any(
            row["source"] == "catalog_evidence" for row in prereqs.values()
        ):
            raise M4ValidationError("远程 Skill 前提不能标记为本地目录证据。")
        if any(row["status"] == "incompatible" for row in prereqs.values()):
            raise M4ValidationError("不兼容的前提不能送入 M4 整合。")
    _id_map(payload["suggestion_decisions"], "suggestion_id", "建议决策")


def parse_m4_response(
    raw: str,
    payload: dict[str, Any],
    output_schema: dict[str, Any],
) -> dict[str, Any]:
    _schema_error(payload, M4Assets.load().input_schema, "M4输入")
    _validate_input(payload)
    parsed = _strict_json_loads(raw)
    if parsed.get("status") == "error" and (
        parsed.get("contributions") or parsed.get("proposed_changes")
    ):
        raise M4ValidationError("M4错误分支不能包含正常增量内容。")
    _schema_error(parsed, output_schema, "M4输出")
    for key in ("request_id", "task_id"):
        if parsed[key] != payload[key]:
            raise M4ValidationError(f"模型返回的{key}与请求不一致。")
    if parsed["status"] == "error":
        return parsed

    bindings = {row["binding_id"]: row for row in payload["bindings"]}
    step_ids = {row["step_id"] for row in payload["steps"]}
    changes = _id_map(parsed["proposed_changes"], "change_id", "M4新增变化")
    seen_pairs: set[tuple[str, str]] = set()
    contributions_by_binding: dict[str, list[dict[str, Any]]] = {binding_id: [] for binding_id in bindings}
    for contribution in parsed["contributions"]:
        binding_id = contribution["binding_id"]
        binding = bindings.get(binding_id)
        if binding is None:
            raise M4ValidationError(f"贡献引用了未选绑定：{binding_id}")
        step_id = contribution["step_id"]
        if step_id not in step_ids or step_id not in binding["step_ids"]:
            raise M4ValidationError(f"贡献步骤不属于该绑定：{step_id}")
        pair = (binding_id, step_id)
        if pair in seen_pairs:
            raise M4ValidationError("同一绑定和步骤的贡献重复。")
        seen_pairs.add(pair)
        if not set(contribution["capability_ids"]).issubset(set(binding["capability_ids"])):
            raise M4ValidationError("贡献引用了绑定未选择的能力。")
        allowed_prerequisites = {
            row["prerequisite_id"] for row in binding["prerequisite_assessments"]
        }
        if not set(contribution["prerequisite_ids"]).issubset(allowed_prerequisites):
            raise M4ValidationError("贡献引用了绑定未声明的前提。")
        for prerequisite in binding["prerequisite_assessments"]:
            if prerequisite["status"] == "unknown" and prerequisite["blocking"]:
                if prerequisite["prerequisite_id"] not in contribution["prerequisite_ids"]:
                    raise M4ValidationError("贡献遗漏了阻断性未知前提。")
                if not contribution["fallback_actions"]:
                    raise M4ValidationError("阻断性未知前提需要明确 fallback。")
        for change_id in contribution["proposed_change_ids"]:
            change = changes.get(change_id)
            if change is None:
                raise M4ValidationError(f"贡献引用了不存在的新增变化：{change_id}")
            if binding_id not in change["binding_ids"]:
                raise M4ValidationError("新增变化没有关联到引用它的绑定。")
        contributions_by_binding[binding_id].append(contribution)

    missing_bindings = sorted(binding_id for binding_id, rows in contributions_by_binding.items() if not rows)
    if missing_bindings:
        raise M4ValidationError(f"已选绑定缺少具体贡献：{', '.join(missing_bindings)}")

    for change in changes.values():
        for binding_id in change["binding_ids"]:
            if binding_id not in bindings:
                raise M4ValidationError(f"新增变化引用了未选绑定：{binding_id}")
            if not any(change["change_id"] in row["proposed_change_ids"] for row in contributions_by_binding[binding_id]):
                raise M4ValidationError("新增变化关联的绑定贡献未引用该变化。")
    return parsed
