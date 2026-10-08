from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .session import SessionState, SessionStateError


class DeliveryValidationError(SessionStateError):
    """Raised when a final delivery operation would bypass an upstream gate."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _live_requirement_ids(session: SessionState) -> set[str]:
    return {str(row.get("item_id")) for row in session.requirements if row.get("item_id")}


def _validate_plan_shape(plan: dict[str, Any]) -> None:
    required = {"goal", "steps", "deliverables", "completion_criteria", "key_work"}
    missing = required - set(plan)
    if missing:
        raise DeliveryValidationError(f"当前方案缺少必要栏目：{'、'.join(sorted(missing))}")
    if not isinstance(plan.get("steps"), list) or not plan["steps"]:
        raise DeliveryValidationError("当前方案没有可执行步骤。")
    if not isinstance(plan.get("deliverables"), list) or not plan["deliverables"]:
        raise DeliveryValidationError("当前方案没有交付物。")
    for step in plan["steps"]:
        if not isinstance(step, dict) or not step.get("step_id"):
            raise DeliveryValidationError("方案包含无效步骤。")
        for field in ("title", "purpose", "actions", "outputs", "completion_criteria"):
            value = step.get(field)
            if not value or (isinstance(value, list) and not any(str(item).strip() for item in value)):
                raise DeliveryValidationError(f"步骤 {step.get('step_id', '未知')} 缺少{field}。")
    step_ids = {row["step_id"] for row in plan["steps"]}
    for row in plan.get("key_work", []):
        if not isinstance(row, dict) or not row.get("key_work_id"):
            raise DeliveryValidationError("关键工作包含无效记录。")
        if not set(row.get("step_ids", [])) <= step_ids:
            raise DeliveryValidationError("关键工作引用了不存在的步骤。")


def validate_delivery_entry(session: SessionState, *, allow_unconfirmed_plan: bool = False) -> None:
    if session.confirmed_requirements_version != session.requirement_version:
        raise DeliveryValidationError("请先确认当前需求版本。")
    if session.open_conflicts:
        raise DeliveryValidationError("当前需求仍有冲突，不能生成或导出结果。")
    if session.pending_review_item_ids or any(row.get("confirmation") == "review_needed" for row in session.requirements):
        raise DeliveryValidationError("当前需求仍需复核，不能生成或导出结果。")
    if any(row.get("importance") == "blocking_direction" for row in session.gaps) and not session.current_draft_authorization():
        raise DeliveryValidationError("方向仍未确定，请补充说明或明确选择先做草稿。")
    plan = session.plan
    interim = allow_unconfirmed_plan and plan.get("status") == "draft"
    if interim:
        if not session.current_draft_authorization():
            raise DeliveryValidationError("先做草稿需要用户先了解并允许保留当前未知内容。")
        if session.skill_state.get("bindings"):
            raise DeliveryValidationError("选用 Skill 前仍需先核对方案。")
        try:
            session.validate_m2_entry()
            session.validate_plan()
        except SessionStateError as exc:
            raise DeliveryValidationError(str(exc)) from exc
    if plan.get("status") != "confirmed" and not interim:
        raise DeliveryValidationError("请先确认当前初始方案。")
    if plan.get("source_requirements_version") != session.requirement_version:
        raise DeliveryValidationError("初始方案来源已过期，请重新生成并确认。")
    if plan.get("confirmed_plan_version") != plan.get("plan_version") and not interim:
        raise DeliveryValidationError("初始方案确认版本与当前内容不一致。")
    if plan.get("pending_key_work_review_ids") and not interim:
        raise DeliveryValidationError("仍有关键工作需要复核。")
    if not isinstance(plan.get("content"), dict):
        raise DeliveryValidationError("当前没有完整的初始方案。")
    _validate_plan_shape(plan["content"])
    live_ids = _live_requirement_ids(session)
    if not live_ids:
        raise DeliveryValidationError("当前没有正式需求。")
    for row in plan["content"].get("requirement_coverage", []):
        if row.get("requirement_id") not in live_ids:
            raise DeliveryValidationError("方案需求覆盖包含已失效需求。")


def _baseline(session: SessionState, *, legacy: bool = False) -> dict[str, Any]:
    plan = deepcopy(session.plan["content"])
    # Reconstruct old baselines exactly when validating an already saved final.
    # New drafts always use the conservative union and explicit guidance.
    unknown = (
        deepcopy(plan.get("unresolved_items", []) or session.plan_unresolved_items())
        if legacy else session.plan_delivery_unknowns()
    )
    # M2 keeps the unresolved item contract intentionally small.  The source
    # snapshot still has the user's origin and wording, so carry that audit
    # context into the final baseline without changing the M2 plan schema.
    source_unknowns = session.plan.get("source_snapshot") or {}
    source_by_gap = {
        str(row.get("gap_id") or row.get("unresolved_id")): row
        for row in source_unknowns.get("unresolved_items", [])
        if isinstance(row, dict) and (row.get("gap_id") or row.get("unresolved_id"))
    }
    enriched_unknown: list[dict[str, Any]] = []
    for row in unknown:
        item = deepcopy(row)
        source_id = item.get("source_gap_id") or (item.get("unresolved_id") if legacy else "")
        source = source_by_gap.get(str(source_id or ""), {})
        if not legacy and item.get("source_gap_id") is None:
            item["origin"] = "m2_inferred"
        elif not legacy and source.get("description") and source["description"] != item.get("description"):
            item["source_description"] = source["description"]
        for key in ("origin", "source_refs", "field", "scope", "importance"):
            if key not in item and key in source:
                item[key] = deepcopy(source[key])
        enriched_unknown.append(item)
    baseline = {
        "task": session.task_text,
        "category": session.selected_category,
        "requirements": deepcopy(session.requirements),
        "plan": plan,
        "unknown": enriched_unknown,
    }
    if not legacy:
        baseline["unknown_handling"] = "ask_then_defer"
    authorization = session.current_draft_authorization()
    if authorization:
        baseline["draft_authorization"] = authorization
    return baseline


def _skill_contributions(session: SessionState, selected: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if selected is not None:
        return deepcopy(selected)
    if not session.skill_state.get("bindings"):
        return []
    previous = session.final_result.get("content")
    if not isinstance(previous, dict):
        return []
    live_ids = {row.get("binding_id") for row in session.skill_state.get("bindings", [])}
    retained: list[dict[str, Any]] = []
    for row in previous.get("skill_contributions", []):
        origins = list(dict.fromkeys([
            *row.get("origin_binding_ids", []),
            *([row["binding_id"]] if row.get("binding_id") else []),
        ]))
        surviving = [binding_id for binding_id in origins if binding_id in live_ids]
        if not surviving:
            continue
        item = deepcopy(row)
        item["origin_binding_ids"] = surviving
        if item.get("binding_id") not in live_ids:
            item.pop("binding_id", None)
        retained.append(item)
    return retained


def _remote_provenance(binding: dict[str, Any]) -> dict[str, Any] | None:
    """Return only provenance recorded by a remote candidate snapshot."""
    record = binding.get("record_snapshot")
    if not isinstance(record, dict) or record.get("origin") != "remote":
        return None
    verification = record.get("verification")
    verification = verification if isinstance(verification, dict) else {}
    return {
        "origin": "remote",
        "source_url": record.get("source_url", ""),
        "repository": record.get("repository", ""),
        "fixed_commit": record.get("fixed_commit", "unresolved"),
        "content_hash_kind": record.get("content_hash_kind", ""),
        "content_sha256": record.get("content_sha256", ""),
        "verification_status": verification.get("verification_status", "unknown"),
        "source_read": bool(verification.get("source_read", False)),
        "installed": bool(verification.get("installed", False)),
        "execution_tested": bool(verification.get("execution_tested", False)),
    }


def skill_reference_for_binding(binding: dict[str, Any]) -> dict[str, Any]:
    """Carry the selected Skill identity to the AI that will perform the task."""
    record = binding.get("record_snapshot") or {}
    verification = record.get("verification") or {}
    return {
        "binding_id": binding.get("binding_id", ""),
        "skill_id": binding.get("skill_id", ""),
        "name": record.get("name") or binding.get("skill_id", ""),
        "origin": record.get("origin", "local_catalog"),
        "source_url": record.get("source_url") or record.get("repository", ""),
        "local_path": record.get("local_snapshot_path", "") if record.get("origin") != "remote" else "",
        "key_work_id": binding.get("key_work_id", ""),
        "step_ids": list(binding.get("step_ids", [])),
        "source_read": bool(verification.get("source_read")),
    }


def _attach_skill_provenance(
    session: SessionState, contributions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Rebuild Skill references from current selections, never from model claims."""
    bindings = {
        str(row.get("binding_id")): row
        for row in session.skill_state.get("bindings", [])
        if row.get("binding_id")
    }
    enriched: list[dict[str, Any]] = []
    for contribution in contributions:
        item = deepcopy(contribution)
        origin_ids = list(item.get("origin_binding_ids", []))
        if item.get("binding_id") and item["binding_id"] not in origin_ids:
            origin_ids.append(item["binding_id"])
        # A shared contribution may survive cancellation of one of its Skills.
        # Always replace source fields so a cancelled source cannot linger.
        item.pop("provenance", None)
        item.pop("provenance_sources", None)
        item["skill_references"] = [
            skill_reference_for_binding(bindings[str(binding_id)])
            for binding_id in origin_ids if str(binding_id) in bindings
        ]
        sources = [
            source
            for binding_id in origin_ids
            for source in [_remote_provenance(bindings.get(str(binding_id), {}))]
            if source is not None
        ]
        if len(sources) == 1:
            item["provenance"] = sources[0]
        elif sources:
            item["provenance_sources"] = sources
        enriched.append(item)
    return enriched


def _pending_suggestions(plan: dict[str, Any], decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decision_by_id = {
        row.get("suggestion_id"): row.get("decision")
        for row in decisions
        if row.get("plan_id") == plan.get("plan_id")
        and row.get("plan_version") == plan.get("plan_version")
    }
    return [
        {
            "suggestion_id": row.get("suggestion_id"),
            "text": row.get("text", ""),
            "reason": row.get("reason", ""),
            "decision": decision_by_id.get(row.get("suggestion_id"), "pending"),
            "requires_user_confirmation": bool(row.get("requires_user_confirmation", False)),
            "kind": row.get("kind", "optional_improvement"),
        }
        for row in plan.get("suggestions", [])
        if isinstance(row, dict)
        and decision_by_id.get(row.get("suggestion_id")) != "accepted"
    ]


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _m4_change_for_review(result: dict[str, Any], review_id: str) -> dict[str, Any] | None:
    """Resolve an M4 review id to its current change record."""
    parts = review_id.split(":", 2)
    if len(parts) != 3 or parts[0] not in {"m4-change", "m4-fallback-required"}:
        return None
    _prefix, request_id, change_id = parts
    content = result.get("content") if isinstance(result.get("content"), dict) else {}
    for row in content.get("pending_changes", []):
        if not isinstance(row, dict) or row.get("change_id") != change_id:
            continue
        row_request_id = row.get("generation_request_id") or result.get("generation_request_id")
        if row_request_id == request_id:
            return row
    return None


def _review_id_is_blocking(result: dict[str, Any], review_id: str) -> bool:
    """M4 proposals are deferred; accepting a conflicting proposal is gated separately."""
    if review_id.startswith(("m4-change:", "m4-fallback-required:")):
        change = _m4_change_for_review(result, review_id)
        # Older sessions may carry review IDs for proposals that are still
        # pending. A known proposal is optional until the user accepts it.
        return change is None
    return True


def blocking_review_required_ids(session: SessionState) -> list[str]:
    result = session.final_result if isinstance(session.final_result, dict) else {}
    review_ids = result.get("review_required_ids", [])
    if not isinstance(review_ids, list):
        return []
    return [
        review_id
        for review_id in review_ids
        if isinstance(review_id, str) and _review_id_is_blocking(result, review_id)
    ]


def _display_list(value: Any, *, empty: str = "无") -> str:
    if isinstance(value, list):
        values = [str(item).strip() for item in value if str(item).strip()]
        return "；".join(values) if values else empty
    if value is None:
        return empty
    clean = str(value).strip()
    return clean or empty


def _requirement_kind_label(kind: Any) -> str:
    return {
        "user_fact": "用户事实",
        "user_decision": "用户决定",
        "system_suggestion": "系统建议",
        "pending_interpretation": "待确认理解",
    }.get(str(kind), "未标注类型")


def _strength_label(strength: Any) -> str:
    return {"hard": "硬约束", "preference": "偏好"}.get(str(strength), "未标注强度")


def _origin_label(origin: Any) -> str:
    return {
        "user_unsure": "用户表示不确定",
        "user_skipped": "用户跳过",
        "missing": "原始任务未提供",
        "ambiguous": "信息仍有歧义",
        "system_suggestion": "系统建议",
        "m2_inferred": "AI 规划时提出，待确认；不代表用户已作出决定",
    }.get(str(origin), "需求分析中的未决项")


def _suggestion_kind_label(kind: Any) -> str:
    return {
        "optional_improvement": "可选改进",
        "scope_change": "范围变化",
        "cost_or_permission": "成本或权限事项",
    }.get(str(kind), "未标注类型")


def _usable_actions(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        action.strip()
        for action in value
        if isinstance(action, str) and action.strip() and action.strip().casefold() not in {"无", "none", "n/a"}
    ]


def _current_basis(session: SessionState) -> dict[str, Any]:
    bindings = session.skill_state.get("bindings", [])
    return {
        "task_id": session.task_id,
        "requirement_version": session.requirement_version,
        "plan_id": session.plan.get("plan_id"),
        "plan_version": session.plan.get("plan_version"),
        "selection_revision": session.skill_state.get("revision", 0),
        "selected_record_hashes": [row.get("record_hash") for row in bindings if row.get("record_hash")],
        "delivery_revision": session.delivery_revision,
    }


def _validate_skill_bindings(session: SessionState) -> set[str]:
    state = session.skill_state
    bindings = state.get("bindings", [])
    if not bindings:
        return set()
    expected_plan_basis = {
        "task_id": session.task_id,
        "requirement_version": session.requirement_version,
        "plan_id": session.plan.get("plan_id"),
        "plan_version": session.plan.get("plan_version"),
    }
    if state.get("status") != "selected" or state.get("basis") != expected_plan_basis:
        raise DeliveryValidationError("所选 Agent Skill 来自旧任务或方案，请重新筛选并选用。")

    content = session.plan.get("content") or {}
    works = {row.get("key_work_id"): row for row in content.get("key_work", [])}
    live_ids: set[str] = set()
    valid_sources = {"user_reported", "catalog_evidence", "program_check", "remote_source_review"}
    for binding in bindings:
        binding_id = binding.get("binding_id")
        snapshot = binding.get("record_snapshot")
        work = works.get(binding.get("key_work_id"))
        if not binding_id or binding_id in live_ids or not isinstance(snapshot, dict) or work is None:
            raise DeliveryValidationError("当前 Skill 绑定缺少有效来源、关键工作或唯一编号。")
        if binding.get("usage_mode") != "method_adaptation" or not snapshot.get("method_adaptation_allowed"):
            raise DeliveryValidationError("当前绑定不支持已核验的方法适配。")
        if binding.get("skill_id") != snapshot.get("skill_id") or binding.get("record_hash") != snapshot.get("record_hash"):
            raise DeliveryValidationError("Skill 绑定与其来源快照不一致。")
        if not set(binding.get("step_ids", [])) <= set(work.get("step_ids", [])):
            raise DeliveryValidationError("Skill 绑定引用了该关键工作之外的方案步骤。")
        prerequisite_ids = {
            row.get("prerequisite_id")
            for row in snapshot.get("adaptation_prerequisites", [])
            if isinstance(row, dict) and row.get("prerequisite_id")
        }
        assessments = binding.get("precondition_assessments", [])
        if not isinstance(assessments, list):
            raise DeliveryValidationError("Skill 前提评估格式无效。")
        seen_assessments: set[str] = set()
        for assessment in assessments:
            prerequisite_id = assessment.get("prerequisite_id") if isinstance(assessment, dict) else None
            status = assessment.get("status", "unknown") if isinstance(assessment, dict) else None
            if prerequisite_id not in prerequisite_ids or prerequisite_id in seen_assessments:
                raise DeliveryValidationError("Skill 前提评估引用了未知或重复的前提。")
            if status not in {"satisfied", "unknown", "incompatible"}:
                raise DeliveryValidationError("Skill 前提评估状态无效。")
            source = assessment.get("source")
            if source not in valid_sources:
                raise DeliveryValidationError("Skill 前提评估来源无效。")
            if snapshot.get("origin") == "remote" and source == "catalog_evidence":
                raise DeliveryValidationError("远程 Skill 前提不能标记为本地目录证据。")
            if status == "incompatible":
                raise DeliveryValidationError("所选 Agent Skill 与当前环境或任务前提不兼容。")
            seen_assessments.add(prerequisite_id)
        live_ids.add(str(binding_id))
    return live_ids


def validate_current_final(
    session: SessionState,
    *,
    require_confirmed: bool = False,
    allowed_review_required_ids: set[str] | None = None,
) -> None:
    result = session.final_result
    expected_statuses = {"confirmed"} if require_confirmed else {"draft", "confirmed"}
    if result.get("status") not in expected_statuses:
        raise DeliveryValidationError("当前没有来源有效的最终结果。")
    interim = bool((result.get("content") or {}).get("plan_review_pending"))
    if interim and (require_confirmed or result.get("status") != "draft"):
        raise DeliveryValidationError("方案尚未核对，当前内容只能作为草稿查看和导出。")
    validate_delivery_entry(session, allow_unconfirmed_plan=interim)
    basis = result.get("basis")
    if not isinstance(basis, dict) or basis != _current_basis(session):
        raise DeliveryValidationError("最终结果来源版本已变化，请重新生成草稿。")
    content = result.get("content")
    baseline = content.get("baseline") if isinstance(content, dict) else None
    legacy = isinstance(baseline, dict) and "unknown_handling" not in baseline
    if not isinstance(baseline, dict) or baseline != _baseline(session, legacy=legacy):
        raise DeliveryValidationError("最终结果没有完整承接当前已确认基线。")
    bindings = _validate_skill_bindings(session)
    binding_by_id = {
        row["binding_id"]: row for row in session.skill_state.get("bindings", [])
    }
    unknown_prerequisites: dict[str, set[str]] = {}
    for binding_id, binding in binding_by_id.items():
        snapshot = binding.get("record_snapshot") or {}
        expected = {
            row.get("prerequisite_id")
            for row in snapshot.get("adaptation_prerequisites", [])
            if isinstance(row, dict) and row.get("prerequisite_id")
        }
        statuses = {
            row.get("prerequisite_id"): row.get("status", "unknown")
            for row in binding.get("precondition_assessments", [])
        }
        unknown_prerequisites[binding_id] = {
            prerequisite_id
            for prerequisite_id in expected
            if statuses.get(prerequisite_id, "unknown") == "unknown"
        }
    contributions = content.get("skill_contributions", [])
    contribution_bindings: set[str] = set()
    represented_unknowns: dict[str, set[str]] = {binding_id: set() for binding_id in bindings}
    for row in contributions:
        origins = set(row.get("origin_binding_ids", []))
        if row.get("binding_id"):
            origins.add(row["binding_id"])
        if not origins or not origins <= bindings:
            raise DeliveryValidationError("最终结果包含未选用或已过期的 Agent Skill 内容。")
        contribution_bindings.update(origins)
        inactive_changes = row.get("disabled_by_rejected_changes", [])
        inactive_review_ids = {
            f"m4-fallback-required:{item.get('generation_request_id')}:{item.get('change_id')}"
            for item in inactive_changes
            if isinstance(item, dict) and item.get("generation_request_id") and item.get("change_id")
        }
        actions_disabled = (
            not row.get("method_actions")
            and inactive_changes
            and not any(_review_id_is_blocking(result, review_id) for review_id in inactive_review_ids)
        )
        if (not row.get("method_actions") and not actions_disabled) or not row.get("planned_inputs") or not row.get("expected_outputs") or not row.get("checkpoints"):
            raise DeliveryValidationError("Agent Skill 适配内容缺少具体动作、输入、输出或检查点。")
        prerequisite_ids = set(row.get("prerequisite_ids", []))
        for binding_id in origins:
            unresolved = unknown_prerequisites.get(binding_id, set())
            represented_unknowns[binding_id].update(prerequisite_ids & unresolved)
            if prerequisite_ids & unresolved:
                fallback = row.get("fallback_actions")
                usable_fallback = (
                    isinstance(fallback, list)
                    and any(
                        isinstance(action, str)
                        and action.strip()
                        and action.strip().casefold() not in {"无", "none", "n/a"}
                        for action in fallback
                    )
                )
                if not usable_fallback:
                    raise DeliveryValidationError("未知 Skill 前提只有在存在可执行 fallback 时才能确认。")
    for binding_id, unknown_ids in unknown_prerequisites.items():
        if not unknown_ids <= represented_unknowns[binding_id]:
            raise DeliveryValidationError("未知 Skill 前提没有关联到适配内容和 fallback。")
    if contribution_bindings != bindings:
        raise DeliveryValidationError("最终结果没有覆盖全部当前选用的 Agent Skill。")
    body = result.get("canonical_body")
    if not isinstance(body, str) or not body.strip() or body != render_canonical_body(content):
        raise DeliveryValidationError("最终结果正文与结构化内容不一致。")
    if result.get("body_sha256") != _content_hash(body):
        raise DeliveryValidationError("最终正文校验失败。")
    review_required_ids = result.get("review_required_ids", [])
    if not isinstance(review_required_ids, list) or any(
        not isinstance(review_id, str) or not review_id for review_id in review_required_ids
    ):
        raise DeliveryValidationError("最终结果复核状态无效。")
    blocking_review_ids = {
        review_id for review_id in review_required_ids if _review_id_is_blocking(result, review_id)
    }
    if blocking_review_ids and (
        allowed_review_required_ids is None
        or not blocking_review_ids <= allowed_review_required_ids
    ):
        raise DeliveryValidationError("仍有最终结果需要复核。")
    if result.get("status") == "confirmed" and result.get("confirmed_revision") != result.get("revision"):
        raise DeliveryValidationError("最终结果确认版本与当前版本不一致。")
    if result.get("status") == "draft" and result.get("confirmed_revision") is not None:
        raise DeliveryValidationError("草稿不能保留旧确认状态。")


def build_final_draft(
    session: SessionState,
    *,
    selected_contributions: list[dict[str, Any]] | None = None,
    accepted_additions: list[dict[str, Any]] | None = None,
    user_notes: list[dict[str, Any]] | None = None,
    allow_unconfirmed_plan: bool = False,
) -> dict[str, Any]:
    validate_delivery_entry(session, allow_unconfirmed_plan=allow_unconfirmed_plan)
    live_bindings = _validate_skill_bindings(session)
    baseline = _baseline(session)
    previous = session.final_result if isinstance(session.final_result, dict) else {}
    previous_content = previous.get("content") if isinstance(previous.get("content"), dict) else {}
    current_plan_basis = (session.plan.get("plan_id"), session.plan.get("plan_version"))
    previous_basis = previous.get("basis") if isinstance(previous.get("basis"), dict) else {}
    previous_same_plan = (previous_basis.get("plan_id"), previous_basis.get("plan_version")) == current_plan_basis
    current_suggestion_ids = {row.get("suggestion_id") for row in session.plan["content"].get("suggestions", [])}
    prior_decisions = [
        deepcopy(row)
        for row in previous.get("suggestion_decisions", [])
        if previous_same_plan and row.get("suggestion_id") in current_suggestion_ids
    ]
    contributions = _attach_skill_provenance(
        session,
        _skill_contributions(session, selected_contributions),
    )
    contribution_bindings: set[str] = set()
    for row in contributions:
        origins = set(row.get("origin_binding_ids", []))
        if row.get("binding_id"):
            origins.add(row["binding_id"])
        if not origins or not origins <= live_bindings:
            raise DeliveryValidationError("方法增量必须只引用当前已选用的绑定。")
        contribution_bindings.update(origins)
    if contribution_bindings != live_bindings:
        raise DeliveryValidationError("最终草稿必须覆盖全部当前已选方法，且不能遗留旧绑定内容。")

    surviving_bindings = live_bindings
    accepted_rows = deepcopy(
        accepted_additions if accepted_additions is not None else previous_content.get("accepted_additions", [])
    )
    # Keep unresolved M4 items when rebuilding for binding changes. A new M4
    # generation replaces them explicitly in delivery_workflow, while ordinary
    # rebuilds must retain still-live pending items for user review.
    m4_pending_changes: list[dict[str, Any]] = []
    for row in previous_content.get("pending_changes", []):
        if not row.get("change_id"):
            continue
        origins = row.get("binding_ids", [])
        remaining_origins = [binding_id for binding_id in origins if binding_id in surviving_bindings]
        if not remaining_origins:
            continue
        item = deepcopy(row)
        item["binding_ids"] = remaining_origins
        m4_pending_changes.append(item)
    notes = deepcopy(user_notes if user_notes is not None else previous_content.get("user_notes", []))
    preserved_unapplied = deepcopy(previous.get("unapplied_edits", []))
    active_notes: list[dict[str, Any]] = []
    for note in notes:
        dependencies = set(note.get("depends_on_binding_ids", []))
        if dependencies <= surviving_bindings:
            active_notes.append(note)
        else:
            preserved_unapplied.append({
                **note,
                "reason": "依赖的 Agent Skill 已取消选用，原文保留为未应用编辑。",
            })
    retained_additions: list[dict[str, Any]] = []
    for row in accepted_rows:
        origins = row.get("origin_binding_ids", [])
        if origins:
            remaining_origins = [binding_id for binding_id in origins if binding_id in surviving_bindings]
            if not remaining_origins:
                continue
        else:
            remaining_origins = []
        if row.get("source_suggestion_id") and not (
            previous_same_plan and row.get("source_suggestion_id") in current_suggestion_ids
        ):
            continue
        item = deepcopy(row)
        if origins:
            item["origin_binding_ids"] = remaining_origins
        retained_additions.append(item)
    accepted_rows = retained_additions
    content = {
        "baseline": baseline,
        "skill_contributions": contributions,
        "accepted_additions": accepted_rows,
        "user_notes": active_notes,
        "pending_changes": [
            *_pending_suggestions(baseline["plan"], prior_decisions),
            *m4_pending_changes,
        ],
    }
    if allow_unconfirmed_plan and session.plan.get("status") == "draft":
        content["plan_review_pending"] = True
    body = render_canonical_body(content)
    revision = int(previous.get("revision", 0)) + 1
    return {
        "schema_version": "final.v0.1",
        "final_id": f"final-{uuid4().hex}",
        "revision": revision,
        "status": "draft",
        "confirmed_revision": None,
        "basis": _current_basis(session),
        "content": content,
        "canonical_body": body,
        "body_sha256": _content_hash(body),
        "renderer_version": "final-render.v0.2",
        "tone": str(previous.get("tone", "neutral")),
        "suggestion_decisions": prior_decisions,
        "change_decisions": deepcopy(previous.get("change_decisions", [])),
        "review_required_ids": [],
        "unapplied_edits": preserved_unapplied,
        "generation_request_id": None,
        "recovery_notice": None,
        "created_at": _now(),
    }


def stage_final_draft(session: SessionState, draft: dict[str, Any], *, expected_basis: dict[str, Any] | None = None) -> None:
    if not isinstance(draft, dict) or draft.get("status") != "draft":
        raise DeliveryValidationError("最终草稿格式无效。")
    interim = bool((draft.get("content") or {}).get("plan_review_pending"))
    validate_delivery_entry(session, allow_unconfirmed_plan=interim)
    basis = draft.get("basis")
    if not isinstance(basis, dict) or basis != _current_basis(session):
        raise DeliveryValidationError("最终草稿缺少当前来源依据，拒绝接收。")
    if expected_basis is not None and basis != expected_basis:
        raise DeliveryValidationError("最终草稿来源已变化，拒绝接收。")
    expected_body = render_canonical_body(draft.get("content", {}))
    if draft.get("canonical_body") != expected_body or draft.get("body_sha256") != _content_hash(expected_body):
        raise DeliveryValidationError("最终草稿正文与结构化内容不一致。")
    if draft.get("confirmed_revision") is not None:
        raise DeliveryValidationError("新生成的最终草稿不能携带旧确认状态。")
    if draft.get("content", {}).get("baseline") != _baseline(session):
        raise DeliveryValidationError("最终草稿没有承接当前已确认基线。")
    live_bindings = _validate_skill_bindings(session)
    contribution_bindings: set[str] = set()
    for row in draft.get("content", {}).get("skill_contributions", []):
        origins = set(row.get("origin_binding_ids", []))
        if row.get("binding_id"):
            origins.add(row["binding_id"])
        if not origins or not origins <= live_bindings:
            raise DeliveryValidationError("最终草稿包含未选用或已过期的方法内容。")
        contribution_bindings.update(origins)
    if contribution_bindings != live_bindings:
        raise DeliveryValidationError("最终草稿没有精确覆盖当前选用的 Agent Skill。")
    previous = deepcopy(session.final_result)
    if previous.get("status") not in {None, "not_started"}:
        previous["archived_at"] = _now()
        previous["archived_reason"] = "regenerated"
        session.final_archive.append(previous)
    session.final_result = deepcopy(draft)
    session._delivery_changed(reason="final_draft_staged")
    # Staging itself should remain current; the change counter is part of the basis
    # only for the next request, so rewrite it after the mutation.
    session.final_result["basis"]["delivery_revision"] = session.delivery_revision
    session.final_result["status"] = "draft"


def edit_final_note(session: SessionState, note_id: str, text: str, depends_on_binding_ids: list[str] | None = None) -> None:
    clean = str(text).strip()
    if not clean:
        raise DeliveryValidationError("附注不能为空。")
    result = session.final_result
    if result.get("status") not in {"draft", "confirmed"} or not isinstance(result.get("content"), dict):
        raise DeliveryValidationError("当前没有可编辑的最终草稿。")
    validate_current_final(session)
    notes = result["content"].setdefault("user_notes", [])
    row = next((item for item in notes if item.get("note_id") == note_id), None)
    if row is None:
        row = {"note_id": note_id, "text": clean, "depends_on_binding_ids": list(depends_on_binding_ids or [])}
        notes.append(row)
    else:
        row.update({"text": clean, "depends_on_binding_ids": list(depends_on_binding_ids or row.get("depends_on_binding_ids", []))})
    result["revision"] = int(result.get("revision", 0)) + 1
    result["status"] = "draft"
    result["confirmed_revision"] = None
    result["canonical_body"] = render_canonical_body(result["content"])
    result["body_sha256"] = _content_hash(result["canonical_body"])
    session._delivery_changed(reason="final_note_edited")
    result["basis"]["delivery_revision"] = session.delivery_revision
    result["status"] = "draft"
    result["confirmed_revision"] = None


def decide_m2_suggestion(session: SessionState, suggestion_id: str, decision: str) -> None:
    if decision not in {"accepted", "rejected"}:
        raise DeliveryValidationError("建议操作必须是接受或拒绝。")
    validate_current_final(session)
    result = session.final_result
    content = result["content"]
    suggestion = next(
        (row for row in content.get("pending_changes", []) if row.get("suggestion_id") == suggestion_id),
        None,
    )
    if suggestion is None or suggestion.get("decision") != "pending":
        raise DeliveryValidationError("该建议不存在、已处理或不属于当前方案版本。")
    if decision == "accepted" and suggestion.get("requires_user_confirmation"):
        raise DeliveryValidationError("该建议可能改变范围或重要决定，请返回需求／方案流程处理。")

    basis = result["basis"]
    decisions = result.setdefault("suggestion_decisions", [])
    decisions.append({
        "plan_id": basis["plan_id"],
        "plan_version": basis["plan_version"],
        "suggestion_id": suggestion_id,
        "decision": decision,
        "decided_by": "user_ui",
        "decided_at": _now(),
    })
    if decision == "accepted":
        content.setdefault("accepted_additions", []).append({
            "source_suggestion_id": suggestion_id,
            "text": suggestion.get("text", ""),
            "reason": suggestion.get("reason", ""),
            "origin_binding_ids": [],
        })
        content["pending_changes"] = [
            row for row in content.get("pending_changes", []) if row.get("suggestion_id") != suggestion_id
        ]
    else:
        suggestion["decision"] = "rejected"

    result["revision"] = int(result.get("revision", 0)) + 1
    result["canonical_body"] = render_canonical_body(content)
    result["body_sha256"] = _content_hash(result["canonical_body"])
    result["confirmed_revision"] = None
    result["status"] = "draft"
    session._delivery_changed(reason=f"suggestion_{decision}")
    result["basis"]["delivery_revision"] = session.delivery_revision
    result["status"] = "draft"


def decide_m4_change(session: SessionState, change_id: str, decision: str) -> None:
    if decision not in {"accepted", "rejected"}:
        raise DeliveryValidationError("变化操作必须是接受或拒绝。")
    current = session.final_result
    current_generation = current.get("generation_request_id")
    matches = [
        row for row in current["content"].get("pending_changes", [])
        if row.get("change_id") == change_id
        and (row.get("generation_request_id") or current_generation) == current_generation
    ]
    if len(matches) != 1 or matches[0].get("decision", "pending") != "pending":
        raise DeliveryValidationError("该变化不存在、已处理或不属于当前生成结果。")
    change = matches[0]
    generation_request_id = change.get("generation_request_id") or current.get("generation_request_id")
    if not isinstance(generation_request_id, str) or not generation_request_id.strip():
        raise DeliveryValidationError("当前变化缺少有效的 M4 生成请求来源。")
    decision_records = [
        row for row in current.get("change_decisions", [])
        if row.get("generation_request_id") == generation_request_id
        and row.get("change_id") == change_id
    ]
    if len(decision_records) > 1 or (
        decision_records and decision_records[0].get("decision") != "pending"
    ):
        raise DeliveryValidationError("该 M4 变化在本次生成中已处理。")
    pending_review_ids = {
        f"m4-change:{request_id}:{row['change_id']}"
        for row in current["content"].get("pending_changes", [])
        if row.get("change_id") and row.get("decision", "pending") == "pending"
        for request_id in [row.get("generation_request_id") or current.get("generation_request_id")]
        if isinstance(request_id, str) and request_id.strip()
    }
    pending_review_ids.update(
        review_id
        for review_id in current.get("review_required_ids", [])
        if isinstance(review_id, str) and review_id.startswith("m4-fallback-required:")
    )
    validate_current_final(session, allowed_review_required_ids=pending_review_ids)
    if decision == "accepted" and change.get("affects_hard_constraints"):
        raise DeliveryValidationError("该变化影响已确认硬约束，请返回上游流程处理。")
    binding_ids = change.get("binding_ids")
    selected_ids = {
        row.get("binding_id") for row in session.skill_state.get("bindings", [])
    }
    if (
        not isinstance(binding_ids, list)
        or not binding_ids
        or not all(isinstance(binding_id, str) and binding_id for binding_id in binding_ids)
        or len(binding_ids) != len(set(binding_ids))
        or not set(binding_ids) <= selected_ids
    ):
        raise DeliveryValidationError("变化必须只引用当前有效的 Skill 绑定。")

    updated = deepcopy(current)
    updated_change = next(
        row for row in updated["content"]["pending_changes"]
        if row.get("change_id") == change_id
        and (row.get("generation_request_id") or current_generation) == generation_request_id
    )
    updated_decision_records = [
        row for row in updated.get("change_decisions", [])
        if row.get("generation_request_id") == generation_request_id
        and row.get("change_id") == change_id
    ]
    decision_record = {
        "generation_request_id": generation_request_id,
        "change_id": change_id,
        "decision": decision,
        "decided_by": "user_ui",
        "decided_at": _now(),
    }
    if updated_decision_records:
        updated_decision_records[0].update(decision_record)
        updated_decision_records[0].pop("reason", None)
    else:
        updated.setdefault("change_decisions", []).append(decision_record)
    if decision == "accepted":
        additions = updated["content"].setdefault("accepted_additions", [])
        if any(
            row.get("source_change_id") == change_id
            and row.get("source_change_generation_request_id") == generation_request_id
            for row in additions
        ):
            raise DeliveryValidationError("该变化已经进入采纳补充，拒绝重复应用。")
        additions.append({
            "source_change_id": change_id,
            "source_change_generation_request_id": generation_request_id,
            "text": updated_change.get("text", updated_change.get("description", "")),
            "reason": updated_change.get("reason", ""),
            "origin_binding_ids": list(binding_ids),
        })
        updated["content"]["pending_changes"] = [
            row for row in updated["content"]["pending_changes"] if row.get("change_id") != change_id
        ]
    else:
        updated_change["decision"] = "rejected"
        action_review_id = f"m4-fallback-required:{generation_request_id}:{change_id}"
        contributions = updated["content"].get("skill_contributions", [])
        affected = [
            row for row in contributions
            if any(
                isinstance(dependency, dict)
                and dependency.get("generation_request_id") == generation_request_id
                and dependency.get("change_id") == change_id
                for dependency in row.get("m4_dependencies", [])
            )
        ]
        for contribution in affected:
            original_actions = deepcopy(contribution.get("method_actions", []))
            fallback_actions = _usable_actions(contribution.get("fallback_actions"))
            contribution.setdefault("inactive_method_actions", []).append({
                "generation_request_id": generation_request_id,
                "change_id": change_id,
                "actions": original_actions,
            })
            if fallback_actions:
                contribution["method_actions"] = fallback_actions
                contribution.setdefault("applied_fallbacks", []).append({
                    "generation_request_id": generation_request_id,
                    "change_id": change_id,
                    "actions": fallback_actions,
                })
            else:
                contribution["method_actions"] = []
                contribution.setdefault("disabled_by_rejected_changes", []).append({
                    "generation_request_id": generation_request_id,
                    "change_id": change_id,
                })
                if change.get("affects_hard_constraints") and action_review_id not in updated.setdefault("review_required_ids", []):
                    updated["review_required_ids"].append(action_review_id)

    review_id = f"m4-change:{generation_request_id}:{change_id}"
    updated["review_required_ids"] = [
        review_required_id
        for review_required_id in updated.get("review_required_ids", [])
        if review_required_id != review_id or decision == "rejected" and review_required_id.startswith("m4-fallback-required:")
    ]
    updated["revision"] = int(updated.get("revision", 0)) + 1
    updated["canonical_body"] = render_canonical_body(updated["content"])
    updated["body_sha256"] = _content_hash(updated["canonical_body"])
    updated["status"] = "draft"
    updated["confirmed_revision"] = None
    session._delivery_changed(reason=f"m4_change_{decision}")
    updated["basis"]["delivery_revision"] = session.delivery_revision
    session.final_result = updated


def confirm_final(session: SessionState) -> int:
    result = session.final_result
    if result.get("status") != "draft":
        raise DeliveryValidationError("当前没有待确认的最终草稿。")
    if (result.get("content") or {}).get("plan_review_pending"):
        raise DeliveryValidationError("方案尚未核对；请先核对方案并生成当前提示。草稿仍可保存和导出。")
    validate_delivery_entry(session)
    validate_current_final(session)
    result["status"] = "confirmed"
    result["confirmed_revision"] = result.get("revision")
    session.touch()
    return int(result["confirmed_revision"])


def validate_loaded_delivery(session: SessionState) -> None:
    result = session.final_result
    status = result.get("status")
    if status == "not_started":
        return
    if not isinstance(result.get("content"), dict):
        if status != "stale":
            result["status"] = "stale"
            result["confirmed_revision"] = None
            result["recovery_notice"] = "旧最终结果缺少当前版本来源，已保留为过期历史。"
        return

    result["recovery_notice"] = None
    content = result["content"]
    expected_body = render_canonical_body(content)
    cached_body = result.get("canonical_body")
    legacy_body_is_valid = (
        result.get("renderer_version") == "final-render.v0.1"
        and isinstance(cached_body, str)
        and cached_body == render_canonical_body(content, _legacy_v01=True)
        and result.get("body_sha256") == _content_hash(cached_body)
    )
    if cached_body != expected_body or result.get("body_sha256") != _content_hash(expected_body):
        result["canonical_body"] = expected_body
        result["body_sha256"] = _content_hash(expected_body)
        if legacy_body_is_valid:
            result["renderer_version"] = "final-render.v0.2"
        else:
            result["status"] = "draft"
            result["confirmed_revision"] = None
            result["recovery_notice"] = "最终正文缓存与结构化内容不一致，已重新渲染并撤销旧确认，请复核。"
    elif legacy_body_is_valid:
        result["renderer_version"] = "final-render.v0.2"

    if result.get("basis") != _current_basis(session):
        result["status"] = "stale"
        result["confirmed_revision"] = None
        result["recovery_notice"] = "最终结果来源版本已变化，已保留内容并撤销旧确认。"
        return
    if result.get("status") == "confirmed" and result.get("confirmed_revision") != result.get("revision"):
        result["status"] = "draft"
        result["confirmed_revision"] = None
        result["recovery_notice"] = "最终结果确认版本不一致，已撤销旧确认，请复核。"
    if result.get("status") in {"draft", "confirmed"}:
        try:
            validate_current_final(session)
        except DeliveryValidationError as exc:
            result["status"] = "draft"
            result["confirmed_revision"] = None
            result["recovery_notice"] = f"最终结果需要重新复核：{exc}"


def set_final_tone(session: SessionState, tone: str) -> None:
    if tone not in {"neutral", "polite"}:
        raise DeliveryValidationError(f"不支持的语气：{tone}")
    result = session.final_result
    validate_current_final(session)
    result["tone"] = tone
    # Tone is a rendering choice. It deliberately does not change semantic revision.
    session.touch()


def invalidate_delivery(session: SessionState, reason: str, *, invalidate_selection: bool = False) -> None:
    session.invalidate_delivery(reason, invalidate_selection=invalidate_selection)


def render_canonical_body(content: dict[str, Any], *, _legacy_v01: bool = False) -> str:
    baseline = content.get("baseline", {})
    plan = baseline.get("plan", {})
    goal = plan.get("goal", {}) if isinstance(plan.get("goal"), dict) else {}
    requirements = [row for row in baseline.get("requirements", []) if isinstance(row, dict)]
    requirement_by_id = {
        str(row.get("item_id")): row for row in requirements if row.get("item_id")
    }
    steps = [row for row in plan.get("steps", []) if isinstance(row, dict)]
    step_by_id = {str(row.get("step_id")): row for row in steps if row.get("step_id")}

    def requirement_texts(ids: Any) -> str:
        values = [
            str(requirement_by_id[str(item)].get("text", "")).strip()
            for item in (ids if isinstance(ids, list) else [])
            if str(item) in requirement_by_id and str(requirement_by_id[str(item)].get("text", "")).strip()
        ]
        return _display_list(values)

    def step_labels(ids: Any) -> str:
        values = []
        for item in ids if isinstance(ids, list) else []:
            step = step_by_id.get(str(item))
            if step is not None:
                values.append(f"{step.get('order', '')}. {step.get('title', '')}".strip())
        return _display_list(values)

    def key_work_order(row: dict[str, Any], index: int) -> tuple[int, int]:
        orders = [
            int(step_by_id[str(step_id)].get("order", 0))
            for step_id in row.get("step_ids", [])
            if str(step_id) in step_by_id
        ]
        return (min(orders) if orders else 10**9, index)

    lines = [
        "任务背景与目标",
        f"任务：{baseline.get('task', '')}",
        f"目标：{goal.get('summary', '')}",
        "",
        "使用对象、场景和范围",
        f"对象：{goal.get('audience', '')}",
        f"范围：{goal.get('scope', '')}",
        "",
        "已确认要求与硬约束",
    ]
    authorization = baseline.get("draft_authorization")
    if authorization:
        lines[0:0] = [
            "用户选择先做草稿，不代表所有内容已经确定。",
            str(authorization.get("explanation", "")),
            "尚未确认的解释只能作为推测；具体信息缺失时只做不依赖它的部分，不得编造。",
            "",
        ]
    if content.get("plan_review_pending"):
        lines[0:0] = ["方案尚未核对，这是按你的选择先整理的草稿；可查看、修改、保存和导出。", ""]
    if requirements:
        for row in requirements:
            lines.append(f"- {row.get('text', '')}")
            lines.append(
                f"  类型：{_requirement_kind_label(row.get('kind'))}；"
                f"强度：{_strength_label(row.get('strength'))}；"
                f"范围：{row.get('scope', '未标注范围')}"
            )
            refs = [
                ref.get("quote", "").strip()
                for ref in row.get("source_refs", [])
                if isinstance(ref, dict) and isinstance(ref.get("quote"), str) and ref.get("quote", "").strip()
            ]
            lines.append(f"  来源原话：{_display_list(refs, empty='未提供用户原话')}")
            lines.append(f"  依赖要求：{requirement_texts(row.get('depends_on'))}")
    else:
        lines.append("- 无")
    lines.extend(["", "工作步骤"])
    for step in sorted(steps, key=lambda row: row.get("order", 0)):
        lines.append(f"{step.get('order', '')}. {step.get('title', '')}：{step.get('purpose', '')}")
        lines.append(f"   输入：{_display_list(step.get('inputs'))}")
        lines.append(f"   动作：{_display_list(step.get('actions'))}")
        lines.append(f"   输出：{_display_list(step.get('outputs'))}")
        lines.append(f"   检查点：{_display_list(step.get('completion_criteria'))}")
        lines.append(f"   前置步骤：{step_labels(step.get('depends_on_step_ids'))}")
        lines.append(f"   关联要求：{requirement_texts(step.get('requirement_ids'))}")
    lines.extend(["", "关键工作与依赖"])
    key_work = [row for row in plan.get("key_work", []) if isinstance(row, dict)]
    if key_work:
        for index, row in sorted(enumerate(key_work), key=lambda item: key_work_order(item[1], item[0])):
            lines.append(f"- {row.get('title', '')}")
            lines.append(f"  目标：{row.get('goal', '')}")
            lines.append(f"  输入：{_display_list(row.get('inputs'))}")
            lines.append(f"  输出：{_display_list(row.get('outputs'))}")
            lines.append(f"  关联步骤：{step_labels(row.get('step_ids'))}")
            dependency_titles = [
                next((str(item.get("title", "")) for item in key_work if str(item.get("key_work_id")) == str(dep)), str(dep))
                for dep in row.get("depends_on_key_work_ids", [])
            ]
            lines.append(f"  前置关键工作：{_display_list(dependency_titles)}")
            lines.append(f"  关联要求：{requirement_texts(row.get('requirement_ids'))}")
            lines.append(f"  完成证据：{_display_list(row.get('checkpoints'))}")
    lines.extend(["", "交付物与完成标准"])
    for row in plan.get("deliverables", []):
        lines.append(f"- 交付物：{row.get('name', '')}；{row.get('description', '')}")
        lines.append(f"  关联步骤：{step_labels(row.get('step_ids'))}")
        lines.append(f"  关联要求：{requirement_texts(row.get('requirement_ids'))}")
    for row in plan.get("completion_criteria", []):
        lines.append(f"- 完成标准：{row.get('text', '')}")
        lines.append(f"  关联要求：{requirement_texts(row.get('requirement_ids'))}")
    contributions = content.get("skill_contributions", [])
    has_skill_references = any(row.get("skill_references") for row in contributions)
    lines.extend(["", "所选 Agent Skill 与任务用法" if has_skill_references else "当前所选的方法适配"])
    if contributions:
        if has_skill_references:
            lines.append("执行本任务时，请先在你的环境中查找以下已选 Agent Skill，读取对应的 SKILL.md，并用于其关联的关键工作和步骤。")
            lines.append("如尚未具备该 Skill，请根据来源获取；需要安装或额外权限时先向用户说明。无法访问来源时，请用户提供文件，并继续可完成的任务部分。")
        for row in contributions:
            for reference in row.get("skill_references", []):
                lines.append(f"- 使用 Agent Skill：{reference.get('name', reference.get('skill_id', ''))}")
                work = next((work for work in key_work if work.get("key_work_id") == reference.get("key_work_id")), {})
                lines.append(f"  用于关键工作：{work.get('title') or reference.get('key_work_id', '')}")
                applied_steps = [row["step_id"]] if row.get("step_id") else reference.get("step_ids", [])
                titles = [step_by_id[step_id].get("title", step_id) for step_id in applied_steps if step_id in step_by_id]
                lines.append(f"  应用步骤：{_display_list(titles)}")
                if reference.get("source_url"):
                    lines.append(f"  Skill 来源：{reference['source_url']}")
                if reference.get("local_path"):
                    lines.append(f"  本机 Skill 文件：{reference['local_path']}")
                    lines.append("  若在另一台电脑使用，请按名称查找该 Skill；路径不可用时请用户提供 SKILL.md 及其引用资源。")
                if not reference.get("source_url") and not reference.get("local_path"):
                    lines.append("  请按 Skill 名称查找；找不到时请用户提供对应 SKILL.md。")
                if not reference.get("source_read"):
                    lines.append("  当前信息有限，仅依据摘要或目录信息推荐；请读取实际 Skill 后确认能力、依赖和适用范围，再用于任务。")
            lines.append(f"  任务用法：{_display_list(row.get('method_actions'))}" if row.get("skill_references") else f"- 方法：{_display_list(row.get('method_actions'))}")
            lines.append(f"  输入：{_display_list(row.get('planned_inputs'))}")
            lines.append(f"  输出：{_display_list(row.get('expected_outputs'))}")
            if row.get("skill_references"):
                lines.append(f"  检查点：{_display_list(row.get('checkpoints'))}")
            lines.append(f"  前提：{_display_list(row.get('prerequisite_ids'), empty='无额外前提')}")
            lines.append(f"  fallback：{_display_list(row.get('fallback_actions'))}")
            provenance = row.get("provenance")
            if isinstance(provenance, dict) and provenance.get("origin") == "remote":
                lines.append("  远程来源核验：")
                lines.append(f"    来源 URL：{provenance.get('source_url', '')}")
                lines.append(f"    固定提交：{provenance.get('fixed_commit', 'unresolved')}")
                lines.append(f"    内容哈希类型：{provenance.get('content_hash_kind', '未记录')}")
                lines.append(f"    内容哈希：{provenance.get('content_sha256', '')}")
                lines.append(f"    核验状态：{provenance.get('verification_status', 'unknown')}")
                lines.append(f"    正文已读取：{'是' if provenance.get('source_read') else '否'}")
                lines.append(f"    已安装：{'是' if provenance.get('installed') else '否'}")
                lines.append(f"    已执行测试：{'是' if provenance.get('execution_tested') else '否'}")
                lines.append("    请下游 AI 在使用时确认所需工具和依赖；以上状态是生成提示时的记录。")
            for source in row.get("provenance_sources", []):
                if not isinstance(source, dict) or source.get("origin") != "remote":
                    continue
                lines.append(f"  远程来源：{source.get('source_url', '')}；固定提交：{source.get('fixed_commit', 'unresolved')}")
    else:
        lines.append("- 本方案未采用外部 Agent Skill。")
    lines.extend(["", "未决事项"])
    unknown = baseline.get("unknown", [])
    if unknown:
        if baseline.get("unknown_handling") == "ask_then_defer":
            lines.append("使用本提示时，优先询问影响当前工作的缺失信息；用户暂不回答或含义仍不清楚时，保留未决标记，先推进不依赖它的部分，不自行编造答案。")
        for row in unknown:
            lines.append(f"- {row.get('description', row.get('text', ''))}")
            lines.append(f"  来源：{_origin_label(row.get('origin'))}")
            if row.get("source_description"):
                lines.append(f"  原始未决事项：{row['source_description']}")
            refs = [
                ref.get("quote", "").strip()
                for ref in row.get("source_refs", [])
                if isinstance(ref, dict) and isinstance(ref.get("quote"), str) and ref.get("quote", "").strip()
            ]
            lines.append(f"  来源原话：{_display_list(refs, empty='未提供')}")
            lines.append(f"  影响：{row.get('impact', '待评估')}")
            lines.append(f"  可继续：{row.get('continuable_work', '待补充')}")
            lines.append(f"  确认时点：{row.get('confirm_by', '待确定')}")
    else:
        lines.append("- 无")
    pending = content.get("pending_changes", [])
    pending_suggestions = pending if _legacy_v01 else [
        row for row in pending if row.get("suggestion_id") and not row.get("change_id")
    ]
    post_delivery_items = [row for row in pending if row.get("change_id")]
    lines.extend(["", "待决定建议（当前未采纳，不要求执行）"])
    if pending_suggestions:
        lines.extend(
            f"- {'未采纳' if row.get('decision') == 'rejected' else '待决定'}：{row.get('text', row.get('description', ''))}；"
            f"来源：M2 系统建议；类型：{_suggestion_kind_label(row.get('kind'))}；理由：{row.get('reason', '')}"
            for row in pending_suggestions
        )
    else:
        lines.append("- 无")
    if not _legacy_v01:
        lines.extend(["", "使用时补充的后置事项"])
        if post_delivery_items:
            for row in post_delivery_items:
                decision = row.get("decision", "pending")
                state = "未采纳" if decision == "rejected" else "待使用时补充"
                hard_note = "；若要采纳，须先回到上游确认硬约束" if row.get("affects_hard_constraints") else ""
                lines.append(
                    f"- {state}：{row.get('text', row.get('description', ''))}；"
                    f"来源：M4 Agent Skill 整合；类型：{row.get('kind', '未标注')}；"
                    f"理由：{row.get('reason', '')}{hard_note}"
                )
        else:
            lines.append("- 无")
    lines.extend(["", "材料清单与提供条件", "- 当前正文只使用会话中已保存的需求、方案和未决事项；未附带的外部材料仍需用户提供。"])
    for row in content.get("accepted_additions", []):
        lines.extend(["", f"附加说明：{row.get('text', row.get('description', ''))}"])
    for row in content.get("user_notes", []):
        lines.extend(["", f"用户附注：{row.get('text', '')}"])
    return "\n".join(lines).strip()


def render_task_prompt(canonical_body: str, tone: str = "neutral") -> str:
    prefixes = {
        "neutral": "根据以下任务说明完成工作。",
        "polite": "请根据以下任务说明完成工作。",
    }
    if tone not in prefixes:
        raise DeliveryValidationError(f"不支持的语气：{tone}")
    if not isinstance(canonical_body, str) or not canonical_body.strip():
        raise DeliveryValidationError("任务正文不能为空。")
    return f"{prefixes[tone]}\n\n{canonical_body}"
