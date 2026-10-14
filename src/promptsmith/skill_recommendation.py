"""Bounded metadata ranking and display scores, independent of model calls."""
from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Iterable, Mapping

SHORTLIST_LIMIT = 12
REVIEW_LIMIT = 8
DISPLAY_LIMIT = 6


def rank_discovery_sources(rows: Iterable[Mapping[str, Any]], *, task_text: str,
                           key_works: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Rank public names/descriptions before spending the source-read budget.

    Search queries and popularity are deliberately not matching evidence.
    Zero-score sources remain eligible for bounded model review.
    """
    from .local_skill_search import _has_unrequested_named_domain, _metadata_score, _task_text
    works = list(key_works)
    task = _task_text(works, task_text)
    def score(row, context=task):
        name = str(row.get("name") or row.get("skill_id") or row.get("url") or row.get("repository") or "")
        description = str(row.get("description") or row.get("repository_description") or "")[:500]
        value = _metadata_score(context, name, description)[0]
        return value // 4 if _has_unrequested_named_domain(context, name) else value
    ranked = sorted((dict(row) for row in rows), key=score, reverse=True)
    # Reserve a strong source for each actual capability before the caller's
    # budget cut: a hundred documentation hits must not evict PDF delivery.
    chosen = []
    for work in works:
        context = _task_text([work], "")
        if ranked and context:
            best = max(ranked, key=lambda row: score(row, context))
            if score(best, context) > 0 and best not in chosen:
                chosen.append(best)
    return chosen + [row for row in ranked if row not in chosen]


def defensible_fallback_candidates(rows: Iterable[Mapping[str, Any]], *, task_text: str,
                                   key_works: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """When AI fails, show only candidates with an explainable capability hit."""
    from .local_skill_search import _has_defensible_match, _has_unrequested_named_domain, _task_text
    task = _task_text(list(key_works), task_text)
    selected = []
    for row in rows:
        record = row.get("record_snapshot") or {}
        info = {"name": row.get("name") or record.get("name", ""),
                "description": row.get("description") or record.get("description", ""),
                "body": record.get("source_text", "")}
        if not _has_unrequested_named_domain(task, str(info["name"])) and _has_defensible_match(task, info):
            selected.append(dict(row))
    return selected


def recommendation_score(row: Mapping[str, Any]) -> float:
    score = row.get("recommendation_score")
    if isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(score):
        return round(max(0., min(1., score)), 3)
    legacy = row.get("ai_relevance_score")
    if isinstance(legacy, int) and not isinstance(legacy, bool) and 1 <= legacy <= 5:
        return legacy / 5
    raw = row.get("match_score", 0)
    raw = raw if isinstance(raw, (int, float)) and not isinstance(raw, bool) and math.isfinite(raw) else 0
    return round(.65 * max(0, raw) / (max(0, raw) + 25), 3)


def sorted_recommendations(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted((dict(row) for row in rows), key=lambda r: (-recommendation_score(r), r.get("origin") == "remote", str(r.get("name", "")).casefold(), str(r.get("candidate_id", ""))))


def shortlist_candidates(rows: Iterable[Mapping[str, Any]], *, task_text: str,
                         key_works: Iterable[Mapping[str, Any]], limit: int = SHORTLIST_LIMIT) -> list[dict[str, Any]]:
    from .local_skill_search import _has_unrequested_named_domain, _metadata_score, _named_task_facets, _task_text
    works = list(key_works)
    tasks = [_task_text([work], task_text) for work in works] or [task_text]

    def score_for(task: str, row: Mapping[str, Any]) -> int:
        name = str(row.get("name", ""))
        score = _metadata_score(task, name, str(row.get("description", ""))[:500])[0]
        return score // 4 if _has_unrequested_named_domain(task, name) else score

    ranked = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        item = deepcopy(dict(row))
        record = item.get("record_snapshot") or {}
        name = str(item.get("name") or record.get("name") or "")[:160]
        description = str(item.get("description") or record.get("description") or "")[:500]
        item["name"], item["description"] = name, description
        scores = [score_for(task, item) for task in tasks]
        item["coarse_score"] = max(scores)
        ranked.append(item)
    ranked.sort(key=lambda r: (-r["coarse_score"], -recommendation_score(r), str(r.get("name", "")).casefold(), str(r.get("candidate_id", ""))))
    seen = set()
    result = []
    for row in ranked:
        # Same names with different bodies remain different Skills.
        digest = row.get("content_sha256")
        identity = (str(digest or row.get("skill_id") or row.get("candidate_id")), str(row.get("key_work_id", "")))
        if identity in seen:
            continue
        seen.add(identity)
        result.append(row)
    # Reserve slots for different works, then fill with the strongest metadata.
    chosen = []
    for task_index in range(len(tasks)):
        if len(chosen) >= limit or not result:
            break
        best = max(result, key=lambda r: score_for(tasks[task_index], r))
        if best not in chosen:
            chosen.append(best)
    # Broad design descriptions must not crowd out a task's named sub-skills.
    for task in tasks:
        facets = sorted(set().union(*(_named_task_facets(task, str(row.get("name", ""))) for row in result)))
        for facet in facets:
            pool = [row for row in result if facet in _named_task_facets(task, str(row.get("name", "")))
                    and not _has_unrequested_named_domain(task, str(row.get("name", "")))]
            if pool and len(chosen) < limit:
                best = max(pool, key=lambda r: score_for(task, r))
                if best not in chosen:
                    chosen.append(best)
    chosen.extend(row for row in result if row not in chosen)
    return chosen[:limit]
