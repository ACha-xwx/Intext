from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


SESSION_SCHEMA_VERSION = "promptsmith.session.v0.2"
LEGACY_SESSION_SCHEMA_VERSION = "promptsmith.session.v0.1"

DIRECTION_FIELDS = {
    "goal",
    "deliverable",
    "purpose",
    "learning_goal",
    "decision_purpose",
    "analysis_question",
    "core_message",
}


class SessionStateError(ValueError):
    pass


class StaleResponseError(SessionStateError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_control() -> dict[str, Any]:
    return {
        # These legacy counters remain in saved sessions for compatibility.
        # Interview continuation is decided by information coverage instead.
        "max_questions": 2,
        "remaining_rounds": 2,
        "allow_questions": True,
        "context_coverage": "complete",
        "thinking_level": "standard",
        "thinking_policy": "coverage_based",
        "interview_rounds_used": 0,
        "interview_round_limit": 5,
        # Empty means the UI should use its environment/default GitHub API URL.
        "skill_search_url": "",
    }


def _migrate_control(value: Any) -> dict[str, Any]:
    migrated = _default_control()
    if isinstance(value, dict):
        migrated.update(deepcopy(value))
    return migrated


def _default_plan() -> dict[str, Any]:
    return {
        "plan_id": None,
        "plan_version": 0,
        "status": "not_started",
        "content": None,
        "original_content": None,
        "source_requirements_version": None,
        "confirmed_plan_version": None,
        "prompt_version": None,
        "contract_version": None,
        "created_at": None,
        "updated_at": None,
        "modified": False,
        "pending_key_work_review_ids": [],
        "reviewed_key_work_ids": [],
        "source_snapshot": None,
        "generation_request_id": None,
    }


def _migrate_plan(value: Any) -> dict[str, Any]:
    default = _default_plan()
    if not isinstance(value, dict):
        return default
    migrated = deepcopy(default)
    migrated.update(deepcopy(value))
    if "version" in value and "plan_version" not in value:
        migrated["plan_version"] = int(value.get("version") or 0)
    if "confirmed_version" in value and "confirmed_plan_version" not in value:
        migrated["confirmed_plan_version"] = value.get("confirmed_version")
    migrated.pop("version", None)
    migrated.pop("confirmed_version", None)
    migrated["pending_key_work_review_ids"] = list(
        dict.fromkeys(migrated.get("pending_key_work_review_ids") or [])
    )
    migrated["reviewed_key_work_ids"] = list(
        dict.fromkeys(migrated.get("reviewed_key_work_ids") or [])
    )
    return migrated


def _default_final() -> dict[str, Any]:
    return {
        "schema_version": "final.v0.1",
        "final_id": None,
        "revision": 0,
        "status": "not_started",
        "confirmed_revision": None,
        "basis": None,
        "content": None,
        "canonical_body": None,
        "body_sha256": None,
        "renderer_version": "final-render.v0.2",
        "tone": "neutral",
        "suggestion_decisions": [],
        "change_decisions": [],
        "review_required_ids": [],
        "unapplied_edits": [],
        "generation_request_id": None,
    }


def _default_skill_state() -> dict[str, Any]:
    return {
        "revision": 0,
        "status": "not_started",
        "basis": None,
        "candidate_batch": None,
        "bindings": [],
        "legacy_selection_unresolved": [],
        "last_error": None,
        "search_state": {
            "status": "idle",
            "local": None,
            "network": None,
            "last_error": None,
            "updated_at": None,
        },
    }


def _migrate_skill_state(value: Any, legacy_selected: Any, *, stored_version: str) -> dict[str, Any]:
    default = _default_skill_state()
    if isinstance(value, dict):
        default.update(deepcopy(value))
    elif stored_version == SESSION_SCHEMA_VERSION:
        default["status"] = "stale"
        default["last_error"] = "当前会话缺少有效的 Skill 状态，请复核选择。"
    if not isinstance(default.get("bindings"), list) or any(
        not isinstance(binding, dict)
        or not isinstance(binding.get("binding_id"), str)
        or not binding.get("binding_id")
        or not isinstance(binding.get("skill_id"), str)
        or not binding.get("skill_id")
        for binding in default["bindings"]
    ):
        raise SessionStateError("Skill 绑定数据损坏，无法安全恢复会话。")
    if not isinstance(default.get("legacy_selection_unresolved"), list):
        raise SessionStateError("Skill 遗留选择数据损坏，无法安全恢复会话。")
    search_state = default.get("search_state")
    if not isinstance(search_state, dict):
        search_state = _default_skill_state()["search_state"]
    else:
        migrated_search = _default_skill_state()["search_state"]
        migrated_search.update(deepcopy(search_state))
        search_state = migrated_search
    if search_state.get("status") not in {
        "idle", "local_running", "local_done", "network_running", "network_done", "error", "cancelled"
    }:
        search_state["status"] = "idle"
    elif search_state.get("status") in {"local_running", "network_running"}:
        interrupted = search_state["status"]
        search_state["status"] = "error"
        search_state["last_error"] = "会话保存时 Skill 搜索尚未完成，请重新尝试。"
        source_key = "local" if interrupted == "local_running" else "network"
        search_state[source_key] = {"status": "interrupted", "count": 0}
    default["search_state"] = search_state
    if stored_version == LEGACY_SESSION_SCHEMA_VERSION and isinstance(legacy_selected, list):
        default["legacy_selection_unresolved"] = list(
            dict.fromkeys([*default["legacy_selection_unresolved"], *legacy_selected])
        )
        if default["legacy_selection_unresolved"] and not default["bindings"]:
            default["status"] = "stale"
    elif stored_version == SESSION_SCHEMA_VERSION:
        # In v0.2 bindings are authoritative; this field is only a compatibility
        # mirror and must not recreate the v0.1 legacy warning on load.
        default["legacy_selection_unresolved"] = []
        mirror = list(dict.fromkeys(binding["skill_id"] for binding in default["bindings"]))
        if legacy_selected is not None and (
            not isinstance(legacy_selected, list) or legacy_selected != mirror
        ):
            default["status"] = "stale"
            default["last_error"] = "Skill 选择镜像与绑定记录不一致，请复核选择。"
    return default


def _migrate_final_result(value: Any) -> dict[str, Any]:
    default = _default_final()
    if isinstance(value, dict):
        default.update(deepcopy(value))
    status = default.get("status")
    if status in {"ready", "valid", "confirmed"} and not default.get("basis"):
        default["status"] = "stale"
        default["confirmed_revision"] = None
    if default.get("status") not in {"not_started", "draft", "confirmed", "stale"}:
        default["status"] = "stale"
    default.setdefault("revision", 0)
    default.setdefault("confirmed_revision", None)
    default.setdefault("tone", "neutral")
    default.setdefault("review_required_ids", [])
    default.setdefault("unapplied_edits", [])
    return default


def _default_m5_state() -> dict[str, Any]:
    """Small optional M5 state; examples and feedback remain append-only lists."""
    return {
        "revision": 0,
        "status": "not_started",
        "request_id": None,
        "example_id": None,
        "feedback_id": None,
        "base_version": None,
        "criterion_id": None,
        "criterion_description": None,
        "candidate_pending": False,
        "last_error": None,
    }


def _migrate_m5_state(value: Any) -> dict[str, Any]:
    default = _default_m5_state()
    if isinstance(value, dict):
        default.update(deepcopy(value))
    if default.get("status") not in {
        "not_started",
        "requesting",
        "ready",
        "feedback_recorded",
        "skipped",
        "error",
        "stale",
    }:
        default["status"] = "stale"
    if not isinstance(default.get("revision"), int) or default["revision"] < 0:
        default["revision"] = 0
    return default


@dataclass
class SessionState:
    schema_version: str = SESSION_SCHEMA_VERSION
    task_id: str = field(default_factory=lambda: f"task-{uuid4().hex}")
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    task_text: str = ""
    selected_category: str | None = None
    category_suggestion: dict[str, Any] | None = None
    requirement_version: int = 0
    analysis_basis_version: int | None = None
    confirmed_requirements_version: int | None = None
    requirements: list[dict[str, Any]] = field(default_factory=list)
    requirement_archive: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    current_source_id: str | None = None
    gaps: list[dict[str, Any]] = field(default_factory=list)
    question_history: list[dict[str, Any]] = field(default_factory=list)
    gap_update_history: list[dict[str, Any]] = field(default_factory=list)
    question_reopen_history: list[dict[str, Any]] = field(default_factory=list)
    interpretation_history: list[dict[str, Any]] = field(default_factory=list)
    deferred_proposals: list[dict[str, Any]] = field(default_factory=list)
    draft_authorization: dict[str, Any] | None = None
    open_conflicts: list[dict[str, Any]] = field(default_factory=list)
    compatible_conflicts: list[list[str]] = field(default_factory=list)
    pending_proposals: list[dict[str, Any]] = field(default_factory=list)
    pending_questions: list[dict[str, Any]] = field(default_factory=list)
    pending_review_item_ids: list[str] = field(default_factory=list)
    last_assistant_text: str = ""
    last_next_action: str | None = None
    last_readiness: dict[str, Any] | None = None
    # The model's semantic assessment is advisory evidence for the next
    # decision.  Program state still owns confirmation and persistence.
    last_model_judgment: dict[str, Any] | None = None
    control: dict[str, Any] = field(default_factory=_default_control)
    pending_requests: dict[str, dict[str, Any]] = field(default_factory=dict)
    api_runs: list[dict[str, Any]] = field(default_factory=list)
    plan: dict[str, Any] = field(default_factory=_default_plan)
    plan_archive: list[dict[str, Any]] = field(default_factory=list)
    selected_skills: list[str] = field(default_factory=list)
    delivery_revision: int = 0
    skill_state: dict[str, Any] = field(default_factory=_default_skill_state)
    final_result: dict[str, Any] = field(default_factory=_default_final)
    final_archive: list[dict[str, Any]] = field(default_factory=list)
    m5_state: dict[str, Any] = field(default_factory=_default_m5_state)
    m5_examples: list[dict[str, Any]] = field(default_factory=list)
    m5_feedback: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    runtime_api_key: str = field(default="", repr=False, compare=False)

    @classmethod
    def new(cls) -> "SessionState":
        return cls()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionState":
        stored_version = data.get("schema_version", LEGACY_SESSION_SCHEMA_VERSION)
        if stored_version not in {LEGACY_SESSION_SCHEMA_VERSION, SESSION_SCHEMA_VERSION}:
            raise SessionStateError(f"不支持的会话格式：{data.get('schema_version')}")
        known = {name for name in cls.__dataclass_fields__ if name != "runtime_api_key"}
        values = {key: deepcopy(value) for key, value in data.items() if key in known}
        values.setdefault("schema_version", SESSION_SCHEMA_VERSION)
        values["schema_version"] = SESSION_SCHEMA_VERSION
        values.setdefault("task_id", f"task-{uuid4().hex}")
        values.setdefault("created_at", _now())
        values.setdefault("updated_at", values["created_at"])
        values["plan"] = _migrate_plan(values.get("plan"))
        values["control"] = _migrate_control(values.get("control"))
        values["skill_state"] = _migrate_skill_state(
            values.get("skill_state"), data.get("selected_skills"), stored_version=stored_version
        )
        values["final_result"] = _migrate_final_result(values.get("final_result"))
        values["m5_state"] = _migrate_m5_state(values.get("m5_state"))
        values.setdefault("m5_examples", [])
        values.setdefault("m5_feedback", [])
        values.setdefault("final_archive", [])
        values.setdefault("delivery_revision", 0)
        session = cls(**values)
        # Earlier versions materialized M2 unknowns as compulsory questions.
        # Keep plan unknowns and answers, but retire that automatic queue.
        obsolete = [q for q in session.pending_questions
                    if q.get("clarification_scope") == "plan" and not q.get("user_requested_reopen")]
        if obsolete:
            session.pending_questions = [q for q in session.pending_questions if q not in obsolete]
            logging.getLogger(__name__).info("Retired automatic planning follow-ups on load; task=%s count=%s; unknowns preserved for downstream AI",
                                            session.task_id, len(obsolete))
        legacy_runs = data.get("trial_runs")
        if isinstance(legacy_runs, list) and legacy_runs:
            logging.getLogger(__name__).info("Ignored retired prompt execution history while loading session; records=%d", len(legacy_runs))
        session._validate_loaded_plan()
        pending = session.pending_requests
        if isinstance(pending, dict) and pending:
            retired = sum(isinstance(request, dict) and request.get("purpose") == "trial" for request in pending.values())
            if retired:
                logging.getLogger(__name__).info("Discarded retired prompt execution requests while loading session; count=%d", retired)
            interrupted = [
                {"request_id": request_id, "purpose": request.get("purpose", "unknown")}
                for request_id, request in pending.items()
                if isinstance(request, dict) and request.get("purpose") != "trial"
            ]
            session.pending_requests = {}
            session.errors.extend(
                {"kind": "request_interrupted_on_load", **row}
                for row in interrupted
            )
        from .finalization import validate_loaded_delivery

        validate_loaded_delivery(session)
        return session

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for name in self.__dataclass_fields__:
            if name != "runtime_api_key":
                data[name] = deepcopy(getattr(self, name))
        return data

    def touch(self) -> None:
        self.updated_at = _now()

    def workspace_navigation(self) -> dict[str, Any]:
        """Read-only review position; revisiting never revokes confirmations."""
        confirmed = self.confirmed_requirements_version == self.requirement_version
        review_ready = (self.last_next_action == "review_requirements" or self.plan.get("content")) and not self.questions_for_review() and not any(
            q.get("assessment_status") == "pending" and q.get("disposition") == "answered" for q in self.question_history)
        route = ["interview"]
        if confirmed or ((self.requirements or self.pending_proposals) and review_ready):
            route.append("requirements")
        if confirmed:
            route.append("plan")
            if self.plan.get("status") == "confirmed":
                route.append("skills")
                if self.final_result.get("canonical_body") and self.final_result.get("status") in {"draft", "confirmed"}:
                    if self.skill_state.get("status") == "skipped" and not self.skill_state.get("bindings"):
                        route.remove("skills")
                    route.append("result")
        basis = [self.requirement_version, self.confirmed_requirements_version,
                 self.plan.get("plan_version"), self.plan.get("status"),
                 self.skill_state.get("revision"), self.delivery_revision,
                 self.final_result.get("revision"), self.final_result.get("status")]
        saved = self.control.get("workspace_navigation")
        natural = route[-1]
        stage = saved.get("stage") if isinstance(saved, dict) and saved.get("basis") == basis else natural
        if stage not in route:
            stage = natural
        index = route.index(stage)
        return {"stage": stage, "natural": natural, "revisiting": stage != natural,
                "previous": route[index-1] if index else None,
                "next": route[index+1] if index+1 < len(route) else None, "basis": basis}

    def navigate_workspace(self, direction: str) -> str:
        navigation = self.workspace_navigation()
        if direction not in {"previous", "next"} or not navigation.get(direction):
            raise SessionStateError("当前没有可返回或继续的步骤。")
        stage = navigation[direction]
        self.control["workspace_navigation"] = {"stage": stage, "basis": navigation["basis"]}
        self.touch()
        logging.getLogger(__name__).info("Workspace review navigation; task=%s from=%s to=%s direction=%s results_preserved=True model_requests=0",
                                        self.task_id, navigation["stage"], stage, direction)
        return stage

    def active_gaps(self) -> list[dict[str, Any]]:
        from .clarification import without_skipped_unknowns
        return without_skipped_unknowns(self, self.gaps)

    def questions_for_review(self, *, include_plan: bool = True, respect_interview_limit: bool = True) -> list[dict[str, Any]]:
        from .clarification import review_candidates
        from .interview import rounds_used, round_limit

        if (self.plan.get("status") in {"draft", "confirmed"}
                and self.plan.get("source_requirements_version") == self.requirement_version
                and self.confirmed_requirements_version == self.requirement_version):
            return deepcopy([q for q in self.pending_questions if q.get("user_requested_reopen")
                             or (q.get("field") == "supplement" and q.get("clarification_scope") != "plan")])

        excluded = {row["gap_id"] for row in self.gaps} - {row["gap_id"] for row in self.active_gaps()}
        questions = deepcopy([q for q in self.pending_questions
                              if (q.get("clarification_scope") != "plan" or q.get("user_requested_reopen"))
                              and (q.get("gap_id") not in excluded or q.get("user_requested_reopen"))])
        if respect_interview_limit and not questions and rounds_used(self) >= round_limit(self):
            return []
        known = {q["question_id"] for q in questions}
        questions.extend(q for q in review_candidates(self, include_plan=include_plan)
                         if q["question_id"] not in known)
        return questions

    def validate_unknown_reviews(self, *, include_plan: bool = True) -> None:
        if self.questions_for_review(include_plan=include_plan, respect_interview_limit=False):
            # UI refreshes use this read-only guard to project enabled states.
            # Actual answers, interview transitions and failed UI actions log
            # at their event boundaries; polling is not a new user event.
            raise SessionStateError("请先逐项回答或跳过待补充问题，再核对并确认。")

    def defer_remaining_interview_unknowns(self) -> int:
        from .interview import rounds_used, round_limit
        if rounds_used(self) < round_limit(self) or self.pending_questions:
            raise SessionStateError("请先完成当前访谈问题，再核对剩余未知。")
        if any(q.get("assessment_status") == "pending" and q.get("disposition") == "answered" for q in self.question_history):
            raise SessionStateError("请先整理已记录的回答，再决定哪些内容使用时补充。")
        working = deepcopy(self)
        questions = working.questions_for_review(respect_interview_limit=False)
        for question in questions:
            working.record_question(question["question_id"], "unsure")
        self.__dict__.update(deepcopy(working.__dict__))
        logging.getLogger(__name__).info("User retained unknowns after bounded interview; task=%s count=%s", self.task_id, len(questions))
        return len(questions)

    def authorize_next_interview_round(self) -> int:
        from .interview import rounds_used, round_limit
        used = rounds_used(self)
        if used < round_limit(self) or self.pending_questions:
            raise SessionStateError("请先完成当前轮的问题，再决定是否继续。")
        if any(q.get("assessment_status") == "pending" and q.get("disposition") == "answered" for q in self.question_history):
            raise SessionStateError("请先整理已记录的回答，再决定是否继续追问。")
        if not self.questions_for_review(respect_interview_limit=False):
            raise SessionStateError("当前没有需要继续追问的未知，请先核对需求。")
        self.control["interview_round_limit"] = used + 1
        self.touch()
        logging.getLogger(__name__).info("User authorized one additional interview round; task=%s next_round=%s", self.task_id, used + 1)
        return used + 1

    def _next_id(self, prefix: str, rows: list[dict[str, Any]], key: str) -> str:
        highest = 0
        for row in rows:
            value = str(row.get(key, ""))
            if value.startswith(prefix) and value[len(prefix) :].isdigit():
                highest = max(highest, int(value[len(prefix) :]))
        return f"{prefix}{highest + 1}"

    def _add_source(self, text: str, role: str = "user") -> str:
        source_id = self._next_id("u" if role == "user" else "s", self.sources, "source_id")
        self.sources.append({"source_id": source_id, "role": role, "text": text})
        self.current_source_id = source_id if role == "user" else None
        return source_id

    def _invalidate_downstream(self) -> None:
        if self.plan.get("status") not in {None, "not_started"}:
            self.plan["status"] = "stale"
            self.plan["confirmed_plan_version"] = None
            self.plan["updated_at"] = _now()
        if self.final_result.get("status") not in {None, "not_started"}:
            self.final_result["status"] = "stale"
            self.final_result["confirmed_revision"] = None
        if self.skill_state.get("status") not in {None, "not_started"}:
            self.skill_state["status"] = "stale"
        # Keep bindings as historical snapshots. The current validity is controlled
        # by the basis and revision checks instead of erasing user choices.
        self.selected_skills = [
            str(row.get("skill_id"))
            for row in self.skill_state.get("bindings", [])
            if row.get("skill_id")
        ]

    def _delivery_changed(self, *, reason: str | None = None) -> None:
        self.delivery_revision = int(self.delivery_revision) + 1
        if reason:
            self.final_result.setdefault("invalidation_reasons", []).append(reason)
        if self.final_result.get("status") not in {None, "not_started"}:
            self.final_result["status"] = "stale"
            self.final_result["confirmed_revision"] = None
        self.touch()

    def set_skill_state(
        self,
        *,
        status: str,
        basis: dict[str, Any] | None = None,
        candidate_batch: dict[str, Any] | None = None,
        bindings: list[dict[str, Any]] | None = None,
        error: str | None = None,
    ) -> None:
        if status not in {"not_started", "candidates_ready", "no_match", "skipped", "selected", "stale"}:
            raise SessionStateError(f"未知的 Skill 状态：{status}")
        current = deepcopy(self.skill_state)
        next_bindings = deepcopy(bindings if bindings is not None else current.get("bindings", []))
        keys: set[tuple[str, str, str]] = set()
        for binding in next_bindings:
            key = (
                str(binding.get("skill_id", "")),
                str(binding.get("key_work_id", "")),
                str(binding.get("usage_mode", "method_adaptation")),
            )
            if not all(key) or key in keys:
                raise SessionStateError("Skill 绑定必须有唯一的 skill、关键工作和使用方式。")
            keys.add(key)
        self.skill_state = {
            "revision": int(current.get("revision", 0)) + 1,
            "status": status,
            "basis": deepcopy(basis if basis is not None else current.get("basis")),
            "candidate_batch": deepcopy(candidate_batch if candidate_batch is not None else current.get("candidate_batch")),
            "bindings": next_bindings,
            "legacy_selection_unresolved": list(current.get("legacy_selection_unresolved", [])),
            "last_error": error,
            "search_state": deepcopy(current.get("search_state", _default_skill_state()["search_state"])),
        }
        self.selected_skills = list(dict.fromkeys(str(row["skill_id"]) for row in next_bindings))
        self._delivery_changed(reason="skill_state_changed")

    def invalidate_delivery(self, reason: str, *, invalidate_selection: bool = False) -> None:
        if invalidate_selection:
            self.skill_state["status"] = "stale"
        self._delivery_changed(reason=reason)

    def _content_changed(self, *, preserve_candidates: bool = False) -> None:
        self.requirement_version += 1
        self.analysis_basis_version = None
        self.confirmed_requirements_version = None
        self.draft_authorization = None
        self.pending_requests.clear()
        if self.m5_state.get("status") not in {"not_started", "stale"}:
            # M5 examples remain historical, but their feedback is tied to
            # the requirement snapshot that produced them.
            self.m5_state["status"] = "stale"
            self.m5_state["candidate_pending"] = False
        if preserve_candidates:
            for proposal in self.pending_proposals:
                proposal["valid_for_version"] = self.requirement_version
        self._invalidate_downstream()
        self._delivery_changed(reason="upstream_changed")

    def _mark_for_review(self, item_ids: set[str]) -> None:
        live_ids = {row["item_id"] for row in self.requirements}
        item_ids.intersection_update(live_ids)
        for item in self.requirements:
            if item["item_id"] in item_ids:
                item["confirmation"] = "review_needed"
        self.pending_review_item_ids = list(
            dict.fromkeys([*self.pending_review_item_ids, *sorted(item_ids)])
        )

    def _drop_candidate_ids(self, proposal_ids: set[str], *, reconcile: bool = True) -> None:
        if not proposal_ids:
            return
        self.pending_proposals = [
            row for row in self.pending_proposals if row.get("proposal_id") not in proposal_ids
        ]
        for conflict in self.open_conflicts:
            conflict["proposal_ids"] = [
                proposal_id
                for proposal_id in conflict.get("proposal_ids", [])
                if proposal_id not in proposal_ids
            ]
        if reconcile:
            self._reconcile_conflicts()

    def _rewrite_active_references(
        self,
        replacement_map: dict[str, str | None],
        *,
        removed_ids: set[str] | None = None,
        resolved_review_ids: set[str] | None = None,
    ) -> set[str]:
        """Rewrite references after a requirement is replaced, edited, or withdrawn.

        References that cannot be redirected remain visible but lose the retired
        dependency; their owning requirement is marked for user review.
        """
        removed = removed_ids or {item_id for item_id, value in replacement_map.items() if value is None}
        resolved = resolved_review_ids or set()
        affected: set[str] = set()
        replacement_ids = {item_id for item_id in replacement_map.values() if item_id is not None}

        def rewrite_dependencies(row: dict[str, Any], *, mark_review: bool = True) -> None:
            dependencies = row.get("depends_on", [])
            rewritten = []
            changed = False
            for dependency in dependencies:
                if dependency not in replacement_map:
                    rewritten.append(dependency)
                    continue
                changed = True
                replacement = replacement_map[dependency]
                if replacement is not None and replacement != row.get("item_id"):
                    rewritten.append(replacement)
            if changed:
                row["depends_on"] = list(dict.fromkeys(rewritten))
                if (
                    mark_review
                    and row.get("item_id") in {item["item_id"] for item in self.requirements}
                    and row.get("item_id") not in replacement_ids
                ):
                    row["confirmation"] = "review_needed"
                    affected.add(row["item_id"])

        for item in self.requirements:
            rewrite_dependencies(item)

        for gap in self.gaps:
            before = list(gap.get("depends_on", []))
            rewrite_dependencies(gap, mark_review=False)
            if before != gap.get("depends_on", []) and any(value in removed for value in before):
                gap["origin"] = "ambiguous"

        for question in self.pending_questions:
            rewrite_dependencies(question, mark_review=False)

        invalid_proposals: set[str] = set()
        for proposal in self.pending_proposals:
            if proposal.get("target_item_id") in replacement_map:
                invalid_proposals.add(proposal["proposal_id"])
                continue
            rewritten = []
            invalid_dependency = False
            for dependency in proposal.get("depends_on", []):
                if dependency not in replacement_map:
                    rewritten.append(dependency)
                    continue
                replacement = replacement_map[dependency]
                if replacement is None:
                    invalid_dependency = True
                    break
                rewritten.append(replacement)
            if invalid_dependency:
                invalid_proposals.add(proposal["proposal_id"])
            else:
                proposal["depends_on"] = list(dict.fromkeys(rewritten))
        self._drop_candidate_ids(invalid_proposals, reconcile=False)

        for conflict in self.open_conflicts:
            existing = []
            for item_id in conflict.get("existing_item_ids", []):
                if item_id in replacement_map:
                    replacement = replacement_map[item_id]
                    if replacement is not None:
                        existing.append(replacement)
                else:
                    existing.append(item_id)
            conflict["existing_item_ids"] = list(dict.fromkeys(existing))

        live_ids = {item["item_id"] for item in self.requirements}
        rewritten_reviews: list[str] = []
        for item_id in self.pending_review_item_ids:
            if item_id in resolved:
                continue
            if item_id in replacement_map:
                replacement = replacement_map[item_id]
                if replacement is None:
                    continue
                rewritten_reviews.append(replacement)
            elif item_id in live_ids:
                rewritten_reviews.append(item_id)
        self.pending_review_item_ids = list(dict.fromkeys(rewritten_reviews))
        self.pending_review_item_ids = [item_id for item_id in self.pending_review_item_ids if item_id in live_ids]
        self._mark_for_review(affected)
        self._reconcile_conflicts()
        return affected

    def _reconcile_conflicts(self) -> None:
        live_ids = {row["item_id"] for row in self.requirements}
        pending_ids = {row["proposal_id"] for row in self.pending_proposals}
        kept: list[dict[str, Any]] = []
        for conflict in self.open_conflicts:
            row = deepcopy(conflict)
            row["existing_item_ids"] = [
                item_id for item_id in row.get("existing_item_ids", []) if item_id in live_ids
            ]
            row["proposal_ids"] = [
                proposal_id for proposal_id in row.get("proposal_ids", []) if proposal_id in pending_ids
            ]
            existing_count = len(set(row["existing_item_ids"]))
            proposal_count = len(set(row["proposal_ids"]))
            if (existing_count >= 2 or proposal_count >= 2 or (existing_count and proposal_count)) and self._conflict_signature(row) not in self.compatible_conflicts:
                kept.append(row)
        self.open_conflicts = kept

    def _conflict_signature(self, conflict: dict[str, Any]) -> list[str]:
        requirements = {row["item_id"]: row for row in self.requirements}
        proposals = {row["proposal_id"]: row for row in self.pending_proposals}
        participants = [requirements[key] for key in conflict.get("existing_item_ids", []) if key in requirements]
        participants += [proposals[key] for key in conflict.get("proposal_ids", []) if key in proposals]
        return sorted(f"{row.get('field', '')}\x1f{row.get('text', '').strip()}" for row in participants)

    def mark_conflict_compatible(self, conflict_id: str) -> None:
        conflict = next((row for row in self.open_conflicts if row.get("conflict_id") == conflict_id), None)
        if conflict is None:
            raise SessionStateError("这项冲突已经变化，请重新查看当前需求。")
        signature = self._conflict_signature(conflict)
        if len(signature) < 2:
            raise SessionStateError("冲突涉及的内容已变化，请重新查看当前需求。")
        if signature not in self.compatible_conflicts:
            self.compatible_conflicts.append(signature)
        self._reconcile_conflicts()
        self.touch()

    def _validate_conflict_continuity(self, returned: list[dict[str, Any]]) -> None:
        live_ids = {row["item_id"] for row in self.requirements}
        returned_by_id: dict[str, dict[str, Any]] = {}
        for conflict in returned:
            conflict_id = conflict.get("conflict_id")
            if conflict_id in returned_by_id:
                raise SessionStateError("模型返回了重复的冲突编号。")
            returned_by_id[conflict_id] = conflict
        for old_conflict in self.open_conflicts:
            conflict_id = old_conflict.get("conflict_id")
            current = returned_by_id.get(conflict_id)
            if current is None:
                raise SessionStateError("历史未解决冲突无依据消失。")
            protected_item_ids = set(old_conflict.get("existing_item_ids", [])) & live_ids
            returned_item_ids = set(current.get("existing_item_ids", []))
            if not protected_item_ids.issubset(returned_item_ids):
                raise SessionStateError("历史未解决冲突遗漏或替换了仍有效的正式需求参与方。")

    def _merge_unresolved_gaps(self, returned: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged = deepcopy(returned)
        returned_ids = {row["gap_id"] for row in returned}
        old_by_id = {row["gap_id"]: row for row in self.gaps}
        for current in merged:
            old = old_by_id.get(current["gap_id"])
            if old and old.get("origin") in {"user_unsure", "user_skipped"}:
                current["origin"] = old["origin"]
        for old in self.gaps:
            if old.get("gap_id") not in returned_ids:
                merged.append(deepcopy(old))
        return merged

    def _validate_model_state_actions(self, result: dict[str, Any], base_version: int) -> None:
        gaps = {row["gap_id"]: row for row in self.gaps}
        answers = {
            row.get("answer_id"): row
            for row in self.question_history
            if row.get("answer_id") and row.get("assessment_status") == "pending"
        }
        sources = {row["source_id"]: row for row in self.sources}
        seen_gaps: set[str] = set()
        seen_answers: set[str] = set()
        for update in result.get("gap_updates", []):
            gap_id = update.get("target_gap_id")
            answer_id = update.get("answer_id")
            answer = answers.get(answer_id)
            if answer is None:
                raise SessionStateError(f"缺口更新引用了不存在或已处理的回答：{answer_id}")
            allowed_gaps = set(answer.get("context_gap_ids", [])) | {answer.get("gap_id")}
            if gap_id not in gaps and not (
                gap_id in allowed_gaps and update.get("action") in {"resolved", "not_applicable"}
            ):
                raise SessionStateError(f"缺口更新引用了不存在的缺口：{gap_id}")
            if gap_id not in allowed_gaps:
                raise SessionStateError("缺口更新的回答与目标缺口不一致。")
            if gap_id in answer.get("assessed_gap_ids", []):
                raise SessionStateError("这条回答已经评估过该缺口。")
            if answer.get("state_version", base_version) > base_version:
                raise SessionStateError("缺口更新引用了晚于本次请求的回答。")
            source_ref = update.get("source_ref", {})
            source_id = source_ref.get("source_id")
            source = sources.get(source_id)
            if (
                source is None
                or source_id != answer.get("answer_source_id")
                or source_ref.get("quote") not in source.get("text", "")
            ):
                raise SessionStateError("缺口更新的回答来源无效。")
            if gap_id in seen_gaps or (answer_id in seen_answers and not answer.get("context_gap_ids")):
                raise SessionStateError("同一缺口或回答不能在一轮中重复更新。")
            seen_gaps.add(gap_id)
            seen_answers.add(answer_id)

        current_source = sources.get(self.current_source_id or "")
        for reopen in result.get("question_reopens", []):
            gap_id = reopen.get("target_gap_id")
            source_ref = reopen.get("source_ref", {})
            if gap_id not in gaps:
                raise SessionStateError(f"问题重开引用了不存在的缺口：{gap_id}")
            if (
                current_source is None
                or current_source.get("role") != "user"
                or source_ref.get("source_id") != self.current_source_id
                or source_ref.get("quote") not in current_source.get("text", "")
            ):
                raise SessionStateError("问题重开没有引用当前有效用户来源。")

    def _apply_gap_updates(
        self,
        updates: list[dict[str, Any]],
        *,
        request_id: str,
        base_version: int,
    ) -> None:
        histories = {row.get("answer_id"): row for row in self.question_history if row.get("answer_id")}
        for update in updates:
            gap_id = update["target_gap_id"]
            action = update["action"]
            if action in {"resolved", "not_applicable"}:
                self.gaps = [row for row in self.gaps if row.get("gap_id") != gap_id]
            else:
                target = next(row for row in self.gaps if row.get("gap_id") == gap_id)
                target["description"] = update["remaining_description"]
                target["origin"] = "ambiguous" if action == "partial" else "user_unsure"
            history = histories[update["answer_id"]]
            if history.get("context_gap_ids"):
                history["assessed_gap_ids"] = list(dict.fromkeys([*history.get("assessed_gap_ids", []), gap_id]))
            if history.get("gap_id") in {None, gap_id}:
                history["assessment_status"] = "applied"
                history["assessment_action"] = action
                history["assessment_request_id"] = request_id
            # Two displayed questions may share one freeform submission. When
            # the model cites that message once per gap, do not leave the
            # equivalent record for the other question stuck as pending.
            group = history.get("submission_group_id")
            if group:
                for other in self.question_history:
                    if (other is not history and other.get("assessment_status") == "pending"
                            and other.get("submission_group_id") == group
                            and other.get("gap_id") == gap_id
                            and other.get("answer_text") == history.get("answer_text")
                            and gap_id in other.get("context_gap_ids", [])
                            and other.get("state_version", 0) <= base_version):
                        other.update(assessment_status="applied", assessment_action=action,
                                     assessment_request_id=request_id,
                                     assessment_source_answer_id=update["answer_id"])
                        other["assessed_gap_ids"] = list(dict.fromkeys([*other.get("assessed_gap_ids", []), gap_id]))
            audit = deepcopy(update)
            audit.update({"request_id": request_id, "base_version": base_version, "applied_at": _now()})
            self.gap_update_history.append(audit)

    def _apply_question_reopens(
        self,
        reopens: list[dict[str, Any]],
        *,
        request_id: str,
        base_version: int,
    ) -> None:
        for reopen in reopens:
            audit = deepcopy(reopen)
            audit.update({"request_id": request_id, "base_version": base_version, "applied_at": _now()})
            self.question_reopen_history.append(audit)

    def _validate_dependencies(self) -> None:
        live_ids = {row["item_id"] for row in self.requirements}
        dangling = [
            (row["item_id"], dependency)
            for row in self.requirements
            for dependency in row.get("depends_on", [])
            if dependency not in live_ids
        ]
        if dangling:
            item_id, dependency = dangling[0]
            raise SessionStateError(f"需求 {item_id} 引用了已失效的前置要求：{dependency}")

    def _validate_active_references(self) -> None:
        live_ids = {row["item_id"] for row in self.requirements}
        for collection_name in ("requirements", "gaps", "pending_questions", "pending_proposals"):
            for row in getattr(self, collection_name):
                dependencies = row.get("depends_on", [])
                dangling = [dependency for dependency in dependencies if dependency not in live_ids]
                if dangling:
                    row_id = row.get("item_id") or row.get("gap_id") or row.get("question_id") or row.get("proposal_id")
                    raise SessionStateError(
                        f"{collection_name} {row_id} 引用了已失效的前置要求：{dangling[0]}"
                    )
        for proposal in self.pending_proposals:
            target = proposal.get("target_item_id")
            if target is not None and target not in live_ids:
                raise SessionStateError(f"候选 {proposal.get('proposal_id')} 引用了已失效的需求：{target}")
        for item_id in self.pending_review_item_ids:
            if item_id not in live_ids:
                raise SessionStateError(f"待复核列表包含已失效的需求：{item_id}")
        for question in self.pending_questions:
            gap_id = question.get("gap_id")
            if gap_id is not None and gap_id not in {gap.get("gap_id") for gap in self.gaps}:
                raise SessionStateError(f"问题 {question.get('question_id')} 引用了不存在的缺口：{gap_id}")
        for conflict in self.open_conflicts:
            if any(item_id not in live_ids for item_id in conflict.get("existing_item_ids", [])):
                raise SessionStateError(f"冲突 {conflict.get('conflict_id')} 引用了已失效的需求")
            pending_ids = {proposal.get("proposal_id") for proposal in self.pending_proposals}
            if any(proposal_id not in pending_ids for proposal_id in conflict.get("proposal_ids", [])):
                raise SessionStateError(f"冲突 {conflict.get('conflict_id')} 引用了不存在的候选")

    def set_task(self, text: str) -> None:
        clean = text.strip()
        if not clean:
            raise SessionStateError("任务内容不能为空。")
        if clean == self.task_text:
            return
        self.task_text = clean
        self._add_source(clean)
        self._mark_for_review({row["item_id"] for row in self.requirements})
        self.pending_proposals = []
        self.pending_questions = []
        self.open_conflicts = []
        self.gaps = []
        self.question_history = []
        self.control["interview_rounds_used"] = 0
        self.control["interview_round_limit"] = 5
        self.gap_update_history = []
        self.question_reopen_history = []
        self.interpretation_history = []
        self.deferred_proposals = []
        self.category_suggestion = None
        self.last_readiness = None
        self.last_next_action = None
        self.last_model_judgment = None
        self.last_assistant_text = "任务已修改，请重新分析并复核现有需求。"
        self._content_changed()

    def choose_category(self, category: str | None) -> None:
        if category == self.selected_category:
            return
        self.selected_category = category
        self._mark_for_review({row["item_id"] for row in self.requirements})
        self.pending_proposals = []
        self.pending_questions = []
        self.category_suggestion = None
        self.last_readiness = None
        self.last_next_action = None
        self.last_model_judgment = None
        self.last_assistant_text = "类别已改变，请重新分析并复核现有需求。"
        self._content_changed()

    def begin_request(self, request_id: str) -> dict[str, Any]:
        if not request_id or request_id in self.pending_requests:
            raise SessionStateError("请求编号为空或重复。")
        snapshot = {
            "request_id": request_id,
            "purpose": "m1",
            "base_version": self.requirement_version,
            "task_text": self.task_text,
            "started_at": _now(),
        }
        self.pending_requests[request_id] = snapshot
        self.touch()
        return deepcopy(snapshot)

    def validate_m2_entry(self) -> None:
        self.validate_unknown_reviews(include_plan=False)
        if not self.task_text.strip():
            raise SessionStateError("任务为空，不能生成初始方案。")
        if not self.requirements:
            raise SessionStateError("没有已确认需求，不能生成初始方案。")
        if self.confirmed_requirements_version != self.requirement_version:
            raise SessionStateError("当前需求版本尚未由用户确认。")
        if self.pending_proposals:
            raise SessionStateError("仍有未处理的需求候选。")
        if self.open_conflicts:
            raise SessionStateError("仍有未处理的需求冲突。")
        if self.pending_review_item_ids or any(
            item.get("confirmation") == "review_needed" for item in self.requirements
        ):
            raise SessionStateError("仍有需求需要用户复核。")
        if self._blocking_gap_snapshot() and not self.current_draft_authorization():
            raise SessionStateError("仍有影响方向的未知，不能生成方案。")
        self._validate_active_references()
        self._validate_dependencies()

    def begin_m2_request(self, request_id: str) -> dict[str, Any]:
        self.validate_m2_entry()
        if not request_id or request_id in self.pending_requests:
            raise SessionStateError("请求编号为空或重复。")
        snapshot = {
            "request_id": request_id,
            "purpose": "m2",
            "task_id": self.task_id,
            "task_text": self.task_text,
            "category": self.selected_category,
            "source_requirements_version": self.requirement_version,
            "confirmed_requirements_version": self.confirmed_requirements_version,
            "base_plan_id": self.plan.get("plan_id"),
            "base_plan_version": int(self.plan.get("plan_version", 0)),
            "connection_version": None,
            "started_at": _now(),
        }
        self.pending_requests[request_id] = snapshot
        self.touch()
        return deepcopy(snapshot)

    def begin_m5_request(
        self,
        request_id: str,
        *,
        criterion_id: str | None,
        criterion_description: str,
        max_chars: int,
    ) -> dict[str, Any]:
        """Register one optional M5 example request against the current snapshot.

        M5 is advisory and may be retried, so a new request supersedes any older
        pending M5 request while retaining its historical examples and feedback.
        The requirement version and task text are captured for stale-response
        checks before a model call is made.
        """
        if not request_id or request_id in self.pending_requests:
            raise SessionStateError("请求编号为空或重复。")
        if not self.task_text.strip():
            raise SessionStateError("任务为空，不能生成示例。")
        # Only one live M5 request is useful.  Removing an older one makes a
        # late response fail the normal pending-request guard in apply_m5.
        self.pending_requests = {
            key: value
            for key, value in self.pending_requests.items()
            if value.get("purpose") != "m5"
        }
        snapshot = {
            "request_id": request_id,
            "purpose": "m5",
            "task_id": self.task_id,
            "task_text": self.task_text,
            "category": self.selected_category,
            "criterion_id": criterion_id,
            "criterion_description": criterion_description,
            "max_chars": max_chars,
            "base_version": self.requirement_version,
            "started_at": _now(),
        }
        self.pending_requests[request_id] = snapshot
        self.m5_state.update(
            {
                "revision": int(self.m5_state.get("revision", 0)) + 1,
                "status": "requesting",
                "request_id": request_id,
                "example_id": None,
                "feedback_id": None,
                "base_version": self.requirement_version,
                "criterion_id": criterion_id,
                "criterion_description": criterion_description,
                "candidate_pending": False,
                "last_error": None,
            }
        )
        self.touch()
        return deepcopy(snapshot)

    def bind_request_connection_version(self, request_id: str, connection_version: int) -> None:
        request = self.pending_requests.get(request_id)
        if request is None:
            raise SessionStateError("找不到待绑定的请求。")
        request["connection_version"] = connection_version
        self.touch()

    def stage_m2_result(
        self,
        request_id: str,
        source_requirements_version: int,
        content: dict[str, Any],
        *,
        prompt_version: str,
        contract_version: str,
    ) -> None:
        request = self.pending_requests.get(request_id)
        if request is None or request.get("purpose") != "m2":
            raise StaleResponseError("方案请求不存在、已处理或已被状态变化作废。")
        self.pending_requests.pop(request_id, None)
        if request.get("task_id") != self.task_id or request.get("task_text") != self.task_text:
            raise StaleResponseError("等待期间任务已变化，已拒绝旧方案。")
        if request.get("category") != self.selected_category:
            raise StaleResponseError("等待期间类别已变化，已拒绝旧方案。")
        if (
            source_requirements_version != request.get("source_requirements_version")
            or source_requirements_version != self.requirement_version
            or self.confirmed_requirements_version != self.requirement_version
        ):
            raise StaleResponseError("返回基于旧需求版本，已拒绝接收。")
        if (
            request.get("base_plan_id") != self.plan.get("plan_id")
            or request.get("base_plan_version") != int(self.plan.get("plan_version", 0))
        ):
            raise StaleResponseError("等待期间方案已被修改，已拒绝旧返回。")
        now = _now()
        if self.plan.get("content") is not None and self.plan.get("status") != "not_started":
            archived = deepcopy(self.plan)
            archived["archived_at"] = now
            archived["archived_reason"] = "regenerated"
            self.plan_archive.append(archived)
        self.plan = {
            "plan_id": f"plan-{uuid4().hex}",
            "plan_version": 1,
            "status": "draft",
            "content": deepcopy(content),
            "original_content": deepcopy(content),
            "source_requirements_version": self.requirement_version,
            "confirmed_plan_version": None,
            "prompt_version": prompt_version,
            "contract_version": contract_version,
            "created_at": now,
            "updated_at": now,
            "modified": False,
            "pending_key_work_review_ids": [
                row["key_work_id"] for row in content.get("key_work", [])
            ],
            "reviewed_key_work_ids": [],
            "source_snapshot": {
                "task_text": self.task_text,
                "selected_category": self.selected_category,
                "requirements": deepcopy(self.requirements),
                "unresolved_items": deepcopy(
                    self.plan_unresolved_items()
                ),
                "draft_authorization": self.current_draft_authorization(),
            },
            "generation_request_id": request_id,
        }
        logging.getLogger(__name__).info("Plan draft staged; task=%s request=%s downstream_unknowns=%s; no automatic post-plan interview",
                                        self.task_id, request_id, len(content.get("unresolved_items", [])))
        # A newly staged M2 draft is current; only downstream delivery state
        # becomes stale. Do not mark the plan itself stale while creating it.
        if self.final_result.get("status") not in {None, "not_started"}:
            self.final_result["status"] = "stale"
            self.final_result["confirmed_revision"] = None
        if self.skill_state.get("status") not in {None, "not_started"}:
            self.skill_state["status"] = "stale"
        self.delivery_revision = int(self.delivery_revision) + 1
        self.touch()
        self.touch()

    def _require_editable_plan(self) -> dict[str, Any]:
        if self.plan.get("status") not in {"draft", "confirmed"} or not isinstance(
            self.plan.get("content"), dict
        ):
            raise SessionStateError("当前没有可编辑的有效方案草稿。")
        if self.plan.get("source_requirements_version") != self.requirement_version:
            raise SessionStateError("方案来源需求已经变化，请基于新需求重新生成。")
        return self.plan["content"]

    def _plan_changed(self, *, review_all_key_work: bool) -> None:
        self.pending_questions = [q for q in self.pending_questions if q.get("clarification_scope") != "plan"]
        content = self.plan["content"]
        self.plan["plan_version"] = int(self.plan.get("plan_version", 0)) + 1
        self.plan["status"] = "draft"
        self.plan["confirmed_plan_version"] = None
        self.plan["modified"] = True
        self.plan["updated_at"] = _now()
        key_ids = [row["key_work_id"] for row in content.get("key_work", [])]
        current_pending = [
            value for value in self.plan.get("pending_key_work_review_ids", []) if value in key_ids
        ]
        if review_all_key_work:
            current_pending = key_ids
            self.plan["reviewed_key_work_ids"] = []
        else:
            self.plan["reviewed_key_work_ids"] = [
                value for value in self.plan.get("reviewed_key_work_ids", []) if value in key_ids
            ]
        self.plan["pending_key_work_review_ids"] = list(dict.fromkeys(current_pending))
        self.pending_requests = {
            key: value for key, value in self.pending_requests.items() if value.get("purpose") != "m2"
        }
        self._delivery_changed(reason="plan_changed")
        self.touch()

    def edit_plan_goal(self, summary: str) -> None:
        clean = summary.strip()
        if not clean:
            raise SessionStateError("方案目标不能为空。")
        content = self._require_editable_plan()
        if content["goal"]["summary"] == clean:
            return
        content["goal"]["summary"] = clean
        self._plan_changed(review_all_key_work=True)

    def edit_plan_goal_details(self, *, audience: str, scope: str) -> None:
        clean_audience, clean_scope = audience.strip(), scope.strip()
        if not clean_audience or not clean_scope:
            raise SessionStateError("方案受众和范围不能为空。")
        content = self._require_editable_plan()
        goal = content["goal"]
        if goal["audience"] == clean_audience and goal["scope"] == clean_scope:
            return
        goal["audience"] = clean_audience
        goal["scope"] = clean_scope
        self._plan_changed(review_all_key_work=True)

    def edit_plan_section(
        self,
        section_type: str,
        entity_id: str,
        updates: dict[str, Any],
    ) -> None:
        specs = {
            "deliverable": ("deliverables", "deliverable_id", {"name", "description"}),
            "criterion": ("completion_criteria", "criterion_id", {"text"}),
            "unresolved": (
                "unresolved_items",
                "unresolved_id",
                {"description", "impact", "continuable_work", "confirm_by"},
            ),
            "suggestion": ("suggestions", "suggestion_id", {"text", "reason"}),
            "key_work": (
                "key_work",
                "key_work_id",
                {
                    "title",
                    "goal",
                    "inputs",
                    "outputs",
                    "checkpoints",
                    "step_ids",
                    "requirement_ids",
                    "depends_on_key_work_ids",
                },
            ),
        }
        spec = specs.get(section_type)
        if spec is None:
            raise SessionStateError("不支持编辑该方案栏目。")
        collection_name, id_key, allowed_fields = spec
        if not updates or set(updates) - allowed_fields:
            raise SessionStateError("方案栏目修改字段无效。")
        content = self._require_editable_plan()
        working = deepcopy(content)
        row = next(
            (item for item in working[collection_name] if item[id_key] == entity_id), None
        )
        if row is None:
            raise SessionStateError(f"找不到方案栏目：{entity_id}")
        cleaned: dict[str, Any] = {}
        for key, value in updates.items():
            if key in {
                "inputs",
                "outputs",
                "checkpoints",
                "step_ids",
                "requirement_ids",
                "depends_on_key_work_ids",
            }:
                if not isinstance(value, list):
                    raise SessionStateError("方案栏目列表字段格式无效。")
                cleaned[key] = list(
                    dict.fromkeys(
                        item.strip() if isinstance(item, str) else item
                        for item in value
                        if not isinstance(item, str) or item.strip()
                    )
                )
            else:
                if not isinstance(value, str) or not value.strip():
                    raise SessionStateError("方案栏目内容不能为空。")
                cleaned[key] = value.strip()
        if all(row[key] == value for key, value in cleaned.items()):
            return
        row.update(cleaned)
        try:
            from .m2 import validate_plan_content

            validate_plan_content(working, self._plan_source_payload(include_skipped=True))
        except Exception as exc:
            raise SessionStateError(str(exc)) from exc
        self.plan["content"] = working
        affected = (
            {entity_id}
            if section_type == "key_work"
            else {item["key_work_id"] for item in working.get("key_work", [])}
        )
        self._plan_changed(review_all_key_work=False)
        self.plan["pending_key_work_review_ids"] = list(
            dict.fromkeys([*self.plan["pending_key_work_review_ids"], *sorted(affected)])
        )
        self.plan["reviewed_key_work_ids"] = [
            value for value in self.plan["reviewed_key_work_ids"] if value not in affected
        ]

    def _plan_source_payload(self, *, include_skipped: bool = False) -> dict[str, Any]:
        from .clarification import without_skipped_unknowns
        source = self.plan.get("source_snapshot") or {}
        unknowns = source.get("unresolved_items", [])
        # Validate a preserved historical plan against its original snapshot;
        # delivery uses the filtered projection instead.
        if not include_skipped:
            unknowns = without_skipped_unknowns(self, unknowns)
        return {
            "requirements": source.get("requirements", []),
            "unresolved_items": [
                {**deepcopy(row), "unresolved_id": row["gap_id"]}
                for row in unknowns
            ],
        }

    def plan_delivery_unknowns(self) -> list[dict[str, Any]]:
        """Union source and planning unknowns without changing the confirmed plan."""
        from .m2 import merge_plan_unknowns
        from .clarification import without_skipped_unknowns

        rows = without_skipped_unknowns(self, (self.plan.get("content") or {}).get("unresolved_items", []))
        # Older delivery snapshots used unknown_id and had no M2 source link.
        for index, row in enumerate(rows, 1):
            row.setdefault("unresolved_id", row.get("unknown_id") or f"legacy-unknown-{index}")
            row.setdefault("source_gap_id", None)
        payload = self._plan_source_payload()
        if not self.plan.get("source_snapshot"):
            payload = {"requirements": self.requirements, "unresolved_items": [
                {**deepcopy(row), "unresolved_id": row["gap_id"]} for row in self.plan_unresolved_items()
            ]}
        return without_skipped_unknowns(self, merge_plan_unknowns(rows, payload))

    def edit_plan_step(
        self,
        step_id: str,
        *,
        title: str,
        purpose: str,
        inputs: list[str] | None = None,
        actions: list[str] | None = None,
        outputs: list[str] | None = None,
        completion_criteria: list[str] | None = None,
        depends_on_step_ids: list[str] | None = None,
        requirement_ids: list[str] | None = None,
    ) -> None:
        content = self._require_editable_plan()
        working = deepcopy(content)
        step = next((row for row in working["steps"] if row["step_id"] == step_id), None)
        if step is None:
            raise SessionStateError(f"找不到方案步骤：{step_id}")
        clean_title, clean_purpose = title.strip(), purpose.strip()
        if not clean_title or not clean_purpose:
            raise SessionStateError("步骤标题和目的不能为空。")

        def clean_list(values: list[str] | None, current: list[str]) -> list[str]:
            if values is None:
                return deepcopy(current)
            return list(dict.fromkeys(value.strip() for value in values if value.strip()))

        updates = {
            "title": clean_title,
            "purpose": clean_purpose,
            "inputs": clean_list(inputs, step.get("inputs", [])),
            "actions": clean_list(actions, step.get("actions", [])),
            "outputs": clean_list(outputs, step.get("outputs", [])),
            "completion_criteria": clean_list(
                completion_criteria, step.get("completion_criteria", [])
            ),
            "depends_on_step_ids": clean_list(
                depends_on_step_ids, step.get("depends_on_step_ids", [])
            ),
            "requirement_ids": clean_list(requirement_ids, step.get("requirement_ids", [])),
        }
        if all(step.get(key) == value for key, value in updates.items()):
            return
        step.update(updates)
        try:
            from .m2 import validate_plan_content

            validate_plan_content(working, self._plan_source_payload(include_skipped=True))
        except Exception as exc:
            raise SessionStateError(str(exc)) from exc
        self.plan["content"] = working
        affected = {
            row["key_work_id"]
            for row in working.get("key_work", [])
            if step_id in row.get("step_ids", [])
        }
        self._plan_changed(review_all_key_work=False)
        self.plan["pending_key_work_review_ids"] = list(
            dict.fromkeys([*self.plan["pending_key_work_review_ids"], *sorted(affected)])
        )
        self.plan["reviewed_key_work_ids"] = [
            value for value in self.plan["reviewed_key_work_ids"] if value not in affected
        ]

    def add_plan_step(
        self,
        title: str,
        purpose: str,
        *,
        inputs: list[str] | None = None,
        actions: list[str] | None = None,
        outputs: list[str] | None = None,
        completion_criteria: list[str] | None = None,
        depends_on_step_ids: list[str] | None = None,
        requirement_ids: list[str] | None = None,
    ) -> str:
        content = self._require_editable_plan()
        clean_title, clean_purpose = title.strip(), purpose.strip()
        if not clean_title or not clean_purpose:
            raise SessionStateError("步骤标题和目的不能为空。")
        step_id = self._next_id("s", content["steps"], "step_id")
        working = deepcopy(content)
        working["steps"].append(
            {
                "step_id": step_id,
                "order": len(working["steps"]) + 1,
                "title": clean_title,
                "purpose": clean_purpose,
                "inputs": list(dict.fromkeys(value.strip() for value in (inputs or []) if value.strip())),
                "actions": list(dict.fromkeys(value.strip() for value in (actions or []) if value.strip())),
                "outputs": list(dict.fromkeys(value.strip() for value in (outputs or []) if value.strip())),
                "completion_criteria": list(
                    dict.fromkeys(value.strip() for value in (completion_criteria or []) if value.strip())
                ),
                "depends_on_step_ids": list(dict.fromkeys(depends_on_step_ids or [])),
                "requirement_ids": list(dict.fromkeys(requirement_ids or [])),
            }
        )
        try:
            from .m2 import validate_plan_content

            validate_plan_content(working, self._plan_source_payload(include_skipped=True))
        except Exception as exc:
            raise SessionStateError(str(exc)) from exc
        self.plan["content"] = working
        self._plan_changed(review_all_key_work=False)
        return step_id

    def delete_plan_step(self, step_id: str) -> None:
        content = self._require_editable_plan()
        if len(content["steps"]) <= 1:
            raise SessionStateError("方案至少需要保留一个步骤。")
        if not any(row["step_id"] == step_id for row in content["steps"]):
            raise SessionStateError(f"找不到方案步骤：{step_id}")
        references = []
        for collection, key in (
            (content["requirement_coverage"], "step_ids"),
            (content["deliverables"], "step_ids"),
            (content["key_work"], "step_ids"),
        ):
            references.extend(row for row in collection if step_id in row.get(key, []))
        references.extend(
            row for row in content["steps"] if step_id in row.get("depends_on_step_ids", [])
        )
        if references:
            raise SessionStateError("该步骤仍被覆盖关系、交付物、关键工作或其他步骤引用。")
        content["steps"] = [row for row in content["steps"] if row["step_id"] != step_id]
        for index, row in enumerate(sorted(content["steps"], key=lambda item: item["order"]), 1):
            row["order"] = index
        self._plan_changed(review_all_key_work=False)

    def move_plan_step(self, step_id: str, offset: int) -> None:
        content = self._require_editable_plan()
        ordered = sorted(content["steps"], key=lambda row: row["order"])
        index = next((i for i, row in enumerate(ordered) if row["step_id"] == step_id), None)
        if index is None:
            raise SessionStateError(f"找不到方案步骤：{step_id}")
        target = index + offset
        if target < 0 or target >= len(ordered):
            return
        ordered[index], ordered[target] = ordered[target], ordered[index]
        for order, row in enumerate(ordered, 1):
            row["order"] = order
        content["steps"] = ordered
        self._plan_changed(review_all_key_work=True)

    def mark_key_work_reviewed(self, key_work_ids: list[str]) -> None:
        self._require_editable_plan()
        if not key_work_ids or len(key_work_ids) != len(set(key_work_ids)):
            raise SessionStateError("请选择不重复的待复核关键工作。")
        pending = set(self.plan.get("pending_key_work_review_ids", []))
        if any(value not in pending for value in key_work_ids):
            raise SessionStateError("选中内容不在待复核关键工作列表中。")
        selected = set(key_work_ids)
        self.plan["pending_key_work_review_ids"] = [
            value for value in self.plan["pending_key_work_review_ids"] if value not in selected
        ]
        self.plan["reviewed_key_work_ids"] = list(
            dict.fromkeys([*self.plan.get("reviewed_key_work_ids", []), *key_work_ids])
        )
        self.plan["updated_at"] = _now()
        self.touch()

    def validate_plan(self) -> None:
        content = self._require_editable_plan()
        from .m2 import validate_plan_content

        validate_plan_content(content, self._plan_source_payload(include_skipped=True))

    def _validate_loaded_plan(self) -> None:
        status = self.plan.get("status")
        if status not in {"not_started", "draft", "confirmed", "stale"}:
            raise SessionStateError(f"会话包含未知的方案状态：{status}")
        content = self.plan.get("content")
        if content is None:
            if status != "not_started":
                raise SessionStateError("会话方案状态与内容不一致。")
            return
        if not isinstance(content, dict):
            # Preserve legacy placeholder plans as stale history without treating them as M2 output.
            self.plan["status"] = "stale"
            self.plan["confirmed_plan_version"] = None
            return
        source = self.plan.get("source_snapshot")
        if not isinstance(source, dict):
            raise SessionStateError("方案缺少可核对的来源需求快照。")
        try:
            from .m2 import validate_plan_content

            validate_plan_content(
                content,
                {
                    "requirements": source.get("requirements", []),
                    "unresolved_items": [
                        {"unresolved_id": row["gap_id"]}
                        for row in source.get("unresolved_items", [])
                    ],
                },
            )
        except Exception as exc:
            raise SessionStateError(f"保存的方案结构或引用无效：{exc}") from exc
        key_ids = {row["key_work_id"] for row in content.get("key_work", [])}
        if not set(self.plan.get("pending_key_work_review_ids", [])).issubset(key_ids):
            raise SessionStateError("保存的关键工作复核状态包含悬空引用。")
        if not set(self.plan.get("reviewed_key_work_ids", [])).issubset(key_ids):
            raise SessionStateError("保存的关键工作已复核状态包含悬空引用。")
        if (
            self.plan.get("source_requirements_version") != self.requirement_version
            or self.confirmed_requirements_version != self.requirement_version
        ):
            self.plan["status"] = "stale"
            self.plan["confirmed_plan_version"] = None
        elif status == "confirmed" and self.plan.get("confirmed_plan_version") != self.plan.get(
            "plan_version"
        ):
            raise SessionStateError("保存的方案确认版本与当前方案版本不一致。")
        elif status == "confirmed":
            try:
                from .m2 import validate_plan_confirmable

                validate_plan_confirmable(content)
            except Exception as exc:
                self.plan["status"] = "draft"
                self.plan["confirmed_plan_version"] = None
                self.plan["confirmation_review_reason"] = f"旧方案不满足当前确认完整性规则：{exc}"
                key_ids = [row["key_work_id"] for row in content.get("key_work", [])]
                self.plan["pending_key_work_review_ids"] = key_ids
                self.plan["reviewed_key_work_ids"] = []

    def confirm_plan(self) -> int:
        self.validate_unknown_reviews()
        self.validate_m2_entry()
        self.validate_plan()
        try:
            from .m2 import validate_plan_confirmable

            validate_plan_confirmable(self.plan["content"])
        except Exception as exc:
            raise SessionStateError(str(exc)) from exc
        if self.plan.get("status") == "stale":
            raise SessionStateError("方案来源需求已变化，请重新生成。")
        if self.plan.get("source_requirements_version") != self.requirement_version:
            raise SessionStateError("方案来源需求版本与当前确认版本不一致。")
        if self.plan.get("pending_key_work_review_ids"):
            raise SessionStateError("仍有关键工作需要用户复核。")
        version = int(self.plan["plan_version"])
        self.plan["status"] = "confirmed"
        self.plan["confirmed_plan_version"] = version
        self.plan["updated_at"] = _now()
        self.touch()
        return version

    def plan_preview(self) -> dict[str, Any]:
        """Snapshot the complete plan shown together with its key work."""
        return deepcopy({
            "task_id": self.task_id,
            "requirement_version": self.requirement_version,
            "confirmed_requirements_version": self.confirmed_requirements_version,
            "plan": self.plan,
            "clarification_questions": self.questions_for_review(),
            "question_history": self.question_history,
        })

    def confirm_plan_preview(self, preview: dict[str, Any]) -> int:
        if preview != self.plan_preview():
            raise SessionStateError("方案已变化，请先查看更新后的方案预览。")
        working = deepcopy(self)
        pending = working.plan.get("pending_key_work_review_ids", [])
        if pending:
            working.mark_key_work_reviewed(list(pending))
        version = working.confirm_plan()
        self.__dict__.update(deepcopy(working.__dict__))
        return version

    def stage_m1_result(self, request_id: str, base_version: int, result: dict[str, Any]) -> None:
        # Keep the old candidate draft while applying one new analysis atomically.
        # A model response can suggest changes; it cannot accept previous work.
        working = deepcopy(self)
        try:
            working._stage_m1_result_in_place(request_id, base_version, result)
        except Exception:
            request = self.pending_requests.get(request_id)
            if request is not None and request.get("purpose", "m1") == "m1":
                self.pending_requests.pop(request_id, None)
            raise
        self.__dict__.update(deepcopy(working.__dict__))

    def _stage_m1_result_in_place(self, request_id: str, base_version: int, result: dict[str, Any]) -> None:
        from .interview import close_question_batch, rounds_used, round_limit
        used = rounds_used(self)
        limit = round_limit(self)
        has_new_answers = any(q.get("assessment_status") == "pending" and q.get("disposition") == "answered"
                              for q in self.question_history)
        existing_batch = bool(self.pending_questions)
        result = close_question_batch(result, exhausted=used >= limit)
        request = self.pending_requests.get(request_id)
        if request is None or request.get("purpose", "m1") != "m1":
            raise StaleResponseError("请求不存在、已处理或已被状态变化作废。")
        self.pending_requests.pop(request_id, None)
        if base_version != request["base_version"] or base_version != self.requirement_version:
            raise StaleResponseError("返回基于旧需求版本，已拒绝接收。")
        if request["task_text"] != self.task_text:
            raise StaleResponseError("等待期间任务文本已变化，已拒绝旧返回。")
        if result.get("status") == "input_error":
            raise SessionStateError(result.get("error", {}).get("message", "模型未能处理本轮输入。"))
        self._validate_model_state_actions(result, base_version)
        self._validate_conflict_continuity(result.get("conflicts", []))
        self.category_suggestion = deepcopy(result.get("category"))
        proposal_remap: dict[str, str] = {}
        semantic_keys = ("operation", "target_item_id", "field", "text", "kind", "strength", "scope", "depends_on", "interpretation_for")
        for proposal in deepcopy(result.get("proposals", [])):
            duplicate = next((row for row in self.pending_proposals if all(row.get(key) == proposal.get(key) for key in semantic_keys)), None)
            original_id = proposal["proposal_id"]
            if duplicate is not None:
                proposal_remap[original_id] = duplicate["proposal_id"]
                continue
            taken = {row["proposal_id"] for row in self.pending_proposals}
            new_id, suffix = original_id, 2
            while new_id in taken:
                new_id = f"{original_id}-next{suffix}"
                suffix += 1
            proposal["proposal_id"] = new_id
            proposal_remap[original_id] = new_id
            proposal["source_request_id"] = request_id
            proposal["source_base_version"] = base_version
            proposal["valid_for_version"] = self.requirement_version
            self.pending_proposals.append(proposal)
        previous_conflicts = {row["conflict_id"]: row for row in self.open_conflicts}
        self.open_conflicts = deepcopy(result.get("conflicts", []))
        for conflict in self.open_conflicts:
            prior = previous_conflicts.get(conflict["conflict_id"], {})
            conflict["proposal_ids"] = list(dict.fromkeys([
                *prior.get("proposal_ids", []),
                *[proposal_remap.get(value, value) for value in conflict.get("proposal_ids", [])],
            ]))
        review_ids = list(result.get("review_item_ids", []))
        live_ids = {row["item_id"] for row in self.requirements}
        if any(item_id not in live_ids for item_id in review_ids):
            raise SessionStateError("模型返回了不存在的待复核需求。")
        program_review_ids = [
            item["item_id"]
            for item in self.requirements
            if item.get("confirmation") == "review_needed"
        ]
        self.pending_review_item_ids = [
            item_id
            for item_id in dict.fromkeys([*program_review_ids, *self.pending_review_item_ids, *review_ids])
            if item_id in live_ids
        ]
        for item in self.requirements:
            if item["item_id"] in self.pending_review_item_ids:
                item["confirmation"] = "review_needed"
        self.gaps = self._merge_unresolved_gaps(result.get("gaps", []))
        self._apply_gap_updates(
            result.get("gap_updates", []), request_id=request_id, base_version=base_version
        )
        closed_gap_ids = {
            row["target_gap_id"] for row in result.get("gap_updates", [])
            if row.get("action") in {"resolved", "not_applicable"}
        }
        superseded_guesses = [
            row for row in self.pending_proposals
            if (row.get("interpretation_for") or {}).get("gap_id") in closed_gap_ids
        ]
        for row in superseded_guesses:
            archived = deepcopy(row)
            archived["deferred_reason"] = "gap_resolved_by_answer"
            self.deferred_proposals.append(archived)
        self._drop_candidate_ids({row["proposal_id"] for row in superseded_guesses})
        self._apply_question_reopens(
            result.get("question_reopens", []), request_id=request_id, base_version=base_version
        )
        for answer in self.question_history:
            if answer.get("assessment_status") == "pending" and answer.get("gap_id") is None and answer.get("state_version", 0) <= base_version:
                answer["assessment_status"] = "applied"
                answer["assessment_action"] = "supplement_processed"
                answer["assessment_request_id"] = request_id
        self.pending_questions = deepcopy(result.get("questions", []))
        self.last_readiness = deepcopy(result.get("readiness"))
        self.last_next_action = result.get("next_action")
        self.last_model_judgment = deepcopy(result.get("model_judgment"))
        self.last_assistant_text = result.get("assistant_text", "")
        self.analysis_basis_version = self.requirement_version
        batch = self.questions_for_review(include_plan=False)
        logging.getLogger(__name__).info(
            "Interview readiness assessed; task=%s round=%s/%s assessment=%s continue_interview=%s next_action=%s questions=%s",
            self.task_id, used, limit, (self.last_model_judgment or {}).get("answer_assessment"),
            (self.last_model_judgment or {}).get("continue_interview"), self.last_next_action, len(batch))
        if not batch and self.last_next_action == "review_requirements":
            logging.getLogger(__name__).info("Interview complete: sufficient information; task=%s rounds_used=%s limit=%s; awaiting user requirements confirmation",
                                            self.task_id, used, limit)
        if used < limit and batch and (has_new_answers or not existing_batch):
            # Freeze the entire visible batch before advancing the counter,
            # including locally derived questions in the fifth round.
            self.pending_questions = batch
            self.control["interview_rounds_used"] = used + 1
            logging.getLogger(__name__).info("Interview question batch prepared; task=%s round=%s/%s questions=%s",
                                            self.task_id, used + 1, limit, len(batch))
        # Legacy question counters are retained in saved sessions and in the
        # input contract for compatibility. The new batch counter bounds the
        # interview without making unresolved information count as confirmed.
        self._reconcile_conflicts()
        self.touch()

    def accept_proposals(self, proposal_ids: list[str]) -> list[dict[str, Any]]:
        if not proposal_ids or len(proposal_ids) != len(set(proposal_ids)):
            raise SessionStateError("待接受的候选为空或包含重复编号。")
        wanted = set(proposal_ids)
        selected = [row for row in self.pending_proposals if row.get("proposal_id") in wanted]
        if len(selected) != len(wanted):
            raise SessionStateError("待接受的候选不存在或已经处理。")
        live_ids = {row["item_id"] for row in self.requirements}
        mutation_targets: list[str] = []
        for proposal in selected:
            if proposal.get("interpretation_for"):
                raise SessionStateError("请先单独核对这段 AI 推测的解释，再选择是否采用。")
            valid_for_version = proposal.get("valid_for_version", self.requirement_version)
            if valid_for_version != self.requirement_version:
                raise SessionStateError("候选基于旧需求版本，请重新分析。")
            operation = proposal["operation"]
            target = proposal.get("target_item_id")
            if operation == "new":
                if target is not None:
                    raise SessionStateError("新增候选不能引用旧需求。")
            else:
                if target not in live_ids:
                    raise SessionStateError(f"候选引用了不存在的需求：{target}")
                mutation_targets.append(target)
            missing_dependency = next(
                (dependency for dependency in proposal.get("depends_on", []) if dependency not in live_ids),
                None,
            )
            if missing_dependency:
                raise SessionStateError(f"候选依赖了不存在的需求：{missing_dependency}")
        if len(mutation_targets) != len(set(mutation_targets)):
            raise SessionStateError("同一批候选不能重复修改同一条需求。")

        working = deepcopy(self)
        created = working._accept_proposals_in_place(proposal_ids)
        runtime_key = self.runtime_api_key
        self.__dict__.update(deepcopy(working.__dict__))
        self.runtime_api_key = runtime_key
        return created

    def _accept_proposals_in_place(self, proposal_ids: list[str]) -> list[dict[str, Any]]:
        wanted = set(proposal_ids)
        selected = [row for row in self.pending_proposals if row["proposal_id"] in wanted]
        created: list[dict[str, Any]] = []
        accepted_ids: set[str] = set()
        result_by_proposal: dict[str, dict[str, Any] | None] = {}
        replacement_map: dict[str, str | None] = {}
        # M1 extraction was already assessed in its response. M5 feedback is
        # new user input that M1 has not yet seen and needs a fresh assessment.
        analysis_was_current = (
            self.analysis_basis_version == self.requirement_version
            and not any(row.get("source") == "m5_feedback" for row in selected)
        )
        for proposal in selected:
            operation = proposal["operation"]
            target = proposal.get("target_item_id")
            if operation != "new":
                old = next((row for row in self.requirements if row["item_id"] == target), None)
                if old is None:  # Defensive: public method prevalidates before this working-copy mutation.
                    raise SessionStateError(f"候选引用了不存在的需求：{target}")
                self.requirements.remove(old)
                archived = deepcopy(old)
                archived["retired_at"] = _now()
                archived["retired_by"] = operation
                self.requirement_archive.append(archived)
                replacement_map[target] = None
            if operation != "withdraw":
                item_id = self._next_id("r", self.requirements + self.requirement_archive, "item_id")
                item = {
                    "item_id": item_id,
                    "field": proposal["field"],
                    "text": proposal["text"],
                    "kind": proposal["kind"],
                    "strength": proposal["strength"],
                    "scope": proposal["scope"],
                    "source_refs": deepcopy(proposal.get("source_refs", [])),
                    "depends_on": deepcopy(proposal.get("depends_on", [])),
                    "confirmation": "pending",
                }
                if proposal.get("source") == "m5_feedback":
                    feedback = next(
                        (row for row in self.m5_feedback
                         if (row.get("candidate") or {}).get("candidate_id") == proposal["proposal_id"]
                         and row.get("task_id") == self.task_id
                         and row.get("example_id") == proposal.get("source_example_id")),
                        None,
                    )
                    if feedback is None:
                        raise SessionStateError("M5反馈候选缺少可核对的用户操作来源。")
                    example = next(
                        (row for row in self.m5_examples if row.get("example_id") == feedback["example_id"]),
                        None,
                    )
                    if example is None:
                        raise SessionStateError("M5反馈候选缺少对应示例来源。")
                    # Preserve the user's own feedback, never the model's example
                    # assumptions. This runs on the transaction's working copy.
                    source_text = str(feedback.get("feedback_text") or "").strip()
                    if not source_text:
                        choice = "A" if feedback.get("disposition") in {"a", "option_a"} else "B"
                        source_text = (
                            f"用户操作记录：对‘{example.get('criterion_description', '当前评价标准')}’"
                            f"选择示例{choice}，未填写具体反馈；具体程度待确认。"
                        )
                    source_id = self._add_source(source_text)
                    item["source_refs"] = [{"source_id": source_id, "quote": source_text}]
                    feedback["accepted_item_id"] = item_id
                self.requirements.append(item)
                created.append(deepcopy(item))
                result_by_proposal[proposal["proposal_id"]] = item
                if target is not None:
                    replacement_map[target] = item_id
            else:
                result_by_proposal[proposal["proposal_id"]] = None
            accepted_ids.add(proposal["proposal_id"])

        updated_conflicts: list[dict[str, Any]] = []
        for conflict in self.open_conflicts:
            row = deepcopy(conflict)
            existing = list(row.get("existing_item_ids", []))
            pending = list(row.get("proposal_ids", []))
            for proposal in selected:
                proposal_id = proposal["proposal_id"]
                if proposal_id not in pending:
                    continue
                pending = [value for value in pending if value != proposal_id]
                target = proposal.get("target_item_id")
                if target is not None:
                    existing = [value for value in existing if value != target]
                created_item = result_by_proposal[proposal_id]
                if proposal["operation"] == "new" and created_item is not None:
                    existing.append(created_item["item_id"])
                elif created_item is not None and (existing or pending):
                    existing.append(created_item["item_id"])
            row["existing_item_ids"] = list(dict.fromkeys(existing))
            row["proposal_ids"] = list(dict.fromkeys(pending))
            updated_conflicts.append(row)
        self.open_conflicts = updated_conflicts
        self.pending_proposals = [row for row in self.pending_proposals if row["proposal_id"] not in accepted_ids]
        self._rewrite_active_references(
            replacement_map,
            resolved_review_ids=set(replacement_map),
        )
        self._content_changed(preserve_candidates=True)
        if analysis_was_current:
            self.analysis_basis_version = self.requirement_version
        self._reconcile_conflicts()
        return created

    def dismiss_proposals(self) -> None:
        dismissed_ids = {row["proposal_id"] for row in self.pending_proposals}
        self._drop_candidate_ids(dismissed_ids)
        self.touch()

    def edit_proposal(self, proposal_id: str, text: str) -> dict[str, Any]:
        """Keep an explicit candidate edit local and still pending confirmation."""
        clean = text.strip()
        if not clean:
            raise SessionStateError("需求内容不能为空。")
        row = next((p for p in self.pending_proposals if p["proposal_id"] == proposal_id), None)
        if row is None or row.get("valid_for_version", self.requirement_version) != self.requirement_version:
            raise SessionStateError("这条候选已变化，请查看当前内容再修改。")
        if clean == row["text"]:
            return deepcopy(row)
        analysis_was_current = self.analysis_basis_version == self.requirement_version
        archived = deepcopy(row)
        archived["deferred_reason"] = "user_corrected_candidate"
        self.deferred_proposals.append(archived)
        source_id = self._add_source(clean)
        row["text"] = clean
        row["source_refs"] = [{"source_id": source_id, "quote": clean}]
        if row.get("kind") != "pending_interpretation":
            row["kind"] = "user_decision"
        self._content_changed(preserve_candidates=True)
        if analysis_was_current:
            # This is the user's explicit replacement text, not a new answer
            # for the model to interpret. Confirmation still checks questions,
            # conflicts and the exact displayed preview.
            self.analysis_basis_version = self.requirement_version
        logging.getLogger(__name__).info("Candidate edited locally; task=%s proposal=%s version=%s; model_request=False",
                                        self.task_id, proposal_id, self.requirement_version)
        return deepcopy(row)

    def edit_requirement(self, item_id: str, text: str) -> dict[str, Any]:
        clean = text.strip()
        if not clean:
            raise SessionStateError("需求内容不能为空。")
        old = next((row for row in self.requirements if row["item_id"] == item_id), None)
        if old is None:
            raise SessionStateError(f"找不到需求：{item_id}")
        self.requirements.remove(old)
        archived = deepcopy(old)
        archived["retired_at"] = _now()
        archived["retired_by"] = "manual_edit"
        self.requirement_archive.append(archived)
        new_item = deepcopy(old)
        new_item["item_id"] = self._next_id("r", self.requirements + self.requirement_archive, "item_id")
        new_item["text"] = clean
        source_id = self._add_source(clean)
        new_item["source_refs"] = [{"source_id": source_id, "quote": clean}]
        new_item["kind"] = "user_decision"
        new_item["confirmation"] = "pending"
        self.requirements.append(new_item)
        self._rewrite_active_references({item_id: new_item["item_id"]}, resolved_review_ids={item_id})
        new_item["confirmation"] = "pending"
        self._content_changed(preserve_candidates=True)
        self._reconcile_conflicts()
        return deepcopy(new_item)

    def withdraw_requirement(self, item_id: str) -> None:
        old = next((row for row in self.requirements if row["item_id"] == item_id), None)
        if old is None:
            raise SessionStateError(f"找不到需求：{item_id}")
        self.requirements.remove(old)
        archived = deepcopy(old)
        archived["retired_at"] = _now()
        archived["retired_by"] = "manual_withdraw"
        self.requirement_archive.append(archived)
        self._rewrite_active_references({item_id: None}, removed_ids={item_id}, resolved_review_ids={item_id})
        self._content_changed(preserve_candidates=True)
        self._reconcile_conflicts()

    def mark_requirements_reviewed(self, item_ids: list[str]) -> None:
        if not item_ids or len(item_ids) != len(set(item_ids)):
            raise SessionStateError("请选择不重复的待复核需求。")
        pending = set(self.pending_review_item_ids)
        if any(item_id not in pending for item_id in item_ids):
            raise SessionStateError("选中内容不在待复核列表中。")
        selected = set(item_ids)
        for item in self.requirements:
            if item["item_id"] in selected:
                item["confirmation"] = "pending"
        self.pending_review_item_ids = [
            item_id for item_id in self.pending_review_item_ids if item_id not in selected
        ]
        self.touch()

    def _blocking_gap_snapshot(self) -> list[dict[str, Any]]:
        return [row for row in self.active_gaps() if row.get("importance") == "blocking_direction"]

    def current_draft_authorization(self) -> dict[str, Any] | None:
        from .clarification import without_skipped_unknowns
        authorization = self.draft_authorization
        blocking = self._blocking_gap_snapshot()
        if not isinstance(authorization, dict) or not blocking:
            return None
        if (
            authorization.get("task_id") != self.task_id
            or authorization.get("requirement_version") != self.requirement_version
            or authorization.get("task_text") != self.task_text
            or authorization.get("category") != self.selected_category
            or without_skipped_unknowns(self, authorization.get("unresolved_items", [])) != blocking
            or not authorization.get("explanation")
            or not any(row.get("source_id") == authorization.get("source_id") and row.get("role") == "user" for row in self.sources)
        ):
            return None
        current = deepcopy(authorization)
        if current["unresolved_items"] != blocking:
            current["unresolved_items"] = blocking
            current["explanation"] = "；".join(row["description"] for row in blocking) + "。先整理不依赖这些信息的部分，具体信息仍待确认。"
        return current

    def plan_unresolved_items(self) -> list[dict[str, Any]]:
        authorized = self.current_draft_authorization() is not None
        return deepcopy([
            row for row in self.active_gaps()
            if row.get("importance") == "can_defer"
            or (authorized and row.get("importance") == "blocking_direction")
        ])

    @staticmethod
    def _direction_presence(items: list[dict[str, Any]]) -> tuple[bool, bool]:
        fields = {
            item.get("field") for item in items
            if str(item.get("text", "")).strip()
            and item.get("kind") in {"user_fact", "user_decision", "pending_interpretation"}
        }
        deliverable = "deliverable" in fields
        return bool(fields & (DIRECTION_FIELDS - {"deliverable"})) or deliverable, deliverable

    def missing_direction_fields(self) -> list[str]:
        changed = {
            row.get("target_item_id") for row in self.pending_proposals
            if row.get("operation") in {"replace", "withdraw"}
        }
        items = [row for row in self.requirements if row["item_id"] not in changed]
        items += [row for row in self.pending_proposals if row.get("operation") != "withdraw"]
        goal, deliverable = self._direction_presence(items)
        return (["goal"] if not goal else []) + (["deliverable"] if not deliverable else [])

    def suggested_task_result(self) -> str | None:
        """Offer the user's exact task for explicit review, never auto-adopt it."""
        if (
            not self.task_text.strip()
            or self.missing_direction_fields() != ["deliverable"]
            or self.analysis_basis_version != self.requirement_version
            or self.control.get("context_coverage") != "complete"
            or not (self.last_readiness or {}).get("goal_identified")
            or self.open_conflicts
            or self.pending_questions
            or any(row.get("kind") == "pending_interpretation" for row in self.pending_proposals)
            or any(row.get("importance") == "blocking_direction" or row.get("field") == "deliverable" for row in self.active_gaps())
            or any(row.get("assessment_status") == "pending" and row.get("disposition") == "answered" for row in self.question_history)
            or any(row.get("field") == "deliverable" for row in self.requirement_archive + self.deferred_proposals)
            or any(row.get("field") == "deliverable" for row in self.pending_proposals)
        ):
            return None
        return self.task_text.strip()

    def requirements_preview(self) -> dict[str, Any]:
        gaps = self._blocking_gap_snapshot()
        explanation = ""
        if gaps:
            descriptions = "；".join(str(row.get("description", "")).strip() for row in gaps)
            explanation = (
                f"{descriptions}。可以先整理不依赖这些信息的结构与步骤；"
                "相关具体内容等你补充后再完善。选择先做草稿不代表这些内容已经确定，"
                "AI 尚未确认的解释也不会自动成为你的要求。"
            )
        return deepcopy({
            "task_id": self.task_id,
            "task_text": self.task_text,
            "selected_category": self.selected_category,
            "requirement_version": self.requirement_version,
            "analysis_basis_version": self.analysis_basis_version,
            "requirements": self.requirements,
            "pending_proposals": self.pending_proposals,
            "pending_review_item_ids": self.pending_review_item_ids,
            "open_conflicts": self.open_conflicts,
            "gaps": self.active_gaps(),
            "sources": self.sources,
            "last_readiness": self.last_readiness,
            "context_coverage": self.control.get("context_coverage"),
            "draft_explanation": explanation,
            "missing_direction_fields": self.missing_direction_fields(),
            "suggested_task_result": self.suggested_task_result(),
            "clarification_questions": self.questions_for_review(include_plan=False),
            "question_history": self.question_history,
        })

    def confirm_requirements_preview(
        self,
        preview: dict[str, Any],
        *,
        accepted_proposal_ids: list[str] | None = None,
        allow_draft: bool = False,
        use_task_as_deliverable: bool = False,
    ) -> int:
        """Commit only the exact content the user has just reviewed, or nothing."""
        if preview != self.requirements_preview():
            raise SessionStateError("需求已变化，请先查看更新后的需求预览。")
        working = deepcopy(self)
        if working.open_conflicts:
            raise SessionStateError("需求预览仍有冲突，请先保留或撤回互相矛盾的要求。")
        if allow_draft:
            # This button explicitly acknowledges the displayed unknown list.
            for question in working.questions_for_review(include_plan=False, respect_interview_limit=False):
                working.record_question(question["question_id"], "unsure")
        interpretations = [row for row in working.pending_proposals if row.get("kind") == "pending_interpretation"]
        if interpretations and not allow_draft:
            raise SessionStateError("请先核对 AI 推测的解释，或在了解未知内容后选择先做草稿。")
        if not allow_draft:
            working.validate_unknown_reviews(include_plan=False)
        for proposal in interpretations:
            if proposal not in working.pending_proposals:
                continue
            if proposal.get("interpretation_for"):
                working.decide_interpretation(proposal["proposal_id"], "skipped")
            else:
                deferred = deepcopy(proposal)
                deferred["deferred_reason"] = "user_requested_draft"
                working.deferred_proposals.append(deferred)
                working._drop_candidate_ids({proposal["proposal_id"]})
        chosen_ids = accepted_proposal_ids
        if chosen_ids is None:
            chosen_ids = [row["proposal_id"] for row in working.pending_proposals]
        if chosen_ids:
            working.accept_proposals(chosen_ids)
        if use_task_as_deliverable:
            text = preview.get("suggested_task_result")
            if not text or text != self.suggested_task_result() or working._direction_presence(working.requirements) != (True, False):
                raise SessionStateError("当前不能按原任务补记结果，请先核对并说明想要的结果。")
            source_text = f"用户确认想要的结果按原任务整理：{text}"
            source_id = working._add_source(source_text)
            working.requirements.append({
                "item_id": working._next_id("r", working.requirements + working.requirement_archive, "item_id"),
                "field": "deliverable", "text": text, "kind": "user_decision",
                "strength": "unspecified", "scope": "整个任务",
                "source_refs": [{"source_id": source_id, "quote": source_text}],
                "depends_on": [], "confirmation": "pending",
            })
            working._content_changed(preserve_candidates=True)
            working.analysis_basis_version = working.requirement_version
            working.last_readiness["deliverable_identified"] = True
        shown_review_ids = set(preview.get("pending_review_item_ids", []))
        review_ids = [value for value in working.pending_review_item_ids if value in shown_review_ids]
        if review_ids:
            working.mark_requirements_reviewed(review_ids)
        if allow_draft and working._blocking_gap_snapshot():
            explanation = str(preview.get("draft_explanation") or "").strip()
            if not explanation:
                raise SessionStateError("先做草稿前需要展示仍缺少的信息及影响。")
            source_id = working._add_source(f"用户选择先做草稿：{explanation}")
            working.draft_authorization = {
                "task_id": working.task_id,
                "task_text": working.task_text,
                "category": working.selected_category,
                "requirement_version": working.requirement_version,
                "unresolved_items": working._blocking_gap_snapshot(),
                "explanation": explanation,
                "source_id": source_id,
                "authorized_at": _now(),
            }
        version = working.confirm_requirements(allow_draft=allow_draft)
        self.__dict__.update(deepcopy(working.__dict__))
        return version

    def confirm_requirements(self, *, allow_draft: bool = False) -> int:
        self.validate_unknown_reviews(include_plan=False)
        if not self.requirements:
            raise SessionStateError("没有可确认的需求。")
        if self.control.get("context_coverage") != "complete":
            raise SessionStateError("当前上下文不完整，不能确认需求。")
        if self.pending_proposals:
            raise SessionStateError("仍有未处理的需求候选。")
        if self.open_conflicts:
            raise SessionStateError("仍有未处理的冲突。")
        if self.pending_review_item_ids or any(
            item.get("confirmation") == "review_needed" for item in self.requirements
        ):
            raise SessionStateError("仍有受修改影响的需求需要复核。")
        if self._blocking_gap_snapshot() and not (allow_draft and self.current_draft_authorization()):
            raise SessionStateError("仍有影响方向的未决项。")
        goal_present, deliverable_present = self._direction_presence(self.requirements)
        if not goal_present:
            raise SessionStateError("还不清楚你想完成什么，请在上方说明任务。")
        if not deliverable_present:
            raise SessionStateError("还没记下你想要的结果，请在上方说明最后希望得到什么。")
        if self.last_readiness is not None:
            authorized_unknown_goal = (
                allow_draft and self.current_draft_authorization() is not None
                and bool(self._blocking_gap_snapshot())
            )
            if bool(self.last_readiness.get("goal_identified")) != goal_present and not authorized_unknown_goal:
                raise SessionStateError("模型的目标充分性判断与当前需求不一致。")
            if bool(self.last_readiness.get("deliverable_identified")) != deliverable_present:
                raise SessionStateError("模型的交付物充分性判断与当前需求不一致。")
            blocking_ids = {
                gap.get("gap_id") for gap in self._blocking_gap_snapshot()
            }
            from .clarification import skipped_gap_ids
            if set(self.last_readiness.get("blocking_gap_ids", [])) - skipped_gap_ids(self) != blocking_ids:
                raise SessionStateError("模型的阻断缺口判断与当前需求不一致。")
        if self.analysis_basis_version != self.requirement_version:
            raise SessionStateError("当前内容在修改后尚未重新分析，请先分析并复核。")
        self._validate_active_references()
        self._validate_dependencies()
        for item in self.requirements:
            item["confirmation"] = "confirmed"
        self.confirmed_requirements_version = self.requirement_version
        self.touch()
        return self.requirement_version

    def record_question(self, question_id: str, disposition: str, text: str = "", *, context_gap_ids: list[str] | None = None) -> str | None:
        if disposition not in {"answered", "unsure", "skipped"}:
            raise SessionStateError("问题状态无效。")
        active = self.questions_for_review(respect_interview_limit=False)
        question = next((row for row in active if row["question_id"] == question_id), None)
        if question is None:
            raise SessionStateError(f"找不到问题：{question_id}")
        if context_gap_ids is not None:
            live_gaps = {row["gap_id"] for row in self.gaps}
            if len(context_gap_ids) != len(set(context_gap_ids)) or not set(context_gap_ids) <= live_gaps:
                raise SessionStateError("回答上下文引用了重复或不存在的未知事项。")
        clean = text.strip()
        if disposition == "answered" and not clean:
            raise SessionStateError("回答不能为空。")
        # Materialize the current batch so answering the first plan question
        # can invalidate its plan without losing the remaining question cards.
        self.pending_questions = active
        from .clarification import review_key
        gap = next((g for g in self.gaps if g["gap_id"] == question.get("gap_id")), None)
        clarification_key = question.get("clarification_key") or (review_key(self, "requirements", gap) if gap else None)
        gap_id = question.get("gap_id")
        source_id = self._add_source(clean) if disposition == "answered" else None
        answer_id = self._next_id("a", self.question_history, "answer_id")
        if disposition == "answered":
            for previous in self.question_history:
                if previous.get("question_id") == question_id and previous.get("assessment_status") == "pending":
                    previous["assessment_status"] = "applied"
                    previous["assessment_action"] = "superseded_by_user_answer"
                    previous["superseded_by_answer_id"] = answer_id
        self.question_history.append(
            {
                "question_id": question["question_id"],
                "gap_id": gap_id,
                "field": question["field"],
                "scope": question["scope"],
                "text": question["text"],
                "disposition": disposition,
                "answer_id": answer_id,
                "answer_source_id": source_id,
                "answer_text": clean,
                "state_version": self.requirement_version + 1,
                "recorded_source_count": len(self.sources),
                "assessment_status": "pending" if disposition == "answered" else "not_applicable",
            }
        )
        if context_gap_ids is not None and disposition == "answered":
            # This is a snapshot of gaps known when the user submitted the
            # freeform message, not model permission to invent resolved items.
            self.question_history[-1]["context_gap_ids"] = list(context_gap_ids)
        if clarification_key:
            self.question_history[-1]["clarification_key"] = clarification_key
            self.question_history[-1]["clarification_scope"] = question.get("clarification_scope", "requirements")
        if question.get("plan_unknown"):
            self.question_history[-1]["plan_unknown"] = deepcopy(question["plan_unknown"])
        logging.getLogger(__name__).info("User question decision; task=%s question=%s stage=%s choice=%s", self.task_id,
                                        question_id, question.get("clarification_scope", "m1"), disposition)
        origin = {
            "answered": "ambiguous",
            "unsure": "user_unsure",
            "skipped": "user_skipped",
        }[disposition]
        for unresolved in self.gaps:
            if unresolved.get("gap_id") == gap_id:
                unresolved["origin"] = origin
        if disposition == "skipped":
            logging.getLogger(__name__).info("Skipped question excluded from active gaps and delivery; task=%s question=%s gap=%s",
                                            self.task_id, question_id, gap_id)
        self.pending_questions = [
            row
            for row in self.pending_questions
            if row["question_id"] != question_id
        ]
        if question.get("clarification_scope") and disposition in {"skipped", "unsure"}:
            # Explicit deferral changes no requirement or plan content. It
            # permits a later confirmation, never performs one itself.
            self.touch()
            return None
        assessed_before = self.analysis_basis_version == self.requirement_version
        self._content_changed(preserve_candidates=True)
        # Skipping records a user's choice but does not change the known task.
        # It must not force an extra model call solely to unlock a preview.
        if disposition in {"skipped", "unsure"} and assessed_before:
            self.analysis_basis_version = self.requirement_version
        return source_id

    def record_supplement(self, text: str, *, gap_ids: list[str] | None = None, context_gap_ids: list[str] | None = None) -> str:
        clean = text.strip()
        if not clean:
            raise SessionStateError("补充内容不能为空。")
        if gap_ids:
            gaps = {row["gap_id"]: row for row in self.gaps}
            if len(gap_ids) != len(set(gap_ids)) or any(value not in gaps for value in gap_ids):
                raise SessionStateError("补充引用了重复或已变化的未知事项，请查看当前问题。")
            working = deepcopy(self)
            source_id = ""
            for gap_id in gap_ids:
                gap = gaps[gap_id]
                last = next((row for row in reversed(working.question_history) if row.get("gap_id") == gap_id), None)
                if last and last.get("assessment_status") == "pending" and last.get("answer_text") == clean:
                    source_id = str(last["answer_source_id"])
                    continue
                question = next((row for row in working.pending_questions if row.get("gap_id") == gap_id), None)
                if question is None and last:
                    question = working.reopen_question(last["question_id"])
                if question is None:
                    question = {
                        "question_id": working._next_id("supplement-", [*working.pending_questions, *working.question_history], "question_id"),
                        "gap_id": gap_id, "field": gap["field"], "scope": gap["scope"],
                        "text": gap["description"], "options": [], "reason": "用户在当前未知事项下直接补充",
                        "depends_on": deepcopy(gap.get("depends_on", [])),
                    }
                    working.pending_questions.append(question)
                source_id = str(working.record_question(question["question_id"], "answered", clean, context_gap_ids=context_gap_ids))
            self.__dict__.update(deepcopy(working.__dict__))
            return source_id
        last = self.question_history[-1] if self.question_history else None
        if last and last.get("field") == "supplement" and last.get("answer_text") == clean and last.get("assessment_status") == "pending":
            return str(last["answer_source_id"])
        question_id = self._next_id("supplement-", [*self.pending_questions, *self.question_history], "question_id")
        self.pending_questions.append({
            "question_id": question_id, "gap_id": None, "field": "supplement",
            "scope": "整体任务", "text": "用户直接补充的要求", "options": [],
            "reason": "用户主动补充或更正", "depends_on": [],
        })
        return str(self.record_question(question_id, "answered", clean, context_gap_ids=context_gap_ids))

    def reopen_question(self, question_id: str) -> dict[str, Any]:
        pending = next((row for row in self.pending_questions if row.get("question_id") == question_id), None)
        if pending is not None:
            return deepcopy(pending)
        old = next((row for row in reversed(self.question_history) if row.get("question_id") == question_id), None)
        if old is None:
            raise SessionStateError("找不到可补答的问题。")
        gap = next((row for row in self.gaps if row.get("gap_id") == old.get("gap_id")), None)
        if old.get("gap_id") is not None and gap is None:
            raise SessionStateError("这个问题已经解决；如需更改，请直接补充说明。")
        question = {key: deepcopy(old[key]) for key in ("question_id", "gap_id", "field", "scope", "text")}
        for key in ("clarification_key", "clarification_scope", "plan_unknown"):
            if key in old:
                question[key] = deepcopy(old[key])
        question.update(options=[], reason="用户主动补答此前的问题", user_requested_reopen=True,
                        depends_on=deepcopy((gap or {}).get("depends_on", [])))
        self.pending_questions.append(question)
        logging.getLogger(__name__).info("User reopened historical question; task=%s question=%s stage=%s",
                                        self.task_id, question_id, question.get("clarification_scope", "requirements"))
        self.touch()
        return deepcopy(question)

    def decide_interpretation(self, proposal_id: str, decision: str) -> dict[str, Any] | None:
        if decision not in {"accepted", "rejected", "skipped"}:
            raise SessionStateError("请选择接受、纠正或跳过这段推测。")
        proposal = next((row for row in self.pending_proposals if row.get("proposal_id") == proposal_id), None)
        link = (proposal or {}).get("interpretation_for")
        if proposal is None or proposal.get("kind") != "pending_interpretation" or not isinstance(link, dict):
            raise SessionStateError("这条内容不是可供确认的解释。")
        if proposal.get("operation") != "new" or proposal.get("target_item_id") is not None:
            raise SessionStateError("确认解释不能附带替换或撤回其他要求。")
        gap = next((row for row in self.gaps if row.get("gap_id") == link.get("gap_id")), None)
        if gap is None or proposal.get("valid_for_version", self.requirement_version) != self.requirement_version:
            raise SessionStateError("这段推测的来源已经变化，请查看当前内容。")
        if proposal.get("field") != gap.get("field") or proposal.get("scope") != gap.get("scope"):
            raise SessionStateError("这段推测与所解释的问题不一致。")
        if any(proposal_id in row.get("proposal_ids", []) for row in self.open_conflicts):
            raise SessionStateError("这段推测仍涉及冲突，请先处理冲突。")
        working = deepcopy(self)
        source_id = None
        created = None
        same_gap_ids = {
            row["proposal_id"] for row in working.pending_proposals
            if (row.get("interpretation_for") or {}).get("gap_id") == gap["gap_id"]
        }
        if decision == "accepted":
            assessed_before = working.analysis_basis_version == working.requirement_version
            text = f"用户确认这段理解：{proposal['text']}"
            question_id = link.get("question_id")
            if not question_id:
                question_id = working._next_id("interpretation-", [*working.pending_questions, *working.question_history], "question_id")
            pending = next((row for row in working.pending_questions if row.get("question_id") == question_id), None)
            if pending is None:
                working.pending_questions.append({
                    "question_id": question_id, "gap_id": gap["gap_id"], "field": gap["field"], "scope": gap["scope"],
                    "text": gap["description"], "options": [], "reason": "用户核对 AI 的解释", "depends_on": gap.get("depends_on", []),
                })
            source_id = working.record_question(question_id, "answered", text)
            answer = working.question_history[-1]
            answer.update(assessment_status="applied", assessment_action="user_confirmed_interpretation")
            selected = next(row for row in working.pending_proposals if row["proposal_id"] == proposal_id)
            selected["kind"] = "user_decision"
            selected["source_refs"] = [{"source_id": source_id, "quote": text}]
            selected.pop("interpretation_for", None)
            working._drop_candidate_ids(same_gap_ids - {proposal_id})
            working.gaps = [row for row in working.gaps if row.get("gap_id") != gap["gap_id"]]
            working.pending_questions = [row for row in working.pending_questions if row.get("gap_id") != gap["gap_id"]]
            if working.last_readiness:
                working.last_readiness["blocking_gap_ids"] = [value for value in working.last_readiness.get("blocking_gap_ids", []) if value != gap["gap_id"]]
                if gap["field"] in DIRECTION_FIELDS - {"deliverable"}:
                    working.last_readiness["goal_identified"] = True
                elif gap["field"] == "deliverable":
                    working.last_readiness["deliverable_identified"] = True
            if assessed_before:
                working.analysis_basis_version = working.requirement_version
            created = working.accept_proposals([proposal_id])[0]
        else:
            assessed_before = working.analysis_basis_version == working.requirement_version
            prior_version = working.requirement_version
            for row in working.pending_proposals:
                if row["proposal_id"] in same_gap_ids:
                    deferred = deepcopy(row)
                    deferred["deferred_reason"] = f"interpretation_{decision}"
                    working.deferred_proposals.append(deferred)
            working._drop_candidate_ids(same_gap_ids)
            if decision == "skipped":
                question = next((row for row in working.pending_questions if row.get("gap_id") == gap["gap_id"]), None)
                if question:
                    working.record_question(question["question_id"], "skipped")
                else:
                    for row in working.gaps:
                        if row["gap_id"] == gap["gap_id"]:
                            row["origin"] = "user_skipped"
            if working.requirement_version == prior_version:
                working._content_changed(preserve_candidates=True)
                if assessed_before:
                    working.analysis_basis_version = working.requirement_version
        working.interpretation_history.append({
            "proposal_id": proposal_id, "gap_id": gap["gap_id"], "question_id": link.get("question_id"),
            "decision": decision, "text": proposal["text"], "source_id": source_id,
            "recorded_source_count": len(working.sources), "recorded_at": _now(),
        })
        working.touch()
        self.__dict__.update(deepcopy(working.__dict__))
        return created

    def accept_generic_interpretation(self, proposal_id: str) -> dict[str, Any]:
        """Record a deliberate choice for an older, unlinked interpretation."""
        proposal = next((row for row in self.pending_proposals if row.get("proposal_id") == proposal_id), None)
        if not proposal or proposal.get("kind") != "pending_interpretation" or proposal.get("interpretation_for"):
            raise SessionStateError("请选择当前预览中需要核对的一段理解。")
        working = deepcopy(self)
        selected = next(row for row in working.pending_proposals if row["proposal_id"] == proposal_id)
        text = f"用户确认这段理解：{selected['text']}"
        source_id = working._add_source(text)
        selected["kind"] = "user_decision"
        selected["source_refs"] = [{"source_id": source_id, "quote": text}]
        created = working.accept_proposals([proposal_id])
        if not created:
            raise SessionStateError("理解确认不能撤回其他要求。")
        self.__dict__.update(deepcopy(working.__dict__))
        return created[0]
