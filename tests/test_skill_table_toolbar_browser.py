"""The Skill table owns its filters; execution deferred for the combined batch."""
import pytest
from playwright.sync_api import expect
from tests.test_frontend_review_regressions import browser, page, load


@pytest.mark.parametrize("theme,width", [("light", 1440), ("dark", 720)])
def test_filters_belong_to_table_and_keep_their_existing_actions(page, theme, width):
    page.set_viewport_size({"width": width, "height": 810})
    load(page, "skills", theme=theme)
    table = page.locator(".skill-table")
    toolbar = table.get_by_role("toolbar", name="Skill 表格筛选")
    assert toolbar.get_by_role("button", name="全部来源", exact=True).get_attribute("aria-pressed") == "true"
    assert table.locator("table").count() == 1
    assert table.get_by_role("button", name="查找本地 Skill").count() == 0
    toolbar.get_by_role("button", name="本地", exact=True).click()
    page.wait_for_function("calls.some(c=>c.action==='source'&&c.data.value==='本地')")
    toolbar.get_by_role("button", name="显示全部", exact=True).click()
    page.wait_for_function("calls.some(c=>c.action==='show_all')")
    assert all(button.bounding_box()["x"] + button.bounding_box()["width"] <= width for button in toolbar.get_by_role("button").all())


def test_filter_buttons_unlock_after_snapshot_rebuild_during_command(page):
    state = load(page, "skills")
    page.evaluate("""()=>{const original=pywebview.api.dispatch;pywebview.api.dispatch=(action,data)=>{
      if(action!=='source')return original(action,data);
      calls.push({action,data});return new Promise(resolve=>window.finishFilter=resolve);
    };}""")
    page.get_by_role("button", name="本地", exact=True).click()
    page.wait_for_function("Boolean(window.finishFilter)")
    state["source"] = "本地"
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    toolbar = page.get_by_role("toolbar", name="Skill 表格筛选")
    expect(toolbar.get_by_role("button", name="本地", exact=True)).to_be_disabled()
    page.evaluate("finishFilter({ok:true})")
    expect(toolbar.get_by_role("button", name="本地", exact=True)).to_be_enabled()
    expect(toolbar.get_by_role("button", name="本地", exact=True)).to_have_attribute("aria-pressed", "true")
