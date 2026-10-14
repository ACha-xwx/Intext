"""Skill controls follow the current review step, without discarding selections."""
from copy import deepcopy

import pytest
from playwright.sync_api import expect

from promptsmith.conversation import conversation_cards
from promptsmith.finalization import build_final_draft, confirm_final, stage_final_draft
from promptsmith.storage import load_session, save_session
from promptsmith.web_workspace import WorkspaceController, view_stamp
from tests.test_conversation_workspace import app, install_session
from tests.test_final_delivery import confirmed_plan_session
from tests.test_frontend_review_regressions import browser, page, load
from tests.test_ui_delivery_interactions import _candidate


def skill_session():
    session = confirmed_plan_session()
    basis = {"task_id": session.task_id, "requirement_version": session.requirement_version,
             "plan_id": session.plan["plan_id"], "plan_version": session.plan["plan_version"]}
    _, binding = _candidate()
    session.set_skill_state(status="selected", basis=basis, bindings=[binding])
    return session


def generate_prompt(session):
    draft = build_final_draft(session)
    stage_final_draft(session, draft, expected_basis=draft["basis"])


@pytest.mark.parametrize("confirmed", [False, True])
def test_prompt_hides_skill_selection_and_previous_step_restores_it(confirmed):
    session = skill_session()
    assert any(card["kind"] == "skills" for card in conversation_cards(session))
    generate_prompt(session)
    if confirmed:
        confirm_final(session)
    before = deepcopy(session.to_dict())
    cards = conversation_cards(session)
    assert any(card["kind"] == "result" for card in cards)
    assert not any(card["kind"] == "skills" for card in cards)

    session.navigate_workspace("previous")
    assert any(card["kind"] == "skills" for card in conversation_cards(session))
    assert not any(card["kind"] == "result" for card in conversation_cards(session))
    session.navigate_workspace("next")
    assert not any(card["kind"] == "skills" for card in conversation_cards(session))
    for key in ("skill_state", "final_result", "plan", "pending_requests"):
        assert session.to_dict()[key] == before[key]


def test_saved_prompt_keeps_selection_hidden_after_reopening(tmp_path):
    session = skill_session()
    generate_prompt(session)
    restored = load_session(save_session(session, tmp_path / "session.json"))
    assert restored.skill_state == session.skill_state
    assert restored.final_result["canonical_body"] == session.final_result["canonical_body"]
    assert not any(card["kind"] == "skills" for card in conversation_cards(restored))


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_desktop_and_live_dom_remove_skill_controls_on_generation(app, page, theme, caplog):
    session = skill_session()
    install_session(app, session)
    controller = WorkspaceController(app)
    load(page, "skills", theme=theme)
    snapshot = controller.snapshot()
    snapshot["theme"] = theme
    page.evaluate("s=>promptsmithView.applySnapshot(s)", snapshot)
    expect(page.locator(".skill-table")).to_have_count(1)

    with caplog.at_level("DEBUG", logger="promptsmith.conversation"):
        generate_prompt(session)
        app.refresh()
        snapshot = controller.snapshot()
        snapshot["theme"] = theme
        page.evaluate("s=>promptsmithView.applySnapshot(s)", snapshot)
        expect(page.locator(".skill-table")).to_have_count(0)
        expect(page.get_by_role("button", name="查找本地 Skill", exact=True)).to_have_count(0)
        expect(page.get_by_role("button", name="继续联网查找", exact=True)).to_have_count(0)
        expect(page.get_by_role("button", name="用已选 Skill 直接生成提示词", exact=True)).to_have_count(0)
        assert "skills" not in app._conversation_frames
        assert "copy" in snapshot["buttons"] and "export" in snapshot["buttons"]
        assert any("skills_visible=False" in record.getMessage() for record in caplog.records)

        controller.dispatch("button", {"key": "back_stage"}, view_stamp(app))
        snapshot = controller.snapshot()
        snapshot["theme"] = theme
        page.evaluate("s=>promptsmithView.applySnapshot(s)", snapshot)
        expect(page.locator(".skill-table")).to_have_count(1)
        assert "skills" in app._conversation_frames
        controller.dispatch("button", {"key": "continue_stage"}, view_stamp(app))
        snapshot = controller.snapshot()
        snapshot["theme"] = theme
        page.evaluate("s=>promptsmithView.applySnapshot(s)", snapshot)
        expect(page.locator(".skill-table")).to_have_count(0)
        count = len([record for record in caplog.records if "Stage controls updated" in record.getMessage()])
        app.refresh()
        controller.snapshot()
        assert len([record for record in caplog.records if "Stage controls updated" in record.getMessage()]) == count
