"""Startup on the real production DOM; only the desktop bridge is simulated."""
import json

import pytest
from playwright.sync_api import expect

from tests.test_frontend_review_regressions import ASSETS, STATES, browser


@pytest.fixture
def hero_page(browser, request):
    view = browser.new_page(viewport={"width": 1440, "height": 810})
    view.set_default_timeout(4000)
    if hasattr(request, "param"):
        view.add_init_script(request.param)
    view.goto((ASSETS / "index.html").as_uri())
    view.evaluate("""() => {
      window.calls=[];window.pywebview={api:{
        diagnostic:async(...args)=>calls.push({action:'diagnostic',args}),
        snapshot:async()=>null,
        dispatch:async(action,data)=>{calls.push({action,data});return {ok:true};}
      }};
    }""")
    yield view
    view.close()


def publish(view, status="not_started", **changes):
    current = json.loads(json.dumps(STATES["empty"]))
    current.update(tutorial_status=status, **changes)
    view.evaluate("s=>promptsmithView.applySnapshot(s)", current)
    return current


def test_first_launch_waits_for_start_before_opening_tutorial(hero_page):
    view = hero_page
    expect(view.get_by_role("status", name="正在加载 Intext")).to_be_visible()
    expect(view.get_by_role("dialog", name="新手入门")).to_have_count(0)
    current = publish(view)
    start = view.get_by_role("button", name="开始使用 Intext", exact=True)
    expect(start).to_be_visible()
    expect(view.get_by_role("dialog", name="新手入门")).to_have_count(0)
    assert view.locator("#workspace-shell").evaluate("e=>e.inert")
    assert not view.evaluate("calls.some(c=>c.action!=='diagnostic')")
    start.click()
    expect(view.locator("#startup-hero")).to_be_hidden()
    expect(view.get_by_role("dialog", name="新手入门")).to_be_visible()
    expect(view.get_by_role("button", name="下一步", exact=True)).to_be_disabled()
    view.evaluate("s=>promptsmithView.applySnapshot(s)", current)
    expect(view.locator("#startup-hero")).to_be_hidden()
    assert not view.evaluate("calls.some(c=>['tutorial_finish','tutorial_skip','send'].includes(c.action))")


@pytest.mark.parametrize("status", ["completed", "skipped"])
def test_returning_users_load_then_enter_without_a_start_button(hero_page, status):
    view = hero_page
    expect(view.get_by_role("status", name="正在加载 Intext")).to_be_visible()
    publish(view, status, drafts={"message":"保留我的目标"})
    expect(view.locator("#startup-hero")).to_be_hidden()
    expect(view.get_by_role("button", name="开始使用 Intext", exact=True)).to_be_hidden()
    expect(view.get_by_role("dialog", name="新手入门")).to_have_count(0)
    expect(view.locator("#message")).to_have_value("保留我的目标")
    assert not view.locator("#workspace-shell").evaluate("e=>e.inert")
    assert not view.evaluate("calls.some(c=>c.action!=='diagnostic')")


def test_startup_keyboard_shortcuts_cannot_operate_on_hidden_workspace(hero_page):
    view = hero_page
    publish(view)
    expect(view.get_by_role("button", name="开始使用 Intext", exact=True)).to_be_visible()
    view.keyboard.press("Control+s")
    view.keyboard.press("Control+k")
    assert not view.evaluate("calls.some(c=>c.action!=='diagnostic')")
    expect(view.get_by_role("dialog", name="搜索历史会话")).to_have_count(0)


@pytest.mark.parametrize("theme,width,height", [("light",1440,810),("dark",720,440),("light",360,360)])
def test_hero_group_is_centered_and_the_reference_animations_are_local(hero_page, theme, width, height):
    view = hero_page
    view.set_viewport_size({"width":width,"height":height})
    expect(view.get_by_role("status", name="正在加载 Intext")).to_be_visible()
    loader = view.locator(".startup-loader")
    assert loader.evaluate("e=>getComputedStyle(e).animationDuration") == "2s"
    assert loader.evaluate("e=>[e.offsetWidth,e.offsetHeight]") == [40,40]
    publish(view, theme=theme)
    start = view.get_by_role("button", name="开始使用 Intext", exact=True)
    expect(start).to_be_visible()
    box = view.locator(".startup-group").bounding_box()
    assert abs(box["x"] + box["width"]/2 - width/2) < 1
    assert abs(box["y"] + box["height"]/2 - height/2) < 1
    assert box["x"] >= 0 and box["x"] + box["width"] <= width
    assert start.evaluate("e=>[e.offsetWidth,e.offsetHeight]") == [60,60]
    assert start.locator("svg").evaluate("e=>[e.getBoundingClientRect().width,e.getBoundingClientRect().height]") == [20,20]
    expect(start.locator("canvas")).to_have_count(1)
    assert not view.evaluate("calls.some(c=>c.action!=='diagnostic')")
    logo = view.locator(".startup-wordmark")
    assert logo.evaluate("e=>e.complete&&e.naturalWidth>0")
    assert logo.evaluate("e=>{const r=e.getBoundingClientRect();return Math.abs(r.width/r.height-e.naturalWidth/e.naturalHeight)}") < .02
    assert logo.bounding_box()["width"] <= 240


def test_lack_of_webgl_keeps_the_start_button_usable_and_logs_the_cause(hero_page):
    view = hero_page
    view.evaluate("HTMLCanvasElement.prototype.getContext=function(){return null;}")
    publish(view)
    start = view.get_by_role("button", name="开始使用 Intext", exact=True)
    expect(start).to_be_enabled()
    view.wait_for_function("calls.some(c=>c.action==='diagnostic'&&c.args[0]==='warn'&&c.args[2].includes('WebGL'))")
    start.click()
    expect(view.get_by_role("dialog", name="新手入门")).to_be_visible()


def test_start_button_clips_the_click_ripple_to_its_circle(hero_page):
    view = hero_page
    publish(view)
    start = view.get_by_role("button", name="开始使用 Intext", exact=True)
    expect(start).to_be_visible()
    start.click()
    expect(start.locator(".startup-ripple")).to_have_count(1)
    assert start.evaluate("e=>getComputedStyle(e).overflow") == "hidden"


def test_static_silver_border_survives_hover_without_webgl(hero_page):
    view = hero_page
    view.evaluate("HTMLCanvasElement.prototype.getContext=function(){return null;}")
    publish(view)
    start = view.get_by_role("button", name="开始使用 Intext", exact=True)
    expect(start).to_be_visible()
    background = start.evaluate("e=>getComputedStyle(e).backgroundImage")
    assert "linear-gradient" in background
    start.hover()
    assert start.evaluate("e=>getComputedStyle(e).backgroundImage") == background
    start.click()
    expect(view.get_by_role("dialog", name="新手入门")).to_be_visible()


def test_reduced_motion_and_keyboard_start_preserve_the_same_flow(hero_page):
    view = hero_page
    view.emulate_media(reduced_motion="reduce")
    publish(view)
    start = view.get_by_role("button", name="开始使用 Intext", exact=True)
    expect(start).to_be_visible()
    assert view.locator(".startup-loader").evaluate("e=>getComputedStyle(e).animationName") == "none"
    view.keyboard.press("Enter")
    expect(view.get_by_role("dialog", name="新手入门")).to_be_visible()
    expect(view.locator(".startup-metal canvas")).to_have_count(0)


def test_product_brand_is_intext_in_main_and_debug_pages(hero_page):
    view = hero_page
    publish(view,"completed")
    expect(view.locator("#startup-hero")).to_be_hidden()
    assert view.title() == "Intext"
    expect(view.locator("header .brand img")).to_have_attribute("alt", "Intext")
    expect(view.locator(".sidebar-logo")).to_have_attribute("alt", "Intext")
    assert "PromptSmith" not in view.locator("body").inner_text()
    view.goto((ASSETS/"debug.html").as_uri())
    assert view.title() == "Intext · Debug 控制台"
    expect(view.locator("header .brand img")).to_have_attribute("alt", "Intext")


def test_hero_uses_the_user_logo_without_runtime_font_generation(hero_page):
    from PIL import Image
    from pathlib import Path
    from tests.test_frontend_review_regressions import ASSETS
    view = hero_page
    publish(view)
    expect(view.get_by_role("button", name="开始使用 Intext", exact=True)).to_be_visible()
    image = view.locator(".startup-wordmark")
    assert image.evaluate("e=>e.complete&&e.naturalWidth===768")
    source = image.get_attribute("src")
    assert source == "brand/intext-logo.png"
    logo = Image.open(Path(ASSETS)/source)
    assert logo.mode == "RGBA" and logo.getpixel((0,0))[3] == 0
    assert view.locator(".startup-name").get_attribute("src") == "brand/intext-wordmark.svg"


def test_sidebar_uses_the_same_color_logo_in_both_themes(hero_page):
    from playwright.sync_api import expect
    publish(hero_page,"completed")
    for theme in ('light','dark'):
        hero_page.evaluate("theme=>document.documentElement.dataset.theme=theme",theme)
        image = hero_page.locator('.sidebar-logo')
        expect(image).to_be_visible()
        assert image.get_attribute('src') == 'brand/intext-logo.png'
        assert image.evaluate('e=>e.complete&&e.naturalWidth>0')
        assert image.evaluate('e=>getComputedStyle(e).filter') == 'none'
        assert hero_page.locator('.sidebar-wordmark').get_attribute('src') == 'brand/intext-english.svg'


def test_glass_composer_buttons_have_no_second_bright_inner_ring(hero_page, tmp_path):
    from PIL import Image

    publish(hero_page, "completed", theme="dark")
    for name in ("#depth-button", "#category-button"):
        button=hero_page.locator(name)
        shot=tmp_path/(name[1:]+".png")
        button.screenshot(path=str(shot))
        image=Image.open(shot).convert("RGB")
        # The reported extra ring runs across the pill at 8px from its top.
        # Its center is clear of label glyphs and the outer glass edge.
        x=image.width//2
        above,ring,below=(image.getpixel((x,y))[0] for y in (7,8,9))
        assert ring <= max(above,below)+10
        button.focus()
        assert button.evaluate("e=>parseFloat(getComputedStyle(e).outlineWidth)")>=2


@pytest.mark.parametrize("hero_page", [pytest.param(
    "window.finishWordmark=null;window.waitingWordmark=null;HTMLImageElement.prototype.decode=function(){return window.waitingWordmark??=new Promise(resolve=>window.finishWordmark=resolve)};",
    id="delayed-svg")], indirect=True)
def test_loading_waits_for_the_local_wordmark_before_entering(hero_page):
    view = hero_page
    publish(view, "completed")
    view.wait_for_timeout(1000)
    expect(view.get_by_role("status", name="正在加载 Intext")).to_be_visible()
    assert view.locator("#workspace-shell").evaluate("e=>e.inert")
    view.evaluate("finishWordmark()")
    expect(view.locator("#startup-hero")).to_be_hidden()


@pytest.mark.parametrize("hero_page", [pytest.param(
    "HTMLImageElement.prototype.decode=function(){return Promise.reject(new Error('Broken local wordmark SVG'))};",
    id="broken-svg")], indirect=True)
def test_wordmark_failure_keeps_a_readable_brand_and_a_working_entry(hero_page):
    view = hero_page
    publish(view)
    start = view.get_by_role("button", name="开始使用 Intext", exact=True)
    expect(start).to_be_visible()
    expect(view.locator(".startup-title")).to_have_text("意织 · Intext")
    assert view.locator(".startup-title").evaluate("e=>parseFloat(getComputedStyle(e).lineHeight)") > 20
    view.wait_for_function("calls.some(c=>c.action==='diagnostic'&&c.args[0]==='warn'&&c.args[2].includes('Broken local wordmark SVG'))")
    start.click()
    expect(view.get_by_role("dialog", name="新手入门")).to_be_visible()
