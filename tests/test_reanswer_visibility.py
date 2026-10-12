"""Visible history actions through the desktop snapshot and production DOM."""
import pytest

from promptsmith.web_workspace import WorkspaceController
from promptsmith.storage import load_session, save_session
from tests.test_conversation_workspace import app, install_session
from tests.test_frontend_review_regressions import browser, page, load
from tests.test_response_workspace import questions


def answer_one(app):
    app.widgets["task_text"].insert("1.0", "准备奖学金答辩提示词")
    app._sync_input()
    app.session.pending_questions = questions()
    app.session.record_question("q1", "answered", "我是本科生")
    app.refresh()


def test_history_action_disappears_when_answers_are_submitted_to_model(app, page):
    answer_one(app)
    controller = WorkspaceController(app)
    snapshot = controller.snapshot()
    page.evaluate("s=>promptsmithView.applySnapshot(s)", snapshot)
    assert page.get_by_role("button", name="补答这个问题", exact=True).count() == 1

    # Public session entry records the request basis; no model call is made.
    app.session.begin_request("submitted-answers")
    app.refresh()
    snapshot = controller.snapshot()
    page.evaluate("s=>promptsmithView.applySnapshot(s)", snapshot)
    assert page.get_by_role("button", name="补答这个问题", exact=True).count() == 0
    assert page.get_by_text("我是本科生", exact=True).is_visible()
    assert not any(key.startswith("question:") for key in app._conversation_buttons)


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("font", [9, 12, 18])
def test_remaining_reanswer_icon_is_centered_in_its_glass_circle(page, theme, font):
    for text in ("本科生", "我的科研经历比较多，希望重点突出研究成果。\n同时保留比赛和成绩方面的背景。"):
        load(page, theme=theme, font_size=font, cards=[
            {"key": "answer:a1", "kind": "user", "question_id": "q1",
             "text": text, "can_reanswer": True},
        ])
        action = page.get_by_role("button", name="补答这个问题", exact=True)
        circle, glyph, bubble = action.bounding_box(), action.locator("svg").bounding_box(), page.locator(".bubble").bounding_box()
        assert circle["width"] == circle["height"]
        for axis, dimension in (("x", "width"), ("y", "height")):
            assert abs(circle[axis] + circle[dimension] / 2 - glyph[axis] - glyph[dimension] / 2) <= .5
        assert abs(circle["y"] + circle["height"] / 2 - bubble["y"] - bubble["height"] / 2) <= .5


@pytest.mark.parametrize("outcome", ["processed", "failed", "cancelled"])
def test_submitted_history_stays_read_only_after_restore_but_new_answers_can_change(app, page, tmp_path, outcome):
    answer_one(app)
    version = app.session.requirement_version
    if outcome == "processed":
        app.session.question_history[0]["assessment_status"] = "applied"
    elif outcome == "failed":
        app.session.api_runs.append({"request_id": "old-request", "base_version": version, "status": "api_error"})
    else:
        app.session.control["response_traces"] = [
            {"id": "old-trace", "history_count": 1, "status": "cancelled", "reasoning": "", "elapsed": 1},
        ]
    app.session.record_question("q2", "answered", "面向专业评审")
    restored = load_session(save_session(app.session, tmp_path / "history.json"))
    install_session(app, restored)
    snapshot = WorkspaceController(app).snapshot()
    page.evaluate("s=>promptsmithView.applySnapshot(s)", snapshot)
    historical = page.locator(".message.user").filter(has_text="我是本科生")
    current = page.locator(".message.user").filter(has_text="面向专业评审")
    assert historical.get_by_role("button", name="补答这个问题", exact=True).count() == 0
    assert current.get_by_role("button", name="补答这个问题", exact=True).count() == 1
    assert set(app._conversation_buttons) >= {"question:" + restored.question_history[1]["answer_id"]}
    before = restored.to_dict()
    app.refresh()
    assert restored.to_dict() == before


def test_skipped_unsent_question_can_still_be_reopened_and_diagnostics_do_not_repeat(app, page, caplog):
    answer_one(app)
    app.session.record_question("q2", "skipped")
    app.refresh()
    snapshot = WorkspaceController(app).snapshot()
    page.evaluate("s=>promptsmithView.applySnapshot(s)", snapshot)
    skipped = page.locator(".message.user").filter(has_text="先跳过")
    skipped.get_by_role("button", name="补答这个问题", exact=True).click()
    page.wait_for_function("calls.some(c=>c.action==='reanswer'&&c.data.id==='q2')")
    caplog.clear()
    for _ in range(3):
        app.refresh()
        WorkspaceController(app).snapshot()
    assert not [r for r in caplog.records if "Historical answer actions updated" in r.message]
