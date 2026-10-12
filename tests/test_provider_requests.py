"""Provider request contracts through the public client and local HTTP seam."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest

from promptsmith.api import ApiConfig, client_for_config, ANTHROPIC_MESSAGES_PROTOCOL
from promptsmith.m1 import M1Assets
from promptsmith.model_catalog import MODELS, PROVIDER_PRESETS


@pytest.fixture(scope="module")
def provider_service():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append({"path": self.path, "authorization": self.headers.get("Authorization"),
                             "x_api_key": self.headers.get("x-api-key"), "body": body})
            native_schema = body.get("output_config", {}).get("format", {}).get("schema", {})
            # Raw Claude structured outputs do not support minLength. M1
            # carries it; SDK helpers would transform it, urllib does not.
            if self.path.endswith("/messages") and '"minLength"' in json.dumps(native_schema):
                status = 400
                response = {"error": {"type": "invalid_request_error", "message": "Unsupported schema constraint: minLength"}}
            elif self.path.endswith("/messages"):
                status = 200
                response = {"stop_reason": "end_turn", "content": [{"type": "thinking", "thinking": "公开摘要"},
                                                                     {"type": "text", "text": '{"status":"ok"}'}]}
            elif self.path.endswith("/responses"):
                status = 200
                response = {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": '{"status":"ok"}'}]}]}
            else:
                status = 200
                response = {"choices": [{"finish_reason": "stop", "message": {"content": '{"status":"ok"}'}}]}
            encoded = json.dumps(response).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, *_args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}/v1", requests
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_claude_m1_keeps_full_contract_without_unsupported_native_schema(provider_service, caplog):
    url, requests = provider_service
    start = len(requests)
    assets = M1Assets.load()
    client = client_for_config(ApiConfig(url, "claude-opus-5-5", "synthetic-key", protocol=ANTHROPIC_MESSAGES_PROTOCOL,
                                         reasoning_effort="high", max_tokens=8192, timeout_seconds=3))
    with caplog.at_level("DEBUG"):
        result = client.complete_json(assets.system_prompt, {"goal": "PRIVATE-GOAL"}, assets.output_schema)
    assert result.content == '{"status":"ok"}' and result.reasoning_content == "公开摘要"
    assert len(requests) == start + 1
    body = requests[-1]["body"]
    assert body["output_config"] == {"effort": "high"}
    assert body["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert body["max_tokens"] == 8192
    assert json.dumps(assets.output_schema, ensure_ascii=False, separators=(",", ":")) in body["system"]
    assert "Anthropic prompt JSON contract selected" in caplog.text
    assert "PRIVATE-GOAL" not in caplog.text and "synthetic-key" not in caplog.text


@pytest.mark.parametrize("model", MODELS, ids=lambda model: model.id)
def test_all_presets_preserve_each_providers_request_contract(provider_service, model):
    url, requests = provider_service
    protocol = PROVIDER_PRESETS[model.provider]["protocol"]
    schema = M1Assets.load().output_schema
    expected_efforts = {
        "OpenAI": ("low", "medium", "high", "max"),
        "Anthropic": ("low", "medium", "high", "max"),
        "Google": ("low", "medium", "high", "high"),
        "DeepSeek": ("low", "high", "high", "max"),
        "xAI": ("low", "medium", "high", "high" if model.id == "grok-4.5" else "xhigh"),
    }[model.provider]
    for effort, expected in zip(("low", "medium", "high", "max"), expected_efforts):
        client = client_for_config(ApiConfig(url, model.id, "synthetic-key", protocol=protocol,
                                             reasoning_effort=effort, max_tokens=16384,
                                             temperature=1.5 if model.provider == "Anthropic" else 0.3,
                                             top_p=0.9, timeout_seconds=3))
        for operation, budget in (("test_connection", 8192), ("complete_text", 512), ("complete_json", 16384)):
            start = len(requests)
            if operation == "test_connection":
                result = client.test_connection()
            elif operation == "complete_text":
                result = client.complete_text("Return text.", "A task", max_output_tokens=512)
            else:
                result = client.complete_json("Return JSON.", {"task": "A task"}, schema)
            assert result.content == '{"status":"ok"}'
            assert len(requests) == start + 1
            request = requests[-1]
            body = request["body"]
            assert body["model"] == model.id
            if protocol == "anthropic_messages":
                assert request["path"] == "/v1/messages"
                assert request["x_api_key"] == "synthetic-key" and request["authorization"] is None
                assert body["thinking"] == {"type": "adaptive", "display": "summarized"}
                assert body["output_config"] == {"effort": expected}
                assert body["max_tokens"] == budget
                assert "reasoning" not in body and "reasoning_effort" not in body
            elif protocol == "openai_responses":
                assert request["path"] == "/v1/responses"
                assert request["authorization"] == "Bearer synthetic-key" and request["x_api_key"] is None
                assert body["reasoning"] == {"effort": expected}
                assert body["max_output_tokens"] == budget
                assert body["store"] is False
                assert isinstance(body["input"], list) and body["input"][0]["role"] == "user"
                assert "thinking" not in body and "max_tokens" not in body
            else:
                assert request["path"] == "/v1/chat/completions"
                assert request["authorization"] == "Bearer synthetic-key" and request["x_api_key"] is None
                assert body["reasoning_effort"] == expected and body["max_tokens"] == budget
                if model.provider == "DeepSeek":
                    assert body["thinking"] == {"type": "enabled"}
                else:
                    assert "thinking" not in body
            # Connection probes intentionally leave sampling to the service.
            if operation != "test_connection":
                if model.provider in {"OpenAI", "Anthropic", "DeepSeek"}:
                    assert "temperature" not in body
                    assert body.get("top_p") == (0.95 if model.provider == "DeepSeek" else None)
                else:
                    assert body["temperature"] == 0.3 and body["top_p"] == 0.9


def test_claude_optional_fields_can_use_its_own_native_schema_rules(provider_service):
    url, requests = provider_service
    schema = {"type": "object", "properties": {"optional": {"type": "string"}}, "additionalProperties": False}
    client = client_for_config(ApiConfig(url, "claude-opus-5-5", "synthetic-key", protocol=ANTHROPIC_MESSAGES_PROTOCOL,
                                         reasoning_effort="high", timeout_seconds=3))
    client.complete_json("Return JSON.", {"task": "demo"}, schema)
    assert requests[-1]["body"]["output_config"]["format"] == {"type": "json_schema", "schema": schema}
    assert requests[-1]["body"]["system"] == "Return JSON."


def test_deepseek_messages_sends_effort_without_claude_native_format(provider_service):
    url, requests = provider_service
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    client = client_for_config(ApiConfig(url, "deepseek-flash", "synthetic-key", protocol=ANTHROPIC_MESSAGES_PROTOCOL,
                                         reasoning_effort="max", timeout_seconds=3))
    client.complete_json("Return JSON.", {"task": "demo"}, schema)
    body = requests[-1]["body"]
    assert body["output_config"] == {"effort": "max"}
    assert body["thinking"] == {"type": "enabled"}
    assert json.dumps(schema, ensure_ascii=False, separators=(",", ":")) in body["system"]


def test_gpt_chat_compatibility_uses_completion_budget_without_deepseek_fields(provider_service):
    url, requests = provider_service
    client = client_for_config(ApiConfig(url, "gpt-6.1-sol", "synthetic-key", protocol="openai_chat_completions",
                                         reasoning_effort="high", max_tokens=16384, temperature=0.3, timeout_seconds=3))
    result = client.complete_json("Return JSON.", {"task": "demo"}, M1Assets.load().output_schema)
    body = requests[-1]["body"]
    assert result.content == '{"status":"ok"}'
    assert body["max_completion_tokens"] == 16384 and "max_tokens" not in body
    assert body["reasoning_effort"] == "high"
    assert "thinking" not in body and "reasoning" not in body and "temperature" not in body
    assert body["response_format"] == {"type": "json_object"}
