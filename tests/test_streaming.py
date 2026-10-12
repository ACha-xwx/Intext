"""Protocol and transport checks using synthetic SSE, with no external requests."""
from concurrent.futures import CancelledError
from io import BytesIO
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from promptsmith.api import ApiConfig, ApiError, ChatCompletionsClient
from promptsmith.streaming import StreamError, consume_sse, observe_stream, response_reasoning
from promptsmith.task_scope import TaskScope


def sse(*items):
    return b"".join(("data: " + (item if isinstance(item, str) else json.dumps(item, ensure_ascii=False))
                     + "\n\n").encode("utf-8") for item in items)


def chat(**delta):
    return {"choices": [{"index": 0, "delta": delta}]}


def test_chat_unicode_usage_refusal_and_terminal_without_waiting_for_eof():
    events = []
    response = BytesIO(b": heartbeat\n\n" + sse(
        {"id": "fixture", "model": "deepseek-flash", **chat(reasoning_content="先思考🧠\n\n")},
        chat(reasoning_content="e\u0301👩\u200d💻"), chat(content='{"ok":true}'),
        {"choices": [{"index": 0, "delta": {"refusal": "fixture"}, "finish_reason": "stop"}]},
        {"choices": [], "usage": {"total_tokens": 42}}, "[DONE]") + b"must not read after DONE")
    envelope, count, thought_chars, content_chars = consume_sse(response, "openai_chat_completions", lambda *e: events.append(e))
    assert envelope["usage"] == {"total_tokens": 42}
    assert envelope["choices"][0]["finish_reason"] == "stop"
    assert envelope["choices"][0]["message"]["refusal"] == "fixture"
    assert response_reasoning(envelope, "openai_chat_completions") == "先思考🧠\n\ne\u0301👩\u200d💻"
    assert content_chars == len('{"ok":true}') and thought_chars == len(events[0][1] + events[1][1])
    assert count == 5 and response.read() == b"must not read after DONE"


def test_anthropic_thinking_text_signature_and_usage():
    events = []
    response = BytesIO(sse(
        {"type": "message_start", "message": {"id": "ant", "usage": {"input_tokens": 7}}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "核对用户要求"}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "signed"}},
        {"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "# 标题"}},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 9}},
        {"type": "message_stop"}))
    envelope, *_ = consume_sse(response, "anthropic_messages", lambda *e: events.append(e))
    assert envelope["usage"] == {"input_tokens": 7, "output_tokens": 9}
    assert envelope["content"][0]["signature"] == "signed"
    assert response_reasoning(envelope, "anthropic_messages") == "核对用户要求"
    assert events == [("reasoning", "核对用户要求"), ("content", "# 标题")]


@pytest.mark.parametrize("status", ["completed", "incomplete"])
def test_responses_preserves_final_envelope_and_public_summary(status):
    events = []
    final = {"id": "resp", "status": status, "usage": {"total_tokens": 12},
             "incomplete_details": {"reason": "max_output_tokens"} if status == "incomplete" else None,
             "output": [{"type": "message", "content": [{"type": "output_text", "text": "完成"}]},
                        {"type": "reasoning", "summary": [{"type": "summary_text", "text": "摘要"}]}]}
    response = BytesIO(sse({"type": "response.reasoning_summary_text.delta", "delta": "摘要"},
                          {"type": "response.output_text.delta", "delta": "完成"},
                          {"type": "response."+status, "response": final}))
    envelope, *_ = consume_sse(response, "openai_responses", lambda *e: events.append(e))
    assert envelope == final
    assert response_reasoning(envelope, "openai_responses") == "摘要"
    assert events == [("reasoning", "摘要"), ("content", "完成")]


@pytest.mark.parametrize("ending", [b"", b"data: not-json\n\n", sse({"error": {"message": "provider failure"}}),
                                     b"data: \xff\n\n", sse({"choices": "invalid"})])
def test_broken_stream_keeps_reasoning_and_partial_content(ending):
    with pytest.raises(StreamError) as failure:
        consume_sse(BytesIO(sse(chat(reasoning_content="思考"), chat(content="部分")) + ending),
                    "openai_chat_completions", lambda *_: None)
    assert response_reasoning(failure.value.envelope, "openai_chat_completions") == "思考"
    assert failure.value.envelope["choices"][0]["message"]["content"] == "部分"


def test_cancellation_checked_during_read_before_emitting():
    scope = TaskScope()
    class CancelOnRead(BytesIO):
        def readline(self):
            scope.cancel()
            return super().readline()
    events = []
    with scope.activate(), pytest.raises(CancelledError):
        consume_sse(CancelOnRead(sse(chat(reasoning_content="迟到"))), "openai_chat_completions", lambda *e: events.append(e))
    assert events == []


@pytest.mark.parametrize("protocol,envelope", [
    ("openai_chat_completions", {"choices": [{"message": {"reasoning_content": ["wrong"]}}]}),
    ("openai_chat_completions", {"choices": "wrong"}),
    ("anthropic_messages", {"content": [{"type": "thinking", "thinking": None}]}),
    ("openai_responses", {"output": [{"type": "reasoning", "summary": None}]}),
])
def test_reasoning_extraction_does_not_break_buffered_response(protocol, envelope):
    assert response_reasoning(envelope, protocol) == ""


def test_transport_exposes_real_chunk_before_server_finishes(monkeypatch):
    arrived, release = threading.Event(), threading.Event()
    seen, results, failures = {}, [], []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            seen.update(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.end_headers()
            self.wfile.write(sse(chat(reasoning_content="正在核对🧠")))
            self.wfile.flush()
            assert release.wait(4)
            self.wfile.write(sse(chat(content='{"ok":true}'),
                {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}, "[DONE]"))
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    client = ChatCompletionsClient(ApiConfig(f"http://127.0.0.1:{server.server_port}/v1", "deepseek-flash", "synthetic-key", reasoning_effort="high"))
    events = []
    def capture(event):
        events.append(event)
        if event["event"] == "reasoning":
            arrived.set()
    def run():
        try:
            with observe_stream(capture):
                results.append(client.complete_json("fixture", {}, {}))
        except Exception as exc:
            failures.append(exc)
    thread = threading.Thread(target=run)
    thread.start()
    try:
        assert arrived.wait(3), failures
        assert not results and thread.is_alive() and not release.is_set()
        release.set()
        thread.join(4)
        assert not failures and results[0].content == '{"ok":true}'
        assert results[0].reasoning_content == "正在核对🧠"
        assert seen["stream"] is True and seen["thinking"] == {"type": "enabled"}
        assert seen["reasoning_effort"] == "high"
        assert [e["event"] for e in events] == ["start", "reasoning", "content", "end"]
    finally:
        release.set()
        thread.join(4)
        server.shutdown()
        server.server_close()
        server_thread.join(2)


@pytest.mark.parametrize("network_error", [None, TimeoutError("read timeout"), OSError("connection reset")])
def test_api_stream_failure_keeps_diagnostic_envelope(monkeypatch, network_error):
    class Response(BytesIO):
        headers = {"Content-Type": "text/event-stream"}
        def readline(self):
            value = super().readline()
            if not value and network_error:
                raise network_error
            return value
    monkeypatch.setattr("promptsmith.api.urlopen", lambda *a, **kw: Response(sse(chat(reasoning_content="思考"), chat(content="部分正文"))))
    client = ChatCompletionsClient(ApiConfig("https://example.invalid", "deepseek-flash", "synthetic-key"))
    events = []
    with observe_stream(events.append), pytest.raises(ApiError) as failure:
        client.complete_json("fixture", {}, {})
    assert failure.value.response_content == "部分正文"
    assert failure.value.reasoning_content == "思考"
    assert failure.value.response_envelope and failure.value.request_snapshot["body"]["stream"]
    assert failure.value.kind == ("timeout" if isinstance(network_error, TimeoutError) else "network" if network_error else "invalid_response")
    assert events[-1]["event"] == "failed"


def test_json_proxy_fallback_extracts_thought_without_requiring_sse(monkeypatch):
    body = {"choices": [{"message": {"content": '{"ok":true}', "reasoning_content": "公开思考"}, "finish_reason": "stop"}]}
    class Response(BytesIO):
        headers = {"Content-Type": "application/json"}
    monkeypatch.setattr("promptsmith.api.urlopen", lambda *a, **kw: Response(json.dumps(body).encode()))
    client = ChatCompletionsClient(ApiConfig("https://example.invalid", "deepseek-flash", "synthetic-key"))
    events = []
    with observe_stream(events.append):
        result = client.complete_json("fixture", {}, {})
    assert result.content == '{"ok":true}' and result.reasoning_content == "公开思考"
    assert [e["event"] for e in events] == ["start", "reasoning", "end"]


def test_length_finish_is_still_truncation_not_success(monkeypatch):
    class Response(BytesIO):
        headers = {"Content-Type": "text/event-stream"}
    monkeypatch.setattr("promptsmith.api.urlopen", lambda *a, **kw: Response(sse(
        chat(reasoning_content="很长的思考"), chat(content='{"partial":'),
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "length"}]}, "[DONE]")))
    client = ChatCompletionsClient(ApiConfig("https://example.invalid", "deepseek-flash", "synthetic-key"))
    with observe_stream(lambda _: None), pytest.raises(ApiError) as failure:
        client.complete_json("fixture", {}, {})
    assert failure.value.kind == "truncated"
    assert failure.value.response_content == '{"partial":'


@pytest.mark.parametrize("protocol,item", [
    ("anthropic_messages", {"type": "message_start", "message": "wrong"}),
    ("anthropic_messages", {"type": "content_block_start", "content_block": {"type": "text"}}),
    ("anthropic_messages", {"type": "content_block_delta", "index": 0, "delta": "wrong"}),
    ("openai_responses", {"type": "response.completed", "response": "wrong"}),
])
def test_malformed_protocol_event_is_recoverable_stream_error(protocol, item):
    with pytest.raises(StreamError):
        consume_sse(BytesIO(sse(item)), protocol, lambda *_: None)
