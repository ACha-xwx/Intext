"""Batch answer contracts, queued for the user's later combined regression."""
from copy import deepcopy
import logging

import pytest

from promptsmith.session import SessionState, SessionStateError
from promptsmith.storage import load_session, save_session
from promptsmith.web_workspace import WorkspaceController, view_stamp
from promptsmith.web_debug import concise_message
from tests.test_conversation_workspace import app
from tests.test_response_workspace import questions


def pending_session():
    session = SessionState.new()
    session.set_task("准备比赛技术文档")
    session.pending_questions = questions()
    return session


def prepare_app(app):
    app.widgets["task_text"].insert("1.0", "准备比赛技术文档")
    app._sync_input()
    app.session.pending_questions = questions()
    app.refresh()


def test_batch_keeps_independent_sources_one_group_and_blank_question(tmp_path):
    session = pending_session()
    session.control["workspace_drafts"] = {"answers": {"q1": "给评委看", "q2": " ", "q3": "中文👩‍💻"}}
    assert session.record_question_answers([
        {"question_id": "q1", "text": "给评委看"},
        {"question_id": "q2", "text": " "},
        {"question_id": "q3", "text": "中文👩‍💻"},
    ]) == ["q1", "q3"]
    history = session.question_history
    assert [row["answer_text"] for row in history] == ["给评委看", "中文👩‍💻"]
    assert len({row["answer_source_id"] for row in history}) == 2
    assert len({row["submission_group_id"] for row in history}) == 1
    assert [row["question_id"] for row in session.questions_for_review()] == ["q2"]
    assert session.control["workspace_drafts"]["answers"] == {"q2": " "}
    save_session(session, tmp_path / "batch.json")
    restored = load_session(tmp_path / "batch.json")
    assert restored.question_history == history
    assert [row["question_id"] for row in restored.questions_for_review()] == ["q2"]


@pytest.mark.parametrize("second", [
    {"question_id": "q1", "text": "重复"},
    {"question_id": "old-question", "text": "过期"},
    {"question_id": "q2", "text": None},
])
def test_invalid_batch_changes_nothing(second):
    session = pending_session()
    before = deepcopy(session.__dict__)
    with pytest.raises(SessionStateError):
        session.record_question_answers([{"question_id": "q1", "text": "第一题"}, second])
    assert session.__dict__ == before


def test_recording_failure_rolls_back_the_entire_batch(monkeypatch, caplog):
    session = pending_session()
    before = deepcopy(session.__dict__)
    original = SessionState.record_question
    def fail_second(self, key, *args, **kwargs):
        if key == "q2":
            raise SessionStateError("模拟第二题记录失败")
        return original(self, key, *args, **kwargs)
    monkeypatch.setattr(SessionState, "record_question", fail_second)
    with caplog.at_level(logging.DEBUG), pytest.raises(SessionStateError):
        session.record_question_answers([
            {"question_id": "q1", "text": "私密回答一"},
            {"question_id": "q2", "text": "私密回答二"},
        ])
    assert session.__dict__ == before
    assert any(record.exc_info for record in caplog.records)
    assert "私密回答" not in caplog.text


def test_web_batch_waits_for_blank_question_then_analyzes_once(app, monkeypatch):
    prepare_app(app)
    calls = []
    monkeypatch.setattr(app, "start_analysis", lambda: calls.append(deepcopy(app.session.question_history)))
    view = WorkspaceController(app)
    result = view.dispatch("answer", {"answers": [
        {"id": "q1", "text": "给评委看"}, {"id": "q3", "text": "提交Markdown"},
    ]}, view_stamp(app))
    assert result == {"submitted": ["q1", "q3"]}
    assert not calls
    assert set(app._question_inputs) == {"q2"}
    view.dispatch("answer", {"answers": [{"id": "q2", "text": "软件比赛"}]}, view_stamp(app))
    assert len(calls) == 1
    assert [row["question_id"] for row in calls[0]] == ["q1", "q3", "q2"]
    assert not app._question_drafts


def test_web_failure_retains_all_drafts_and_stale_action_cannot_submit(app, monkeypatch):
    prepare_app(app)
    calls = []
    monkeypatch.setattr(app, "start_analysis", lambda: calls.append(True))
    app._question_inputs["q1"].insert("1.0", "未提交草稿")
    app._question_drafts["q1"] = "未提交草稿"
    app.session.control["workspace_drafts"] = {"answers": {"q1": "未提交草稿"}}
    view = WorkspaceController(app)
    before = deepcopy(app.session.__dict__)
    with pytest.raises(ValueError):
        view.dispatch("answer", {"answers": [{"id": "q1", "text": "新回答"}, {"id": "old", "text": "过期"}]}, view_stamp(app))
    assert app.session.__dict__ == before
    assert app._question_inputs["q1"].get("1.0", "end-1c") == "未提交草稿"
    assert app._question_drafts["q1"] == "未提交草稿" and not calls
    stamp = view_stamp(app)
    app.new_session()
    with pytest.raises(ValueError):
        view.dispatch("answer", {"answers": [{"id": "q1", "text": "迟到回答"}]}, stamp)
    assert not app.session.question_history


def test_native_empty_question_send_collects_other_filled_answers(app, monkeypatch):
    prepare_app(app)
    calls = []
    monkeypatch.setattr(app, "start_analysis", lambda: calls.append(True))
    app._question_inputs["q1"].insert("1.0", "第一题")
    app._question_inputs["q3"].insert("1.0", "第三题")
    app.root.update()
    app._conversation_buttons["submit:q2"].invoke()
    assert [row["question_id"] for row in app.session.question_history] == ["q1", "q3"]
    assert set(app._question_inputs) == {"q2"} and not calls


def test_web_legacy_single_answer_and_busy_guard_are_preserved(app, monkeypatch):
    prepare_app(app)
    monkeypatch.setattr(app, "start_analysis", lambda: None)
    view = WorkspaceController(app)
    assert view.dispatch("answer", {"id": "q2", "text": "只提交这一题"}, view_stamp(app)) == {"submitted": ["q2"]}
    assert [row["question_id"] for row in app.session.question_history] == ["q2"]
    app._set_busy(True, "模拟处理中")
    with pytest.raises(ValueError):
        view.dispatch("answer", {"answers": [{"id": "q1", "text": "不应提交"}]}, view_stamp(app))
    assert len(app.session.question_history) == 1
    app._set_busy(False, "模拟结束")


def test_debug_batch_summary_is_concise_but_errors_remain_complete():
    raw = "Question answer batch saved: task=task-fixture count=2 questions=['q1', 'q3'] remaining=1"
    assert concise_message(raw, logging.INFO) == "已提交 2 个回答，剩余 1 个问题"
    error = "Question answer batch rejected; no answers committed: task=task-fixture\n完整异常链"
    assert concise_message(error, logging.ERROR) == error


def test_answer_batch_can_reject_multiple_displayed_explanations_of_the_same_gap():
    session = pending_session()
    session.gaps = [{"gap_id": "g1", "field": "audience", "scope": "目标", "description": "谁会使用？",
                     "importance": "blocking_direction", "origin": "ambiguous", "depends_on": []}]
    session.pending_questions[0]["gap_id"] = "g1"
    session.pending_proposals = [{
        "proposal_id": key, "kind": "pending_interpretation", "operation": "new", "target_item_id": None,
        "field": "audience", "scope": "目标", "text": "可能是评委", "valid_for_version": session.requirement_version,
        "interpretation_for": {"gap_id": "g1", "question_id": "q1"},
    } for key in ["p1", "p2"]]
    assert session.record_question_answers([
        {"question_id": "q1", "text": "给评委看"},
    ], reject_interpretation_ids=["p1", "p2"]) == ["q1"]
    assert session.question_history[-1]["answer_text"] == "给评委看"
    assert not session.pending_proposals
