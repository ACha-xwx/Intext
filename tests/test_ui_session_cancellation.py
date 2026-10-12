"""Conversation switching must detach old work, including already queued callbacks."""
from __future__ import annotations

import queue
import time
import tkinter as tk
from threading import Event

import pytest

from promptsmith.api import ApiError, ApiResult
from promptsmith.session import SessionState
from promptsmith.storage import save_session
from promptsmith.ui import PromptSmithApp
from tests.test_final_delivery import confirmed_plan_session


def _wait(predicate, window=None, timeout=4):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if window is not None:
            window.update()
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError("异步取消场景未在限定时间内完成。")


def _drain_completions(application):
    while True:
        try:
            callback, value = application.completions.get_nowait()
        except queue.Empty:
            return
        callback(value)


@pytest.fixture
def app(tk_root, tmp_path, monkeypatch):
    # Keep all work local and avoid scanning the user's Skill directories.
    monkeypatch.setattr("promptsmith.ui.warm_local_skill_index", lambda *_args: None)
    monkeypatch.setattr("promptsmith.ui.messagebox.askyesno", lambda *_args, **_kwargs: True)
    window = tk.Toplevel(tk_root)
    window.withdraw()
    application = PromptSmithApp(window, session=confirmed_plan_session(), evidence_root=tmp_path / "runs")
    application.widgets["task_text"].delete("1.0", "end")
    application.widgets["task_text"].insert("1.0", application.session.task_text)
    application.api_base_var.set("https://example.test")
    application.api_model_var.set("fixture")
    application.api_key_var.set("fixture-key")
    application.confirm_model_settings()
    try:
        yield application, window
    finally:
        application.shutdown(wait=True)
        window.destroy()


def _switch(application, action, tmp_path, monkeypatch):
    if action == "new":
        application.new_session()
    else:
        # Reopening the same saved task also requires a new instance guard.
        saved = SessionState.from_dict(application.session.to_dict())
        saved.pending_requests.clear()
        path = tmp_path / "reopened.json"
        save_session(saved, path)
        monkeypatch.setattr("promptsmith.ui.filedialog.askopenfilename", lambda **_kwargs: str(path))
        application.open_session()


@pytest.mark.parametrize("action", ["new", "open"])
@pytest.mark.parametrize("stage", ["m1", "m2"])
@pytest.mark.parametrize("fail", [False, True])
def test_switch_unlocks_immediately_and_discards_old_model_return(app, tmp_path, monkeypatch, action, stage, fail):
    application, window = app
    entered, release = Event(), Event()

    class Client:
        calls = 0

        def complete_json(self, *_args):
            self.calls += 1
            entered.set()
            assert release.wait(4)
            if fail:
                raise ApiError("network", "old model failure")
            return ApiResult("{", 1, None, "old-response", "fixture")

    client = Client()
    monkeypatch.setattr(application, "_client", lambda _config: client)
    starts = {"m1": application.start_analysis, "m2": application.start_plan_generation}
    try:
        starts[stage]()
        assert entered.wait(2)
        previous = application.session
        application.widgets["conversation_input"].insert("1.0", "旧对话未发送的输入")
        _switch(application, action, tmp_path, monkeypatch)
        assert application.session is not previous
        assert not application._conversation_locked()
        assert application.busy_kind is None
        assert not application.session.pending_requests
        assert application.widgets["conversation_input"].get("1.0", "end-1c") == ""
        # Switching unlocks the workspace, but the empty composer cannot send.
        assert str(application.widgets["conversation_send_button"]["state"]) == "disabled"
        application.widgets["conversation_input"].insert("1.0", "新对话可以继续输入")
        assert str(application.widgets["conversation_send_button"]["state"]) == "normal"
        application.widgets["conversation_input"].delete("1.0", "end")
        status = application.status_var.get()
        errors = list(application.session.errors)

        # Old completion must not unlock or overwrite a newer operation either.
        application.busy_kind = "m1"
        application._set_busy(True, "new operation is running")
        release.set()
        _wait(lambda: not application._background_futures, window)
        _drain_completions(application)
        window.update()
        assert application.busy
        assert application.busy_kind == "m1"
        assert application.status_var.get() == "new operation is running"
        assert application.session.errors == errors
        assert client.calls == 1
        application._set_busy(False, status)
    finally:
        release.set()


@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("action", ["new", "open"])
def test_already_queued_completion_cannot_change_new_conversation(app, tmp_path, monkeypatch, caplog, fail, action):
    application, window = app
    caplog.set_level("DEBUG", logger="promptsmith.worker")

    def operation():
        if fail:
            raise RuntimeError("old queued error")
        return "old queued response"

    _wait(lambda: not application._background_futures, window)
    _drain_completions(application)
    application._submit(operation, lambda value: application.status_var.set(value),
                        lambda exc: application.status_var.set(str(exc)))
    _wait(lambda: not application.completions.empty())  # Deliberately don't pump Tk.
    _switch(application, action, tmp_path, monkeypatch)
    status = application.status_var.get()
    window.update()
    _drain_completions(application)
    assert application.status_var.get() == status
    assert not application._conversation_locked()
    assert "Conversation background tasks invalidated" in caplog.text
    assert "Discarded completion from cancelled scope" in caplog.text


def test_new_work_does_not_wait_for_two_blocked_old_workers(app):
    application, window = app
    entered = [Event(), Event()]
    release, fresh_done, queued_ran = Event(), Event(), Event()

    def old_work(index):
        entered[index].set()
        assert release.wait(4)
        return "old response"

    try:
        for index in range(2):
            application._submit(lambda index=index: old_work(index),
                                lambda value: application.status_var.set(value),
                                lambda exc: application.status_var.set(str(exc)))
        assert all(event.wait(2) for event in entered)
        application._submit(queued_ran.set, lambda _value: None, lambda exc: pytest.fail(str(exc)))
        application.new_session()
        application._submit(lambda: "fresh response", lambda _value: fresh_done.set(),
                            lambda exc: pytest.fail(str(exc)))
        _wait(fresh_done.is_set, window, timeout=2)
        assert not release.is_set()
        status = application.status_var.get()
        release.set()
        _wait(lambda: not application._background_futures, window)
        _drain_completions(application)
        assert application.status_var.get() == status
        assert not queued_ran.is_set()
    finally:
        release.set()


@pytest.mark.parametrize("stage", ["m1", "m2"])
def test_deferred_operation_keeps_original_workflow_and_instance_guard(app, tmp_path, monkeypatch, stage):
    application, _window = app
    captured, invoked = [], []
    workflow = application.workflow
    monkeypatch.setattr(application, "_submit", lambda *args: captured.append(args))
    monkeypatch.setattr(workflow, f"invoke_{stage}", lambda *_args, **_kwargs: invoked.append(workflow))
    if stage == "m1":
        application.start_analysis()
    else:
        application.start_plan_generation()
    operation, success, failure = captured[-1]
    _switch(application, "open", tmp_path, monkeypatch)
    status = application.status_var.get()
    operation()
    success(None)
    failure(RuntimeError("old failure"))
    assert invoked == [workflow]
    assert application.status_var.get() == status
    assert not application._conversation_locked()


def test_application_index_task_survives_session_switch(app):
    application, window = app
    entered, release, completed = Event(), Event(), Event()

    def warming():
        entered.set()
        assert release.wait(4)

    try:
        application._submit(warming, lambda _value: completed.set(), lambda exc: pytest.fail(str(exc)),
                            session_scoped=False)
        assert entered.wait(2)
        application.new_session()
        release.set()
        _wait(completed.is_set, window)
    finally:
        release.set()
