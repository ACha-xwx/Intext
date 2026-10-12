from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from copy import deepcopy
from pathlib import Path
from typing import Any, Protocol

from .api import ApiError, ApiResult
from .categories import CATEGORY_CONFIG
from .m1 import (
    M1Assets,
    M1JsonError,
    M1_INCREMENTAL_PROMPT_VERSION,
    apply_m1_response,
    build_m1_input,
    m1_request_mode,
    m1_system_prompt,
    parse_m1_response,
)
from .m2 import M2Assets, apply_m2_response, build_m2_input, m2_system_prompt, parse_m2_response
from .m5 import M5Assets, apply_m5_response, build_m5_input, parse_m5_response
from .runlog import RunEvidenceWriter
from .session import SessionState
from .task_scope import check_cancelled


class JsonCompletionClient(Protocol):
    def complete_json(
        self, system_prompt: str, payload: dict[str, Any], output_schema: dict[str, Any]
    ) -> ApiResult: ...


class M1CallFailure(RuntimeError):
    def __init__(
        self,
        message: str,
        evidence_dir: Path,
        *,
        kind: str,
        api_result: ApiResult,
    ):
        super().__init__(message)
        self.evidence_dir = evidence_dir
        self.kind = kind
        self.api_result = api_result


@dataclass(frozen=True)
class M1CallOutcome:
    raw_response: str
    parsed: dict[str, Any]
    api_result: ApiResult
    evidence_dir: Path
    prompt_version: str | None = None
    request_mode: str = "full"
    recovery_mode: str = "model"


class M2CallFailure(RuntimeError):
    def __init__(
        self,
        message: str,
        evidence_dir: Path,
        *,
        kind: str,
        api_result: ApiResult,
        recovery_action: str = "",
        validation_stage: str | None = None,
        status_code: int | None = None,
    ):
        super().__init__(message)
        self.evidence_dir = evidence_dir
        self.kind = kind
        self.api_result = api_result
        self.recovery_action = recovery_action
        self.validation_stage = validation_stage
        self.status_code = status_code


@dataclass(frozen=True)
class M2CallOutcome:
    raw_response: str
    parsed: dict[str, Any]
    api_result: ApiResult
    evidence_dir: Path
    request_mode: str = "full"
    normalization_report: list[dict[str, Any]] = field(default_factory=list)


class M5CallFailure(RuntimeError):
    def __init__(
        self,
        message: str,
        evidence_dir: Path,
        *,
        kind: str,
        api_result: ApiResult,
    ):
        super().__init__(message)
        self.evidence_dir = evidence_dir
        self.kind = kind
        self.api_result = api_result


@dataclass(frozen=True)
class M5CallOutcome:
    raw_response: str
    parsed: dict[str, Any]
    api_result: ApiResult
    evidence_dir: Path


class Phase12Workflow:
    def __init__(
        self,
        session: SessionState,
        assets: M1Assets,
        evidence_root: str | Path,
        m2_assets: M2Assets | None = None,
        m5_assets: M5Assets | None = None,
    ):
        self.session = session
        self.assets = assets
        self.m2_assets = m2_assets or M2Assets.load()
        self.m5_assets = m5_assets or M5Assets.load()
        self.writer = RunEvidenceWriter(evidence_root)

    def prepare_m1(self, request_id: str, *, current_date: str | None = None) -> dict[str, Any]:
        return build_m1_input(self.session, request_id, current_date=current_date)

    def m1_retry_recommended(self) -> bool:
        """Keep recovery available across save/reopen, without starting a call."""
        for run in reversed(self.session.api_runs):
            if not str(run.get("contract_version", "")).startswith("m1."):
                continue
            if run.get("base_version") != self.session.requirement_version:
                return False
            if run.get("status") == "accepted_as_candidate":
                return False
            return (
                run.get("status") in {"truncated", "input_error"}
                or run.get("request_mode") == "compact_retry"
            )
        return False

    def _complete_m1(self, client, prompt, payload, *, attempt):
        """Diagnose actual calls, without logging user content or changing limits."""
        logger = logging.getLogger(__name__)
        def json_bytes(value):
            return len(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8"))
        logger.debug(
            "M1 request input cost; request=%s attempt=%s system_bytes=%s payload_bytes=%s schema_bytes=%s",
            payload["request_id"], attempt, len(prompt.encode("utf-8")), json_bytes(payload),
            json_bytes(self.assets.output_schema),
        )
        try:
            result = client.complete_json(prompt, payload, self.assets.output_schema)
        except ApiError as exc:
            logger.warning("M1 request failed; request=%s attempt=%s kind=%s latency_ms=%s",
                           payload["request_id"], attempt, exc.kind, exc.latency_ms)
            raise
        usage = result.usage or {}
        def count(value):
            return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
        input_tokens = count(usage.get("prompt_tokens", usage.get("input_tokens")))
        output_tokens = count(usage.get("completion_tokens", usage.get("output_tokens")))
        details = usage.get("completion_tokens_details", usage.get("output_tokens_details")) or {}
        reasoning = count(details.get("reasoning_tokens")) if isinstance(details, dict) else None
        answer = (output_tokens - reasoning if output_tokens is not None and reasoning is not None
                  and reasoning <= output_tokens else None)
        logger.info(
            "M1 request completed; request=%s attempt=%s latency_ms=%s input_tokens=%s output_tokens=%s "
            "reasoning_tokens=%s answer_tokens=%s finish=%s",
            payload["request_id"], attempt, result.latency_ms, input_tokens, output_tokens,
            reasoning, answer, result.finish_reason,
        )
        return result

    def invoke_m1(
        self,
        payload: dict[str, Any],
        client: JsonCompletionClient,
        *,
        protocol: str,
        configured_model: str,
        request_parameters: dict[str, Any] | None = None,
        compact_retry: bool = False,
    ) -> M1CallOutcome:
        check_cancelled()
        category_snapshot = deepcopy(self.session.category_suggestion)
        has_pending_answers = any(
            row.get("disposition") == "answered"
            and row.get("assessment_status") == "pending"
            for row in payload.get("state", {}).get("question_history", [])
        )
        mode = m1_request_mode(
            has_pending_answers=has_pending_answers,
            compact_retry=compact_retry,
        )
        # Historical m1.v0.1 fixtures retain their original response semantics.
        if self.assets.contract_version != "m1.v0.2":
            mode = "full"
        effective_prompt = m1_system_prompt(self.assets.system_prompt, mode=mode)
        prompt_version = self.assets.prompt_version if mode == "full" else M1_INCREMENTAL_PROMPT_VERSION
        evidence_options = {
            "effective_prompt": effective_prompt,
            "prompt_version": prompt_version,
            "request_mode": mode,
        }
        failure_options = {"prompt_version": prompt_version, "request_mode": mode}
        control = payload.get("control", {})
        logging.getLogger(__name__).info(
            "M1 interview request; task=%s request=%s mode=%s policy=%s rounds=%s/%s remaining=%s pending_answers=%s",
            payload["task_id"], payload["request_id"], mode, control.get("interview_policy", "legacy"),
            control.get("interview_rounds_used", 0), control.get("interview_round_limit", "legacy"),
            control.get("interview_rounds_remaining", "legacy"), has_pending_answers,
        )
        try:
            api_result = self._complete_m1(client, effective_prompt, payload, attempt=1)
            check_cancelled()
        except ApiError as exc:
            check_cancelled()
            api_result = ApiResult.from_error(exc)
            check = {
                "valid": False,
                "schema": "not_reached",
                "semantic": "not_reached",
                "business_status": None,
                "failure_kind": exc.kind,
                "status_code": exc.status_code,
                "finish_reason": exc.finish_reason,
                "error": str(exc),
            }
            evidence_dir = self._write_evidence(
                payload, api_result, protocol, configured_model, check, request_parameters, **evidence_options
            )
            self._record_failure(payload, exc.kind, str(exc), evidence_dir, api_result, **failure_options)
            raise M1CallFailure(
                str(exc), evidence_dir, kind=exc.kind, api_result=api_result
            ) from exc
        parsed: dict[str, Any] | None = None
        recovery_mode = "model"
        normalization: list[dict[str, Any]] = []
        # Validation is local. A single user action must never silently start
        # two further, potentially minutes-long reasoning requests.
        try:
            parsed = parse_m1_response(
                api_result.content, payload, self.assets.output_schema, incremental=mode != "full",
                normalization_report=normalization,
            )
            check_cancelled()
            if parsed["status"] == "ok":
                self._validate_m1_candidate(payload, parsed)
            check = {
                "valid": True, "schema": "passed", "semantic": "passed",
                "business_status": parsed["status"], "error": None, "normalization": normalization,
                "retry_policy": "user_initiated_only",
            }
        except Exception as exc:
            check_cancelled()
            kind = "json_error" if isinstance(exc, M1JsonError) else "validation_error"
            check = {
                "valid": False, "schema": "failed_or_not_reached", "semantic": "failed_or_not_reached",
                "business_status": None, "failure_kind": kind, "error": str(exc),
                "normalization": normalization, "retry_policy": "user_initiated_only",
                "auto_correction": {"attempt": 1, "action": "manual_retry_required", "previous_errors": []},
            }
            evidence_dir = self._write_evidence(
                payload, api_result, protocol, configured_model, check, request_parameters, **evidence_options
            )
            if self._is_recoverable_interview_error(str(exc)):
                try:
                    parsed = self._build_m1_recovery_candidate(payload, reason=str(exc), category_snapshot=category_snapshot)
                    self._validate_m1_candidate(payload, parsed)
                except Exception as recovery_exc:
                    check_cancelled()
                    message = f"本次需求整理未能采用，已有信息已保留：{recovery_exc}"
                    self._record_failure(payload, kind, message, evidence_dir, api_result, **failure_options)
                    raise M1CallFailure(message, evidence_dir, kind=kind, api_result=api_result) from recovery_exc
                recovery_mode = "program_recovery"
                check = {**check, "valid": True, "schema": "recovery", "semantic": "recovery",
                         "business_status": "ok", "failure_kind": None, "error": None,
                         "recovery_fallback": {"mode": recovery_mode, "reason": str(exc),
                                               "previous_evidence_dirs": [str(evidence_dir)]}}
            else:
                message = f"本次需求整理返回未能采用：{exc}。未自动重试，已有内容已保留。"
                self._record_failure(payload, kind, message, evidence_dir, api_result, **failure_options)
                raise M1CallFailure(message, evidence_dir, kind=kind, api_result=api_result) from exc
        check_cancelled()
        if parsed is None:  # pragma: no cover - validation returns or raises
            raise M1CallFailure("模型没有返回可用的需求整理结果。", Path(), kind="validation_error")
        evidence_dir = self._write_evidence(
            payload, api_result, protocol, configured_model, check, request_parameters, **evidence_options
        )
        if parsed["status"] == "input_error":
            if self._is_semantic_input_error(parsed):
                reason = str((parsed.get("error") or {}).get("message") or "模型没有形成可靠的语义判断。")
                try:
                    parsed = self._build_m1_recovery_candidate(payload, reason=reason, category_snapshot=category_snapshot)
                    self._validate_m1_candidate(payload, parsed)
                except Exception as exc:
                    check_cancelled()
                    message = f"无法保留当前访谈状态：{exc}"
                    recovery_check = {
                        **check,
                        "valid": False,
                        "schema": "recovery_failed",
                        "semantic": "recovery_failed",
                        "business_status": "input_error",
                        "failure_kind": "validation_error",
                        "error": message,
                        "recovery_fallback": {
                            "mode": "program_recovery",
                            "source_status": "input_error",
                            "reason": reason,
                            "previous_evidence_dirs": [str(evidence_dir)],
                        },
                    }
                    failed_evidence = self._write_evidence(
                        payload,
                        api_result,
                        protocol,
                        configured_model,
                        recovery_check,
                        request_parameters,
                        **evidence_options,
                    )
                    self._record_failure(
                        payload, "validation_error", message, failed_evidence, api_result, **failure_options
                    )
                    raise M1CallFailure(
                        message, failed_evidence, kind="validation_error", api_result=api_result
                    ) from exc
                recovery_mode = "program_recovery"
                check = {
                    "valid": True,
                    "schema": "recovery",
                    "semantic": "recovery",
                    "business_status": "ok",
                    "error": None,
                    "recovery_fallback": {
                        "mode": recovery_mode,
                        "source_status": "input_error",
                        "reason": reason,
                        "previous_evidence_dirs": [str(evidence_dir)],
                    },
                    "retry_policy": "user_initiated_only",
                }
                evidence_options = {
                    **evidence_options,
                    "effective_prompt": evidence_options.get("effective_prompt", effective_prompt),
                }
                evidence_dir = self._write_evidence(
                    payload,
                    api_result,
                    protocol,
                    configured_model,
                    check,
                    request_parameters,
                    **evidence_options,
                )
                (evidence_dir / "response.effective.json").write_text(
                    json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                return M1CallOutcome(
                    api_result.content,
                    parsed,
                    api_result,
                    evidence_dir,
                    prompt_version,
                    mode,
                    recovery_mode,
                )
            message = parsed["error"]["message"]
            self._record_failure(payload, "input_error", message, evidence_dir, api_result, **failure_options)
            raise M1CallFailure(
                f"模型未能处理本轮输入：{message}",
                evidence_dir,
                kind="input_error",
                api_result=api_result,
            )
        if mode != "full" or check.get("normalization"):
            (evidence_dir / "response.effective.json").write_text(
                json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        return M1CallOutcome(
            api_result.content,
            parsed,
            api_result,
            evidence_dir,
            prompt_version,
            mode,
            recovery_mode,
        )

    @staticmethod
    def _is_semantic_input_error(parsed: dict[str, Any]) -> bool:
        """Treat a contract-valid ``input_error`` as a semantic recovery signal.

        A model response has already passed JSON, Schema, and semantic shape
        validation before this method is called.  Some contract-valid
        ``input_error`` responses still describe a semantic dead-end (for
        example an unresolved acronym), while generic ``invalid_input`` is a
        real failure that must preserve state and remain visible to the user.
        The code/message markers below distinguish those two cases.
        """
        if parsed.get("status") != "input_error" or not isinstance(parsed.get("error"), dict):
            return False
        error = parsed["error"]
        code = str(error.get("code") or "").casefold()
        message = str(error.get("message") or "").casefold()
        # A contract-valid input_error can still be a model's semantic
        # dead-end. Restrict recovery to explicit semantic markers so generic
        # invalid_input responses remain real failures and preserve state.
        semantic_codes = {
            "context_incomplete",
            "semantic_incomplete",
            "ambiguous_context",
            "missing_context",
        }
        # ``input_error`` is a model-level result, not a transport/API error.
        # Providers and models use several natural-language variants for the
        # same semantic dead-end (for example "无法理解当前内容" or
        # "无法判断 JGS 的具体含义").  Keep genuine protocol failures such
        # as "无法处理输入" visible, but route semantic uncertainty back to
        # the interview so it can continue with the existing state.
        semantic_terms = (
            "简称", "术语", "含义", "语义", "信息不完整", "信息不足",
            "上下文不足", "上下文不完整", "内容不完整", "无法理解",
            "无法判断", "无法确定", "不明确", "不清楚", "需要继续核对",
            "ambiguous", "unclear", "incomplete", "insufficient context",
            "cannot determine", "cannot understand",
        )
        return code in semantic_codes or any(term in message for term in semantic_terms)

    @staticmethod
    def _is_recoverable_interview_error(message: str) -> bool:
        """Return whether a failed model decision can be continued safely.

        Never adopt invalid model edits. Without further requests, recover a
        question from existing state for content/shape failures. Explicit
        request identity and version mismatches remain rejected.
        """
        text = str(message or "").casefold()
        if any(marker in text for marker in ("request_id", "task_id", "base_version", "schema_version", "旧版本", "已失效")):
            return False
        markers = (
            "模型判断与需求复核步骤不一致",
            "模型判断与当前追问步骤不一致",
            "模型判断为信息充分时",
            "模型要求继续追问，但没有返回",
            "模型判断为信息未完整时",
            "暂停整理时不能同时声明继续追问",
            "model_judgment",
            "仍有阻断缺口",
            "回答不充分",
            "继续追问",
            "不存在",
            "来源",
            "对齐",
            "重复",
            "schema",
            "json",
        )
        return any(marker.casefold() in text for marker in markers)

    def _build_m1_recovery_candidate(self, payload: dict[str, Any], *, reason: str,
                                     category_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
        """Keep the interview usable when the model chooses input_error.

        The bridge only carries forward state already supplied by the user or
        previously proposed by the model.  If no question is available, it adds
        one generic goal gap rather than guessing a term, requirement, or choice.
        """
        state = payload["state"]
        gaps = deepcopy(state.get("gaps", []))
        gap_by_id = {row.get("gap_id"): row for row in gaps}
        questions: list[dict[str, Any]] = []
        for row in state.get("pending_questions", []):
            gap = gap_by_id.get(row.get("gap_id"))
            if not gap or row.get("field") != gap.get("field") or row.get("scope") != gap.get("scope"):
                continue
            if not str(row.get("text") or "").strip():
                continue
            question = deepcopy(row)
            question.setdefault("options", [])
            question.setdefault("reason", "这个信息会影响后续整理方向。")
            question.setdefault("depends_on", [])
            questions.append(question)
            if payload.get("schema_version") == "m1.v0.1" and len(questions) == 3:
                break

        skipped_gap_ids = {
            row.get("gap_id")
            for row in state.get("question_history", [])
            if row.get("disposition") in {"skipped", "unsure"}
        }
        if not questions:
            candidate_gap = next(
                (
                    row
                    for row in gaps
                    if row.get("gap_id") not in skipped_gap_ids
                    and row.get("importance") == "blocking_direction"
                ),
                next((row for row in gaps if row.get("gap_id") not in skipped_gap_ids), None),
            )
            if candidate_gap is not None:
                question_id = "q-recovery"
                existing_question_ids = {
                    row.get("question_id") for row in [*state.get("pending_questions", []), *state.get("question_history", [])]
                }
                suffix = 2
                while question_id in existing_question_ids:
                    question_id = f"q-recovery-{suffix}"
                    suffix += 1
                questions.append(
                    {
                        "question_id": question_id,
                        "gap_id": candidate_gap["gap_id"],
                        "field": candidate_gap["field"],
                        "scope": candidate_gap["scope"],
                        "text": (
                            f"为了继续明确“{candidate_gap['scope']}”，你可以直接补充目前知道的线索；"
                            "如果暂时不确定，也可以让我列出可能的理解供你确认。"
                        ),
                        "options": [],
                        "reason": "这个信息会影响后续整理方向，不要求你先说出正式名称。",
                        "depends_on": deepcopy(candidate_gap.get("depends_on", [])),
                    }
                )

        if not gaps:
            gaps = [
                {
                    "gap_id": "g-recovery-goal",
                    "field": "goal",
                    "scope": "任务目标",
                    "description": "还需要确认这次任务希望解决什么问题或得到什么结果。",
                    "importance": "blocking_direction",
                    "origin": "missing",
                    "source_refs": [],
                    "depends_on": [],
                }
            ]
            questions = [
                {
                    "question_id": "q-recovery-goal",
                    "gap_id": "g-recovery-goal",
                    "field": "goal",
                    "scope": "任务目标",
                    "text": "你这次最希望解决什么问题，或者最后想得到什么结果？",
                    "options": [],
                    "reason": "先明确目标，后面才能判断需要整理哪些要求。",
                    "depends_on": [],
                }
            ]

        category = state.get("selected_category")
        allowed_categories = set(CATEGORY_CONFIG["category_fields"]) | {"general"}
        previous_category = category_snapshot or {}
        keep_previous_category = category in (None, "auto") and previous_category.get("primary") in allowed_categories
        if keep_previous_category:
            category = previous_category["primary"]
        if category not in allowed_categories:
            category = "general"
        conflicts = [
            {
                "conflict_id": row["conflict_id"],
                "existing_item_ids": list(row.get("item_ids", [])),
                "proposal_ids": list(row.get("proposal_ids", [])),
                "description": row["description"],
                "change_intent": "unclear",
            }
            for row in state.get("open_conflicts", [])
        ]
        blocking_ids = [row["gap_id"] for row in gaps if row.get("importance") == "blocking_direction"]
        requirements = state.get("requirements", [])
        goal_fields = {"goal", "purpose", "learning_goal", "analysis_question", "decision_purpose", "use_context"}
        has_goal = any(row.get("field") in goal_fields for row in requirements)
        has_deliverable = any(row.get("field") == "deliverable" for row in requirements)
        result = {
            "schema_version": payload["schema_version"],
            "request_id": payload["request_id"],
            "task_id": payload["task_id"],
            "base_version": payload["base_version"],
            "status": "ok",
            "error": None,
            "category": {
                "primary": category,
                "secondary": [],
                "reason": "先保留当前类别判断，继续核对任务内容。",
            },
            "proposals": [],
            "conflicts": conflicts,
            "review_item_ids": [],
            "gap_updates": [],
            "question_reopens": [],
            "gaps": gaps,
            "questions": questions,
            "readiness": {
                "goal_identified": has_goal,
                "deliverable_identified": has_deliverable,
                "blocking_gap_ids": blocking_ids,
                "reason": "模型暂时没有形成可靠判断，已保留现有缺口并继续核对。",
            },
            "next_action": "ask" if questions else "pause_with_unknowns",
            "assistant_text": (
                "我先保留你已经提供的信息。这个关键点还没有可靠结论，"
                "你可以直接补充线索；如果暂时不确定，也可以让我列出可能的理解。"
                if questions
                else "我先保留你已经提供的信息。这个方向还没有可靠结论，你可以继续补充线索。"
            ),
        }
        if keep_previous_category:
            result["category"] = {key: deepcopy(previous_category[key]) for key in ("primary", "secondary", "reason")}
        if "model_judgment" in self.assets.output_schema.get("properties", {}):
            result["model_judgment"] = {
                "answer_assessment": "unclear",
                "critical_gap_ids": blocking_ids,
                "continue_interview": bool(questions),
                "confidence": "low",
                "reason": f"模型返回语义型输入问题（{reason}），当前不能把任何推测当成已确认要求。",
            }
        return result

    def _validate_m1_candidate(self, payload: dict[str, Any], parsed: dict[str, Any]) -> None:
        """Validate on a copy without changing the current session."""
        probe = deepcopy(self.session)
        apply_m1_response(probe, payload, parsed)

    def _record_failure(
        self,
        payload: dict[str, Any],
        kind: str,
        message: str,
        evidence_dir: Path,
        api_result: ApiResult,
        *,
        prompt_version: str | None = None,
        request_mode: str = "full",
    ) -> None:
        self.session.pending_requests.pop(payload["request_id"], None)
        self.session.errors.append(
            {"request_id": payload["request_id"], "kind": kind, "message": message}
        )
        self.session.api_runs.append(
            {
                "request_id": payload["request_id"],
                "base_version": payload["base_version"],
                "prompt_version": prompt_version or self.assets.prompt_version,
                "contract_version": self.assets.contract_version,
                "request_mode": request_mode,
                "latency_ms": api_result.latency_ms,
                "usage": api_result.usage,
                "finish_reason": api_result.finish_reason,
                "status": kind,
                "evidence_dir": str(evidence_dir),
            }
        )
        self.session.touch()

    def _write_evidence(
        self,
        payload: dict[str, Any],
        api_result: ApiResult,
        protocol: str,
        configured_model: str,
        check: dict[str, Any],
        request_parameters: dict[str, Any] | None,
        *,
        effective_prompt: str | None = None,
        prompt_version: str | None = None,
        request_mode: str = "full",
    ) -> Path:
        return self.writer.write(
            task_id=payload["task_id"],
            request_id=payload["request_id"],
            prompt_version=prompt_version or self.assets.prompt_version,
            protocol=protocol,
            model=api_result.model or configured_model,
            input_payload=payload,
            system_prompt=effective_prompt if effective_prompt is not None else self.assets.system_prompt,
            output_schema=self.assets.output_schema,
            raw_response=api_result.content,
            request_snapshot=api_result.request_snapshot,
            response_envelope=api_result.response_envelope,
            metadata={
                "latency_ms": api_result.latency_ms,
                "usage": api_result.usage,
                "provider_response_id": api_result.response_id,
                "request_mode": request_mode,
                "finish_reason": api_result.finish_reason,
                "request_parameters": request_parameters or {},
            },
            check=check,
        )

    def apply_m1(self, payload: dict[str, Any], outcome: M1CallOutcome) -> None:
        apply_m1_response(self.session, payload, outcome.parsed)
        self.session.api_runs.append(
            {
                "request_id": payload["request_id"],
                "base_version": payload["base_version"],
                "prompt_version": outcome.prompt_version or self.assets.prompt_version,
                "contract_version": self.assets.contract_version,
                "request_mode": outcome.request_mode,
                "latency_ms": outcome.api_result.latency_ms,
                "usage": outcome.api_result.usage,
                "finish_reason": outcome.api_result.finish_reason,
                "status": "accepted_as_candidate",
                "recovery_mode": outcome.recovery_mode,
                "evidence_dir": str(outcome.evidence_dir),
            }
        )
        self.session.touch()

    def prepare_m2(self, request_id: str, *, current_date: str | None = None) -> dict[str, Any]:
        return build_m2_input(self.session, request_id, current_date=current_date)

    def m2_retry_recommended(self) -> bool:
        for run in reversed(self.session.api_runs):
            if not str(run.get("contract_version", "")).startswith("m2."):
                continue
            if run.get("source_requirements_version") != self.session.requirement_version:
                return False
            if run.get("status") == "accepted_as_plan_draft":
                return False
            return bool(run.get("status"))
        return False

    def invoke_m2(
        self,
        payload: dict[str, Any],
        client: JsonCompletionClient,
        *,
        protocol: str,
        configured_model: str,
        request_parameters: dict[str, Any] | None = None,
        compact_retry: bool = False,
    ) -> M2CallOutcome:
        check_cancelled()
        mode = "compact_retry" if compact_retry else "full"
        effective_prompt = m2_system_prompt(self.m2_assets.system_prompt, compact_retry=compact_retry)
        evidence_options = {"effective_prompt": effective_prompt, "request_mode": mode}
        logging.getLogger(__name__).info("M2 planning request with interview context; task=%s request=%s questions=%s sources=%s",
                                        payload["task_id"], payload["request_id"], len(payload.get("interview_context", [])),
                                        len(payload.get("relevant_materials", [])))
        try:
            api_result = client.complete_json(
                effective_prompt, payload, self.m2_assets.output_schema
            )
            check_cancelled()
        except ApiError as exc:
            check_cancelled()
            api_result = ApiResult.from_error(exc)
            check = {
                "valid": False,
                "schema": "not_reached",
                "semantic": "not_reached",
                "business_status": None,
                "failure_kind": exc.kind,
                "status_code": exc.status_code,
                "finish_reason": exc.finish_reason,
                "error": str(exc),
            }
            evidence_dir = self._write_m2_evidence(
                payload, api_result, protocol, configured_model, check, request_parameters, **evidence_options
            )
            self._record_m2_failure(payload, exc.kind, str(exc), evidence_dir, api_result, request_mode=mode)
            raise M2CallFailure(
                str(exc), evidence_dir, kind=exc.kind, api_result=api_result,
                status_code=exc.status_code,
            ) from exc
        normalization_report: list[dict[str, Any]] = []
        try:
            parsed = parse_m2_response(
                api_result.content, payload, self.m2_assets.output_schema,
                normalization_report=normalization_report,
            )
            check = {
                "valid": True,
                "schema": "passed",
                "semantic": "passed",
                "business_status": parsed["status"],
                "error": None,
                "normalization": normalization_report,
            }
        except Exception as exc:
            stage = getattr(exc, "stage", "internal")
            check = {
                "valid": False,
                "schema": "passed" if stage == "semantic" else "failed" if stage == "schema" else "not_reached",
                "semantic": "failed" if stage == "semantic" else "not_reached",
                "failure_stage": stage,
                "normalization": normalization_report,
                "business_status": None,
                "failure_kind": "validation_error",
                "error": str(exc),
            }
            evidence_dir = self._write_m2_evidence(
                payload, api_result, protocol, configured_model, check, request_parameters, **evidence_options
            )
            message = f"模型返回未通过M2校验：{exc}"
            self._record_m2_failure(
                payload, "validation_error", message, evidence_dir, api_result, request_mode=mode
            )
            raise M2CallFailure(
                message, evidence_dir, kind="validation_error", api_result=api_result,
                validation_stage=stage,
            ) from exc
        evidence_dir = self._write_m2_evidence(
            payload, api_result, protocol, configured_model, check, request_parameters, **evidence_options
        )
        if parsed["status"] == "error":
            message = parsed["error"]["message"]
            self._record_m2_failure(payload, "content_error", message, evidence_dir, api_result, request_mode=mode)
            raise M2CallFailure(
                f"模型未能形成方案：{message}",
                evidence_dir,
                kind="content_error",
                api_result=api_result,
                recovery_action=parsed["error"]["recovery_action"],
            )
        return M2CallOutcome(api_result.content, parsed, api_result, evidence_dir, mode, normalization_report)

    def _write_m2_evidence(
        self,
        payload: dict[str, Any],
        api_result: ApiResult,
        protocol: str,
        configured_model: str,
        check: dict[str, Any],
        request_parameters: dict[str, Any] | None,
        *,
        effective_prompt: str | None = None,
        request_mode: str = "full",
    ) -> Path:
        return self.writer.write(
            task_id=payload["task_id"],
            request_id=payload["request_id"],
            prompt_version=self.m2_assets.prompt_version,
            protocol=protocol,
            model=api_result.model or configured_model,
            input_payload=payload,
            system_prompt=effective_prompt if effective_prompt is not None else self.m2_assets.system_prompt,
            output_schema=self.m2_assets.output_schema,
            raw_response=api_result.content,
            metadata={
                "latency_ms": api_result.latency_ms,
                "usage": api_result.usage,
                "provider_response_id": api_result.response_id,
                "finish_reason": api_result.finish_reason,
                "request_mode": request_mode,
                "request_parameters": request_parameters or {},
            },
            check={**check, "finish_reason": api_result.finish_reason},
        )

    def _record_m2_failure(
        self,
        payload: dict[str, Any],
        kind: str,
        message: str,
        evidence_dir: Path,
        api_result: ApiResult,
        *,
        request_mode: str = "full",
    ) -> None:
        self.session.pending_requests.pop(payload["request_id"], None)
        self.session.errors.append(
            {"request_id": payload["request_id"], "kind": f"m2_{kind}", "message": message}
        )
        self.session.api_runs.append(
            {
                "request_id": payload["request_id"],
                "source_requirements_version": payload["source_requirements_version"],
                "prompt_version": self.m2_assets.prompt_version,
                "contract_version": self.m2_assets.contract_version,
                "latency_ms": api_result.latency_ms,
                "usage": api_result.usage,
                "finish_reason": api_result.finish_reason,
                "request_mode": request_mode,
                "status": kind,
                "evidence_dir": str(evidence_dir),
            }
        )
        self.session.touch()

    def apply_m2(self, payload: dict[str, Any], outcome: M2CallOutcome) -> None:
        apply_m2_response(
            self.session,
            payload,
            outcome.parsed,
            prompt_version=self.m2_assets.prompt_version,
            contract_version=self.m2_assets.contract_version,
        )
        self.session.api_runs.append(
            {
                "request_id": payload["request_id"],
                "source_requirements_version": payload["source_requirements_version"],
                "prompt_version": self.m2_assets.prompt_version,
                "contract_version": self.m2_assets.contract_version,
                "latency_ms": outcome.api_result.latency_ms,
                "usage": outcome.api_result.usage,
                "finish_reason": outcome.api_result.finish_reason,
                "request_mode": outcome.request_mode,
                "status": "accepted_as_plan_draft",
                "normalization": deepcopy(outcome.normalization_report),
                "evidence_dir": str(outcome.evidence_dir),
            }
        )
        self.session.touch()

    def prepare_m5(
        self,
        request_id: str,
        *,
        criterion_id: str | None = None,
        criterion_description: str,
        max_chars: int = 240,
    ) -> dict[str, Any]:
        return build_m5_input(
            self.session,
            request_id,
            criterion_id=criterion_id,
            criterion_description=criterion_description,
            max_chars=max_chars,
        )

    def invoke_m5(
        self,
        payload: dict[str, Any],
        client: JsonCompletionClient,
        *,
        protocol: str,
        configured_model: str,
        request_parameters: dict[str, Any] | None = None,
    ) -> M5CallOutcome:
        """Call M5, record evidence, and return a validated but unapplied example."""
        check_cancelled()
        try:
            api_result = client.complete_json(
                self.m5_assets.system_prompt,
                payload,
                self.m5_assets.output_schema,
            )
            check_cancelled()
        except ApiError as exc:
            check_cancelled()
            api_result = ApiResult.from_error(exc)
            check = {
                "valid": False,
                "schema": "not_reached",
                "semantic": "not_reached",
                "business_status": None,
                "failure_kind": exc.kind,
                "status_code": exc.status_code,
                "finish_reason": exc.finish_reason,
                "error": str(exc),
            }
            evidence_dir = self._write_m5_evidence(
                payload, api_result, protocol, configured_model, check, request_parameters
            )
            self._record_m5_failure(payload, exc.kind, str(exc), evidence_dir, api_result)
            raise M5CallFailure(str(exc), evidence_dir, kind=exc.kind, api_result=api_result) from exc

        try:
            normalization: list[dict[str, Any]] = []
            parsed = parse_m5_response(
                api_result.content,
                payload,
                self.m5_assets.output_schema,
                normalization_report=normalization,
            )
            check = {
                "valid": True,
                "schema": "passed",
                "semantic": "passed",
                "business_status": parsed["status"],
                "error": None,
                "normalization": normalization,
            }
        except Exception as exc:
            check = {
                "valid": False,
                "schema": "failed_or_not_reached",
                "semantic": "failed_or_not_reached",
                "business_status": None,
                "failure_kind": "validation_error",
                "error": str(exc),
            }
            evidence_dir = self._write_m5_evidence(
                payload, api_result, protocol, configured_model, check, request_parameters
            )
            message = f"模型返回未通过M5校验：{exc}"
            self._record_m5_failure(payload, "validation_error", message, evidence_dir, api_result)
            raise M5CallFailure(
                message, evidence_dir, kind="validation_error", api_result=api_result
            ) from exc

        evidence_dir = self._write_m5_evidence(
            payload, api_result, protocol, configured_model, check, request_parameters
        )
        if parsed["status"] == "error":
            message = (parsed.get("error") or {}).get("message") or "模型未能生成示例。"
            self._record_m5_failure(payload, "content_error", message, evidence_dir, api_result)
            raise M5CallFailure(
                f"模型未能生成示例：{message}",
                evidence_dir,
                kind="content_error",
                api_result=api_result,
            )
        if normalization:
            (evidence_dir / "response.effective.json").write_text(
                json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        return M5CallOutcome(api_result.content, parsed, api_result, evidence_dir)

    def _write_m5_evidence(
        self,
        payload: dict[str, Any],
        api_result: ApiResult,
        protocol: str,
        configured_model: str,
        check: dict[str, Any],
        request_parameters: dict[str, Any] | None,
    ) -> Path:
        return self.writer.write(
            task_id=payload["task_id"],
            request_id=payload["request_id"],
            prompt_version=self.m5_assets.prompt_version,
            protocol=protocol,
            model=api_result.model or configured_model,
            input_payload=payload,
            system_prompt=self.m5_assets.system_prompt,
            output_schema=self.m5_assets.output_schema,
            raw_response=api_result.content,
            metadata={
                "latency_ms": api_result.latency_ms,
                "usage": api_result.usage,
                "provider_response_id": api_result.response_id,
                "finish_reason": api_result.finish_reason,
                "request_parameters": request_parameters or {},
            },
            check={**check, "finish_reason": api_result.finish_reason},
        )

    def _record_m5_failure(
        self,
        payload: dict[str, Any],
        kind: str,
        message: str,
        evidence_dir: Path,
        api_result: ApiResult,
    ) -> None:
        self.session.pending_requests.pop(payload["request_id"], None)
        self.session.m5_state.update(
            {
                "status": "error",
                "request_id": payload["request_id"],
                "base_version": payload.get("base_version"),
                "last_error": message,
                "candidate_pending": False,
            }
        )
        self.session.errors.append(
            {"request_id": payload["request_id"], "kind": f"m5_{kind}", "message": message}
        )
        self.session.api_runs.append(
            {
                "request_id": payload["request_id"],
                "base_version": payload["base_version"],
                "prompt_version": self.m5_assets.prompt_version,
                "contract_version": self.m5_assets.contract_version,
                "latency_ms": api_result.latency_ms,
                "usage": api_result.usage,
                "finish_reason": api_result.finish_reason,
                "status": kind,
                "evidence_dir": str(evidence_dir),
            }
        )
        self.session.touch()

    def apply_m5(self, payload: dict[str, Any], outcome: M5CallOutcome) -> dict[str, Any] | None:
        row = apply_m5_response(self.session, payload, outcome.parsed)
        self.session.api_runs.append(
            {
                "request_id": payload["request_id"],
                "base_version": payload["base_version"],
                "prompt_version": self.m5_assets.prompt_version,
                "contract_version": self.m5_assets.contract_version,
                "latency_ms": outcome.api_result.latency_ms,
                "usage": outcome.api_result.usage,
                "finish_reason": outcome.api_result.finish_reason,
                "status": "accepted_as_m5_example",
                "evidence_dir": str(outcome.evidence_dir),
            }
        )
        self.session.touch()
        return row
