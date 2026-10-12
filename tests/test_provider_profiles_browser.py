"""Production DOM; only the external desktop boundary is simulated."""
import pytest

from tests.test_frontend_review_regressions import browser, page, load


def test_provider_switch_submits_source_draft_and_uses_restored_profile(page):
    state = load(page, page="settings")
    state["settings"]["connection"].update(state["settings"]["providers"]["DeepSeek"], provider="DeepSeek")
    load(page, page="settings", settings=state["settings"])
    page.evaluate("""() => {pywebview.api.dispatch=async(action,data)=>{
        calls.push({action,data});
        if(action==='settings_provider')return {ok:true,data:{settings:{...promptsmithSettings.current,
            connection:{provider:'OpenAI',protocol:'OpenAI Responses',base_url:'https://saved.example.invalid/v1',model:'saved-model'},
            available_models:['saved-model'],has_key:true,confirmed:true,revision:'restored'}}};
        return {ok:true};
    }}""")
    page.get_by_label("API Key", exact=True).fill("disposable-browser-draft")
    page.get_by_role("button", name="服务名称预设", exact=True).click()
    page.get_by_role("option", name="OpenAI", exact=True).click()
    page.wait_for_function("calls.some(c=>c.action==='settings_provider')")
    payload = page.evaluate("calls.find(c=>c.action==='settings_provider').data")
    assert payload["target"] == "OpenAI"
    assert payload["connection"]["provider"] == "DeepSeek"
    assert payload["key_action"] == "replace" and payload["key"] == "disposable-browser-draft"
    assert page.get_by_label("接口地址", exact=True).input_value() == "https://saved.example.invalid/v1"
    assert page.get_by_label("API Key", exact=True).input_value() == ""
    assert "已配置" in page.get_by_label("API Key", exact=True).get_attribute("placeholder")
    assert "disposable-browser-draft" not in page.evaluate("JSON.stringify(promptsmithSettings.current)")


def test_model_menu_empty_directory_guides_to_settings(page):
    from playwright.sync_api import expect
    load(page, models=[])
    page.locator("#model-button").click()
    expect(page.get_by_text("请先在设置中为供应商获取模型列表。", exact=True)).to_be_visible()


def test_provider_menu_has_icons_and_animates_closed_without_intercepting_input(page):
    load(page, page="settings")
    toggle = page.get_by_role("button", name="服务名称预设", exact=True)
    toggle.click()
    choices = page.locator("#settings-field-connection-provider-suggestions")
    assert choices.locator("img").count() == 5
    assert choices.evaluate("e=>getComputedStyle(e).borderRadius") == "16px"
    page.wait_for_timeout(420)
    toggle.evaluate("e=>e.click()")
    assert choices.evaluate("e=>!e.hidden&&e.inert&&e.getAnimations().some(a=>a.playState==='running')")
    page.wait_for_timeout(280)
    assert choices.evaluate("e=>e.hidden")
    toggle.click()
    page.get_by_label("服务名称", exact=True).press("ArrowUp")
    page.get_by_label("服务名称", exact=True).press("Escape")
    assert page.get_by_label("服务名称", exact=True).get_attribute("aria-expanded") == "false"


@pytest.mark.parametrize("theme,width", [("light", 1440), ("dark", 720)])
def test_selected_provider_checkmark_stays_compact_and_all_five_rows_are_readable(page, theme, width):
    page.set_viewport_size({"width": width, "height": 810})
    load(page, page="settings", theme=theme)
    page.get_by_role("button", name="服务名称预设", exact=True).click()
    choices = page.get_by_role("listbox", name="服务名称预设", exact=True)
    page.wait_for_timeout(420)
    selected = choices.locator('[aria-selected="true"]')
    checkmark = selected.locator("svg").bounding_box()
    assert 12 <= checkmark["width"] <= 24 and 12 <= checkmark["height"] <= 24
    for option in choices.get_by_role("option").all():
        box = option.bounding_box()
        assert 38 <= box["height"] <= 60
    assert choices.evaluate("e=>e.scrollHeight<=e.clientHeight+1")
