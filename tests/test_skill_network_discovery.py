import hashlib
import json
import threading
import time
from types import SimpleNamespace

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


def test_network_discovery_keeps_web_results_when_index_fails(monkeypatch):
    monkeypatch.setattr(discovery, "search_online_skills", lambda *a, **kw: (_ for _ in ()).throw(SkillSearchError("network", "index offline")))
    monkeypatch.setattr(discovery, "search_open_web_skills", lambda *a, **kw: SkillSearchResult("teaching", "ok", [_candidate("web", "https://other.example.test/SKILL.md")], "web-batch", "b" * 64))
    result = discovery.search_network_skill_candidates(
        [{"key_work_id": "lesson", "title": "讲解分部积分法"}], task_text="讲课", client=Client(),
    )
    assert [row["name"] for row in result.candidates] == ["web"]
    assert "index offline" in result.diagnostics["errors"][0]


def test_network_discovery_keeps_collected_candidates_when_ai_review_fails(monkeypatch):
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
