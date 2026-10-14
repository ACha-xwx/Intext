"""Isolated native WebView2 presentation checks; synthetic bridge, no real APIs."""
from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import tempfile
from threading import Timer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "local_artifacts/backtrack_answers_20261013"
OUT.mkdir(parents=True, exist_ok=True)
STATES = json.loads((ROOT / "tests/fixtures/frontend_review.json").read_text(encoding="utf-8"))
checks, errors = [], []


class Api:
    def __init__(self):
        self.calls = []

    def snapshot(self, *_args):
        return None

    def diagnostic(self, *_args):
        pass

    def dispatch(self, action, data, *_args):
        self.calls.append(dict(action=action, data=data))
        if action == "answer":
            return dict(ok=True, data=dict(submitted=[row["id"] for row in data["answers"]]))
        return dict(ok=True)


def check(name, passed):
    checks.append(dict(name=name, passed=bool(passed)))
    assert passed, name


def stage_state(theme, stage, natural, previous, next_stage):
    state = deepcopy(STATES["plan"])
    state.update(theme=theme, session="native-backtrack-" + theme, stamp=theme + stage,
                 drafts={}, locked=False, stop_scope="scope-" + theme)
    nav = dict(stage=stage, natural=natural, previous=previous, next=next_stage, revisiting=stage != natural)
    state["navigation"] = nav
    state["cards"] = [dict(kind="navigation", key="navigation", title="回看与继续", **nav)]
    state["buttons"] = {"back_stage": dict(text="返回上一步", enabled=True)}
    if next_stage:
        state["buttons"]["continue_stage"] = dict(text="继续下一步", enabled=True)
    return state


with tempfile.TemporaryDirectory(prefix="promptsmith-backtrack-") as isolation:
    os.environ["LOCALAPPDATA"] = isolation
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={port}"
    import webview
    from playwright.sync_api import sync_playwright

    api = Api()
    window = webview.create_window("PromptSmith 返回流程隔离验收", str(ROOT / "resources/ui/workspace/index.html"),
                                   js_api=api, width=1440, height=810)

    def loaded():
        try:
            with sync_playwright() as runtime:
                browser = runtime.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                page = next(p for c in browser.contexts for p in c.pages if "index.html" in p.url)
                page.set_default_timeout(6000)
                page.wait_for_function("Boolean(window.pywebview?.api?.dispatch)")
                for theme in ("light", "dark"):
                    busy = stage_state(theme, "requirements", "requirements", "interview", None)
                    busy["locked"] = True
                    busy["cards"] += [deepcopy(c) for c in STATES["plan"]["cards"] if c["kind"] == "requirements"]
                    page.evaluate("s=>promptsmithView.applySnapshot(s)", busy)
                    back = page.get_by_role("button", name="返回上一步", exact=True)
                    check(theme + ": busy back remains enabled", back.is_enabled())
                    before = len(api.calls)
                    back.click()
                    page.wait_for_function("!document.body.classList.contains('pending')")
                    check(theme + ": back uses cancellable navigate bridge", any(
                        c["action"] == "navigate" and c["data"].get("scope") == "scope-"+theme
                        for c in api.calls[before:]))

                    restored = stage_state(theme, "interview", "interview", None, None)
                    answers = {"q1": "给评委👩‍💻", "q2": "中文", "q3": "PDF交付"}
                    restored["drafts"] = dict(answer_restore_id="restored-"+theme, answers=answers)
                    restored["cards"] = [dict(key="active_question" if i == 1 else "question:q"+str(i),
                        kind="question", question=dict(question_id="q"+str(i), text="请回答问题"+str(i)))
                        for i in range(1, 4)]
                    page.evaluate("s=>promptsmithView.applySnapshot(s)", restored)
                    page.wait_for_timeout(80)
                    fields = page.locator(".answer-input")
                    check(theme + ": whole round restored", [f.input_value() for f in fields.all()] == list(answers.values()))
                    check(theme + ": first answer focused", fields.first.evaluate("e=>e===document.activeElement"))
                    check(theme + ": generated review hidden", page.get_by_role("heading", name="一起核对需求").count() == 0)
                    fields.first.fill("修改后的回答")
                    page.evaluate("s=>promptsmithView.applySnapshot(s)", restored)
                    check(theme + ": normal polling preserves edits", fields.first.input_value() == "修改后的回答")
                    fields.first.press("Shift+Enter")
                    check(theme + ": Shift Enter newline", fields.first.input_value() == "修改后的回答\n")
                    before = len(api.calls)
                    fields.nth(1).press("Enter")
                    page.wait_for_function("!document.body.classList.contains('pending')")
                    batch = next(c for c in api.calls[before:] if c["action"] == "answer")
                    check(theme + ": Enter sends whole round", batch["data"]["answers"] == [
                        dict(id="q1", text="修改后的回答\n"), dict(id="q2", text="中文"), dict(id="q3", text="PDF交付")])
                    page.screenshot(path=str(OUT / (theme+"-answers-native.png")))

                    nav = dict(stage="interview", natural="interview", previous="interview", next=None, revisiting=False)
                    restored["navigation"] = nav
                    restored["cards"].insert(0, dict(kind="navigation", key="navigation", title="回看与继续", **nav))
                    restored["buttons"]["back_stage"] = dict(text="返回上一步", enabled=True)
                    page.evaluate("s=>promptsmithView.applySnapshot(s)", restored)
                    fields.nth(1).fill("还没同步的修改")
                    before = len(api.calls)
                    page.get_by_role("button", name="返回上一步", exact=True).click()
                    page.wait_for_function("!document.body.classList.contains('pending')")
                    latest = next(c for c in api.calls[before:] if c["action"] == "navigate")
                    check(theme + ": back carries unflushed inputs", latest["data"]["answer_drafts"]["q2"] == "还没同步的修改")

                    requirements = stage_state(theme, "requirements", "plan", "interview", "plan")
                    requirements["cards"][:0] = [dict(key="history:"+str(i), kind="history_question", text="较长的历史问答\n"*12)
                                                   for i in range(15)]
                    requirements["cards"] += [dict(key="requirements", kind="requirements", title="需求已确认", confirmed=True)]
                    page.evaluate("s=>promptsmithView.applySnapshot(s)", requirements)
                    page.wait_for_timeout(80)
                    box = page.get_by_role("heading", name="需求已确认", exact=True).bounding_box()
                    viewport = page.locator("#viewport").bounding_box()
                    check(theme + ": requirements start visible", viewport["y"] <= box["y"] < viewport["y"]+180)

                    plan = stage_state(theme, "plan", "skills", "requirements", "skills")
                    plan["cards"] += [deepcopy(c) for c in STATES["plan"]["cards"] if c["kind"] == "plan"]
                    plan["buttons"].update(confirm_plan=dict(text="确认方案并生成提示词", enabled=True),
                                            find_skills=dict(text="确认方案并查找 Skill", enabled=True))
                    page.evaluate("s=>promptsmithView.applySnapshot(s)", plan)
                    check(theme + ": both confirmation actions restored", all(
                        page.get_by_role("button", name=name, exact=True).is_enabled()
                        for name in ("确认方案并生成提示词", "确认方案并查找 Skill")))
                    check(theme + ": separate key work gate absent", page.get_by_role("button", name="已核对修改后的关键工作").count() == 0)
                    page.screenshot(path=str(OUT / (theme+"-plan-native.png")))
                    before = len(api.calls)
                    page.get_by_role("button", name="继续下一步", exact=True).click()
                    page.wait_for_function("!document.body.classList.contains('pending')")
                    check(theme + ": continue forwards action", any(c["action"] == "button" and c["data"].get("key") == "continue_stage" for c in api.calls[before:]))
                check("only synthetic navigation and answer actions", all(c["action"] in {"navigate", "button", "answer", "drafts"} for c in api.calls))
                check("no automatic PromptSmith logs", not list((Path(isolation)/"PromptSmith/logs").glob("*.log")))
        except Exception as exc:
            errors.append(repr(exc))
        finally:
            window.destroy()

    def timeout():
        errors.append("Native check exceeded 55 seconds")
        window.destroy()
    watchdog = Timer(55, timeout)
    window.events.loaded += loaded
    watchdog.start()
    try:
        webview.start(gui="edgechromium", storage_path=isolation, private_mode=True, http_server=True)
    finally:
        watchdog.cancel()

(OUT / "native-results.json").write_text(json.dumps(dict(checks=checks, errors=errors), ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(dict(checks=checks, errors=errors), ensure_ascii=True))
assert not errors, errors
