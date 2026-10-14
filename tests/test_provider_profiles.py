"""Public settings and desktop actions with disposable Windows credentials."""
import json
import sys

import pytest

from promptsmith.preferences import defaults, load_settings, save_preferences
from promptsmith.web_workspace import WorkspaceController
from tests.test_conversation_workspace import app


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI")


def connection(provider):
    return dict(provider=provider, protocol="OpenAI Chat Completions",
                base_url=f"https://{provider.lower()}.example.invalid/v1", model="offline-model")


def test_each_provider_keeps_encrypted_credentials_and_confirmation_after_restart(tmp_path):
    path = tmp_path / "settings.json"
    for provider, key in [("OpenAI", "disposable-openai-key"), ("DeepSeek", "disposable-deepseek-key")]:
        save_preferences(path, defaults(), connection(provider), api_key=key, model_confirmed=True)
    loaded = load_settings(path)
    assert loaded.api_key == "disposable-deepseek-key"
    assert loaded.model_profiles["OpenAI"].api_key == "disposable-openai-key"
    assert loaded.model_profiles["OpenAI"].model_confirmed
    assert loaded.model_profiles["DeepSeek"].model_confirmed
    assert "disposable-" not in path.read_text(encoding="utf-8")
    assert "disposable-" not in repr(loaded)

    save_preferences(path, defaults(), connection("DeepSeek"), api_key="")
    loaded = load_settings(path)
    assert not loaded.api_key and not loaded.model_confirmed
    assert loaded.model_profiles["OpenAI"].api_key == "disposable-openai-key"
    assert not loaded.model_profiles["DeepSeek"].api_key


def submit(view, action, *, target=None, key=None, base=None):
    snapshot = view.settings_snapshot()
    public = dict(snapshot["connection"])
    if base:
        public["base_url"] = base
    return view.settings_action(action, dict(revision=snapshot["revision"], connection=public,
        values=snapshot["values"], key_action="replace" if key else "keep", key=key or "", target=target))


def test_switch_preserves_drafts_and_restores_saved_keys_without_browser_disclosure(app, tk_root):
    view = WorkspaceController(app)
    submit(view, "settings_confirm", key="disposable-deepseek-profile", base="https://ds.example.invalid/v1")
    submit(view, "settings_provider", target="OpenAI")
    assert not view.settings_snapshot()["has_key"]
    submit(view, "settings_confirm", key="disposable-openai-profile")
    submit(view, "settings_provider", target="DeepSeek")
    assert app.api_key_var.get() == "disposable-deepseek-profile"
    assert app.api_base_var.get() == "https://ds.example.invalid/v1"
    assert view.settings_snapshot()["confirmed"]
    # Switching keeps an unsaved key only in Python, never in public snapshots.
    submit(view, "settings_provider", target="OpenAI", key="disposable-deepseek-draft")
    submit(view, "settings_provider", target="DeepSeek")
    assert app.api_key_var.get() == "disposable-deepseek-draft"
    assert view.settings_snapshot()["confirmed"]  # Valid Web configuration needs no explicit confirmation.
    assert "disposable-" not in json.dumps(view.snapshot(), ensure_ascii=False)
    loaded = load_settings(app._preferences_path)
    assert loaded.model_profiles["DeepSeek"].api_key == "disposable-deepseek-profile"
    assert loaded.model_profiles["OpenAI"].api_key == "disposable-openai-profile"

    import tkinter as tk
    from promptsmith.ui import PromptSmithApp
    window = tk.Toplevel(tk_root)
    window.withdraw()
    restarted = PromptSmithApp(window, evidence_root=app.evidence_root)
    try:
        other = WorkspaceController(restarted)
        assert restarted.api_key_var.get() == "disposable-openai-profile"
        submit(other, "settings_provider", target="DeepSeek")
        assert restarted.api_key_var.get() == "disposable-deepseek-profile"
        assert other.settings_snapshot()["confirmed"]
    finally:
        restarted.shutdown(wait=True)
        window.destroy()


def test_only_fetched_models_are_offered_and_directory_survives_restart(app, tk_root):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from tests.test_ui_reliability import pump

    calls = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append((self.path, self.headers.get("Authorization")))
            content = json.dumps({"data": [{"id": "deepseek-flash"}, {"id": "private-local-model"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(content)
        def log_message(self, *_args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    view = WorkspaceController(app)
    try:
        submit(view, "settings_confirm", key="disposable-list-key", base=f"http://127.0.0.1:{server.server_port}/v1")
        assert view.snapshot()["models"] == []
        submit(view, "settings_models")
        pump(app.root, app)
        models = view.snapshot()["models"]
        assert [m["id"] for m in models] == ["deepseek-flash", "private-local-model"]
        assert models[0]["name"] == "Deepseek V4.1 Flash" and models[0]["description"]
        assert not models[1]["reasoning"] and not models[1]["image"]
        assert calls == [("/v1/models", "Bearer disposable-list-key")]
        assert load_settings(app._preferences_path).model_ids == ("deepseek-flash", "private-local-model")
        assert view.settings_snapshot()["confirmed"]  # fetching is not a new confirmation
        import tkinter as tk
        from promptsmith.ui import PromptSmithApp
        window = tk.Toplevel(tk_root)
        window.withdraw()
        restarted = PromptSmithApp(window, evidence_root=app.evidence_root)
        try:
            assert [m["id"] for m in WorkspaceController(restarted).snapshot()["models"]] == ["deepseek-flash", "private-local-model"]
            restarted.api_key_var.set("disposable-replaced-key")
            assert WorkspaceController(restarted).snapshot()["models"] == []
        finally:
            restarted.shutdown(wait=True)
            window.destroy()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_cross_provider_picker_uses_origin_service_even_for_shared_gateway_model(app, tk_root):
    from promptsmith.web_workspace import view_stamp
    path = app._preferences_path
    # Public saved profiles simulate directories previously acquired from APIs.
    for provider, key in [("OpenAI", "disposable-picker-openai"), ("DeepSeek", "disposable-picker-deepseek")]:
        config = connection(provider)
        config["model"] = "gpt-6.1-sol"
        save_preferences(path, defaults(), config, api_key=key, model_confirmed=True, model_ids=("gpt-6.1-sol",))
    import tkinter as tk
    from promptsmith.ui import PromptSmithApp
    window = tk.Toplevel(tk_root)
    window.withdraw()
    restarted = PromptSmithApp(window, evidence_root=app.evidence_root)
    try:
        view = WorkspaceController(restarted)
        models = view.snapshot()["models"]
        assert {(m["id"], m["service_provider"]) for m in models} == {
            ("gpt-6.1-sol", "DeepSeek"), ("gpt-6.1-sol", "OpenAI")}
        view.dispatch("model", dict(id="gpt-6.1-sol", service="OpenAI"), view_stamp(restarted))
        assert restarted._draft_api_config().api_key == "disposable-picker-openai"
        assert restarted.api_base_var.get() == "https://openai.example.invalid/v1"
        assert view.settings_snapshot()["confirmed"]
        assert load_settings(path).connection["provider"] == "OpenAI"
        view.dispatch("model", dict(id="gpt-6.1-sol", service="DeepSeek"), view_stamp(restarted))
        assert restarted._draft_api_config().api_key == "disposable-picker-deepseek"
        assert load_settings(path).connection["provider"] == "DeepSeek"
    finally:
        restarted.shutdown(wait=True)
        window.destroy()


def test_legacy_single_profile_migrates_and_bad_secondary_key_does_not_break_active(tmp_path):
    path = tmp_path / "settings.json"
    save_preferences(path, defaults(), connection("DeepSeek"), api_key="disposable-legacy", model_confirmed=True)
    document = json.loads(path.read_text(encoding="utf-8"))
    document.pop("model_profiles")
    path.write_text(json.dumps(document), encoding="utf-8")
    save_preferences(path, defaults(), connection("OpenAI"), api_key="disposable-migrated", model_confirmed=True)
    loaded = load_settings(path)
    assert loaded.model_profiles["DeepSeek"].api_key == "disposable-legacy"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["model_profiles"]["DeepSeek"]["credentials"]["api_key"]["ciphertext"] = "%%%"
    path.write_text(json.dumps(document), encoding="utf-8")
    loaded = load_settings(path)
    assert loaded.api_key == "disposable-migrated" and loaded.model_confirmed
    assert not loaded.model_profiles["DeepSeek"].api_key and loaded.model_profiles["DeepSeek"].warning


def test_all_five_profiles_keep_parameters_directories_and_redacted_diagnostics(app):
    from promptsmith.model_catalog import PROVIDERS
    view = WorkspaceController(app)
    for index, provider in enumerate(PROVIDERS):
        submit(view, "settings_provider", target=provider)
        snapshot = view.settings_snapshot()
        snapshot["values"]["max_tokens"] = str(8192 + index)
        view.settings_action("settings_confirm", dict(revision=snapshot["revision"], connection=snapshot["connection"],
            values=snapshot["values"], key_action="replace", key="disposable-five-"+provider))
        app.widgets["api_model_combo"].configure(values=(provider+"-private",))
        submit(view, "settings_save")
    for index, provider in enumerate(PROVIDERS):
        submit(view, "settings_provider", target=provider)
        snapshot = view.settings_snapshot()
        assert app.api_key_var.get() == "disposable-five-"+provider
        assert snapshot["available_models"] == [provider+"-private"]
        assert snapshot["values"]["max_tokens"] == str(8192 + index)
        assert snapshot["confirmed"]
    saved = load_settings(app._preferences_path)
    assert set(saved.model_profiles) == set(PROVIDERS)
    content = "\n".join(row.text for row in app.runtime_log.entries_after())
    assert "Provider profile switched" in content
    assert "disposable-five-" not in content
    assert "disposable-five-" not in app._preferences_path.read_text(encoding="utf-8")
    assert not app.runtime_log.directory.exists()


def test_changed_legacy_active_projection_stays_authoritative_after_another_provider_save(tmp_path):
    path = tmp_path / "settings.json"
    save_preferences(path, defaults(), connection("OpenAI"), api_key="disposable-old-active", model_confirmed=True)
    document = json.loads(path.read_text(encoding="utf-8"))
    # Simulates a previous version clearing its active legacy projection.
    document.pop("credentials")
    document.pop("model_confirmation")
    path.write_text(json.dumps(document), encoding="utf-8")
    assert not load_settings(path).api_key
    save_preferences(path, defaults(), connection("DeepSeek"), api_key="disposable-new-active", model_confirmed=True)
    loaded = load_settings(path)
    assert not loaded.model_profiles["OpenAI"].api_key
    assert not loaded.model_profiles["OpenAI"].model_confirmed


def test_unreadable_existing_settings_abort_save_and_preserve_other_provider(tmp_path, monkeypatch):
    from pathlib import Path

    path = tmp_path / "settings.json"
    save_preferences(path, defaults(), connection("OpenAI"), api_key="disposable-preserved-key", model_confirmed=True)
    original = path.read_bytes()
    read_text = Path.read_text

    def denied_once(target, *args, **kwargs):
        if target == path:
            monkeypatch.setattr(Path, "read_text", read_text)
            raise PermissionError("Settings temporarily unavailable")
        return read_text(target, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", denied_once)
    with pytest.raises(PermissionError, match="temporarily unavailable"):
        save_preferences(path, defaults(), connection("DeepSeek"), api_key="disposable-pending-key")
    assert path.read_bytes() == original
    assert load_settings(path).model_profiles["OpenAI"].api_key == "disposable-preserved-key"

    # The same action is safe to retry after the transient filesystem fault.
    save_preferences(path, defaults(), connection("DeepSeek"), api_key="disposable-pending-key")
    loaded = load_settings(path)
    assert loaded.model_profiles["OpenAI"].api_key == "disposable-preserved-key"
    assert loaded.model_profiles["DeepSeek"].api_key == "disposable-pending-key"
