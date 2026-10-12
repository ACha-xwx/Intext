from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import pytest

from promptsmith.runlog import RunEvidenceWriter


@pytest.mark.parametrize(("check", "expected_level"), [
    ({"valid": False, "auto_correction": {"attempt": 1, "action": "retry_with_contextual_correction"}}, logging.WARNING),
    ({"valid": False, "auto_correction": {"attempt": 3, "action": "exhausted"}}, logging.ERROR),
    ({"valid": False, "failure_kind": "network"}, logging.ERROR),
    ({"valid": True}, logging.INFO),
])
def test_recoverable_attempt_warning_keeps_traceback_and_final_errors(tmp_path, caplog, check, expected_level):
    caplog.set_level(logging.DEBUG, logger="promptsmith.runlog")
    try:
        raise ValueError("synthetic quote validation failure")
    except ValueError:
        location = RunEvidenceWriter(tmp_path).write(
            task_id="task-recovery", request_id="req-recovery", prompt_version="fixture",
            protocol="offline", model="fixture", input_payload={}, system_prompt="fixture",
            output_schema={}, raw_response="{}", metadata={}, check=check,
        )
    record = next(record for record in caplog.records if record.name == "promptsmith.runlog")
    assert record.levelno == expected_level
    assert record.exc_info and record.exc_info[0] is ValueError
    assert "synthetic quote validation failure" in caplog.text
    assert json.loads((location / "check.json").read_text(encoding="utf-8")) == check


def test_run_evidence_uses_unique_location_when_timestamp_and_request_repeat(tmp_path, monkeypatch) -> None:
    class FixedDatetime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 6, 13, 9, 59, 58238, tzinfo=tz or timezone.utc)

    monkeypatch.setattr("promptsmith.runlog.datetime", FixedDatetime)
    writer = RunEvidenceWriter(tmp_path)
    kwargs = {
        "task_id": "task-1",
        "request_id": "req-1",
        "prompt_version": "M1_system_v0.22",
        "protocol": "fixture",
        "model": "configured-model",
        "input_payload": {"request_id": "req-1"},
        "system_prompt": "system",
        "output_schema": {"type": "object"},
        "raw_response": "{}",
        "metadata": {},
        "check": {"valid": True},
    }

    first = writer.write(**kwargs)
    second = writer.write(**kwargs)

    assert first != second
    assert first.exists() and second.exists()
    assert sorted(path.name for path in first.parent.iterdir()) == sorted((first.name, second.name))


def test_run_evidence_preserves_raw_response_and_never_writes_key(tmp_path) -> None:
    writer = RunEvidenceWriter(tmp_path)
    secret = "sk-do-not-write"
    raw = '{"request_id":"req-1","status":"ok"}\n'

    location = writer.write(
        task_id="task-1",
        request_id="req-1",
        prompt_version="M1_system_v0.2",
        protocol="openai_chat_completions",
        model="configured-model",
        input_payload={"request_id": "req-1"},
        system_prompt="system",
        output_schema={"type": "object"},
        raw_response=raw,
        metadata={"latency_ms": 12, "usage": None, "api_key": secret},
        check={"valid": True},
    )

    assert (location / "response.raw.txt").read_text(encoding="utf-8") == raw
    combined = "\n".join(path.read_text(encoding="utf-8") for path in location.iterdir())
    assert secret not in combined
    meta = json.loads((location / "meta.json").read_text(encoding="utf-8"))
    assert "api_key" not in meta
    assert meta["evidence_type"] == "model_response"
