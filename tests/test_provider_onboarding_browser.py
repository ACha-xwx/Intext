"""First-run service setup through production DOM, Controller and Windows DPAPI."""
import json
import sys

import pytest
from playwright.sync_api import expect

from promptsmith.preferences import load_settings
from promptsmith.web_workspace import WorkspaceController
from tests.test_conversation_workspace import app
from tests.test_frontend_review_regressions import browser, page, load


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI")


@pytest.mark.parametrize("key", ["disposable-onboarding-key", "sk-ant-" + "x" * 180,
                                 "token_" + "z" * 1024], ids=["no-prefix", "anthropic-shaped", "long-token"])
def test_new_custom_service_saves_before_model_selection_and_unlocks_tutorial(page, app, key):
    view = WorkspaceController(app)
    view.install_native_bridge()
    view.dispatch("settings", {}, view.snapshot()["stamp"])

    def dispatch(action, data, stamp):
        try:
            return dict(ok=True, data=view.dispatch(action, data, stamp))
        except (ValueError, OSError) as error:
            return dict(ok=False, error=str(error), error_kind="validation" if isinstance(error, ValueError) else "persistence")

    page.expose_function("desktop_dispatch", dispatch)
    page.expose_function("desktop_snapshot", lambda _version: dict(version=1, state=view.snapshot()))
    page.evaluate("""() => {
      pywebview.api.dispatch=(action,data,stamp)=>{calls.push({action,data});return desktop_dispatch(action,data,stamp);};
      pywebview.api.snapshot=desktop_snapshot;
    }""")
    load(page, **dict(view.snapshot(), tutorial_status="not_started"))
    guide = page.get_by_role("dialog", name="新手入门")
    next_step = guide.get_by_role("button", name="下一步", exact=True)
    next_step.click()
    service = page.get_by_label("服务名称", exact=True)
    service.fill("YUN")
    service.press("Tab")
    expect(page.get_by_role("combobox", name="模型供应商", exact=True)).to_be_enabled()
    family = page.get_by_role("combobox", name="模型供应商", exact=True)
    family.click()
    page.get_by_role("listbox", name="模型供应商预设", exact=True).get_by_role("option", name="OpenAI", exact=True).click()
    page.get_by_label("接口地址", exact=True).fill("https://gateway.example.invalid/v1")
    page.get_by_label("API Key", exact=True).fill(key)
    # Keep focus in the key input, as in the user's screenshot; autosave is debounced.
    expect(next_step).to_be_enabled(timeout=3500)
    assert page.get_by_label("模型 ID", exact=True).input_value() == ""
    snap = view.settings_snapshot()
    assert snap["has_key"] and not snap["confirmed"]
    assert snap["connection"]["provider"] == "YUN"
    saved = load_settings(app._preferences_path)
    assert saved.api_key == key
    assert saved.connection["model_provider"] == "OpenAI"
    assert saved.connection["model"] == ""
    assert key not in app._preferences_path.read_text(encoding="utf-8")
    assert key not in json.dumps(view.snapshot())
    expect(page.get_by_label("API Key", exact=True)).to_have_value("")
    next_step.click()
    expect(guide.get_by_role("heading", name="获取可用模型", exact=True)).to_be_visible()
    expect(next_step).to_be_disabled()
    assert all(c["action"] != "settings_test" for c in page.evaluate("calls"))


@pytest.mark.parametrize("name,value,valid", [
    ("thinking_speed", "1", True),
    ("thinking_speed", "1.3", True),
    ("history_save_interval", "2", True),
    ("history_save_interval", "2.7", True),
    ("notification_seconds", "2.5", True),
    ("conversation_width", "900.5", False),
])
def test_numeric_controls_follow_real_preference_contract(page, app, name, value, valid):
    view = WorkspaceController(app)
    view.dispatch("settings", {}, view.snapshot()["stamp"])
    load(page, **view.snapshot())
    page.get_by_role("tab", name=view.settings_snapshot()["fields"][name]["category"], exact=True).click()
    control = page.locator("#settings-field-" + name)
    control.fill(value)
    assert control.evaluate("element=>element.checkValidity()") is valid
