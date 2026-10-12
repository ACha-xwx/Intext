"""Offline checks of the replicated widgets and settings confirmation boundary."""
import tkinter as tk

from promptsmith.model_catalog import EFFORTS, find_model, picker_models, search_models
from promptsmith.preferences import load_settings
from tests.test_conversation_workspace import app


def composer(app):
    return app.widgets["conversation_composer"]


def test_send_is_persistent_but_disabled_for_empty_whitespace_and_busy(app, monkeypatch):
    widget = composer(app)
    sent = []
    monkeypatch.setattr(widget.send_button, "command", lambda: sent.append(True))
    assert widget.send_button.winfo_manager() == "grid"
    assert str(widget.send_button.cget("state")) == "disabled"
    widget.entry.insert("1.0", " \n\t ")
    widget.send_button.invoke()
    assert not sent
    widget.entry.insert("end", "目标")
    assert str(widget.send_button.cget("state")) == "normal"
    widget.send_button.invoke()
    assert sent == [True]
    app.busy = True
    widget.refresh()
    widget.send_button.invoke()
    assert sent == [True]
    assert widget.entry.get("1.0", "end-1c").endswith("目标")
    app.busy = False
    widget.entry.delete("1.0", "end")
    assert str(widget.send_button.cget("state")) == "disabled"


def test_confirmed_custom_gateway_applies_and_persists_model_and_effort_directly(app):
    widget = composer(app)
    base, key, protocol = app.api_base_var.get(), app.api_key_var.get(), app.protocol_var.get()
    widget.choose_model(find_model("claude-opus-5-5"))
    assert (app.api_base_var.get(), app.api_key_var.get(), app.protocol_var.get()) == (base, key, protocol)
    assert app._model_settings_confirmed()
    widget.choose_effort("max")
    assert app._draft_api_config().reasoning_effort == "max"
    widget.toggle_picker()
    picker = widget.picker
    assert tuple(picker.effort_buttons) == EFFORTS
    assert app._model_settings_confirmed()
    assert load_settings(app._preferences_path).model_confirmed
    assert load_settings(app._preferences_path).preferences["reasoning_effort"] == "max"
    assert not hasattr(picker, "confirm_button")
    picker.close()
    app.preference_vars["reasoning_effort"].set("low")
    assert not app._model_settings_confirmed()


def test_official_provider_switch_clears_key_and_uses_latest_preset(app):
    widget = composer(app)
    app.api_base_var.set("https://api.deepseek.com")
    app.api_key_var.set("synthetic-key")
    widget.choose_model(find_model("gpt-6.1-sol"))
    assert app.api_model_var.get() == "gpt-6.1-sol"
    assert app.api_base_var.get() == "https://api.openai.com/v1"
    assert app.api_key_var.get() == ""
    assert app.preference_vars["reasoning_effort"].get() == "high"
    assert not app._model_settings_confirmed()


def test_picker_search_categories_selection_and_deepseek_chips(app):
    # Presets supply metadata only. Actual selectable IDs now come from a
    # previously fetched service directory, including gateway-hosted families.
    from promptsmith.model_catalog import MODELS
    app.widgets["api_model_combo"].configure(values=tuple(m.id for m in MODELS))
    widget = composer(app)
    widget.toggle_picker()
    picker = widget.picker
    picker.select_provider("DeepSeek")
    assert [m.id for m in picker.rows] == ["deepseek-flash", "deepseek-v4-pro"]
    assert all(not m.image for m in picker.rows)
    assert "DeepSeek" in widget.icons
    picker.query.set("  opus  ")
    assert [m.id for m in picker.rows] == ["claude-opus-5-5"]
    picker._select_row(0)
    assert widget.picker is picker  # selection keeps the thinking track open
    assert picker.row_widgets[0]._check.itemcget("check", "state") == "normal"
    picker.query.set("不存在的模型")
    assert picker.rows == ()
    picker.select_provider("OpenAI")
    assert not picker.query.get()
    assert {m.id for m in picker.rows} == {"gpt-6-astra", "gpt-6.1-sol", "gpt-6-sol", "gpt-6-luna", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5"}
    picker.close()
    widget.toggle_picker()
    assert widget.picker is not None
    widget.picker.close()


def test_picker_keyboard_effort_and_busy_close_preserve_draft(app):
    widget = composer(app)
    widget.entry.insert("1.0", "尚未发送的目标")
    widget.toggle_picker()
    picker = widget.picker
    picker._set_effort("low")
    picker._move_effort("low", 1)
    assert app.preference_vars["reasoning_effort"].get() == "medium"
    picker._move_effort("max", 1)
    assert app.preference_vars["reasoning_effort"].get() == "low"
    app.delivery_busy = True
    widget.refresh()
    assert widget.picker is None
    assert str(widget.model_button.cget("state")) == "disabled"
    assert widget.entry.get("1.0", "end-1c") == "尚未发送的目标"


def test_autogrow_and_placeholder_are_not_sent_text(app):
    widget = composer(app)
    assert not widget.entry.get("1.0", "end-1c")
    widget.entry.insert("1.0", "一\n二\n三\n四\n五\n六\n七\n八")
    app.root.update_idletasks()
    assert 2 <= int(widget.entry.cget("height")) <= 6
    assert not widget.placeholder.winfo_manager()
    widget.entry.delete("1.0", "end")
    app.root.update_idletasks()
    assert int(widget.entry.cget("height")) == 2
    assert widget.placeholder.winfo_manager() == "place"


def test_custom_directory_preserves_current_and_searches_all_providers():
    models = (*picker_models("private-model", ("private-model", "other-private"), service_provider="自定义服务", model_provider="OpenAI"),
              *picker_models("", ("deepseek-flash",), service_provider="DeepSeek"))
    assert [m.id for m in search_models(models, "OpenAI", "")] == ["private-model", "other-private"]
    assert len([m for m in models if m.id == "private-model"]) == 1
    assert {m.provider for m in search_models(models, "DeepSeek", "方案")} >= {"DeepSeek"}


def test_theme_saved_repaints_replica_without_changing_business_or_confirmation(app):
    widget = composer(app)
    before = app.session.to_dict()
    widget.entry.insert("1.0", "主题切换应保留这段草稿")
    for theme in ("dark", "light"):
        app.preference_vars["composer_theme"].set(theme)
        assert app.save_settings()
        app.root.update_idletasks()
        assert widget.theme_name == theme
        assert widget.entry.cget("bg") == widget.palette.bg
        assert widget.entry.cget("fg") == widget.palette.ink
        assert widget.entry.cget("insertbackground") == widget.palette.ink
        assert widget.placeholder.cget("fg") == widget.palette.placeholder
        assert widget.send_button.cget("bg") == widget.palette.bg
        assert widget.send_button.palette == widget.palette
        assert load_settings(app._preferences_path).preferences["composer_theme"] == theme
        assert app._model_settings_confirmed()
        assert widget.entry.get("1.0", "end-1c") == "主题切换应保留这段草稿"
        widget.toggle_picker()
        assert widget.picker.palette == widget.palette
        widget.picker.close()
    assert app.session.to_dict() == before


def test_undo_and_paste_update_send_state_and_all_icons_load(app):
    widget = composer(app)
    assert set(widget.icons) == {"OpenAI", "Anthropic", "xAI", "Google", "DeepSeek"}
    widget.entry.insert("1.0", "中文粘贴内容")
    app.root.update()
    assert str(widget.send_button.cget("state")) == "normal"
    widget.entry.edit_undo()
    app.root.update()
    assert not widget.entry.get("1.0", "end-1c")
    assert str(widget.send_button.cget("state")) == "disabled"


def test_repeated_same_model_keeps_chosen_effort_and_confirmation(app):
    widget = composer(app)
    widget.choose_model(find_model("deepseek-flash"))
    widget.choose_effort("max")
    app.confirm_model_settings()
    version = app.connection_version
    widget.choose_model(find_model("deepseek-flash"))
    assert app._model_settings_confirmed()
    assert app.preference_vars["reasoning_effort"].get() == "max"
    assert app.connection_version == version


def test_large_custom_model_list_scrolls_and_exposes_full_descriptions(app):
    widget = composer(app)
    app.widgets["api_model_combo"].configure(values=tuple(f"private-model-{n:03d}" for n in range(80)))
    app.root.deiconify()
    app.root.update()
    widget.toggle_picker()
    picker = widget.picker
    picker.select_provider("DeepSeek")
    app.root.update()
    assert picker.scroll.winfo_ismapped()
    # A drag reaches models outside the initial viewport; selection on the
    # confirmed gateway applies directly without a second confirmation button.
    scroll = picker.scroll
    scroll._press(type("Event", (), {"y": 2})())
    scroll._drag(type("Event", (), {"y": scroll.winfo_height()-2})())
    app.root.update()
    assert picker.canvas.yview()[0] > .5
    picker._focus_row(len(picker.rows)-1)
    app.root.update()
    assert app.root.focus_get() == picker.row_widgets[-1]
    picker._select_row(len(picker.rows)-1)
    assert app.api_model_var.get() == "private-model-079"
    assert app._model_settings_confirmed()
    row = picker.row_widgets[-1]
    picker._show_row_tip(row)
    assert row._full_description in picker.provider_tip.cget("text")
    picker.select_provider("OpenAI")
    app.root.update()
    assert not picker.scroll.winfo_ismapped()
