from __future__ import annotations

from uuid import uuid4
from .streaming import consume_sse, StreamError, stream_observed, publish, response_reasoning

import json
import logging
import math
import re
import socket
import time
from concurrent.futures import CancelledError
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from .task_scope import check_cancelled, interrupt_on_cancel
from .model_catalog import find_model
from .model_input import prepare_json_input, log_response_usage


PROVIDER_ID = "deepseek"
PROTOCOL_ID = "openai_chat_completions"
OPENAI_RESPONSES_PROTOCOL = "openai_responses"
ANTHROPIC_MESSAGES_PROTOCOL = "anthropic_messages"
LEGACY_PROTOCOL_ID = "deepseek_chat_completions"
DEFAULT_GENERATION_TIMEOUT_SECONDS = 120
CONNECTION_TIMEOUT_SECONDS = 15
STRUCTURED_OUTPUT_MAX_TOKENS = 8192
DEEPSEEK_STRUCTURED_OUTPUT_MAX_TOKENS = 65536
HTTP_ERROR_DETAIL_MAX_CHARS = 512
SUPPORTED_PROTOCOLS = {
    PROTOCOL_ID,
    OPENAI_RESPONSES_PROTOCOL,
    ANTHROPIC_MESSAGES_PROTOCOL,
}


class ApiError(RuntimeError):
    def __init__(
        self,
        kind: str,
        message: str,
        status_code: int | None = None,
        latency_ms: int | None = None,
        timeout_seconds: float | None = None,
        response_content: str = "",
        response_usage: dict[str, Any] | None = None,
        response_id: str | None = None,
        response_model: str | None = None,
        finish_reason: str | None = None,
        error_detail: str = "",
    ):
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code
        self.latency_ms = latency_ms
        self.timeout_seconds = timeout_seconds
        # These fields are diagnostics only.  A response that raised ApiError
        # must never be treated as a successful completion by callers.
        self.response_content = response_content
        self.response_usage = response_usage
        self.response_id = response_id
        self.response_model = response_model
        self.finish_reason = finish_reason
        self.error_detail = error_detail


@dataclass(frozen=True)
class ApiConfig:
    base_url: str
    model: str
    api_key: str = field(repr=False)
    timeout_seconds: float = DEFAULT_GENERATION_TIMEOUT_SECONDS
    provider: str = PROVIDER_ID
    protocol: str = PROTOCOL_ID
    max_tokens: int | None = None
    temperature: float | str | None = "auto"
    top_p: float | None = None
    reasoning_effort: str = "auto"

    def __post_init__(self) -> None:
        for name in ("base_url", "model", "api_key", "provider", "protocol"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name}不能为空。")
        object.__setattr__(self, "provider", self.provider.strip())
        normalized_protocol = PROTOCOL_ID if self.protocol == LEGACY_PROTOCOL_ID else self.protocol
        if normalized_protocol not in SUPPORTED_PROTOCOLS:
            raise ValueError(f"当前版本不支持协议：{normalized_protocol}")
        object.__setattr__(self, "protocol", normalized_protocol)
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds必须大于0。")
        if self.max_tokens is not None and (isinstance(self.max_tokens, bool) or not isinstance(self.max_tokens, int) or not 1 <= self.max_tokens <= 262144):
            raise ValueError("max_tokens必须是1到262144之间的整数，或使用自动值。")
        model = find_model(self.model)
        sampling_adapted = bool(model and model.provider in {"OpenAI", "Anthropic", "DeepSeek"})
        for name, maximum in (("temperature", 1 if normalized_protocol == ANTHROPIC_MESSAGES_PROTOCOL and not sampling_adapted else 2), ("top_p", 1)):
            value = getattr(self, name)
            if value is None or (name == "temperature" and value == "auto"):
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= maximum:
                raise ValueError(f"{name}必须在0到{maximum}之间，或留空使用服务端默认。")
        if normalized_protocol == ANTHROPIC_MESSAGES_PROTOCOL and not sampling_adapted and self.temperature not in (None, "auto") and self.top_p is not None:
            raise ValueError("Anthropic Messages 请只设置 temperature 或 top_p 中的一项。")
        if self.reasoning_effort not in {"auto", "omit", "low", "medium", "high", "max"}:
            raise ValueError("推理强度无效。")


@dataclass(frozen=True)
class ApiResult:
    content: str
    latency_ms: int | None
    usage: dict[str, Any] | None
    response_id: str | None
    model: str | None
    probe_truncated: bool = False
    finish_reason: str | None = None
    request_snapshot: dict[str, Any] | None = None
    response_envelope: dict[str, Any] | None = None

    reasoning_content: str = ""

    @classmethod
    def from_error(cls, error: ApiError) -> "ApiResult":
        return cls(
        error.response_content, error.latency_ms, error.response_usage,
            error.response_id, error.response_model, finish_reason=error.finish_reason,
            request_snapshot=getattr(error, "request_snapshot", None),
            response_envelope=getattr(error, "response_envelope", None),
            reasoning_content=getattr(error, "reasoning_content", ""),
        )


@dataclass(frozen=True)
class ModelListResult:
    model_ids: list[str]
    latency_ms: int | None


def _validate_output_limit(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 4096:
        raise ValueError("max_output_tokens必须是1到4096之间的整数。")


def _is_verified_deepseek(config: ApiConfig) -> bool:
    """Enable DeepSeek-only generation options for the verified endpoint/model."""
    parsed = urlsplit(config.base_url.strip())
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/").lower()
    if parsed.scheme != "https" or host != "api.deepseek.com" or parsed.query or parsed.fragment:
        return False
    paths = {
        PROTOCOL_ID: {"", "/v1", "/chat/completions", "/v1/chat/completions"},
        OPENAI_RESPONSES_PROTOCOL: {"", "/v1", "/responses", "/v1/responses"},
        ANTHROPIC_MESSAGES_PROTOCOL: {"/anthropic", "/anthropic/v1", "/anthropic/messages", "/anthropic/v1/messages"},
    }
    return path in paths[config.protocol] and config.model.strip() in {"deepseek-flash", "deepseek-v4-pro"}


def structured_request_parameters(config: ApiConfig) -> dict[str, Any]:
    """Return only protocol/provider parameters that this request may send."""
    verified = _is_verified_deepseek(config)
    limit = config.max_tokens or (DEEPSEEK_STRUCTURED_OUTPUT_MAX_TOKENS if verified else STRUCTURED_OUTPUT_MAX_TOKENS)
    parameters = reasoning_request_parameters(config)
    if config.protocol == OPENAI_RESPONSES_PROTOCOL:
        return {"max_output_tokens": limit, **parameters}
    if config.protocol == ANTHROPIC_MESSAGES_PROTOCOL:
        return {"max_tokens": limit, **parameters}
    # GPT-6 Chat Completions budgets include both reasoning and visible output.
    model = find_model(config.model)
    key = "max_completion_tokens" if model and model.provider == "OpenAI" else "max_tokens"
    return {key: limit, **parameters}


def reasoning_request_parameters(config: ApiConfig) -> dict[str, Any]:
    """Translate the four UI levels to documented provider/protocol values."""
    model = find_model(config.model)
    effort = "low" if config.reasoning_effort == "auto" and _is_verified_deepseek(config) else config.reasoning_effort
    if effort in {"auto", "omit"}:
        return {}
    actual = model.map_effort(effort) if model else effort
    if actual != effort:
        logging.getLogger(__name__).debug("Thinking effort mapped: model=%s selected=%s effective=%s", config.model, effort, actual)
    if config.protocol == OPENAI_RESPONSES_PROTOCOL:
        return {"reasoning": {"effort": actual}}
    if config.protocol == ANTHROPIC_MESSAGES_PROTOCOL:
        thinking = {"thinking": {"type": "enabled"}} if model and model.provider == "DeepSeek" else (
            {"thinking": {"type": "adaptive", "display": "summarized"}} if model and model.adaptive else {})
        return {**thinking, "output_config": {"effort": actual}}
    thinking = {"thinking": {"type": "enabled"}} if model and model.provider == "DeepSeek" else {}
    return {**thinking, "reasoning_effort": actual}


def bounded_request_parameters(config: ApiConfig, limit: int) -> dict[str, Any]:
    """Connection probes and text completions share generation's effort mapping."""
    key = ("max_output_tokens" if config.protocol == OPENAI_RESPONSES_PROTOCOL else
           "max_completion_tokens" if config.protocol == PROTOCOL_ID and (model := find_model(config.model)) and model.provider == "OpenAI" else "max_tokens")
    return {key: limit, **reasoning_request_parameters(config)}


def sampling_request_parameters(config: ApiConfig) -> dict[str, Any]:
    parameters = {}
    model = find_model(config.model)
    # These providers ignore or reject temperature during reasoning. Omit it
    # rather than present a setting as effective when the API does not use it.
    no_temperature = bool(model and model.provider in {"OpenAI", "Anthropic", "DeepSeek"})
    temperature = 0 if config.temperature == "auto" and config.protocol == PROTOCOL_ID else config.temperature
    if temperature not in (None, "auto") and not no_temperature:
        parameters["temperature"] = temperature
    if config.top_p is not None:
        if not model or model.provider not in {"OpenAI", "Anthropic"}:
            parameters["top_p"] = max(.95, config.top_p) if model and model.provider == "DeepSeek" else config.top_p
    if no_temperature and (temperature not in (None, "auto") or config.top_p is not None):
        logging.getLogger(__name__).debug("Sampling parameters adapted for thinking model=%s; effective=%s", config.model, parameters)
    return parameters


class _HttpClient:
    protocol_name = "模型协议"

    def __init__(self, config: ApiConfig):
        self.config = config
        # Diagnostics for the immediately preceding request.  Workflow
        # evidence consumes these before the client is reused.
        self.last_request_snapshot: dict[str, Any] | None = None
        self.last_response_envelope: dict[str, Any] | None = None

    @staticmethod
    def _endpoint(base_url: str, suffix: str, known_suffixes: tuple[str, ...]) -> str:
        base = base_url.strip().rstrip("/")
        for known in known_suffixes:
            if base.endswith(known):
                base = base[: -len(known)].rstrip("/")
                break
        return f"{base}{suffix}"

    def _elapsed(self, started: float) -> int:
        return round((time.perf_counter() - started) * 1000)

    def _http_error_detail(self, error: HTTPError) -> str:
        """Extract a short, redacted provider diagnostic from an HTTP error body."""
        try:
            raw = error.read(8192)
        except (OSError, ValueError):
            return ""
        if not raw:
            return ""
        if isinstance(raw, bytes):
            text = raw.decode("utf-8", errors="replace")
        else:
            text = str(raw)
        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            detail = text
        else:
            mappings = []
            if isinstance(payload, dict):
                nested = payload.get("error")
                if isinstance(nested, dict):
                    mappings.append(nested)
                mappings.append(payload)
            parts: list[str] = []
            for mapping in mappings:
                for key in ("message", "detail", "code", "type", "param"):
                    value = mapping.get(key)
                    if isinstance(value, (str, int, float)) and str(value).strip():
                        candidate = str(value).strip()
                        if candidate not in parts:
                            parts.append(candidate)
            detail = "；".join(parts) if parts else text
        detail = " ".join(str(detail).split())
        if self.config.api_key:
            detail = detail.replace(self.config.api_key, "[redacted]")
        detail = re.sub(r"(?i)(bearer\s+)[^\s,;]+", r"\1[redacted]", detail)
        return detail[:HTTP_ERROR_DETAIL_MAX_CHARS]

    def _send_json(
        self,
        request: Request,
        *,
        invalid_message: str,
        model_directory: bool = False,
    ) -> tuple[dict[str, Any], int]:
        check_cancelled()
        logger = logging.getLogger(__name__)
        endpoint = urlsplit(request.full_url)
        target = f"{endpoint.scheme}://{endpoint.hostname}{endpoint.path}"
        logger.debug("HTTP request started: %s %s; protocol=%s model=%s timeout=%ss",
                     request.get_method(), target, self.config.protocol, self.config.model,
                     self.config.timeout_seconds)
        if request.data:
            parameters = json.loads(request.data)
            options = {
                key: parameters[key] for key in ("max_tokens", "max_output_tokens", "max_completion_tokens",
                                                "temperature", "top_p", "reasoning_effort", "reasoning", "thinking")
                if key in parameters
            }
            if isinstance(parameters.get("output_config"), dict) and "effort" in parameters["output_config"]:
                options["output_config"] = {"effort": parameters["output_config"]["effort"]}
            logger.debug("Model request options: %s", options)
        try:
            result, latency = self._send_json_impl(request, invalid_message=invalid_message,
                                                   model_directory=model_directory)
            check_cancelled()
        except CancelledError:
            logger.info("HTTP response discarded after task cancellation: %s %s", request.get_method(), target)
            raise
        except Exception as exc:
            check_cancelled()
            logger.exception("HTTP request failed: %s %s; kind=%s status=%s latency_ms=%s",
                             request.get_method(), target, getattr(exc, "kind", None),
                             getattr(exc, "status_code", None), getattr(exc, "latency_ms", None))
            raise
        logger.info("HTTP request completed: %s %s; latency_ms=%s", request.get_method(), target, latency)
        return result, latency

    def _send_json_impl(
        self,
        request: Request,
        *,
        invalid_message: str,
        model_directory: bool = False,
    ) -> tuple[dict[str, Any], int]:
        started = time.perf_counter()
        self.last_response_envelope = None
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                # shutdown wakes a blocked read before BufferedReader.close
                # tries to acquire its lock on the cancelling UI thread.
                transport = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
                def abort_response():
                    if transport is not None:
                        try:
                            transport.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass
                    close = getattr(response, "close", None)
                    if close is not None:
                        close()
                with interrupt_on_cancel(abort_response):
                    if "text/event-stream" in str(getattr(response, "headers", {}).get("Content-Type", "")).lower():
                        envelope, count, thought_size, text_size = consume_sse(response, self.config.protocol,
                            lambda kind, text: publish(kind, id=self._stream_id, text=text))
                        self.last_response_envelope = envelope
                        logging.getLogger(__name__).info("Model stream received: id=%s events=%s reasoning_chars=%s content_chars=%s latency_ms=%s",
                            self._stream_id, count, thought_size, text_size, self._elapsed(started))
                        return envelope, self._elapsed(started)
                    raw = response.read()
        except StreamError as exc:
            self.last_response_envelope = exc.envelope
            raise ApiError(exc.kind, str(exc), latency_ms=self._elapsed(started),
                           timeout_seconds=self.config.timeout_seconds if exc.kind == "timeout" else None,
                           response_content=self._partial_stream_content(exc.envelope),
                           response_usage=exc.envelope.get("usage"),
                           response_id=exc.envelope.get("id"), response_model=exc.envelope.get("model")) from exc
        except HTTPError as exc:
            latency = self._elapsed(started)
            detail = self._http_error_detail(exc)
            if exc.code in {401, 403}:
                kind = "authentication"
                message = "鉴权失败，请检查密钥、模型权限和接口地址。"
            elif model_directory and exc.code == 404:
                kind = "unsupported_endpoint"
                message = "当前服务不支持模型目录，请保留手动填写模型 ID。"
            else:
                kind = "http_error"
                message = f"接口返回HTTP {exc.code}。"
            if detail:
                message = f"{message} 服务端说明：{detail}"
            raise ApiError(kind, message, exc.code, latency, error_detail=detail) from exc
        except (TimeoutError, socket.timeout) as exc:
            latency = self._elapsed(started)
            message = (
                f"获取模型列表超时（当前阈值 {self.config.timeout_seconds:g} 秒），可继续手动填写模型 ID。"
                if model_directory
                else f"接口请求超时（当前阈值 {self.config.timeout_seconds:g} 秒），任务输入和已有会话未丢失。"
            )
            raise ApiError(
                "timeout", message, latency_ms=latency, timeout_seconds=self.config.timeout_seconds
            ) from exc
        except URLError as exc:
            latency = self._elapsed(started)
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                message = (
                    f"获取模型列表超时（当前阈值 {self.config.timeout_seconds:g} 秒），可继续手动填写模型 ID。"
                    if model_directory
                    else f"接口请求超时（当前阈值 {self.config.timeout_seconds:g} 秒），任务输入和已有会话未丢失。"
                )
                raise ApiError(
                    "timeout", message, latency_ms=latency, timeout_seconds=self.config.timeout_seconds
                ) from exc
            message = (
                "无法连接模型目录，可继续手动填写模型 ID。"
                if model_directory
                else "无法连接模型接口，请检查地址和网络。"
            )
            raise ApiError("network", message, latency_ms=latency) from exc
        latency = self._elapsed(started)
        check_cancelled()
        try:
            envelope = json.loads(raw.decode("utf-8"))
            if not isinstance(envelope, dict):
                raise TypeError
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise ApiError("invalid_response", invalid_message, latency_ms=latency) from exc
        self.last_response_envelope = envelope
        if stream_observed() and hasattr(self, "_stream_id"):
            reasoning = response_reasoning(envelope, self.config.protocol)
            if reasoning:
                publish("reasoning", id=self._stream_id, text=reasoning)
            logging.getLogger(__name__).debug("Model returned buffered JSON: id=%s reasoning_chars=%s", self._stream_id, len(reasoning))
        return envelope, latency

    def _post_json(self, endpoint: str, body: dict[str, Any], headers: dict[str, str]) -> tuple[dict[str, Any], int]:
        self._stream_id = uuid4().hex
        if stream_observed():
            body = {**body, "stream": True}
            publish("start", id=self._stream_id, model=self.config.model, protocol=self.config.protocol)
        self.last_request_snapshot = {
            "method": "POST",
            "endpoint": endpoint,
            "headers": dict(headers),
            "body": body,
        }
        request = Request(
            endpoint,
            data=json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "text/event-stream, application/json" if stream_observed() else "application/json",
                "User-Agent": "PromptSmith/0.2",
                **headers,
            },
        )
        try:
            result = self._send_json(
                request,
                invalid_message=f"模型接口响应格式不符合{self.protocol_name}约定。",
            )
            log_response_usage(result[0], request_id=self._stream_id, latency_ms=result[1])
            publish("end", id=self._stream_id)
            return result
        except ApiError as exc:
            publish("failed", id=self._stream_id, text=str(exc))
            exc.reasoning_content = response_reasoning(self.last_response_envelope or {}, self.config.protocol)
            exc.request_snapshot = self.last_request_snapshot
            exc.response_envelope = self.last_response_envelope
            raise

    def _get_json(self, endpoint: str, headers: dict[str, str]) -> tuple[dict[str, Any], int]:
        request = Request(
            endpoint,
            method="GET",
            headers={"Accept": "application/json", "User-Agent": "PromptSmith/0.2", **headers},
        )
        return self._send_json(
            request,
            invalid_message="模型目录响应格式不符合当前服务约定，可继续手动填写模型 ID。",
            model_directory=True,
        )

    @staticmethod
    def _partial_stream_content(envelope):
        choices = envelope.get("choices") or []
        if choices and isinstance(choices[0], dict):
            return (choices[0].get("message") or {}).get("content", "")
        if isinstance(envelope.get("content"), list):
            return "".join(b.get("text", "") for b in envelope["content"] if isinstance(b, dict) and isinstance(b.get("text"), str))
        return "".join(b.get("text", "") for row in envelope.get("output", []) if isinstance(row, dict)
                       for b in row.get("content", []) if isinstance(b, dict) and isinstance(b.get("text"), str))

    @staticmethod
    def _parse_model_ids(envelope: dict[str, Any], latency_ms: int) -> ModelListResult:
        data = envelope.get("data")
        if not isinstance(data, list):
            raise ApiError(
                "invalid_response",
                "模型目录响应格式不符合当前服务约定，可继续手动填写模型 ID。",
                latency_ms=latency_ms,
            )
        model_ids = []
        for row in data:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"].strip():
                raise ApiError(
                    "invalid_response",
                    "模型目录响应格式不符合当前服务约定，可继续手动填写模型 ID。",
                    latency_ms=latency_ms,
                )
            model_ids.append(row["id"])
        return ModelListResult(model_ids, latency_ms)


class ChatCompletionsClient(_HttpClient):
    protocol_name = "Chat Completions"

    @property
    def endpoint(self) -> str:
        base = self.config.base_url.strip().rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    @property
    def models_endpoint(self) -> str:
        return self._endpoint(
            self.config.base_url,
            "/models",
            ("/chat/completions", "/responses", "/messages", "/models"),
        )

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.config.api_key}"}

    def list_models(self) -> ModelListResult:
        envelope, latency = self._get_json(self.models_endpoint, self._headers())
        return self._parse_model_ids(envelope, latency)

    def test_connection(self) -> ApiResult:
        return self._post(
            {
                "model": self.config.model.strip(),
                "messages": [
                    {"role": "system", "content": "You are a connection test."},
                    {"role": "user", "content": "Reply with OK."},
                ],
                **bounded_request_parameters(self.config, 8192),
            },
            allow_probe_truncation=True,
        )

    def complete_json(
        self, system_prompt: str, payload: dict[str, Any], output_schema: dict[str, Any]
    ) -> ApiResult:
        system_prompt, input_text = prepare_json_input(system_prompt, payload, output_schema)
        schema_text = json.dumps(output_schema, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        system_with_contract = (
            f"{system_prompt}\n\n【应用提供的输出结构契约】\n"
            "只输出符合以下JSON Schema的JSON对象：\n"
            f"{schema_text}"
        )
        body = {
                "model": self.config.model.strip(),
                "messages": [
                    {"role": "system", "content": system_with_contract},
                    {
                        "role": "user",
                        "content": input_text,
                    },
                ],
                "response_format": {"type": "json_object"},
                **sampling_request_parameters(self.config),
            }
        body.update(structured_request_parameters(self.config))
        return self._post(body)

    def complete_text(
        self, system_prompt: str, user_text: str, *, max_output_tokens: int = 512
    ) -> ApiResult:
        """Run a bounded plain-text completion without a JSON response contract."""
        _validate_output_limit(max_output_tokens)
        return self._post(
            {
                "model": self.config.model.strip(),
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
                **bounded_request_parameters(self.config, max_output_tokens),
                **sampling_request_parameters(self.config),
            }
        )

    def _post(self, body: dict[str, Any], *, allow_probe_truncation: bool = False) -> ApiResult:
        envelope, latency = self._post_json(self.endpoint, body, self._headers())
        try:
            choice = envelope["choices"][0]
            if not isinstance(choice, dict):
                raise TypeError
            finish_reason = choice.get("finish_reason")
            truncated = finish_reason == "length"
            message = choice.get("message")
            partial_content = ""
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                partial_content = message["content"]
            usage = envelope.get("usage")
            usage = usage if isinstance(usage, dict) else None
            response_id = envelope.get("id") if isinstance(envelope.get("id"), str) else None
            response_model = envelope.get("model") if isinstance(envelope.get("model"), str) else None
            if truncated and not allow_probe_truncation:
                details = (usage or {}).get("completion_tokens_details") or {}
                reasoning_tokens = details.get("reasoning_tokens") if isinstance(details, dict) else None
                output_tokens = (usage or {}).get("completion_tokens")
                reasoning_only = (not partial_content.strip() and isinstance(reasoning_tokens, int)
                                  and isinstance(output_tokens, int) and output_tokens > 0
                                  and reasoning_tokens >= output_tokens)
                message = ("模型思考耗尽输出预算，尚未返回正文；未自动重试。可更换模型，或自行调整思考强度后再试。"
                           if reasoning_only else "模型输出因长度限制被截断。")
                if reasoning_only:
                    logging.getLogger(__name__).warning("Model reasoning exhausted output budget; model=%s reasoning_tokens=%s output_tokens=%s content_chars=0 retry=False",
                                                        response_model, reasoning_tokens, output_tokens)
                raise ApiError(
                    "truncated",
                    message,
                    latency_ms=latency,
                    response_content=partial_content,
                    response_usage=usage,
                    response_id=response_id,
                    response_model=response_model,
                    finish_reason=finish_reason,
                )
            message = choice["message"]
            if not isinstance(message, dict):
                raise TypeError
            refusal = message.get("refusal")
            if refusal:
                raise ApiError("refusal", "模型拒绝完成当前请求。", latency_ms=latency)
            content = message.get("content")
            if content is None and truncated:
                content = ""
            if not isinstance(content, str) or (not content.strip() and not truncated):
                raise TypeError
        except ApiError:
            raise
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise ApiError(
                "invalid_response",
                "模型接口响应格式不符合Chat Completions约定。",
                latency_ms=latency,
            ) from exc
        usage = envelope.get("usage")
        return ApiResult(
            content,
            latency,
            usage if isinstance(usage, dict) else None,
            envelope.get("id") if isinstance(envelope.get("id"), str) else None,
            envelope.get("model") if isinstance(envelope.get("model"), str) else None,
            truncated,
            finish_reason if isinstance(finish_reason, str) else None,
            self.last_request_snapshot,
            self.last_response_envelope,
            response_reasoning(envelope, self.config.protocol),
        )


def _native_json_schema_issue(schema: Any, *, dialect: str = "openai", root: bool = True) -> str | None:
    """Select a conservative native subset for each API's own schema rules.

    Business schemas remain unchanged. Optional fields and conditional rules
    belong in the JSON-mode prompt and the existing local parsers instead.
    """
    if not isinstance(schema, dict):
        return "boolean_or_non_object_schema"
    if root and (schema.get("type") != "object" or (dialect == "openai" and "anyOf" in schema)):
        return "root_must_be_object"
    supported = {
        "$schema", "$id", "$defs", "$ref", "title", "description", "type",
        "properties", "required", "additionalProperties", "items", "anyOf",
        "enum", "const", "format", "minItems",
    }
    if dialect == "openai":
        supported.update({"pattern", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf", "maxItems"})
    else:
        supported.update({"default", "definitions"})
    if set(schema) - supported:
        return "unsupported_schema_keyword"
    properties = schema.get("properties", {})
    if schema.get("type") == "object" or "properties" in schema:
        if schema.get("additionalProperties") is not False:
            return "object_must_be_closed"
        if dialect == "openai" and set(schema.get("required", [])) != set(properties):
            return "optional_object_properties"
    if dialect == "anthropic":
        if schema.get("minItems", 0) not in (0, 1):
            return "unsupported_array_minimum"
        if "format" in schema and schema["format"] not in {
            "date-time", "time", "date", "duration", "email", "hostname", "uri", "ipv4", "ipv6", "uuid",
        }:
            return "unsupported_string_format"
    children = [*properties.values(), *schema.get("$defs", {}).values(),
                *schema.get("definitions", {}).values(), *schema.get("anyOf", [])]
    if "items" in schema:
        children.append(schema["items"])
    for child in children:
        issue = _native_json_schema_issue(child, dialect=dialect, root=False)
        if issue:
            return issue
    return None


class OpenAIResponsesClient(_HttpClient):
    protocol_name = "OpenAI Responses"

    @property
    def endpoint(self) -> str:
        return self._endpoint(
            self.config.base_url,
            "/responses",
            ("/chat/completions", "/responses", "/messages", "/models"),
        )

    @property
    def models_endpoint(self) -> str:
        return self._endpoint(
            self.config.base_url,
            "/models",
            ("/chat/completions", "/responses", "/messages", "/models"),
        )

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.config.api_key}"}

    def list_models(self) -> ModelListResult:
        envelope, latency = self._get_json(self.models_endpoint, self._headers())
        return self._parse_model_ids(envelope, latency)

    def test_connection(self) -> ApiResult:
        return self._post(
            {
                "model": self.config.model.strip(),
                "instructions": "You are a connection test.",
                "input": "Reply with OK.",
                **bounded_request_parameters(self.config, 8192),
            },
            allow_probe_truncation=True,
        )

    def complete_json(
        self, system_prompt: str, payload: dict[str, Any], output_schema: dict[str, Any]
    ) -> ApiResult:
        system_prompt, input_text = prepare_json_input(system_prompt, payload, output_schema)
        request_parameters = structured_request_parameters(self.config)
        schema_text = json.dumps(output_schema, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        contract_instructions = (
            f"{system_prompt}\n\n【应用提供的输出结构契约】\n"
            "只输出符合以下JSON Schema的JSON对象：\n"
            f"{schema_text}"
        )
        schema_issue = _native_json_schema_issue(output_schema)
        if schema_issue:
            output_format = {"type": "json_object"}
            logging.getLogger(__name__).info(
                "Responses JSON mode selected before request: reason=%s; original contract retained for local parsing",
                schema_issue,
            )
        else:
            output_format = {"type": "json_schema", "name": "promptsmith_result", "schema": output_schema, "strict": True}
            logging.getLogger(__name__).debug("Responses native strict JSON schema selected")
        body = {
            "model": self.config.model.strip(),
            "instructions": contract_instructions if schema_issue else system_prompt,
            "input": input_text,
            **request_parameters,
            **sampling_request_parameters(self.config),
            "text": {"format": output_format},
        }
        try:
            return self._post(body)
        except ApiError as exc:
            # Removing the native format cannot fix a bad model/parameter or
            # authorization error. Only explicit format incompatibility merits
            # one fallback request; malformed schemas remain visible failures.
            detail = exc.error_detail.lower()
            format_name = r"(?:\bjson_schema\b|\bjson_object\b|\bstructured outputs?\b|\btext\.format\b|\bresponse_format\b)"
            quoted_format = rf"['\"`]?{format_name}(?![\w.])['\"`]?"
            incompatible = bool(re.search(
                rf"{quoted_format}\s+(?:(?:is|are)\s+)?(?:not supported|unsupported|not implemented)\b"
                rf"|(?:does not support|doesn't support)\s+{quoted_format}"
                rf"|(?:unknown parameter|unrecognized parameter|unsupported parameter)\s*:\s*{quoted_format}",
                detail,
            ))
            if exc.status_code != 400 or not incompatible:
                logging.getLogger(__name__).debug(
                    "Responses format fallback skipped: status=%s kind=%s", exc.status_code, exc.kind,
                )
                raise
            # Some Responses proxies lack native structured outputs. Keep the
            # same contract in the instructions for local parser validation.
            fallback_body = {
                **body,
                "instructions": contract_instructions,
            }
            fallback_body.pop("text", None)
            logging.getLogger(__name__).warning(
                "Responses native JSON format unsupported; sending one compatible request with the same schema contract",
            )
            return self._post(fallback_body)

    def complete_text(
        self, system_prompt: str, user_text: str, *, max_output_tokens: int = 512
    ) -> ApiResult:
        """Run a bounded plain-text completion without a JSON response contract."""
        _validate_output_limit(max_output_tokens)
        return self._post(
            {
                "model": self.config.model.strip(),
                "instructions": system_prompt,
                "input": user_text,
                **bounded_request_parameters(self.config, max_output_tokens),
                **sampling_request_parameters(self.config),
            }
        )

    def _post(self, body: dict[str, Any], *, allow_probe_truncation: bool = False) -> ApiResult:
        envelope, latency = self._post_json(self.endpoint, body, self._headers())
        status = envelope.get("status")
        incomplete = status == "incomplete"
        incomplete_details = envelope.get("incomplete_details")
        finish_reason = (
            incomplete_details.get("reason")
            if isinstance(incomplete_details, dict) and isinstance(incomplete_details.get("reason"), str)
            else (status if isinstance(status, str) else None)
        )
        texts: list[str] = []
        refusal = False
        output = envelope.get("output")
        if isinstance(output, list):
            for item in output:
                if not isinstance(item, dict) or item.get("type") != "message":
                    continue
                contents = item.get("content", [])
                if not isinstance(contents, list):
                    continue
                for block in contents:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "output_text" and isinstance(block.get("text"), str):
                        texts.append(block["text"])
                    elif block.get("type") == "refusal":
                        refusal = True
        content = "".join(texts)
        usage = envelope.get("usage")
        usage = usage if isinstance(usage, dict) else None
        response_id = envelope.get("id") if isinstance(envelope.get("id"), str) else None
        response_model = envelope.get("model") if isinstance(envelope.get("model"), str) else None
        probe_truncated = (
            incomplete
            and isinstance(envelope.get("incomplete_details"), dict)
            and envelope["incomplete_details"].get("reason") == "max_output_tokens"
        )
        if incomplete and (not allow_probe_truncation or not probe_truncated):
            raise ApiError(
                "truncated",
                "模型输出未完成或因长度限制被截断。",
                latency_ms=latency,
                response_content=content,
                response_usage=usage,
                response_id=response_id,
                response_model=response_model,
                finish_reason=finish_reason,
            )
        if not isinstance(output, list):
            raise ApiError(
                "invalid_response",
                "模型接口响应格式不符合OpenAI Responses约定。",
                latency_ms=latency,
            )
        if refusal and not texts:
            raise ApiError("refusal", "模型拒绝完成当前请求。", latency_ms=latency)
        if not content.strip() and not probe_truncated:
            raise ApiError("invalid_response", "OpenAI Responses返回中没有可用文本。", latency_ms=latency)
        return ApiResult(
            content,
            latency,
            usage,
            response_id,
            response_model,
            probe_truncated,
            finish_reason,
            self.last_request_snapshot,
            self.last_response_envelope,
            response_reasoning(envelope, self.config.protocol),
        )


class AnthropicMessagesClient(_HttpClient):
    protocol_name = "Anthropic Messages"
    anthropic_version = "2023-06-01"
    max_model_pages = 10

    @property
    def endpoint(self) -> str:
        return self._endpoint(
            self.config.base_url,
            "/messages",
            ("/chat/completions", "/responses", "/messages", "/models"),
        )

    @property
    def models_endpoint(self) -> str:
        base = self._endpoint(
            self.config.base_url,
            "/models",
            ("/chat/completions", "/responses", "/messages", "/models"),
        )
        return f"{base}?{urlencode({'limit': 1000})}"

    def _models_page_endpoint(self, after_id: str | None = None) -> str:
        base = self.models_endpoint.split("?", 1)[0]
        query = {"limit": 1000}
        if after_id is not None:
            query["after_id"] = after_id
        return f"{base}?{urlencode(query)}"

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self.config.api_key, "anthropic-version": self.anthropic_version}

    def list_models(self) -> ModelListResult:
        model_ids: list[str] = []
        known_ids: set[str] = set()
        seen_cursors: set[str] = set()
        after_id: str | None = None
        total_latency = 0
        for _page_number in range(self.max_model_pages):
            envelope, latency = self._get_json(self._models_page_endpoint(after_id), self._headers())
            total_latency += latency
            page = self._parse_model_ids(envelope, latency)
            for model_id in page.model_ids:
                if model_id not in known_ids:
                    known_ids.add(model_id)
                    model_ids.append(model_id)
            has_more = envelope.get("has_more", False)
            if not isinstance(has_more, bool):
                raise ApiError(
                    "invalid_response",
                    "Anthropic 模型目录的 has_more 格式无效；可继续手动填写模型 ID。",
                    latency_ms=total_latency,
                )
            if not has_more:
                return ModelListResult(model_ids, total_latency)
            next_cursor = envelope.get("last_id")
            if not isinstance(next_cursor, str) or not next_cursor.strip() or next_cursor in seen_cursors:
                raise ApiError(
                    "invalid_response",
                    "Anthropic 模型目录分页游标缺失或重复；可继续手动填写模型 ID。",
                    latency_ms=total_latency,
                )
            seen_cursors.add(next_cursor)
            after_id = next_cursor
        raise ApiError(
            "pagination_limit",
            f"Anthropic 模型目录超过 {self.max_model_pages} 页的安全上限；可手动填写模型 ID。",
            latency_ms=total_latency,
        )

    def test_connection(self) -> ApiResult:
        return self._post(
            {
                "model": self.config.model.strip(),
                "system": "You are a connection test.",
                "messages": [{"role": "user", "content": "Reply with OK."}],
                **bounded_request_parameters(self.config, 8192),
            },
            allow_probe_truncation=True,
        )

    def complete_json(
        self, system_prompt: str, payload: dict[str, Any], output_schema: dict[str, Any]
    ) -> ApiResult:
        system_prompt, input_text = prepare_json_input(system_prompt, payload, output_schema)
        parameters = structured_request_parameters(self.config)
        output_config = parameters.pop("output_config", {})
        model = find_model(self.config.model)
        schema_issue = ("provider_has_no_native_format" if model and model.provider == "DeepSeek" else
                        _native_json_schema_issue(output_schema, dialect="anthropic"))
        if schema_issue:
            schema_text = json.dumps(output_schema, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            system_prompt = (
                f"{system_prompt}\n\n【应用提供的输出结构契约】\n"
                "只输出符合以下JSON Schema的JSON对象：\n"
                f"{schema_text}"
            )
            logging.getLogger(__name__).info(
                "Anthropic prompt JSON contract selected before request: reason=%s; original contract retained for local parsing",
                schema_issue,
            )
        else:
            output_config["format"] = {"type": "json_schema", "schema": output_schema}
            logging.getLogger(__name__).debug("Anthropic native JSON schema selected")
        return self._post(
            {
                "model": self.config.model.strip(),
                "system": system_prompt,
                "messages": [
                    {
                        "role": "user",
                        "content": input_text,
                    }
                ],
                **parameters,
                **sampling_request_parameters(self.config),
                **({"output_config": output_config} if output_config else {}),
            }
        )

    def complete_text(
        self, system_prompt: str, user_text: str, *, max_output_tokens: int = 512
    ) -> ApiResult:
        """Run a bounded plain-text completion without a JSON response contract."""
        _validate_output_limit(max_output_tokens)
        return self._post(
            {
                "model": self.config.model.strip(),
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_text}],
                **bounded_request_parameters(self.config, max_output_tokens),
                **sampling_request_parameters(self.config),
            }
        )

    def _post(self, body: dict[str, Any], *, allow_probe_truncation: bool = False) -> ApiResult:
        envelope, latency = self._post_json(self.endpoint, body, self._headers())
        stop_reason = envelope.get("stop_reason")
        probe_truncated = stop_reason == "max_tokens" and allow_probe_truncation
        if stop_reason in {"max_tokens", "model_context_window_exceeded"} and not probe_truncated:
            blocks = envelope.get("content")
            partial_content = "".join(
                block["text"]
                for block in (blocks if isinstance(blocks, list) else [])
                if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
            )
            usage = envelope.get("usage")
            raise ApiError(
                "truncated",
                "模型输出因令牌或上下文限制被截断。",
                latency_ms=latency,
                response_content=partial_content,
                response_usage=usage if isinstance(usage, dict) else None,
                response_id=envelope.get("id") if isinstance(envelope.get("id"), str) else None,
                response_model=envelope.get("model") if isinstance(envelope.get("model"), str) else None,
                finish_reason=stop_reason,
            )
        if stop_reason == "refusal":
            raise ApiError("refusal", "模型拒绝完成当前请求。", latency_ms=latency)
        blocks = envelope.get("content")
        if not isinstance(blocks, list):
            raise ApiError(
                "invalid_response",
                "模型接口响应格式不符合Anthropic Messages约定。",
                latency_ms=latency,
            )
        texts = [
            block["text"]
            for block in blocks
            if isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        ]
        content = "".join(texts)
        if not content.strip() and not probe_truncated:
            raise ApiError("invalid_response", "Anthropic Messages返回中没有可用文本。", latency_ms=latency)
        usage = envelope.get("usage")
        return ApiResult(
            content,
            latency,
            usage if isinstance(usage, dict) else None,
            envelope.get("id") if isinstance(envelope.get("id"), str) else None,
            envelope.get("model") if isinstance(envelope.get("model"), str) else None,
            probe_truncated,
            stop_reason if isinstance(stop_reason, str) else None,
            self.last_request_snapshot,
            self.last_response_envelope,
            response_reasoning(envelope, self.config.protocol),
        )


def client_for_config(config: ApiConfig) -> ChatCompletionsClient | OpenAIResponsesClient | AnthropicMessagesClient:
    if config.protocol == PROTOCOL_ID:
        return ChatCompletionsClient(config)
    if config.protocol == OPENAI_RESPONSES_PROTOCOL:
        return OpenAIResponsesClient(config)
    if config.protocol == ANTHROPIC_MESSAGES_PROTOCOL:
        return AnthropicMessagesClient(config)
    raise ValueError(f"当前版本不支持协议：{config.protocol}")
