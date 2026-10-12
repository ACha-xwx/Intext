"""Stop uses the desktop action boundary and keeps the current session."""
from copy import deepcopy
from threading import Event
from promptsmith.storage import load_session, save_session

import pytest

from promptsmith.api import ApiResult
from promptsmith.web_workspace import WorkspaceController, view_stamp
from tests.test_ui_session_cancellation import app, _wait, _drain_completions


@pytest.mark.parametrize("stage", ["m1", "m2"])
def test_stop_unlocks_current_session_and_prevents_retry_or_late_apply(app, monkeypatch, stage):
    application, window = app
    entered, release = Event(), Event()

    class Client:
        calls = 0

        def complete_json(self, *_args):
            self.calls += 1
            entered.set()
            assert release.wait(4)
            return ApiResult("{", 1, None, "late", "fixture")

    client = Client()
    monkeypatch.setattr(application, "_client", lambda _config: client)
    owner = application.session
    prior = deepcopy(owner.to_dict())
    controller = WorkspaceController(application)
    try:
        (application.start_analysis if stage == "m1" else application.start_plan_generation)()
        assert entered.wait(2)
        controller.dispatch("stop", {"session": application._session_instance_token, "scope": controller.snapshot()["stop_scope"]}, view_stamp(application))
        assert not controller.snapshot()["locked"]
        assert application.session is owner and not owner.pending_requests
        for field in ("requirements", "plan", "skill_state", "final_result"):
            assert owner.to_dict()[field] == prior[field]
        release.set()
        _wait(lambda: not application._background_futures, window)
        _drain_completions(application)
        assert client.calls == 1
        assert not owner.errors
        assert not application._conversation_locked()
        # The same session can immediately make a fresh request.
        entered.clear()
        application.start_analysis()
        _wait(lambda: client.calls >= 2, window)
        controller.dispatch("stop", {"session": application._session_instance_token, "scope": controller.snapshot()["stop_scope"]}, view_stamp(application))
    finally:
        release.set()


def test_old_session_stop_cannot_cancel_a_new_session(app):
    application, _window = app
    controller = WorkspaceController(application)
    with pytest.raises(ValueError, match="会话"):
        controller.dispatch("stop", {"session": "old-session"}, view_stamp(application))


def test_retired_scope_stop_cannot_cancel_next_request(app):
    application, _window = app
    controller = WorkspaceController(application)
    old_scope = controller.snapshot()["stop_scope"]
    application.busy = True
    application.cancel_active_request()
    current_scope = application._session_tasks
    with pytest.raises(ValueError, match="任务"):
        controller.dispatch("stop", {"session": application._session_instance_token,
                                     "scope": old_scope}, view_stamp(application))
    assert not current_scope.cancelled


def test_delayed_stop_from_completed_operation_cannot_stop_next_operation(app):
    application, window = app
    controller = WorkspaceController(application)
    entered, release = Event(), Event()
    failures = []
    application._submit(lambda: "first", lambda _: None, failures.append)
    old_scope = controller.snapshot()["stop_scope"]
    _wait(lambda: not application._background_futures, window)
    _drain_completions(application)
    def second():
        entered.set()
        assert release.wait(4)
    application._submit(second, lambda _: None, failures.append)
    try:
        assert entered.wait(2)
        with pytest.raises(ValueError, match="任务"):
            controller.dispatch("stop", {"session": application._session_instance_token,
                                         "scope": old_scope}, view_stamp(application))
        assert not application._session_tasks.cancelled
    finally:
        release.set()


@pytest.mark.parametrize("kind", ["local", "network"])
def test_stopping_skill_search_clears_running_state_and_keeps_retry_available(app, monkeypatch, tmp_path, kind):
    application, window = app
    entered, release = Event(), Event()
    def operation(*_args):
        entered.set()
        assert release.wait(4)
    method = "_local_skill_search_operation" if kind == "local" else "_network_skill_search_operation"
    monkeypatch.setattr(application, method, operation)
    application.session.skill_state["search_state"] = {"status": "local_done", "local": {"status": "ok", "count": 2}}
    try:
        (application.find_skills if kind == "local" else application.search_online_skills)()
        assert entered.wait(2)
        application.cancel_active_request()
        state = application.session.skill_state["search_state"]
        assert state["status"] == "cancelled"
        assert state[kind]["status"] != "running"
        assert "正在" not in application.skill_status_var.get()
        assert str(application.widgets["skill_online_button"]["state"]) == "normal"
        restored = load_session(save_session(application.session, tmp_path / "stopped.json"))
        assert restored.skill_state["search_state"]["status"] == "cancelled"
        assert restored.skill_state["search_state"][kind] == state[kind]
    finally:
        release.set()
