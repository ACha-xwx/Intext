"""Actual WebView2 + Python settings bridge + localhost model directories."""
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "local_artifacts/provider_profiles_20261012"
OUT.mkdir(parents=True, exist_ok=True)
result = {"checks": []}
requests = []


def check(name, value):
    result["checks"].append({"name": name, "passed": bool(value)})
    assert value, name


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        provider = self.path.split("/")[1]
        requests.append((self.path, self.headers.get("Authorization"), self.headers.get("x-api-key")))
        ids = {"OpenAI": "gpt-6.1-sol", "Anthropic": "claude-opus-5-5", "xAI": "grok-4.7",
               "Google": "gemini-3.8-flash", "DeepSeek": "deepseek-flash"}
        content = json.dumps({"data": [{"id": ids[provider]}, {"id": provider+"-private"}], "has_more": False}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(content)
    def do_POST(self):
        raise AssertionError("No generation/test request is authorized by this check")
    def log_message(self, *_args):
        pass


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
thread = Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    with tempfile.TemporaryDirectory(prefix="promptsmith-providers-webview-") as isolation:
        os.environ["LOCALAPPDATA"] = isolation
        for key in list(os.environ):
            if key.startswith("PROMPTSMITH_") or key in {"OPENAI_API_KEY", "DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY", "GITHUB_TOKEN", "GH_TOKEN"}:
                os.environ.pop(key)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={port}"
        import webview
        import promptsmith.ui as ui
        import promptsmith.web_workspace as workspace
        from promptsmith.runtime_log import RuntimeLog
        from promptsmith.preferences import load_settings
        from playwright.sync_api import sync_playwright, expect
        ui.warm_local_skill_index = lambda *_args: None
        create_window = webview.create_window

        def create(*args, **kwargs):
            window = create_window(*args, **kwargs)
            def loaded():
                try:
                    with sync_playwright() as runtime:
                        browser = runtime.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                        page = next(p for c in browser.contexts for p in c.pages if "index.html" in p.url)
                        page.set_default_timeout(10000)
                        page.get_by_role("button", name="设置", exact=True).click()
                        expect(page.get_by_label("服务名称", exact=True)).to_be_visible()

                        def switch(provider):
                            page.get_by_role("button", name="服务名称预设", exact=True).click()
                            page.get_by_role("option", name=provider, exact=True).click()
                            page.wait_for_function("p=>!inFlight&&promptsmithSettings.current.connection.provider===p", arg=provider)

                        for provider in ("OpenAI", "Anthropic", "xAI", "Google", "DeepSeek"):
                            switch(provider)
                            page.get_by_label("接口地址", exact=True).fill(f"http://127.0.0.1:{server.server_port}/{provider}/v1")
                            page.get_by_label("API Key", exact=True).fill("disposable-native-"+provider)
                            page.get_by_role("button", name="确认", exact=True).click()
                            page.wait_for_function("!inFlight&&promptsmithSettings.current.confirmed")
                            check(provider+" explicit confirmation persisted", True)
                            page.get_by_role("button", name="获取模型", exact=True).click()
                            page.wait_for_function("!inFlight&&!promptsmithSettings.current.busy&&promptsmithSettings.current.available_models.length===2")
                            check(provider+" actual models fetched", True)
                        for provider in ("OpenAI", "Anthropic", "xAI", "Google", "DeepSeek"):
                            switch(provider)
                            check(provider+" restored key flag and directory", page.evaluate("promptsmithSettings.current.has_key&&promptsmithSettings.current.confirmed&&promptsmithSettings.current.available_models.length===2"))
                            check(provider+" restored endpoint", provider+"/v1" in page.get_by_label("接口地址", exact=True).input_value())
                        for theme, size in [("light", (1440, 810)), ("dark", (720, 500))]:
                            page.get_by_role("tab", name="界面", exact=True).click()
                            page.get_by_label("输入区与模型菜单主题", exact=True).select_option(theme)
                            page.get_by_role("button", name="保存设置", exact=True).click()
                            page.wait_for_function("t=>!inFlight&&state.theme===t", arg=theme)
                            page.get_by_role("tab", name="模型", exact=True).click()
                            window.resize(*size)
                            page.get_by_role("button", name="服务名称预设", exact=True).click()
                            choices = page.get_by_role("listbox", name="服务名称预设", exact=True)
                            check(theme+" five icon choices", choices.get_by_role("option").count() == 5 and choices.locator("img").count() == 5)
                            page.wait_for_timeout(450)
                            checkmark = choices.locator('[aria-selected="true"] svg').bounding_box()
                            check(theme+" compact selected checkmark", 12 <= checkmark["width"] <= 24 and 12 <= checkmark["height"] <= 24)
                            check(theme+" readable provider rows", all(38 <= row.bounding_box()["height"] <= 60 for row in choices.get_by_role("option").all()))
                            check(theme+" icons match saved theme", choices.evaluate("e=>[...e.querySelectorAll('img')].every(img=>img.src===state.icons[state.theme][img.closest('[role=option]').dataset.value])"))
                            page.locator("#settings-page").screenshot(path=str(OUT/(theme+"-providers.png")))
                            page.keyboard.press("Escape")
                        page.get_by_role("button", name="返回工作区", exact=True).click()
                        page.wait_for_function("document.querySelector('#settings-page').hidden")
                        page.locator("#model-button").click()
                        search = page.get_by_label("搜索模型", exact=True)
                        search.fill("private")
                        check("bottom offers only fetched unknown IDs", page.locator(".model-row").count() == 5)
                        check("unknown IDs have no guessed capabilities", page.locator(".model-row .capability").count() == 0)
                        search.fill("GPT-6.1")
                        check("local metadata matches fetched model", page.locator(".model-row").count() == 1)
                        page.locator(".model-row").click()
                        page.wait_for_function("state.model==='gpt-6.1-sol'&&state.active_service==='OpenAI'&&!choiceRunning")
                        check("composer selection uses originating provider", True)
                        page.locator(".picker").screenshot(path=str(OUT/"picker.png"))
                        check("no browser credential disclosure", page.evaluate("!JSON.stringify(state).includes('disposable-native-')"))
                        result["user_agent"] = page.evaluate("navigator.userAgent")
                        result["errors"] = page.evaluate("[...document.querySelectorAll('.settings-error')].map(e=>e.textContent).filter(Boolean)")
                        browser.close()
                except Exception as exc:
                    result["error"] = repr(exc)
                finally:
                    window.destroy()
            window.events.loaded += loaded
            return window
        webview.create_window = create
        logs = RuntimeLog(Path(isolation)/"PromptSmith/logs").start()
        try:
            workspace.run_web_workspace(logs)
            (OUT/"native-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            assert not result.get("error"), result.get("error")
            saved = load_settings(Path(isolation)/"PromptSmith/settings.json")
            check("all five saved keys and directories decrypt independently", all(
                profile.api_key == "disposable-native-"+provider and len(profile.model_ids) == 2
                for provider, profile in saved.model_profiles.items()) and len(saved.model_profiles) == 5)
            check("only five local directory requests", len(requests) == 5)
            check("no automatic logs written", not list((Path(isolation)/"PromptSmith/logs").glob("*.log")))
        finally:
            logs.close()
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)
(OUT/"native-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=True))
assert not result.get("error") and not result.get("errors")
