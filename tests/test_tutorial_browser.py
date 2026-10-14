"""Guided actions on the production DOM; external desktop API is simulated."""
import pytest
from playwright.sync_api import expect
from tests.test_frontend_review_regressions import browser, page, load


def test_tutorial_requires_real_settings_actions_before_advancing(page):
    load(page, tutorial_status="not_started")
    guide = page.get_by_role("dialog", name="新手入门")
    expect(guide).to_be_visible()
    next_step = guide.get_by_role("button", name="下一步", exact=True)
    expect(next_step).to_be_disabled()
    # The actual application remains operable, unlike a modal reading carousel.
    page.get_by_role("button", name="设置", exact=True).click()
    page.wait_for_function("calls.some(c=>c.action==='settings')")
    current = load(page, page="settings", tutorial_status="not_started")
    expect(next_step).to_be_enabled()
    next_step.click()
    expect(guide.get_by_role("heading", name="配置模型服务", exact=True)).to_be_visible()
    current["settings"]["has_key"] = False
    page.evaluate("s=>promptsmithView.applySnapshot(s)", current)
    expect(next_step).to_be_disabled()
    current["settings"]["has_key"] = True
    current["settings"]["connection"].update(provider="DeepSeek", model_provider="DeepSeek", base_url="https://api.deepseek.com")
    page.evaluate("s=>promptsmithView.applySnapshot(s)", current)
    expect(next_step).to_be_enabled()
    next_step.click()
    expect(guide.get_by_role("heading", name="获取可用模型", exact=True)).to_be_visible()
    current["settings"]["available_models"] = []
    page.evaluate("s=>promptsmithView.applySnapshot(s)", current)
    expect(next_step).to_be_disabled()
    current["settings"]["available_models"] = ["deepseek-flash"]
    page.evaluate("s=>promptsmithView.applySnapshot(s)", current)
    expect(next_step).to_be_enabled()
    assert not page.evaluate("calls.some(c=>c.action==='tutorial_finish')")


def configured_step(page, **changes):
    current = load(page, page="settings", tutorial_status="not_started", **changes)
    current["settings"]["has_key"] = True
    current["settings"]["confirmed"] = True
    current["settings"]["connection"].update(provider="DeepSeek", model_provider="DeepSeek", base_url="https://api.deepseek.com", model="deepseek-flash")
    current["settings"]["available_models"] = ["deepseek-flash"]
    page.evaluate("s=>promptsmithView.applySnapshot(s)", current)
    return current


def test_final_step_can_complete_without_sending_a_goal(page):
    current = configured_step(page)
    guide = page.get_by_role("dialog", name="新手入门")
    for _ in range(4):
        guide.get_by_role("button", name="下一步", exact=True).click()
    finish = guide.get_by_role("button", name="完成", exact=True)
    expect(finish).to_be_enabled()
    assert guide.get_by_role("button", name="跳过教程").count() == 0
    page.get_by_role("button", name="返回工作区", exact=True).click()
    current.update(page="workspace", settings=None)
    page.evaluate("s=>promptsmithView.applySnapshot(s)", current)
    expect(finish).to_be_enabled()
    assert page.evaluate("calls.filter(c=>c.action==='send').length") == 0
    assert not page.evaluate("calls.some(c=>c.action==='tutorial_finish')")
    finish.click()
    expect(guide).to_have_count(0)
    assert page.evaluate("calls.filter(c=>c.action==='tutorial_finish').length") == 1


def test_close_does_not_mark_complete_and_first_page_can_skip(page):
    current = load(page, tutorial_status="not_started", drafts={"message":"未发送目标"})
    guide = page.get_by_role("dialog", name="新手入门")
    guide.get_by_role("button", name="关闭教程", exact=True).click()
    expect(guide).to_have_count(0)
    assert not page.evaluate("calls.some(c=>c.action.startsWith('tutorial_'))")
    page.evaluate("s=>promptsmithView.applySnapshot(s)", current)
    expect(guide).to_have_count(0)
    page.evaluate("promptsmithTutorial.open('settings')")
    guide.get_by_role("button", name="跳过教程", exact=True).click()
    expect(guide).to_have_count(0)
    assert page.evaluate("calls.filter(c=>c.action==='tutorial_skip').length") == 1
    assert not page.evaluate("calls.some(c=>c.action==='tutorial_finish')")
    expect(page.locator("#message")).to_have_value("未发送目标")


def test_skipped_or_completed_startup_does_not_open_but_settings_replays(page):
    load(page, page="settings", tutorial_status="skipped")
    guide = page.get_by_role("dialog", name="新手入门")
    expect(guide).to_have_count(0)
    page.get_by_role("tab", name="界面", exact=True).click()
    replay = page.get_by_role("button", name="重新查看教程", exact=True)
    replay.click()
    expect(guide).to_be_visible()
    guide.get_by_role("button", name="关闭教程", exact=True).click()
    expect(guide).to_have_count(0)
    assert replay.evaluate("e=>e===document.activeElement")


def test_replaying_from_interface_tab_shows_actual_model_controls(page):
    configured_step(page)
    guide = page.get_by_role("dialog", name="新手入门")
    guide.get_by_role("button", name="关闭教程", exact=True).click()
    expect(guide).to_have_count(0)
    page.get_by_role("tab", name="界面", exact=True).click()
    page.get_by_role("button", name="重新查看教程", exact=True).click()
    guide.get_by_role("button", name="下一步", exact=True).click()
    expect(page.get_by_label("API Key", exact=True)).to_be_visible()
    expect(page.get_by_role("tab", name="模型", exact=True)).to_have_attribute("aria-selected", "true")
    assert not page.evaluate("calls.some(c=>['settings_test','send'].includes(c.action))")


@pytest.mark.parametrize("theme,width,height", [("light",1440,810),("dark",720,500),("light",480,440)])
def test_guide_is_responsive_and_never_blocks_target_actions(page, theme, width, height):
    page.set_viewport_size({"width":width,"height":height})
    configured_step(page, theme=theme)
    guide = page.get_by_role("dialog", name="新手入门")
    page.wait_for_timeout(300)
    box = guide.bounding_box()
    assert box["x"] >= 0 and box["y"] >= 0 and box["x"]+box["width"] <= width and box["y"]+box["height"] <= height
    assert guide.evaluate("e=>e.scrollWidth<=e.clientWidth+1")
    guide.get_by_role("button", name="下一步", exact=True).click()
    assert guide.locator(".tutorial-track").evaluate("e=>e.getAnimations().some(a=>a.playState==='running')")
    assert guide.locator(".tutorial-progress>div").evaluate("e=>e.getAnimations().some(a=>a.playState==='running')")
    key = page.get_by_label("API Key", exact=True)
    key.scroll_into_view_if_needed()
    key.click()
    assert key.evaluate("e=>e===document.activeElement")
    assert guide.get_by_role("heading").count() == 1


@pytest.mark.parametrize("width,height", [(720,500),(480,440)])
def test_small_guide_prioritizes_current_heading_and_instructions(page, width, height):
    page.set_viewport_size({"width":width,"height":height})
    configured_step(page)
    guide = page.get_by_role("dialog", name="新手入门")
    guide.get_by_role("button", name="下一步", exact=True).click()
    page.wait_for_timeout(350)
    clip = guide.locator(".tutorial-clip").bounding_box()
    title = guide.get_by_role("heading", name="配置模型服务", exact=True).bounding_box()
    text = guide.locator('.tutorial-slide[aria-hidden="false"] p').bounding_box()
    assert title["y"] >= clip["y"] and title["y"]+title["height"] <= clip["y"]+clip["height"]
    assert text["y"] + 32 <= clip["y"]+clip["height"]


def test_skip_save_failure_is_visible_and_retryable(page):
    page.evaluate("""() => {pywebview.api.dispatch=async(action,data)=>{
      calls.push({action,data});return {ok:calls.filter(c=>c.action==='tutorial_skip').length>1,error:'simulated write failure'};
    }}""")
    load(page, tutorial_status="not_started")
    guide = page.get_by_role("dialog", name="新手入门")
    guide.get_by_role("button", name="跳过教程", exact=True).click()
    expect(page.get_by_text("教程状态未能保存，请再试一次。", exact=True)).to_be_visible()
    expect(guide).to_be_visible()
    guide.get_by_role("button", name="跳过教程", exact=True).click()
    expect(guide).to_have_count(0)


def test_guide_reduced_motion_and_escape_keep_incomplete_state(page):
    page.emulate_media(reduced_motion="reduce")
    configured_step(page)
    guide = page.get_by_role("dialog", name="新手入门")
    guide.get_by_role("button", name="下一步", exact=True).click()
    assert guide.locator(".tutorial-track").evaluate("e=>getComputedStyle(e).transitionDuration") == "0s"
    guide.get_by_role("button", name="关闭教程", exact=True).focus()
    page.keyboard.press("Escape")
    expect(guide).to_have_count(0)
    assert not page.evaluate("calls.some(c=>c.action.startsWith('tutorial_'))")


def test_last_step_on_small_window_can_send_a_long_goal(page):
    page.set_viewport_size({"width":480,"height":440})
    current = configured_step(page)
    guide = page.get_by_role("dialog", name="新手入门")
    for _ in range(4):
        guide.get_by_role("button", name="下一步", exact=True).click()
    page.get_by_role("button", name="返回工作区", exact=True).click()
    current.update(page="workspace", settings=None)
    page.evaluate("s=>promptsmithView.applySnapshot(s)", current)
    message = page.locator("#message")
    message.fill("为比赛项目写技术文档\n" * 10)
    message.scroll_into_view_if_needed()
    message.click()
    send = page.locator("#send")
    send.scroll_into_view_if_needed()
    assert send.bounding_box()["y"] + send.bounding_box()["height"] <= guide.bounding_box()["y"]
    send.click(timeout=2000)
    expect(guide.get_by_role("button", name="完成", exact=True)).to_be_enabled()


@pytest.mark.parametrize("operation", ["configure", "model", "provider"])
def test_last_autosave_or_provider_response_unlocks_without_later_snapshot(page, operation):
    current = configured_step(page)
    if operation in {"configure", "provider"}:
        current["settings"]["has_key"] = False
    else:
        current["settings"]["confirmed"] = False
        current["settings"]["connection"]["model"] = ""
    page.evaluate("s=>promptsmithView.applySnapshot(s)", current)
    guide = page.get_by_role("dialog", name="新手入门")
    next_step = guide.get_by_role("button", name="下一步", exact=True)
    for _ in range(3 if operation == "model" else 1):
        next_step.click()
    expect(next_step).to_be_disabled()
    # The desktop publishes the final saved snapshot while its command is
    # finishing, then no further changes. This mirrors the production race.
    page.evaluate("""s=>{
      window.savedSnapshot=s;window.releaseTutorialSave=null;window.lastSnapshot=null;
      pywebview.api.dispatch=async(action,data)=>{
        calls.push({action,data});
        if(!['settings_autosave','settings_provider'].includes(action))return {ok:true};
        await new Promise(resolve=>releaseTutorialSave=resolve);
        savedSnapshot.settings={...savedSnapshot.settings,has_key:true,confirmed:true,
          connection:{...data.connection,...(data.target?{provider:data.target,model_provider:data.target}: {})},
          values:data.values,revision:'tutorial-saved'};
        lastSnapshot={version:2,state:savedSnapshot};
        return {ok:true,data:{settings:savedSnapshot.settings}};
      };
      pywebview.api.snapshot=async()=>{const result=lastSnapshot;lastSnapshot=null;return result;};
    }""", current)
    if operation == "configure":
        page.get_by_label("API Key", exact=True).fill("disposable-guide-key")
    elif operation == "model":
        page.get_by_label("模型 ID", exact=True).click()
        page.get_by_role("option", name="deepseek-flash", exact=True).click()
    else:
        page.get_by_label("服务名称", exact=True).click()
        page.get_by_role("listbox", name="服务名称预设").get_by_role("option", name="OpenAI", exact=True).click()
    page.wait_for_function("releaseTutorialSave!==null")
    expect(next_step).to_be_disabled()
    page.evaluate("releaseTutorialSave()")
    page.wait_for_function("!promptsmithSettings.saving&&!promptsmithSettings.switching&&!inFlight")
    expect(next_step).to_be_enabled()
    assert page.evaluate("calls.filter(c=>['settings_autosave','settings_provider'].includes(c.action)).length") == 1


def test_final_step_remains_optional_after_rejected_send_or_session_change(page):
    current = configured_step(page)
    guide = page.get_by_role("dialog", name="新手入门")
    for _ in range(4):
        guide.get_by_role("button", name="下一步", exact=True).click()
    current.update(page="workspace", settings=None)
    page.evaluate("s=>promptsmithView.applySnapshot(s)", current)
    finish = guide.get_by_role("button", name="完成", exact=True)
    page.evaluate("""()=>{pywebview.api.dispatch=async(action,data)=>{
      calls.push({action,data});return {ok:action!=='send',error:'simulated rejected goal'};
    }}""")
    page.locator("#message").fill("我的第一个目标")
    page.locator("#send").click()
    expect(page.get_by_text("simulated rejected goal", exact=True)).to_be_visible()
    expect(finish).to_be_enabled()
    page.evaluate("""()=>{pywebview.api.dispatch=async(action,data)=>{
      calls.push({action,data});return {ok:true};
    }}""")
    page.locator("#send").click()
    expect(finish).to_be_enabled()
    current["session"] = "another-tutorial-session"
    page.evaluate("s=>promptsmithView.applySnapshot(s)", current)
    expect(finish).to_be_enabled()
    assert not page.evaluate("calls.some(c=>c.action==='tutorial_finish')")


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_tutorial_dims_only_surroundings_and_does_not_block_settings_click(page, theme, tmp_path):
    from PIL import Image

    load(page, tutorial_status="not_started", theme=theme)
    page.wait_for_timeout(350)
    shot = tmp_path / "spotlight.png"
    page.screenshot(path=str(shot))
    image = Image.open(shot).convert("RGB")
    # Independent expected theme colors, multiplied by 75% outside the hole.
    expected = 191 if theme == "light" else 17
    actual = image.getpixel((700, 140))
    assert all(abs(channel - expected) <= 2 for channel in actual)
    target = page.locator("#settings").bounding_box()
    sample = image.getpixel((int(target["x"]+10), int(target["y"]+10)))
    assert sample == ((255,255,255) if theme == "light" else (23,23,23))
    page.locator("#settings").click()
    page.wait_for_function("calls.some(c=>c.action==='settings')")
    page.get_by_role("button", name="关闭教程", exact=True).click()
    page.wait_for_timeout(250)
    page.screenshot(path=str(shot))
    assert Image.open(shot).convert("RGB").getpixel((700,140)) == ((255,255,255) if theme == "light" else (23,23,23))


def test_each_completed_step_celebrates_once_without_a_completion_hint(page):
    current = load(page, tutorial_status="not_started")
    guide = page.get_by_role("dialog", name="新手入门")
    expect(page.locator(".tutorial-celebration")).to_have_count(0)
    current.update(page="settings")
    # Use real settings markup and production readiness, with only the bridge simulated.
    current = configured_step(page)
    expect(guide.locator(".tutorial-hint")).to_be_hidden()
    expect(page.locator(".tutorial-celebration")).to_be_visible()
    particle = page.locator(".tutorial-celebration i").first
    first = particle.bounding_box()
    page.wait_for_timeout(120)
    second = particle.bounding_box()
    assert first != second
    page.evaluate("s=>promptsmithView.applySnapshot(s)",current)
    page.wait_for_timeout(1400)
    expect(page.locator(".tutorial-celebration")).to_have_count(0)
    page.evaluate("s=>promptsmithView.applySnapshot(s)",current)
    expect(page.locator(".tutorial-celebration")).to_have_count(0)
    guide.get_by_role("button", name="下一步", exact=True).click()
    expect(page.locator(".tutorial-celebration")).to_be_visible()
    guide.get_by_role("button", name="关闭教程", exact=True).click()
    expect(page.locator(".tutorial-celebration")).to_have_count(0)


def test_reduced_motion_unlocks_steps_without_confetti_animation(page):
    page.emulate_media(reduced_motion="reduce")
    configured_step(page)
    guide = page.get_by_role("dialog", name="新手入门")
    expect(guide.locator(".tutorial-hint")).to_be_hidden()
    expect(guide.get_by_role("button", name="下一步", exact=True)).to_be_enabled()
    expect(page.locator(".tutorial-celebration")).to_have_count(0)
