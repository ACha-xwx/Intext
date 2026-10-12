import hashlib
import json
import threading
import time
from types import SimpleNamespace

import pytest

import promptsmith.skill_network_discovery as discovery
from promptsmith.skill_ai_selection import SkillAiSelectionError
from promptsmith.skill_search import SkillSearchError, SkillSearchResult


def _candidate(candidate_id, source):
    raw = f"---\nname: {candidate_id}\ndescription: Teaching skill.\n---\nUse examples.\n"
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return {
        "candidate_id": candidate_id, "skill_id": source, "name": candidate_id,
        "description": "Teaching skill", "origin": "remote", "key_work_id": "lesson",
        "content_sha256": digest, "record_hash": digest,
        "record_snapshot": {"source_text": raw},
    }


def test_network_eligibility_accepts_skill_md_identity_but_rejects_general_web_url():
    skill = _candidate("skill", "https://example.test/skills/teaching/SKILL.md")
    webpage = _candidate("webpage", "https://example.test/skills/teaching/")

    assert discovery._is_agent_skill_reference(skill)
    assert not discovery._is_agent_skill_reference(webpage)


class Client:
    def __init__(self):
        self.calls = []

    def complete_json(self, prompt, payload, schema):
        self.calls.append((prompt, payload))
        if schema.get("required") == ["queries"]:
            answer = {"queries": ["teaching SKILL.md", "plain language agent skill"]}
        elif schema.get("required") == ["candidate_ids"]:
            answer = {"candidate_ids": [item["candidate_id"] for item in payload["skills"]]}
        else:
            answer = {"matches": [{"candidate_id": item["candidate_id"], "key_work_id": "lesson", "reason": "能用例子帮助初学者理解。"} for item in payload["skills"]]}
        return SimpleNamespace(content=json.dumps(answer, ensure_ascii=False))


def test_network_discovery_combines_sources_and_ai_reviews_originals(monkeypatch):
    index = _candidate("index", "https://skills.example.test/teaching/SKILL.md")
    duplicate = _candidate("duplicate", index["skill_id"])
    web = _candidate("web", "https://other.example.test/plain/SKILL.md")
    calls = []

    def indexed(*args, **kwargs):
        label = "index" if kwargs["include_index"] else "github"
        calls.append((label, kwargs))
        return SkillSearchResult(
            "teaching", "ok" if label == "index" else "no_match",
            [index] if label == "index" else [], f"{label}-batch", "a" * 64,
        )

    def open_web(*args, **kwargs):
        calls.append(("web", kwargs))
        return SkillSearchResult("teaching", "ok", [duplicate, web], "web-batch", "b" * 64)

    monkeypatch.setattr(discovery, "search_online_skills", indexed)
    monkeypatch.setattr(discovery, "search_open_web_skills", open_web)
    client = Client()
    result = discovery.search_network_skill_candidates(
        [{"key_work_id": "lesson", "title": "讲解分部积分法", "step_ids": ["step-1"]}],
        task_text="给初学者讲解分部积分法", client=client,
    )

    assert [row["name"] for row in result.candidates] == ["index", "web"]
    assert all(row["match_reason"] == "能用例子帮助初学者理解。" for row in result.candidates)
    by_source = {name: kwargs for name, kwargs in calls}
    assert by_source["index"]["queries"] == ["teaching SKILL.md AI Agent", "plain language agent skill SKILL.md"]
    assert by_source["index"]["include_unmatched"] is True
    assert by_source["index"]["include_github_supplement"] is False
    assert by_source["github"]["include_index"] is False
    assert by_source["github"]["include_github_supplement"] is True
    assert by_source["github"]["queries"] == by_source["index"]["queries"]
    assert by_source["web"]["queries"] == by_source["index"]["queries"]
    assert any("source" in payload["skills"][0] for _, payload in client.calls if "skills" in payload)


def test_network_discovery_keeps_web_results_when_index_fails(monkeypatch, caplog):
    monkeypatch.setattr(discovery, "search_online_skills", lambda *a, **kw: (_ for _ in ()).throw(SkillSearchError("network", "index offline")))
    monkeypatch.setattr(discovery, "search_open_web_skills", lambda *a, **kw: SkillSearchResult("teaching", "ok", [_candidate("web", "https://other.example.test/SKILL.md")], "web-batch", "b" * 64))
    result = discovery.search_network_skill_candidates(
        [{"key_work_id": "lesson", "title": "讲解分部积分法"}], task_text="讲课", client=Client(),
    )
    assert [row["name"] for row in result.candidates] == ["web"]
    assert "index offline" in result.diagnostics["errors"][0]
    assert "Skill discovery source failed" in caplog.text
    assert "Traceback" in caplog.text and "SkillSearchError" in caplog.text


def test_network_discovery_keeps_collected_candidates_when_ai_review_fails(monkeypatch, caplog):
    candidate = _candidate("web", "https://other.example.test/SKILL.md")
    monkeypatch.setattr(
        discovery, "search_online_skills",
        lambda *a, **kw: SkillSearchResult("teaching", "no_match", [], "empty", "a" * 64),
    )
    monkeypatch.setattr(
        discovery, "search_open_web_skills",
        lambda *a, **kw: SkillSearchResult("teaching", "ok", [candidate], "web", "b" * 64),
    )
    monkeypatch.setattr(
        discovery, "select_skill_candidates_with_ai",
        lambda *a, **kw: (_ for _ in ()).throw(SkillAiSelectionError("模型暂不可用")),
    )

    result = discovery.search_network_skill_candidates(
        [{"key_work_id": "lesson", "title": "讲解课程"}],
        task_text="讲解课程", client=Client(), timeout_seconds=0.2,
    )

    assert [row["name"] for row in result.candidates] == ["web"]
    assert result.candidates[0]["ai_review_status"] == "unavailable"
    assert result.diagnostics["ai_review_status"] == "failed"
    assert "Network Skill AI review unavailable" in caplog.text
    assert "SkillAiSelectionError" in caplog.text and "Traceback" in caplog.text


def test_network_discovery_filters_non_skill_urls_before_ai_review(monkeypatch):
    ordinary_page = _candidate("kimi", "https://www.kimi.com/slides/")
    ordinary_page["record_snapshot"] = {
        "skill_id": "web:https://www.kimi.com/slides/",
        "name": "Kimi PPT Assistant",
        "description": "AI slide generator",
        "origin": "remote",
        "source_kind": "web",
        "source_url": "https://www.kimi.com/slides/",
        "source_text": "",
        "local_source_snapshot_sha256": "a" * 64,
        "capabilities": [],
        "evidence_bundle": {
            "source_url": "https://www.kimi.com/slides/",
            "search_title": "Kimi PPT Assistant",
            "fetch_status": "search_result_only",
        },
    }
    monkeypatch.setattr(
        discovery, "search_online_skills",
        lambda *a, **kw: SkillSearchResult("teaching", "no_match", [], "empty", "a" * 64),
    )
    monkeypatch.setattr(
        discovery, "search_open_web_skills",
        lambda *a, **kw: SkillSearchResult("teaching", "ok", [ordinary_page], "web", "b" * 64),
    )
    client = Client()

    result = discovery.search_network_skill_candidates(
        [{"key_work_id": "lesson", "title": "讲解数学"}],
        task_text="讲解数学", client=client,
    )

    assert result.candidates == []
    assert all("kimi" not in json.dumps(payload, ensure_ascii=False).casefold() for _, payload in client.calls)


def test_network_discovery_runs_three_sources_in_parallel_with_independent_budgets(monkeypatch):
    index = _candidate("index", "https://skills.example.test/teaching/SKILL.md")
    entered = []
    barrier = threading.Barrier(3)

    def indexed(*args, **kwargs):
        entered.append("index" if kwargs["include_index"] else "github")
        barrier.wait(timeout=1)
        assert kwargs["timeout_seconds"] == 0.2
        if kwargs["include_index"]:
            return SkillSearchResult("teaching", "ok", [index], "index-batch", "a" * 64)
        return SkillSearchResult("teaching", "no_match", [], "github-batch", "b" * 64)

    def open_web(*args, **kwargs):
        entered.append("web")
        barrier.wait(timeout=1)
        assert kwargs["timeout_seconds"] == 0.2
        return SkillSearchResult("teaching", "no_match", [], "web-batch", "c" * 64)

    monkeypatch.setattr(discovery, "search_online_skills", indexed)
    monkeypatch.setattr(discovery, "search_open_web_skills", open_web)
    result = discovery.search_network_skill_candidates(
        [{"key_work_id": "lesson", "title": "讲课"}],
        task_text="独立并行预算测试", client=Client(), timeout_seconds=0.2,
    )

    assert [row["name"] for row in result.candidates] == ["index"]
    assert set(entered) == {"index", "github", "web"}
    assert set(result.diagnostics["sources"]) == {"skill_index", "github", "open_web"}
    assert all("elapsed_ms" in row for row in result.diagnostics["source_diagnostics"].values())


def test_network_discovery_reuses_successful_source_cache(monkeypatch):
    discovery.clear_network_skill_cache()
    calls = []

    def indexed(*args, **kwargs):
        calls.append("index" if kwargs["include_index"] else "github")
        return SkillSearchResult(
            "teaching", "no_match", [],
            "index-batch" if kwargs["include_index"] else "github-batch",
            "a" * 64,
        )

    def open_web(*args, **kwargs):
        calls.append("web")
        return SkillSearchResult("teaching", "no_match", [], "web-batch", "c" * 64)

    monkeypatch.setattr(discovery, "search_online_skills", indexed)
    monkeypatch.setattr(discovery, "search_open_web_skills", open_web)
    works = [{"key_work_id": "lesson", "title": "缓存测试"}]
    discovery.search_network_skill_candidates(works, task_text="缓存测试", client=Client(), timeout_seconds=0.2)
    discovery.search_network_skill_candidates(works, task_text="缓存测试", client=Client(), timeout_seconds=0.2)

    assert calls.count("index") == 1
    assert calls.count("github") == 1
    assert calls.count("web") == 1


def test_custom_network_limits_and_review_options_reach_all_sources(monkeypatch):
    discovery.clear_network_skill_cache()
    observed = []
    def search(*args, **kwargs):
        observed.append(kwargs)
        return SkillSearchResult("test", "no_match", [], "test", "a"*64)
    monkeypatch.setattr(discovery, "generate_skill_search_queries", lambda *args, **kwargs: ["ui"])
    monkeypatch.setattr(discovery, "search_online_skills", search)
    monkeypatch.setattr(discovery, "search_open_web_skills", search)
    reviews = []
    monkeypatch.setattr(discovery, "select_skill_candidates_with_ai", lambda *args, **kwargs: (reviews.append(kwargs) or []))
    options = {"shortlist_limit": 4, "review_limit": 2, "input_budget_chars": 9000, "excerpt_chars": 500}
    discovery.search_network_skill_candidates([], task_text="UI", client=Client(), timeout_seconds=2,
                                               max_verified_candidates=3, review_options=options, cache_ttl_seconds=0)
    assert len(observed) == 3
    assert all(row["max_verified_candidates"] == 3 and row["timeout_seconds"] == 2 for row in observed)
    assert all(reviews[0][key] == value for key, value in options.items())


def test_repeated_search_reuses_query_plan_for_same_model_and_task(monkeypatch):
    from promptsmith.api import ApiConfig
    discovery.clear_network_skill_cache()
    empty = lambda *a, **kw: SkillSearchResult("teaching", "no_match", [], "empty", "a" * 64)
    monkeypatch.setattr(discovery, "search_online_skills", empty)
    monkeypatch.setattr(discovery, "search_open_web_skills", empty)
    works = [{"key_work_id": "lesson", "title": "Teaching"}]

    def client(model="model", key="synthetic-key"):
        value = Client()
        value.config = ApiConfig("https://example.invalid", model, key, reasoning_effort="high")
        return value

    first, again = client(), client()
    discovery.search_network_skill_candidates(works, task_text="Teaching", client=first)
    discovery.search_network_skill_candidates(works, task_text="Teaching", client=again)
    assert len(first.calls) == 1
    assert not again.calls, "Cached sources should not require a repeated identical query planning request."
    different = client(model="another-model")
    discovery.search_network_skill_candidates(works, task_text="Teaching", client=different)
    assert len(different.calls) == 1
    disabled = client()
    discovery.search_network_skill_candidates(works, task_text="Teaching", client=disabled, cache_ttl_seconds=0)
    assert len(disabled.calls) == 1
    discovery.clear_network_skill_cache()


@pytest.fixture
def query_cache_search(monkeypatch):
    from promptsmith.api import ApiConfig
    discovery.clear_network_skill_cache()
    empty = lambda *a, **kw: SkillSearchResult("test", "no_match", [], "empty", "a" * 64)
    monkeypatch.setattr(discovery, "search_online_skills", empty)
    monkeypatch.setattr(discovery, "search_open_web_skills", empty)

    def search(*, task="Teaching", works=None, config=None, client=None, ttl=10):
        value = client or Client()
        value.config = config or ApiConfig("https://example.invalid", "model", "synthetic-cache-key")
        result = discovery.search_network_skill_candidates(
            works or [{"key_work_id": "lesson", "title": "Teaching"}],
            task_text=task, client=value, cache_ttl_seconds=ttl,
        )
        return value, result

    yield search
    discovery.clear_network_skill_cache()


@pytest.mark.parametrize("change", ["key", "task", "works", "effort", "budget"])
def test_query_cache_separates_credentials_task_work_and_model_settings(query_cache_search, change):
    from dataclasses import replace
    from promptsmith.api import ApiConfig
    config = ApiConfig("https://example.invalid", "model", "synthetic-cache-key")
    first, _ = query_cache_search(config=config)
    options = {"config": config}
    if change == "key":
        options["config"] = replace(config, api_key="synthetic-other-key")
    elif change == "effort":
        options["config"] = replace(config, reasoning_effort="max")
    elif change == "budget":
        options["config"] = replace(config, max_tokens=8192)
    elif change == "task":
        options["task"] = "Teaching physics"
    else:
        options["works"] = [{"key_work_id": "lesson", "title": "Teaching", "goal": "Explain physics"}]
    changed, result = query_cache_search(**options)
    assert len(first.calls) == len(changed.calls) == 1
    assert not result.diagnostics["query_plan_cached"]
    again, result = query_cache_search(config=config)
    assert not again.calls and result.diagnostics["query_plan_cached"]


def test_query_cache_expires_and_manual_clear_replans(query_cache_search, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(discovery.time, "monotonic", lambda: clock[0])
    query_cache_search()
    clock[0] = 109.9
    cached, result = query_cache_search()
    assert not cached.calls and result.diagnostics["query_plan_cached"]
    clock[0] = 110.0
    expired, result = query_cache_search()
    assert len(expired.calls) == 1 and not result.diagnostics["query_plan_cached"]
    discovery.clear_network_skill_cache()
    cleared, _ = query_cache_search()
    assert len(cleared.calls) == 1


@pytest.mark.parametrize("failure", ["invalid_json", "api_error", "cancelled"])
def test_unsuccessful_query_planning_is_not_cached(query_cache_search, failure):
    from concurrent.futures import CancelledError

    class FailingClient(Client):
        def complete_json(self, *args):
            self.calls.append(args)
            if failure == "invalid_json":
                return SimpleNamespace(content="not json")
            if failure == "cancelled":
                raise CancelledError()
            raise RuntimeError("synthetic planning failure")

    failed = FailingClient()
    if failure == "cancelled":
        with pytest.raises(CancelledError):
            query_cache_search(client=failed)
    else:
        _, result = query_cache_search(client=failed)
        assert not result.diagnostics["query_plan_cached"]
    retried, result = query_cache_search()
    assert len(failed.calls) == len(retried.calls) == 1
    assert not result.diagnostics["query_plan_cached"]
