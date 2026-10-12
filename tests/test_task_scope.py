"""Offline cancellation boundaries; execution deferred until the bug batch is complete."""
from __future__ import annotations

from concurrent.futures import CancelledError
from urllib.request import Request

import pytest

from promptsmith.api import ApiConfig, ApiResult, ChatCompletionsClient
from promptsmith.m1 import M1Assets
from promptsmith.open_skill_search import generate_skill_search_queries
from promptsmith.session import SessionState
from promptsmith.skill_ai_selection import _model_json
from promptsmith.task_scope import TaskScope, check_cancelled
from promptsmith.workflow import Phase12Workflow


def test_scope_cancellation_does_not_leak_into_other_tasks():
    previous, current = TaskScope(), TaskScope()
    with previous.activate():
        previous.cancel()
        with current.activate():
            check_cancelled()
        with pytest.raises(CancelledError):
            check_cancelled()
    check_cancelled()
    with current.activate():
        check_cancelled()


def test_m1_cancellation_stops_parsing_without_another_request(tmp_path):
    scope = TaskScope()
    session = SessionState.new()
    session.set_task("为软件重构设计界面。")
    workflow = Phase12Workflow(session, M1Assets.load(), tmp_path / "runs")
    payload = workflow.prepare_m1("cancel-m1")

    class Client:
        calls = 0

        def complete_json(self, *_args):
            self.calls += 1
            scope.cancel()
            return ApiResult("{", 1, None, "cancelled-fixture", "fixture")

    client = Client()
    with scope.activate(), pytest.raises(CancelledError):
        workflow.invoke_m1(payload, client, protocol="openai_chat_completions", configured_model="fixture")
    assert client.calls == 1
    assert session.errors == []
    assert session.pending_proposals == []


def test_http_cancellation_discards_body_before_decoding(monkeypatch):
    scope = TaskScope()

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def read(self):
            scope.cancel()
            return b"invalid JSON from the old conversation"

    monkeypatch.setattr("promptsmith.api.urlopen", lambda *_args, **_kwargs: Response())
    client = ChatCompletionsClient(ApiConfig("https://example.test", "fixture", "fixture-key"))
    with scope.activate(), pytest.raises(CancelledError):
        client._send_json(Request("https://example.test/chat/completions"), invalid_message="invalid")
    assert client.last_response_envelope is None


@pytest.mark.parametrize("operation", ["queries", "selection"])
def test_skill_cancellation_is_not_wrapped_as_optional_failure(operation):
    scope = TaskScope()

    class Client:
        def complete_json(self, *_args):
            scope.cancel()
            return ApiResult("{}", 1, None, "cancelled-fixture", "fixture")

    with scope.activate(), pytest.raises(CancelledError):
        if operation == "queries":
            generate_skill_search_queries([], context_text="UI 重构", client=Client())
        else:
            _model_json(Client(), "prompt", {}, {})
