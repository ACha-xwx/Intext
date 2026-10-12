"""Exercise real sidebar buttons and CSS frames, with an isolated desktop bridge."""
import json
import os
from pathlib import Path

import pytest

from tests.test_frontend_review_regressions import browser, page, load, settle


SAMPLE = """async ({duration, reverseAt=null}) => {
  const frames=[];
  const toggle=()=>document.querySelector(document.body.classList.contains('sidebar-collapsed')?'#sidebar-dock-toggle':'#sidebar-toggle');
  const rect=element=>{const r=element.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height};};
  const opacity=element=>{let value=1;for(let e=element;e;e=e.parentElement)value*=Number(getComputedStyle(e).opacity);return value;};
  const sample=time=>{
    const list=document.querySelector('#history-list'),style=getComputedStyle(list);
    const selectors=document.body.classList.contains('sidebar-collapsed')?
      ['.sidebar-logo','#sidebar-dock-toggle','#sidebar-dock-search','#sidebar-dock-new']:
      ['.sidebar-logo','#sidebar-toggle','#history-search','#new-chat'];
    frames.push({time,controls:selectors.map(selector=>rect(document.querySelector(selector))),
      list:{...rect(list),opacity:opacity(list),visibility:style.visibility,display:style.display},
      visibleButtons:[...document.querySelectorAll('#sidebar .sidebar-icon,#new-chat')]
        .filter(e=>getComputedStyle(e).visibility==='visible'&&opacity(e)>.05)
        .map(e=>({id:e.id,...rect(e)})),
      shell:rect(document.querySelector('#workspace-shell'))});
  };
  sample(-1);
  toggle().click();
  sample(0);
  const start=performance.now();let reversed=false;
  await new Promise(resolve=>{
    const tick=now=>{const elapsed=Math.max(0,now-start);sample(elapsed);
      if(reverseAt!==null&&!reversed&&elapsed>=reverseAt){toggle().click();reversed=true;}
      if(elapsed<duration)requestAnimationFrame(tick);else resolve();
    };requestAnimationFrame(tick);
  });
  return frames;
}"""


def sample_transition(page, *, duration=450, reverse_at=None, name="collapse"):
    frames = page.evaluate(SAMPLE, {"duration": duration, "reverseAt": reverse_at})
    evidence = os.environ.get("PROMPTSMITH_ANIMATION_EVIDENCE")
    if evidence:
        directory = Path(evidence)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{name}.json").write_text(json.dumps(frames, indent=2), encoding="utf-8")
    return frames


@pytest.mark.parametrize("size", [(1440, 810), (720, 440)])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_collapse_keeps_controls_at_top_and_history_exits_continuously(page, size, theme):
    page.set_viewport_size({"width": size[0], "height": size[1]})
    load(page, "plan", theme=theme)
    page.evaluate("promptsmithHistory.setCollapsed(false)")
    settle(page)
    frames = sample_transition(page, name=f"collapse-{theme}-{size[0]}")
    for frame in frames:
        for control in frame["controls"][:3]:
            assert 0 <= control["y"] and control["y"] + control["height"] <= 70, frame
        assert frame["controls"][3]["y"] + frame["controls"][3]["height"] <= 135, frame
    early = [frame for frame in frames if 0 <= frame["time"] <= 50]
    assert any(frame["list"]["height"] > 0 and frame["list"]["opacity"] > 0
               and frame["list"]["visibility"] == "visible" for frame in early)
    assert any(0 < frame["list"]["opacity"] < 1 for frame in frames)
    assert not page.locator("#history-list").is_visible()
    assert page.locator("#sidebar-toggle").get_attribute("aria-expanded") == "false"


@pytest.mark.parametrize("reverse", [False, True])
def test_expand_or_reverse_retains_history_focus_and_working_controls(page, reverse):
    load(page, "plan")
    page.evaluate("promptsmithHistory.setCollapsed(false)")
    settle(page)
    if not reverse:
        page.locator("#sidebar-toggle").click()
        settle(page)
    frames = sample_transition(page, duration=650, reverse_at=85 if reverse else None,
                               name="reverse" if reverse else "expand")
    for frame in frames:
        assert all(0 <= c["y"] and c["y"] + c["height"] <= 70 for c in frame["controls"][:3])
    assert page.locator("#sidebar-toggle").get_attribute("aria-expanded") == "true"
    assert page.locator("#history-list").is_visible()
    page.locator(".history-select").first.click()
    page.wait_for_function("calls.some(c=>c.action==='history_open')")
    page.locator("#history-search").click()
    assert page.locator("#history-search-input").evaluate("e=>e===document.activeElement")
    page.keyboard.press("Escape")
    page.locator("#new-chat").click()
    page.wait_for_function("calls.some(c=>c.action==='new')")


def test_hidden_history_cannot_take_keyboard_focus_or_block_the_workspace(page):
    load(page, "plan")
    page.evaluate("promptsmithHistory.setCollapsed(false)")
    settle(page)
    page.locator(".history-select").first.focus()
    page.evaluate("promptsmithHistory.setCollapsed(true)")
    assert page.get_by_role("button", name="展开边栏", exact=True).evaluate("e=>e===document.activeElement")
    # The fading list is already unavailable to keyboard input, then fully hidden.
    page.locator(".history-select").first.evaluate("e=>e.focus()")
    assert page.get_by_role("button", name="展开边栏", exact=True).evaluate("e=>e===document.activeElement")
    settle(page)
    page.locator("#message").fill("侧栏收起后仍能输入")
    assert page.locator("#message").evaluate("e=>e===document.activeElement")
    assert page.evaluate("document.elementFromPoint(100,300).closest('#sidebar')===null")
    assert sum(c["action"] == "diagnostic" and c["args"][1] == "sidebar visibility"
               for c in page.evaluate("calls")) == 2


def test_reduced_motion_and_reload_restore_the_requested_sidebar_state(page):
    page.emulate_media(reduced_motion="reduce")
    load(page, "plan")
    page.evaluate("promptsmithHistory.setCollapsed(false)")
    settle(page)
    page.get_by_role("button", name="收起边栏", exact=True).click()
    page.wait_for_function("getComputedStyle(document.querySelector('#history-list')).visibility==='hidden'")
    assert page.locator("#sidebar-toggle").get_attribute("aria-expanded") == "false"
    page.reload()
    assert page.locator("#sidebar-toggle").get_attribute("aria-expanded") == "false"
    assert not page.locator("#history-list").is_visible()
    page.get_by_role("button", name="展开边栏", exact=True).click()
    assert page.locator("#sidebar-toggle").get_attribute("aria-expanded") == "true"


@pytest.mark.parametrize("reverse_at", [None, 85])
def test_sidebar_buttons_never_cross_or_overlap_during_collapse_and_reversal(page, reverse_at):
    load(page, "plan")
    page.evaluate("promptsmithHistory.setCollapsed(false)")
    settle(page)
    frames = sample_transition(page, duration=650, reverse_at=reverse_at,
                               name=f"button-paths-{reverse_at}")
    for frame in frames:
        controls = frame["visibleButtons"]
        for i, first in enumerate(controls):
            for second in controls[i + 1:]:
                x = min(first["x"] + first["width"], second["x"] + second["width"]) - max(first["x"], second["x"])
                y = min(first["y"] + first["height"], second["y"] + second["height"]) - max(first["y"], second["y"])
                assert x <= 1 or y <= 1, (frame["time"], first, second)


def test_fast_pointer_reversal_uses_expand_action_and_collapsed_search_returns_focus(page):
    load(page, "plan")
    page.evaluate("promptsmithHistory.setCollapsed(false)")
    settle(page)
    page.get_by_role("button", name="收起边栏", exact=True).click()
    page.wait_for_timeout(70)
    expand = page.get_by_role("button", name="展开边栏", exact=True).bounding_box()
    page.mouse.click(expand["x"] + expand["width"] / 2, expand["y"] + expand["height"] / 2)
    settle(page)
    assert page.get_by_role("button", name="收起边栏", exact=True).get_attribute("aria-expanded") == "true"
    assert not page.locator(".history-overlay").count()
    page.get_by_role("button", name="收起边栏", exact=True).click()
    settle(page)
    search = page.get_by_role("button", name="搜索历史会话", exact=True)
    search.click()
    assert page.locator("#history-search-input").evaluate("e=>e===document.activeElement")
    page.keyboard.press("Escape")
    assert search.evaluate("e=>e===document.activeElement")
    page.get_by_role("button", name="开启新对话", exact=True).click()
    page.wait_for_function("calls.some(c=>c.action==='new')")
