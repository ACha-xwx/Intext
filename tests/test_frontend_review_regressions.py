"""Real Chromium DOM, with only the external desktop bridge simulated.

No personal settings, conversations, or model requests are accessed.
"""
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(os.environ.get("PROMPTSMITH_TEST_ASSETS", ROOT / "resources/ui/workspace"))
STATES = json.loads((ROOT / "tests/fixtures/frontend_review.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def browser():
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(channel="chrome", headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    page = browser.new_page(viewport={"width": 1440, "height": 810})
    page.set_default_timeout(4000)
    page.goto((ASSETS / "index.html").as_uri())
    page.evaluate("""() => {
      window.calls=[]; window.pywebview={api:{
        diagnostic:async (...args)=>{calls.push({action:'diagnostic',args});},
        snapshot:async()=>null,
        dispatch:async(action,data)=>{calls.push({action,data});return {ok:true};}
      }};
    }""")
    yield page
    page.close()


def load(view, kind="empty", **changes):
    state = json.loads(json.dumps(STATES[kind]))
    state.update(changes)
    view.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    return state


def settle(page):
    page.wait_for_timeout(450)


def test_busy_integration_can_be_cancelled_from_current_conversation(page):
    state = json.loads(json.dumps(STATES["skills"]))
    state["locked"] = True
    state["buttons"]["cancel_request"] = {"text": "取消本次请求", "enabled": True}
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    cancel = page.get_by_role("button", name="取消本次请求")
    assert cancel.count() == 1
    assert cancel.is_enabled()
    cancel.click()
    page.wait_for_function("calls.some(c=>c.action==='button'&&c.data.key==='cancel_request')")
    assert page.get_by_role("button", name="停止生成", exact=True).is_enabled()


@pytest.mark.parametrize("font", [9, 12, 18])
@pytest.mark.parametrize("collapsed", [False, True])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_small_window_keeps_all_header_actions_visible(page, font, collapsed, theme):
    page.set_viewport_size({"width": 720, "height": 440})
    load(page, font_size=font, theme=theme)
    page.evaluate("v=>promptsmithHistory.setCollapsed(v)", collapsed)
    settle(page)
    for control in page.locator("header button").all():
        box = control.bounding_box()
        assert box and box["x"] >= 0 and box["x"] + box["width"] <= 720
        assert box["y"] + box["height"] <= 440


@pytest.mark.parametrize("category", ["模型", "Skill 搜索", "界面", "会话与导出", "诊断"])
def test_small_settings_can_scroll_and_reach_save(page, category):
    page.set_viewport_size({"width": 720, "height": 440})
    load(page, page="settings", font_size=18)
    page.evaluate("promptsmithHistory.setCollapsed(false)")
    page.get_by_role("tab", name=category, exact=True).click()
    settle(page)
    save = page.get_by_role("button", name="保存设置", exact=True)
    save.scroll_into_view_if_needed()
    box = save.bounding_box()
    assert box and box["y"] >= 0 and box["y"] + box["height"] <= 440
    assert page.locator(".settings-scroll").bounding_box()["height"] >= 80
    save.click()
    page.wait_for_function("calls.some(c=>c.action==='settings_save')")


@pytest.mark.parametrize("font", [9, 12, 18])
@pytest.mark.parametrize("collapsed", [False, True])
def test_picker_bounds_follow_content_and_window_resize(page, font, collapsed):
    page.set_viewport_size({"width": 720, "height": 440})
    load(page, font_size=font)
    page.evaluate("v=>promptsmithHistory.setCollapsed(v)", collapsed)
    settle(page)
    page.locator("#model-button").click()
    settle(page)
    for size in [(720, 440), (800, 500), (720, 440)]:
        page.set_viewport_size({"width": size[0], "height": size[1]})
        settle(page)
        box = page.locator(".picker").bounding_box()
        assert box and box["x"] >= 0 and box["y"] >= 0
        assert box["x"] + box["width"] <= size[0]
        assert box["y"] + box["height"] <= size[1]
        assert page.locator(".picker-search input").bounding_box()["y"] >= 0


@pytest.mark.parametrize("trigger", ["#model-button", "[data-panel=summary]"])
def test_dialogs_have_a_meaningful_accessible_name(page, trigger):
    load(page, "plan")
    page.locator(trigger).click()
    settle(page)
    dialog = page.get_by_role("dialog")
    assert dialog.count() == 1
    assert dialog.get_attribute("aria-label") or dialog.get_attribute("aria-labelledby")


@pytest.mark.parametrize("trigger", ["#file-button", "#depth-button", "#category-button"])
def test_choice_popups_use_named_menu_semantics(page, trigger):
    load(page)
    page.locator(trigger).click()
    settle(page)
    menu = page.get_by_role("menu")
    assert menu.count() == 1
    assert menu.get_attribute("aria-label")
    assert menu.get_by_role("menuitem").count() >= 2


@pytest.mark.parametrize("trigger", ["#model-button", "#file-button", "#depth-button", "#category-button", "[data-panel=summary]"])
def test_popup_enters_focus_and_escape_returns_to_trigger(page, trigger):
    load(page, "plan")
    control = page.locator(trigger)
    control.focus()
    control.click()
    settle(page)
    assert page.locator(".popup").evaluate("e=>e.contains(document.activeElement)")
    assert control.get_attribute("aria-expanded") == "true"
    page.keyboard.press("Escape")
    settle(page)
    assert control.evaluate("e=>e===document.activeElement")
    assert control.get_attribute("aria-expanded") == "false"


def test_history_dialog_returns_to_recreated_history_trigger(page):
    state = load(page)
    more = page.locator(".history-more").first
    more.focus()
    more.click()
    page.get_by_role("menuitem", name="重命名").click()
    state["history"]["entries"][0]["title"] = "后台刷新标题"
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    page.keyboard.press("Escape")
    assert page.locator(".history-more").first.evaluate("e=>e===document.activeElement")


def test_requirement_rows_can_be_selected_with_keyboard(page):
    state = load(page, "requirements")
    settle(page)
    options = page.get_by_role("button", name="选择需求", exact=False)
    assert options.count() == len(state["requirement_rows"])
    options.nth(1).focus()
    page.keyboard.press("Enter")
    assert page.locator(".detail").inner_text() == state["requirement_rows"][1]["text"]
    page.wait_for_function("calls.some(c=>c.action==='requirement_row'&&c.data.id==='r:r2')")
    assert options.nth(1).evaluate("e=>e===document.activeElement")


def test_collapsed_thought_is_excluded_from_tab_and_returns_internal_focus(page):
    load(page, "interview")
    header = page.locator(".trace>button").first
    header.click()
    settle(page)
    thought = page.locator(".thought").first
    thought.focus()
    # A pointer activation may keep the old focus; collapsing must recover it.
    header.evaluate("e=>e.click()")
    assert header.evaluate("e=>e===document.activeElement")
    page.keyboard.press("Tab")
    assert not page.evaluate("!!document.activeElement.closest('.trace .reveal:not(.open)')")
    header.click()
    settle(page)
    nested = page.locator(".trace-body>button").first
    thought.focus()
    nested.evaluate("e=>e.click()")
    assert nested.evaluate("e=>e===document.activeElement")
    page.keyboard.press("Tab")
    assert not page.evaluate("!!document.activeElement.closest('.thoughtReveal,.trace .reveal:not(.open)')")


@pytest.mark.parametrize("kind", ["model", "search", "rename"])
def test_composition_confirmation_does_not_trigger_an_action(page, kind):
    load(page)
    if kind == "model":
        page.locator("#model-button").click()
        field = page.get_by_role("textbox", name="搜索模型")
        action = "model"
    elif kind == "search":
        page.locator("#history-search").click()
        field = page.get_by_role("searchbox", name="搜索会话名称")
        action = "history_open"
    else:
        page.evaluate("promptsmithHistory.setCollapsed(false)")
        settle(page)
        page.locator(".history-row").first.hover()
        page.locator(".history-more").first.click()
        page.get_by_role("menuitem", name="重命名").click()
        field = page.get_by_role("textbox", name="会话名称")
        action = "history_rename"
    settle(page)
    field.dispatch_event("keydown", {"key": "Enter", "isComposing": True, "keyCode": 229})
    page.wait_for_timeout(150)
    assert not page.evaluate("a=>calls.some(c=>c.action===a)", action)
    field.press("Enter")
    page.wait_for_function("a=>calls.some(c=>c.action===a)", arg=action)


def test_settings_categories_support_roving_tab_and_arrows_without_losing_draft(page):
    load(page, page="settings")
    field = page.locator("#settings-field-connection-model")
    field.fill("草稿-model")
    tabs = page.get_by_role("tab")
    tabs.first.focus()
    page.keyboard.press("ArrowRight")
    assert page.get_by_role("tab", selected=True).inner_text() == "Skill 搜索"
    assert tabs.evaluate_all("ts=>ts.filter(t=>t.tabIndex===0).length") == 1
    page.keyboard.press("End")
    assert page.get_by_role("tab", selected=True).inner_text() == "诊断"
    page.keyboard.press("Home")
    assert field.input_value() == "草稿-model"
    page.keyboard.press("ArrowLeft")
    assert page.get_by_role("tab", selected=True).inner_text() == "诊断"


def test_debug_recovery_clears_sync_error_but_retains_copy_error(page):
    page.goto((ASSETS / "debug.html").as_uri())
    page.evaluate("""() => {
      window.failSync=true;window.pywebview={api:{diagnostic:async()=>true,
        snapshot:async()=>{if(failSync)throw new Error('offline');return {
          preferences:{font_size:12},preference_revision:1,sequence:0,entries:[],cached:0,directory_exists:false
        };}
      }};
    }""")
    page.evaluate("promptsmithDebug.poll()")
    assert page.locator("#debug-error").is_visible()
    page.evaluate("failSync=false;promptsmithDebug.poll()")
    assert page.locator("#debug-error").is_hidden()
    page.evaluate("Object.defineProperty(navigator,'clipboard',{value:{writeText:async()=>{throw new Error('denied');}}})")
    page.locator("#copy").click()
    assert page.locator("#debug-error").is_visible()
    page.evaluate("promptsmithDebug.poll()")
    assert "复制" in page.locator("#debug-error").inner_text()


def test_rejected_requirement_selection_keeps_backend_selection_visible(page):
    state = load(page, "requirements", requirement_selection=["r:r1"])
    settle(page)
    page.evaluate("pywebview.api.dispatch=async()=>({ok:false,error:'内容已变化，请刷新'})")
    page.get_by_role("button", name="选择需求").nth(1).click()
    page.wait_for_timeout(150)
    assert page.locator(".detail").inner_text() == state["requirement_rows"][0]["text"]


def test_pending_panel_disables_selection_until_backend_is_ready(page):
    load(page, "requirements", requirement_selection=["r:r1"])
    page.evaluate("()=>{pywebview.api.dispatch=action=>action==='requirement_row'?new Promise(resolve=>window.resolvePanel=resolve):Promise.resolve({ok:true});}")
    page.get_by_role("button", name="选择需求").first.click()
    settle(page)
    assert page.get_by_role("button", name="选择需求").first.is_disabled()
    page.evaluate("resolvePanel({ok:true})")


@pytest.mark.parametrize("trigger", ["#file-button", "#depth-button", "#category-button"])
def test_menus_support_arrows_home_end_and_tab_exit(page, trigger):
    load(page)
    page.locator(trigger).click()
    settle(page)
    items = page.get_by_role("menuitem")
    page.keyboard.press("ArrowDown")
    assert items.nth(1).evaluate("e=>e===document.activeElement")
    assert items.evaluate_all("is=>is.filter(i=>i.tabIndex===0).length") == 1
    page.keyboard.press("End")
    assert items.last.evaluate("e=>e===document.activeElement")
    page.keyboard.press("Home")
    assert items.first.evaluate("e=>e===document.activeElement")
    page.keyboard.press("Tab")
    assert not page.evaluate("!!document.activeElement.closest('.popup')")


def test_busy_cancel_keeps_focus_across_progress_snapshots(page):
    state = load(page, "skills", locked=True)
    state["buttons"]["cancel_request"] = {"text": "取消本次请求", "enabled": True}
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    cancel = page.get_by_role("button", name="取消本次请求")
    cancel.focus()
    state["status"] = "正在处理下一段"
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    assert cancel.evaluate("e=>e===document.activeElement")
    page.keyboard.press("Enter")
    page.wait_for_function("calls.some(c=>c.action==='button'&&c.data.key==='cancel_request')")


def test_empty_page_keeps_recovery_area_hidden(page):
    load(page)
    assert page.locator("#recovery").is_hidden()


def test_small_settings_retains_draft_with_long_error_and_can_save(page):
    page.set_viewport_size({"width": 720, "height": 440})
    load(page, page="settings", font_size=18)
    field = page.locator("#settings-field-connection-model")
    field.fill("保留的模型草稿")
    page.evaluate("document.querySelector('.settings-error').textContent='请更换目录后重试。'.repeat(60)")
    page.get_by_role("tab", name="诊断", exact=True).click()
    page.get_by_role("button", name="保存设置").click()
    page.wait_for_function("calls.some(c=>c.action==='settings_save'&&c.data.connection.model==='保留的模型草稿')")
    page.get_by_role("tab", name="模型", exact=True).click()
    assert field.input_value() == "保留的模型草稿"
