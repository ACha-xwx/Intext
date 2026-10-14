"""Operation-based onboarding through the public desktop boundary."""
import json
import pytest

from promptsmith.preferences import load_settings
from promptsmith.web_workspace import WorkspaceController
from tests.test_conversation_workspace import app


def test_skip_is_distinct_from_completion_and_survives_model_autosave(app):
    controller = WorkspaceController(app)
    first = controller.snapshot()
    assert first["tutorial_status"] == "not_started"
    stored = json.loads(app._preferences_path.read_text(encoding="utf-8"))
    task = app.session.to_dict()
    app.busy = True
    controller.dispatch("tutorial_skip", {}, first["stamp"])
    assert controller.snapshot()["tutorial_status"] == "skipped"
    assert app.busy and app.session.to_dict() == task
    after = json.loads(app._preferences_path.read_text(encoding="utf-8"))
    for key in ("credentials", "model_profiles", "model_confirmation", "connection"):
        assert after.get(key) == stored.get(key)
    assert WorkspaceController(app).snapshot()["tutorial_status"] == "skipped"
    app.busy = False
    settings = controller.settings_snapshot()
    controller.settings_action("settings_autosave", dict(revision=settings["revision"],
        connection=settings["connection"], values=settings["values"], key_action="keep", key=""))
    assert WorkspaceController(app).snapshot()["tutorial_status"] == "skipped"
    assert load_settings(app._preferences_path).api_key == "offline-key"


def test_completion_can_be_saved_without_sending_a_goal(app):
    controller = WorkspaceController(app)
    task = app.session.to_dict()
    app.busy = True
    controller.dispatch("tutorial_finish", {}, controller.snapshot()["stamp"])
    assert app.busy
    assert WorkspaceController(app).snapshot()["tutorial_status"] == "completed"
    assert app.session.to_dict() == task


def test_completion_from_an_outdated_workspace_is_rejected(app):
    controller = WorkspaceController(app)
    before = app._preferences_path.read_bytes()
    with pytest.raises(ValueError, match="页面已更新"):
        controller.dispatch("tutorial_finish", {}, "old-workspace")
    assert controller.snapshot()["tutorial_status"] == "not_started"
    assert app._preferences_path.read_bytes() == before


def test_state_save_failure_keeps_original_state_and_allows_retry(app, monkeypatch, caplog):
    import os
    controller = WorkspaceController(app)
    before = app._preferences_path.read_bytes()
    replace = os.replace

    def fail(path, target):
        if target == app._preferences_path:
            raise OSError("simulated tutorial disk failure")
        return replace(path, target)

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError, match="simulated tutorial disk failure"):
        controller.dispatch("tutorial_skip", {}, controller.snapshot()["stamp"])
    assert controller.snapshot()["tutorial_status"] == "not_started"
    assert app._preferences_path.read_bytes() == before
    assert any(record.exc_info for record in caplog.records if "Tutorial state save failed" in record.message)
    monkeypatch.setattr(os, "replace", replace)
    controller.dispatch("tutorial_skip", {}, controller.snapshot()["stamp"])
    assert WorkspaceController(app).snapshot()["tutorial_status"] == "skipped"
