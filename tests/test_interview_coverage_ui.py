"""Real Tk controls and synthetic model replies, with no external requests."""
import json
from copy import deepcopy

from promptsmith.m1 import build_m1_input, parse_m1_response, apply_m1_response, M1Assets
from promptsmith.storage import load_session, save_session
from tests.test_conversation_workspace import app, install_session, send
from tests.test_interview_coverage import TASK, batch_result, closed_interview
from tests.test_unknown_clarification import plan_with_new_unknowns
from promptsmith.session import SessionState


def test_seven_cards_submit_the_whole_group_once(app, monkeypatch, tmp_path):
    session = SessionState.new()
    session.set_task(TASK)
    payload = build_m1_input(session, "first")
    response = batch_result(payload)
    apply_m1_response(session, payload, response)
    install_session(app, session)
    requests = []
    monkeypatch.setattr(app, "start_analysis", lambda: requests.append(build_m1_input(app.session, "whole-batch")))
    for i in range(7):
        assert not any("访谈第" in label.cget("text") or "最多自动询问" in label.cget("text") for label in app._conversation_labels)
        send(app, f"第{i + 1}项回答")
        assert len(requests) == (1 if i == 6 else 0)
        if i == 2:
            install_session(app, load_session(save_session(app.session, tmp_path / "partial.json")))
    assert [row["answer_text"] for row in requests[0]["state"]["question_history"]] == [f"第{i + 1}项回答" for i in range(7)]
    assert app.session.control["interview_rounds_used"] == 1


def test_extra_round_button_grants_only_one_and_reappears_after_summary(app, monkeypatch):
    install_session(app, closed_interview())
    requests = []
    monkeypatch.setattr(app, "start_analysis", lambda: requests.append(build_m1_input(app.session, f"extra-{len(requests)}")))
    for used in (5, 6):
        assert app._primary_action().kind == "review_remaining_unknowns"
        assert app._conversation_focus_key == "interview_unknowns"
        assert not app.session.questions_for_review()
        assert any("是否需要继续询问" in label.cget("text") for label in app._conversation_labels)
        old_button = app._conversation_buttons["continue_interview"]
        old_token = app._conversation_token()
        old_button.invoke()
        assert len(requests) == used - 4
        assert app.session.control["interview_round_limit"] == used + 1
        app._conversation_action(old_token, lambda: requests.append("stale-click"))
        assert len(requests) == used - 4
        payload = requests[-1]
        result = batch_result(payload, count=1, suffix=str(used))
        apply_m1_response(app.session, payload, parse_m1_response(json.dumps(result), payload, M1Assets.load().output_schema))
        app.refresh()
        assert app.session.control["interview_rounds_used"] == used + 1
        assert "continue_interview" not in app._conversation_buttons
        for q in app.session.questions_for_review():
            app.session.record_question(q["question_id"], "unsure")
        payload = build_m1_input(app.session, f"summary-{used}")
        result = batch_result(payload, count=1, suffix=f"later-{used}")
        apply_m1_response(app.session, payload, parse_m1_response(json.dumps(result), payload, M1Assets.load().output_schema))
        app.refresh()
        assert "continue_interview" in app._conversation_buttons
    assert not app.dialogs


def test_post_plan_unknowns_do_not_open_interview_closing_even_at_limit(app, monkeypatch, tmp_path):
    session = plan_with_new_unknowns()
    session.control["interview_rounds_used"] = 5
    install_session(app, session)
    requests = []
    monkeypatch.setattr(app, "start_analysis", lambda: requests.append("model"))
    unknowns = deepcopy(session.plan["content"]["unresolved_items"])
    if app._workspace_popover is None or app._workspace_popover.kind != "plan":
        app.toggle_plan_review()
    assert str(app._conversation_buttons["confirm_plan"]["state"]) == "normal"
    assert "defer_interview_unknowns" not in app._conversation_buttons
    assert "continue_interview" not in app._conversation_buttons
    assert not requests
    assert session.plan["status"] == "draft"
    assert session.plan["content"]["unresolved_items"] == unknowns
    assert not session.questions_for_review(respect_interview_limit=False)
    install_session(app, load_session(save_session(session, tmp_path / "stopped.json")))
    assert "continue_interview" not in app._conversation_buttons
    if app._workspace_popover is None or app._workspace_popover.kind != "plan":
        app.toggle_plan_review()
    assert str(app._conversation_buttons["confirm_plan"]["state"]) == "normal"
    app._conversation_buttons["confirm_plan"].invoke()
    assert app.session.plan["status"] == "confirmed"
    assert "交付形式未确认" in app.session.final_result["canonical_body"]
    assert not requests and not app.dialogs


def test_continuation_is_disabled_until_last_answers_are_organized(app):
    session = closed_interview()
    source = session._add_source("已有回答等待整理")
    session.question_history.append({"question_id": "q-supplement", "answer_id": "a-supplement", "field": "supplement",
        "scope": "整体任务", "text": "补充", "disposition": "answered", "answer_source_id": source,
        "answer_text": "已有回答等待整理", "assessment_status": "pending", "gap_id": None})
    install_session(app, session)
    assert str(app._conversation_buttons["continue_interview"]["state"]) == "disabled"
    assert str(app._conversation_buttons["defer_interview_unknowns"]["state"]) == "disabled"
    assert app._primary_action().kind == "analyze_answer"
