"""Actual WebView2 Debug acceptance with disposable logs; no model or user data."""
import json
import logging
import os
from pathlib import Path
import socket
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "local_artifacts/debug_log_view_20261013"
OUT.mkdir(parents=True, exist_ok=True)
result = {"checks": []}


def check(name, value):
    result["checks"].append(dict(name=name, passed=bool(value)))
    print(json.dumps(result["checks"][-1], ensure_ascii=True), flush=True)
    assert value, name


with tempfile.TemporaryDirectory(prefix="promptsmith-debug-layout-") as isolation:
    os.environ["LOCALAPPDATA"] = isolation
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={port}"
    import webview
    from playwright.sync_api import sync_playwright, expect
    from promptsmith.preferences import defaults
    from promptsmith.runtime_log import RuntimeLog
    from promptsmith.web_debug import DebugApi, WebDebugConsole

    logs = RuntimeLog(Path(isolation) / "PromptSmith/logs")
    logs.register_secret("disposable-native-debug-key")
    console = WebDebugConsole(logs, None)
    console.apply_preferences(defaults())
    for i in range(80):
        logs.record("promptsmith.web_workspace", logging.DEBUG,
                    f"Web workspace action completed: action=drafts task=task-fixture-{i}")
    logs.record("promptsmith.web_workspace", logging.DEBUG,
                "Browser settings suggestions opened: settings-field-connection-provider")
    try:
        try:
            raise ValueError("底层错误 disposable-native-debug-key")
        except ValueError as exc:
            raise RuntimeError("完整异常中文🧪 " * 30) from exc
    except RuntimeError:
        logs.record("promptsmith.api", logging.ERROR, "模型请求失败", exc_info=sys.exc_info())
    window = webview.create_window("PromptSmith · Debug 隔离验收",
                                  str(ROOT / "resources/ui/workspace/debug.html"),
                                  js_api=DebugApi(console), width=1120, height=640, min_size=(600, 320))

    def loaded():
        try:
            with sync_playwright() as runtime:
                browser = runtime.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                page = next(p for c in browser.contexts for p in c.pages if "debug.html" in p.url)
                page.set_default_timeout(10000)
                expect(page.locator(".log-message").filter(has_text="草稿已同步").first).to_be_visible()
                check("compact clock source level columns", page.locator(".log-line").first.evaluate("e=>/^\\d{2}:\\d{2}:\\d{2}$/.test(e.querySelector('.log-time').textContent)&&e.querySelector('.log-level').textContent==='DBG'&&e.querySelector('.log-source').textContent==='[web_workspace]'"))
                check("known messages use concise Chinese", page.locator(".log-message").filter(has_text="展开服务名称菜单").count() == 1)
                check("complete redacted exception chain", all(value in page.locator(".log-error .log-message").inner_text() for value in ("ValueError", "RuntimeError", "direct cause", "🧪", "[REDACTED]")))
                check("secret absent from DOM", "disposable-native-debug-key" not in page.locator("body").inner_text())
                check("toolbar retains save clear copy and filters", page.get_by_role("button", name="保存日志", exact=True).count() == 1 and page.locator(".log-legend-item").count() == 5)
                for theme, size in (("light", (1120, 640)), ("dark", (600, 440))):
                    values = dict(defaults(), composer_theme=theme)
                    console.apply_preferences(values)
                    window.resize(*size)
                    page.wait_for_function("theme=>document.documentElement.dataset.theme===theme", arg=theme)
                    check(theme + " messages wrap without horizontal overflow", page.locator("#debug-scroll").evaluate("e=>e.scrollWidth<=e.clientWidth+1"))
                    page.locator("#debug-scroll").evaluate("e=>e.scrollTop=0")
                    page.screenshot(path=str(OUT / (theme + "-debug.png")))
                page.locator("#debug-scroll").evaluate("e=>e.scrollTop=180")
                before = page.locator(".log-line[data-id='20']").bounding_box()["y"]
                logs.record("promptsmith.ui", logging.WARNING, "隔离新增日志")
                expect(page.locator(".log-message").filter(has_text="隔离新增日志")).to_be_visible()
                check("new logs preserve history reading", abs(page.locator(".log-line[data-id='20']").bounding_box()["y"] - before) < 2)
                warning = page.locator(".legend-warning")
                warning.click()
                check("filter hides level and retains count", page.locator(".log-warning").count() == 0 and warning.get_attribute("aria-pressed") == "false" and warning.locator(".legend-count").inner_text() == "1")
                warning.click()
                check("filter restores original record", page.locator(".log-warning").count() == 1)
                check("no logs written before manual save", not logs.directory.exists())
                page.get_by_role("button", name="保存日志", exact=True).click()
                page.wait_for_function("Array.from(document.querySelectorAll('.notification-body')).some(e=>e.textContent.startsWith('已保存'))")
                content = logs.path.read_text(encoding="utf-8")
                check("manual save retains full metadata and exception", all(value in content for value in ("action=drafts task=task-fixture-0", "promptsmith.web_workspace", "ValueError", "RuntimeError", "direct cause")))
                check("manual save remains redacted", "disposable-native-debug-key" not in content)
                result["user_agent"] = page.evaluate("navigator.userAgent")
                browser.close()
        except Exception as exc:
            result["error"] = repr(exc)
            try:
                page.screenshot(path=str(OUT / "failure.png"))
            except Exception:
                pass
        finally:
            window.destroy()

    window.events.loaded += loaded
    webview.start(gui="edgechromium")
(OUT / "native-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
assert not result.get("error"), result.get("error")
