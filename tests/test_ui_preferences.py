import tkinter as tk
from types import SimpleNamespace

import pytest

from promptsmith.ui import PromptSmithApp
from test_final_delivery import confirmed_plan_session


@pytest.fixture
def app(tk_root, tmp_path):
    window = tk.Toplevel(tk_root)
    application = PromptSmithApp(window, evidence_root=tmp_path / "runs")
    application.api_base_var.set("https://example.invalid/v1")
    application.api_model_var.set("offline-model")
    application.api_key_var.set("fixture-secret")
    yield application
    application.shutdown(wait=True)
    window.destroy()


def test_model_edit_invalidates_confirmation_but_not_model_directory(app):
    app.confirm_model_settings()
    snapshot = app._api_config()
    directory_version = app.model_directory_version
    app.preference_vars["max_tokens"].set("16384")
    assert not app._model_settings_confirmed()
    assert app.model_directory_version == directory_version
    assert snapshot.max_tokens is None
    app.confirm_model_settings()
    assert app._api_config().max_tokens == 16384
    app.preference_vars["generation_timeout"].set("300")
    app.confirm_model_settings()
    assert app._api_config().timeout_seconds == 300
    assert snapshot.timeout_seconds == 120


def test_save_does_not_confirm_and_model_confirm_preserves_unrelated_draft(app):
    app.preference_vars["font_size"].set("16")
    app.confirm_model_settings()
    assert app.preferences["font_size"] == 12
    app.preference_vars["temperature"].set("0.7")
    app.save_settings()
    assert app.preferences["font_size"] == 16
    assert not app._model_settings_confirmed()
    app.confirm_model_settings()
    assert app._api_config().temperature == .7
    assert "fixture-secret" not in app._preferences_path.read_text(encoding="utf-8")


def test_settings_reopen_and_new_session_defaults(tk_root, tmp_path, monkeypatch):
    window = tk.Toplevel(tk_root)
    app = PromptSmithApp(window, evidence_root=tmp_path / "runs")
    app.preference_vars["default_thinking"].set("deep")
    app.preference_vars["default_tone"].set("polite")
    app.save_settings()
    app.shutdown(wait=True)
    window.destroy()
    window = tk.Toplevel(tk_root)
    app = PromptSmithApp(window, evidence_root=tmp_path / "runs")
    try:
        assert app.session.control["thinking_level"] == "deep"
        assert app.session.control["default_tone"] == "polite"
        assert app.api_key_var.get() == ""
        assert not app._model_settings_confirmed()
        monkeypatch.setattr("promptsmith.ui.messagebox.askyesno", lambda *args, **kw: True)
        app.new_session()
        session = confirmed_plan_session()
        session.control["default_tone"] = "polite"
        from promptsmith.finalization import build_final_draft
        assert build_final_draft(session)["tone"] == "polite"
    finally:
        app.shutdown(wait=True)
        window.destroy()


def test_invalid_save_stays_actionable_and_does_not_apply(app, monkeypatch):
    before = dict(app.preferences)
    notices = []
    monkeypatch.setattr(app, "_show_error", lambda *args, **kw: notices.append(args))
    app.preference_vars["generation_timeout"].set("nan")
    assert not app.save_settings()
    assert app.preferences == before
    assert "重试" in app.settings_status_var.get()
    assert notices
    assert any("Cannot save settings" in row.text and "Traceback" in row.text for row in app.runtime_log.entries_after())


def test_diagnostics_display_limits_preserve_complete_manual_archive(app, tmp_path):
    app.preference_vars["debug_history"].set("100")
    app.preference_vars["debug_lines"].set("500")
    app.preference_vars["debug_level"].set("ERROR 及以上")
    app.preference_vars["debug_autoscroll"].set(False)
    app.save_settings()
    for i in range(200):
        app.runtime_log.record("fixture", 10, f"all-level-{i}")
    app.debug_console_enabled_var.set(True)
    app.set_debug_console_enabled()
    assert len(app.runtime_log.entries_after()) == 100
    assert app.debug_console.level_var.get() == "ERROR 及以上"
    assert not app.debug_console.autoscroll_var.get()
    assert app.debug_console.line_limit == 500
    assert not list(tmp_path.rglob("*.log"))
    saved = app.runtime_log.save().read_text(encoding="utf-8")
    assert "all-level-0" in saved and "all-level-199" in saved
    app.preference_vars["debug_history"].set("500")
    app.save_settings()
    assert any("all-level-0" in row.text for row in app.runtime_log.entries_after())


def test_search_settings_are_captured_before_worker(app, monkeypatch, tmp_path):
    app.session = confirmed_plan_session()
    app.confirm_model_settings()
    app.preference_vars["local_candidates"].set("4")
    app.preference_vars["shortlist_limit"].set("3")
    app.preference_vars["review_limit"].set("2")
    app.preference_vars["search_model_timeout"].set("89")
    app.widgets["setting_extra_skill_roots"].insert("1.0", str(tmp_path / "skills"))
    assert app.save_settings()
    configs = []
    monkeypatch.setattr(app, "_client", lambda config: (configs.append(config) or object()))
    captured = []
    monkeypatch.setattr(app, "_submit", lambda operation, success, failure: captured.append(operation))
    app.find_skills()
    request = app._skill_search_request
    assert request["preferences"]["review_limit"] == 2
    assert tmp_path / "skills" in request["skill_roots"]
    assert configs[-1].timeout_seconds == 89
    app.preference_vars["local_candidates"].set("20")
    app.save_settings()
    assert request["preferences"]["local_candidates"] == 4
    observed = {}
    from promptsmith.local_skill_search import LocalSkillSearchResult
    def discovery(works, **kw):
        observed.update(kw)
        return LocalSkillSearchResult(status="no_match", candidates=[], catalog_hash="", scanned_count=0, errors=[], batch_id="fixture")
    monkeypatch.setattr("promptsmith.ui.discover_local_skill_candidates", discovery)
    monkeypatch.setattr("promptsmith.ui.select_skill_candidates_with_ai", lambda client, rows, **kw: (observed.update(kw) or []))
    request["catalog"] = None
    captured[-1]()
    assert observed["max_candidates"] == 4
    assert observed["shortlist_limit"] == 3
    assert observed["review_limit"] == 2


def test_removed_m5_setting_and_connection_timeout_reaches_operation(app, monkeypatch):
    assert "m5_max_chars" not in app.preference_vars
    app.preference_vars["connection_timeout"].set("31")
    app.confirm_model_settings()
    app.save_settings()
    assert app._model_directory_config().timeout_seconds == 31
    captured = []
    monkeypatch.setattr(app, "_client", lambda config: (captured.append(config) or SimpleNamespace(test_connection=lambda: SimpleNamespace(model="fixture", latency_ms=1, probe_truncated=False))))
    monkeypatch.setattr(app, "_submit", lambda operation, success, failure: success(operation()))
    app.test_connection()
    assert captured[-1].timeout_seconds == 31
    assert not hasattr(app, "start_m5_generation")


def test_restore_only_selected_category_preserves_connection(app):
    app.preference_vars["max_tokens"].set("20000")
    app.preference_vars["font_size"].set("16")
    tabs = app.widgets["settings_categories"]
    tabs.select(2)
    app.restore_settings_category()
    assert app.preference_vars["font_size"].get() == "12"
    assert app.preference_vars["max_tokens"].get() == "20000"
    assert app.api_key_var.get() == "fixture-secret"


def test_directory_preferences_reach_save_and_export_dialogs(app, tmp_path, monkeypatch):
    app.preference_vars["session_directory"].set(str(tmp_path / "sessions"))
    app.preference_vars["export_directory"].set(str(tmp_path / "exports"))
    assert app.save_settings()
    observed = []
    monkeypatch.setattr("promptsmith.ui.filedialog.asksaveasfilename", lambda **kw: (observed.append(kw) or ""))
    app.save()
    app._export_delivery("draft")
    assert str(observed[0]["initialdir"]) == str(tmp_path / "sessions")
    assert str(observed[1]["initialdir"]) == str(tmp_path / "exports")


def test_confirmed_model_settings_are_ready_after_restart(app, tk_root):
    app.preference_vars["max_tokens"].set("20000")
    app.confirm_model_settings()
    window = tk.Toplevel(tk_root)
    reopened = PromptSmithApp(window, evidence_root=app.evidence_root)
    try:
        assert reopened.api_model_var.get() == "offline-model"
        assert reopened.preference_vars["max_tokens"].get() == "20000"
        assert reopened.api_key_var.get() == "fixture-secret"
        assert reopened._model_settings_confirmed()
        assert reopened._api_config().max_tokens == 20000
        assert str(reopened.widgets["confirm_model_settings_button"].cget("state")) == "disabled"
    finally:
        reopened.shutdown(wait=True)
        window.destroy()


def test_saved_width_changes_next_start_and_draft_is_not_applied(app, tk_root, monkeypatch):
    original = app.root.geometry()
    app.preference_vars["window_width"].set("1232")
    assert app.preferences["window_width"] == 1440
    assert app.save_settings()
    assert app.root.geometry() == original
    window = tk.Toplevel(tk_root)
    monkeypatch.setattr(window, "winfo_screenwidth", lambda: 1920)
    monkeypatch.setattr(window, "winfo_screenheight", lambda: 1080)
    reopened = PromptSmithApp(window, evidence_root=app.evidence_root)
    try:
        window.update_idletasks()
        assert window.geometry().split("+")[0] == "1232x693"
    finally:
        reopened.shutdown(wait=True)
        window.destroy()


def test_confirm_model_does_not_hide_unsaved_other_categories(app):
    app.widgets["setting_extra_skill_roots"].insert("1.0", "D:/skills")
    app.root.update()
    app.confirm_model_settings()
    assert app.preferences["extra_skill_roots"] == ""
    assert "单独保存" in app.settings_status_var.get()
    assert "D:/skills" in app.widgets["setting_extra_skill_roots"].get("1.0", "end-1c")
