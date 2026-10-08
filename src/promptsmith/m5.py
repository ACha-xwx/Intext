"""M5 local examples and feedback extraction.

M5 is deliberately a small, optional aid for expressing one hard-to-name
criterion.  It never writes a requirement directly; feedback is returned as a
pending candidate that the normal requirement confirmation path can review.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from jsonschema import Draft202012Validator

from .paths import m1_asset_dir
from .session import SessionState, SessionStateError, StaleResponseError


class M5ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class M5Assets:
    system_prompt: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    prompt_version: str = "M5_system_v0.2"
    contract_version: str = "m5.v0.1"

    @classmethod
    def load(cls, directory: str | Path | None = None) -> "M5Assets":
        root = Path(directory) if directory else m1_asset_dir()
        return cls(
            system_prompt=(root / "M5_system_v0.2.txt").read_text(encoding="utf-8-sig"),
            input_schema=json.loads((root / "M5_input_v0.1.schema.json").read_text(encoding="utf-8-sig")),
            output_schema=json.loads((root / "M5_output_v0.1.schema.json").read_text(encoding="utf-8-sig")),
        )


def _schema_error(value: dict[str, Any], schema: dict[str, Any], label: str) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        path = ".".join(str(part) for part in errors[0].path) or "$"
        raise M5ValidationError(f"{label}不符合契约（{path}）：{errors[0].message}")


def _strict_json_loads(raw: str) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise M5ValidationError(f"模型JSON包含重复键：{key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> Any:
        raise M5ValidationError(f"模型JSON包含非法数值：{value}")

    try:
        parsed = json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid_constant)
    except M5ValidationError:
        raise
    except json.JSONDecodeError as exc:
        raise M5ValidationError(f"模型未返回有效JSON：第{exc.lineno}行第{exc.colno}列") from None
    if not isinstance(parsed, dict):
        raise M5ValidationError("模型JSON根节点必须是对象。")
    return parsed


def _clean_text(value: Any, label: str, *, max_length: int = 600) -> str:
    if not isinstance(value, str) or not value.strip():
        raise M5ValidationError(f"{label}不能为空。")
    value = value.strip()
    if len(value) > max_length:
        raise M5ValidationError(f"{label}过长，不能超过{max_length}个字符。")
    return value


def _clean_string_list(value: Any, label: str, *, max_items: int = 12) -> list[str]:
    if not isinstance(value, list) or len(value) > max_items:
        raise M5ValidationError(f"{label}必须是不超过{max_items}项的字符串数组。")
    result = []
    for row in value:
        result.append(_clean_text(row, label, max_length=300))
    return list(dict.fromkeys(result))


def _dimension_matches(actual: str, expected: str, criterion_id: str | None) -> bool:
    if criterion_id and actual.casefold() == criterion_id.casefold():
        return True
    left, right = actual.casefold(), expected.casefold()
    if left == right or left in right or right in left:
        return True
    left_tokens = set(re.findall(r"[a-z0-9_]{3,}|[\u4e00-\u9fff]{2}", left))
    right_tokens = set(re.findall(r"[a-z0-9_]{3,}|[\u4e00-\u9fff]{2}", right))
    return bool(left_tokens & right_tokens)


def _obvious_constraint_conflict(option: str, hard_constraints: list[str]) -> bool:
    """Reject only explicit negative constraints with visible lexical overlap."""
    for constraint in hard_constraints:
        negative = re.search(r"(?:不要|不添加|不包含|不得|禁止|不能|不应)\s*([^，。；;,.]+)", constraint)
        if not negative:
            continue
        forbidden = negative.group(1).strip()
        if forbidden and forbidden in option:
            return True
    return False


# M5 examples are deliberately narrow, but an example can still smuggle a
# participation condition into otherwise harmless copy.  Keep this check
# conservative: it only inspects high-risk equipment, cost, and eligibility
# language, then requires the exact action/claim to be present in user-backed
# context.  General stylistic wording is left to the model and human review.
_M5_BOUNDARY_TERMS = (
    "手机",
    "相机",
    "器材",
    "装备",
    "设备",
    "工具",
    "材料",
    "证件",
    "身份证",
    "费用",
    "收费",
    "免费",
    "付费",
    "报名费",
    "门票",
    "基础",
    "经验",
    "资格",
    "专业能力",
)
_M5_BOUNDARY_GROUPS = (
    ("手机", "相机", "器材", "装备", "设备", "工具", "材料"),
    ("费用", "收费", "免费", "付费", "报名费", "门票"),
    ("基础", "经验", "资格", "专业能力"),
)
_M5_ACTION_RE = re.compile(
    r"(?P<verb>带上|携带|带着|自备|准备好)\s*"
    r"(?P<object>[^，。！？,.；;:：\s]{1,16}?)(?="
    r"即可|就能|参加|来|去|[，。！？,.；;:：\s]|$)"
)
_M5_NEGATED_CONDITION_RE = re.compile(
    r"(?P<verb>无需|不用|不需要)\s*(?:携带|带上|准备|具备|有)?\s*"
    r"(?P<object>[^，。！？,.；;:：\s]{1,16}?)(?="
    r"即可|就能|参加|来|去|[，。！？,.；;:：\s]|$)"
)
_M5_EXPLICIT_COST_RE = re.compile(r"免费|不收费|无需付费|不需要付费")


def _compact_text(value: Any) -> str:
    """Normalize only layout punctuation for conservative phrase matching."""
    return re.sub(r"\s+", "", str(value or "")).replace("：", ":")


def _m5_trusted_context(payload: Mapping[str, Any]) -> str:
    """Build text that is allowed to support facts in a generated example."""
    chunks: list[str] = []
    task = payload.get("task") or {}
    if isinstance(task, Mapping):
        chunks.append(str(task.get("text") or ""))
    criterion = payload.get("criterion") or {}
    if isinstance(criterion, Mapping):
        chunks.append(str(criterion.get("description") or ""))
    for row in payload.get("known_requirements", []) or []:
        if not isinstance(row, Mapping):
            continue
        chunks.append(str(row.get("text") or ""))
        for ref in row.get("source_refs", []) or []:
            if isinstance(ref, Mapping):
                chunks.append(str(ref.get("quote") or ""))
    for value in payload.get("hard_constraints", []) or []:
        chunks.append(str(value or ""))
    return _compact_text(" ".join(chunks))


def _m5_boundary_violations(
    options: list[str],
    payload: Mapping[str, Any],
    unsupported_assumptions: list[str],
) -> list[str]:
    """Find high-risk facts in options which have no user-backed wording.

    ``unsupported_assumptions`` can document a deliberately hypothetical
    phrase, but an explicit user boundary (for example, no equipment or fee
    requirements) still rejects that phrase.  This preserves transparency
    without allowing a model to turn a forbidden assumption into copy.
    """
    context = _m5_trusted_context(payload)
    hard_constraints = [str(value or "") for value in payload.get("hard_constraints", []) or []]
    forbidden_terms: set[str] = set()
    for constraint in hard_constraints:
        if not re.search(r"(?:不要|不添加|不得|禁止|不能|不应)", constraint):
            continue
        for group in _M5_BOUNDARY_GROUPS:
            if any(term in constraint for term in group):
                forbidden_terms.update(group)
    declared = _compact_text(" ".join(unsupported_assumptions))
    violations: list[str] = []

    def inspect(phrase: str, object_text: str) -> None:
        compact_phrase = _compact_text(phrase)
        compact_object = _compact_text(object_text)
        if not compact_object or not any(term in compact_object for term in _M5_BOUNDARY_TERMS):
            return
        if compact_phrase in context:
            return
        if any(term in compact_object for term in forbidden_terms):
            violations.append(phrase)
            return
        # A model may explicitly label a hypothetical assumption.  It remains
        # visible for review, but is not rejected solely for being hypothetical.
        if compact_object not in declared and compact_phrase not in declared:
            violations.append(phrase)

    for option in options:
        for match in _M5_ACTION_RE.finditer(option):
            inspect(match.group(0), match.group("object"))
        for match in _M5_NEGATED_CONDITION_RE.finditer(option):
            inspect(match.group(0), match.group("object"))
        for match in _M5_EXPLICIT_COST_RE.finditer(option):
            inspect(match.group(0), match.group(0))
    return list(dict.fromkeys(violations))


def _require_request_fields(payload: Mapping[str, Any]) -> None:
    if not isinstance(payload.get("request_id"), str) or not payload["request_id"].strip():
        raise M5ValidationError("M5请求缺少request_id。")
    if not isinstance(payload.get("task_id"), str) or not payload["task_id"].strip():
        raise M5ValidationError("M5请求缺少task_id。")
    if not isinstance(payload.get("base_version"), int) or payload["base_version"] < 0:
        raise M5ValidationError("M5请求的base_version无效。")


def build_m5_input(
    session: SessionState,
    request_id: str,
    *,
    criterion_id: str | None = None,
    criterion_description: str,
    max_chars: int = 240,
) -> dict[str, Any]:
    """Snapshot current context and register a guarded M5 request."""
    description = _clean_text(criterion_description, "评价标准", max_length=300)
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or not 40 <= max_chars <= 600:
        raise M5ValidationError("示例长度上限必须是40到600之间的整数。")
    if not session.task_text.strip():
        raise M5ValidationError("任务为空，不能生成示例。")
    if criterion_id is not None:
        criterion_id = _clean_text(criterion_id, "criterion_id", max_length=100)
    snapshot = session.begin_m5_request(
        request_id,
        criterion_id=criterion_id,
        criterion_description=description,
        max_chars=max_chars,
    )
    requirements = deepcopy(session.requirements)
    hard_constraints = [
        str(row.get("text", ""))
        for row in requirements
        if row.get("strength") == "hard" and str(row.get("text", "")).strip()
    ]
    payload = {
        "schema_version": "m5.v0.1",
        "request_id": request_id,
        "task_id": session.task_id,
        "base_version": snapshot["base_version"],
        "task": {
            "text": session.task_text,
            "category": session.selected_category,
        },
        "criterion": {
            "criterion_id": criterion_id,
            "description": description,
        },
        "known_requirements": requirements,
        "unknowns": deepcopy(session.gaps),
        "hard_constraints": hard_constraints,
        "max_chars": max_chars,
    }
    try:
        _schema_error(payload, M5Assets.load().input_schema, "M5输入")
    except Exception:
        session.pending_requests.pop(request_id, None)
        raise
    return payload


def parse_m5_response(
    raw: str,
    payload: dict[str, Any],
    output_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _require_request_fields(payload)
    _schema_error(payload, M5Assets.load().input_schema, "M5输入")
    parsed = _strict_json_loads(raw)
    schema = output_schema or M5Assets.load().output_schema
    _schema_error(parsed, schema, "M5输出")
    for key in ("request_id", "task_id", "base_version"):
        if parsed.get(key) != payload.get(key):
            raise M5ValidationError(f"模型返回的{key}与请求不一致。")
    if parsed["status"] == "error":
        if parsed.get("example") is not None:
            raise M5ValidationError("M5错误分支不能包含示例。")
        return parsed
    example = parsed.get("example")
    if not isinstance(example, dict):
        raise M5ValidationError("M5成功分支缺少example。")
    criterion = payload["criterion"]
    dimension = _clean_text(example.get("dimension"), "示例维度", max_length=180)
    if not _dimension_matches(dimension, criterion["description"], criterion.get("criterion_id")):
        raise M5ValidationError("示例维度与请求的评价标准不一致。")
    shared = _clean_string_list(example.get("shared_assumptions", []), "共同前提")
    unsupported = _clean_string_list(example.get("unsupported_assumptions", []), "未支持假设")
    option_a = _clean_text(example.get("option_a"), "选项A", max_length=payload["max_chars"])
    option_b = _clean_text(example.get("option_b"), "选项B", max_length=payload["max_chars"])
    if option_a == option_b:
        raise M5ValidationError("选项A和选项B必须存在可比较差异。")
    difference = _clean_text(example.get("difference_summary"), "差异说明", max_length=300)
    hard_constraints = payload.get("hard_constraints", [])
    if _obvious_constraint_conflict(option_a, hard_constraints) or _obvious_constraint_conflict(option_b, hard_constraints):
        raise M5ValidationError("示例与用户明确的硬约束存在明显冲突。")
    boundary_violations = _m5_boundary_violations(
        [option_a, option_b], payload, unsupported
    )
    if boundary_violations:
        examples = "、".join(boundary_violations[:3])
        raise M5ValidationError(
            f"示例包含未经用户提供或违反边界的事实声明：{examples}。"
        )
    normalized = deepcopy(parsed)
    normalized["example"] = {
        "dimension": dimension,
        "shared_assumptions": shared,
        "option_a": option_a,
        "option_b": option_b,
        "difference_summary": difference,
        "unsupported_assumptions": unsupported,
    }
    return normalized


def apply_m5_response(session: SessionState, payload: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any] | None:
    """Apply only a current, validated response; return the saved example."""
    request_id = payload.get("request_id")
    request = session.pending_requests.get(request_id)
    if not request or request.get("purpose") != "m5":
        raise StaleResponseError("M5请求不存在、已处理或已被状态变化作废。")
    if request.get("task_id") != session.task_id or request.get("task_text") != session.task_text:
        session.pending_requests.pop(request_id, None)
        raise StaleResponseError("等待期间会话或任务已变化，已拒绝旧示例。")
    if request.get("base_version") != session.requirement_version or payload.get("base_version") != session.requirement_version:
        session.pending_requests.pop(request_id, None)
        raise StaleResponseError("示例基于旧需求版本，已拒绝接收。")
    session.pending_requests.pop(request_id, None)
    if parsed.get("status") == "error":
        session.m5_state.update(
            {"status": "error", "request_id": request_id, "last_error": parsed.get("error")}
        )
        session.touch()
        return None
    example = deepcopy(parsed["example"])
    row = {
        "example_id": f"m5-{uuid4().hex}",
        "request_id": request_id,
        "task_id": session.task_id,
        "base_version": session.requirement_version,
        "criterion_id": request.get("criterion_id"),
        "criterion_description": request.get("criterion_description"),
        "example": example,
        "status": "ready",
        "created_at": session.updated_at,
    }
    session.m5_examples.append(row)
    session.m5_state.update(
        {
            "status": "ready",
            "request_id": request_id,
            "example_id": row["example_id"],
            "base_version": session.requirement_version,
            "criterion_id": request.get("criterion_id"),
            "criterion_description": request.get("criterion_description"),
            "last_error": None,
        }
    )
    session.touch()
    return deepcopy(row)


def feedback_candidate(example_row: Mapping[str, Any], disposition: str, feedback: str = "") -> dict[str, Any] | None:
    """Create a narrow, reviewable candidate without accepting example details."""
    if disposition not in {"a", "b", "option_a", "option_b", "neither", "skipped"}:
        raise M5ValidationError("M5反馈选项无效。")
    if disposition in {"neither", "skipped"}:
        return None
    example = example_row.get("example") or {}
    dimension = str(example.get("dimension") or example_row.get("criterion_description") or "目标维度").strip()
    normalized = "a" if disposition in {"a", "option_a"} else "b"
    clean_feedback = feedback.strip()
    if clean_feedback:
        text = f"在“{dimension}”方面：{clean_feedback}"
    else:
        text = f"在“{dimension}”方面，更接近示例{normalized.upper()}的表达倾向（具体程度待确认）。"
    return {
        "candidate_id": f"m5-candidate-{uuid4().hex}",
        "operation": "new",
        "target_item_id": None,
        "field": "style",
        "text": text,
        "kind": "pending_interpretation",
        "strength": "preference",
        "scope": "当前任务",
        "source": "m5_feedback",
        "source_example_id": example_row.get("example_id"),
        "source_refs": [],
        "depends_on": [],
        "reason": "来自用户对M5局部示例的反馈，需在需求卡中复核后才生效。",
        "confirmation": "pending",
    }


def record_m5_feedback(
    session: SessionState,
    example_id: str,
    disposition: str,
    feedback: str = "",
) -> dict[str, Any]:
    example = next((row for row in session.m5_examples if row.get("example_id") == example_id), None)
    if example is None:
        raise SessionStateError("找不到可反馈的M5示例。")
    if (
        example.get("task_id") != session.task_id
        or example.get("base_version") != session.requirement_version
    ):
        session.m5_state["status"] = "stale"
        session.m5_state["candidate_pending"] = False
        raise SessionStateError("该M5示例基于旧任务或旧需求版本，请重新生成示例。")
    clean_feedback = feedback.strip()
    if len(clean_feedback) > 600:
        raise SessionStateError("M5反馈不能超过600个字符。")
    candidate = feedback_candidate(example, disposition, clean_feedback)
    row = {
        "feedback_id": f"m5-feedback-{uuid4().hex}",
        "example_id": example_id,
        "task_id": session.task_id,
        "base_version": session.requirement_version,
        "disposition": disposition,
        "feedback_text": clean_feedback,
        "candidate": candidate,
        "source": "m5_feedback",
        "created_at": session.updated_at,
    }
    session.m5_feedback.append(row)
    session.m5_state.update(
        {
            "status": "feedback_recorded",
            "example_id": example_id,
            "feedback_id": row["feedback_id"],
            "candidate_pending": candidate is not None,
        }
    )
    session.touch()
    return deepcopy(row)
