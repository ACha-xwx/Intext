"""Actual Tk planning boundaries; synthetic replies and isolated data."""
from copy import deepcopy

from promptsmith.m1 import build_m1_input
from promptsmith.storage import load_session, save_session
from tests.test_conversation_workspace import app, install_session, send
from tests.test_unknown_clarification import plan_with_new_unknowns, legacy_plan_question


def test_plan_unknowns_do_not_make_question_cards_or_disable_confirmation(app):
    session=plan_with_new_unknowns()
    install_session(app,session)
    assert app._primary_action().kind!="focus_question"
    assert not app._question_inputs
    assert "active_question" not in app._conversation_frames
    if app._workspace_popover is None or app._workspace_popover.kind != "plan":
        app.toggle_plan_review()
    assert str(app._conversation_buttons["confirm_plan"]["state"])=="normal"
    assert str(app._conversation_buttons["find_skills"]["state"])=="normal"
    unknowns=deepcopy(session.plan["content"]["unresolved_items"])
    assert session.plan["status"]=="draft"
    app._conversation_buttons["confirm_plan"].invoke()
    assert session.plan["status"]=="confirmed"
    assert session.plan["content"]["unresolved_items"]==unknowns
    assert "交付形式未确认" in session.final_result["canonical_body"]
    assert "运行说明尚未提供" in session.final_result["canonical_body"]
    assert not session.question_history and not app.dialogs


def test_direct_post_plan_supplement_reassesses_once_and_invalidates_old_plan(app,monkeypatch):
    install_session(app,plan_with_new_unknowns())
    requests=[]
    monkeypatch.setattr(app,"start_analysis",lambda:requests.append(build_m1_input(app.session,"supplement")))
    send(app,"只需要完整源码，视觉参考由我交给下游")
    assert len(requests)==1
    assert app.session.plan["status"]=="stale"
    assert app.session.confirmed_requirements_version is None
    assert requests[0]["state"]["question_history"][-1]["answer_text"]=="只需要完整源码，视觉参考由我交给下游"
    assert not app._question_inputs and not app.dialogs


def test_old_automatic_queue_reloads_into_plan_without_asking_or_changing_history(app,tmp_path):
    session=plan_with_new_unknowns()
    session.pending_questions=[legacy_plan_question(session)]
    reopened=load_session(save_session(session,tmp_path/"legacy-queue.json"))
    install_session(app,reopened)
    assert not app._question_inputs and not reopened.question_history
    if app._workspace_popover is None or app._workspace_popover.kind != "plan":
        app.toggle_plan_review()
    assert str(app._conversation_buttons["confirm_plan"]["state"])=="normal"
    app._conversation_buttons["confirm_plan"].invoke()
    assert reopened.plan["status"]=="confirmed"
    assert "运行说明尚未提供" in reopened.final_result["canonical_body"]


def test_confirmed_plan_can_enter_skill_and_final_paths_without_post_plan_questions(app,monkeypatch):
    session=plan_with_new_unknowns()
    session.confirm_plan_preview(session.plan_preview())
    install_session(app,session)
    searches=[]
    monkeypatch.setattr(app,"_submit",lambda *args:searches.append(args))
    app.find_skills()
    assert len(searches)==1 and app._skill_search_busy
    assert not app._question_inputs and not app.dialogs
