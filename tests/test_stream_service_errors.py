"""Public client diagnostics for HTTP-success streams with service errors."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest

from promptsmith.api import ApiConfig, ApiError, client_for_config, OPENAI_RESPONSES_PROTOCOL
from promptsmith.streaming import observe_stream


@pytest.fixture
def stream_service():
    events = []
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            encoded = b"".join(("data: " + json.dumps(event, ensure_ascii=False) + "\n\n").encode("utf-8")
                               for event in events)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", events, requests
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def test_service_error_is_visible_in_api_failure_debug_and_stream_feedback(stream_service, caplog):
    url, events, requests = stream_service
    events.append({"type": "error", "code": "permission_denied", "param": "model",
                   "message": "The model is not enabled for this account."})
    client = client_for_config(ApiConfig(url, "gpt-6.1-sol", "synthetic-stream-key",
                                         protocol=OPENAI_RESPONSES_PROTOCOL, timeout_seconds=3))
    feedback = []
    with caplog.at_level("DEBUG"), observe_stream(feedback.append), pytest.raises(ApiError) as failure:
        client.complete_json("Return a JSON object.", {"goal": "test"}, {"type": "object"})
    error = failure.value
    assert "The model is not enabled for this account." in str(error)
    assert "permission_denied" in error.error_detail and "model" in error.error_detail
    assert "permission_denied" in caplog.text
    assert "permission_denied" in feedback[-1]["text"] and feedback[-1]["event"] == "failed"
    assert error.response_envelope["stream_error"]["param"] == "model"
    assert len(requests) == 1, "A provider error must not silently repeat a paid generation."


def test_failed_response_preserves_nested_service_reason_usage_and_partial_output(stream_service):
    url, events, requests = stream_service
    events.extend([
        {"type": "response.created", "response": {"id": "resp-created", "model": "gpt-6.1-sol"}},
        {"type": "response.reasoning_summary_text.delta", "delta": "公开摘要"},
        {"type": "response.output_text.delta", "delta": "部分正文"},
        {"type": "response.failed", "response": {
            "id": "resp-upstream", "model": "actual-gpt", "status": "failed",
            "usage": {"input_tokens": 15, "output_tokens": 7},
            "error": {"code": "server_error", "message": "Upstream capacity unavailable.", "param": None},
        }},
    ])
    client = client_for_config(ApiConfig(url, "gpt-6.1-sol", "synthetic-stream-key",
                                         protocol=OPENAI_RESPONSES_PROTOCOL, timeout_seconds=3))
    with observe_stream(lambda _: None), pytest.raises(ApiError) as failure:
        client.complete_json("Return a JSON object.", {"goal": "test"}, {"type": "object"})
    error = failure.value
    assert "Upstream capacity unavailable." in str(error) and "server_error" in error.error_detail
    assert error.response_id == "resp-upstream" and error.response_model == "actual-gpt"
    assert error.response_usage == {"input_tokens": 15, "output_tokens": 7}
    assert error.reasoning_content == "公开摘要" and error.response_content == "部分正文"
    assert error.response_envelope["stream_error"]["response"]["status"] == "failed"
    assert error.status_code is None, "HTTP 200 is not a provider HTTP 400."
    assert len(requests) == 1


@pytest.mark.parametrize("protocol, model", [
    ("openai_chat_completions", "deepseek-flash"),
    ("openai_responses", "gpt-6.1-sol"),
    ("anthropic_messages", "claude-opus-5-5"),
])
def test_stream_error_details_are_redacted_and_complete_in_debug(stream_service, caplog, protocol, model):
    url, events, requests = stream_service
    secret = "synthetic-private-api-key-83972"
    message = f"Credential {secret} Bearer another-private-token " + "upstream detail " * 60 + "END-OF-DIAGNOSTIC"
    events.append({"type": "error", "error": {
        "message": message, "code": "upstream_rejected", "type": "invalid_request_error", "param": "model",
    }})
    client = client_for_config(ApiConfig(url, model, secret, protocol=protocol, timeout_seconds=3))
    with caplog.at_level("DEBUG"), observe_stream(lambda _: None), pytest.raises(ApiError) as failure:
        client.complete_json("Return a JSON object.", {"goal": "PRIVATE-USER-GOAL"}, {"type": "object"})
    assert "upstream_rejected" in failure.value.error_detail
    assert "END-OF-DIAGNOSTIC" in caplog.text, "Debug must retain details beyond the short UI excerpt."
    assert secret not in caplog.text and "another-private-token" not in caplog.text
    assert secret not in str(failure.value) and "another-private-token" not in str(failure.value)
    assert "PRIVATE-USER-GOAL" not in caplog.text
    assert len(requests) == 1


def test_empty_service_error_does_not_invent_a_provider_reason(stream_service):
    url, events, requests = stream_service
    events.append({"type": "error", "error": {}})
    client = client_for_config(ApiConfig(url, "gpt-6.1-sol", "synthetic-stream-key",
                                         protocol=OPENAI_RESPONSES_PROTOCOL, timeout_seconds=3))
    with observe_stream(lambda _: None), pytest.raises(ApiError) as failure:
        client.complete_json("Return a JSON object.", {}, {"type": "object"})
    assert failure.value.response_envelope["stream_error"] == {"type": "error", "error": {}}
    assert failure.value.status_code is None
    assert "400" not in str(failure.value) and "permission_denied" not in failure.value.error_detail
    assert len(requests) == 1


def test_generic_gateway_rejection_exposes_the_service_request_id_without_guessing_a_parameter(stream_service, caplog):
    url, events, requests = stream_service
    events.append({
        "type": "response.failed", "request_id": "gateway-request-fixture",
        "response": {
            "id": "resp-gateway-fixture", "model": "gpt-6.1-sol", "object": "response", "output": [], "status": "failed",
            "error": {"code": "invalid_request", "type": "invalid_request_error",
                      "message": "The request could not be processed. Please check the request parameters.",
                      "request_id": "gateway-request-fixture"},
        },
    })
    client = client_for_config(ApiConfig(url, "gpt-6.1-sol", "synthetic-stream-key",
                                         protocol=OPENAI_RESPONSES_PROTOCOL, timeout_seconds=3))
    feedback = []
    with caplog.at_level("DEBUG"), observe_stream(feedback.append), pytest.raises(ApiError) as failure:
        client.complete_json("Return a JSON object.", {}, {"type": "object"})
    assert "gateway-request-fixture" in str(failure.value)
    assert "request_id=gateway-request-fixture" in failure.value.error_detail
    assert "gateway-request-fixture" in caplog.text and "gateway-request-fixture" in feedback[-1]["text"]
    assert failure.value.response_id == "resp-gateway-fixture"
    assert failure.value.status_code is None
    assert "text.format" not in str(failure.value), "A generic rejection does not identify the bad parameter."
    assert len(requests) == 1
