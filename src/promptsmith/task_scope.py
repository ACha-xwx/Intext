"""Cooperative cancellation shared by a conversation's background operations."""
from __future__ import annotations

from concurrent.futures import CancelledError
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Event, Lock
from typing import Callable, Iterator
import logging
from uuid import uuid4


_current_scope: ContextVar[TaskScope | None] = ContextVar("promptsmith_task_scope", default=None)


class TaskScope:
    def __init__(self) -> None:
        self._cancelled = Event()
        self.token = uuid4().hex
        self._lock = Lock()
        self._aborters: set[Callable[[], None]] = set()

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def cancel(self) -> None:
        self._cancelled.set()
        with self._lock:
            aborters = tuple(self._aborters)
            self._aborters.clear()
        for abort in aborters:
            try:
                abort()
            except Exception:
                logging.getLogger(__name__).warning("Cancelled transport cleanup failed", exc_info=True)

    def check(self) -> None:
        if self.cancelled:
            raise CancelledError("后台任务已停止或随会话切换、程序关闭取消。")

    @contextmanager
    def interrupt_on_cancel(self, abort: Callable[[], None]) -> Iterator[None]:
        with self._lock:
            cancelled = self.cancelled
            if not cancelled:
                self._aborters.add(abort)
        if cancelled:
            abort()
            self.check()
        try:
            self.check()
            yield
        finally:
            with self._lock:
                self._aborters.discard(abort)

    @contextmanager
    def activate(self) -> Iterator[None]:
        token = _current_scope.set(self)
        try:
            self.check()
            yield
        finally:
            _current_scope.reset(token)


def check_cancelled() -> None:
    scope = _current_scope.get()
    if scope is not None:
        scope.check()


@contextmanager
def interrupt_on_cancel(abort: Callable[[], None]) -> Iterator[None]:
    scope = _current_scope.get()
    if scope is None:
        yield
    else:
        with scope.interrupt_on_cancel(abort):
            yield
