"""Debug interactions on the production DOM; only the desktop bridge is stubbed."""
from pathlib import Path

import pytest

from tests.test_frontend_review_regressions import browser

ASSETS = Path(__file__).resolve().parents[1] / "resources/ui/workspace"


@pytest.fixture
def debug_page(browser):
    page = browser.new_page(viewport={"width": 1120, "height": 640})
    page.set_default_timeout(1500)
    page.goto((ASSETS / "debug.html").as_uri())
    page.evaluate("""() => {
      window.records=[];window.diagnostics=[];window.revision=1;
      window.prefs={font_size:12,composer_theme:'light',debug_level:'全部',
        debug_autoscroll:true,debug_history:1500,debug_lines:6000};
      window.pywebview={api:{diagnostic:async(...args)=>diagnostics.push(args),
        snapshot:async(since)=>({preferences:prefs,preference_revision:revision,
          entries:records.filter(e=>e.id>since),sequence:records.length,
          cached:records.length,path:'',error:'',saved_sequence:0,directory_exists:false})}};
    }""")
    yield page
    page.close()


def push(page, entries):
    page.evaluate("""async values=>{
      for(const row of values)records.push({id:records.length+1,...row});
      await promptsmithDebug.poll();
    }""", entries)


def position(page):
    return page.locator("#debug-scroll").evaluate("e=>({top:e.scrollTop,end:e.scrollHeight-e.clientHeight,left:e.scrollLeft})")


def test_legend_counts_records_and_toggles_one_level_without_erasing_history(debug_page):
    page = debug_page
    push(page, [{"level": level, "text": f"severity-{level}\ntraceback line"} for level in (10, 20, 30, 40, 50)])
    legend = page.get_by_role("group", name="日志类型筛选")
    assert legend.get_by_role("button").count() == 5
    for name in ("DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"):
        assert legend.get_by_role("button", name=f"{name} 1", exact=True).get_attribute("aria-pressed") == "true"
    info = legend.get_by_role("button", name="INFO 1", exact=True)
    info.click()
    assert info.get_attribute("aria-pressed") == "false"
    assert page.locator(".log-info").count() == 0
    assert page.locator(".log-error").count() == 1
    push(page, [{"level": 20, "text": "hidden-new-info"}])
    info = legend.get_by_role("button", name="INFO 2", exact=True)
    assert info.get_attribute("aria-pressed") == "false"
    info.click()
    assert page.locator(".log-info").count() == 2
    page.locator("#clear").click()
    assert page.locator(".log-line").count() == 0
    assert all(button.inner_text().endswith("0") for button in legend.get_by_role("button").all())


def test_new_logs_preserve_history_reading_and_resume_following_at_bottom(debug_page):
    page = debug_page
    push(page, [{"level": 10, "text": f"history-{i}"} for i in range(100)])
    assert abs(position(page)["top"] - position(page)["end"]) < 2
    page.locator("#debug-scroll").evaluate("e=>e.scrollTop=180")
    before = position(page)
    push(page, [{"level": 40, "text": "new-error"}])
    assert abs(position(page)["top"] - before["top"]) < 2
    page.locator("#debug-scroll").evaluate("e=>e.scrollTop=e.scrollHeight")
    push(page, [{"level": 20, "text": "follow-at-bottom"}])
    assert abs(position(page)["top"] - position(page)["end"]) < 2


def test_reading_anchor_survives_display_cache_eviction(debug_page):
    page = debug_page
    page.evaluate("prefs.debug_history=60")
    push(page, [{"level": 10, "text": f"anchor-{i}"} for i in range(60)])
    page.locator("#debug-scroll").evaluate("e=>e.scrollTop=300")
    before = page.locator(".log-line").filter(has_text="anchor-20").bounding_box()
    push(page, [{"level": 10, "text": f"new-{i}"} for i in range(5)])
    after = page.locator(".log-line").filter(has_text="anchor-20").bounding_box()
    assert before and after and abs(before["y"] - after["y"]) < 2


def test_autoscroll_disabled_keeps_position_even_at_bottom(debug_page):
    page = debug_page
    push(page, [{"level": 10, "text": f"entry-{i}"} for i in range(60)])
    page.locator("#autoscroll").uncheck()
    before = position(page)
    push(page, [{"level": 10, "text": "do-not-follow"}])
    assert abs(position(page)["top"] - before["top"]) < 2


def test_multiline_anchor_survives_trimming_inside_one_record(debug_page):
    page = debug_page
    page.evaluate("prefs.debug_lines=60")
    push(page, [{"level": 40, "text": "\n".join(f"multi-{i}" for i in range(60))}])
    page.locator("#debug-scroll").evaluate("e=>e.scrollTop=240")
    def row_top():
        return page.locator(".log-error").evaluate("""el=>{
          const text=el.querySelector('.log-message').firstChild,index=text.data.indexOf('multi-15');
          const range=document.createRange();range.setStart(text,index);range.setEnd(text,index+8);
          return range.getBoundingClientRect().top;
        }""")
    before = row_top()
    push(page, [{"level": 20, "text": f"new-{i}"} for i in range(5)])
    assert abs(row_top() - before) < 2


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("font", [9, 12, 18])
def test_small_legend_stays_reachable_with_theme_colors(debug_page, theme, font):
    page = debug_page
    page.set_viewport_size({"width": 600, "height": 400})
    page.evaluate("([theme,font])=>Object.assign(prefs,{composer_theme:theme,font_size:font})", [theme, font])
    push(page, [{"level": level, "text": f"severity-{level}"} for level in (10, 20, 30, 40, 50)])
    for button in page.locator(".log-legend-item").all():
        box = button.bounding_box()
        assert box and 0 <= box["x"] and box["x"] + box["width"] <= 600
        assert 0 <= box["y"] and box["y"] + box["height"] <= 400
    dot = page.locator(".legend-info .legend-dot")
    assert dot.evaluate("e=>getComputedStyle(e).backgroundColor") == "rgb(245, 247, 250)"
    page.locator(".legend-info").click()
    assert dot.evaluate("e=>getComputedStyle(e).backgroundColor") != "rgb(245, 247, 250)"
    assert page.locator("#debug-scroll").bounding_box()["height"] >= 40


def test_presets_keyboard_and_all_hidden_keep_counts_without_poll_diagnostics(debug_page):
    page = debug_page
    push(page, [{"level": level, "text": f"severity-{level}"} for level in (10, 20, 30, 40, 50)])
    page.locator("#level").select_option("40")
    assert page.locator(".log-line").count() == 2
    info = page.get_by_role("button", name="INFO 1", exact=True)
    info.focus()
    page.keyboard.press("Space")
    assert info.get_attribute("aria-pressed") == "true"
    assert page.locator(".log-line").count() == 3
    assert page.locator("#level").input_value() == "custom"
    while page.locator(".log-legend-item[aria-pressed=true]").count():
        page.locator(".log-legend-item[aria-pressed=true]").first.click()
    assert page.locator(".log-line").count() == 0
    push(page, [{"level": 30, "text": "hidden-warning"}])
    assert page.get_by_role("button", name="WARN 2", exact=True).get_attribute("aria-pressed") == "false"
    before = page.evaluate("diagnostics.length")
    for _ in range(5):
        page.evaluate("promptsmithDebug.poll()")
    assert page.evaluate("diagnostics.length") == before
    page.locator("#level").select_option("10")
    assert page.locator(".log-line").count() == 6


def test_long_save_status_and_font_change_preserve_history_anchor(debug_page):
    page = debug_page
    push(page, [{"level": 10, "text": f"entry-{i}"} for i in range(100)])
    page.locator("#debug-scroll").evaluate("e=>{e.scrollTop=250;e.scrollLeft=0}")
    before = page.locator(".log-line[data-id='20']").bounding_box()["y"]
    page.evaluate("""()=>{
      const snapshot=pywebview.api.snapshot;
      pywebview.api.snapshot=async since=>({...await snapshot(since),path:'C:/very-long-folder/'.repeat(10),saved_sequence:100});
    }""")
    page.evaluate("promptsmithDebug.poll()")
    assert abs(page.locator(".log-line[data-id='20']").bounding_box()["y"] - before) < 2
    page.evaluate("prefs.font_size=18")
    page.evaluate("promptsmithDebug.poll()")
    assert position(page)["top"] < position(page)["end"]


def test_history_preference_shrinks_counts_and_view_without_new_log(debug_page):
    page = debug_page
    push(page, [{"level": 10, "text": f"history-{i}"} for i in range(100)])
    page.evaluate("prefs.debug_history=30;revision+=1")
    page.evaluate("promptsmithDebug.poll()")
    assert page.locator(".log-line").count() == 30
    assert page.get_by_role("button", name="DEBUG 30", exact=True).count() == 1


def test_idle_poll_leaves_presentation_unchanged(debug_page):
    page = debug_page
    push(page, [{"level": 10, "text": f"idle-{i}"} for i in range(100)])
    page.locator("#debug-scroll").evaluate("e=>e.scrollTop=250")
    mutations = page.evaluate("""async()=>{
      let changes=0;const observer=new MutationObserver(rows=>changes+=rows.length);
      observer.observe(document.body,{subtree:true,childList:true,characterData:true});
      for(let i=0;i<5;i++)await promptsmithDebug.poll();
      await Promise.resolve();observer.disconnect();return changes;
    }""")
    assert mutations == 0
