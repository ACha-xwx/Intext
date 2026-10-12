"""Discovery and deterministic matching for local ``SKILL.md`` files.

The local search path intentionally reads source text only.  It does not import,
install, or execute a discovered Skill.  Each returned candidate contains an
immutable source snapshot hash so later workflow stages can bind the exact file
that was reviewed.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
from uuid import uuid4


MAX_SOURCE_BYTES = 256 * 1024
DEFAULT_MAX_CANDIDATES = None
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ENGLISH_WORD = re.compile(r"[a-z0-9][a-z0-9_-]{1,}", re.IGNORECASE)
_CJK_RUN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")
_FRONTMATTER_BOUNDARY = re.compile(r"^\s*---\s*$")

_PRUNED_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".venv", "venv", "node_modules",
    "dist", "build", "coverage", ".mypy_cache", ".pytest_cache", "target",
}

# Common bilingual task signals.  They let a Chinese task find an English
# Skill while leaving the final ranking deterministic and explainable.
_BILINGUAL_TERMS: dict[str, tuple[str, ...]] = {
    "界面": ("ui", "ux", "interface", "frontend", "layout", "visual"),
    "配色": ("color", "colour", "theme", "theming"),
    "字体": ("typography", "font", "type"),
    "留白": ("spacing", "layout", "composition"),
    "重构": ("refactor", "refactoring", "redesign"),
    "学习": ("learn", "learning", "study", "curriculum", "lesson", "course", "education"),
    "讲解": ("teaching", "lesson", "tutor", "explain", "education"),
    "教学": ("teaching", "lesson", "tutor", "education"),
    "初学者": ("beginner", "lesson", "tutor", "learn", "teaching"),
    "课程": ("course", "curriculum", "lesson", "teaching"),
    "计划": ("plan", "planning", "roadmap", "schedule"),
    "教程": ("tutorial", "guide", "lesson"),
    "练习": ("exercise", "practice", "drill"),
    "复习": ("review", "revision", "retrospective"),
    "需求": ("requirement", "specification", "spec", "discovery"),
    "规格": ("specification", "spec", "requirements"),
    "代码": ("code", "coding", "programming"),
    "开发": ("development", "develop", "software", "engineering"),
    "测试": ("test", "testing", "verification", "quality"),
    "文档": ("document", "documentation", "docs", "writing"),
    "写作": ("writing", "writer", "draft", "editing"),
    "论文": ("paper", "academic", "research", "citation"),
    "研究": ("research", "study", "literature", "evidence"),
    "数据": ("data", "dataset", "analysis"),
    "设计": ("design", "architecture", "ux", "prototype"),
    "分析": ("analysis", "analyze", "assessment"),
    "部署": ("deploy", "deployment", "release", "hosting"),
    "工作流": ("workflow", "process", "pipeline"),
    "提示": ("prompt", "instruction"),
    "修复": ("fix", "bug", "bugfix", "debug", "debugging", "troubleshoot"),
    "问题": ("issue", "problem", "bug", "debug", "debugging"),
    "浏览器": ("browser", "web", "website", "chrome", "tab"),
    "网页": ("web", "website", "browser", "page"),
    "页面": ("page", "web", "browser"),
}

# These words occur in the boilerplate of many Skills.  A hit in a
# frontmatter description is useful as supporting evidence, but by itself it
# should not make a generic testing/documentation Skill appear relevant to an
# unrelated task.  Domain terms such as ``code``, ``curriculum`` and ``paper``
# remain strong signals.
_GENERIC_MATCH_TERMS = {
    "test", "testing", "verification", "quality", "software", "development",
    "develop", "engineering", "workflow", "process",
}

# A few Skill families are intentionally narrow.  Their generic descriptions
# mention coding, testing, or debugging even when the task is about another
# domain, so require an explicit task signal before surfacing these names.
# The rule is name-based and therefore does not suppress an otherwise useful
# general workflow Skill whose body happens to contain a domain example.
_NAMED_DOMAIN_SIGNALS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("music", "audio", "fl-studio", "gsap"), ("music", "audio", "fl-studio", "gsap", "音乐", "音频", "作曲", "动画")),
    (("pdf",), ("pdf", "便携文档")),
    (("game",), ("game", "游戏")),
    (("shadcn", "tailwind", "react", "angular", "vue"), ("shadcn", "tailwind", "react", "angular", "vue", "web", "网页", "网站")),
    (("openai", "codex", "chatgpt"), ("openai", "codex", "chatgpt", "api", "模型", "接口")),
    (("humanizer", "humanize"), ("humanizer", "humanize", "写作", "文本", "文章", "文案", "润色")),
    (("browser", "chrome", "firefox", "agent-browser"), ("browser", "chrome", "firefox", "网页", "浏览器")),
    (("presentation", "presentations", "powerpoint", "slides", "slide", "deck"), ("presentation", "powerpoint", "slides", "slide", "deck", "ppt", "演示", "幻灯片")),
    (("excel", "spreadsheet", "workbook"), ("excel", "spreadsheet", "workbook", "表格", "电子表格")),
)


@dataclass(frozen=True)
class LocalSkillSearchResult:
    status: str
    candidates: list[dict[str, Any]]
    catalog_hash: str
    scanned_count: int
    errors: list[str]
    batch_id: str = ""
    scanned_files: int = 0
    matched_files: int = 0
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Keep aliases useful to callers that use either naming convention.
        if self.scanned_files == 0 and self.scanned_count:
            object.__setattr__(self, "scanned_files", self.scanned_count)

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "catalog_id": "promptsmith-local-files",
            "catalog_version": "skill-md.v1",
            "catalog_hash": self.catalog_hash,
            "origin": "local_file",
            "source_kind": "local_file",
            "scanned_count": self.scanned_count,
            "scanned_files": self.scanned_files,
            "matched_files": self.matched_files,
            "errors": list(self.errors),
            "diagnostics": deepcopy(self.diagnostics),
            "result": {
                "status": self.status,
                "candidates": deepcopy(self.candidates),
                "unmatched_key_work_ids": [],
                "error": None,
            },
        }


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _record_hash(record: Mapping[str, Any]) -> str:
    body = deepcopy(dict(record))
    body.pop("record_hash", None)
    return _sha256(_canonical(body))


def _clean(value: Any, fallback: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _parse_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value.strip()


def _parse_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    """Parse the small scalar subset used by common Skill frontmatter.

    PyYAML is intentionally optional.  When it is unavailable, folded and
    literal descriptions are handled directly and unknown YAML is ignored.
    """

    lines = raw.splitlines()
    if not lines or not _FRONTMATTER_BOUNDARY.match(lines[0]):
        return {}, raw
    end = next((i for i, line in enumerate(lines[1:], 1) if _FRONTMATTER_BOUNDARY.match(line)), None)
    if end is None:
        return {}, raw
    values: dict[str, str] = {}
    current_key = ""
    folded = False
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^\s*([A-Za-z0-9_-]+)\s*:\s*(.*)$", line)
        if match:
            current_key = match.group(1).strip().casefold()
            value = match.group(2).strip()
            folded = value in {">", ">-", ">+", "|", "|-", "|+"}
            values[current_key] = "" if folded else _parse_scalar(value)
            continue
        if current_key and folded and line.startswith((" ", "\t")):
            part = line.strip()
            if part:
                values[current_key] = f"{values[current_key]} {part}".strip()
    body = "\n".join(lines[end + 1:])
    return values, body


def _fallback_name_description(path: Path, body: str, metadata: Mapping[str, str]) -> tuple[str, str]:
    name = _clean(metadata.get("name"))
    description = _clean(metadata.get("description"))
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not name:
        heading = next((line.lstrip("#").strip() for line in lines if line.startswith("#")), "")
        name = heading or path.parent.name or path.stem
    if not description:
        description = next((line for line in lines if not line.startswith("#") and not line.startswith("```")), "")
    return name, description or "未提供 Skill 描述。"


def _default_roots() -> list[Path]:
    home = Path.home()
    project = Path.cwd()
    roots = [
        home / ".codex" / "skills",
        home / ".agents" / "skills",
        home / ".codex" / "plugins" / "cache",
        project / "skills",
        project / ".skills",
        project / ".codex" / "skills",
        project / ".agents" / "skills",
    ]
    # A bundled app can run from a temporary resource root.  Include its
    # skills directory without importing paths or making startup dependent on
    # the application package.
    try:
        from .paths import resource_root

        resource = resource_root()
    except (FileNotFoundError, ImportError):
        resource = None
    if resource is not None:
        roots.extend([resource / "skills", resource / ".skills"])
    return roots


def _normalize_roots(roots: Iterable[str | Path] | None) -> list[Path]:
    values = _default_roots() if roots is None else list(roots)
    result: list[Path] = []
    seen: set[str] = set()
    for value in values:
        try:
            path = Path(value).expanduser().resolve(strict=False)
        except (OSError, RuntimeError, TypeError):
            logging.getLogger(__name__).warning("Cannot resolve local Skill root: %s", value, exc_info=True)
            continue
        key = os.path.normcase(str(path))
        if key in seen or not path.is_dir():
            continue
        seen.add(key)
        result.append(path)
    return result


def _iter_skill_files(roots: Iterable[Path]) -> tuple[list[Path], list[str]]:
    paths: list[Path] = []
    errors: list[str] = []
    seen_real: set[str] = set()
    def scan_error(exc: OSError) -> None:
        errors.append(f"无法扫描本地 Skill 目录 {exc.filename}：{exc}")
        logging.getLogger(__name__).warning("Cannot walk Skill directory: %s", exc.filename,
                                          exc_info=(type(exc), exc, exc.__traceback__))
    for root in roots:
        try:
            for current, dirs, files in os.walk(root, topdown=True, followlinks=False, onerror=scan_error):
                dirs[:] = [name for name in dirs if name not in _PRUNED_DIRS]
                # Do not recurse through symlinked directories, even when a
                # platform reports them as directories.
                dirs[:] = [name for name in dirs if not (Path(current) / name).is_symlink()]
                for filename in files:
                    if filename.casefold() != "skill.md":
                        continue
                    path = Path(current) / filename
                    if path.is_symlink() or not path.is_file():
                        continue
                    try:
                        resolved_path = path.resolve(strict=True)
                        # Keep a normalized key for deduplication, while retaining
                        # the resolved path's original casing for provenance and
                        # user-facing results on case-insensitive filesystems.
                        identity = os.path.normcase(str(resolved_path))
                    except (OSError, RuntimeError):
                        logging.getLogger(__name__).warning("Cannot resolve Skill file: %s", path, exc_info=True)
                        continue
                    if identity in seen_real:
                        continue
                    seen_real.add(identity)
                    paths.append(resolved_path)
        except (OSError, RuntimeError) as exc:
            logging.getLogger(__name__).warning("Cannot scan Skill directory: %s", root, exc_info=True)
            errors.append(f"无法扫描本地 Skill 目录 {root}：{exc}")
    paths.sort(key=lambda path: os.path.normcase(str(path)))
    return paths, errors


def _task_text(works: Sequence[Mapping[str, Any]], context_text: str) -> str:
    chunks = [context_text] if isinstance(context_text, str) else []
    for work in works:
        for key in ("title", "goal", "purpose", "description", "inputs", "outputs", "actions", "checkpoints"):
            value = work.get(key)
            if isinstance(value, str):
                chunks.append(value)
            elif isinstance(value, Iterable) and not isinstance(value, (bytes, Mapping)):
                chunks.extend(str(item) for item in value if isinstance(item, str))
    return " ".join(chunks).strip()


def _search_terms(text: str) -> tuple[set[str], set[str]]:
    lowered = text.casefold()
    english = {match.casefold() for match in _ENGLISH_WORD.findall(lowered.replace("-", " ").replace("_", " "))}
    cjk = {run for run in _CJK_RUN.findall(lowered) if len(run) >= 2}
    expanded: set[str] = set(english)
    for term, translations in _BILINGUAL_TERMS.items():
        if term in lowered:
            # Keep the Chinese signal itself as a matchable token.  CJK text
            # often has no whitespace, so retaining only the full run (for
            # example ``课程学习计划``) misses shorter terms in a Skill file.
            cjk.add(term)
            expanded.update(translations)
    return expanded, cjk


def _score(task: str, candidate_text: str, name: str, description: str) -> tuple[int, list[str]]:
    task_english, task_cjk = _search_terms(task)
    candidate_lower = candidate_text.casefold()
    candidate_english = {match.casefold() for match in _ENGLISH_WORD.findall(candidate_lower.replace("-", " ").replace("_", " "))}
    candidate_cjk = {run for run in _CJK_RUN.findall(candidate_lower) if len(run) >= 2}
    candidate_cjk.update(term for term in _BILINGUAL_TERMS if term in candidate_lower)
    matched = sorted(task_english & candidate_english)
    matched_cjk = sorted(term for term in task_cjk if term in candidate_lower or term in candidate_cjk)
    score = len(matched) * 4 + len(matched_cjk) * 6
    name_lower = name.casefold()
    description_lower = description.casefold()
    score += sum(2 for term in matched if term in name_lower or term in description_lower)
    evidence = [*matched, *matched_cjk]
    return score, evidence[:20]


def _named_task_facets(task: str, name: str) -> set[str]:
    """Explicit task facets supported by a Skill name, without reading its body."""
    lowered = name.casefold().replace("-", " ").replace("_", " ")
    facets = (
        ("color", ("配色", "色彩", "主题", "color", "theme"), ("color", "colour", "theming", "theme")),
        ("typography", ("字体", "排版", "字号", "typography", "font"), ("typography", "font", "readable")),
        ("spacing", ("留白", "间距", "spacing"), ("spacing", "layout", "composition")),
        ("hierarchy", ("层级", "hierarchy"), ("hierarchy",)),
        ("refactoring", ("重构", "refactor", "redesign"), ("refactor", "refactoring", "redesign")),
    )
    return {facet for facet, triggers, names in facets
            if any(term in task.casefold() for term in triggers) and any(term in lowered for term in names)}


def _metadata_score(task: str, name: str, description: str) -> tuple[int, list[str]]:
    """Names identify requested sub-skills more precisely than broad prose."""
    score, evidence = _score(task, name + " " + description[:500], name, description[:500])
    return score + 24 * len(_named_task_facets(task, name)), evidence


def _has_defensible_match(task: str, info: Mapping[str, Any]) -> bool:
    """Return whether a Skill has enough non-boilerplate evidence to show.

    Skill files commonly repeat words such as ``testing`` and ``verification``
    in generic safety guidance.  Requiring either a strong frontmatter/name
    signal or two strong terms in the opening body keeps those boilerplate
    hits from turning a no-match search into a long list of unrelated Skills.
    The body allowance preserves Skills whose frontmatter only says
    ``A practical workflow`` while their opening instructions contain the
    actual capability (for example curriculum and exercise planning).
    """

    task_english, task_cjk = _search_terms(task)
    name = str(info.get("name", ""))
    description = str(info.get("description", ""))
    body = str(info.get("body", ""))

    def _english(text: str) -> set[str]:
        return {match.casefold() for match in _ENGLISH_WORD.findall(text.casefold().replace("-", " ").replace("_", " "))}

    def _cjk(text: str) -> set[str]:
        lowered = text.casefold()
        runs = {run for run in _CJK_RUN.findall(lowered) if len(run) >= 2}
        runs.update(term for term in _BILINGUAL_TERMS if term in lowered)
        return runs

    metadata_english = task_english & _english(f"{name} {description}")
    metadata_cjk = {term for term in task_cjk if term in f"{name} {description}".casefold()}
    strong_metadata = {
        term for term in metadata_english if term not in _GENERIC_MATCH_TERMS
    }
    strong_metadata.update(metadata_cjk)
    if strong_metadata:
        return True

    # Inspect only the opening body excerpt for fallback matching.  Later
    # sections often contain cross-domain examples and universal checklists.
    body_english = task_english & _english(body[:2000])
    body_cjk = {term for term in task_cjk if term in body[:2000].casefold() or term in _cjk(body[:2000])}
    strong_body = {
        term for term in body_english if term not in _GENERIC_MATCH_TERMS
    }
    strong_body.update(body_cjk)
    return len(strong_body) >= 2


def _has_unrequested_named_domain(task: str, name: str) -> bool:
    """Return whether a narrow named Skill family lacks a task signal."""

    task_lower = task.casefold()
    name_lower = name.casefold()
    for name_markers, task_markers in _NAMED_DOMAIN_SIGNALS:
        if any(marker in name_lower for marker in name_markers) and not any(
            marker.casefold() in task_lower for marker in task_markers
        ):
            return True
    return False


def _source_priority(path: str | Path) -> tuple[int, str]:
    """Prefer directly installed Skills over duplicate plugin cache copies."""

    value = str(path)
    lowered = value.casefold().replace("/", "\\")
    cache_marker = "\\.codex\\plugins\\cache\\"
    # The direct ~/.codex/skills and ~/.agents/skills roots are the user's
    # active copies; bundled/plugin cache paths are immutable fallbacks.
    priority = 1 if cache_marker in lowered else 0
    return priority, lowered


def _read_skill(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        logging.getLogger(__name__).warning("Cannot read Skill file: %s", path, exc_info=True)
        return None, f"无法读取 {path}：{exc}"
    digest = _sha256(raw_bytes)
    # CRLF/LF is a transport detail when the same Skill is installed in more
    # than one root.  Keep the raw digest for provenance, and a normalized
    # digest for duplicate/equivalent-content suppression.
    normalized_bytes = raw_bytes.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    dedup_digest = _sha256(normalized_bytes)
    try:
        raw = raw_bytes[:MAX_SOURCE_BYTES].decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        logging.getLogger(__name__).warning("Skill file is not UTF-8: %s", path, exc_info=True)
        return None, f"Skill 文件不是有效 UTF-8（{path}）：{exc}"
    metadata, body = _parse_frontmatter(raw)
    name, description = _fallback_name_description(path, body, metadata)
    content_text = "\n".join((name, description, body))
    return {
        "path": path,
        "digest": digest,
        "dedup_digest": dedup_digest,
        "name": name,
        "description": description,
        "body": body[:MAX_SOURCE_BYTES],
        "content_text": content_text,
    }, None


def _build_record(info: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(info["path"]).resolve()
    digest = str(info["digest"])
    name = str(info["name"])
    description = str(info["description"])
    body = str(info.get("body", ""))
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-") or "skill"
    skill_id = f"local:{slug}:{digest[:16]}"
    capability_id = f"local-cap-{digest[:16]}"
    capability = {
        "capability_id": capability_id,
        # Include a bounded body excerpt because many Skills leave their
        # frontmatter description generic while the actual capability is
        # stated in the Markdown instructions.
        "summary": " ".join(part for part in (description, body[:1200]) if part).strip(),
        "work_signal_groups": [],
        "match_terms": [name, description],
        "inputs": ["用户已确认的任务目标和方案"],
        "outputs": ["基于本地 Agent Skill 指令的方案建议"],
        "limitations": ["仅读取本地 SKILL.md 指令，不执行文件中的命令。"],
        "evidence": str(path),
    }
    record: dict[str, Any] = {
        "record_schema_version": "local-skill.v0.1",
        "skill_id": skill_id,
        "name": name,
        "description": description,
        "repository": "",
        "fixed_commit": "local",
        # Local files do not have a catalog publication timestamp.  A dynamic
        # wall-clock value here would make identical scans produce different
        # record and catalog hashes, so use a stable provenance marker instead.
        "source_recorded_at": "local-file",
        "source_path": str(path),
        "local_snapshot_path": str(path),
        "source_url": "",
        "local_source_snapshot_sha256": digest,
        "content_sha256": digest,
        "content_hash_kind": "source_content",
        "capabilities": [capability],
        "method_adaptation_allowed": True,
        "adaptation_summary": "只参考本地 SKILL.md 中供 Agent 遵循的指令，不执行原文件命令。",
        "suitable_work": ["需要参考本地 Agent Skill 指令完成已确认任务的工作。"],
        "unsuitable_work": ["要求自动执行、安装或发布原 Skill 内容的工作。"],
        "host_tool_requirements": [],
        "original_side_effects": [],
        "adaptation_side_effects": ["仅生成 Agent Skill 指令参考，不产生原 Skill 的宿主副作用。"],
        "original_prerequisites": [],
        "adaptation_prerequisites": [],
        "incompatible_if": [],
        "license": {},
        "verification": {
            "source_read": True,
            "local_text_checked": True,
            "upstream_rechecked": False,
            "host_dependencies_available": "unknown",
            "installed": False,
            "execution_tested": False,
            "verification_status": "source_verified",
        },
        "origin": "local_file",
        "source_kind": "local_file",
        "body_preview": str(info["body"])[:4000],
    }
    record["record_hash"] = _record_hash(record)
    return record


def search_local_skill_files(
    key_works: Iterable[Mapping[str, Any]],
    *,
    context_text: str = "",
    roots: Iterable[str | Path] | None = None,
    max_candidates: int | None = DEFAULT_MAX_CANDIDATES,
    task_text: str | None = None,
    include_unmatched: bool = False,
    progress: Callable[[str], Any] | None = None,
) -> LocalSkillSearchResult:
    """Scan local Skill files and return deterministic, provenance-rich candidates."""

    if max_candidates is not None and (
        isinstance(max_candidates, bool) or not isinstance(max_candidates, int) or max_candidates < 1
    ):
        raise ValueError("本地 Skill 候选数量上限必须是正整数。")
    works = [dict(row) for row in key_works if isinstance(row, Mapping) and str(row.get("key_work_id", "")).strip()]
    if task_text and not context_text:
        context_text = task_text
    from .local_skill_index import file_stamp, indexed_skill_metadata
    indexed, errors, diagnostics = indexed_skill_metadata(roots, progress=progress)
    # Each discovered file is bound to the key work that best explains its
    # match.  This prevents every candidate from being incorrectly attached to
    # the first work when a confirmed plan contains several independent works.
    entries: list[tuple[dict[str, Any], dict[str, Any], int, list[str], dict[str, Any] | None]] = []
    work_tasks = [(_task_text([work], context_text), work) for work in works]
    for info in indexed:
        # Rank cheap names/descriptions first; opening text is fallback evidence.
        record = {"skill_id": str(info["name"])}
        if work_tasks:
            scored = [
                (
                    *(_metadata_score(task, str(info["name"]), str(info["description"])) if include_unmatched else _score(task, str(info["content_text"]), str(info["name"]), str(info["description"]))),
                    task,
                    work,
                )
                for task, work in work_tasks
            ]
            # Highest score wins; key_work_id makes ties deterministic.
            score, evidence, best_task, best_work = max(
                scored,
                key=lambda item: (item[0], -len(str(item[3].get("key_work_id", ""))), str(item[3].get("key_work_id", ""))),
            )
        else:
            best_task = _task_text([], context_text)
            score, evidence = _score(
                best_task,
                str(info["content_text"]),
                str(info["name"]),
                str(info["description"]),
            )
            best_work = None
        if include_unmatched and _has_unrequested_named_domain(best_task, str(info["name"])):
            score //= 4
        if include_unmatched or (
            score > 0
            and _has_defensible_match(best_task, info)
            and not _has_unrequested_named_domain(best_task, str(info["name"]))
        ):
            entries.append((record, info, score, evidence, best_work))

    # The same Skill is often installed once under ~/.codex/skills and again
    # in a plugin cache.  Keep one candidate for identical source content,
    # preferring the active direct installation and then a deterministic path.
    entries.sort(
        key=lambda item: (
            -item[2],
            _source_priority(item[1]["path"]),
            str(item[0]["skill_id"]),
            str(item[1]["path"]).casefold(),
        )
    )
    deduplicated: list[tuple[dict[str, Any], dict[str, Any], int, list[str], dict[str, Any] | None]] = []
    seen_content: set[str] = set()
    for item in entries:
        digest = str(item[1].get("dedup_digest") or item[1].get("digest", ""))
        if digest and digest in seen_content:
            continue
        if digest:
            seen_content.add(digest)
        deduplicated.append(item)
    entries = deduplicated
    # The compatibility search can return all matches; UI discovery caps at 24.
    selected_files = entries[:max_candidates]
    candidates: list[dict[str, Any]] = []
    for record, info, score, evidence, best_work in selected_files:
        full, error = _read_skill(Path(info["path"]))
        if error or full is None:
            errors.append(error or "候选 Skill 无法读取。")
            continue
        try:
            current_stamp = file_stamp(Path(info["path"]))
        except OSError as exc:
            logging.getLogger(__name__).warning("Cannot inspect candidate Skill: %s", info["path"], exc_info=True)
            errors.append(f"无法检查候选 Skill 文件 {info['path']}：{exc}")
            continue
        if current_stamp != info["stamp"] or full["digest"] != info["digest"]:
            errors.append(f"Skill 文件在查找期间已变化：{info['path']}")
            continue
        record = _build_record(full)
        work_rows = works or [{"key_work_id": "local-search", "step_ids": []}]
        # A source Skill may support more than one key work.
        work = best_work or work_rows[0]
        key_work_id = str(work["key_work_id"])
        step_ids = [str(value) for value in work.get("step_ids", []) if isinstance(value, str) and value.strip()]
        candidate_id = f"candidate-local-{_sha256((record['skill_id'] + ':' + key_work_id).encode('utf-8'))[:20]}"
        capability_id = record["capabilities"][0]["capability_id"]
        candidates.append({
            "candidate_id": candidate_id,
            "skill_id": record["skill_id"],
            "key_work_id": key_work_id,
            "record_hash": record["record_hash"],
            "record_snapshot": deepcopy(record),
            "step_ids": step_ids,
            "capability_ids": [capability_id],
            "usage_mode": "method_adaptation",
            "method_adaptation_allowed": True,
            "adaptation_prerequisite_ids": [],
            "limitations": list(record["capabilities"][0]["limitations"]),
            "compatibility": "compatible",
            "verification_status": "source_verified",
            "selection_allowed": True,
            "match_score": score,
            "matched_work_signals": evidence,
            "match_evidence": [{"group_id": "local_file", "label": "本地 Skill 文本", "matched_terms": evidence}],
            "match_reason": (
                "待 AI 阅读 Skill 内容并判断适配性。" if include_unmatched
                else "本地 Skill 文件匹配" + ("：" + "、".join(evidence) if evidence else "（待 AI 进一步分析）") + "。"
            ),
            "source_path": str(info["path"]),
            "local_snapshot_path": str(info["path"]),
            "source_url": "",
            "repository": "",
            "fixed_commit": "local",
            "suitable_work": list(record["suitable_work"]),
            "unsuitable_work": list(record["unsuitable_work"]),
            "host_tool_requirements": [],
            "original_side_effects": [],
            "adaptation_side_effects": list(record["adaptation_side_effects"]),
            "license": {},
            "verification_levels": {
                "catalog_recorded": "verified",
                "local_text_checked": "verified",
                "fixed_source_traceable": "verified",
                "host_dependencies_available": "unknown",
                "execution_tested": "not_tested",
            },
            "origin": "local_file",
            "source_kind": "local_file",
            "name": record["name"],
            "description": record["description"],
            "source_stamp": current_stamp,
        })
    catalog_hash = _sha256(_canonical({
        "catalog_id": "promptsmith-local-files",
        "catalog_version": "skill-md.v1",
        "records": [row[1]["digest"] for row in entries],
    }))
    status = "ok" if candidates else "empty"
    return LocalSkillSearchResult(
        status=status,
        candidates=candidates,
        catalog_hash=catalog_hash,
        scanned_count=diagnostics["indexed_files"],
        errors=errors[:20],
        batch_id=f"batch-local-file-{uuid4().hex}",
        scanned_files=diagnostics["indexed_files"],
        matched_files=len(entries),
        diagnostics={**diagnostics, "content_reads": len(selected_files), "shortlisted_files": len(candidates)},
    )


def search_local_skills(
    works: Iterable[Mapping[str, Any]],
    *,
    task_text: str = "",
    roots: Iterable[str | Path] | None = None,
    max_candidates: int | None = DEFAULT_MAX_CANDIDATES,
) -> LocalSkillSearchResult:
    """Compatibility wrapper using the ``task_text`` naming convention."""

    return search_local_skill_files(
        works,
        context_text=task_text,
        roots=roots,
        max_candidates=max_candidates,
    )


def discover_local_skill_candidates(
    key_works: Iterable[Mapping[str, Any]],
    *,
    context_text: str = "",
    roots: Iterable[str | Path] | None = None,
    progress: Callable[[str], Any] | None = None,
    max_candidates: int = 24,
) -> LocalSkillSearchResult:
    """Use indexed names/descriptions to offer at most 24 files for AI review."""

    return search_local_skill_files(
        key_works,
        context_text=context_text,
        roots=roots,
        include_unmatched=True,
        max_candidates=max_candidates,
        progress=progress,
    )


__all__ = ["LocalSkillSearchResult", "search_local_skill_files", "search_local_skills", "discover_local_skill_candidates"]
