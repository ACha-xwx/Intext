from __future__ import annotations

import json
from pathlib import Path

import pytest

from promptsmith.api import ApiError, ApiResult
from promptsmith.finalization import build_final_draft, confirm_final, set_final_tone
from promptsmith.session import SessionState, SessionStateError, StaleResponseError
from promptsmith import trial
from promptsmith.trial import (
    TrialCallFailure,
    apply_trial_result,
    build_trial_request,
    invoke_trial,
)
from promptsmith.storage import load_session, save_session


class TextClient:
    def __init__(self, content: str = "试运行输出", usage: dict | None = None):
        self.content = content
        self.usage = usage
        self.calls = 0

    def complete_text(self, _system_prompt, _user_text, *, max_output_tokens=512):
        self.calls += 1
        return ApiResult(
            content=self.content,
            latency_ms=27,
            usage=self.usage,
            response_id="trial-fixture",
            model="fixture-model",
        )


class FailingClient:
    def complete_text(self, _system_prompt, _user_text, *, max_output_tokens=512):
        raise ApiError("timeout", "试运行超时。", latency_ms=41)


def confirmed_session() -> SessionState:
    session = SessionState.new()
    session.set_task("写一则摄影社招新通知。")
    session.requirements = [
        {
            "item_id": "req-1",
            "field": "goal",
            "text": "写一则招新通知",
            "kind": "user_fact",
            "strength": "hard",
            "scope": "当前任务",
            "source_refs": [],
            "depends_on": [],
            "confirmation": "confirmed",
        },
        {
            "item_id": "req-2",
            "field": "deliverable",
            "text": "一则新生微信群招新通知",
            "kind": "user_fact",
            "strength": "hard",
            "scope": "当前任务",
            "source_refs": [],
            "depends_on": [],
            "confirmation": "confirmed",
        },
    ]
    session.requirement_version = 1
    session.confirmed_requirements_version = 1
    session.plan = {
        "plan_id": "plan-1",
        "plan_version": 1,
        "status": "confirmed",
        "content": {
            "goal": {"summary": "写通知", "audience": "新生", "scope": "招新通知"},
            "requirement_coverage": [
                {"requirement_id": "req-1", "summary": "招新目标", "step_ids": ["step-1"], "deliverable_ids": ["deliverable-1"], "criterion_ids": ["criterion-1"]},
                {"requirement_id": "req-2", "summary": "通知交付物", "step_ids": ["step-1"], "deliverable_ids": ["deliverable-1"], "criterion_ids": ["criterion-1"]},
            ],
            "steps": [{
                "step_id": "step-1", "order": 1,
                "title": "整理信息", "purpose": "形成招新通知",
                "inputs": ["用户提供的任务信息"],
                "actions": ["整理已知活动信息"],
                "outputs": ["招新通知"],
                "completion_criteria": ["不添加未提供的信息"],
                "depends_on_step_ids": [], "requirement_ids": ["req-1", "req-2"],
            }],
            "deliverables": [{"deliverable_id": "deliverable-1", "name": "招新通知", "description": "新生微信群招新通知", "step_ids": ["step-1"], "requirement_ids": ["req-1", "req-2"]}],
            "completion_criteria": [{"criterion_id": "criterion-1", "text": "信息准确且不添加未提供内容", "requirement_ids": ["req-2"]}],
            "key_work": [{
                "key_work_id": "key-work-1", "title": "整理通知内容", "step_ids": ["step-1"],
                "goal": "形成准确通知", "inputs": ["用户提供的信息"], "outputs": ["招新通知"],
                "requirement_ids": ["req-1", "req-2"], "depends_on_key_work_ids": [],
                "checkpoints": ["不添加未知负责人或费用"],
            }],
            "unresolved_items": [],
            "suggestions": [],
        },
        "source_requirements_version": 1,
        "confirmed_plan_version": 1,
        "reviewed_key_work_ids": ["key-work-1"],
        "source_snapshot": {"requirements": session.requirements, "unresolved_items": []},
    }
    session.final_result = build_final_draft(session)
    confirm_final(session)
    return session


def test_trial_success_records_version_hash_usage_and_output(tmp_path: Path) -> None:
    session = confirmed_session()
    payload = build_trial_request(session, "trial-1", max_output_tokens=64)
    client = TextClient(usage={"prompt_tokens": 12, "completion_tokens": 8})
    outcome = invoke_trial(payload, client, protocol="fixture", configured_model="fixture-model")
    row = apply_trial_result(session, payload, outcome)

    assert row["output"] == "试运行输出"
    assert row["usage"] == {"prompt_tokens": 12, "completion_tokens": 8}
    assert row["final_revision"] == session.final_result["revision"]
    assert row["body_sha256"] == session.final_result["body_sha256"]
    assert row["tone"] == session.final_result["tone"]
    assert row["protocol"] == "fixture"
    assert len(session.trial_runs) == 1
    assert client.calls == 1


def test_trial_missing_usage_stays_missing() -> None:
    session = confirmed_session()
    payload = build_trial_request(session, "trial-no-usage", max_output_tokens=64)
    outcome = invoke_trial(payload, TextClient(usage=None), protocol="fixture", configured_model="fixture-model")
    row = apply_trial_result(session, payload, outcome)
    assert row["usage"] is None

    assert session.final_result["status"] == "confirmed"


def test_trial_failure_records_attempt_metadata_without_changing_final() -> None:
    assert callable(getattr(trial, "record_trial_failure", None))
    session = confirmed_session()
    payload = build_trial_request(session, "trial-fail", max_output_tokens=64)
    before_final = json.loads(json.dumps(session.final_result, ensure_ascii=False))
    with pytest.raises(TrialCallFailure) as captured:
        invoke_trial(payload, FailingClient(), protocol="fixture", configured_model="fixture-model")

    row = trial.record_trial_failure(session, payload, captured.value)
    assert row["status"] == "failed"
    assert row["created_at"]
    assert row["protocol"] == "fixture"
    assert row["model"] == "fixture-model"
    assert row["final_revision"] == payload["final_revision"]
    assert row["body_sha256"] == payload["body_sha256"]
    assert row["usage"] is None
    assert row["latency_ms"] == 41
    assert row["error_kind"] == "timeout"
    assert session.final_result == before_final
    assert payload["request_id"] not in session.pending_requests


def test_trial_rejects_stale_final_response_and_records_rejected_history() -> None:
    session = confirmed_session()
    payload = build_trial_request(session, "trial-stale", max_output_tokens=64)
    outcome = invoke_trial(payload, TextClient(), protocol="fixture", configured_model="fixture-model")
    session.final_result["revision"] += 1
    with pytest.raises(StaleResponseError):
        apply_trial_result(session, payload, outcome)
    assert len(session.trial_runs) == 1
    stale = session.trial_runs[0]
    assert stale["status"] == "rejected_stale"
    assert stale["error_kind"] == "stale_response"
    assert stale["protocol"] == "fixture"
    assert stale["model"] == "fixture-model"
    assert stale["final_revision"] == payload["final_revision"]
    assert stale["body_sha256"] == payload["body_sha256"]
    assert stale["usage"] is None
    assert session.final_result["status"] == "confirmed"


def test_trial_tone_change_rejects_response_from_previous_prompt_rendering() -> None:
    session = confirmed_session()
    payload = build_trial_request(session, "trial-tone-stale", max_output_tokens=64)
    outcome = invoke_trial(payload, TextClient(), protocol="fixture", configured_model="fixture-model")
    set_final_tone(session, "polite")

    with pytest.raises(StaleResponseError):
        apply_trial_result(session, payload, outcome)

    assert session.trial_runs[0]["status"] == "rejected_stale"
    assert session.trial_runs[0]["tone"] == "neutral"
    assert session.final_result["tone"] == "polite"


def test_trial_superseded_request_is_recorded_as_stale_without_applying_output() -> None:
    session = confirmed_session()
    old_payload = build_trial_request(session, "trial-old", max_output_tokens=64)
    old_outcome = invoke_trial(old_payload, TextClient("old output"), protocol="fixture", configured_model="fixture-model")
    current_payload = build_trial_request(session, "trial-current", max_output_tokens=64)
    current_outcome = invoke_trial(current_payload, TextClient("current output"), protocol="fixture", configured_model="fixture-model")

    with pytest.raises(StaleResponseError):
        apply_trial_result(session, old_payload, old_outcome)
    applied = apply_trial_result(session, current_payload, current_outcome)

    assert applied["output"] == "current output"
    assert [(row["request_id"], row["status"]) for row in session.trial_runs] == [
        ("trial-old", "rejected_stale"),
        ("trial-current", "completed"),
    ]


def test_trial_history_survives_save_and_reopen(tmp_path: Path) -> None:
    session = confirmed_session()
    payload = build_trial_request(session, "trial-save", max_output_tokens=64)
    outcome = invoke_trial(payload, TextClient(usage=None), protocol="fixture", configured_model="fixture-model")
    apply_trial_result(session, payload, outcome)
    failed_payload = build_trial_request(session, "trial-fail-save", max_output_tokens=64)
    with pytest.raises(TrialCallFailure) as captured:
        invoke_trial(failed_payload, FailingClient(), protocol="fixture", configured_model="fixture-model")
    trial.record_trial_failure(session, failed_payload, captured.value)

    path = save_session(session, tmp_path / "trial-session.json")
    reopened = load_session(path)

    assert [row["status"] for row in reopened.trial_runs] == ["completed", "failed"]
    assert reopened.trial_runs[0]["usage"] is None
    assert reopened.trial_runs[1]["error_kind"] == "timeout"
    assert reopened.trial_runs[1]["body_sha256"] == session.final_result["body_sha256"]


def test_trial_requires_confirmed_current_final() -> None:
    session = confirmed_session()
    session.final_result["status"] = "stale"
    with pytest.raises(SessionStateError):
        build_trial_request(session, "trial-invalid", max_output_tokens=64)
