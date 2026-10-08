from __future__ import annotations

import json
from pathlib import Path

from promptsmith.api import ApiResult
from promptsmith.m1 import M1Assets, build_m1_input
from promptsmith.session import SessionState
from promptsmith.workflow import Phase12Workflow


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "resources" / "prompts"


class _SequenceClient:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.prompts: list[str] = []

    def complete_json(self, system_prompt, payload, schema):
        self.prompts.append(system_prompt)
        return ApiResult(
            content=self.responses.pop(0),
            latency_ms=10,
            usage={"total_tokens": 12},
            response_id=f"bridge-{len(self.prompts)}",
            model="fixture-model",
        )


def _legacy_semantic_error(payload: dict) -> dict:
    return {
        "schema_version": payload["schema_version"],
        "request_id": payload["request_id"],
        "task_id": payload["task_id"],
        "base_version": payload["base_version"],
        "status": "input_error",
        "error": {"code": "context_incomplete", "message": "无法确定 JGS 的含义"},
        "category": {"primary": "general", "secondary": [], "reason": "需要继续核对"},
        "proposals": [],
        "conflicts": [],
        "review_item_ids": [],
        "gap_updates": [],
        "question_reopens": [],
        "gaps": [],
        "questions": [],
        "readiness": {
            "goal_identified": False,
            "deliverable_identified": False,
            "blocking_gap_ids": [],
            "reason": "需要继续核对",
        },
        "next_action": "pause_with_unknowns",
        "assistant_text": "我还需要继续核对。",
    }


def test_m1_input_declares_model_judgment_as_quality_authority() -> None:
    session = SessionState.new()
    session.set_task("讲解 JGS，面向零基础学习者")
    session.control["max_questions"] = 0
    session.control["remaining_rounds"] = 0
    session.control["allow_questions"] = False

    payload = build_m1_input(session, "req-quality-policy")

    assert payload["control"]["quality_policy"] == "model_judgment_first"


def test_semantic_input_error_uses_a_context_bridge_prompt(tmp_path) -> None:
    session = SessionState.new()
    session.set_task("讲解 JGS，面向零基础学习者")
    workflow = Phase12Workflow(session, M1Assets.load(DESIGN), tmp_path)
    payload = workflow.prepare_m1("req-semantic-bridge", current_date="2026-10-06")
    client = _SequenceClient([
        json.dumps(_legacy_semantic_error(payload), ensure_ascii=False),
        json.dumps(_legacy_semantic_error(payload), ensure_ascii=False),
        json.dumps(_legacy_semantic_error(payload), ensure_ascii=False),
    ])

    outcome = workflow.invoke_m1(
        payload,
        client,
        protocol="fixture",
        configured_model="fixture-model",
    )

    assert outcome.recovery_mode == "program_recovery"
    assert len(client.prompts) == 3
    assert "语义桥接" in client.prompts[1]
    assert "不要把语义不完整当作 input_error" in client.prompts[1]
