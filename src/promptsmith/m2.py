from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .categories import CATEGORY_CONFIG
from .paths import m2_asset_dir
from .session import SessionState, SessionStateError


class M2ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class M2Assets:
    system_prompt: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    prompt_version: str = "M2_system_v0.2"
    contract_version: str = "m2.v0.1"

    @classmethod
    def load(cls, directory: str | Path | None = None) -> "M2Assets":
        root = Path(directory) if directory else m2_asset_dir()
        return cls(
            system_prompt=(root / "M2_system_v0.2.txt").read_text(encoding="utf-8-sig"),
            input_schema=json.loads(
                (root / "M2_input_v0.1.schema.json").read_text(encoding="utf-8-sig")
            ),
            output_schema=json.loads(
                (root / "M2_output_v0.1.schema.json").read_text(encoding="utf-8-sig")
            ),
        )


def m2_system_prompt(base_prompt: str, *, compact_retry: bool = False) -> str:
    if not compact_retry:
        return base_prompt
    return base_prompt + (
        "\n\n【重新生成方案】\n"
        "上一次生成没有得到完整可用的结果，请从本次完整输入重新生成一个 JSON 对象。"
        "缩短重复说明，用简短的行动和检查描述；不要补接上次的半截 JSON，"
        "不要输出下游任务正文，不能省略正式需求覆盖、未知事项、必要步骤或检查。"
    )


def _schema_error(value: dict[str, Any], schema: dict[str, Any], label: str) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: list(e.path))
    if errors:
        path = ".".join(str(part) for part in errors[0].path) or "$"
        raise M2ValidationError(f"{label}不符合契约（{path}）：{errors[0].message}")


def _strict_json_loads(raw: str) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise M2ValidationError(f"模型JSON包含重复键：{key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> Any:
        raise M2ValidationError(f"模型JSON包含非法数值：{value}")

    try:
        parsed = json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid_constant)
    except M2ValidationError:
        raise
    except json.JSONDecodeError as exc:
        raise M2ValidationError(f"模型未返回有效JSON：第{exc.lineno}行第{exc.colno}列") from None
    if not isinstance(parsed, dict):
        raise M2ValidationError("模型JSON根节点必须是对象。")
    return parsed


def _category_for_input(session: SessionState) -> tuple[str, list[str]]:
    suggestion = session.category_suggestion or {}
    primary = session.selected_category or suggestion.get("primary") or "general"
    if primary not in CATEGORY_CONFIG["category_fields"]:
        primary = "general"
    secondary = [
        value
        for value in suggestion.get("secondary", [])
        if value in CATEGORY_CONFIG["category_fields"] and value != primary
    ]
    return primary, list(dict.fromkeys(secondary))


def _m2_strength(value: Any) -> Any:
    """Adapt M1's explicit unknown strength to the narrower M2 input contract.

    ``unspecified`` is a valid M1 value, but M2 only distinguishes hard
    requirements from preferences.  Keep the session requirement unchanged
    and treat the unknown strength as the non-binding option in the request
    snapshot rather than silently promoting it to a hard requirement.
    """
    return "preference" if value == "unspecified" else value


def build_m2_input(
    session: SessionState,
    request_id: str,
    *,
    current_date: str | None = None,
) -> dict[str, Any]:
    """Build and bind one M2 request to the current confirmed requirements snapshot."""
    session.validate_m2_entry()
    request = session.begin_m2_request(request_id)
    primary, secondary = _category_for_input(session)
    referenced_sources = {
        ref.get("source_id")
        for row in [*session.requirements, *session.gaps]
        for ref in row.get("source_refs", [])
    }
    payload = {
        "schema_version": "m2.v0.1",
        "request_id": request_id,
        "task_id": session.task_id,
        "source_requirements_version": session.requirement_version,
        "confirmed_requirements_version": session.confirmed_requirements_version,
        "control": {"current_date": current_date or date.today().isoformat()},
        "task": {"text": session.task_text},
        "category": {
            "primary": primary,
            "secondary": secondary,
            "config_version": CATEGORY_CONFIG["version"],
            "applicable_fields": list(
                dict.fromkeys(
                    [
                        *CATEGORY_CONFIG["common_fields"],
                        *CATEGORY_CONFIG["category_fields"].get(primary, []),
                        *[
                            field
                            for category in secondary
                            for field in CATEGORY_CONFIG["category_fields"].get(category, [])
                        ],
                    ]
                )
            ),
        },
        "requirements": [
            {
                key: (
                    _m2_strength(row.get(key))
                    if key == "strength"
                    else deepcopy(row.get(key))
                )
                for key in (
                    "item_id",
                    "field",
                    "text",
                    "kind",
                    "strength",
                    "scope",
                    "source_refs",
                    "depends_on",
                )
            }
            for row in session.requirements
        ],
        "unresolved_items": [
            {
                "unresolved_id": row["gap_id"],
                "field": row["field"],
                "scope": row["scope"],
                "description": (
                    "用户已选择先做草稿，这项含义仍未确定：" + row["description"]
                    + "。只整理不依赖该信息的结构与步骤；相关具体内容等用户补充后完善，不得猜测填满。"
                    if row.get("importance") == "blocking_direction" else row["description"]
                ),
                # v0.1 already means permission to defer in this plan request.
                # Keep original directional importance in the session/source snapshot.
                "importance": "can_defer",
                "can_defer": True,
                "source_refs": deepcopy(row.get("source_refs", [])),
                "depends_on": deepcopy(row.get("depends_on", [])),
            }
            for row in session.plan_unresolved_items()
        ],
        "relevant_materials": [
            deepcopy(row) for row in session.sources if row.get("source_id") in referenced_sources
        ],
        "plan_context": {
            "current_plan_id": session.plan.get("plan_id"),
            "current_plan_version": int(session.plan.get("plan_version", 0)),
        },
    }
    try:
        _schema_error(payload, M2Assets.load().input_schema, "M2输入")
    except Exception:
        session.pending_requests.pop(request_id, None)
        raise
    return payload


def _unique_ids(rows: list[dict[str, Any]], key: str, label: str) -> set[str]:
    values = [row[key] for row in rows]
    if len(values) != len(set(values)):
        raise M2ValidationError(f"{label}包含重复编号。")
    return set(values)


def _check_subset(values: list[str], allowed: set[str], label: str) -> None:
    invalid = set(values) - allowed
    if invalid:
        raise M2ValidationError(f"{label}引用了不存在的编号：{', '.join(sorted(invalid))}")


def _check_acyclic(rows: list[dict[str, Any]], id_key: str, deps_key: str, label: str) -> None:
    graph = {row[id_key]: set(row.get(deps_key, [])) for row in rows}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise M2ValidationError(f"{label}存在循环依赖。")
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph[node]:
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def validate_plan_content(plan: dict[str, Any], payload: dict[str, Any]) -> None:
    requirement_ids = {row["item_id"] for row in payload["requirements"]}
    gap_ids = {row["unresolved_id"] for row in payload["unresolved_items"]}
    coverage = plan["requirement_coverage"]
    coverage_ids = [row["requirement_id"] for row in coverage]
    if len(coverage_ids) != len(set(coverage_ids)) or set(coverage_ids) != requirement_ids:
        raise M2ValidationError("需求覆盖必须逐项且仅一次承接全部正式需求。")

    steps = plan["steps"]
    deliverables = plan["deliverables"]
    criteria = plan["completion_criteria"]
    key_work = plan["key_work"]
    step_ids = _unique_ids(steps, "step_id", "方案步骤")
    deliverable_ids = _unique_ids(deliverables, "deliverable_id", "交付物")
    criterion_ids = _unique_ids(criteria, "criterion_id", "完成标准")
    key_work_ids = _unique_ids(key_work, "key_work_id", "关键工作")
    _unique_ids(plan["unresolved_items"], "unresolved_id", "未决事项")
    _unique_ids(plan["suggestions"], "suggestion_id", "系统建议")

    orders = [row["order"] for row in steps]
    if len(orders) != len(set(orders)):
        raise M2ValidationError("方案步骤顺序号不能重复。")

    for row in coverage:
        _check_subset(row["step_ids"], step_ids, "需求覆盖的步骤")
        _check_subset(row["deliverable_ids"], deliverable_ids, "需求覆盖的交付物")
        _check_subset(row["criterion_ids"], criterion_ids, "需求覆盖的完成标准")
    for row in steps:
        _check_subset(row["depends_on_step_ids"], step_ids, "步骤依赖")
        _check_subset(row["requirement_ids"], requirement_ids, "步骤需求")
        if row["step_id"] in row["depends_on_step_ids"]:
            raise M2ValidationError("步骤不能依赖自身。")
    for row in deliverables:
        _check_subset(row["step_ids"], step_ids, "交付物步骤")
        _check_subset(row["requirement_ids"], requirement_ids, "交付物需求")
    for row in criteria:
        _check_subset(row["requirement_ids"], requirement_ids, "完成标准需求")
    for row in key_work:
        _check_subset(row["step_ids"], step_ids, "关键工作步骤")
        _check_subset(row["requirement_ids"], requirement_ids, "关键工作需求")
        _check_subset(row["depends_on_key_work_ids"], key_work_ids, "关键工作依赖")
        if row["key_work_id"] in row["depends_on_key_work_ids"]:
            raise M2ValidationError("关键工作不能依赖自身。")
    _check_acyclic(steps, "step_id", "depends_on_step_ids", "方案步骤")
    _check_acyclic(key_work, "key_work_id", "depends_on_key_work_ids", "关键工作")

    returned_gap_ids = [row["source_gap_id"] for row in plan["unresolved_items"]]
    if len(returned_gap_ids) != len(set(returned_gap_ids)) or set(returned_gap_ids) != gap_ids:
        raise M2ValidationError("方案必须逐项保留输入中的全部可延后未知。")
    for row in plan["suggestions"]:
        if row["kind"] in {"scope_change", "cost_or_permission"} and not row[
            "requires_user_confirmation"
        ]:
            raise M2ValidationError("新增范围、成本或权限建议必须等待用户确认。")


def validate_plan_confirmable(plan: dict[str, Any]) -> None:
    placeholders = {"待补充", "待完善", "待定", "暂无", "todo", "tbd", "n/a"}

    def meaningful(value: Any) -> bool:
        return isinstance(value, str) and value.strip() and value.strip().casefold() not in placeholders

    for step in plan.get("steps", []):
        missing = []
        if not meaningful(step.get("title")):
            missing.append("标题")
        if not meaningful(step.get("purpose")):
            missing.append("目的")
        for key, label in (
            ("actions", "行动"),
            ("outputs", "输出"),
            ("completion_criteria", "完成标准"),
        ):
            values = step.get(key, [])
            if not isinstance(values, list) or not any(meaningful(value) for value in values):
                missing.append(label)
        if missing:
            raise M2ValidationError(
                f"步骤 {step.get('step_id', '未知')} 缺少可执行的{'、'.join(missing)}。"
            )

    for row in plan.get("key_work", []):
        missing = []
        if not meaningful(row.get("title")):
            missing.append("标题")
        if not meaningful(row.get("goal")):
            missing.append("目标")
        for key, label in (("inputs", "输入"), ("outputs", "输出"), ("checkpoints", "检查点")):
            values = row.get(key, [])
            if not isinstance(values, list) or not any(meaningful(value) for value in values):
                missing.append(label)
        if not row.get("step_ids"):
            missing.append("关联步骤")
        if missing:
            raise M2ValidationError(
                f"关键工作 {row.get('key_work_id', '未知')} 缺少{'、'.join(missing)}。"
            )


def parse_m2_response(
    raw: str,
    payload: dict[str, Any],
    output_schema: dict[str, Any],
) -> dict[str, Any]:
    parsed = _strict_json_loads(raw)
    _schema_error(parsed, output_schema, "M2输出")
    for key in ("request_id", "task_id", "source_requirements_version"):
        if parsed[key] != payload[key]:
            raise M2ValidationError(f"模型返回的{key}与请求不一致。")
    if parsed["status"] == "ok":
        if parsed["plan"] is None or parsed["error"] is not None:
            raise M2ValidationError("正常分支必须只包含方案。")
        validate_plan_content(parsed["plan"], payload)
    else:
        if parsed["plan"] is not None or parsed["error"] is None:
            raise M2ValidationError("错误分支必须只包含结构化错误。")
        allowed = {
            *[row["item_id"] for row in payload["requirements"]],
            *[row["unresolved_id"] for row in payload["unresolved_items"]],
        }
        _check_subset(parsed["error"]["related_input_ids"], allowed, "结构化错误")
    return parsed


def apply_m2_response(
    session: SessionState,
    payload: dict[str, Any],
    parsed: dict[str, Any],
    *,
    prompt_version: str = "M2_system_v0.2",
    contract_version: str = "m2.v0.1",
) -> None:
    if parsed["status"] != "ok":
        session.pending_requests.pop(payload["request_id"], None)
        raise SessionStateError(f"模型无法形成方案：{parsed['error']['message']}")
    # Revalidate before the one state mutation, so malformed callers cannot partially write a plan.
    validate_plan_content(parsed["plan"], payload)
    session.stage_m2_result(
        payload["request_id"],
        payload["source_requirements_version"],
        parsed["plan"],
        prompt_version=prompt_version,
        contract_version=contract_version,
    )
