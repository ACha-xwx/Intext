from __future__ import annotations

import pytest

from promptsmith.session import SessionState, SessionStateError


def _binding() -> dict:
    return {"binding_id": "binding-1", "skill_id": "to-spec", "key_work_id": "k1"}


def test_v02_selected_skill_mirror_does_not_become_legacy_selection() -> None:
    session = SessionState.new()
    session.set_skill_state(status="selected", bindings=[_binding()])

    loaded = SessionState.from_dict(session.to_dict())

    assert loaded.skill_state["status"] == "selected"
    assert loaded.skill_state["bindings"] == [_binding()]
    assert loaded.selected_skills == ["to-spec"]
    assert loaded.skill_state["legacy_selection_unresolved"] == []


def test_v02_skipped_reopens_without_legacy_warning() -> None:
    session = SessionState.new()
    session.set_skill_state(status="selected", bindings=[_binding()])
    session.set_skill_state(status="skipped", bindings=[])

    loaded = SessionState.from_dict(session.to_dict())

    assert loaded.skill_state["status"] == "skipped"
    assert loaded.selected_skills == []
    assert loaded.skill_state["legacy_selection_unresolved"] == []


def test_v02_mirror_mismatch_requires_review_without_creating_legacy_selection() -> None:
    session = SessionState.new()
    session.set_skill_state(status="selected", bindings=[_binding()])
    data = session.to_dict()
    data["selected_skills"] = ["other-skill"]

    loaded = SessionState.from_dict(data)

    assert loaded.skill_state["status"] == "stale"
    assert loaded.skill_state["bindings"] == [_binding()]
    assert loaded.skill_state["legacy_selection_unresolved"] == []


def test_v02_corrupt_bindings_are_rejected() -> None:
    data = SessionState.new().to_dict()
    data["skill_state"]["bindings"] = "corrupt"

    with pytest.raises(SessionStateError, match="绑定"):
        SessionState.from_dict(data)
