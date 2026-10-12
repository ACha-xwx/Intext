"""Responses compatibility through a real local gateway, with no paid calls."""

from contextlib import nullcontext
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest

from promptsmith.api import ApiConfig, ApiError, client_for_config, OPENAI_RESPONSES_PROTOCOL
from promptsmith.m1 import M1Assets
from promptsmith.m2 import M2Assets
from promptsmith.m3 import M3Assets
from promptsmith.m4 import M4Assets
from promptsmith.streaming import observe_stream


@pytest.fixture
def gateway():
    requests = []
    requirements = set()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            failure = None
            if "message_input" in requirements and not isinstance(body.get("input"), list):
                failure = "input must be a list of messages"
            elif "no_store" in requirements and body.get("store") is not False:
                failure = "store must be false"
            elif "prompt_contract" in requirements and body.get("text", {}).get("format", {}).get("type") == "json_object":
                failure = "json_object is not supported by this gateway"
            elif "json_input_instruction" in requirements and not any(
                "json" in part.get("text", "").lower()
                for message in body.get("input", []) for part in message.get("content", [])
            ):
                failure = "Response input messages must contain the word 'json' in some form to use 'text.format' of type 'json_object'."
            elif "service_failure" in requirements:
                failure = "The request could not be processed. Please check the request parameters."
            if failure:
                response = {"type": "response.failed", "response": {
                    "id": "resp-local-rejection", "status": "failed", "output": [],
                    "error": {"code": "invalid_request", "message": failure, "request_id": "gateway-fixture-request"},
                }}
            else:
                response = {"type": "response.completed", "response": {
                    "id": "resp-local-ok", "status": "completed",
                    "output": [{"type": "message", "content": [
                        {"type": "output_text", "text": '{"status":"ok"}'},
                    ]}],
                }}
            if "format_http_error" in requirements:
                encoded = json.dumps({"error": {"message": "text.format is not supported"}}).encode()
                content_type, status = "application/json", 400
            elif body.get("stream") and "buffered" not in requirements:
                encoded = ("data: " + json.dumps(response) + "\n\n").encode()
                content_type, status = "text/event-stream", 200
            else:
                encoded = json.dumps(response["response"]).encode()
                content_type, status = "application/json", 200
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", requests, requirements
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


@pytest.mark.parametrize("stream", [False, True])
def test_prompt_json_contract_is_visible_in_input_without_changing_original_business_text(gateway, stream, caplog):
    url, requests, requirements = gateway
    requirements.add("json_input_instruction")
    client = client_for_config(ApiConfig(
        url, "gpt-6.1-sol", "synthetic-gateway-key", protocol=OPENAI_RESPONSES_PROTOCOL,
        reasoning_effort="high", max_tokens=8192, timeout_seconds=3,
    ))
    with caplog.at_level("DEBUG"), observe_stream(lambda _: None) if stream else nullcontext():
        result = client.complete_json("整理目标。", {"goal": "PRIVATE-GOAL\n🧑‍💻"}, M1Assets.load().output_schema)
    assert result.content == '{"status":"ok"}' and len(requests) == 1
    body = requests[0]
    content = body["input"][0]["content"]
    assert len(content) == 2
    assert "JSON" in content[0]["text"] and content[0]["type"] == "input_text"
    assert content[1] == {"type": "input_text", "text": '{"goal":"PRIVATE-GOAL\\n🧑‍💻"}'}
    assert "text" not in body
    assert body["reasoning"] == {"effort": "high"} and body["max_output_tokens"] == 8192
    assert "PRIVATE-GOAL" not in caplog.text and "synthetic-gateway-key" not in caplog.text


@pytest.mark.parametrize("operation", ["test_connection", "complete_text", "complete_json"])
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("restriction", ["message_input", "no_store"])
def test_responses_calls_accept_compatible_gateways_without_losing_input(gateway, operation, stream, restriction, caplog):
    url, requests, requirements = gateway
    requirements.add(restriction)
    caplog.set_level("DEBUG", logger="promptsmith.api")
    client = client_for_config(ApiConfig(
        url, "gpt-6.1-sol", "synthetic-gateway-key", protocol=OPENAI_RESPONSES_PROTOCOL,
        reasoning_effort="high", max_tokens=16384, timeout_seconds=3,
    ))
    with observe_stream(lambda _: None) if stream else nullcontext():
        if operation == "test_connection":
            result = client.test_connection()
            expected_text, budget = "Reply with OK.", 8192
        elif operation == "complete_text":
            result = client.complete_text("保留完整指令。", "目标含换行\nUnicode 🧑‍💻", max_output_tokens=512)
            expected_text, budget = "目标含换行\nUnicode 🧑‍💻", 512
        else:
            result = client.complete_json("保留完整指令。", {"goal": "目标含换行\nUnicode 🧑‍💻"},
                                          M1Assets.load().output_schema)
            expected_text, budget = '{"goal":"目标含换行\\nUnicode 🧑‍💻"}', 16384
    assert result.content == '{"status":"ok"}'
    assert len(requests) == 1, "Compatibility must not repeat a generation."
    body = requests[0]
    content = body["input"][0]["content"]
    assert body["input"][0]["role"] == "user"
    assert content[-1] == {"type": "input_text", "text": expected_text}
    assert len(content) == (2 if operation == "complete_json" else 1)
    assert body["model"] == "gpt-6.1-sol" and body["reasoning"] == {"effort": "high"}
    assert body["max_output_tokens"] == budget
    assert body["store"] is False
    assert bool(body.get("stream")) == stream
    assert "input=message_items store=false" in caplog.text
    assert "synthetic-gateway-key" not in caplog.text and "Unicode" not in caplog.text


@pytest.mark.parametrize("assets_type", [M1Assets, M2Assets, M3Assets, M4Assets])
@pytest.mark.parametrize("stream", [False, True])
def test_business_schemas_work_without_gateway_json_mode_and_keep_full_contract(gateway, assets_type, stream, caplog):
    url, requests, requirements = gateway
    requirements.update({"message_input", "no_store", "prompt_contract"})
    assets = assets_type.load()
    before = deepcopy(assets.output_schema)
    client = client_for_config(ApiConfig(
        url, "gpt-6.1-sol", "synthetic-gateway-key", protocol=OPENAI_RESPONSES_PROTOCOL,
        reasoning_effort="high", max_tokens=8192, timeout_seconds=3,
    ))
    with caplog.at_level("DEBUG"), observe_stream(lambda _: None) if stream else nullcontext():
        result = client.complete_json(assets.system_prompt, {"goal": "PRIVATE-GOAL"}, assets.output_schema)
    assert result.content == '{"status":"ok"}' and len(requests) == 1
    body = requests[0]
    assert "text" not in body
    assert body["instructions"].startswith(assets.system_prompt)
    assert json.dumps(before, ensure_ascii=False, separators=(",", ":")) in body["instructions"]
    assert body["input"][0]["role"] == "user"
    assert body["input"][0]["content"][-1] == {"type": "input_text", "text": '{"goal":"PRIVATE-GOAL"}'}
    assert "JSON" in body["input"][0]["content"][0]["text"]
    assert assets.output_schema == before
    assert body["model"] == "gpt-6.1-sol" and body["reasoning"] == {"effort": "high"}
    assert body["max_output_tokens"] == 8192 and body["store"] is False
    assert "Responses prompt JSON contract selected" in caplog.text
    assert "output_format=prompt_text" in caplog.text
    assert "PRIVATE-GOAL" not in caplog.text and "synthetic-gateway-key" not in caplog.text


def test_prompt_contract_failure_does_not_retry_an_identical_request(gateway):
    url, requests, requirements = gateway
    requirements.add("format_http_error")
    client = client_for_config(ApiConfig(url, "gpt-6.1-sol", "synthetic-gateway-key",
                                         protocol=OPENAI_RESPONSES_PROTOCOL, timeout_seconds=3))
    with pytest.raises(ApiError) as failure:
        client.complete_json("Return JSON.", {}, M1Assets.load().output_schema)
    assert failure.value.status_code == 400
    assert len(requests) == 1, "No format was sent, so removing it cannot fix the rejection."
    assert "text" not in requests[0]


@pytest.mark.parametrize("stream,buffered", [(False, False), (True, False), (True, True)])
def test_gateway_failed_response_keeps_cause_and_request_id_for_both_transports(gateway, stream, buffered, caplog):
    url, requests, requirements = gateway
    requirements.add("service_failure")
    if buffered:
        requirements.add("buffered")
    client = client_for_config(ApiConfig(url, "gpt-6.1-sol", "synthetic-gateway-key",
                                         protocol=OPENAI_RESPONSES_PROTOCOL, timeout_seconds=3))
    feedback = []
    with caplog.at_level("DEBUG"), observe_stream(feedback.append) if stream else nullcontext():
        with pytest.raises(ApiError) as failure:
            client.complete_json("Return JSON.", {"goal": "PRIVATE-GOAL"}, M1Assets.load().output_schema)
    error = failure.value
    assert "The request could not be processed." in str(error)
    assert "request_id=gateway-fixture-request" in error.error_detail
    assert error.response_id == "resp-local-rejection" and error.status_code is None
    assert "gateway-fixture-request" in caplog.text
    assert len(requests) == 1
    assert "PRIVATE-GOAL" not in caplog.text and "synthetic-gateway-key" not in caplog.text
    if stream:
        assert feedback[-1]["event"] == "failed" and "gateway-fixture-request" in feedback[-1]["text"]
