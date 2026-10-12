"""Popup rendering and interrupted transitions; offline native Tk checks."""
import tkinter.font as tkfont
from tkinter import ttk

from promptsmith.composer import THEMES
from tests.test_conversation_workspace import app
from tests.test_ui_refinement import show, pump


def test_choice_menu_keeps_native_size_and_theme_backing_during_animation(app):
    show(app)
    composer = app.widgets["conversation_composer"]
    composer.toggle_choices("category")
    menu = composer.choice_menu
    assert not menu.window.winfo_ismapped()
    pump(app)
    for progress in (0., .2, .6, 1.015, 1.):
        menu.animate(progress)
        app.root.update_idletasks()
        assert (menu.window.winfo_width(), menu.window.winfo_height()) == (menu.width, menu.height)
        assert menu.window.cget("bg") == menu.shell.cget("bg") == THEMES["light"].bg
        if app.root.tk.call("tk", "windowingsystem") == "win32":
            assert not menu.window.attributes("-transparentcolor")
    menu.close(immediate=True)


def test_closing_partly_open_menu_does_not_flash_fully_visible(app):
    show(app)
    composer = app.widgets["conversation_composer"]
    composer.toggle_choices("depth")
    menu = composer.choice_menu
    pump(app)
    menu.animate(.2)
    menu.close()
    assert float(menu.window.attributes("-alpha")) <= .21
    assert composer.choice_menu is None
    pump(app)
    assert not menu.window.winfo_exists()


def test_close_before_first_idle_cancels_pending_mapping(app):
    show(app)
    composer = app.widgets["conversation_composer"]
    composer.toggle_choices("category")
    menu = composer.choice_menu
    menu.close()
    app.root.update()
    assert not menu.window.winfo_exists()
    assert composer.choice_menu is None
    assert not app.callback_errors


def test_debug_fonts_are_local_and_resize_with_original_font_basis(app):
    show(app)
    app.debug_console_enabled_var.set(True)
    app.set_debug_console_enabled(persist=False)
    console = app.debug_console
    style = ttk.Style(app.root)
    for size in (12, 16):
        app.typography.apply({"font_size": size})
        assert tkfont.Font(app.root, font=console.text.cget("font")).actual("size") == size
        for name in ("TLabel", "TButton", "TCheckbutton", "Muted.TLabel"):
            assert tkfont.Font(app.root, font=style.lookup("DebugConsole."+name, "font")).actual("size") == size
        assert tkfont.Font(app.root, font=console.level_combo.cget("font")).actual("size") == size
        console._prepare_level_popup()
        popup = app.root.tk.call("ttk::combobox::PopdownWindow", str(console.level_combo))
        font = app.root.tk.call(f"{popup}.f.l", "cget", "-font")
        assert tkfont.Font(app.root, font=font).actual("size") == size
        assert app.typography.font().actual("size") == round(size*1.25)
    assert not app.runtime_log.path


def test_reasoning_font_keeps_original_size_across_stream_and_theme(app):
    from promptsmith.response_ui import ResponseTrace
    show(app)
    record = dict(id="font-scope", status="working", reasoning="中文 English 🧠\n", activities=[])
    trace = ResponseTrace(app.widgets["conversation_timeline"], record)
    trace.grid(row=0, column=0, sticky="ew")
    try:
        trace.writer.finish()
        for _ in range(20):
            if not trace.writer.pending:
                break
            pump(app,.1)
        assert not trace.writer.pending
        for size in (12, 16):
            app.typography.apply({"font_size": size})
            trace.apply_theme("dark")
            assert tkfont.Font(app.root, font=trace.thought.cget("font")).actual("size") == size
            assert trace.thought.get("1.0", "end-1c") == record["reasoning"]
            assert tkfont.Font(app.root, font=app.widgets["conversation_input"].cget("font")).actual("size") == round(size*1.25)
    finally:
        trace.destroy()
