"""Reply presentation, adaptive typing and per-question collection contracts."""
from copy import deepcopy
import json
import time
import tkinter as tk
from threading import Event

import pytest

from promptsmith.m1 import build_m1_input
from promptsmith.response_ui import AdaptiveWriter, HERO_TEXT, MarkdownText, PROMPT_SECTIONS, ResponseTrace
from promptsmith.streaming import publish
from promptsmith.storage import save_session, load_session
from tests.test_conversation_workspace import app, install_session
from tests.test_ui_session_cancellation import _wait, _drain_completions
from tests.test_ui_delivery_interactions import _candidate, _set_candidate_batch, _DeliveryUiClient, _configure_delivery_client
from tests.test_final_delivery import confirmed_plan_session


class FakeText:
    def __init__(self):
        self.jobs = []
        self.text = ""
        self.chunks = []
        self.delays = []
    def after(self, delay, callback):
        self.delays.append(delay)
        self.jobs.append(callback)
        return callback
    def after_cancel(self, callback):
        self.jobs.remove(callback)
    def winfo_exists(self):
        return True
    def yview(self):
        return (0, 1)
    def configure(self, **_):
        pass
    def insert(self, index, text):
        assert index == "end"
        self.text += text
        self.chunks.append(text)
    def yview_moveto(self, _):
        pass
    def frame(self):
        self.jobs.pop(0)()


def test_adaptive_writer_catches_up_without_finish_flush_or_unicode_loss():
    widget, drained = FakeText(), []
    writer = AdaptiveWriter(widget, lambda: drained.append(True))
    source = ("汉字e\u0301🧠👩\u200d💻🇨🇳👍🏽\r\n\r\n  下一段\n\n" * 4000).rstrip()
    writer.feed(source)
    writer.finish()
    assert widget.text == "" and len(widget.jobs) == 1
    widget.frame()
    assert 1 < len(widget.chunks[0]) < len(source)
    while widget.jobs:
        widget.frame()
    expected = ("汉字e\u0301🧠👩\u200d💻🇨🇳👍🏽\n下一段\n" * 4000).rstrip()
    assert widget.text == expected
    assert len(widget.chunks) > 10 and drained == [True]
    assert set(widget.delays) == {16} and writer.largest_chunk <= 4105
    assert not any(c.endswith("\u200d") or c.startswith("\u0301") for c in widget.chunks)
    sparse = FakeText()
    short = AdaptiveWriter(sparse)
    short.feed("abcdef")
    sparse.frame()
    assert len(sparse.chunks[0]) < len(widget.chunks[0])
    short.close()


def test_split_crlf_and_joiner_survive_with_single_line_break():
    widget = FakeText()
    writer = AdaptiveWriter(widget)
    for value in ["第一段\r", "\n\n", "  第二段👩", "\u200d", "💻"]:
        writer.feed(value)
    writer.finish()
    while widget.jobs:
        widget.frame()
    assert widget.text == "第一段\n第二段👩\u200d💻"
    writer.feed("late")
    writer.close()
    assert not widget.jobs


def questions():
    return [{"question_id": f"q{i}", "gap_id": None, "field": "audience", "scope": "目标",
             "text": f"第{i}个问题？", "options": [], "reason": "internal", "depends_on": []} for i in range(1, 4)]


def test_hero_is_centered_and_old_welcome_progress_are_hidden(app):
    hero = app.widgets["conversation_hero"]
    assert hero.cget("text") == HERO_TEXT
    assert hero.winfo_manager() == "place"
    assert float(hero.place_info()["relx"]) == float(hero.place_info()["rely"]) == .5
    assert "welcome" not in app._conversation_frames
    assert all("当前进度" != str(w.cget("text")) for w in app._conversation_labels)
    app.widgets["task_text"].insert("1.0", "目标")
    app._sync_input()
    app.refresh()
    assert not hero.winfo_manager()


@pytest.mark.parametrize("theme,bg", [("light", "#ffffff"), ("dark", "#171717")])
def test_entire_workspace_has_one_surface_and_no_duplicate_next_step(app, theme, bg):
    app.preferences["composer_theme"] = theme
    app.refresh()
    for name in ("workspace_shell", "workspace_header", "workspace_footer", "conversation_page",
                 "conversation_heading", "conversation_viewport"):
        assert app.widgets[name].cget("bg") == bg
    assert app.root.cget("bg") == bg
    assert not app.widgets["conversation_heading"].winfo_manager()
    assert not app.widgets["workspace_footer"].winfo_manager()
    app.widgets["task_text"].insert("1.0", "目标")
    app._sync_input()
    app.session.pending_questions = questions()
    app.refresh()
    assert app.widgets["conversation_heading"].winfo_manager() == "grid"
    assert not app.widgets["workspace_footer"].winfo_manager()
    assert not any(label.cget("text") == "下一步" for label in app._conversation_labels)
    for name in ("task_summary_button", "settings_button", "conversation_scrollbar"):
        assert app.widgets[name].cget("bg") == bg
    assert app.widgets["conversation_composer"].cget("bg") == bg
    assert not any(element == "Notebook.client" for element, _ in tk.ttk.Style(app.root).layout("Flow.TNotebook"))
    app.show_settings()
    app.root.update_idletasks()
    assert app.widgets["settings_save_button"].winfo_class() == "TButton"
    app.return_from_settings()
    assert set(app._question_inputs) == {"q1", "q2", "q3"}


@pytest.mark.parametrize("failed", [False, True])
def test_completion_save_waits_for_all_stream_metadata_without_flushing_animation(app, tmp_path, monkeypatch, failed):
    app.widgets["task_text"].insert("1.0", "目标")
    app._sync_input()
    app.root.after_cancel(app._response_after)
    app._response_after = None
    delivered = []
    path = tmp_path / "complete.json"
    def operation():
        publish("start", id="race", model="fixture", protocol="openai_chat_completions")
        for _ in range(3000):
            publish("reasoning", id="race", text="思考👩\u200d💻")
        if failed:
            raise RuntimeError("synthetic failure after partial stream")
        publish("end", id="race")
    def save_on_completion(_):
        delivered.append(True)
        assert app._trace_records["race"]["status"] == ("failed" if failed else "done")
        assert app._trace_widgets["race"].writer.pending
        save_session(app.session, path)
    app._submit(operation, save_on_completion, save_on_completion)
    _wait(lambda: not app.completions.empty())
    _drain_completions(app)  # Deliberately dispatch business completion first.
    assert not delivered
    app._poll_response_events()
    _wait(lambda: bool(delivered), app.root)
    loaded = load_session(path)
    assert loaded.control["response_traces"][0]["reasoning"] == "思考👩\u200d💻"*3000
    monkeypatch.setattr("tkinter.filedialog.askopenfilename", lambda **_: str(path))
    app.open_session()
    assert app.session.to_dict() == loaded.to_dict()
    assert not app._response_deliveries


def test_all_inline_questions_allow_out_of_order_answers_and_one_model_call(app, monkeypatch):
    app.widgets["task_text"].insert("1.0", "重做UI")
    app._sync_input()
    app.session.pending_questions = questions()
    app.refresh()
    assert set(app._question_inputs) == {"q1", "q2", "q3"}
    calls = []
    monkeypatch.setattr(app, "start_analysis", lambda: calls.append(build_m1_input(app.session, "combined")))
    app._question_inputs["q1"].insert("1.0", "尚未提交的第一题")
    for key, value in [("q3", "第三题"), ("q2", "第二题"), ("q1", "尚未提交的第一题")]:
        if key != "q1":
            app._question_inputs[key].insert("1.0", value)
        app.root.update()
        app._conversation_buttons["submit:"+key].invoke()
        if key != "q1":
            assert not calls
            assert app._question_inputs["q1"].get("1.0", "end-1c") == "尚未提交的第一题"
    assert len(calls) == 1
    assert [(a["question_id"], a["answer_text"]) for a in calls[0]["state"]["question_history"]] == [
        ("q3", "第三题"), ("q2", "第二题"), ("q1", "尚未提交的第一题")]
    assert app.session.confirmed_requirements_version is None


def test_question_draft_survives_theme_refresh_and_empty_submit_is_disabled(app):
    app.widgets["task_text"].insert("1.0", "目标")
    app._sync_input()
    app.session.pending_questions = questions()
    app.refresh()
    assert str(app._conversation_buttons["submit:q2"]["state"]) == "disabled"
    app._question_inputs["q2"].insert("1.0", "中英文👩\u200d💻草稿")
    app.preferences["composer_theme"] = "dark"
    app.status_var.set("刷新状态")
    app.refresh()
    assert app._question_inputs["q2"].get("1.0", "end-1c") == "中英文👩\u200d💻草稿"
    assert str(app._conversation_buttons["submit:q2"]["state"]) == "normal"
    assert app._question_inputs["q2"].cget("bg") == "#262626"


def test_markdown_headers_render_as_headers_not_literal_markers(tk_root):
    text = MarkdownText(tk_root, "# 总目标\n## **需求**\n副标题\n---\n<h1>另一个标题</h1>\n```text\n# 代码\n```\n正文 `code`")
    try:
        content = text.get("1.0", "end-1c")
        assert "# 总目标" not in content and "总目标" in content
        assert text.tag_ranges("h1") and text.tag_ranges("h2")
        assert "h2" in text.tag_names("2.0") and "bold" in text.tag_names("2.0")
        assert "# 代码" in content and "code" in text.tag_names("5.0")
    finally:
        text.destroy()


def test_template_sections_have_visual_hierarchy_without_changing_plain_prompt(tk_root):
    source = "根据以下任务说明完成工作。\n\n任务背景与目标\n任务：生成方案\n\n工作步骤\n1. 核对目标"
    text = MarkdownText(tk_root, source, section_titles=PROMPT_SECTIONS)
    try:
        assert text.get("1.0", "end-1c").rstrip() == source
        assert "h2" in text.tag_names("3.0") and "h2" in text.tag_names("6.0")
    finally:
        text.destroy()


def test_long_real_tk_thought_does_not_block_heartbeat_and_refresh_retains_writer(app):
    app.widgets["task_text"].insert("1.0", "目标")
    app._sync_input()
    scope, token = app._session_tasks, app._session_instance_token
    def event(kind, **values):
        app._response_events.put((scope, token, None, {"event": kind, "id": "trace", "operation": "op", **values}))
    event("start", model="fixture", protocol="openai_chat_completions", activities=[["读取已确认要求", "3 项"]])
    source = "第一段🧠e\u0301👩\u200d💻\n\n第二段\n\n" * 1200
    event("reasoning", text=source)
    _wait(lambda: "trace" in app._trace_widgets, app.root)
    widget = app._trace_widgets["trace"]
    writer = widget.writer
    assert not writer.finished
    app.status_var.set("其它控件仍可更新")
    app.refresh()
    assert app._trace_widgets["trace"].writer is writer
    event("end")
    beats = []
    def heartbeat():
        beats.append(time.monotonic())
        if writer.pending:
            app.root.after(20, heartbeat)
    app.root.after(20, heartbeat)
    _wait(lambda: writer.finished and not writer.pending, app.root, timeout=8)
    assert len(beats) >= 5
    assert widget.thought.get("1.0", "end-1c") == source.replace("\n\n", "\n")
    assert writer.frames > 10
    assert not app.callback_errors


@pytest.mark.parametrize("switch", ["new", "open"])
def test_late_stream_events_are_discarded_after_conversation_switch(app, tmp_path, monkeypatch, switch):
    app.widgets["task_text"].insert("1.0", "旧目标")
    app._sync_input()
    entered, release = Event(), Event()
    def operation():
        publish("start", id="old", model="fixture", protocol="openai_chat_completions")
        publish("reasoning", id="old", text="早期思考")
        entered.set()
        assert release.wait(4)
        publish("reasoning", id="old", text="迟到思考")
        publish("end", id="old")
    try:
        app._submit(operation, lambda _: None, lambda exc: app.status_var.set(str(exc)))
        assert entered.wait(2)
        _wait(lambda: "old" in app._trace_widgets, app.root)
        old_writer = app._trace_widgets["old"].writer
        if switch == "new":
            app.new_session()
        else:
            path = save_session(app.session, tmp_path / "session.json")
            monkeypatch.setattr("tkinter.filedialog.askopenfilename", lambda **_: str(path))
            app.open_session()
        before = deepcopy(app.session.control.get("response_traces", []))
        assert old_writer.closed
        release.set()
        _wait(lambda: not app._background_futures, app.root)
        _drain_completions(app)
        # Pump response queue as well as completion queue.
        _wait(lambda: app._response_events.empty(), app.root)
        assert app.session.control.get("response_traces", []) == before
        assert "迟到思考" not in str(before)
    finally:
        release.set()


def test_reasoning_is_saved_for_display_but_not_in_m1_payload(app, tmp_path):
    app.widgets["task_text"].insert("1.0", "目标")
    app._sync_input()
    record = {"id": "saved", "status": "done", "elapsed": 1.2, "reasoning": "DISPLAY_ONLY_SENTINEL",
              "activities": [["汇总用户回答", "2 条"]]}
    app.session.control["response_traces"] = [record]
    path = save_session(app.session, tmp_path / "session.json")
    loaded = load_session(path)
    assert loaded.control["response_traces"] == [record]
    assert "DISPLAY_ONLY_SENTINEL" not in json.dumps(build_m1_input(loaded, "req"))
    install_session(app, loaded)
    trace = app._trace_widgets["saved"]
    assert "已完成" in trace.header.cget("text")
    assert not hasattr(trace, "copy")


def test_response_failure_has_guidance_and_complete_debug_chain_without_auto_save(app):
    app.widgets["task_text"].insert("1.0", "目标")
    app._sync_input()
    def operation():
        publish("start", id="failed", model="fixture", protocol="openai_chat_completions")
        publish("reasoning", id="failed", text="已有思考")
        try:
            raise OSError("underlying synthetic failure")
        except OSError as exc:
            raise RuntimeError("outer synthetic failure") from exc
    app._submit(operation, lambda _: pytest.fail("unexpected success"), lambda exc: app.status_var.set(str(exc)))
    _wait(lambda: "failed" in app._trace_widgets and app._trace_records["failed"]["status"] == "failed", app.root)
    assert "重试" in app._trace_widgets["failed"].note.cget("text")
    assert app._trace_records["failed"]["reasoning"] == "已有思考"
    assert not list(app.runtime_log.directory.glob("*.log"))
    app.debug_console_enabled_var.set(True)
    app.set_debug_console_enabled()
    app.debug_console.save_button.invoke()
    text = app.runtime_log.path.read_text(encoding="utf-8")
    assert "Response trace started" in text and "Background operation failed" in text
    assert "OSError" in text and "RuntimeError" in text and "direct cause" in text


@pytest.mark.parametrize("transport_finished", [False, True])
def test_explicit_delivery_cancel_stops_typing_even_after_transport_end(app, monkeypatch, transport_finished):
    install_session(app, confirmed_plan_session())
    candidate, _ = _candidate()
    _set_candidate_batch(app, candidate)
    entered, release = Event(), Event()
    class Client(_DeliveryUiClient):
        def complete_json(self, *args):
            publish("start", id="delivery", model="fixture", protocol="openai_chat_completions")
            publish("reasoning", id="delivery", text="初步思考\n"*3000)
            if transport_finished:
                publish("end", id="delivery")
            entered.set()
            assert release.wait(4)
            publish("reasoning", id="delivery", text="迟到内容")
            publish("end", id="delivery")
            return super().complete_json(*args)
    _configure_delivery_client(app, monkeypatch, Client())
    try:
        app.widgets["skill_analyze_button"].invoke()
        assert entered.wait(2)
        _wait(lambda: "delivery" in app._trace_widgets, app.root)
        trace = app._trace_widgets["delivery"]
        app.cancel_delivery_request()
        assert trace.writer.closed and trace._indicator_after is None
        assert trace.record["status"] == "cancelled"
        assert "已取消" in trace.thinking_button.cget("text")
        before = trace.record["reasoning"]
        release.set()
        _wait(lambda: not app._background_futures and app._response_events.empty(), app.root)
        assert trace.record["reasoning"] == before and "迟到内容" not in before
        assert not app.delivery_busy
    finally:
        release.set()
