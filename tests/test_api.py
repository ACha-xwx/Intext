from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse

import pytest

import promptsmith.api as api
from promptsmith.api import (
    ANTHROPIC_MESSAGES_PROTOCOL,
    LEGACY_PROTOCOL_ID,
    OPENAI_RESPONSES_PROTOCOL,
    PROTOCOL_ID,
    PROVIDER_ID,
    AnthropicMessagesClient,
    ApiConfig,
    ApiError,
    ChatCompletionsClient,
    OpenAIResponsesClient,
    client_for_config,
)


class Handler(BaseHTTPRequestHandler):
    status = 200
    response: dict = {}
    seen: dict = {}

    def do_GET(self) -> None:  # noqa: N802
        type(self).seen = {
            "path": self.path,
            "authorization": self.headers.get("Authorization"),
            "x_api_key": self.headers.get("x-api-key"),
            "anthropic_version": self.headers.get("anthropic-version"),
        }
        encoded = json.dumps(type(self).response).encode("utf-8")
        self.send_response(type(self).status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        type(self).seen = {
            "path": self.path,
            "authorization": self.headers.get("Authorization"),
            "x_api_key": self.headers.get("x-api-key"),
            "anthropic_version": self.headers.get("anthropic-version"),
            "body": json.loads(body.decode("utf-8")),
        }
        encoded = json.dumps(type(self).response).encode("utf-8")
        self.send_response(type(self).status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args) -> None:
        return


@pytest.fixture
def server():
    Handler.status = 200
    Handler.response = {}
    Handler.seen = {}
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


@pytest.mark.parametrize("protocol", [PROTOCOL_ID, OPENAI_RESPONSES_PROTOCOL, ANTHROPIC_MESSAGES_PROTOCOL])
def test_generation_defaults_to_120_seconds_for_each_protocol(protocol: str) -> None:
    config = ApiConfig(base_url="https://example.invalid/v1", model="model", api_key="key", protocol=protocol)

    assert config.timeout_seconds == 120
    assert api.DEFAULT_GENERATION_TIMEOUT_SECONDS == 120
    assert api.CONNECTION_TIMEOUT_SECONDS == 15
    assert api.STRUCTURED_OUTPUT_MAX_TOKENS == 8192


def test_api_error_timeout_metadata_is_optional() -> None:
    error = ApiError("authentication", "denied", 401, 12)

    assert error.timeout_seconds is None
    assert error.status_code == 401
    assert error.latency_ms == 12


@pytest.mark.parametrize("protocol", [PROTOCOL_ID, OPENAI_RESPONSES_PROTOCOL, ANTHROPIC_MESSAGES_PROTOCOL])
@pytest.mark.parametrize("operation", ["complete_json", "list_models"])
def test_delayed_local_http_timeout_records_actual_limit_without_retry(protocol: str, operation: str) -> None:
    requests: list[str] = []
    release_request = threading.Event()

    class DelayedHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            requests.append(self.path)
            release_request.wait(timeout=0.5)

        def do_POST(self) -> None:  # noqa: N802
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            self.do_GET()

        def log_message(self, format: str, *args) -> None:
            return

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), DelayedHandler)
    thread = threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    config = ApiConfig(
        base_url=f"http://127.0.0.1:{httpd.server_port}/v1",
        model="model",
        api_key="local-test-key",
        protocol=protocol,
        timeout_seconds=0.05,
    )
    try:
        client = client_for_config(config)
        with pytest.raises(ApiError) as captured:
            if operation == "complete_json":
                client.complete_json("system", {"task": "demo"}, {"type": "object"})
            else:
                client.list_models()

        error = captured.value
        assert error.kind == "timeout"
        assert error.timeout_seconds == 0.05
        assert "0.05" in str(error)
        assert error.latency_ms is not None and error.latency_ms >= 30
        assert error.status_code is None
        assert not hasattr(error, "usage")
        assert "local-test-key" not in str(error)
        assert len(requests) == 1
    finally:
        release_request.set()
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("operation", ["complete_json", "list_models"])
def test_direct_and_wrapped_timeouts_preserve_configured_limit(monkeypatch, wrapped: bool, operation: str) -> None:
    timeouts: list[float] = []

    def raise_timeout(request, *, timeout):
        timeouts.append(timeout)
        error = TimeoutError("local test timeout")
        raise URLError(error) if wrapped else error

    monkeypatch.setattr(api, "urlopen", raise_timeout)
    client = ChatCompletionsClient(
        ApiConfig(base_url="https://example.invalid/v1", model="model", api_key="key", timeout_seconds=0.125)
    )

    with pytest.raises(ApiError) as captured:
        if operation == "complete_json":
            client.complete_json("system", {"task": "demo"}, {"type": "object"})
        else:
            client.list_models()

    assert captured.value.kind == "timeout"
    assert captured.value.timeout_seconds == 0.125
    assert "0.125" in str(captured.value)
    assert captured.value.latency_ms is not None
    assert timeouts == [0.125]


def test_complete_json_sends_deepseek_json_object_protocol(server) -> None:
    Handler.response = {
        "id": "resp-1",
        "model": "test-model",
        "choices": [{"message": {"content": '{"status":"ok"}'}}],
        "usage": {"prompt_tokens": 8, "completion_tokens": 3, "total_tokens": 11},
    }
    config = ApiConfig(base_url=server, model="test-model", api_key="top-secret", timeout_seconds=3)
    result = ChatCompletionsClient(config).complete_json(
        "system prompt", {"task": "demo"}, {"type": "object", "properties": {}}
    )

    assert result.content == '{"status":"ok"}'
    assert result.usage["total_tokens"] == 11
    assert result.latency_ms >= 0
    assert Handler.seen["path"] == "/chat/completions"
    assert Handler.seen["authorization"] == "Bearer top-secret"
    assert Handler.seen["body"]["response_format"] == {"type": "json_object"}
    assert Handler.seen["body"]["temperature"] == 0
    assert Handler.seen["body"]["max_tokens"] == 8192
    assert '"type":"object"' in Handler.seen["body"]["messages"][0]["content"]
    assert Handler.seen["body"]["messages"][1]["content"] == '{"task":"demo"}'


def test_verified_deepseek_m2_budget_is_larger_and_provider_specific(server) -> None:
    Handler.response = {
        "id": "deepseek-result",
        "model": "deepseek-flash",
        "choices": [{"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}],
        "usage": {"total_tokens": 12},
    }
    verified = ApiConfig(
        base_url="https://api.deepseek.com",
        model="deepseek-flash",
        api_key="test-key",
    )
    request = ChatCompletionsClient(verified)
    monkey_response = api.urlopen

    def capture(request_obj, *, timeout):
        assert timeout == 120
        Handler.seen = {"body": json.loads(request_obj.data.decode("utf-8"))}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_args): return False
            def read(self): return json.dumps(Handler.response).encode("utf-8")
        return Response()

    api.urlopen = capture
    try:
        request.complete_json("system", {"task": "demo"}, {"type": "object"})
    finally:
        api.urlopen = monkey_response
    assert Handler.seen["body"]["max_tokens"] == 65536
    assert Handler.seen["body"]["reasoning_effort"] == "low"


@pytest.mark.parametrize(
    "config",
    [
        ApiConfig(base_url="https://proxy.example/api.deepseek.com", model="deepseek-flash", api_key="key"),
        ApiConfig(base_url="https://api.deepseek.com.evil.example", model="deepseek-flash", api_key="key"),
        ApiConfig(base_url="https://api.deepseek.com/v2", model="deepseek-flash", api_key="key"),
        ApiConfig(base_url="https://api.deepseek.com", model="deepseek-chat", api_key="key"),
    ],
)
def test_deepseek_specific_parameters_are_not_used_for_unverified_configs(config) -> None:
    parameters = api.structured_request_parameters(config)
    assert parameters == {"max_tokens": 8192}
    assert "reasoning_effort" not in parameters


@pytest.mark.parametrize(
    ("protocol", "expected"),
    [
        (PROTOCOL_ID, {"max_tokens": 8192}),
        (OPENAI_RESPONSES_PROTOCOL, {"max_output_tokens": 8192}),
        (ANTHROPIC_MESSAGES_PROTOCOL, {"max_tokens": 8192}),
    ],
)
def test_structured_output_limits_keep_protocol_specific_fields(protocol, expected) -> None:
    config = ApiConfig(
        base_url="https://example.invalid/v1",
        model="model",
        api_key="key",
        protocol=protocol,
        provider="custom",
    )
    assert api.structured_request_parameters(config) == expected


@pytest.mark.parametrize(
    ("protocol", "expected_path", "response", "assert_body"),
    [
        (
            PROTOCOL_ID,
            "/chat/completions",
            {"id": "text-1", "model": "test-model", "choices": [{"message": {"content": "plain result"}}], "usage": {"total_tokens": 7}},
            lambda body: body["messages"] == [
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "user request"},
            ] and body["max_tokens"] == 24,
        ),
        (
            OPENAI_RESPONSES_PROTOCOL,
            "/v1/responses",
            {"id": "text-2", "status": "completed", "model": "test-model", "output": [{"type": "message", "content": [{"type": "output_text", "text": "plain result"}]}], "usage": {"total_tokens": 8}},
            lambda body: body["instructions"] == "system prompt" and body["input"] == "user request" and body["max_output_tokens"] == 24,
        ),
        (
            ANTHROPIC_MESSAGES_PROTOCOL,
            "/v1/messages",
            {"id": "text-3", "type": "message", "model": "test-model", "content": [{"type": "text", "text": "plain result"}], "stop_reason": "end_turn", "usage": {"output_tokens": 8}},
            lambda body: body["system"] == "system prompt" and body["messages"] == [{"role": "user", "content": "user request"}] and body["max_tokens"] == 24,
        ),
    ],
)
def test_complete_text_uses_protocol_specific_plain_text_request(
    server, protocol, expected_path, response, assert_body
) -> None:
    Handler.response = response
    config = ApiConfig(
        base_url=f"{server}/v1" if protocol != PROTOCOL_ID else server,
        model="test-model",
        api_key="text-secret",
        protocol=protocol,
        timeout_seconds=3,
    )
    result = client_for_config(config).complete_text("system prompt", "user request", max_output_tokens=24)

    assert result.content == "plain result"
    assert result.usage is not None
    assert Handler.seen["path"] == expected_path
    assert assert_body(Handler.seen["body"])


def test_complete_text_rejects_unbounded_output_limit(server) -> None:
    config = ApiConfig(base_url=server, model="test-model", api_key="secret", timeout_seconds=3)
    with pytest.raises(ValueError):
        ChatCompletionsClient(config).complete_text("system", "request", max_output_tokens=0)


def test_full_chat_completions_endpoint_is_not_duplicated(server) -> None:
    Handler.response = {
        "choices": [{"message": {"content": "ok"}}],
        "usage": {},
    }
    config = ApiConfig(
        base_url=f"{server}/chat/completions", model="test-model", api_key="secret", timeout_seconds=3
    )

    ChatCompletionsClient(config).test_connection()

    assert Handler.seen["path"] == "/chat/completions"
    assert "response_format" not in Handler.seen["body"]


@pytest.mark.parametrize(
    ("protocol", "response", "limit_field"),
    [
        (
            PROTOCOL_ID,
            {"id": "chat-probe", "model": "test-model", "choices": [{"finish_reason": "length", "message": {"content": None}}]},
            "max_tokens",
        ),
        (
            OPENAI_RESPONSES_PROTOCOL,
            {"id": "responses-probe", "model": "test-model", "status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}, "output": []},
            "max_output_tokens",
        ),
        (
            ANTHROPIC_MESSAGES_PROTOCOL,
            {"id": "anthropic-probe", "model": "test-model", "stop_reason": "max_tokens", "content": []},
            "max_tokens",
        ),
    ],
)
def test_truncated_connection_probe_is_partial_success_but_generation_still_fails(
    server, protocol: str, response: dict, limit_field: str
) -> None:
    Handler.response = response
    client = client_for_config(
        ApiConfig(base_url=server, model="test-model", api_key="secret", protocol=protocol, timeout_seconds=3)
    )

    result = client.test_connection()

    assert result.probe_truncated is True
    assert result.model == "test-model"
    assert result.latency_ms is not None
    assert Handler.seen["body"][limit_field] == 8192
    with pytest.raises(ApiError) as captured:
        client.complete_text("system", "task", max_output_tokens=32)
    assert captured.value.kind == "truncated"


@pytest.mark.parametrize(
    ("protocol", "response"),
    [
        (PROTOCOL_ID, {"choices": []}),
        (OPENAI_RESPONSES_PROTOCOL, {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}}),
        (ANTHROPIC_MESSAGES_PROTOCOL, {"stop_reason": "max_tokens"}),
    ],
)
def test_malformed_truncated_probe_is_not_accepted(server, protocol: str, response: dict) -> None:
    Handler.response = response
    client = client_for_config(
        ApiConfig(base_url=server, model="test-model", api_key="secret", protocol=protocol, timeout_seconds=3)
    )
    with pytest.raises(ApiError) as captured:
        client.test_connection()
    assert captured.value.kind == "invalid_response"


def test_http_error_is_classified_without_exposing_key(server) -> None:
    Handler.status = 401
    secret = "sk-private-value"
    Handler.response = {"error": {"message": f"invalid credential {secret}"}}
    client = ChatCompletionsClient(
        ApiConfig(base_url=server, model="test-model", api_key=secret, timeout_seconds=3)
    )

    with pytest.raises(ApiError) as captured:
        client.test_connection()

    assert captured.value.kind == "authentication"
    assert captured.value.status_code == 401
    assert captured.value.error_detail == "invalid credential [redacted]"
    assert secret not in str(captured.value)
    assert secret not in repr(captured.value)


def test_api_config_repr_never_exposes_key() -> None:
    secret = "sk-private-value"
    config = ApiConfig(base_url="https://api.deepseek.com", model="deepseek-chat", api_key=secret)

    assert secret not in repr(config)


def test_provider_protocol_are_separate_and_legacy_protocol_is_normalized() -> None:
    config = ApiConfig(
        base_url="https://api.deepseek.com",
        model="deepseek-flash",
        api_key="secret",
        provider=PROVIDER_ID,
        protocol=LEGACY_PROTOCOL_ID,
    )

    assert config.provider == "deepseek"
    assert config.protocol == PROTOCOL_ID == "openai_chat_completions"


@pytest.mark.parametrize(
    ("base_suffix", "expected_path"),
    [
        ("", "/models"),
        ("/v1", "/v1/models"),
        ("/chat/completions", "/models"),
        ("/v1/chat/completions", "/v1/models"),
        ("/models", "/models"),
    ],
)
def test_list_models_uses_provider_directory_endpoint_and_bearer_auth(
    server, base_suffix: str, expected_path: str
) -> None:
    Handler.response = {
        "object": "list",
        "data": [
            {"id": "model-b", "object": "model", "owned_by": "provider"},
            {"id": "model-a", "object": "model", "owned_by": "provider"},
        ],
    }
    client = ChatCompletionsClient(
        ApiConfig(base_url=f"{server}{base_suffix}", model="manual-model", api_key="directory-secret", timeout_seconds=3)
    )

    result = client.list_models()

    assert result.model_ids == ["model-b", "model-a"]
    assert Handler.seen["path"] == expected_path
    assert Handler.seen["authorization"] == "Bearer directory-secret"


def test_list_models_allows_an_empty_service_result(server) -> None:
    Handler.response = {"object": "list", "data": []}
    client = ChatCompletionsClient(
        ApiConfig(base_url=server, model="manual-model", api_key="secret", timeout_seconds=3)
    )

    result = client.list_models()

    assert result.model_ids == []


@pytest.mark.parametrize(
    ("status", "kind"),
    [(401, "authentication"), (403, "authentication"), (404, "unsupported_endpoint")],
)
def test_list_models_classifies_expected_http_failures(server, status: int, kind: str) -> None:
    Handler.status = status
    Handler.response = {"error": {"message": "provider failure"}}
    client = ChatCompletionsClient(
        ApiConfig(base_url=server, model="manual-model", api_key="private-key", timeout_seconds=3)
    )

    with pytest.raises(ApiError) as captured:
        client.list_models()

    assert captured.value.kind == kind
    assert "private-key" not in str(captured.value)


@pytest.mark.parametrize(
    "response",
    [
        {"data": "not-a-list"},
        {"object": "list", "data": [{}]},
        {"object": "list", "data": [{"id": 123}]},
    ],
)
def test_list_models_rejects_unexpected_response_shapes(server, response: dict) -> None:
    Handler.response = response
    client = ChatCompletionsClient(
        ApiConfig(base_url=server, model="manual-model", api_key="secret", timeout_seconds=3)
    )

    with pytest.raises(ApiError) as captured:
        client.list_models()

    assert captured.value.kind == "invalid_response"


def test_malformed_provider_response_is_rejected(server) -> None:
    Handler.response = {"id": "bad", "choices": []}
    client = ChatCompletionsClient(
        ApiConfig(base_url=server, model="test-model", api_key="secret", timeout_seconds=3)
    )

    with pytest.raises(ApiError, match="响应格式") as captured:
        client.test_connection()

    assert captured.value.kind == "invalid_response"


@pytest.mark.parametrize("field", ["base_url", "model", "api_key"])
def test_required_configuration_is_checked(field) -> None:
    values = {"base_url": "https://api.deepseek.com", "model": "deepseek-chat", "api_key": "key"}
    values[field] = ""

    with pytest.raises(ValueError):
        ApiConfig(**values)


def test_custom_provider_and_all_supported_protocols_are_accepted() -> None:
    for protocol in (PROTOCOL_ID, OPENAI_RESPONSES_PROTOCOL, ANTHROPIC_MESSAGES_PROTOCOL):
        config = ApiConfig(
            base_url="https://example.invalid/v1",
            model="custom-model-id",
            api_key="secret",
            provider="my-private-service",
            protocol=protocol,
        )
        assert config.provider == "my-private-service"
        assert config.protocol == protocol


def test_client_factory_selects_real_protocol_adapter() -> None:
    common = dict(base_url="https://example.invalid/v1", model="model", api_key="key")
    assert isinstance(client_for_config(ApiConfig(**common, protocol=PROTOCOL_ID)), ChatCompletionsClient)
    assert isinstance(
        client_for_config(ApiConfig(**common, protocol=OPENAI_RESPONSES_PROTOCOL)),
        OpenAIResponsesClient,
    )
    assert isinstance(
        client_for_config(ApiConfig(**common, protocol=ANTHROPIC_MESSAGES_PROTOCOL)),
        AnthropicMessagesClient,
    )


def test_openai_responses_uses_its_endpoint_body_and_output_shape(server) -> None:
    Handler.response = {
        "id": "resp_1",
        "status": "completed",
        "model": "response-model",
        "output": [
            {"type": "reasoning", "summary": []},
            {
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {"type": "output_text", "text": '{"status":"ok"}', "annotations": []}
                ],
            },
        ],
        "usage": {"input_tokens": 8, "output_tokens": 3, "total_tokens": 11},
    }
    config = ApiConfig(
        base_url=f"{server}/v1",
        model="response-model",
        api_key="response-secret",
        protocol=OPENAI_RESPONSES_PROTOCOL,
        timeout_seconds=3,
    )

    result = OpenAIResponsesClient(config).complete_json(
        "system prompt", {"task": "demo"}, {"type": "object", "properties": {}}
    )

    assert result.content == '{"status":"ok"}'
    assert result.usage["total_tokens"] == 11
    assert Handler.seen["path"] == "/v1/responses"
    assert Handler.seen["authorization"] == "Bearer response-secret"
    assert Handler.seen["body"]["instructions"] == "system prompt"
    assert Handler.seen["body"]["input"] == '{"task":"demo"}'
    assert Handler.seen["body"]["max_output_tokens"] == 8192
    assert Handler.seen["body"]["text"]["format"] == {
        "type": "json_schema",
        "name": "promptsmith_result",
        "schema": {"type": "object", "properties": {}},
        "strict": True,
    }


@pytest.mark.parametrize("detail", [
    "json_schema is not supported",
    "This model does not support structured outputs",
    "Unknown parameter: 'text.format'",
    "Unsupported parameter: 'response_format'",
])
def test_openai_responses_retries_json_completion_without_schema_after_http_400(detail) -> None:
    requests: list[dict] = []

    class FallbackHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            requests.append(body)
            if len(requests) == 1:
                response = {"error": {"message": detail}}
                encoded = json.dumps(response).encode("utf-8")
                self.send_response(400)
            else:
                response = {
                    "id": "resp_fallback",
                    "status": "completed",
                    "output": [{
                        "type": "message",
                        "content": [{"type": "output_text", "text": '{"status":"ok"}'}],
                    }],
                }
                encoded = json.dumps(response).encode("utf-8")
                self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args) -> None:
            return

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), FallbackHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        schema = {"type": "object", "properties": {"status": {"type": "string"}}}
        client = OpenAIResponsesClient(
            ApiConfig(
                base_url=f"http://127.0.0.1:{httpd.server_port}/v1",
                model="response-model",
                api_key="key",
                protocol=OPENAI_RESPONSES_PROTOCOL,
                timeout_seconds=3,
            )
        )

        result = client.complete_json("system prompt", {"task": "demo"}, schema)

        assert result.content == '{"status":"ok"}'
        assert len(requests) == 2
        assert requests[0]["text"]["format"]["type"] == "json_schema"
        assert "text" not in requests[1]
        assert json.dumps(schema, ensure_ascii=False, separators=(",", ":")) in requests[1]["instructions"]
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


def test_openai_responses_does_not_retry_non_400_json_completion_error(server) -> None:
    Handler.status = 500
    Handler.response = {"error": {"message": "temporary provider failure"}}
    client = OpenAIResponsesClient(
        ApiConfig(
            base_url=f"{server}/v1",
            model="response-model",
            api_key="key",
            protocol=OPENAI_RESPONSES_PROTOCOL,
            timeout_seconds=3,
        )
    )

    with pytest.raises(ApiError) as captured:
        client.complete_json("system", {"task": "demo"}, {"type": "object"})

    assert captured.value.status_code == 500
    assert "temporary provider failure" in str(captured.value)


@pytest.mark.parametrize("detail", [
    "invalid max_output_tokens",
    "Invalid schema for response_format 'promptsmith_result': property 'pattern' is not supported",
    "text.format.schema contains an unsupported property: pattern",
    "Unsupported schema keyword for json_schema: pattern",
    "Unknown parameter: 'text.format.schema.additionalProperties'",
    "Unknown parameter: 'response_format.json_schema.schema.pattern'",
])
def test_openai_responses_does_not_retry_unrelated_http_400(detail) -> None:
    requests: list[dict] = []

    class BadRequestHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            requests.append(json.loads(self.rfile.read(length).decode("utf-8")))
            encoded = json.dumps({"error": {"message": detail}}).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args) -> None:
            return

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), BadRequestHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        client = OpenAIResponsesClient(
            ApiConfig(
                base_url=f"http://127.0.0.1:{httpd.server_port}/v1",
                model="response-model",
                api_key="synthetic-classification-secret",
                protocol=OPENAI_RESPONSES_PROTOCOL,
                timeout_seconds=3,
            )
        )
        with pytest.raises(ApiError) as captured:
            client.complete_json("system", {"task": "demo"}, {"type": "object"})
        assert captured.value.error_detail == detail
        assert len(requests) == 1
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


@pytest.mark.parametrize(
    ("response", "kind"),
    [
        ({"id": "r", "status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}}, "truncated"),
        (
            {
                "id": "r",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "refusal", "refusal": "declined"}],
                    }
                ],
            },
            "refusal",
        ),
    ],
)
def test_openai_responses_rejects_incomplete_and_refusal(server, response: dict, kind: str) -> None:
    Handler.response = response
    client = OpenAIResponsesClient(
        ApiConfig(
            base_url=f"{server}/v1",
            model="response-model",
            api_key="key",
            protocol=OPENAI_RESPONSES_PROTOCOL,
            timeout_seconds=3,
        )
    )

    with pytest.raises(ApiError) as captured:
        client.complete_text("system", "task")

    assert captured.value.kind == kind


def test_anthropic_messages_uses_protocol_headers_body_and_text_blocks(server) -> None:
    Handler.response = {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-custom",
        "content": [
            {"type": "thinking", "thinking": "hidden"},
            {"type": "text", "text": '{"status":"ok"}'},
        ],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 8, "output_tokens": 3},
    }
    config = ApiConfig(
        base_url=f"{server}/v1",
        model="claude-custom",
        api_key="anthropic-secret",
        provider="anthropic",
        protocol=ANTHROPIC_MESSAGES_PROTOCOL,
        timeout_seconds=3,
    )

    result = AnthropicMessagesClient(config).complete_json(
        "system prompt", {"task": "demo"}, {"type": "object", "properties": {}}
    )

    assert result.content == '{"status":"ok"}'
    assert result.usage == {"input_tokens": 8, "output_tokens": 3}
    assert Handler.seen["path"] == "/v1/messages"
    assert Handler.seen["authorization"] is None
    assert Handler.seen["x_api_key"] == "anthropic-secret"
    assert Handler.seen["anthropic_version"] == "2023-06-01"
    assert Handler.seen["body"]["system"] == "system prompt"
    assert Handler.seen["body"]["max_tokens"] == 8192
    assert Handler.seen["body"]["messages"] == [
        {"role": "user", "content": '{"task":"demo"}'}
    ]
    assert Handler.seen["body"]["output_config"]["format"] == {
        "type": "json_schema",
        "schema": {"type": "object", "properties": {}},
    }


def test_anthropic_messages_rejects_truncation_and_lists_models_with_own_headers(server) -> None:
    config = ApiConfig(
        base_url=f"{server}/v1",
        model="claude-custom",
        api_key="anthropic-secret",
        provider="anthropic",
        protocol=ANTHROPIC_MESSAGES_PROTOCOL,
        timeout_seconds=3,
    )
    client = AnthropicMessagesClient(config)
    Handler.response = {
        "id": "msg_1",
        "content": [{"type": "text", "text": "partial"}],
        "stop_reason": "max_tokens",
        "usage": {"input_tokens": 1, "output_tokens": 8},
    }
    with pytest.raises(ApiError) as captured:
        client.complete_text("system", "task")
    assert captured.value.kind == "truncated"

    Handler.response = {"data": [{"id": "claude-one"}], "has_more": False, "last_id": None}
    result = client.list_models()
    assert result.model_ids == ["claude-one"]
    assert Handler.seen["path"] == "/v1/models?limit=1000"
    assert Handler.seen["x_api_key"] == "anthropic-secret"
    assert Handler.seen["anthropic_version"] == "2023-06-01"


def test_anthropic_model_directory_follows_bounded_after_id_pages() -> None:
    requests: list[str] = []

    class PaginatedHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            requests.append(self.path)
            cursor = parse_qs(urlparse(self.path).query).get("after_id", [None])[0]
            if cursor is None:
                response = {
                    "data": [{"id": "custom-a"}],
                    "has_more": True,
                    "last_id": "custom-a",
                }
            else:
                response = {
                    "data": [{"id": "custom-b"}],
                    "has_more": False,
                    "last_id": None,
                }
            raw = json.dumps(response).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format: str, *args) -> None:
            return

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), PaginatedHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        client = AnthropicMessagesClient(
            ApiConfig(
                base_url=f"http://127.0.0.1:{httpd.server_port}/v1",
                model="custom-model",
                api_key="custom-secret",
                provider="custom-anthropic-compatible",
                protocol=ANTHROPIC_MESSAGES_PROTOCOL,
                timeout_seconds=3,
            )
        )

        result = client.list_models()

        assert result.model_ids == ["custom-a", "custom-b"]
        assert requests == ["/v1/models?limit=1000", "/v1/models?limit=1000&after_id=custom-a"]
    finally:
        httpd.shutdown()
        thread.join(timeout=2)
