from __future__ import annotations

import json
import logging
from copy import deepcopy
from .clarification import plan_unknown_description
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .categories import CATEGORY_CONFIG
from .paths import m2_asset_dir
from .session import SessionState, SessionStateError


class M2ValidationError(ValueError):
    def __init__(self, message: str, *, stage: str = "semantic"):
        super().__init__(message)
        self.stage = stage


@dataclass(frozen=True)
class M2Assets:
    system_prompt: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    prompt_version: str = "M2_system_v0.6"
    contract_version: str = "m2.v0.1"

    @classmethod
    def load(cls, directory: str | Path | None = None) -> "M2Assets":
        root = Path(directory) if directory else m2_asset_dir()
        return cls(
            system_prompt=(root / "M2_system_v0.6.txt").read_text(encoding="utf-8-sig"),
            input_schema=json.loads(
                (root / "M2_input_v0.2.schema.json").read_text(encoding="utf-8-sig")
            ),
            output_schema=json.loads(
                (root / "M2_output_v0.2.schema.json").read_text(encoding="utf-8-sig")
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
        raise M2ValidationError(f"{label}不符合契约（{path}）：{errors[0].message}", stage="schema")


def _strict_json_loads(raw: str) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise M2ValidationError(f"模型JSON包含重复键：{key}", stage="json")
            result[key] = value
        return result

    def invalid_constant(value: str) -> Any:
        raise M2ValidationError(f"模型JSON包含非法数值：{value}", stage="json")

    try:
        parsed = json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid_constant)
    except M2ValidationError:
        raise
    except json.JSONDecodeError as exc:
        raise M2ValidationError(f"模型未返回有效JSON：第{exc.lineno}行第{exc.colno}列", stage="json") from None
    if not isinstance(parsed, dict):
        raise M2ValidationError("模型JSON根节点必须是对象。", stage="json")
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
        for row in [*session.requirements, *session.active_gaps()]
        for ref in row.get("source_refs", [])
    }
    history = [row for row in session.question_history if not row.get("superseded_by_answer_id")]
    referenced_sources.update(row.get("answer_source_id") for row in history if row.get("answer_source_id"))
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
                "description": plan_unknown_description(row),
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
        "interview_context": [
            {"question_id": row["question_id"], "field": row["field"], "scope": row["scope"],
             "question": row["text"], "disposition": row["disposition"],
             "answer_source_id": row.get("answer_source_id"), "assessment_status": row.get("assessment_status", "legacy_unverified")}
            for row in history
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


def merge_plan_unknowns(
    rows: list[dict[str, Any]],
    payload: dict[str, Any],
    *,
    report: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Conserve source unknowns; normalize model suggestions without inventing facts.

    Only call at the model ingestion boundary or on a delivery copy. Saved
    plans are validated, not silently rewritten after confirmation.
    """
    events = report if report is not None else []
    gap_ids = {row["unresolved_id"] for row in payload["unresolved_items"]}
    requirement_ids = {row["item_id"] for row in payload["requirements"]}
    reserved = {row["unresolved_id"] for row in rows}
    used: set[str] = set()
    fingerprints: set[str] = set()
    merged: list[dict[str, Any]] = []

    def next_id() -> str:
        index = 1
        while f"u-recovered-{index}" in reserved | used:
            index += 1
        return f"u-recovered-{index}"

    for original in rows:
        row = deepcopy(original)
        source = row["source_gap_id"]
        related = list(dict.fromkeys(row.get("related_requirement_ids", [])))
        if source is not None and source not in gap_ids:
            if source in requirement_ids:
                related = list(dict.fromkeys([*related, source]))
            row["source_gap_id"] = None
            events.append({"action": "classify_new_unknown", "unresolved_id": row["unresolved_id"],
                           "original_source_gap_id": source})
        valid_related = [value for value in related if value in requirement_ids]
        if valid_related != related:
            events.append({"action": "remove_unverified_requirement_refs", "unresolved_id": row["unresolved_id"],
                           "removed_ids": [value for value in related if value not in requirement_ids]})
        if valid_related or "related_requirement_ids" in row:
            row["related_requirement_ids"] = valid_related
        fingerprint = json.dumps({key: value for key, value in row.items() if key != "unresolved_id"},
                                 sort_keys=True, ensure_ascii=False)
        if fingerprint in fingerprints:
            events.append({"action": "merge_exact_duplicate", "unresolved_id": row["unresolved_id"]})
            continue
        fingerprints.add(fingerprint)
        if row["unresolved_id"] in used:
            replacement = next_id()
            events.append({"action": "assign_unique_id", "original_id": row["unresolved_id"], "new_id": replacement})
            row["unresolved_id"] = replacement
        used.add(row["unresolved_id"])
        merged.append(row)

    covered = {row["source_gap_id"] for row in merged}
    for source in payload["unresolved_items"]:
        gap_id = source["unresolved_id"]
        if gap_id in covered:
            continue
        identifier = next_id()
        used.add(identifier)
        merged.append({
            "unresolved_id": identifier, "source_gap_id": gap_id,
            "description": source["description"],
            "impact": "该事项仍未确定，依赖它的具体内容需补充后再落实。",
            "continuable_work": "先完成不依赖该信息的部分；使用最终提示时继续向用户确认，不自行填入答案。",
            "confirm_by": "开始依赖该信息的工作前",
        })
        events.append({"action": "restore_source_unknown", "source_gap_id": gap_id, "unresolved_id": identifier})
    return merged


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

    returned_gap_ids = {row["source_gap_id"] for row in plan["unresolved_items"] if row["source_gap_id"] is not None}
    if not gap_ids.issubset(returned_gap_ids):
        raise M2ValidationError("方案遗漏了来源快照中的未决事项。")
    _check_subset(list(returned_gap_ids), gap_ids, "未决事项来源")
    for row in plan["unresolved_items"]:
        _check_subset(row.get("related_requirement_ids", []), requirement_ids, "未决事项关联需求")
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


def _normalize_model_plan(plan: dict[str, Any], payload: dict[str, Any], events: list[dict[str, Any]]) -> None:
    from .model_output import extra_notes
    before = deepcopy(plan)
    collections = (("steps", "step_id"), ("deliverables", "deliverable_id"),
                   ("completion_criteria", "criterion_id"), ("key_work", "key_work_id"),
                   ("suggestions", "suggestion_id"))
    for key, id_key in collections:
        seen: set[str] = set()
        reserved = {row[id_key] for row in plan[key]}
        for index, row in enumerate(plan[key]):
            if row[id_key] in seen:
                replacement = f"{id_key}-recovered-{index + 1}"
                while replacement in reserved:
                    replacement += "-new"
                row[id_key] = replacement
                reserved.add(replacement)
            seen.add(row[id_key])
    requirements = {row["item_id"]: row for row in payload["requirements"]}
    steps = {row["step_id"] for row in plan["steps"]}
    outputs = {row["deliverable_id"] for row in plan["deliverables"]}
    criteria = {row["criterion_id"] for row in plan["completion_criteria"]}
    orders = [row["order"] for row in plan["steps"]]
    for index, row in enumerate(plan["steps"]):
        if len(orders) != len(set(orders)):
            row["order"] = index + 1
        row["depends_on_step_ids"] = [value for value in row["depends_on_step_ids"] if value in steps and value != row["step_id"]]
        for key in ("actions", "outputs", "completion_criteria"):
            if not row[key]:
                row[key] = [f"{row['title']}的{key}尚待细化，请结合当前需求向用户确认。"]
    work_ids = {row["key_work_id"] for row in plan["key_work"]}
    for row in plan["key_work"]:
        row["depends_on_key_work_ids"] = [value for value in row["depends_on_key_work_ids"] if value in work_ids and value != row["key_work_id"]]
        row["step_ids"] = [value for value in row["step_ids"] if value in steps] or [plan["steps"][0]["step_id"]]
        for key in ("inputs", "outputs", "checkpoints"):
            if not row[key]:
                row[key] = [f"{row['title']}的{key}尚待核对，先按已确认目标展开。"]
    for key, id_key, dep_key in (("steps", "step_id", "depends_on_step_ids"), ("key_work", "key_work_id", "depends_on_key_work_ids")):
        try:
            _check_acyclic(plan[key], id_key, dep_key, key)
        except M2ValidationError:
            prior: set[str] = set()
            for row in plan[key]:
                row[dep_key] = [value for value in row[dep_key] if value in prior]
                prior.add(row[id_key])
    for key in ("steps", "deliverables", "completion_criteria", "key_work"):
        for row in plan[key]:
            row["requirement_ids"] = [value for value in row["requirement_ids"] if value in requirements]
            if key == "deliverables":
                row["step_ids"] = [value for value in row["step_ids"] if value in steps]
    coverage = {}
    for row in plan["requirement_coverage"]:
        if row["requirement_id"] not in requirements or row["requirement_id"] in coverage:
            continue
        for key, allowed in (("step_ids", steps), ("deliverable_ids", outputs), ("criterion_ids", criteria)):
            row[key] = [value for value in row[key] if value in allowed]
        coverage[row["requirement_id"]] = row
    for key, requirement in requirements.items():
        if key not in coverage:
            coverage[key] = {"requirement_id": key, "summary": requirement["text"] + "（具体安排请下游 AI 核对补充）",
                             "step_ids": [], "deliverable_ids": [], "criterion_ids": []}
    plan["requirement_coverage"] = list(coverage.values())
    for row in plan["suggestions"]:
        if row["kind"] in {"scope_change", "cost_or_permission"}:
            row["requires_user_confirmation"] = True
    if plan != before:
        events.append({"action": "repair_plan_links", "value": before})
    notes = extra_notes(events)
    if plan != before:
        notes.append("模型方案的编号、覆盖或步骤细节存在不一致，已按当前需求整理；原安排与细节仍需下游 AI 核对，不代表已经完成验证。原始关联记录：" + json.dumps(
            {key: before[key] for key in ("requirement_coverage", "steps", "key_work") if before[key] != plan[key]}, ensure_ascii=False))
    for index, note in enumerate(notes):
        identifier = f"u-format-{index + 1}"
        while any(row["unresolved_id"] == identifier for row in plan["unresolved_items"]):
            identifier += "-new"
        plan["unresolved_items"].append({"unresolved_id": identifier, "source_gap_id": None,
            "description": note, "impact": "可能影响具体执行方式。", "continuable_work": "先按已确认目标开展可确定的部分。",
            "confirm_by": "执行相关工作前与用户核对"})


def _prepare_plan_shape(plan: dict[str, Any], events: list[dict[str, Any]]) -> None:
    """Fill descriptive omissions with explicit unknowns, never factual guesses."""
    if isinstance(plan.get("goal"), dict):
        for key, label in (("summary", "目标"), ("audience", "受众"), ("scope", "范围")):
            if not plan["goal"].get(key):
                plan["goal"][key] = f"{label}尚未明确，请结合用户原始任务核对。"
                events.append({"action": "unknown_description", "field": key})
    for collection, id_key, arrays, texts in (
        ("steps", "step_id", ("inputs", "actions", "outputs", "completion_criteria", "depends_on_step_ids", "requirement_ids"), ("title", "purpose")),
        ("deliverables", "deliverable_id", ("step_ids", "requirement_ids"), ("name", "description")),
        ("completion_criteria", "criterion_id", ("requirement_ids",), ("text",)),
        ("key_work", "key_work_id", ("step_ids", "inputs", "outputs", "requirement_ids", "depends_on_key_work_ids", "checkpoints"), ("title", "goal")),
        ("requirement_coverage", "requirement_id", ("step_ids", "deliverable_ids", "criterion_ids"), ("summary",)),
    ):
        for index, row in enumerate(plan.get(collection, []) or []):
            if not isinstance(row, dict):
                continue
            if not row.get(id_key) and id_key != "requirement_id":
                row[id_key] = f"{id_key}-generated-{index + 1}"
                events.append({"action": "assign_missing_id", "collection": collection})
            for key in arrays:
                if key not in row:
                    row[key] = []
                    events.append({"action": "empty_collection", "field": f"{collection}.{key}"})
            for key in texts:
                if not row.get(key):
                    row[key] = f"{key}尚待细化，请结合当前目标与用户核对。"
                    events.append({"action": "unknown_description", "field": f"{collection}.{key}"})
            if collection == "steps" and not isinstance(row.get("order"), int):
                row["order"] = index + 1
                events.append({"action": "assign_step_order"})


def parse_m2_response(
    raw: str,
    payload: dict[str, Any],
    output_schema: dict[str, Any],
    *,
    normalization_report: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from .model_output import json_text, normalize_shape, log_repairs
    events = normalization_report if normalization_report is not None else []
    parsed = normalize_shape(_strict_json_loads(json_text(raw)), output_schema, events)
    if parsed.get("status") == "ok" and isinstance(parsed.get("plan"), dict):
        _prepare_plan_shape(parsed["plan"], events)
    _schema_error(parsed, output_schema, "M2输出")
    for key in ("request_id", "task_id", "source_requirements_version"):
        if parsed[key] != payload[key]:
            raise M2ValidationError(f"模型返回的{key}与请求不一致。")
    if parsed["status"] == "ok":
        if parsed["plan"] is None or parsed["error"] is not None:
            raise M2ValidationError("正常分支必须只包含方案。")
        _normalize_model_plan(parsed["plan"], payload, events)
        parsed["plan"]["unresolved_items"] = merge_plan_unknowns(
            parsed["plan"]["unresolved_items"], payload, report=events
        )
        validate_plan_content(parsed["plan"], payload)
    else:
        if parsed["plan"] is not None or parsed["error"] is None:
            raise M2ValidationError("错误分支必须只包含结构化错误。")
        allowed = {
            *[row["item_id"] for row in payload["requirements"]],
            *[row["unresolved_id"] for row in payload["unresolved_items"]],
        }
        _check_subset(parsed["error"]["related_input_ids"], allowed, "结构化错误")
    log_repairs("M2", payload["request_id"], events)
    return parsed


def apply_m2_response(
    session: SessionState,
    payload: dict[str, Any],
    parsed: dict[str, Any],
    *,
    prompt_version: str = "M2_system_v0.3",
    contract_version: str = "m2.v0.1",
) -> None:
    if parsed["status"] != "ok":
        session.pending_requests.pop(payload["request_id"], None)
        raise SessionStateError(f"模型无法形成方案：{parsed['error']['message']}")
    # Revalidate before the one state mutation, so malformed callers cannot partially write a plan.
    validate_plan_content(parsed["plan"], payload)
    from .clarification import without_skipped_unknowns
    content = deepcopy(parsed["plan"])
    content["unresolved_items"] = without_skipped_unknowns(session, content.get("unresolved_items", []))
    removed = len(parsed["plan"].get("unresolved_items", [])) - len(content["unresolved_items"])
    if removed:
        logging.getLogger(__name__).info("Excluded skipped items from model plan; task=%s count=%s", session.task_id, removed)
    session.stage_m2_result(
        payload["request_id"],
        payload["source_requirements_version"],
        content,
        prompt_version=prompt_version,
        contract_version=contract_version,
    )
