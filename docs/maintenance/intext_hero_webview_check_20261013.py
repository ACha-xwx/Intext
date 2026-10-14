"""Native WebView2 startup DOM; synthetic snapshots, no personal data or API."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import tempfile
from threading import Timer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "local_artifacts/intext_hero_20261013/native"
OUT.mkdir(parents=True, exist_ok=True)
parser = argparse.ArgumentParser()
parser.add_argument("--status", choices=("not_started", "completed", "skipped"), required=True)
args = parser.parse_args()
STATES = json.loads((ROOT / "tests/fixtures/frontend_review.json").read_text(encoding="utf-8"))
result = {"status": args.status, "checks": []}


def check(name, value):
    result["checks"].append(dict(name=name, passed=bool(value)))
    print(json.dumps(result["checks"][-1], ensure_ascii=True), flush=True)
    assert value, name


class Api:
    def __init__(self):
        self.calls = []
        self.diagnostics = []

    def snapshot(self, *_args):
        return None

    def diagnostic(self, *values):
        self.diagnostics.append(values)

    def dispatch(self, action, data, *_args):
        self.calls.append(dict(action=action, data=data))
        return dict(ok=True)


with tempfile.TemporaryDirectory(prefix="intext-hero-check-") as isolation:
    os.environ["LOCALAPPDATA"] = isolation
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={port}"
    import webview
    from playwright.sync_api import sync_playwright, expect

    api = Api()
    window = webview.create_window("Intext 隔离验收", str(ROOT / "resources/ui/workspace/index.html"),
                                   js_api=api, width=1440, height=810)

    def loaded():
        try:
            with sync_playwright() as runtime:
                browser = runtime.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                page = next(p for c in browser.contexts for p in c.pages if "index.html" in p.url)
                page.set_default_timeout(10000)
                page.wait_for_function("Boolean(window.pywebview?.api?.dispatch)")
                check("native page uses Intext brand", page.title() == "Intext")
                expect(page.get_by_role("status", name="正在加载 Intext")).to_be_visible()
                check("loader precedes ready snapshot", page.locator(".startup-loader").evaluate(
                    "e=>[e.offsetWidth,e.offsetHeight,getComputedStyle(e).animationDuration]") == [40, 40, "2s"])
                check("workspace cannot operate before entry", page.locator("#workspace-shell").evaluate("e=>e.inert"))
                state = deepcopy(STATES["empty"])
                state.update(tutorial_status=args.status, drafts={"message": "保留目标草稿"})
                page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
                start = page.get_by_role("button", name="开始使用 Intext", exact=True)
                guide = page.get_by_role("dialog", name="新手入门")
                if args.status == "not_started":
                    expect(start).to_be_visible()
                    check("larger circular start action", start.evaluate("e=>[e.offsetWidth,e.offsetHeight]") == [60,60])
                    check("single loaded SVG at smaller width", page.locator(".startup-wordmark").evaluate(
                        "e=>e.complete&&e.naturalWidth>0&&e.getBoundingClientRect().width===640"))
                    check("no premature tutorial", guide.count() == 0)
                    expect(start.locator("canvas")).to_have_count(1)
                    check("native liquid metal uses WebGL2", start.locator("canvas").evaluate(
                        "e=>Boolean(e.getContext('webgl2'))"))
                    for theme in ("light", "dark"):
                        state["theme"] = theme
                        page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
                        page.screenshot(path=str(OUT / (args.status + "-" + theme + ".png")))
                        check(theme + " group centered", page.locator(".startup-group").evaluate(
                            "e=>{const r=e.getBoundingClientRect();return Math.abs(r.x+r.width/2-innerWidth/2)<1&&Math.abs(r.y+r.height/2-innerHeight/2)<1}"))
                    window.resize(720, 500)
                    page.wait_for_function("innerWidth<760")
                    check("narrow hero fits", page.locator(".startup-group").evaluate(
                        "e=>{const r=e.getBoundingClientRect();return r.x>=0&&r.right<=innerWidth&&r.y>=0&&r.bottom<=innerHeight}"))
                    page.keyboard.press("Control+s")
                    page.keyboard.press("Control+k")
                    check("hidden shortcuts send no commands", not api.calls)
                    start.click()
                    expect(guide).to_be_visible()
                    expect(guide.get_by_role("button", name="下一步", exact=True)).to_be_disabled()
                    check("tutorial starts after click and waits for operation", guide.is_visible())
                else:
                    expect(page.locator("#startup-hero")).to_be_hidden()
                    check("saved status enters automatically without tutorial", not start.is_visible() and guide.count() == 0)
                expect(page.locator("#startup-hero")).to_be_hidden()
                check("shader released after entry", page.locator(".startup-metal canvas").count() == 0)
                check("workspace unlocked and draft retained", not page.locator("#workspace-shell").evaluate("e=>e.inert")
                      and page.locator("#message").input_value() == "保留目标草稿")
                page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
                check("snapshot does not reopen hero", not page.locator("#startup-hero").is_visible())
                check("no generation or status mutation", not api.calls)
                page.wait_for_function("promptsmithStartup.entered")
                check("lifecycle diagnostics present", any("进入工作区" in str(row) for row in api.diagnostics))
                check("no automatic application logs", not list((Path(isolation)/"PromptSmith/logs").glob("*.log")))
                result["user_agent"] = page.evaluate("navigator.userAgent")
                result["diagnostics"] = api.diagnostics
        except Exception as exc:
            result["error"] = repr(exc)
            try:
                page.screenshot(path=str(OUT / (args.status + "-failure.png")))
            except Exception:
                pass
        finally:
            timeout.cancel()
            window.destroy()

    window.events.loaded += loaded
    timeout = Timer(80, window.destroy)
    timeout.daemon = True
    timeout.start()
    webview.start(gui="edgechromium", storage_path=isolation, private_mode=True, http_server=True)

(OUT / (args.status + ".json")).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
assert not result.get("error"), result.get("error")
assert len(result["checks"]) >= 10, "acceptance did not finish"
