"""Stage controls through the existing desktop and production DOM boundaries."""
from copy import deepcopy

import pytest

from promptsmith.finalization import build_final_draft
from promptsmith.web_workspace import WorkspaceController, view_stamp
from tests.test_conversation_workspace import app, install_session
from tests.test_final_delivery import confirmed_plan_session
from tests.test_frontend_review_regressions import browser, page, load


@pytest.mark.parametrize("with_result", [False, True])
def test_confirmed_plan_hidden_downstream_and_restored_on_back(app, page, with_result):
    session = confirmed_plan_session()
    if with_result:
        session.skill_state["status"] = "skipped"
        session.final_result = build_final_draft(session)
    install_session(app, session)
    controller = WorkspaceController(app)
    before = deepcopy(session.to_dict())
    snapshot = controller.snapshot()
    assert not any(card["kind"] == "plan" for card in snapshot["cards"])
    page.evaluate("s=>promptsmithView.applySnapshot(s)", snapshot)
    assert page.get_by_role("heading", name="一起核对方案", exact=True).count() == 0
    assert "edit_plan" not in snapshot["buttons"]

    controller.dispatch("button", {"key": "back_stage"}, view_stamp(app))
    review = controller.snapshot()
    assert any(card["kind"] == "plan" for card in review["cards"])
    page.evaluate("s=>promptsmithView.applySnapshot(s)", review)
    assert page.get_by_role("heading", name="一起核对方案", exact=True).is_visible()
    assert page.get_by_role("button", name="展开完整方案并编辑", exact=True).is_enabled()
    controller.dispatch("button", {"key": "continue_stage"}, view_stamp(app))
    assert not any(card["kind"] == "plan" for card in controller.snapshot()["cards"])
    for key in ("requirements", "plan", "skill_state", "final_result", "pending_requests", "question_history"):
        assert session.to_dict()[key] == before[key]


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_integration_cancel_is_inline_and_footer_stays_clear(page, theme):
    state = load(page, "skills", theme=theme, locked=True)
    state["buttons"]["cancel_request"] = {"text": "取消本次整合", "enabled": True}
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    cancel = page.locator("#timeline").get_by_role("button", name="取消本次整合", exact=True)
    assert cancel.count() == 1
    assert cancel.is_enabled()
    assert page.locator("footer").get_by_role("button", name="取消本次整合", exact=True).count() == 0
    assert page.get_by_role("button", name="停止生成", exact=True).is_enabled()
    cancel.click()
    page.wait_for_function("calls.some(c=>c.action==='button'&&c.data.key==='cancel_request')")

    state["locked"] = False
    del state["buttons"]["cancel_request"]
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    assert page.get_by_role("button", name="取消本次整合", exact=True).count() == 0
