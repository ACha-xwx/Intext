"""User-visible action row layout and notes without a tone editing control."""
import pytest
from playwright.sync_api import expect

from promptsmith.finalization import build_final_draft, set_final_tone, stage_final_draft
from promptsmith.storage import load_session, save_session
from promptsmith.web_workspace import WorkspaceController, view_stamp
from tests.test_conversation_workspace import app, install_session
from tests.test_final_delivery import confirmed_plan_session
from tests.test_frontend_review_regressions import browser, page, load


@pytest.mark.parametrize("kind,count", [("requirements", 3), ("plan", 3), ("skills", 3), ("skills_selected", 5), ("result", 3)])
@pytest.mark.parametrize("theme,width", [("light", 1440), ("dark", 720)])
def test_stage_actions_fill_the_row_as_equal_glass_buttons(page, kind, count, theme, width):
    page.set_viewport_size({"width": width, "height": 810})
    fixture_kind = "skills" if kind == "skills_selected" else "final" if kind == "result" else kind
    state = load(page, fixture_kind, theme=theme)
    card_kind = "skills" if kind == "skills_selected" else kind
    state["cards"] = [c for c in state["cards"] if c["kind"] in {"user", card_kind}]
    if kind == "requirements":
        state["buttons"].update(edit_requirement={"text": "修改选中需求", "enabled": False},
                                 remove_requirement={"text": "移除选中需求", "enabled": False},
                                 adopt_requirement={"text": "采用选中修改", "enabled": False})
    elif kind == "plan":
        state["buttons"]["confirm_plan"] = {"text": "确认方案并生成提示词", "enabled": True}
    if kind == "skills":
        for key in ("integrate", "direct_skills"):
            state["buttons"].pop(key, None)
    elif kind == "skills_selected":
        state["buttons"].update(integrate={"text": "整合所选 Skill 并生成提示词", "enabled": True},
                                 direct_skills={"text": "用已选 Skill 直接生成提示词", "enabled": True})
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    card = page.locator("#timeline > .message").last
    row = card.locator(".actions").first
    buttons = row.locator("button")
    expect(buttons).to_have_count(count)
    assert card.get_by_role("button", name="采用选中修改", exact=True).count() == 0
    boxes = [b.bounding_box() for b in buttons.all()]
    bounds = row.bounding_box()
    assert abs(boxes[0]["x"] - bounds["x"]) < 1
    assert abs(boxes[-1]["x"] + boxes[-1]["width"] - bounds["x"] - bounds["width"]) < 1
    rows = {}
    for box in boxes:
        rows.setdefault(round(box["y"]), []).append(box)
    if width == 1440:
        assert len(rows) == 1
    for row_boxes in rows.values():
        assert abs(row_boxes[0]["x"] - bounds["x"]) < 1
        assert abs(row_boxes[-1]["x"] + row_boxes[-1]["width"] - bounds["x"] - bounds["width"]) < 1
        assert max(b["width"] for b in row_boxes) - min(b["width"] for b in row_boxes) < 1
    for control in buttons.all():
        assert "glass" in control.get_attribute("class").split()
        assert control.evaluate("b=>b.scrollWidth<=b.clientWidth+1")
    assert page.locator("#viewport").evaluate("v=>v.scrollWidth<=v.clientWidth+1")


def test_result_has_only_copy_export_and_notes_and_notes_cannot_change_tone(page):
    state = load(page, "final")
    state["cards"] = [c for c in state["cards"] if c["kind"] in {"user", "result"}]
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    result = page.locator("#timeline > .message").last
    assert result.get_by_role("button", name="保存会话", exact=True).count() == 0
    assert result.get_by_role("button", name="确认最终提示词", exact=True).count() == 0
    assert result.get_by_role("button", name="语气和附注", exact=True).count() == 0
    result.get_by_role("button", name="附注", exact=True).click()
    panel = page.get_by_role("dialog", name="附注", exact=True)
    expect(panel).to_be_visible()
    assert panel.get_by_label("提示词语气", exact=True).count() == 0
    assert panel.locator("select").count() == 0
    panel.get_by_role("button", name="添加附注", exact=True).click()
    page.wait_for_function("calls.some(c=>c.action==='button'&&c.data.key==='add_final_note')")
    assert not page.evaluate("calls.some(c=>c.action==='tone')")


def test_glass_row_preserves_action_dispatch_and_reduced_motion(page):
    state = load(page, "plan")
    state["cards"] = [c for c in state["cards"] if c["kind"] in {"user", "plan"}]
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    control = page.get_by_role("button", name="展开完整方案并编辑", exact=True)
    control.click()
    page.wait_for_function("calls.some(c=>c.action==='button'&&c.data.key==='edit_plan')")
    assert "glass" in control.get_attribute("class").split()
    control.hover()
    page.wait_for_timeout(300)
    assert control.evaluate("b=>getComputedStyle(b).transform") != "none"
    page.emulate_media(reduced_motion="reduce")
    assert control.evaluate("b=>getComputedStyle(b).transitionDuration") == "0s"


def test_actual_result_controls_open_web_note_editor_and_preserve_saved_tone(app, page, tmp_path, caplog):
    session = confirmed_plan_session()
    stage_final_draft(session, build_final_draft(session))
    set_final_tone(session, "polite")
    install_session(app, session)
    controller = WorkspaceController(app)
    controller.install_native_bridge()
    load(page, "final")
    snapshot = controller.snapshot()
    assert snapshot["buttons"]["result_details"]["text"] == "附注"
    assert "save" not in snapshot["buttons"] and "confirm_final" not in snapshot["buttons"]
    page.evaluate("s=>promptsmithView.applySnapshot(s)", snapshot)
    result = page.locator("#timeline > .message").last
    assert result.locator(".stage-actions button").all_text_contents() == ["复制提示词", "导出方案和提示词", "附注"]
    result.get_by_role("button", name="附注", exact=True).click()
    controller.dispatch("panel", {"kind": "result"}, view_stamp(app))
    page.evaluate("s=>promptsmithView.applySnapshot(s)", controller.snapshot())
    panel = page.get_by_role("dialog", name="附注", exact=True)
    expect(panel).to_be_visible()
    assert panel.locator("select").count() == 0
    panel.get_by_role("button", name="添加附注", exact=True).click()
    controller.dispatch("button", {"key": "add_final_note"}, view_stamp(app))
    snapshot = controller.snapshot()
    assert snapshot["editor"]["kind"] == "note"
    assert [f["key"] for f in snapshot["editor"]["fields"]] == ["text"]
    page.evaluate("s=>promptsmithView.applySnapshot(s)", snapshot)
    editor = page.get_by_role("dialog", name="添加用户附注", exact=True)
    expect(editor).to_be_visible()
    editor.get_by_label("附注内容", exact=True).fill("执行前先核对截图和参考组件。")
    with caplog.at_level("INFO", logger="promptsmith.web_editors"):
        controller.dispatch("editor_save", {"id": snapshot["editor"]["id"],
                            "values": {"text": "执行前先核对截图和参考组件。"}}, view_stamp(app))
    assert controller.snapshot()["editor"] is None
    assert "执行前先核对截图和参考组件。" in session.final_result["canonical_body"]
    assert session.final_result["tone"] == "polite"
    assert "Web editor saved: kind=note" in caplog.text
    restored = load_session(save_session(session, tmp_path / "note.json"))
    assert restored.final_result["tone"] == "polite"
    assert "执行前先核对截图和参考组件。" in restored.final_result["canonical_body"]
