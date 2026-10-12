"""Task prompt sufficiency, keyboard input and full question reflow; offline."""
import json
import time
from copy import deepcopy
import tkinter.font as tkfont

import pytest

from promptsmith.m1 import M1Assets, build_m1_input, parse_m1_response, apply_m1_response, m1_system_prompt
from promptsmith.m2 import M2Assets
from promptsmith.session import SessionState
from promptsmith.storage import load_session, save_session
from tests.test_m1_model_authority_v11 import _base
from tests.test_interview_coverage import TASK
from tests.test_conversation_workspace import app, install_session
from tests.test_response_workspace import questions
from tests.test_ui_refinement import show, pump
from tests.test_unknown_clarification import plan_with_new_unknowns


@pytest.mark.parametrize("used", [0, 1, 2, 4])
def test_sufficient_judgment_ends_before_limit_keeps_unknowns_and_does_not_confirm(used, tmp_path, caplog):
    session = SessionState.new()
    session.set_task(TASK)
    session.control["interview_rounds_used"] = used
    payload = build_m1_input(session, "sufficient")
    result = _base(payload)
    result["category"]["primary"] = "coding"
    result["gaps"] = [{"gap_id": "g-material", "field": "existing_code", "scope": "源码材料",
                       "description": "用户将在下游执行时提供源码和风格文件。", "importance": "can_defer",
                       "origin": "material_unavailable", "source_refs": [], "depends_on": []}]
    result["model_judgment"] = {"answer_assessment": "sufficient", "continue_interview": False,
                                "critical_gap_ids": [], "confidence": "high", "reason": "足以写提示词"}
    with caplog.at_level("INFO"):
        parsed = parse_m1_response(json.dumps(result), payload, M1Assets.load().output_schema)
        apply_m1_response(session, payload, parsed)
    assert not session.questions_for_review(respect_interview_limit=False)
    assert session.control["interview_rounds_used"] == used
    assert session.gaps[0]["origin"] == "material_unavailable"
    assert session.confirmed_requirements_version is None
    assert "Interview complete: sufficient information" in caplog.text
    reopened = load_session(save_session(session, tmp_path / "sufficient.json"))
    assert not reopened.questions_for_review(respect_interview_limit=False)
    reopened.record_supplement("新增一项尚未分析的要求")
    assert reopened.questions_for_review(respect_interview_limit=False)  # Stale assessment is not a bypass.


def test_all_active_prompts_define_downstream_files_and_no_minimum_round_count():
    assets = M1Assets.load()
    for mode in ("full", "incremental", "compact_retry"):
        prompt = m1_system_prompt(assets.system_prompt, mode=mode)
        assert "不设最低轮数" in prompt
        assert "不要求用户给本程序上传/粘贴实际文件" in prompt
        assert "EXE打包" in prompt
        assert "访谈一般在 4～5 轮" not in prompt
        assert "不显示访谈轮数" in prompt
    plan = M2Assets.load().system_prompt
    assert "不要求PromptSmith重新访谈" in plan
    assert "程序会向用户逐项展示问题" not in plan


def setup_questions(app):
    app.widgets["task_text"].insert("1.0", "重做UI")
    app._sync_input()
    app.session.pending_questions = questions()
    app.refresh()
    show(app)


def press(app, widget, sequence):
    widget.focus_force()
    pump(app, .03)
    widget.event_generate(sequence)
    pump(app, .03)


def test_enter_submits_target_shift_enter_newline_and_batch_is_summarized_once(app, monkeypatch):
    setup_questions(app)
    calls = []
    monkeypatch.setattr(app, "start_analysis", lambda: calls.append(build_m1_input(app.session, "combined")))
    widget = app._question_inputs["q3"]
    widget.insert("1.0", "第一行👩\u200d💻")
    widget.mark_set("insert", "end-1c")
    press(app, widget, "<Shift-Return>")
    assert widget.get("1.0", "end-1c") == "第一行👩\u200d💻\n"
    assert not app.session.question_history and not calls
    widget.insert("insert", "第二行")
    press(app, widget, "<Return>")
    assert app.session.question_history[-1]["question_id"] == "q3"
    assert app.session.question_history[-1]["answer_text"] == "第一行👩\u200d💻\n第二行"
    assert not calls
    for key in ("q1", "q2"):
        widget = app._question_inputs[key]
        widget.insert("1.0", key + "回答")
        press(app, widget, "<Return>")
    assert len(calls) == 1
    assert [q["question_id"] for q in calls[0]["state"]["question_history"]] == ["q3", "q1", "q2"]


def test_empty_or_busy_enter_does_not_send_or_insert_newline(app, monkeypatch):
    setup_questions(app)
    calls = []
    monkeypatch.setattr(app, "start_analysis", lambda: calls.append("model"))
    widget = app._question_inputs["q2"]
    widget.insert("1.0", " ")
    press(app, widget, "<Return>")
    assert widget.get("1.0", "end-1c") == " "
    widget.insert("1.0", "忙时保留")
    before = widget.get("1.0", "end-1c")
    app.busy = True
    press(app, widget, "<Return>")
    press(app, widget, "<Shift-Return>")
    assert widget.get("1.0", "end-1c") == before
    assert not app.session.question_history and not calls
    app.busy = False


def test_long_question_fits_real_column_on_initial_render_and_resize(app):
    show(app)
    app.widgets["task_text"].insert("1.0", "重做UI")
    app._sync_input()
    text = "请补充：现有源码尚未实际提供，界面结构、页面数量、入口方式与现有功能基线需待用户随提示词一并提供给下游AI读取；这里的文字应完整显示并按实际对话列宽换行。\n你希望如何安排这项内容？"
    rows = questions()
    rows[0]["text"] = text
    app.session.pending_questions = rows
    app.refresh()
    for width in (1440, 720, 1100):
        show(app, width)
        pump(app, .08)
        label = next(label for label in app._conversation_labels if label.cget("text") == text)
        assert label.winfo_reqwidth() <= label.winfo_width()
        assert label.winfo_reqheight() <= label.winfo_height()
        font = tkfont.Font(app.root, font=label.cget("font"))
        assert label.winfo_height() >= font.metrics("linespace") * 3
        assert "下游AI读取" in label.cget("text")
        assert not any("访谈第" in label.cget("text") or "最多自动询问" in label.cget("text") for label in app._conversation_labels)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_plan_review_lives_inline_with_all_content_actions(app, theme, caplog):
    app.preferences["composer_theme"] = theme
    session = plan_with_new_unknowns()
    install_session(app, session)
    show(app)
    assert "plan" in app._conversation_frames
    assert "conversation_hint" not in app.widgets and "workspace_status" not in app.widgets
    assert "confirm_plan" in app._conversation_buttons
    original = deepcopy(session.to_dict())
    assert "plan_review_button" not in app.widgets
    assert "edit_plan_goal" not in app._conversation_buttons
    assert session.to_dict() == original
    reading = app.widgets["conversation_plan_reading"]
    assert reading.winfo_toplevel() is app.root
    text = reading.get("1.0", "end-1c")
    assert "现有项目代码和运行说明尚未提供" in text and "交付形式未确认" in text
    assert "步骤" not in text.splitlines()
    for key in ("edit_plan", "review_plan", "confirm_plan", "find_skills"):
        assert app._conversation_buttons[key].winfo_toplevel() is app.root
    app._conversation_buttons["confirm_plan"].invoke()
    assert session.plan["status"] == "confirmed" and session.final_result["status"] == "draft"
    assert app._workspace_popover is None
    assert "confirm_plan" not in app._conversation_buttons
    assert any("方案状态：已确认" == label.cget("text") for label in app._conversation_labels)


def test_plan_inline_empty_stale_busy_and_summary_preserve_business_state(app):
    show(app, 720)
    app.toggle_plan_review()
    assert "conversation_plan_reading" not in app.widgets
    assert "plan" not in app._conversation_frames
    install_session(app, plan_with_new_unknowns())
    app.busy = True
    app.refresh()
    assert str(app._conversation_buttons["confirm_plan"]["state"]) == "disabled"
    app.busy = False
    app.session.record_supplement("增加新的要求")
    app.refresh()
    assert "confirm_plan" not in app._conversation_buttons
    assert str(app._conversation_buttons["edit_plan"]["state"]) == "disabled"
    assert any("旧方案已过期" in label.cget("text") for label in app._conversation_labels)
    before = app.session.to_dict()
    app.toggle_conversation_summary()
    assert app._workspace_popover.kind == "summary"
    app.toggle_requirements_review()
    assert app._workspace_popover.kind == "summary"
    assert app.session.to_dict() == before
