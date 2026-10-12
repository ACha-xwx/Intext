"""Isolated actual WebView2 settings CRUD; localhost directories only."""
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
OUT = ROOT / "local_artifacts/custom_provider_20261013"
OUT.mkdir(parents=True, exist_ok=True)
result = {"checks": []}
requests = []
NATIVE_KEYS = {"GPT中转甲":"disposable-native-gpt-a", "GPT中转乙":"disposable-native-gpt-b", "Claude中转":"disposable-native-claude"}


def check(name, value):
    result["checks"].append({"name": name, "passed": bool(value)})
    print(json.dumps({"check":name,"passed":bool(value)}, ensure_ascii=True), flush=True)
    assert value, name


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        requests.append(self.path)
        data = json.dumps({"data": [{"id": "gpt-6.1-sol"}, {"id": "private-alias"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        raise AssertionError("No model generation or connection probe authorized")

    def log_message(self, *_args):
        pass


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
thread = Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    with tempfile.TemporaryDirectory(prefix="promptsmith-custom-native-") as isolation:
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

                        def switch(name, typed=False):
                            if typed:
                                page.get_by_label("服务名称", exact=True).fill(name)
                                page.get_by_label("服务名称", exact=True).press("Tab")
                            else:
                                page.get_by_role("button", name="服务名称预设", exact=True).click()
                                page.get_by_role("listbox", name="服务名称预设", exact=True).get_by_role("option", name=name, exact=True).click()
                            page.wait_for_function("n=>!inFlight&&promptsmithSettings.current.connection.provider===n", arg=name)

                        for name, family in [("GPT中转甲", "OpenAI"), ("GPT中转乙", "OpenAI"), ("Claude中转", "Anthropic")]:
                            switch(name, typed=True)
                            check(name+" starts without guessed family/key/endpoint", page.evaluate("!promptsmithSettings.current.connection.model_provider&&!promptsmithSettings.current.has_key&&!promptsmithSettings.current.connection.base_url"))
                            page.get_by_role("button", name="保存设置", exact=True).click()
                            expect(page.locator(".settings-error")).to_contain_text("请选择模型供应商")
                            page.get_by_label("模型供应商", exact=True).select_option(family)
                            page.get_by_label("官网链接", exact=True).fill("https://gateway.example.invalid")
                            page.get_by_label("接口地址", exact=True).fill(f"http://127.0.0.1:{server.server_port}/v1")
                            page.get_by_label("模型 ID", exact=True).fill("private-alias")
                            key = page.get_by_label("API Key", exact=True)
                            key.fill(NATIVE_KEYS[name])
                            page.get_by_role("button", name="显示密钥", exact=True).click()
                            check(name+" typed key visibility", key.get_attribute("type") == "text")
                            page.get_by_role("button", name="确认", exact=True).click()
                            page.wait_for_function("!inFlight&&promptsmithSettings.current.confirmed")
                            check(name+" clears typed key after confirm", key.input_value() == "" and key.get_attribute("type") == "password")
                            page.get_by_role("button", name="获取模型", exact=True).click()
                            page.wait_for_function("!inFlight&&!promptsmithSettings.current.busy&&promptsmithSettings.current.available_models.length===2")
                            check(name+" fetched list visible", page.get_by_role("region", name="已获取模型", exact=True).get_by_text("private-alias", exact=True).is_visible())
                        for theme, size in [("light", (1440, 810)), ("dark", (720, 500))]:
                            page.get_by_role("tab", name="界面", exact=True).click()
                            page.get_by_label("输入区与模型菜单主题", exact=True).select_option(theme)
                            page.get_by_role("button", name="保存设置", exact=True).click()
                            page.wait_for_function("t=>!inFlight&&state.theme===t", arg=theme)
                            page.get_by_role("tab", name="模型", exact=True).click()
                            window.resize(*size)
                            page.get_by_role("button", name="服务名称预设", exact=True).click()
                            group = page.locator('.settings-provider-group[data-family="OpenAI"]')
                            check(theme+" GPT services share OpenAI group", group.get_by_role("option").count() == 3)
                            check(theme+" five family groups", page.locator(".settings-provider-group").count() == 5)
                            check(theme+" rows stay compact", all(38 <= option.bounding_box()["height"] <= 60 for option in page.get_by_role("listbox", name="服务名称预设", exact=True).get_by_role("option").all()))
                            check(theme+" icons follow chosen family", group.evaluate("e=>[...e.querySelectorAll('img')].every(img=>img.src===state.icons[state.theme].OpenAI)"))
                            page.locator("#settings-page").screenshot(path=str(OUT/(theme+"-groups.png")))
                            page.keyboard.press("Escape")
                        switch("GPT中转甲")
                        check("restores custom type website key flag", page.evaluate("promptsmithSettings.current.connection.model_provider==='OpenAI'&&promptsmithSettings.current.connection.website==='https://gateway.example.invalid'&&promptsmithSettings.current.has_key&&promptsmithSettings.current.confirmed"))
                        page.get_by_role("button", name="返回工作区", exact=True).click()
                        page.wait_for_function("document.querySelector('#settings-page').hidden")
                        page.locator("#model-button").click()
                        check("picker has no custom tab", page.locator('.providers button[data-provider="custom"]').count() == 0)
                        page.get_by_label("搜索模型", exact=True).fill("private-alias")
                        check("aliases preserve source identity", page.locator(".model-row").count() == 3)
                        check("unknown abilities not guessed", page.locator(".model-row .capability").count() == 0)
                        page.keyboard.press("Escape")
                        page.keyboard.press("Escape")
                        page.wait_for_function("!popupKind")
                        page.get_by_role("button", name="设置", exact=True).click()
                        page.get_by_role("button", name="删除供应商", exact=True).click()
                        dialog = page.get_by_role("dialog", name="删除自定义供应商", exact=True)
                        dialog.get_by_role("button", name="取消", exact=True).click()
                        check("cancel deletion preserves current", page.evaluate("promptsmithSettings.current.connection.provider==='GPT中转甲'"))
                        page.get_by_role("button", name="删除供应商", exact=True).click()
                        dialog.get_by_role("button", name="删除", exact=True).click()
                        page.wait_for_function("!inFlight&&promptsmithSettings.current.connection.provider==='DeepSeek'")
                        check("deleted source models gone", page.evaluate("state.models.every(m=>m.service_provider!=='GPT中转甲')"))
                        switch("GPT中转乙")
                        check("other service remains confirmed", page.evaluate("promptsmithSettings.current.confirmed&&promptsmithSettings.current.has_key"))
                        page.get_by_role("button", name="保存设置", exact=True).click()
                        page.wait_for_function("!inFlight")
                        check("browser never receives persisted key", page.evaluate("!JSON.stringify(state).includes('disposable-native-')"))
                        result["user_agent"] = page.evaluate("navigator.userAgent")
                        result["errors"] = page.locator(".settings-error").all_text_contents()
                        browser.close()
                except Exception as exc:
                    result["error"] = repr(exc)
                    result["requests"] = requests
                    result["debug_tail"] = [entry.text for entry in logs.entries_after()][-80:]
                    try:
                        result["failure_ui"] = page.evaluate("({settings:promptsmithSettings.current,notifications:state.notifications,form_error:document.querySelector('.settings-error')?.textContent})")
                    except Exception:
                        pass
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
            check("restart data excludes deleted profile", "GPT中转甲" not in saved.model_profiles)
            check("remaining keys independently decrypt", all(saved.model_profiles[name].api_key == NATIVE_KEYS[name] for name in ("GPT中转乙", "Claude中转")))
            check("only three localhost directory requests", len(requests) == 3)
            check("no automatic logs", not list((Path(isolation)/"PromptSmith/logs").glob("*.log")))
        finally:
            logs.close()
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)
(OUT/"native-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=True))
assert not result.get("error"), result.get("error")
