"""Actual log snapshots; all paths isolated, no automatic persistence."""
import logging
from promptsmith.runtime_log import RuntimeLog
from promptsmith.web_workspace import DesktopApi
from promptsmith.web_debug import DebugApi, WebDebugConsole
from promptsmith.preferences import defaults


def test_debug_projection_redacts_all_levels_and_save_retains_entire_run(tmp_path):
    logs = RuntimeLog(tmp_path / "logs", history_limit=2)
    logs.register_secret("offline-sensitive")
    console = WebDebugConsole(logs, DesktopApi())
    console.apply_preferences(defaults())
    api = DebugApi(console)
    for level in (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR):
        logs.record("fixture", level, "before offline-sensitive")
    try:
        raise RuntimeError("full traceback fixture")
    except RuntimeError:
        import sys
        logs.record("fixture", logging.CRITICAL, "full exception", exc_info=sys.exc_info())
    snapshot = api.snapshot()
    assert [e["level"] for e in snapshot["entries"]] == [40, 50]
    assert "Traceback" in snapshot["entries"][-1]["text"]
    assert not (tmp_path / "logs").exists()
    assert "offline-sensitive" not in str(snapshot)
    assert api.save()["ok"]
    text = logs.path.read_text(encoding="utf-8")
    assert all(label in text for label in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"))
    assert "full traceback fixture" in text and "offline-sensitive" not in text
    assert not api.snapshot(snapshot["sequence"])["entries"] or logs.sequence > snapshot["sequence"]


def test_debug_close_routes_to_tk_queue_and_programmatic_close_keeps_preference():
    api = DesktopApi()
    console = WebDebugConsole(None, api)
    console.user_closed()
    request = api._queue.get_nowait()
    assert request["action"] == "debug_closed" and request["data"]["id"] == console.identity
    console.user_closed()
    assert api._queue.empty()
    other = WebDebugConsole(None, api)
    other.close()
    other.user_closed()
    assert api._queue.empty()


def test_debug_failed_manual_save_returns_retry_and_complete_error(tmp_path, monkeypatch):
    logs = RuntimeLog(tmp_path / "logs")
    api = DebugApi(WebDebugConsole(logs, DesktopApi()))
    monkeypatch.setattr("pathlib.Path.mkdir", lambda *_a, **_kw: (_ for _ in ()).throw(PermissionError("fixture read-only")))
    assert not api.save()["ok"]
    snapshot = api.snapshot()
    assert "fixture read-only" in snapshot["error"]
    assert "PermissionError" in snapshot["entries"][-1]["text"]


def test_debug_browser_errors_include_stack_and_redact_without_writing_files(tmp_path):
    logs = RuntimeLog(tmp_path / "logs")
    logs.register_secret("debug-browser-secret")
    api = DebugApi(WebDebugConsole(logs, DesktopApi()))
    assert api.diagnostic("error", "unhandled rejection", "Error: debug-browser-secret\n at poll (debug.js:42)")
    entry = api.snapshot()["entries"][-1]
    assert entry["level"] == logging.ERROR and "at poll" in entry["text"]
    assert "debug-browser-secret" not in entry["text"] and "[REDACTED]" in entry["text"]
    assert not logs.directory.exists()
