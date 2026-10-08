from __future__ import annotations

import json
from pathlib import Path

import pytest

from promptsmith.api import ApiError, ApiResult
from promptsmith.m1 import M1Assets
from promptsmith.m2 import M2Assets
from promptsmith.session import SessionState, StaleResponseError
from promptsmith.workflow import M2CallFailure, Phase12Workflow


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "resources" / "prompts"


def confirmed_session() -> SessionState:
    session = SessionState.new()
    session.set_task("写一份给新生的社团招新活动方案。")
    session.selected_category = "writing"
    session.requirements = [
        {
            "item_id": "r1",
            "field": "deliverable",
            "text": "一份可执行的社团招新活动方案",
            "kind": "user_decision",
            "strength": "hard",
            "scope": "整体任务",
            "source_refs": [],
            "depends_on": [],
            "confirmation": "confirmed",
        }
    ]
    session.analysis_basis_version = session.requirement_version
    session.confirm_requirements()
    return session


def valid_result(payload: dict) -> dict:
    return {
        "schema_version": "m2.v0.1",
        "request_id": payload["request_id"],
        "task_id": payload["task_id"],
        "source_requirements_version": payload["source_requirements_version"],
        "status": "ok",
        "error": None,
        "plan": {
            "goal": {"summary": "形成招新活动方案", "audience": "新生", "scope": "活动筹备与执行"},
            "requirement_coverage": [{"requirement_id": "r1", "summary": "完整覆盖", "step_ids": ["s1"], "deliverable_ids": ["d1"], "criterion_ids": ["c1"]}],
            "steps": [{"step_id": "s1", "order": 1, "title": "形成方案", "purpose": "明确活动安排", "inputs": ["需求"], "actions": ["整理流程"], "outputs": ["方案"], "completion_criteria": ["可执行"], "depends_on_step_ids": [], "requirement_ids": ["r1"]}],
            "deliverables": [{"deliverable_id": "d1", "name": "活动方案", "description": "完整招新方案", "step_ids": ["s1"], "requirement_ids": ["r1"]}],
            "completion_criteria": [{"criterion_id": "c1", "text": "方案可执行", "requirement_ids": ["r1"]}],
            "unresolved_items": [],
            "suggestions": [],
            "key_work": [{"key_work_id": "k1", "title": "活动流程", "step_ids": ["s1"], "goal": "形成执行链路", "inputs": ["需求"], "outputs": ["流程"], "requirement_ids": ["r1"], "depends_on_key_work_ids": [], "checkpoints": ["流程完整"]}],
        },
    }


class Client:
    def __init__(self, responder):
        self.responder = responder

    def complete_json(self, _system_prompt, payload, _schema):
        return ApiResult(
            content=json.dumps(self.responder(payload), ensure_ascii=False),
            latency_ms=12,
            usage={"total_tokens": 30},
            response_id="fixture-m2",
            model="fixture-model",
        )


def test_workflow_generates_and_records_m2_draft(tmp_path: Path) -> None:
    session = confirmed_session()
    workflow = Phase12Workflow(session, M1Assets.load(DESIGN), tmp_path, M2Assets.load(DESIGN))
    payload = workflow.prepare_m2("m2-workflow", current_date="2026-09-23")

    outcome = workflow.invoke_m2(
        payload,
        Client(valid_result),
        protocol="openai_chat_completions",
        configured_model="fixture-model",
    )
    workflow.apply_m2(payload, outcome)

    assert session.plan["status"] == "draft"
    assert session.api_runs[-1]["status"] == "accepted_as_plan_draft"
    assert (outcome.evidence_dir / "response.raw.txt").exists()


def test_workflow_structured_error_keeps_existing_plan(tmp_path: Path) -> None:
    session = confirmed_session()
    session.plan["status"] = "stale"
    session.plan["content"] = {"preserved": True}
    before = json.loads(json.dumps(session.plan))
    workflow = Phase12Workflow(session, M1Assets.load(DESIGN), tmp_path, M2Assets.load(DESIGN))
    payload = workflow.prepare_m2("m2-error", current_date="2026-09-23")

    def error(payload: dict) -> dict:
        return {
            "schema_version": "m2.v0.1",
            "request_id": payload["request_id"],
            "task_id": payload["task_id"],
            "source_requirements_version": payload["source_requirements_version"],
            "status": "error",
            "plan": None,
            "error": {"code": "insufficient_input", "message": "信息不足", "related_input_ids": ["r1"], "recovery_action": "返回需求页"},
        }

    with pytest.raises(M2CallFailure):
        workflow.invoke_m2(
            payload,
            Client(error),
            protocol="openai_chat_completions",
            configured_model="fixture-model",
        )

    assert session.plan == before


def test_m1_and_m2_pending_request_purposes_are_isolated() -> None:
    session = confirmed_session()
    workflow = Phase12Workflow(session, M1Assets.load(DESIGN), ROOT / "tmp", M2Assets.load(DESIGN))

    payload = workflow.prepare_m2("purpose-m2", current_date="2026-09-23")

    assert session.pending_requests[payload["request_id"]]["purpose"] == "m2"
    with pytest.raises(StaleResponseError):
        session.stage_m1_result(payload["request_id"], session.requirement_version, {})
    assert payload["request_id"] in session.pending_requests
    assert session.plan["status"] == "not_started"

    m1_request = session.begin_request("purpose-m1")
    with pytest.raises(StaleResponseError):
        session.stage_m2_result(
            m1_request["request_id"],
            session.requirement_version,
            {},
            prompt_version="M2_system_v0.2",
            contract_version="m2.v0.1",
        )
    assert m1_request["request_id"] in session.pending_requests


def test_m2_truncation_preserves_partial_response_usage_and_existing_state(tmp_path: Path) -> None:
    session = confirmed_session()
    session.plan.update(status="stale", content={"preserved": True}, plan_version=3)
    old_plan = json.loads(json.dumps(session.plan))
    old_requirements = json.loads(json.dumps(session.requirements))
    workflow = Phase12Workflow(session, M1Assets.load(DESIGN), tmp_path, M2Assets.load(DESIGN))
    payload = workflow.prepare_m2("m2-truncated", current_date="2026-10-01")

    class TruncatedClient:
        def complete_json(self, *_args):
            raise ApiError(
                "truncated",
                "模型输出因长度限制被截断。",
                latency_ms=12000,
                response_content='{"status":"ok","plan":',
                response_usage={"completion_tokens": 8192},
                response_id="partial-response-id",
                response_model="deepseek-flash",
                finish_reason="length",
            )

    with pytest.raises(M2CallFailure) as failure:
        workflow.invoke_m2(
            payload,
            TruncatedClient(),
            protocol="openai_chat_completions",
            configured_model="deepseek-flash",
            request_parameters={"max_tokens": 65536, "reasoning_effort": "low"},
        )

    assert failure.value.kind == "truncated"
    assert session.requirements == old_requirements
    assert session.plan == old_plan
    assert payload["request_id"] not in session.pending_requests
    evidence = failure.value.evidence_dir
    assert (evidence / "response.raw.txt").read_text(encoding="utf-8") == '{"status":"ok","plan":'
    metadata = json.loads((evidence / "meta.json").read_text(encoding="utf-8"))
    check = json.loads((evidence / "check.json").read_text(encoding="utf-8"))
    assert metadata["usage"] == {"completion_tokens": 8192}
    assert metadata["provider_response_id"] == "partial-response-id"
    assert metadata["request_parameters"]["max_tokens"] == 65536
    assert check["failure_kind"] == "truncated"
    assert check["finish_reason"] == "length"


def test_m2_v02_prompt_is_loaded_and_packaged() -> None:
    assets = M2Assets.load(DESIGN)
    spec = (ROOT / "PromptSmith.spec").read_text(encoding="utf-8")
    assert assets.prompt_version == "M2_system_v0.2"
    assert "不是" not in assets.system_prompt or "而不是直接完成下游" in assets.system_prompt
    assert "JGS" in assets.system_prompt
    assert "M2_system_v0.2.txt" in spec
