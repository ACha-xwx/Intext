"""Load and deterministically filter the local Skill method catalog.

The catalog is deliberately data-only.  Loading it never imports, installs, or
executes a source Skill.  Candidate records carry enough provenance for later
M3/M4 requests to bind a snapshot rather than a mutable name.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


CATALOG_SCHEMA_VERSION = "catalog.v0.1"
_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


def _default_catalog_path() -> Path:
    try:
        from .paths import resource_root

        return resource_root() / "resources" / "skill_catalog" / "catalog_v0.1.json"
    except (FileNotFoundError, ImportError):
        return Path(__file__).resolve().parents[2] / "resources" / "skill_catalog" / "catalog_v0.1.json"


class SkillCatalogError(ValueError):
    """Raised when a catalog cannot be trusted as structured local data."""

    def __init__(self, message: str, *, code: str = "invalid_catalog") -> None:
        super().__init__(message)
        self.code = code


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
        "utf-8"
    )


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _record_hash(record: Mapping[str, Any]) -> str:
    body = deepcopy(dict(record))
    body.pop("record_hash", None)
    return _sha256(_canonical(body))


def _clean_terms(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(item.strip() for item in value if isinstance(item, str) and item.strip()))


def _work_text(work: Mapping[str, Any]) -> str:
    values: list[str] = []
    for key in ("title", "goal", "purpose", "description"):
        value = work.get(key)
        if isinstance(value, str):
            values.append(value)
    for key in ("inputs", "outputs", "checkpoints", "actions"):
        values.extend(value for value in work.get(key, []) if isinstance(value, str))
    return " ".join(values).casefold()


def _contains_term(text: str, term: str) -> bool:
    normalized = term.strip().casefold()
    return bool(normalized) and normalized in text


def _verification_levels(record: Mapping[str, Any]) -> dict[str, str]:
    verification = record.get("verification")
    verification = verification if isinstance(verification, Mapping) else {}
    repo = record.get("repository")
    commit = record.get("fixed_commit")
    source_url = record.get("source_url")
    source_traceable = (
        isinstance(repo, str)
        and bool(repo.strip())
        and isinstance(commit, str)
        and bool(re.fullmatch(r"[0-9a-fA-F]{40}", commit))
        and isinstance(source_url, str)
        and source_url.startswith(f"{repo.rstrip('/')}/blob/{commit}/")
    )
    host_status = verification.get("host_dependencies_available", "unknown")
    if host_status not in {"available", "unavailable", "unknown"}:
        host_status = "unknown"
    return {
        "catalog_recorded": "verified",
        "local_text_checked": "verified" if verification.get("local_text_checked") is True else "unknown",
        "fixed_source_traceable": "verified" if source_traceable else "unknown",
        "host_dependencies_available": host_status,
        "execution_tested": "verified" if verification.get("execution_tested") is True else "not_tested",
    }


@dataclass(frozen=True)
class CatalogMatch:
    status: str
    candidates: list[dict[str, Any]]
    unmatched_key_work_ids: list[str]
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "candidates": deepcopy(self.candidates),
            "unmatched_key_work_ids": list(self.unmatched_key_work_ids),
            "error": deepcopy(self.error),
        }


MatchResult = CatalogMatch


class SkillCatalog:
    """Validated, immutable-in-use view of ``catalog_v0.1.json``."""

    def __init__(self, payload: Mapping[str, Any], path: Path, source_root: Path | None) -> None:
        self.schema_version = str(payload["schema_version"])
        self.catalog_id = str(payload["catalog_id"])
        self.catalog_version = str(payload.get("catalog_version", ""))
        self.path = path
        self.source_root = source_root
        self.records = tuple(deepcopy(row) for row in payload["records"])
        self.snapshot_hash = _sha256(_canonical({"schema_version": self.schema_version, "catalog_id": self.catalog_id, "catalog_version": self.catalog_version, "records": self.records}))
        self._source_verification: dict[str, dict[str, Any]] | None = None

    @classmethod
    def load(
        cls,
        path: str | Path | None = None,
        *,
        source_root: str | Path | None = None,
        verify_sources: bool = False,
    ) -> "SkillCatalog":
        location = Path(path) if path is not None else _default_catalog_path()
        location = location.expanduser().resolve()
        try:
            raw = location.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise SkillCatalogError(f"无法读取 Skill 目录：{exc}", code="catalog_unavailable") from exc
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SkillCatalogError(f"Skill 目录不是有效 JSON：{exc}", code="invalid_json") from exc
        cls._validate_payload(payload)
        root = Path(source_root).expanduser().resolve() if source_root is not None else location.parent
        catalog = cls(payload, location, root)
        if verify_sources:
            catalog.verify_sources(root)
        return catalog

    @staticmethod
    def _validate_payload(payload: Any) -> None:
        if not isinstance(payload, dict):
            raise SkillCatalogError("Skill 目录根节点必须是对象。", code="invalid_shape")
        if payload.get("schema_version") != CATALOG_SCHEMA_VERSION:
            raise SkillCatalogError(
                f"不支持的 Skill 目录格式：{payload.get('schema_version')}", code="unsupported_version"
            )
        if not isinstance(payload.get("catalog_id"), str) or not payload["catalog_id"].strip():
            raise SkillCatalogError("Skill 目录缺少 catalog_id。", code="invalid_shape")
        records = payload.get("records")
        if not isinstance(records, list):
            raise SkillCatalogError("Skill 目录 records 必须是数组。", code="invalid_shape")
        seen: set[str] = set()
        for record in records:
            if not isinstance(record, dict):
                raise SkillCatalogError("Skill 目录包含非对象记录。", code="invalid_record")
            skill_id = record.get("skill_id")
            if not isinstance(skill_id, str) or not skill_id.strip() or skill_id in seen:
                raise SkillCatalogError("Skill 目录包含空或重复的 skill_id。", code="invalid_record")
            seen.add(skill_id)
            if not isinstance(record.get("source_path"), str) or not record["source_path"].strip():
                raise SkillCatalogError(f"记录 {skill_id} 缺少 source_path。", code="invalid_record")
            source_hash = record.get("local_source_snapshot_sha256")
            if not isinstance(source_hash, str) or not _HEX64.fullmatch(source_hash):
                raise SkillCatalogError(f"记录 {skill_id} 的来源哈希无效。", code="invalid_record")
            expected = record.get("record_hash")
            if not isinstance(expected, str) or not _HEX64.fullmatch(expected):
                raise SkillCatalogError(f"记录 {skill_id} 缺少 record_hash。", code="invalid_record")
            if expected.casefold() != _record_hash(record):
                raise SkillCatalogError(f"记录 {skill_id} 的 record_hash 不匹配。", code="record_hash_mismatch")
            capabilities = record.get("capabilities")
            if not isinstance(capabilities, list) or not capabilities:
                raise SkillCatalogError(f"记录 {skill_id} 缺少能力摘要。", code="invalid_record")
            cap_ids: set[str] = set()
            for capability in capabilities:
                if not isinstance(capability, dict):
                    raise SkillCatalogError(f"记录 {skill_id} 的能力摘要无效。", code="invalid_record")
                capability_id = capability.get("capability_id")
                if not isinstance(capability_id, str) or not capability_id.strip() or capability_id in cap_ids:
                    raise SkillCatalogError(f"记录 {skill_id} 的能力编号重复或为空。", code="invalid_record")
                cap_ids.add(capability_id)
                groups = capability.get("work_signal_groups", [])
                if not isinstance(groups, list):
                    raise SkillCatalogError(f"记录 {skill_id} 的工作信号组无效。", code="invalid_record")
                group_ids: set[str] = set()
                for group in groups:
                    if not isinstance(group, dict):
                        raise SkillCatalogError(f"记录 {skill_id} 的工作信号组无效。", code="invalid_record")
                    group_id = group.get("group_id")
                    terms = _clean_terms(group.get("terms"))
                    if not isinstance(group_id, str) or not group_id.strip() or group_id in group_ids or not terms:
                        raise SkillCatalogError(f"记录 {skill_id} 的工作信号组缺少唯一编号或信号。", code="invalid_record")
                    group_ids.add(group_id)

    def get(self, skill_id: str) -> dict[str, Any] | None:
        for row in self.records:
            if row["skill_id"] == skill_id:
                return deepcopy(row)
        return None

    def assess_bindings(self, bindings: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        """Compare selected bindings with this catalog without replacing snapshots."""
        affected: list[str] = []
        reasons: list[str] = []
        for binding in bindings:
            binding_id = str(binding.get("binding_id", ""))
            skill_id = str(binding.get("skill_id", ""))
            expected_hash = binding.get("record_hash")
            current = self.get(skill_id)
            if current is None:
                affected.append(binding_id)
                reasons.append(f"目录中已找不到方法 {skill_id}。")
                continue
            if current.get("record_hash") != expected_hash:
                affected.append(binding_id)
                reasons.append(f"方法 {skill_id} 的目录记录已变化。")
                continue
            if self._source_verification is not None:
                verification = self._source_verification.get(skill_id)
                if not verification or verification.get("verification_status") != "source_verified":
                    affected.append(binding_id)
                    status = (verification or {}).get("verification_status", "source_unavailable")
                    if status == "source_mismatch":
                        reasons.append(f"方法 {skill_id} 的本地来源文件已变化。")
                    else:
                        reasons.append(f"方法 {skill_id} 的本地来源文件不可用。")
        return {
            "status": "stale" if affected else "ok",
            "affected_binding_ids": list(dict.fromkeys(affected)),
            "reasons": list(dict.fromkeys(reasons)),
        }

    def verify_sources(self, source_root: str | Path | None = None) -> dict[str, dict[str, Any]]:
        root = Path(source_root).expanduser().resolve() if source_root is not None else self.source_root
        result: dict[str, dict[str, Any]] = {}
        for record in self.records:
            source_path = Path(record["source_path"])
            if not source_path.is_absolute() and root is not None:
                source_path = root / source_path
            exists = source_path.is_file()
            actual_hash = _sha256(source_path.read_bytes()) if exists else None
            expected_hash = record["local_source_snapshot_sha256"]
            result[record["skill_id"]] = {
                "skill_id": record["skill_id"],
                "source_path": str(source_path),
                "source_exists": exists,
                "actual_sha256": actual_hash,
                "expected_sha256": expected_hash,
                "hash_matches": bool(exists and actual_hash and actual_hash.casefold() == expected_hash.casefold()),
                "record_hash_matches": _record_hash(record).casefold() == record["record_hash"].casefold(),
                "verification_levels": _verification_levels(record),
                "verification_status": (
                    "source_verified"
                    if exists and actual_hash and actual_hash.casefold() == expected_hash.casefold()
                    else "source_mismatch"
                    if exists
                    else "source_unavailable"
                ),
                "installed": bool(record.get("verification", {}).get("installed", False)),
                "execution_tested": bool(record.get("verification", {}).get("execution_tested", False)),
            }
        self._source_verification = deepcopy(result)
        return result

    def match(
        self,
        key_works: Mapping[str, Any] | Iterable[Mapping[str, Any]],
        *,
        context_text: str | None = None,
        target_environment: Mapping[str, Any] | None = None,
        max_per_work: int = 3,
        max_total: int = 8,
    ) -> CatalogMatch:
        if isinstance(key_works, Mapping):
            works = [key_works]
        else:
            works = list(key_works)
        work_ids: list[str] = []
        for work in works:
            if not isinstance(work, Mapping) or not isinstance(work.get("key_work_id"), str) or not work["key_work_id"].strip():
                raise SkillCatalogError("关键工作必须包含非空 key_work_id。", code="invalid_input")
            if work["key_work_id"] in work_ids:
                raise SkillCatalogError("关键工作包含重复 key_work_id。", code="invalid_input")
            work_ids.append(work["key_work_id"])
        if not self.records:
            return CatalogMatch("empty", [], work_ids)
        task_context = context_text.strip().casefold() if isinstance(context_text, str) else ""
        forbidden = [str(value).casefold() for value in (target_environment or {}).get("forbidden_actions", []) if str(value).strip()]
        all_candidates: list[dict[str, Any]] = []
        unmatched: list[str] = []
        for work in works:
            text = _work_text(work)
            scored: list[tuple[int, str, dict[str, Any]]] = []
            for record in self.records:
                matched_caps: list[dict[str, Any]] = []
                score = 0
                for capability in record["capabilities"]:
                    signal_groups = capability.get("work_signal_groups", [])
                    group_evidence: list[dict[str, Any]] = []
                    if signal_groups:
                        for group in signal_groups:
                            group_terms = _clean_terms(group.get("terms"))
                            matched_sources: list[dict[str, Any]] = []
                            work_matches = [term for term in group_terms if _contains_term(text, term)]
                            if work_matches:
                                matched_sources.append(
                                    {"source": "key_work", "label": "关键工作", "matched_terms": work_matches}
                                )
                            if group.get("allow_task_context") is True and task_context:
                                context_matches = [
                                    term for term in group_terms if _contains_term(task_context, term)
                                ]
                                if context_matches:
                                    matched_sources.append(
                                        {
                                            "source": "task_context",
                                            "label": "任务描述",
                                            "matched_terms": context_matches,
                                        }
                                    )
                            matched_signals = list(
                                dict.fromkeys(
                                    term
                                    for source in matched_sources
                                    for term in source["matched_terms"]
                                )
                            )
                            if not matched_signals:
                                group_evidence = []
                                break
                            group_evidence.append(
                                {
                                    "group_id": group["group_id"],
                                    "label": str(group.get("label", group["group_id"])),
                                    "matched_terms": matched_signals,
                                    "matched_sources": matched_sources,
                                }
                            )
                    else:
                        signals = _clean_terms(capability.get("work_signals"))
                        matched_signals = [term for term in signals if _contains_term(text, term)]
                        minimum = capability.get("min_work_signal_matches", 1)
                        if not isinstance(minimum, int) or isinstance(minimum, bool):
                            minimum = 1
                        if len(matched_signals) >= max(1, minimum):
                            group_evidence.append(
                                {
                                    "group_id": "work_signals",
                                    "label": "关键工作信号",
                                    "matched_terms": matched_signals,
                                    "matched_sources": [
                                        {"source": "key_work", "label": "关键工作", "matched_terms": matched_signals}
                                    ],
                                }
                            )
                    if not group_evidence:
                        continue
                    detail_terms = _clean_terms(capability.get("match_terms"))
                    matched_details = [term for term in detail_terms if _contains_term(text, term)]
                    score += 3 * sum(len(group["matched_terms"]) for group in group_evidence) + len(matched_details)
                    matched_caps.append(
                        {
                            "capability": capability,
                            "group_evidence": group_evidence,
                            "matched_details": matched_details,
                        }
                    )
                if not matched_caps:
                    continue
                cap_ids = [item["capability"]["capability_id"] for item in matched_caps]
                matched_signals = list(
                    dict.fromkeys(
                        term
                        for item in matched_caps
                        for group in item["group_evidence"]
                        for term in group["matched_terms"]
                    )
                )
                match_groups = [
                    group
                    for item in matched_caps
                    for group in item["group_evidence"]
                ]
                match_reason = "匹配依据：" + "；".join(
                    f"{group['label']}（"
                    + "；".join(
                        f"{source['label']}：{', '.join(source['matched_terms'])}"
                        for source in group.get("matched_sources", [])
                    )
                    + "）"
                    for group in match_groups
                ) + "。"
                incompatible = any(
                    _contains_term(" ".join(forbidden), phrase)
                    for phrase in _clean_terms(record.get("incompatible_if"))
                )
                source_status = (
                    self._source_verification.get(record["skill_id"], {}).get("verification_status")
                    if self._source_verification is not None
                    else "catalog_recorded"
                )
                source_available = source_status in {"source_verified", "catalog_recorded"}
                candidate_id = f"candidate-{record['skill_id']}-{work['key_work_id']}"
                step_ids = _clean_terms(work.get("step_ids"))
                candidate = {
                    "candidate_id": candidate_id,
                    "skill_id": record["skill_id"],
                    "key_work_id": work["key_work_id"],
                    "record_hash": record["record_hash"],
                    "record_snapshot": deepcopy(record),
                    "step_ids": step_ids,
                    "capability_ids": cap_ids,
                    "usage_mode": "method_adaptation",
                    "method_adaptation_allowed": bool(record.get("method_adaptation_allowed", False)),
                    "adaptation_prerequisite_ids": [
                        row.get("prerequisite_id")
                        for row in record.get("adaptation_prerequisites", [])
                        if isinstance(row, dict) and isinstance(row.get("prerequisite_id"), str)
                    ],
                    "limitations": list(
                        dict.fromkeys(
                            limitation
                            for item in matched_caps
                            for limitation in _clean_terms(item["capability"].get("limitations"))
                        )
                    ),
                    "compatibility": (
                        "incompatible"
                        if incompatible
                        else "unverified"
                        if not source_available
                        else "compatible"
                    ),
                    "verification_status": source_status,
                    "selection_allowed": (
                        bool(record.get("method_adaptation_allowed", False))
                        and not incompatible
                        and source_available
                    ),
                    "match_score": score,
                    "matched_work_signals": matched_signals,
                    "match_evidence": deepcopy(match_groups),
                    "match_reason": match_reason,
                    "source_path": record["source_path"],
                    "local_snapshot_path": record.get("local_snapshot_path", record["source_path"]),
                    "source_url": record.get("source_url"),
                    "repository": record.get("repository"),
                    "fixed_commit": record.get("fixed_commit"),
                    "suitable_work": _clean_terms(record.get("suitable_work")),
                    "unsuitable_work": _clean_terms(record.get("unsuitable_work")),
                    "host_tool_requirements": _clean_terms(record.get("host_tool_requirements")),
                    "original_side_effects": _clean_terms(record.get("original_side_effects")),
                    "adaptation_side_effects": _clean_terms(record.get("adaptation_side_effects")),
                    "license": deepcopy(record.get("license", {})),
                    "verification_levels": _verification_levels(record),
                }
                scored.append((score, record["skill_id"], candidate))
            scored.sort(key=lambda item: (-item[0], item[1], work["key_work_id"]))
            selected = [item[2] for item in scored[: max(0, max_per_work)]]
            all_candidates.extend(selected)
            if not any(item["selection_allowed"] for item in selected):
                unmatched.append(work["key_work_id"])
        all_candidates.sort(key=lambda item: (-item["match_score"], item["skill_id"], item["key_work_id"]))
        all_candidates = all_candidates[: max(0, max_total)]
        compatible = [item for item in all_candidates if item["selection_allowed"]]
        if not all_candidates:
            status = "no_match"
        elif not compatible:
            status = "incompatible"
        else:
            status = "ok"
            unmatched = [work_id for work_id in unmatched if work_id not in {row["key_work_id"] for row in compatible}]
        return CatalogMatch(status, all_candidates, unmatched)


def load_catalog(
    path: str | Path | None = None,
    *,
    source_root: str | Path | None = None,
    verify_sources: bool = False,
) -> SkillCatalog:
    return SkillCatalog.load(path, source_root=source_root, verify_sources=verify_sources)


def match_catalog(
    catalog: SkillCatalog,
    key_works: Mapping[str, Any] | Iterable[Mapping[str, Any]],
    *,
    context_text: str | None = None,
    target_environment: Mapping[str, Any] | None = None,
    max_per_work: int = 3,
    max_total: int = 8,
) -> CatalogMatch:
    return catalog.match(
        key_works,
        context_text=context_text,
        target_environment=target_environment,
        max_per_work=max_per_work,
        max_total=max_total,
    )
