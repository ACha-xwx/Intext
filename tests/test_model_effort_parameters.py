"""Request-body contracts from the provider documentation, no real model calls."""
from dataclasses import replace

import pytest

from promptsmith.api import (ANTHROPIC_MESSAGES_PROTOCOL, OPENAI_RESPONSES_PROTOCOL,
                            PROTOCOL_ID, ApiConfig, client_for_config,
                            sampling_request_parameters, structured_request_parameters)


@pytest.mark.parametrize("protocol", [PROTOCOL_ID, OPENAI_RESPONSES_PROTOCOL, ANTHROPIC_MESSAGES_PROTOCOL])
@pytest.mark.parametrize("model", ["deepseek-flash", "deepseek-v4-pro"])
@pytest.mark.parametrize("selected,actual", [("low", "low"), ("medium", "high"), ("high", "high"), ("max", "max")])
def test_deepseek_documented_effort_mapping_across_all_request_types(protocol, model, selected, actual, monkeypatch):
    base = "https://api.deepseek.com/anthropic" if protocol == ANTHROPIC_MESSAGES_PROTOCOL else "https://api.deepseek.com"
    config = ApiConfig(base, model, "synthetic", protocol=protocol, reasoning_effort=selected)
    client = client_for_config(config)
    requests = []
    monkeypatch.setattr(client, "_post", lambda body, **_kw: requests.append(body))
    client.complete_json("system", {"goal": "离线测试"}, {"type": "object", "properties": {}})
    client.complete_text("system", "离线测试")
    client.test_connection()
    assert len(requests) == 3
    for body in requests:
        if protocol == PROTOCOL_ID:
            assert body["thinking"] == {"type": "enabled"}
            assert body["reasoning_effort"] == actual
        elif protocol == OPENAI_RESPONSES_PROTOCOL:
            assert body["reasoning"] == {"effort": actual}
            assert "thinking" not in body and "reasoning_effort" not in body
        else:
            assert body["thinking"] == {"type": "enabled"}
            assert body["output_config"]["effort"] == actual
        assert body["model"] == model
    if protocol == ANTHROPIC_MESSAGES_PROTOCOL:
        assert "format" in requests[0]["output_config"]
    assert "temperature" not in sampling_request_parameters(config)


@pytest.mark.parametrize("model", ["gpt-6-astra", "gpt-6.1-sol"])
def test_gpt6_max_effort_and_chat_token_budget(model):
    config = ApiConfig("https://api.openai.com/v1", model, "synthetic", reasoning_effort="max", temperature=.7, top_p=.8)
    assert structured_request_parameters(config) == {"max_completion_tokens": 8192, "reasoning_effort": "max"}
    assert sampling_request_parameters(config) == {}
    response = replace(config, protocol=OPENAI_RESPONSES_PROTOCOL)
    assert structured_request_parameters(response)["reasoning"] == {"effort": "max"}


@pytest.mark.parametrize("model", ["claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"])
def test_latest_claude_uses_adaptive_effort_and_preserves_format(model, monkeypatch):
    config = ApiConfig("https://api.anthropic.com/v1", model, "synthetic", protocol=ANTHROPIC_MESSAGES_PROTOCOL, reasoning_effort="max")
    client = client_for_config(config)
    captured = []
    monkeypatch.setattr(client, "_post", lambda body, **_kw: captured.append(body))
    client.complete_json("system", {}, {"type": "object"})
    assert captured[0]["thinking"] == {"type": "adaptive"}
    assert captured[0]["output_config"] == {"effort": "max", "format": {"type": "json_schema", "schema": {"type": "object"}}}


@pytest.mark.parametrize("model,actual", [("grok-4.7", "xhigh"), ("grok-4.6", "xhigh"), ("grok-4.5", "high"), ("gemini-3.8-flash", "high"), ("gemini-3.1-pro-preview", "high")])
def test_max_maps_to_each_model_supported_upper_level(model, actual):
    config = ApiConfig("https://gateway.invalid/v1", model, "synthetic", reasoning_effort="max")
    assert structured_request_parameters(config)["reasoning_effort"] == actual


def test_custom_models_keep_explicit_effort_and_sampling():
    config = ApiConfig("https://custom.invalid/v1", "private-model", "synthetic", reasoning_effort="max", temperature=.6, top_p=.8)
    assert structured_request_parameters(config) == {"max_tokens": 8192, "reasoning_effort": "max"}
    assert sampling_request_parameters(config) == {"temperature": .6, "top_p": .8}
    assert "reasoning_effort" not in structured_request_parameters(replace(config, reasoning_effort="omit"))


def test_deepseek_uses_documented_top_p_floor():
    config = ApiConfig("https://api.deepseek.com", "deepseek-flash", "synthetic", top_p=.8, reasoning_effort="high")
    assert sampling_request_parameters(config) == {"top_p": .95}


@pytest.mark.parametrize("protocol,model,expected", [
    (PROTOCOL_ID, "gpt-6-astra", "max_completion_tokens"),
    (PROTOCOL_ID, "deepseek-flash", "thinking"),
    (ANTHROPIC_MESSAGES_PROTOCOL, "claude-opus-5-5", "output_config"),
])
def test_debug_logs_effective_generation_options_without_credentials_or_schema(protocol, model, expected, monkeypatch, caplog):
    import json
    from urllib.request import Request

    config = ApiConfig("https://offline.invalid/v1", model, "synthetic-secret", protocol=protocol, reasoning_effort="max")
    client = client_for_config(config)
    monkeypatch.setattr(client, "_send_json_impl", lambda *a, **kw: ({}, 1))
    body = {"model": model, **structured_request_parameters(config)}
    body.setdefault("output_config", {})["format"] = {"schema": {"private_task": "hidden-schema-content"}}
    request = Request("https://offline.invalid/v1", data=json.dumps(body).encode(), headers={"Authorization": "Bearer synthetic-secret"})
    with caplog.at_level("DEBUG", logger="promptsmith.api"):
        client._send_json(request, invalid_message="invalid")
    options = next(record.getMessage() for record in caplog.records if "Model request options" in record.getMessage())
    assert expected in options and "max" in options
    assert "synthetic-secret" not in caplog.text
    assert "hidden-schema-content" not in caplog.text
