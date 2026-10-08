from pathlib import Path

from promptsmith.local_skill_search import search_local_skills


def _skill(path: Path, name: str, description: str, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n",
        encoding="utf-8",
    )


def test_generic_testing_boilerplate_does_not_match_unrelated_domains(tmp_path: Path) -> None:
    _skill(
        tmp_path / "tdd" / "SKILL.md",
        "test-driven-development",
        "Use when implementing code or fixing bugs.",
        "Write a failing test before implementation.",
    )
    _skill(
        tmp_path / "slides" / "SKILL.md",
        "Presentations",
        "Create and edit PowerPoint slides and decks.",
        "Follow the visual design and slide layout guidance.",
    )
    _skill(
        tmp_path / "excel" / "SKILL.md",
        "excel-live-control",
        "Control an active Microsoft Excel workbook.",
        "Inspect workbook values and formulas.",
    )
    _skill(
        tmp_path / "browser" / "SKILL.md",
        "browser",
        "Open, inspect, and test websites in a browser.",
        "Use browser tabs and verify the page after actions.",
    )
    _skill(
        tmp_path / "humanizer" / "SKILL.md",
        "humanizer-zh",
        "Remove AI writing traces and edit natural language text.",
        "Rewrite paragraphs and polish the wording.",
    )
    _skill(
        tmp_path / "openai" / "SKILL.md",
        "openai-docs",
        "Use for OpenAI and Codex API documentation.",
        "Search official model and SDK references.",
    )

    result = search_local_skills(
        [{"key_work_id": "code", "title": "编写测试并修复代码问题", "goal": "开发软件", "step_ids": []}],
        task_text="编写测试并修复代码问题",
        roots=[tmp_path],
    )

    assert result.status == "ok"
    assert [candidate["name"] for candidate in result.candidates] == [
        "test-driven-development"
    ]


def test_identical_skill_content_is_returned_once_across_installation_roots(tmp_path: Path) -> None:
    body = "Write a failing test before implementing code."
    _skill(tmp_path / "active" / "SKILL.md", "test-driven-development", "Implement code and fix bugs.", body)
    _skill(tmp_path / "cache" / "SKILL.md", "test-driven-development", "Implement code and fix bugs.", body)

    result = search_local_skills(
        [{"key_work_id": "code", "title": "编写测试并修复代码问题", "goal": "开发软件", "step_ids": []}],
        task_text="编写测试并修复代码问题",
        roots=[tmp_path],
    )

    assert result.scanned_files == 2
    assert result.matched_files == 1
    assert len(result.candidates) == 1
    assert result.candidates[0]["name"] == "test-driven-development"


def test_named_domain_skill_is_kept_when_the_task_explicitly_requests_that_domain(tmp_path: Path) -> None:
    _skill(tmp_path / "openai" / "SKILL.md", "openai-docs", "Use OpenAI API and model documentation.")
    _skill(tmp_path / "browser" / "SKILL.md", "browser", "Inspect and test websites in a browser.")

    openai = search_local_skills(
        [{"key_work_id": "api", "title": "调用 OpenAI API", "goal": "查阅模型文档", "step_ids": []}],
        task_text="调用 OpenAI API 并查阅模型文档",
        roots=[tmp_path],
    )
    assert [candidate["name"] for candidate in openai.candidates] == ["openai-docs"]

    browser = search_local_skills(
        [{"key_work_id": "web", "title": "测试浏览器网页", "goal": "验证页面行为", "step_ids": []}],
        task_text="测试浏览器网页并验证页面行为",
        roots=[tmp_path],
    )
    assert [candidate["name"] for candidate in browser.candidates] == ["browser"]


def test_candidate_binds_to_best_matching_key_work(tmp_path: Path) -> None:
    _skill(
        tmp_path / "code" / "SKILL.md",
        "code-review",
        "Review code and test bug fixes.",
    )
    _skill(
        tmp_path / "paper" / "SKILL.md",
        "paper-writing",
        "Write academic papers and review citations.",
    )

    result = search_local_skills(
        [
            {"key_work_id": "slides", "title": "撰写学术论文", "goal": "核对引用", "step_ids": ["p1"]},
            {"key_work_id": "code", "title": "编写测试并修复代码问题", "goal": "开发软件", "step_ids": ["c1"]},
        ],
        roots=[tmp_path],
    )

    by_name = {candidate["name"]: candidate for candidate in result.candidates}
    assert by_name["paper-writing"]["key_work_id"] == "slides"
    assert by_name["paper-writing"]["step_ids"] == ["p1"]
    assert by_name["code-review"]["key_work_id"] == "code"
    assert by_name["code-review"]["step_ids"] == ["c1"]
