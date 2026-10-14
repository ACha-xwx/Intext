"""User-facing back navigation restores the last round as unsubmitted inputs."""
from copy import deepcopy
import pytest
from promptsmith.session import SessionStateError
from promptsmith.conversation import conversation_cards
from tests.test_batch_answers import pending_session
from promptsmith.storage import load_session, save_session
from tests.test_final_delivery import confirmed_plan_session
from tests.test_conversation_workspace import app, install_session
from promptsmith.web_workspace import WorkspaceController, view_stamp


def test_back_after_submitting_a_round_restores_all_answers_as_unsubmitted():
    session = pending_session()
    answers = [{"question_id": f"q{i}", "text": f"完整回答{i} 👩‍💻"} for i in range(1, 4)]
    session.record_question_answers(answers)
    assert not session.questions_for_review()

    assert session.workspace_navigation()["previous"]
    session.navigate_workspace("previous")

    assert [q["question_id"] for q in session.questions_for_review()] == ["q1", "q2", "q3"]
    assert session.control["workspace_drafts"]["answers"] == {r["question_id"]: r["text"] for r in answers}
    assert not session.question_history
    assert len([c for c in conversation_cards(session) if c["kind"] == "question"]) == 3
    assert not any(c["kind"] in {"requirements", "plan", "skills", "result"} for c in conversation_cards(session))


def test_busy_back_cancels_request_restores_inputs_and_ignores_late_result(app, monkeypatch):
    from threading import Event
    from promptsmith.api import ApiResult
    from tests.test_ui_session_cancellation import _wait, _drain_completions
    session = pending_session()
    install_session(app, session)
    entered, release = Event(), Event()
    calls = []
    class Client:
        def complete_json(self, *_args):
            calls.append(True)
            entered.set()
            assert release.wait(5)
            return ApiResult("{", 1, None, "late", "fixture")
    monkeypatch.setattr(app, "_client", lambda _config: Client())
    controller = WorkspaceController(app)
    try:
        controller.dispatch("answer", {"answers": [{"id": f"q{i}", "text": f"恢复回答{i}"} for i in range(1, 4)]}, view_stamp(app))
        assert entered.wait(2)
        old_scope = app._session_tasks
        snapshot = controller.snapshot()
        controller.dispatch("navigate", {"direction": "previous", "stage": snapshot["navigation"]["stage"], "session": snapshot["session"], "scope": snapshot["stop_scope"]}, snapshot["stamp"])
        assert not controller.snapshot()["locked"]
        assert [app._question_inputs[f"q{i}"].get("1.0", "end-1c") for i in range(1, 4)] == [f"恢复回答{i}" for i in range(1, 4)]
        assert len([c for c in controller.snapshot()["cards"] if c["kind"] == "question"]) == 3
        release.set()
        _wait(lambda: not any(owner is old_scope for owner in app._background_futures.values()), app.root)
        _drain_completions(app)
        assert not session.pending_requests and not session.errors and not session.question_history
        controller.dispatch("answer", {"answers": [{"id": f"q{i}", "text": f"恢复回答{i}"} for i in range(1, 4)]}, view_stamp(app))
        _wait(lambda: len(calls) == 2, app.root)
        assert len(session.question_history) == 3
    finally:
        release.set()


def test_legacy_session_recovers_last_answer_group_without_adopting_unsubmitted_facts():
    session = pending_session()
    session.record_question_answers([{"question_id": "q1", "text": "评委"}, {"question_id": "q2", "text": "中文"}, {"question_id": "q3", "text": "PDF"}])
    source = session.question_history[-1]["answer_source_id"]
    session.requirements = [{"item_id": "r1", "field": "deliverable", "text": "PDF", "source_refs": [{"source_id": source, "quote": "PDF"}], "depends_on": [], "confirmation": "confirmed"}]
    session.last_next_action = "review_requirements"
    for row in session.question_history:
        row["assessment_status"] = "applied"
    session.analysis_basis_version = session.requirement_version
    session.control.pop("answer_round_checkpoint")
    session.navigate_workspace("previous")
    assert len(session.questions_for_review()) == 3
    assert not session.question_history
    assert session.control["workspace_drafts"]["answers"]["q3"] == "PDF"
    assert not session.requirements and session.analysis_basis_version is None
    assert source not in {s["source_id"] for s in session.sources}


def test_back_during_plan_generation_returns_to_last_answers_but_completed_plan_returns_to_requirements():
    session = pending_session()
    session.record_question_answers([{"question_id": "q1", "text": "评委"}, {"question_id": "q2", "text": "中文"}, {"question_id": "q3", "text": "PDF"}])
    confirmed = confirmed_plan_session()
    session.requirements = confirmed.requirements
    session.confirmed_requirements_version = session.requirement_version
    assert session.workspace_navigation()["stage"] == "plan"
    assert session.workspace_navigation()["previous"] == "interview"
    session.plan = confirmed.plan
    assert session.workspace_navigation()["stage"] == "skills"
    session.navigate_workspace("previous")
    assert session.workspace_navigation()["stage"] == "plan"
    session.navigate_workspace("previous")
    assert session.workspace_navigation()["stage"] == "requirements"


def test_restored_round_survives_save_and_hides_its_generation(tmp_path):
    session = pending_session()
    session.control["response_traces"] = [{"id": "initial", "history_count": 0}]
    session.record_question_answers([{"question_id": "q1", "text": "评委"}])
    session.record_question_answers([{"question_id": "q2", "text": "中文"}, {"question_id": "q3", "text": "PDF"}])
    session.control["response_traces"].append({"id": "after-answers", "history_count": 3})
    session = load_session(save_session(session, tmp_path / "round.json"))
    session.navigate_workspace("previous")
    session = load_session(save_session(session, tmp_path / "restored.json"))
    assert session.control["workspace_drafts"]["answers"] == {"q1": "评委", "q2": "中文", "q3": "PDF"}
    assert [c["trace"]["id"] for c in conversation_cards(session) if c["kind"] == "trace"] == ["initial"]
    assert len(session.control["response_traces"]) == 2  # diagnostic evidence retained
    session.record_question_answers([{"question_id": key, "text": text} for key, text in session.control["workspace_drafts"]["answers"].items()])
    assert len(session.question_history) == 3
    assert session.workspace_navigation()["previous"] == "interview"
    session.navigate_workspace("previous")
    assert not session.question_history


def test_late_draft_before_back_cannot_clear_restored_answers(app, tmp_path):
    from tests.test_history_workspace import enabled
    session = pending_session()
    session.record_question_answers([{"question_id": "q1", "text": "给评委"}])
    install_session(app, session)
    controller, history = enabled(app, tmp_path)
    try:
        old = controller.snapshot()
        controller.dispatch("button", {"key": "back_stage"}, old["stamp"])
        restored = controller.snapshot()
        controller.dispatch("drafts", {"session": old["session"], "sequence": 100, "answers": {}, "message": "", "scroll": 0}, old["stamp"])
        assert controller.snapshot()["drafts"]["answers"] == {"q1": "给评委", "q2": "", "q3": ""}
        generation = restored["drafts"]["answer_restore_id"]
        controller.dispatch("drafts", {"session": restored["session"], "answer_restore_id": generation, "sequence": 101, "answers": {"q1": "改过的回答"}, "message": "", "scroll": 0}, restored["stamp"])
        assert controller.snapshot()["drafts"]["answers"] == {"q1": "改过的回答"}
        assert controller.snapshot()["drafts"]["answer_restore_id"] == generation
    finally:
        history.close()


def test_returned_confirmed_plan_has_both_actions_and_no_separate_review_gate(app, monkeypatch):
    session = confirmed_plan_session()
    session.plan["pending_key_work_review_ids"] = [session.plan["content"]["key_work"][0]["key_work_id"]]
    install_session(app, session)
    controller = WorkspaceController(app)
    controller.dispatch("button", {"key": "back_stage"}, view_stamp(app))
    snapshot = controller.snapshot()
    assert {"confirm_plan", "find_skills"} <= snapshot["buttons"].keys()
    assert "review_plan" not in snapshot["buttons"]
    assert not any(c["kind"] == "skills" for c in snapshot["cards"])
    captured = []
    monkeypatch.setattr(app, "_submit", lambda *args: captured.append(args))
    controller.dispatch("button", {"key": "find_skills"}, snapshot["stamp"])
    assert captured and app._skill_search_busy
    assert session.workspace_navigation()["stage"] == "skills"


def test_continue_from_returned_plan_restarts_cancelled_search(app, monkeypatch):
    session = confirmed_plan_session()
    session.skill_state["search_state"] = {"status": "cancelled", "local": {"status": "cancelled", "count": 0}}
    install_session(app, session)
    controller = WorkspaceController(app)
    controller.dispatch("button", {"key": "back_stage"}, view_stamp(app))
    captured = []
    monkeypatch.setattr(app, "_submit", lambda *args: captured.append(args))
    controller.dispatch("button", {"key": "continue_stage"}, view_stamp(app))
    assert app._skill_search_busy and captured
    assert session.workspace_navigation()["stage"] == "skills"


def test_choose_skills_after_direct_delivery_opens_new_search_instead_of_old_result(app, monkeypatch):
    from promptsmith.finalization import build_final_draft
    session = confirmed_plan_session()
    session.skill_state["status"] = "skipped"
    session.final_result = build_final_draft(session)
    install_session(app, session)
    controller = WorkspaceController(app)
    controller.dispatch("button", {"key": "back_stage"}, view_stamp(app))
    assert session.workspace_navigation()["stage"] == "plan"
    monkeypatch.setattr(app, "_submit", lambda *args: None)
    controller.dispatch("button", {"key": "find_skills"}, view_stamp(app))
    assert session.workspace_navigation()["stage"] == "skills"
    assert any(c["kind"] == "skills" for c in controller.snapshot()["cards"])
    assert not any(c["kind"] == "result" for c in controller.snapshot()["cards"])


@pytest.mark.parametrize("corruption", ["answers", "trace_ids", "runtime_key", "invalid_version"])
def test_invalid_checkpoint_cannot_partially_restore_or_override_runtime_state(corruption):
    session = pending_session()
    session.record_question_answers([{"question_id": "q1", "text": "评委"}])
    checkpoint = session.control["answer_round_checkpoint"]
    if corruption in {"answers", "trace_ids"}:
        checkpoint.pop(corruption)
    elif corruption == "runtime_key":
        checkpoint["state"]["runtime_api_key"] = "unexpected-key"
    else:
        checkpoint["state"]["requirement_version"] = "broken"
    before = deepcopy(session.__dict__)
    with pytest.raises(SessionStateError):
        session.navigate_workspace("previous")
    assert session.__dict__ == before


def test_legacy_partial_submissions_restore_entire_last_round_and_valid_gap_references():
    session = pending_session()
    session.control["response_traces"] = [{"id": "before-round", "history_count": 0}]
    session.record_question_answers([{"question_id": "q1", "text": "评委"}])
    session.record_question_answers([{"question_id": "q2", "text": "中文"}, {"question_id": "q3", "text": "PDF"}])
    session.control["response_traces"].append({"id": "after-round", "history_count": 3})
    session.control.pop("answer_round_checkpoint")
    session.navigate_workspace("previous")
    assert set(session.control["workspace_drafts"]["answers"]) == {"q1", "q2", "q3"}
    from promptsmith.m1 import build_m1_input
    build_m1_input(session, "restored-request")  # validates live references


def test_new_goal_cannot_restore_answers_from_previous_goal():
    session = pending_session()
    session.record_question_answers([{"question_id": "q1", "text": "给评委看"}])
    session.set_task("为儿童编写数学练习题")
    assert session.workspace_navigation()["previous"] is None


def test_legacy_round_remains_recoverable_after_a_freeform_supplement():
    session = pending_session()
    session.control["response_traces"] = [{"id": "initial", "history_count": 0}]
    session.record_question_answers([{"question_id": f"q{i}", "text": f"回答{i}"} for i in range(1, 4)])
    session.control["response_traces"].append({"id": "after-round", "history_count": 3})
    session.pending_questions.append({"question_id": "supplement", "gap_id": None, "field": "supplement", "scope": "task", "text": "补充"})
    session.record_question("supplement", "answered", "另外的补充")
    session.control.pop("answer_round_checkpoint")
    assert session.workspace_navigation()["previous"] == "interview"
    session.navigate_workspace("previous")
    assert set(session.control["workspace_drafts"]["answers"]) == {"q1", "q2", "q3"}
    assert not session.question_history


def test_back_after_partial_submission_preserves_other_filled_drafts():
    session = pending_session()
    session.control["workspace_drafts"] = {"answers": {"q1": "第一题", "q3": "尚未提交的第三题"}}
    session.record_question_answers([{"question_id": "q1", "text": "第一题"}])
    session.navigate_workspace("previous")
    assert session.control["workspace_drafts"]["answers"] == {"q1": "第一题", "q3": "尚未提交的第三题"}


def test_back_preserves_drafts_changed_after_partial_submission():
    session = pending_session()
    session.control["workspace_drafts"] = {"answers": {"q2": "原来的第二题"}}
    session.record_question_answers([{"question_id": "q1", "text": "已提交的第一题"}])
    session.control["workspace_drafts"]["answers"] = {"q2": "后修改的第二题", "q3": "后来填写的第三题", "other-round": "不属于本轮"}
    session.navigate_workspace("previous")
    assert session.control["workspace_drafts"]["answers"] == {"q1": "已提交的第一题", "q2": "后修改的第二题", "q3": "后来填写的第三题"}


def test_web_back_carries_latest_unflushed_answer_drafts(app):
    session = pending_session()
    session.record_question_answers([{"question_id": "q1", "text": "第一题"}])
    install_session(app, session)
    controller = WorkspaceController(app)
    snapshot = controller.snapshot()
    controller.dispatch("navigate", {"direction": "previous", "stage": "interview", "session": snapshot["session"], "scope": snapshot["stop_scope"],
                                     "answer_drafts": {"q2": "刚写入尚未存档", "q3": "第三题👩‍💻"}}, snapshot["stamp"])
    assert controller.snapshot()["drafts"]["answers"] == {"q1": "第一题", "q2": "刚写入尚未存档", "q3": "第三题👩‍💻"}


def test_back_preserves_explicitly_cleared_pending_answer():
    session = pending_session()
    session.control["workspace_drafts"] = {"answers": {"q2": "旧草稿"}}
    session.record_question_answers([{"question_id": "q1", "text": "第一题"}])
    session.navigate_workspace("previous", answer_drafts={"q2": ""})
    assert session.control["workspace_drafts"]["answers"] == {"q1": "第一题", "q2": ""}


def test_tk_back_preserves_latest_pending_input(app):
    session = pending_session()
    session.record_question_answers([{"question_id": "q1", "text": "第一题"}])
    install_session(app, session)
    app._question_inputs["q2"].insert("1.0", "刚填写的第二题")
    controller = WorkspaceController(app)
    controller.dispatch("button", {"key": "back_stage"}, view_stamp(app))
    assert app._question_inputs["q1"].get("1.0", "end-1c") == "第一题"
    assert app._question_inputs["q2"].get("1.0", "end-1c") == "刚填写的第二题"


def test_invalid_live_drafts_cannot_change_session_during_back(app):
    session = pending_session()
    session.record_question_answers([{"question_id": "q1", "text": "第一题"}])
    install_session(app, session)
    controller = WorkspaceController(app)
    snapshot = controller.snapshot()
    before = deepcopy(session.to_dict())
    with pytest.raises(ValueError, match="回答草稿格式不正确"):
        controller.dispatch("navigate", {"direction": "previous", "stage": "interview", "session": snapshot["session"],
                                         "scope": snapshot["stop_scope"], "answer_drafts": {"q2": None}}, snapshot["stamp"])
    assert session.to_dict() == before


def test_cancelled_local_search_restarts_once_and_late_previous_result_is_discarded(app, tmp_path, monkeypatch):
    from threading import Event
    from promptsmith.local_skill_search import LocalSkillSearchResult
    from tests.test_ui_session_cancellation import _wait, _drain_completions
    session = confirmed_plan_session()
    install_session(app, session)
    candidate_calls = []
    entered, release = Event(), Event()
    def discovery(*args, **kwargs):
        candidate_calls.append(True)
        if len(candidate_calls) == 1:
            entered.set()
            assert release.wait(6)
        return LocalSkillSearchResult("no_match", [], "", 0, [])
    monkeypatch.setattr(app, "_skill_roots", lambda: [tmp_path / "empty-skills"])
    monkeypatch.setattr("promptsmith.ui.discover_local_skill_candidates", discovery)
    monkeypatch.setattr(app, "_client", lambda config: object())
    monkeypatch.setattr("promptsmith.ui.select_skill_candidates_with_ai", lambda *args, **kwargs: [])
    controller = WorkspaceController(app)
    try:
        controller.dispatch("button", {"key": "find_skills"}, view_stamp(app))
        assert entered.wait(2)
        snapshot = controller.snapshot()
        controller.dispatch("navigate", {"direction": "previous", "stage": "skills", "session": snapshot["session"], "scope": snapshot["stop_scope"]}, snapshot["stamp"])
        assert session.workspace_navigation()["stage"] == "plan"
        assert {"find_skills", "confirm_plan"} <= controller.snapshot()["buttons"].keys()
        controller.dispatch("button", {"key": "continue_stage"}, view_stamp(app))
        _wait(lambda: session.skill_state["search_state"]["status"] == "local_done", app.root)
        assert len(candidate_calls) == 2 and session.workspace_navigation()["stage"] == "skills"
        before = deepcopy(session.skill_state)
        release.set()
        _wait(lambda: not any(future.running() and owner.cancelled for future, owner in app._background_futures.items()), app.root)
        _drain_completions(app)
        assert session.skill_state == before
    finally:
        release.set()


def test_cancelled_network_search_continues_network_and_keeps_new_result(app, monkeypatch):
    from threading import Event
    from tests.test_network_skill_relevance import Http, Model
    from tests.test_ui_session_cancellation import _wait, _drain_completions
    from promptsmith.skill_network_discovery import search_network_skill_candidates, clear_network_skill_cache
    session = confirmed_plan_session()
    session.skill_state["search_state"] = {"status": "local_done", "local": {"status": "no_match", "count": 0}}
    install_session(app, session)
    entered, release = Event(), Event()
    calls = []
    http = Http([("learning-plan", "Plan a beginner Python learning curriculum with exercises")])
    model = Model()
    # Use the real discovery pipeline with disposable HTTP/model boundaries.
    def discovery(*args, **kwargs):
        calls.append(True)
        if len(calls) == 1:
            entered.set()
            assert release.wait(6)
        return search_network_skill_candidates(*args, **kwargs)
    monkeypatch.setattr("promptsmith.ui.search_network_skill_candidates", discovery)
    monkeypatch.setattr(app, "_client", lambda config: model)
    app.skill_search_opener = http
    controller = WorkspaceController(app)
    clear_network_skill_cache()
    try:
        controller.dispatch("button", {"key": "find_online"}, view_stamp(app))
        assert entered.wait(2)
        snapshot = controller.snapshot()
        controller.dispatch("navigate", {"direction": "previous", "stage": "skills", "session": snapshot["session"], "scope": snapshot["stop_scope"]}, snapshot["stamp"])
        assert session.workspace_navigation()["stage"] == "plan"
        assert session.skill_state["search_state"]["resume_kind"] == "network"
        controller.dispatch("button", {"key": "continue_stage"}, view_stamp(app))
        _wait(lambda: session.skill_state["search_state"]["status"] == "network_done", app.root)
        assert len(calls) == 2 and http.urls and model.calls
        assert session.workspace_navigation()["stage"] == "skills"
        before = deepcopy(session.skill_state)
        release.set()
        _wait(lambda: not any(future.running() and owner.cancelled for future, owner in app._background_futures.items()), app.root)
        _drain_completions(app)
        assert session.skill_state == before
    finally:
        release.set()
        clear_network_skill_cache()


def test_returned_plan_can_confirm_and_generate_prompt_without_search_or_model(app, monkeypatch):
    session = confirmed_plan_session()
    session.skill_state["search_state"] = {"status": "cancelled", "local": {"status": "cancelled", "count": 0}, "resume_kind": "local"}
    session.plan["pending_key_work_review_ids"] = ["k1"]
    install_session(app, session)
    controller = WorkspaceController(app)
    controller.dispatch("button", {"key": "back_stage"}, view_stamp(app))
    assert session.workspace_navigation()["stage"] == "plan"
    def unexpected_request(*args):
        pytest.fail("Direct prompt delivery must not submit a search or model request")
    monkeypatch.setattr(app, "_submit", unexpected_request)
    controller.dispatch("button", {"key": "confirm_plan"}, view_stamp(app))
    snapshot = controller.snapshot()
    assert session.plan["status"] == "confirmed" and not session.plan["pending_key_work_review_ids"]
    assert snapshot["navigation"]["stage"] == "result"
    assert any(card["kind"] == "result" for card in snapshot["cards"])
    assert not any(card["kind"] == "plan" for card in snapshot["cards"])
    assert session.final_result["canonical_body"]
    assert not app._skill_search_busy and not snapshot["locked"]
