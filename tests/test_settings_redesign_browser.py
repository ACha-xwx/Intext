"""Settings interactions through the production DOM, isolated desktop bridge."""
from tests.test_frontend_review_regressions import browser, page, load
import pytest


def test_service_arrow_closes_once_even_when_input_has_focus(page):
    load(page, page="settings")
    service = page.get_by_label("服务名称", exact=True)
    service.click()
    toggle = page.get_by_role("button", name="服务名称预设", exact=True)
    assert toggle.get_attribute("aria-expanded") == "true"
    page.evaluate("calls.length=0")
    toggle.click()
    page.wait_for_timeout(300)
    assert toggle.get_attribute("aria-expanded") == "false"
    events = page.evaluate("calls.filter(c=>c.action==='diagnostic'&&c.args[1].startsWith('settings suggestions')).map(c=>c.args[1])")
    assert events == ["settings suggestions closed"]


def test_edit_autosaves_without_save_or_confirm_buttons(page):
    from playwright.sync_api import expect
    load(page, page="settings")
    page.evaluate("""() => {pywebview.api.dispatch=async(action,data)=>{
      calls.push({action,data});return {ok:true,data:{settings:{...promptsmithSettings.current,
        connection:data.connection,values:data.values,revision:'saved',has_key:true,confirmed:true}}};
    }}""")
    model = page.get_by_label("模型 ID", exact=True)
    model.fill("my-new-model")
    page.wait_for_function("calls.some(c=>c.action==='settings_autosave')", timeout=2000)
    expect(model).to_have_value("my-new-model")
    assert page.get_by_role("button", name="保存设置", exact=True).count() == 0
    assert page.get_by_role("button", name="确认", exact=True).count() == 0
    assert page.get_by_role("button", name="已确认", exact=True).count() == 0


def test_all_setting_choices_use_animated_menus_and_provider_icons(page):
    from playwright.sync_api import expect
    state = load(page, page="settings")
    state["settings"]["connection"].update(provider="测试中转", model_provider="OpenAI")
    state["settings"]["available_models"] = ["gpt-6.1-sol", "private-alias"]
    load(page, page="settings", settings=state["settings"])
    family = page.get_by_role("combobox", name="模型供应商", exact=True)
    family.click()
    menu = page.get_by_role("listbox", name="模型供应商预设", exact=True)
    expect(menu).to_be_visible()
    assert menu.locator(".provider").count() == 5
    assert menu.evaluate("e=>getComputedStyle(e).animationName") != "none"
    page.keyboard.press("Escape")
    page.get_by_label("模型 ID", exact=True).click()
    assert page.get_by_role("listbox", name="模型 ID预设").locator(".provider").count() == 2
    assert page.locator(".settings-form select").count() == 0
    page.get_by_role("tab", name="界面", exact=True).click()
    theme = page.get_by_role("combobox", name="输入区与模型菜单主题", exact=True)
    theme.click()
    expect(page.get_by_role("option", name="深色", exact=True)).to_be_visible()
    theme.press("End")
    theme.press("Enter")
    expect(theme).to_have_text("深色")


def test_settings_use_reference_card_label_above_and_icon_underline_navigation(page):
    load(page, page="settings")
    assert page.locator(".settings-card").count() == 1
    assert page.locator(".settings-local-nav").count() == 1
    for tab in page.get_by_role("tab").all():
        assert tab.locator("svg").count() == 1
        assert tab.evaluate("e=>getComputedStyle(e,'::before').height") == "2px"
    label = page.locator('label[for="settings-field-connection-provider"]')
    control = page.get_by_label("服务名称", exact=True)
    a, b = label.bounding_box(), control.bounding_box()
    assert a["y"] + a["height"] <= b["y"]
    assert page.get_by_role("region", name="已获取模型", exact=True).count() == 0
    assert page.locator(".settings-brand").count() == 0


def test_slow_autosave_keeps_newer_input_and_serializes_updates(page):
    load(page, page="settings")
    page.evaluate("""() => {window.releaseSave=null;pywebview.api.dispatch=async(action,data)=>{
      calls.push({action,data});if(calls.filter(c=>c.action==='settings_autosave').length===1)await new Promise(resolve=>releaseSave=resolve);
      return {ok:true,data:{settings:{...promptsmithSettings.current,connection:data.connection,values:data.values,revision:data.connection.model}}};
    }}""")
    model = page.get_by_label("模型 ID", exact=True)
    model.fill("first-model")
    page.wait_for_function("releaseSave!==null")
    assert model.is_enabled()
    model.fill("latest-model")
    page.evaluate("releaseSave()")
    page.wait_for_function("calls.filter(c=>c.action==='settings_autosave').length===2")
    page.wait_for_function("!promptsmithSettings.saving")
    assert model.input_value() == "latest-model"
    assert page.evaluate("calls.filter(c=>c.action==='settings_autosave').map(c=>c.data.connection.model)") == ["first-model", "latest-model"]


def test_dropdown_is_a_floating_panel_without_moving_following_fields(page):
    from playwright.sync_api import expect
    state = load(page, page="settings")
    state["settings"]["connection"].update(provider="测试中转", model_provider="OpenAI")
    load(page, page="settings", settings=state["settings"])
    website = page.get_by_label("官网链接", exact=True)
    before = website.bounding_box()
    family = page.get_by_role("combobox", name="模型供应商", exact=True)
    family.click()
    menu = page.get_by_role("listbox", name="模型供应商预设", exact=True)
    expect(menu).to_be_visible()
    after = website.bounding_box()
    assert abs(before["y"] - after["y"]) < 1
    assert menu.evaluate("e=>getComputedStyle(e).position") == "fixed"
    page.keyboard.press("Escape")
    expect(menu).not_to_be_visible()


@pytest.mark.parametrize("width", [480, 720, 1440])
def test_navigation_fills_width_and_accepts_additional_categories(page, width):
    page.set_viewport_size({"width": width, "height": 810})
    state = load(page, page="settings")
    nav = page.locator(".settings-tabs").bounding_box()
    first, last = page.get_by_role("tab").first.bounding_box(), page.get_by_role("tab").last.bounding_box()
    assert abs(first["x"] - nav["x"]) < 1
    assert abs(last["x"] + last["width"] - nav["x"] - nav["width"]) < 1
    state["settings"]["fields"]["future_setting"] = dict(category="扩展", label="扩展设置", default="")
    state["settings"]["values"]["future_setting"] = ""
    load(page, page="settings", settings=state["settings"])
    extra = page.get_by_role("tab", name="扩展", exact=True)
    assert extra.is_visible()
    box = extra.bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= width
    rows = {}
    for tab in page.get_by_role("tab").all():
        bounds = tab.bounding_box()
        rows.setdefault(round(bounds["y"]), []).append(bounds)
    if width == 480:
        assert len(rows) > 1
    elif width == 1440:
        assert len(rows) == 1
    for row in rows.values():
        assert abs(row[0]["x"] - nav["x"]) < 1
        assert abs(row[-1]["x"] + row[-1]["width"] - nav["x"] - nav["width"]) < 1
        assert max(item["width"] for item in row) - min(item["width"] for item in row) < 1
    extra.click()
    assert page.get_by_label("扩展设置", exact=True).is_visible()


def test_debug_toggle_remains_immediate_while_model_is_running(page):
    from playwright.sync_api import expect
    state = load(page, page="settings")
    state["settings"]["busy"] = True
    load(page, page="settings", settings=state["settings"])
    page.get_by_role("tab", name="诊断", exact=True).click()
    toggle = page.get_by_role("switch", name="开启 Debug 控制台", exact=True)
    expect(toggle).to_be_enabled()
    toggle.click()
    page.wait_for_function("calls.some(c=>c.action==='settings_debug')", timeout=2000)
    assert page.evaluate("calls.find(c=>c.action==='settings_debug').data.enabled") is True


def test_switch_during_slow_save_never_saves_source_under_destination(page):
    load(page, page="settings")
    page.evaluate("""() => {window.releaseSave=null;pywebview.api.dispatch=async(action,data)=>{
      calls.push({action,data});if(action==='settings_autosave'&&calls.filter(c=>c.action===action).length===1)
        await new Promise(resolve=>releaseSave=resolve);
      return {ok:true,data:{settings:{...promptsmithSettings.current,connection:action==='settings_provider'?
        {provider:data.target,...promptsmithSettings.current.providers[data.target]}:data.connection,values:data.values,revision:'updated'}}};
    }}""")
    page.get_by_label("模型 ID", exact=True).fill("source-model")
    page.wait_for_function("releaseSave!==null")
    page.get_by_label("服务名称", exact=True).click()
    page.get_by_role("listbox", name="服务名称预设", exact=True).get_by_role("option", name="DeepSeek", exact=True).click()
    page.evaluate("releaseSave()")
    page.wait_for_function("calls.some(c=>c.action==='settings_provider')")
    assert page.evaluate("calls.filter(c=>c.action==='settings_autosave').every(c=>c.data.connection.provider==='OpenAI')")
    assert page.evaluate("calls.find(c=>c.action==='settings_provider').data.target") == "DeepSeek"


def test_failed_save_keeps_source_and_key_until_retry_before_switch(page):
    load(page, page="settings")
    page.evaluate("""() => {window.failSave=true;pywebview.api.dispatch=async(action,data)=>{
      calls.push({action,data});if(action==='settings_autosave'&&failSave)return {ok:false,error_kind:'persistence',error:'模拟磁盘写入失败'};
      return {ok:true,data:{settings:{...promptsmithSettings.current,connection:action==='settings_provider'?
        {provider:data.target,...promptsmithSettings.current.providers[data.target]}:data.connection,values:data.values,revision:'retry-saved'}}};
    }}""")
    page.get_by_label("API Key", exact=True).fill("disposable-failed-save-key")
    page.get_by_label("服务名称", exact=True).click()
    page.get_by_role("listbox", name="服务名称预设", exact=True).get_by_role("option", name="DeepSeek", exact=True).click()
    page.wait_for_function("calls.some(c=>c.action==='settings_autosave')")
    page.wait_for_function("!promptsmithSettings.switching&&!promptsmithSettings.saving")
    assert not page.evaluate("calls.some(c=>c.action==='settings_provider')")
    assert page.get_by_label("API Key", exact=True).input_value() == "disposable-failed-save-key"
    assert page.get_by_label("服务名称", exact=True).input_value() == "OpenAI"
    page.evaluate("failSave=false")
    page.get_by_role("button", name="重试自动保存", exact=True).click()
    page.wait_for_function("!promptsmithSettings.saving&&promptsmithSettings.keyAction==='keep'")
    assert page.get_by_label("API Key", exact=True).input_value() == ""


def test_typing_service_name_during_save_does_not_commit_a_different_identity(page):
    load(page, page="settings")
    page.evaluate("""() => {window.releaseSave=null;pywebview.api.dispatch=async(action,data)=>{
      calls.push({action,data});if(action==='settings_autosave'&&calls.filter(c=>c.action===action).length===1)
        await new Promise(resolve=>releaseSave=resolve);
      return {ok:true,data:{settings:{...promptsmithSettings.current,connection:data.connection,values:data.values,revision:'updated'}}};
    }}""")
    page.get_by_label("模型 ID", exact=True).fill("source-model")
    page.wait_for_function("releaseSave!==null")
    page.get_by_label("服务名称", exact=True).fill("DeepSeek")
    page.evaluate("releaseSave()")
    page.wait_for_function("!promptsmithSettings.saving")
    assert page.evaluate("calls.filter(c=>c.action==='settings_autosave').every(c=>c.data.connection.provider==='OpenAI')")
    assert not page.evaluate("calls.some(c=>c.action==='settings_provider')")
    assert page.get_by_label("服务名称", exact=True).input_value() == "DeepSeek"


def test_incomplete_connection_draft_can_be_staged_by_switching_service(page):
    load(page, page="settings")
    page.evaluate("""() => {pywebview.api.dispatch=async(action,data)=>{
      calls.push({action,data});if(action==='settings_autosave')return {ok:false,error_kind:'validation',error:'地址必须为HTTP(S) URL'};
      return {ok:true,data:{settings:{...promptsmithSettings.current,connection:{provider:data.target,...promptsmithSettings.current.providers[data.target]},revision:'switched'}}};
    }}""")
    page.get_by_label("接口地址", exact=True).fill("")
    page.get_by_label("服务名称", exact=True).click()
    page.get_by_role("listbox", name="服务名称预设", exact=True).get_by_role("option", name="DeepSeek", exact=True).click()
    page.wait_for_function("calls.some(c=>c.action==='settings_provider')", timeout=2500)
    assert page.evaluate("calls.find(c=>c.action==='settings_provider').data.connection.base_url") == ""
