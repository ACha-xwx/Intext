from __future__ import annotations

from pathlib import Path

import pytest

from promptsmith.exporter import export_markdown
from promptsmith.finalization import (
    DeliveryValidationError,
    build_final_draft,
    confirm_final,
    stage_final_draft,
)
from promptsmith.session import SessionState
from tests.test_final_delivery import (
    _attach_m4_change,
    _m4_change,
    _session_with_bound_prerequisite,
    confirmed_plan_session,
)


def _remote_session():
    session = confirmed_plan_session()
    basis = {
        "task_id": session.task_id,
        "requirement_version": session.requirement_version,
        "plan_id": session.plan["plan_id"],
        "plan_version": session.plan["plan_version"],
    }
    record = {
        "skill_id": "github:example/remote-skill:SKILL.md",
        "record_hash": "r" * 64,
        "origin": "remote",
        "method_adaptation_allowed": True,
        "capabilities": [],
        "adaptation_prerequisites": [
            {"prerequisite_id": "remote-source-review", "description": "用户核对远程来源。"}
        ],
        "source_url": "https://github.com/example/remote-skill/blob/abc123/skills/SKILL.md",
        "repository": "https://github.com/example/remote-skill",
        "fixed_commit": "abc123",
        "content_hash_kind": "api_metadata",
        "content_sha256": "h" * 64,
        "verification": {
            "verification_status": "network_unverified",
            "source_read": False,
            "installed": False,
            "execution_tested": False,
        },
    }
    binding = {
        "binding_id": "binding-remote",
        "skill_id": record["skill_id"],
        "record_hash": record["record_hash"],
        "record_snapshot": record,
        "key_work_id": "k1",
        "step_ids": ["s1"],
        "usage_mode": "method_adaptation",
        "capability_ids": [],
        "precondition_assessments": [
            {
                "prerequisite_id": "remote-source-review",
                "status": "unknown",
                "source": "remote_source_review",
            }
        ],
    }
    session.set_skill_state(
        status="selected",
        basis=basis,
        candidate_batch={"batch_id": "remote-batch", "catalog_hash": "c" * 64, "result": {"candidates": []}},
        bindings=[binding],
    )
    contribution = {
        "binding_id": binding["binding_id"],
        "origin_binding_ids": [binding["binding_id"]],
        "step_id": "s1",
        "method_actions": ["按远程 Skill 方法组织学习步骤。"],
        "planned_inputs": ["已确认需求"],
        "expected_outputs": ["学习方案"],
        "checkpoints": ["核对方法适配边界"],
        "prerequisite_ids": ["remote-source-review"],
        "fallback_actions": ["来源未核对时回到基础方案步骤。"],
    }
    draft = build_final_draft(session, selected_contributions=[contribution])
    stage_final_draft(session, draft, expected_basis=draft["basis"])
    return session


def test_export_final_and_draft_are_readable_and_atomic(tmp_path: Path) -> None:
    session = confirmed_plan_session()
    session.final_result = build_final_draft(session)
    draft_path = export_markdown(session, tmp_path / "draft.md", mode="draft")
    assert draft_path.exists()
    assert "草稿" in draft_path.read_text(encoding="utf-8")
    confirm_final(session)
    final_path = export_markdown(session, tmp_path / "final.md", mode="final")
    text = final_path.read_text(encoding="utf-8")
    assert "最终任务提示" in text
    assert "每天 30 分钟" in text
    assert "电脑是否安装 Python 未知" in text
    assert not list(tmp_path.glob("*.tmp"))


def test_pending_hard_m4_proposal_does_not_block_final_export(tmp_path: Path) -> None:
    session = _session_with_bound_prerequisite("satisfied", [])
    _attach_m4_change(session, _m4_change(hard=True))

    confirm_final(session)
    path = export_markdown(session, tmp_path / "final-with-followup.md", mode="final")

    text = path.read_text(encoding="utf-8")
    assert "增加术语核对记录。" in text
    assert "若要采纳，须先回到上游确认硬约束" in text


def test_final_export_requires_confirmation(tmp_path: Path) -> None:
    session = confirmed_plan_session()
    session.final_result = build_final_draft(session)
    with pytest.raises(ValueError, match="确认"):
        export_markdown(session, tmp_path / "final.md", mode="final")


def test_existing_export_is_preserved_without_explicit_overwrite(tmp_path: Path) -> None:
    session = confirmed_plan_session()
    session.final_result = build_final_draft(session)
    confirm_final(session)
    target = tmp_path / "final.md"
    target.write_text("previous export", encoding="utf-8")

    with pytest.raises(FileExistsError, match="明确允许覆盖"):
        export_markdown(session, target, mode="final")

    assert target.read_text(encoding="utf-8") == "previous export"


def test_export_replace_failure_keeps_previous_file_and_cleans_temporary(tmp_path: Path, monkeypatch) -> None:
    import promptsmith.exporter as exporter_module

    session = confirmed_plan_session()
    session.final_result = build_final_draft(session)
    confirm_final(session)
    target = tmp_path / "final.md"
    target.write_text("previous export", encoding="utf-8")

    def fail_replace(_source, _target):
        raise OSError("simulated export failure")

    monkeypatch.setattr(exporter_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated export failure"):
        export_markdown(session, target, mode="final", overwrite=True)

    assert target.read_text(encoding="utf-8") == "previous export"


def test_not_started_cannot_export_placeholder(tmp_path: Path) -> None:
    session = confirmed_plan_session()
    session.final_result = SessionState().final_result
    target = tmp_path / "empty.md"
    with pytest.raises(DeliveryValidationError, match="尚未生成"):
        export_markdown(session, target, mode="draft")
    assert not target.exists()


def test_remote_provenance_is_present_in_body_and_markdown_export(tmp_path: Path) -> None:
    session = _remote_session()
    body = session.final_result["canonical_body"]
    assert "来源 URL：https://github.com/example/remote-skill/blob/abc123/skills/SKILL.md" in body
    assert "固定提交：abc123" in body
    assert "内容哈希类型：api_metadata" in body
    assert f"内容哈希：{'h' * 64}" in body
    assert "核验状态：network_unverified" in body
    assert "正文已读取：否" in body
    assert "已安装：否" in body
    assert "已执行测试：否" in body
    confirm_final(session)

    target = export_markdown(session, tmp_path / "remote.md", mode="final")
    text = target.read_text(encoding="utf-8")
    for expected in (
        "GitHub 地址：https://github.com/example/remote-skill/blob/abc123/skills/SKILL.md",
        "固定提交：abc123",
        "内容哈希类型：api_metadata",
        f"内容哈希：{'h' * 64}",
        "核验状态：network_unverified",
        "正文已读取：否",
        "已安装：否",
        "已执行测试：否",
    ):
        assert expected in text


def test_final_export_revalidates_current_basis_before_write(tmp_path: Path) -> None:
    session = confirmed_plan_session()
    session.final_result = build_final_draft(session)
    confirm_final(session)
    target = tmp_path / "stale.md"
    session.plan["plan_version"] += 1
    with pytest.raises(DeliveryValidationError):
        export_markdown(session, target, mode="final")
    assert not target.exists()
    assert not target.with_name(f".{target.name}.tmp").exists()


def test_noncritical_m4_followup_is_in_formal_export(tmp_path: Path) -> None:
    session = _session_with_bound_prerequisite("satisfied", [])
    _attach_m4_change(session, _m4_change())

    confirm_final(session)
    target = export_markdown(session, tmp_path / "with-followup.md", mode="final")
    text = target.read_text(encoding="utf-8")

    assert "使用时补充的后置事项" in text
    assert "增加术语核对记录。" in text
