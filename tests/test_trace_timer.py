"""Visible thinking elapsed time through the real browser snapshot boundary."""
import pytest

from tests.test_frontend_review_regressions import browser, page, load


def working_trace(page, elapsed=5.8, reasoning=""):
    state = load(page, "interview")
    page.clock.install(time=0)
    page.clock.pause_at(1000)
    record = next(c["trace"] for c in state["cards"] if c["kind"] == "trace")
    record.update(status="working", elapsed=elapsed, reasoning=reasoning)
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    return state, record


def label(page):
    return page.locator(".trace>button").inner_text()


def test_working_elapsed_advances_without_new_snapshot_or_reasoning_chunk(page):
    working_trace(page)
    assert "5.8 秒" in label(page)
    readings = []
    for _ in range(7):
        page.clock.run_for(100)
        readings.append(label(page))
    for actual, expected in zip(readings, ["5.9", "6.0", "6.1", "6.2", "6.3", "6.4", "6.5"]):
        assert expected + " 秒" in actual


def test_delayed_repeated_snapshots_do_not_pause_or_reverse_the_visible_clock(page):
    state, record = working_trace(page)
    page.clock.run_for(700)
    for elapsed, expected in [(5.8, "6.5"), (6.0, "6.6"), (6.1, "6.7")]:
        record["elapsed"] = elapsed
        page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
        assert expected + " 秒" in label(page)
        page.clock.run_for(100)
    assert "6.8 秒" in label(page)
    events = page.evaluate("calls.filter(c=>c.action==='diagnostic'&&c.args[1].startsWith('trace clock'))")
    assert [e["args"][1] for e in events] == ["trace clock started"]


@pytest.mark.parametrize("status, expected", [("done", "已完成"), ("failed", "处理未完成"), ("cancelled", "已取消")])
def test_terminal_elapsed_uses_final_backend_value_and_stops_while_text_finishes(page, status, expected):
    reasoning = "汉字👩🏽‍💻é𠮷\n" * 500
    state, record = working_trace(page, reasoning=reasoning)
    page.clock.run_for(300)
    record.update(status=status, elapsed=6.04)
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    final_label = label(page)
    visible_at_completion = page.locator(".thought").text_content()
    assert expected in final_label and "6.0 秒" in final_label
    page.clock.run_for(5000)
    assert label(page) == final_label
    assert page.locator(".thought").text_content() == (visible_at_completion if status == "cancelled" else reasoning)
    events = page.evaluate("calls.filter(c=>c.action==='diagnostic'&&c.args[1].startsWith('trace clock'))")
    assert [e["args"][1] for e in events] == ["trace clock started", "trace clock stopped"]


def test_session_change_and_removed_trace_cannot_keep_updating_old_elapsed(page):
    state, _ = working_trace(page)
    page.evaluate("window.retiredTrace=document.querySelector('.trace');window.retiredLabel=retiredTrace.querySelector('button').textContent")
    next_state = dict(state, session="fresh-timer-session", cards=[])
    page.evaluate("s=>promptsmithView.applySnapshot(s)", next_state)
    page.clock.run_for(1000)
    assert page.locator(".trace").count() == 0
    assert page.evaluate("retiredTrace.querySelector('button').textContent===retiredLabel")
    # A new request starts from its own elapsed time, not the removed clock.
    next_state["cards"] = state["cards"]
    page.evaluate("s=>promptsmithView.applySnapshot(s)", next_state)
    assert "5.8 秒" in label(page)
    next_state["cards"] = []
    page.evaluate("s=>promptsmithView.applySnapshot(s)", next_state)
    page.clock.run_for(1000)
    assert page.locator(".trace").count() == 0


def test_elapsed_stays_continuous_when_folded_and_with_reduced_motion(page):
    page.emulate_media(reduced_motion="reduce")
    working_trace(page)
    if page.locator(".trace>button").get_attribute("aria-expanded") == "false":
        page.locator(".trace>button").evaluate("e=>e.click()")
    page.locator(".trace>button").evaluate("e=>e.click()")
    assert page.locator(".trace>button").get_attribute("aria-expanded") == "false"
    page.clock.run_for(700)
    assert "6.5 秒" in label(page)


def test_digit_changes_keep_timer_and_disclosure_icon_width_stable(page):
    state, record = working_trace(page)
    positions = []
    for elapsed in [11.1, 88.8, 99.9]:
        record.update(status="done", elapsed=elapsed)
        page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
        positions.append(page.locator(".trace>button .chevron").bounding_box()["x"])
    assert max(positions) - min(positions) < 0.5
