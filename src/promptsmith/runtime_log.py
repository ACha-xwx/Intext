from __future__ import annotations

import io
import logging
import re
import sys
import tempfile
import threading
import warnings
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4


_CREDENTIAL = re.compile(
    r'''(?i)((?:api[_-]?key|x-api-key|authorization|password|secret|access[_-]?token|token)["']?\s*[:=]\s*["']?)(?:bearer\s+)?(\[REDACTED\]|\[[^\s,;"'&}\]]+\]|[^\s,;"'&}\]]+)'''
)
_BEARER = re.compile(r"(?i)(bearer\s+)(\[REDACTED\]|[^\s,;\"']+)")


@dataclass(frozen=True)
class LogEntry:
    sequence: int
    level: int
    text: str


class _LogStream(io.TextIOBase):
    def __init__(self, owner: RuntimeLog, original, name: str, level: int):
        self.owner = owner
        self.original = original
        self.name = name
        self.level = level
        self.pending: dict[int, str] = {}
        self.lock = threading.RLock()

    @property
    def encoding(self):
        return getattr(self.original, "encoding", None) or "utf-8"

    def writable(self) -> bool:
        return True

    def isatty(self) -> bool:
        return bool(self.original and self.original.isatty())

    def fileno(self) -> int:
        if self.original is None:
            raise io.UnsupportedOperation("No native console")
        return self.original.fileno()

    def write(self, text: str) -> int:
        if not isinstance(text, str):
            raise TypeError("Stream output must be text")
        with self.lock:
            if self.original is not None:
                self.original.write(text)
            thread = threading.get_ident()
            value = self.pending.get(thread, "") + text
            lines = value.split("\n")
            self.pending[thread] = lines.pop()
            for line in lines:
                if line.rstrip("\r"):
                    self.owner.record(self.name, self.level, line.rstrip("\r"))
            # Bound partial-line buffering without dropping output from the archive.
            if len(self.pending[thread]) >= 16384:
                self.owner.record(self.name, self.level, self.pending.pop(thread))
        return len(text)

    def flush(self) -> None:
        with self.lock:
            for text in self.pending.values():
                if text:
                    self.owner.record(self.name, self.level, text)
            self.pending.clear()
            if self.original is not None:
                self.original.flush()


class RuntimeLog(logging.Handler):
    """Collect sanitized logs in memory; write a snapshot only on explicit save."""

    def __init__(self, directory: str | Path, *, history_limit: int = 1500):
        super().__init__(logging.DEBUG)
        self.directory = Path(directory)
        self.path: Path | None = None
        self.history: deque[LogEntry] = deque(maxlen=history_limit)
        # Only the view is bounded. Explicit saves include the entire run.
        self._archive: list[LogEntry] = []
        self._save_lock = threading.Lock()
        self.sequence = 0
        self.saved_sequence = 0
        self.file_error = ""
        self.secrets: set[str] = set()
        self.started = False
        self.streams: list[_LogStream] = []
        self.previous_hooks = None
        self.setFormatter(logging.Formatter(
            "[%(asctime)s.%(msecs)03d] [%(threadName)s/%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))

    def redact(self, text: str) -> str:
        with self.lock:
            for secret in sorted(self.secrets, key=len, reverse=True):
                text = text.replace(secret, "[REDACTED]")
        text = _CREDENTIAL.sub(r"\1[REDACTED]", text)
        return _BEARER.sub(r"\1[REDACTED]", text)

    def register_secret(self, value: str | None) -> None:
        if value:
            with self.lock:
                self.secrets.add(value)

    def emit(self, record: logging.LogRecord) -> None:
        text = self.redact(self.format(record))
        self.sequence += 1
        entry = LogEntry(self.sequence, record.levelno, text)
        self.history.append(entry)
        self._archive.append(entry)

    def record(self, name: str, level: int, message: str, *, exc_info=None) -> None:
        self.handle(logging.LogRecord(name, level, "", 0, message, (), exc_info))

    def entries_after(self, sequence: int = 0) -> list[LogEntry]:
        with self.lock:
            return [entry for entry in self.history if entry.sequence > sequence]

    def set_history_limit(self, limit: int) -> None:
        with self.lock:
            self.history = deque(self._archive[-limit:], maxlen=limit)

    def save(self) -> Path:
        with self._save_lock:
            temporary = None
            try:
                for stream in self.streams:
                    stream.flush()
                self.record("promptsmith.logging", logging.INFO, "Manual log snapshot requested")
                with self.lock:
                    entries = tuple(self._archive)
                self.directory.mkdir(parents=True, exist_ok=True)
                name = f"PromptSmith_{datetime.now():%Y%m%d_%H%M%S_%f}_{uuid4().hex}.log"
                destination = self.directory / name
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", errors="backslashreplace", newline="\n",
                                                 dir=self.directory, prefix=".snapshot-",
                                                 suffix=".tmp", delete=False) as output:
                    temporary = Path(output.name)
                    for entry in entries:
                        # Credentials may have been registered after an early record.
                        output.write(self.redact(entry.text) + "\n")
                temporary.replace(destination)
                with self.lock:
                    self.path = destination
                    self.saved_sequence = entries[-1].sequence
                    self.file_error = ""
                self.record("promptsmith.logging", logging.INFO,
                            f"Manual log snapshot saved: records={len(entries)} path={destination}")
                return destination
            except OSError as exc:
                with self.lock:
                    self.file_error = self.redact(str(exc))
                self.record("promptsmith.logging", logging.ERROR,
                            f"Manual log saving failed: {self.file_error}", exc_info=sys.exc_info())
                raise
            finally:
                if temporary is not None:
                    try:
                        temporary.unlink(missing_ok=True)
                    except OSError:
                        self.record("promptsmith.logging", logging.ERROR,
                                    "Cannot remove incomplete log snapshot", exc_info=sys.exc_info())

    def start(self, *, capture_process: bool = False) -> RuntimeLog:
        if self.started:
            return self
        self.started = True
        self.root_logger = logging.getLogger()
        self.previous_level = self.root_logger.level
        self.root_logger.setLevel(logging.DEBUG)
        self.root_logger.addHandler(self)
        if capture_process:
            self.streams = [_LogStream(self, sys.stdout, "stdout", logging.INFO),
                            _LogStream(self, sys.stderr, "stderr", logging.ERROR)]
            sys.stdout, sys.stderr = self.streams
            self.previous_hooks = (sys.excepthook, threading.excepthook, warnings.showwarning, sys.unraisablehook)
            sys.excepthook = self._exception_hook
            threading.excepthook = self._thread_exception_hook
            warnings.showwarning = self._warning_hook
            sys.unraisablehook = self._unraisable_hook
        self.record("promptsmith.logging", logging.INFO, "Runtime logging started; manual saving enabled")
        return self

    def _exception_hook(self, exc_type, value, traceback) -> None:
        self.record("promptsmith.exception", logging.CRITICAL, "Uncaught process exception",
                    exc_info=(exc_type, value, traceback))
        self.previous_hooks[0](exc_type, value, traceback)

    def _thread_exception_hook(self, args) -> None:
        self.record("promptsmith.exception", logging.ERROR,
                    f"Uncaught thread exception: {args.thread.name if args.thread else 'unknown'}",
                    exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        self.previous_hooks[1](args)

    def _warning_hook(self, message, category, filename, lineno, file=None, line=None) -> None:
        self.record("py.warnings", logging.WARNING,
                    warnings.formatwarning(message, category, filename, lineno, line).rstrip())
        if file is not None:
            self.previous_hooks[2](message, category, filename, lineno, file, line)

    def _unraisable_hook(self, args) -> None:
        self.record("promptsmith.exception", logging.ERROR,
                    f"Unraisable exception: {args.err_msg or 'callback or object cleanup'}",
                    exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        self.previous_hooks[3](args)

    def close(self) -> None:
        if self.started:
            for stream in self.streams:
                stream.flush()
            for name, stream in zip(("stdout", "stderr"), self.streams):
                if getattr(sys, name) is stream:
                    setattr(sys, name, stream.original)
            if self.previous_hooks:
                for owner, name, current, previous in (
                    (sys, "excepthook", self._exception_hook, self.previous_hooks[0]),
                    (threading, "excepthook", self._thread_exception_hook, self.previous_hooks[1]),
                    (warnings, "showwarning", self._warning_hook, self.previous_hooks[2]),
                    (sys, "unraisablehook", self._unraisable_hook, self.previous_hooks[3]),
                ):
                    if getattr(owner, name) == current:
                        setattr(owner, name, previous)
            self.record("promptsmith.logging", logging.INFO, "Runtime logging stopped")
            self.root_logger.removeHandler(self)
            if self.root_logger.level == logging.DEBUG:
                self.root_logger.setLevel(self.previous_level)
            self.started = False
        super().close()
