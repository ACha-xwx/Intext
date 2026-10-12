"""Serialize model input and omit only exactly reconstructible duplicates.

Local validation/evidence keeps the original payload. The wire view can refer
to a complete answer source instead of repeating its text in question history.
"""
from __future__ import annotations

import json
import logging
from copy import deepcopy
from typing import Any


_ANSWER_REFERENCE = "question_history省略的answer_text＝sources中answer_source_id对应text的完整原文。"


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def prepare_json_input(
    system_prompt: str, payload: dict[str, Any], output_schema: dict[str, Any],
) -> tuple[str, str]:
    original = json_text(payload)
    wire = original
    removed = 0
    if payload.get("schema_version") == "m1.v0.2":
        sources = {row.get("source_id"): row.get("text") for row in payload.get("sources", [])}
        compact = deepcopy(payload)
        for row in compact.get("state", {}).get("question_history", []):
            text = row.get("answer_text")
            if isinstance(text, str) and text and sources.get(row.get("answer_source_id")) == text:
                row.pop("answer_text")
                removed += 1
        candidate = json_text(compact)
        # The lookup instruction itself has a cost. Keep the original view for
        # tiny answers where reference overhead would outweigh deduplication.
        if len(original.encode("utf-8")) - len(candidate.encode("utf-8")) > len(("\n" + _ANSWER_REFERENCE).encode("utf-8")):
            wire = candidate
            system_prompt += "\n" + _ANSWER_REFERENCE
        else:
            removed = 0
    logging.getLogger(__name__).debug(
        "Model JSON input cost; schema=%s request=%s system_bytes=%s payload_bytes=%s "
        "original_payload_bytes=%s schema_bytes=%s referenced_answers=%s",
        payload.get("schema_version", "selection"), payload.get("request_id", "none"),
        len(system_prompt.encode("utf-8")), len(wire.encode("utf-8")), len(original.encode("utf-8")),
        len(json_text(output_schema).encode("utf-8")), removed,
    )
    return system_prompt, wire


def log_response_usage(envelope: dict[str, Any], *, request_id: str, latency_ms: int) -> None:
    """Report server counts once per transport response, never user text."""
    usage = envelope.get("usage")
    usage = usage if isinstance(usage, dict) else {}

    def count(value: Any) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None

    input_tokens = count(usage.get("prompt_tokens", usage.get("input_tokens")))
    output_tokens = count(usage.get("completion_tokens", usage.get("output_tokens")))
    details = usage.get("completion_tokens_details", usage.get("output_tokens_details"))
    reasoning = count(details.get("reasoning_tokens")) if isinstance(details, dict) else None
    answer = (output_tokens - reasoning if output_tokens is not None and reasoning is not None
              and reasoning <= output_tokens else None)
    logging.getLogger(__name__).info(
        "Model response usage; request=%s latency_ms=%s input_tokens=%s output_tokens=%s "
        "reasoning_tokens=%s answer_tokens=%s",
        request_id, latency_ms, input_tokens, output_tokens, reasoning, answer,
    )
