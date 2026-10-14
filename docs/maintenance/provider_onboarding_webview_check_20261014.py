"""Actual source/frozen WebView2: fresh custom service, tutorial, restart/migration.

Only a localhost model directory is contacted; no real key or model generation.
"""
import argparse
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
from threading import Thread
import time
from urllib.request import build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from promptsmith.preferences import load_settings, load_tutorial_status
from promptsmith.session import SessionState
from promptsmith.session_history import SessionHistory
from playwright.sync_api import sync_playwright, expect
import psutil
from settings_brand_webview_check_20261014 import application_windows, close_window


def run(executable, output):
    output.mkdir(parents=True, exist_ok=True)
    report = dict(kind="actual_frozen_webview2" if executable else "actual_source_webview2", checks=[])
    requests = []

    def check(name, passed):
        report["checks"].append(dict(name=name, passed=bool(passed)))
        assert passed, name

    class Directory(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            body = json.dumps({"data": [{"id": "gpt-6.1-sol"}, {"id": "codex-auto-review"}]}).encode()
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

    server = ThreadingHTTPServer(("127.0.0.1", 0), Directory)
    Thread(target=server.serve_forever, daemon=True).start()
    opener = build_opener(ProxyHandler({}))

    @contextmanager
    def launch(isolated, command, runtime):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        env = {k: v for k, v in os.environ.items() if not k.startswith("PROMPTSMITH_")}
        env.update(LOCALAPPDATA=str(isolated), PROMPTSMITH_SMOKE_CLOSE_MS="90000",
                   WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=f"--remote-debugging-port={port}")
        process = subprocess.Popen([*command, "--renderer", "web"], cwd=isolated, env=env,
                                   creationflags=subprocess.CREATE_NO_WINDOW,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        page = browser = None
        try:
            deadline = time.monotonic() + 55
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"Application exited before WebView2: {process.returncode}")
                for _, title, messages in application_windows(process):
                    if title == "Unhandled exception in script":
                        raise RuntimeError("Frozen startup failed: " + "\n".join(messages))
                try:
                    with opener.open(f"http://127.0.0.1:{port}/json/version", timeout=.5):
                        break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Actual WebView2 did not become ready")
                    time.sleep(.15)
            browser = runtime.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            # CDP may be ready while the initial WebView2 page is still about:blank.
            deadline = time.monotonic() + 15
            while page is None:
                page = next((p for context in browser.contexts for p in context.pages
                             if "index.html" in p.url), None)
                if page is None:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("WebView2 workspace navigation did not finish")
                    context = browser.contexts[0]
                    if context.pages:
                        context.pages[0].wait_for_timeout(100)
                    else:
                        context.wait_for_event("page", timeout=15000)
            page.wait_for_load_state("domcontentloaded")
            page.set_default_timeout(12000)
            check("actual WebView2 page", page.title() == "Intext")
            yield page
            browser.close()
            browser = None
            close_window(process)
            check("normal WebView2 shutdown", process.wait(timeout=15) == 0)
        except Exception:
            if page is not None:
                try:
                    page.screenshot(path=str(output / "failure.png"))
                except Exception:
                    pass
            raise
        finally:
            if browser is not None:
                browser.close()
            if process.poll() is None:
                close_window(process)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    for child in psutil.Process(process.pid).children(recursive=True):
                        child.kill()
                    process.kill()
                    process.wait(timeout=5)

    try:
        with tempfile.TemporaryDirectory(prefix="intext-service-acceptance-") as directory, sync_playwright() as runtime:
            isolated = Path(directory)
            if executable:
                target = isolated / "Intext.exe"
                shutil.copy2(executable, target)
                report["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
                command = [str(target)]
            else:
                command = [sys.executable, str(ROOT / "run_promptsmith.py")]
            data_root = isolated / "Intext"
            settings_path = data_root / "settings.json"
            with launch(isolated, command, runtime) as page:
                page.get_by_role("button", name="开始使用 Intext", exact=True).click()
                guide = page.get_by_role("dialog", name="新手入门")
                next_step = guide.get_by_role("button", name="下一步", exact=True)
                page.get_by_role("button", name="设置", exact=True).click()
                next_step.click()
                service = page.get_by_label("服务名称", exact=True)
                service.fill("YUN")
                service.press("Tab")
                family = page.get_by_role("combobox", name="模型供应商", exact=True)
                expect(family).to_be_enabled()
                family.click()
                page.get_by_role("listbox", name="模型供应商预设", exact=True).get_by_role("option", name="OpenAI", exact=True).click()
                page.get_by_label("接口地址", exact=True).fill(f"http://127.0.0.1:{server.server_port}/v1")
                page.get_by_label("API Key", exact=True).fill("disposable-native-onboarding")
                expect(next_step).to_be_enabled()
                check("key autosaved while input still focused", page.get_by_label("API Key", exact=True).input_value() == "")
                saved = load_settings(settings_path)
                check("encrypted custom key saved without model ID", saved.api_key == "disposable-native-onboarding" and saved.connection["model"] == "" and saved.connection["model_provider"] == "OpenAI")
                check("secret absent from saved text and browser snapshot", "disposable-native-onboarding" not in settings_path.read_text(encoding="utf-8") and "disposable-native-onboarding" not in page.evaluate("JSON.stringify(state)"))
                check("new default directory and no old directory", settings_path.is_file() and not (isolated / "PromptSmith").exists())
                next_step.click()
                expect(next_step).to_be_disabled()
                page.get_by_role("button", name="获取模型", exact=True).click()
                expect(next_step).to_be_enabled()
                check("directory fetched through actual local HTTP", requests == ["/v1/models"])
                next_step.click()
                expect(next_step).to_be_disabled()
                page.get_by_label("模型 ID", exact=True).click()
                menu = page.get_by_role("listbox", name="模型 ID预设", exact=True)
                check("unusable codex-auto-review hidden", menu.get_by_role("option", name="codex-auto-review", exact=True).count() == 0)
                menu.get_by_role("option", name="gpt-6.1-sol", exact=True).click()
                expect(next_step).to_be_enabled()
                check("selected model saved and ready", load_settings(settings_path).model_confirmed)
                next_step.click()
                finish = guide.get_by_role("button", name="完成", exact=True)
                expect(finish).to_be_enabled()
                check("tutorial not completed prematurely", load_tutorial_status(settings_path) == "not_started")
                finish.click()
                expect(guide).to_have_count(0)
                check("tutorial completed only by finish", load_tutorial_status(settings_path) == "completed")
                page.screenshot(path=str(output / "configured.png"))
            session = SessionState.new()
            session.set_task("恢复上次比赛技术文档的回答")
            identity = SessionHistory(data_root / "history").save(session.to_dict())
            before = settings_path.read_bytes()
            data_root.rename(isolated / "PromptSmith")
            with launch(isolated, command, runtime) as page:
                page.wait_for_function("promptsmithStartup.entered")
                check("existing tutorial completion restored", page.get_by_role("dialog", name="新手入门").count() == 0)
                page.get_by_role("button", name="设置", exact=True).click()
                expect(page.get_by_label("服务名称", exact=True)).to_have_value("YUN")
                check("migration keeps encrypted settings bytes", settings_path.read_bytes() == before)
                check("migration keeps key and confirmation", load_settings(settings_path).api_key == "disposable-native-onboarding" and load_settings(settings_path).model_confirmed)
                check("legacy folder renamed", not (isolated / "PromptSmith").exists())
                restored = SessionHistory(data_root / "history")
                check("migration keeps resumable history", restored.load(identity).task_text == session.task_text)
                check("no automatic runtime log files", not list((data_root / "logs").glob("*.log")))
                check("no model generation HTTP request", "UNEXPECTED POST" not in requests)
                report["user_agent"] = page.evaluate("navigator.userAgent")
                page.screenshot(path=str(output / "restored.png"))
        check("all HTTP requests local model directory only", all(path == "/v1/models" for path in requests))
    except Exception as error:
        report["error"] = repr(error)
        raise
    finally:
        server.shutdown()
        server.server_close()
        report["directory_requests"] = requests
        (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(dict(kind=report["kind"], checks=len(report["checks"]), passed=all(c["passed"] for c in report["checks"]))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.exe.resolve() if args.exe else None, args.output.resolve())
