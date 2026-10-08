from __future__ import annotations

import json
from pathlib import Path

import pytest

from promptsmith.api import ApiResult
from promptsmith.m1 import M1Assets, M1ValidationError, build_m1_input, parse_m1_response
from promptsmith.session import SessionState
from promptsmith.workflow import Phase12Workflow


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "resources" / "prompts"


def _base(payload: dict) -> dict:
    return {
        "schema_version": payload["schema_version"],
        "request_id": payload["request_id"],
        "task_id": payload["task_id"],
        "base_version": payload["base_version"],
        "status": "ok",
        "error": None,
        "category": {"primary": "learning", "secondary": [], "reason": "学习任务。"},
        "proposals": [],
        "conflicts": [],
        "review_item_ids": [],
        "gap_updates": [],
        "question_reopens": [],
        "gaps": [],
        "questions": [],
        "readiness": {
            "goal_identified": True,
            "deliverable_identified": True,
            "blocking_gap_ids": [],
            "reason": "目标和结果已明确。",
        },
        "next_action": "review_requirements",
        "assistant_text": "请核对整理结果。",
    }


def _jgs_partial(payload: dict) -> dict:
    result = _base(payload)
    result["gaps"] = [{
        "gap_id": "g-jgs",
        "field": "goal",
        "scope": "JGS术语含义",
        "description": "JGS具体指什么仍会改变讲解方向。",
        "importance": "blocking_direction",
        "origin": "ambiguous",
        "source_refs": [],
        "depends_on": [],
    }]
    result["questions"] = [{
        "question_id": "q-jgs",
        "gap_id": "g-jgs",
        "field": "goal",
        "scope": "JGS术语含义",
        "text": "在数值分析语境下，你希望我先列出可能的 JGS 含义供你确认吗？",
        "options": [],
        "reason": "具体含义会改变后续讲解方向。",
        "depends_on": [],
    }]
    result["readiness"]["blocking_gap_ids"] = ["g-jgs"]
    result["readiness"]["reason"] = "讲解方向明确，但术语含义还需要核对。"
    result["next_action"] = "ask"
    result["model_judgment"] = {
        "answer_assessment": "partial",
        "critical_gap_ids": ["g-jgs"],
        "continue_interview": True,
        "confidence": "high",
        "reason": "用户补充了领域线索，但还没有确定 JGS 的具体对象。",
    }
    return result


def test_model_judgment_cannot_claim_ready_while_requesting_more_information() -> None:
    session = SessionState.new()
    session.set_task("讲解 JGS，面向零基础学生")
    payload = build_m1_input(session, "req-authority-contradiction")
    result = _jgs_partial(payload)
    result["next_action"] = "review_requirements"

    with pytest.raises(M1ValidationError, match="模型判断与需求复核步骤不一致"):
        parse_m1_response(json.dumps(result, ensure_ascii=False), payload, M1Assets.load(DESIGN).output_schema)


def test_old_question_controls_do_not_block_model_led_follow_up() -> None:
    session = SessionState.new()
    session.set_task("讲解 JGS，面向零基础学生")
    session.control.update({"max_questions": 0, "remaining_rounds": 0, "allow_questions": False})
    payload = build_m1_input(session, "req-authority-budget")
    result = _jgs_partial(payload)

    parsed = parse_m1_response(
        json.dumps(result, ensure_ascii=False), payload, M1Assets.load(DESIGN).output_schema
    )

    assert parsed["next_action"] == "ask"
    assert parsed["model_judgment"]["continue_interview"] is True


def test_legacy_current_response_gets_compatible_model_judgment() -> None:
    session = SessionState.new()
    session.set_task("整理一个学习任务")
    payload = build_m1_input(session, "req-authority-default")
    result = _base(payload)
    result.pop("model_judgment", None)

    parsed = parse_m1_response(
        json.dumps(result, ensure_ascii=False), payload, M1Assets.load(DESIGN).output_schema
    )

    assert parsed["model_judgment"]["answer_assessment"] == "sufficient"
    assert parsed["model_judgment"]["continue_interview"] is False


class _InputErrorClient:
    def __init__(self, raw: str):
        self.raw = raw
        self.calls = 0

    def complete_json(self, _system_prompt, _payload, _schema):
        self.calls += 1
        return ApiResult(
            content=self.raw,
            latency_ms=5,
            usage={"total_tokens": 8},
            response_id=f"semantic-{self.calls}",
            model="fixture-model",
        )


def test_valid_semantic_input_error_never_becomes_user_visible_call_failure(tmp_path) -> None:
    session = SessionState.new()
    session.set_task("讲解 JGS，面向零基础学生")
    workflow = Phase12Workflow(session, M1Assets.load(DESIGN), tmp_path)
    payload = workflow.prepare_m1("req-authority-input-error", current_date="2026-10-06")
    result = _base(payload)
    result.update(
        status="input_error",
        error={"code": "invalid_input", "message": "无法判断 JGS 的具体含义"},
        category={"primary": "general", "secondary": [], "reason": "需要继续核对"},
        gaps=[],
        questions=[],
        readiness={
            "goal_identified": False,
            "deliverable_identified": False,
            "blocking_gap_ids": [],
            "reason": "需要继续核对",
        },
        next_action="pause_with_unknowns",
        assistant_text="我还需要继续核对 JGS。",
    )
    outcome = workflow.invoke_m1(
        payload,
        _InputErrorClient(json.dumps(result, ensure_ascii=False)),
        protocol="fixture",
        configured_model="fixture-model",
    )

    assert outcome.recovery_mode == "program_recovery"
    assert outcome.parsed["status"] == "ok"
    assert outcome.parsed["next_action"] == "ask"
    assert session.errors == []


def test_v021_correction_prompt_makes_model_judgment_mandatory() -> None:
    prompt = Phase12Workflow._m1_correction_prompt(
        "BASE", "模型输出缺少判断字段", attempt=2
    )

    assert "必须完整填写 model_judgment" in prompt
    assert "answer_assessment" in prompt
    assert "continue_interview" in prompt
    assert "next_action" in prompt


def test_v021_semantic_bridge_requires_continuable_normal_interview() -> None:
    prompt = Phase12Workflow._m1_semantic_bridge_prompt(
        "BASE", "把语义不足误写成 input_error", attempt=2
    )

    assert "必须改为 status=ok" in prompt
    assert "必须完整填写 model_judgment" in prompt
    assert "continue_interview=true" in prompt
    assert "next_action=ask" in prompt
    assert "只有用户明确要求停止" in prompt
