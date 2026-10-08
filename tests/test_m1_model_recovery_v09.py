import json
from pathlib import Path

from promptsmith.api import ApiResult
from promptsmith.m1 import M1Assets
from promptsmith.session import SessionState
from promptsmith.workflow import Phase12Workflow


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "resources" / "prompts"


class _RepeatedSemanticInputErrorClient:
    def __init__(self, response: str):
        self.response = response
        self.calls = 0

    def complete_json(self, system_prompt, payload, schema):
        self.calls += 1
        return ApiResult(
            content=self.response,
            latency_ms=12,
            usage={"total_tokens": 31},
            response_id=f"recovery-{self.calls}",
            model="fixture-model",
        )


def test_repeated_semantic_input_error_becomes_continuable_interview(tmp_path) -> None:
    template = json.loads(
        (DESIGN / "examples" / "01_报名网站.expected.json").read_text(encoding="utf-8")
    )
    session = SessionState.new()
    session.set_task("讲解 JGS，面向零基础学习者")
    session.gaps = [
        {
            "gap_id": "g-jgs-meaning",
            "field": "learning_goal",
            "scope": "JGS术语含义",
            "description": "JGS在本任务中具体指什么仍未确定。",
            "importance": "blocking_direction",
            "origin": "ambiguous",
            "source_refs": [],
            "depends_on": [],
        }
    ]
    workflow = Phase12Workflow(session, M1Assets.load(DESIGN), tmp_path)
    payload = workflow.prepare_m1("req-semantic-recovery", current_date="2026-10-06")
    for key in ("schema_version", "request_id", "task_id", "base_version"):
        template[key] = payload[key]
    template.update(
        status="input_error",
        error={"code": "context_incomplete", "message": "无法确定简称含义"},
        category={"primary": "general", "secondary": [], "reason": "需要继续核对"},
        proposals=[],
        conflicts=[],
        review_item_ids=[],
        gap_updates=[],
        question_reopens=[],
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
    client = _RepeatedSemanticInputErrorClient(json.dumps(template, ensure_ascii=False))

    outcome = workflow.invoke_m1(
        payload,
        client,
        protocol="fixture",
        configured_model="fixture-model",
    )

    assert client.calls == 3
    assert outcome.recovery_mode == "program_recovery"
    assert outcome.parsed["status"] == "ok"
    assert outcome.parsed["next_action"] == "ask"
    assert outcome.parsed["gaps"][0]["gap_id"] == "g-jgs-meaning"
    assert outcome.parsed["questions"]
    assert outcome.parsed["questions"][0]["gap_id"] == "g-jgs-meaning"
    assert outcome.parsed["model_judgment"]["continue_interview"] is True
    assert session.errors == []

    workflow.apply_m1(payload, outcome)
    assert session.api_runs[-1]["status"] == "accepted_as_candidate"
    assert session.api_runs[-1]["recovery_mode"] == "program_recovery"

    check = json.loads((outcome.evidence_dir / "check.json").read_text(encoding="utf-8"))
    assert check["valid"] is True
    assert check["recovery_fallback"]["mode"] == "program_recovery"
    assert check["recovery_fallback"]["source_status"] == "input_error"
