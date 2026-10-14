"""Real WebView2 + desktop controller; localhost directory, synthetic generation."""
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread, Timer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "local_artifacts/intext_hero_20261013/tutorial"
OUT.mkdir(parents=True, exist_ok=True)
result = {"checks": []}
requests, generations = [], []


def check(name, value):
    result["checks"].append(dict(name=name, passed=bool(value)))
    print(json.dumps(result["checks"][-1], ensure_ascii=True), flush=True)
    assert value, name


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        requests.append(self.path)
        data = json.dumps({"data": [{"id": "fixture-model"}, {"id": "codex-auto-review"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        requests.append("UNEXPECTED POST")
        self.send_error(405)

    def log_message(self, *_args):
        pass


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
Thread(target=server.serve_forever, daemon=True).start()
try:
    with tempfile.TemporaryDirectory(prefix="promptsmith-tutorial-") as isolation:
        os.environ["LOCALAPPDATA"] = isolation
        for name in list(os.environ):
            if name.startswith("PROMPTSMITH_") or name in {"OPENAI_API_KEY", "DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY", "GITHUB_TOKEN", "GH_TOKEN"}:
                os.environ.pop(name)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={port}"
        import webview
        from playwright.sync_api import sync_playwright, expect
        import promptsmith.ui as ui
        import promptsmith.web_workspace as workspace
        from promptsmith.preferences import load_settings, load_tutorial_status
        from promptsmith.runtime_log import RuntimeLog

        ui.warm_local_skill_index = lambda *_args: None
        # The user really sends through Controller/Session; replace only the
        # generation launch, so this acceptance never makes a paid model call.
        ui.PromptSmithApp.start_analysis = lambda app: generations.append(app.session.task_text)
        create_window = webview.create_window
        timeout = None

        def create(*args, **kwargs):
            window = create_window(*args, **kwargs)

            def loaded():
                global timeout
                try:
                    with sync_playwright() as runtime:
                        browser = runtime.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                        page = next(p for c in browser.contexts for p in c.pages if "index.html" in p.url)
                        page.set_default_timeout(12000)
                        guide = page.get_by_role("dialog", name="新手入门")
                        next_step = guide.get_by_role("button", name="下一步", exact=True)
                        start = page.get_by_role("button", name="开始使用 Intext", exact=True)
                        expect(start).to_be_visible()
                        check("hero waits before showing tutorial", guide.count() == 0)
                        start.click()
                        expect(page.locator("#startup-hero")).to_be_hidden()
                        expect(guide).to_be_visible()
                        check("first run waits for actual settings action", next_step.is_disabled())
                        check("first page offers skip without marking completed", guide.get_by_role("button", name="跳过教程", exact=True).is_visible() and load_tutorial_status(Path(isolation)/"PromptSmith/settings.json") == "not_started")
                        page.get_by_role("button", name="设置", exact=True).click()
                        expect(next_step).to_be_enabled()
                        next_step.click()
                        expect(next_step).to_be_disabled()
                        check("service configuration is gated", next_step.is_disabled())
                        page.get_by_label("服务名称", exact=True).click()
                        page.get_by_role("listbox", name="服务名称预设").get_by_role("option", name="OpenAI", exact=True).click()
                        page.get_by_label("接口地址", exact=True).fill(f"http://127.0.0.1:{server.server_port}/v1")
                        page.get_by_label("API Key", exact=True).fill("disposable-tutorial-key")
                        page.get_by_label("API Key", exact=True).press("Tab")
                        expect(next_step).to_be_enabled()
                        path = Path(isolation) / "PromptSmith/settings.json"
                        check("configuration saved encrypted before progressing", "disposable-tutorial-key" not in path.read_text(encoding="utf-8") and load_settings(path).api_key == "disposable-tutorial-key")
                        next_step.click()
                        expect(next_step).to_be_disabled()
                        page.get_by_role("button", name="获取模型", exact=True).click()
                        expect(next_step).to_be_enabled()
                        check("directory gate uses actual localhost result", requests == ["/v1/models"])
                        next_step.click()
                        expect(next_step).to_be_disabled()
                        page.get_by_label("模型 ID", exact=True).click()
                        page.get_by_role("listbox", name="模型 ID预设").get_by_role("option", name="fixture-model", exact=True).click()
                        expect(next_step).to_be_enabled()
                        check("model selection automatically persisted", load_settings(path).connection["model"] == "fixture-model")
                        check("model-only save does not show window restart notice", page.get_by_text("启动窗口大小下次启动生效", exact=False).count() == 0)
                        next_step.click()
                        finish = guide.get_by_role("button", name="完成", exact=True)
                        expect(finish).to_be_enabled()
                        check("no premature completion", load_tutorial_status(path) == "not_started")
                        page.get_by_role("button", name="返回工作区", exact=True).click()
                        page.wait_for_function("state.page==='workspace'&&!inFlight")
                        expect(finish).to_be_enabled()
                        check("finish is available without sending a goal", finish.is_enabled() and generations == [])
                        page.screenshot(path=str(OUT / "light-complete.png"))
                        finish.click()
                        expect(guide).to_have_count(0)
                        check("completion only after clicking finish", load_tutorial_status(path) == "completed")
                        page.get_by_role("button", name="设置", exact=True).click()
                        page.get_by_role("tab", name="界面", exact=True).click()
                        page.get_by_role("combobox", name="输入区与模型菜单主题", exact=True).click()
                        page.get_by_role("option", name="深色", exact=True).click()
                        page.wait_for_function("state.theme==='dark'&&!promptsmithSettings.saving")
                        page.get_by_role("button", name="重新查看教程", exact=True).click()
                        expect(guide).to_be_visible()
                        check("replay starts at step one", guide.get_by_text("第 1 步，共 5 步", exact=True).is_visible())
                        window.resize(720, 500)
                        page.wait_for_function("innerWidth<760")
                        next_step.click()
                        key = page.get_by_label("API Key", exact=True)
                        key.scroll_into_view_if_needed()
                        key.click()
                        check("narrow dark service controls remain clickable", key.evaluate("e=>e===document.activeElement"))
                        page.screenshot(path=str(OUT / "dark-settings.png"))
                        guide.get_by_role("button", name="关闭教程", exact=True).click()
                        expect(guide).to_have_count(0)
                        check("closing replay keeps completion and model", load_tutorial_status(path) == "completed" and load_settings(path).connection["model"] == "fixture-model")
                        check("tutorial has no extra generation or connection probes", generations == [] and requests == ["/v1/models"])
                        result["user_agent"] = page.evaluate("navigator.userAgent")
                except Exception as exc:
                    result["error"] = repr(exc)
                    result["debug_tail"] = [entry.text for entry in logs.entries_after()][-60:]
                    try:
                        page.screenshot(path=str(OUT / "native-failure.png"))
                    except Exception:
                        pass
                finally:
                    if timeout:
                        timeout.cancel()
                    window.destroy()

            window.events.loaded += loaded
            timeout = Timer(180, window.destroy)
            timeout.daemon = True
            timeout.start()
            return window

        webview.create_window = create
        logs = RuntimeLog(Path(isolation)/"PromptSmith/logs").start()
        try:
            workspace.run_web_workspace(logs)
            check("no automatic PromptSmith log files", not list((Path(isolation)/"PromptSmith/logs").glob("*.log")))
        finally:
            logs.close()
finally:
    server.shutdown()
    server.server_close()
(OUT / "native-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
assert not result.get("error"), result.get("error")
assert len(result["checks"]) >= 14, "acceptance did not run to completion"
