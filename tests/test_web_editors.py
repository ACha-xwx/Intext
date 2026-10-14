"""Editing through the real desktop controller and production browser DOM."""
import tkinter as tk
from copy import deepcopy

import pytest

from promptsmith.web_workspace import WorkspaceController, view_stamp
from promptsmith.session import SessionStateError
from tests.test_conversation_workspace import app, install_session
from tests.test_final_delivery import confirmed_plan_session
from tests.test_frontend_review_regressions import browser, page, load


def review_controller(app):
    install_session(app, confirmed_plan_session())
    controller = WorkspaceController(app)
    controller.install_native_bridge()
    while app.session.workspace_navigation()["stage"] != "requirements":
        controller.dispatch("button", {"key": "back_stage"}, view_stamp(app))
    return controller


def test_return_to_requirements_opens_web_editor_without_hidden_window_wait(app):
    controller = review_controller(app)
    controller.dispatch("requirement_row", {"id": "r:r2"}, view_stamp(app))
    hidden = []
    # Drive the original *real* dialog and release its wait to keep a red run bounded.
    # This is an external window observation, not an editor mock.
    def watchdog():
        for child in app.root.winfo_children():
            if isinstance(child, tk.Toplevel):
                hidden.append(not child.winfo_viewable())
                child.destroy()
    timer = app.root.after(180, watchdog)
    try:
        controller.dispatch("button", {"key": "edit_requirement"}, view_stamp(app))
        snapshot = controller.snapshot()
        assert snapshot.get("editor"), f"No Web editor; invisible Tk dialogs observed: {hidden}"
        assert snapshot["editor"]["title"] == "编辑需求"
        assert not hidden
        assert not app.root.winfo_viewable()
    finally:
        app.root.after_cancel(timer)


def test_requirement_editor_cancel_save_validation_and_stale_are_recoverable(app, caplog):
    controller = review_controller(app)
    controller.dispatch("requirement_row", {"id": "r:r2"}, view_stamp(app))
    before = deepcopy(app.session.to_dict())
    controller.dispatch("button", {"key": "edit_requirement"}, view_stamp(app))
    editor = controller.snapshot()["editor"]
    with pytest.raises(ValueError, match="不能为空"):
        controller.dispatch("editor_save", {"id": editor["id"], "values": {"text": "  "}}, view_stamp(app))
    assert controller.snapshot()["editor"]["error"]
    controller.dispatch("editor_cancel", {"id": editor["id"]}, view_stamp(app))
    assert app.session.to_dict() == before
    controller.dispatch("settings", {}, view_stamp(app))
    assert controller.snapshot()["page"] == "settings"
    controller.dispatch("settings_back", {}, view_stamp(app))
    controller.dispatch("button", {"key": "edit_requirement"}, view_stamp(app))
    editor = controller.snapshot()["editor"]
    old_stamp = view_stamp(app)
    controller.dispatch("editor_save", {"id": editor["id"], "values": {"text": "十四天，每天一小时\n完整计划 👩🏽‍💻"}}, old_stamp)
    assert app.session.requirements[1]["text"] == "十四天，每天一小时\n完整计划 👩🏽‍💻"
    assert app.session.plan["status"] == "stale"
    assert app.session.confirmed_requirements_version is None
    assert controller.snapshot()["editor"] is None
    with pytest.raises(ValueError):
        controller.dispatch("editor_save", {"id": editor["id"], "values": {"text": "迟到"}}, old_stamp)
    assert "Web editor opened" in caplog.text and "Web editor saved" in caplog.text
    assert "十四天，每天一小时\n完整计划" not in caplog.text


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_web_editor_is_visible_preserves_draft_and_cancel_restores_focus(page, theme):
    editor = dict(id="editor-1", kind="requirement", title="编辑需求", target="r:r1", error="",
                  fields=[dict(key="text", label="需求内容", value="原始目标", required=True)])
    state = load(page, theme=theme)
    page.locator("#settings").focus()
    state["editor"] = editor
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    dialog = page.get_by_role("dialog", name="编辑需求", exact=True)
    assert dialog.is_visible()
    field = dialog.get_by_label("需求内容", exact=True)
    field.fill("修改草稿\n👩🏽‍💻")
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    assert field.input_value() == "修改草稿\n👩🏽‍💻"
    field.press("Escape")
    page.wait_for_function("calls.some(c=>c.action==='editor_cancel'&&c.data.id==='editor-1')")
    assert page.locator("#settings").evaluate("e=>e===document.activeElement")


def test_complete_plan_editing_stays_in_web_and_preserves_business_rules(app):
    install_session(app, confirmed_plan_session())
    controller = WorkspaceController(app)
    controller.install_native_bridge()
    controller.dispatch("button", {"key": "back_stage"}, view_stamp(app))
    controller.dispatch("button", {"key": "edit_plan"}, view_stamp(app))
    overview = controller.snapshot().get("editor")
    assert overview and overview["kind"] == "plan"
    assert not app.root.winfo_viewable()

    controller.dispatch("editor_open", {"id": overview["id"], "kind": "key_work", "target": "k1"}, view_stamp(app))
    editor = controller.snapshot()["editor"]
    values = {f["key"]: f["value"] for f in editor["fields"]}
    values["title"] = "设计可执行的每日学习顺序"
    controller.dispatch("editor_save", {"id": editor["id"], "values": values}, view_stamp(app))
    assert app.session.plan["content"]["key_work"][1]["title"] == values["title"]
    assert app.session.plan["content"]["key_work"][1]["depends_on_key_work_ids"] == ["k0"]
    assert app.session.plan["pending_key_work_review_ids"] == ["k1"]
    assert app.session.plan["status"] == "draft"
    overview = controller.snapshot()["editor"]
    assert overview["kind"] == "plan"
    controller.dispatch("editor_review", {"id": overview["id"], "target": "k1"}, view_stamp(app))
    assert app.session.plan["pending_key_work_review_ids"] == []
    overview = controller.snapshot()["editor"]
    controller.dispatch("editor_open", {"id": overview["id"], "kind": "step", "target": "s1"}, view_stamp(app))
    editor = controller.snapshot()["editor"]
    values = {f["key"]: f["value"] for f in editor["fields"]}
    values["actions"] = "学习概念\n练习 👩🏽‍💻\n检查结果"
    controller.dispatch("editor_save", {"id": editor["id"], "values": values}, view_stamp(app))
    step = app.session.plan["content"]["steps"][1]
    assert step["actions"] == ["学习概念", "练习 👩🏽‍💻", "检查结果"]
    assert step["depends_on_step_ids"] == ["s0"]
    assert step["requirement_ids"] == ["r1", "r2"]
    assert not app.root.winfo_viewable()


def test_plan_overview_and_link_choices_are_usable_in_browser(page):
    from tests.test_final_delivery import confirmed_plan_session
    content = confirmed_plan_session().plan["content"]
    overview = dict(id="plan-1", kind="plan", title="完整方案编辑", content=content, pending=["k1"], error="", fields=[])
    state = load(page, editor=overview)
    dialog = page.get_by_role("dialog", name="完整方案编辑", exact=True)
    dialog.get_by_text("设计每日学习顺序", exact=True).click()
    assert dialog.get_by_role("button", name="编辑关键工作：设计每日学习顺序", exact=True).is_visible()
    dialog.get_by_role("button", name="编辑关键工作：设计每日学习顺序", exact=True).click()
    page.wait_for_function("calls.some(c=>c.action==='editor_open'&&c.data.kind==='key_work'&&c.data.target==='k1')")
    state["editor"] = dict(id="work-1", kind="key_work", title="编辑关键工作", error="", fields=[
        dict(key="title",label="标题",value="设计每日学习顺序",required=True),
        dict(key="step_ids",label="关联步骤",value="s1",type="choices",required=False,
             choices=[dict(id="s0",label="确认起点"),dict(id="s1",label="安排每日学习")])])
    page.evaluate("s=>promptsmithView.applySnapshot(s)",state)
    dialog = page.get_by_role("dialog",name="编辑关键工作",exact=True)
    assert dialog.get_by_label("安排每日学习",exact=True).is_checked()
    dialog.get_by_label("确认起点",exact=True).check()
    dialog.get_by_role("button",name="保存",exact=True).click()
    page.wait_for_function("calls.some(c=>c.action==='editor_save'&&c.data.values.step_ids==='s0\\ns1')")


@pytest.mark.parametrize("kind,target,changed_key,changed_value,collection", [
    ("goal", None, "summary", "完整的入门学习提示词", "goal"),
    ("goal_details", None, "audience", "完全零基础的学习者", "goal"),
    ("deliverable", "d1", "description", "逐日练习和检查方式", "deliverables"),
    ("criterion", "c1", "text", "能够完成入门练习", "completion_criteria"),
    ("unresolved", "u1", "continuable_work", "下游执行时核对环境", "unresolved_items"),
    ("suggestion", "sg1", "reason", "帮助理解与复习", "suggestions"),
])
def test_all_plan_fields_save_through_session(app, kind, target, changed_key, changed_value, collection):
    install_session(app, confirmed_plan_session())
    controller = WorkspaceController(app)
    controller.install_native_bridge()
    controller.dispatch("button", {"key": "back_stage"}, view_stamp(app))
    controller.dispatch("button", {"key": "edit_plan"}, view_stamp(app))
    overview = controller.snapshot()["editor"]
    controller.dispatch("editor_open", {"id": overview["id"], "kind": kind, "target": target}, view_stamp(app))
    editor = controller.snapshot()["editor"]
    values = {f["key"]: f["value"] for f in editor["fields"]}
    values[changed_key] = changed_value
    controller.dispatch("editor_save", {"id": editor["id"], "values": values}, view_stamp(app))
    saved = app.session.plan["content"][collection]
    assert (saved if collection == "goal" else saved[0])[changed_key] == changed_value
    assert app.session.plan["status"] == "draft"
    assert controller.snapshot()["editor"]["kind"] == "plan"


def test_added_step_move_delete_and_errors_keep_web_editing_usable(app):
    install_session(app, confirmed_plan_session())
    controller = WorkspaceController(app)
    controller.install_native_bridge()
    controller.dispatch("button", {"key": "back_stage"}, view_stamp(app))
    controller.dispatch("button", {"key": "edit_plan"}, view_stamp(app))
    overview = controller.snapshot()["editor"]
    controller.dispatch("editor_open", {"id": overview["id"], "kind": "step_delete", "target": "s1"}, view_stamp(app))
    editor = controller.snapshot()["editor"]
    with pytest.raises(SessionStateError, match="引用"):
        controller.dispatch("editor_save", {"id": editor["id"], "values": {}}, view_stamp(app))
    assert controller.snapshot()["editor"]["error"]
    controller.dispatch("editor_cancel", {"id": editor["id"]}, view_stamp(app))
    overview = controller.snapshot()["editor"]
    controller.dispatch("editor_open", {"id": overview["id"], "kind": "step_new"}, view_stamp(app))
    editor = controller.snapshot()["editor"]
    values = {f["key"]: f["value"] for f in editor["fields"]}
    values.update(title="整理总结", purpose="整理下游提示词", actions="整理学习重点", outputs="总结", completion_criteria="概念清晰", requirement_ids="r1")
    controller.dispatch("editor_save", {"id": editor["id"], "values": values}, view_stamp(app))
    overview = controller.snapshot()["editor"]
    added = next(s for s in overview["content"]["steps"] if s["title"] == "整理总结")
    controller.dispatch("editor_move", {"id": overview["id"], "target": added["step_id"], "offset": -1}, view_stamp(app))
    overview = controller.snapshot()["editor"]
    assert overview["content"]["steps"][1]["title"] == "整理总结"
    controller.dispatch("editor_open", {"id": overview["id"], "kind": "step_delete", "target": added["step_id"]}, view_stamp(app))
    editor = controller.snapshot()["editor"]
    controller.dispatch("editor_save", {"id": editor["id"], "values": {}}, view_stamp(app))
    assert all(s["title"] != "整理总结" for s in app.session.plan["content"]["steps"])


def test_note_and_pending_requirement_use_web_and_stale_session_cannot_save(app):
    from promptsmith.finalization import build_final_draft
    session = confirmed_plan_session()
    session.skill_state["status"] = "skipped"
    session.final_result = build_final_draft(session)
    install_session(app, session)
    controller = WorkspaceController(app)
    controller.install_native_bridge()
    controller.dispatch("panel", {"kind": "result"}, view_stamp(app))
    controller.dispatch("button", {"key": "add_final_note"}, view_stamp(app))
    editor = controller.snapshot()["editor"]
    controller.dispatch("editor_save", {"id": editor["id"], "values": {"text": "下游执行前核对可用环境"}}, view_stamp(app))
    assert "下游执行前核对可用环境" in session.final_result["canonical_body"]
    while session.workspace_navigation()["stage"] != "requirements":
        controller.dispatch("button", {"key": "back_stage"}, view_stamp(app))
    session.pending_proposals.append(dict(proposal_id="p1",text="原始理解",field="scope",kind="pending_interpretation"))
    app.refresh()
    controller.dispatch("requirement_row", {"id": "p:p1"}, view_stamp(app))
    controller.dispatch("button", {"key": "edit_requirement"}, view_stamp(app))
    editor = controller.snapshot()["editor"]
    old_stamp = view_stamp(app)
    controller.dispatch("editor_save", {"id": editor["id"], "values": {"text": "仅设计 UI 布局"}}, old_stamp)
    assert session.pending_proposals[0]["text"] == "仅设计 UI 布局"
    controller.dispatch("button", {"key": "edit_requirement"}, view_stamp(app))
    editor = controller.snapshot()["editor"]
    old_stamp = view_stamp(app)
    app._install_session(confirmed_plan_session(),reason="synthetic-switch")
    assert controller.snapshot()["editor"] is None
    with pytest.raises(ValueError):
        controller.dispatch("editor_save", {"id": editor["id"], "values": {"text": "迟到修改"}}, old_stamp)
    assert all(r["text"] != "迟到修改" for r in app.session.requirements)


def test_conflict_confirmation_uses_web_and_cancel_keeps_requirements(app):
    controller = review_controller(app)
    app.session.open_conflicts = [dict(conflict_id="cf1",status="open",description="请核对两项要求",existing_item_ids=["r1","r2"],proposal_ids=[])]
    app.refresh()
    before = deepcopy(app.session.to_dict())
    app.review_current_conflict()
    editor = controller.snapshot()["editor"]
    assert editor and editor["kind"] == "conflict"
    assert "请核对两项要求" in editor["message"]
    controller.dispatch("editor_cancel", {"id": editor["id"]}, view_stamp(app))
    assert app.session.to_dict() == before
    app.review_current_conflict()
    editor = controller.snapshot()["editor"]
    controller.dispatch("editor_save", {"id": editor["id"], "values": {}}, view_stamp(app))
    assert not app.session.open_conflicts
    assert app.session.compatible_conflicts
    assert not app.root.winfo_viewable()


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_small_web_editor_validation_keyboard_and_failure_keep_controls_usable(page, theme, tmp_path):
    page.set_viewport_size({"width":720,"height":440})
    editor = dict(id="long-form",kind="goal_details",title="编辑受众与范围",error="",fields=[
        dict(key="audience",label="主要受众",value="长内容\n"*120,required=True),
        dict(key="scope",label="方案范围",value="UI 布局",required=True)])
    state = load(page,theme=theme,font_size=18,editor=editor)
    dialog = page.get_by_role("dialog",name="编辑受众与范围",exact=True)
    box=dialog.bounding_box()
    assert box["x"]>=0 and box["y"]>=0 and box["x"]+box["width"]<=720 and box["y"]+box["height"]<=440
    field=dialog.get_by_label("方案范围",exact=True)
    field.fill("未提交草稿👩🏽‍💻")
    field.press("Enter")
    assert field.input_value().endswith("\n")
    assert not page.evaluate("calls.some(c=>c.action==='editor_save')")
    page.evaluate("pywebview.api.dispatch=async(action,data)=>{calls.push({action,data});return action==='editor_save'?{ok:false,error:'模拟保存失败'}:{ok:true};}")
    field.press("Control+Enter")
    page.wait_for_function("calls.some(c=>c.action==='editor_save') && !document.body.classList.contains('pending')")
    assert field.input_value()=="未提交草稿👩🏽‍💻\n"
    assert dialog.get_by_role("button",name="保存",exact=True).is_enabled()
    assert "模拟保存失败" in dialog.get_by_role("alert").inner_text()
    state["editor"]["error"]="保存失败，请修改后重试。"
    page.evaluate("s=>promptsmithView.applySnapshot(s)",state)
    assert dialog.locator(".notification-body").last.inner_text()=="保存失败，请修改后重试。"
    for _ in range(10):
        page.keyboard.press("Tab")
        assert dialog.evaluate("e=>e.contains(document.activeElement)")
    page.screenshot(path=str(tmp_path/(theme+"-editor.png")))
