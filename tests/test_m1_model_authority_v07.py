from __future__ import annotations

import json
from pathlib import Path

from promptsmith.api import ApiResult
from promptsmith.m1 import M1Assets, build_m1_input, parse_m1_response
from promptsmith.session import SessionState
from promptsmith.workflow import Phase12Workflow


def _jgs_response(payload: dict) -> dict:
    result = {
        "schema_version": payload["schema_version"],
        "request_id": payload["request_id"],
        "task_id": payload["task_id"],
        "base_version": payload["base_version"],
        "status": "ok",
        "error": None,
        "category": {"primary": "learning", "secondary": [], "reason": "学生学习讲解。"},
        "proposals": [{
            "proposal_id": "p-explain", "operation": "new", "target_item_id": None,
            "field": "deliverable", "text": "讲解 JGS", "kind": "user_decision", "strength": "hard",
            "scope": "当前讲解", "source_refs": [{"source_id": payload["current_source_id"], "quote": "讲解 JGS"}],
            "depends_on": [], "reason": "用户提出讲解任务。",
        }],
        "conflicts": [], "review_item_ids": [], "gap_updates": [], "question_reopens": [],
        "gaps": [
            {"gap_id": "g1", "field": "goal", "scope": "当前讲解", "description": "JGS所指领域未知", "importance": "blocking_direction", "origin": "missing", "source_refs": [], "depends_on": []},
            {"gap_id": "g2", "field": "audience", "scope": "当前讲解", "description": "讲解对象未知", "importance": "blocking_direction", "origin": "missing", "source_refs": [], "depends_on": []},
        ],
        "questions": [
            {"question_id": "q1", "gap_id": "g1", "field": "goal", "scope": "当前讲解", "text": "JGS是哪个领域的？", "options": [], "reason": "明确讲解方向。", "depends_on": []},
            {"question_id": "q2", "gap_id": "g2", "field": "audience", "scope": "当前讲解", "text": "讲解给谁学习？", "options": [], "reason": "明确讲解对象。", "depends_on": []},
        ],
        "readiness": {"goal_identified": True, "deliverable_identified": True, "blocking_gap_ids": ["g1", "g2"], "reason": "讲解方向仍需核对。"},
        "next_action": "ask",
        "assistant_text": "我先核对 JGS 的含义和讲解对象。",
    }
    return result


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "resources" / "prompts"


def test_v08_assets_make_quality_decision_model_led() -> None:
    assets = M1Assets.load(DESIGN)

    assert assets.prompt_version == "M1_system_v0.18"
    assert "不是“需求已经足够”的质量门槛" in assets.system_prompt
    assert "候选解释" in assets.system_prompt
    assert "主动建议公开资料检索" in assets.system_prompt
    assert (DESIGN / "M1_incremental_v0.11.txt").read_text(encoding="utf-8-sig").strip()


def test_model_can_continue_after_legacy_question_controls_are_exhausted() -> None:
    session = SessionState.new()
    session.set_task("讲解 JGS，面向零基础学习者")
    payload = build_m1_input(session, "req-v07")
    payload["control"]["max_questions"] = 0
    payload["control"]["remaining_rounds"] = 0
    payload["control"]["allow_questions"] = False
    gap = {
        "gap_id": "g-meaning",
        "field": "learning_goal",
        "scope": "JGS 术语含义",
        "description": "JGS 在本任务中具体指什么仍未确定。",
        "importance": "blocking_direction",
        "origin": "ambiguous",
        "source_refs": [],
        "depends_on": [],
    }
    response = {
        "schema_version": "m1.v0.2",
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
        "gaps": [gap],
        "questions": [
            {
                "question_id": "q-meaning",
                "gap_id": "g-meaning",
                "field": "learning_goal",
                "scope": "JGS 术语含义",
                "text": "你说的 JGS 是哪一类数值分析概念，还是希望我先列出可能含义供你确认？",
                "options": [],
                "reason": "术语含义会决定后续讲解方向；用户不必先提供全称。",
                "depends_on": [],
            }
        ],
        "readiness": {
            "goal_identified": True,
            "deliverable_identified": True,
            "blocking_gap_ids": ["g-meaning"],
            "reason": "讲解目标已明确，但术语含义仍影响方向。",
        },
        "next_action": "ask",
        "assistant_text": "我先根据上下文继续核对 JGS 的含义。",
    }

    parsed = parse_m1_response(
        json.dumps(response, ensure_ascii=False), payload, M1Assets.load(DESIGN).output_schema
    )

    assert parsed["next_action"] == "ask"
    assert parsed["questions"][0]["gap_id"] == "g-meaning"


class _SequenceClient:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls: list[str] = []

    def complete_json(self, system_prompt, payload, schema):
        self.calls.append(system_prompt)
        return ApiResult(
            content=self.responses.pop(0),
            latency_ms=10,
            usage={"total_tokens": 10},
            response_id=f"response-{len(self.calls)}",
            model="fixture-model",
        )


def test_m1_gives_model_one_contextual_self_correction_attempt(tmp_path) -> None:
    session = SessionState.new()
    session.set_task("帮我做一个活动报名网站，不做付款。")
    workflow = Phase12Workflow(session, M1Assets.load(DESIGN), tmp_path)
    payload = workflow.prepare_m1("req-auto-correct", current_date="2026-09-22")
    valid = json.loads((DESIGN / "examples" / "01_报名网站.expected.json").read_text(encoding="utf-8"))
    for key in ("schema_version", "request_id", "task_id", "base_version"):
        valid[key] = payload[key]
    valid["gap_updates"] = []
    valid["question_reopens"] = []
    client = _SequenceClient(["{\"not\":\"the contract\"}", json.dumps(valid, ensure_ascii=False)])

    outcome = workflow.invoke_m1(
        payload,
        client,
        protocol="fixture",
        configured_model="fixture-model",
    )

    assert len(client.calls) == 2
    assert "重新检查并输出合法 JSON" in client.calls[1]
    assert outcome.parsed["status"] == "ok"
    assert session.errors == []


def test_m1_gives_model_two_content_correction_attempts(tmp_path) -> None:
    session = SessionState.new()
    session.set_task("帮我做一个活动报名网站，不做付款。")
    workflow = Phase12Workflow(session, M1Assets.load(DESIGN), tmp_path)
    payload = workflow.prepare_m1("req-auto-correct-twice", current_date="2026-09-22")
    valid = json.loads((DESIGN / "examples" / "01_报名网站.expected.json").read_text(encoding="utf-8"))
    for key in ("schema_version", "request_id", "task_id", "base_version"):
        valid[key] = payload[key]
    valid["gap_updates"] = []
    valid["question_reopens"] = []
    client = _SequenceClient(["{\"not\":\"the contract\"}", "{\"still\":\"not the contract\"}", json.dumps(valid, ensure_ascii=False)])

    outcome = workflow.invoke_m1(
        payload,
        client,
        protocol="fixture",
        configured_model="fixture-model",
    )

    assert len(client.calls) == 3
    assert "重新检查并输出合法 JSON" in client.calls[1]
    assert "重新检查并输出合法 JSON" in client.calls[2]
    assert outcome.parsed["status"] == "ok"
    assert session.errors == []


def test_input_error_is_repaired_as_a_normal_interview_response(tmp_path) -> None:
    session = SessionState.new()
    session.set_task("帮我做一个活动报名网站，不做付款。")
    workflow = Phase12Workflow(session, M1Assets.load(DESIGN), tmp_path)
    payload = workflow.prepare_m1("req-input-error-recovery", current_date="2026-09-22")
    valid = json.loads((DESIGN / "examples" / "01_报名网站.expected.json").read_text(encoding="utf-8"))
    for key in ("schema_version", "request_id", "task_id", "base_version"):
        valid[key] = payload[key]
    valid["gap_updates"] = []
    valid["question_reopens"] = []

    legacy_error = json.loads(json.dumps(valid, ensure_ascii=False))
    legacy_error.update(
        status="input_error",
        error={"code": "context_incomplete", "message": "无法确定术语含义"},
        category={"primary": "general", "secondary": [], "reason": "需要继续核对"},
        proposals=[],
        conflicts=[],
        review_item_ids=[],
        gaps=[],
        questions=[],
        readiness={
            "goal_identified": False,
            "deliverable_identified": False,
            "blocking_gap_ids": [],
            "reason": "需要继续核对",
        },
        next_action="pause_with_unknowns",
        assistant_text="我还需要继续核对。",
    )
    client = _SequenceClient([
        json.dumps(legacy_error, ensure_ascii=False),
        json.dumps(valid, ensure_ascii=False),
    ])

    outcome = workflow.invoke_m1(
        payload,
        client,
        protocol="fixture",
        configured_model="fixture-model",
    )

    assert len(client.calls) == 2
    assert "input_error" in client.calls[1]
    assert "必须改为 status=ok" in client.calls[1]
    assert outcome.parsed["status"] == "ok"
    assert session.errors == []


def test_m1_stage_does_not_consume_legacy_question_budget() -> None:
    session = SessionState.new()
    session.set_task("整理一个学习任务")
    session.control["remaining_rounds"] = 0
    request = session.begin_request("req-no-budget")
    response = {
        "questions": [{
            "question_id": "q1",
            "gap_id": "g1",
            "field": "goal",
            "scope": "整体任务",
            "text": "想完成什么？",
            "options": [],
            "reason": "影响后续方向。",
            "depends_on": [],
        }],
        "gaps": [{
            "gap_id": "g1",
            "field": "goal",
            "scope": "整体任务",
            "description": "任务目标还不清楚。",
            "importance": "blocking_direction",
            "origin": "missing",
            "source_refs": [],
            "depends_on": [],
        }],
    }
    response.update({
        "category": {"primary": "learning", "secondary": [], "reason": "学习任务。"},
        "proposals": [],
        "conflicts": [],
        "review_item_ids": [],
        "gap_updates": [],
        "question_reopens": [],
        "readiness": {
            "goal_identified": False,
            "deliverable_identified": False,
            "blocking_gap_ids": ["g1"],
            "reason": "目标还不清楚。",
        },
        "next_action": "ask",
        "assistant_text": "我先核对任务目标。",
    })
    response["gaps"] = [{
        "gap_id": "g1",
        "field": "goal",
        "scope": "整体任务",
        "description": "任务目标还不清楚。",
        "importance": "blocking_direction",
        "origin": "missing",
        "source_refs": [],
        "depends_on": [],
    }]

    session.stage_m1_result(request["request_id"], request["base_version"], response)

    assert session.control["remaining_rounds"] == 0


def test_model_judgment_is_optional_and_saved_with_partial_answer() -> None:
    session = SessionState.new()
    session.set_task("讲解 JGS，面向零基础学习者")
    payload = build_m1_input(session, "req-judgment")
    response = _jgs_response(payload)
    response["model_judgment"] = {
        "answer_assessment": "partial",
        "critical_gap_ids": ["g1"],
        "continue_interview": True,
        "confidence": "high",
        "reason": "当前信息只说明了任务方向，JGS的具体含义仍会改变讲解内容。",
    }

    parsed = parse_m1_response(
        json.dumps(response, ensure_ascii=False), payload, M1Assets.load().output_schema
    )
    session.stage_m1_result(payload["request_id"], payload["base_version"], parsed)

    assert session.last_model_judgment == response["model_judgment"]


def test_new_context_after_skip_can_return_a_different_question_without_reopen() -> None:
    session = SessionState.new()
    session.set_task("讲解 JGS")
    first_payload = build_m1_input(session, "req-first")
    first = _jgs_response(first_payload)
    first_parsed = parse_m1_response(
        json.dumps(first, ensure_ascii=False), first_payload, M1Assets.load().output_schema
    )
    session.stage_m1_result(first_payload["request_id"], first_payload["base_version"], first_parsed)
    session.record_question("q1", "skipped")
    session.record_supplement("我说的是数值分析语境中的 JGS，请先按这个方向核对。", gap_ids=["g1"])

    payload = build_m1_input(session, "req-after-skip")
    response = _jgs_response(payload)
    response["request_id"] = payload["request_id"]
    response["base_version"] = payload["base_version"]
    # This round is about the new supplement; do not carry the first-round
    # deliverable proposal with a quote from the older source.
    response["proposals"] = []
    response["question_reopens"] = []
    response["gap_updates"] = [{
        "update_id": "update-a1",
        "target_gap_id": "g1",
        "answer_id": next(row["answer_id"] for row in payload["state"]["question_history"] if row["assessment_status"] == "pending"),
        "action": "partial",
        "source_ref": {
            "source_id": next(row["answer_source_id"] for row in payload["state"]["question_history"] if row["assessment_status"] == "pending"),
            "quote": "我说的是数值分析语境中的 JGS，请先按这个方向核对。",
        },
        "remaining_description": "数值分析语境已明确，但 JGS 的具体对象仍需核对。",
        "reason": "用户补充了新的领域线索，但还没有确定具体对象。",
    }]
    response["gaps"] = [row for row in response["gaps"] if row["gap_id"] in {"g1", "g2"}]
    response["questions"] = [{
        "question_id": "q1-next",
        "gap_id": "g1",
        "field": "goal",
        "scope": "当前讲解",
        "text": "在数值分析语境下，你希望我先核对 JGS 的具体对象，还是先按你手头材料中的定义讲解？",
        "options": [],
        "reason": "新的领域线索允许换一种更具体的确认方式。",
        "depends_on": [],
    }]
    response["readiness"]["blocking_gap_ids"] = ["g1", "g2"]
    response["next_action"] = "ask"

    parsed = parse_m1_response(
        json.dumps(response, ensure_ascii=False), payload, M1Assets.load().output_schema
    )
    assert parsed["questions"][0]["question_id"] == "q1-next"
