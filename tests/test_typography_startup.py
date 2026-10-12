"""Opening with old font settings requires no generated font or worker."""
import json
from pathlib import Path
import threading
import tkinter as tk
import tkinter.font as tkfont

import pytest

from promptsmith.preferences import RETIRED_FONT_FIELDS, defaults, save_preferences
from promptsmith.ui import PromptSmithApp


@pytest.mark.parametrize("old_cache", [False, True])
def test_startup_ignores_old_fonts_cache_and_needs_no_font_worker(tk_root, tmp_path, monkeypatch, old_cache):
    path = tmp_path / "settings.json"
    save_preferences(path, defaults(), {})
    document = json.loads(path.read_text(encoding="utf-8"))
    document["preferences"].update(chinese_font="uninstalled-font", latin_font="missing-font", split_fonts=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    cache = tmp_path / "font_cache"
    if old_cache:
        cache.mkdir()
        (cache / "legacy.ttf").write_bytes(b"invalid old font -- never read")
    original_read = Path.read_bytes
    def no_cached_reads(target):
        assert cache not in target.parents, "Retired font cache was accessed"
        return original_read(target)
    monkeypatch.setattr(Path, "read_bytes", no_cached_reads)
    monkeypatch.setattr("promptsmith.ui.warm_local_skill_index", lambda _roots: None)
    monkeypatch.setattr(tkfont, "families", lambda *_: pytest.fail("Startup enumerated installed font families"))
    window = tk.Toplevel(tk_root)
    application = PromptSmithApp(window, diagnostics_root=tmp_path, evidence_root=tmp_path / "runs")
    try:
        window.update()
        assert window.winfo_ismapped()
        assert application.typography.family == tkfont.nametofont("TkDefaultFont", window).actual("family")
        assert not any(key in application.preference_vars for key in RETIRED_FONT_FIELDS)
        assert not any(thread.name == "ui-font" for thread in threading.enumerate())
        composer = application.widgets["conversation_composer"]
        composer.entry.insert("1.0", "中文 English 0123 草稿")
        window.update()
        assert str(composer.send_button.cget("state")) == "normal"
        assert application.save_settings()
        assert composer.entry.get("1.0", "end-1c") == "中文 English 0123 草稿"
        if old_cache:
            assert list(cache.iterdir()) == [cache / "legacy.ttf"]
        else:
            assert not cache.exists()
        assert not list((tmp_path / "logs").glob("*.log"))
        logs = "\n".join(entry.text for entry in application.runtime_log._archive)
        assert "Native UI typography applied" in logs
        assert "Ignored retired custom font preferences" in logs
    finally:
        application.shutdown(wait=True)
        window.destroy()
