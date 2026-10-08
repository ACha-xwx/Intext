from copy import deepcopy

import pytest

from promptsmith.delivery_workflow import DeliveryWorkflow
from promptsmith.exporter import export_markdown
from promptsmith.finalization import build_final_draft, confirm_final, render_task_prompt
from promptsmith.local_skill_search import search_local_skills
from promptsmith.open_skill_search import _candidate_from_search_result
from promptsmith.session import SessionState
from promptsmith.skill_search import _online_fallback_record, normalize_github_results
from tests.test_delivery_workflow import DeliveryHandler, _StaticClient, make_session


def _session():
    session = make_session()
    session.plan["content"]["unresolved_items"] = []
    session.plan["source_snapshot"] = {"requirements": deepcopy(session.requirements), "unresolved_items": []}
    return session


def _bind(session, record):
    session.set_skill_state(status="selected", basis=session.skill_state["basis"], bindings=[{
        "binding_id": "selected-skill", "skill_id": record["skill_id"],
        "record_hash": record["record_hash"], "record_snapshot": record,
        "key_work_id": "k1", "step_ids": ["s1"], "usage_mode": "method_adaptation",
        "capability_ids": [row["capability_id"] for row in record["capabilities"]],
        "precondition_assessments": [],
    }])


def _integrate(session, tmp_path):
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "calls")
    payload = workflow.prepare_m4("handoff-test", connection_version=1)
    response = DeliveryHandler._m4_output(payload)
    outcome = workflow.invoke_m4(payload, _StaticClient(response), protocol="offline", configured_model="fixture")
    workflow.apply_m4(payload, outcome, connection_version=1)
    confirm_final(session)
    return payload


@pytest.mark.parametrize("kind", ["search_metadata", "api_metadata", "source_content", "source_verified"])
def test_selected_github_skill_survives_m4_copy_export_and_reopen(tmp_path, kind):
    session = _session()
    url = "https://github.com/example/agent-skills/blob/main/skills/spec-writer/SKILL.md"
    source_read = kind in {"source_content", "source_verified"}
    if source_read:
        record = normalize_github_results([{
            "full_name": "example/agent-skills", "path": "skills/spec-writer/SKILL.md",
            "html_url": url, "description": "Write requirements specs.",
        }], query="requirements", key_work_ids=["k1"])[0]["record_snapshot"]
        record.update(name="spec-writer", content_hash_kind="source_content",
                      source_text="---\nname: spec-writer\ndescription: Write specs.\n---\nMap requirements to checks.")
        record["verification"]["source_read"] = True
        record["verification"]["verification_status"] = "source_verified" if kind == "source_verified" else "source_read"
    elif kind == "api_metadata":
        record = _online_fallback_record({
            "repository": "example/agent-skills", "skill_id": "spec-writer",
            "url": url, "name": "spec-writer", "description": "Write requirements specs.",
            "source_index": "skills.sh",
        }, error="raw temporarily unavailable", searched_at="2026-10-08T00:00:00Z")
    else:
        record = _candidate_from_search_result(url, "spec-writer", query="requirements SKILL.md", key_work_id="k1",
                                     searched_at="2026-10-08T00:00:00Z", error="raw temporarily unavailable")["record_snapshot"]
    assert record and record["content_hash_kind"] == ("source_content" if source_read else kind)
    candidate = {"candidate_id": "selected", "skill_id": record["skill_id"], "key_work_id": "k1",
                 "step_ids": ["s1"], "record_hash": record["record_hash"], "record_snapshot": record,
                 "capability_ids": [row["capability_id"] for row in record["capabilities"]]}
    session.set_skill_state(status="candidates_ready", basis=session.skill_state["basis"], bindings=[],
                            candidate_batch={"batch_id": "handoff", "catalog_hash": "a" * 64,
                                             "result": {"candidates": [candidate]}})
    m3 = DeliveryWorkflow(session, evidence_root=tmp_path / "m3").prepare_m3("m3-handoff", connection_version=1)
    assert m3["candidates"][0]["provenance"]["verification_status"] == record["verification"]["verification_status"]
    _bind(session, record)
    payload = _integrate(session, tmp_path)
    assert payload["bindings"][0]["provenance"]["source_read"] is source_read
    prompt = render_task_prompt(session.final_result["canonical_body"])
    assert "使用 Agent Skill：spec-writer" in prompt
    assert url in prompt
    assert "用于关键工作：整理软件报名系统需求规格" in prompt
    assert "应用步骤：整理规格" in prompt
    assert "读取对应的 SKILL.md" in prompt
    assert f"正文已读取：{'是' if source_read else '否'}" in prompt
    assert "已安装：否" in prompt
    if source_read:
        assert "尚未读取、安装或执行" not in prompt
    else:
        assert "信息有限" in prompt
    exported = export_markdown(session, tmp_path / "handoff.md", mode="final").read_text(encoding="utf-8")
    assert prompt in exported
    if source_read:
        assert "尚未读取、安装或执行" not in exported
    reopened = SessionState.from_dict(session.to_dict())
    assert reopened.final_result["status"] == "confirmed"
    assert reopened.final_result["canonical_body"] == session.final_result["canonical_body"]


def test_local_skill_handoff_includes_name_path_and_portability(tmp_path):
    skill = tmp_path / "spec-writer" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text("---\nname: spec-writer\ndescription: 整理软件报名系统需求规格\n---\n核对需求与测试。", encoding="utf-8")
    session = _session()
    record = search_local_skills(session.plan["content"]["key_work"], roots=[tmp_path]).candidates[0]["record_snapshot"]
    _bind(session, record)
    _integrate(session, tmp_path)
    prompt = render_task_prompt(session.final_result["canonical_body"])
    assert "使用 Agent Skill：spec-writer" in prompt
    assert str(skill) in prompt
    assert "用于关键工作：整理软件报名系统需求规格" in prompt
    assert "另一台电脑" in prompt and "提供" in prompt


def test_rebuild_removes_cancelled_skill_identity_and_source():
    from tests.test_exporter import _remote_session

    session = _remote_session()
    original = session.skill_state["bindings"][0]
    second = deepcopy(original)
    second.update(binding_id="second", skill_id="remaining-skill")
    second["record_snapshot"].update(skill_id="remaining-skill", name="remaining-skill",
                                      source_url="https://example.test/remaining/SKILL.md")
    session.set_skill_state(status="selected", basis=session.skill_state["basis"], bindings=[original, second])
    row = deepcopy(session.final_result["content"]["skill_contributions"][0])
    row["origin_binding_ids"] = [original["binding_id"], second["binding_id"]]
    session.final_result = build_final_draft(session, selected_contributions=[row])
    session.set_skill_state(status="selected", basis=session.skill_state["basis"], bindings=[second])
    draft = build_final_draft(session)
    assert "example/remote-skill" not in draft["canonical_body"]
    assert "使用 Agent Skill：remaining-skill" in draft["canonical_body"]
