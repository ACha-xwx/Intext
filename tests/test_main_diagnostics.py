import builtins
import logging
import sys

import pytest

import promptsmith.main as entry
from promptsmith.runtime_log import RuntimeLog


@pytest.mark.parametrize("module,level", [("ui", 1), ("tkinter", 0)])
def test_ui_import_failure_reaches_log_before_tk_creation(tmp_path, monkeypatch, module, level):
    original_import = builtins.__import__
    previous_handlers = list(logging.getLogger().handlers)
    previous_stdout, previous_stderr = sys.stdout, sys.stderr
    monkeypatch.setattr(entry, "application_data_dir", lambda: tmp_path)
    monkeypatch.setenv("PROMPTSMITH_API_KEY", "startup-fixture-secret")
    logs = RuntimeLog(tmp_path / "logs")
    monkeypatch.setattr(entry, "RuntimeLog", lambda _directory: logs)

    def fail_ui(name, globals=None, locals=None, fromlist=(), import_level=0, **kwargs):
        import_level = kwargs.get("level", import_level)
        if name == module and import_level == level:
            raise ImportError("UI startup failed startup-fixture-secret")
        return original_import(name, globals, locals, fromlist, import_level)

    monkeypatch.setattr(builtins, "__import__", fail_ui)
    with pytest.raises(ImportError, match="UI startup failed"):
        entry.main(["--smoke-test"])
    assert logs.path is None and not logs.directory.exists()
    content = logs.save().read_text(encoding="utf-8")
    assert "Desktop startup or main loop failed" in content and "ImportError" in content
    assert "Traceback" in content and "startup-fixture-secret" not in content
    assert "Runtime logging stopped" in content
    assert logging.getLogger().handlers == previous_handlers
    assert sys.stdout is previous_stdout and sys.stderr is previous_stderr


@pytest.mark.parametrize("renderer", ["mshtml", "edgechromium"])
def test_webview_preflight_requires_chromium_before_backend_starts(monkeypatch, renderer):
    import importlib
    from types import SimpleNamespace
    from promptsmith.web_workspace import ensure_webview2, WebRendererUnavailable
    monkeypatch.setattr(importlib.import_module("webview.guilib"), "initialize", lambda _gui: SimpleNamespace(renderer=renderer))
    if renderer == "edgechromium":
        ensure_webview2()
    else:
        with pytest.raises(WebRendererUnavailable, match="WebView2 Runtime"):
            ensure_webview2()


def test_explicit_web_startup_failure_shows_actionable_prompt_without_backend(tmp_path, monkeypatch):
    from promptsmith.web_workspace import WebRendererUnavailable
    errors = []
    monkeypatch.setattr(entry, "application_data_dir", lambda: tmp_path)
    monkeypatch.setattr("promptsmith.web_workspace.run_web_workspace",
                        lambda *_a, **_kw: (_ for _ in ()).throw(WebRendererUnavailable("请安装 WebView2 Runtime")))
    monkeypatch.setattr("tkinter.messagebox.showerror", lambda title, message: errors.append((title, message)))
    assert entry.main(["--renderer", "web"]) == 1
    assert errors and "WebView2 Runtime" in errors[0][1]
    assert not (tmp_path / "logs").exists()


def test_auto_web_preflight_failure_falls_back_to_tk_and_shuts_down(tmp_path, monkeypatch, caplog):
    from promptsmith.web_workspace import WebRendererUnavailable
    calls = []
    class Root:
        def after(self, *_a): pass
        def mainloop(self): calls.append("mainloop")
        def destroy(self): calls.append("destroy")
    class App:
        def __init__(self, *_a, **_kw):
            from types import SimpleNamespace
            self.executor = SimpleNamespace(shutdown=lambda **_kw: calls.append("executor shutdown"))
        def shutdown(self, **_kw): calls.append("shutdown")
        def close(self): pass
    monkeypatch.setattr(entry, "application_data_dir", lambda: tmp_path)
    monkeypatch.setattr("promptsmith.web_workspace.run_web_workspace",
                        lambda *_a, **_kw: (_ for _ in ()).throw(WebRendererUnavailable("missing runtime")))
    monkeypatch.setattr("tkinter.Tk", Root)
    monkeypatch.setattr("promptsmith.ui.PromptSmithApp", App)
    with caplog.at_level(logging.INFO):
        assert entry.main([]) == 0
    assert calls == ["mainloop", "shutdown", "executor shutdown", "destroy"]
    assert "Continuing startup with Tk" in caplog.text
