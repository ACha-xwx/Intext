"""Save at the application boundary; filesystem/dialog faults are external."""
from pathlib import Path

import pytest

from promptsmith.storage import load_session
from tests.test_conversation_workspace import app


@pytest.mark.parametrize("failure", ["mkdir", "chooser", "write"])
def test_save_failure_keeps_previous_file_and_session_and_allows_retry(app, tmp_path, monkeypatch, caplog, failure):
    old = tmp_path / "old.json"
    old.write_text("original content", encoding="utf-8")
    app.session_path = old
    app.preferences["session_directory"] = str(tmp_path / "blocked")
    task = app.session.task_id
    errors = []
    monkeypatch.setattr("promptsmith.ui.messagebox.showerror", lambda *a, **k: errors.append(a))
    original_mkdir = Path.mkdir
    def mkdir(path, *args, **kwargs):
        if path == tmp_path / "blocked" and failure == "mkdir":
            raise PermissionError("synthetic directory denied")
        return original_mkdir(path, *args, **kwargs)
    monkeypatch.setattr(Path, "mkdir", mkdir)
    def choose(**options):
        if failure == "chooser":
            raise OSError("synthetic chooser failure")
        return str(tmp_path)  # A directory cannot be used as a JSON file.
    monkeypatch.setattr("promptsmith.ui.filedialog.asksaveasfilename", choose)
    app.save(save_as=True)
    assert errors and "保存失败" in errors[0][0]
    assert "设置" in errors[0][1] and "目录" in errors[0][1]
    assert app.session_path == old and old.read_text(encoding="utf-8") == "original content"
    assert app.session.task_id == task
    assert "Traceback" in caplog.text
    app.preferences["session_directory"] = str(tmp_path / "allowed")
    saved = tmp_path / "retry.json"
    monkeypatch.setattr("promptsmith.ui.filedialog.asksaveasfilename", lambda **kw: str(saved))
    app.save(save_as=True)
    assert app.session_path == saved and load_session(saved).task_id == task


def test_atomic_replace_failure_preserves_saved_file_and_session(app, tmp_path, monkeypatch, caplog):
    import os
    saved = tmp_path / "existing.json"
    saved.write_text("original", encoding="utf-8")
    app.session_path = saved
    before = app.session.to_dict()
    errors = []
    monkeypatch.setattr("promptsmith.ui.messagebox.showerror", lambda *a, **k: errors.append(a))
    original_replace = os.replace
    def replace(source, target):
        if Path(target) == saved:
            raise PermissionError("synthetic replace denied")
        return original_replace(source, target)
    monkeypatch.setattr(os, "replace", replace)
    app.save()
    assert errors and "replace denied" in caplog.text
    assert saved.read_text(encoding="utf-8") == "original"
    assert app.session_path == saved and app.session.to_dict() == before


def test_save_dialog_cancel_preserves_file_session_and_draft(app, tmp_path, monkeypatch):
    saved = tmp_path / "existing.json"
    saved.write_text("original", encoding="utf-8")
    app.session_path = saved
    app.preferences["session_directory"] = str(tmp_path)
    app.widgets["task_text"].insert("1.0", "尚未提交的草稿")
    before = app.session.to_dict()
    monkeypatch.setattr("promptsmith.ui.filedialog.asksaveasfilename", lambda **kw: "")
    app.save(save_as=True)
    assert saved.read_text(encoding="utf-8") == "original"
    assert app.session_path == saved and app.session.to_dict() == before
    assert app.widgets["task_text"].get("1.0", "end-1c") == "尚未提交的草稿"
