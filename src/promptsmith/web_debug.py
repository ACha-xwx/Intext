"""WebView2 Debug presentation; all data here is independent of Tk objects."""
from copy import deepcopy
import logging
import os
import threading
from uuid import uuid4

from .paths import resource_root

LOG = logging.getLogger(__name__)


class WebDebugConsole:
    """Minimal native-console adapter. Tk only publishes plain preferences."""
    def __init__(self, logs, desktop_api):
        self.logs = logs
        self.desktop_api = desktop_api
        self.identity = uuid4().hex
        self.lock = threading.Lock()
        self.preferences = {}
        self.preference_revision = 0
        self.closed = False
        self.focus_requested = False
        self.window = self  # Existing settings use console.window.lift().

    def apply_preferences(self, values):
        with self.lock:
            self.preferences = deepcopy(values)
            self.preference_revision += 1

    def update_palette(self, values):
        with self.lock:
            for key in ("composer_theme", "font_size"):
                self.preferences[key] = values[key]

    def lift(self):
        with self.lock:
            self.focus_requested = True

    def close(self):
        with self.lock:
            self.closed = True

    def user_closed(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
        self.desktop_api._debug_closed(self.identity)
        LOG.info("Web Debug window closed by user; collection continues in memory")


class DebugApi:
    """Read redacted logs, explicitly save, or open the fixed logs directory."""
    def __init__(self, console):
        self._console = console

    def snapshot(self, since=0):
        if isinstance(since, bool) or not isinstance(since, (int, float)) or since < 0:
            since = 0
        console = self._console
        with console.lock:
            preferences = deepcopy(console.preferences)
            revision = console.preference_revision
        logs = console.logs
        entries = logs.entries_after(int(since))
        return dict(entries=[dict(id=e.sequence, level=e.level, text=logs.redact(e.text)) for e in entries],
                    sequence=entries[-1].sequence if entries else int(since), cached=len(logs.entries_after()),
                    saved_sequence=logs.saved_sequence, path=str(logs.path) if logs.path else "",
                    error=logs.file_error, directory_exists=logs.directory.is_dir(), preferences=preferences,
                    preference_revision=revision)

    def save(self):
        try:
            path = self._console.logs.save()
            return dict(ok=True, path=str(path))
        except OSError:
            return dict(ok=False, error="日志未保存，请检查目录权限或磁盘空间后重试。")

    def diagnostic(self, level, event, detail):
        levels = {"debug": logging.DEBUG, "info": logging.INFO, "warn": logging.WARNING, "error": logging.ERROR}
        self._console.logs.record(__name__, levels.get(level, logging.DEBUG),
                                  "Debug browser %s: %s" % (str(event)[:120], str(detail)[:12000]))
        return True

    def open_directory(self):
        try:
            directory = self._console.logs.directory
            if not directory.is_dir():
                return dict(ok=False, error="日志目录尚未创建，请先保存日志。")
            os.startfile(directory)
            return dict(ok=True)
        except OSError:
            LOG.exception("Web Debug could not open log directory")
            return dict(ok=False, error="无法打开日志目录，请查看错误记录后重试。")


class DebugWindowManager:
    """Create and close Chromium windows from pywebview's worker thread."""
    def __init__(self, desktop_api, logs):
        self.desktop_api, self.logs = desktop_api, logs
        self.lock = threading.Lock()
        self.consoles = []
        self.windows = {}

    def create_console(self, _parent, _logs, _on_close):
        console = WebDebugConsole(self.logs, self.desktop_api)
        with self.lock:
            self.consoles.append(console)
        return console

    def sync(self):
        import webview
        with self.lock:
            consoles = list(self.consoles)
        for console in consoles:
            with console.lock:
                closed, focus = console.closed, console.focus_requested
                console.focus_requested = False
            window = self.windows.get(console.identity)
            if closed:
                if window:
                    self.windows.pop(console.identity)
                    if not window.events.closed.is_set():
                        window.destroy()
                with self.lock:
                    if console in self.consoles:
                        self.consoles.remove(console)
                continue
            try:
                if window is None:
                    window = webview.create_window("PromptSmith · Debug 控制台",
                        str(resource_root()/"resources/ui/workspace/debug.html"), js_api=DebugApi(console),
                        width=1120, height=640, min_size=(600, 320), background_color="#171717", text_select=True)
                    window.events.closed += console.user_closed
                    self.windows[console.identity] = window
                    LOG.info("Web Debug window opened: engine=WebView2 severity_colors=preserved")
                elif focus:
                    window.show()
            except Exception:
                LOG.exception("Web Debug window operation failed; will retry")

    def close_all(self):
        with self.lock:
            consoles = list(self.consoles)
        for console in consoles:
            console.close()
        self.sync()
