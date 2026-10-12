"""User edits and request cancellation through existing application actions."""
from copy import deepcopy
import pytest

from tests.test_guided_ui import app, stage_jgs


def prepare_review(app):
    stage_jgs(app)
    app.session.pending_questions = []
    app.session.gaps = []
    app.session.last_next_action = "review_requirements"
    app.refresh()


def test_candidate_whitespace_edit_does_not_invoke_model_or_invalidate(app, monkeypatch):
    prepare_review(app)
    row = app.session.pending_proposals[0]
    row["text"] = "重新设计修改后的 UI 页面（布局与各元素样式已更新）"
    app.refresh()
    app.toggle_requirements_review()
    app.widgets["conversation_requirements_tree"].selection_set("p:" + row["proposal_id"])
    app._conversation_show_requirement_selection()
    before = deepcopy(app.session.to_dict())
    calls = []
    monkeypatch.setattr("promptsmith.guided_flow.simpledialog.askstring",
                        lambda *a, **k: "重新设计修改后的  UI 页面（布局与各元素样式已更新）")
    monkeypatch.setattr(app, "_submit", lambda *a, **k: calls.append(a))
    app._conversation_buttons["edit_requirement"].invoke()
    assert calls == [], "Only inserting a space must not submit another model request"
    assert app.session.to_dict() == before
    assert not app.busy


def test_reviewed_candidate_edit_can_confirm_and_go_straight_to_plan(app, monkeypatch):
    from tests.test_conversation_workspace import install_session
    from tests.test_final_delivery import confirmed_plan_session
    from tests.test_session import proposal
    session = confirmed_plan_session()
    session.confirmed_requirements_version = None
    session.plan = type(session).new().plan
    session.last_next_action = "review_requirements"
    session.pending_proposals = [proposal("p-edit", "采用清晰的视觉层级")]
    install_session(app, session)
    row = app.session.pending_proposals[0]
    app.widgets["conversation_requirements_tree"].selection_set("p:" + row["proposal_id"])
    app._conversation_show_requirement_selection()
    monkeypatch.setattr("promptsmith.guided_flow.simpledialog.askstring", lambda *a, **k: "采用清晰且简洁的视觉层级")
    requests = []
    monkeypatch.setattr(app, "_submit", lambda *a, **k: requests.append(app.busy_kind))
    app._conversation_buttons["edit_requirement"].invoke()
    assert requests == [] and app.session.confirmed_requirements_version is None
    assert str(app._conversation_buttons["confirm_requirements"]["state"]) == "normal"
    app._conversation_buttons["confirm_requirements"].invoke()
    assert app.session.confirmed_requirements_version == app.session.requirement_version
    assert requests == ["m2"], "An explicit edit and confirmation need M2, not another M1 interview"


def test_unassessed_answers_are_not_bypassed_by_local_candidate_edit(app):
    prepare_review(app)
    app.session.record_supplement("还要增加一个此前未分析的新目标")
    row = app.session.pending_proposals[0]
    app.session.edit_proposal(row["proposal_id"], "明确修改一项候选")
    assert app.session.analysis_basis_version is None
    from promptsmith.session import SessionStateError
    with pytest.raises(SessionStateError):
        app.session.confirm_requirements_preview(app.session.requirements_preview())


def test_explicit_candidate_edit_is_saved_locally_pending_review(app, monkeypatch):
    prepare_review(app)
    row = app.session.pending_proposals[0]
    key = row["proposal_id"]
    app.toggle_requirements_review()
    app.widgets["conversation_requirements_tree"].selection_set("p:" + key)
    app._conversation_show_requirement_selection()
    calls = []
    monkeypatch.setattr("promptsmith.guided_flow.simpledialog.askstring",
                        lambda *a, **k: "重新设计界面布局，保留全部现有功能")
    monkeypatch.setattr(app, "_submit", lambda *a, **k: calls.append(a))
    app._conversation_buttons["edit_requirement"].invoke()
    assert calls == []
    edited = next(p for p in app.session.pending_proposals if p["proposal_id"] == key)
    assert edited["text"] == "重新设计界面布局，保留全部现有功能"
    assert edited["operation"] == row["operation"]
    assert edited["target_item_id"] == row["target_item_id"]
    source = next(s for s in app.session.sources if s["source_id"] == edited["source_refs"][0]["source_id"])
    assert source["role"] == "user" and source["text"] == edited["text"]
    assert app.session.confirmed_requirements_version is None
    assert not app.busy
