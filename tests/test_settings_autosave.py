"""Automatic settings through the public desktop boundary and encrypted reload."""
import json
import tkinter as tk
import pytest

from promptsmith.preferences import load_settings
from promptsmith.ui import PromptSmithApp
from promptsmith.web_workspace import WorkspaceController
from tests.test_conversation_workspace import app


@pytest.mark.parametrize("action,changes", [
    ("effort", {"value":"low"}),
    ("settings_autosave", {"composer_theme":"dark"}),
    ("settings_autosave", {"window_width":1200}),
])
def test_window_restart_notice_only_follows_a_changed_window_size(app, action, changes):
    view=WorkspaceController(app)
    if action=="effort":
        view.dispatch(action,changes,view.snapshot()["stamp"])
    else:
        snap=view.settings_snapshot()
        view.settings_action(action,dict(revision=snap["revision"],connection=snap["connection"],
            values=dict(snap["values"],**changes),changed_fields=list(changes),key_action="keep",key=""))
    notices=view.snapshot()["notifications"]
    assert notices
    assert any("启动窗口大小下次启动生效" in item["body"] for item in notices) == ("window_width" in changes)


def test_resaving_an_unchanged_window_size_does_not_repeat_restart_notice(app):
    view=WorkspaceController(app);snap=view.settings_snapshot()
    view.settings_action("settings_autosave",dict(revision=snap["revision"],connection=snap["connection"],
        values=snap["values"],changed_fields=["window_width"],key_action="keep",key=""))
    assert all("启动窗口大小下次启动生效" not in item["body"] for item in view.snapshot()["notifications"])


def test_valid_edit_is_saved_and_ready_without_confirmation(app, tk_root):
    view = WorkspaceController(app)
    snap = view.settings_snapshot()
    public = dict(snap["connection"], model="new-offline-model")
    result = view.settings_action("settings_autosave", dict(revision=snap["revision"],
        connection=public, values=snap["values"], key_action="replace", key="disposable-auto-key"))
    assert result["settings"]["confirmed"]
    assert result["settings"]["connection"]["model"] == "new-offline-model"
    loaded = load_settings(app._preferences_path)
    assert loaded.api_key == "disposable-auto-key" and loaded.model_confirmed
    assert "disposable-auto-key" not in app._preferences_path.read_text(encoding="utf-8")
    assert "disposable-auto-key" not in json.dumps(view.snapshot())
    window = tk.Toplevel(tk_root)
    window.withdraw()
    restarted = PromptSmithApp(window, evidence_root=app.evidence_root)
    try:
        assert WorkspaceController(restarted).settings_snapshot()["confirmed"]
    finally:
        restarted.shutdown(wait=True)
        window.destroy()


def test_invalid_numeric_edit_does_not_replace_saved_settings(app):
    import pytest
    view = WorkspaceController(app)
    snap = view.settings_snapshot()
    values = dict(snap["values"], max_tokens="not-a-number")
    with pytest.raises(ValueError):
        view.settings_action("settings_autosave", dict(revision=snap["revision"], connection=snap["connection"],
            values=values, key_action="keep", key=""))
    assert view.settings_snapshot()["values"] == snap["values"]


def test_empty_model_can_be_saved_then_completed_without_confirmation(app):
    view = WorkspaceController(app)
    snap = view.settings_snapshot()
    result = view.settings_action("settings_autosave", dict(revision=snap["revision"], connection=dict(snap["connection"], model=""),
        values=snap["values"], key_action="keep", key=""))
    assert not result["settings"]["confirmed"]
    assert load_settings(app._preferences_path).connection["model"] == ""
    snap = view.settings_snapshot()
    result = view.settings_action("settings_autosave", dict(revision=snap["revision"], connection=dict(snap["connection"], model="restored-model"),
        values=snap["values"], key_action="keep", key=""))
    assert result["settings"]["confirmed"]


def test_web_uses_valid_existing_configuration_without_old_confirmation(app):
    app.api_model_var.set("edited-valid-model")
    assert WorkspaceController(app).settings_snapshot()["confirmed"]


def test_appearance_edit_saves_even_with_incomplete_model_draft(app):
    view = WorkspaceController(app)
    app.api_base_var.set("")
    app.api_model_var.set("")
    snap = view.settings_snapshot()
    result = view.settings_action("settings_autosave", dict(revision=snap["revision"], connection=snap["connection"],
        values=dict(snap["values"], composer_theme="dark"), changed_fields=["composer_theme"], key_action="keep", key=""))
    assert result["settings"]["values"]["composer_theme"] == "dark"
    assert load_settings(app._preferences_path).preferences["composer_theme"] == "dark"


def test_desktop_autosave_preserves_credentials_profiles_and_model_draft(app):
    view = WorkspaceController(app)
    before = json.loads(app._preferences_path.read_text(encoding="utf-8"))
    app.api_base_var.set("")
    snap = view.settings_snapshot()
    result = view.settings_action("settings_autosave", dict(revision=snap["revision"], connection=snap["connection"],
        values=dict(snap["values"], composer_theme="dark", max_tokens="invalid-draft"),
        changed_fields=["composer_theme"], key_action="keep", key=""))
    after = json.loads(app._preferences_path.read_text(encoding="utf-8"))
    for name in ("connection", "credentials", "model_profiles", "model_directory", "model_confirmation"):
        assert after.get(name) == before.get(name)
    assert result["settings"]["connection"]["base_url"] == ""
    assert after["preferences"]["max_tokens"] == before["preferences"]["max_tokens"]


def test_desktop_autosave_write_failure_keeps_disk_and_current_preferences(app, monkeypatch):
    import pytest
    import os
    from pathlib import Path
    view = WorkspaceController(app)
    before = app._preferences_path.read_bytes()
    snap = view.settings_snapshot()
    original = os.replace

    def fail_settings_replace(path, target):
        if Path(target) == app._preferences_path:
            raise OSError("simulated settings disk write failure")
        return original(path, target)

    monkeypatch.setattr(os, "replace", fail_settings_replace)
    with pytest.raises(OSError, match="simulated settings disk"):
        view.settings_action("settings_autosave", dict(revision=snap["revision"], connection=snap["connection"],
            values=dict(snap["values"], composer_theme="dark"), changed_fields=["composer_theme"], key_action="keep", key=""))
    assert app._preferences_path.read_bytes() == before
    assert view.settings_snapshot()["values"]["composer_theme"] == snap["values"]["composer_theme"]


def test_incomplete_source_connection_is_restored_after_switching_back(app):
    view = WorkspaceController(app)
    snap = view.settings_snapshot()
    source = snap["connection"]["provider"]
    destination = "OpenAI" if source != "OpenAI" else "DeepSeek"
    view.settings_action("settings_provider", dict(revision=snap["revision"],
        connection=dict(snap["connection"], base_url=""), values=snap["values"],
        key_action="keep", key="", target=destination))
    snap = view.settings_snapshot()
    view.settings_action("settings_provider", dict(revision=snap["revision"], connection=snap["connection"],
        values=snap["values"], key_action="keep", key="", target=source))
    assert view.settings_snapshot()["connection"]["base_url"] == ""
    assert not view.settings_snapshot()["confirmed"]


def test_dpapi_failure_is_a_persistence_failure_and_preserves_saved_settings(app, monkeypatch):
    import pytest
    from promptsmith.credentials import CredentialProtectionError
    from promptsmith.preferences import SettingsPersistenceError
    view = WorkspaceController(app)
    view.install_native_bridge()
    snap = view.settings_snapshot()
    before = app._preferences_path.read_bytes()
    monkeypatch.setattr("promptsmith.credentials.sys.platform", "unsupported")
    with pytest.raises(SettingsPersistenceError) as caught:
        view.settings_action("settings_autosave", dict(revision=snap["revision"], connection=snap["connection"],
            values=snap["values"], key_action="replace", key="disposable-dpapi-failure"))
    assert isinstance(caught.value.__cause__, CredentialProtectionError)
    assert app._preferences_path.read_bytes() == before
    assert "disposable-dpapi-failure" not in json.dumps(view.settings_snapshot())


def test_settings_size_failure_preserves_source_and_saved_document(app):
    import pytest
    from promptsmith.preferences import SettingsPersistenceError
    view = WorkspaceController(app)
    snap = view.settings_snapshot()
    document = json.loads(app._preferences_path.read_text(encoding="utf-8"))
    document["future_metadata"] = "x" * 1040000
    app._preferences_path.write_text(json.dumps(document), encoding="utf-8")
    before = app._preferences_path.read_bytes()
    with pytest.raises(SettingsPersistenceError, match="过大"):
        view.settings_action("settings_autosave", dict(revision=snap["revision"], connection=snap["connection"],
            values=dict(snap["values"], extra_skill_roots="C:/fixture-root\n" * 1000),
            changed_fields=["extra_skill_roots"], key_action="keep", key=""))
    assert app._preferences_path.read_bytes() == before
    assert view.settings_snapshot()["connection"]["provider"] == snap["connection"]["provider"]
