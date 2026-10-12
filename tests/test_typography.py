"""Native defaults, size changes and compatibility; no remote model calls."""
import json
import tkinter.font as tkfont
from tkinter import ttk

import pytest

from promptsmith.debug_console import LEVEL_COLORS
from promptsmith.preferences import RETIRED_FONT_FIELDS, load_settings, update_debug_preference
from promptsmith.typography import Typography, ui_font
from tests.test_conversation_workspace import app


def test_all_widgets_picker_and_debug_use_platform_default(app):
    family = tkfont.nametofont("TkDefaultFont", app.root).actual("family")
    assert app.typography.family == family
    assert not any(key in app.preference_vars for key in RETIRED_FONT_FIELDS)
    assert "font_preview" not in app.widgets
    app.root.deiconify()
    app.debug_console_enabled_var.set(True)
    app.set_debug_console_enabled(persist=False)
    app.widgets["conversation_composer"].toggle_picker()
    app.root.update()
    style = ttk.Style(app.root)
    for name in ("TLabel", "TButton", "TEntry", "TCombobox", "TNotebook.Tab", "Treeview", "Treeview.Heading"):
        assert tkfont.Font(app.root, font=style.lookup(name, "font")).actual("family") == family

    def check_widgets(parent):
        for child in parent.winfo_children():
            if "font" in child.keys() and child.cget("font"):
                assert tkfont.Font(app.root, font=child.cget("font")).actual("family") == family, (str(child), child.winfo_class())
            check_widgets(child)
    check_widgets(app.root)
    for level, color in LEVEL_COLORS.items():
        assert app.debug_console.text.tag_cget(str(level), "foreground") == color
    assert not list(app.runtime_log.directory.glob("*.log"))


def test_size_change_keeps_draft_business_state_confirmation_and_colors(app):
    before = app.session.to_dict()
    version = app.connection_version
    composer = app.widgets["conversation_composer"]
    composer.entry.insert("1.0", "中文 English 0123 草稿")
    app.debug_console_enabled_var.set(True)
    app.set_debug_console_enabled(persist=False)
    composer.toggle_picker()
    picker = composer.picker
    app.preference_vars["font_size"].set("16")
    assert app.save_settings()
    assert not picker.window.winfo_exists()
    assert app.typography.font().actual("size") == 20
    assert tkfont.Font(app.root, font=app.debug_console.text.cget("font")).actual("size") == 16
    assert app._model_settings_confirmed()
    assert app.connection_version == version
    assert app.session.to_dict() == before
    assert composer.entry.get("1.0", "end-1c") == "中文 English 0123 草稿"
    loaded = load_settings(app._preferences_path)
    assert loaded.preferences["font_size"] == 16 and loaded.model_confirmed
    assert not any(key in loaded.preferences for key in RETIRED_FONT_FIELDS)
    for level, color in LEVEL_COLORS.items():
        assert app.debug_console.text.tag_cget(str(level), "foreground") == color


@pytest.mark.parametrize("save_mode", ["settings", "debug_toggle"])
def test_retired_preferences_are_ignored_and_removed_without_losing_credential(app, save_mode):
    path = app._preferences_path
    document = json.loads(path.read_text(encoding="utf-8"))
    credential, confirmation = document["credentials"], document["model_confirmation"]
    document["preferences"].update(chinese_font="removed-font", latin_font={"bad": "format"}, split_fonts=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    loaded = load_settings(path)
    assert loaded.model_confirmed and loaded.api_key == "offline-key"
    assert not loaded.warning
    assert not any(key in loaded.preferences for key in RETIRED_FONT_FIELDS)
    if save_mode == "settings":
        assert app.save_settings()
    else:
        update_debug_preference(path, True)
        updated = json.loads(path.read_text(encoding="utf-8"))
        assert updated["credentials"] == credential
        assert updated["model_confirmation"] == confirmation
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert not any(key in saved["preferences"] for key in RETIRED_FONT_FIELDS)
    assert "offline-key" not in path.read_text(encoding="utf-8")
    assert load_settings(path).model_confirmed


def test_native_named_fonts_are_unchanged_and_follow_platform_choice(tk_root):
    named = {name: tkfont.nametofont(name, tk_root).actual() for name in tkfont.names(tk_root)}
    default = tkfont.nametofont("TkDefaultFont", tk_root)
    platform_family = tkfont.nametofont("TkFixedFont", tk_root).actual("family")
    default.configure(family=platform_family)
    try:
        manager = Typography(tk_root, {"font_size": 12})
        assert manager.family == platform_family
        manager.apply({"font_size": 18})
        assert manager.font().actual("family") == platform_family
        assert manager.font().actual("size") == 22
        assert default.actual() == {**named["TkDefaultFont"], "family": platform_family}
        for name, actual in named.items():
            if name != "TkDefaultFont":
                assert tkfont.nametofont(name, tk_root).actual() == actual
    finally:
        default.configure(**named["TkDefaultFont"])
        tk_root.__dict__.pop("_promptsmith_typography", None)


def test_standalone_font_uses_tk_default_without_custom_manager(tk_root):
    default = tkfont.nametofont("TkDefaultFont", tk_root)
    family = tkfont.Font(tk_root, font=ui_font(tk_root, 11, "bold")).actual("family")
    assert family == default.actual("family")
