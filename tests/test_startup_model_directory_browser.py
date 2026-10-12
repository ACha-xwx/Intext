"""Automatic directory feedback at the production settings DOM boundary."""
from tests.test_frontend_review_regressions import browser, page, load
from tests.test_custom_provider_browser import custom_state


def test_auto_directory_status_updates_in_place_and_keeps_manual_action_available(page):
    settings = custom_state(page)
    settings["available_models"] = ["cached-model"]
    settings["directory_status"] = "正在自动获取模型列表，已有列表仍可使用。"
    load(page, page="settings", settings=settings)
    status = page.get_by_role("status").filter(has_text="正在自动获取")
    assert status.is_visible()
    assert page.get_by_role("button", name="获取模型", exact=True).is_enabled()
    original_input = page.get_by_label("接口地址", exact=True)
    original_input.fill("http://localhost:4567/v1")
    settings["directory_status"] = "自动获取模型列表失败。已有列表保留，可点击“获取模型”重试。"
    load(page, page="settings", settings=settings)
    assert page.get_by_role("status").filter(has_text="自动获取模型列表失败").is_visible()
    assert original_input.input_value() == "http://localhost:4567/v1"
    assert page.get_by_text("cached-model", exact=True).is_visible()
    settings["available_models"] = ["fresh-model"]
    settings["directory_status"] = "已自动获取 1 个模型。"
    load(page, page="settings", settings=settings)
    assert page.get_by_role("status").filter(has_text="已自动获取 1 个模型").is_visible()
    assert page.get_by_text("fresh-model", exact=True).is_visible()
    assert page.get_by_text("cached-model", exact=True).count() == 0
