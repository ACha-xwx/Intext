"""Regression checks of the actual font and picker symptoms reported by users."""
import json


from promptsmith.model_catalog import find_model
from promptsmith.preferences import defaults, load_settings
from tests.test_conversation_workspace import app


def test_high_default_and_legacy_auto_migration_preserve_verified_interface(app):
    assert defaults()["reasoning_effort"] == "high"
    app.preference_vars["reasoning_effort"].set("auto")
    app.confirm_model_settings()
    document = json.loads(app._preferences_path.read_text(encoding="utf-8"))
    document.pop("composer_defaults")
    app._preferences_path.write_text(json.dumps(document), encoding="utf-8")
    loaded = load_settings(app._preferences_path)
    assert loaded.preferences["reasoning_effort"] == "high"
    assert loaded.model_confirmed
    # Explicit newer selections in the full settings page remain intentional.
    app.confirm_model_settings()
    assert load_settings(app._preferences_path).preferences["reasoning_effort"] == "auto"


def test_picker_choice_cannot_confirm_other_pending_settings_drafts(app):
    composer = app.widgets["conversation_composer"]
    app.preference_vars["temperature"].set("0.5")
    assert not app._model_settings_confirmed()
    composer.choose_model(find_model("gpt-6-astra"))
    composer.choose_effort("max")
    assert not app._model_settings_confirmed()
    assert "右上角设置" in app.status_var.get()


def test_picker_cache_reused_check_centered_and_no_extra_actions(app):
    composer = app.widgets["conversation_composer"]
    app.root.deiconify()
    app.root.update()
    composer.choose_model(find_model("deepseek-flash"))
    composer.toggle_picker()
    app.root.update()
    picker = composer.picker
    row = next(r for r in picker.row_widgets if r._model_id == "deepseek-flash")
    assert abs((row._check.winfo_rooty()+row._check.winfo_height()/2)
               -(row._name.winfo_rooty()+row._name.winfo_height()/2)) <= 1
    assert not hasattr(picker, "confirm_button")
    assert picker.effort_buttons["high"].selected
    before = tuple(row.find_all())
    for _ in range(5):
        composer.refresh()
    assert tuple(row.find_all()) == before
    picker.close()
    composer.toggle_picker()
    assert composer.picker is picker
    assert picker.window.winfo_exists()
    assert not picker._closed
    # Changing font/theme disposes the old cached window, not just its view.
    app.preference_vars["composer_theme"].set("dark")
    assert app.save_settings()
    assert not picker.window.winfo_exists()


def test_provider_images_have_smooth_partial_alpha_pixels(app):
    from PIL import ImageTk
    from promptsmith.display import display_scale
    composer = app.widgets["conversation_composer"]
    image = ImageTk.getimage(composer.icons["OpenAI"])
    assert image.width == round(24*display_scale(app.root))
    assert any(0 < pixel[3] < 255 for pixel in image.getdata())
    # Typeface selection cannot move or change the checkmark glyph.
    assert composer.check_icon.width() == 20


def test_choice_save_failure_keeps_old_saved_settings_and_reports_next_action(app, monkeypatch):
    composer = app.widgets["conversation_composer"]
    before = app._preferences_path.read_bytes()
    monkeypatch.setattr("promptsmith.settings_ui.save_preferences", lambda *a, **k: (_ for _ in ()).throw(PermissionError("write denied")))
    composer.choose_effort("max")
    assert app._preferences_path.read_bytes() == before
    assert not app._model_settings_confirmed()
    assert "设置未保存" in app.settings_status_var.get()
    assert "请修改" in app.settings_status_var.get()
    assert app.dialogs
