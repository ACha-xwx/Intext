"""Live display controls through the production Chromium workspace."""
from tests.test_frontend_review_regressions import browser, page, load
from playwright.sync_api import expect
from tests.test_debug_legend import debug_page
import pytest


@pytest.mark.parametrize('width', [900,1440])
def test_live_width_and_notification_duration_apply_without_reload(page, width):
    page.set_viewport_size({'width':width,'height':810})
    load(page, kind='empty', display_preferences=dict(conversation_width=720,
        notification_seconds=1, thinking_autoscroll=False, thinking_speed=2))
    assert page.locator('#timeline').bounding_box()['width'] <= 721
    assert page.locator('#composer').bounding_box()['width'] <= 721
    page.evaluate("promptsmithNotifications.show('短通知',{key:'duration-check'})")
    toast = page.locator('[data-key="duration-check"]')
    expect(toast).to_be_visible()
    assert toast.locator('.notification-countdown').evaluate('e=>getComputedStyle(e).animationDuration') == '1s'
    expect(toast).to_have_count(0, timeout=2200)


def test_duration_change_does_not_restart_existing_notification(page):
    state = load(page, display_preferences=dict(notification_seconds=1))
    page.evaluate("promptsmithNotifications.show('现有消息',{key:'existing'})")
    page.wait_for_timeout(650)
    state['display_preferences']['notification_seconds'] = 8
    page.evaluate('s=>promptsmithView.applySnapshot(s)',state)
    expect(page.locator('[data-key="existing"]')).to_have_count(0,timeout=1800)


@pytest.mark.parametrize('speed', [.5, 2.])
def test_thinking_speed_keeps_unicode_and_does_not_force_scroll(page, speed):
    from tests.test_trace_timer import working_trace
    state, record = working_trace(page)
    state['display_preferences'] = dict(thinking_speed=speed, thinking_autoscroll=False)
    record['reasoning'] = '👩🏽‍💻é𠮷\n' * 500
    page.evaluate('s=>promptsmithView.applySnapshot(s)', state)
    page.locator('.trace>button').click()
    page.clock.run_for(180)
    visible = page.locator('.thought').text_content()
    assert visible and record['reasoning'].startswith(visible)
    assert page.locator('.thought').evaluate('e=>e.scrollTop') == 0
    count = page.locator('.thought').evaluate('e=>[...e.textContent].length')
    assert count < (3000 if speed == .5 else 8000)
    assert count > (200 if speed == .5 else 1800)
    page.clock.run_for(6000)
    assert page.locator('.thought').text_content() == record['reasoning']


def test_debug_refresh_follows_saved_interval_and_live_changes(debug_page):
    page = debug_page
    page.clock.install(time=0)
    page.clock.pause_at(1000)
    page.evaluate("""() => {prefs.debug_refresh_ms=500;window.pollTimes=[];
      const original=pywebview.api.snapshot;pywebview.api.snapshot=async since=>{
        pollTimes.push(performance.now());return original(since);
      };window.dispatchEvent(new Event('pywebviewready'));
    }""")
    page.clock.run_for(1100)
    times = page.evaluate('pollTimes')
    assert [value-times[0] for value in times] == [0,500,1000]
    page.evaluate('prefs.debug_refresh_ms=200;revision++')
    page.clock.run_for(650)
    assert [value-times[0] for value in page.evaluate('pollTimes.slice(-2)')] == [1500,1700]
