import json
import logging
import sys
import threading
import time
import tkinter as tk
from copy import deepcopy
from urllib.error import URLError
from urllib.error import HTTPError
from urllib.request import Request
from io import BytesIO
from pathlib import Path

import pytest

from promptsmith.api import ApiConfig, ApiError, ChatCompletionsClient
from promptsmith.debug_console import DebugConsole, LEVEL_COLORS, load_debug_preference, save_debug_preference
from promptsmith.runtime_log import RuntimeLog
from promptsmith.typography import Typography
from promptsmith.ui import PromptSmithApp
from promptsmith.preferences import load_preferences


@pytest.fixture
def app(tk_root, tmp_path):
    window = tk.Toplevel(tk_root)
    window.withdraw()
    application = PromptSmithApp(window, evidence_root=tmp_path / "runs")
    yield application
    application.shutdown(wait=True)
    window.destroy()


def test_settings_toggle_reopen_retains_memory_and_only_button_saves(app):
    before = deepcopy(app.session.to_dict())
    app.show_settings()
    assert not app.debug_console_enabled_var.get()
    toggle = app.widgets["debug_console_toggle"]
    toggle.invoke()
    first = app.debug_console
    app.set_debug_console_enabled()
    assert app.debug_console is first
    assert load_preferences(app._preferences_path)[0]["debug_console_enabled"]
    logging.getLogger("promptsmith.console-test").info("visible before close")
    first.poll()
    assert "visible before close" in first.text.get("1.0", "end")
    first.on_close()
    assert app.debug_console is None and not app.debug_console_enabled_var.get()
    assert not load_preferences(app._preferences_path)[0]["debug_console_enabled"]
    logging.getLogger("promptsmith.console-test").error("written while closed")
    toggle.invoke()
    app.debug_console.poll()
    assert "written while closed" in app.debug_console.text.get("1.0", "end")
    assert app.runtime_log.path is None and not app.runtime_log.directory.exists()
    app.debug_console.save_button.invoke()
    assert "written while closed" in app.runtime_log.path.read_text(encoding="utf-8")
    assert "已保存" in app.debug_console.path_var.get()
    assert app.session.to_dict() == before
    assert not app._model_settings_confirmed()


def test_console_filter_clear_copy_and_redaction(app):
    app.api_key_var.set("sensitive-fixture-value")
    app.debug_console_enabled_var.set(True)
    app.set_debug_console_enabled()
    console = app.debug_console
    logger = logging.getLogger("promptsmith.console-test")
    logger.debug("low level entry")
    logger.error("error sensitive-fixture-value")
    console.level_var.set("ERROR 及以上")
    console.rebuild()
    content = console.text.get("1.0", "end-1c")
    assert "low level entry" not in content
    assert "[REDACTED]" in content and "sensitive-fixture-value" not in content
    console.copy()
    assert console.window.clipboard_get() == content
    console.clear()
    assert console.text.get("1.0", "end-1c") == ""
    assert app.runtime_log.path is None and not app.runtime_log.directory.exists()
    logger.error("after clear")
    console.poll()
    assert "after clear" in console.text.get("1.0", "end")
    console.save_button.invoke()
    saved = app.runtime_log.path.read_text(encoding="utf-8")
    assert "low level entry" in saved and "after clear" in saved
    assert "sensitive-fixture-value" not in saved and "[REDACTED]" in saved


def test_console_uses_distinct_severity_colors(app):
    app.debug_console_enabled_var.set(True)
    app.set_debug_console_enabled()
    console = app.debug_console
    expected = {
        logging.DEBUG: "#66b3ff",
        logging.INFO: "#f5f7fa",
        logging.WARNING: "#ffd166",
        logging.ERROR: "#ff6b6b",
        logging.CRITICAL: "#ff3b30",
    }
    assert LEVEL_COLORS == expected
    assert {level: console.text.tag_cget(str(level), "foreground") for level in expected} == expected


def test_background_exception_full_chain_and_tk_callback_logged(app, monkeypatch):
    completed = []
    def operation():
        try:
            raise ValueError("worker root cause")
        except ValueError as exc:
            raise RuntimeError("worker outer failure") from exc
    app._submit(operation, lambda _value: pytest.fail("failure expected"), completed.append)
    deadline = time.monotonic() + 5
    while not completed and time.monotonic() < deadline:
        app.root.update()
        time.sleep(.01)
    assert len(completed) == 1 and isinstance(completed[0], RuntimeError)
    seen = []
    app._previous_callback_exception = lambda *args: seen.append(args)
    try:
        raise KeyError("Tk root cause")
    except KeyError:
        app._tk_root.report_callback_exception(*sys.exc_info())
    assert seen
    content = app.runtime_log.save().read_text(encoding="utf-8")
    assert "Background operation failed" in content and "promptsmith_" in content
    assert all(text in content for text in ("worker root cause", "worker outer failure", "direct cause",
                                            "Unhandled Tk callback", "Tk root cause", "Traceback"))
    notices = []
    monkeypatch.setattr("promptsmith.ui.messagebox.showerror", lambda *args, **kwargs: notices.append(args))
    try:
        raise OSError("handled UI error")
    except OSError as exc:
        app._show_error("保存失败", str(exc), parent=app.root)
    assert notices
    assert "handled UI error" in app.runtime_log.save().read_text(encoding="utf-8")


def test_info_and_warning_dialogs_are_captured_without_changing_dialogs(app, monkeypatch):
    notices = []
    monkeypatch.setattr("promptsmith.ui.messagebox.showinfo", lambda *args, **kwargs: notices.append(args))
    monkeypatch.setattr("promptsmith.ui.messagebox.showwarning", lambda *args, **kwargs: notices.append(args))
    app._show_info("notice title", "notice detail", parent=app.root)
    try:
        raise ValueError("warning underlying failure")
    except ValueError:
        app._show_warning("warning title", "warning detail", parent=app.root)
    content = app.runtime_log.save().read_text(encoding="utf-8")
    assert notices == [("notice title", "notice detail"), ("warning title", "warning detail")]
    assert "notice title: notice detail" in content and "/INFO]" in content
    assert "warning title: warning detail" in content and "/WARNING]" in content
    assert "ValueError: warning underlying failure" in content


def test_api_failure_preserves_status_and_full_diagnostics(app, monkeypatch):
    config = ApiConfig("https://example.invalid/v1", "offline-model", "test-api-secret")
    app.runtime_log.register_secret(config.api_key)
    def fail(*args, **kwargs):
        raise URLError("network diagnostic test-api-secret")
    monkeypatch.setattr("promptsmith.api.urlopen", fail)
    with pytest.raises(ApiError, match="无法连接"):
        ChatCompletionsClient(config)._send_json(Request(config.base_url), invalid_message="invalid")
    content = app.runtime_log.save().read_text(encoding="utf-8")
    assert "HTTP request failed" in content and "kind=network" in content
    assert "network diagnostic" in content and "URLError" in content and "Traceback" in content
    assert config.api_key not in content


@pytest.mark.parametrize("failure,kind,details", [
    (TimeoutError("underlying timeout"), "timeout", "TimeoutError: underlying timeout"),
    (HTTPError("https://example.invalid/v1", 429, "rate limit", {}, BytesIO(b'{}')),
     "http_error", "HTTPError"),
])
def test_api_wrapped_failures_preserve_original_cause(app, monkeypatch, failure, kind, details):
    def fail(*args, **kwargs):
        raise failure
    monkeypatch.setattr("promptsmith.api.urlopen", fail)
    client = ChatCompletionsClient(ApiConfig("https://example.invalid/v1", "offline-model", "test-key"))
    with pytest.raises(ApiError) as raised:
        client._send_json(Request(client.config.base_url), invalid_message="invalid")
    assert raised.value.kind == kind and raised.value.__cause__ is failure
    content = app.runtime_log.save().read_text(encoding="utf-8")
    assert details in content and "direct cause" in content


def test_debug_preference_restores_on_start_and_shutdown_cleans_poll(tk_root, tmp_path):
    save_debug_preference(tmp_path / "diagnostics.json", True)
    window = tk.Toplevel(tk_root)
    app = PromptSmithApp(window, evidence_root=tmp_path / "runs")
    console = app.debug_console
    assert console is not None
    app.shutdown(wait=True)
    app.shutdown(wait=True)
    assert console.closed and console.after_id is None
    assert app.runtime_log not in logging.getLogger().handlers
    assert load_debug_preference(tmp_path / "diagnostics.json")
    assert load_preferences(tmp_path / "settings.json")[0]["debug_console_enabled"]
    assert app.runtime_log.path is None and not app.runtime_log.directory.exists()
    window.destroy()


def test_corrupt_preferences_recover_to_default(tmp_path):
    path = tmp_path / "diagnostics.json"
    path.write_text("{broken")
    assert not load_debug_preference(path)
    save_debug_preference(path, True)
    assert json.loads(path.read_text()) == {"debug_console_enabled": True}


def test_save_button_failure_shows_red_traceback_and_can_retry(app, monkeypatch):
    app.debug_console_enabled_var.set(True)
    app.set_debug_console_enabled()
    console = app.debug_console
    assert console.path_var.get() == "未保存"
    assert console.directory_button.instate(["disabled"])
    def fail(*args):
        raise OSError("disk full retry fixture")
    with monkeypatch.context() as failing:
        failing.setattr(Path, "replace", fail)
        console.save_button.invoke()
    assert app.runtime_log.path is None
    assert "保存失败" in console.path_var.get()
    content = console.text.get("1.0", "end-1c")
    assert "Traceback" in content and "OSError: disk full retry fixture" in content
    position = console.text.search("Manual log saving failed", "1.0")
    assert str(logging.ERROR) in console.text.tag_names(position)
    assert console.save_button.instate(["!disabled"])
    console.save_button.invoke()
    assert not app.runtime_log.file_error
    assert "已保存" in console.path_var.get()
    assert "disk full retry fixture" in app.runtime_log.path.read_text(encoding="utf-8")
    assert console.directory_button.instate(["!disabled"])


@pytest.fixture
def isolated_console(tk_root, tmp_path):
    parent = tk.Toplevel(tk_root)
    parent.withdraw()
    typography = Typography(parent, {"font_size": 12})
    logs = RuntimeLog(tmp_path / "logs", history_limit=100)
    console = DebugConsole(parent, logs, lambda: None)
    console.window.update()
    yield console, logs
    console.close()
    logs.close()
    typography.close()
    parent.destroy()


def test_tk_legend_counts_records_and_filters_independently(isolated_console):
    console, logs = isolated_console
    for level in LEVEL_COLORS:
        logs.record("fixture", level, f"severity-{level}\ntraceback line")
    console.poll()
    assert len(console.legend_buttons) == 5
    for level, button in console.legend_buttons.items():
        assert button.cget("text").endswith(" 1")
    console.legend_buttons[logging.INFO].invoke()
    assert "severity-20" not in console.text.get("1.0", "end")
    assert "severity-40" in console.text.get("1.0", "end")
    assert console.legend_buttons[logging.INFO].cget("foreground") == "#7e858d"
    logs.record("fixture", logging.INFO, "hidden-new-info")
    console.poll()
    assert console.legend_buttons[logging.INFO].cget("text").endswith(" 2")
    console.legend_buttons[logging.INFO].invoke()
    assert "hidden-new-info" in console.text.get("1.0", "end")
    console.clear()
    assert all(b.cget("text").endswith(" 0") for b in console.legend_buttons.values())
    assert not logs.directory.exists()


def test_tk_new_logs_do_not_steal_history_and_resume_at_bottom(isolated_console):
    console, logs = isolated_console
    for i in range(80):
        logs.record("fixture", logging.INFO, f"history-{i}")
    console.poll()
    console.window.update()
    assert console.text.yview()[1] >= .999
    console.text.yview("15.0")
    console.window.update()
    before = console.text.get("@0,0", "@0,0 lineend")
    logs.record("fixture", logging.ERROR, "new-error")
    console.poll()
    console.window.update()
    assert console.text.get("@0,0", "@0,0 lineend") == before
    console.text.see("end")
    console.window.update()
    logs.record("fixture", logging.DEBUG, "follow-at-bottom")
    console.poll()
    console.window.update()
    assert console.text.yview()[1] >= .999
    console.autoscroll_var.set(False)
    before = console.text.get("@0,0", "@0,0 lineend")
    logs.record("fixture", logging.WARNING, "do-not-follow")
    console.poll()
    console.window.update()
    assert console.text.get("@0,0", "@0,0 lineend") == before


def test_tk_anchor_survives_line_trim_and_cache_eviction(isolated_console):
    console, logs = isolated_console
    logs.set_history_limit(60)
    console.line_limit = 55
    for i in range(60):
        logs.record("fixture", logging.INFO, f"anchor-{i}")
    console.poll()
    console.window.update()
    console.text.yview("20.0")
    console.window.update()
    before = console.text.get("@0,0", "@0,0 lineend")
    for i in range(5):
        logs.record("fixture", logging.ERROR, f"new-{i}")
    console.poll()
    console.window.update()
    assert console.text.get("@0,0", "@0,0 lineend") == before
    assert console.text.yview()[1] < .999


def test_tk_multiline_anchor_survives_trimming_inside_one_record(isolated_console):
    console, logs = isolated_console
    console.line_limit = 60
    logs.record("fixture", logging.ERROR, "\n".join(f"multi-{i}" for i in range(60)))
    console.poll()
    console.window.update()
    console.text.yview("15.0")
    console.window.update()
    before = console.text.get("@0,0", "@0,0 lineend")
    for i in range(5):
        logs.record("fixture", logging.INFO, f"new-{i}")
    console.poll()
    console.window.update()
    assert console.text.get("@0,0", "@0,0 lineend") == before


def test_tk_hidden_new_logs_evict_old_display_without_writing_or_idle_logs(isolated_console):
    console, logs = isolated_console
    logs.set_history_limit(2)
    logs.record("fixture", logging.INFO, "old-display")
    console.poll()
    console.legend_buttons[logging.ERROR].invoke()
    for _ in range(2):
        logs.record("fixture", logging.ERROR, "hidden-error")
    console.poll()
    assert "old-display" not in console.text.get("1.0", "end")
    assert console.legend_buttons[logging.INFO].cget("text") == "INFO 0"
    assert console.legend_buttons[logging.ERROR].cget("text") == "ERROR 2"
    before = logs.sequence
    for _ in range(5):
        console.poll()
    assert logs.sequence == before and not logs.directory.exists()
