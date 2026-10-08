"""Combine public network Skill evidence before model review."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
import threading
import time
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlsplit
from uuid import uuid4

from .open_skill_search import (
    OPEN_WEB_SEARCH_URL,
    generate_skill_search_queries,
    search_open_web_skills,
)
from .skill_ai_selection import SkillAiSelectionError, select_skill_candidates_with_ai
from .skill_search import (
    SkillSearchError,
    SkillSearchResult,
    _canonical,
    _online_skill_metadata,
    _sha256,
    search_online_skills,
)


_SOURCE_CACHE_TTL_SECONDS = 15 * 60
_SOURCE_CACHE: dict[str, tuple[float, SkillSearchResult]] = {}
_SOURCE_CACHE_LOCK = threading.Lock()
_MAX_VERIFIED_PER_SOURCE = 8


def _is_agent_skill_reference(candidate: Mapping[str, Any]) -> bool:
    """Reject remote candidates without a concrete Agent Skill artifact."""

    record = candidate.get("record_snapshot")
    if not isinstance(record, Mapping):
        return False
    evidence = record.get("evidence_bundle")
    evidence = evidence if isinstance(evidence, Mapping) else {}
    source_path = str(
        candidate.get("source_path") or record.get("source_path") or evidence.get("source_path") or ""
    ).replace("\\", "/")
    skill_id = str(candidate.get("skill_id") or record.get("skill_id") or "")
    source_url = str(candidate.get("source_url") or record.get("source_url") or evidence.get("source_url") or "")
    if not source_url:
        try:
            if urlsplit(skill_id).scheme.casefold() == "https":
                source_url = skill_id
        except ValueError:
            pass
    skill_file = source_path.rstrip("/").rsplit("/", 1)[-1].casefold() == "skill.md"
    try:
        url_path = urlsplit(source_url).path
    except ValueError:
        url_path = ""
    skill_url = url_path.rstrip("/").rsplit("/", 1)[-1].casefold() == "skill.md"

    discovery_source = str(record.get("discovery_source") or evidence.get("discovery_source") or "").casefold()
    repository = str(candidate.get("repository") or record.get("repository") or "")
    trusted_index_entry = (
        discovery_source == "skills.sh"
        and repository.startswith("https://github.com/")
        and bool(skill_id)
    )
    if not skill_file and not skill_url and not trusted_index_entry:
        return False

    source_text = record.get("source_text")
    if isinstance(source_text, str) and source_text.strip():
        try:
            _online_skill_metadata(source_text.encode("utf-8"))
        except SkillSearchError:
            return False
    return True


def clear_network_skill_cache() -> None:
    """Clear successful source results, primarily for tests and manual retry."""

    with _SOURCE_CACHE_LOCK:
        _SOURCE_CACHE.clear()


def _source_cache_key(
    source: str,
    *,
    works: list[dict[str, Any]],
    task_text: str,
    queries: list[str],
    search_url: str,
    web_search_url: str,
) -> str:
    return _sha256(_canonical({
        "source": source,
        "works": works,
        "task_text": task_text,
        "queries": queries,
        "search_url": search_url,
        "web_search_url": web_search_url,
        "verification_cap": _MAX_VERIFIED_PER_SOURCE,
    }))


def _cached_source_result(key: str) -> SkillSearchResult | None:
    now = time.monotonic()
    with _SOURCE_CACHE_LOCK:
        item = _SOURCE_CACHE.get(key)
        if item is None:
            return None
        created, result = item
        if now - created > _SOURCE_CACHE_TTL_SECONDS:
            _SOURCE_CACHE.pop(key, None)
            return None
        return deepcopy(result)


def _store_source_result(key: str, result: SkillSearchResult) -> None:
    if result.error:
        return
    with _SOURCE_CACHE_LOCK:
        _SOURCE_CACHE[key] = (time.monotonic(), deepcopy(result))


def search_network_skill_candidates(
    key_works: Iterable[Mapping[str, Any]],
    *,
    task_text: str,
    client: Any,
    search_url: str = "https://skills.sh",
    web_search_url: str = OPEN_WEB_SEARCH_URL,
    token: str | None = None,
    opener: Callable[..., Any] | None = None,
    timeout_seconds: float = 45.0,
    progress: Callable[[str], Any] | None = None,
) -> SkillSearchResult:
    """Search three independent sources in parallel, then review candidates.

    ``timeout_seconds`` is a per-source budget.  The three source adapters are
    submitted together, so the discovery wall time is bounded by the slowest
    source rather than the sum of all source budgets.
    """

    works = [dict(row) for row in key_works if isinstance(row, Mapping)]
    queries = generate_skill_search_queries(
        works, context_text=task_text, client=client, progress=progress
    )
    budget = float(timeout_seconds)
    if budget <= 0:
        raise ValueError("联网 Skill 搜索超时必须大于 0。")
    source_specs = (
        ("skill_index", "Skill 索引", lambda: search_online_skills(
            works, context_text=task_text, token=token, opener=opener,
            search_url=search_url, timeout_seconds=budget, queries=queries,
            include_unmatched=True, include_index=True,
            include_github_supplement=False,
            max_verified_candidates=_MAX_VERIFIED_PER_SOURCE, progress=progress,
        )),
        ("github", "GitHub", lambda: search_online_skills(
            works, context_text=task_text, token=token, opener=opener,
            search_url=search_url, timeout_seconds=budget, queries=queries,
            include_unmatched=True, include_index=False,
            include_github_supplement=True,
            max_verified_candidates=_MAX_VERIFIED_PER_SOURCE, progress=progress,
        )),
        ("open_web", "开放网页", lambda: search_open_web_skills(
            works, context_text=task_text, opener=opener, search_url=web_search_url,
            timeout_seconds=budget, queries=queries,
            max_verified_candidates=_MAX_VERIFIED_PER_SOURCE, progress=progress,
        )),
    )

    def run_source(source: str, label: str, search: Callable[[], SkillSearchResult]):
        key = _source_cache_key(
            source, works=works, task_text=task_text, queries=queries,
            search_url=search_url, web_search_url=web_search_url,
        )
        cached = _cached_source_result(key)
        if cached is not None:
            return source, label, cached, 0, None, True
        if progress:
            progress(f"正在检索{label}（单独预算 {budget:g} 秒）…")
        started = time.monotonic()
        try:
            result = search()
        except (SkillSearchError, OSError, ValueError) as exc:
            return source, label, None, int((time.monotonic() - started) * 1000), exc, False
        _store_source_result(key, result)
        return source, label, result, int((time.monotonic() - started) * 1000), None, False

    source_results: dict[str, SkillSearchResult] = {}
    source_diagnostics: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=len(source_specs), thread_name_prefix="skill-search") as pool:
        futures = {
            pool.submit(run_source, source, label, search): (source, label)
            for source, label, search in source_specs
        }
        for future in as_completed(futures):
            source, label = futures[future]
            try:
                source_name, source_label, result, elapsed_ms, exception, cached = future.result()
            except Exception as exc:  # defensive isolation for an adapter bug
                result = None
                elapsed_ms = 0
                exception = exc
                cached = False
                source_name, source_label = source, label
            source_error = None
            if exception is not None:
                source_error = str(exception)
            elif result is not None and result.error:
                source_error = str(result.error.get("message", "来源暂不可用"))
            if source_error:
                errors.append(f"{source_label}：{source_error}")
                if progress:
                    progress(f"{source_label}暂不可用，继续使用其他来源")
            if result is not None:
                source_results[source_name] = result
            diagnostics = result.diagnostics if result and isinstance(result.diagnostics, dict) else {}
            source_diagnostics[source_name] = {
                "label": source_label,
                "status": "error" if source_error else ("ok" if result and result.candidates else "no_match"),
                "elapsed_ms": elapsed_ms,
                "discovered_count": int(diagnostics.get("discovered_count", len(result.candidates) if result else 0)),
                "verified_count": int(diagnostics.get("verified_count", len(result.candidates) if result else 0)),
                "collected_count": int(diagnostics.get("collected_count", diagnostics.get("candidate_count", len(result.candidates) if result else 0))),
                "candidate_count": len(result.candidates) if result else 0,
                "search_engines": diagnostics.get("search_engines", []),
                "cached": cached,
                "error": source_error,
            }

    results = [source_results[source] for source, _label, _search in source_specs if source in source_results]

    discovered: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    seen_hashes: set[str] = set()
    rejected_non_skill_count = 0
    for result in results:
        for row in result.candidates:
            if not _is_agent_skill_reference(row):
                rejected_non_skill_count += 1
                continue
            source = str(row.get("source_url") or row.get("skill_id") or "").casefold()
            digest = str(row.get("content_sha256") or "")
            if source in seen_sources or (digest and digest in seen_hashes):
                continue
            seen_sources.add(source)
            if digest:
                seen_hashes.add(digest)
            discovered.append(row)

    if not discovered and errors and not results:
        raise SkillSearchError("network", "；".join(errors))
    if progress:
        progress(f"已收集 {len(discovered)} 个不同的 Skill 信息，正在让 AI 综合筛选…")
    ai_review_error = None
    try:
        selected = select_skill_candidates_with_ai(
            client, discovered, task_text=task_text, key_works=works, progress=progress
        )
    except SkillAiSelectionError as exc:
        ai_review_error = str(exc)
        selected = deepcopy(discovered)
        for row in selected:
            row["ai_review_status"] = "unavailable"
            row["ai_review_error"] = ai_review_error
            row.setdefault("match_reason", "已收集公开 Skill 信息，AI 筛选暂未完成，可先查看来源后自行判断。")
        if progress:
            progress("AI 筛选暂不可用，已保留公开信息候选供参考")
    diagnostics = {
        "queries": queries,
        "errors": errors,
        "sources": ["skill_index", "github", "open_web"],
        "verified_count": len(discovered),
        "collected_count": len(discovered),
        "rejected_non_skill_count": rejected_non_skill_count,
        "selected_count": len(selected),
        "parallel": True,
        "per_source_timeout_seconds": budget,
        "source_diagnostics": source_diagnostics,
        "ai_review_status": "failed" if ai_review_error else "completed",
        "ai_review_error": ai_review_error,
    }
    return SkillSearchResult(
        query="; ".join(queries), status="ok" if selected else "no_match",
        candidates=selected, batch_id=f"batch-network-{uuid4().hex}",
        catalog_hash=_sha256(_canonical({"sources": [row.get("record_hash") for row in selected]})),
        error={"kind": "network", "message": "；".join(errors)} if errors and not selected else None,
        diagnostics=diagnostics,
        unmatched_key_work_ids=[
            row["key_work_id"] for row in works
            if isinstance(row.get("key_work_id"), str)
            and row["key_work_id"] not in {item.get("key_work_id") for item in selected}
        ],
    )


__all__ = ["search_network_skill_candidates", "clear_network_skill_cache"]
