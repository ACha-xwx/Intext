from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_SENSITIVE = re.compile(r"(api[_-]?key|authorization|secret|password|access[_-]?token)", re.IGNORECASE)


def _sanitized(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitized(item) for key, item in value.items() if not _SENSITIVE.search(str(key))}
    if isinstance(value, list):
        return [_sanitized(item) for item in value]
    return deepcopy(value)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


class RunEvidenceWriter:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def write(
        self,
        *,
        task_id: str,
        request_id: str,
        prompt_version: str,
        protocol: str,
        model: str,
        input_payload: dict[str, Any],
        system_prompt: str,
        output_schema: dict[str, Any],
        raw_response: str,
        request_snapshot: dict[str, Any] | None = None,
        response_envelope: dict[str, Any] | None = None,
        metadata: dict[str, Any],
        check: dict[str, Any],
    ) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        safe_request = re.sub(r"[^A-Za-z0-9_.-]", "_", request_id)
        # A provider retry can happen within the same microsecond with the
        # same request id.  Keep the readable timestamp/request name, then
        # add a deterministic suffix only when that location is occupied.
        task_root = self.root / task_id
        location = task_root / f"{timestamp}_{safe_request}"
        suffix = 1
        while True:
            try:
                location.mkdir(parents=True, exist_ok=False)
                break
            except FileExistsError:
                location = task_root / f"{timestamp}_{safe_request}_{suffix}"
                suffix += 1
        _write_json(location / "input.json", _sanitized(input_payload))
        (location / "system.txt").write_text(system_prompt, encoding="utf-8", newline="\n")
        _write_json(location / "output.schema.json", output_schema)
        (location / "response.raw.txt").write_text(raw_response, encoding="utf-8", newline="")
        if request_snapshot is not None:
            _write_json(location / "request.snapshot.json", _sanitized(request_snapshot))
        if response_envelope is not None:
            _write_json(location / "response.envelope.json", _sanitized(response_envelope))
        meta = {
            "evidence_type": "model_response",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "task_id": task_id,
            "request_id": request_id,
            "prompt_version": prompt_version,
            "protocol": protocol,
            "model": model,
            **_sanitized(metadata),
        }
        _write_json(location / "meta.json", meta)
        _write_json(location / "check.json", _sanitized(check))
        return location
