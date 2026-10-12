"""Full inline plan review through production cards, bridge, Tk and Chromium."""
from copy import deepcopy

from promptsmith.conversation import conversation_cards
from promptsmith.web_workspace import WorkspaceController
from tests.test_conversation_workspace import app, install_session
from tests.test_final_delivery import confirmed_plan_session
from tests.test_frontend_review_regressions import browser, page, load
from promptsmith.session import SessionState
from promptsmith.web_workspace import view_stamp
from promptsmith.finalization import build_final_draft
from promptsmith.session import SessionStateError
import pytest


def test_back_from_plan_restores_review_without_requests_and_survives_save(app, monkeypatch, tmp_path):
    session = confirmed_plan_session()
    session.plan["status"] = "draft"
    session.plan["confirmed_plan_version"] = None
    install_session(app, session)
    calls = []
    monkeypatch.setattr(app, "_submit", lambda *args: calls.append(args))
    before = deepcopy(session.to_dict())
    controller = WorkspaceController(app)
    controller.dispatch("button", {"key": "back_stage"}, view_stamp(app))
    snapshot = controller.snapshot()
    assert any(c["kind"] == "requirements" and c["confirmed"] for c in snapshot["cards"])
    assert not any(c["kind"] == "plan" for c in snapshot["cards"])
    assert not calls
    for key in ("requirements", "requirement_version", "confirmed_requirements_version", "plan", "skill_state", "final_result", "question_history"):
        assert session.to_dict()[key] == before[key]
    from promptsmith.storage import save_session, load_session
    restored = load_session(save_session(session, tmp_path / "review-position.json"))
    install_session(app, restored)
    assert any(c["kind"] == "requirements" for c in controller.snapshot()["cards"])
    controller.dispatch("button", {"key": "continue_stage"}, view_stamp(app))
    assert any(c["kind"] == "plan" for c in controller.snapshot()["cards"])
    assert not any(c["kind"] == "requirements" for c in controller.snapshot()["cards"])
    assert not calls


@pytest.mark.parametrize("with_skills,expected", [(False, "plan"), (True, "skills")])
def test_result_back_uses_actual_route_and_primary_continues_existing_result(app, monkeypatch, with_skills, expected):
    session = confirmed_plan_session()
    session.skill_state["status"] = "selected" if with_skills else "skipped"
    session.final_result = build_final_draft(session)
    install_session(app, session)
    calls = []
    monkeypatch.setattr(app, "_submit", lambda *args: calls.append(args))
    controller = WorkspaceController(app)
    controller.dispatch("button", {"key": "back_stage"}, view_stamp(app))
    assert session.workspace_navigation()["stage"] == expected
    assert not any(c["kind"] == "result" for c in controller.snapshot()["cards"])
    app.run_primary_action()
    assert any(c["kind"] == "result" for c in controller.snapshot()["cards"])
    assert not calls


def test_review_edit_invalidates_downstream_and_old_continue_is_rejected(app, monkeypatch):
    session = confirmed_plan_session()
    session.final_result = build_final_draft(session)
    install_session(app, session)
    controller = WorkspaceController(app)
    calls = []
    monkeypatch.setattr(app, "_submit", lambda *args: calls.append(args))
    while session.workspace_navigation()["stage"] != "requirements":
        controller.dispatch("button", {"key": "back_stage"}, view_stamp(app))
    stamp = view_stamp(app)
    controller.dispatch("requirement_row", {"id": "r:r2"}, stamp)
    controller.dispatch("button", {"key": "edit_requirement"}, stamp)
    editor = controller.snapshot()["editor"]
    controller.dispatch("editor_save", {"id": editor["id"], "values": {"text": "十四天，每天一小时的完整学习计划"}}, stamp)
    assert session.requirements[1]["text"] == "十四天，每天一小时的完整学习计划"
    assert session.plan["status"] == session.final_result["status"] == "stale"
    assert session.confirmed_requirements_version is None
    assert "continue_stage" not in controller.snapshot()["buttons"]
    with pytest.raises(ValueError, match="内容已变化"):
        controller.dispatch("button", {"key": "continue_stage"}, stamp)
    assert not calls


def test_review_reaches_interview_without_inventing_questions():
    session = confirmed_plan_session()
    session.navigate_workspace("previous")  # Skill -> plan
    session.navigate_workspace("previous")  # Plan -> requirements
    session.navigate_workspace("previous")  # Requirements -> interview history
    cards = conversation_cards(session)
    assert not any(c["kind"] in {"requirements", "plan", "skills", "result", "question"} for c in cards)
    assert session.workspace_navigation()["next"] == "requirements"
    assert not session.workspace_navigation()["previous"]
    with pytest.raises(SessionStateError):
        session.navigate_workspace("previous")
    # Corrupt/old saved UI state cannot restore nonexistent downstream stages.
    session.control["workspace_navigation"]["stage"] = "arbitrary"
    assert session.workspace_navigation()["stage"] == "skills"


def test_bridge_rejects_stale_session_or_operation_before_cancelling(app):
    install_session(app, confirmed_plan_session())
    controller = WorkspaceController(app)
    snapshot = controller.snapshot()
    data = {"direction": "previous", "session": snapshot["session"], "scope": snapshot["stop_scope"], "stage": "skills"}
    for changed in ({"session": "old"}, {"scope": "old"}, {"stage": "plan"}, {"direction": "next"}):
        with pytest.raises(ValueError):
            controller.dispatch("navigate", dict(data, **changed), snapshot["stamp"])
        assert app.session.workspace_navigation()["stage"] == "skills"


def test_back_while_generating_cancels_and_rejects_late_response(app, monkeypatch):
    from threading import Event
    from promptsmith.api import ApiResult
    from tests.test_ui_session_cancellation import _wait, _drain_completions
    session = confirmed_plan_session()
    session.plan = SessionState.new().plan
    install_session(app, session)
    entered, release = Event(), Event()
    class Client:
        def complete_json(self, *_args):
            entered.set()
            assert release.wait(5)
            return ApiResult("{", 1, None, "late", "fixture")
    monkeypatch.setattr(app, "_client", lambda _config: Client())
    controller = WorkspaceController(app)
    try:
        app.start_plan_generation()
        assert entered.wait(2)
        snapshot = controller.snapshot()
        assert snapshot["buttons"]["back_stage"]["enabled"]
        controller.dispatch("navigate", {"direction": "previous", "stage": "plan", "session": snapshot["session"], "scope": snapshot["stop_scope"]}, snapshot["stamp"])
        assert not controller.snapshot()["locked"]
        assert any(c["kind"] == "requirements" for c in controller.snapshot()["cards"])
        release.set()
        _wait(lambda: not app._background_futures, app.root)
        _drain_completions(app)
        assert session.plan["content"] is None and not session.pending_requests and not session.errors
    finally:
        release.set()


def test_generated_plan_is_inline_and_confirmed_requirements_are_hidden(app):
    session = confirmed_plan_session()
    session.plan["status"] = "draft"
    session.plan["confirmed_plan_version"] = None
    install_session(app, session)
    snapshot = WorkspaceController(app).snapshot()
    assert any(c["kind"] == "plan" for c in snapshot["cards"])
    assert not any(c["kind"] == "requirements" for c in snapshot["cards"])
    assert "plan" in app._conversation_frames
    assert "plan_review_button" not in app.widgets
    assert "edit_plan_goal" not in snapshot["buttons"]
    assert {"edit_plan", "confirm_plan", "find_skills"} <= snapshot["buttons"].keys()
    text = next(c["text"] for c in snapshot["cards"] if c["kind"] == "plan")
    for section in ("受众：", "范围：", "交付物", "整体完成标准", "关键工作", "待补充事项", "AI 的可选建议"):
        assert section in text


def test_plan_dom_uses_full_card_without_top_panel_or_goal_edit(page):
    state = load(page, "plan")
    plan = next(c for c in state["cards"] if c["kind"] == "plan")
    plan["text"] = "方案目标\n受众：初学者\n范围：七天\n## 交付物\n完整计划\n## 关键工作\n每日安排"
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    assert page.locator("header").get_by_role("button", name="核对方案", exact=True).count() == 0
    assert page.get_by_role("button", name="修改方案目标", exact=True).count() == 0
    assert page.locator("#timeline").get_by_role("heading", name="一起核对方案").count() == 1
    assert page.locator("#timeline").get_by_text("方案目标", exact=False).count() >= 1
    page.locator("#timeline details summary").filter(has_text="交付物").click()
    assert page.get_by_text("完整计划", exact=False).is_visible()


def test_browser_back_remains_available_while_busy_and_positions_review_top(page):
    state = load(page, "plan", locked=True, stop_scope="busy-fixture")
    state["cards"] = [c for c in state["cards"] if c["kind"] not in {"requirements", "skills"}]
    nav = {"stage": "plan", "natural": "plan", "previous": "requirements", "next": None, "revisiting": False}
    state["navigation"] = nav
    state["cards"].insert(1, {"kind": "navigation", "key": "navigation", "title": "回看与继续", **nav})
    state["buttons"]["back_stage"] = {"text": "返回上一步", "enabled": True}
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    back = page.get_by_role("button", name="返回上一步", exact=True)
    assert back.is_enabled()
    back.click()
    page.wait_for_function("calls.some(c=>c.action==='navigate'&&c.data.direction==='previous'&&c.data.scope==='busy-fixture')")
    # An existing, long interview must remain above the review card.
    state["locked"] = False
    state["cards"] = [c for c in state["cards"] if c["kind"] not in {"plan", "navigation"}]
    for i in range(15):
        state["cards"].append({"key": "history:"+str(i), "kind": "history_question", "title": "此前的问题", "text": "完整历史问答\n"*12})
    nav.update(stage="requirements", previous="interview", next="plan", revisiting=True)
    state["cards"].append({"kind": "navigation", "key": "navigation", "title": "回看与继续", **nav})
    state["cards"].append({"kind": "requirements", "key": "requirements", "title": "需求已确认", "confirmed": True})
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    page.wait_for_timeout(100)
    box = page.get_by_role("heading", name="需求已确认", exact=True).bounding_box()
    viewport = page.locator("#viewport").bounding_box()
    assert viewport["y"] <= box["y"] < viewport["y"]+180


def test_back_rejects_queued_continue_after_draft_flush(page):
    state = load(page, "plan")
    nav = {"stage": "skills", "natural": "result", "previous": "plan", "next": "result", "revisiting": True}
    state["navigation"] = nav
    state["cards"].insert(1, {"kind": "navigation", "key": "navigation", "title": "回看与继续", **nav})
    state["buttons"].update(back_stage={"text": "返回上一步", "enabled": True}, continue_stage={"text": "继续下一步", "enabled": True})
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    page.evaluate("()=>{promptsmithHistory.flushDrafts=()=>new Promise(resolve=>window.releaseDraft=resolve);}")
    page.get_by_role("button", name="继续下一步", exact=True).click()
    page.get_by_role("button", name="返回上一步", exact=True).click()
    page.wait_for_function("calls.some(c=>c.action==='navigate')")
    state["stamp"] = "new-plan-stamp"
    state["navigation"].update(stage="plan", previous="requirements", next="skills")
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    page.evaluate("releaseDraft()")
    page.wait_for_timeout(150)
    assert not page.evaluate("calls.some(c=>c.action==='button'&&c.data.key==='continue_stage')")
