from __future__ import annotations

from pathlib import Path

from promptsmith.local_skill_search import search_local_skill_files, search_local_skills


def _write_skill(path: Path, *, name: str, description: str, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return path


def _work(*, work_id: str = "k1", title: str = "整理课程学习计划") -> dict:
    return {
        "key_work_id": work_id,
        "title": title,
        "goal": "为学习者编写可执行的课程计划",
        "step_ids": ["s1"],
        "inputs": ["学习目标"],
        "outputs": ["课程计划"],
        "actions": ["整理学习步骤"],
        "checkpoints": ["步骤可执行"],
    }


def test_discovers_skill_md_and_returns_m3_compatible_local_candidate(tmp_path: Path) -> None:
    path = _write_skill(
        tmp_path / "course-planning" / "SKILL.md",
        name="course-planning",
        description="帮助整理课程学习计划和练习。",
        body="# Course planning\nCreate a step-by-step lesson plan with exercises.",
    )

    result = search_local_skills([_work()], task_text="我想创建一份课程学习计划", roots=[tmp_path])

    assert result.status == "ok"
    assert result.scanned_count == 1
    assert result.catalog_hash and len(result.catalog_hash) == 64
    assert not result.errors
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate["origin"] == "local_file"
    assert candidate["source_kind"] == "local_file"
    assert candidate["selection_allowed"] is True
    assert candidate["key_work_id"] == "k1"
    assert candidate["step_ids"] == ["s1"]
    assert candidate["source_path"] == str(path.resolve())
    assert candidate["local_snapshot_path"] == str(path.resolve())
    assert candidate["record_snapshot"]["origin"] == "local_file"
    assert candidate["record_snapshot"]["verification"]["verification_status"] == "source_verified"
    assert candidate["record_snapshot"]["local_source_snapshot_sha256"]
    assert candidate["capability_ids"]


def test_duplicate_roots_and_symlink_paths_do_not_duplicate_candidates(tmp_path: Path) -> None:
    skill = _write_skill(
        tmp_path / "skills" / "writing" / "SKILL.md",
        name="writing",
        description="写作和文档整理。",
        body="# Writing\nDraft and edit documentation.",
    )
    # The same root is intentionally supplied twice; implementations may also
    # encounter the same file through an overlapping parent root.
    result = search_local_skills([_work(title="整理项目文档")], roots=[tmp_path, tmp_path, skill.parent])

    assert result.scanned_count == 1
    assert len(result.candidates) == 1
    assert result.candidates[0]["record_snapshot"]["source_path"] == str(skill.resolve())


def test_malformed_or_unreadable_skill_is_reported_without_aborting_scan(tmp_path: Path) -> None:
    _write_skill(
        tmp_path / "good" / "SKILL.md",
        name="good",
        description="测试方法。",
        body="# Good\nTesting and verification.",
    )
    bad = tmp_path / "bad" / "SKILL.md"
    bad.parent.mkdir()
    bad.write_bytes(b"\xff\xfe\x00")

    result = search_local_skills([_work(title="测试软件")], roots=[tmp_path])

    assert result.scanned_count == 2
    assert len(result.candidates) == 1
    assert result.candidates[0]["record_snapshot"]["name"] == "good"
    assert result.errors


def test_chinese_task_matches_english_skill_from_body_without_matching_name(tmp_path: Path) -> None:
    _write_skill(
        tmp_path / "method-one" / "SKILL.md",
        name="method-one",
        description="A practical workflow.",
        body="# Study design\nBuild a beginner curriculum with lessons, exercises, and review checkpoints.",
    )
    _write_skill(
        tmp_path / "deployment" / "SKILL.md",
        name="deployment",
        description="Deploy a website to a cloud service.",
        body="# Deployment\nPublish sites with hosting configuration.",
    )

    result = search_local_skill_files(
        [_work()], context_text="为零基础学习者安排七天入门学习和练习", roots=[tmp_path]
    )

    assert result.scanned_files == 2
    assert result.matched_files == 1
    assert [row["record_snapshot"]["name"] for row in result.candidates] == ["method-one"]
    assert "curriculum" in result.candidates[0]["record_snapshot"]["capabilities"][0]["summary"]


def test_frontmatter_folded_description_and_title_fallback_are_readable(tmp_path: Path) -> None:
    path = tmp_path / "paper" / "SKILL.md"
    path.parent.mkdir()
    path.write_text(
        "---\nname: paper-writer\ndescription: >-\n  Write academic papers.\n  Review references and citations.\n---\n\n# Paper writer\nUse literature evidence.\n",
        encoding="utf-8",
    )
    title_only = tmp_path / "notes" / "SKILL.md"
    title_only.parent.mkdir()
    title_only.write_text("# 学习笔记\n\n整理学习材料和课程内容。\n", encoding="utf-8")

    result = search_local_skills([_work()], roots=[tmp_path])
    names = {row["record_snapshot"]["name"]: row for row in result.candidates}

    assert "学习笔记" in names
    paper_result = search_local_skills([_work(title="撰写学术论文并核对引用")], roots=[tmp_path])
    paper = next(row for row in paper_result.candidates if row["record_snapshot"]["name"] == "paper-writer")
    assert paper["record_snapshot"]["description"] == "Write academic papers. Review references and citations."


def test_catalog_hash_is_deterministic_and_changes_when_source_content_changes(tmp_path: Path) -> None:
    path = _write_skill(tmp_path / "notes" / "SKILL.md", name="notes", description="学习笔记。", body="整理课程。")
    first = search_local_skills([_work()], roots=[tmp_path])
    again = search_local_skills([_work()], roots=[tmp_path])
    path.write_text(path.read_text(encoding="utf-8") + "新增练习检查。", encoding="utf-8")
    changed = search_local_skills([_work()], roots=[tmp_path])

    assert first.catalog_hash == again.catalog_hash
    assert first.candidates == again.candidates
    assert first.catalog_hash != changed.catalog_hash
    assert first.candidates[0]["record_hash"] != changed.candidates[0]["record_hash"]


def test_candidate_limit_is_bounded_and_records_allowed_step_ids(tmp_path: Path) -> None:
    for index in range(5):
        _write_skill(
            tmp_path / f"course-{index}" / "SKILL.md",
            name=f"course-{index}", description="学习课程计划。", body="课程练习和复习。",
        )
    result = search_local_skills([_work(), _work(work_id="k2")], roots=[tmp_path], max_candidates=3)

    assert result.scanned_files == 5
    assert len(result.candidates) == 3
    assert all(row["step_ids"] == ["s1"] for row in result.candidates)
    assert len({row["candidate_id"] for row in result.candidates}) == 3


def test_default_search_returns_all_matching_local_skills(tmp_path: Path) -> None:
    for index in range(12):
        _write_skill(
            tmp_path / f"course-{index}" / "SKILL.md",
            name=f"course-{index}", description="学习课程计划。", body="课程练习和复习。",
        )

    result = search_local_skills([_work()], roots=[tmp_path])

    assert result.matched_files == 12
    assert len(result.candidates) == 12


def test_default_roots_scan_known_skill_locations_and_ignore_other_home_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)
    _write_skill(tmp_path / ".codex" / "skills" / "notes" / "SKILL.md", name="notes", description="学习笔记。", body="课程练习。")
    _write_skill(tmp_path / ".agents" / "skills" / "course" / "SKILL.md", name="course", description="学习课程计划。", body="课程练习。")
    _write_skill(tmp_path / ".codex" / "plugins" / "cache" / "publisher" / "plugin" / "1.0" / "skills" / "study" / "SKILL.md", name="study", description="学习课程计划。", body="课程练习。")
    _write_skill(tmp_path / "unrelated-downloads" / "large-tree" / "SKILL.md", name="unrelated", description="学习课程计划。", body="课程练习。")

    result = search_local_skills([_work()])

    assert result.scanned_files == 3
    assert {row["record_snapshot"]["name"] for row in result.candidates} == {"notes", "course", "study"}


def test_symlinked_directory_is_not_traversed(tmp_path: Path) -> None:
    import pytest

    outside = tmp_path / "outside"
    _write_skill(outside / "course" / "SKILL.md", name="course", description="课程学习计划。", body="练习。")
    root = tmp_path / "skills"
    root.mkdir()
    try:
        (root / "linked").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks requires a Windows privilege on this host.")

    result = search_local_skills([_work()], roots=[root])

    assert result.scanned_files == 0
    assert result.candidates == []
