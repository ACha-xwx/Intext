"""Public discovery/search boundaries with disposable HTTP and model responses."""
import json
import hashlib
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
import pytest

from promptsmith.open_skill_search import search_open_web_skills
from promptsmith.skill_network_discovery import clear_network_skill_cache, search_network_skill_candidates
from promptsmith.skill_search import search_online_skills

WORKS = [{"key_work_id": "docs", "title": "比赛程序项目的技术文档写作与内容准确性检查", "step_ids": ["s1"]},
         {"key_work_id": "pdf", "title": "PDF交付质量", "step_ids": ["s2"]}]
TASK = "给比赛程序项目写技术文档，面向评委，检查内容准确性并交付PDF。"


@pytest.fixture(autouse=True)
def isolated_source_cache():
    clear_network_skill_cache()
    yield
    clear_network_skill_cache()


class Http:
    def __init__(self, names):
        self.names = names
        self.urls = []

    def __call__(self, request, timeout=None):
        url = request.full_url
        self.urls.append(url)
        if "/api/search" in url:
            return json.dumps({"skills": [
                {"skillId": name, "name": name, "description": description,
                 "url": f"https://skills.example.test/{name}/SKILL.md"}
                for name, description in self.names]}).encode()
        if "api.github.com/search/repositories" in url:
            return b'{"items":[]}'
        if "bing.com/search" in url:
            return b"<rss><channel></channel></rss>"
        if "duckduckgo.com" in url:
            return b'{"results":[]}'
        if url.endswith("SKILL.md"):
            name = urlsplit(url).path.split("/")[-2]
            description = dict(self.names)[name]
            return f"---\nname: {name}\ndescription: {description}\n---\n\nFollow the capability described above.\n".encode()
        raise AssertionError(f"Unexpected HTTP target: {url}")


class Model:
    def __init__(self, *, fail=False, score=.9):
        self.fail, self.score = fail, score
        self.calls = []

    def complete_json(self, prompt, payload, schema):
        self.calls.append(payload)
        if "queries" in schema.get("required", []):
            result = {"queries": ["AI Agent Skill 技术文档写作 SKILL.md 比赛项目",
                                  "agent skill PDF 导出 渲染检查 目录页码 SKILL.md"]}
        elif self.fail:
            raise OSError("模拟模型服务不可用")
        elif "candidate_ids" in schema.get("required", []):
            result = {"candidate_ids": [r["candidate_id"] for r in payload["skills"]]}
        else:
            result = {"matches": [{"candidate_id": r["candidate_id"], "key_work_id": "docs",
                                    "reason": "核对技术文档内容并组织报告。", "recommendation_score": self.score}
                                   for r in payload["skills"]]}
        return SimpleNamespace(content=json.dumps(result, ensure_ascii=False))


def test_index_keeps_short_document_and_pdf_queries_despite_long_model_queries():
    http = Http([])
    search_online_skills(WORKS, context_text=TASK, queries=[
        f"AI Agent Skill 技术文档 比赛写作-{i} SKILL.md" for i in range(6)],
        opener=http, include_github_supplement=False)
    terms = [parse_qs(urlsplit(url).query)["q"][0] for url in http.urls]
    assert "documentation" in terms and "pdf" in terms
    assert not any("agent" in term.casefold() or "skill.md" in term.casefold() for term in terms)
    assert len(terms) <= 6


def test_relevant_metadata_is_ranked_before_read_budget_not_hot_result_order():
    noise = [(f"video-{i}", "Generate videos and social media clips") for i in range(10)]
    http = Http([*noise, ("technical-docs", "Write technical documentation and verify report accuracy")])
    result = search_online_skills(WORKS, context_text=TASK, opener=http,
                                 include_github_supplement=False, max_verified_candidates=1)
    assert {r["name"] for r in result.candidates} == {"technical-docs"}
    assert not any("/video-" in url for url in http.urls)


def test_document_results_do_not_evict_pdf_capability_from_read_budget():
    http = Http([(f"documentation-{i}", "Write technical documentation and check report accuracy") for i in range(30)]
                + [("pdf", "Render and inspect PDF delivery")])
    result = search_online_skills(WORKS, context_text=TASK, opener=http,
                                 include_github_supplement=False, max_verified_candidates=2)
    assert {r["name"] for r in result.candidates} == {"documentation-0", "pdf"}


def test_open_web_ranks_skill_paths_before_read_budget():
    http = Http([("video", "Generate video"), ("pdf", "Create and check PDF documents")])
    def opener(request, timeout=None):
        if "search" in request.full_url:
            return json.dumps({"results": [{"url": f"https://skills.example.test/{name}/SKILL.md", "title": desc}
                                          for name, desc in http.names]}).encode()
        return http(request, timeout)
    result = search_open_web_skills(WORKS, context_text=TASK, opener=opener,
                                   search_url="https://search.example.test/?q={query}",
                                   queries=["PDF Agent Skill"], max_verified_candidates=1)
    assert [r["name"] for r in result.candidates] == ["pdf"]


def test_later_document_query_is_not_crowded_out_by_first_query_results():
    http = Http([(f"video-{i}", "Generate videos") for i in range(48)]
                + [("pdf", "Create and check PDF documents")])
    def opener(request, timeout=None):
        if "search" in request.full_url:
            query = parse_qs(urlsplit(request.full_url).query)["q"][0]
            rows = ([{"url": "https://skills.example.test/pdf/SKILL.md", "title": "PDF documents Skill"}]
                    if "pdf" in query else
                    [{"url": f"https://skills.example.test/video-{i}/SKILL.md", "title": "Video generation"} for i in range(48)])
            return json.dumps({"results": rows}).encode()
        return http(request, timeout)
    result = search_open_web_skills(WORKS, context_text=TASK, opener=opener,
                                   search_url="https://search.example.test/?q={query}",
                                   queries=["video agent skill", "pdf agent skill"], max_verified_candidates=1)
    assert [r["name"] for r in result.candidates] == ["pdf"]


def test_relevant_result_after_per_query_share_is_ranked_before_that_limit():
    http = Http([(f"video-{i}", "Generate videos") for i in range(24)]
                + [("pdf", "Create and check PDF documents")])
    def opener(request, timeout=None):
        if "search" in request.full_url:
            rows = [{"url": f"https://skills.example.test/video-{i}/SKILL.md", "title": "Video generation"} for i in range(24)]
            rows.append({"url": "https://skills.example.test/pdf/SKILL.md", "title": "PDF document Skill"})
            return json.dumps({"results": rows}).encode()
        return http(request, timeout)
    result = search_open_web_skills(WORKS, context_text=TASK, opener=opener,
                                   search_url="https://search.example.test/?q={query}",
                                   queries=["document agent skill", "pdf agent skill"], max_verified_candidates=1)
    assert [r["name"] for r in result.candidates] == ["pdf"]


def test_github_collection_prefers_documentation_skill_over_first_tree_entry():
    raw = b"---\nname: technical-docs\ndescription: Write technical documentation\n---\nCreate accurate documentation."
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    def opener(request, timeout=None):
        url = request.full_url
        if "/search/repositories" in url:
            return b'{"items":[{"full_name":"sample/skills","description":"technical documentation"}]}'
        if "/git/trees/" in url:
            return json.dumps({"tree": [{"path": "video/SKILL.md", "sha": "b"*40},
                                         {"path": "technical-docs/SKILL.md", "sha": blob}]}).encode()
        if "/commits?" in url:
            return json.dumps([{"sha": "a"*40}]).encode()
        if "raw.githubusercontent.com" in url:
            assert "technical-docs/SKILL.md" in url
            return raw
        if url.endswith("/repos/sample/skills"):
            return b'{"default_branch":"main"}'
        raise AssertionError(url)
    result = search_online_skills(WORKS, context_text=TASK, opener=opener,
                                 include_index=False, max_verified_candidates=1)
    assert {r["name"] for r in result.candidates} == {"technical-docs"}


def test_ai_failure_never_turns_unrelated_hot_skills_into_recommendations():
    http = Http([("video", "Generate videos"), ("twitter", "Automate social media"),
                 ("technical-docs", "Write technical documentation")])
    result = search_network_skill_candidates(WORKS, task_text=TASK, client=Model(fail=True), opener=http)
    assert {r["name"] for r in result.candidates} == {"technical-docs"}
    assert all(r["ai_review_status"] == "unavailable" for r in result.candidates)
    assert result.diagnostics["ai_review_status"] == "failed"
    assert result.diagnostics["fallback_rejected_count"] == 2


def test_low_score_model_matches_are_excluded_without_another_model_retry():
    http = Http([("video", "Generate videos")])
    model = Model(score=.05)
    result = search_network_skill_candidates(WORKS, task_text=TASK, client=model, opener=http)
    assert result.candidates == [] and result.status == "no_match"
    assert result.diagnostics["ai_review"]["low_score_rejected_count"] == 1
    assert len(model.calls) == 2  # One query plan, one review; never force a match.
