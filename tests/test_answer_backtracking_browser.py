"""Production inputs restore within a session without losing Unicode drafts."""
from copy import deepcopy
from tests.test_frontend_review_regressions import browser, page
from tests.test_batch_answers_browser import pending_questions


def test_round_restore_replaces_stale_live_inputs_and_focuses_first_answer(page):
    state = pending_questions(page)
    page.locator(".answer-input").first.fill("旧缓存")
    state["drafts"] = {"answer_restore_id": "round-restored-1", "answers": {"q1": "给评委👩‍💻", "q2": "中文", "q3": "PDF"}}
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    page.wait_for_timeout(60)
    assert [i.input_value() for i in page.locator(".answer-input").all()] == ["给评委👩‍💻", "中文", "PDF"]
    assert page.locator(".answer-input").first.evaluate("e=>e===document.activeElement")
    page.locator(".answer-input").first.fill("新修改")
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    assert page.locator(".answer-input").first.input_value() == "新修改"
    page.locator(".answer-input").first.press("Enter")
    page.wait_for_function("calls.some(c=>c.action==='answer')")
    assert next(c for c in page.evaluate("calls") if c["action"] == "answer")["data"]["answers"] == [
        {"id": "q1", "text": "新修改"}, {"id": "q2", "text": "中文"}, {"id": "q3", "text": "PDF"}]


def test_back_captures_latest_input_without_waiting_for_draft_flush(page):
    state = pending_questions(page)
    nav = dict(stage="interview", natural="interview", previous="interview", next=None, revisiting=False)
    state["navigation"] = nav
    state["cards"].insert(0, dict(kind="navigation", key="navigation", title="回看与继续", **nav))
    state["buttons"]["back_stage"] = dict(text="返回上一步", enabled=True)
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    page.evaluate("()=>{promptsmithHistory.flushDrafts=()=>new Promise(()=>{});}")
    page.locator(".answer-input").nth(1).fill("刚输入的第二题")
    page.get_by_role("button", name="返回上一步", exact=True).click()
    page.wait_for_function("calls.some(c=>c.action==='navigate')")
    data = next(c["data"] for c in page.evaluate("calls") if c["action"] == "navigate")
    assert data["answer_drafts"] == {"q1": "", "q2": "刚输入的第二题", "q3": ""}
