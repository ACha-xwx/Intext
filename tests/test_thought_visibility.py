"""Actual trace disclosure behavior through production DOM and Tk surfaces."""

import tkinter as tk

import pytest

from promptsmith.response_ui import ResponseTrace
from tests.test_conversation_workspace import app
from tests.test_frontend_review_regressions import browser, page
from tests.test_trace_timer import working_trace


def test_empty_thinking_has_no_disclosure_but_keeps_elapsed_and_activity(page):
    state, record = working_trace(page)
    record["activities"] = [["检索已确认要求", "2 条"]]
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    page.locator(".trace>button").evaluate("e=>e.click()")
    page.clock.run_for(450)
    assert not page.get_by_role("button", name="思考内容", exact=True).is_visible()
    assert page.get_by_text("检索已确认要求", exact=True).is_visible()
    assert "6.2 秒" in page.locator(".trace>button").inner_text()


def test_tk_empty_thinking_has_no_disclosure_but_keeps_failure_guidance(app):
    host = tk.Frame(app.root)
    try:
        trace = ResponseTrace(host, {"id": "empty", "status": "failed", "reasoning": "",
                                    "elapsed": 2.4, "error": "连接失败，请重试。"})
        assert not trace.thinking_button.winfo_manager()
        assert not trace.thought_frame.winfo_manager()
        assert trace.note.cget("text") == "连接失败，请重试。"
        assert "2.4 秒" in trace.header.cget("text")
    finally:
        host.destroy()


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("font", [9, 12, 18])
def test_elapsed_and_disclosure_have_clear_gap_at_all_supported_text_sizes(page, theme, font):
    state, record = working_trace(page)
    state.update(theme=theme, font_size=font)
    positions = []
    for elapsed in [11.1, 88.8, 99.9, 400.0, 3600.0]:
        record.update(status="done", elapsed=elapsed)
        page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
        label = page.locator(".trace>button>span").nth(1).bounding_box()
        arrow = page.locator(".trace>button .chevron").bounding_box()
        assert arrow["x"] - (label["x"] + label["width"]) >= 8
        assert abs(arrow["y"] + arrow["height"]/2 - (label["y"] + label["height"]/2)) <= 1
        positions.append(arrow["x"])
    assert max(positions[:3]) - min(positions[:3]) < .5


def test_hiding_cleared_thinking_returns_keyboard_focus_to_visible_header(page):
    state, record = working_trace(page, reasoning="公开思考摘要")
    page.locator(".trace>button").evaluate("e=>e.click()")
    page.clock.run_for(450)
    page.get_by_role("button", name="思考内容", exact=True).focus()
    record["reasoning"] = ""
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    assert page.locator(".trace>button").evaluate("e=>e===document.activeElement")


@pytest.mark.parametrize("status", ["working", "done", "failed", "cancelled"])
def test_whitespace_only_thinking_stays_hidden_and_errors_are_readable(page, status):
    state, record = working_trace(page, reasoning="\r\n \t \n")
    record.update(status=status, error="请求失败，请检查设置后重试。" if status == "failed" else "")
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    page.locator(".trace>button").evaluate("e=>e.click()")
    page.clock.run_for(450)
    assert not page.get_by_role("button", name="思考内容", exact=True).is_visible()
    assert not page.locator(".thought").is_visible()
    if status == "failed":
        assert page.get_by_text("请求失败，请检查设置后重试。", exact=True).is_visible()


def test_first_public_thinking_chunk_appears_without_reopening_user_collapsed_content(page):
    state, record = working_trace(page)
    page.evaluate("calls.length=0")
    record["model"] = "gpt-6.1-sol"
    page.locator(".trace>button").evaluate("e=>e.click()")
    page.clock.run_for(450)
    thought_button = page.get_by_role("button", name="思考内容", exact=True)
    assert not thought_button.is_visible()
    record["reasoning"] = "PUBLIC_SUMMARY_汉字👩🏽‍💻"
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    assert thought_button.is_visible()
    thought_button.evaluate("e=>e.click()")
    for suffix in ["", "\n后续摘要", "\n更多摘要"]:
        record["reasoning"] += suffix
        page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    assert thought_button.get_attribute("aria-expanded") == "false"
    assert page.locator(".trace>button").get_attribute("aria-expanded") == "true"
    record.update(status="done", elapsed=7.2)
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    page.clock.run_for(5000)
    thought_button.evaluate("e=>e.click()")
    page.clock.run_for(450)
    assert page.locator(".thought").is_visible()
    assert page.locator(".thought").text_content() == record["reasoning"]
    events = page.evaluate("calls.filter(c=>c.action==='diagnostic'&&c.args[1]==='trace thinking visibility')")
    assert len(events) == 1
    assert events[0]["args"][2].endswith("visible=true")
    assert all("PUBLIC_SUMMARY" not in str(event) for event in events)


def test_tk_first_chunk_restores_thinking_without_resetting_user_toggle_or_spamming_logs(app, caplog):
    host = tk.Frame(app.root)
    record = {"id": "late", "status": "working", "reasoning": " \n", "elapsed": 0.0}
    try:
        trace = ResponseTrace(host, record)
        assert not trace.thinking_button.winfo_manager()
        record["reasoning"] = "PRIVATE_BODY_SENTINEL"
        trace.update_status()
        assert trace.thinking_button.winfo_manager() == "pack"
        assert trace.thought_frame.winfo_manager() == "pack"
        trace.toggle_thought()
        opened = trace.thought_frame.opened
        for elapsed in [1.0, 1.1, 1.2]:
            record["elapsed"] = elapsed
            trace.update_status()
        assert trace.thought_frame.opened == opened
        events = [r.getMessage() for r in caplog.records if "Reasoning visibility changed:" in r.getMessage()]
        assert len(events) == 2
        assert all("PRIVATE_BODY_SENTINEL" not in event for event in events)
    finally:
        host.destroy()
