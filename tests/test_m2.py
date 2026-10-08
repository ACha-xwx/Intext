from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from promptsmith.m2 import M2Assets, M2ValidationError, apply_m2_response, build_m2_input, parse_m2_response
from promptsmith.session import SessionState, SessionStateError, StaleResponseError
from promptsmith.storage import load_session, save_session


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "resources" / "prompts"
ASSETS = M2Assets.load(DESIGN)


def test_m2_example_fixtures_are_schema_valid_and_marked_as_manual() -> None:
    from jsonschema import Draft202012Validator

    example_dir = DESIGN / "examples_m2"
    payload = json.loads((example_dir / "01_报名网站.input.json").read_text(encoding="utf-8"))
    normal = json.loads(
        (example_dir / "01_报名网站.output.fixture.json").read_text(encoding="utf-8")
    )
    error = json.loads(
        (example_dir / "02_结构化错误.output.fixture.json").read_text(encoding="utf-8")
    )
    metadata = json.loads((example_dir / "fixture.meta.json").read_text(encoding="utf-8"))

    Draft202012Validator(ASSETS.input_schema).validate(payload)
    Draft202012Validator(ASSETS.output_schema).validate(normal)
    Draft202012Validator(ASSETS.output_schema).validate(error)
    assert metadata["evidence_type"] == "manual_fixture"
    assert metadata["real_model_call"] is False


def requirement(item_id: str, field: str, text: str, *, strength: str = "hard") -> dict:
    return {
        "item_id": item_id,
        "field": field,
        "text": text,
        "kind": "user_decision",
        "strength": strength,
        "scope": "整体任务",
        "source_refs": [],
        "depends_on": [],
        "confirmation": "confirmed",
    }


def confirmed_session(category: str = "coding", *, with_unknown: bool = True) -> SessionState:
    session = SessionState.new()
    session.set_task("制作一个活动报名网站，供课堂演示，不做付款。")
    session.selected_category = category
    session.requirements = [
        requirement("r1", "deliverable", "一个可演示的活动报名网站"),
        requirement("r2", "constraints", "不实现付款功能"),
        requirement("r3", "use_context", "用于课堂演示", strength="preference"),
    ]
    if with_unknown:
        session.gaps = [
            {
                "gap_id": "g1",
                "field": "runtime",
                "scope": "部署方式",
                "description": "最终部署位置尚未决定。",
                "importance": "can_defer",
                "origin": "user_unsure",
                "source_refs": [],
                "depends_on": ["r1"],
            }
        ]
    session.analysis_basis_version = session.requirement_version
    session.confirm_requirements()
    return session


def valid_result(payload: dict) -> dict:
    requirement_ids = [row["item_id"] for row in payload["requirements"]]
    return {
        "schema_version": "m2.v0.1",
        "request_id": payload["request_id"],
        "task_id": payload["task_id"],
        "source_requirements_version": payload["source_requirements_version"],
        "status": "ok",
        "error": None,
        "plan": {
            "goal": {
                "summary": "完成一个能展示报名主流程的网站。",
                "audience": "课堂同学与老师",
                "scope": "活动浏览、报名提交和结果确认；不含付款。",
            },
            "requirement_coverage": [
                {
                    "requirement_id": item_id,
                    "summary": f"方案承接 {item_id}",
                    "step_ids": ["s1"],
                    "deliverable_ids": ["d1"],
                    "criterion_ids": ["c1"],
                }
                for item_id in requirement_ids
            ],
            "steps": [
                {
                    "step_id": "s1",
                    "order": 1,
                    "title": "实现并检查报名流程",
                    "purpose": "形成可演示的完整主流程。",
                    "inputs": ["已确认需求"],
                    "actions": ["实现活动列表", "实现报名表单", "检查不含付款入口"],
                    "outputs": ["可运行网站"],
                    "completion_criteria": ["能够完成一次报名演示"],
                    "depends_on_step_ids": [],
                    "requirement_ids": requirement_ids,
                }
            ],
            "deliverables": [
                {
                    "deliverable_id": "d1",
                    "name": "活动报名网站",
                    "description": "覆盖课堂演示所需的活动浏览和报名。",
                    "step_ids": ["s1"],
                    "requirement_ids": requirement_ids,
                }
            ],
            "completion_criteria": [
                {
                    "criterion_id": "c1",
                    "text": "网站能演示报名流程，且没有付款功能。",
                    "requirement_ids": requirement_ids,
                }
            ],
            "unresolved_items": [
                {
                    "unresolved_id": "u1",
                    "source_gap_id": row["unresolved_id"],
                    "description": row["description"],
                    "impact": "不影响本地演示，但影响最终发布步骤。",
                    "continuable_work": "先完成本地可运行版本。",
                    "confirm_by": "准备发布前",
                }
                for row in payload["unresolved_items"]
            ],
            "suggestions": [],
            "key_work": [
                {
                    "key_work_id": "k1",
                    "title": "报名主流程实现",
                    "step_ids": ["s1"],
                    "goal": "确保核心演示链路可用。",
                    "inputs": ["已确认需求"],
                    "outputs": ["可演示网站"],
                    "requirement_ids": requirement_ids,
                    "depends_on_key_work_ids": [],
                    "checkpoints": ["报名提交成功", "页面中没有付款入口"],
                }
            ],
        },
    }


def parse_for(session: SessionState, request_id: str = "m2-request") -> tuple[dict, dict]:
    payload = build_m2_input(session, request_id, current_date="2026-09-23")
    result = valid_result(payload)
    parsed = parse_m2_response(json.dumps(result, ensure_ascii=False), payload, ASSETS.output_schema)
    return payload, parsed


@pytest.mark.parametrize(
    "mutate",
    [
        lambda s: setattr(s, "confirmed_requirements_version", None),
        lambda s: s.pending_proposals.append({"proposal_id": "p1"}),
        lambda s: s.open_conflicts.append({"conflict_id": "c1"}),
        lambda s: s.pending_review_item_ids.append("r1"),
        lambda s: s.gaps.append(
            {
                "gap_id": "blocking",
                "field": "goal",
                "scope": "整体",
                "description": "方向未知",
                "importance": "blocking_direction",
                "origin": "missing",
                "source_refs": [],
                "depends_on": [],
            }
        ),
    ],
)
def test_m2_entry_rejects_unready_requirements_before_starting_request(mutate) -> None:
    session = confirmed_session()
    mutate(session)

    with pytest.raises(SessionStateError):
        build_m2_input(session, "blocked-m2", current_date="2026-09-23")

    assert "blocked-m2" not in session.pending_requests


def test_m2_input_contains_confirmed_requirements_unknowns_and_category() -> None:
    session = confirmed_session("presentation")

    payload = build_m2_input(session, "m2-input", current_date="2026-09-23")

    assert payload["source_requirements_version"] == session.requirement_version
    assert payload["confirmed_requirements_version"] == session.requirement_version
    assert [row["item_id"] for row in payload["requirements"]] == ["r1", "r2", "r3"]
    assert payload["unresolved_items"][0]["unresolved_id"] == "g1"
    assert payload["category"]["primary"] == "presentation"
    assert payload["category"]["config_version"]


def test_m2_input_adapts_unspecified_strength_without_mutating_requirement() -> None:
    session = confirmed_session()
    session.requirements[0]["strength"] = "unspecified"

    payload = build_m2_input(session, "m2-unspecified-strength", current_date="2026-09-23")

    assert payload["requirements"][0]["strength"] == "preference"
    assert session.requirements[0]["strength"] == "unspecified"


@pytest.mark.parametrize("tamper", ["missing_coverage", "bad_reference", "cycle"])
def test_m2_semantic_validation_rejects_invalid_plan(tamper: str) -> None:
    session = confirmed_session()
    payload = build_m2_input(session, f"invalid-{tamper}", current_date="2026-09-23")
    result = valid_result(payload)
    if tamper == "missing_coverage":
        result["plan"]["requirement_coverage"].pop()
    elif tamper == "bad_reference":
        result["plan"]["steps"][0]["requirement_ids"] = ["missing-r"]
    elif tamper == "cycle":
        step = deepcopy(result["plan"]["steps"][0])
        step.update(step_id="s2", order=2, depends_on_step_ids=["s1"])
        result["plan"]["steps"][0]["depends_on_step_ids"] = ["s2"]
        result["plan"]["steps"].append(step)

    with pytest.raises(M2ValidationError):
        parse_m2_response(json.dumps(result, ensure_ascii=False), payload, ASSETS.output_schema)


def test_m2_missing_unknown_is_restored_from_input():
    session = confirmed_session()
    payload = build_m2_input(session, "missing-unknown")
    result = valid_result(payload)
    result["plan"]["unresolved_items"] = []
    parsed = parse_m2_response(json.dumps(result), payload, ASSETS.output_schema)
    assert parsed["plan"]["unresolved_items"][0]["source_gap_id"] == "g1"
    assert parsed["plan"]["unresolved_items"][0]["description"] == payload["unresolved_items"][0]["description"]


def test_structured_error_branch_is_valid_but_cannot_be_applied() -> None:
    session = confirmed_session()
    payload = build_m2_input(session, "m2-error", current_date="2026-09-23")
    result = {
        "schema_version": "m2.v0.1",
        "request_id": payload["request_id"],
        "task_id": payload["task_id"],
        "source_requirements_version": payload["source_requirements_version"],
        "status": "error",
        "plan": None,
        "error": {
            "code": "insufficient_input",
            "message": "无法形成完整方案。",
            "related_input_ids": ["r1"],
            "recovery_action": "返回需求页补充交付范围。",
        },
    }

    parsed = parse_m2_response(json.dumps(result, ensure_ascii=False), payload, ASSETS.output_schema)
    before = deepcopy(session.plan)
    with pytest.raises(SessionStateError, match="无法形成"):
        apply_m2_response(session, payload, parsed)
    assert session.plan == before


def test_m2_plan_draft_edit_review_confirm_and_round_trip(tmp_path: Path) -> None:
    session = confirmed_session()
    payload, parsed = parse_for(session)

    apply_m2_response(session, payload, parsed)

    assert session.plan["status"] == "draft"
    assert session.plan["source_requirements_version"] == session.requirement_version
    assert session.plan["pending_key_work_review_ids"] == ["k1"]
    original_requirement_version = session.requirement_version
    session.edit_plan_goal("完成一个更清楚的课堂演示报名网站。")
    assert session.requirement_version == original_requirement_version
    assert session.plan["plan_version"] == 2
    assert session.plan["confirmed_plan_version"] is None
    session.mark_key_work_reviewed(["k1"])
    confirmed = session.confirm_plan()
    assert confirmed == session.plan["plan_version"]

    path = save_session(session, tmp_path / "m2-session.json")
    reopened = load_session(path)
    assert reopened.plan == session.plan
    assert reopened.plan["confirmed_plan_version"] == confirmed


def test_regeneration_archives_previous_plan() -> None:
    session = confirmed_session()
    first_payload, first_parsed = parse_for(session, "first")
    apply_m2_response(session, first_payload, first_parsed)
    first_plan_id = session.plan["plan_id"]

    second_payload, second_parsed = parse_for(session, "second")
    apply_m2_response(session, second_payload, second_parsed)

    assert session.plan["plan_id"] != first_plan_id
    assert session.plan_archive[-1]["plan_id"] == first_plan_id
    assert session.plan_archive[-1]["archived_reason"] == "regenerated"


def test_requirement_change_keeps_old_plan_but_marks_it_stale() -> None:
    session = confirmed_session()
    payload, parsed = parse_for(session)
    apply_m2_response(session, payload, parsed)
    session.mark_key_work_reviewed(["k1"])
    session.confirm_plan()
    plan_id = session.plan["plan_id"]

    session.edit_requirement("r2", "首版不实现付款功能")

    assert session.plan["plan_id"] == plan_id
    assert session.plan["status"] == "stale"
    assert session.plan["confirmed_plan_version"] is None


def test_m2_late_response_is_rejected_after_plan_edit() -> None:
    session = confirmed_session()
    first_payload, first_parsed = parse_for(session, "first-plan")
    apply_m2_response(session, first_payload, first_parsed)
    payload = build_m2_input(session, "late-plan", current_date="2026-09-23")
    parsed = parse_m2_response(
        json.dumps(valid_result(payload), ensure_ascii=False), payload, ASSETS.output_schema
    )
    session.edit_plan_goal("用户先修改当前草稿")

    with pytest.raises(StaleResponseError):
        apply_m2_response(session, payload, parsed)


def test_request_connection_version_is_bound_in_program_state() -> None:
    session = confirmed_session()
    payload = build_m2_input(session, "connection-bound", current_date="2026-09-23")

    session.bind_request_connection_version(payload["request_id"], 4)

    assert session.pending_requests[payload["request_id"]]["connection_version"] == 4


def test_step_edit_add_move_and_delete_preserve_requirements_and_plan_rules() -> None:
    session = confirmed_session()
    payload, parsed = parse_for(session)
    apply_m2_response(session, payload, parsed)
    requirement_version = session.requirement_version

    session.edit_plan_step("s1", title="实现课堂报名主流程", purpose="清楚展示报名路径。")
    added = session.add_plan_step("整理演示说明", "准备课堂展示的操作顺序。")
    session.move_plan_step(added, -1)

    assert session.requirement_version == requirement_version
    assert session.plan["plan_version"] == 4
    assert [row["step_id"] for row in session.plan["content"]["steps"]] == [added, "s1"]
    assert session.plan["pending_key_work_review_ids"] == ["k1"]

    session.delete_plan_step(added)
    assert [row["step_id"] for row in session.plan["content"]["steps"]] == ["s1"]


def test_referenced_step_cannot_be_deleted_silently() -> None:
    session = confirmed_session()
    payload, parsed = parse_for(session)
    apply_m2_response(session, payload, parsed)
    session.add_plan_step("补充步骤", "让方案保持至少两个步骤。")

    with pytest.raises(SessionStateError, match="仍被"):
        session.delete_plan_step("s1")


def test_structured_plan_sections_are_editable_without_changing_requirements() -> None:
    session = confirmed_session()
    payload, parsed = parse_for(session)
    apply_m2_response(session, payload, parsed)
    requirement_version = session.requirement_version

    session.edit_plan_goal_details(audience="老师和同学", scope="课堂演示主流程")
    session.edit_plan_section(
        "deliverable", "d1", {"name": "课堂报名演示站", "description": "用于现场演示报名"}
    )
    session.edit_plan_section("criterion", "c1", {"text": "能够现场完成报名且无付款入口"})
    session.edit_plan_section(
        "unresolved",
        "u1",
        {
            "description": "正式部署位置待定",
            "impact": "影响发布方式",
            "continuable_work": "先完成本地版本",
            "confirm_by": "发布前",
        },
    )
    session.edit_plan_section("key_work", "k1", {"title": "演示主流程", "goal": "现场演示成功"})

    assert session.requirement_version == requirement_version
    assert session.plan["content"]["deliverables"][0]["name"] == "课堂报名演示站"
    assert session.plan["content"]["completion_criteria"][0]["text"].startswith("能够现场")
    assert session.plan["content"]["unresolved_items"][0]["confirm_by"] == "发布前"
    assert session.plan["content"]["key_work"][0]["title"] == "演示主流程"
    assert session.plan["pending_key_work_review_ids"] == ["k1"]
