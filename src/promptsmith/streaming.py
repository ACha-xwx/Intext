"""Optional worker-local SSE observation; business parsers still receive envelopes."""
from contextlib import contextmanager
from contextvars import ContextVar
import json

from .task_scope import check_cancelled

_observer = ContextVar("promptsmith_stream_observer", default=None)


@contextmanager
def observe_stream(callback):
    token = _observer.set(callback)
    try:
        yield
    finally:
        _observer.reset(token)


def stream_observed():
    return _observer.get() is not None


def publish(event, **values):
    callback = _observer.get()
    if callback is not None:
        callback({"event": event, **values})


class StreamError(ValueError):
    def __init__(self, message, envelope, *, kind="invalid_response"):
        super().__init__(message)
        self.envelope = envelope
        self.kind = kind


def consume_sse(response, protocol, emit):
    """Read complete UTF-8 SSE events, never read the whole HTTP response first."""
    content, reasoning, blocks = [], [], {}
    envelope = {}
    complete = False
    terminal = False
    data = []
    events = 0

    def snapshot():
        if protocol == "openai_chat_completions":
            return {**envelope, "choices": [{"index": 0, "finish_reason": envelope.get("finish_reason"),
                "message": {"role": "assistant", "content": "".join(content), "reasoning_content": "".join(reasoning)}}]}
        if protocol == "anthropic_messages":
            return {**envelope, "content": [blocks[i] for i in sorted(blocks)]}
        return {**envelope, "output": [{"type": "message", "content": [{"type": "output_text", "text": "".join(content)}]},
                                      {"type": "reasoning", "summary": [{"type": "summary_text", "text": "".join(reasoning)}]}]}

    def append(kind, value):
        if isinstance(value, str) and value:
            (reasoning if kind == "reasoning" else content).append(value)
            emit(kind, value)

    def handle(raw):
        nonlocal complete, terminal, envelope, events
        if raw == "[DONE]":
            complete = True
            terminal = True
            return
        try:
            item = json.loads(raw)
            if not isinstance(item, dict):
                raise ValueError("SSE data must be an object")
        except (ValueError, TypeError) as exc:
            raise StreamError("模型流式响应包含无法读取的数据，请重试。", snapshot()) from exc
        events += 1
        if item.get("error") or item.get("type") in {"error", "response.failed"}:
            envelope["stream_error"] = item
            raise StreamError("模型服务在流式输出期间返回错误，请检查 Debug 并重试。", snapshot())
        if protocol == "openai_chat_completions":
            for key in ("id", "model", "usage"):
                if item.get(key) is not None:
                    envelope[key] = item[key]
            choices = item.get("choices") or []
            if not isinstance(choices, list) or any(not isinstance(c, dict) for c in choices):
                raise StreamError("模型流式响应的消息格式无法读取，请重试。", snapshot())
            for choice in choices:
                if choice.get("index", 0) != 0:
                    continue
                delta = choice.get("delta") or {}
                if not isinstance(delta, dict):
                    raise StreamError("模型流式响应的增量格式无法读取，请重试。", snapshot())
                append("reasoning", delta.get("reasoning_content") or delta.get("reasoning"))
                append("content", delta.get("content"))
                if delta.get("refusal"):
                    envelope["refusal"] = delta["refusal"]
                if choice.get("finish_reason") is not None:
                    envelope["finish_reason"] = choice["finish_reason"]
                    complete = True
        elif protocol == "anthropic_messages":
            kind = item.get("type")
            if kind == "message_start":
                message = item.get("message") or {}
                if not isinstance(message, dict):
                    raise StreamError("模型流式消息格式无法读取，请重试。", snapshot())
                envelope.update(message)
            elif kind == "content_block_start":
                block = item.get("content_block") or {}
                if not isinstance(block, dict) or not isinstance(item.get("index"), int):
                    raise StreamError("模型流式内容块格式无法读取，请重试。", snapshot())
                block = dict(block)
                blocks[item["index"]] = block
                append("reasoning" if block.get("type") == "thinking" else "content", block.get("thinking") or block.get("text"))
            elif kind == "content_block_delta":
                delta = item.get("delta") or {}
                if not isinstance(delta, dict) or not isinstance(item.get("index"), int):
                    raise StreamError("模型流式增量格式无法读取，请重试。", snapshot())
                block = blocks.setdefault(item["index"], {"type": "text", "text": ""})
                key = "thinking" if delta.get("type") == "thinking_delta" else "text"
                value = delta.get(key)
                if isinstance(value, str):
                    block[key] = block.get(key, "") + value
                    append("reasoning" if key == "thinking" else "content", value)
                if isinstance(delta.get("signature"), str):
                    block["signature"] = block.get("signature", "") + delta["signature"]
            elif kind == "message_delta":
                delta = item.get("delta") or {}
                if not isinstance(delta, dict):
                    raise StreamError("模型流式结束信息无法读取，请重试。", snapshot())
                envelope.update(delta)
                usage, extra = envelope.get("usage"), item.get("usage")
                envelope["usage"] = {**(usage if isinstance(usage, dict) else {}), **(extra if isinstance(extra, dict) else {})}
            elif kind == "message_stop":
                complete = True
                terminal = True
        else:
            kind = item.get("type", "")
            if kind in {"response.output_text.delta", "response.reasoning_summary_text.delta", "response.reasoning_text.delta"}:
                append("content" if kind == "response.output_text.delta" else "reasoning", item.get("delta"))
            elif kind in {"response.completed", "response.incomplete"}:
                envelope = item.get("response") or {}
                if not isinstance(envelope, dict):
                    envelope = {}
                    raise StreamError("模型流式结束信息无法读取，请重试。", snapshot())
                complete = True
                terminal = True
            elif kind == "response.created":
                response_data = item.get("response") or {}
                if not isinstance(response_data, dict):
                    raise StreamError("模型流式响应信息无法读取，请重试。", snapshot())
                envelope.update(response_data)

    while True:
        check_cancelled()
        try:
            raw = response.readline()
        except TimeoutError as exc:
            raise StreamError("模型流式输出等待超时，已有内容保留，可以重试。", snapshot(), kind="timeout") from exc
        except OSError as exc:
            raise StreamError("模型流式连接中断，已有内容保留，请检查网络后重试。", snapshot(), kind="network") from exc
        check_cancelled()
        if not raw:
            if data:
                handle("\n".join(data))
            break
        try:
            line = raw.decode("utf-8").lstrip("\ufeff").rstrip("\r\n")
        except UnicodeDecodeError as exc:
            raise StreamError("模型流式响应字符编码不正确，请重试。", snapshot()) from exc
        if not line:
            if data:
                handle("\n".join(data))
                data.clear()
                if terminal:
                    break
        elif line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
        # Comments, heartbeat, event/id fields do not contain message text.
    if not complete:
        raise StreamError("模型流式连接提前结束，已有内容保留，可重新生成。", snapshot())
    final = snapshot()
    if protocol == "openai_responses" and isinstance(envelope.get("output"), list) and envelope["output"]:
        final = envelope
    if protocol == "openai_chat_completions" and envelope.get("refusal"):
        final["choices"][0]["message"]["refusal"] = envelope["refusal"]
    return final, events, len("".join(reasoning)), len("".join(content))


def response_reasoning(envelope, protocol):
    if not isinstance(envelope, dict):
        return ""
    if protocol == "openai_chat_completions":
        choices = envelope.get("choices") or []
        message = choices[0].get("message") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
        if not isinstance(message, dict):
            return ""
        value = message.get("reasoning_content") or message.get("reasoning")
        return value if isinstance(value, str) else ""
    if protocol == "anthropic_messages":
        blocks = envelope.get("content") or []
        return "\n".join(block["thinking"] for block in blocks if isinstance(block, dict)
                         and block.get("type") == "thinking" and isinstance(block.get("thinking"), str)) if isinstance(blocks, list) else ""
    output = envelope.get("output") or []
    if not isinstance(output, list):
        return ""
    values = []
    for item in output:
        if isinstance(item, dict) and item.get("type") == "reasoning" and isinstance(item.get("summary"), list):
            values.extend(block["text"] for block in item["summary"] if isinstance(block, dict) and isinstance(block.get("text"), str))
    return "\n".join(values)
