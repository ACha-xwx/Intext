"""Online scoring through the public search and disposable HTTP/model boundaries."""
import json
from types import SimpleNamespace

import pytest
from playwright.sync_api import expect

from promptsmith.skill_network_discovery import clear_network_skill_cache, search_network_skill_candidates
from promptsmith.storage import load_session, save_session
from promptsmith.web_workspace import WorkspaceController, view_stamp
from promptsmith.runtime_log import RuntimeLog
from promptsmith.web_debug import DebugApi, WebDebugConsole
from tests.test_conversation_workspace import app, install_session
from tests.test_debug_log_view import DesktopApi
from tests.test_final_delivery import confirmed_plan_session
from tests.test_frontend_review_regressions import browser, page, load
from tests.test_network_skill_relevance import Http, TASK, WORKS
from tests.test_ui_skill_search import _pump_until


@pytest.fixture(autouse=True)
def isolated_cache():
    clear_network_skill_cache()
    yield
    clear_network_skill_cache()


class SummaryModel:
    def __init__(self, *, wrapped=False, malformed_row=False, string_score=False, work_id="docs"):
        self.wrapped = wrapped
        self.malformed_row = malformed_row
        self.string_score = string_score
        self.work_id = work_id
        self.reviews = []

    def complete_json(self, prompt, payload, schema):
        if "queries" in schema["required"]:
            return SimpleNamespace(content='{"queries":["technical documentation","pdf"]}')
        self.reviews.append((prompt, payload))
        if "candidate_ids" in schema["required"]:
            return SimpleNamespace(content=json.dumps({"candidate_ids": [r["candidate_id"] for r in payload["skills"]]}))
        matches = [{"candidate_id": r["candidate_id"], "key_work_id": self.work_id,
                    "reason": "简介明确覆盖技术文档组织和准确性核对。",
                    "usage_suggestion": "根据项目资料编写评委可读的技术报告，并逐项核对描述。",
                    "recommendation_score": "0.93" if self.string_score else .93}
                   for r in payload["skills"]]
        if self.malformed_row:
            matches.insert(0, {"candidate_id": "not-in-search", "key_work_id": "docs", "reason": "错误引用", "recommendation_score": .99})
        text = json.dumps({"matches": matches}, ensure_ascii=False)
        return SimpleNamespace(content="```json\n" + text + "\n```" if self.wrapped else text)


@pytest.mark.parametrize("count", [1, 10])
def test_network_recommends_from_introductions_in_one_scoring_pass(count):
    model = SummaryModel()
    descriptions = [(f"technical-docs-{i}", "Write technical documentation and verify report accuracy") for i in range(count)]
    result = search_network_skill_candidates(WORKS, task_text=TASK, client=model, opener=Http(descriptions),
                                             max_verified_candidates=12)
    assert result.diagnostics["ai_review_status"] == "completed"
    assert len(model.reviews) == 1
    prompt, payload = model.reviews[0]
    assert len(payload["skills"]) == count
    assert all(r["description"] == descriptions[0][1] for r in payload["skills"])
    assert all("source" not in r for r in payload["skills"])
    assert all(r["evidence"]["evidence_level"] == "skill_summary" for r in payload["skills"])
    assert "0" in prompt and "1" in prompt
    assert result.candidates and len(result.candidates) <= 8
    assert all(r["recommendation_score"] == .93 for r in result.candidates)
    assert all("逐项核对" in r["usage_suggestion"] for r in result.candidates)
    assert all(r["ai_review_status"] == "completed" for r in result.candidates)


def test_fenced_model_json_does_not_turn_successful_scores_into_a_coarse_fallback():
    model = SummaryModel(wrapped=True)
    result = search_network_skill_candidates(WORKS, task_text=TASK, client=model,
                                             opener=Http([("technical-docs", "Write accurate technical documentation")]))
    assert result.diagnostics["ai_review_status"] == "completed"
    assert result.candidates[0]["recommendation_score"] == .93
    assert "AI" in result.candidates[0]["recommendation_basis"]
    assert len(model.reviews) == 1


@pytest.mark.parametrize("options", [{"string_score": True}, {"malformed_row": True}])
def test_usable_model_scores_survive_numeric_strings_or_an_invalid_extra_row(options):
    model = SummaryModel(**options)
    result = search_network_skill_candidates(WORKS, task_text=TASK, client=model,
                                             opener=Http([("technical-docs", "Write accurate technical documentation")]))
    assert result.diagnostics["ai_review_status"] == "completed"
    assert len(result.candidates) == 1
    assert result.candidates[0]["recommendation_score"] == .93
    assert result.candidates[0]["ai_review_status"] == "completed"
    if options.get("malformed_row"):
        assert result.diagnostics["ai_review"]["invalid_match_count"] == 1
    assert len(model.reviews) == 1


def test_ai_score_orders_recommendations_and_excludes_low_scores():
    class ScoredModel(SummaryModel):
        def complete_json(self, prompt, payload, schema):
            if "queries" in schema["required"]:
                return super().complete_json(prompt, payload, schema)
            scores = {"pdf": .96, "technical-docs": .81, "video": .05}
            return SimpleNamespace(content=json.dumps({"matches": [
                {"candidate_id": r["candidate_id"], "key_work_id": "pdf" if r["name"] == "pdf" else "docs",
                 "reason": "按简介评估对应工作", "recommendation_score": scores[r["name"]]}
                for r in payload["skills"]]}))
    result = search_network_skill_candidates(WORKS, task_text=TASK, client=ScoredModel(),
        opener=Http([("technical-docs", "Write technical documentation"), ("pdf", "Create and inspect PDF documents"),
                     ("video", "Generate video clips")]))
    assert [(r["name"], r["recommendation_score"]) for r in result.candidates] == [("pdf", .96), ("technical-docs", .81)]
    assert result.diagnostics["ai_review"]["scored_count"] == 3
    assert result.diagnostics["ai_review"]["low_score_rejected_count"] == 1


def test_known_skill_introduction_is_scored_when_the_source_body_is_forbidden():
    from urllib.error import HTTPError
    http = Http([("technical-docs", "Write accurate technical documentation")])
    def opener(request, timeout=None):
        if request.full_url.endswith("SKILL.md"):
            raise HTTPError(request.full_url, 403, "Forbidden", {}, None)
        return http(request, timeout)
    model = SummaryModel()
    result = search_network_skill_candidates(WORKS, task_text=TASK, client=model, opener=opener)
    assert result.diagnostics["ai_review_status"] == "completed"
    assert result.candidates[0]["recommendation_score"] == .93
    assert result.candidates[0]["evidence_level"] == "skill_summary"
    assert "未阅读全文" in result.candidates[0]["ai_evidence_note"]


def test_missing_all_model_scores_remains_a_visible_unreviewed_failure():
    class NoScores(SummaryModel):
        def complete_json(self, prompt, payload, schema):
            result = super().complete_json(prompt, payload, schema)
            if "matches" in schema["required"]:
                answer = json.loads(result.content)
                for row in answer["matches"]:
                    row.pop("recommendation_score")
                result.content = json.dumps(answer)
            return result
    result = search_network_skill_candidates(WORKS, task_text=TASK, client=NoScores(),
        opener=Http([("technical-docs", "Write accurate technical documentation")]))
    assert result.diagnostics["ai_review_status"] == "failed"
    assert "缺少推荐评分" in result.diagnostics["ai_review_error"]
    assert all(r["ai_review_status"] == "unavailable" for r in result.candidates)
    assert all("AI 尚未核验" in r["recommendation_basis"] for r in result.candidates)


def test_empty_scores_do_not_claim_ai_found_no_match():
    class EmptyScores(SummaryModel):
        def complete_json(self, prompt, payload, schema):
            if "queries" in schema["required"]:
                return super().complete_json(prompt, payload, schema)
            self.reviews.append((prompt, payload))
            return SimpleNamespace(content='{"matches":[]}')
    model = EmptyScores()
    result = search_network_skill_candidates(WORKS, task_text=TASK, client=model,
        opener=Http([("technical-docs", "Write accurate technical documentation")]))
    assert result.diagnostics["ai_review_status"] == "failed"
    assert "未返回" in result.diagnostics["ai_review_error"]
    assert result.diagnostics["ai_review"]["scored_count"] == 0
    assert result.diagnostics["ai_review"]["unscored_count"] == 1
    assert all(r["ai_review_status"] == "unavailable" for r in result.candidates)
    assert len(model.reviews) == 1


@pytest.mark.parametrize("late_error", [False, True])
def test_cancel_during_summary_scoring_never_becomes_a_coarse_fallback(late_error, caplog):
    from concurrent.futures import CancelledError
    from promptsmith.task_scope import TaskScope
    scope = TaskScope()
    class CancelledModel(SummaryModel):
        def complete_json(self, prompt, payload, schema):
            response = super().complete_json(prompt, payload, schema)
            if "matches" in schema["required"]:
                scope.cancel()
                if late_error:
                    raise OSError("取消后的迟到网络错误")
            return response
    model = CancelledModel()
    with scope.activate(), pytest.raises(CancelledError):
        search_network_skill_candidates(WORKS, task_text=TASK, client=model,
            opener=Http([("technical-docs", "Write accurate technical documentation")]))
    assert len(model.reviews) == 1
    assert "Network Skill AI review unavailable" not in caplog.text


def test_desktop_stop_during_scoring_discards_late_recommendations(app, monkeypatch, caplog):
    from copy import deepcopy
    from threading import Event
    session = confirmed_plan_session()
    session.skill_state["search_state"] = {"local": {"status": "no_match", "count": 0}}
    install_session(app, session)
    entered, release = Event(), Event()
    class WaitingModel(SummaryModel):
        def complete_json(self, prompt, payload, schema):
            response = super().complete_json(prompt, payload, schema)
            if "matches" in schema["required"]:
                entered.set()
                assert release.wait(6)
            return response
    model = WaitingModel(work_id=session.plan["content"]["key_work"][0]["key_work_id"])
    app.skill_search_opener = Http([("technical-docs", "Write accurate technical documentation")])
    monkeypatch.setattr(app, "_client", lambda config: model)
    controller = WorkspaceController(app)
    before = deepcopy(session.skill_state.get("candidate_batch"))
    try:
        controller.dispatch("button", {"key": "find_online"}, view_stamp(app))
        assert entered.wait(3)
        snapshot = controller.snapshot()
        assert snapshot["locked"]
        controller.dispatch("stop", {"session": snapshot["session"], "scope": snapshot["stop_scope"]}, view_stamp(app))
        snapshot = controller.snapshot()
        assert not snapshot["locked"]
        assert snapshot["buttons"]["find_online"]["enabled"]
    finally:
        release.set()
    _pump_until(app.root, lambda: not app._background_futures)
    app.root.update()
    assert session.skill_state.get("candidate_batch") == before
    assert session.skill_state["search_state"]["status"] == "cancelled"
    assert not session.pending_requests
    assert len(model.reviews) == 1
    assert "Network Skill AI review unavailable" not in caplog.text


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_search_score_use_generate_and_reopen_through_desktop_and_dom(app, page, monkeypatch, tmp_path, theme):
    session = confirmed_plan_session()
    session.skill_state["search_state"] = {"local": {"status": "no_match", "count": 0}}
    install_session(app, session)
    model = SummaryModel(work_id=session.plan["content"]["key_work"][0]["key_work_id"])
    app.skill_search_opener = Http([("technical-docs", "Write accurate technical documentation")])
    monkeypatch.setattr(app, "_client", lambda config: model)
    controller = WorkspaceController(app)
    controller.install_native_bridge()
    load(page, "skills", theme=theme)
    controller.dispatch("button", {"key": "find_online"}, view_stamp(app))
    _pump_until(app.root, lambda: app.session.skill_state.get("search_state", {}).get("status") == "network_done")
    snapshot = controller.snapshot()
    snapshot["theme"] = theme
    card = next(c for c in snapshot["cards"] if c["kind"] == "skills")
    assert "按 Skill 简介评分" in card["progress"] and "AI 筛选暂不可用" not in card["progress"]
    assert len(card["rows"]) == 1 and card["rows"][0]["score"] == .93
    assert "技术文档组织" in card["rows"][0]["details"] and "逐项核对" in card["rows"][0]["details"]
    assert "AI 简介评分" in card["rows"][0]["details"]
    page.evaluate("s=>promptsmithView.applySnapshot(s)", snapshot)
    table = page.locator(".skill-table")
    table.locator("details").first.evaluate("e=>e.open=true")
    expect(table).to_contain_text("0.93")
    expect(table).to_contain_text("技术文档组织")
    controller.dispatch("select_skill", {"id": card["rows"][0]["id"]}, view_stamp(app))
    assert session.skill_state["bindings"]
    controller.dispatch("button", {"key": "direct_skills"}, view_stamp(app))
    assert session.final_result["status"] == "draft"
    snapshot = controller.snapshot()
    snapshot["theme"] = theme
    page.evaluate("s=>promptsmithView.applySnapshot(s)", snapshot)
    expect(page.locator(".skill-table")).to_have_count(0)
    assert page.locator("#timeline > .message").last.locator(".stage-actions button").all_text_contents() == ["复制提示词", "导出方案和提示词", "附注"]
    restored = load_session(save_session(session, tmp_path / "scored.json"))
    assert restored.final_result["canonical_body"] == session.final_result["canonical_body"]
    assert restored.skill_state["bindings"] == session.skill_state["bindings"]
    assert len(model.reviews) == 1


def test_scoring_debug_is_concise_and_manual_archive_keeps_diagnostics(tmp_path):
    import logging
    logs = RuntimeLog(tmp_path / "logs")
    api = DebugApi(WebDebugConsole(logs, DesktopApi()))
    started = "AI Skill scoring started: mode=summary candidates=3 input_chars=1900"
    done = "AI Skill selection completed: shortlisted=3 reviewed=3 selected=2 calls=1 input_chars=1900 low_score_rejected=1 mode=summary"
    logs.record("promptsmith.skill_ai_selection", logging.INFO, started)
    logs.record("promptsmith.skill_ai_selection", logging.INFO, done)
    entries = api.snapshot()["entries"]
    assert entries[0]["message"] == "AI 正在按简介评分：3 项 Skill"
    assert entries[1]["message"] == "Skill 简介评分完成：处理 3 项，推荐 2 项，低分排除 1 项"
    assert not logs.directory.exists()
    saved = logs.save().read_text(encoding="utf-8")
    assert started in saved and done in saved
