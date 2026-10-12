"""Explicit custom service families through the real client and local HTTP."""
import pytest

from promptsmith.api import ApiConfig, client_for_config
from promptsmith.m1 import M1Assets
from promptsmith.model_catalog import PROVIDER_PRESETS
from tests.test_provider_requests import provider_service


@pytest.mark.parametrize("family", ["OpenAI", "Anthropic", "xAI", "Google", "DeepSeek"])
def test_custom_alias_uses_selected_family_request_contract(provider_service, family, caplog):
    url, requests = provider_service
    client = client_for_config(ApiConfig(url, "private-alias", "disposable-request-key",
        provider="麻豆科技", model_provider=family, protocol=PROVIDER_PRESETS[family]["protocol"],
        reasoning_effort="max", max_tokens=16384, temperature=0.3, top_p=0.9))
    with caplog.at_level("DEBUG"):
        result = client.complete_json("Return JSON", {"goal": "PRIVATE-GOAL"}, M1Assets.load().output_schema)
    assert result.content == '{"status":"ok"}'
    body = requests[-1]["body"]
    assert body["model"] == "private-alias"
    if family in {"OpenAI", "xAI"}:
        assert requests[-1]["path"].endswith("/responses")
        assert body["reasoning"]["effort"] == ("xhigh" if family == "xAI" else "max")
        assert body["max_output_tokens"] == 16384
    elif family == "Anthropic":
        assert requests[-1]["path"].endswith("/messages")
        assert body["thinking"] == {"type": "adaptive", "display": "summarized"}
        assert body["output_config"]["effort"] == "max"
    elif family == "DeepSeek":
        assert body["thinking"] == {"type": "enabled"}
        assert body["reasoning_effort"] == "max"
        assert body["top_p"] == .95
    else:
        assert body["reasoning_effort"] == "high"
        assert body["temperature"] == .3 and body["top_p"] == .9
    if family in {"OpenAI", "Anthropic", "DeepSeek"}:
        assert "temperature" not in body
    assert "model_provider="+family in caplog.text
    assert "PRIVATE-GOAL" not in caplog.text and "disposable-request-key" not in caplog.text


@pytest.mark.parametrize("family,protocol", [("OpenAI", "openai_chat_completions"), ("DeepSeek", "anthropic_messages")])
@pytest.mark.parametrize("operation", ["test_connection", "complete_text", "complete_json"])
def test_custom_family_alternate_protocol_keeps_its_own_parameters(provider_service, family, protocol, operation):
    url, requests = provider_service
    # A conflicting known ID must still use the user's explicit chosen family.
    client = client_for_config(ApiConfig(url, "gemini-3.8-flash", "disposable-alt-key", provider="Custom relay",
        model_provider=family, protocol=protocol, reasoning_effort="max", max_tokens=16384, temperature=.3))
    if operation == "complete_json":
        client.complete_json("Return JSON", {"task":"demo"}, {"type":"object", "properties":{}, "required":[], "additionalProperties":False})
    elif operation == "complete_text":
        client.complete_text("Reply", "demo", max_output_tokens=100)
    else:
        client.test_connection()
    body = requests[-1]["body"]
    assert body["model"] == "gemini-3.8-flash"
    if family == "OpenAI":
        assert "max_completion_tokens" in body and "max_tokens" not in body
        assert body["reasoning_effort"] == "max" and "thinking" not in body
    else:
        assert body["thinking"] == {"type":"enabled"}
        assert body["output_config"] == {"effort":"max"}
