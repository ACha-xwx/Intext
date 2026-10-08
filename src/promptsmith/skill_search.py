"""Read-only GitHub Skill discovery.

Network results deliberately stay separate from :mod:`skill_catalog`.  A
remote result is a recommendation with immutable provenance; it is never
treated as an installed local Skill and no downloaded text is executed.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from copy import deepcopy
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from uuid import uuid4


GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
NETWORK_CATALOG_ID = "promptsmith-github-network"
NETWORK_CATALOG_VERSION = "github-search.v1"
_SHA40 = re.compile(r"^[0-9a-fA-F]{40}$")


class SkillSearchError(RuntimeError):
    """A classified failure while reading a remote Skill index."""

    def __init__(self, kind: str, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _record_hash(record: Mapping[str, Any]) -> str:
    body = deepcopy(dict(record))
    body.pop("record_hash", None)
    return _sha256(_canonical(body))


def _valid_sha(value: Any) -> str | None:
    return value.strip().lower() if isinstance(value, str) and _SHA40.fullmatch(value.strip()) else None


def _nonempty(value: Any, fallback: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _repository_url(full_name: str, item: Mapping[str, Any]) -> str:
    value = _nonempty(item.get("repository_url"))
    if value:
        return value.rstrip("/")
    value = _nonempty(item.get("html_url"))
    if value:
        marker = "/blob/"
        if marker in value:
            return value.split(marker, 1)[0]
        return value.rstrip("/")
    return f"https://github.com/{full_name}" if full_name else ""


def _query_for_search(query: str, search_type: str) -> str:
    query = query.strip()
    if search_type == "code" and "filename:SKILL.md" not in query and "path:SKILL.md" not in query:
        return f"{query} filename:SKILL.md" if query else "filename:SKILL.md"
    return query


def build_github_search_request(
    query: str,
    *,
    token: str | None = None,
    page: int = 1,
    per_page: int = 30,
    api_base_url: str = GITHUB_API_BASE,
    search_type: str = "repositories",
) -> Request:
    """Build a bounded GitHub search request without performing I/O."""

    if not isinstance(query, str) or not query.strip():
        raise ValueError("联网 Skill 搜索关键词不能为空。")
    if search_type not in {"repositories", "code"}:
        raise ValueError("GitHub 搜索类型必须是 repositories 或 code。")
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        raise ValueError("GitHub 搜索页码必须是正整数。")
    if isinstance(per_page, bool) or not isinstance(per_page, int) or not 1 <= per_page <= 100:
        raise ValueError("GitHub 搜索每页数量必须在 1 到 100 之间。")
    parsed_base = _validated_api_base_url(api_base_url)
    endpoint = f"{parsed_base.geturl().rstrip('/')}/search/{search_type}"
    params = {
        "q": _query_for_search(query, search_type),
        "page": page,
        "per_page": per_page,
    }
    if search_type == "repositories":
        params.update({"sort": "stars", "order": "desc"})
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "PromptSmith-SkillSearch/1.0",
    }
    official_github_api = parsed_base.hostname == "api.github.com" and parsed_base.port in {None, 443}
    if official_github_api and isinstance(token, str) and token.strip():
        headers["Authorization"] = f"Bearer {token.strip()}"
    return Request(f"{endpoint}?{urlencode(params)}", headers=headers, method="GET")


def _validated_api_base_url(value: str):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("GitHub 搜索地址必须是有效 HTTPS URL。")
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError:
        raise ValueError("GitHub 搜索地址必须是有效 HTTPS URL。") from None
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or port is not None and not 1 <= port <= 65535
    ):
        raise ValueError("GitHub 搜索地址必须是无凭据、无查询参数的 HTTPS URL。")
    return parsed


def _item_identity(item: Mapping[str, Any]) -> tuple[str, str]:
    repository = item.get("repository")
    repository = repository if isinstance(repository, Mapping) else {}
    full_name = _nonempty(item.get("full_name")) or _nonempty(repository.get("full_name"))
    path = _nonempty(item.get("path")) or _nonempty(item.get("source_path"))
    path = path.replace("\\", "/")
    return full_name.casefold(), path.casefold()


def _normalize_record(item: Mapping[str, Any], *, query: str) -> dict[str, Any] | None:
    repository = item.get("repository")
    repository = repository if isinstance(repository, Mapping) else {}
    full_name, path = _item_identity(item)
    if not full_name or not path or path.rsplit("/", 1)[-1].casefold() != "skill.md":
        return None
    path = _nonempty(item.get("path")) or _nonempty(item.get("source_path"))
    path = path.replace("\\", "/")
    display_name = _nonempty(item.get("name"), path.rsplit("/", 1)[-1])
    description = _nonempty(item.get("description"), "未提供 Skill 描述。")
    repo_url = _repository_url(full_name, {**repository, **item})
    # GitHub code-search ``sha`` is a blob hash, not a commit id.
    commit = (
        _valid_sha(item.get("commit_sha"))
        or _valid_sha((item.get("commit") or {}).get("sha") if isinstance(item.get("commit"), Mapping) else None)
    )
    fixed_commit = commit or "unresolved"
    content = item.get("content")
    if isinstance(content, str):
        content_sha256 = _sha256(content.encode("utf-8"))
        content_hash_kind = "source_content"
    else:
        # Repository search does not return file content.  Hash the immutable
        # API fields we did receive and label it so callers do not mistake it
        # for a downloaded source snapshot.
        content_sha256 = _sha256(
            _canonical(
                {
                    "full_name": full_name,
                    "path": path,
                    "sha": commit,
                    "name": display_name,
                    "description": description,
                }
            )
        )
        content_hash_kind = "api_metadata"
    source_url = (
        f"https://github.com/{full_name}/blob/{commit}/{path}"
        if commit
        else _nonempty(item.get("html_url"), repo_url)
    )
    skill_id = f"github:{full_name}:{path}"
    capability_id = f"remote-{_sha256(skill_id.encode('utf-8'))[:12]}"
    capability = {
        "capability_id": capability_id,
        "summary": description,
        "work_signal_groups": [],
        "match_terms": [display_name],
        "inputs": ["用户已确认的任务目标和方案"],
        "outputs": ["基于远程 Agent Skill 指令的方案建议"],
        "limitations": ["联网候选尚未在本机安装或执行，仅可作为 Agent Skill 参考。"],
        "evidence": source_url,
    }
    record: dict[str, Any] = {
        "record_schema_version": "remote-skill.v0.1",
        "skill_id": skill_id,
        "name": display_name,
        "description": description,
        "repository": repo_url,
        "fixed_commit": fixed_commit,
        "source_recorded_at": _nonempty(item.get("updated_at"), _nonempty(item.get("pushed_at"))),
        "source_path": path,
        "local_snapshot_path": "",
        "source_url": source_url,
        "local_source_snapshot_sha256": content_sha256,
        "content_sha256": content_sha256,
        "content_hash_kind": content_hash_kind,
        "capabilities": [capability],
        # A network hit is a recommendation, not an installation.  The user
        # may select it after reviewing the pinned source when available;
        # records without a code-search SHA remain visibly unverified.
        "method_adaptation_allowed": True,
        "adaptation_summary": "只参考远程 SKILL.md 中供 Agent 遵循的指令，不执行原仓库代码或宿主命令。",
        "suitable_work": ["需要参考公开 Agent Skill 指令完成已确认任务的工作。"],
        "unsuitable_work": ["要求本应用自动安装、执行或发布远程仓库内容的工作。"],
        "host_tool_requirements": [],
        "original_side_effects": [],
        "adaptation_side_effects": ["联网候选只作为 Agent Skill 参考，不产生远程仓库副作用。"],
        "original_prerequisites": [],
        "adaptation_prerequisites": [
            {
                "prerequisite_id": "remote-source-review",
                "description": "用户确认接受该远程来源，并自行核对其内容和许可。",
                "status": "unknown",
            }
        ],
        "incompatible_if": [],
        "license": deepcopy(item.get("license")) if isinstance(item.get("license"), Mapping) else {},
        "verification": {
            "source_read": False,
            "local_text_checked": False,
            "upstream_rechecked": True,
            "upstream_rechecked_at": _nonempty(item.get("updated_at"), _nonempty(item.get("pushed_at"))),
            "host_dependencies_available": "unknown",
            "installed": False,
            "execution_tested": False,
            "verification_status": "remote_recorded" if commit else "network_unverified",
        },
        "origin": "remote",
        "source_kind": "github",
        "search_query": query,
        "remote_result": deepcopy(dict(item)),
    }
    record["record_hash"] = _record_hash(record)
    return record


def normalize_github_results(
    payload: Mapping[str, Any] | Iterable[Mapping[str, Any]],
    *,
    query: str = "",
    key_work_ids: Iterable[str] | None = None,
    key_work_steps: Mapping[str, Iterable[str]] | None = None,
) -> list[dict[str, Any]]:
    """Normalize GitHub repository/code items into M3-compatible candidates."""

    if isinstance(payload, Mapping):
        items = payload.get("items")
    else:
        items = payload
    if not isinstance(items, Iterable) or isinstance(items, (str, bytes, Mapping)):
        raise SkillSearchError("invalid_response", "GitHub 搜索响应缺少有效 items 数组。")
    work_ids = [value.strip() for value in (key_work_ids or ["network-search"]) if isinstance(value, str) and value.strip()]
    if not work_ids:
        work_ids = ["network-search"]
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        if not isinstance(item, Mapping):
            continue
        identity = _item_identity(item)
        if identity in seen:
            continue
        record = _normalize_record(item, query=query)
        if record is None:
            continue
        seen.add(identity)
        records.append(record)
    candidates: list[dict[str, Any]] = []
    for record in records:
        remote = record.get("remote_result") or {}
        score = remote.get("score")
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            score = remote.get("stargazers_count", 0)
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            score = 0
        for key_work_id in work_ids:
            step_ids = [
                value.strip()
                for value in (key_work_steps or {}).get(key_work_id, [])
                if isinstance(value, str) and value.strip()
            ]
            candidate_id = f"candidate-network-{_sha256((record['skill_id'] + ':' + key_work_id).encode('utf-8'))[:20]}"
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "skill_id": record["skill_id"],
                    "key_work_id": key_work_id,
                    "record_hash": record["record_hash"],
                    "record_snapshot": deepcopy(record),
                    "step_ids": step_ids,
                    "capability_ids": [record["capabilities"][0]["capability_id"]],
                    "usage_mode": "method_adaptation",
                    "method_adaptation_allowed": bool(record["method_adaptation_allowed"]),
                    "adaptation_prerequisite_ids": ["remote-source-review"],
                    "limitations": list(record["capabilities"][0]["limitations"]),
                    "compatibility": "compatible" if record["method_adaptation_allowed"] else "unverified",
                    "verification_status": (
                        "remote_recorded"
                        if record["fixed_commit"] != "unresolved"
                        else "network_unverified"
                    ),
                    "selection_allowed": True,
                    "match_score": score,
                    "matched_work_signals": [],
                    "match_evidence": [
                        {
                            "group_id": "remote_search",
                            "label": "网络搜索",
                            "matched_terms": [query] if query.strip() else [],
                            "matched_sources": [{"source": "network", "label": "GitHub", "matched_terms": [query]}],
                        }
                    ],
                    "match_reason": f"来自 GitHub 网络搜索：{record['description']}",
                    "source_path": record["source_path"],
                    "local_snapshot_path": record["local_snapshot_path"],
                    "source_url": record["source_url"],
                    "repository": record["repository"],
                    "fixed_commit": record["fixed_commit"],
                    "content_sha256": record["content_sha256"],
                    "local_source_snapshot_sha256": record["local_source_snapshot_sha256"],
                    "description": record["description"],
                    "name": record["name"],
                    "suitable_work": list(record["suitable_work"]),
                    "unsuitable_work": list(record["unsuitable_work"]),
                    "host_tool_requirements": list(record["host_tool_requirements"]),
                    "original_side_effects": list(record["original_side_effects"]),
                    "adaptation_side_effects": list(record["adaptation_side_effects"]),
                    "license": deepcopy(record["license"]),
                    "verification_levels": {
                        "catalog_recorded": "verified",
                        "local_text_checked": "not_tested",
                        "fixed_source_traceable": "verified" if record["method_adaptation_allowed"] else "unknown",
                        "host_dependencies_available": "unknown",
                        "execution_tested": "not_tested",
                    },
                    "origin": "remote",
                    "source_kind": "github",
                    "provenance": {
                        "origin": "remote",
                        "source_url": record["source_url"],
                        "fixed_commit": record["fixed_commit"],
                        "content_hash_kind": record["content_hash_kind"],
                        "content_sha256": record["content_sha256"],
                        "verification_status": record["verification"]["verification_status"],
                        "source_read": False,
                        "installed": False,
                        "execution_tested": False,
                    },
                }
            )
    return candidates


@dataclass(frozen=True)
class SkillSearchResult:
    query: str
    status: str
    candidates: list[dict[str, Any]]
    batch_id: str
    catalog_hash: str
    error: dict[str, str] | None = None
    diagnostics: dict[str, Any] | None = None
    unmatched_key_work_ids: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "catalog_id": NETWORK_CATALOG_ID,
            "catalog_version": NETWORK_CATALOG_VERSION,
            "catalog_hash": self.catalog_hash,
            "origin": "network",
            "source_kind": "github",
            "query": self.query,
            "result": {
                "status": self.status,
                "candidates": deepcopy(self.candidates),
                "unmatched_key_work_ids": deepcopy(self.unmatched_key_work_ids or []),
                "error": deepcopy(self.error),
            },
            "diagnostics": deepcopy(self.diagnostics or {}),
        }


class GitHubSkillSearcher:
    """Small, injectable GitHub client used by the asynchronous UI layer."""

    def __init__(
        self,
        *,
        token: str | None = None,
        timeout_seconds: float = 15.0,
        opener: Callable[..., Any] | None = None,
        api_base_url: str = GITHUB_API_BASE,
        search_type: str = "code",
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("联网 Skill 搜索超时必须大于 0。")
        if search_type not in {"repositories", "code"}:
            raise ValueError("GitHub 搜索类型必须是 repositories 或 code。")
        self.token = token
        self.timeout_seconds = float(timeout_seconds)
        self.opener = opener
        self.api_base_url = api_base_url
        self.search_type = search_type

    def search(
        self,
        query: str,
        *,
        page: int = 1,
        per_page: int = 30,
        key_work_ids: Iterable[str] | None = None,
    ) -> SkillSearchResult:
        request = build_github_search_request(
            query,
            token=self.token,
            page=page,
            per_page=per_page,
            api_base_url=self.api_base_url,
            search_type=self.search_type,
        )
        try:
            open_fn = self.opener or urlopen
            with open_fn(request, timeout=self.timeout_seconds) as response:
                status_code = response.getcode() if hasattr(response, "getcode") else 200
                if isinstance(status_code, int) and status_code >= 400:
                    raise SkillSearchError(
                        "http",
                        f"GitHub 搜索请求失败（HTTP {status_code}）。",
                        status_code,
                    )
                raw = response.read()
        except SkillSearchError:
            raise
        except HTTPError as exc:
            raise SkillSearchError("http", f"GitHub 搜索请求失败（HTTP {exc.code}）。", exc.code) from None
        except (URLError, TimeoutError, OSError) as exc:
            raise SkillSearchError("network", f"无法连接 GitHub 搜索服务：{exc}") from None
        try:
            payload = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise SkillSearchError("invalid_response", f"GitHub 搜索响应不是有效 JSON：{exc}") from None
        if not isinstance(payload, Mapping) or not isinstance(payload.get("items"), list):
            raise SkillSearchError("invalid_response", "GitHub 搜索响应缺少有效 items 数组。")
        candidates = normalize_github_results(payload, query=query, key_work_ids=key_work_ids)
        catalog_hash = _sha256(
            _canonical(
                {
                    "catalog_id": NETWORK_CATALOG_ID,
                    "catalog_version": NETWORK_CATALOG_VERSION,
                    "query": query.strip(),
                    "records": [row["record_hash"] for row in candidates],
                }
            )
        )
        return SkillSearchResult(
            query=query.strip(),
            status="ok" if candidates else "empty",
            candidates=candidates,
            batch_id=f"batch-network-{uuid4().hex}",
            catalog_hash=catalog_hash,
        )


def search_github_skills(
    query: str,
    *,
    token: str | None = None,
    timeout_seconds: float = 15.0,
    opener: Callable[..., Any] | None = None,
    api_base_url: str = GITHUB_API_BASE,
    search_type: str = "code",
    key_work_ids: Iterable[str] | None = None,
) -> SkillSearchResult:
    """Convenience wrapper for one network Skill search."""

    return GitHubSkillSearcher(
        token=token,
        timeout_seconds=timeout_seconds,
        opener=opener,
        api_base_url=api_base_url,
        search_type=search_type,
    ).search(query, key_work_ids=key_work_ids)


def build_skill_query(
    key_works: Iterable[Mapping[str, Any]],
    *,
    context_text: str | None = None,
) -> str:
    """Turn confirmed work into a bounded GitHub SKILL.md code-search query."""

    terms: list[str] = ["skill"]
    for work in key_works:
        if not isinstance(work, Mapping):
            continue
        for key in ("title", "goal", "purpose", "description"):
            value = work.get(key)
            if isinstance(value, str) and value.strip():
                terms.append(value.strip())
        for key in ("inputs", "outputs", "actions", "checkpoints"):
            values = work.get(key, [])
            if isinstance(values, Iterable) and not isinstance(values, (str, bytes, Mapping)):
                terms.extend(value.strip() for value in values if isinstance(value, str) and value.strip())
    if isinstance(context_text, str) and context_text.strip():
        terms.append(context_text.strip())
    # GitHub rejects oversized q parameters. Keep the task signal bounded while
    # reserving space for the Skill marker and repository qualifiers.
    normalized_terms: list[str] = []
    for term in dict.fromkeys(terms):
        normalized = " ".join(term.split())[:96].rstrip()
        if normalized:
            normalized_terms.append(normalized)
    suffix = ["filename:SKILL.md"]
    suffix_length = len(suffix[0])
    budget = max(1, 256 - suffix_length - 1)
    selected: list[str] = []
    for term in normalized_terms:
        proposed = " ".join([*selected, term])
        if len(proposed) > budget:
            break
        selected.append(term)
    if not selected:
        selected = ["skill"]
    return " ".join([*selected, *suffix])


def search_github_repositories(
    key_works: Iterable[Mapping[str, Any]],
    *,
    context_text: str | None = None,
    token: str | None = None,
    timeout_seconds: float = 15.0,
    opener: Callable[..., Any] | None = None,
    api_base_url: str = GITHUB_API_BASE,
    key_work_ids: Iterable[str] | None = None,
    key_work_steps: Mapping[str, Iterable[str]] | None = None,
) -> SkillSearchResult:
    """Search GitHub for actual SKILL.md files matching confirmed key work."""

    works = list(key_works)
    inferred_ids = [
        row.get("key_work_id")
        for row in works
        if isinstance(row, Mapping) and isinstance(row.get("key_work_id"), str) and row["key_work_id"].strip()
    ]
    confirmed_steps = {
        row.get("key_work_id"): [
            step_id.strip()
            for step_id in row.get("step_ids", [])
            if isinstance(step_id, str) and step_id.strip()
        ]
        for row in works
        if isinstance(row, Mapping)
        and isinstance(row.get("key_work_id"), str)
        and row["key_work_id"].strip()
    }
    if key_work_steps is not None:
        confirmed_steps = {
            work_id: [
                step_id.strip()
                for step_id in values
                if isinstance(step_id, str)
                and step_id.strip()
                and step_id.strip() in set(confirmed_steps.get(work_id, []))
            ]
            for work_id, values in key_work_steps.items()
            if work_id in confirmed_steps
        }
    result = GitHubSkillSearcher(
        token=token,
        timeout_seconds=timeout_seconds,
        opener=opener,
        api_base_url=api_base_url,
        search_type="code",
    ).search(
        build_skill_query(works, context_text=context_text),
        key_work_ids=key_work_ids if key_work_ids is not None else inferred_ids,
    )
    for candidate in result.candidates:
        candidate["step_ids"] = list(confirmed_steps.get(candidate["key_work_id"], []))
    if result.status == "empty":
        return SkillSearchResult(
            query=result.query,
            status="no_match",
            candidates=result.candidates,
            batch_id=result.batch_id,
            catalog_hash=result.catalog_hash,
            error=result.error,
        )
    return result


# ---------------------------------------------------------------------------
# Indexed online Skill discovery
# ---------------------------------------------------------------------------

_ONLINE_DEFAULT_INDEX = "https://skills.sh"
_ONLINE_QUERY_BY_CATEGORY = {
    "writing": ("writing", "editing", "document"),
    "presentation": ("presentation", "powerpoint", "slides", "deck"),
    "learning": ("teaching", "learning", "education"),
    "planning_research": ("research", "planning", "literature review"),
    "data_analysis": ("data analysis", "visualization", "spreadsheet"),
    "coding": ("software development", "testing", "python"),
    "general": ("workflow", "research", "writing"),
}
_ONLINE_SIGNALS = (
    (r"ppt|幻灯|汇报|演示|powerpoint|slides?", "powerpoint"),
    (r"论文|文献|研究|调研|literature|paper", "research"),
    (r"数据|图表|可视化|csv|excel|统计|spreadsheet", "data analysis"),
    (r"编程|代码|程序|python|开发|测试|软件", "software development"),
    (r"学习|讲解|教学|零基础|课程|teach|learn", "teaching"),
    (r"写作|通知|文章|文稿|报告|writing", "writing"),
    (r"策划|规划|计划|workflow", "planning"),
)
_ONLINE_REPOSITORY = re.compile(r"^[\w.-]+/[\w.-]+$")
_ONLINE_SHA40 = re.compile(r"^[0-9a-f]{40}$", re.I)
_ONLINE_MAX_BYTES = 350_000
_ONLINE_TREE_MAX_BYTES = 8_000_000


def _online_blob_sha(raw: bytes) -> str:
    """Return Git's immutable blob object id for a downloaded file."""

    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _online_skill_metadata(raw: bytes) -> tuple[str, str]:
    """Read the required YAML frontmatter from a real SKILL.md file."""

    try:
        body = raw.decode("utf-8-sig").replace("\r\n", "\n")
    except UnicodeDecodeError as exc:
        raise SkillSearchError("invalid_skill", f"SKILL.md 不是有效 UTF-8：{exc}") from None
    if not body.startswith("---\n"):
        raise SkillSearchError("invalid_skill", "SKILL.md 缺少 YAML 元数据。")
    end = body.find("\n---", 4)
    if end < 0:
        raise SkillSearchError("invalid_skill", "SKILL.md 元数据未闭合。")
    frontmatter = body[4:end]

    def field(name: str) -> str:
        match = re.search(rf"(?m)^{re.escape(name)}:[ \t]*(.*)$", frontmatter)
        if not match:
            return ""
        value = match.group(1).strip()
        if value in {">", "|", ">-", "|-"}:
            lines: list[str] = []
            for line in frontmatter[match.end() :].splitlines():
                if line and not line[0].isspace():
                    break
                if line.strip():
                    lines.append(line.strip())
            value = " ".join(lines)
        return value.strip().strip("\"'")[:500]

    name, description = field("name"), field("description")
    if not name or not description:
        raise SkillSearchError("invalid_skill", "SKILL.md 缺少 name 或 description。")
    if not body[end + 4 :].strip():
        raise SkillSearchError("invalid_skill", "SKILL.md 缺少供 Agent 遵循的指令正文。")
    return name, description


def _online_work_text(work: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key in ("title", "goal", "purpose", "description"):
        value = work.get(key)
        if isinstance(value, str):
            parts.append(value)
    for key in ("inputs", "outputs", "actions", "checkpoints"):
        values = work.get(key, [])
        if isinstance(values, Iterable) and not isinstance(values, (str, bytes, Mapping)):
            parts.extend(str(value) for value in values if isinstance(value, str))
    return " ".join(parts)


def _online_queries(
    key_works: Iterable[Mapping[str, Any]],
    *,
    context_text: str | None = None,
    category: str | None = None,
    queries: Iterable[str] | None = None,
) -> list[str]:
    """Produce short independent terms; avoid sending whole Chinese paragraphs to q."""

    terms: list[str] = []
    if queries is not None:
        terms.extend(value.strip() for value in queries if isinstance(value, str) and value.strip())
    text = " ".join(_online_work_text(work) for work in key_works)
    if isinstance(context_text, str):
        text += " " + context_text
    for pattern, term in _ONLINE_SIGNALS:
        if re.search(pattern, text, re.I) and term not in terms:
            terms.append(term)
    for term in _ONLINE_QUERY_BY_CATEGORY.get(category or "general", _ONLINE_QUERY_BY_CATEGORY["general"]):
        if term not in terms:
            terms.append(term)
    if not terms:
        terms = ["skill", "workflow"]
    # Keep searches cheap and predictable.  Terms are individually URL encoded.
    return list(dict.fromkeys(" ".join(item.split())[:96].strip() for item in terms if item.strip()))[:6]


def _online_github_queries(search_terms: Iterable[str]) -> list[str]:
    queries: list[str] = []
    seen: set[str] = set()
    for term in search_terms:
        cleaned = re.sub(r"(?i)\bSKILL\.md\b|\bagent\s+skills?\b|\bskills?\b", " ", term)
        cleaned = " ".join(cleaned.split()[:4]).strip()
        if not cleaned or cleaned.casefold() in seen:
            continue
        seen.add(cleaned.casefold())
        queries.append(f'{cleaned} "SKILL.md" "agent skill" in:readme')
        if len(queries) >= 3:
            break
    return queries


def _online_validate_search_url(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("联网 Skill 搜索地址必须是 HTTPS URL。")
    parsed = urlsplit(value.strip())
    if parsed.scheme.casefold() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("联网 Skill 搜索地址必须是无凭据的 HTTPS URL。")
    return value.strip()


def _online_search_endpoint(base_url: str, query: str) -> str:
    """Support skills.sh, an endpoint URL, or a URL template containing {query}."""

    value = _online_validate_search_url(base_url)
    parsed = urlsplit(value)
    if "{query}" in value:
        return value.replace("{query}", quote(query, safe=""))
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    has_q = any(key.casefold() in {"q", "query", "search"} for key, _ in query_pairs)
    if parsed.hostname.casefold() == "skills.sh" and not parsed.path.rstrip("/"):
        path = "/api/search"
    elif not parsed.path or parsed.path == "/":
        path = "/api/search"
    else:
        path = parsed.path
    if not has_q:
        query_pairs.append(("q", query))
    else:
        query_pairs = [(key, query if key.casefold() in {"q", "query", "search"} else current)
                       for key, current in query_pairs]
    return urlunsplit((parsed.scheme, parsed.netloc, path, urlencode(query_pairs), parsed.fragment))


def _online_reader(opener: Callable[..., Any] | None, url: str, timeout: float) -> bytes:
    request = Request(url, headers={
        "Accept": "application/json, text/plain, text/markdown, */*",
        "User-Agent": "PromptSmith-SkillSearch/2.0",
    }, method="GET")
    open_fn = opener or urlopen
    try:
        try:
            response = open_fn(request, timeout=timeout)
        except TypeError:
            # Compatibility with v0.5 injectable fetch(url, timeout) callbacks.
            response = open_fn(url, timeout)
        if hasattr(response, "__enter__"):
            with response as active:
                status = active.getcode() if hasattr(active, "getcode") else 200
                if isinstance(status, int) and status >= 400:
                    raise SkillSearchError("http", f"网络请求失败（HTTP {status}）。", status)
                try:
                    raw = active.read(_ONLINE_TREE_MAX_BYTES + 1)
                except TypeError:
                    raw = active.read()
        else:
            if hasattr(response, "read"):
                try:
                    raw = response.read(_ONLINE_TREE_MAX_BYTES + 1)
                except TypeError:
                    raw = response.read()
            else:
                raw = response
        if not isinstance(raw, bytes):
            raw = bytes(raw)
        if len(raw) > _ONLINE_TREE_MAX_BYTES:
            raise SkillSearchError("response_too_large", "网络响应过大，已跳过。")
        return raw
    except SkillSearchError:
        raise
    except HTTPError as exc:
        raise SkillSearchError("http", f"网络请求失败（HTTP {exc.code}）。", exc.code) from None
    except (URLError, TimeoutError, OSError) as exc:
        raise SkillSearchError("network", f"无法连接网络搜索服务：{exc}") from None


def _online_json(raw: bytes) -> Any:
    """Decode a JSON response while preserving object and array payloads.

    Search and repository metadata endpoints return objects, while GitHub's
    ``/commits`` endpoint returns a top-level array.  The old helper rejected
    that array before the commit verifier could inspect it, making every
    otherwise valid ``SKILL.md`` appear as an unverified/no-match result.
    Callers that require an object still validate that shape explicitly.
    """
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SkillSearchError("invalid_response", f"网络搜索响应不是有效 JSON：{exc}") from None
    if not isinstance(value, (Mapping, list)):
        raise SkillSearchError("invalid_response", "网络搜索响应必须是 JSON 对象或数组。")
    return value


def _online_is_skill_markdown_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return (
        parsed.scheme.casefold() == "https"
        and bool(parsed.hostname)
        and parsed.path.rstrip("/").rsplit("/", 1)[-1].casefold() == "skill.md"
    )


def _online_discovery_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping):
        raise SkillSearchError("invalid_response", "网络搜索响应必须是 JSON 对象。")
    rows = payload.get("skills")
    if not isinstance(rows, list):
        rows = payload.get("results")
    if not isinstance(rows, list):
        rows = payload.get("items")
    if not isinstance(rows, list):
        raise SkillSearchError("invalid_response", "网络搜索响应缺少 skills/results/items 数组。")
    found: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        source = _nonempty(row.get("source"))
        skill_id = _nonempty(row.get("skillId")) or _nonempty(row.get("skill_id"))
        source_url = _nonempty(row.get("url")) or _nonempty(row.get("source_url"))
        if source and _ONLINE_REPOSITORY.fullmatch(source):
            found.append({"repository": source, "skill_id": skill_id, "source_index": "skills.sh",
                          "installs": row.get("installs", 0)})
        elif _online_is_skill_markdown_url(source_url):
            found.append({"repository": "", "skill_id": skill_id, "source_index": "web", "url": source_url})
    return found


def _online_github_paths(
    opener: Callable[..., Any] | None,
    repository: str,
    *,
    deadline: float,
) -> list[tuple[str, str]]:
    remaining = max(0.1, deadline - time.monotonic())
    metadata = _online_json(_online_reader(opener, f"{GITHUB_API_BASE}/repos/{repository}", min(6.0, remaining)))
    if not isinstance(metadata, Mapping):
        raise SkillSearchError("invalid_response", f"GitHub 仓库元数据不是 JSON 对象：{repository}。")
    branch = metadata.get("default_branch")
    if not isinstance(branch, str) or not branch:
        return []
    remaining = max(0.1, deadline - time.monotonic())
    tree = _online_json(_online_reader(opener, f"{GITHUB_API_BASE}/repos/{repository}/git/trees/{quote(branch)}?recursive=1", min(6.0, remaining)))
    if not isinstance(tree, Mapping):
        raise SkillSearchError("invalid_response", f"GitHub 仓库目录不是 JSON 对象：{repository}。")
    if tree.get("truncated"):
        return []
    rows = tree.get("tree")
    if not isinstance(rows, list):
        return []
    return [(row["path"], row["sha"]) for row in rows
            if isinstance(row, Mapping) and isinstance(row.get("path"), str)
            and (row["path"] == "SKILL.md" or row["path"].endswith("/SKILL.md"))
            and isinstance(row.get("sha"), str)]


def _online_latest_commit(opener: Callable[..., Any] | None, repository: str, path: str, *, deadline: float) -> tuple[str, str | None]:
    remaining = max(0.1, deadline - time.monotonic())
    payload = _online_json(_online_reader(opener, f"{GITHUB_API_BASE}/repos/{repository}/commits?path={quote(path)}&per_page=1", min(6.0, remaining)))
    rows = payload if isinstance(payload, list) else []
    if not rows or not isinstance(rows[0], Mapping):
        return "", None
    commit = rows[0].get("sha")
    date = ((rows[0].get("commit") or {}).get("committer") or {}).get("date") if isinstance(rows[0].get("commit"), Mapping) else None
    return commit if isinstance(commit, str) and _ONLINE_SHA40.fullmatch(commit) else "", date if isinstance(date, str) else None


class _GitHubSkillLinks(HTMLParser):
    def __init__(self, repository: str) -> None:
        super().__init__(convert_charrefs=True)
        self.repository = repository
        self.links: list[tuple[str, str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a":
            return
        href = dict(attrs).get("href") or ""
        parsed = urlsplit(urljoin(f"https://github.com/{self.repository}", href))
        prefix = f"/{self.repository}/blob/"
        if parsed.hostname != "github.com" or not parsed.path.startswith(prefix):
            return
        parts = parsed.path[len(prefix):].split("/", 1)
        if len(parts) != 2 or not (parts[1].casefold().endswith("/skill.md") or parts[1].casefold() == "skill.md"):
            return
        self.links.append((urlunsplit(("https", "github.com", parsed.path, "", "")), parts[0], parts[1]))


def _online_path_matches_id(path: str, requested_id: str) -> bool:
    parts = path.strip("/").split("/")
    return not requested_id or len(parts) == 1 or parts[-2].casefold() == requested_id.casefold()


def _online_public_github_source(
    opener: Callable[..., Any] | None,
    repository: str,
    requested_id: str,
    *,
    deadline: float,
) -> tuple[str, str, bytes] | None:
    page = _online_reader(opener, f"https://github.com/{repository}", min(6.0, max(0.1, deadline - time.monotonic())))
    if len(page) > 2_000_000:
        return None
    parser = _GitHubSkillLinks(repository)
    parser.feed(page.decode("utf-8-sig", errors="replace"))
    for source_url, branch, path in list(dict.fromkeys(parser.links))[:12]:
        if not _online_path_matches_id(path, requested_id):
            continue
        if time.monotonic() >= deadline:
            return None
        raw_url = f"https://raw.githubusercontent.com/{repository}/{quote(branch)}/{quote(path, safe='/')}"
        try:
            raw = _online_reader(opener, raw_url, min(6.0, max(0.1, deadline - time.monotonic())))
            _online_skill_metadata(raw)
            return source_url, path, raw
        except SkillSearchError:
            continue
    return None


def _online_record_from_source(
    opener: Callable[..., Any] | None,
    item: Mapping[str, Any],
    *,
    deadline: float,
    searched_at: str,
) -> dict[str, Any] | None:
    repository = _nonempty(item.get("repository"))
    requested_id = _nonempty(item.get("skill_id"))
    source_index = _nonempty(item.get("source_index"), "skills.sh")
    if repository:
        try:
            paths = _online_github_paths(opener, repository, deadline=deadline)
            if requested_id:
                paths = [(candidate_path, candidate_sha) for candidate_path, candidate_sha in paths
                         if _online_path_matches_id(candidate_path, requested_id)]
            if not paths:
                return None
            path, tree_sha = paths[0]
            metadata = _online_json(_online_reader(opener, f"{GITHUB_API_BASE}/repos/{repository}", min(6.0, max(0.1, deadline - time.monotonic()))))
            if not isinstance(metadata, Mapping):
                raise SkillSearchError("invalid_response", f"GitHub 仓库元数据不是 JSON 对象：{repository}。")
            branch = metadata.get("default_branch")
            if not isinstance(branch, str):
                return None
            raw_url = f"https://raw.githubusercontent.com/{repository}/{quote(branch)}/{quote(path, safe='/')}"
            try:
                raw = _online_reader(opener, raw_url, min(6.0, max(0.1, deadline - time.monotonic())))
            except (SkillSearchError, OSError, TimeoutError) as exc:
                if not _online_source_record_is_recoverable(exc):
                    raise
                fallback_item = {
                    **dict(item),
                    "source_path": path,
                    "source_url": f"https://github.com/{repository}/blob/{branch}/{path}",
                    "name": _nonempty(item.get("skill_id")) or path.rstrip("/").split("/")[-2],
                }
                return _online_fallback_record(fallback_item, error=str(exc), searched_at=searched_at)
            if _online_blob_sha(raw).casefold() != tree_sha.casefold():
                raise SkillSearchError("source_changed", f"{repository}/{path} 下载内容与目录哈希不一致。")
            name, description = _online_skill_metadata(raw)
            commit, updated = _online_latest_commit(opener, repository, path, deadline=deadline)
            if not commit:
                return None
            pinned_url = f"https://raw.githubusercontent.com/{repository}/{commit}/{quote(path, safe='/')}"
            pinned = _online_reader(opener, pinned_url, min(6.0, max(0.1, deadline - time.monotonic())))
            if pinned != raw:
                raise SkillSearchError("source_changed", f"{repository}/{path} 固定提交内容已变化。")
            source_url = f"https://github.com/{repository}/blob/{commit}/{path}"
            fixed_commit = commit
        except SkillSearchError as exc:
            if exc.status_code not in {403, 429}:
                raise
            public_source = _online_public_github_source(opener, repository, requested_id, deadline=deadline)
            if public_source is None:
                raise
            source_url, path, raw = public_source
            name, description = _online_skill_metadata(raw)
            fixed_commit, updated = "unresolved", None
        source_kind = "github"
    else:
        source_url = _nonempty(item.get("url"))
        if not _online_is_skill_markdown_url(source_url):
            return None
        raw = _online_reader(opener, source_url, min(6.0, max(0.1, deadline - time.monotonic())))
        name, description = _online_skill_metadata(raw)
        path, fixed_commit, updated, source_kind = source_url.rsplit("/", 1)[-1], "unresolved", None, "web"
    content_hash = hashlib.sha256(raw).hexdigest()
    skill_id = f"{repository}:{path}" if repository else source_url
    record: dict[str, Any] = {
        "record_schema_version": "remote-skill.v0.2",
        "skill_id": skill_id,
        "name": name,
        "description": description,
        "source_type": "online",
        "source_kind": source_kind,
        "repository": f"https://github.com/{repository}" if repository else "",
        "source_path": path,
        "source_url": source_url,
        "fixed_commit": fixed_commit,
        "skill_file_updated_at": updated,
        "searched_at": searched_at,
        "discovery_source": source_index,
        "source_text": raw.decode("utf-8-sig", errors="replace"),
        "evidence_bundle": {
            "repository": f"https://github.com/{repository}" if repository else "",
            "source_url": source_url,
            "source_path": path,
            "name": name,
            "description": description,
            "fetch_status": "full_skill",
            "fetch_errors": [],
        },
        "local_source_snapshot_sha256": content_hash,
        "content_sha256": content_hash,
        "content_hash_kind": "source_content",
        "dependency_notes": [],
        "method_adaptation_allowed": True,
        "adaptation_summary": "只参考已读取的 Agent Skill 指令，不安装或执行远程内容。",
        "adaptation_prerequisites": [{
            "prerequisite_id": "remote-source-review",
            "description": "用户确认接受该远程来源，并自行核对其内容和许可。",
            "status": "unknown",
        }],
        "capabilities": [{"capability_id": "skill-reference", "summary": description,
                          "work_signal_groups": [], "match_terms": [name], "inputs": [], "outputs": [],
                          "limitations": ["远程 Skill 未安装或执行。"], "evidence": source_url}],
        "verification": {"source_read": True, "local_text_checked": False,
                          "upstream_rechecked": source_kind == "github" and fixed_commit != "unresolved", "installed": False,
                          "execution_tested": False,
                          "verification_status": "source_verified" if source_kind == "github" and fixed_commit != "unresolved" else "source_read"},
        "origin": "remote",
        "search_query": _nonempty(item.get("query")),
    }
    record["record_hash"] = _record_hash(record)
    return record


def _online_fallback_record(
    item: Mapping[str, Any],
    *,
    error: str | None,
    searched_at: str,
) -> dict[str, Any] | None:
    """Build a reference record from public metadata when source reading fails.

    This is intentionally a recommendation record.  It preserves the URL,
    description, README/search evidence and failure reason so the model can
    still judge relevance without treating the candidate as fully verified.
    """

    repository = _nonempty(item.get("repository"))
    source_url = _nonempty(item.get("source_url")) or _nonempty(item.get("url"))
    html_url = _nonempty(item.get("html_url"))
    if not source_url:
        source_url = html_url or (f"https://github.com/{repository}" if repository else "")
    if not source_url.startswith("https://") and not repository:
        return None
    source_kind = "github" if repository or "github" in source_url.casefold() else _nonempty(item.get("source_kind"), "web")
    name = _nonempty(item.get("name"))
    if not name:
        name = _nonempty(item.get("skill_id")) or (repository.rsplit("/", 1)[-1] if repository else "网络候选")
    description = (
        _nonempty(item.get("description"))
        or _nonempty(item.get("repository_description"))
        or _nonempty(item.get("search_snippet"))
        or _nonempty(item.get("title"))
        or "搜索结果未提供完整 Skill 描述。"
    )[:1200]
    source_path = _nonempty(item.get("source_path")).replace("\\", "/")
    url_path = urlsplit(source_url).path if source_url.startswith("https://") else ""
    if not source_path and url_path.rsplit("/", 1)[-1].casefold() == "skill.md":
        source_path = url_path.lstrip("/")
    index_source = _nonempty(item.get("source_index")).casefold()
    explicit_skill_index_entry = bool(repository and _nonempty(item.get("skill_id")) and index_source == "skills.sh")
    confirmed_skill_file = _online_is_skill_markdown_url(source_url)
    if not confirmed_skill_file and not explicit_skill_index_entry:
        return None
    source_text = item.get("source_text") if isinstance(item.get("source_text"), str) else ""
    readme = _nonempty(item.get("readme_text")) or _nonempty(item.get("readme_excerpt"))
    fetch_errors = list(item.get("fetch_errors", [])) if isinstance(item.get("fetch_errors"), list) else []
    if error and error not in fetch_errors:
        fetch_errors.append(error[:500])
    evidence_bundle = {
        "repository": f"https://github.com/{repository}" if repository else _nonempty(item.get("repository_url")),
        "source_url": source_url,
        "source_path": source_path,
        "name": name,
        "description": description,
        "repository_description": _nonempty(item.get("repository_description")) or _nonempty(item.get("description")),
        "readme_excerpt": readme[:6000],
        "search_title": _nonempty(item.get("title")) or name,
        "search_snippet": _nonempty(item.get("search_snippet")),
        "search_query": _nonempty(item.get("query")),
        "discovery_source": _nonempty(item.get("source_index"), "网络搜索"),
        "fetch_status": "partial" if source_text or readme else "search_result_only",
        "fetch_errors": fetch_errors,
    }
    if source_text:
        digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        content_hash_kind = "source_content"
        verification_status = "source_read"
    else:
        digest = _sha256(_canonical(evidence_bundle))
        content_hash_kind = "api_metadata"
        verification_status = "metadata_only" if readme or description else "search_result_only"
    record: dict[str, Any] = {
        "record_schema_version": "remote-skill.v0.3",
        "skill_id": (
            f"{repository}:{source_path}" if repository and source_path else
            f"{repository}:{_nonempty(item.get('skill_id'))}" if repository else
            f"web:{source_url}"
        ),
        "name": name,
        "description": description,
        "source_type": "online",
        "source_kind": source_kind,
        "repository": evidence_bundle["repository"],
        "source_path": source_path,
        "source_url": source_url,
        "fixed_commit": _nonempty(item.get("fixed_commit"), "unresolved"),
        "searched_at": searched_at,
        "discovery_source": evidence_bundle["discovery_source"],
        "search_query": evidence_bundle["search_query"],
        "source_text": source_text,
        "evidence_bundle": evidence_bundle,
        "local_source_snapshot_sha256": digest,
        "content_sha256": digest,
        "content_hash_kind": content_hash_kind,
        "method_adaptation_allowed": True,
        "adaptation_summary": "只提供公开信息作为 Agent Skill 参考，不安装或执行远程内容。",
        "adaptation_prerequisites": [{
            "prerequisite_id": "remote-source-review",
            "description": "用户或下游 AI 进一步确认远程来源、内容和许可。",
            "status": "unknown",
        }],
        "capabilities": [{
            "capability_id": "skill-reference",
            "summary": description,
            "work_signal_groups": [],
            "match_terms": [name],
            "inputs": [], "outputs": [],
            "limitations": ["当前证据可能只有 README、仓库描述或搜索摘要。"],
            "evidence": source_url,
        }],
        "verification": {
            "source_read": bool(source_text),
            "local_text_checked": False,
            "upstream_rechecked": False,
            "installed": False,
            "execution_tested": False,
            "verification_status": verification_status,
        },
        "origin": "remote",
        "remote_result": deepcopy(dict(item)),
    }
    record["record_hash"] = _record_hash(record)
    return record


def _online_source_record_is_recoverable(exc: BaseException) -> bool:
    """Only downgrade transport/access failures; malformed source stays rejected."""

    if not isinstance(exc, SkillSearchError):
        return isinstance(exc, (OSError, TimeoutError))
    return exc.kind in {"network", "http", "response_too_large", "timeout"} or exc.status_code in {403, 429, 408, 502, 503, 504}


def search_online_skills(
    key_works: Iterable[Mapping[str, Any]],
    *,
    context_text: str | None = None,
    token: str | None = None,
    timeout_seconds: float = 45.0,
    opener: Callable[..., Any] | None = None,
    search_url: str = _ONLINE_DEFAULT_INDEX,
    key_work_ids: Iterable[str] | None = None,
    key_work_steps: Mapping[str, Iterable[str]] | None = None,
    category: str | None = None,
    queries: Iterable[str] | None = None,
    include_unmatched: bool = False,
    include_index: bool = True,
    include_github_supplement: bool = True,
    max_verified_candidates: int = 8,
    progress: Callable[[str], Any] | None = None,
) -> SkillSearchResult:
    """Collect public Skill evidence from an index and optional GitHub supplement.

    A complete, pinned ``SKILL.md`` is preferred.  If transport, rate-limit or
    timeout failures prevent that read, the public metadata already collected is
    retained for the model instead of being silently converted into no results.
    ``token`` is accepted for API compatibility but is intentionally not sent to
    arbitrary search indexes.
    """

    if timeout_seconds <= 0:
        raise ValueError("联网 Skill 搜索超时必须大于 0。")
    if isinstance(max_verified_candidates, bool) or not isinstance(max_verified_candidates, int) or max_verified_candidates < 1:
        raise ValueError("联网 Skill 搜索候选上限必须是正整数。")
    if not include_index and not include_github_supplement:
        raise ValueError("联网 Skill 搜索至少需要启用一个来源。")
    works = [dict(work) for work in key_works if isinstance(work, Mapping)]
    inferred_ids = [row.get("key_work_id") for row in works if isinstance(row.get("key_work_id"), str) and row["key_work_id"].strip()]
    work_ids = [value.strip() for value in (key_work_ids or inferred_ids) if isinstance(value, str) and value.strip()]
    if not work_ids:
        work_ids = ["network-search"]
    confirmed_steps = {row.get("key_work_id"): [value for value in row.get("step_ids", []) if isinstance(value, str) and value.strip()]
                       for row in works if isinstance(row.get("key_work_id"), str)}
    if key_work_steps is not None:
        confirmed_steps = {work_id: [value for value in values if value in confirmed_steps.get(work_id, [])]
                           for work_id, values in key_work_steps.items() if work_id in confirmed_steps}
    search_terms = _online_queries(works, context_text=context_text, category=category, queries=queries)
    searched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    started = time.monotonic()
    deadline = started + float(timeout_seconds)
    messages: list[str] = []
    errors: list[str] = []
    discovered: dict[str, dict[str, Any]] = {}
    custom_index = _online_validate_search_url(search_url)
    is_default_index = custom_index.rstrip("/").casefold() == _ONLINE_DEFAULT_INDEX
    if include_index:
        for term in search_terms:
            if time.monotonic() >= deadline:
                errors.append("联网 Skill 搜索超过时间限制。")
                break
            endpoint = _online_search_endpoint(custom_index, term)
            message = f"正在搜索 Skill：{term}"
            messages.append(message)
            if progress:
                progress(message)
            try:
                payload = _online_json(_online_reader(opener, endpoint, min(8.0, max(0.1, deadline - time.monotonic()))))
                for row in _online_discovery_rows(payload):
                    row["query"] = term
                    identity = f"{row.get('repository')}:{row.get('skill_id')}:{row.get('url')}"
                    discovered.setdefault(identity, row)
            except (SkillSearchError, OSError, ValueError) as exc:
                errors.append(f"{custom_index}（{term}）：{exc}")
    if include_github_supplement:
        for query in _online_github_queries(search_terms):
            if time.monotonic() >= deadline:
                errors.append("GitHub 搜索超过时间限制。")
                break
            try:
                endpoint = f"{GITHUB_API_BASE}/search/repositories?{urlencode({'q': query, 'sort': 'best-match', 'per_page': 3})}"
                payload = _online_json(_online_reader(opener, endpoint, min(8.0, max(0.1, deadline - time.monotonic()))))
                if not isinstance(payload, Mapping):
                    raise SkillSearchError("invalid_response", "GitHub 搜索响应必须是 JSON 对象。")
                for row in payload.get("items", []) if isinstance(payload.get("items"), list) else []:
                    repository = row.get("full_name") if isinstance(row, Mapping) else None
                    if isinstance(repository, str) and _ONLINE_REPOSITORY.fullmatch(repository):
                        item = dict(row)
                        item.update({
                            "repository": repository,
                            "skill_id": item.get("skill_id", ""),
                            "source_index": "GitHub",
                            "query": query,
                            "repository_description": item.get("description", ""),
                        })
                        discovered.setdefault(f"{repository}::github", item)
            except (SkillSearchError, OSError, ValueError) as exc:
                errors.append(f"GitHub（{query}）：{exc}")
                if isinstance(exc, SkillSearchError) and exc.status_code in {403, 429}:
                    break
    # An empty, well-formed index is a valid ``no_match`` result.  If every
    # source failed (including malformed JSON or a wrong response shape),
    # surface the failure so the UI can show a retry/error state instead of
    # silently presenting an empty search page.
    if not discovered and errors:
        raise SkillSearchError("network", errors[0])
    records: list[dict[str, Any]] = []
    evidence_counts = {"full_skill": 0, "metadata": 0, "search_result_only": 0}
    for item in list(discovered.values())[:max_verified_candidates]:
        if time.monotonic() >= deadline:
            errors.append("联网 Skill 搜索超过时间限制。")
            break
        try:
            record = _online_record_from_source(opener, item, deadline=deadline, searched_at=searched_at)
        except (SkillSearchError, OSError, ValueError) as exc:
            errors.append(f"{item.get('repository') or item.get('url')}: {exc}")
            record = _online_fallback_record(
                item,
                error=str(exc),
                searched_at=searched_at,
            ) if _online_source_record_is_recoverable(exc) else None
        if record and not any(existing["skill_id"] == record["skill_id"] for existing in records):
            records.append(record)
            verification_status = record.get("verification", {}).get("verification_status", "unknown")
            if verification_status in {"source_verified", "source_read"}:
                evidence_counts["full_skill"] += 1
                message = f"已读取 Skill 信息：{record['name']}（完整 SKILL.md）"
            elif verification_status == "metadata_only":
                evidence_counts["metadata"] += 1
                message = f"已收集 Skill 信息：{record['name']}（公开元数据）"
            else:
                evidence_counts["search_result_only"] += 1
                message = f"已保留搜索线索：{record['name']}"
            messages.append(message)
            if progress:
                progress(message)
    candidates: list[dict[str, Any]] = []
    for work in works:
        work_id = work.get("key_work_id")
        if not isinstance(work_id, str) or not work_id.strip():
            continue
        work_text = _online_work_text(work).casefold()
        for record in records:
            record_text = (record["name"] + " " + record["description"] + " " + record.get("source_text", "")).casefold()
            signal_words = set(re.findall(r"[a-z][a-z0-9-]{2,}", record_text))
            task_words = set(re.findall(r"[a-z][a-z0-9-]{2,}", work_text))
            matched = sorted(signal_words & task_words)
            # Chinese work descriptions often have no Latin tokens in common
            # with an English Skill.  Translate *this work* into category
            # signals before falling back; using the global query list here
            # would attach a PowerPoint Skill to every confirmed work in the
            # same search batch (for example, an unrelated Excel work).
            if not matched:
                work_signals = [term for pattern, term in _ONLINE_SIGNALS if re.search(pattern, work_text, re.I)]
                matched = [term for term in work_signals if term.casefold() in record_text]
            if not matched and not include_unmatched:
                continue
            capability = record["capabilities"][0]
            candidate_id = f"candidate-network-{_sha256((record['skill_id'] + ':' + work_id).encode('utf-8'))[:20]}"
            candidates.append({
                "candidate_id": candidate_id,
                "skill_id": record["skill_id"], "key_work_id": work_id,
                "record_hash": record["record_hash"], "record_snapshot": deepcopy(record),
                "step_ids": list(confirmed_steps.get(work_id, [])), "capability_ids": [capability["capability_id"]],
                "usage_mode": "method_adaptation", "method_adaptation_allowed": True,
                "adaptation_prerequisite_ids": ["remote-source-review"], "limitations": capability["limitations"],
                "compatibility": "conditional", "verification_status": record["verification"]["verification_status"],
                "selection_allowed": True, "match_score": len(matched), "matched_work_signals": matched,
                "match_evidence": [{"group_id": "remote_search", "label": "网络搜索", "matched_terms": matched,
                                    "matched_sources": [{"source": record["discovery_source"], "label": record["discovery_source"], "matched_terms": matched}]}],
                "match_reason": (
                    f"公开 Skill 信息与此关键工作可能相关（{', '.join(matched)}）。"
                    if matched else "已收集公开 Skill 信息，交由 AI 综合判断与任务的关系。"
                ),
                "source_path": record["source_path"], "local_snapshot_path": "", "source_url": record["source_url"],
                "repository": record["repository"], "fixed_commit": record["fixed_commit"],
                "content_sha256": record["content_sha256"], "local_source_snapshot_sha256": record["local_source_snapshot_sha256"],
                "description": record["description"], "name": record["name"], "origin": "remote", "source_kind": record["source_kind"],
                 "evidence_level": "full_skill" if record["verification"]["verification_status"] in {"source_verified", "source_read"} else ("metadata" if record["verification"]["verification_status"] == "metadata_only" else "search_result"),
                 "evidence_bundle": deepcopy(record.get("evidence_bundle", {})),
                 "evidence_limitations": list((record.get("evidence_bundle") or {}).get("fetch_errors", [])) or (["完整 SKILL.md 尚未读取。"] if not record.get("source_text") else []),
                 "provenance": {"origin": "remote", "source_url": record["source_url"], "fixed_commit": record["fixed_commit"],
                                "content_hash_kind": record.get("content_hash_kind", "source_content"), "content_sha256": record["content_sha256"],
                                "verification_status": record["verification"]["verification_status"], "source_read": bool(record.get("source_text")),
                               "installed": False, "execution_tested": False},
            })
    matched_ids = {row["key_work_id"] for row in candidates}
    result_status = "ok" if candidates else "no_match"
    catalog_hash = _sha256(_canonical({"catalog": NETWORK_CATALOG_ID, "version": NETWORK_CATALOG_VERSION,
                                       "queries": search_terms, "records": [row["record_hash"] for row in records]}))
    diagnostics = {"queries": search_terms, "errors": errors[:12], "discovered_count": len(discovered),
                "verified_count": evidence_counts["full_skill"], "candidate_count": len(records),
                "collected_count": len(records),
                   "evidence_counts": evidence_counts, "progress": messages, "searched_at": searched_at,
                   "search_url": custom_index, "source_policy": "Skill index + GitHub" if include_github_supplement else "Skill index",
                   "index": bool(include_index), "github_supplement": bool(include_github_supplement),
                   "verification_cap": max_verified_candidates}
    return SkillSearchResult(
        query="; ".join(search_terms), status=result_status, candidates=candidates,
        batch_id=f"batch-network-{uuid4().hex}", catalog_hash=catalog_hash,
        error={"kind": "network", "message": errors[0]} if errors and not candidates else None,
        diagnostics=diagnostics,
        unmatched_key_work_ids=[work_id for work_id in work_ids if work_id not in matched_ids],
    )


class OnlineSkillSearch:
    """Compatibility adapter for the v0.5 dictionary-shaped search API."""

    def __init__(self, fetch: Callable[..., Any] | None = None, *, budget_seconds: float = 45.0) -> None:
        self.fetch = fetch
        self.budget_seconds = budget_seconds

    def search(self, works: list[dict[str, Any]], *, category: str | None = None, task_text: str = "") -> dict[str, Any]:
        try:
            result = search_online_skills(works, context_text=task_text, category=category,
                                          timeout_seconds=self.budget_seconds, opener=self.fetch)
        except SkillSearchError as exc:
            return {"searched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "queries": _online_queries(works, context_text=task_text, category=category),
                    "sources": ["skills.sh", "GitHub"], "errors": [str(exc)], "record_count": 0,
                    "result": {"status": "no_match", "candidates": [],
                               "unmatched_key_work_ids": [row.get("key_work_id") for row in works if row.get("key_work_id")], "error": {"kind": exc.kind, "message": str(exc)}}}
        payload = result.to_dict()
        payload["searched_at"] = result.diagnostics.get("searched_at") if result.diagnostics else ""
        payload["queries"] = result.diagnostics.get("queries", []) if result.diagnostics else []
        payload["sources"] = ["skills.sh", "GitHub"]
        payload["errors"] = result.diagnostics.get("errors", []) if result.diagnostics else []
        payload["record_count"] = result.diagnostics.get("verified_count", 0) if result.diagnostics else 0
        payload["result"]["unmatched_key_work_ids"] = [row.get("key_work_id") for row in works
                                                           if row.get("key_work_id") not in {item.get("key_work_id") for item in result.candidates}]
        return payload


def merge_candidates(
    local_candidates: Iterable[Mapping[str, Any]],
    remote_candidates: Iterable[Mapping[str, Any]],
    *,
    catalog_hash: str,
) -> dict[str, Any]:
    """Merge local and remote rows while keeping local rows authoritative."""

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    sources: list[str] = []
    for source_name, candidates in (("local", local_candidates), ("remote", remote_candidates)):
        if source_name not in sources:
            sources.append(source_name)
        for row in candidates:
            if not isinstance(row, Mapping):
                continue
            candidate = deepcopy(dict(row))
            key = (str(candidate.get("skill_id", "")), str(candidate.get("key_work_id", "")))
            if key in seen:
                continue
            seen.add(key)
            candidate.setdefault("origin", source_name)
            candidate.setdefault("source_kind", source_name)
            rows.append(candidate)
    merged_hash = _sha256(
        _canonical(
            {
                "catalog_hash": catalog_hash,
                "sources": sources,
                "records": [row.get("record_hash") for row in rows],
            }
        )
    )
    return {
        "batch_id": f"batch-merged-{uuid4().hex}",
        "catalog_id": NETWORK_CATALOG_ID,
        "catalog_version": NETWORK_CATALOG_VERSION,
        "catalog_hash": merged_hash,
        "sources": sources,
        "origin": "merged",
        "source_kind": "local_and_remote",
        "result": {
            "status": "ok" if rows else "no_match",
            "candidates": rows,
            "unmatched_key_work_ids": [],
            "error": None,
        },
    }
