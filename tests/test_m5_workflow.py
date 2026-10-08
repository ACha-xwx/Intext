from __future__ import annotations

import json
from pathlib import Path

import pytest

from promptsmith.api import ApiError, ApiResult
from promptsmith.m1 import M1Assets
from promptsmith.m5 import (
    M5Assets,
    M5ValidationError,
    build_m5_input,
    parse_m5_response,
    record_m5_feedback,
)
from promptsmith.session import SessionState, SessionStateError, StaleResponseError
from promptsmith.workflow import M5CallFailure, Phase12Workflow


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "resources" / "prompts"


class Client:
    def __init__(self, content: str):
        self.content = content

    def complete_json(self, _system_prompt, _payload, _schema):
        return ApiResult(
            content=self.content,
            latency_ms=19,
            usage={"total_tokens": 28},
            response_id="m5-fixture",
            model="fixture-m5",
        )


class FailingClient:
    def complete_json(self, _system_prompt, _payload, _schema):
        raise ApiError("network", "无法连接模型接口。", latency_ms=31)


def valid_response(payload: dict) -> dict:
    return {
        "schema_version": "m5.v0.1",
        "request_id": payload["request_id"],
        "task_id": payload["task_id"],
        "base_version": payload["base_version"],
        "status": "ok",
        "error": None,
        "example": {
            "dimension": "语气",
            "shared_assumptions": ["保持原任务主题"],
            "option_a": "语气自然克制。",
            "option_b": "语气自然活泼。",
            "difference_summary": "B更活泼。",
            "unsupported_assumptions": ["未确定正式口号"],
        },
    }


def session_with_task() -> SessionState:
    session = SessionState.new()
    session.set_task("写一份社团招新通知。")
    return session


def test_m5_rejects_unprovided_equipment_action_in_example() -> None:
    session = SessionState.new()
    session.set_task(
        "为摄影社写一则发在新生微信群的招新通知。"
        "活动是校园南广场的手机摄影体验。"
        "不要添加未提供的负责人、收费或器材要求。"
    )
    session.requirements.append(
        {
            "item_id": "r-equipment-boundary",
            "field": "constraints",
            "text": "不得添加未提供的负责人、收费或器材要求。",
            "kind": "user_decision",
            "strength": "hard",
            "scope": "招新通知整体",
            "source_refs": [],
            "depends_on": [],
            "confirmation": "pending",
        }
    )
    payload = build_m5_input(session, "m5-equipment-boundary", criterion_description="语气")
    raw = json.dumps(
        {
            "schema_version": "m5.v0.1",
            "request_id": payload["request_id"],
            "task_id": payload["task_id"],
            "base_version": payload["base_version"],
            "status": "ok",
            "error": None,
            "example": {
                "dimension": "语气",
                "shared_assumptions": ["活动为手机摄影体验"],
                "option_a": "欢迎新生来体验手机摄影，带上手机即可参加。",
                "option_b": "欢迎新生来参加手机摄影体验。",
                "difference_summary": "A额外写明参与时需要携带手机。",
                "unsupported_assumptions": [],
            },
        },
        ensure_ascii=False,
    )

    with pytest.raises(M5ValidationError, match="事实|器材|未经用户提供"):
        parse_m5_response(raw, payload)


def test_m5_workflow_registers_request_and_applies_example(tmp_path: Path) -> None:
    session = session_with_task()
    workflow = Phase12Workflow(
        session, M1Assets.load(DESIGN), tmp_path, m5_assets=M5Assets.load(DESIGN)
    )
    payload = workflow.prepare_m5("m5-01", criterion_id="tone", criterion_description="语气")

    assert session.pending_requests["m5-01"]["purpose"] == "m5"
    outcome = workflow.invoke_m5(
        payload,
        Client(json.dumps(valid_response(payload), ensure_ascii=False)),
        protocol="fixture",
        configured_model="fixture-m5",
    )
    workflow.apply_m5(payload, outcome)

    assert len(session.m5_examples) == 1
    assert session.m5_state["status"] == "ready"
    assert session.api_runs[-1]["status"] == "accepted_as_m5_example"
    assert (outcome.evidence_dir / "response.raw.txt").exists()


def test_m5_transport_failure_preserves_requirements_and_records_missing_usage(tmp_path: Path) -> None:
    session = session_with_task()
    before = json.loads(json.dumps(session.requirements))
    workflow = Phase12Workflow(session, M1Assets.load(DESIGN), tmp_path)
    payload = workflow.prepare_m5("m5-network", criterion_description="语气")

    with pytest.raises(M5CallFailure) as captured:
        workflow.invoke_m5(
            payload, FailingClient(), protocol="fixture", configured_model="fixture-m5"
        )

    assert session.requirements == before
    assert session.m5_examples == []
    assert session.m5_state["status"] == "error"
    assert session.api_runs[-1]["usage"] is None
    assert captured.value.api_result.latency_ms == 31


def test_m5_apply_rejects_response_after_task_change(tmp_path: Path) -> None:
    session = session_with_task()
    workflow = Phase12Workflow(session, M1Assets.load(DESIGN), tmp_path)
    payload = workflow.prepare_m5("m5-stale", criterion_description="语气")
    outcome = workflow.invoke_m5(
        payload,
        Client(json.dumps(valid_response(payload), ensure_ascii=False)),
        protocol="fixture",
        configured_model="fixture-m5",
    )
    session.set_task("写一份完全不同的报名说明。")

    with pytest.raises(StaleResponseError):
        workflow.apply_m5(payload, outcome)

    assert session.m5_examples == []


def test_m5_example_becomes_stale_when_requirements_change(tmp_path: Path) -> None:
    session = session_with_task()
    workflow = Phase12Workflow(session, M1Assets.load(DESIGN), tmp_path)
    payload = workflow.prepare_m5("m5-state", criterion_description="语气")
    outcome = workflow.invoke_m5(
        payload,
        Client(json.dumps(valid_response(payload), ensure_ascii=False)),
        protocol="fixture",
        configured_model="fixture-m5",
    )
    row = workflow.apply_m5(payload, outcome)
    assert row is not None

    session.set_task("改写成产品使用说明。")
    assert session.m5_state["status"] == "stale"
    with pytest.raises(SessionStateError):
        record_m5_feedback(session, row["example_id"], "a")
