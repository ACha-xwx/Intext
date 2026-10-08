import json
from io import BytesIO

import pytest

from promptsmith.open_skill_search import generate_skill_search_queries, search_open_web_skills


def test_web_search_does_not_return_ordinary_websites_as_agent_skills():
    page_url = "https://slides.example.test/ai-presentation-tool"

    def fetch(request, timeout):
        if request.full_url.startswith("https://search.example.test/api?"):
            return BytesIO(json.dumps({"results": [{"url": page_url, "title": "AI Presentation Maker"}]}).encode())
        if request.full_url == page_url:
            return BytesIO(b"<html><h1>AI Presentation Maker</h1><p>Create slides online.</p></html>")
        raise AssertionError(request.full_url)

    result = search_open_web_skills(
        [{"key_work_id": "slides", "title": "制作培训演示文稿"}],
        search_url="https://search.example.test/api?q={query}",
        queries=["presentation agent skill SKILL.md"],
        opener=fetch,
    )

    assert result.candidates == []
    assert result.status == "no_match"
    assert result.diagnostics["discovered_count"] == 0


def test_search_planning_targets_agent_skill_artifacts():
    calls = []

    class QueryClient:
        def complete_json(self, prompt, payload, schema):
            calls.append((prompt, payload, schema))
            return type("Result", (), {"content": json.dumps({"queries": ["teaching Agent Skill SKILL.md"]})})()

    queries = generate_skill_search_queries(
        [{"key_work_id": "lesson", "title": "讲解分部积分法"}],
        client=QueryClient(),
    )

    assert queries == ["teaching Agent Skill SKILL.md"]
    assert "AI Agent" in calls[0][0]
    assert "SKILL.md" in calls[0][0]
    assert "普通方法" in calls[0][0]
    assert "普通网站" in calls[0][0]


def test_fallback_web_queries_include_agent_skill_artifact_marker():
    queries = generate_skill_search_queries(
        [{"key_work_id": "lesson", "title": "讲解分部积分法"}],
    )

    assert queries
    assert all("skill.md" in query.casefold() for query in queries)
    assert all("agent" in query.casefold() and "skill" in query.casefold() for query in queries)


def test_explicit_web_queries_are_also_scoped_to_agent_skills():
    result = search_open_web_skills(
        [{"key_work_id": "lesson", "title": "讲解分部积分法"}],
        queries=["teaching"],
        opener=lambda *_args, **_kwargs: BytesIO(b"<rss><channel></channel></rss>"),
    )

    assert result.diagnostics["queries"] == ["teaching AI Agent Skill SKILL.md"]


def test_default_web_search_reads_bing_rss_skill_result():
    blob_url = "https://github.com/example/lesson/blob/main/SKILL.md"
    raw_url = "https://raw.githubusercontent.com/example/lesson/main/SKILL.md"
    source = b"---\nname: teaching\ndescription: Explain ideas clearly.\n---\nUse examples.\n"
    requested = []

    def fetch(request, timeout):
        requested.append(request.full_url)
        if request.full_url.startswith("https://www.bing.com/search?format=rss&q="):
            return BytesIO((
                '<?xml version="1.0"?><rss><channel><item><title>Teaching Skill</title>'
                f'<link>{blob_url}</link></item></channel></rss>'
            ).encode())
        if request.full_url == raw_url:
            return BytesIO(source)
        raise AssertionError(request.full_url)

    result = search_open_web_skills(
        [{"key_work_id": "lesson", "title": "讲解分部积分法"}],
        queries=["teaching SKILL.md"], opener=fetch,
    )

    assert [row["name"] for row in result.candidates] == ["teaching"]
    assert result.diagnostics["search_engines"] == ["Bing"]
    assert any(url.startswith("https://www.bing.com/search?format=rss&q=") for url in requested)


def test_default_web_search_falls_back_when_bing_returns_challenge():
    blob_url = "https://github.com/example/lesson/blob/main/SKILL.md"
    raw_url = "https://raw.githubusercontent.com/example/lesson/main/SKILL.md"
    source = b"---\nname: teaching\ndescription: Explain ideas clearly.\n---\nUse examples.\n"
    requested = []

    def fetch(request, timeout):
        requested.append(request.full_url)
        if request.full_url.startswith("https://www.bing.com/search?"):
            return BytesIO(b"<html><title>Verify you are human</title></html>")
        if request.full_url.startswith("https://html.duckduckgo.com/html/?q="):
            return BytesIO(f'<html><a href="{blob_url}">Teaching Skill</a></html>'.encode())
        if request.full_url == raw_url:
            return BytesIO(source)
        raise AssertionError(request.full_url)

    result = search_open_web_skills(
        [{"key_work_id": "lesson", "title": "讲解分部积分法"}],
        queries=["teaching SKILL.md"], opener=fetch,
    )

    assert [row["name"] for row in result.candidates] == ["teaching"]
    assert result.diagnostics["search_engines"] == ["Bing", "DuckDuckGo"]
    assert any(url.startswith("https://html.duckduckgo.com/html/?q=") for url in requested)


def test_custom_web_endpoint_failure_continues_with_public_fallback():
    requested = []

    def fetch(request, timeout):
        requested.append(request.full_url)
        raise OSError("custom endpoint offline")

    with pytest.raises(Exception, match="custom endpoint offline"):
        search_open_web_skills(
            [{"key_work_id": "lesson", "title": "讲课"}],
            search_url="https://search.example.test/api?q={query}",
            queries=["teaching SKILL.md"], opener=fetch,
        )

    assert len(requested) == 3
    assert requested[0].startswith("https://search.example.test/api?")
    assert requested[1].startswith("https://www.bing.com/search?")
    assert requested[2].startswith("https://html.duckduckgo.com/html/?")


def test_web_search_reads_github_blob_skill_as_raw_markdown():
    blob_url = "https://github.com/example/lesson/blob/main/skills/teaching/SKILL.md"
    raw_url = "https://raw.githubusercontent.com/example/lesson/main/skills/teaching/SKILL.md"
    source = b"---\nname: teaching\ndescription: Explain ideas clearly.\n---\nUse examples.\n"
    requested = []

    def fetch(request, timeout):
        requested.append(request.full_url)
        if request.full_url.startswith("https://search.example.test/api?"):
            return BytesIO(json.dumps({"results": [{"url": blob_url, "title": "Teaching"}]}).encode())
        if request.full_url == raw_url:
            return BytesIO(source)
        raise AssertionError(request.full_url)

    result = search_open_web_skills(
        [{"key_work_id": "lesson", "title": "讲解分部积分法"}],
        context_text="给初学者讲解分部积分法",
        search_url="https://search.example.test/api?q={query}",
        queries=["teaching SKILL.md"],
        opener=fetch,
    )

    assert [row["name"] for row in result.candidates] == ["teaching"]
    assert result.candidates[0]["record_snapshot"]["source_text"] == source.decode()
    assert result.candidates[0]["source_url"] == blob_url
    assert raw_url in requested


def test_web_search_reports_source_failure_instead_of_empty_match():
    def fetch(request, timeout):
        raise OSError("offline")

    try:
        search_open_web_skills(
            [{"key_work_id": "lesson", "title": "讲课"}],
            search_url="https://search.example.test/api?q={query}",
            queries=["teaching SKILL.md"],
            opener=fetch,
        )
    except Exception as exc:
        assert "offline" in str(exc)
    else:
        raise AssertionError("A failed source cannot be reported as no match")


def test_web_search_does_not_offer_unread_skill_url_as_candidate():
    blob_url = "https://github.com/example/lesson/blob/main/SKILL.md"
    requested = []

    def fetch(request, timeout):
        requested.append(request.full_url)
        if request.full_url.startswith("https://www.bing.com/search?"):
            return BytesIO((
                '<?xml version="1.0"?><rss><channel><item><title>Teaching Skill</title>'
                f'<link>{blob_url}</link></item></channel></rss>'
            ).encode())
        raise OSError("raw source offline")

    result = search_open_web_skills(
        [{"key_work_id": "lesson", "title": "讲解课程"}],
        queries=["teaching SKILL.md"], opener=fetch,
    )

    assert result.candidates == []
    assert result.diagnostics["unverified_sources"]
    assert result.diagnostics["unverified_sources"][0]["url"] == blob_url
    assert "raw source offline" in result.diagnostics["unverified_sources"][0]["error"]


def test_search_result_fallback_rejects_non_skill_pages():
    from promptsmith.open_skill_search import _candidate_from_search_result

    with pytest.raises(ValueError, match="普通网页"):
        _candidate_from_search_result(
            "https://example.test/tutorial", "Tutorial",
            query="agent skill", key_work_id="lesson", searched_at="2026-10-07T00:00:00Z",
        )


def test_github_root_skill_blob_is_downloaded_as_raw_markdown():
    from promptsmith.open_skill_search import _source_download_url

    assert _source_download_url("https://github.com/example/lesson/blob/main/SKILL.md") == (
        "https://raw.githubusercontent.com/example/lesson/main/SKILL.md"
    )


def test_duckduckgo_challenge_is_reported_as_source_failure():
    def fetch(request, timeout):
        return BytesIO(b'<html><form action="//duckduckgo.com/anomaly.js?sv=html"></form></html>')

    with pytest.raises(Exception, match="DuckDuckGo"):
        search_open_web_skills(
            [{"key_work_id": "lesson", "title": "Teach math"}],
            search_url="https://html.duckduckgo.com/html/?q={query}",
            queries=["teaching SKILL.md"], opener=fetch,
        )
