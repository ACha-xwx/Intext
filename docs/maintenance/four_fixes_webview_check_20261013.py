"""Production HTML in isolated native WebView2; synthetic bridge, no model calls."""
from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import tempfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "local_artifacts/network_relevance_20261013"
OUT.mkdir(parents=True, exist_ok=True)
STATES = json.loads((ROOT / "tests/fixtures/frontend_review.json").read_text(encoding="utf-8"))
checks = []


class Api:
    def __init__(self):
        self.calls = []
        self.settings = None

    def snapshot(self, *_args):
        return None

    def diagnostic(self, *_args):
        pass

    def dispatch(self, action, data, *_args):
        self.calls.append(dict(action=action, data=data))
        if action == "answer":
            return dict(ok=True, data=dict(submitted=[row["id"] for row in data["answers"]]))
        if action == "settings_rename_provider":
            settings = deepcopy(self.settings)
            settings["connection"]["provider"] = data["name"]
            settings["saved_providers"] = [data["name"] if n == data["target"] else n for n in settings["saved_providers"]]
            settings["provider_families"] = {data["name"]: "OpenAI"}
            settings["revision"] = "renamed"
            return dict(ok=True, data=dict(settings=settings))
        return dict(ok=True)


def check(name, passed):
    checks.append(dict(name=name, passed=bool(passed)))
    assert passed, name


with tempfile.TemporaryDirectory(prefix="promptsmith-four-fixes-") as isolation:
    os.environ["LOCALAPPDATA"] = isolation
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={port}"
    import webview
    from playwright.sync_api import sync_playwright, expect

    api = Api()
    window = webview.create_window("PromptSmith 隔离验收", str(ROOT / "resources/ui/workspace/index.html"),
                                   js_api=api, width=1440, height=810)
    error = []

    def loaded():
        try:
            with sync_playwright() as runtime:
                browser = runtime.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                page = next(p for c in browser.contexts for p in c.pages if "index.html" in p.url)
                page.set_default_timeout(10000)
                page.wait_for_function("Boolean(window.pywebview?.api?.dispatch)")
                for theme in ("light", "dark"):
                    state = deepcopy(STATES["empty"])
                    state.update(theme=theme, session="native-answers-"+theme)
                    state["cards"] = [{"key": "question:"+qid, "kind": "question", "question": {
                        "question_id": qid, "text": "问题"+qid}} for qid in ("q1", "q2", "q3")]
                    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
                    fields = page.locator(".answer-input")
                    fields.nth(0).fill("评委阅读")
                    fields.nth(2).fill("PDF交付")
                    fields.nth(0).press("Enter")
                    page.wait_for_function("!document.body.classList.contains('pending')")
                    batch = next(row for row in reversed(api.calls) if row["action"] == "answer")
                    check(theme+": all nonempty answers sent", batch["data"]["answers"] == [
                        {"id": "q1", "text": "评委阅读"}, {"id": "q3", "text": "PDF交付"}])
                    fields.nth(1).fill("第一行")
                    fields.nth(1).press("Shift+Enter")
                    check(theme+": Shift Enter inserts newline", fields.nth(1).input_value() == "第一行\n")

                    state = deepcopy(STATES["skills"])
                    state.update(theme=theme, session="native-skills-"+theme)
                    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
                    toolbar = page.get_by_role("toolbar", name="Skill 表格筛选")
                    check(theme+": filters share table frame", toolbar.evaluate("e=>e.parentElement.classList.contains('skill-table')"))
                    check(theme+": workflow actions outside table", page.locator(".skill-table").get_by_role("button", name="查找本地 Skill").count() == 0)
                    page.locator(".skill-table details").first.evaluate("e=>e.open=true")
                    page.evaluate("window.originalSkillTable=document.querySelector('.skill-table')")
                    next(c for c in state["cards"] if c["kind"] == "skills")["progress"] = "正在联网搜索 Skill：已收集10项信息"
                    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
                    check(theme+": progress preserves table", page.evaluate("originalSkillTable===document.querySelector('.skill-table')"))
                    check(theme+": progress preserves expanded detail", page.locator(".skill-table details").first.evaluate("e=>e.open"))
                    check(theme+": progress inline", "已收集10项" in page.get_by_role("status", name="Skill 搜索进度").inner_text())

                    state = deepcopy(STATES["empty"])
                    state.update(theme=theme, session="native-settings-"+theme, page="settings")
                    settings = state["settings"]
                    settings.update(saved_providers=["OpenAI", "GPT中转"], provider_families={"GPT中转": "OpenAI"}, confirmed=True, has_key=True)
                    settings["connection"].update(provider="GPT中转", model_provider="OpenAI")
                    api.settings = deepcopy(settings)
                    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
                    rename = page.get_by_role("button", name="重命名", exact=True)
                    field = page.get_by_label("服务名称", exact=True)
                    a, b = field.bounding_box(), rename.bounding_box()
                    check(theme+": rename next to service", a["x"]+a["width"] < b["x"] and abs(a["y"]+a["height"]/2-b["y"]-b["height"]/2) <= 1)
                    rename.click()
                    dialog = page.get_by_role("dialog", name="重命名自定义供应商")
                    dialog.get_by_role("textbox", name="新的服务名称").fill("比赛GPT")
                    dialog.get_by_role("textbox", name="新的服务名称").press("Enter")
                    expect(dialog).to_have_count(0)
                    check(theme+": rename applies", field.input_value() == "比赛GPT")
                    payload = next(row["data"] for row in reversed(api.calls) if row["action"] == "settings_rename_provider")
                    check(theme+": rename sends no key", "key" not in payload and page.get_by_label("API Key", exact=True).input_value() == "")
                check("no model bridge actions", all(row["action"] in {"answer", "drafts", "settings_rename_provider"} for row in api.calls))
                # WebView2 profile databases have their own transaction logs;
                # this contract concerns PromptSmith's diagnostic log folder.
                check("no automatic PromptSmith logs", not list((Path(isolation)/"PromptSmith/logs").glob("*.log")))
        except Exception as exc:
            error.append(repr(exc))
        finally:
            window.destroy()

    window.events.loaded += loaded
    webview.start(gui="edgechromium", storage_path=isolation, private_mode=True, http_server=True)

(OUT / "native-results.json").write_text(json.dumps(dict(checks=checks, errors=error), ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(dict(checks=checks, errors=error), ensure_ascii=True))
assert not error, error
