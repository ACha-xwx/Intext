"""Managed local checkpoints and a small, lazily loaded history catalogue."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import tempfile
from threading import RLock
from uuid import uuid4, uuid5, NAMESPACE_URL

from .paths import application_data_dir, migrate_legacy_application_data
from .session import SessionState

LOG = logging.getLogger(__name__)
ID = re.compile(r"^[a-f0-9]{32}$")


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".history-", suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            json.dump(value, output, ensure_ascii=False, allow_nan=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def history_group(timestamp: str, now: datetime | None = None) -> str:
    now = now or datetime.now().astimezone()
    try:
        date = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        days = (now.date() - date.astimezone(now.tzinfo).date()).days
    except (ValueError, TypeError):
        return "更早"
    if days <= 0:
        return "今天"
    if days == 1:
        return "昨天"
    if days < 7:
        return "七天内"
    if days < 30:
        return "30天内"
    return "更早"


def session_stage(data: dict) -> str:
    if data.get("final_result", {}).get("status") in {"draft", "confirmed"}:
        return "提示词已生成"
    if data.get("plan", {}).get("status") == "confirmed":
        return "选择 Skill / 生成提示词"
    if data.get("plan", {}).get("status") == "draft":
        return "核对方案"
    if data.get("requirements"):
        return "补充与核对需求"
    return "整理目标" if data.get("task_text") else "尚未发送"


class SessionHistory:
    """Only managed UUID paths can be opened/deleted; external exports stay intact.

    Healthy startup reads index + directory stats, never session bodies. Orphan
    or newer records repair an interrupted two-file commit; corrupt records are
    retained on disk and marked unavailable instead of silently discarded.
    """
    def __init__(self, directory: str | Path | None = None):
        if directory is None:
            migrate_legacy_application_data()
        self.directory = Path(directory) if directory is not None else application_data_dir() / "history"
        self.records = self.directory / "records"
        self.index_path = self.directory / "index.json"
        self.lock = RLock()
        self.entries = {}
        self.imports = {}
        self.issues = []
        self._load_index()

    def _path(self, identity: str) -> Path:
        if not isinstance(identity, str) or not ID.fullmatch(identity):
            raise ValueError("会话编号无效。")
        return self.records / (identity + ".json")

    def _write_index(self) -> None:
        atomic_json(self.index_path, {"version": 1, "entries": self.entries, "imports": self.imports})

    def _read_record(self, identity: str) -> dict:
        data = json.loads(self._path(identity).read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("session"), dict) or not isinstance(data.get("meta"), dict):
            raise ValueError("历史会话文件格式不正确。")
        if data["meta"].get("id") != identity:
            raise ValueError("历史会话编号不匹配。")
        return data

    def _load_index(self) -> None:
        changed = False
        try:
            document = json.loads(self.index_path.read_text(encoding="utf-8"))
            if document.get("version") != 1 or not isinstance(document.get("entries"), dict):
                raise ValueError("Invalid history index")
            self.imports = document.get("imports", {}) if isinstance(document.get("imports"), dict) else {}
            for key, row in document["entries"].items():
                if ID.fullmatch(key) and isinstance(row, dict) and row.get("id") == key:
                    self.entries[key] = row
                else:
                    changed = True
        except FileNotFoundError:
            pass
        except Exception:
            changed = True
            self.issues.append("历史索引损坏，已尝试从本地记录恢复。")
            LOG.exception("History index unreadable; rebuilding from managed records")
        # A deletion rename is either rolled back or finished according to the index.
        for tombstone in self.records.glob("*.deleted"):
            identity = tombstone.stem
            if not ID.fullmatch(identity):
                continue
            if identity in self.entries and not self._path(identity).exists():
                os.replace(tombstone, self._path(identity))
            else:
                tombstone.unlink()
            changed = True
        for path in self.records.glob("*.json"):
            identity = path.stem
            if not ID.fullmatch(identity):
                continue
            stat = path.stat()
            existing = self.entries.get(identity)
            if existing and existing.get("file_mtime_ns") == stat.st_mtime_ns and not existing.get("unavailable"):
                continue
            try:
                self.entries[identity] = dict(self._read_record(identity)["meta"], file_mtime_ns=stat.st_mtime_ns)
                changed = True
            except Exception:
                LOG.exception("History record cannot be indexed: id=%s", identity)
                self.issues.append("有历史记录无法读取，原文件已保留；可在 Debug 查看原因。")
                if existing:
                    existing["unavailable"] = True
        for key, row in self.entries.items():
            if not self._path(key).exists():
                row["unavailable"] = True
                changed = True
        if changed:
            try:
                self._write_index()
            except OSError:
                self.issues.append("历史索引暂时无法保存，现有记录仍可查看；请检查目录权限或磁盘空间。")
                LOG.exception("History index repair could not be saved; catalogue remains available in memory")
        LOG.info("History catalogue loaded: entries=%s issues=%s lazy_session_loading=True", len(self.entries), len(self.issues))

    def list(self, now: datetime | None = None) -> list[dict]:
        with self.lock:
            rows = deepcopy(list(self.entries.values()))
        for row in rows:
            row.pop("file_mtime_ns", None)
            row["group"] = "置顶" if row.get("pinned") else history_group(row.get("updated_at", ""), now)
        def timestamp(row):
            try:
                date = datetime.fromisoformat(row.get("updated_at", "").replace("Z", "+00:00"))
                return date.replace(tzinfo=timezone.utc).timestamp() if date.tzinfo is None else date.timestamp()
            except (ValueError, TypeError, AttributeError):
                return 0.
        return sorted(rows, key=lambda r: (bool(r.get("pinned")), timestamp(r), r["id"]), reverse=True)

    def save(self, data: dict, identity: str | None = None, *, preserve_time: bool = False) -> str:
        with self.lock:
            identity = identity or uuid4().hex
            path = self._path(identity)
            old = self.entries.get(identity, {})
            now = datetime.now(timezone.utc).isoformat()
            title = " ".join(str(data.get("task_text") or data.get("control", {}).get("workspace_drafts", {}).get("message") or "新对话").split())[:60]
            meta = dict(id=identity, task_id=data["task_id"], title=old.get("title") if old.get("custom_title") else title,
                        custom_title=bool(old.get("custom_title")), pinned=bool(old.get("pinned")),
                        created_at=old.get("created_at", data.get("created_at", now)), updated_at=data.get("updated_at", now) if preserve_time else now,
                        stage=session_stage(data))
            atomic_json(path, {"version": 1, "meta": meta, "session": data})
            self.entries[identity] = dict(meta, file_mtime_ns=path.stat().st_mtime_ns)
            # If this fails, the complete record remains discoverable on next startup.
            self._write_index()
            LOG.debug("History checkpoint saved: id=%s task=%s stage=%s", identity, data["task_id"], meta["stage"])
            return identity

    def import_directory(self, directory: str | Path) -> None:
        """Import earlier manual saves once; never modify the original files.

        Repeat startup only stats known paths. Removed managed imports stay
        removed; changing an external export never overwrites a resumed task.
        """
        from .storage import load_session
        imported = 0
        with self.lock:
            for path in Path(directory).expanduser().glob("*.json"):
                key = str(path.resolve())
                stat = path.stat()
                previous = self.imports.get(key)
                if previous and (previous.get("id") or previous.get("mtime") == stat.st_mtime_ns):
                    continue
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    if not isinstance(raw, dict) or not raw.get("task_id") or "schema_version" not in raw:
                        raise ValueError("Not a PromptSmith session")
                    session = load_session(path)
                    identity = uuid5(NAMESPACE_URL, key + ":" + session.task_id).hex
                    self.save(session.to_dict(), identity, preserve_time=True)
                    self.imports[key] = dict(id=identity, mtime=stat.st_mtime_ns)
                    imported += 1
                except Exception:
                    self.imports[key] = dict(id=None, mtime=stat.st_mtime_ns)
                    LOG.warning("Earlier session export could not be imported; original retained: path=%s", path, exc_info=True)
                self._write_index()
        if imported:
            LOG.info("Earlier manual sessions copied into history: count=%s original_files_untouched=True", imported)

    def load(self, identity: str) -> SessionState:
        with self.lock:
            if identity not in self.entries:
                raise ValueError("这条会话已不存在，请刷新历史列表。")
            data = self._read_record(identity)
        session = SessionState.from_dict(data["session"])
        LOG.info("History session resumed: id=%s task=%s stage=%s", identity, session.task_id, session_stage(session.to_dict()))
        return session

    def rename(self, identity: str, title: str) -> None:
        title = title.strip() if isinstance(title, str) else ""
        if not title or len(title) > 100 or any(ord(c) < 32 for c in title):
            raise ValueError("请输入1至100个字符的会话名称。")
        self._edit(identity, title=title, custom_title=True)
        LOG.info("History session renamed: id=%s", identity)

    def pin(self, identity: str, pinned: bool) -> None:
        if not isinstance(pinned, bool):
            raise ValueError("置顶状态无效。")
        self._edit(identity, pinned=pinned)
        LOG.info("History session pin changed: id=%s pinned=%s", identity, pinned)

    def _edit(self, identity, **changes):
        with self.lock:
            if identity not in self.entries:
                raise ValueError("这条会话已不存在。")
            record = self._read_record(identity)
            record["meta"].update(changes)
            atomic_json(self._path(identity), record)
            self.entries[identity] = dict(record["meta"], file_mtime_ns=self._path(identity).stat().st_mtime_ns)
            self._write_index()

    def delete(self, identity: str) -> None:
        with self.lock:
            if identity not in self.entries:
                raise ValueError("这条会话已不存在。")
            path = self._path(identity)
            tombstone = path.with_suffix(".deleted")
            if path.exists():
                os.replace(path, tombstone)
            previous = self.entries.pop(identity)
            try:
                self._write_index()
            except Exception:
                self.entries[identity] = previous
                if tombstone.exists():
                    os.replace(tombstone, path)
                raise
            tombstone.unlink(missing_ok=True)
            LOG.info("History session deleted: id=%s external_files_untouched=True", identity)
