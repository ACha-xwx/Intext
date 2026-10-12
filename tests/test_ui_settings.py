from copy import deepcopy
from types import SimpleNamespace
import tkinter as tk

import pytest

from promptsmith.ui import PromptSmithApp


@pytest.fixture
def app(tk_root, tmp_path):
    window = tk.Toplevel(tk_root)
    window.withdraw()
    application = PromptSmithApp(window, evidence_root=tmp_path / "runs")
    application.api_base_var.set("https://example.invalid/v1")
    application.api_model_var.set("offline-model")
    application.api_key_var.set("offline-fixture-key")
    yield application
    application.shutdown(wait=True)
    window.destroy()


@pytest.mark.parametrize("screen, expected", [((1920, 1080), (1440, 810)), ((1280, 720), (1088, 612)), ((910, 512), (720, 405))])
def test_default_window_fits_screen_at_16_9(tk_root, tmp_path, monkeypatch, screen, expected):
    window = tk.Toplevel(tk_root)
    window.withdraw()
    monkeypatch.setattr(window, "winfo_screenwidth", lambda: screen[0])
    monkeypatch.setattr(window, "winfo_screenheight", lambda: screen[1])
    application = PromptSmithApp(window, evidence_root=tmp_path / "runs")
    try:
        window.update_idletasks()
        width, height = map(int, window.geometry().split("+", 1)[0].split("x"))
        assert (width, height) == expected
        assert width * 9 == height * 16
        window.deiconify()
        window.update()
        for name in ("settings_button", "save_button"):
            widget = application.widgets[name]
            assert widget.winfo_ismapped()
            assert widget.winfo_rootx() + widget.winfo_width() <= window.winfo_rootx() + width
    finally:
        application.shutdown(wait=True)
        window.destroy()


def test_settings_navigation_keeps_unsynced_inputs_and_business_state(app):
    app.widgets["task_text"].insert("1.0", "为课堂制作一份讲解提纲")
    app.answer_var.set("尚未提交的补充")
    app.show_workspace(1)
    before = deepcopy(app.session.to_dict())
    app.widgets["settings_button"].invoke()
    app.widgets["settings_button"].invoke()
    assert app.notebook.index(app.notebook.select()) == 4
    app.widgets["analyze_button"].invoke()
    assert app.notebook.index(app.notebook.select()) == 1
    assert app.session.to_dict() == before
    assert app.answer_var.get() == "尚未提交的补充"


def test_probe_success_does_not_confirm_or_enable_generation(app, monkeypatch):
    app.show_settings()
    calls = []
    monkeypatch.setattr(app, "_client", lambda config: SimpleNamespace(
        test_connection=lambda: SimpleNamespace(model=config.model, latency_ms=1, probe_truncated=False)
    ))
    monkeypatch.setattr(app, "_submit", lambda operation, success, failure: (calls.append("probe"), success(operation())))
    app.widgets["test_connection_button"].invoke()
    assert calls == ["probe"]
    assert "连接成功" in app.status_var.get()
    assert not app._model_settings_confirmed()
    assert app._missing_generation_config() == ["确认模型设置"]
    with pytest.raises(ValueError, match="确认"):
        app._api_config()
    app.widgets["confirm_model_settings_button"].invoke()
    assert app._model_settings_confirmed()
    assert app._api_config().model == "offline-model"
    assert calls == ["probe"]
    assert app.notebook.index(app.notebook.select()) == 4


def test_confirm_does_not_require_probe_or_mutate_session(app, monkeypatch):
    monkeypatch.setattr(app, "_submit", lambda *args: pytest.fail("Confirmation must not call a model"))
    before = deepcopy(app.session.to_dict())
    app.widgets["confirm_model_settings_button"].invoke()
    assert app._model_settings_confirmed()
    assert app._missing_generation_config() == []
    assert app.session.to_dict() == before
    assert "offline-fixture-key" not in str(app.session.to_dict())


@pytest.mark.parametrize("field, value", [("provider_var", "Custom Service"), ("protocol_var", "OpenAI Responses"), ("api_base_var", "https://changed.invalid/v1"), ("api_model_var", "changed-model"), ("api_key_var", "changed-key")])
def test_changing_confirmed_config_requires_explicit_reconfirmation(app, field, value):
    app.confirm_model_settings()
    variable = getattr(app, field)
    original = variable.get()
    version = app.connection_version
    variable.set(value)
    assert not app._model_settings_confirmed()
    assert app.connection_version > version
    variable.set(original)
    if field == "provider_var":
        # Switching back now restores that provider's explicitly saved profile.
        assert app._model_settings_confirmed()
        assert app._api_config().api_key == "offline-fixture-key"
        return
    assert not app._model_settings_confirmed()
    with pytest.raises(ValueError, match="确认"):
        app._api_config()


def test_incomplete_config_cannot_be_confirmed(app, monkeypatch):
    notices = []
    monkeypatch.setattr("promptsmith.ui.messagebox.showerror", lambda *args, **kwargs: notices.append(args))
    app.api_key_var.set("")
    app.widgets["confirm_model_settings_button"].invoke()
    assert notices
    assert not app._model_settings_confirmed()
    assert "未确认" in app.status_var.get()


def test_unconfirmed_config_routes_to_confirm_button(app):
    app.widgets["task_text"].insert("1.0", "为课堂制作一份讲解提纲")
    app.run_primary_action()
    assert app.notebook.index(app.notebook.select()) == 4
    assert app._primary_action().kind == "return_from_settings"
    assert not app._model_settings_confirmed()
