"""Custom service settings through the production browser DOM."""
import pytest
from playwright.sync_api import expect

from tests.test_frontend_review_regressions import browser, page, load


def custom_state(page, **changes):
    state = load(page, page="settings", **changes)
    settings = state["settings"]
    settings.update(saved_providers=["OpenAI", "GPT中转", "Claude中转"],
                    provider_families={"GPT中转": "OpenAI", "Claude中转": "Anthropic"})
    load(page, page="settings", settings=settings, **changes)
    return settings


def test_settings_groups_custom_services_by_selected_family_and_restores_source(page):
    settings = custom_state(page)
    page.evaluate("""() => {pywebview.api.dispatch=async(action,data)=>{
      calls.push({action,data});if(action==='settings_provider')return {ok:true,data:{settings:{...promptsmithSettings.current,
        connection:{provider:data.target,model_provider:'OpenAI',protocol:'OpenAI Responses',base_url:'https://gpt.example.invalid/v1',model:'private-alias',website:'https://gpt.example.invalid'},
        available_models:['private-alias'],has_key:true,confirmed:true,revision:'custom'}}};return {ok:true};}}""")
    page.get_by_role("button", name="服务名称预设", exact=True).click()
    group = page.locator('.settings-provider-group[data-family="OpenAI"]')
    expect(group.get_by_role("option", name="GPT中转", exact=True)).to_be_visible()
    assert group.get_by_role("option", name="OpenAI", exact=True).count() == 1
    assert group.get_by_role("option", name="Claude中转", exact=True).count() == 0
    page.get_by_role("option", name="GPT中转", exact=True).click()
    page.wait_for_function("calls.some(c=>c.action==='settings_provider')")
    payload = page.evaluate("calls.find(c=>c.action==='settings_provider').data")
    assert payload["connection"]["provider"] == settings["connection"]["provider"]
    expect(page.get_by_label("模型供应商", exact=True)).to_have_value("OpenAI")
    expect(page.get_by_label("官网链接", exact=True)).to_have_value("https://gpt.example.invalid")
    expect(page.get_by_role("region", name="已获取模型", exact=True)).to_contain_text("private-alias")
    assert page.get_by_label("API Key", exact=True).input_value() == ""


def test_custom_service_requires_family_before_saving_and_key_visibility_is_ephemeral(page):
    settings = custom_state(page)
    settings["connection"].update(provider="新中转", model_provider="", website="")
    settings["saved_providers"].append("新中转")
    load(page, page="settings", settings=settings)
    key = page.get_by_label("API Key", exact=True)
    key.fill("disposable-typed-key")
    page.get_by_role("button", name="显示密钥", exact=True).click()
    assert key.get_attribute("type") == "text"
    page.get_by_role("button", name="隐藏密钥", exact=True).click()
    assert key.get_attribute("type") == "password"
    page.get_by_role("button", name="保存设置", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("请选择模型供应商")
    assert not page.evaluate("calls.some(c=>c.action==='settings_save')")
    page.get_by_label("模型供应商", exact=True).select_option("Anthropic")
    expect(page.get_by_label("协议", exact=True)).to_have_value("Anthropic Messages")
    page.get_by_role("button", name="保存设置", exact=True).click()
    page.wait_for_function("calls.some(c=>c.action==='settings_save')")
    data = page.evaluate("calls.find(c=>c.action==='settings_save').data")
    assert data["connection"]["model_provider"] == "Anthropic"
    assert data["key"] == "disposable-typed-key"
    assert key.get_attribute("type") == "password"


def test_custom_delete_requires_confirmation_and_builtin_has_no_delete(page):
    settings = custom_state(page)
    expect(page.get_by_role("button", name="删除供应商", exact=True)).not_to_be_visible()
    settings["connection"].update(provider="GPT中转", model_provider="OpenAI")
    load(page, page="settings", settings=settings)
    page.get_by_role("button", name="删除供应商", exact=True).click()
    dialog = page.get_by_role("dialog", name="删除自定义供应商")
    expect(dialog).to_contain_text("GPT中转")
    dialog.get_by_role("button", name="取消", exact=True).click()
    assert not page.evaluate("calls.some(c=>c.action==='settings_delete_provider')")
    page.get_by_role("button", name="删除供应商", exact=True).click()
    dialog.get_by_role("button", name="删除", exact=True).click()
    page.wait_for_function("calls.some(c=>c.action==='settings_delete_provider')")
    assert page.evaluate("calls.find(c=>c.action==='settings_delete_provider').data.target") == "GPT中转"


def test_switching_to_builtin_preserves_custom_source_family_draft(page):
    settings = custom_state(page)
    settings["connection"].update(provider="GPT中转", model_provider="OpenAI")
    load(page, page="settings", settings=settings)
    page.get_by_label("模型供应商", exact=True).select_option("Anthropic")
    page.get_by_role("button", name="服务名称预设", exact=True).click()
    page.get_by_role("listbox", name="服务名称预设", exact=True).get_by_role("option", name="DeepSeek", exact=True).click()
    page.wait_for_function("calls.some(c=>c.action==='settings_provider')")
    source = page.evaluate("calls.find(c=>c.action==='settings_provider').data.connection")
    assert source["provider"] == "GPT中转"
    assert source["model_provider"] == "Anthropic"
    assert source["protocol"] == "Anthropic Messages"


def test_successful_delete_returns_focus_to_visible_service_control(page):
    settings = custom_state(page)
    settings["connection"].update(provider="GPT中转", model_provider="OpenAI")
    load(page, page="settings", settings=settings)
    page.evaluate("""() => {pywebview.api.dispatch=async(action,data)=>{
      calls.push({action,data});if(action==='settings_delete_provider')return {ok:true,data:{settings:{...promptsmithSettings.current,
        connection:{provider:'DeepSeek',...promptsmithSettings.current.providers.DeepSeek},
        saved_providers:['OpenAI','Claude中转'],has_key:false,confirmed:false,revision:'deleted'}}};return {ok:true};}}""")
    page.get_by_role("button", name="删除供应商", exact=True).click()
    dialog = page.get_by_role("dialog", name="删除自定义供应商")
    dialog.get_by_role("button", name="取消", exact=True).click()
    expect(page.get_by_role("button", name="删除供应商", exact=True)).to_be_focused()
    page.get_by_role("button", name="删除供应商", exact=True).click()
    dialog.get_by_role("button", name="删除", exact=True).click()
    expect(page.get_by_label("服务名称", exact=True)).to_be_focused()
