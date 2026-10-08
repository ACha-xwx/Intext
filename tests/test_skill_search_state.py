from __future__ import annotations

from promptsmith.session import SessionState


def test_new_session_has_search_state_defaults():
    state = SessionState.new().skill_state

    assert state["search_state"] == {
        "status": "idle",
        "local": None,
        "network": None,
        "last_error": None,
        "updated_at": None,
    }


def test_skill_state_migration_preserves_search_state():
    session = SessionState.from_dict(
        {
            "schema_version": "promptsmith.session.v0.2",
            "skill_state": {
                "status": "candidates_ready",
                "search_state": {
                    "status": "network_done",
                    "local": {"status": "ok", "count": 1},
                    "network": {"status": "ok", "count": 2},
                    "last_error": None,
                    "updated_at": "2026-10-06T00:00:00+00:00",
                },
                "bindings": [],
            },
            "selected_skills": [],
        }
    )

    assert session.skill_state["search_state"]["network"]["count"] == 2


def test_set_skill_state_keeps_search_state_when_candidate_batch_changes():
    session = SessionState.new()
    session.skill_state["search_state"] = {
        "status": "local_done",
        "local": {"status": "ok", "count": 1},
        "network": None,
        "last_error": None,
        "updated_at": "2026-10-06T00:00:00+00:00",
    }

    session.set_skill_state(
        status="candidates_ready",
        basis={"plan_version": 1},
        candidate_batch={"catalog_hash": "changed"},
        bindings=[],
    )

    assert session.skill_state["search_state"]["status"] == "local_done"
