"""Guarded short-text trial runs for a confirmed final prompt.

Trial output is deliberately independent from requirements, plans, and the
final result.  A request carries enough of the current final snapshot to
reject a response that arrives after the user changed or invalidated it.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from .api import ApiError, ApiResult
from .finalization import render_task_prompt
from .session import SessionState, SessionStateError, StaleResponseError


class TrialValidationError(SessionStateError):
    """The current session cannot be used for a trial run."""


class TrialCallFailure(RuntimeError):
    """The model call failed before a trial result could be applied."""

    def __init__(
        self,
        message: str,
        *,
        kind: str = "api_error",
        api_result: ApiResult | None = None,
        protocol: str = "unknown",
        configured_model: str = "unknown",
    ):
        super().__init__(message)
        self.kind = kind
        self.api_result = api_result
        self.protocol = protocol
        self.configured_model = configured_model


class TextCompletionClient(Protocol):
    def complete_text(
        self, system_prompt: str, user_text: str, *, max_output_tokens: int = 512
    ) -> ApiResult: ...


@dataclass(frozen=True)
class TrialCallOutcome:
    output: str
    api_result: ApiResult
    protocol: str
    configured_model: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _body_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _current_final_basis(session: SessionState) -> dict[str, Any]:
    result = session.final_result
    basis = result.get("basis")
    if not isinstance(basis, dict):
        raise TrialValidationError("当前最终提示缺少有效来源依据。")
    if basis.get("task_id") != session.task_id:
        raise TrialValidationError("当前最终提示不属于本任务。")
    if basis.get("requirement_version") != session.requirement_version:
        raise TrialValidationError("最终提示来源需求已变化，请重新确认。")
    if basis.get("plan_id") != session.plan.get("plan_id") or basis.get("plan_version") != session.plan.get("plan_version"):
        raise TrialValidationError("最终提示来源方案已变化，请重新确认。")
    if session.confirmed_requirements_version != session.requirement_version:
        raise TrialValidationError("请先确认当前需求。")
    if session.plan.get("status") != "confirmed":
        raise TrialValidationError("请先确认当前方案。")
    if result.get("status") != "confirmed" or result.get("confirmed_revision") != result.get("revision"):
        raise TrialValidationError("请先确认当前最终提示。")
    body = result.get("canonical_body")
    if not isinstance(body, str) or not body.strip() or result.get("body_sha256") != _body_hash(body):
        raise TrialValidationError("当前最终提示正文无效，请重新生成。")
    return deepcopy(basis)


def build_trial_request(
    session: SessionState,
    request_id: str | None = None,
    *,
    max_output_tokens: int = 512,
) -> dict[str, Any]:
    """Snapshot the confirmed final prompt and register a guarded request."""
    if not request_id:
        request_id = f"trial-{uuid4().hex}"
    if request_id in session.pending_requests:
        raise TrialValidationError("试运行请求编号重复。")
    if isinstance(max_output_tokens, bool) or not isinstance(max_output_tokens, int) or not 1 <= max_output_tokens <= 4096:
        raise TrialValidationError("试运行输出上限必须是1到4096之间的整数。")
    _current_final_basis(session)
    result = session.final_result
    body = str(result["canonical_body"])
    tone = str(result.get("tone") or "neutral")
    user_prompt = render_task_prompt(body, tone)
    snapshot = {
        "request_id": request_id,
        "purpose": "trial",
        "task_id": session.task_id,
        "task_text": session.task_text,
        "requirement_version": session.requirement_version,
        "final_revision": int(result["revision"]),
        "body_sha256": result["body_sha256"],
        "tone": tone,
        "canonical_body": body,
        "user_prompt": user_prompt,
        "max_output_tokens": max_output_tokens,
        "started_at": _now(),
    }
    # A single live trial is enough; historical runs remain append-only.
    session.pending_requests = {
        key: value for key, value in session.pending_requests.items() if value.get("purpose") != "trial"
    }
    session.pending_requests[request_id] = deepcopy(snapshot)
    session.touch()
    return snapshot


def invoke_trial(
    payload: dict[str, Any],
    client: TextCompletionClient,
    *,
    protocol: str,
    configured_model: str,
) -> TrialCallOutcome:
    """Call a text model without applying anything to the session."""
    try:
        api_result = client.complete_text(
            "根据用户提供的任务提示完成一次短文本试运行。只输出任务结果，不解释提示词。",
            payload["user_prompt"],
            max_output_tokens=payload["max_output_tokens"],
        )
    except ApiError as exc:
        failed = ApiResult(
            content="",
            latency_ms=exc.latency_ms,
            usage=None,
            response_id=None,
            model=configured_model,
        )
        raise TrialCallFailure(
            str(exc),
            kind=exc.kind,
            api_result=failed,
            protocol=protocol,
            configured_model=configured_model,
        ) from exc
    if not isinstance(api_result, ApiResult):
        raise TrialCallFailure(
            "模型接口返回格式无效。",
            kind="invalid_response",
            protocol=protocol,
            configured_model=configured_model,
        )
    if not isinstance(api_result.content, str) or not api_result.content.strip():
        raise TrialCallFailure(
            "模型未返回可用试运行结果。",
            kind="empty_output",
            api_result=api_result,
            protocol=protocol,
            configured_model=configured_model,
        )
    return TrialCallOutcome(api_result.content, api_result, protocol, configured_model)


def _trial_history_row(
    session: SessionState,
    payload: dict[str, Any],
    api_result: ApiResult | None,
    *,
    protocol: str,
    configured_model: str,
    status: str,
    output: str = "",
    error_kind: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    request_id = payload.get("request_id")
    return {
        "run_id": f"run-{uuid4().hex}",
        "task_id": payload.get("task_id", session.task_id),
        "request_id": request_id,
        "final_revision": payload.get("final_revision"),
        "body_sha256": payload.get("body_sha256"),
        "tone": payload.get("tone"),
        "protocol": protocol,
        "model": (api_result.model if api_result else None) or configured_model,
        "latency_ms": api_result.latency_ms if api_result else None,
        "usage": deepcopy(api_result.usage) if api_result and api_result.usage is not None else None,
        "output": output,
        "started_at": payload.get("started_at"),
        "created_at": _now(),
        "status": status,
        "error_kind": error_kind,
        "error_message": error_message,
    }


def record_trial_failure(
    session: SessionState,
    payload: dict[str, Any],
    failure: TrialCallFailure,
    *,
    protocol: str | None = None,
    configured_model: str | None = None,
) -> dict[str, Any]:
    """Record a failed attempt and consume its pending request exactly once."""
    request_id = payload.get("request_id")
    previous = next((row for row in session.trial_runs if row.get("request_id") == request_id), None)
    if previous is not None:
        return deepcopy(previous)
    request = session.pending_requests.get(request_id)
    if not isinstance(request, dict) or request.get("purpose") != "trial":
        _record_unmatched_stale(
            session,
            payload,
            failure.api_result,
            protocol=protocol or failure.protocol,
            configured_model=configured_model or failure.configured_model,
            error_message="试运行失败响应到达时，请求已失效或被替换。",
        )
        raise StaleResponseError("试运行请求不存在、已处理或已被状态变化作废。")
    stale = not _trial_request_is_current(session, request)
    session.pending_requests.pop(request_id, None)
    row = _trial_history_row(
        session,
        request,
        failure.api_result,
        protocol=protocol or failure.protocol,
        configured_model=configured_model or failure.configured_model,
        status="rejected_stale" if stale else "failed",
        error_kind="stale_response" if stale else failure.kind,
        error_message=("等待期间最终提示已变化，试运行失败响应已按过期记录。" if stale else str(failure)),
    )
    session.trial_runs.append(row)
    session.touch()
    return deepcopy(row)


def _trial_request_is_current(session: SessionState, request: dict[str, Any]) -> bool:
    result = session.final_result
    return bool(
        request.get("task_id") == session.task_id
        and request.get("task_text") == session.task_text
        and request.get("requirement_version") == session.requirement_version
        and result.get("status") == "confirmed"
        and result.get("revision") == request.get("final_revision")
        and result.get("confirmed_revision") == request.get("final_revision")
        and result.get("body_sha256") == request.get("body_sha256")
        and result.get("tone") == request.get("tone")
    )


def _record_unmatched_stale(
    session: SessionState,
    payload: dict[str, Any],
    api_result: ApiResult,
    *,
    protocol: str,
    configured_model: str,
    error_message: str,
) -> dict[str, Any] | None:
    request_id = payload.get("request_id")
    if any(row.get("request_id") == request_id for row in session.trial_runs):
        return None
    if (
        payload.get("purpose") != "trial"
        or payload.get("task_id") != session.task_id
        or not isinstance(request_id, str)
        or not request_id
        or not isinstance(payload.get("final_revision"), int)
        or not isinstance(payload.get("body_sha256"), str)
    ):
        return None
    row = _trial_history_row(
        session,
        payload,
        api_result,
        protocol=protocol,
        configured_model=configured_model,
        status="rejected_stale",
        output=api_result.content,
        error_kind="stale_response",
        error_message=error_message,
    )
    session.trial_runs.append(row)
    session.touch()
    return deepcopy(row)


def apply_trial_result(
    session: SessionState,
    payload: dict[str, Any],
    outcome: TrialCallOutcome,
    *,
    protocol: str | None = None,
    configured_model: str | None = None,
) -> dict[str, Any]:
    """Apply a current trial response as an independent historical row."""
    request_id = payload.get("request_id")
    request = session.pending_requests.get(request_id)
    if not isinstance(request, dict) or request.get("purpose") != "trial":
        _record_unmatched_stale(
            session,
            payload,
            outcome.api_result,
            protocol=protocol or outcome.protocol,
            configured_model=configured_model or outcome.configured_model,
            error_message="试运行结果到达时，请求已失效或被替换，结果未应用。",
        )
        raise StaleResponseError("试运行请求不存在、已处理或已被状态变化作废。")
    result = session.final_result
    if not _trial_request_is_current(session, request):
        session.pending_requests.pop(request_id, None)
        stale_row = _trial_history_row(
            session,
            request,
            outcome.api_result,
            protocol=protocol or outcome.protocol,
            configured_model=configured_model or outcome.configured_model,
            status="rejected_stale",
            output=outcome.output,
            error_kind="stale_response",
            error_message="等待期间任务或最终提示已变化，已拒绝旧试运行结果。",
        )
        session.trial_runs.append(stale_row)
        session.touch()
        raise StaleResponseError("等待期间任务或最终提示已变化，已拒绝旧试运行结果。")
    if not isinstance(outcome.output, str) or not outcome.output.strip():
        raise TrialValidationError("试运行结果不能为空。")
    session.pending_requests.pop(request_id, None)
    api_result = outcome.api_result
    row = _trial_history_row(
        session,
        request,
        api_result,
        protocol=protocol or outcome.protocol,
        configured_model=configured_model or outcome.configured_model,
        status="completed",
        output=outcome.output,
    )
    session.trial_runs.append(row)
    session.touch()
    return row
