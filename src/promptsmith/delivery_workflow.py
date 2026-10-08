"""Prepare, invoke, validate, and atomically apply M3/M4 delivery calls."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .api import ApiError, ApiResult
from .finalization import (
    DeliveryValidationError,
    build_final_draft,
    render_canonical_body,
    skill_reference_for_binding,
    stage_final_draft,
    validate_current_final,
)
from .m3 import M3Assets, _remote_provenance, build_m3_input, parse_m3_response
from .m4 import M4Assets, build_m4_input, parse_m4_response
from .runlog import RunEvidenceWriter
from .session import SessionState, SessionStateError, StaleResponseError
from .workflow import JsonCompletionClient


class DeliveryWorkflowError(SessionStateError):
    pass


class DeliveryStaleResponseError(StaleResponseError):
    pass


class DeliveryCallFailure(RuntimeError):
    def __init__(
        self,
        message: str,
        evidence_dir: Path,
        *,
        kind: str,
        api_result: ApiResult,
    ) -> None:
        super().__init__(message)
        self.evidence_dir = evidence_dir
        self.kind = kind
        self.api_result = api_result


@dataclass(frozen=True)
class DeliveryCallOutcome:
    request_id: str
    purpose: str
    payload: dict[str, Any]
    raw_response: str
    parsed: dict[str, Any] | None
    api_result: ApiResult
    evidence_dir: Path
    failure_kind: str | None = None
    error: str | None = None
    status_code: int | None = None


M3CallOutcome = DeliveryCallOutcome
M4CallOutcome = DeliveryCallOutcome


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _environment(value: dict[str, Any] | None, unknowns: list[dict[str, Any]]) -> dict[str, list[str]]:
    provided = value or {}
    unknown = provided.get("unknown")
    if unknown is None:
        unknown = [str(row.get("description", "")) for row in unknowns if row.get("description")]
    result = {
        "known": deepcopy(provided.get("known", [])),
        "unknown": deepcopy(unknown),
        "forbidden_actions": deepcopy(provided.get("forbidden_actions", [])),
    }
    for key, rows in result.items():
        if not isinstance(rows, list) or any(not isinstance(row, str) or not row.strip() for row in rows):
            raise DeliveryWorkflowError(f"环境字段 {key} 必须是非空字符串数组。")
    return result


def _key_work_for_model(row: dict[str, Any]) -> dict[str, Any]:
    fields = ("key_work_id", "title", "goal", "inputs", "outputs", "checkpoints", "step_ids")
    return {key: deepcopy(row.get(key)) for key in fields}


def _step_for_model(row: dict[str, Any]) -> dict[str, Any]:
    fields = ("step_id", "title", "purpose", "inputs", "actions", "outputs", "completion_criteria")
    return {key: deepcopy(row.get(key)) for key in fields}


def _prerequisites_for_binding(binding: dict[str, Any]) -> list[dict[str, Any]]:
    record = binding.get("record_snapshot") or {}
    is_remote = record.get("origin") == "remote"

    def source_for(assessment: dict[str, Any]) -> str:
        source = assessment.get("source")
        if is_remote and source in {None, "catalog_evidence"}:
            return "remote_source_review"
        return source or "catalog_evidence"

    source_rows = record.get("adaptation_prerequisites", [])
    assessments = binding.get("precondition_assessments")
    if assessments is None:
        assessments = binding.get("prerequisite_assessments", [])
    assessed = {
        row.get("prerequisite_id"): row
        for row in assessments
        if isinstance(row, dict) and row.get("prerequisite_id")
    }
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in source_rows:
        prerequisite_id = source.get("prerequisite_id")
        if not isinstance(prerequisite_id, str) or not prerequisite_id:
            continue
        assessment = assessed.get(prerequisite_id, {})
        result.append(
            {
                "prerequisite_id": prerequisite_id,
                "description": source.get("description") or assessment.get("description") or prerequisite_id,
                "status": assessment.get("status", source.get("status", "unknown")),
                "source": source_for(assessment),
                "blocking": bool(assessment.get("blocking", source.get("blocking", True))),
            }
        )
        seen.add(prerequisite_id)
    for prerequisite_id, assessment in assessed.items():
        if prerequisite_id in seen:
            continue
        result.append(
            {
                "prerequisite_id": prerequisite_id,
                "description": assessment.get("description") or prerequisite_id,
                "status": assessment.get("status", "unknown"),
                "source": source_for(assessment),
                "blocking": bool(assessment.get("blocking", True)),
            }
        )
    return result


def _method_summary_for_binding(binding: dict[str, Any]) -> str:
    record = binding.get("record_snapshot") or {}
    reference = skill_reference_for_binding(binding)
    summary = (
        f"已选 Agent Skill：{reference['name']}\n"
        f"来源：{reference['source_url'] or reference['local_path'] or '请按名称查找或让用户提供文件'}\n"
        f"说明：{str(record.get('description') or record.get('adaptation_summary') or '').strip()}"
    )[:2000]
    verification = record.get("verification") or {}
    if not isinstance(verification, dict) or not verification.get("source_read"):
        return summary

    source_field = "source_text" if record.get("origin") == "remote" else "body_preview"
    source_text = record.get(source_field)
    if not isinstance(source_text, str) or not source_text.strip():
        return summary

    # The selected snapshot is already pinned to its record hash; keep only a
    # bounded excerpt of its Agent Skill instructions in the model request.
    excerpt_limit = max(1000, 3200 - len(summary))
    excerpt = source_text.strip()[:excerpt_limit]
    if len(source_text.strip()) > excerpt_limit:
        excerpt += "\n[Agent Skill 指令摘录已截断]"
    prefix = f"{summary}\n" if summary else ""
    return f"{prefix}以下是已选 Agent Skill 的来源指令摘录，仅供参考：\n{excerpt}"


class DeliveryWorkflow:
    """M3/M4 call boundary; invoke is side-effect-free for session business state."""

    def __init__(
        self,
        session: SessionState,
        *,
        evidence_root: str | Path,
        m3_assets: M3Assets | None = None,
        m4_assets: M4Assets | None = None,
        session_instance_token: str | None = None,
    ) -> None:
        self.session = session
        self.m3_assets = m3_assets or M3Assets.load()
        self.m4_assets = m4_assets or M4Assets.load()
        self.writer = RunEvidenceWriter(evidence_root)
        self.session_instance_token = session_instance_token or uuid4().hex
        self._requests: dict[str, dict[str, Any]] = {}
        self._used_request_ids: set[str] = set()
        self._slot_epochs = {"m3": 0, "m4": 0}

    def prepare_m3(
        self,
        request_id: str,
        *,
        connection_version: int,
        target_environment: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._validate_request_id(request_id, connection_version)
        from .finalization import validate_delivery_entry

        validate_delivery_entry(self.session)
        state = self.session.skill_state
        if state.get("status") not in {"candidates_ready", "selected"}:
            raise DeliveryWorkflowError("当前没有可分析的候选批次。")
        batch = state.get("candidate_batch")
        if not isinstance(batch, dict) or not batch.get("batch_id") or not batch.get("catalog_hash"):
            raise DeliveryWorkflowError("当前候选批次缺少批次编号或目录快照。")
        result = batch.get("result") or {}
        candidates = result.get("candidates") or []
        if not candidates:
            raise DeliveryWorkflowError("当前批次没有候选，无需调用 M3。")
        plan_content = self.session.plan["content"]
        unknowns = plan_content.get("unresolved_items", [])
        payload = build_m3_input(
            request_id,
            self.session.task_id,
            self._source_basis(),
            [_key_work_for_model(row) for row in plan_content.get("key_work", [])],
            candidates,
            _environment(target_environment, unknowns),
        )
        context = self._context("m3", payload, connection_version)
        self._register(context, payload)
        return deepcopy(payload)

    def prepare_m4(
        self,
        request_id: str,
        *,
        connection_version: int,
        target_environment: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._validate_request_id(request_id, connection_version)
        from .finalization import validate_delivery_entry

        validate_delivery_entry(self.session)
        state = self.session.skill_state
        if state.get("status") != "selected" or not state.get("bindings"):
            raise DeliveryWorkflowError("当前没有已选用的 Agent Skill。")
        plan_content = deepcopy(self.session.plan["content"])
        unknowns = deepcopy(
            plan_content.get("unresolved_items", [])
            or [row for row in self.session.gaps if row.get("importance") == "can_defer"]
        )
        baseline_plan = {
            "plan_id": self.session.plan["plan_id"],
            "plan_version": self.session.plan["plan_version"],
            **plan_content,
        }
        baseline_unknowns = [
            {
                "unknown_id": str(row.get("unknown_id") or row.get("unresolved_id") or row.get("source_gap_id") or f"unknown-{index + 1}"),
                "description": str(row.get("description") or row.get("text") or "未提供说明"),
            }
            for index, row in enumerate(unknowns)
        ]
        decisions_by_id = {
            row.get("suggestion_id"): row.get("decision")
            for row in self.session.final_result.get("suggestion_decisions", [])
            if row.get("plan_id") == self.session.plan.get("plan_id")
            and row.get("plan_version") == self.session.plan.get("plan_version")
        }
        payload = build_m4_input(
            {
                "schema_version": "m4.v0.1",
                "request_id": request_id,
                "task_id": self.session.task_id,
                "source_basis": self._source_basis(),
                "baseline": {
                    "task_text": self.session.task_text,
                    "requirements": deepcopy(self.session.requirements),
                    "plan": baseline_plan,
                    "unknowns": baseline_unknowns,
                },
                "bindings": [
                    {
                        "binding_id": row["binding_id"],
                        "skill_id": row["skill_id"],
                        "key_work_id": row["key_work_id"],
                        "record_hash": row["record_hash"],
                        "usage_mode": row.get("usage_mode", "method_adaptation"),
                        "step_ids": deepcopy(row.get("step_ids", [])),
                        "capability_ids": deepcopy(row.get("capability_ids", [])),
                        "prerequisite_assessments": _prerequisites_for_binding(row),
                        "method_adaptation_allowed": bool((row.get("record_snapshot") or {}).get("method_adaptation_allowed")),
                        "adaptation_summary": _method_summary_for_binding(row),
                        **(
                            {"provenance": provenance}
                            if isinstance(row.get("record_snapshot"), dict)
                            and (provenance := _remote_provenance(row["record_snapshot"])) is not None
                            else {}
                        ),
                    }
                    for row in state["bindings"]
                ],
                "key_work": [_key_work_for_model(row) for row in plan_content.get("key_work", [])],
                "steps": [_step_for_model(row) for row in plan_content.get("steps", [])],
                "suggestion_decisions": [
                    {
                        "suggestion_id": row["suggestion_id"],
                        "status": decisions_by_id.get(row.get("suggestion_id"), "pending"),
                        "description": str(row.get("text") or row.get("description") or row["suggestion_id"]),
                    }
                    for row in plan_content.get("suggestions", [])
                ],
                "target_environment": _environment(target_environment, unknowns),
            }
        )
        context = self._context("m4", payload, connection_version)
        self._register(context, payload)
        return deepcopy(payload)

    def invoke_m3(
        self,
        payload: dict[str, Any],
        client: JsonCompletionClient,
        *,
        protocol: str,
        configured_model: str,
        request_parameters: dict[str, Any] | None = None,
    ) -> M3CallOutcome:
        return self._invoke(
            "m3", payload, client, self.m3_assets, protocol, configured_model, request_parameters
        )

    def invoke_m4(
        self,
        payload: dict[str, Any],
        client: JsonCompletionClient,
        *,
        protocol: str,
        configured_model: str,
        request_parameters: dict[str, Any] | None = None,
    ) -> M4CallOutcome:
        return self._invoke(
            "m4", payload, client, self.m4_assets, protocol, configured_model, request_parameters
        )

    def apply_m3(
        self,
        payload: dict[str, Any],
        outcome: M3CallOutcome,
        *,
        connection_version: int,
        current_session_token: str | None = None,
    ) -> dict[str, Any]:
        context = self._claim("m3", payload, outcome, connection_version, current_session_token)
        if outcome.failure_kind or outcome.parsed is None:
            self._record_failure(context, outcome)
            self._requests.pop(payload["request_id"], None)
            raise self._failure(outcome)
        try:
            parsed = parse_m3_response(outcome.raw_response, payload, self.m3_assets.output_schema)
            if parsed["status"] == "error":
                self._record_business_error(context, outcome, parsed["error"]["message"])
                raise self._failure(outcome, "content_error", parsed["error"]["message"])
            if parsed != outcome.parsed:
                raise DeliveryWorkflowError("M3原始响应与已校验结果不一致。")
            next_state = deepcopy(self.session.skill_state)
            batch = next_state.get("candidate_batch")
            batch["m3_analysis"] = {
                "request_id": payload["request_id"],
                "prompt_version": self.m3_assets.prompt_version,
                "contract_version": self.m3_assets.contract_version,
                "record_hashes": deepcopy(context["snapshot"]["candidate_record_hashes"]),
                "result": deepcopy(parsed),
                "evidence_dir": str(outcome.evidence_dir),
            }
            self._commit_m3(next_state, context, outcome)
            return deepcopy(parsed)
        except DeliveryCallFailure:
            raise
        except Exception as exc:
            self._record_business_error(context, outcome, str(exc))
            raise self._failure(outcome, "apply_error", str(exc)) from exc
        finally:
            self._requests.pop(payload["request_id"], None)

    def apply_m4(
        self,
        payload: dict[str, Any],
        outcome: M4CallOutcome,
        *,
        connection_version: int,
        current_session_token: str | None = None,
    ) -> dict[str, Any]:
        context = self._claim("m4", payload, outcome, connection_version, current_session_token)
        if outcome.failure_kind or outcome.parsed is None:
            self._record_failure(context, outcome)
            self._requests.pop(payload["request_id"], None)
            raise self._failure(outcome)
        try:
            parsed = parse_m4_response(outcome.raw_response, payload, self.m4_assets.output_schema)
            if parsed["status"] == "error":
                self._record_business_error(context, outcome, parsed["error"]["message"])
                raise self._failure(outcome, "content_error", parsed["error"]["message"])
            if parsed != outcome.parsed:
                raise DeliveryWorkflowError("M4原始响应与已校验结果不一致。")
            working = deepcopy(self.session)
            request_id = payload["request_id"]
            prior_final = deepcopy(working.final_result)
            # A new generation supersedes unresolved changes from an older
            # generation; accepted additions remain in the rebuilt baseline.
            previous_content = working.final_result.get("content") or {}
            previous_content["pending_changes"] = [
                row for row in previous_content.get("pending_changes", [])
                if row.get("change_id") is None
            ]
            working.final_result["content"] = previous_content
            # Decisions belong to the generation that produced them. The prior
            # final is archived by stage_final_draft; the new current result
            # must not present an older generation's decision as current.
            working.final_result["change_decisions"] = []
            contributions = [
                {
                    **deepcopy(row),
                    "origin_binding_ids": [row["binding_id"]],
                    "m4_dependencies": [
                        {"generation_request_id": request_id, "change_id": change_id}
                        for change_id in row["proposed_change_ids"]
                    ],
                }
                for row in parsed["contributions"]
            ]
            draft = build_final_draft(working, selected_contributions=contributions)
            change_decisions = deepcopy(draft.get("change_decisions", []))
            pending_changes = deepcopy(draft["content"].get("pending_changes", []))
            for change in parsed["proposed_changes"]:
                pending_changes.append(
                    {
                        "change_id": change["change_id"],
                        "text": change["description"],
                        "reason": change["reason"],
                        "decision": "pending",
                        "kind": change["kind"],
                        "binding_ids": deepcopy(change["binding_ids"]),
                        "affects_hard_constraints": change["affects_hard_constraints"],
                        "generation_request_id": request_id,
                    }
                )
                change_decisions.append(
                    {
                        "generation_request_id": request_id,
                        "change_id": change["change_id"],
                        "decision": "pending",
                        "decided_by": "workflow",
                        "reason": "M4 首次接收，等待用户决定。",
                    }
                )
            draft["content"]["pending_changes"] = pending_changes
            draft["change_decisions"] = change_decisions
            draft["generation_request_id"] = request_id
            draft["review_required_ids"] = []
            self._refresh_final_body(draft)
            working.final_result = prior_final
            stage_final_draft(working, draft, expected_basis=draft["basis"])
            blocking_ids = list(working.final_result.get("review_required_ids", []))
            working.final_result["review_required_ids"] = []
            validate_current_final(working)
            working.final_result["review_required_ids"] = blocking_ids
            self._commit_m4(working, context, outcome)
            return deepcopy(parsed)
        except DeliveryCallFailure:
            raise
        except Exception as exc:
            self._record_business_error(context, outcome, str(exc))
            raise self._failure(outcome, "apply_error", str(exc)) from exc
        finally:
            self._requests.pop(payload["request_id"], None)

    def cancel(self, request_id: str) -> bool:
        context = self._requests.pop(request_id, None)
        if context is None:
            return False
        purpose = context["purpose"]
        if context["epoch"] == self._slot_epochs[purpose]:
            self._slot_epochs[purpose] += 1
        return True

    def invalidate_requests(self, purpose: str | None = None) -> None:
        purposes = {purpose} if purpose else {"m3", "m4"}
        for slot in purposes:
            if slot not in self._slot_epochs:
                raise ValueError(f"未知请求用途：{slot}")
            self._slot_epochs[slot] += 1
        self._requests = {
            request_id: context
            for request_id, context in self._requests.items()
            if context["purpose"] not in purposes
        }

    def _invoke(
        self,
        purpose: str,
        payload: dict[str, Any],
        client: JsonCompletionClient,
        assets: M3Assets | M4Assets,
        protocol: str,
        configured_model: str,
        request_parameters: dict[str, Any] | None,
    ) -> DeliveryCallOutcome:
        request_id = str(payload.get("request_id", ""))
        context = self._requests.get(request_id)
        if context is None or context.get("purpose") != purpose or context.get("payload_json") != _canonical(payload):
            raise DeliveryStaleResponseError("请求已取消、已失效或不属于当前模块。")
        api_result = ApiResult("", None, None, None, None)
        parsed: dict[str, Any] | None = None
        failure_kind: str | None = None
        error: str | None = None
        status_code: int | None = None
        check: dict[str, Any]
        try:
            api_result = client.complete_json(assets.system_prompt, payload, assets.output_schema)
        except ApiError as exc:
            failure_kind, error, status_code = exc.kind, str(exc), exc.status_code
            api_result = ApiResult.from_error(exc)
            check = {
                "valid": False,
                "schema": "not_reached",
                "semantic": "not_reached",
                "business_status": None,
                "failure_kind": failure_kind,
                "status_code": status_code,
                "finish_reason": exc.finish_reason,
                "error": error,
            }
        except Exception as exc:
            failure_kind = "client_error"
            error = f"模型调用失败（{type(exc).__name__}）。"
            check = {
                "valid": False,
                "schema": "not_reached",
                "semantic": "not_reached",
                "business_status": None,
                "failure_kind": failure_kind,
                "error": error,
            }
        else:
            try:
                parser = parse_m3_response if purpose == "m3" else parse_m4_response
                parsed = parser(api_result.content, payload, assets.output_schema)
                check = {
                    "valid": True,
                    "schema": "passed",
                    "semantic": "passed",
                    "business_status": parsed["status"],
                    "error": None,
                }
            except Exception as exc:
                failure_kind = "validation_error"
                error = str(exc)
                check = {
                    "valid": False,
                    "schema": "failed_or_not_reached",
                    "semantic": "failed_or_not_reached",
                    "business_status": None,
                    "failure_kind": failure_kind,
                    "error": error,
                }
        evidence_dir = self.writer.write(
            task_id=payload["task_id"],
            request_id=request_id,
            prompt_version=assets.prompt_version,
            protocol=protocol,
            model=api_result.model or configured_model,
            input_payload=payload,
            system_prompt=assets.system_prompt,
            output_schema=assets.output_schema,
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
        if parsed and parsed.get("status") == "error":
            error = parsed["error"]["message"]
        return DeliveryCallOutcome(
            request_id=request_id,
            purpose=purpose,
            payload=deepcopy(payload),
            raw_response=api_result.content,
            parsed=deepcopy(parsed),
            api_result=api_result,
            evidence_dir=evidence_dir,
            failure_kind=failure_kind,
            error=error,
            status_code=status_code,
        )

    def _claim(
        self,
        purpose: str,
        payload: dict[str, Any],
        outcome: DeliveryCallOutcome,
        connection_version: int,
        current_session_token: str | None,
    ) -> dict[str, Any]:
        request_id = str(payload.get("request_id", ""))
        context = self._requests.get(request_id)
        try:
            if context is None or context.get("purpose") != purpose:
                raise DeliveryStaleResponseError("请求不存在、已处理或用途不匹配。")
            if outcome.request_id != request_id or outcome.purpose != purpose:
                raise DeliveryStaleResponseError("响应与当前请求不匹配。")
            if context["payload_json"] != _canonical(payload) or _canonical(outcome.payload) != context["payload_json"]:
                raise DeliveryStaleResponseError("响应请求内容与原始快照不一致。")
            if context["session_token"] != self.session_instance_token:
                raise DeliveryStaleResponseError("响应属于另一个会话实例。")
            if current_session_token is not None and current_session_token != context["session_token"]:
                raise DeliveryStaleResponseError("会话已切换，已拒绝迟到响应。")
            if connection_version != context["connection_version"]:
                raise DeliveryStaleResponseError("模型连接配置版本已变化，已拒绝迟到响应。")
            if context["epoch"] != self._slot_epochs[purpose]:
                raise DeliveryStaleResponseError("同类请求已更新或当前请求已取消。")
            if context["snapshot"] != self._snapshot(purpose):
                raise DeliveryStaleResponseError("等待期间需求、方案、候选或最终结果已变化。")
            return context
        except DeliveryStaleResponseError:
            self._requests.pop(request_id, None)
            raise
        except Exception as exc:
            self._requests.pop(request_id, None)
            raise DeliveryStaleResponseError(f"等待期间上游状态已失效：{exc}") from exc

    def _context(self, purpose: str, payload: dict[str, Any], connection_version: int) -> dict[str, Any]:
        return {
            "request_id": payload["request_id"],
            "purpose": purpose,
            "task_id": self.session.task_id,
            "session_token": self.session_instance_token,
            "connection_version": connection_version,
            "snapshot": self._snapshot(purpose),
            "payload_json": _canonical(payload),
        }

    def _snapshot(self, purpose: str) -> dict[str, Any]:
        plan = self.session.plan
        state = self.session.skill_state
        batch = state.get("candidate_batch") or {}
        candidates = ((batch.get("result") or {}).get("candidates") or []) if isinstance(batch, dict) else []
        bindings = state.get("bindings") or []
        snapshot = {
            "task_id": self.session.task_id,
            "task_text": self.session.task_text,
            "category": self.session.selected_category,
            "requirement_version": self.session.requirement_version,
            "confirmed_requirements_version": self.session.confirmed_requirements_version,
            "plan_id": plan.get("plan_id"),
            "plan_version": plan.get("plan_version"),
            "confirmed_plan_version": plan.get("confirmed_plan_version"),
            "skill_revision": state.get("revision", 0),
            "skill_status": state.get("status"),
        }
        if purpose == "m3":
            snapshot.update(
                {
                    "candidate_batch_id": batch.get("batch_id"),
                    "catalog_hash": batch.get("catalog_hash"),
                    "candidate_record_hashes": [row.get("record_hash") for row in candidates],
                    "candidate_fingerprint": _digest(candidates),
                }
            )
        else:
            snapshot.update(
                {
                    "binding_fingerprint": _digest(bindings),
                    "selected_record_hashes": [row.get("record_hash") for row in bindings],
                    "delivery_revision": self.session.delivery_revision,
                    "final_id": self.session.final_result.get("final_id"),
                    "final_revision": self.session.final_result.get("revision"),
                }
            )
        return snapshot

    def _register(self, context: dict[str, Any], payload: dict[str, Any]) -> None:
        request_id = context["request_id"]
        if request_id in self._used_request_ids:
            raise DeliveryWorkflowError("请求编号已在本次运行中使用。")
        purpose = context["purpose"]
        if purpose == "m4" and any(active.get("purpose") == "m4" for active in self._requests.values()):
            raise DeliveryWorkflowError("已有 M4 请求处理中；请等待完成或先取消当前请求。")
        self._requests = {
            active_id: active
            for active_id, active in self._requests.items()
            if active["purpose"] != purpose
        }
        self._slot_epochs[purpose] += 1
        context["epoch"] = self._slot_epochs[purpose]
        self._requests[request_id] = deepcopy(context)
        self._used_request_ids.add(request_id)

    def _validate_request_id(self, request_id: str, connection_version: int) -> None:
        if not isinstance(request_id, str) or not request_id.strip():
            raise DeliveryWorkflowError("请求编号不能为空。")
        if request_id in self._used_request_ids:
            raise DeliveryWorkflowError("请求编号已在本次运行中使用。")
        if not isinstance(connection_version, int) or connection_version < 0:
            raise DeliveryWorkflowError("连接配置版本必须是非负整数。")

    def _source_basis(self) -> dict[str, Any]:
        return {
            "task_id": self.session.task_id,
            "plan_id": self.session.plan.get("plan_id"),
            "plan_version": self.session.plan.get("plan_version"),
            "requirement_version": self.session.requirement_version,
            "confirmed_plan_version": self.session.plan.get("confirmed_plan_version"),
            "confirmed_requirements_version": self.session.confirmed_requirements_version,
        }

    def _commit_m3(
        self,
        skill_state: dict[str, Any],
        context: dict[str, Any],
        outcome: DeliveryCallOutcome,
    ) -> None:
        api_runs = deepcopy(self.session.api_runs)
        api_runs.append(self._run_row(context, outcome, "accepted_as_candidate_analysis"))
        self.session.skill_state, self.session.api_runs = skill_state, api_runs
        self.session.touch()

    def _commit_m4(
        self,
        working: SessionState,
        context: dict[str, Any],
        outcome: DeliveryCallOutcome,
    ) -> None:
        working.api_runs.append(self._run_row(context, outcome, "accepted_as_final_draft"))
        self.session.final_result, self.session.final_archive, self.session.delivery_revision, self.session.updated_at, self.session.api_runs = (
            working.final_result,
            working.final_archive,
            working.delivery_revision,
            working.updated_at,
            working.api_runs,
        )

    def _record_failure(self, context: dict[str, Any], outcome: DeliveryCallOutcome) -> None:
        message = outcome.error or "模型调用失败。"
        self.session.errors.append(
            {"request_id": outcome.request_id, "kind": f"{context['purpose']}_{outcome.failure_kind or 'error'}", "message": message}
        )
        self.session.api_runs.append(self._run_row(context, outcome, outcome.failure_kind or "error"))
        self.session.touch()

    def _record_business_error(self, context: dict[str, Any], outcome: DeliveryCallOutcome, message: str) -> None:
        self.session.errors.append(
            {"request_id": outcome.request_id, "kind": f"{context['purpose']}_content_error", "message": message}
        )
        self.session.api_runs.append(self._run_row(context, outcome, "content_error"))
        self.session.touch()

    def _run_row(self, context: dict[str, Any], outcome: DeliveryCallOutcome, status: str) -> dict[str, Any]:
        return {
            "request_id": outcome.request_id,
            "purpose": context["purpose"],
            "task_id": context["task_id"],
            "connection_version": context["connection_version"],
            "prompt_version": self.m3_assets.prompt_version if context["purpose"] == "m3" else self.m4_assets.prompt_version,
            "contract_version": self.m3_assets.contract_version if context["purpose"] == "m3" else self.m4_assets.contract_version,
            "latency_ms": outcome.api_result.latency_ms,
            "usage": deepcopy(outcome.api_result.usage),
            "finish_reason": outcome.api_result.finish_reason,
            "status": status,
            "evidence_dir": str(outcome.evidence_dir),
        }

    @staticmethod
    def _refresh_final_body(draft: dict[str, Any]) -> None:
        body = render_canonical_body(draft["content"])
        draft["canonical_body"] = body
        draft["body_sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()

    @staticmethod
    def _failure(
        outcome: DeliveryCallOutcome,
        kind: str | None = None,
        message: str | None = None,
    ) -> DeliveryCallFailure:
        return DeliveryCallFailure(
            message or outcome.error or "模型调用失败。",
            outcome.evidence_dir,
            kind=kind or outcome.failure_kind or "content_error",
            api_result=outcome.api_result,
        )
