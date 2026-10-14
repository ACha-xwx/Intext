"""Custom services at the public saved-settings and desktop-action seams."""
import json
import sys

import pytest

from promptsmith.preferences import defaults, load_settings, save_preferences
from promptsmith.web_workspace import WorkspaceController
from tests.test_conversation_workspace import app


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI")


def custom_connection(family=None):
    value = dict(provider="麻豆科技", protocol="OpenAI Responses",
                 base_url="https://gateway.example.invalid/v1", model="private-alias")
    if family is not None:
        value["model_provider"] = family
    return value


def test_custom_service_requires_family_then_saves_and_restores_it(tmp_path):
    path = tmp_path / "settings.json"
    for family in (None, "", "other"):
        with pytest.raises(ValueError, match="模型供应商"):
            save_preferences(path, defaults(), custom_connection(family), api_key="disposable-custom-key")
    save_preferences(path, defaults(), custom_connection("OpenAI"), api_key="disposable-custom-key",
                     model_confirmed=True, model_ids=("private-alias",))
    loaded = load_settings(path)
    assert loaded.connection["model_provider"] == "OpenAI"
    assert loaded.model_profiles["麻豆科技"].api_key == "disposable-custom-key"
    assert loaded.model_confirmed and loaded.model_ids == ("private-alias",)
    assert "disposable-" not in path.read_text(encoding="utf-8")


def test_controller_saves_custom_family_switches_and_restores_after_restart(app, tk_root):
    from tests.test_provider_profiles import submit
    import tkinter as tk
    from promptsmith.ui import PromptSmithApp

    view = WorkspaceController(app)
    snapshot = view.settings_snapshot()
    with pytest.raises(ValueError, match="模型供应商"):
        view.settings_action("settings_save", dict(revision=snapshot["revision"], connection=custom_connection(),
            values=snapshot["values"], key_action="replace", key="disposable-custom-key"))
    assert app.provider_var.get() == "DeepSeek"  # Reject before changing source/key.
    snapshot = view.settings_snapshot()
    view.settings_action("settings_confirm", dict(revision=snapshot["revision"], connection=custom_connection("OpenAI"),
        values=snapshot["values"], key_action="replace", key="disposable-custom-key"))
    assert view.settings_snapshot()["confirmed"]
    assert "麻豆科技" in view.settings_snapshot()["saved_providers"]
    submit(view, "settings_provider", target="DeepSeek")
    submit(view, "settings_provider", target="麻豆科技")
    assert view.settings_snapshot()["connection"]["model_provider"] == "OpenAI"
    assert app.api_key_var.get() == "disposable-custom-key"
    window = tk.Toplevel(tk_root)
    window.withdraw()
    restarted = PromptSmithApp(window, evidence_root=app.evidence_root)
    try:
        other = WorkspaceController(restarted)
        assert "麻豆科技" in other.settings_snapshot()["saved_providers"]
        assert other.settings_snapshot()["confirmed"]
        assert restarted._draft_api_config().model_provider == "OpenAI"
        assert "disposable-" not in json.dumps(other.snapshot(), ensure_ascii=False)
    finally:
        restarted.shutdown(wait=True)
        window.destroy()


def test_legacy_custom_key_survives_but_requires_explicit_family_selection(tmp_path):
    from promptsmith.credentials import encrypt_api_key
    path = tmp_path / "settings.json"
    old = custom_connection()
    path.write_text(json.dumps(dict(version=2, preferences=defaults(), connection=old,
        credentials={"api_key": encrypt_api_key("disposable-legacy-custom", old)})), encoding="utf-8")
    loaded = load_settings(path)
    assert loaded.api_key == "disposable-legacy-custom"
    assert not loaded.model_confirmed
    assert "模型供应商" in loaded.warning


def test_existing_builtin_confirmation_format_remains_valid(tmp_path):
    import hashlib
    from promptsmith.preferences import FIELDS
    from promptsmith.credentials import encrypt_api_key

    path = tmp_path / "settings.json"
    old = dict(provider="OpenAI", protocol="OpenAI Responses", base_url="https://api.openai.com/v1", model="gpt-6.1-sol")
    credential = encrypt_api_key("disposable-builtin-legacy", old)
    # The published pre-custom-provider v1 confirmation format had four fields.
    basis = dict(connection=old, parameters={key: defaults()[key] for key, spec in FIELDS.items() if spec.category == "模型"}, credential=credential)
    fingerprint = hashlib.sha256(b"PromptSmith.model_confirmation.v1\0" + json.dumps(basis, sort_keys=True, ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()
    path.write_text(json.dumps(dict(version=2, composer_defaults=1, preferences=defaults(), connection=old,
        credentials={"api_key": credential}, model_confirmation=dict(version=1, fingerprint=fingerprint))), encoding="utf-8")
    assert load_settings(path).model_confirmed


def test_website_is_saved_as_metadata_without_invalidating_model_confirmation(app):
    view = WorkspaceController(app)
    snapshot = view.settings_snapshot()
    public = dict(snapshot["connection"], website="https://gateway.example.invalid")
    view.settings_action("settings_save", dict(revision=snapshot["revision"], connection=public,
        values=snapshot["values"], key_action="keep", key=""))
    assert view.settings_snapshot()["confirmed"]
    loaded = load_settings(app._preferences_path)
    assert loaded.connection["website"] == "https://gateway.example.invalid"
    assert loaded.model_confirmed


def test_custom_models_and_settings_profiles_use_explicit_family(app):
    view = WorkspaceController(app)
    snap = view.settings_snapshot()
    view.settings_action("settings_confirm", dict(revision=snap["revision"], connection=custom_connection("OpenAI"),
        values=snap["values"], key_action="replace", key="disposable-family-key"))
    app.widgets["api_model_combo"].configure(values=("private-alias",))
    snap = view.settings_snapshot()
    view.settings_action("settings_save", dict(revision=snap["revision"], connection=snap["connection"],
        values=snap["values"], key_action="keep", key=""))
    assert view.settings_snapshot()["provider_families"]["麻豆科技"] == "OpenAI"
    models = view.snapshot()["models"]
    custom = next(m for m in models if m["id"] == "private-alias")
    assert custom["provider"] == "OpenAI" and custom["service_provider"] == "麻豆科技"
    assert not custom["image"] and not custom["reasoning"]


def test_delete_custom_service_removes_saved_key_directory_and_survives_next_save(app):
    from tests.test_provider_profiles import submit
    view = WorkspaceController(app)
    snap = view.settings_snapshot()
    view.settings_action("settings_confirm", dict(revision=snap["revision"], connection=custom_connection("OpenAI"),
        values=snap["values"], key_action="replace", key="disposable-delete-key"))
    app.widgets["api_model_combo"].configure(values=("private-alias",))
    submit(view, "settings_save")
    snap = view.settings_snapshot()
    view.settings_action("settings_delete_provider", dict(revision=snap["revision"], target="麻豆科技"))
    assert view.settings_snapshot()["connection"]["provider"] == "DeepSeek"
    assert "麻豆科技" not in view.settings_snapshot()["saved_providers"]
    submit(view, "settings_save")
    loaded = load_settings(app._preferences_path)
    assert "麻豆科技" not in loaded.model_profiles
    assert "麻豆科技" not in app._preferences_path.read_text(encoding="utf-8")
    assert all(m["service_provider"] != "麻豆科技" for m in view.snapshot()["models"])
    with pytest.raises(ValueError, match="内置"):
        view.settings_action("settings_delete_provider", dict(revision=view.settings_snapshot()["revision"], target="DeepSeek"))


def test_custom_source_type_draft_restores_after_switching_to_builtin(app):
    from tests.test_provider_profiles import submit
    view = WorkspaceController(app)
    snap = view.settings_snapshot()
    view.settings_action("settings_confirm", dict(revision=snap["revision"], connection=custom_connection("OpenAI"),
        values=snap["values"], key_action="replace", key="disposable-source-draft"))
    snap = view.settings_snapshot()
    draft = dict(snap["connection"], model_provider="Anthropic", protocol="Anthropic Messages")
    view.settings_action("settings_provider", dict(revision=snap["revision"], connection=draft,
        values=snap["values"], key_action="keep", key="", target="DeepSeek"))
    submit(view, "settings_provider", target="麻豆科技")
    assert view.settings_snapshot()["connection"]["model_provider"] == "Anthropic"
    assert view.settings_snapshot()["connection"]["protocol"] == "Anthropic Messages"
    assert view.settings_snapshot()["confirmed"]  # Supported family and valid configuration are sufficient.


def test_delete_write_failure_keeps_custom_profile_and_credential_for_retry(app, monkeypatch):
    import os
    view = WorkspaceController(app)
    snap = view.settings_snapshot()
    view.settings_action("settings_confirm", dict(revision=snap["revision"], connection=custom_connection("OpenAI"),
        values=snap["values"], key_action="replace", key="disposable-delete-retry"))
    before = app._preferences_path.read_bytes()
    data = dict(revision=view.settings_snapshot()["revision"], target="麻豆科技")
    def denied(*_args):
        raise PermissionError("Disposable atomic-write failure")
    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", denied)
        with pytest.raises(PermissionError, match="atomic-write"):
            view.settings_action("settings_delete_provider", data)
    assert app._preferences_path.read_bytes() == before
    assert app.api_key_var.get() == "disposable-delete-retry"
    assert view.settings_snapshot()["confirmed"]
    view.settings_action("settings_delete_provider", data)
    assert "麻豆科技" not in load_settings(app._preferences_path).model_profiles
