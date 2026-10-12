"""Deferred offline checks: HTTP access failures, credentials and source fallback."""
from email.message import Message
from io import BytesIO
import logging
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from promptsmith.skill_http import (SkillHttpSession, SkillRedirectHandler,
                                   diagnostic_target, request_headers)
from promptsmith.skill_search import _online_reader, search_online_skills, SkillSearchError
from promptsmith.open_skill_search import search_open_web_skills
from tests.test_skill_search import _online_work, _online_response, _Response, _REPO, _SKILL


def denial(url, code=403, body=b"Forbidden", headers=None):
    values = Message()
    for key, value in (headers or {}).items():
        values[key] = value
    return HTTPError(url, code, "Forbidden", values, BytesIO(body))


@pytest.mark.parametrize("url,accept", [
    ("https://api.github.com/repos/org/repo", "application/vnd.github+json"),
    ("https://raw.githubusercontent.com/org/repo/main/SKILL.md", "text/plain"),
    ("https://github.com/org/repo", "text/html"),
    ("https://skills.sh/api/search?q=ui", "application/json"),
])
def test_request_headers_match_endpoint_type(url, accept):
    headers = request_headers(url)
    assert headers["Accept"].startswith(accept)
    assert "Mozilla/5.0" in headers["User-Agent"]
    assert "Authorization" not in headers


@pytest.mark.parametrize("url,authenticated", [
    ("https://api.github.com/repos/org/repo", True),
    ("https://api.github.com.evil.test/repos/org/repo", False),
    ("https://skills.sh/api/search?q=ui", False),
    ("https://raw.githubusercontent.com/org/repo/main/SKILL.md", False),
    ("https://github.com/org/repo", False),
    ("https://api.github.com:8443/repos/org/repo", False),
])
def test_github_token_only_reaches_official_https_api(url, authenticated):
    requests = []
    session = SkillHttpSession(lambda request, timeout: requests.append(request) or BytesIO(b"fixture"), token="test-secret")
    assert _online_reader(session, url, 1) == b"fixture"
    assert bool(requests[0].get_header("Authorization")) == authenticated
    assert "test-secret" not in repr(session.diagnostics())


@pytest.mark.parametrize("target,authenticated", [
    ("https://other.test/receive", False),
    ("http://api.github.com/repos/new/repo", False),
    ("https://api.github.com/repos/new/repo", True),
])
def test_redirects_drop_credentials_outside_official_api(target, authenticated):
    request = Request("https://api.github.com/repos/org/repo")
    request.add_unredirected_header("Authorization", "Bearer test-secret")
    redirected = SkillRedirectHandler().redirect_request(request, None, 302, "Found", {}, target)
    assert bool(redirected.get_header("Authorization")) == authenticated


def test_read_cache_reuses_metadata_and_does_not_make_network_calls_twice():
    requests = []
    session = SkillHttpSession(lambda req, timeout: requests.append(req.full_url) or BytesIO(b"{}"))
    url = "https://api.github.com/repos/org/repo"
    assert _online_reader(session, url, 1) == _online_reader(session, url, 1) == b"{}"
    assert requests == [url]
    assert session.diagnostics()["cache_hits"] == 1


def test_rate_limit_pauses_repeated_api_access_but_allows_raw_content(caplog):
    requests = []
    def fetch(request, timeout):
        requests.append(request.full_url)
        if request.full_url.startswith("https://api.github.com/"):
            raise denial(request.full_url, body=b'{"message":"API rate limit exceeded"}',
                         headers={"X-RateLimit-Remaining": "0", "Retry-After": "60"})
        return BytesIO(b"skill-content")
    session = SkillHttpSession(fetch)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(SkillSearchError) as first:
            _online_reader(session, "https://api.github.com/repos/org/one", 1)
        with pytest.raises(SkillSearchError) as second:
            _online_reader(session, "https://api.github.com/repos/org/two", 1)
    assert first.value.access_reason == "rate_limit"
    assert second.value.request_skipped
    assert len(requests) == 1
    assert _online_reader(session, "https://raw.githubusercontent.com/org/two/main/SKILL.md", 1) == b"skill-content"
    assert session.diagnostics()["access_issues"][0]["retry_after"] == "60"
    assert any(record.exc_info and record.levelno == logging.WARNING for record in caplog.records)


def test_single_file_forbidden_does_not_hide_other_files_on_same_host():
    def fetch(req, timeout):
        if req.full_url.endswith("/private/SKILL.md"):
            raise denial(req.full_url)
        return BytesIO(b"public-skill")
    session = SkillHttpSession(fetch)
    with pytest.raises(SkillSearchError):
        _online_reader(session, "https://example.test/private/SKILL.md", 1)
    assert _online_reader(session, "https://example.test/public/SKILL.md", 1) == b"public-skill"


def test_core_quota_pause_does_not_suppress_search_quota():
    def fetch(req, timeout):
        if "/repos/" in req.full_url:
            raise denial(req.full_url, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Resource": "core"})
        return BytesIO(b'{"items":[]}')
    session = SkillHttpSession(fetch)
    with pytest.raises(SkillSearchError):
        _online_reader(session, "https://api.github.com/repos/org/repo", 1)
    assert _online_reader(session, "https://api.github.com/search/repositories?q=ui", 1) == b'{"items":[]}'


@pytest.mark.parametrize("status,body,reason", [
    (403, b"Forbidden", "forbidden"), (403, b"Cloudflare verify you are human", "blocked"),
    (429, b"Too many requests", "rate_limit"), (521, b"Web server is down", "upstream_unavailable"),
])
def test_http_error_classification_and_redacted_logs(status, body, reason, caplog):
    url = "https://index.example.test/search?api_key=do-not-log&q=private-goal#hidden"
    def fetch(req, timeout):
        raise denial(req.full_url, status, body)
    with caplog.at_level(logging.DEBUG), pytest.raises(SkillSearchError) as caught:
        _online_reader(SkillHttpSession(fetch), url, 1)
    assert caught.value.access_reason == reason
    assert "index.example.test/search" in str(caught.value)
    assert "do-not-log" not in caplog.text + str(caught.value)
    assert "private-goal" not in caplog.text + str(caught.value)
    assert diagnostic_target("https://user:password@index.example.test/search?token=secret") == "https://index.example.test/search"


def test_legacy_url_timeout_fetch_callback_still_works():
    def fetch(url, timeout):
        if not isinstance(url, str):
            raise TypeError("legacy callback accepts a URL")
        return BytesIO(b"fixture")
    assert _online_reader(SkillHttpSession(fetch), "https://example.test/SKILL.md", 1) == b"fixture"


def test_malformed_github_token_is_not_passed_or_logged(caplog):
    requests = []
    token = "secret\ninvalid-header"
    with caplog.at_level(logging.DEBUG):
        session = SkillHttpSession(lambda req, timeout: requests.append(req) or BytesIO(b"{}"), token=token)
        _online_reader(session, "https://api.github.com/repos/org/repo", 1)
    assert requests[0].get_header("Authorization") is None
    assert "secret" not in caplog.text
    assert not session.diagnostics()["github_authenticated"]


def test_forbidden_index_is_only_queried_once_and_github_can_still_succeed():
    index_requests = []
    def fetch(req, timeout):
        if req.full_url.startswith("https://skills.sh/api/search"):
            index_requests.append(req.full_url)
            raise denial(req.full_url)
        if req.full_url.startswith("https://api.github.com/search/repositories"):
            return _Response({"items": [{"full_name": _REPO}]})
        return _online_response(req, timeout)
    result = search_online_skills(_online_work(), queries=["slides", "presentation"], opener=fetch)
    assert len(index_requests) == 1
    assert result.candidates
    assert result.diagnostics["errors"]
    assert result.diagnostics["http"]["access_issues"][0]["status_code"] == 403


def test_blocked_web_engine_is_skipped_for_remaining_queries():
    requests = []
    def fetch(req, timeout):
        requests.append(req.full_url)
        if req.full_url.startswith("https://www.bing.com/"):
            raise denial(req.full_url)
        if "duckduckgo.com" in req.full_url:
            return BytesIO(b'<html><a href="https://content.example.test/SKILL.md">slide skill</a></html>')
        return BytesIO(_SKILL)
    result = search_open_web_skills(_online_work(), queries=["slides", "presentation"], opener=fetch)
    assert result.candidates
    assert sum(url.startswith("https://www.bing.com/") for url in requests) == 1
    assert sum("duckduckgo.com" in url for url in requests) == 2


def test_challenge_page_is_not_requeried_or_treated_as_skill():
    counts = {}
    def fetch(req, timeout):
        host = req.full_url.split("/")[2]
        counts[host] = counts.get(host, 0) + 1
        return BytesIO(b"<html>verify you are human</html>")
    with pytest.raises(SkillSearchError):
        search_open_web_skills(_online_work(), queries=["slides", "presentation"], opener=fetch)
    assert all(value == 1 for value in counts.values())


def test_network_source_cache_changes_with_github_credentials_and_inherits_context(monkeypatch):
    from contextvars import ContextVar
    import promptsmith.skill_network_discovery as discovery
    from promptsmith.skill_search import SkillSearchResult
    marker = ContextVar("skill-search-fixture", default="missing")
    marker.set("current-search")
    calls = []
    def empty_source(*args, **kwargs):
        calls.append(marker.get())
        return SkillSearchResult(query="fixture", status="no_match", candidates=[], batch_id="fixture", catalog_hash="a")
    monkeypatch.setattr(discovery, "generate_skill_search_queries", lambda *a, **kw: ["slides"])
    monkeypatch.setattr(discovery, "search_online_skills", empty_source)
    monkeypatch.setattr(discovery, "search_open_web_skills", empty_source)
    monkeypatch.setattr(discovery, "select_skill_candidates_with_ai", lambda *a, **kw: [])
    discovery.clear_network_skill_cache()
    try:
        discovery.search_network_skill_candidates(_online_work(), task_text="slides", client=object())
        discovery.search_network_skill_candidates(_online_work(), task_text="slides", client=object())
        assert calls == ["current-search"] * 3
        result = discovery.search_network_skill_candidates(_online_work(), task_text="slides", client=object(), token="test-secret")
        assert calls == ["current-search"] * 6
        assert "test-secret" not in repr(result.diagnostics)
    finally:
        discovery.clear_network_skill_cache()
