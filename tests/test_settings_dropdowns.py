"""Settings dropdown presentation at the production browser DOM boundary."""

import pytest

from tests.test_frontend_review_regressions import browser, page as browser_page, load
from tests.test_custom_provider_browser import choose_setting


@pytest.fixture
def page(browser_page):
    browser_page.evaluate("""() => {pywebview.api.dispatch=async(action,data)=>{
      calls.push({action,data});
      if(action==='settings_autosave')return {ok:true,data:{settings:{...promptsmithSettings.current,
        connection:data.connection,values:data.values,revision:'autosaved'}}};
      if(action==='settings_provider'){
        const current=promptsmithSettings.current;
        return {ok:true,data:{settings:{...current,
          connection:{provider:data.target,...(current.providers[data.target]||{protocol:'OpenAI Chat Completions',base_url:'',model:'',model_provider:''})},
          has_key:false,confirmed:false,available_models:[],revision:'switched-'+data.target}}};
      }
      return {ok:true};
    }}""")
    return browser_page


def test_filled_provider_opens_all_presets_and_protocol_remains_clickable(page):
    from playwright.sync_api import expect

    state = load(page, page="settings")
    state["settings"]["connection"].update(state["settings"]["providers"]["DeepSeek"], provider="DeepSeek")
    load(page, page="settings", settings=state["settings"])
    provider = page.get_by_label("服务名称", exact=True)
    box = provider.bounding_box()
    page.mouse.click(box["x"] + box["width"] - 18, box["y"] + box["height"] / 2)
    choices = page.get_by_role("listbox", name="服务名称预设", exact=True)
    expect(choices).to_be_visible()
    for name in state["settings"]["providers"]:
        expect(choices.get_by_role("option", name=name, exact=True)).to_be_visible()
    choices.get_by_role("option", name="OpenAI", exact=True).click()
    assert provider.input_value() == "OpenAI"
    assert page.get_by_label("接口地址", exact=True).input_value() == "https://api.openai.com/v1"
    assert page.get_by_label("模型 ID", exact=True).input_value() == "gpt-6.1-sol"
    expect(choices).not_to_be_visible()
    protocol = page.get_by_label("协议", exact=True)
    protocol.click()
    page.keyboard.press("Escape")
    expect(protocol).to_be_focused()
    protocol.press("Home")
    protocol.press("Enter")
    assert protocol.get_attribute("data-value") == "OpenAI Chat Completions"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_settings_suggestions_float_without_reflow_and_support_custom_input_and_keyboard(page, theme):
    from playwright.sync_api import expect

    page.set_viewport_size({"width": 720, "height": 500})
    state = load(page, page="settings", theme=theme)
    provider = page.get_by_label("服务名称", exact=True)
    following = page.get_by_label("模型供应商", exact=True)
    before = following.bounding_box()
    provider.click()
    choices = page.get_by_role("listbox", name="服务名称预设", exact=True)
    protocol = page.get_by_label("协议", exact=True)
    assert abs(following.bounding_box()["y"] - before["y"]) < 1
    page.keyboard.press("Escape")
    expect(choices).not_to_be_visible()
    protocol.click()
    page.keyboard.press("Escape")
    expect(protocol).to_be_focused()
    provider.focus()
    provider.press("ArrowUp")
    provider.press("Enter")
    assert provider.input_value() == "Google"
    assert page.get_by_label("模型 ID", exact=True).input_value() == "gemini-3.8-flash"
    expect(choices).not_to_be_visible()
    provider.fill("Anth")
    expect(choices.get_by_role("option", name="Anthropic", exact=True)).to_be_visible()
    assert choices.get_by_role("option").count() == 1
    provider.press("Escape")
    assert provider.input_value() == "Anth"
    expect(provider).to_be_focused()
    provider.fill("自定义中转")
    provider.press("Tab")
    expect(choices).not_to_be_visible()
    page.get_by_role("button", name="服务名称预设", exact=True).click()
    assert choices.get_by_role("option").count() == 5
    page.get_by_role("tab", name="界面", exact=True).click()
    expect(choices).not_to_be_visible()
    page.get_by_role("tab", name="模型", exact=True).click()
    assert provider.input_value() == "自定义中转"
    page.get_by_role("button", name="服务名称预设", exact=True).click()
    load(page, page="settings", settings=state["settings"])
    expect(choices).to_be_visible()
    state["settings"]["busy"] = True
    load(page, page="settings", settings=state["settings"])
    expect(choices).not_to_be_visible()
    expect(page.get_by_role("button", name="服务名称预设", exact=True)).to_be_disabled()
    state["settings"]["busy"] = False
    load(page, page="settings", settings=state["settings"])
    page.get_by_role("button", name="服务名称预设", exact=True).click()
    load(page, page="workspace", settings=state["settings"])
    expect(choices).not_to_be_visible()


def test_model_suggestions_refresh_without_overwriting_custom_drafts_or_changing_credentials(page):
    from playwright.sync_api import expect

    state = load(page, page="settings")
    state["settings"]["available_models"] = ["deepseek-flash", "gpt-6.1-sol"]
    load(page, page="settings", settings=state["settings"])
    model = page.get_by_label("模型 ID", exact=True)
    page.get_by_role("button", name="模型 ID预设", exact=True).click()
    choices = page.get_by_role("listbox", name="模型 ID预设", exact=True)
    choices.get_by_role("option", name="deepseek-flash", exact=True).click()
    assert model.input_value() == "deepseek-flash"
    expect(choices).not_to_be_visible()
    page.get_by_role("button", name="模型 ID预设", exact=True).click()
    state["settings"]["available_models"] = ["deepseek-flash", "gpt-6.1-sol", "custom-model"]
    load(page, page="settings", settings=state["settings"])
    expect(choices.get_by_role("option", name="custom-model", exact=True)).to_be_visible()
    model.fill("my-model")
    model.press("Tab")
    page.wait_for_function("!promptsmithSettings.saving&&!promptsmithSettings.dirty.size")
    state["settings"] = page.evaluate("promptsmithSettings.current")
    load(page, page="settings", settings=state["settings"])
    assert model.input_value() == "my-model"
    page.wait_for_function("calls.some(c=>c.action==='settings_autosave'&&c.data.connection.model==='my-model')")
    payload = page.evaluate("calls.find(c=>c.action==='settings_autosave'&&c.data.connection.model==='my-model').data")
    assert payload["connection"]["model"] == "my-model"
    assert payload["key_action"] == "keep"
    assert not any(word in page.evaluate("JSON.stringify(calls.filter(c=>c.action==='diagnostic'))")
                   for word in ("my-model", "deepseek-flash", "custom-model"))


def test_clicking_exact_typed_preset_applies_linked_fields_without_clearing_same_saved_selection(page):
    state = load(page, page="settings")
    provider = page.get_by_label("服务名称", exact=True)
    provider.fill("DeepSeek")
    page.get_by_role("listbox", name="服务名称预设", exact=True).get_by_role("option", name="DeepSeek", exact=True).click()
    assert page.get_by_label("模型 ID", exact=True).input_value() == "deepseek-flash"
    assert page.get_by_label("接口地址", exact=True).input_value() == "https://api.deepseek.com"
    # The new provider has its own empty credential; keep no longer means reuse
    # the old provider's key. The source profile was preserved by the switch.
    assert page.evaluate("calls.find(c=>c.action==='settings_provider').data.key_action") == "keep"

    # A fresh form with a saved preset must not invalidate its credential just
    # because the same preset is selected again.
    page.reload()
    page.evaluate("window.calls=[];window.pywebview={api:{diagnostic:async()=>{},snapshot:async()=>null,dispatch:async(action,data)=>{calls.push({action,data});return {ok:true};}}}")
    load(page, page="settings", settings=state["settings"])
    page.get_by_role("button", name="服务名称预设", exact=True).click()
    page.get_by_role("listbox", name="服务名称预设", exact=True).get_by_role("option", name="OpenAI", exact=True).click()
    page.wait_for_timeout(550)
    assert not page.evaluate("calls.some(c=>c.action==='settings_autosave'||c.action==='settings_provider')")
    assert page.evaluate("promptsmithSettings.current.has_key") == state["settings"]["has_key"]


@pytest.mark.parametrize("theme,font,width", [("light", 12, 1440), ("dark", 12, 1440),
                                             ("light", 9, 720), ("dark", 18, 720)])
def test_settings_dropdown_arrows_stay_centered_for_native_and_editable_choices(page, theme, font, width):
    page.set_viewport_size({"width": width, "height": 810})
    state = load(page, page="settings", theme=theme, font_size=font)
    for category in ["模型", "界面", "会话与导出", "诊断"]:
        page.get_by_role("tab", name=category, exact=True).click()
        choices = page.locator('.settings-form:not([hidden]) [role="combobox"]')
        for choice in choices.all():
            choice.scroll_into_view_if_needed()
            arrow = choice.locator("..").locator(".settings-choice-arrow")
            assert arrow.count() == 1, "Every dropdown needs one consistently positioned arrow."
            field_box, arrow_box = choice.bounding_box(), arrow.bounding_box()
            assert abs((field_box["y"] + field_box["height"] / 2) -
                       (arrow_box["y"] + arrow_box["height"] / 2)) <= 1
            assert field_box["x"] < arrow_box["x"] < arrow_box["x"] + arrow_box["width"] < field_box["x"] + field_box["width"]
            assert arrow.get_attribute("aria-hidden") == "true"
            assert arrow.evaluate("e=>getComputedStyle(e).pointerEvents") == "none"
    load(page, page="settings", theme=theme, font_size=font, settings=state["settings"])
    assert page.locator(".settings-choice-arrow").count() == page.locator('.settings-form [role="combobox"]').count()


def test_settings_choice_wrappers_keep_custom_inputs_presets_keyboard_and_save_payload(page):
    state = load(page, page="settings")
    provider = page.get_by_label("服务名称", exact=True)
    provider.fill("DeepSeek")
    provider.press("Tab")
    assert page.get_by_label("接口地址", exact=True).input_value() == "https://api.deepseek.com"
    assert page.get_by_label("模型 ID", exact=True).input_value() == "deepseek-flash"
    protocol = page.get_by_label("协议", exact=True)
    protocol.focus()
    protocol.press("Home")
    protocol.press("ArrowDown")
    protocol.press("Enter")
    assert protocol.get_attribute("data-value") == "OpenAI Responses"
    provider.fill("自建中转服务")
    provider.press("Tab")
    page.wait_for_function("!inFlight&&promptsmithSettings.current.connection.provider==='自建中转服务'")
    choose_setting(page, "模型供应商", "OpenAI")
    page.get_by_label("接口地址", exact=True).fill("https://gateway.example.invalid/v1")
    model = page.get_by_label("模型 ID", exact=True)
    model.fill("custom-model-v2")
    model.press("Tab")
    updated = page.evaluate("promptsmithSettings.current")
    load(page, page="settings", settings=updated)
    assert provider.input_value() == "自建中转服务" and model.input_value() == "custom-model-v2"
    page.wait_for_function("calls.some(c=>c.action==='settings_autosave'&&c.data.connection.model==='custom-model-v2')")
    payload = page.evaluate("calls.find(c=>c.action==='settings_autosave'&&c.data.connection.model==='custom-model-v2').data")
    assert payload["connection"]["provider"] == "自建中转服务"
    assert payload["connection"]["model"] == "custom-model-v2"
    assert payload["connection"]["protocol"] == "OpenAI Responses"
    assert page.evaluate("calls.filter(c=>c.action==='diagnostic'&&c.args[1]==='settings fields rendered').length") == 1
