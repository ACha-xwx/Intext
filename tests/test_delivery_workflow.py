from __future__ import annotations

import json
import threading
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import pytest

from promptsmith.api import (
    ANTHROPIC_MESSAGES_PROTOCOL,
    OPENAI_RESPONSES_PROTOCOL,
    PROTOCOL_ID,
    ApiConfig,
    ApiResult,
    client_for_config,
)
from promptsmith.session import SessionState
from promptsmith.skill_catalog import SkillCatalog
from promptsmith.delivery_workflow import (
    DeliveryCallFailure,
    DeliveryStaleResponseError,
    DeliveryWorkflowError,
    DeliveryWorkflow,
)
from promptsmith.finalization import decide_m4_change, validate_delivery_entry
from promptsmith.local_skill_search import search_local_skills
from promptsmith.skill_search import normalize_github_results


ROOT = Path(__file__).resolve().parents[1]
PROTOCOLS = [PROTOCOL_ID, OPENAI_RESPONSES_PROTOCOL, ANTHROPIC_MESSAGES_PROTOCOL]


class DeliveryHandler(BaseHTTPRequestHandler):
    protocol_id = PROTOCOL_ID
    mode = "m3"
    delay_entered: threading.Event | None = None
    delay_release: threading.Event | None = None
    seen: dict = {}

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        path = urlparse(self.path).path
        type(self).seen = {
            "path": path,
            "authorization": self.headers.get("Authorization"),
            "x_api_key": self.headers.get("x-api-key"),
            "anthropic_version": self.headers.get("anthropic-version"),
            "body": body,
        }
        if type(self).delay_entered:
            type(self).delay_entered.set()
            if type(self).delay_release:
                type(self).delay_release.wait(timeout=5)

        payload = self._extract_payload(path, body)
        if type(self).mode == "m3":
            response = self._m3_output(payload)
        elif type(self).mode == "m4":
            response = self._m4_output(payload)
        elif type(self).mode == "invalid":
            response = {"not": "a valid response"}
        else:
            response = {"schema_version": "wrong"}

        text = json.dumps(response, ensure_ascii=False)
        if path == "/chat/completions":
            envelope = {
                "id": "stub-chat-response",
                "model": body.get("model", "stub-model"),
                "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
            }
        elif path == "/responses":
            envelope = {
                "id": "stub-responses-response",
                "model": body.get("model", "stub-model"),
                "status": "completed",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
                "usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
            }
        else:
            envelope = {
                "id": "stub-anthropic-response",
                "model": body.get("model", "stub-model"),
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": text}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 20, "output_tokens": 10},
            }
        encoded = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    @staticmethod
    def _extract_payload(path: str, body: dict) -> dict:
        if path == "/chat/completions":
            raw = body["messages"][1]["content"]
        elif path == "/responses":
            raw = body["input"][0]["content"][-1]["text"]
        else:
            raw = body["messages"][0]["content"]
        return json.loads(raw)

    @staticmethod
    def _m3_output(payload: dict) -> dict:
        candidates = payload["candidates"]
        assessments = [
            {
                "candidate_id": row["candidate_id"],
                "decision": "recommend",
                "capability_ids": [row["capabilities"][0]["capability_id"]],
                "reason": "该能力与对应关键工作直接相关。",
                "planned_inputs": ["已确认需求"],
                "expected_outputs": ["当前工作产物"],
                "prerequisite_ids": [],
                "limitations": ["只适配方法，不执行原版 Skill。"],
            }
            for row in candidates
        ]
        return {
            "schema_version": "m3.v0.1",
            "request_id": payload["request_id"],
            "task_id": payload["task_id"],
            "status": "ok",
            "assessments": assessments,
            "unmatched_key_work_ids": [],
            "error": None,
        }

    @staticmethod
    def _m4_output(payload: dict) -> dict:
        contributions = []
        for binding in payload["bindings"]:
            prerequisite_ids = [
                row["prerequisite_id"]
                for row in binding["prerequisite_assessments"]
                if row["status"] == "unknown" and row["blocking"]
            ]
            contributions.append(
                {
                    "binding_id": binding["binding_id"],
                    "step_id": binding["step_ids"][0],
                    "capability_ids": [binding["capability_ids"][0]],
                    "method_actions": ["按能力摘要组织当前工作产物。"],
                    "planned_inputs": ["已确认需求"],
                    "expected_outputs": ["可复核的工作草稿"],
                    "checkpoints": ["逐项核对需求与边界。"],
                    "prerequisite_ids": prerequisite_ids,
                    "fallback_actions": ["缺少必要材料时保留未知并执行不依赖该材料的步骤。"],
                    "proposed_change_ids": [],
                }
            )
        return {
            "schema_version": "m4.v0.1",
            "request_id": payload["request_id"],
            "task_id": payload["task_id"],
            "status": "ok",
            "contributions": contributions,
            "proposed_changes": [],
            "error": None,
        }

    def log_message(self, format: str, *args) -> None:
        return


@pytest.fixture
def stub_server():
    DeliveryHandler.mode = "m3"
    DeliveryHandler.delay_entered = None
    DeliveryHandler.delay_release = None
    DeliveryHandler.seen = {}
    server = ThreadingHTTPServer(("127.0.0.1", 0), DeliveryHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        if DeliveryHandler.delay_release:
            DeliveryHandler.delay_release.set()
        server.shutdown()
        thread.join(timeout=2)


def make_session(*, with_binding: bool = False) -> SessionState:
    session = SessionState.new()
    session.task_text = "整理已确认的软件报名系统需求规格"
    session.selected_category = "general"
    session.requirement_version = 1
    session.analysis_basis_version = 1
    session.confirmed_requirements_version = 1
    session.requirements = [{"item_id": "r1", "text": "形成本地规格文档", "strength": "hard"}]
    session.plan = {
        "plan_id": "plan-delivery-test",
        "plan_version": 1,
        "status": "confirmed",
        "content": {
            "goal": {"summary": "为软件报名系统形成可复核需求规格", "audience": "开发团队", "scope": "本地文档"},
            "requirement_coverage": [{"requirement_id": "r1", "summary": "交付规格", "step_ids": ["s1"], "deliverable_ids": ["d1"], "criterion_ids": ["c1"]}],
            "steps": [{"step_id": "s1", "order": 1, "title": "整理规格", "purpose": "形成可复核文档", "inputs": ["需求"], "actions": ["整理需求和验收方式"], "outputs": ["规格草稿"], "completion_criteria": ["需求与测试对应"], "depends_on_step_ids": [], "requirement_ids": ["r1"]}],
            "deliverables": [{"deliverable_id": "d1", "name": "本地规格文档", "description": "含需求和测试策略", "step_ids": ["s1"], "requirement_ids": ["r1"]}],
            "completion_criteria": [{"criterion_id": "c1", "text": "需求与测试对应", "requirement_ids": ["r1"]}],
            "unresolved_items": [{"unknown_id": "u1", "description": "仓库结构尚未提供", "impact": "不能核实代码事实", "continuable_work": "先整理需求规格"}],
            "suggestions": [],
            "key_work": [{"key_work_id": "k1", "title": "整理软件报名系统需求规格", "goal": "形成软件报名系统规格文档", "inputs": ["已确认的软件需求"], "outputs": ["软件规格文档"], "checkpoints": ["覆盖测试决定"], "step_ids": ["s1"], "requirement_ids": ["r1"], "depends_on_key_work_ids": []}],
        },
        "source_requirements_version": 1,
        "confirmed_plan_version": 1,
        "pending_key_work_review_ids": [],
        "reviewed_key_work_ids": ["k1"],
    }
    basis = {
        "task_id": session.task_id,
        "requirement_version": session.requirement_version,
        "plan_id": session.plan["plan_id"],
        "plan_version": session.plan["plan_version"],
    }
    if with_binding:
        catalog = SkillCatalog.load(ROOT / "resources" / "skill_catalog" / "catalog_v0.1.json", source_root=ROOT, verify_sources=True)
        record = next(row for row in catalog.records if row["skill_id"] == "to-spec")
        session.set_skill_state(
            status="selected",
            basis=basis,
            bindings=[{
                "binding_id": "binding-test",
                "skill_id": "to-spec",
                "record_hash": record["record_hash"],
                "record_snapshot": record,
                "key_work_id": "k1",
                "step_ids": ["s1"],
                "usage_mode": "method_adaptation",
                "capability_ids": ["cap-spec-structure"],
                "precondition_assessments": [
                    {"prerequisite_id": "adapt-confirmed-requirements", "status": "satisfied", "source": "user_reported"},
                    {"prerequisite_id": "adapt-local-output", "status": "satisfied", "source": "user_reported"},
                ],
            }],
        )
    else:
        catalog = SkillCatalog.load(ROOT / "resources" / "skill_catalog" / "catalog_v0.1.json", source_root=ROOT, verify_sources=True)
        work = session.plan["content"]["key_work"][0]
        match = catalog.match([work])
        session.set_skill_state(
            status="candidates_ready",
            basis=basis,
            candidate_batch={
                "batch_id": "batch-test",
                "catalog_id": catalog.catalog_id,
                "catalog_version": catalog.catalog_version,
                "catalog_hash": catalog.snapshot_hash,
                "result": match.to_dict(),
            },
            bindings=[],
        )
    # This downstream fixture represents a user who explicitly deferred the
    # missing repository material before confirming the plan.
    for question in session.questions_for_review():
        session.record_question(question["question_id"], "skipped")
    return session


def client_for(server: str, protocol: str):
    return client_for_config(
        ApiConfig(
            base_url=server,
            model="stub-model",
            api_key="test-only-secret",
            timeout_seconds=3,
            protocol=protocol,
        )
    )


def test_m4_does_not_repeat_plan_step_and_key_work_text(tmp_path: Path) -> None:
    session = make_session(with_binding=True)
    before = deepcopy(session.plan)
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path)
    payload = workflow.prepare_m4("compact-m4", connection_version=1)

    assert session.plan == before
    assert payload["steps"][0]["actions"] == before["content"]["steps"][0]["actions"]
    assert payload["key_work"][0]["goal"] == before["content"]["key_work"][0]["goal"]
    assert payload["baseline"]["plan"]["steps"][0]["depends_on_step_ids"] == []
    assert payload["baseline"]["plan"]["steps"][0]["requirement_ids"] == ["r1"]
    wire = json.dumps(payload, ensure_ascii=False)
    assert wire.count("整理需求和验收方式") == 1
    assert wire.count("形成软件报名系统规格文档") == 1


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_m3_prepare_invoke_apply_uses_each_protocol_and_records_candidate_analysis(
    stub_server, tmp_path: Path, protocol: str
) -> None:
    DeliveryHandler.mode = "m3"
    session = make_session()
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "evidence")
    payload = workflow.prepare_m3("m3-" + protocol, connection_version=1)

    outcome = workflow.invoke_m3(
        payload,
        client_for(stub_server, protocol),
        protocol=protocol,
        configured_model="stub-model",
    )
    workflow.apply_m3(payload, outcome, connection_version=1)

    assert session.skill_state["candidate_batch"]["m3_analysis"]["result"]["status"] == "ok"
    assert DeliveryHandler.seen["path"] == {
        PROTOCOL_ID: "/chat/completions",
        OPENAI_RESPONSES_PROTOCOL: "/responses",
        ANTHROPIC_MESSAGES_PROTOCOL: "/messages",
    }[protocol]
    assert session.api_runs[-1]["status"] == "accepted_as_candidate_analysis"
    assert DeliveryHandler.seen["authorization"] == (
        "Bearer test-only-secret" if protocol != ANTHROPIC_MESSAGES_PROTOCOL else None
    )
    assert DeliveryHandler.seen["x_api_key"] == (
        "test-only-secret" if protocol == ANTHROPIC_MESSAGES_PROTOCOL else None
    )
    assert DeliveryHandler.seen["anthropic_version"] == (
        "2023-06-01" if protocol == ANTHROPIC_MESSAGES_PROTOCOL else None
    )
    assert "test-only-secret" not in "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (tmp_path / "evidence").rglob("*")
        if path.is_file()
    )


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_m4_prepare_invoke_apply_builds_a_final_draft_over_each_protocol(
    stub_server, tmp_path: Path, protocol: str
) -> None:
    DeliveryHandler.mode = "m4"
    session = make_session(with_binding=True)
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "evidence")
    payload = workflow.prepare_m4("m4-" + protocol, connection_version=2)

    outcome = workflow.invoke_m4(
        payload,
        client_for(stub_server, protocol),
        protocol=protocol,
        configured_model="stub-model",
    )
    workflow.apply_m4(payload, outcome, connection_version=2)

    assert session.final_result["status"] == "draft"
    assert session.final_result["generation_request_id"] == payload["request_id"]
    assert session.final_result["content"]["skill_contributions"][0]["binding_id"] == "binding-test"
    assert session.api_runs[-1]["status"] == "accepted_as_final_draft"
    assert DeliveryHandler.seen["path"] == {
        PROTOCOL_ID: "/chat/completions",
        OPENAI_RESPONSES_PROTOCOL: "/responses",
        ANTHROPIC_MESSAGES_PROTOCOL: "/messages",
    }[protocol]


def test_delivery_payloads_keep_remote_source_provenance_and_review_source(tmp_path: Path) -> None:
    session = make_session()
    basis = session.skill_state["basis"]
    candidate = normalize_github_results(
        [{
            "full_name": "example/remote-skill",
            "name": "SKILL.md",
            "path": "skills/to-spec/SKILL.md",
            "description": "组织需求规格和测试决定",
            "html_url": "https://github.com/example/remote-skill/blob/main/skills/to-spec/SKILL.md",
            "updated_at": "2026-10-01T00:00:00Z",
        }],
        query="requirements",
        key_work_ids=["k1"],
    )[0]
    candidate["step_ids"] = ["s1"]
    candidate_batch = {
        "batch_id": "remote-batch-test",
        "catalog_hash": "a" * 64,
        "result": {"status": "ok", "candidates": [candidate]},
    }
    session.set_skill_state(
        status="candidates_ready", basis=basis, candidate_batch=candidate_batch, bindings=[]
    )
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "evidence")

    m3_payload = workflow.prepare_m3("m3-remote-source", connection_version=1)

    provenance = m3_payload["candidates"][0]["provenance"]
    assert provenance["origin"] == "remote"
    assert provenance["source_url"].startswith("https://github.com/")
    assert provenance["fixed_commit"] == "unresolved"
    assert provenance["content_hash_kind"] == "api_metadata"
    assert provenance["source_read"] is False

    record = candidate["record_snapshot"]
    binding = {
        "binding_id": "remote-binding-test",
        "skill_id": candidate["skill_id"],
        "record_hash": candidate["record_hash"],
        "record_snapshot": record,
        "key_work_id": "k1",
        "step_ids": ["s1"],
        "usage_mode": "method_adaptation",
        "capability_ids": candidate["capability_ids"],
        "precondition_assessments": [
            {"prerequisite_id": "remote-source-review", "status": "unknown", "source": "catalog_evidence"}
        ],
    }
    session.set_skill_state(
        status="selected", basis=basis, candidate_batch=candidate_batch, bindings=[binding]
    )

    m4_payload = workflow.prepare_m4("m4-remote-source", connection_version=2)

    prepared_binding = m4_payload["bindings"][0]
    assert prepared_binding["provenance"] == provenance
    assert prepared_binding["prerequisite_assessments"][0]["source"] == "remote_source_review"

    binding["precondition_assessments"][0]["source"] = "remote_source_review"
    session.set_skill_state(
        status="selected", basis=basis, candidate_batch=candidate_batch, bindings=[binding]
    )
    validate_delivery_entry(session)


def test_m4_receives_bounded_method_text_from_selected_local_skill(tmp_path: Path) -> None:
    skill_file = tmp_path / "requirements" / "SKILL.md"
    skill_file.parent.mkdir()
    skill_file.write_text(
        "---\nname: requirements\ndescription: 整理软件报名系统需求规格。\n---\n\n"
        "# 方法\n先建立需求与验收条件的对应表，再核对遗漏项。\n" + "补充说明。" * 1000,
        encoding="utf-8",
    )
    session = make_session()
    basis = session.skill_state["basis"]
    candidate = search_local_skills(
        session.plan["content"]["key_work"], task_text=session.task_text, roots=[tmp_path]
    ).candidates[0]
    session.set_skill_state(status="selected", basis=basis, bindings=[{
        "binding_id": "local-method",
        "skill_id": candidate["skill_id"],
        "record_hash": candidate["record_hash"],
        "record_snapshot": candidate["record_snapshot"],
        "key_work_id": "k1",
        "step_ids": ["s1"],
        "usage_mode": "method_adaptation",
        "capability_ids": candidate["capability_ids"],
        "precondition_assessments": [],
    }])

    payload = DeliveryWorkflow(session, evidence_root=tmp_path / "evidence").prepare_m4(
        "m4-local-method", connection_version=1
    )

    summary = payload["bindings"][0]["adaptation_summary"]
    assert "先建立需求与验收条件的对应表" in summary
    assert "[Agent Skill 指令摘录已截断]" in summary
    assert len(summary) < 3400


def test_m4_receives_selected_verified_online_method_text(tmp_path: Path) -> None:
    session = make_session()
    basis = session.skill_state["basis"]
    candidate = normalize_github_results(
        [{"full_name": "example/method", "name": "SKILL.md", "path": "skills/method/SKILL.md",
          "description": "整理需求", "html_url": "https://github.com/example/method/blob/main/skills/method/SKILL.md"}],
        query="requirements", key_work_ids=["k1"],
    )[0]
    record = candidate["record_snapshot"]
    record["source_text"] = "# 方法\n先列出输入，再逐条映射到验收检查点。"
    record["verification"]["source_read"] = True
    session.set_skill_state(status="selected", basis=basis, bindings=[{
        "binding_id": "remote-method",
        "skill_id": record["skill_id"],
        "record_hash": record["record_hash"],
        "record_snapshot": record,
        "key_work_id": "k1",
        "step_ids": ["s1"],
        "usage_mode": "method_adaptation",
        "capability_ids": candidate["capability_ids"],
        "precondition_assessments": [
            {"prerequisite_id": "remote-source-review", "status": "unknown", "source": "remote_source_review"}
        ],
    }])

    payload = DeliveryWorkflow(session, evidence_root=tmp_path / "evidence").prepare_m4(
        "m4-remote-method", connection_version=1
    )

    assert "先列出输入，再逐条映射到验收检查点" in payload["bindings"][0]["adaptation_summary"]
    assert payload["bindings"][0]["provenance"]["source_read"] is True


def test_m3_rejects_a_response_when_candidate_batch_changes_before_apply(tmp_path: Path) -> None:
    session = make_session()
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "evidence")
    payload = workflow.prepare_m3("m3-batch-stale", connection_version=4)
    outcome = workflow.invoke_m3(payload, _StaticClient(DeliveryHandler._m3_output(payload)), protocol=PROTOCOL_ID, configured_model="test")
    session.set_skill_state(
        status="candidates_ready",
        basis=session.skill_state["basis"],
        candidate_batch={"batch_id": "new-batch", "catalog_hash": "changed", "result": {"candidates": []}},
        bindings=[],
    )
    before = session.to_dict()

    with pytest.raises(DeliveryStaleResponseError):
        workflow.apply_m3(payload, outcome, connection_version=4)

    assert session.to_dict() == before


def test_m4_rejects_response_if_delivery_revision_changes_during_invoke(
    stub_server, tmp_path: Path
) -> None:
    DeliveryHandler.mode = "m4"
    entered, release = threading.Event(), threading.Event()
    DeliveryHandler.delay_entered = entered
    DeliveryHandler.delay_release = release
    session = make_session(with_binding=True)
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "evidence")
    payload = workflow.prepare_m4("m4-delivery-stale", connection_version=1)
    outcome_box: dict[str, object] = {}

    def invoke() -> None:
        outcome_box["outcome"] = workflow.invoke_m4(
            payload,
            client_for(stub_server, PROTOCOL_ID),
            protocol=PROTOCOL_ID,
            configured_model="stub-model",
        )

    before_invoke = session.to_dict()
    thread = threading.Thread(target=invoke)
    thread.start()
    assert entered.wait(timeout=2)
    assert session.to_dict() == before_invoke
    session.invalidate_delivery("simulated_user_edit")
    after_edit = session.to_dict()
    release.set()
    thread.join(timeout=4)
    assert not thread.is_alive()

    with pytest.raises(DeliveryStaleResponseError):
        workflow.apply_m4(payload, outcome_box["outcome"], connection_version=1)

    assert session.to_dict() == after_edit


def test_connection_aba_and_cancelled_response_cannot_apply(tmp_path: Path) -> None:
    session = make_session()
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "evidence")
    payload = workflow.prepare_m3("m3-connection-aba", connection_version=10)
    outcome = workflow.invoke_m3(payload, _StaticClient(DeliveryHandler._m3_output(payload)), protocol=PROTOCOL_ID, configured_model="test")
    before = session.to_dict()
    with pytest.raises(DeliveryStaleResponseError):
        workflow.apply_m3(payload, outcome, connection_version=12)
    assert session.to_dict() == before

    payload2 = workflow.prepare_m3("m3-cancelled", connection_version=12)
    outcome2 = workflow.invoke_m3(payload2, _StaticClient(DeliveryHandler._m3_output(payload2)), protocol=PROTOCOL_ID, configured_model="test")
    assert workflow.cancel(payload2["request_id"])
    with pytest.raises(DeliveryStaleResponseError):
        workflow.apply_m3(payload2, outcome2, connection_version=12)
    assert session.to_dict() == before


def test_m4_partial_response_generates_reference_prompt_and_preserves_selection(tmp_path: Path) -> None:
    session = make_session(with_binding=True)
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "evidence")
    payload = workflow.prepare_m4("m4-invalid-output", connection_version=1)
    invalid = {"not": "an M4 response"}
    outcome = workflow.invoke_m4(payload, _StaticClient(invalid), protocol=PROTOCOL_ID, configured_model="test")
    before = {
        "final_result": deepcopy(session.final_result),
        "final_archive": deepcopy(session.final_archive),
        "delivery_revision": session.delivery_revision,
        "skill_state": deepcopy(session.skill_state),
    }

    workflow.apply_m4(payload, outcome, connection_version=1)
    assert session.final_result["status"] == "draft"
    assert "to-spec" in session.final_result["canonical_body"]
    assert "an M4 response" in session.final_result["canonical_body"]
    assert session.skill_state == before["skill_state"]


def test_m3_delayed_response_after_task_change_is_discarded_without_apply_writes(
    stub_server, tmp_path: Path
) -> None:
    DeliveryHandler.mode = "m3"
    entered, release = threading.Event(), threading.Event()
    DeliveryHandler.delay_entered = entered
    DeliveryHandler.delay_release = release
    session = make_session()
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "evidence")
    payload = workflow.prepare_m3("m3-delayed-task-change", connection_version=3)
    outcome_box: dict[str, object] = {}

    def invoke() -> None:
        outcome_box["outcome"] = workflow.invoke_m3(
            payload,
            client_for(stub_server, PROTOCOL_ID),
            protocol=PROTOCOL_ID,
            configured_model="stub-model",
        )

    before_invoke = session.to_dict()
    thread = threading.Thread(target=invoke)
    thread.start()
    assert entered.wait(timeout=2)
    assert session.to_dict() == before_invoke
    session.task_text = "已经修改的新任务"
    after_edit = session.to_dict()
    release.set()
    thread.join(timeout=4)
    assert not thread.is_alive()

    with pytest.raises(DeliveryStaleResponseError):
        workflow.apply_m3(
            payload,
            outcome_box["outcome"],
            connection_version=3,
        )

    assert session.to_dict() == after_edit


def test_cancelled_delayed_m4_response_is_discarded(stub_server, tmp_path: Path) -> None:
    DeliveryHandler.mode = "m4"
    entered, release = threading.Event(), threading.Event()
    DeliveryHandler.delay_entered = entered
    DeliveryHandler.delay_release = release
    session = make_session(with_binding=True)
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "evidence")
    payload = workflow.prepare_m4("m4-cancel-in-flight", connection_version=7)
    outcome_box: dict[str, object] = {}

    def invoke() -> None:
        outcome_box["outcome"] = workflow.invoke_m4(
            payload,
            client_for(stub_server, ANTHROPIC_MESSAGES_PROTOCOL),
            protocol=ANTHROPIC_MESSAGES_PROTOCOL,
            configured_model="stub-model",
        )

    before_invoke = session.to_dict()
    thread = threading.Thread(target=invoke)
    thread.start()
    assert entered.wait(timeout=2)
    assert session.to_dict() == before_invoke
    assert workflow.cancel(payload["request_id"])
    after_cancel = session.to_dict()
    release.set()
    thread.join(timeout=4)
    assert not thread.is_alive()

    with pytest.raises(DeliveryStaleResponseError):
        workflow.apply_m4(
            payload,
            outcome_box["outcome"],
            connection_version=7,
        )

    assert session.to_dict() == after_cancel


def test_duplicate_apply_is_rejected_after_the_first_atomic_commit(tmp_path: Path) -> None:
    session = make_session()
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "evidence")
    payload = workflow.prepare_m3("m3-duplicate-apply", connection_version=1)
    outcome = workflow.invoke_m3(
        payload,
        _StaticClient(DeliveryHandler._m3_output(payload)),
        protocol=PROTOCOL_ID,
        configured_model="test",
    )
    workflow.apply_m3(payload, outcome, connection_version=1)
    after_first = session.to_dict()

    with pytest.raises(DeliveryStaleResponseError):
        workflow.apply_m3(payload, outcome, connection_version=1)

    assert session.to_dict() == after_first


def test_request_ids_cannot_be_reused_after_apply(tmp_path: Path) -> None:
    session = make_session()
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "evidence")
    payload = workflow.prepare_m3("m3-single-use-id", connection_version=1)
    outcome = workflow.invoke_m3(
        payload,
        _StaticClient(DeliveryHandler._m3_output(payload)),
        protocol=PROTOCOL_ID,
        configured_model="test",
    )
    workflow.apply_m3(payload, outcome, connection_version=1)

    with pytest.raises(DeliveryWorkflowError, match="请求编号"):
        workflow.prepare_m3("m3-single-use-id", connection_version=1)


def test_m4_proposed_change_is_deferred_to_final_prompt(tmp_path: Path) -> None:
    session = make_session(with_binding=True)
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "evidence")
    payload = workflow.prepare_m4("m4-pending-change", connection_version=1)
    response = DeliveryHandler._m4_output(payload)
    change = {
        "change_id": "change-local-glossary",
        "binding_ids": ["binding-test"],
        "kind": "scope",
        "description": "增加一页领域术语表。",
        "reason": "统一规格中的领域词汇。",
        "affects_hard_constraints": False,
    }
    response["proposed_changes"] = [change]
    response["contributions"][0]["proposed_change_ids"] = [change["change_id"]]
    outcome = workflow.invoke_m4(
        payload,
        _StaticClient(response),
        protocol=PROTOCOL_ID,
        configured_model="test",
    )

    workflow.apply_m4(payload, outcome, connection_version=1)

    final = session.final_result
    assert final["status"] == "draft"
    assert final["review_required_ids"] == []
    assert final["content"]["pending_changes"][-1]["decision"] == "pending"
    assert final["change_decisions"][-1] == {
        "generation_request_id": "m4-pending-change",
        "change_id": "change-local-glossary",
        "decision": "pending",
        "decided_by": "workflow",
        "reason": "M4 首次接收，等待用户决定。",
    }


def test_m4_same_change_id_is_a_fresh_decision_in_each_generation(tmp_path: Path) -> None:
    session = make_session(with_binding=True)
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "evidence")

    for request_id in ("m4-round-one", "m4-round-two"):
        payload = workflow.prepare_m4(request_id, connection_version=1)
        response = DeliveryHandler._m4_output(payload)
        change = {
            "change_id": "repeatable-change",
            "binding_ids": ["binding-test"],
            "kind": "assumption",
            "description": "新增一条复核记录。",
            "reason": "补足来源追溯。",
            "affects_hard_constraints": False,
        }
        response["proposed_changes"] = [change]
        response["contributions"][0]["proposed_change_ids"] = [change["change_id"]]
        outcome = workflow.invoke_m4(
            payload,
            _StaticClient(response),
            protocol=PROTOCOL_ID,
            configured_model="test",
        )
        workflow.apply_m4(payload, outcome, connection_version=1)
        assert session.final_result["content"]["pending_changes"][-1]["generation_request_id"] == request_id
        assert session.final_result["change_decisions"] == [{
            "generation_request_id": request_id,
            "change_id": "repeatable-change",
            "decision": "pending",
            "decided_by": "workflow",
            "reason": "M4 首次接收，等待用户决定。",
        }]
        if request_id == "m4-round-one":
            decide_m4_change(session, "repeatable-change", "accepted")
        else:
            prior = session.final_archive[-1]
            assert prior["generation_request_id"] == "m4-round-one"
            assert prior["change_decisions"][-1]["decision"] == "accepted"
            decide_m4_change(session, "repeatable-change", "accepted")
            additions = [
                row for row in session.final_result["content"]["accepted_additions"]
                if row.get("source_change_id") == "repeatable-change"
            ]
            assert len(additions) == 2
            assert {row["source_change_generation_request_id"] for row in additions} == {
                "m4-round-one",
                "m4-round-two",
            }


def test_repeated_prepare_m4_is_blocked_until_cancel_or_completion(tmp_path: Path) -> None:
    session = make_session(with_binding=True)
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "evidence")
    first = workflow.prepare_m4("m4-click-one", connection_version=1)

    with pytest.raises(DeliveryWorkflowError, match="M4.*处理中"):
        workflow.prepare_m4("m4-click-two", connection_version=1)

    assert workflow.cancel(first["request_id"])
    assert workflow.prepare_m4("m4-after-cancel", connection_version=1)["request_id"] == "m4-after-cancel"


def test_new_m3_request_supersedes_an_older_in_flight_request(tmp_path: Path) -> None:
    session = make_session()
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "evidence")
    old_payload = workflow.prepare_m3("m3-old", connection_version=1)
    old_outcome = workflow.invoke_m3(
        old_payload,
        _StaticClient(DeliveryHandler._m3_output(old_payload)),
        protocol=PROTOCOL_ID,
        configured_model="test",
    )
    before = session.to_dict()
    workflow.prepare_m3("m3-new", connection_version=1)

    with pytest.raises(DeliveryStaleResponseError):
        workflow.apply_m3(old_payload, old_outcome, connection_version=1)

    assert session.to_dict() == before


class _StaticClient:
    def __init__(self, response: dict):
        self.response = response

    def complete_json(self, system_prompt: str, payload: dict, output_schema: dict) -> ApiResult:
        return ApiResult(json.dumps(self.response, ensure_ascii=False), 1, None, "static-response", "static-model")
