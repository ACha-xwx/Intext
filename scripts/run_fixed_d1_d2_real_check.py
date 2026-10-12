"""Fixed D1/D2 production-chain runner with explicit, resumable review checkpoints.

New runs require a non-existent evidence directory. On a checkpoint, inspect
review_request.json and write a decision JSON with its checkpoint_id and
snapshot_sha256 plus reviewer, rationale and actions, then use --resume
--decisions PATH. Model candidates are never automatically accepted.

This is a source-level content walkthrough, not an EXE/UI acceptance result.
Only tests inject offline clients; the CLI never labels fixtures as real output.
Credentials are accepted through a process environment or an invisible prompt
and are not part of any persisted object. The global limit includes earlier
attempts via --prior-call-count (eight earlier calls for this demonstration).
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from promptsmith.api import ApiConfig, ChatCompletionsClient
from promptsmith.delivery_workflow import DeliveryWorkflow
from promptsmith.exporter import export_markdown
from promptsmith.finalization import (
    build_final_draft, confirm_final, decide_m2_suggestion, decide_m4_change,
    render_task_prompt, stage_final_draft, validate_current_final,
)
from promptsmith.m1 import M1Assets
from promptsmith.m5 import M5Assets, feedback_candidate, record_m5_feedback
from promptsmith.session import SessionState, SessionStateError
from promptsmith.skill_catalog import SkillCatalog
from promptsmith.storage import load_session, save_session
from promptsmith.workflow import Phase12Workflow

DESIGN = ROOT / "resources" / "prompts"
DEFAULT_OUT = ROOT / "verification" / "acceptance_20260929_demo_features"
MAX_CALLS = 14
FIXED_FEEDBACK = "喜欢 B 的直接，但不要口号"
CASES = {
    "D1": {
        "task": (
            "为摄影社写一则发在新生微信群的招新通知，500 字以内。我希望语气自然，但拿不准应该活泼到什么程度。"
            "活动是 2026 年 10 月 10 日 14:00–16:00 在校园南广场的手机摄影体验，报名截止 2026 年 10 月 8 日；"
            "报名链接为演示用 https://example.com/photo-signup。不要添加未提供的负责人、收费或器材要求。"
        ),
        "category": "writing", "mode": "no_skill",
    },
    "D2": {
        "task": (
            "为社团活动报名工具整理可供开发者使用的需求规格。已确定：成员可查看活动并报名或取消，"
            "管理员可设置人数上限并导出报名名单；同一成员不能重复报名，满额时不能新增报名。"
            "交付物是需求规格与测试要点，不要求现在写代码、部署、创建 issue 或对外发布。"
        ),
        "category": "coding", "mode": "skill",
    },
}


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _basis(session: SessionState) -> dict[str, Any]:
    return {
        "task_id": session.task_id, "requirement_version": session.requirement_version,
        "plan_id": session.plan.get("plan_id"), "plan_version": session.plan.get("plan_version"),
    }


def _review_state_hash(session: SessionState) -> str:
    state = session.to_dict()
    # `validate_loaded_delivery` may add a non-semantic recovery notice while
    # reopening a session. It must not invalidate an otherwise identical
    # operator checkpoint.
    final_result = state.get("final_result")
    if isinstance(final_result, dict):
        final_result = deepcopy(final_result)
        final_result.pop("recovery_notice", None)
        state["final_result"] = final_result
    return _digest({key: state.get(key) for key in (
        "task_id", "task_text", "selected_category", "requirement_version", "sources",
        "requirements", "pending_proposals", "pending_questions", "gaps", "open_conflicts",
        "pending_review_item_ids", "analysis_basis_version", "confirmed_requirements_version",
        "plan", "skill_state", "final_result", "m5_examples", "m5_feedback",
    )})


class CallBudgetExhausted(RuntimeError):
    pass


class DemoRun:
    """A small persisted operator script; it uses unchanged product entry points."""

    def __init__(self, config: ApiConfig, out_dir: Path, case_ids: list[str], *,
                 client: Any = None, prior_call_count: int | None = None, resume: bool = False,
                 evidence_mode: str = "real_model", max_calls: int | None = None, budget_reason: str = ""):
        self.config = config
        self.client = client if client is not None else ChatCompletionsClient(config)
        self.out_dir = Path(out_dir).resolve()
        if evidence_mode not in {"real_model", "offline_fixture"}:
            raise ValueError("invalid evidence mode")
        if not case_ids or any(value not in CASES for value in case_ids) or len(set(case_ids)) != len(case_ids):
            raise ValueError("case_ids must select D1 and/or D2 once")
        if max_calls is not None and (isinstance(max_calls, bool) or not isinstance(max_calls, int) or max_calls < 1):
            raise ValueError("max_calls must be a positive integer")
        if max_calls is not None and max_calls > MAX_CALLS and not budget_reason.strip():
            raise ValueError("A concrete budget reason is required above the default 14-call cap.")
        self.sessions: dict[str, SessionState] = {}
        if resume:
            self.manifest = json.loads((self.out_dir / "run_summary.json").read_text(encoding="utf-8"))
            if self.manifest["evidence_mode"] != evidence_mode:
                raise ValueError("Cannot change offline/real evidence classification on resume.")
            if self.manifest["model"] != config.model or self.manifest["base_url"] != config.base_url:
                raise ValueError("Resume must preserve the recorded endpoint and model.")
            for case_id in self.manifest["case_order"]:
                self.sessions[case_id] = load_session(self.out_dir / case_id / "session.json")
                case = self.manifest["cases"][case_id]
                last = case["calls"][-1] if case["calls"] else None
                if case["stage"].endswith("_call") and last and last["module"] == case["stage"].removesuffix("_call") and last["status"] in {"started", "applied"}:
                    case["status"] = "failed"
                    case["failure"] = {"stage": case["stage"], "error_type": "InterruptedProgress",
                        "error": "A prior call may have run. Inspect persisted evidence before an explicit recovery/retry.", "at": _now()}
                    self.manifest["status"] = "failed"
            if max_calls is not None and max_calls != self.manifest["call_limit"]:
                if max_calls < self.manifest["calls_used"]:
                    raise ValueError("Call limit cannot be below already recorded calls.")
                self.manifest.setdefault("budget_adjustments", []).append({"at": _now(),
                    "from": self.manifest["call_limit"], "to": max_calls, "reason": budget_reason})
                self.manifest["call_limit"] = max_calls
                if self.manifest["status"] == "budget_exhausted" and max_calls > self.manifest["calls_used"]:
                    self.manifest["status"] = "running"
                    for case in self.manifest["cases"].values():
                        if case["status"] == "budget_exhausted":
                            case.setdefault("failure_history", []).append(case.pop("failure"))
                            case["status"] = "running"
            self._save()
        else:
            max_calls = MAX_CALLS if max_calls is None else max_calls
            prior_call_count = (0 if evidence_mode == "offline_fixture" else 8) if prior_call_count is None else prior_call_count
            if isinstance(prior_call_count, bool) or not isinstance(prior_call_count, int) or not 0 <= prior_call_count <= max_calls:
                raise ValueError("prior_call_count must be between zero and the call limit")
            self.out_dir.mkdir(parents=True, exist_ok=False)
            self.manifest = {
                "runner_version": "fixed-demos.v0.2", "created_at": _now(),
                "evidence_mode": evidence_mode, "surface": "source_production_chain",
                "base_url": config.base_url, "model": config.model, "protocol": config.protocol,
                "case_order": case_ids, "prior_call_count": prior_call_count,
                "calls_used": prior_call_count, "call_limit": max_calls,
                "budget_adjustments": ([{"at": _now(), "from": MAX_CALLS, "to": max_calls, "reason": budget_reason}]
                                       if max_calls != MAX_CALLS else []),
                "status": "running", "cases": {},
            }
            for case_id in case_ids:
                case = CASES[case_id]
                session = SessionState.new()
                session.set_task(case["task"])
                session.choose_category(case["category"])
                self.sessions[case_id] = session
                self.manifest["cases"][case_id] = {
                    "case_id": case_id, **deepcopy(case), "stage": "m1_call",
                    "status": "running", "calls": [], "user_actions": [],
                    "decisions": [], "m5_done": False, "checkpoint": None,
                    "content_review": {"status": "pending_real_output_and_review"},
                }
            self._save()

    def _save(self) -> None:
        self.manifest["updated_at"] = _now()
        for case_id, session in self.sessions.items():
            save_session(session, self.out_dir / case_id / "session.json")
            _write(self.out_dir / case_id / "walkthrough_manifest.json", self.manifest["cases"][case_id])
        _write(self.out_dir / "run_summary.json", self.manifest)

    def _workflow(self, case_id: str) -> Phase12Workflow:
        return Phase12Workflow(self.sessions[case_id], M1Assets.load(DESIGN),
                               self.out_dir / case_id / "model_evidence", m5_assets=M5Assets.load(DESIGN))

    def _checkpoint(self, case_id: str, contents: dict[str, Any], allowed_actions: dict[str, Any]) -> None:
        case = self.manifest["cases"][case_id]
        checkpoint = {
            "checkpoint_id": f"{case_id}-{case['stage']}-{len(case['decisions']) + 1}",
            "case_id": case_id, "stage": case["stage"], "contents": deepcopy(contents),
            "snapshot_sha256": _digest(contents), "allowed_actions": allowed_actions,
            "business_state_sha256": _review_state_hash(self.sessions[case_id]),
            "instruction": "Inspect actual output against the fixed task. Supply reviewer, rationale, checkpoint_id, snapshot_sha256 and actions. Do not invent user decisions or promote model suggestions to hard constraints.",
        }
        checkpoint["decision_template"] = {
            "case_id": case_id, "checkpoint_id": checkpoint["checkpoint_id"],
            "snapshot_sha256": checkpoint["snapshot_sha256"], "reviewer": "填写审查者",
            "rationale": "填写对实际内容的判读依据，不可只写同意", "actions": deepcopy(allowed_actions),
        }
        case["checkpoint"] = checkpoint
        case["status"] = "needs_review"
        self.manifest["status"] = "needs_review"
        _write(self.out_dir / case_id / "review_request.json", checkpoint)
        self._save()

    def _call(self, case_id: str, module: str) -> Any:
        if self.manifest["calls_used"] >= self.manifest["call_limit"]:
            raise CallBudgetExhausted("Total call limit reached, including prior attempts.")
        session = self.sessions[case_id]
        case = self.manifest["cases"][case_id]
        request_id = f"{case_id}-{module}-{len(case['calls']) + 1}-{uuid4().hex[:8]}"
        workflow = self._workflow(case_id)
        delivery = DeliveryWorkflow(session, evidence_root=self.out_dir / case_id / "model_evidence")
        if module == "m5":
            payload = workflow.prepare_m5(request_id, criterion_id="tone", criterion_description="语气自然但活泼程度适中")
        elif module in {"m1", "m2"}:
            payload = getattr(workflow, f"prepare_{module}")(request_id, current_date="2026-09-29")
        elif module in {"m3", "m4"}:
            if module == "m4":
                self._verify_selected_catalog(session)
            payload = getattr(delivery, f"prepare_{module}")(request_id, connection_version=0)
        else:
            raise ValueError(f"Unsupported model stage: {module}")
        self.manifest["calls_used"] += 1
        call = {"module": module, "request_id": request_id, "status": "started",
                "protocol": self.config.protocol, "model": self.config.model, "usage": None,
                "evidence_dir": None, "started_at": _now(), "input": deepcopy(payload)}
        owner = workflow if module in {"m1", "m2", "m5"} else delivery
        assets = workflow.assets if module == "m1" else getattr(owner, f"{module}_assets")
        call.update(prompt_version=assets.prompt_version, contract_version=assets.contract_version,
                    system_prompt_sha256=hashlib.sha256(assets.system_prompt.encode("utf-8")).hexdigest(),
                    output_schema_sha256=_digest(assets.output_schema))
        case["calls"].append(call)
        self._save()  # Crash/timeout still consumes a reserved call; no silent replay.
        started = time.perf_counter()
        outcome = None
        try:
            outcome = getattr(owner, f"invoke_{module}")(
                payload, self.client, protocol=self.config.protocol, configured_model=self.config.model,
                request_parameters={"base_url": self.config.base_url, "model": self.config.model,
                                    "protocol": self.config.protocol, "temperature": 0,
                                    "response_format": "json_object"})
            call["evidence_dir"] = str(outcome.evidence_dir)
            call["parsed_status"] = (outcome.parsed or {}).get("status")
            kwargs = {"connection_version": 0} if module in {"m3", "m4"} else {}
            parsed = getattr(owner, f"apply_{module}")(payload, outcome, **kwargs)
            assets = getattr(owner, f"{module}_assets", None) if module != "m1" else workflow.assets
            if assets:
                call["prompt_version"] = assets.prompt_version
                call["contract_version"] = assets.contract_version
            call.update(status="applied", model=outcome.api_result.model or self.config.model,
                        usage=deepcopy(outcome.api_result.usage), latency_ms=outcome.api_result.latency_ms)
            # Persist the applied state and next stage together in finally. A
            # resume must never repeat a successful call due to stale progress.
            case["stage"] = {"m1": "m1_review", "m2": "plan_review", "m5": "m5_review",
                             "m3": "skill_review", "m4": "final_review"}[module]
            if module == "m5":
                case["m5_example"] = parsed
            return parsed
        except Exception as exc:
            api_result = getattr(exc, "api_result", None) or getattr(outcome, "api_result", None)
            call.update(status="failed", error_type=type(exc).__name__, error=str(exc),
                        evidence_dir=str(getattr(exc, "evidence_dir", None) or call["evidence_dir"] or "") or None)
            if api_result is not None:
                call.update(model=api_result.model or self.config.model, usage=deepcopy(api_result.usage),
                            latency_ms=api_result.latency_ms)
            raise
        finally:
            call["elapsed_ms_observed"] = round((time.perf_counter() - started) * 1000)
            call["finished_at"] = _now()
            self._save()

    def _catalog(self, case_id: str) -> None:
        session = self.sessions[case_id]
        catalog = SkillCatalog.load(ROOT / "resources" / "skill_catalog" / "catalog_v0.1.json",
                                    source_root=ROOT, verify_sources=False)
        match = catalog.match(
            session.plan["content"].get("key_work", []), context_text=session.task_text
        )
        batch = {"batch_id": f"batch-{uuid4().hex}", "catalog_id": catalog.catalog_id,
                 "catalog_version": catalog.catalog_version, "catalog_hash": catalog.snapshot_hash,
                 "result": match.to_dict()}
        session.set_skill_state(status="candidates_ready" if match.status in {"ok", "incompatible"} else match.status,
                                basis=_basis(session), candidate_batch=batch, bindings=[])
        self.manifest["cases"][case_id]["skill_match"] = deepcopy(batch)

    @staticmethod
    def _verify_selected_catalog(session: SessionState) -> None:
        if not session.skill_state.get("bindings"):
            return
        # Mirrors source UI _refresh_selected_catalog; finding candidates alone
        # does not assert that their referenced source snapshots are available.
        catalog = SkillCatalog.load(ROOT / "resources" / "skill_catalog" / "catalog_v0.1.json",
                                    source_root=ROOT, verify_sources=True)
        assessment = catalog.assess_bindings(session.skill_state["bindings"])
        if assessment["status"] == "stale":
            raise SessionStateError("Selected Skill source check failed: " + "; ".join(assessment["reasons"]))

    def advance(self) -> dict[str, Any]:
        """Run until a review or error; each actual call passes production validation."""
        if self.manifest["status"] in {"failed", "budget_exhausted"}:
            return deepcopy(self.manifest)
        for case_id in self.manifest["case_order"]:
            case = self.manifest["cases"][case_id]
            session = self.sessions[case_id]
            while case["stage"] != "done":
                if case.get("checkpoint"):
                    self.manifest["status"] = "needs_review"
                    self._save()
                    return deepcopy(self.manifest)
                stage = case["stage"]
                try:
                    if stage.endswith("_call"):
                        module = stage.removesuffix("_call")
                        parsed = self._call(case_id, module)
                        case["stage"] = {"m1": "m1_review", "m2": "plan_review",
                                           "m5": "m5_review", "m3": "skill_review",
                                           "m4": "final_review"}[module]
                        if module == "m5":
                            case["m5_example"] = parsed
                    elif stage == "m1_review":
                        self._checkpoint(case_id, {"fixed_task": case["task"],
                            "requirements": session.requirements, "proposals": session.pending_proposals,
                            "questions": session.pending_questions, "unknown": session.gaps,
                            "conflicts": session.open_conflicts, "review_item_ids": session.pending_review_item_ids,
                            "readiness": session.last_readiness, "m5_done": case["m5_done"]},
                            {"accept_proposal_ids": [], "dismiss_remaining": False, "question_actions": [],
                             "review_requirement_ids": [], "confirm_requirements": False, "continue_analysis": False})
                    elif stage == "m5_review":
                        self._checkpoint(case_id, {"example": case["m5_example"], "fixed_feedback": FIXED_FEEDBACK,
                            "questions": session.pending_questions,
                            "candidate_preview": feedback_candidate(case["m5_example"], "b", FIXED_FEEDBACK)},
                            {"accept_fixed_m5_feedback": True, "tone_question_id": None})
                    elif stage == "plan_review":
                        self._checkpoint(case_id, {"plan": session.plan, "requirements": session.requirements,
                            "unknown": session.gaps}, {"review_key_work_ids": [], "confirm_plan": True})
                    elif stage == "catalog":
                        self._catalog(case_id)
                        candidates = session.skill_state["candidate_batch"]["result"]["candidates"]
                        case["stage"] = "m3_call" if case_id == "D2" and candidates else "skill_review"
                    elif stage == "skill_review":
                        self._checkpoint(case_id, {"fixed_mode": case["mode"], "skill_state": session.skill_state},
                                         {
                                             # A missing catalog match is a valid no-Skill path for either
                                             # fixed case. Only require a selection when an eligible candidate
                                             # was actually returned.
                                             "skip_skill": case_id == "D1" or not session.skill_state.get("candidate_batch", {}).get("result", {}).get("candidates"),
                                             "select_candidate_id": None,
                                         })
                    elif stage == "final_review":
                        self._checkpoint(case_id, {"final": session.final_result,
                            "requirements": session.requirements, "unknown": session.gaps},
                            {"m2_suggestion_decisions": {}, "m4_change_decisions": {}, "confirm_final": True})
                    elif stage == "persist":
                        self._persist_and_export(case_id)
                        case["stage"] = "content_review"
                    elif stage == "content_review":
                        self._checkpoint(case_id, {"fixed_task": case["task"], "final_prompt": session.final_result.get("canonical_body", ""),
                            "final": session.final_result, "observations": _content_observations(case_id, session.final_result.get("canonical_body", "")),
                            "evidence_mode": self.manifest["evidence_mode"]},
                            {"content_verdict": "passed|failed|partial", "findings": []})
                    else:
                        raise RuntimeError(f"Unknown stage {stage}")
                    self._save()
                except Exception as exc:
                    case["status"] = "budget_exhausted" if isinstance(exc, CallBudgetExhausted) else "failed"
                    case["failure"] = {"stage": stage, "error_type": type(exc).__name__, "error": str(exc), "at": _now()}
                    self.manifest["status"] = case["status"]
                    self._save()
                    return deepcopy(self.manifest)
        self.manifest["status"] = ("completed" if all(row["content_review"]["status"] == "passed"
                                    for row in self.manifest["cases"].values()) else "completed_with_findings")
        self._save()
        return deepcopy(self.manifest)

    def apply_decision(self, decision: dict[str, Any]) -> None:
        """Apply one content-bound operator decision atomically, never an unreviewed default."""
        case_id = decision.get("case_id")
        case = self.manifest["cases"].get(case_id)
        checkpoint = case.get("checkpoint") if case else None
        if not checkpoint or any(decision.get(key) != checkpoint[key] for key in ("checkpoint_id", "snapshot_sha256")):
            raise ValueError("Decision must target the exact current checkpoint and snapshot.")
        if checkpoint.get("business_state_sha256") != _review_state_hash(self.sessions[case_id]):
            raise ValueError("Business state changed after the review snapshot; the old decision cannot be applied.")
        if not str(decision.get("reviewer", "")).strip() or not str(decision.get("rationale", "")).strip():
            raise ValueError("An identified reviewer and concrete review rationale are required.")
        actions = decision.get("actions")
        if not isinstance(actions, dict) or not actions:
            raise ValueError("Explicit actions are required.")
        allowed = set(checkpoint["allowed_actions"])
        if not set(actions) <= allowed:
            raise ValueError("Decision contains unsupported actions.")
        session = deepcopy(self.sessions[case_id])
        updated = deepcopy(case)
        stage = case["stage"]
        if stage == "m1_review":
            ids = actions.get("accept_proposal_ids", [])
            if ids:
                selected = [row for row in session.pending_proposals if row["proposal_id"] in ids]
                if any(row.get("kind") == "system_suggestion" and row.get("strength") == "hard" for row in selected):
                    raise ValueError("Model suggestions cannot become user hard constraints in this fixed run.")
                session.accept_proposals(ids)
            if actions.get("dismiss_remaining"):
                session.dismiss_proposals()
            for answer in actions.get("question_actions", []):
                session.record_question(answer["question_id"], answer["disposition"], answer.get("text", ""))
            if actions.get("review_requirement_ids"):
                session.mark_requirements_reviewed(actions["review_requirement_ids"])
            if session.pending_proposals:
                raise SessionStateError("Review all remaining candidates explicitly before advancing.")
            if case_id == "D1" and not case["m5_done"]:
                if actions.get("confirm_requirements"):
                    raise ValueError("D1 must review its fixed M5 feedback before confirming requirements.")
                updated["stage"] = "m5_call"
            elif actions.get("confirm_requirements"):
                session.confirm_requirements()
                updated["stage"] = "m2_call"
            elif actions.get("continue_analysis") or session.analysis_basis_version != session.requirement_version:
                updated["stage"] = "m1_call"
            else:
                updated["stage"] = "m1_review"
        elif stage == "m5_review":
            if actions.get("accept_fixed_m5_feedback") is not True:
                raise ValueError("Review the fixed B feedback and its narrow interpretation explicitly.")
            row = record_m5_feedback(session, case["m5_example"]["example_id"], "b", FIXED_FEEDBACK)
            candidate = deepcopy(row["candidate"])
            proposal_id = candidate.get("proposal_id") or candidate.pop("candidate_id")
            candidate.update(proposal_id=proposal_id, source_request_id=row.get("example_id"),
                             source_base_version=session.requirement_version, valid_for_version=session.requirement_version)
            if not any(value.get("proposal_id") == proposal_id for value in session.pending_proposals):
                session.pending_proposals.append(candidate)
                session.touch()
            created = session.accept_proposals([proposal_id])
            tone_question_id = actions.get("tone_question_id")
            if tone_question_id:
                question = next((q for q in session.pending_questions if q["question_id"] == tone_question_id), None)
                if not question or question.get("field") != "style":
                    raise ValueError("The fixed M5 feedback can only answer an explicitly reviewed style question.")
                session.record_question(tone_question_id, "answered", FIXED_FEEDBACK)
            updated["m5_feedback"] = {"record": row, "accepted_proposal": candidate, "created_requirements": created}
            updated["m5_done"] = True
            updated["stage"] = "m1_call"
        elif stage == "plan_review":
            if actions.get("review_key_work_ids"):
                session.mark_key_work_reviewed(actions["review_key_work_ids"])
            if actions.get("confirm_plan") is not True:
                raise ValueError("This checkpoint requires explicit review and confirmation of the initial plan.")
            session.confirm_plan()
            updated["stage"] = "catalog"
        elif stage == "skill_review":
            candidates = session.skill_state["candidate_batch"]["result"]["candidates"]
            if actions.get("skip_skill"):
                if actions.get("select_candidate_id"):
                    raise ValueError("Select or skip, not both.")
                session.set_skill_state(status="skipped", basis=_basis(session),
                                        candidate_batch=session.skill_state["candidate_batch"], bindings=[])
                draft = build_final_draft(session)
                stage_final_draft(session, draft, expected_basis=draft["basis"])
                updated["actual_mode"] = "no_skill"
                updated["stage"] = "final_review"
            else:
                selected = next((row for row in candidates if row["candidate_id"] == actions.get("select_candidate_id")), None)
                if case_id != "D2" or not selected or selected["skill_id"] != "to-spec" or not selected.get("selection_allowed"):
                    raise ValueError("D2 may select an actual eligible to-spec candidate, or explicitly skip.")
                binding = {"binding_id": f"binding-{uuid4().hex}",
                           **{key: deepcopy(selected[key]) for key in ("skill_id", "record_hash", "record_snapshot", "key_work_id", "step_ids", "usage_mode", "capability_ids")},
                           "precondition_assessments": [{"prerequisite_id": value, "status": "unknown", "source": "catalog_evidence"}
                                                        for value in selected.get("adaptation_prerequisite_ids", [])]}
                session.set_skill_state(status="selected", basis=_basis(session),
                                        candidate_batch=session.skill_state["candidate_batch"], bindings=[binding])
                updated["actual_mode"] = "skill"
                updated["stage"] = "m4_call"
        elif stage == "final_review":
            for suggestion_id, value in actions.get("m2_suggestion_decisions", {}).items():
                decide_m2_suggestion(session, suggestion_id, value)
            for change_id, value in actions.get("m4_change_decisions", {}).items():
                decide_m4_change(session, change_id, value)
            if actions.get("confirm_final"):
                # Never rebuild an M4 result or erase its pending changes/review IDs here.
                self._verify_selected_catalog(session)
                confirm_final(session)
                updated["stage"] = "persist"
            else:
                updated["stage"] = "final_review"
        elif stage == "content_review":
            verdict = actions.get("content_verdict")
            if verdict not in {"passed", "failed", "partial"} or not isinstance(actions.get("findings"), list):
                raise ValueError("Content review needs a verdict and explicit findings list.")
            updated["content_review"] = {"status": verdict, "findings": actions["findings"],
                "reviewer": decision["reviewer"], "rationale": decision["rationale"],
                "evidence_mode": self.manifest["evidence_mode"]}
            updated["stage"] = "done"
        else:
            raise ValueError("No operator action is accepted at this stage.")
        updated["decisions"].append(deepcopy(decision))
        updated["user_actions"].append({"stage": stage, "reviewer": decision["reviewer"],
                                          "actions": deepcopy(actions), "at": _now()})
        updated["checkpoint"] = None
        updated["status"] = "completed" if updated["stage"] == "done" else "running"
        self.sessions[case_id] = session
        self.manifest["cases"][case_id] = updated
        self.manifest["status"] = "running"
        _write(self.out_dir / case_id / "decisions" / f"{len(updated['decisions']):03d}.json", decision)
        self._save()

    def allow_retry(self, *, reviewer: str, rationale: str) -> None:
        if self.manifest["status"] != "failed" or not reviewer.strip() or not rationale.strip():
            raise ValueError("Explicit reviewer and retry rationale are required for a failed run.")
        case = next(row for row in self.manifest["cases"].values() if row["status"] == "failed")
        if not case["stage"].endswith("_call"):
            raise ValueError("Only failed model stages support a same-task retry.")
        case.setdefault("failure_history", []).append(case.pop("failure"))
        case["user_actions"].append({"action": "explicit_same_task_retry", "reviewer": reviewer, "rationale": rationale, "at": _now()})
        case["status"] = "running"
        self.manifest["status"] = "running"
        self._save()

    def _persist_and_export(self, case_id: str) -> None:
        session = self.sessions[case_id]
        path = save_session(session, self.out_dir / case_id / "final_session.json")
        reopened = load_session(path)
        validate_current_final(reopened, require_confirmed=True)
        important = ("requirement_version", "requirements", "gaps", "open_conflicts",
                     "plan", "skill_state", "final_result", "m5_feedback")
        before, after = session.to_dict(), reopened.to_dict()
        checks = {key: before[key] == after[key] for key in important}
        if not all(checks.values()):
            raise RuntimeError("Saved/reopened business state differs: " + str(checks))
        case = self.manifest["cases"][case_id]
        export_path = export_markdown(reopened, self.out_dir / case_id / "final_export.md", mode="final")
        copied = render_task_prompt(reopened.final_result["canonical_body"], reopened.final_result.get("tone", "neutral"))
        (self.out_dir / case_id / "copy_payload.txt").write_text(copied, encoding="utf-8")
        case["persistence"] = {"checks": checks, "session_path": str(path), "export_path": str(export_path),
                               "copy_payload_sha256": hashlib.sha256(copied.encode("utf-8")).hexdigest(),
                               "copy_boundary": "Production render payload only; no OS clipboard/UI assertion."}
        case["final"] = deepcopy(reopened.final_result)
        self.sessions[case_id] = reopened


def _content_observations(case_id: str, output: str) -> dict[str, Any]:
    """Lexical observations do not decide semantic compliance or invent content."""
    if case_id == "D1":
        terms = ["2026", "10", "14:00", "16:00", "校园南广场", "https://example.com/photo-signup"]
        return {"label": "observations_only_requires_content_review",
                "literal_terms_present": {term: term in output for term in terms},
                "character_count": len(output), "within_500_characters": len(output) <= 500,
                "inspect_for_unprovided_facts": ["负责人", "收费", "器材要求"],
                "date_deadline_and_polarity_need_review": True}
    terms = ["查看", "报名", "取消", "人数", "导出", "重复", "满额"]
    return {"label": "observations_only_requires_content_review",
            "literal_terms_present": {term: term in output for term in terms},
            "unknowns_to_check": ["技术栈", "登录方式", "导出格式"],
            "forbidden_action_polarity_needs_review": ["编码", "部署", "创建 issue", "发布"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("PROMPTSMITH_API_BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--model", default=os.environ.get("PROMPTSMITH_MODEL", "deepseek-chat"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT / f"real_d1_d2_{time.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}")
    parser.add_argument("--case", choices=["D1", "D2", "all"], default="all")
    parser.add_argument("--prior-call-count", type=int, default=8, help="Earlier calls count toward the shared 14-call cap.")
    parser.add_argument("--max-calls", type=int, help="Default is 14; resume preserves its recorded limit unless explicitly changed.")
    parser.add_argument("--budget-reason", default="", help="Required for an explicit cap above 14; saved in evidence.")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--retry-reason")
    parser.add_argument("--reviewer", default="operator")
    parser.add_argument("--api-key-stdin", action="store_true")
    args = parser.parse_args()
    key = sys.stdin.readline().strip() if args.api_key_stdin else os.environ.get("PROMPTSMITH_API_KEY") or getpass.getpass("API key (memory only): ")
    if not key:
        raise SystemExit("missing API key")
    config = ApiConfig(base_url=args.base_url, model=args.model, api_key=key, timeout_seconds=120)
    run = DemoRun(config, args.out, ["D1", "D2"] if args.case == "all" else [args.case],
                  prior_call_count=args.prior_call_count, resume=args.resume,
                  max_calls=args.max_calls, budget_reason=args.budget_reason)
    if args.decisions:
        run.apply_decision(json.loads(args.decisions.read_text(encoding="utf-8-sig")))
    if args.retry_reason:
        run.allow_retry(reviewer=args.reviewer, rationale=args.retry_reason)
    result = run.advance()
    print(json.dumps({"status": result["status"], "evidence_dir": str(run.out_dir),
                      "calls_used_including_prior": result["calls_used"], "call_limit": result["call_limit"],
                      "cases": {key: {"stage": row["stage"], "status": row["status"]} for key, row in result["cases"].items()}}, ensure_ascii=False))
    key = ""
    return exit_code(result)


def exit_code(result: dict[str, Any]) -> int:
    return 0 if result["status"] == "completed" else 2 if result["status"] == "needs_review" else 1


if __name__ == "__main__":
    raise SystemExit(main())
