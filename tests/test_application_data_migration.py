"""Default data location and legacy migration using real settings/history files."""
import sys

import pytest

from promptsmith.paths import application_data_dir


def test_new_default_uses_intext_without_creating_files(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert application_data_dir() == tmp_path / "Intext"
    assert not (tmp_path / "Intext").exists()


@pytest.mark.parametrize("target_exists", [False, True])
def test_legacy_directory_migrates_once_even_if_empty_target_exists(tmp_path, monkeypatch, caplog, target_exists):
    from promptsmith.paths import migrate_legacy_application_data
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    legacy, target = tmp_path / "PromptSmith", tmp_path / "Intext"
    legacy.mkdir()
    (legacy / "retained.txt").write_text("original", encoding="utf-8")
    if target_exists:
        target.mkdir()
    with caplog.at_level("INFO"):
        migrate_legacy_application_data()
        migrate_legacy_application_data()
    assert not legacy.exists()
    assert (target / "retained.txt").read_text(encoding="utf-8") == "original"
    assert caplog.text.count("Application data directory migrated;") == 1
    assert not (target / "logs").exists()


def test_existing_intext_data_is_not_overwritten_or_merged(tmp_path, monkeypatch, caplog):
    from promptsmith.paths import migrate_legacy_application_data
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    legacy, target = tmp_path / "PromptSmith", tmp_path / "Intext"
    for root, value in ((legacy, "legacy"), (target, "current")):
        root.mkdir()
        (root / "settings.json").write_text(value, encoding="utf-8")
    migrate_legacy_application_data()
    assert (legacy / "settings.json").read_text(encoding="utf-8") == "legacy"
    assert (target / "settings.json").read_text(encoding="utf-8") == "current"
    assert "legacy directory retained" in caplog.text


def test_failed_directory_rename_keeps_legacy_data_and_reports_cause(tmp_path, monkeypatch, caplog):
    from pathlib import Path
    from promptsmith.paths import migrate_legacy_application_data
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    legacy = tmp_path / "PromptSmith"
    legacy.mkdir()
    (legacy / "settings.json").write_text("original", encoding="utf-8")
    original = Path.rename
    def fail_legacy_rename(source, destination):
        if source == legacy:
            raise PermissionError("simulated legacy directory locked")
        return original(source, destination)
    monkeypatch.setattr(Path, "rename", fail_legacy_rename)
    with pytest.raises(OSError, match="原数据已保留") as caught:
        migrate_legacy_application_data()
    assert isinstance(caught.value.__cause__, PermissionError)
    assert "simulated legacy directory locked" in caplog.text
    assert (legacy / "settings.json").read_text(encoding="utf-8") == "original"
    assert not (tmp_path / "Intext").exists()


@pytest.mark.parametrize("isolation", ["diagnostics_root", "runtime_log"])
def test_isolated_app_does_not_migrate_default_data(tmp_path, monkeypatch, tk_root, isolation):
    import tkinter as tk
    from promptsmith.runtime_log import RuntimeLog
    from promptsmith.ui import PromptSmithApp
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "default"))
    legacy = tmp_path / "default/PromptSmith"
    legacy.mkdir(parents=True)
    (legacy / "retained.txt").write_text("production data", encoding="utf-8")
    isolated = tmp_path / "isolated"
    runtime_log = RuntimeLog(isolated / "logs").start() if isolation == "runtime_log" else None
    kwargs = {isolation: runtime_log if runtime_log else isolated}
    window = tk.Toplevel(tk_root)
    window.withdraw()
    app = None
    try:
        app = PromptSmithApp(window, **kwargs)
        assert app._preferences_path == isolated / "settings.json"
        assert (legacy / "retained.txt").read_text(encoding="utf-8") == "production data"
        assert not (tmp_path / "default/Intext").exists()
    finally:
        if app is not None:
            app.shutdown(wait=True)
        if runtime_log is not None:
            runtime_log.close()
        window.destroy()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI")
def test_default_startup_migrates_encrypted_settings_and_resumable_history(tmp_path, monkeypatch, tk_root):
    import tkinter as tk
    from promptsmith.preferences import defaults, save_preferences, load_settings
    from promptsmith.session import SessionState
    from promptsmith.session_history import SessionHistory
    from promptsmith.ui import PromptSmithApp
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    old = tmp_path / "PromptSmith"
    connection = dict(provider="YUN", model_provider="OpenAI", protocol="OpenAI Responses",
                      base_url="https://gateway.example.invalid/v1", model="gpt-6.1-sol")
    save_preferences(old / "settings.json", dict(defaults(), model_directory_autorefresh=False),
                     connection, api_key="disposable-migration-key", model_confirmed=True)
    old_settings = (old / "settings.json").read_bytes()
    session = SessionState.new()
    session.set_task("继续整理比赛技术文档")
    history = SessionHistory(old / "history")
    identity = history.save(session.to_dict())
    (old / "runs").mkdir()
    (old / "runs/evidence.json").write_text('{"retained":true}', encoding="utf-8")
    window = tk.Toplevel(tk_root)
    window.withdraw()
    app = PromptSmithApp(window)
    try:
        assert app._preferences_path == tmp_path / "Intext/settings.json"
        assert app.api_key_var.get() == "disposable-migration-key"
        assert (tmp_path / "Intext/settings.json").read_bytes() == old_settings
        assert load_settings(app._preferences_path).model_confirmed
        restored = SessionHistory()
        assert restored.list()[0]["id"] == identity
        assert restored.load(identity).task_text == "继续整理比赛技术文档"
        assert (tmp_path / "Intext/runs/evidence.json").read_text(encoding="utf-8") == '{"retained":true}'
        assert not old.exists()
    finally:
        app.shutdown(wait=True)
        window.destroy()
