"""Read-only Skill table projections; business state stays in SessionState."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from .skill_recommendation import sorted_recommendations


SOURCE_FILTERS = ("全部来源", "本地", "联网", "内置", "已选")


def source_group(row: Mapping[str, Any]) -> str:
    record = row.get("record_snapshot") or {}
    origin = row.get("origin") or record.get("origin")
    if origin == "remote":
        return "联网"
    if origin == "local_file":
        return "本地"
    return "内置"


def binding_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("skill_id", "")), str(row.get("key_work_id", "")),
            str(row.get("usage_mode", "method_adaptation")))


def candidate_identity(row: Mapping[str, Any]) -> tuple[str, ...]:
    # A local and a network reference must remain separately inspectable.
    return (source_group(row), *binding_key(row))


def table_rows(candidates: Iterable[Mapping[str, Any]],
               bindings: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Also project bindings whose original candidates aren't in an old session."""
    rows = [dict(row) for row in candidates]
    bindings = list(bindings)
    selected_keys = {binding_key(binding) for binding in bindings}
    by_snapshot = defaultdict(list)
    for row in rows:
        by_snapshot[(candidate_identity(row), row.get("record_hash"))].append(row)
        row["_binding_ids"] = []
        row["_already_selected"] = binding_key(row) in selected_keys
    for binding in bindings:
        matches = by_snapshot.get((candidate_identity(binding), binding.get("record_hash")), [])
        if matches:
            for row in matches:
                row["_binding_ids"].append(binding["binding_id"])
        else:
            row = dict(binding)
            row.update(candidate_id="selected:" + binding["binding_id"],
                       _binding_ids=[binding["binding_id"]], _binding_only=True,
                       _already_selected=True, selection_allowed=False)
            rows.append(row)
    return sorted_recommendations(rows)


def visible_rows(rows: Iterable[Mapping[str, Any]], *, source: str = "全部来源",
                 show_all: bool = False, limit: int = 6) -> list[dict[str, Any]]:
    ranked = sorted_recommendations(row for row in rows if
        source == "全部来源" or (source == "已选" and row.get("_binding_ids"))
        or source_group(row) == source)
    if show_all or source == "已选":
        return ranked
    groups = defaultdict(list)
    for row in ranked:
        groups[source_group(row)].append(row)
    # Share the default budget across sources instead of hiding a whole source
    # behind higher scores. Within each source, keep recommendation order.
    chosen = []
    budget = max(limit, len(groups))
    while len(chosen) < budget and any(groups.values()):
        for group in groups.values():
            if group and len(chosen) < budget:
                chosen.append(group.pop(0))
    chosen_ids = {row["candidate_id"] for row in chosen}
    chosen.extend(row for row in ranked if row.get("_binding_ids")
                  and row["candidate_id"] not in chosen_ids)
    return sorted_recommendations(chosen)
