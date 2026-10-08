from __future__ import annotations

import json
from pathlib import Path

import pytest

from promptsmith.skill_catalog import SkillCatalog, SkillCatalogError, _record_hash


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "resources" / "skill_catalog" / "catalog_v0.1.json"


def test_catalog_loads_real_records_and_verifies_source_hashes() -> None:
    catalog = SkillCatalog.load(CATALOG, source_root=ROOT, verify_sources=True)

    assert catalog.schema_version == "catalog.v0.1"
    assert [row["skill_id"] for row in catalog.records] == [
        "to-spec",
        "domain-modeling",
        "goal-prompt",
    ]
    assert catalog.snapshot_hash
    verification = catalog.verify_sources(ROOT)
    assert all(row["source_exists"] for row in verification.values())
    assert all(row["hash_matches"] for row in verification.values())
    assert all(row["record_hash_matches"] for row in verification.values())


def test_default_catalog_path_uses_project_resource_root() -> None:
    catalog = SkillCatalog.load()

    assert catalog.path == CATALOG.resolve()


def test_legacy_work_signals_explain_matches_without_borrowing_task_context(tmp_path: Path) -> None:
    payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    record = payload["records"][0]
    record["capabilities"] = [{
        "capability_id": "legacy-spec", "work_signals": ["需求规格"],
    }]
    record["record_hash"] = _record_hash(record)
    payload["records"] = [record]
    path = tmp_path / "legacy-catalog.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    catalog = SkillCatalog.load(path)

    result = catalog.match({"key_work_id": "k1", "title": "需求规格整理"})
    assert result.status == "ok"
    candidate = result.candidates[0]
    assert "关键工作：需求规格" in candidate["match_reason"]
    assert candidate["match_evidence"][0]["matched_sources"] == [
        {"source": "key_work", "label": "关键工作", "matched_terms": ["需求规格"]}
    ]
    assert catalog.match(
        {"key_work_id": "k2", "title": "撰写通知"}, context_text="需求规格"
    ).status == "no_match"


def test_matching_is_deterministic_and_bounded() -> None:
    catalog = SkillCatalog.load(CATALOG, source_root=ROOT, verify_sources=True)
    work = {
        "key_work_id": "kw-spec",
        "title": "整理软件开发规格",
        "goal": "把需求、用户故事、实现决定和测试策略整理成规格文档",
        "inputs": ["已确认需求", "范围边界"],
        "outputs": ["本地规格文档"],
        "checkpoints": ["每条要求有对应测试决定"],
        "step_ids": ["step-spec"],
    }

    first = catalog.match([work])
    second = catalog.match([work])

    assert first.status == "ok"
    assert first.to_dict() == second.to_dict()
    assert len(first.candidates) <= 3
    assert first.candidates[0]["skill_id"] == "to-spec"
    assert first.candidates[0]["key_work_id"] == "kw-spec"
    assert first.candidates[0]["selection_allowed"] is True
    assert first.candidates[0]["step_ids"] == ["step-spec"]
    assert first.candidates[0]["record_hash"]


def test_catalog_record_is_selectable_without_shipping_original_source_files() -> None:
    catalog = SkillCatalog.load(CATALOG, verify_sources=False)
    work = {
        "key_work_id": "kw-spec",
        "title": "整理软件开发规格",
        "goal": "把需求、用户故事、实现决定和测试策略整理成规格文档",
        "inputs": ["已确认需求"],
        "outputs": ["本地规格文档"],
        "step_ids": ["s1"],
    }

    result = catalog.match([work])

    assert result.status == "ok"
    assert result.candidates[0]["verification_status"] == "catalog_recorded"
    assert result.candidates[0]["selection_allowed"] is True


def test_writing_notice_has_no_false_positive_match() -> None:
    catalog = SkillCatalog.load(CATALOG, source_root=ROOT, verify_sources=True)
    work = {
        "key_work_id": "kw-notice",
        "title": "整理用户需求并撰写摄影社招新通知",
        "goal": "写一则不超过500字、自然语气的微信群通知",
        "inputs": ["活动时间", "报名方式"],
        "outputs": ["微信群通知"],
        "checkpoints": ["活动、报名、咨询信息齐全"],
        "step_ids": ["step-notice"],
    }

    result = catalog.match([work])

    assert result.status == "no_match"
    assert result.candidates == []
    assert result.unmatched_key_work_ids == ["kw-notice"]


def test_domain_modeling_matches_explicit_domain_terms_and_relationship_work() -> None:
    catalog = SkillCatalog.load(CATALOG, source_root=ROOT, verify_sources=True)
    work = {
        "key_work_id": "kw-domain",
        "title": "澄清报名系统领域术语与实体关系",
        "goal": "形成成员、活动、报名之間的关系说明和术语表",
        "inputs": ["已确认的报名流程"],
        "outputs": ["领域术语表", "实体关系说明"],
        "checkpoints": ["业务对象和关系均有来源说明"],
    }

    result = catalog.match([work])

    assert result.status == "ok"
    candidate = next(row for row in result.candidates if row["skill_id"] == "domain-modeling")
    assert candidate["selection_allowed"] is True
    assert candidate["matched_work_signals"]
    assert "领域" in candidate["match_reason"] or "实体关系" in candidate["match_reason"]


def test_generic_goal_checklist_does_not_match_goal_prompt_from_weak_goal_term() -> None:
    catalog = SkillCatalog.load(CATALOG, source_root=ROOT, verify_sources=True)
    work = {
        "key_work_id": "kw-checklist",
        "title": "整理活动执行清单",
        "goal": "明确目标、完成条件、责任人和时间安排",
        "inputs": ["活动安排"],
        "outputs": ["一页执行清单"],
        "checkpoints": ["每项工作有负责人和完成条件"],
    }

    result = catalog.match([work])

    assert result.status == "no_match"
    assert all(row["skill_id"] != "goal-prompt" for row in result.candidates)
    assert result.unmatched_key_work_ids == ["kw-checklist"]


def test_software_spec_candidate_explains_the_specific_matching_work() -> None:
    catalog = SkillCatalog.load(CATALOG, source_root=ROOT, verify_sources=True)
    work = {
        "key_work_id": "kw-registration-spec",
        "title": "整理软件报名系统规格",
        "goal": "把已确认的软件需求整理成用户故事、实现决定和测试决定",
        "inputs": ["已确认的软件功能需求", "范围边界"],
        "outputs": ["本地软件规格文档"],
        "checkpoints": ["每条软件要求有对应测试决定"],
    }

    result = catalog.match([work])

    assert result.status == "ok"
    candidate = next(row for row in result.candidates if row["skill_id"] == "to-spec")
    assert candidate["selection_allowed"] is True
    assert candidate["matched_work_signals"]
    assert "软件" in candidate["match_reason"] or "报名系统" in candidate["match_reason"]
    assert candidate["suitable_work"]
    assert candidate["unsuitable_work"]


def test_task_context_does_not_replace_required_specification_work_signal() -> None:
    catalog = SkillCatalog.load(CATALOG, source_root=ROOT, verify_sources=True)
    work = {
        "key_work_id": "kw-general-spec",
        "title": "课程内容整理",
        "goal": "将课程目标和章节整理成教学材料。",
        "inputs": ["课程材料"],
        "outputs": ["教学材料"],
        "checkpoints": ["内容完整"],
    }

    result = catalog.match(
        [work],
        context_text="为社团活动报名工具整理软件需求规格。",
    )

    assert all(row["skill_id"] != "to-spec" for row in result.candidates)
    assert result.unmatched_key_work_ids == ["kw-general-spec"]


def test_software_context_and_generic_scope_do_not_make_notice_specification_work() -> None:
    catalog = SkillCatalog.load(CATALOG)
    result = catalog.match(
        {"key_work_id": "kw-notice", "title": "活动通知编写",
         "inputs": ["活动时间、地点、报名截止日", "范围边界"],
         "outputs": ["一段微信群文字"]},
        context_text="为社团活动报名工具整理需求规格，并撰写活动通知。",
    )
    assert result.status == "no_match"
    assert result.candidates == []


def test_confirmed_registration_tool_context_matches_each_d2_spec_work() -> None:
    catalog = SkillCatalog.load(CATALOG, source_root=ROOT, verify_sources=True)
    works = [
        {
            "key_work_id": "k1",
            "title": "功能需求规格编写",
            "goal": "把成员、管理员功能与报名规则整理为结构化需求。",
            "inputs": ["已确认需求", "范围边界"],
            "outputs": ["功能需求规格初稿"],
            "checkpoints": ["每项功能和规则均有对应需求条目"],
        },
        {
            "key_work_id": "k2",
            "title": "测试要点编写",
            "goal": "为已确认的功能和规则整理可核对的测试要点。",
            "inputs": ["功能需求规格初稿"],
            "outputs": ["测试要点初稿"],
            "checkpoints": ["测试要点与需求条目一一对应"],
        },
        {
            "key_work_id": "k3",
            "title": "开发者可用性与演示标准复核",
            "goal": "复核规格和测试要点能否支撑开发者与比赛演示。",
            "inputs": ["需求规格", "测试要点"],
            "outputs": ["复核意见与修订稿"],
            "checkpoints": ["核心流程可支撑演示", "详略程度符合比赛定位"],
        },
    ]
    task_context = "为社团活动报名工具整理可供开发者使用的需求规格与测试要点。"

    result = catalog.match(works, context_text=task_context)

    assert result.status == "ok"
    assert {row["key_work_id"] for row in result.candidates if row["skill_id"] == "to-spec"} == {
        "k1",
        "k2",
        "k3",
    }
    for candidate in result.candidates:
        if candidate["skill_id"] != "to-spec":
            continue
        software_group = next(
            group for group in candidate["match_evidence"] if group["group_id"] == "software_context"
        )
        task_evidence = next(source for source in software_group["matched_sources"] if source["source"] == "task_context")
        assert "报名工具" in task_evidence["matched_terms"]
        assert "任务描述" in candidate["match_reason"]


@pytest.mark.parametrize(
    "title,goal",
    [
        ("应用数学课程规格编写", "将应用数学课程目标、章节与测试安排整理成规格"),
        ("课程应用需求规格编写", "整理课程应用需求与测试规格"),
        ("网站内容规格整理", "整理网站栏目和内容规格"),
        ("教学工具需求规格编写", "整理教学工具的课程需求规格"),
        ("文档开发规格整理", "整理文档编制规格与检查要点"),
    ],
)
def test_general_course_or_document_spec_work_does_not_match_to_spec(title: str, goal: str) -> None:
    catalog = SkillCatalog.load(CATALOG, source_root=ROOT, verify_sources=True)
    work = {
        "key_work_id": "kw-general-spec",
        "title": title,
        "goal": goal,
        "inputs": ["课程或文档材料"],
        "outputs": ["规格说明"],
        "checkpoints": ["范围边界明确"],
    }

    result = catalog.match([work], context_text="整理课程或文档材料并形成可复核的规格说明。")

    assert all(row["skill_id"] != "to-spec" for row in result.candidates)
    assert result.unmatched_key_work_ids == ["kw-general-spec"]


def test_catalog_records_trace_fixed_sources_and_report_five_verification_levels() -> None:
    catalog = SkillCatalog.load(CATALOG, source_root=ROOT, verify_sources=True)
    expected_repositories = {
        "to-spec": ("https://github.com/mattpocock/skills", "c55ee46073ed923f86ce59a5eb3b6d895095d1b7"),
        "domain-modeling": ("https://github.com/mattpocock/skills", "c55ee46073ed923f86ce59a5eb3b6d895095d1b7"),
        "goal-prompt": ("https://github.com/trailofbits/skills", "123037ec8aed26f0d86327cc39137ee5043e5deb"),
    }

    for skill_id, (repository, commit) in expected_repositories.items():
        record = catalog.get(skill_id)
        assert record is not None
        assert record["repository"] == repository
        assert record["fixed_commit"] == commit
        assert record["source_url"].startswith(f"{repository}/blob/{commit}/")
        assert record["local_snapshot_path"] == record["source_path"]
        assert record["license"]["repository"] == repository
        assert record["license"]["fixed_commit"] == commit
        assert record["license"]["evidence_url"].startswith(f"{repository}/blob/{commit}/")

        levels = catalog.verify_sources(ROOT)[skill_id]["verification_levels"]
        assert levels == {
            "catalog_recorded": "verified",
            "local_text_checked": "verified",
            "fixed_source_traceable": "verified",
            "host_dependencies_available": "unknown",
            "execution_tested": "not_tested",
        }

        persisted = record["verification"]
        assert persisted["upstream_rechecked"] is False
        assert persisted["upstream_rechecked_at"] is None
        assert persisted["host_dependencies_available"] == "unknown"
        assert persisted["installed"] is False
        assert persisted["execution_tested"] is False


def test_empty_catalog_is_distinct_from_no_match(tmp_path: Path) -> None:
    empty = tmp_path / "empty.json"
    empty.write_text(
        json.dumps({"schema_version": "catalog.v0.1", "catalog_id": "empty", "records": []}),
        encoding="utf-8",
    )

    catalog = SkillCatalog.load(empty, verify_sources=False)

    result = catalog.match(
        [{"key_work_id": "kw1", "title": "任意工作", "goal": "做事", "step_ids": ["s1"]}]
    )
    assert result.status == "empty"
    assert result.unmatched_key_work_ids == ["kw1"]


def test_malformed_catalog_is_rejected_without_falling_back(tmp_path: Path) -> None:
    malformed = tmp_path / "bad.json"
    malformed.write_text("{not-json", encoding="utf-8")

    with pytest.raises(SkillCatalogError, match="JSON") as captured:
        SkillCatalog.load(malformed)

    assert captured.value.code == "invalid_json"


def test_missing_source_is_reported_without_marking_skill_verified(tmp_path: Path) -> None:
    catalog = SkillCatalog.load(CATALOG, source_root=tmp_path, verify_sources=True)

    verification = catalog.verify_sources(tmp_path)

    assert all(not row["source_exists"] for row in verification.values())
    assert all(not row["hash_matches"] for row in verification.values())
    assert all(row["verification_status"] == "source_unavailable" for row in verification.values())
    assert all(row["installed"] is False for row in verification.values())
    assert all(row["execution_tested"] is False for row in verification.values())


def test_missing_source_candidates_are_visible_but_not_selectable(tmp_path: Path) -> None:
    catalog = SkillCatalog.load(CATALOG, source_root=tmp_path, verify_sources=True)
    work = {
        "key_work_id": "kw-spec",
        "title": "整理软件开发规格",
        "goal": "整理需求和用户故事为本地规格文档",
        "inputs": ["已确认需求"],
        "outputs": ["本地规格文档"],
        "step_ids": ["s1"],
    }

    result = catalog.match([work])

    assert result.candidates
    assert all(row["verification_status"] == "source_unavailable" for row in result.candidates)
    assert all(row["selection_allowed"] is False for row in result.candidates)


def test_changed_source_hash_is_reported_and_blocks_selection(tmp_path: Path) -> None:
    source = tmp_path / "resources" / "skill_catalog" / "sources" / "mattpocock_to-spec.md"
    source.parent.mkdir(parents=True)
    source.write_text("changed source", encoding="utf-8")
    catalog = SkillCatalog.load(CATALOG, source_root=tmp_path, verify_sources=True)
    verification = catalog.verify_sources(tmp_path)

    assert verification["to-spec"]["verification_status"] == "source_mismatch"
    work = {
        "key_work_id": "kw-spec",
        "title": "整理软件开发规格",
        "goal": "整理需求为开发规格文档",
        "inputs": ["已确认需求"],
        "outputs": ["本地规格文档"],
        "step_ids": ["s1"],
    }
    result = catalog.match([work])
    to_spec = next(row for row in result.candidates if row["skill_id"] == "to-spec")
    assert to_spec["verification_status"] == "source_mismatch"
    assert to_spec["selection_allowed"] is False


def test_incompatible_environment_is_marked_and_not_selectable() -> None:
    catalog = SkillCatalog.load(CATALOG, source_root=ROOT, verify_sources=True)
    work = {
        "key_work_id": "kw-spec",
        "title": "整理软件开发规格",
        "goal": "整理需求和用户故事为本地规格文档",
        "inputs": ["已确认需求"],
        "outputs": ["本地规格文档"],
        "step_ids": ["s1"],
    }

    result = catalog.match([work], target_environment={"forbidden_actions": ["发布 issue"]})

    assert result.status == "incompatible"
    assert result.candidates
    assert all(row["selection_allowed"] is False for row in result.candidates)
    assert all(row["compatibility"] == "incompatible" for row in result.candidates)


def _write_catalog_variant(source: Path, destination: Path, *, changed_skill_id: str | None = None, remove_skill_id: str | None = None) -> None:
    payload = json.loads(source.read_text(encoding="utf-8"))
    records = []
    for record in payload["records"]:
        if record["skill_id"] == remove_skill_id:
            continue
        record = dict(record)
        if record["skill_id"] == changed_skill_id:
            record["description"] = record["description"] + "（目录更新）"
            record["record_hash"] = _record_hash(record)
        records.append(record)
    payload["records"] = records
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _binding_from_catalog(catalog: SkillCatalog, skill_id: str = "to-spec") -> dict:
    record = catalog.get(skill_id)
    assert record is not None
    return {"binding_id": "binding-1", "skill_id": skill_id, "record_hash": record["record_hash"], "record_snapshot": record}


def test_binding_catalog_consistency_accepts_unchanged_and_unrelated_updates(tmp_path: Path) -> None:
    original_path = tmp_path / "original.json"
    original_path.write_text(CATALOG.read_text(encoding="utf-8"), encoding="utf-8")
    original = SkillCatalog.load(original_path)
    binding = _binding_from_catalog(original)

    unchanged = original.assess_bindings([binding])
    assert unchanged["status"] == "ok"
    assert unchanged["affected_binding_ids"] == []

    unrelated_path = tmp_path / "unrelated.json"
    _write_catalog_variant(original_path, unrelated_path, changed_skill_id="domain-modeling")
    unrelated = SkillCatalog.load(unrelated_path)
    result = unrelated.assess_bindings([binding])
    assert result["status"] == "ok"
    assert result["affected_binding_ids"] == []


def test_binding_catalog_consistency_detects_changed_or_missing_selected_record(tmp_path: Path) -> None:
    original_path = tmp_path / "original.json"
    original_path.write_text(CATALOG.read_text(encoding="utf-8"), encoding="utf-8")
    original = SkillCatalog.load(original_path)
    binding = _binding_from_catalog(original)

    changed_path = tmp_path / "changed.json"
    _write_catalog_variant(original_path, changed_path, changed_skill_id="to-spec")
    changed = SkillCatalog.load(changed_path)
    changed_result = changed.assess_bindings([binding])
    assert changed_result["status"] == "stale"
    assert changed_result["affected_binding_ids"] == ["binding-1"]

    missing_path = tmp_path / "missing.json"
    _write_catalog_variant(original_path, missing_path, remove_skill_id="to-spec")
    missing = SkillCatalog.load(missing_path)
    missing_result = missing.assess_bindings([binding])
    assert missing_result["status"] == "stale"
    assert missing_result["affected_binding_ids"] == ["binding-1"]
