"""Actual WebView2 feedback acceptance; synthetic workspace and disposable logs.

No personal settings, sessions, paid API calls, or automatic log files are used.
The backend controller contract is tested separately in test_notifications.py.
"""
from copy import deepcopy
import json
import logging
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "local_artifacts/notifications_20261013"
OUT.mkdir(parents=True, exist_ok=True)
result = {"checks": []}


def check(name, value):
    result["checks"].append(dict(name=name, passed=bool(value)))
    print(json.dumps(result["checks"][-1], ensure_ascii=True), flush=True)
    assert value, name


with tempfile.TemporaryDirectory(prefix="promptsmith-notifications-") as isolation:
    os.environ["LOCALAPPDATA"] = isolation
    for name in ("PROMPTSMITH_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY"):
        os.environ.pop(name, None)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    # Stable animation timing in this disposable two-window harness, even if
    # another desktop app gains focus during acceptance. Production is unchanged.
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
        f"--remote-debugging-port={port} --disable-background-timer-throttling "
        "--disable-renderer-backgrounding --disable-backgrounding-occluded-windows"
    )
    import webview
    from playwright.sync_api import sync_playwright, expect
    from promptsmith.preferences import defaults
    from promptsmith.runtime_log import RuntimeLog
    from promptsmith.web_debug import DebugApi, WebDebugConsole

    logs = RuntimeLog(Path(isolation) / "PromptSmith/logs")
    logs.register_secret("disposable-notification-secret")
    state = json.loads((ROOT / "tests/fixtures/frontend_review.json").read_text(encoding="utf-8"))["empty"]

    class FixtureApi:
        def __init__(self):
            self.lock = threading.Lock()
            self.state = state
            self.version = 1

        def snapshot(self, _since=0):
            with self.lock:
                return dict(version=self.version, state=deepcopy(self.state))

        def dispatch(self, action, _data, _stamp):
            if action == "editor_save":
                with self.lock:
                    self.state["editor"]["error"] = "模拟保存失败，草稿保留。"
                    self.version += 1
                return dict(ok=False, error="模拟保存失败，草稿保留。")
            if action == "settings_autosave":
                return dict(ok=False, error_kind="persistence", error="模拟磁盘写入失败。")
            return dict(ok=True)

        def diagnostic(self, level, event, detail):
            logs.record("promptsmith.web_workspace", {"error":40,"warn":30,"info":20}.get(level,10),
                        f"Browser {event}: {detail}")
            return True

        def update(self, **changes):
            with self.lock:
                self.state.update(changes)
                self.version += 1

    api = FixtureApi()
    console = WebDebugConsole(logs, None)
    console.apply_preferences(defaults())
    main = webview.create_window("PromptSmith · 通知隔离验收", str(ROOT / "resources/ui/workspace/index.html"),
                                 js_api=api, width=1440, height=810, min_size=(480, 320))
    debug = webview.create_window("PromptSmith · Debug 通知隔离验收", str(ROOT / "resources/ui/workspace/debug.html"),
                                  js_api=DebugApi(console), width=800, height=540, min_size=(600, 320))

    def loaded():
        try:
            with sync_playwright() as runtime:
                browser = runtime.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                page = next(p for c in browser.contexts for p in c.pages if "index.html" in p.url)
                dpage = next(p for c in browser.contexts for p in c.pages if "debug.html" in p.url)
                page.set_default_timeout(10000)
                dpage.set_default_timeout(10000)
                expect(page.locator("#message")).to_be_visible()
                page.wait_for_function("state!==null")
                def dismiss_all(view):
                    view.evaluate("document.querySelectorAll('.notification-close').forEach(e=>e.click())")
                    expect(view.locator(".notification-card")).to_have_count(0)

                for theme, size in (("light", (1440,810)), ("dark", (600,460))):
                    api.update(theme=theme)
                    main.resize(*size)
                    page.bring_to_front()
                    page.wait_for_function("t=>document.documentElement.dataset.theme===t", arg=theme)
                    before = page.locator("#message").bounding_box()
                    page.evaluate("""()=>{
                      for(const variant of ['success','info','warning','error'])
                        promptsmithNotifications.show('中文消息🧪：'+variant,{variant,title:{success:'操作成功',info:'消息提示',warning:'请注意',error:'操作未完成'}[variant]});
                    }""")
                    expect(page.locator(".notification-card")).to_have_count(4)
                    page.wait_for_timeout(250)
                    check(theme+" four types in top right", page.locator(".notification-card").first.evaluate("e=>{const r=e.getBoundingClientRect();return r.top<30&&r.right<=innerWidth&&r.left>=0}") and page.locator(".notification-success .notification-icon circle").count()==1)
                    check(theme+" overlay preserves layout", page.locator("#message").bounding_box()==before)
                    check(theme+" countdown bars in all cards", page.locator(".notification-countdown").count()==4 and page.locator(".notification-countdown").first.evaluate("e=>{const s=getComputedStyle(e);return s.animationDuration==='5s'&&s.animationTimingFunction==='linear'}"))
                    page.screenshot(path=str(OUT/(theme+"-notifications.png")))
                    first = page.locator('[data-key="'+page.locator('.notification-card').first.get_attribute('data-key')+'"]')
                    following = page.locator('[data-key="'+page.locator('.notification-card').nth(1).get_attribute('data-key')+'"]')
                    target = first.bounding_box()['y']
                    start = following.bounding_box()['y']
                    first.get_by_role('button', name='关闭通知', exact=True).click()
                    page.wait_for_function("k=>![...document.querySelectorAll('.notification-card')].some(e=>e.dataset.key===k)", arg=first.get_attribute('data-key'), polling=5)
                    position = following.bounding_box()['y']
                    check(theme+" following notification moves continuously", target + 1 < position <= start + 1)
                    check(theme+" upward shift has no temporary scrollbar", page.locator('#notifications').evaluate("e=>e.scrollHeight<=e.clientHeight&&e.scrollWidth<=e.clientWidth"))
                    page.wait_for_timeout(300)
                    check(theme+" following notification reaches empty slot", abs(following.bounding_box()['y']-target)<1)
                    dismiss_all(page)

                page.evaluate("""()=>{
                  window.nativeNoticeStart=performance.now();
                  promptsmithNotifications.sync('native-countdown','第一张独立倒计时');
                }""")
                page.wait_for_timeout(1200)
                fraction = page.locator('.notification-countdown').evaluate("e=>e.getBoundingClientRect().width/e.parentElement.clientWidth")
                check("countdown visibly decreases evenly", .65 < fraction < .85)
                page.evaluate("promptsmithNotifications.show('第二张独立倒计时',{key:'native-second'})")
                page.wait_for_function("document.querySelector('[data-key=native-countdown]')?.classList.contains('closing')", timeout=6000, polling=10)
                elapsed = page.evaluate("performance.now()-nativeNoticeStart")
                check("first closes after five seconds while second stays", 4950 <= elapsed <= 5800 and page.locator('[data-key=native-second]:not(.closing)').count()==1)
                check("exit frame cannot show a horizontal scrollbar", page.locator('#notifications').evaluate("e=>getComputedStyle(e).overflowX==='hidden'"))
                expect(page.locator('[data-key=native-countdown]')).to_have_count(0)
                page.evaluate("promptsmithNotifications.sync('native-countdown','第一张独立倒计时')")
                check("auto closed snapshot does not replay", page.locator('[data-key=native-countdown]').count()==0)
                expect(page.locator('[data-key=native-second]')).to_have_count(0, timeout=2500)

                page.bring_to_front()
                page.evaluate("promptsmithNotifications.show('替换前',{key:'native-replacement'})")
                page.wait_for_timeout(2000)
                page.evaluate("window.nativeReplacementStart=performance.now();promptsmithNotifications.show('替换后',{key:'native-replacement'})")
                page.wait_for_timeout(3200)
                check("replacement starts a new five seconds", page.locator('[data-key=native-replacement]:not(.closing)').count()==1 and page.locator('.notification-body').inner_text()=='替换后')
                page.wait_for_function("document.querySelector('[data-key=native-replacement]')?.classList.contains('closing')", timeout=6000, polling=10)
                elapsed = page.evaluate("performance.now()-nativeReplacementStart")
                check("replacement expires five seconds after replacement", 4950 <= elapsed <= 5800)
                expect(page.locator('[data-key=native-replacement]')).to_have_count(0)

                page.evaluate("""()=>{window.nativeModalStart=performance.now();
                  promptsmithNotifications.show('模态迁移继续计时',{key:'native-modal-countdown'});}""")
                page.wait_for_timeout(1000)
                previous = page.locator('.notification-countdown').evaluate("e=>e.getBoundingClientRect().width/e.parentElement.clientWidth")
                continuous = True
                for action in (
                    "const d=document.createElement('dialog');d.id='native-modal';d.innerHTML='<button>继续编辑</button>';document.body.append(d);d.showModal()",
                    "document.querySelector('#native-modal').close()",
                    "document.querySelector('#native-modal').showModal()",
                    "document.querySelector('#native-modal').remove()",
                ):
                    page.evaluate('()=>{' + action + '}')
                    page.wait_for_timeout(100)
                    current = page.locator('.notification-countdown').evaluate("e=>e.getBoundingClientRect().width/e.parentElement.clientWidth")
                    continuous = continuous and current <= previous + .015
                    previous = current
                check("modal open close and removal never refill countdown", continuous)
                page.wait_for_function("document.querySelector('[data-key=native-modal-countdown]')?.classList.contains('closing')", timeout=5000, polling=10)
                elapsed = page.evaluate("performance.now()-nativeModalStart")
                check("modal rehost preserves original five second lifetime", 4950 <= elapsed <= 5800)
                expect(page.locator('[data-key=native-modal-countdown]')).to_have_count(0)

                api.update(notifications=[dict(id=1,level="warning",body="可关闭的目录提醒。",key="native-fixture")])
                expect(page.locator(".notification-card")).to_have_count(1)
                dismiss_all(page)
                page.evaluate("poll()")
                page.wait_for_timeout(250)
                check("closed snapshot notification does not return", page.locator(".notification-card").count()==0)
                page.evaluate("promptsmithNotifications.show('中文🧪<img src=x onerror=alert(1)>'.repeat(100),{variant:'error'})")
                check("long feedback is text only and wraps", page.locator(".notification-card img").count()==0 and page.locator(".notification-body").evaluate("e=>e.scrollWidth<=e.clientWidth+1"))
                dismiss_all(page)

                api.update(editor=dict(id="native-editor",kind="requirement",title="修改需求",error="",fields=[dict(key="text",label="需求内容",value="原需求",required=True)]))
                expect(page.get_by_role("dialog",name="修改需求")).to_be_visible()
                field = page.get_by_label("需求内容",exact=True)
                field.fill("未提交草稿👩🏽‍💻")
                page.locator(".editor-save").click()
                expect(page.locator(".notification-error")).to_have_count(1)
                check("failed editor save keeps draft and enabled controls", field.input_value()=="未提交草稿👩🏽‍💻" and page.locator(".editor-save").is_enabled())
                reachable = False
                for _ in range(8):
                    page.keyboard.press("Tab")
                    if page.evaluate("document.activeElement.getAttribute('aria-label')==='关闭通知'"):
                        reachable = True
                        page.keyboard.press("Enter")
                        break
                check("notification keyboard close reachable inside modal", reachable)
                check("focus stays inside editor after close", page.evaluate("Boolean(document.activeElement.closest('dialog[open]'))"))
                api.update(editor=None,page="settings")
                expect(page.locator(".settings-card")).to_be_visible()
                page.get_by_label("模型 ID",exact=True).fill("retained-model")
                expect(page.locator(".notification-error").filter(has_text="模拟磁盘写入失败")).to_have_count(1)
                expect(page.get_by_role("button",name="重试自动保存",exact=True)).to_be_visible()
                check("settings failure keeps draft and retry", page.get_by_label("模型 ID",exact=True).input_value()=="retained-model" and page.get_by_role("button",name="重试自动保存",exact=True).is_visible())
                dismiss_all(page)

                try:
                    try:
                        raise ValueError("底层原因 disposable-notification-secret")
                    except ValueError as exc:
                        raise RuntimeError("完整异常🧪") from exc
                except RuntimeError:
                    logs.record("promptsmith.api",logging.ERROR,"隔离错误",exc_info=sys.exc_info())
                expect(dpage.locator(".log-error").filter(has_text="完整异常")).to_be_visible()
                check("Debug log entries do not become notifications", dpage.locator(".notification-card").count()==0)
                check("no log files until explicit save", not logs.directory.exists())
                dpage.get_by_role("button",name="保存日志",exact=True).click()
                expect(dpage.locator(".notification-success")).to_be_visible()
                content = logs.path.read_text(encoding="utf-8")
                check("manual save notification and full redacted exception", "已保存" in dpage.locator(".notification-body").inner_text() and all(x in content for x in ("ValueError","RuntimeError","direct cause","[REDACTED]")) and "disposable-notification-secret" not in content)
                dismiss_all(dpage)
                dpage.evaluate("promptsmithDebug.poll()")
                dpage.wait_for_timeout(200)
                check("closed saved log notification does not return", dpage.locator(".notification-card").count()==0)
                console.apply_preferences(dict(defaults(),composer_theme="dark"))
                dpage.wait_for_function("document.documentElement.dataset.theme==='dark'")
                dpage.get_by_role("button",name="保存日志",exact=True).click()
                expect(dpage.locator(".notification-success")).to_be_visible()
                dpage.screenshot(path=str(OUT/"dark-debug-notifications.png"))
                result["user_agent"] = page.evaluate("navigator.userAgent")
        except Exception as exc:
            result["error"] = repr(exc)
            try:
                result["notification_state"] = page.evaluate("""()=>({now:performance.now(),replacementStart:window.nativeReplacementStart,visibility:document.visibilityState,
                  cards:[...document.querySelectorAll('.notification-card')].map(e=>({key:e.dataset.key,classes:e.className,bar:getComputedStyle(e.querySelector('.notification-countdown')).transform}))})""")
                page.screenshot(path=str(OUT/"failure.png"))
            except Exception as inspection_error:
                result["inspection_error"] = repr(inspection_error)
        finally:
            # Also drain on a failed assertion, before native controls close.
            try:
                for view in (page, dpage):
                    view.evaluate("window.pywebview=null")
                    view.wait_for_function("!polling")
                page.wait_for_timeout(500)
                browser.close()
            except Exception:
                pass
            console.close()
            debug.destroy()
            main.destroy()

    main.events.loaded += loaded
    webview.start(gui="edgechromium")
(OUT/"native-results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
assert not result.get("error"), result.get("error")
