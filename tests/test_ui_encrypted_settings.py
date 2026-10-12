import json
import logging
import sys
import tkinter as tk

import pytest

from promptsmith.credentials import CredentialProtectionError
from promptsmith.debug_console import save_debug_preference
from promptsmith.preferences import defaults, load_settings, save_preferences
from promptsmith.ui import PromptSmithApp


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Uses Windows DPAPI and Tk")
CONNECTION = {"provider": "Custom fixture", "model_provider": "Google", "protocol": "OpenAI Chat Completions",
              "base_url": "https://example.invalid/v1", "model": "offline-model"}


@pytest.fixture
def app(tk_root, tmp_path):
    window = tk.Toplevel(tk_root)
    window.withdraw()
    instance = PromptSmithApp(window, diagnostics_root=tmp_path, evidence_root=tmp_path / "runs")
    instance.provider_var.set(CONNECTION["provider"])
    instance.model_provider_var.set(CONNECTION["model_provider"])
    instance.protocol_var.set(CONNECTION["protocol"])
    instance.api_base_var.set(CONNECTION["base_url"])
    instance.api_model_var.set(CONNECTION["model"])
    instance.api_key_var.set("disposable-ui-key")
    yield instance
    instance.shutdown(wait=True)
    window.destroy()


def reopen(tk_root, data_root):
    window = tk.Toplevel(tk_root)
    window.withdraw()
    return window, PromptSmithApp(window, diagnostics_root=data_root, evidence_root=data_root / "runs")


def test_key_restore_replace_clear_and_save_without_confirmation(app, tk_root):
    assert app.save_settings()
    assert not app._model_settings_confirmed()
    for key in ("disposable-ui-key", "disposable-ui-replacement", ""):
        app.api_key_var.set(key)
        assert app.save_settings()
        window, other = reopen(tk_root, app._preferences_path.parent)
        try:
            assert other.api_key_var.get() == key
            assert not other._model_settings_confirmed()
            if key:
                other.confirm_model_settings()
                assert other._model_settings_confirmed()
                logging.getLogger("promptsmith.credential-test").error("Synthetic redaction check: %s", key)
                assert key not in other.runtime_log.save().read_text(encoding="utf-8")
        finally:
            other.shutdown(wait=True)
            window.destroy()
    assert "credentials" not in json.loads(app._preferences_path.read_text(encoding="utf-8"))
    app.api_key_var.set("edited-unsaved-key")
    assert "未保存" in app.settings_status_var.get()


def test_test_connection_does_not_save_or_confirm(app, monkeypatch):
    from types import SimpleNamespace
    assert app.save_settings()
    previous = app._preferences_path.read_bytes()
    app.api_key_var.set("disposable-test-only-key")
    monkeypatch.setattr(app, "_client", lambda *_: SimpleNamespace(
        test_connection=lambda: SimpleNamespace(model="offline-model", latency_ms=1, probe_truncated=False)))
    monkeypatch.setattr(app, "_submit", lambda operation, success, failure: success(operation()))
    app.test_connection()
    assert not app._model_settings_confirmed()
    assert app._preferences_path.read_bytes() == previous


def test_debug_toggle_never_saves_model_drafts(app, tk_root):
    assert app.save_settings()
    original = json.loads(app._preferences_path.read_text(encoding="utf-8"))
    app.api_base_var.set("https://different.invalid")
    assert app.api_key_var.get() == ""
    app.api_key_var.set("unsaved-disposable-key")
    app.preference_vars["temperature"].set("0.7")
    app.widgets["debug_console_toggle"].invoke()
    saved = json.loads(app._preferences_path.read_text(encoding="utf-8"))
    assert saved["connection"] == original["connection"]
    assert saved["credentials"] == original["credentials"]
    assert saved["preferences"]["temperature"] == original["preferences"]["temperature"]
    assert saved["preferences"]["debug_console_enabled"]
    window, other = reopen(tk_root, app._preferences_path.parent)
    try:
        assert other.api_key_var.get() == "disposable-ui-key" and other.debug_console is not None
    finally:
        other.shutdown(wait=True)
        window.destroy()


def test_decryption_failure_explained_and_reentry_repairs(app, tk_root):
    app.confirm_model_settings()
    saved = json.loads(app._preferences_path.read_text(encoding="utf-8"))
    saved["credentials"]["api_key"]["ciphertext"] = "broken-ciphertext"
    saved["preferences"]["font_size"] = 15
    app._preferences_path.write_text(json.dumps(saved), encoding="utf-8")
    window, other = reopen(tk_root, app._preferences_path.parent)
    try:
        assert other.preferences["font_size"] == 15 and other.api_key_var.get() == ""
        assert "重新输入" in other.status_var.get() and "重新输入" in other.settings_status_var.get()
        assert not other._model_settings_confirmed()
        assert any("Cannot restore saved API Key" in row.text and "Traceback" in row.text
                   for row in other.runtime_log.entries_after())
        other.api_key_var.set("disposable-repair-key")
        other.confirm_model_settings()
        assert other._model_settings_confirmed() and not load_settings(other._preferences_path).warning
    finally:
        other.shutdown(wait=True)
        window.destroy()


@pytest.mark.parametrize("operation", ["encrypt", "write"])
def test_save_failure_preserves_old_settings_and_confirmation_can_retry(app, monkeypatch, operation):
    app.confirm_model_settings()
    previous = app._preferences_path.read_bytes()
    app.api_key_var.set("disposable-key-after-failure")
    messages = []
    monkeypatch.setattr(app, "_show_error", lambda *args, **kw: messages.append(args))
    with monkeypatch.context() as failure:
        if operation == "encrypt":
            def fail(*args, **kwargs):
                raise CredentialProtectionError("DPAPI 加密失败（系统错误码 5）。")
            failure.setattr("promptsmith.credentials._dpapi", fail)
        else:
            def fail(*args, **kwargs):
                raise PermissionError("Synthetic settings write denied")
            failure.setattr("promptsmith.preferences.os.replace", fail)
        app.confirm_model_settings()
        assert not app._model_settings_confirmed()
        assert app._preferences_path.read_bytes() == previous
        assert "重试" in app.settings_status_var.get() and messages
        assert not list(app._preferences_path.parent.glob("*.tmp"))
        content = "\n".join(row.text for row in app.runtime_log.entries_after())
        assert "Traceback" in content and "Cannot save settings" in content
        assert "disposable-key-after-failure" not in content and "disposable-ui-key" not in content
    assert load_settings(app._preferences_path).model_confirmed
    app.confirm_model_settings()
    assert app._model_settings_confirmed()
    assert load_settings(app._preferences_path).api_key == "disposable-key-after-failure"


def test_environment_endpoint_override_does_not_reuse_saved_key(tk_root, tmp_path, monkeypatch):
    save_preferences(tmp_path / "settings.json", defaults(), CONNECTION, api_key="disposable-env-key")
    monkeypatch.setenv("PROMPTSMITH_API_BASE_URL", "https://override.invalid")
    window, app = reopen(tk_root, tmp_path)
    try:
        assert app.api_key_var.get() == "" and "重新输入" in app.status_var.get()
        assert load_settings(tmp_path / "settings.json").api_key == "disposable-env-key"
    finally:
        app.shutdown(wait=True)
        window.destroy()


def test_legacy_debug_migration_preserves_credentials_and_new_file_wins(tk_root, tmp_path):
    path = tmp_path / "settings.json"
    save_preferences(path, defaults(), CONNECTION, api_key="disposable-migration-key")
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["preferences"]["debug_console_enabled"]
    data["version"] = 1
    path.write_text(json.dumps(data), encoding="utf-8")
    legacy = tmp_path / "diagnostics.json"
    save_debug_preference(legacy, True)
    original = legacy.read_bytes()
    window, app = reopen(tk_root, tmp_path)
    try:
        assert app.debug_console is not None
        assert load_settings(path).api_key == "disposable-migration-key"
        assert json.loads(path.read_text(encoding="utf-8"))["credentials"] == data["credentials"]
        assert legacy.read_bytes() == original
        app._close_debug_console()
    finally:
        app.shutdown(wait=True)
        window.destroy()
    window, app = reopen(tk_root, tmp_path)
    try:
        assert app.debug_console is None and not app.debug_console_enabled_var.get()
    finally:
        app.shutdown(wait=True)
        window.destroy()


def test_default_settings_path_uses_application_data_dir(tk_root, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    window = tk.Toplevel(tk_root)
    app = PromptSmithApp(window)
    try:
        assert app._preferences_path == tmp_path / "PromptSmith" / "settings.json"
        assert app.save_settings()
        assert app._preferences_path.exists()
        assert not app.runtime_log.directory.exists()
    finally:
        app.shutdown(wait=True)
        window.destroy()


def test_long_failure_status_does_not_clip_save_controls(app):
    app.show_settings()
    app.preference_vars["font_size"].set("18")
    assert app.save_settings()
    app.root.geometry("960x640")
    app.settings_status_var.set("API Key 无法解密，请在模型设置中重新输入并确认。其它设置已恢复。" * 3)
    app.root.update()
    canvas = app.widgets["settings_page_canvas"]
    for key in ("settings_save_button", "settings_restore_button"):
        button = app.widgets[key]
        assert button.winfo_rooty() + button.winfo_height() <= canvas.winfo_rooty() + canvas.winfo_height()


def test_confirmation_survives_nonmodel_save_and_debug_draft_toggle(app, tk_root):
    app.confirm_model_settings()
    app.preference_vars["font_size"].set("15")
    app.preference_vars["search_timeout"].set("77")
    assert app.save_settings() and app._model_settings_confirmed()
    original = json.loads(app._preferences_path.read_text(encoding="utf-8"))
    assert original["model_confirmation"]["version"] == 1
    assert "disposable-ui-key" not in app._preferences_path.read_text(encoding="utf-8")
    app.api_model_var.set("unsaved-model")
    assert not app._model_settings_confirmed()
    app.widgets["debug_console_toggle"].invoke()
    saved = json.loads(app._preferences_path.read_text(encoding="utf-8"))
    assert saved["model_confirmation"] == original["model_confirmation"]
    assert saved["credentials"] == original["credentials"]
    window, other = reopen(tk_root, app._preferences_path.parent)
    try:
        assert other._model_settings_confirmed() and other._api_config().model == "offline-model"
        assert other.preferences["font_size"] == 15 and other.preferences["search_timeout"] == 77
        assert other.debug_console is not None
        assert any("Model confirmation restored" in row.text for row in other.runtime_log.entries_after())
        content = other.runtime_log.save().read_text(encoding="utf-8")
        assert "Model confirmation restored" in content and "disposable-ui-key" not in content
    finally:
        other.shutdown(wait=True)
        window.destroy()


@pytest.mark.parametrize("field,value", [("api_model_var", "other-model"), ("api_key_var", "replacement-key"),
    ("api_key_var", ""), ("api_base_var", "https://other.invalid"), ("temperature", "0.4"),
    ("generation_timeout", "200"), ("connection_timeout", "20"), ("max_tokens", "1234"),
    ("top_p", "0.8"), ("reasoning_effort", "omit")])
def test_saved_model_edits_require_new_confirmation_after_restart(app, tk_root, field, value):
    app.confirm_model_settings()
    variable = getattr(app, field) if field.endswith("_var") else app.preference_vars[field]
    variable.set(value)
    assert not app._model_settings_confirmed()
    assert app.save_settings()
    assert "model_confirmation" not in json.loads(app._preferences_path.read_text(encoding="utf-8"))
    assert any("Model confirmation invalidated" in row.text for row in app.runtime_log.entries_after())
    window, other = reopen(tk_root, app._preferences_path.parent)
    try:
        assert not other._model_settings_confirmed()
        with pytest.raises(ValueError, match="确认"):
            other._api_config()
    finally:
        other.shutdown(wait=True)
        window.destroy()


def test_environment_model_override_requires_confirmation(app, tk_root, monkeypatch):
    app.confirm_model_settings()
    monkeypatch.setenv("PROMPTSMITH_MODEL", "override-model")
    window, other = reopen(tk_root, app._preferences_path.parent)
    try:
        assert other.api_key_var.get() == "disposable-ui-key"
        assert not other._model_settings_confirmed()
        assert "启动时" in other.status_var.get() and "确认" in other.status_var.get()
    finally:
        other.shutdown(wait=True)
        window.destroy()


def test_legacy_settings_need_confirmation_once(app, tk_root):
    assert app.save_settings()
    window, other = reopen(tk_root, app._preferences_path.parent)
    try:
        assert not other._model_settings_confirmed()
        other.confirm_model_settings()
        assert other._model_settings_confirmed()
    finally:
        other.shutdown(wait=True)
        window.destroy()
    window, other = reopen(tk_root, app._preferences_path.parent)
    try:
        assert other._model_settings_confirmed()
    finally:
        other.shutdown(wait=True)
        window.destroy()


@pytest.mark.parametrize("action", ["new", "open"])
def test_restored_model_confirmation_survives_conversation_switch(app, tk_root, tmp_path, monkeypatch, action):
    from promptsmith.session import SessionState
    from promptsmith.storage import save_session
    app.confirm_model_settings()
    window, other = reopen(tk_root, app._preferences_path.parent)
    try:
        monkeypatch.setattr("promptsmith.ui.messagebox.askyesno", lambda *_args, **_kwargs: True)
        before = other._api_config()
        if action == "new":
            other.new_session()
        else:
            path = tmp_path / "session.json"
            save_session(SessionState.new(), path)
            monkeypatch.setattr("promptsmith.ui.filedialog.askopenfilename", lambda **_kwargs: str(path))
            other.open_session()
        assert other._model_settings_confirmed()
        assert other._api_config() == before
        assert load_settings(other._preferences_path).model_confirmed
    finally:
        other.shutdown(wait=True)
        window.destroy()


def test_invalid_saved_protocol_options_do_not_restore_confirmation(app, tk_root):
    from promptsmith.preferences import load_settings
    app.confirm_model_settings()
    saved = json.loads(app._preferences_path.read_text(encoding="utf-8"))
    saved["connection"]["protocol"] = "Anthropic Messages"
    # A saved approval cannot turn otherwise invalid protocol options into a usable config.
    save_preferences(app._preferences_path, {**defaults(), "temperature": "0.4", "top_p": "0.8"},
                     saved["connection"], api_key="disposable-ui-key", model_confirmed=True)
    assert load_settings(app._preferences_path).model_confirmed
    window, other = reopen(tk_root, app._preferences_path.parent)
    try:
        assert not other._model_settings_confirmed()
        assert "修正" in other.status_var.get()
        assert any("saved configuration is invalid" in row.text and "Traceback" in row.text
                   for row in other.runtime_log.entries_after())
    finally:
        other.shutdown(wait=True)
        window.destroy()
