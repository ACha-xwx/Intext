from __future__ import annotations

import json
from datetime import datetime, timezone

from promptsmith.runlog import RunEvidenceWriter


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
