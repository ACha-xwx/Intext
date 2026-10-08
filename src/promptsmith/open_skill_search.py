"""Open-web discovery for read-only ``SKILL.md`` sources.

This adapter is deliberately separate from the indexed Skill search. It can
use public search endpoints (or a caller supplied HTTPS endpoint), discover
links on arbitrary HTTPS domains, and retain readable ``SKILL.md`` files.
Unverified links remain in diagnostics instead of becoming selectable Skills.
Downloaded text is never imported, installed, or executed.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree

from .skill_search import (
    NETWORK_CATALOG_ID,
    NETWORK_CATALOG_VERSION,
    SkillSearchError,
    SkillSearchResult,
    _canonical,
    _online_json,
    _online_queries,
    _online_reader,
    _online_skill_metadata,
    _online_validate_search_url,
    _record_hash,
    _sha256,
)


OPEN_WEB_SEARCH_URL = "https://www.bing.com/search?format=rss&q={query}"
DUCKDUCKGO_SEARCH_URL = "https://html.duckduckgo.com/html/?q={query}"
MAX_SEARCH_RESULTS = 48
MAX_SKILL_SOURCES = 24
MAX_PAGE_LINKS = 80
MAX_SOURCE_BYTES = 350_000
DEFAULT_MAX_VERIFIED_CANDIDATES = 8


class OpenWebSkillSearchError(SkillSearchError):
    """A classified open-web search or source verification failure."""


class _SearchLinkParser(HTMLParser):
    """Extract anchors without interpreting arbitrary page markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href = ""
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a":
            return
        values = dict(attrs)
        self._href = values.get("href") or ""
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self._href:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = ""
            self._text = []


def _normalise_query_values(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        cleaned = " ".join(value.split()).strip()
        if not cleaned:
            continue
        # Search services differ in maximum query length.  Keep every query
        # compact and preserve a query's useful beginning.
        cleaned = cleaned[:160].rstrip()
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result[:8]


def _agent_skill_queries(values: Iterable[str]) -> list[str]:
    """Keep open-web queries focused on Agent Skill artifacts."""

    queries: list[str] = []
    for value in _normalise_query_values(values):
        folded = value.casefold()
        markers: list[str] = []
        if "agent" not in folded:
            markers.append("AI Agent")
        if "skill.md" not in folded:
            if "skill" not in folded:
                markers.append("Skill")
            markers.append("SKILL.md")
        suffix = " ".join(markers)
        if suffix:
            value = f"{value[: max(1, 160 - len(suffix) - 1)].rstrip()} {suffix}"
        queries.append(value)
    return queries


def _decode_model_content(value: Any) -> Any:
    if isinstance(value, Mapping):
        return value
    content = getattr(value, "content", value)
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig", errors="replace")
    if isinstance(content, str):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None
    return content


def generate_skill_search_queries(
    key_works: Iterable[Mapping[str, Any]],
    *,
    context_text: str | None = None,
    category: str | None = None,
    client: Any | None = None,
    fallback_queries: Iterable[str] | None = None,
    progress: Callable[[str], Any] | None = None,
) -> list[str]:
    """Generate several independent web queries, optionally with an AI client.

    ``client`` follows the existing ``complete_json(prompt, payload, schema)``
    contract.  Model output is treated as untrusted data: only returned query
    strings are accepted, and malformed output falls back to deterministic
    local signals.  The fallback makes the feature usable without an API key.
    """

    works = [dict(row) for row in key_works if isinstance(row, Mapping)]
    fallback = _agent_skill_queries(
        fallback_queries if fallback_queries is not None else _online_queries(
            works, context_text=context_text, category=category
        )
    )
    if client is None:
        if progress:
            progress(f"已生成 {len(fallback)} 个联网检索方向")
        return fallback
    prompt = (
        "你是 AI Agent Skill 检索查询规划器。根据用户任务和关键工作，生成 3 到 6 个互补的短查询。"
        "检索目标是供 AI Agent 加载并遵循的 Skill 指令包，通常以 SKILL.md 或 Skill 索引条目发布；"
        "普通教程、普通方法文章、普通网站、在线工具和一般 GitHub 仓库都不是 Skill，只能作为发现真实 Skill 文件的线索。"
        "每个查询覆盖不同任务能力，并包含 AI Agent Skill、agent skill、SKILL.md 等语义；"
        "优先使用中英文任务关键词，不要把搜索目标改成泛泛的方法或工具。"
        '只返回 JSON 对象 {"queries":["..."]}，不要返回解释。'
    )
    schema = {
        "type": "object",
        "required": ["queries"],
        "additionalProperties": False,
        "properties": {"queries": {"type": "array", "minItems": 1, "maxItems": 8, "items": {"type": "string"}}},
    }
    payload = {"context_text": context_text or "", "category": category or "", "key_works": works}
    try:
        if progress:
            progress("正在让 AI 规划多角度联网检索词…")
        raw = client.complete_json(prompt, payload, schema)
        decoded = _decode_model_content(raw)
        values = decoded.get("queries") if isinstance(decoded, Mapping) else None
        queries = _agent_skill_queries(values if isinstance(values, list) else [])
        if queries:
            return queries
    except Exception:
        # Query planning is an enhancement.  A provider outage must not hide
        # deterministic search terms or turn a valid search into a failure.
        pass
    return fallback


def _search_request_url(base_url: str, query: str) -> str:
    value = _online_validate_search_url(base_url)
    if "{query}" in value:
        return value.replace("{query}", quote(query, safe=""))
    parsed = urlsplit(value)
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    replaced = False
    output: list[tuple[str, str]] = []
    for key, current in pairs:
        if key.casefold() in {"q", "query", "search", "keyword"}:
            output.append((key, query))
            replaced = True
        else:
            output.append((key, current))
    if not replaced:
        output.append(("q", query))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", urlencode(output), ""))


def _safe_http_url(value: Any, *, base: str | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    value = html.unescape(value.strip())
    if value.startswith("//"):
        value = "https:" + value
    if base:
        value = urljoin(base, value)
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    if parsed.scheme.casefold() != "https" or not parsed.hostname or parsed.username or parsed.password:
        return ""
    # Search result redirectors often put the real URL in uddg/url/target.
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for key in ("uddg", "url", "target", "dest", "destination"):
        target = params.get(key)
        if target and target.startswith("https://"):
            return _safe_http_url(unquote(target))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))


def _urls_from_json(value: Any, *, base: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, Mapping):
        title = str(value.get("title") or value.get("name") or "")
        for key in ("url", "link", "href", "source_url", "source"):
            candidate = _safe_http_url(value.get(key), base=base)
            if candidate:
                found.append((candidate, title))
        for child in value.values():
            found.extend(_urls_from_json(child, base=base))
    elif isinstance(value, list):
        for child in value:
            found.extend(_urls_from_json(child, base=base))
    return found


def _urls_from_html(raw: bytes, *, base: str) -> list[tuple[str, str]]:
    try:
        parser = _SearchLinkParser()
        parser.feed(raw.decode("utf-8-sig", errors="replace"))
    except Exception:
        return []
    return [(_safe_http_url(href, base=base), text) for href, text in parser.links if _safe_http_url(href, base=base)]


def _urls_from_rss(raw: bytes) -> list[tuple[str, str]] | None:
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError:
        return None
    if root.tag.rsplit("}", 1)[-1].casefold() != "rss":
        return None
    links: list[tuple[str, str]] = []
    for item in root.findall("./channel/item"):
        url = _safe_http_url(item.findtext("link"))
        if url:
            links.append((url, item.findtext("title") or ""))
    return links


def _is_search_challenge(raw: bytes) -> bool:
    preview = raw[:100_000].lower()
    return b"anomaly.js" in preview or (
        b"<html" in preview
        and any(marker in preview for marker in (
            b"verify you are human", b"human verification", b"complete the captcha",
        ))
    )


def _looks_like_skill_url(url: str) -> bool:
    path = urlsplit(url).path.casefold().rstrip("/")
    return path.endswith("/skill.md") or path == "skill.md"


def _source_download_url(url: str) -> str:
    """GitHub blob pages are HTML; read their corresponding Markdown source."""

    parsed = urlsplit(url)
    if parsed.hostname and parsed.hostname.casefold() == "github.com":
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 5 and parts[2] == "blob" and parts[-1].casefold() == "skill.md":
            owner, repository, _blob, ref, *path = parts
            return f"https://raw.githubusercontent.com/{owner}/{repository}/{ref}/{'/'.join(path)}"
    return url


def _source_urls_from_result(
    opener: Callable[..., Any] | None,
    result_urls: Iterable[tuple[str, str]],
    *,
    deadline: float,
    progress: Callable[[str], Any] | None = None,
) -> list[tuple[str, str]]:
    """Turn search results and one level of landing pages into SKILL.md URLs."""

    sources: list[tuple[str, str]] = []
    seen: set[str] = set()
    for url, label in result_urls:
        if not url or url in seen:
            continue
        seen.add(url)
        if _looks_like_skill_url(url):
            sources.append((url, label))
            continue
        if time_remaining(deadline) <= 0:
            break
        try:
            raw = _online_reader(opener, url, min(5.0, time_remaining(deadline)))
        except SkillSearchError:
            continue
        if len(raw) > MAX_SOURCE_BYTES:
            continue
        for nested, nested_label in _urls_from_html(raw, base=url):
            if nested and _looks_like_skill_url(nested) and nested not in seen:
                seen.add(nested)
                sources.append((nested, nested_label or label))
                if progress:
                    progress(f"发现 SKILL.md：{nested}")
            if len(sources) >= MAX_SKILL_SOURCES:
                return sources
    return sources[:MAX_SKILL_SOURCES]


def time_remaining(deadline: float) -> float:
    # Kept as a function so tests can use deterministic monkeypatches without
    # replacing every timeout expression.
    import time

    return max(0.0, deadline - time.monotonic())


def _candidate_from_source(url: str, label: str, raw: bytes, *, query: str, key_work_id: str, searched_at: str) -> dict[str, Any]:
    name, description = _online_skill_metadata(raw)
    source_text = raw.decode("utf-8-sig", errors="replace")
    digest = hashlib.sha256(raw).hexdigest()
    record = {
        "record_schema_version": "remote-skill.open-web.v0.1",
        "skill_id": f"web:{url}",
        "name": name,
        "description": description,
        "source_type": "online",
        "source_kind": "web",
        "repository": "",
        "source_path": urlsplit(url).path.rsplit("/", 1)[-1] or "SKILL.md",
        "source_url": url,
        "fixed_commit": "unresolved",
        "searched_at": searched_at,
        "discovery_source": label or "open-web",
        "search_query": query,
        "source_text": source_text,
        "evidence_bundle": {
            "source_url": url,
            "source_path": urlsplit(url).path.rsplit("/", 1)[-1] or "SKILL.md",
            "name": name,
            "description": description,
            "search_query": query,
            "discovery_source": label or "open-web",
            "fetch_status": "full_skill",
            "fetch_errors": [],
        },
        "local_source_snapshot_sha256": digest,
        "content_sha256": digest,
        "content_hash_kind": "source_content",
        "method_adaptation_allowed": True,
        "adaptation_summary": "只参考已读取的远程 Agent Skill 指令，不安装或执行远程内容。",
        "limitations": ["远程 Skill 未安装或执行。"],
        "adaptation_prerequisites": [{"prerequisite_id": "remote-source-review", "description": "用户确认远程来源与许可。", "status": "unknown"}],
        "capabilities": [{"capability_id": "skill-reference", "summary": description, "work_signal_groups": [], "match_terms": [name], "inputs": [], "outputs": [], "limitations": ["远程 Skill 未安装或执行。"], "evidence": url}],
        "verification": {"source_read": True, "local_text_checked": False, "upstream_rechecked": False, "installed": False, "execution_tested": False, "verification_status": "source_read"},
        "origin": "remote",
    }
    record["record_hash"] = _record_hash(record)
    capability = record["capabilities"][0]
    candidate = {
        "candidate_id": f"candidate-web-{_sha256((url + ':' + key_work_id).encode('utf-8'))[:20]}",
        "skill_id": record["skill_id"],
        "key_work_id": key_work_id,
        "record_hash": record["record_hash"],
        "record_snapshot": deepcopy(record),
        "step_ids": [],
        "capability_ids": [capability["capability_id"]],
        "usage_mode": "method_adaptation",
        "method_adaptation_allowed": True,
        "adaptation_prerequisite_ids": ["remote-source-review"],
        "limitations": list(record["limitations"]),
        "compatibility": "conditional",
        "verification_status": "source_read",
        "selection_allowed": True,
        "match_score": 0,
        "matched_work_signals": [],
        "match_evidence": [{"group_id": "open_web_search", "label": "开放网络搜索", "matched_terms": [query], "matched_sources": [{"source": "open-web", "label": label or "网页搜索", "matched_terms": [query]}]}],
        "match_reason": "已从开放网络读取并核验 SKILL.md，可交由 AI 结合任务进一步筛选。",
        "source_path": record["source_path"],
        "local_snapshot_path": "",
        "source_url": url,
        "repository": "",
        "fixed_commit": "unresolved",
        "content_sha256": digest,
        "local_source_snapshot_sha256": digest,
        "description": description,
        "name": name,
        "suitable_work": ["需要参考公开 Agent Skill 指令的工作。"],
        "unsuitable_work": ["要求自动安装、执行或发布远程仓库内容的工作。"],
        "origin": "remote",
        "source_kind": "web",
        "provenance": {"origin": "remote", "source_url": url, "fixed_commit": "unresolved", "content_hash_kind": "source_content", "content_sha256": digest, "verification_status": "source_read", "source_read": True, "installed": False, "execution_tested": False},
    }
    return candidate


def _candidate_from_search_result(
    url: str,
    label: str,
    *,
    query: str,
    key_work_id: str,
    searched_at: str,
    error: str | None = None,
) -> dict[str, Any]:
    """Keep a direct SKILL.md hit when its content could not be read."""

    if not _looks_like_skill_url(url):
        raise ValueError("普通网页不能作为 Agent Skill 候选。")

    title = " ".join((label or "网页搜索结果").split())[:300]
    path = urlsplit(url).path.rsplit("/", 1)[-1] or "网页结果"
    name = title or path
    errors = [error[:500]] if error else []
    evidence_bundle = {
        "source_url": url,
        "source_path": path,
        "name": name,
        "description": title or "搜索结果未提供摘要。",
        "search_title": title,
        "search_snippet": title,
        "search_query": query,
        "discovery_source": "开放网页搜索",
        "fetch_status": "search_result_only",
        "fetch_errors": errors,
    }
    digest = hashlib.sha256(_canonical(evidence_bundle)).hexdigest()
    record = {
        "record_schema_version": "remote-skill.open-web.v0.2",
        "skill_id": f"web:{url}",
        "name": name,
        "description": evidence_bundle["description"],
        "source_type": "online",
        "source_kind": "web",
        "repository": "",
        "source_path": path,
        "source_url": url,
        "fixed_commit": "unresolved",
        "searched_at": searched_at,
        "discovery_source": "开放网页搜索",
        "search_query": query,
        "source_text": "",
        "evidence_bundle": evidence_bundle,
        "local_source_snapshot_sha256": digest,
        "content_sha256": digest,
        "content_hash_kind": "search_metadata",
        "method_adaptation_allowed": True,
        "adaptation_summary": "只提供公开搜索信息作为 Agent Skill 线索，不安装或执行网页内容。",
        "limitations": ["只有搜索结果或页面线索，完整 SKILL.md 尚未读取。"],
        "adaptation_prerequisites": [{
            "prerequisite_id": "remote-source-review",
            "description": "用户或下游 AI 进一步确认来源、内容和许可。",
            "status": "unknown",
        }],
        "capabilities": [{
            "capability_id": "skill-reference",
            "summary": evidence_bundle["description"],
            "work_signal_groups": [], "match_terms": [name],
            "inputs": [], "outputs": [],
            "limitations": ["完整 Skill 内容尚未读取。"],
            "evidence": url,
        }],
        "verification": {
            "source_read": False, "local_text_checked": False,
            "upstream_rechecked": False, "installed": False,
            "execution_tested": False, "verification_status": "search_result_only",
        },
        "origin": "remote",
        "remote_result": {"url": url, "title": title, "query": query},
    }
    record["record_hash"] = _record_hash(record)
    return {
        "candidate_id": f"candidate-web-{_sha256((url + ':' + key_work_id).encode('utf-8'))[:20]}",
        "skill_id": record["skill_id"], "key_work_id": key_work_id,
        "record_hash": record["record_hash"], "record_snapshot": deepcopy(record),
        "step_ids": [], "capability_ids": ["skill-reference"],
        "usage_mode": "method_adaptation", "method_adaptation_allowed": True,
        "adaptation_prerequisite_ids": ["remote-source-review"],
        "limitations": list(record["limitations"]), "compatibility": "conditional",
        "verification_status": "search_result_only", "selection_allowed": True,
        "match_score": 0, "matched_work_signals": [],
        "match_evidence": [{"group_id": "open_web_search", "label": "开放网页搜索", "matched_terms": [query],
                            "matched_sources": [{"source": "open-web", "label": title or "网页搜索", "matched_terms": [query]}]}],
        "match_reason": "已保留网页搜索线索，交由 AI 结合任务判断；完整 Skill 内容尚未读取。",
        "source_path": path, "local_snapshot_path": "", "source_url": url,
        "repository": "", "fixed_commit": "unresolved", "content_sha256": digest,
        "local_source_snapshot_sha256": digest, "description": record["description"],
        "name": name, "suitable_work": ["需要核对公开网页中 Agent Skill 来源的工作。"],
        "unsuitable_work": ["要求本应用自动安装或执行网页内容的工作。"],
        "origin": "remote", "source_kind": "web",
        "evidence_level": "search_result", "evidence_bundle": deepcopy(evidence_bundle),
        "evidence_limitations": list(record["limitations"]),
        "provenance": {"origin": "remote", "source_url": url, "fixed_commit": "unresolved",
                       "content_hash_kind": "search_metadata", "content_sha256": digest,
                       "verification_status": "search_result_only", "source_read": False,
                       "installed": False, "execution_tested": False},
    }


def search_open_web_skills(
    key_works: Iterable[Mapping[str, Any]],
    *,
    context_text: str | None = None,
    timeout_seconds: float = 45.0,
    opener: Callable[..., Any] | None = None,
    search_url: str = OPEN_WEB_SEARCH_URL,
    queries: Iterable[str] | None = None,
    query_client: Any | None = None,
    ai_client: Any | None = None,
    category: str | None = None,
    max_verified_candidates: int = DEFAULT_MAX_VERIFIED_CANDIDATES,
    progress: Callable[[str], Any] | None = None,
) -> SkillSearchResult:
    """Search arbitrary HTTPS web results and verify actual ``SKILL.md`` files."""

    if timeout_seconds <= 0:
        raise ValueError("开放网络 Skill 搜索超时必须大于 0。")
    if (
        isinstance(max_verified_candidates, bool)
        or not isinstance(max_verified_candidates, int)
        or max_verified_candidates < 1
    ):
        raise ValueError("开放网络 Skill 搜索候选上限必须是正整数。")
    works = [dict(row) for row in key_works if isinstance(row, Mapping)]
    work_ids = [row["key_work_id"] for row in works if isinstance(row.get("key_work_id"), str) and row["key_work_id"].strip()]
    anchor_work = work_ids[0] if work_ids else "network-search"
    search_terms = _agent_skill_queries(queries or [])
    if not search_terms:
        search_terms = generate_skill_search_queries(works, context_text=context_text, category=category, client=query_client, progress=progress)
    if not search_terms:
        raise OpenWebSkillSearchError("query", "没有生成有效的开放网络检索词。")
    base_url = _online_validate_search_url(search_url)
    built_in_search = base_url == OPEN_WEB_SEARCH_URL
    host = (urlsplit(base_url).hostname or "").casefold()
    custom_label = "DuckDuckGo" if host in {"duckduckgo.com", "html.duckduckgo.com"} else host or "自定义搜索"
    if built_in_search:
        engines = [("Bing", base_url), ("DuckDuckGo", DUCKDUCKGO_SEARCH_URL)]
    else:
        # A custom endpoint supplements public discovery. A failure or narrow
        # index must not turn the whole search into a single-site search.
        engines = [
            (custom_label, base_url),
            ("Bing", OPEN_WEB_SEARCH_URL),
            ("DuckDuckGo", DUCKDUCKGO_SEARCH_URL),
        ]
    import time

    deadline = time.monotonic() + float(timeout_seconds)
    searched_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="seconds")
    errors: list[str] = []
    unverified_sources: list[dict[str, str]] = []
    result_links: list[tuple[str, str]] = []
    seen_results: set[str] = set()
    attempted_engines: list[str] = []
    for term in search_terms:
        if time_remaining(deadline) <= 0:
            errors.append("开放网络搜索超过时间限制。")
            break
        for engine_name, engine_url in engines:
            if time_remaining(deadline) <= 0:
                errors.append("开放网络搜索超过时间限制。")
                break
            endpoint = _search_request_url(engine_url, term)
            if engine_name not in attempted_engines:
                attempted_engines.append(engine_name)
            if progress:
                progress(f"正在搜索开放网络（{engine_name}）：{term}")
            try:
                raw = _online_reader(opener, endpoint, min(8.0, time_remaining(deadline)))
                if _is_search_challenge(raw):
                    raise OpenWebSkillSearchError("blocked", f"{engine_name} 返回了验证页面。")
                rss_links = _urls_from_rss(raw)
                if rss_links is not None:
                    links = rss_links
                elif built_in_search and engine_name == "Bing":
                    raise OpenWebSkillSearchError("invalid_response", "Bing 未返回可解析的 RSS 搜索结果。")
                else:
                    try:
                        payload = _online_json(raw)
                        links = _urls_from_json(payload, base=endpoint)
                    except SkillSearchError:
                        links = _urls_from_html(raw, base=endpoint)
                for url, label in links:
                    if url and url not in seen_results:
                        seen_results.add(url)
                        result_links.append((url, label))
                        if len(result_links) >= MAX_SEARCH_RESULTS:
                            break
                # Continue with the other engines so a narrow or partial
                # endpoint does not hide public search results. Once an engine
                # returns links, avoid redundant requests for this query.
                if links:
                    break
            except (SkillSearchError, OSError, ValueError) as exc:
                errors.append(f"{engine_name}（{term}）：{exc}")
    skill_urls = _source_urls_from_result(
        opener,
        result_links[:MAX_SEARCH_RESULTS],
        deadline=deadline,
        progress=progress,
    )
    candidates: list[dict[str, Any]] = []
    for source_url, label in skill_urls[:max_verified_candidates]:
        if time_remaining(deadline) <= 0:
            errors.append("开放网络搜索超过时间限制。")
            break
        try:
            raw = _online_reader(opener, _source_download_url(source_url), min(8.0, time_remaining(deadline)))
            if len(raw) > MAX_SOURCE_BYTES:
                raise OpenWebSkillSearchError("response_too_large", "SKILL.md 文件过大，已跳过。")
            candidate = _candidate_from_source(source_url, label, raw, query=search_terms[0], key_work_id=anchor_work, searched_at=searched_at)
            candidates.append(candidate)
            if progress:
                    progress(f"已读取 Skill 信息：{candidate['name']}")
        except (SkillSearchError, OSError, ValueError) as exc:
            errors.append(f"{source_url}：{exc}")
            unverified_sources.append({"url": source_url, "label": label, "error": str(exc)[:500]})
            if progress:
                progress(f"未能确认 Skill 文件，已记录来源线索：{label or source_url}")
    if ai_client is not None and candidates:
        from .skill_ai_selection import SkillAiSelectionError, select_skill_candidates_with_ai

        try:
            candidates = select_skill_candidates_with_ai(ai_client, candidates, task_text=context_text or "", key_works=works, progress=progress)
        except SkillAiSelectionError as exc:
            errors.append(str(exc))
            for row in candidates:
                row["ai_review_status"] = "unavailable"
                row["ai_review_error"] = str(exc)
    catalog_hash = _sha256(_canonical({"catalog": NETWORK_CATALOG_ID, "version": "open-web.v1", "queries": search_terms, "records": [row["record_hash"] for row in candidates]}))
    status = "ok" if candidates else "no_match"
    if not result_links and errors:
        raise OpenWebSkillSearchError("network", "；".join(errors[:4]))
    diagnostics = {
        "queries": search_terms,
        "search_url": base_url,
        "search_engines": attempted_engines,
        "source_policy": "open-web",
        "result_count": len(result_links),
        "discovered_count": len(skill_urls),
        "verified_count": len(candidates),
        "verification_cap": max_verified_candidates,
        "errors": errors[:12],
        "unverified_sources": unverified_sources[:MAX_SKILL_SOURCES],
        "searched_at": searched_at,
    }
    return SkillSearchResult(query="; ".join(search_terms), status=status, candidates=candidates, batch_id=f"batch-open-web-{_sha256((searched_at + '|' + '|'.join(search_terms)).encode())[:16]}", catalog_hash=catalog_hash, error={"kind": "network", "message": errors[0]} if errors and not candidates else None, diagnostics=diagnostics, unmatched_key_work_ids=[work_id for work_id in work_ids if not any(row.get("key_work_id") == work_id for row in candidates)])


# Friendly aliases for callers that describe this as generic/public web search.
search_generic_web_skills = search_open_web_skills
search_public_web_skills = search_open_web_skills


__all__ = [
    "OPEN_WEB_SEARCH_URL",
    "OpenWebSkillSearchError",
    "generate_skill_search_queries",
    "search_open_web_skills",
    "search_generic_web_skills",
    "search_public_web_skills",
]
