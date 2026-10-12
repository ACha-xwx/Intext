from __future__ import annotations

import json
import hashlib
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from promptsmith.skill_search import (
    SkillSearchError,
    build_skill_query,
    build_github_search_request,
    merge_candidates,
    search_github_repositories,
)
import promptsmith.skill_search as search_module


class _Response:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        if isinstance(self.payload, bytes):
            return self.payload
        return json.dumps(self.payload).encode("utf-8")

    def getcode(self):
        return self.status


def test_build_skill_query_contains_task_terms_and_repository_filter():
    query = build_skill_query(
        [{"title": "整理研究综述", "goal": "检索并归纳论文"}],
        context_text="需要引用和证据核验",
    )

    assert "skill" in query
    assert "research" in query or "检索" in query
    assert "SKILL.md" in query
    assert "filename:SKILL.md" in query


def test_build_skill_query_is_bounded_for_github_api():
    query = build_skill_query(
        [{"title": "任务 " + ("很长 " * 200), "goal": "目标 " + ("内容 " * 200)}],
        context_text="上下文 " + ("说明 " * 200),
    )

    assert len(query) <= 256
    assert "SKILL.md" in query
    assert "filename:SKILL.md" in query


def test_search_github_repositories_searches_for_skill_files(monkeypatch):
    payload = {
        "items": [
            {
                "full_name": "example/research-skill",
                "name": "research-skill",
                "description": "Research workflow skill",
                "path": "skills/research/SKILL.md",
                "html_url": "https://github.com/example/research-skill/blob/main/skills/research/SKILL.md",
                "sha": "a" * 40,
            }
        ]
    }

    def fake_urlopen(request, timeout):
        assert request.full_url.startswith("https://api.github.com/search/code?")
        assert "filename%3ASKILL.md" in request.full_url
        assert timeout > 0
        return _Response(payload)

    monkeypatch.setattr("promptsmith.skill_search.urlopen", fake_urlopen)
    result = search_github_repositories(
        [{"key_work_id": "work-1", "title": "整理研究综述", "goal": "检索论文"}],
        context_text="需要引用和证据核验",
    )

    assert result.status == "ok"
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate["origin"] == "remote"
    assert candidate["selection_allowed"] is True
    assert candidate["record_snapshot"]["method_adaptation_allowed"] is True
    assert candidate["record_snapshot"]["verification"]["verification_status"] == "network_unverified"
    assert candidate["source_url"] == "https://github.com/example/research-skill/blob/main/skills/research/SKILL.md"
    assert candidate["limitations"]
    assert candidate["step_ids"] == []
    assert candidate["provenance"]["content_hash_kind"] == "api_metadata"
    assert candidate["provenance"]["source_read"] is False


def test_search_github_repositories_assigns_confirmed_steps_to_remote_candidate(monkeypatch):
    payload = {"items": [{
        "full_name": "example/remote-skill",
        "name": "remote-skill",
        "description": "Remote Agent Skill",
        "path": "SKILL.md",
        "html_url": "https://github.com/example/remote-skill/blob/main/SKILL.md",
    }]}
    monkeypatch.setattr("promptsmith.skill_search.urlopen", lambda *_args, **_kwargs: _Response(payload))

    result = search_github_repositories(
        [{"key_work_id": "work-1", "title": "任务", "step_ids": ["step-a", "step-b"]}],
        key_work_steps={"work-1": ["step-a", "step-b"]},
    )

    assert result.candidates[0]["step_ids"] == ["step-a", "step-b"]


def test_github_repository_metadata_without_skill_file_is_not_a_skill_candidate():
    candidates = search_module.normalize_github_results(
        [{
            "full_name": "example/ordinary-project",
            "name": "ordinary-project",
            "description": "A general-purpose project that mentions teaching methods.",
            "html_url": "https://github.com/example/ordinary-project",
        }],
        query="teaching",
        key_work_ids=["lesson"],
    )

    assert candidates == []


def test_metadata_fallback_requires_a_skill_artifact_or_explicit_skill_index_entry():
    generic_repo = search_module._online_fallback_record(
        {
            "repository": "example/ordinary-project",
            "description": "A project with generic methods.",
            "source_index": "GitHub",
        },
        error="GitHub unavailable",
        searched_at="2026-10-07T00:00:00Z",
    )
    indexed_skill = search_module._online_fallback_record(
        {
            "repository": "example/agent-skills",
            "skill_id": "lesson-planning",
            "source_index": "skills.sh",
            "description": "An indexed Agent Skill.",
        },
        error="SKILL.md temporarily unavailable",
        searched_at="2026-10-07T00:00:00Z",
    )

    assert generic_repo is None
    assert indexed_skill is not None
    assert indexed_skill["source_path"] == ""
    assert indexed_skill["skill_id"].endswith(":lesson-planning")


def test_skill_index_does_not_promote_arbitrary_urls_to_skill_entries():
    rows = search_module._online_discovery_rows({
        "results": [{
            "skillId": "presentation-helper",
            "url": "https://www.kimi.com/slides/",
            "title": "Kimi PPT Assistant",
        }],
    })

    assert rows == []


def test_online_web_source_must_be_an_actual_skill_markdown_path():
    skill_like_page = b"---\nname: slides\ndescription: Create slides.\n---\nFollow these instructions.\n"
    record = search_module._online_record_from_source(
        lambda *_args, **_kwargs: _Response(skill_like_page),
        {"url": "https://www.kimi.com/slides/", "source_index": "Skill index"},
        deadline=time.monotonic() + 3,
        searched_at="2026-10-07T00:00:00Z",
    )

    assert record is None


def test_skill_markdown_requires_instruction_body_after_frontmatter():
    with pytest.raises(SkillSearchError, match="指令正文"):
        search_module._online_skill_metadata(
            b"---\nname: empty-skill\ndescription: An empty skill.\n---\n  \n"
        )


def test_github_repository_supplement_queries_for_agent_skill_files():
    queries = search_module._online_github_queries(["teaching"])

    assert len(queries) == 1
    assert "SKILL.md" in queries[0]
    assert "agent skill" in queries[0]
    assert "in:readme" in queries[0]


def test_search_github_repositories_uses_only_steps_for_each_confirmed_work(monkeypatch):
    payload = {"items": [{
        "full_name": "example/remote-skill", "path": "SKILL.md",
        "html_url": "https://github.com/example/remote-skill/blob/main/SKILL.md",
    }]}
    monkeypatch.setattr("promptsmith.skill_search.urlopen", lambda *_args, **_kwargs: _Response(payload))

    result = search_github_repositories(
        [
            {"key_work_id": "work-1", "title": "A", "step_ids": ["step-a", "step-b"]},
            {"key_work_id": "work-2", "title": "B", "step_ids": ["step-c"]},
        ],
        key_work_steps={"work-1": ["step-a"], "work-2": ["step-c"]},
    )

    assert {row["key_work_id"]: row["step_ids"] for row in result.candidates} == {
        "work-1": ["step-a"],
        "work-2": ["step-c"],
    }


@pytest.mark.parametrize(
    "api_base_url",
    [
        "not a url",
        "file:///tmp/api",
        "http://api.example.test",
        "https://user:secret@api.example.test",
        "https://api.example.test?token=secret",
        "https://api.example.test#fragment",
    ],
)
def test_github_search_rejects_invalid_or_unsafe_custom_api_urls(api_base_url):
    with pytest.raises(ValueError, match="HTTPS"):
        build_github_search_request("skill", api_base_url=api_base_url)


def test_custom_api_url_does_not_receive_github_token():
    request = build_github_search_request(
        "skill", api_base_url="https://api.example.test/github", token="secret-token"
    )

    assert request.full_url.startswith("https://api.example.test/github/search/")
    assert request.get_header("Authorization") is None


def test_custom_api_url_is_trimmed_before_building_endpoint():
    request = build_github_search_request(
        "skill", api_base_url="  https://api.example.test/github/  "
    )

    assert request.full_url.startswith("https://api.example.test/github/search/")


def test_search_github_reports_empty_results(monkeypatch):
    monkeypatch.setattr(
        "promptsmith.skill_search.urlopen",
        lambda *_args, **_kwargs: _Response({"items": []}),
    )

    result = search_github_repositories([{"key_work_id": "work-1", "title": "不存在的任务"}])

    assert result.status == "no_match"
    assert result.candidates == []


def test_search_github_translates_http_and_json_errors(monkeypatch):
    monkeypatch.setattr(
        "promptsmith.skill_search.urlopen",
        lambda *_args, **_kwargs: _Response({"message": "rate limit"}, status=403),
    )
    with pytest.raises(SkillSearchError, match="403"):
        search_github_repositories([{"key_work_id": "work-1", "title": "任务"}])

    def invalid(*_args, **_kwargs):
        return _Response(b"not json")

    monkeypatch.setattr("promptsmith.skill_search.urlopen", invalid)
    with pytest.raises(SkillSearchError, match="JSON"):
        search_github_repositories([{"key_work_id": "work-1", "title": "任务"}])


def test_merge_candidates_keeps_local_and_remote_references_separate():
    local = {
        "candidate_id": "local-1",
        "skill_id": "same-skill",
        "key_work_id": "work-1",
        "record_hash": "a" * 64,
        "record_snapshot": {"skill_id": "same-skill"},
        "selection_allowed": True,
        "origin": "local",
    }
    remote = {
        "candidate_id": "remote-1",
        "skill_id": "same-skill",
        "key_work_id": "work-1",
        "record_hash": "b" * 64,
        "record_snapshot": {"skill_id": "same-skill"},
        "selection_allowed": True,
        "origin": "remote",
    }
    batch = merge_candidates([local], [remote], catalog_hash="local-hash")

    assert len(batch["result"]["candidates"]) == 2
    assert {row["origin"] for row in batch["result"]["candidates"]} == {"local", "remote"}
    assert batch["sources"] == ["local", "remote"]
    assert batch["catalog_hash"] != "local-hash"


_SKILL = b"---\nname: slide-review\ndescription: Review a PowerPoint presentation for clarity and structure.\n---\n\n# Steps\nRead the brief, organize slides, and review clarity.\n"
_REPO = "example/slides"
_PATH = "skills/slide-review/SKILL.md"
_COMMIT = "a" * 40


def _online_work():
    return [{"key_work_id": "work-1", "title": "制作 PPT 汇报", "goal": "清晰组织幻灯片",
             "step_ids": ["step-a", "step-b"]}]


def _blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _online_response(request, timeout):
    url = request.full_url
    assert timeout > 0
    if url.startswith("https://skills.sh/api/search?"):
        return _Response({"skills": [{"source": _REPO, "skillId": "slide-review", "installs": 5}]})
    if url.startswith("https://api.github.com/search/repositories?"):
        return _Response({"items": []})
    if url == f"https://api.github.com/repos/{_REPO}":
        return _Response({"default_branch": "main"})
    if "/git/trees/" in url:
        return _Response({"tree": [{"path": _PATH, "sha": _blob_sha(_SKILL)}]})
    if url.startswith(f"https://api.github.com/repos/{_REPO}/commits?"):
        return _Response([{"sha": _COMMIT, "commit": {"committer": {"date": "2026-10-01T00:00:00Z"}}}])
    if url.startswith(f"https://raw.githubusercontent.com/{_REPO}/"):
        return _Response(_SKILL)
    raise AssertionError(url)


def test_online_search_restores_skills_index_and_reads_pinned_skill():
    result = search_module.search_online_skills(_online_work(), opener=_online_response)

    assert result.status == "ok"
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate["step_ids"] == ["step-a", "step-b"]
    assert candidate["source_url"] == f"https://github.com/{_REPO}/blob/{_COMMIT}/{_PATH}"
    assert candidate["content_sha256"] == hashlib.sha256(_SKILL).hexdigest()
    assert candidate["provenance"]["source_read"] is True
    assert candidate["provenance"]["content_hash_kind"] == "source_content"
    assert candidate["record_snapshot"]["source_text"].endswith("review clarity.\n")
    assert candidate["record_snapshot"]["searched_at"]
    assert result.to_dict()["diagnostics"]["verified_count"] == 1


@pytest.mark.parametrize("changed", ["tree_hash", "pinned_content", "missing_metadata"])
def test_online_search_does_not_offer_unverified_files(changed):
    def altered(request, timeout):
        url = request.full_url
        if changed == "tree_hash" and "/git/trees/" in url:
            return _Response({"tree": [{"path": _PATH, "sha": "0" * 40}]})
        if changed == "pinned_content" and f"/{_COMMIT}/" in url:
            return _Response(_SKILL + b"changed")
        if changed == "missing_metadata" and url.startswith("https://raw.githubusercontent.com/"):
            return _Response(b"# Not a Skill\n")
        return _online_response(request, timeout)

    result = search_module.search_online_skills(_online_work(), opener=altered)

    assert result.status == "no_match"
    assert result.candidates == []
    assert result.to_dict()["diagnostics"]["errors"]


def test_online_search_chinese_work_uses_short_multiround_keywords():
    queried = []

    def fetch(request, timeout):
        if request.full_url.startswith("https://skills.sh/api/search?"):
            queried.append(parse_qs(urlparse(request.full_url).query)["q"][0])
        return _online_response(request, timeout)

    search_module.search_online_skills(_online_work(), opener=fetch)

    assert any(word in queried for word in ("presentation", "powerpoint", "slides"))
    assert len(queried) >= 2
    assert all(len(word) < 80 and "in:name" not in word for word in queried)


def test_online_search_model_queries_and_progress_are_supported():
    messages = []
    result = search_module.search_online_skills(
        _online_work(), opener=_online_response, queries=["powerpoint", "visual storytelling"],
        progress=messages.append,
    )

    assert result.to_dict()["diagnostics"]["queries"][:2] == ["powerpoint", "visual storytelling"]
    assert any("powerpoint" in message for message in messages)
    assert any("SKILL.md" in message for message in messages)


def test_github_supplement_uses_multiple_task_queries_for_skill_artifacts(monkeypatch):
    searched = []
    discovered = []

    def fetch(request, timeout):
        assert request.full_url.startswith("https://api.github.com/search/repositories?")
        query = parse_qs(urlparse(request.full_url).query)["q"][0]
        searched.append(query)
        if "travel guide" in query:
            return _Response({"items": [{"full_name": "travel/guide"}]})
        return _Response({"items": []})

    def inspect_source(_opener, item, **_kwargs):
        discovered.append(item["repository"])
        return None

    monkeypatch.setattr(search_module, "_online_record_from_source", inspect_source)
    search_module.search_online_skills(
        _online_work(), opener=fetch, include_index=False,
        queries=["旅行攻略生成 agent skill SKILL.md", "travel guide agent skill SKILL.md"],
    )

    assert any("travel guide" in query for query in searched)
    assert all('"SKILL.md"' in query and '"agent skill"' in query and "in:readme" in query for query in searched)
    assert discovered == ["travel/guide"]


def test_github_api_limit_uses_public_page_to_read_skill():
    source_url = f"https://github.com/{_REPO}/blob/main/{_PATH}"

    def fetch(request, timeout):
        url = request.full_url
        if url.startswith("https://api.github.com/search/repositories?"):
            return _Response({"items": [{"full_name": _REPO}]})
        if url == f"https://api.github.com/repos/{_REPO}":
            raise search_module.SkillSearchError("http", "HTTP 403", 403)
        if url == f"https://github.com/{_REPO}":
            return _Response(f'<html><a href="/{_REPO}/blob/main/{_PATH}">SKILL.md</a></html>'.encode())
        if url == f"https://raw.githubusercontent.com/{_REPO}/main/{_PATH}":
            return _Response(_SKILL)
        raise AssertionError(url)

    result = search_module.search_online_skills(
        _online_work(), opener=fetch, include_index=False,
        include_unmatched=True, queries=["slide review SKILL.md"],
    )

    assert result.status == "ok"
    assert result.candidates[0]["source_url"] == source_url
    assert result.candidates[0]["fixed_commit"] == "unresolved"
    assert result.candidates[0]["verification_status"] == "source_read"
    assert result.candidates[0]["record_snapshot"]["source_text"] == _SKILL.decode()


def test_github_public_fallback_accepts_root_skill_for_index_id():
    repository = "example/root-skill"

    def fetch(request, timeout):
        url = request.full_url
        if url == f"https://api.github.com/repos/{repository}":
            raise search_module.SkillSearchError("http", "HTTP 403", 403)
        if url == f"https://github.com/{repository}":
            return _Response(f'<a href="/{repository}/blob/main/skill.md">skill.md</a>'.encode())
        if url == f"https://raw.githubusercontent.com/{repository}/main/skill.md":
            return _Response(_SKILL)
        raise AssertionError(url)

    record = search_module._online_record_from_source(
        fetch, {"repository": repository, "skill_id": "slide-review"},
        deadline=time.monotonic() + 10, searched_at="2026-10-07T00:00:00Z",
    )

    assert record is not None
    assert record["source_path"] == "skill.md"


@pytest.mark.parametrize("search_url, expected", [
    ("https://index.example.test", "https://index.example.test/api/search"),
    ("https://index.example.test/search", "https://index.example.test/search"),
    ("https://index.example.test/find?q={query}&limit=8", "https://index.example.test/find"),
])
def test_online_custom_search_address_is_used_as_search_endpoint(search_url, expected):
    requests = []

    def fetch(request, timeout):
        requests.append(request)
        if request.full_url.startswith(expected):
            assert request.get_header("Authorization") is None
            return _Response({"skills": [{"source": _REPO, "skillId": "slide-review"}]})
        return _online_response(request, timeout)

    result = search_module.search_online_skills(
        _online_work(), opener=fetch, search_url=search_url, token="github-test-token",
    )

    assert result.status == "ok"
    assert requests[0].full_url.startswith(expected)
    assert parse_qs(urlparse(requests[0].full_url).query)["q"][0]


def test_online_generic_search_supports_actual_skill_on_other_sites():
    source_url = "https://docs.example.test/skills/slides/SKILL.md"

    def fetch(request, timeout):
        if request.full_url.startswith("https://search.example.test/find?"):
            return _Response({"results": [{"url": source_url, "title": "Slide review"}]})
        if request.full_url == source_url:
            return _Response(_SKILL)
        if request.full_url.startswith("https://api.github.com/search/repositories?"):
            return _Response({"items": []})
        raise AssertionError(request.full_url)

    result = search_module.search_online_skills(
        _online_work(), opener=fetch, search_url="https://search.example.test/find?q={query}",
    )

    assert result.status == "ok"
    assert result.candidates[0]["source_url"] == source_url
    assert result.candidates[0]["provenance"]["source_read"] is True
    assert result.candidates[0]["fixed_commit"] == "unresolved"
    assert result.candidates[0]["record_snapshot"]["source_kind"] == "web"


def test_online_search_matches_each_confirmed_work_independently():
    works = _online_work() + [{"key_work_id": "work-2", "title": "分析 Excel 数据", "step_ids": ["step-c"]}]
    result = search_module.search_online_skills(works, opener=_online_response)

    assert {row["key_work_id"] for row in result.candidates} == {"work-1"}
    assert result.to_dict()["result"]["unmatched_key_work_ids"] == ["work-2"]


def test_online_all_sources_failing_reports_failure_instead_of_zero_results():
    def offline(request, timeout):
        raise OSError("offline")

    with pytest.raises(SkillSearchError, match="offline"):
        search_module.search_online_skills(_online_work(), opener=offline)


def test_online_valid_empty_search_is_distinct_from_failure():
    result = search_module.search_online_skills(
        _online_work(), opener=lambda *_args, **_kwargs: _Response({"skills": [], "items": []}),
    )

    assert result.status == "no_match"
    assert result.candidates == []
    assert result.to_dict()["diagnostics"]["errors"] == []


def test_online_search_can_run_index_only_and_caps_verification(monkeypatch):
    verified = []

    def fake_record(_opener, item, **kwargs):
        verified.append(item["url"])
        return None

    monkeypatch.setattr(search_module, "_online_record_from_source", fake_record)

    def fetch(request, timeout):
        if request.full_url.startswith("https://skills.example.test/api/search?"):
            return _Response({"skills": [{"url": f"https://skills.example.test/{i}/SKILL.md"} for i in range(10)]})
        raise AssertionError(request.full_url)

    result = search_module.search_online_skills(
        _online_work(),
        opener=fetch,
        search_url="https://skills.example.test",
        include_github_supplement=False,
        max_verified_candidates=2,
    )

    assert len(verified) == 2
    assert result.diagnostics["verification_cap"] == 2
    assert result.diagnostics["github_supplement"] is False
