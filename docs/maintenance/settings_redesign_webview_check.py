"""Isolated real WebView2 settings acceptance; localhost directory GET only."""
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
OUT = ROOT / "local_artifacts/settings_redesign_20261013"
OUT.mkdir(parents=True, exist_ok=True)
result = {"checks": []}
requests = []


def check(name, value):
    result["checks"].append(dict(name=name, passed=bool(value)))
    print(json.dumps(result["checks"][-1], ensure_ascii=True), flush=True)
    assert value, name


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        requests.append(self.path)
        body = json.dumps({"data": [{"id": "codex-auto-review"}, {"id": "gpt-6.1-sol"}, {"id": "private-alias"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        requests.append("UNEXPECTED POST")
        self.send_error(405)

    def log_message(self, *_args):
        pass


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
Thread(target=server.serve_forever, daemon=True).start()
try:
    with tempfile.TemporaryDirectory(prefix="promptsmith-settings-redesign-") as isolation:
        os.environ["LOCALAPPDATA"] = isolation
        for name in list(os.environ):
            if name.startswith("PROMPTSMITH_") or name in {"OPENAI_API_KEY", "DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY", "GITHUB_TOKEN", "GH_TOKEN"}:
                os.environ.pop(name)
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
                        page.set_default_timeout(12000)

                        def settled():
                            page.wait_for_function("!promptsmithSettings.saving&&!inFlight&&!promptsmithSettings.switching&&!promptsmithSettings.dirty.size&&promptsmithSettings.keyAction==='keep'")

                        def choice(label, value):
                            page.get_by_role("combobox", name=label, exact=True).click()
                            page.get_by_role("listbox", name=label + "预设", exact=True).get_by_role("option", name=value, exact=True).click()

                        def switch(name, typed=False):
                            field = page.get_by_label("服务名称", exact=True)
                            if typed:
                                field.fill(name)
                                field.press("Tab")
                            else:
                                field.click()
                                page.get_by_role("listbox", name="服务名称预设", exact=True).get_by_role("option", name=name, exact=True).click()
                            page.wait_for_function("n=>!inFlight&&!promptsmithSettings.switching&&promptsmithSettings.current.connection.provider===n", arg=name)

                        page.get_by_role("button", name="设置", exact=True).click()
                        expect(page.locator(".settings-card")).to_be_visible()
                        check("removed explicit save and confirm controls", page.get_by_role("button", name="保存设置", exact=True).count() == 0 and page.get_by_role("button", name="确认", exact=True).count() == 0)
                        check("reference card with no brand", page.locator(".settings-card").count() == 1 and page.locator(".settings-brand").count() == 0)
                        check("all choices use custom combobox", page.locator(".settings-form select").count() == 0)
                        page.get_by_role("tab", name="界面", exact=True).click()
                        choice("输入区与模型菜单主题", "深色")
                        settled()
                        check("ordinary preference saves before model configured", load_settings(Path(isolation)/"PromptSmith/settings.json").preferences["composer_theme"] == "dark")
                        page.get_by_role("tab", name="模型", exact=True).click()
                        switch("本地验收服务", typed=True)
                        choice("模型供应商", "OpenAI")
                        page.get_by_label("接口地址", exact=True).fill(f"http://127.0.0.1:{server.server_port}/v1")
                        page.get_by_label("模型 ID", exact=True).fill("private-alias")
                        page.get_by_label("API Key", exact=True).fill("disposable-native-autosave")
                        page.get_by_label("API Key", exact=True).press("Tab")
                        settled()
                        check("automatic save enables valid model", page.evaluate("promptsmithSettings.current.confirmed&&promptsmithSettings.current.has_key"))
                        check("typed key cleared and never in browser snapshot", page.get_by_label("API Key", exact=True).input_value() == "" and "disposable-native-autosave" not in page.evaluate("JSON.stringify(state)"))
                        page.get_by_role("button", name="获取模型", exact=True).click()
                        page.wait_for_function("!inFlight&&!promptsmithSettings.current.busy&&promptsmithSettings.current.available_models.length===2")
                        check("internal model filtered and standalone list removed", page.evaluate("!promptsmithSettings.current.available_models.includes('codex-auto-review')") and page.get_by_role("region", name="已获取模型", exact=True).count() == 0)
                        for theme, size in [("light", (1440, 810)), ("dark", (720, 500))]:
                            page.get_by_role("tab", name="界面", exact=True).click()
                            choice("输入区与模型菜单主题", "浅色" if theme == "light" else "深色")
                            settled()
                            page.wait_for_function("t=>state.theme===t", arg=theme)
                            page.get_by_role("tab", name="模型", exact=True).click()
                            window.resize(*size)
                            page.wait_for_function("w=>Math.abs(innerWidth-w)<40", arg=size[0])
                            check(theme+" navigation fills full settings width", page.locator(".settings-tabs").evaluate("e=>{const a=e.firstElementChild.getBoundingClientRect(),b=e.lastElementChild.getBoundingClientRect(),r=e.getBoundingClientRect();return Math.abs(a.left-r.left)<1&&Math.abs(b.right-r.right)<1}"))
                            following = page.get_by_label("模型供应商", exact=True)
                            before = following.bounding_box()
                            page.get_by_label("服务名称", exact=True).click()
                            menu = page.get_by_role("listbox", name="服务名称预设", exact=True)
                            check(theme+" popover leaves following field in place", abs(following.bounding_box()["y"]-before["y"]) < 1 and menu.evaluate("e=>getComputedStyle(e).position==='fixed'&&e.matches(':popover-open')"))
                            check(theme+" provider icons", menu.locator("img").count() >= 5)
                            page.locator("#settings-page").screenshot(path=str(OUT/(theme+"-settings.png")))
                            page.keyboard.press("Escape")
                            expect(menu).not_to_be_visible()
                            page.get_by_label("模型 ID", exact=True).click()
                            check(theme+" fetched model choices include icons", page.get_by_role("listbox", name="模型 ID预设", exact=True).locator("img").count() == 2)
                            page.keyboard.press("Escape")
                        switch("DeepSeek")
                        switch("本地验收服务")
                        check("switch restores saved connection and key flag", page.evaluate("promptsmithSettings.current.confirmed&&promptsmithSettings.current.has_key&&promptsmithSettings.current.connection.model==='private-alias'"))
                        page.get_by_label("模型 ID", exact=True).fill("updated-alias")
                        page.get_by_role("button", name="返回工作区", exact=True).click()
                        page.wait_for_function("document.querySelector('#settings-page').hidden")
                        check("leaving flushes latest edit", load_settings(Path(isolation)/"PromptSmith/settings.json").connection["model"] == "updated-alias")
                        page.get_by_role("button", name="设置", exact=True).click()
                        expect(page.get_by_label("接口地址", exact=True)).to_be_visible()
                        page.get_by_label("接口地址", exact=True).fill("")
                        switch("DeepSeek")
                        switch("本地验收服务")
                        check("incomplete connection draft survives switching away and back", page.get_by_label("接口地址", exact=True).input_value() == "")
                        page.get_by_role("button", name="删除供应商", exact=True).click()
                        page.get_by_role("dialog").get_by_role("button", name="取消", exact=True).click()
                        check("cancel deletion preserves current profile", page.evaluate("promptsmithSettings.current.connection.provider==='本地验收服务'"))
                        page.get_by_role("button", name="删除供应商", exact=True).click()
                        page.get_by_role("dialog").get_by_role("button", name="删除", exact=True).click()
                        page.wait_for_function("!inFlight&&promptsmithSettings.current.connection.provider==='DeepSeek'")
                        check("delete removes encrypted saved profile", "本地验收服务" not in load_settings(Path(isolation)/"PromptSmith/settings.json").model_profiles)
                        result["user_agent"] = page.evaluate("navigator.userAgent")
                        browser.close()
                except Exception as exc:
                    result["error"] = repr(exc)
                    result["debug_tail"] = [entry.text for entry in logs.entries_after()][-60:]
                    try:
                        page.screenshot(path=str(OUT/"failure.png"))
                        result["failure_ui"] = page.evaluate("({settings:promptsmithSettings.current,error:document.querySelector('.settings-error')?.textContent,notifications:state.notifications})")
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
            if not result.get("error"):
                check("only one localhost GET, no generation or probe", requests == ["/v1/models"])
                check("no automatic log files", not list((Path(isolation)/"PromptSmith/logs").glob("*.log")))
            result["requests"] = requests
        finally:
            logs.close()
finally:
    server.shutdown()
    server.server_close()
(OUT/"native-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=True))
assert not result.get("error"), result.get("error")
