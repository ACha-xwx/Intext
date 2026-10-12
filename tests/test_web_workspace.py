"""Browser projection and queued action contracts; no genuine model calls."""
import json
import threading

import pytest

from promptsmith.web_workspace import DesktopApi, WorkspaceController, view_stamp
from tests.test_conversation_workspace import app, install_session
from tests.test_response_workspace import questions
from tests.test_final_delivery import confirmed_plan_session
from promptsmith.api import ApiResult, ModelListResult
from promptsmith.preferences import FIELDS, load_settings


def controller(app):
    return WorkspaceController(app)


def test_projection_never_exposes_model_credentials_and_is_serializable(app):
    view = controller(app)
    snapshot = view.snapshot()
    encoded = json.dumps(snapshot, ensure_ascii=False)
    assert app.api_key_var.get() not in encoded
    assert "api_key" not in encoded
    assert snapshot["effort"] == "high" and snapshot["cards"][0]["kind"] == "welcome"
    assert all(len(snapshot["icons"][theme]) == 5 for theme in ("light", "dark"))


def test_sent_goal_reuses_workflow_and_explicit_model_confirmation(app, monkeypatch):
    view = controller(app)
    requests = []
    monkeypatch.setattr(app, "_submit", lambda *a: requests.append(a))
    view.dispatch("send", {"text": "重新设计软件界面"}, view_stamp(app))
    assert app.session.task_text == "重新设计软件界面"
    assert requests and app.busy
    assert app.session.confirmed_requirements_version is None


def test_changed_model_configuration_cannot_start_generation(app, monkeypatch):
    view = controller(app)
    app.api_model_var.set("unconfirmed-fixture")
    requests = []
    monkeypatch.setattr(app, "_submit", lambda *a: requests.append(a))
    view.dispatch("send", {"text": "重新设计软件界面"}, view_stamp(app))
    assert not requests
    assert app.notebook.index(app.notebook.select()) == app._settings_page_index


def test_stale_browser_action_cannot_mutate_new_conversation(app):
    view = controller(app)
    old = view_stamp(app)
    app.new_session()
    with pytest.raises(ValueError, match="内容已变化"):
        view.dispatch("send", {"text": "迟到内容"}, old)
    assert not app.session.task_text


def test_answers_collected_individually_then_combined(app, monkeypatch):
    app.widgets["task_text"].insert("1.0", "重做UI")
    app._sync_input()
    app.session.pending_questions = questions()
    app.refresh()
    requests = []
    monkeypatch.setattr(app, "start_analysis", lambda: requests.append(True))
    view = controller(app)
    for i in range(1, 4):
        view.dispatch("answer", {"id": f"q{i}", "text": f"回答{i}"}, view_stamp(app))
    assert requests == [True]
    assert [r["answer_text"] for r in app.session.question_history] == ["回答1", "回答2", "回答3"]


def test_skip_remains_exclusion_and_reanswer_remains_explicit(app, monkeypatch):
    app.widgets["task_text"].insert("1.0", "重做UI")
    app._sync_input()
    app.session.pending_questions = questions()
    app.refresh()
    monkeypatch.setattr(app, "start_analysis", lambda: None)
    view = controller(app)
    view.dispatch("skip", {"id": "q1"}, view_stamp(app))
    assert app.session.question_history[0]["disposition"] == "skipped"
    view.dispatch("reanswer", {"id": "q1"}, view_stamp(app))
    assert app._answer_target_id == "q1"


@pytest.mark.parametrize("kind", ["summary", "result"])
def test_review_projection_stays_native_state_derived(app, kind):
    install_session(app, confirmed_plan_session())
    view = controller(app)
    view.dispatch("panel", {"kind": kind}, view_stamp(app))
    snapshot = view.snapshot()
    assert snapshot["panel"] == kind
    assert not any(c["kind"] == "plan" for c in snapshot["cards"])
    view.dispatch("button", {"key": "back_stage"}, view_stamp(app))
    snapshot = view.snapshot()
    assert any(c["kind"] == "plan" and "text" in c for c in snapshot["cards"])
    assert snapshot["requirement_rows"]
    # Confirmed requirements are revisited through the current flow, not a panel.
    while app.session.workspace_navigation()["stage"] != "requirements":
        view.dispatch("button", {"key": "back_stage"}, view_stamp(app))
    snapshot = view.snapshot()
    row = snapshot["requirement_rows"][0]
    view.dispatch("requirement_row", {"id": row["id"]}, view_stamp(app))
    assert app.widgets["conversation_requirements_tree"].selection() == (row["id"],)


def test_api_workers_only_exchange_data_and_shutdown_unblocks_waiters():
    api = DesktopApi()
    result = []
    worker = threading.Thread(target=lambda: result.append(api.dispatch("send", {"text": "test"}, "stamp")))
    worker.start()
    request = api._queue.get(timeout=2)
    assert request["action"] == "send" and not result
    request["result"] = {"ok": True}
    request["done"].set()
    worker.join(2)
    assert result == [{"ok": True}]
    api._closing.set()
    assert not api.dispatch("send", {}, "stamp")["ok"]
    assert api.snapshot(0) is None


def test_browser_cannot_call_arbitrary_native_methods(app):
    view = controller(app)
    with pytest.raises(ValueError, match="未知操作"):
        view.dispatch("__getattribute__", {}, view_stamp(app))
    with pytest.raises(ValueError, match="格式"):
        view.dispatch("send", "wrong", view_stamp(app))


def settings_data(view, **changes):
    snapshot = view.settings_snapshot()
    return dict(revision=snapshot["revision"], connection=snapshot["connection"],
                values=snapshot["values"], key_action="keep", **changes)


def test_settings_stays_in_web_window_and_exports_all_categories_without_key(app):
    view = controller(app)
    view.install_native_bridge()
    view.dispatch("settings", {}, view_stamp(app))
    app.root.update_idletasks()
    snapshot = view.snapshot()
    assert snapshot["page"] == "settings" and app.root.state() == "withdrawn"
    assert set(snapshot["settings"]["fields"]) == set(FIELDS)
    assert len({field["category"] for field in snapshot["settings"]["fields"].values()}) == 5
    assert snapshot["settings"]["has_key"] and snapshot["settings"]["confirmed"]
    assert app.api_key_var.get() not in json.dumps(snapshot)
    view.dispatch("settings_back", {}, view_stamp(app))
    assert view.snapshot()["page"] == "workspace" and app.root.state() == "withdrawn"


def test_web_settings_connection_test_never_confirms_and_confirm_preserves_other_drafts(app, monkeypatch):
    view = controller(app)
    view.install_native_bridge()
    monkeypatch.setattr(app, "_submit", lambda operation, success, failure: success(ApiResult("OK", 8, None, "test", "offline")))
    draft = settings_data(view)
    draft["connection"]["model"] = "changed-model"
    draft["values"]["font_size"] = "15"
    view.dispatch("settings_test", draft, view_stamp(app))
    assert not app._model_settings_confirmed() and "连接成功" in app.status_var.get()
    draft["revision"] = view.settings_snapshot()["revision"]
    view.dispatch("settings_confirm", draft, view_stamp(app))
    loaded = load_settings(app._preferences_path)
    assert loaded.model_confirmed and loaded.connection["model"] == "changed-model"
    assert loaded.preferences["font_size"] == 12


def test_web_settings_save_encrypts_replacement_key_and_restores_confirmation(app):
    view = controller(app)
    draft = settings_data(view, key="disposable-new-key")
    draft["key_action"] = "replace"
    view.dispatch("settings_confirm", draft, view_stamp(app))
    draft = settings_data(view)
    draft["values"].update(font_size="13", extra_skill_roots="C:/fixture/skills\nD:/extra", export_directory="C:/fixture/export")
    view.dispatch("settings_save", draft, view_stamp(app))
    loaded = load_settings(app._preferences_path)
    assert loaded.api_key == "disposable-new-key" and loaded.model_confirmed
    assert loaded.preferences["extra_skill_roots"] == "C:/fixture/skills\nD:/extra"
    assert loaded.preferences["font_size"] == 13
    assert "disposable-new-key" not in app._preferences_path.read_text()
    assert "disposable-new-key" not in json.dumps(view.settings_snapshot())


def test_web_settings_clear_key_and_reject_stale_or_invalid_settings_without_mutation(app):
    view = controller(app)
    draft = settings_data(view)
    app.preference_vars["reasoning_effort"].set("max")
    with pytest.raises(ValueError, match="设置已"):
        view.dispatch("settings_save", draft, view_stamp(app))
    draft = settings_data(view)
    draft["values"]["generation_timeout"] = "nan"
    with pytest.raises(ValueError, match="值无效"):
        view.dispatch("settings_save", draft, view_stamp(app))
    assert app.api_key_var.get() == "offline-key"
    draft = settings_data(view)
    draft["key_action"] = "clear"
    view.dispatch("settings_save", draft, view_stamp(app))
    assert not load_settings(app._preferences_path).api_key
    assert not load_settings(app._preferences_path).model_confirmed


def test_web_settings_get_models_and_directory_browse_use_existing_handlers(app, monkeypatch):
    view = controller(app)
    monkeypatch.setattr(app, "_submit", lambda operation, success, failure: success(ModelListResult(["model-one", "model-two"], 7)))
    view.dispatch("settings_models", settings_data(view), view_stamp(app))
    assert view.settings_snapshot()["available_models"] == ["model-one", "model-two"]
    monkeypatch.setattr("tkinter.filedialog.askdirectory", lambda **kwargs: "C:/fixture/export")
    result = view.dispatch("settings_browse", dict(revision=view.settings_snapshot()["revision"], key="export_directory"), view_stamp(app))
    assert result["path"] == "C:/fixture/export"
    assert app.preference_vars["export_directory"].get() == ""


def test_web_feedback_is_redacted_and_records_exception_cause(app, caplog):
    import logging
    view = controller(app)
    view.install_native_bridge()
    app.runtime_log.register_secret("fixture-sensitive-value")
    with caplog.at_level(logging.ERROR):
        try:
            raise RuntimeError("nested fixture cause")
        except RuntimeError:
            app._show_error("失败", "fixture-sensitive-value")
    assert view.notifications[-1]["text"] == "失败：[REDACTED]"
    assert "nested fixture cause" in caplog.text
    assert "fixture-sensitive-value" not in caplog.text


def test_fetched_custom_model_can_be_selected_but_unknown_id_is_rejected(app):
    view = controller(app)
    app.widgets["api_model_combo"].configure(values=["gateway-ui-model"])
    assert any(m["id"] == "gateway-ui-model" for m in view.snapshot()["models"])
    result = view.dispatch("model", {"id": "gateway-ui-model"}, view_stamp(app))
    assert result["model"] == "gateway-ui-model" and app._model_settings_confirmed()
    with pytest.raises(ValueError, match="模型不存在"):
        view.dispatch("model", {"id": "not-in-directory"}, view_stamp(app))
    assert app.api_model_var.get() == "gateway-ui-model"


def test_debug_can_open_during_busy_generation_without_submitting_model_draft(app, monkeypatch):
    view = controller(app)
    app.busy = True
    previous_model = app.api_model_var.get()
    opened = []
    monkeypatch.setattr(app, "set_debug_console_enabled", lambda: opened.append(app.debug_console_enabled_var.get()))
    view.dispatch("settings_debug", dict(revision=view.settings_snapshot()["revision"], enabled=True), view_stamp(app))
    assert opened == [True] and app.api_model_var.get() == previous_model


def test_first_snapshot_failure_still_reports_retry_and_can_recover():
    api = DesktopApi()
    api._publish_sync_error()
    snapshot = api.snapshot(0)
    assert snapshot["version"] == 1 and "重试" in snapshot["state"]["sync_error"]
    with api._lock:
        api._state = {"stamp": "recovered", "cards": []}
        api._version += 1
    assert api.snapshot(1)["state"]["stamp"] == "recovered"
