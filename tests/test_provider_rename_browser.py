"""Settings rename dialog through production DOM; regression execution deferred."""
from playwright.sync_api import expect
from tests.test_frontend_review_regressions import browser, page, load
from tests.test_custom_provider_browser import custom_state


def rename_state(page):
    settings = custom_state(page)
    settings["connection"].update(provider="GPT中转", model_provider="OpenAI")
    settings["confirmed"] = settings["has_key"] = True
    load(page, page="settings", settings=settings)
    return settings


def test_custom_rename_dialog_keeps_key_private_and_applies_new_name(page):
    rename_state(page)
    page.evaluate("""()=>{pywebview.api.dispatch=async(action,data)=>{
      calls.push({action,data});if(action==='settings_rename_provider'){
        const s=promptsmithSettings.current;
        return {ok:true,data:{settings:{...s,revision:'renamed',connection:{...s.connection,provider:data.name},
          saved_providers:s.saved_providers.map(n=>n===data.target?data.name:n),provider_families:{[data.name]:'OpenAI'}}}};
      }return {ok:true};};}""")
    page.get_by_role("button", name="重命名", exact=True).click()
    dialog = page.get_by_role("dialog", name="重命名自定义供应商")
    field = dialog.get_by_role("textbox", name="新的服务名称")
    expect(field).to_have_value("GPT中转")
    field.fill("比赛GPT")
    field.press("Enter")
    expect(dialog).to_have_count(0)
    expect(page.get_by_label("服务名称", exact=True)).to_have_value("比赛GPT")
    data = page.evaluate("calls.find(c=>c.action==='settings_rename_provider').data")
    assert data["target"] == "GPT中转" and data["name"] == "比赛GPT"
    assert "key" not in data and "connection" not in data
    assert page.get_by_label("API Key", exact=True).input_value() == ""


def test_cancel_or_failure_keeps_original_profile_and_enter_ime_does_not_send(page):
    rename_state(page)
    page.evaluate("()=>{pywebview.api.dispatch=async(action,data)=>{calls.push({action,data});return action==='settings_rename_provider'?{ok:false,error:'模拟重命名失败'}:{ok:true};};}")
    page.get_by_role("button", name="重命名", exact=True).click()
    dialog = page.get_by_role("dialog", name="重命名自定义供应商")
    field = dialog.get_by_role("textbox", name="新的服务名称")
    field.fill("新名称")
    field.dispatch_event("keydown", {"key": "Enter", "isComposing": True, "keyCode": 229})
    assert not page.evaluate("calls.some(c=>c.action==='settings_rename_provider')")
    dialog.get_by_role("button", name="确认重命名", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("模拟重命名失败")
    expect(dialog).to_be_visible()
    expect(field).to_have_value("新名称")
    expect(page.get_by_label("服务名称", exact=True)).to_have_value("GPT中转")
    dialog.get_by_role("button", name="取消", exact=True).click()
    expect(page.get_by_role("button", name="重命名", exact=True)).to_be_focused()


def test_rename_button_is_next_to_custom_service_and_builtin_uses_full_width(page):
    settings = rename_state(page)
    row = page.locator(".settings-service-row")
    control = row.get_by_role("combobox", name="服务名称", exact=True)
    rename = row.get_by_role("button", name="重命名", exact=True)
    expect(rename).to_be_visible()
    field_box, button_box = control.bounding_box(), rename.bounding_box()
    assert field_box["x"] + field_box["width"] < button_box["x"]
    assert abs(field_box["y"] + field_box["height"]/2 - button_box["y"] - button_box["height"]/2) <= 1
    custom_width = field_box["width"]
    settings["connection"]["provider"] = "OpenAI"
    load(page, page="settings", settings=settings)
    expect(rename).not_to_be_visible()
    assert control.bounding_box()["width"] > custom_width


def test_leaving_settings_closes_rename_dialog_and_restores_controls(page):
    rename_state(page)
    page.get_by_role("button", name="重命名", exact=True).click()
    expect(page.get_by_role("dialog", name="重命名自定义供应商")).to_be_visible()
    page.evaluate("promptsmithSettings.update(null,false)")
    assert page.get_by_role("dialog", name="重命名自定义供应商").count() == 0
    page.evaluate("promptsmithSettings.update(promptsmithSettings.current,true)")
    expect(page.get_by_role("button", name="重命名", exact=True)).to_be_enabled()
