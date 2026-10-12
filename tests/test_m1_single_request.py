"""Local validation never starts an unrequested second reasoning process."""
import json

import pytest

from promptsmith.api import ApiResult, ApiError
from promptsmith.m1 import M1Assets
from promptsmith.session import SessionState
from promptsmith.workflow import Phase12Workflow, M1CallFailure
from tests.test_generation_timeout_ui import jgs_response


@pytest.mark.parametrize("failure", ["pending_target", "json", "identity", "input_error"])
def test_invalid_m1_return_has_one_request_and_preserves_input(tmp_path, failure):
    session = SessionState.new()
    session.set_task("讲解JGS")
    workflow = Phase12Workflow(session, M1Assets.load(), tmp_path / "runs")
    payload = workflow.prepare_m1("single-request")
    response = jgs_response(payload)
    if failure == "pending_target":
        response["proposals"][0].update(operation="replace", target_item_id="p1")
    elif failure == "identity":
        response["request_id"] = "other-request"
    elif failure == "input_error":
        response.update(status="input_error", error={"code": "invalid_input", "message": "无法处理输入"})
        for key in ("proposals", "gaps", "questions", "conflicts", "review_item_ids", "gap_updates", "question_reopens"):
            response[key] = []
        response["readiness"] = {"goal_identified": False, "deliverable_identified": False,
                                 "blocking_gap_ids": [], "reason": "输入错误"}
        response["model_judgment"] = None
        response["next_action"] = "pause_with_unknowns"
    raw = "{" if failure == "json" else json.dumps(response, ensure_ascii=False)

    class Client:
        calls = 0

        def complete_json(self, *_args):
            self.calls += 1
            return ApiResult(raw, 214244, {"completion_tokens": 37724}, "fixture", "fixture")

    client = Client()
    try:
        workflow.invoke_m1(payload, client, protocol="offline", configured_model="fixture")
    except M1CallFailure:
        pass
    assert client.calls == 1, "Schema/reference failures must not trigger two more expensive calls"
    assert session.task_text == "讲解JGS"
    assert not session.requirements
    assert not session.pending_proposals


def test_reasoning_budget_exhaustion_has_one_call_and_explains_empty_answer(tmp_path):
    from promptsmith.api import ApiConfig, ChatCompletionsClient
    import promptsmith.api as api
    from unittest.mock import patch
    envelope = {"id": "budget-fixture", "model": "fixture", "choices": [{"finish_reason": "length",
                "message": {"role": "assistant", "content": "", "reasoning_content": "仅有思考"}}],
                "usage": {"completion_tokens": 65536, "completion_tokens_details": {"reasoning_tokens": 65536}}}
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self): return json.dumps(envelope).encode()
    client = ChatCompletionsClient(ApiConfig(base_url="https://example.invalid", model="fixture", api_key="fixture"))
    session = SessionState.new()
    session.set_task("整理目标")
    workflow = Phase12Workflow(session, M1Assets.load(), tmp_path / 'runs')
    payload = workflow.prepare_m1('budget-fixture')
    with patch.object(api, 'urlopen', return_value=Response()) as transport, pytest.raises(M1CallFailure) as failure:
        workflow.invoke_m1(payload, client, protocol="offline", configured_model="fixture")
    assert transport.call_count == 1
    assert failure.value.kind == 'truncated'
    assert '思考耗尽' in str(failure.value) and '正文' in str(failure.value)
    assert not session.requirements and not session.pending_proposals
