"""Responses wire compatibility, exercised against a local HTTP service."""

from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest

from promptsmith.api import ApiConfig, client_for_config, OPENAI_RESPONSES_PROTOCOL
from promptsmith.m1 import M1Assets
from promptsmith.m2 import M2Assets
from promptsmith.m3 import M3Assets
from promptsmith.m4 import M4Assets


@pytest.fixture
def responses_service():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            native = body.get("text", {}).get("format", {})
            schema = native.get("schema", {})
            # OpenAI strict mode rejects optional root properties. This is the
            # actual M1 incompatibility, independent of our format selection.
            optional = set(schema.get("properties", {})) - set(schema.get("required", []))
            if native.get("strict") and optional:
                status = 400
                response = {"error": {"message": "The request could not be processed. Please check the request parameters.",
                                      "code": "invalid_request", "type": "invalid_request_error",
                                      "param": "text.format.schema"}}
            else:
                status = 200
                response = {"status": "completed", "output": [{"type": "reasoning", "summary": []},
                    {"type": "message", "content": [{"type": "output_text", "text": '{"status":"ok"}'}]}]}
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


def test_m1_gpt_request_succeeds_once_without_invalid_strict_schema(responses_service, caplog):
    url, requests = responses_service
    assets = M1Assets.load()
    before = deepcopy(assets.output_schema)
    client = client_for_config(ApiConfig(url, "gpt-6.1-sol", "synthetic-key", protocol=OPENAI_RESPONSES_PROTOCOL,
                                         reasoning_effort="high", max_tokens=8192, timeout_seconds=3))
    with caplog.at_level("DEBUG"):
        result = client.complete_json(assets.system_prompt, {"goal": "PRIVATE-GOAL"}, assets.output_schema)
    assert result.content == '{"status":"ok"}'
    assert len(requests) == 1
    body = requests[0]
    assert body["text"]["format"] == {"type": "json_object"}
    assert json.dumps(before, ensure_ascii=False, separators=(",", ":")) in body["instructions"]
    assert assets.output_schema == before
    assert body["reasoning"] == {"effort": "high"}
    assert body["max_output_tokens"] == 8192 and "thinking" not in body
    assert result.reasoning_content == ""
    assert "JSON mode selected" in caplog.text
    assert "PRIVATE-GOAL" not in caplog.text and "synthetic-key" not in caplog.text


@pytest.mark.parametrize("assets_type", [M2Assets, M3Assets, M4Assets])
def test_later_stage_business_contracts_use_json_mode_without_loss(responses_service, assets_type):
    url, requests = responses_service
    assets = assets_type.load()
    schema = deepcopy(assets.output_schema)
    client = client_for_config(ApiConfig(url, "gpt-6.1-sol", "synthetic-key", protocol=OPENAI_RESPONSES_PROTOCOL,
                                         reasoning_effort="high", max_tokens=16384, timeout_seconds=3))
    assert client.complete_json(assets.system_prompt, {"stage": assets.contract_version}, schema).content
    assert len(requests) == 1
    assert requests[0]["text"]["format"] == {"type": "json_object"}
    assert json.dumps(schema, ensure_ascii=False, separators=(",", ":")) in requests[0]["instructions"]
    assert schema == assets.output_schema
    assert requests[0]["max_output_tokens"] == 16384


@pytest.mark.parametrize("schema", [
    {"type": "object", "properties": {"optional": {"type": "string"}}, "additionalProperties": False},
    {"type": "object", "properties": {}, "required": [], "additionalProperties": True},
    {"type": "object", "properties": {}, "required": [], "additionalProperties": False,
     "$defs": {"nested": {"type": "object", "properties": {"value": {"type": "string"}}, "additionalProperties": False}}},
    {"type": "object", "properties": {}, "required": [], "additionalProperties": False, "allOf": []},
    {"type": "object", "properties": {}, "required": [], "additionalProperties": False, "anyOf": [{"type": "object"}]},
    {"type": "object", "properties": {"value": True}, "required": ["value"], "additionalProperties": False},
])
def test_incompatible_schemas_do_not_become_native_strict_requests(responses_service, schema):
    url, requests = responses_service
    client = client_for_config(ApiConfig(url, "gpt-6.1-sol", "synthetic-key", protocol=OPENAI_RESPONSES_PROTOCOL,
                                         timeout_seconds=3))
    client.complete_json("Return the requested result.", {"task": "demo"}, schema)
    assert len(requests) == 1
    assert requests[0]["text"]["format"] == {"type": "json_object"}
    assert json.dumps(schema, ensure_ascii=False, separators=(",", ":")) in requests[0]["instructions"]


def test_closed_required_schema_keeps_native_strict_output(responses_service):
    url, requests = responses_service
    schema = {"type": "object", "properties": {"status": {"type": "string", "enum": ["ok", "error"]}},
              "required": ["status"], "additionalProperties": False}
    client = client_for_config(ApiConfig(url, "gpt-6.1-sol", "synthetic-key", protocol=OPENAI_RESPONSES_PROTOCOL,
                                         timeout_seconds=3))
    assert client.complete_json("Return status.", {"task": "demo"}, schema).content == '{"status":"ok"}'
    assert len(requests) == 1
    assert requests[0]["text"]["format"] == {
        "type": "json_schema", "name": "promptsmith_result", "schema": schema, "strict": True,
    }
    assert requests[0]["instructions"] == "Return status."
