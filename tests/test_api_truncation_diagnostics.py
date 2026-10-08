from __future__ import annotations

import pytest

from promptsmith.api import (
    ANTHROPIC_MESSAGES_PROTOCOL,
    OPENAI_RESPONSES_PROTOCOL,
    PROTOCOL_ID,
    ApiConfig,
    ApiError,
    client_for_config,
)


def _client(monkeypatch, protocol: str, envelope: dict):
    config = ApiConfig(
        base_url="https://example.invalid/v1",
        model="configured-model",
        api_key="test-key",
        protocol=protocol,
    )
    client = client_for_config(config)
    calls = []

    def once(*_args, **_kwargs):
        calls.append(1)
        assert len(calls) == 1, "A failed completion must not automatically retry."
        return envelope, 17

    monkeypatch.setattr(client, "_post_json", once)
    return client


@pytest.mark.parametrize(
    ("protocol", "envelope", "partial", "finish_reason"),
    [
        (
            PROTOCOL_ID,
            {
                "id": "chat-response",
                "model": "chat-model",
                "choices": [
                    {"finish_reason": "length", "message": {"content": '{"partial":'}}
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 8192},
            },
            '{"partial":',
            "length",
        ),
        (
            OPENAI_RESPONSES_PROTOCOL,
            {
                "id": "responses-response",
                "model": "responses-model",
                "status": "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"},
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": '{"partial":'}],
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 8192},
            },
            '{"partial":',
            "max_output_tokens",
        ),
        (
            ANTHROPIC_MESSAGES_PROTOCOL,
            {
                "id": "anthropic-response",
                "model": "anthropic-model",
                "stop_reason": "max_tokens",
                "content": [{"type": "text", "text": '{"partial":'}],
                "usage": {"input_tokens": 10, "output_tokens": 8192},
            },
            '{"partial":',
            "max_tokens",
        ),
    ],
)
def test_truncated_generation_preserves_partial_response_diagnostics(
    monkeypatch, protocol: str, envelope: dict, partial: str, finish_reason: str
) -> None:
    client = _client(monkeypatch, protocol, envelope)

    with pytest.raises(ApiError) as captured:
        client.complete_json("system", {"task": "demo"}, {"type": "object"})

    error = captured.value
    assert error.kind == "truncated"
    assert error.response_content == partial
    assert error.response_usage == envelope["usage"]
    assert error.response_id == envelope["id"]
    assert error.response_model == envelope["model"]
    assert error.finish_reason == finish_reason


@pytest.mark.parametrize("protocol", [PROTOCOL_ID, OPENAI_RESPONSES_PROTOCOL, ANTHROPIC_MESSAGES_PROTOCOL])
def test_truncated_response_is_still_rejected_even_when_partial_text_is_complete_json(
    monkeypatch, protocol: str
) -> None:
    if protocol == PROTOCOL_ID:
        envelope = {
            "id": "chat-complete-json",
            "model": "m",
            "choices": [
                {"finish_reason": "length", "message": {"content": '{"status":"ok"}'}}
            ],
        }
    elif protocol == OPENAI_RESPONSES_PROTOCOL:
        envelope = {
            "id": "responses-complete-json",
            "model": "m",
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": '{"status":"ok"}'}]}
            ],
        }
    else:
        envelope = {
            "id": "anthropic-complete-json",
            "model": "m",
            "stop_reason": "max_tokens",
            "content": [{"type": "text", "text": '{"status":"ok"}'}],
        }

    with pytest.raises(ApiError) as captured:
        _client(monkeypatch, protocol, envelope).complete_json(
            "system", {"task": "demo"}, {"type": "object"}
        )

    assert captured.value.kind == "truncated"
    assert captured.value.response_content == '{"status":"ok"}'


def test_transport_error_keeps_diagnostic_fields_empty() -> None:
    error = ApiError("timeout", "timed out", latency_ms=3, timeout_seconds=0.1)

    assert error.response_content == ""
    assert error.response_usage is None
    assert error.response_id is None
    assert error.response_model is None
    assert error.finish_reason is None


@pytest.mark.parametrize(
    ("protocol", "envelope", "finish_reason"),
    [
        (
            PROTOCOL_ID,
            {"choices": [{"finish_reason": "length", "message": {"content": None}}]},
            "length",
        ),
        (
            OPENAI_RESPONSES_PROTOCOL,
            {"status": "incomplete", "output": []},
            "incomplete",
        ),
        (
            ANTHROPIC_MESSAGES_PROTOCOL,
            {"stop_reason": "model_context_window_exceeded", "content": []},
            "model_context_window_exceeded",
        ),
    ],
)
def test_truncated_response_keeps_missing_metadata_missing(
    monkeypatch, protocol: str, envelope: dict, finish_reason: str
) -> None:
    envelope.update(id=17, model=[], usage="unavailable")
    with pytest.raises(ApiError) as captured:
        _client(monkeypatch, protocol, envelope).complete_json(
            "system", {"task": "demo"}, {"type": "object"}
        )

    error = captured.value
    assert error.kind == "truncated"
    assert error.response_content == ""
    assert error.response_usage is None
    assert error.response_id is None
    assert error.response_model is None
    assert error.finish_reason == finish_reason
