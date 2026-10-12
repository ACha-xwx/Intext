"""Demand review is visible in the conversation once the interview is complete."""
from promptsmith.conversation import conversation_cards
from tests.test_conversation_workspace import app, install_session
from tests.test_final_delivery import confirmed_plan_session


def test_completed_interview_has_review_table_in_timeline_without_top_entry(app):
    session = confirmed_plan_session()
    session.confirmed_requirements_version = None
    session.plan = type(session).new().plan
    session.last_next_action = "review_requirements"
    install_session(app, session)
    tree = app.widgets.get("conversation_requirements_tree")
    assert tree is not None and tree.winfo_exists()
    assert tree.winfo_toplevel() is app.root
    assert "accept_requirement" not in app._conversation_buttons
    assert "confirm_requirements" in app._conversation_buttons
    assert "requirements" in app._conversation_frames


def test_interview_questions_hide_requirements_until_ready():
    session = confirmed_plan_session()
    session.confirmed_requirements_version = None
    session.plan = type(session).new().plan
    session.last_next_action = "ask"
    session.last_model_judgment = None
    session.pending_questions = [{"question_id": "q-ui", "gap_id": None, "field": "audience",
                                 "scope": "用户", "text": "界面给谁使用？", "options": [], "depends_on": []}]
    assert not any(card["kind"] == "requirements" for card in conversation_cards(session))
