"""Public controller and production DOM progress projection."""
import pytest
from tests.test_conversation_workspace import app, install_session
from tests.test_final_delivery import confirmed_plan_session
from promptsmith.web_workspace import WorkspaceController
from tests.test_frontend_review_regressions import browser, page, load
from tests.test_ui_skill_search import _pump_until
from tests.test_network_skill_relevance import Http, Model
from promptsmith.skill_network_discovery import clear_network_skill_cache


def test_per_item_search_progress_is_inline_but_completion_and_failures_notify(app):
    install_session(app, confirmed_plan_session())
    view = WorkspaceController(app)
    for i in range(20):
        app.skill_status_var.set(f"正在联网搜索 Skill：已读取 Skill 信息：item-{i}")
    snap = view.snapshot()
    assert snap["notifications"] == []
    assert next(c for c in snap["cards"] if c["kind"] == "skills")["progress"].endswith("item-19")
    app.skill_status_var.set("联网搜索完成：收集20项，AI未发现适合当前任务的Skill。可以重试或跳过。")
    assert len(view.snapshot()["notifications"]) == 1
    app.skill_status_var.set("联网搜索失败：服务拒绝；请稍后重试。")
    assert view.snapshot()["notifications"][-1]["level"] == "error"


@pytest.mark.parametrize("outcome", ["low_scores", "empty_scores", "service_error"])
def test_scoring_outcome_explains_result_and_emits_only_final_summary(app, monkeypatch, outcome):
    session = confirmed_plan_session()
    session.skill_state["search_state"] = {"local": {"status": "no_match", "count": 0}}
    install_session(app, session)
    view = WorkspaceController(app)
    class EmptyReview(Model):
        def complete_json(self, prompt, payload, schema):
            if "queries" in schema.get("required", []):
                return super().complete_json(prompt, payload, schema)
            if outcome == "service_error":
                raise OSError("模拟筛选服务不可用")
            from types import SimpleNamespace
            if outcome == "low_scores":
                import json
                return SimpleNamespace(content=json.dumps({"matches": [
                    {"candidate_id": row["candidate_id"], "key_work_id": payload["key_works"][0]["key_work_id"],
                     "reason": "视频生成不能辅助当前任务。", "recommendation_score": .05}
                    for row in payload["skills"]]}))
            return SimpleNamespace(content='{"matches":[]}')
    clear_network_skill_cache()
    app.skill_search_opener = Http([("video", "Generate videos")])
    monkeypatch.setattr(app, "_client", lambda config: EmptyReview())
    app.search_online_skills()
    _pump_until(app.root, lambda: app.session.skill_state.get("search_state", {}).get("status") == "network_done")
    snapshot = view.snapshot()
    text = next(c for c in snapshot["cards"] if c["kind"] == "skills")["progress"]
    failed = outcome != "low_scores"
    assert ("AI 筛选暂不可用" if failed else "AI 未发现适合当前任务的匹配") in text and "跳过 Skill" in text
    if outcome == "empty_scores":
        assert "未返回任何有效的 Skill 评分" in text
        assert "AI 未发现适合当前任务的匹配" not in text
    feedback = [n for n in snapshot["notifications"] if n["key"] == "status:skill_status_var"]
    assert len(feedback) == 1 and feedback[0]["body"] == text
    network = app.session.skill_state["search_state"]["network"]
    assert network["ai_review_status"] == ("failed" if failed else "completed")
    if outcome == "low_scores":
        assert network["ai_review"]["scored_count"] == 1
        assert network["ai_review"]["low_score_rejected_count"] == 1
    clear_network_skill_cache()


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_progress_updates_preserve_table_nodes_and_open_details(page, theme):
    state = load(page, "skills", theme=theme)
    card = next(c for c in state["cards"] if c["kind"] == "skills")
    page.locator(".skill-table details").first.evaluate("e=>e.open=true")
    page.evaluate("window.originalSkillTable=document.querySelector('.skill-table')")
    for i in range(3):
        card["progress"] = f"正在联网搜索 Skill：读取第{i}项"
        page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    assert page.evaluate("originalSkillTable===document.querySelector('.skill-table')")
    assert page.locator(".skill-table details").first.evaluate("e=>e.open")
    assert page.get_by_role("status", name="Skill 搜索进度").inner_text() == card["progress"]
    assert page.locator(".notification-card").count() == 0
