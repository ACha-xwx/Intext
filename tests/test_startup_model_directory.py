"""Public desktop startup against an isolated, controllable HTTP directory."""
import json
import sys
import time
import tkinter as tk
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread

import pytest

from promptsmith.preferences import defaults, load_settings, save_preferences
from promptsmith.ui import PromptSmithApp
from promptsmith.web_workspace import WorkspaceController


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI desktop")


def wait_for(window, predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        window.update()
        time.sleep(.01)
    window.update()
    assert predicate()


@pytest.fixture
def directory_server():
    class Directory:
        calls = []
        entered = Event()
        release = Event()
        status = 200
        ids = ["deepseek-flash", "new-private-model"]
    fixture = Directory()
    fixture.release.set()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            fixture.calls.append((self.path, self.headers.get("Authorization") or self.headers.get("x-api-key")))
            ids, status = list(fixture.ids), fixture.status
            fixture.entered.set()
            fixture.release.wait(5)
            body = json.dumps({"data": [{"id": value} for value in ids]} if status == 200
                              else {"error": {"message": "fixture denied", "code": "denied"}}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    fixture.base = f"http://127.0.0.1:{server.server_port}/v1"
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    yield fixture
    fixture.release.set()
    server.shutdown()
    server.server_close()
    worker.join(2)


@pytest.fixture
def start_app(tk_root, tmp_path, monkeypatch):
    # This boundary has no personal configuration or model generation requests.
    for name in ("PROMPTSMITH_PROVIDER", "PROMPTSMITH_API_BASE_URL", "PROMPTSMITH_MODEL", "PROMPTSMITH_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("promptsmith.ui.warm_local_skill_index", lambda _roots: None)
    applications = []

    def start():
        window = tk.Toplevel(tk_root)
        window.withdraw()
        app = PromptSmithApp(window, evidence_root=tmp_path / "runs")
        applications.append(app)
        view = WorkspaceController(app)
        view.install_native_bridge()
        return app, view

    yield start
    for app in applications:
        app.shutdown(wait=True)
        app.root.destroy()


def save_profile(tmp_path, server, provider="DeepSeek", key="disposable-startup-key", ids=()):
    connection = dict(provider=provider, protocol="OpenAI Chat Completions", base_url=server.base,
                      model="deepseek-flash")
    if provider not in {"OpenAI", "Anthropic", "xAI", "Google", "DeepSeek"}:
        connection["model_provider"] = "OpenAI"
    save_preferences(tmp_path / "settings.json", defaults(), connection,
                     api_key=key, model_confirmed=bool(key), model_ids=ids)


def test_saved_key_fetches_directory_at_startup_without_click(start_app, directory_server, tmp_path):
    save_profile(tmp_path, directory_server)
    app, view = start_app()
    wait_for(app.root, lambda: bool(view.snapshot()["models"]))
    assert directory_server.calls == [("/v1/models", "Bearer disposable-startup-key")]
    assert [model["id"] for model in view.snapshot()["models"]] == ["deepseek-flash", "new-private-model"]
    assert load_settings(tmp_path / "settings.json").model_ids == ("deepseek-flash", "new-private-model")
    assert view.settings_snapshot()["confirmed"]
    assert not app.busy
    assert "model_list_button" in app.widgets


def test_slow_startup_directory_keeps_cached_models_and_settings_usable(start_app, directory_server, tmp_path):
    directory_server.release.clear()
    save_profile(tmp_path, directory_server, ids=("cached-model",))
    app, view = start_app()
    wait_for(app.root, directory_server.entered.is_set)
    assert not app.busy
    assert [model["id"] for model in view.snapshot()["models"]] == ["cached-model"]
    assert "正在自动获取" in view.settings_snapshot().get("directory_status", "")
    snapshot = view.settings_snapshot()
    view.settings_action("settings_provider", dict(revision=snapshot["revision"],
        connection=snapshot["connection"], values=snapshot["values"], key_action="keep", key="", target="OpenAI"))
    assert view.settings_snapshot()["connection"]["provider"] == "OpenAI"
    directory_server.release.set()
    wait_for(app.root, lambda: any(model["id"] == "new-private-model" for model in view.snapshot()["models"]))
    assert view.settings_snapshot()["connection"]["provider"] == "OpenAI"
    assert load_settings(tmp_path / "settings.json").model_profiles["DeepSeek"].model_ids == ("deepseek-flash", "new-private-model")


def test_failed_auto_fetch_keeps_cache_and_explains_how_to_retry(start_app, directory_server, tmp_path):
    directory_server.status = 403
    save_profile(tmp_path, directory_server, ids=("cached-model",))
    app, view = start_app()
    wait_for(app.root, lambda: "失败" in view.settings_snapshot().get("directory_status", ""))
    assert [model["id"] for model in view.snapshot()["models"]] == ["cached-model"]
    assert load_settings(tmp_path / "settings.json").model_ids == ("cached-model",)
    assert "获取模型" in view.settings_snapshot()["directory_status"]
    assert not app.busy and view.settings_snapshot()["confirmed"]
    assert any("自动获取模型列表失败" in row["body"] and row["level"] == "error"
               for row in view.snapshot()["notifications"])  # closable feedback, no modal
    content = "\n".join(row.text for row in app.runtime_log.entries_after())
    assert "Startup model directory failed" in content and "Traceback" in content
    assert "disposable-startup-key" not in content
    assert not app.runtime_log.directory.exists()


def test_every_saved_service_with_a_key_refreshes_once_and_no_key_service_is_skipped(start_app, directory_server, tmp_path):
    for provider, key in [("OpenAI", "disposable-openai"), ("DeepSeek", "disposable-deepseek"),
                          ("GPT中转", "disposable-custom"), ("Google", "")]:
        save_profile(tmp_path, directory_server, provider, key, ("cached-model",))
    app, view = start_app()
    wait_for(app.root, lambda: sum(model["id"] == "new-private-model" for model in view.snapshot()["models"]) == 3)
    assert sorted(directory_server.calls) == [("/v1/models", "Bearer disposable-custom"),
        ("/v1/models", "Bearer disposable-deepseek"), ("/v1/models", "Bearer disposable-openai")]
    saved = load_settings(tmp_path / "settings.json")
    assert saved.connection["provider"] == "Google" and not saved.api_key
    assert saved.model_profiles["GPT中转"].model_ids == ("deepseek-flash", "new-private-model")
    assert not view.settings_snapshot()["confirmed"]


def test_key_edit_discards_delayed_old_directory(start_app, directory_server, tmp_path):
    directory_server.release.clear()
    save_profile(tmp_path, directory_server, ids=("cached-model",))
    app, view = start_app()
    wait_for(app.root, directory_server.entered.is_set)
    app.api_key_var.set("disposable-new-draft-key")
    directory_server.release.set()
    # Observe the public diagnostic outcome after the owner consumes the result;
    # the completion queue can already be empty by the time root.update returns.
    wait_for(app.root, lambda: any("Startup model directory result discarded" in row.text
                                 for row in app.runtime_log.entries_after()))
    assert view.snapshot()["models"] == []
    assert load_settings(tmp_path / "settings.json").model_ids == ("cached-model",)
    assert load_settings(tmp_path / "settings.json").api_key == "disposable-startup-key"
    assert view.settings_snapshot()["directory_status"] == ""
    assert view.settings_snapshot()["confirmed"]  # Valid edited key is usable, but not saved by directory refresh.


def test_auto_failure_can_be_retried_with_existing_button(start_app, directory_server, tmp_path):
    directory_server.status = 403
    save_profile(tmp_path, directory_server, ids=("cached-model",))
    app, view = start_app()
    wait_for(app.root, lambda: "失败" in view.settings_snapshot()["directory_status"])
    directory_server.status = 200
    app.widgets["model_list_button"].invoke()
    wait_for(app.root, lambda: not app.busy)
    assert [model["id"] for model in view.snapshot()["models"]] == ["deepseek-flash", "new-private-model"]
    assert len(directory_server.calls) == 2
    assert view.settings_snapshot()["directory_status"] == ""


def test_delete_during_automatic_fetch_does_not_restore_service_or_saved_key(start_app, directory_server, tmp_path):
    directory_server.release.clear()
    save_profile(tmp_path, directory_server, "GPT中转", ids=("cached-model",))
    app, view = start_app()
    wait_for(app.root, directory_server.entered.is_set)
    snapshot = view.settings_snapshot()
    view.settings_action("settings_delete_provider", dict(revision=snapshot["revision"], target="GPT中转"))
    directory_server.release.set()
    wait_for(app.root, lambda: bool(app.completions.qsize()))
    for _ in range(10):
        app.root.update()
        time.sleep(.01)
    assert "GPT中转" not in view.settings_snapshot()["saved_providers"]
    assert "GPT中转" not in load_settings(tmp_path / "settings.json").model_profiles
    assert not any(model["service_provider"] == "GPT中转" for model in view.snapshot()["models"])


def test_close_during_delayed_fetch_does_not_write_late_directory(start_app, directory_server, tmp_path):
    directory_server.release.clear()
    save_profile(tmp_path, directory_server, ids=("cached-model",))
    app, _view = start_app()
    wait_for(app.root, directory_server.entered.is_set)
    started = time.monotonic()
    app.shutdown(wait=False)
    assert time.monotonic() - started < .5
    directory_server.release.set()
    wait_for(app.root, lambda: bool(app.completions.qsize()))
    assert load_settings(tmp_path / "settings.json").model_ids == ("cached-model",)


def test_manual_fetch_supersedes_inflight_startup_result(start_app, directory_server, tmp_path):
    directory_server.release.clear()
    directory_server.ids = ["old-startup-model"]
    save_profile(tmp_path, directory_server, ids=("cached-model",))
    app, view = start_app()
    wait_for(app.root, directory_server.entered.is_set)
    directory_server.ids = ["manual-fresh-model"]
    app.widgets["model_list_button"].invoke()
    wait_for(app.root, lambda: len(directory_server.calls) == 2)
    directory_server.release.set()
    wait_for(app.root, lambda: not app.busy)
    assert [model["id"] for model in view.snapshot()["models"]] == ["manual-fresh-model"]
    assert load_settings(tmp_path / "settings.json").model_ids == ("manual-fresh-model",)
    assert view.settings_snapshot()["directory_status"] == ""


def test_saved_settings_without_a_key_do_not_make_a_startup_request(start_app, directory_server, tmp_path):
    save_profile(tmp_path, directory_server, key="")
    app, view = start_app()
    app.root.update()
    assert directory_server.calls == []
    assert view.settings_snapshot()["directory_status"] == ""
    assert not app.busy


@pytest.mark.parametrize("provider,protocol,path,auth", [
    ("DeepSeek", "OpenAI Chat Completions", "/v1/models", "Bearer disposable-protocol"),
    ("OpenAI", "OpenAI Responses", "/v1/models", "Bearer disposable-protocol"),
    ("Anthropic", "Anthropic Messages", "/v1/models?limit=1000", "disposable-protocol"),
])
def test_startup_directory_uses_saved_protocol_and_auth(start_app, directory_server, tmp_path, provider, protocol, path, auth):
    config = dict(provider=provider, protocol=protocol, base_url=directory_server.base, model="private-alias")
    save_preferences(tmp_path / "settings.json", defaults(), config, api_key="disposable-protocol")
    app, view = start_app()
    wait_for(app.root, lambda: bool(view.snapshot()["models"]))
    assert directory_server.calls == [(path, auth)]
    assert view.settings_snapshot()["confirmed"]  # Valid configuration is usable without a confirmation button.
    assert not load_settings(tmp_path / "settings.json").model_confirmed  # GET does not write confirmation.
