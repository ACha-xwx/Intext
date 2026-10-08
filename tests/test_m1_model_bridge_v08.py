from __future__ import annotations

import json

import pytest

from promptsmith.m1 import M1Assets, M1ValidationError, build_m1_input, parse_m1_response
from promptsmith.session import SessionState


DESIGN = M1Assets.load()


def _state_with_skipped_question() -> SessionState:
    session = SessionState.new()
    session.set_task("讲解 JGS")
    session.gaps = [{
        "gap_id": "g-meaning",
        "field": "goal",
        "scope": "JGS含义",
        "description": "JGS具体指什么仍不清楚。",
        "importance": "blocking_direction",
        "origin": "missing",
        "source_refs": [],
        "depends_on": [],
    }]
    session.pending_questions = [{
        "question_id": "q-meaning",
        "gap_id": "g-meaning",
        "field": "goal",
        "scope": "JGS含义",
        "text": "JGS具体指什么？",
        "options": [],
        "reason": "影响后续讲解方向。",
        "depends_on": [],
    }]
    session.record_question("q-meaning", "skipped")
    return session


def test_old_saved_session_without_judgment_or_source_count_loads_safely() -> None:
    original = _state_with_skipped_question()
    saved = original.to_dict()
    saved.pop("last_model_judgment", None)
    for row in saved["question_history"]:
        row.pop("recorded_source_count", None)

    restored = SessionState.from_dict(saved)
    payload = build_m1_input(restored, "req-legacy-bridge")

    assert restored.last_model_judgment is None
    assert payload["state"]["question_history"][0]["recorded_source_count"] == len(restored.sources)


def test_model_signal_is_advisory_and_persists_through_save_load() -> None:
    session = SessionState.new()
    session.set_task("讲解 JGS")
    payload = build_m1_input(session, "req-bridge-signal")
    result = {
        "schema_version": payload["schema_version"],
        "request_id": payload["request_id"],
        "task_id": payload["task_id"],
        "base_version": payload["base_version"],
        "status": "ok",
        "error": None,
        "category": {"primary": "learning", "secondary": [], "reason": "学习任务。"},
        "proposals": [{
            "proposal_id": "p-deliverable",
            "operation": "new",
            "target_item_id": None,
            "field": "deliverable",
            "text": "关于 JGS 的讲解",
            "kind": "user_decision",
            "strength": "hard",
            "scope": "当前任务",
            "source_refs": [{"source_id": payload["current_source_id"], "quote": "讲解 JGS"}],
            "depends_on": [],
            "reason": "用户明确提出讲解任务。",
        }],
        "conflicts": [],
        "review_item_ids": [],
        "gap_updates": [],
        "question_reopens": [],
        "gaps": [{
            "gap_id": "g-meaning",
            "field": "goal",
            "scope": "JGS含义",
            "description": "JGS的具体含义仍会改变讲解方向。",
            "importance": "blocking_direction",
            "origin": "ambiguous",
            "source_refs": [],
            "depends_on": [],
        }],
        "questions": [{
            "question_id": "q-meaning",
            "gap_id": "g-meaning",
            "field": "goal",
            "scope": "JGS含义",
            "text": "你说的 JGS 属于哪个领域，还是希望我先列出可能含义？",
            "options": [],
            "reason": "术语含义会改变讲解方向。",
            "depends_on": [],
        }],
        "readiness": {
            "goal_identified": True,
            "deliverable_identified": True,
            "blocking_gap_ids": ["g-meaning"],
            "reason": "目标和结果已明确，但术语含义仍需核对。",
        },
        "next_action": "ask",
        "assistant_text": "我先继续核对 JGS 的含义。",
        "model_judgment": {
            "answer_assessment": "partial",
            "critical_gap_ids": ["g-meaning"],
            "continue_interview": True,
            "confidence": "high",
            "reason": "当前信息只说明想学习 JGS，尚未确定具体对象。",
        },
    }
    parsed = parse_m1_response(json.dumps(result, ensure_ascii=False), payload, DESIGN.output_schema)
    session.stage_m1_result(payload["request_id"], payload["base_version"], parsed)
    restored = SessionState.from_dict(session.to_dict())

    assert restored.last_model_judgment == result["model_judgment"]
    assert restored.pending_questions[0]["gap_id"] == "g-meaning"


def test_old_skipped_question_is_not_repeated_without_new_context() -> None:
    session = _state_with_skipped_question()
    saved = session.to_dict()
    for row in saved["question_history"]:
        row.pop("recorded_source_count", None)
    restored = SessionState.from_dict(saved)
    payload = build_m1_input(restored, "req-no-repeat")
    result = {
        "schema_version": payload["schema_version"],
        "request_id": payload["request_id"],
        "task_id": payload["task_id"],
        "base_version": payload["base_version"],
        "status": "ok",
        "error": None,
        "category": {"primary": "learning", "secondary": [], "reason": "学习任务。"},
        "proposals": [], "conflicts": [], "review_item_ids": [], "gap_updates": [],
        "question_reopens": [],
        "gaps": restored.gaps,
        "questions": [{
            "question_id": "q-repeat",
            "gap_id": "g-meaning",
            "field": "goal",
            "scope": "JGS含义",
            "text": "JGS具体指什么？",
            "options": [],
            "reason": "需要明确方向。",
            "depends_on": [],
        }],
        "readiness": {
            "goal_identified": True,
            "deliverable_identified": True,
            "blocking_gap_ids": ["g-meaning"],
            "reason": "术语仍未明确。",
        },
        "next_action": "ask",
        "assistant_text": "请说明 JGS 的具体含义。",
    }
    with pytest.raises(M1ValidationError, match="不能在无新上下文时重复询问"):
        parse_m1_response(json.dumps(result, ensure_ascii=False), payload, DESIGN.output_schema)
