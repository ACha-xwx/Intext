"""Incremental local metadata index; it never imports or executes Skill files."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from contextlib import suppress
from pathlib import Path
from typing import Any, Callable, Iterable
from uuid import uuid4

_LOCK = threading.RLock()
INDEX_VERSION = 1


def file_stamp(path: Path) -> list[int]:
    stat = path.stat()
    return [stat.st_mtime_ns, stat.st_size, stat.st_ctime_ns]


def indexed_skill_metadata(
    roots: Iterable[str | Path] | None = None,
    *,
    cache_dir: Path | None = None,
    progress: Callable[[str], Any] | None = None,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    # Import lazily so the existing parser remains the one source of metadata.
    from .local_skill_search import _iter_skill_files, _normalize_roots, _read_skill
    from .paths import application_data_dir

    started = time.perf_counter()
    normalized = _normalize_roots(roots)
    key = hashlib.sha256(json.dumps([os.path.normcase(str(p)) for p in normalized]).encode()).hexdigest()
    target = (cache_dir or application_data_dir() / "cache" / "skill_index") / (key + ".json")
    with _LOCK:
        try:
            saved = json.loads(target.read_text(encoding="utf-8"))
            cached = saved.get("entries", {}) if saved.get("version") == INDEX_VERSION else {}
            if not isinstance(cached, dict):
                cached = {}
        except FileNotFoundError:
            cached = {}
        except (OSError, ValueError, AttributeError):
            logging.getLogger(__name__).warning("Cannot load Skill index; rebuilding: %s", target, exc_info=True)
            cached = {}
        paths, errors = _iter_skill_files(normalized)
        if progress:
            progress(f"正在更新本地索引：发现 {len(paths)} 个 Skill 文件")
        entries: dict[str, Any] = {}
        metadata: list[dict[str, Any]] = []
        reads = hits = 0
        for path in paths:
            identity = os.path.normcase(str(path))
            try:
                stamp = file_stamp(path)
            except OSError as exc:
                logging.getLogger(__name__).warning("Cannot inspect Skill file: %s", path, exc_info=True)
                errors.append(f"无法检查 Skill 文件 {path}：{exc}")
                continue
            previous = cached.get(identity)
            valid = (isinstance(previous, dict) and previous.get("stamp") == stamp
                     and all(isinstance(previous.get(k), str) for k in ("name", "description", "body", "digest", "dedup_digest"))
                     and len(previous.get("digest", "")) == 64)
            if valid:
                entry = dict(previous)
                hits += 1
            else:
                info, error = _read_skill(path)
                reads += 1
                if error or info is None:
                    errors.append(error or f"无法读取 {path}")
                    continue
                # A changing file is not allowed to seed a valid cached entry.
                try:
                    if file_stamp(path) != stamp:
                        errors.append(f"Skill 文件扫描期间已变化：{path}")
                        continue
                except OSError:
                    logging.getLogger(__name__).warning("Skill disappeared during indexing: %s", path, exc_info=True)
                    continue
                entry = {"stamp": stamp, "name": info["name"][:160], "description": info["description"][:800],
                         "digest": info["digest"], "dedup_digest": info["dedup_digest"], "body": info["body"][:2000]}
            entries[identity] = entry
            metadata.append({**entry, "path": path, "content_text": " ".join((entry["name"], entry["description"], entry["body"]))})
        changed = entries != cached
        if changed or not target.is_file():
            temp = target.with_suffix(f".{uuid4().hex}.tmp")
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                temp.write_text(json.dumps({"version": INDEX_VERSION, "entries": entries}, ensure_ascii=False), encoding="utf-8")
                temp.replace(target)
            except OSError as exc:
                logging.getLogger(__name__).exception("Cannot save Skill index: %s", target)
                errors.append(f"索引无法保存，本轮仍可查找：{exc}")
            finally:
                with suppress(OSError):
                    temp.unlink(missing_ok=True)
        diagnostics = {"indexed_files": len(paths), "cache_hits": hits, "metadata_reads": reads,
                       "removed_files": len(set(cached) - set(entries)), "index_updated": changed,
                       "index_elapsed_ms": round((time.perf_counter() - started) * 1000)}
        logging.getLogger(__name__).debug("Skill index ready: %s; errors=%s", diagnostics, len(errors))
        if progress:
            progress(f"本地索引就绪：{len(metadata)} 项，复用 {hits} 项，更新 {reads} 项")
        return metadata, errors, diagnostics


def warm_local_skill_index(roots=None) -> dict[str, Any]:
    """Background startup work independent of task state or model settings."""
    return indexed_skill_metadata(roots)[2]
