"""Production DOM and desktop bridge contract for inline review and Stop."""
from tests.test_frontend_review_regressions import browser, page, load
import pytest


def test_review_table_and_actions_are_inline_and_keyboard_accessible(page):
    state = load(page, "requirements")
    state["buttons"]["edit_requirement"] = {"text": "修改选中需求", "enabled": True}
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    assert page.locator('[data-panel="requirements"]').count() == 0
    assert page.locator("#timeline .requirement-select").count() == len(state["requirement_rows"])
    select = page.locator("#timeline .requirement-select").first
    select.focus()
    page.keyboard.press("Enter")
    page.wait_for_function("calls.some(c=>c.action==='requirement_row')")
    assert page.locator("#timeline .detail").inner_text() == state["requirement_rows"][0]["text"]
    assert page.get_by_role("button", name="是这个意思", exact=True).count() == 0
    assert page.locator('#timeline [data-action="edit_requirement"]').count() == 1


def test_busy_composer_has_enabled_stop_even_with_empty_draft(page):
    state = load(page, "interview", locked=True)
    stop = page.get_by_role("button", name="停止生成", exact=True)
    assert stop.count() == 1 and stop.is_enabled()
    stop.click()
    page.wait_for_function("calls.some(c=>c.action==='stop')")
    call = page.evaluate("calls.find(c=>c.action==='stop')")
    assert call["data"]["session"] == state["session"]
    assert page.locator("#message").input_value() == ""
    load(page, "interview", locked=False)
    assert page.get_by_role("button", name="发送消息", exact=True).is_disabled()


def test_enter_while_busy_does_not_accidentally_stop_generation(page):
    load(page, "interview", locked=True)
    page.locator("#message").fill("下一条草稿")
    page.locator("#message").press("Enter")
    assert page.evaluate("calls.filter(c=>c.action==='stop'||c.action==='send').length") == 0
    assert page.locator("#message").input_value() == "下一条草稿"


def test_inline_selection_keeps_keyboard_focus_after_backend_snapshot(page):
    state = load(page, "requirements")
    selected = page.locator(".requirement-select").nth(1)
    selected.focus()
    state["requirement_selection"] = [state["requirement_rows"][1]["id"]]
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    assert page.locator(".requirement-select").nth(1).evaluate("e=>e===document.activeElement")
    assert page.locator("#timeline .detail").inner_text() == state["requirement_rows"][1]["text"]


def test_stop_bypasses_a_pending_command_and_draft_flush(page):
    state = load(page, "requirements")
    page.evaluate("""() => {
      pywebview.api.dispatch = (action,data) => {
        calls.push({action,data});
        if(action==='requirement_row')return new Promise(resolve=>window.releaseAction=resolve);
        return Promise.resolve({ok:true});
      };
    }""")
    page.locator('.requirement-select').first.click()
    page.wait_for_function("document.body.classList.contains('pending')")
    state.update(locked=True, stop_scope="current-scope")
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    page.evaluate("() => {promptsmithHistory.flushDrafts=()=>new Promise(()=>{});}")
    page.get_by_role('button', name='停止生成', exact=True).click(timeout=1000)
    page.wait_for_function("calls.some(c=>c.action==='stop')")
    assert page.evaluate("calls.find(c=>c.action==='stop').data.scope") == "current-scope"
    page.evaluate("releaseAction({ok:true})")


@pytest.mark.parametrize('theme', ['light', 'dark'])
@pytest.mark.parametrize('size', [(1440, 810), (720, 440)])
def test_continue_answers_sits_above_composer_on_the_right(page, theme, size):
    page.set_viewport_size({'width': size[0], 'height': size[1]})
    state = load(page, 'interview', theme=theme)
    state['cards'] = [card for card in state['cards'] if card['kind'] != 'question']
    state['buttons']['primary'] = {'text': '继续整理回答', 'enabled': True}
    page.evaluate('s=>promptsmithView.applySnapshot(s)', state)
    action = page.get_by_role('button', name='继续整理回答', exact=True)
    action_box, composer = action.bounding_box(), page.locator('#composer').bounding_box()
    assert action_box['y'] + action_box['height'] <= composer['y']
    assert abs(action_box['x'] + action_box['width'] - composer['x'] - composer['width']) < 2
    assert page.locator('#recovery').get_by_role('button', name='继续整理回答').count() == 0
    action.click()
    page.wait_for_function("calls.some(c=>c.action==='button'&&c.data.key==='primary')")


@pytest.mark.parametrize('status', ['working', 'done', 'failed', 'cancelled'])
def test_reasoning_starts_folded_and_snapshots_preserve_user_toggle(page, status):
    state = load(page, 'interview')
    state['session'] = 'folded-' + status
    record = next(c['trace'] for c in state['cards'] if c['kind'] == 'trace')
    record.update(status=status, reasoning='新返回的思考内容')
    page.evaluate('s=>promptsmithView.applySnapshot(s)', state)
    header = page.locator('.trace>button')
    assert header.get_attribute('aria-expanded') == 'false'
    assert page.locator('.trace>.reveal').evaluate('e=>e.inert')
    header.click()
    assert header.get_attribute('aria-expanded') == 'true'
    record['reasoning'] += '，后续分片'
    page.evaluate('s=>promptsmithView.applySnapshot(s)', state)
    assert header.get_attribute('aria-expanded') == 'true'
    header.click()
    page.evaluate('s=>promptsmithView.applySnapshot(s)', state)
    assert header.get_attribute('aria-expanded') == 'false'


@pytest.mark.parametrize('previous_status', ['working', 'done'])
def test_stop_freezes_visible_reasoning_including_completed_transport_backlog(page, previous_status):
    page.clock.install(time=0)
    page.clock.pause_at(0)
    state = load(page, 'interview')
    state['session'] = 'cancel-animation-' + previous_status
    record = next(c['trace'] for c in state['cards'] if c['kind'] == 'trace')
    reasoning = '汉字👩🏽‍💻é𠮷\n' * 4000
    record.update(status=previous_status, reasoning=reasoning)
    page.evaluate('s=>promptsmithView.applySnapshot(s)', state)
    page.clock.run_for(32)
    visible = page.locator('.thought').text_content()
    assert visible and visible != reasoning
    record.update(status='cancelled', reasoning=reasoning + '迟到分片', elapsed=8.3)
    page.evaluate('s=>promptsmithView.applySnapshot(s)', state)
    assert page.locator('.thought').text_content() == visible
    page.clock.run_for(3000)
    page.evaluate('s=>promptsmithView.applySnapshot(s)', state)
    page.clock.run_for(3000)
    assert page.locator('.thought').text_content() == visible
    assert '已取消' in page.locator('.trace>button').inner_text()


def test_restored_cancelled_reasoning_is_static_and_readable_without_animation(page):
    page.clock.install(time=0)
    page.clock.pause_at(0)
    state = load(page, 'interview')
    state['session'] = 'restore-cancelled-animation'
    record = next(c['trace'] for c in state['cards'] if c['kind'] == 'trace')
    reasoning = '已保存的思考👩🏽‍💻é𠮷\n' * 1000
    record.update(status='cancelled', reasoning=reasoning)
    page.evaluate('s=>promptsmithView.applySnapshot(s)', state)
    assert page.locator('.thought').text_content() == reasoning
    page.clock.run_for(2000)
    assert page.locator('.thought').text_content() == reasoning
