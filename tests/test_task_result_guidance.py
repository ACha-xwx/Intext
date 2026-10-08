"""Regression for a ready JGS interview with no separately tagged result."""
from copy import deepcopy
import json

import pytest

from promptsmith.session import SessionState, SessionStateError
from promptsmith.m1 import M1Assets, M1ValidationError, build_m1_input, parse_m1_response
from promptsmith.storage import load_session, save_session
from tests.test_guided_ui import app
from tests.test_session import m1_result, proposal
from tests.test_ui_reliability import base_result


def goal_only_session():
    state = SessionState.new()
    state.set_task("讲解JGS")
    domain = state._add_source("数值分析领域")
    meaning = state._add_source("用户确认这段理解：JGS 可能指数值分析中的 Jacobi 与 Gauss-Seidel 迭代法")
    rows = [
        proposal("p-goal", "获得关于 JGS 的讲解", field="goal"),
        proposal("p-domain", "JGS 属于数值分析领域", field="goal"),
        proposal("p-meaning", "JGS 可能指数值分析中的 Jacobi 与 Gauss-Seidel 迭代法", field="goal"),
    ]
    for row, sid, quote in zip(rows, ["u1", domain, meaning], [state.task_text, "数值分析领域", state.sources[-1]["text"]]):
        row["source_refs"] = [{"source_id": sid, "quote": quote}]
    rows[1]["kind"] = "user_fact"
    result = m1_result(proposals=rows)
    result["next_action"] = "review_requirements"
    request = state.begin_request("ready-jgs")
    state.stage_m1_result("ready-jgs", request["base_version"], result)
    state.accept_proposals(["p-meaning"])
    return state


def show_session(app, state):
    app.session = app.workflow.session = app.delivery_workflow.session = state
    app.widgets["task_text"].insert("1.0", state.task_text)
    app.refresh()


def test_jgs_missing_result_has_visible_offer_and_one_click_to_m2(app, monkeypatch):
    state = goal_only_session()
    before = deepcopy(state.to_dict())
    show_session(app, state)
    assert state.to_dict() == before
    assert app.primary_action_var.get() == "确认需求并生成方案"
    assert "讲解JGS" in app.preview_note_var.get()
    assert "原话" in app.preview_note_var.get()
    assert "底部" in app.question_context_var.get()
    assert not app.widgets["skip_question_button"].winfo_manager()
    calls = []
    monkeypatch.setattr(app, "start_plan_generation", lambda: calls.append("m2"))
    app.widgets["analyze_button"].invoke()
    assert calls == ["m2"]
    assert not app.errors
    assert state.confirmed_requirements_version == state.requirement_version
    result = next(row for row in state.requirements if row["field"] == "deliverable")
    assert result["text"] == "讲解JGS"
    assert result["kind"] == "user_decision"
    assert not any(row["field"] in {"audience", "length"} for row in state.requirements)
    source = next(row for row in state.sources if row["source_id"] == result["source_refs"][0]["source_id"])
    assert "用户确认" in source["text"] and "讲解JGS" in source["text"]


def test_task_result_requires_explicit_shown_confirmation_and_survives_save(tmp_path):
    state = goal_only_session()
    preview = state.requirements_preview()
    assert preview["suggested_task_result"] == state.task_text
    before = deepcopy(state.to_dict())
    with pytest.raises(SessionStateError, match="结果|交付物"):
        state.confirm_requirements_preview(preview)
    assert state.to_dict() == before
    state.confirm_requirements_preview(preview, use_task_as_deliverable=True)
    path = save_session(state, tmp_path / "jgs.json")
    reopened = load_session(path)
    assert reopened.to_dict() == state.to_dict()
    reopened.validate_m2_entry()


@pytest.mark.parametrize("reason", ["stale", "blocking", "conflict", "no_goal", "result_gap", "truncated"])
def test_task_result_offer_does_not_bypass_unfinished_interview(reason):
    state = goal_only_session()
    if reason == "stale":
        state.analysis_basis_version = None
    elif reason == "blocking":
        state.gaps = [{"gap_id": "g1", "field": "goal", "scope": "整个任务", "description": "JGS 的含义还没有确定", "importance": "blocking_direction", "origin": "ambiguous", "source_refs": [], "depends_on": []}]
    elif reason == "conflict":
        state.open_conflicts = [{"conflict_id": "c1", "existing_item_ids": [], "proposal_ids": ["p-goal"], "description": "讲解对象互相矛盾"}]
    elif reason == "no_goal":
        state.last_readiness["goal_identified"] = False
    elif reason == "result_gap":
        state.gaps = [{"gap_id": "g-result", "field": "deliverable", "scope": "整个任务", "description": "最终需要讲义还是练习题尚未说明", "importance": "can_defer", "origin": "missing", "source_refs": [], "depends_on": []}]
    else:
        state.control["context_coverage"] = "truncated"
    preview = state.requirements_preview()
    assert not preview.get("suggested_task_result")
    before = deepcopy(state.to_dict())
    with pytest.raises(SessionStateError):
        state.confirm_requirements_preview(preview, use_task_as_deliverable=True)
    assert state.to_dict() == before


def test_missing_result_reveals_specific_question_if_model_has_not_identified_it(app):
    state = goal_only_session()
    state.last_readiness["deliverable_identified"] = False
    state.gaps = [{"gap_id": "g-result", "field": "deliverable", "scope": "整个任务", "description": "最终需要什么结果尚未说明", "importance": "can_defer", "origin": "missing", "source_refs": [], "depends_on": []}]
    show_session(app, state)
    assert app._primary_action().kind == "focus_question"
    assert "最后" in app.question_context_var.get()
    assert "结果" in app.question_context_var.get()
    assert "上方" in app.guidance_var.get()


def test_user_can_confirm_original_result_immediately_after_accepting_meaning():
    state = goal_only_session()
    state.last_readiness["deliverable_identified"] = False
    preview = state.requirements_preview()
    assert preview["suggested_task_result"] == "讲解JGS"
    state.confirm_requirements_preview(preview, use_task_as_deliverable=True)
    assert state.last_readiness["deliverable_identified"] is True
    state.validate_m2_entry()


def test_changed_preview_cannot_confirm_old_task_result_offer():
    state = goal_only_session()
    preview = state.requirements_preview()
    state.set_task("解释另一个术语")
    before = deepcopy(state.to_dict())
    with pytest.raises(SessionStateError, match="变化"):
        state.confirm_requirements_preview(preview, use_task_as_deliverable=True)
    assert state.to_dict() == before


@pytest.mark.parametrize("field, accepted", [("deliverable", True), ("constraints", False)])
def test_incremental_old_source_backfill_is_limited_to_missing_result(field, accepted):
    state = goal_only_session()
    state.record_supplement("没有了")
    payload = build_m1_input(state, "backfill-result")
    response = base_result(payload)
    response["proposals"] = [{
        "proposal_id": "p-backfill", "operation": "new", "target_item_id": None,
        "field": field, "text": "关于 JGS 的讲解", "kind": "user_decision",
        "strength": "unspecified", "scope": "整个任务", "depends_on": [],
        "source_refs": [{"source_id": "u1", "quote": "讲解JGS"}],
        "reason": "补记原任务已经说明的结果，不增加新的要求。",
    }]
    raw = json.dumps(response, ensure_ascii=False)
    if accepted:
        parsed = parse_m1_response(raw, payload, M1Assets.load().output_schema, incremental=True)
        assert parsed["proposals"][0]["field"] == "deliverable"
    else:
        with pytest.raises(M1ValidationError, match="来源"):
            parse_m1_response(raw, payload, M1Assets.load().output_schema, incremental=True)
