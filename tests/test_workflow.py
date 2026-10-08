from __future__ import annotations

import json
from pathlib import Path

import pytest

from promptsmith.api import ApiError, ApiResult
from promptsmith.m1 import M1Assets
from promptsmith.session import SessionState
from promptsmith.workflow import M1CallFailure, Phase12Workflow


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "resources" / "prompts"


class FakeClient:
    def __init__(self, content: str):
        self.content = content

    def complete_json(self, system_prompt, payload, schema):
        return ApiResult(
            content=self.content,
            latency_ms=15,
            usage={"total_tokens": 42},
            response_id="fake-response",
            model="fixture-model",
        )


class FailingClient:
    def complete_json(self, system_prompt, payload, schema):
        raise ApiError("network", "无法连接模型接口，请检查地址和网络。", latency_ms=23)


def test_workflow_records_then_applies_valid_candidate(tmp_path) -> None:
    expected = json.loads((DESIGN / "examples" / "01_报名网站.expected.json").read_text(encoding="utf-8"))
    session = SessionState.new()
    session.set_task("帮我做一个活动报名网站，不做付款。")
    workflow = Phase12Workflow(session, M1Assets.load(DESIGN), tmp_path)
    payload = workflow.prepare_m1("req-01", current_date="2026-09-22")
    for key in ("schema_version", "request_id", "task_id", "base_version"):
        expected[key] = payload[key]
    expected["gap_updates"] = []
    expected["question_reopens"] = []

    outcome = workflow.invoke_m1(
        payload,
        FakeClient(json.dumps(expected, ensure_ascii=False)),
        protocol="fixture",
        configured_model="fixture-model",
        request_parameters={"temperature": 0, "response_format": "json_object"},
    )
    workflow.apply_m1(payload, outcome)

    assert len(session.pending_proposals) == 3
    assert session.pending_questions[0]["field"] == "use_context"
    assert outcome.evidence_dir.exists()
    assert json.loads((outcome.evidence_dir / "check.json").read_text(encoding="utf-8"))["valid"] is True
    meta = json.loads((outcome.evidence_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["request_parameters"]["temperature"] == 0


def test_invalid_model_output_is_preserved_but_not_applied(tmp_path) -> None:
    session = SessionState.new()
    session.set_task("帮我做一个活动报名网站，不做付款。")
    workflow = Phase12Workflow(session, M1Assets.load(DESIGN), tmp_path)
    payload = workflow.prepare_m1("req-bad", current_date="2026-09-23")
    raw = '{"not":"the contract"}'

    with pytest.raises(M1CallFailure) as captured:
        workflow.invoke_m1(payload, FakeClient(raw), protocol="fixture", configured_model="fixture-model")

    assert session.pending_proposals == []
    assert (captured.value.evidence_dir / "response.raw.txt").read_text(encoding="utf-8") == raw
    check = json.loads((captured.value.evidence_dir / "check.json").read_text(encoding="utf-8"))
    assert check["valid"] is False


def test_valid_input_error_is_recorded_as_failure_and_preserves_state(tmp_path) -> None:
    template = json.loads((DESIGN / "examples" / "01_报名网站.expected.json").read_text(encoding="utf-8"))
    session = SessionState.new()
    session.set_task("帮我做一个活动报名网站，不做付款。")
    session.requirements = [
        {
            "item_id": "r-old",
            "field": "deliverable",
            "text": "活动报名网站",
            "kind": "user_decision",
            "strength": "hard",
            "scope": "整体任务",
            "source_refs": [{"source_id": "u1", "quote": "活动报名网站"}],
            "depends_on": [],
            "confirmation": "review_needed",
        }
    ]
    session.gaps = [
        {
            "gap_id": "g-old",
            "field": "use_context",
            "scope": "整体任务",
            "description": "用途尚未明确。",
            "importance": "can_defer",
            "origin": "missing",
            "source_refs": [{"source_id": "u1", "quote": "活动报名网站"}],
            "depends_on": [],
        }
    ]
    session.open_conflicts = [
        {"conflict_id": "c-old", "existing_item_ids": [], "proposal_ids": [], "description": "旧冲突"}
    ]
    session.pending_proposals = [{"proposal_id": "p-old"}]
    session.pending_review_item_ids = ["r-old"]
    session.control["remaining_rounds"] = 1
    workflow = Phase12Workflow(session, M1Assets.load(DESIGN), tmp_path)
    payload = workflow.prepare_m1("req-input-error", current_date="2026-09-23")
    for key in ("schema_version", "request_id", "task_id", "base_version"):
        template[key] = payload[key]
    template["gap_updates"] = []
    template["question_reopens"] = []
    template.update(
        status="input_error",
        error={"code": "invalid_input", "message": "无法处理输入"},
        category={"primary": "general", "secondary": [], "reason": "输入错误"},
        proposals=[],
        conflicts=[],
        review_item_ids=[],
        gaps=[],
        questions=[],
        readiness={
            "goal_identified": False,
            "deliverable_identified": False,
            "blocking_gap_ids": [],
            "reason": "输入错误",
        },
        next_action="pause_with_unknowns",
        assistant_text="输入需复核",
    )
    before = {
        "gaps": list(session.gaps),
        "conflicts": list(session.open_conflicts),
        "proposals": list(session.pending_proposals),
        "reviews": list(session.pending_review_item_ids),
        "rounds": session.control["remaining_rounds"],
    }

    with pytest.raises(M1CallFailure, match="无法处理输入") as captured:
        workflow.invoke_m1(
            payload,
            FakeClient(json.dumps(template, ensure_ascii=False)),
            protocol="fixture",
            configured_model="fixture-model",
        )

    assert session.gaps == before["gaps"]
    assert session.open_conflicts == before["conflicts"]
    assert session.pending_proposals == before["proposals"]
    assert session.pending_review_item_ids == before["reviews"]
    assert session.control["remaining_rounds"] == before["rounds"]
    assert captured.value.evidence_dir.exists()
    check = json.loads((captured.value.evidence_dir / "check.json").read_text(encoding="utf-8"))
    assert check["business_status"] == "input_error"


def test_transport_failure_records_available_metadata_and_preserves_state(tmp_path) -> None:
    session = SessionState.new()
    session.set_task("帮我做一个活动报名网站")
    session.gaps = [
        {
            "gap_id": "g-old",
            "field": "runtime",
            "scope": "整体任务",
            "description": "运行方式未知。",
            "importance": "can_defer",
            "origin": "missing",
            "source_refs": [],
            "depends_on": [],
        }
    ]
    workflow = Phase12Workflow(session, M1Assets.load(DESIGN), tmp_path)
    payload = workflow.prepare_m1("req-network", current_date="2026-09-23")
    before = list(session.gaps)

    with pytest.raises(M1CallFailure) as captured:
        workflow.invoke_m1(
            payload,
            FailingClient(),
            protocol="fixture",
            configured_model="fixture-model",
        )

    assert captured.value.kind == "network"
    assert captured.value.api_result.latency_ms == 23
    assert captured.value.api_result.usage is None
    assert session.gaps == before
    assert payload["request_id"] not in session.pending_requests
    assert session.api_runs[-1]["status"] == "network"
    assert session.api_runs[-1]["latency_ms"] == 23
    assert session.api_runs[-1]["usage"] is None
    meta = json.loads((captured.value.evidence_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["latency_ms"] == 23
    assert meta["usage"] is None
