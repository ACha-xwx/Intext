"""Retired prompt execution must not reappear when loading old data."""
from copy import deepcopy
import json
import logging
import tkinter as tk

import pytest

from promptsmith.finalization import build_final_draft, stage_final_draft, confirm_final
from promptsmith.preferences import defaults, FIELDS, load_settings, save_preferences, update_debug_preference
from promptsmith.session import SessionState
from promptsmith.storage import load_session, save_session
from promptsmith.ui import PromptSmithApp
from tests.test_final_delivery import confirmed_plan_session


@pytest.mark.parametrize("version", ["promptsmith.session.v0.1", "promptsmith.session.v0.2"])
def test_old_execution_data_ignored_and_final_survives_roundtrip(tmp_path, version, caplog):
    session = confirmed_plan_session()
    draft = build_final_draft(session)
    stage_final_draft(session, draft, expected_basis=draft["basis"])
    confirm_final(session)
    data = session.to_dict()
    data["schema_version"] = version
    data["trial_runs"] = [{"output": "legacy-output-not-current-task", "status": "completed"}]
    data["pending_requests"] = {"old-trial": {"purpose": "trial"}, "old-m1": {"purpose": "m1"}}
    path = tmp_path / "old-session.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    original = path.read_bytes()
    with caplog.at_level(logging.INFO):
        restored = load_session(path)
    assert restored.final_result["status"] == "confirmed"
    assert restored.final_result["canonical_body"] == session.final_result["canonical_body"]
    assert restored.pending_requests == {}
    assert not hasattr(restored, "trial_runs")
    assert all(row.get("purpose") != "trial" for row in restored.errors)
    assert any(row.get("purpose") == "m1" for row in restored.errors)
    assert "Discarded retired" in caplog.text and "Ignored retired" in caplog.text
    assert "legacy-output-not-current-task" not in caplog.text
    assert path.read_bytes() == original
    saved = save_session(restored, tmp_path / "new-session.json")
    assert "trial_runs" not in json.loads(saved.read_text(encoding="utf-8"))


def test_old_token_preference_removed_without_losing_other_preferences(tmp_path):
    path = tmp_path / "settings.json"
    old = {**defaults(), "trial_tokens": "invalid-retired-number", "font_size": 15}
    path.write_text(json.dumps({"preferences": old, "connection": {}}), encoding="utf-8")
    loaded = load_settings(path)
    assert "trial_tokens" not in loaded.preferences and "trial_tokens" not in FIELDS
    assert loaded.preferences["font_size"] == 15
    update_debug_preference(path, True)
    assert "trial_tokens" not in json.loads(path.read_text(encoding="utf-8"))["preferences"]
    assert load_settings(path).preferences["font_size"] == 15
    save_preferences(path, loaded.preferences, loaded.connection)
    assert "trial_tokens" not in json.loads(path.read_text(encoding="utf-8"))["preferences"]


def test_result_and_conversation_keep_delivery_without_execution(tk_root, tmp_path, monkeypatch):
    window = tk.Toplevel(tk_root)
    app = PromptSmithApp(window, session=confirmed_plan_session(), evidence_root=tmp_path / "runs")
    app.widgets["task_text"].insert("1.0", app.session.task_text)
    app.category_var.set(next(label for label, value in app.category_by_label.items()
                             if value == app.session.selected_category))
    requests = []
    monkeypatch.setattr(app, "_client", lambda *_: requests.append("unexpected-request"))
    try:
        assert not any(name.startswith("trial_") for name in app.widgets)
        assert not hasattr(app, "start_trial_run")
        app.skip_skills()
        app.generate_no_skill_final()
        before = deepcopy(app.session.final_result)
        app.show_workspace(3)
        app.toggle_result_options()
        app.refresh()
        assert "试运行" not in app.widgets["result_optional_button"].cget("text")
        assert app.session.final_result == before
        app.show_workspace(0)
        assert "试运行" not in app._conversation_buttons["result_details"].cget("text")
        body = app.widgets["final_task_prompt_text"].get("1.0", "end-1c")
        app.copy_current_prompt()
        assert window.clipboard_get() == body
        target = tmp_path / "delivered.md"
        monkeypatch.setattr("promptsmith.ui.filedialog.asksaveasfilename", lambda **_: str(target))
        app.export_current_result()
        assert body in target.read_text(encoding="utf-8")
        assert not requests
    finally:
        app.shutdown(wait=True)
        window.destroy()
