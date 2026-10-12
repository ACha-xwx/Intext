from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

from promptsmith.exporter import export_markdown
from promptsmith.finalization import (
    DeliveryValidationError,
    build_final_draft,
    confirm_final,
    decide_m4_change,
    decide_m2_suggestion,
    edit_final_note,
    render_canonical_body,
    render_task_prompt,
    stage_final_draft,
    set_final_tone,
    validate_delivery_entry,
)
from promptsmith.session import SessionState, SessionStateError
from promptsmith.storage import load_session, save_session


def confirmed_plan_session() -> SessionState:
    session = SessionState.new()
    session.set_task("为零基础学习者规划 7 天 Python 入门")
    session.selected_category = "learning"
    session.requirements = [
        {
            "item_id": "r1",
            "field": "goal",
            "text": "面向零基础学习者制定 Python 入门计划",
            "kind": "user_fact",
            "strength": "hard",
            "scope": "学习计划对象",
            "source_refs": [{"source_id": "u1", "quote": "我是零基础学习者。"}],
            "depends_on": [],
            "confirmation": "confirmed",
        },
        {
            "item_id": "r2",
            "field": "deliverable",
            "text": "7 天计划，每天 30 分钟，包含练习和检查方式",
            "kind": "user_decision",
            "strength": "hard",
            "scope": "交付物",
            "source_refs": [{"source_id": "u2", "quote": "安排 7 天，每天 30 分钟。"}],
            "depends_on": [],
            "confirmation": "confirmed",
        },
    ]
    session.analysis_basis_version = session.requirement_version
    session.confirm_requirements()
    session.begin_m2_request("m2-fixture")
    session.pending_requests.pop("m2-fixture")
    session.plan = {
        "plan_id": "plan-fixture",
        "plan_version": 1,
        "status": "confirmed",
        "content": {
            "goal": {"summary": "规划 7 天 Python 入门", "audience": "零基础学习者", "scope": "入门学习"},
            "requirement_coverage": [
                {"requirement_id": "r1", "summary": "学习目标", "step_ids": ["s1"], "deliverable_ids": ["d1"], "criterion_ids": ["c1"]},
                {"requirement_id": "r2", "summary": "每日学习时长", "step_ids": ["s1"], "deliverable_ids": ["d1"], "criterion_ids": ["c1"]},
            ],
            "steps": [
                {"step_id": "s0", "order": 1, "title": "确认起点", "purpose": "按零基础安排内容", "inputs": ["学习者背景"], "actions": ["确认入门范围"], "outputs": ["起点说明"], "completion_criteria": ["不预设已有 Python 知识"], "depends_on_step_ids": [], "requirement_ids": ["r1"]},
                {"step_id": "s1", "order": 2, "title": "安排每日学习", "purpose": "形成 7 天渐进计划", "inputs": ["学习目标", "起点说明"], "actions": ["安排概念、练习和检查"], "outputs": ["逐日计划"], "completion_criteria": ["每天 30 分钟"], "depends_on_step_ids": ["s0"], "requirement_ids": ["r1", "r2"]},
            ],
            "deliverables": [{"deliverable_id": "d1", "name": "7 天学习计划", "description": "包含练习与检查方式", "step_ids": ["s1"], "requirement_ids": ["r1", "r2"]}],
            "completion_criteria": [{"criterion_id": "c1", "text": "不承诺掌握全部 Python", "requirement_ids": ["r2"]}],
            "unresolved_items": [{"unresolved_id": "u1", "source_gap_id": "g1", "description": "电脑是否安装 Python 未知", "impact": "影响运行练习", "continuable_work": "先安排无需安装的概念学习", "confirm_by": "开始运行练习前"}],
            "suggestions": [{"suggestion_id": "sg1", "kind": "optional_improvement", "text": "可增加复习日", "reason": "帮助巩固", "requires_user_confirmation": False}],
            "key_work": [
                {"key_work_id": "k0", "title": "核对学习起点", "step_ids": ["s0"], "goal": "明确零基础起点", "inputs": ["学习者背景"], "outputs": ["起点说明"], "requirement_ids": ["r1"], "depends_on_key_work_ids": [], "checkpoints": ["不假定学习者已有编程知识"]},
                {"key_work_id": "k1", "title": "设计每日学习顺序", "step_ids": ["s1"], "goal": "安排学习内容", "inputs": ["学习目标", "起点说明"], "outputs": ["逐日计划"], "requirement_ids": ["r1", "r2"], "depends_on_key_work_ids": ["k0"], "checkpoints": ["逐日内容可执行", "符合每天 30 分钟"]},
            ],
        },
        "original_content": None,
        "source_requirements_version": session.requirement_version,
        "confirmed_plan_version": 1,
        "pending_key_work_review_ids": [],
        "reviewed_key_work_ids": ["k0", "k1"],
        "source_snapshot": {
            "requirements": deepcopy(session.requirements),
            "unresolved_items": [{"gap_id": "g1", "field": "runtime", "scope": "运行环境", "description": "电脑是否安装 Python 未知", "origin": "user_unsure", "source_refs": [{"source_id": "u3", "quote": "我不确定电脑是否安装 Python。"}]}],
        },
    }
    return session


def test_no_skill_draft_is_deep_copy_and_keeps_unknowns_and_suggestions() -> None:
    session = confirmed_plan_session()
    original = deepcopy(session.plan["content"])
    validate_delivery_entry(session)
    draft = build_final_draft(session)

    assert draft["status"] == "draft"
    assert draft["content"]["baseline"]["plan"] == original
    assert draft["content"]["baseline"]["unknown"]
    assert draft["content"]["pending_changes"]
    assert draft["canonical_body"]
    assert "本方案未采用外部 Agent Skill" in draft["canonical_body"]
    assert session.plan["content"] == original


def test_tone_wrappers_share_exact_canonical_body() -> None:
    session = confirmed_plan_session()
    draft = build_final_draft(session)
    body = draft["canonical_body"]
    assert render_canonical_body(draft["content"]) == body
    neutral = render_task_prompt(body, "neutral")
    polite = render_task_prompt(body, "polite")
    assert neutral.split("\n\n", 1)[1] == polite.split("\n\n", 1)[1] == body


def test_canonical_body_distinguishes_requirement_source_type_scope_and_strength() -> None:
    draft = build_final_draft(confirmed_plan_session())
    body = draft["canonical_body"]

    assert "面向零基础学习者制定 Python 入门计划" in body
    assert "类型：用户事实" in body
    assert "来源原话：我是零基础学习者。" in body
    assert "范围：学习计划对象" in body
    assert "强度：硬约束" in body
    assert "类型：用户决定" in body
    assert "来源原话：安排 7 天，每天 30 分钟。" in body


def test_canonical_body_includes_key_work_goals_dependencies_steps_and_evidence() -> None:
    draft = build_final_draft(confirmed_plan_session())
    body = draft["canonical_body"]

    assert "关键工作" in body
    assert "核对学习起点" in body
    assert "目标：明确零基础起点" in body
    assert "输入：学习者背景" in body
    assert "输出：起点说明" in body
    assert "关联步骤：1. 确认起点" in body
    assert "完成证据：不假定学习者已有编程知识" in body
    assert "关联要求：面向零基础学习者制定 Python 入门计划" in body
    assert "前置关键工作：无" in body
    assert "前置关键工作：核对学习起点" in body
    assert "关联步骤：2. 安排每日学习" in body
    assert "完成证据：逐日内容可执行；符合每天 30 分钟" in body


def test_canonical_body_preserves_unknown_origin_and_resolution_boundary() -> None:
    draft = build_final_draft(confirmed_plan_session())
    body = draft["canonical_body"]

    assert "未决事项" in body
    assert "电脑是否安装 Python 未知" in body
    assert "来源：用户表示不确定" in body
    assert "来源原话：我不确定电脑是否安装 Python。" in body
    assert "影响：影响运行练习" in body
    assert "可继续：先安排无需安装的概念学习" in body
    assert "确认时点：开始运行练习前" in body


def test_canonical_body_marks_unadopted_suggestions_as_system_advice() -> None:
    draft = build_final_draft(confirmed_plan_session())
    body = draft["canonical_body"]

    assert "待决定建议（当前未采纳，不要求执行）" in body
    assert "待决定：可增加复习日" in body
    assert "来源：M2 系统建议" in body
    assert "类型：可选改进" in body
    assert "理由：帮助巩固" in body


def test_canonical_body_is_self_contained_and_does_not_invent_missing_materials() -> None:
    draft = build_final_draft(confirmed_plan_session())
    body = draft["canonical_body"]

    for heading in (
        "任务背景与目标",
        "使用对象、场景和范围",
        "已确认要求与硬约束",
        "工作步骤",
        "交付物与完成标准",
        "当前所选的方法适配",
        "未决事项",
        "待决定建议（当前未采纳，不要求执行）",
        "材料清单与提供条件",
    ):
        assert heading in body
    assert "未附带的外部材料仍需用户提供" in body
    assert "按刚才的" not in body
    assert "上面的聊天" not in body
    assert "2026-10-01" not in body
    assert "https://" not in body
    assert "1000 元" not in body


def test_confirm_final_requires_current_draft_and_preserves_tone() -> None:
    session = confirmed_plan_session()
    session.final_result = build_final_draft(session)
    revision = session.final_result["revision"]
    confirmed = confirm_final(session)
    assert confirmed == revision
    assert session.final_result["status"] == "confirmed"
    set_final_tone(session, "polite")
    assert session.final_result["confirmed_revision"] == revision
    assert session.final_result["revision"] == revision


def test_unconfirmed_upstream_is_rejected() -> None:
    session = confirmed_plan_session()
    session.plan["status"] = "draft"
    with pytest.raises(DeliveryValidationError):
        validate_delivery_entry(session)


def test_session_v01_migrates_without_auto_confirming_legacy_skill() -> None:
    data = {
        "schema_version": "promptsmith.session.v0.1",
        "task_id": "task-old",
        "selected_skills": ["to-spec"],
        "final_result": {"status": "ready", "content": "old"},
    }
    loaded = SessionState.from_dict(data)
    assert loaded.schema_version == "promptsmith.session.v0.2"
    assert loaded.skill_state["legacy_selection_unresolved"] == ["to-spec"]
    assert loaded.final_result["status"] == "stale"
    assert loaded.final_result["confirmed_revision"] is None


def test_invalid_final_confirmation_does_not_change_state() -> None:
    session = confirmed_plan_session()
    before = json.loads(json.dumps(session.to_dict(), ensure_ascii=False))
    with pytest.raises(DeliveryValidationError):
        confirm_final(session)
    assert session.to_dict() == before


def test_note_edit_creates_current_draft_and_revokes_confirmation() -> None:
    session = confirmed_plan_session()
    session.final_result = build_final_draft(session)
    confirm_final(session)
    old_revision = session.final_result["revision"]

    edit_final_note(session, "note-independent", "不购买付费课程。")

    assert session.final_result["status"] == "draft"
    assert session.final_result["revision"] == old_revision + 1
    assert session.final_result["confirmed_revision"] is None
    assert "不购买付费课程。" in session.final_result["canonical_body"]
    confirm_final(session)


def test_final_confirmation_rejects_changed_plan_basis_without_writes() -> None:
    session = confirmed_plan_session()
    draft = build_final_draft(session)
    stage_final_draft(session, draft, expected_basis=draft["basis"])
    session.plan["plan_version"] += 1
    session.plan["confirmed_plan_version"] = session.plan["plan_version"]
    before = session.to_dict()

    with pytest.raises(DeliveryValidationError, match="来源版本"):
        confirm_final(session)

    assert session.to_dict() == before


def test_load_repairs_corrupt_render_cache_and_revokes_confirmation(tmp_path) -> None:
    session = confirmed_plan_session()
    session.final_result = build_final_draft(session)
    confirm_final(session)
    saved = save_session(session, tmp_path / "cache-corrupt.json")
    payload = json.loads(saved.read_text(encoding="utf-8"))
    payload["final_result"]["canonical_body"] = "被篡改的缓存正文"
    saved.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    loaded = load_session(saved)

    assert loaded.final_result["status"] == "draft"
    assert loaded.final_result["confirmed_revision"] is None
    assert loaded.final_result["canonical_body"] == render_canonical_body(loaded.final_result["content"])
    assert loaded.final_result["recovery_notice"]


def test_load_upgrades_valid_v01_body_without_revoking_confirmation(tmp_path) -> None:
    session = confirmed_plan_session()
    session.final_result = build_final_draft(session)
    confirm_final(session)
    old_body = render_canonical_body(session.final_result["content"], _legacy_v01=True)
    session.final_result["canonical_body"] = old_body
    session.final_result["body_sha256"] = hashlib.sha256(old_body.encode("utf-8")).hexdigest()
    session.final_result["renderer_version"] = "final-render.v0.1"

    loaded = load_session(save_session(session, tmp_path / "v01-confirmed.json"))

    assert loaded.final_result["status"] == "confirmed"
    assert loaded.final_result["confirmed_revision"] == loaded.final_result["revision"]
    assert loaded.final_result["renderer_version"] == "final-render.v0.2"
    assert "使用时补充的后置事项" in loaded.final_result["canonical_body"]
    exported = export_markdown(loaded, tmp_path / "v01-confirmed.md", mode="final")
    assert "最终任务提示" in exported.read_text(encoding="utf-8")


def test_load_upgrades_v01_m4_suggestion_to_nonblocking_post_delivery_item(tmp_path) -> None:
    session = _session_with_bound_prerequisite("satisfied", [])
    _attach_m4_change(session, _m4_change(hard=True))
    old_body = render_canonical_body(session.final_result["content"], _legacy_v01=True)
    assert "来源：M2 系统建议" in old_body
    session.final_result["canonical_body"] = old_body
    session.final_result["body_sha256"] = hashlib.sha256(old_body.encode("utf-8")).hexdigest()
    session.final_result["renderer_version"] = "final-render.v0.1"

    loaded = load_session(save_session(session, tmp_path / "v01-m4.json"))

    assert loaded.final_result["status"] == "draft"
    assert loaded.final_result["renderer_version"] == "final-render.v0.2"
    assert "来源：M4 Agent Skill 整合" in loaded.final_result["canonical_body"]
    assert "若要采纳，须先回到上游确认硬约束" in loaded.final_result["canonical_body"]
    assert confirm_final(loaded) == loaded.final_result["revision"]
    assert "增加术语核对记录。" in export_markdown(
        loaded, tmp_path / "v01-m4.md", mode="final"
    ).read_text(encoding="utf-8")


def test_rebuild_without_skill_removes_old_contributions_and_preserves_notes() -> None:
    session = confirmed_plan_session()
    record = {
        "skill_id": "local-method",
        "record_hash": "record-hash",
        "method_adaptation_allowed": True,
        "capabilities": [],
    }
    basis = {
        "task_id": session.task_id,
        "requirement_version": session.requirement_version,
        "plan_id": session.plan["plan_id"],
        "plan_version": session.plan["plan_version"],
    }
    binding = {
        "binding_id": "binding-1",
        "skill_id": "local-method",
        "record_hash": "record-hash",
        "record_snapshot": record,
        "key_work_id": "k1",
        "step_ids": ["s1"],
        "usage_mode": "method_adaptation",
    }
    session.set_skill_state(status="selected", basis=basis, bindings=[binding])
    contribution = {
        "binding_id": "binding-1",
        "origin_binding_ids": ["binding-1"],
        "step_id": "s1",
        "method_actions": ["按方法整理规格"],
        "planned_inputs": ["当前需求"],
        "expected_outputs": ["规格草稿"],
        "checkpoints": ["核对硬约束"],
        "prerequisite_ids": [],
        "fallback_actions": ["条件缺失时回到原方案步骤。"],
    }
    draft = build_final_draft(session, selected_contributions=[contribution])
    stage_final_draft(session, draft, expected_basis=draft["basis"])
    edit_final_note(session, "independent", "独立附注保留。")
    edit_final_note(session, "dependent", "依赖 Skill 的附注。", ["binding-1"])

    session.set_skill_state(status="skipped", basis=basis, bindings=[])
    rebuilt = build_final_draft(session)

    assert rebuilt["content"]["skill_contributions"] == []
    assert [row["text"] for row in rebuilt["content"]["user_notes"]] == ["独立附注保留。"]
    assert any(row["note_id"] == "dependent" for row in rebuilt["unapplied_edits"])
    stage_final_draft(session, rebuilt, expected_basis=rebuilt["basis"])
    assert "按方法整理规格" not in session.final_result["canonical_body"]


def test_m2_suggestion_accept_and_reject_are_explicit() -> None:
    accepted_session = confirmed_plan_session()
    accepted_session.final_result = build_final_draft(accepted_session)
    old_revision = accepted_session.final_result["revision"]

    decide_m2_suggestion(accepted_session, "sg1", "accepted")

    accepted = accepted_session.final_result
    assert accepted["status"] == "draft"
    assert accepted["revision"] == old_revision + 1
    assert accepted["confirmed_revision"] is None
    assert [row["source_suggestion_id"] for row in accepted["content"]["accepted_additions"]] == ["sg1"]
    assert accepted["content"]["pending_changes"] == []
    assert "可增加复习日" in accepted["canonical_body"]
    assert accepted["suggestion_decisions"][0]["decision"] == "accepted"
    with pytest.raises(DeliveryValidationError):
        decide_m2_suggestion(accepted_session, "sg1", "rejected")

    rejected_session = confirmed_plan_session()
    rejected_session.final_result = build_final_draft(rejected_session)
    decide_m2_suggestion(rejected_session, "sg1", "rejected")
    rejected = rejected_session.final_result
    assert rejected["content"]["accepted_additions"] == []
    assert rejected["content"]["pending_changes"][0]["decision"] == "rejected"
    assert "未采纳：可增加复习日" in rejected["canonical_body"]


def test_scope_changing_suggestion_cannot_be_accepted_in_final_page() -> None:
    session = confirmed_plan_session()
    session.plan["content"]["suggestions"][0]["kind"] = "scope_change"
    session.plan["content"]["suggestions"][0]["requires_user_confirmation"] = True
    session.final_result = build_final_draft(session)
    before = session.to_dict()

    with pytest.raises(DeliveryValidationError, match="返回需求／方案流程"):
        decide_m2_suggestion(session, "sg1", "accepted")

    assert session.to_dict() == before


def _session_with_bound_prerequisite(status: str, fallback_actions: list[str]) -> SessionState:
    session = confirmed_plan_session()
    record = {
        "skill_id": "local-method",
        "record_hash": "record-hash",
        "method_adaptation_allowed": True,
        "capabilities": [],
        "adaptation_prerequisites": [
            {"prerequisite_id": "adapt-material", "description": "有可核对的领域材料。"}
        ],
    }
    basis = {
        "task_id": session.task_id,
        "requirement_version": session.requirement_version,
        "plan_id": session.plan["plan_id"],
        "plan_version": session.plan["plan_version"],
    }
    binding = {
        "binding_id": "binding-prerequisite",
        "skill_id": "local-method",
        "record_hash": "record-hash",
        "record_snapshot": record,
        "key_work_id": "k1",
        "step_ids": ["s1"],
        "usage_mode": "method_adaptation",
        "precondition_assessments": [
            {"prerequisite_id": "adapt-material", "status": status, "source": "user_reported"}
        ],
    }
    session.set_skill_state(status="selected", basis=basis, bindings=[binding])
    contribution = {
        "binding_id": binding["binding_id"],
        "origin_binding_ids": [binding["binding_id"]],
        "step_id": "s1",
        "method_actions": ["按已确认材料整理领域术语。"],
        "planned_inputs": ["已确认需求"],
        "expected_outputs": ["术语清单"],
        "checkpoints": ["术语有来源依据"],
        "prerequisite_ids": ["adapt-material"],
        "fallback_actions": fallback_actions,
    }
    draft = build_final_draft(session, selected_contributions=[contribution])
    stage_final_draft(session, draft, expected_basis=draft["basis"])
    return session


def _attach_m4_change(session: SessionState, change: dict) -> None:
    result = session.final_result
    result["generation_request_id"] = "m4-run-fixture"
    pending = deepcopy(change)
    pending["generation_request_id"] = result["generation_request_id"]
    pending["text"] = pending.pop("description")
    result["content"]["pending_changes"].append(pending)
    result.setdefault("change_decisions", []).append({
        "generation_request_id": result["generation_request_id"],
        "change_id": pending["change_id"],
        "decision": "pending",
        "decided_by": "workflow",
        "reason": "M4 首次接收，等待用户决定。",
    })
    result.setdefault("review_required_ids", []).append(
        f"m4-change:{result['generation_request_id']}:{pending['change_id']}"
    )
    result["canonical_body"] = render_canonical_body(result["content"])
    result["body_sha256"] = hashlib.sha256(result["canonical_body"].encode("utf-8")).hexdigest()


def _m4_change(change_id: str = "change-1", *, bindings: list[str] | None = None, hard: bool = False) -> dict:
    return {
        "change_id": change_id,
        "binding_ids": list(bindings or ["binding-prerequisite"]),
        "kind": "assumption",
        "description": "增加术语核对记录。",
        "reason": "帮助保持领域用语一致。",
        "affects_hard_constraints": hard,
        "decision": "pending",
    }


def test_unknown_skill_prerequisite_is_explained_without_blocking_delivery() -> None:
    session = _session_with_bound_prerequisite("unknown", ["先只整理用户已提供的术语，缺失材料标为待补充。"])
    assert confirm_final(session) == session.final_result["revision"]

    satisfied = _session_with_bound_prerequisite("satisfied", [])
    assert confirm_final(satisfied) == satisfied.final_result["revision"]

    blocked = _session_with_bound_prerequisite("unknown", [])
    assert "待核对前提" in blocked.final_result["canonical_body"]
    assert confirm_final(blocked) == blocked.final_result["revision"]


def test_incompatible_skill_prerequisite_remains_a_reference_for_downstream_review() -> None:
    session = _session_with_bound_prerequisite("satisfied", [])
    session.skill_state["bindings"][0]["precondition_assessments"][0]["status"] = "incompatible"
    draft = build_final_draft(session)
    stage_final_draft(session, draft, expected_basis=draft["basis"])
    assert "incompatible" in session.final_result["canonical_body"]
    assert confirm_final(session) == session.final_result["revision"]


def test_skill_prerequisite_status_requires_a_recorded_source() -> None:
    session = _session_with_bound_prerequisite("satisfied", [])
    session.skill_state["bindings"][0]["precondition_assessments"][0].pop("source")

    with pytest.raises(DeliveryValidationError, match="来源"):
        confirm_final(session)


def test_m4_change_acceptance_is_recorded_and_applied_as_addition() -> None:
    session = _session_with_bound_prerequisite("satisfied", [])
    _attach_m4_change(session, _m4_change())
    revision = session.final_result["revision"]

    decide_m4_change(session, "change-1", "accepted")

    result = session.final_result
    assert result["status"] == "draft"
    assert result["revision"] == revision + 1
    assert result["confirmed_revision"] is None
    assert all(row.get("change_id") != "change-1" for row in result["content"]["pending_changes"])
    assert result["content"]["accepted_additions"][-1] == {
            "source_change_id": "change-1",
            "source_change_generation_request_id": "m4-run-fixture",
            "text": "增加术语核对记录。",
        "reason": "帮助保持领域用语一致。",
        "origin_binding_ids": ["binding-prerequisite"],
    }
    assert result["change_decisions"][-1]["generation_request_id"] == "m4-run-fixture"
    assert result["change_decisions"][-1]["change_id"] == "change-1"
    assert result["change_decisions"][-1]["decision"] == "accepted"
    assert len(result["change_decisions"]) == 1
    assert result["change_decisions"][0]["decided_by"] == "user_ui"
    assert result["review_required_ids"] == []
    assert "增加术语核对记录。" in result["canonical_body"]


def test_m4_change_rejection_keeps_explicit_decision_without_applying() -> None:
    session = _session_with_bound_prerequisite("satisfied", [])
    _attach_m4_change(session, _m4_change())
    revision = session.final_result["revision"]

    decide_m4_change(session, "change-1", "rejected")

    result = session.final_result
    assert result["revision"] == revision + 1
    assert result["confirmed_revision"] is None
    assert result["content"]["accepted_additions"] == []
    rejected = next(row for row in result["content"]["pending_changes"] if row.get("change_id") == "change-1")
    assert rejected["decision"] == "rejected"
    assert result["change_decisions"][-1]["decision"] == "rejected"
    assert result["review_required_ids"] == []
    assert "未采纳：增加术语核对记录。" in result["canonical_body"]


def test_rejected_m4_change_disables_dependent_actions_and_uses_fallback() -> None:
    session = _session_with_bound_prerequisite("satisfied", [])
    _attach_m4_change(session, _m4_change())
    contribution = session.final_result["content"]["skill_contributions"][0]
    contribution["proposed_change_ids"] = ["change-1"]
    contribution["method_actions"] = ["依据新增术语核对记录执行方法。"]
    contribution["fallback_actions"] = ["变化被拒绝时只保留基础核对步骤。"]
    contribution["m4_dependencies"] = [{"generation_request_id": "m4-run-fixture", "change_id": "change-1"}]
    session.final_result["canonical_body"] = render_canonical_body(session.final_result["content"])
    session.final_result["body_sha256"] = hashlib.sha256(session.final_result["canonical_body"].encode("utf-8")).hexdigest()

    decide_m4_change(session, "change-1", "rejected")

    content = session.final_result["content"]
    assert "依据新增术语核对记录执行方法。" not in session.final_result["canonical_body"]
    assert content["skill_contributions"][0]["method_actions"] == ["变化被拒绝时只保留基础核对步骤。"]
    assert confirm_final(session) == session.final_result["revision"]


def test_rejected_noncritical_m4_change_without_fallback_is_deferred() -> None:
    session = _session_with_bound_prerequisite("satisfied", [])
    _attach_m4_change(session, _m4_change())
    contribution = session.final_result["content"]["skill_contributions"][0]
    contribution["proposed_change_ids"] = ["change-1"]
    contribution["method_actions"] = ["依据新增术语核对记录执行方法。"]
    contribution["fallback_actions"] = []
    contribution["m4_dependencies"] = [{"generation_request_id": "m4-run-fixture", "change_id": "change-1"}]
    session.final_result["canonical_body"] = render_canonical_body(session.final_result["content"])
    session.final_result["body_sha256"] = hashlib.sha256(session.final_result["canonical_body"].encode("utf-8")).hexdigest()

    decide_m4_change(session, "change-1", "rejected")

    assert session.final_result["content"]["skill_contributions"][0]["method_actions"] == []
    assert session.final_result["review_required_ids"] == []
    assert confirm_final(session) == session.final_result["revision"]
    assert "使用时补充的后置事项" in session.final_result["canonical_body"]
    assert "增加术语核对记录。" in session.final_result["canonical_body"]

    session.set_skill_state(
        status="skipped",
        basis={
            "task_id": session.task_id,
            "requirement_version": session.requirement_version,
            "plan_id": session.plan["plan_id"],
            "plan_version": session.plan["plan_version"],
        },
        bindings=[],
    )
    rebuilt = build_final_draft(session)
    stage_final_draft(session, rebuilt, expected_basis=rebuilt["basis"])
    assert confirm_final(session) == session.final_result["revision"]


def test_pending_noncritical_m4_change_is_deferred_to_final_prompt() -> None:
    session = _session_with_bound_prerequisite("satisfied", [])
    _attach_m4_change(session, _m4_change())

    # A method-level suggestion produced after the confirmed plan is useful
    # context for the downstream user, but it must not reopen the upstream gate.
    revision = confirm_final(session)

    assert revision == session.final_result["revision"]
    assert "增加术语核对记录。" in session.final_result["canonical_body"]
    assert "使用时补充的后置事项" in session.final_result["canonical_body"]


def test_pending_hard_constraint_m4_change_is_deferred_without_adoption() -> None:
    session = _session_with_bound_prerequisite("satisfied", [])
    _attach_m4_change(session, _m4_change(hard=True))

    assert confirm_final(session) == session.final_result["revision"]
    assert "增加术语核对记录。" in session.final_result["canonical_body"]
    assert "若要采纳，须先回到上游确认硬约束" in session.final_result["canonical_body"]


def test_rejected_m4_fallback_survives_save_and_reopen(tmp_path) -> None:
    session = _session_with_bound_prerequisite("satisfied", [])
    _attach_m4_change(session, _m4_change())
    contribution = session.final_result["content"]["skill_contributions"][0]
    contribution["proposed_change_ids"] = ["change-1"]
    contribution["method_actions"] = ["依据新增术语核对记录执行方法。"]
    contribution["fallback_actions"] = ["变化被拒绝时只保留基础核对步骤。"]
    contribution["m4_dependencies"] = [{"generation_request_id": "m4-run-fixture", "change_id": "change-1"}]
    session.final_result["canonical_body"] = render_canonical_body(session.final_result["content"])
    session.final_result["body_sha256"] = hashlib.sha256(session.final_result["canonical_body"].encode("utf-8")).hexdigest()

    decide_m4_change(session, "change-1", "rejected")
    saved = save_session(session, tmp_path / "m4-rejected-fallback.json")
    reopened = load_session(saved)

    contribution = reopened.final_result["content"]["skill_contributions"][0]
    assert contribution["method_actions"] == ["变化被拒绝时只保留基础核对步骤。"]
    assert contribution["applied_fallbacks"][0]["change_id"] == "change-1"
    assert "依据新增术语核对记录执行方法。" not in reopened.final_result["canonical_body"]
    assert confirm_final(reopened) == reopened.final_result["revision"]


def test_m4_workflow_followups_can_be_decided_one_at_a_time() -> None:
    session = _session_with_bound_prerequisite("satisfied", [])
    _attach_m4_change(session, _m4_change("change-1"))
    _attach_m4_change(session, _m4_change("change-2"))

    decide_m4_change(session, "change-1", "rejected")

    assert session.final_result["review_required_ids"] == ["m4-change:m4-run-fixture:change-2"]
    assert any(
        row.get("generation_request_id") == "m4-run-fixture"
        and row.get("change_id") == "change-2"
        and row.get("decision") == "pending"
        for row in session.final_result["change_decisions"]
    )
    assert confirm_final(session) == session.final_result["revision"]
    assert "增加术语核对记录。" in session.final_result["canonical_body"]

    decide_m4_change(session, "change-2", "accepted")
    assert session.final_result["review_required_ids"] == []
    assert confirm_final(session) == session.final_result["revision"]


def test_m4_decision_does_not_remove_unrelated_review_blockers() -> None:
    session = _session_with_bound_prerequisite("satisfied", [])
    _attach_m4_change(session, _m4_change())
    session.final_result["review_required_ids"].append("unrelated-review")
    before = session.to_dict()

    with pytest.raises(DeliveryValidationError, match="复核"):
        decide_m4_change(session, "change-1", "rejected")

    assert session.to_dict() == before


def test_m4_change_that_affects_hard_constraints_cannot_be_accepted() -> None:
    session = _session_with_bound_prerequisite("satisfied", [])
    _attach_m4_change(session, _m4_change(hard=True))
    before = session.to_dict()

    with pytest.raises(DeliveryValidationError, match="硬约束|上游"):
        decide_m4_change(session, "change-1", "accepted")

    assert session.to_dict() == before


def test_rebuild_keeps_shared_skill_content_for_surviving_binding() -> None:
    session = confirmed_plan_session()
    basis = {
        "task_id": session.task_id,
        "requirement_version": session.requirement_version,
        "plan_id": session.plan["plan_id"],
        "plan_version": session.plan["plan_version"],
    }
    bindings = [
        {
            "binding_id": binding_id,
            "skill_id": skill_id,
            "record_hash": f"hash-{binding_id}",
            "record_snapshot": {
                "skill_id": skill_id,
                "record_hash": f"hash-{binding_id}",
                "method_adaptation_allowed": True,
                "capabilities": [],
                "adaptation_prerequisites": [],
            },
            "key_work_id": "k1",
            "step_ids": ["s1"],
            "usage_mode": "method_adaptation",
            "precondition_assessments": [],
        }
        for binding_id, skill_id in (("binding-a", "method-a"), ("binding-b", "method-b"))
    ]
    session.set_skill_state(status="selected", basis=basis, bindings=bindings)
    shared = {
        "origin_binding_ids": ["binding-a", "binding-b"],
        "step_id": "s1",
        "method_actions": ["共同核对术语和范围。"],
        "planned_inputs": ["已确认需求"],
        "expected_outputs": ["核对记录"],
        "checkpoints": ["需求与术语一致"],
        "prerequisite_ids": [],
        "fallback_actions": [],
    }
    addition = {
        "source_change_id": "shared-change",
        "text": "共同记录必要术语。",
        "origin_binding_ids": ["binding-a", "binding-b"],
    }
    draft = build_final_draft(
        session,
        selected_contributions=[shared],
        accepted_additions=[addition],
    )
    stage_final_draft(session, draft, expected_basis=draft["basis"])
    _attach_m4_change(session, _m4_change("shared-pending", bindings=["binding-a", "binding-b"]))
    _attach_m4_change(session, _m4_change("solo-pending", bindings=["binding-a"]))

    session.set_skill_state(status="selected", basis=basis, bindings=[bindings[1]])
    rebuilt = build_final_draft(session)

    assert len(rebuilt["content"]["skill_contributions"]) == 1
    assert rebuilt["content"]["skill_contributions"][0]["origin_binding_ids"] == ["binding-b"]
    assert rebuilt["content"]["accepted_additions"][0]["origin_binding_ids"] == ["binding-b"]
    m4_changes = {
        row["change_id"]: row for row in rebuilt["content"]["pending_changes"] if row.get("change_id")
    }
    assert m4_changes["shared-pending"]["binding_ids"] == ["binding-b"]
    assert "solo-pending" not in m4_changes
