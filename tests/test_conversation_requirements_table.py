"""Requirement comparison table uses real Tk widgets and session actions."""
from copy import deepcopy
import _tkinter

from promptsmith.storage import load_session, save_session
from promptsmith.web_workspace import WorkspaceController, view_stamp
from tests.test_conversation_workspace import app, install_session as _install_session
from tests.test_final_delivery import confirmed_plan_session


def install_session(app, session):
    _install_session(app, session)
    while app.session.workspace_navigation()["stage"] != "requirements":
        app.navigate_workspace("previous")


def select(app, key):
    app.widgets["conversation_requirements_tree"].selection_set(key)
    app._conversation_show_requirement_selection()


def test_confirmed_requirements_are_a_read_only_table_with_full_selected_text(app, monkeypatch):
    # Fail deterministically if a scrollbar/Text geometry loop would otherwise
    # trap update_idletasks forever and freeze both tests and the actual UI.
    def bounded_idle():
        for _ in range(500):
            if not app.root.tk.dooneevent(_tkinter.IDLE_EVENTS | _tkinter.DONT_WAIT):
                return
        raise AssertionError("The reading area never settled its idle layout")
    monkeypatch.setattr(app.root, "update_idletasks", bounded_idle)
    session = confirmed_plan_session()
    session.requirements[0]["text"] = "这是长需求的第一行\n" + "完整需求内容" * 60
    install_session(app, session)
    before = deepcopy(session.to_dict())
    tree = app.widgets["conversation_requirements_tree"]
    assert tree.cget("columns") == ("field", "text", "kind", "state")
    assert len(tree.get_children()) == len(session.requirements)
    key = "r:" + session.requirements[0]["item_id"]
    select(app, key)
    values = tree.item(key, "values")
    assert values[-1] == "已确认"
    assert "\n" not in values[1] and values[1].endswith("…")
    assert app.widgets["conversation_requirement_details"].get("1.0", "end-1c") == session.requirements[0]["text"]
    assert str(app._conversation_buttons["edit_requirement"]["state"]) == "normal"
    assert not "accept_requirement" in app._conversation_buttons
    app.refresh()
    assert session.to_dict() == before
    assert app.widgets["conversation_requirements_tree"].selection() == (key,)


def test_table_edit_invalidates_confirmed_plan_and_rejects_old_action(app, monkeypatch):
    install_session(app, confirmed_plan_session())
    app.generate_default_final()
    assert app.session.final_result["status"] == "draft"
    while app.session.workspace_navigation()["stage"] != "requirements":
        app.navigate_workspace("previous")
    key = "r:" + app.session.requirements[0]["item_id"]
    select(app, key)
    old_token = app._conversation_token()
    monkeypatch.setattr(app, "_multi_text_dialog", lambda *_: {"text": "调整布局和元素样式，保留全部现有功能"})
    app._conversation_buttons["edit_requirement"].invoke()
    edited = next(row for row in app.session.requirements if row["text"] == "调整布局和元素样式，保留全部现有功能")
    assert app.session.plan["status"] == "stale"
    assert app.session.final_result["status"] == "stale"
    assert app.session.confirmed_requirements_version is None
    calls = []
    app._conversation_action(old_token, lambda: calls.append("stale"))
    assert not calls
    assert app.widgets["conversation_requirements_tree"].selection() == ("r:" + edited["item_id"],)
    assert not app.dialogs


def test_table_remove_updates_session_and_restores_on_reopen(app, tmp_path):
    install_session(app, confirmed_plan_session())
    removed = app.session.requirements[0]["item_id"]
    select(app, "r:" + removed)
    app._conversation_buttons["remove_requirement"].invoke()
    assert not any(row["item_id"] == removed for row in app.session.requirements)
    assert app.session.plan["status"] == "stale"
    assert not app.widgets["conversation_requirements_tree"].exists("r:" + removed)
    install_session(app, load_session(save_session(app.session, tmp_path / "table.json")))
    assert len(app.widgets["conversation_requirements_tree"].get_children()) == len(app.session.requirements)
    assert not app.widgets["conversation_requirements_tree"].exists("r:" + removed)
    assert not app.dialogs


def test_busy_disables_table_actions_and_selection_stays_read_only(app):
    install_session(app, confirmed_plan_session())
    key = "r:" + app.session.requirements[0]["item_id"]
    app.busy = True
    app.refresh()
    select(app, key)
    assert str(app._conversation_buttons["edit_requirement"]["state"]) == "disabled"
    assert str(app._conversation_buttons["remove_requirement"]["state"]) == "disabled"
    assert app.session.plan["status"] == "confirmed"
    app.busy = False
    app.refresh()
    assert str(app._conversation_buttons["edit_requirement"]["state"]) == "normal"


def test_pending_interpretations_and_replacements_remain_editable_and_removable_without_adoption(app):
    from tests.test_session import proposal
    session = confirmed_plan_session()
    idea = proposal("p-meaning", "仅改布局和样式，不增加新功能")
    idea.update(kind="pending_interpretation", source_refs=[], valid_for_version=session.requirement_version)
    target = session.requirements[0]
    replacement = proposal("p-replace", "按参考图改进视觉层级", "replace", target["item_id"])
    replacement.update(source_refs=[], valid_for_version=session.requirement_version)
    session.pending_proposals = [idea, replacement]
    install_session(app, session)
    controller = WorkspaceController(app)
    controller.install_native_bridge()
    before = deepcopy(session.requirements)
    for key, edited in (("p-meaning", "只调整视觉样式"), ("p-replace", "优化页面布局")):
        controller.dispatch("requirement_row", {"id": "p:" + key}, view_stamp(app))
        snapshot = controller.snapshot()
        assert snapshot["buttons"]["edit_requirement"]["enabled"]
        assert snapshot["buttons"]["remove_requirement"]["enabled"]
        assert "adopt_requirement" not in snapshot["buttons"]
        assert "accept_requirement" not in snapshot["buttons"]
        assert next(row for row in snapshot["requirement_rows"] if row["id"] == "p:" + key)["status"] == "待确认解释"
        controller.dispatch("button", {"key": "edit_requirement"}, view_stamp(app))
        editor = controller.snapshot()["editor"]
        controller.dispatch("editor_save", {"id": editor["id"], "values": {"text": edited}}, view_stamp(app))
        assert next(row for row in session.pending_proposals if row["proposal_id"] == key)["text"] == edited
        controller.dispatch("requirement_row", {"id": "p:" + key}, view_stamp(app))
        controller.dispatch("button", {"key": "remove_requirement"}, view_stamp(app))
        assert not any(row["proposal_id"] == key for row in session.pending_proposals)
        assert session.requirements == before
    assert not app.dialogs
