"""Production DOM batch actions; execution deferred until the remaining fixes."""
import pytest

from tests.test_frontend_review_regressions import browser, page, load


def pending_questions(page):
    state = load(page)
    state["cards"] = [{"key": f"question:q{i}", "kind": "question", "question": {
        "question_id": f"q{i}", "text": f"问题{i}？",
    }} for i in range(1, 4)]
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    return state


@pytest.mark.parametrize("trigger", ["enter", "button"])
def test_any_question_submits_all_filled_answers_and_leaves_blank(page, trigger):
    pending_questions(page)
    inputs = page.locator(".answer-input")
    inputs.nth(0).fill("给评委看")
    inputs.nth(2).fill("中文👩‍💻")
    if trigger == "enter":
        inputs.nth(1).press("Enter")
    else:
        page.get_by_role("button", name="提交本轮已填写的回答").nth(1).click()
    page.wait_for_function("calls.some(c=>c.action==='answer')")
    answers = page.evaluate("calls.filter(c=>c.action==='answer')")
    assert len(answers) == 1
    assert answers[0]["data"] == {"answers": [{"id": "q1", "text": "给评委看"}, {"id": "q3", "text": "中文👩‍💻"}]}


def test_shift_enter_and_ime_do_not_submit(page):
    pending_questions(page)
    field = page.locator(".answer-input").first
    field.fill("第一行")
    field.press("Shift+Enter")
    assert field.input_value() == "第一行\n"
    field.dispatch_event("keydown", {"key": "Enter", "isComposing": True, "keyCode": 229})
    assert not page.evaluate("calls.some(c=>c.action==='answer')")


def test_batch_failure_keeps_every_draft_and_allows_retry(page):
    pending_questions(page)
    page.evaluate("pywebview.api.dispatch=async(action,data)=>{calls.push({action,data});return action==='answer'?{ok:false,error:'模拟记录失败'}:{ok:true};}")
    page.locator(".answer-input").nth(0).fill("第一题草稿")
    page.locator(".answer-input").nth(2).fill("第三题草稿")
    page.locator(".answer-input").nth(0).press("Enter")
    page.wait_for_function("document.querySelector('.notification-card')")
    assert page.locator(".answer-input").nth(0).input_value() == "第一题草稿"
    assert page.locator(".answer-input").nth(2).input_value() == "第三题草稿"
    assert page.get_by_role("button", name="提交本轮已填写的回答").nth(1).is_enabled()


def test_empty_or_busy_batch_does_not_send(page):
    state = pending_questions(page)
    page.locator(".answer-input").first.press("Enter")
    assert not page.evaluate("calls.some(c=>c.action==='answer')")
    assert all(button.is_disabled() for button in page.get_by_role("button", name="提交本轮已填写的回答").all())
    page.locator(".answer-input").first.fill("暂存")
    state["locked"] = True
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    assert page.locator(".answer-input").first.is_disabled()
    assert not page.evaluate("calls.some(c=>c.action==='answer')")


def test_double_enter_sends_once_and_freezes_drafts_until_completion(page):
    pending_questions(page)
    page.evaluate("""()=>{
      const original=pywebview.api.dispatch;
      pywebview.api.dispatch=async(action,data)=>{
        if(action!=='answer')return original(action,data);
        calls.push({action,data});return new Promise(resolve=>window.completeBatch=()=>resolve({ok:true,data:{submitted:['q1']}}));
      };
    }""")
    field = page.locator(".answer-input").first
    field.fill("一次提交")
    field.evaluate("e=>{e.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));e.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));}")
    page.wait_for_function("Boolean(window.completeBatch)")
    assert field.is_disabled()
    assert len(page.evaluate("calls.filter(c=>c.action==='answer')")) == 1
    page.evaluate("completeBatch()")
    page.wait_for_function("!document.body.classList.contains('pending')")
