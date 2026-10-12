from __future__ import annotations

from copy import deepcopy
import json

import pytest

from promptsmith.api import (
    ANTHROPIC_MESSAGES_PROTOCOL, OPENAI_RESPONSES_PROTOCOL, PROTOCOL_ID,
    ApiConfig, ApiError, ApiResult, client_for_config,
)
from promptsmith.delivery_workflow import DeliveryWorkflow
from promptsmith.m1 import M1Assets
from promptsmith.storage import load_session, save_session
from promptsmith.workflow import M2CallFailure, M5CallFailure, Phase12Workflow
from tests.test_delivery_workflow import make_session
from tests.test_generation_timeout_ui import app
from tests.test_m2_workflow import confirmed_session, valid_result
from tests.test_m5_workflow import session_with_task
from tests.test_ui_reliability import pump


@pytest.mark.parametrize("model", ["deepseek-flash", "deepseek-v4-pro"])
@pytest.mark.parametrize("protocol,base,limit_field,effort_field,stop", [
    (PROTOCOL_ID, "https://api.deepseek.com/v1/chat/completions", "max_tokens", "reasoning_effort", "stop"),
    (OPENAI_RESPONSES_PROTOCOL, "https://api.deepseek.com/v1/responses", "max_output_tokens", "reasoning", "completed"),
    (ANTHROPIC_MESSAGES_PROTOCOL, "https://api.deepseek.com/anthropic/v1", "max_tokens", "output_config", "end_turn"),
])
def test_official_deepseek_actual_json_body_keeps_contract_and_budget(
    model, protocol, base, limit_field, effort_field, stop, monkeypatch,
):
    client = client_for_config(ApiConfig(base, model, "test-key", protocol=protocol))
    seen = []
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    if protocol == PROTOCOL_ID:
        envelope = {"choices": [{"finish_reason": stop, "message": {"content": '{"ok":true}'}}]}
    elif protocol == OPENAI_RESPONSES_PROTOCOL:
        envelope = {"status": stop, "output": [{"type": "message", "content": [{"type": "output_text", "text": '{"ok":true}'}]}]}
    else:
        envelope = {"stop_reason": stop, "content": [{"type": "text", "text": '{"ok":true}'}]}
    monkeypatch.setattr(client, "_post_json", lambda endpoint, body, headers: (seen.append(body) or (envelope, 12)))
    result = client.complete_json("system", {"task": "demo"}, schema)
    body = seen[0]
    assert body[limit_field] == 65536
    assert body[effort_field] == ("low" if effort_field == "reasoning_effort" else
                                  {"effort": "low"} if effort_field == "reasoning" else
                                  {"effort": "low", "format": {"type": "json_schema", "schema": schema}})
    if protocol == PROTOCOL_ID:
        assert body["response_format"] == {"type": "json_object"}
        assert json.loads(body["messages"][1]["content"]) == {"task": "demo"}
    elif protocol == OPENAI_RESPONSES_PROTOCOL:
        assert body["text"]["format"]["schema"] == schema
    assert result.finish_reason == stop


class TruncatedClient:
    def complete_json(self, *_args):
        raise ApiError(
            "truncated", "模型输出因长度限制被截断。", latency_ms=1000,
            response_content='{"plan":', response_usage={"completion_tokens": 8192},
            response_id="partial-id", response_model="deepseek-flash", finish_reason="length",
        )


def test_m2_retry_survives_reopen_and_preserves_all_input(tmp_path):
    session = confirmed_session()
    workflow = Phase12Workflow(session, M1Assets.load(), tmp_path / "calls")
    payload = workflow.prepare_m2("first")
    with pytest.raises(M2CallFailure) as failure:
        workflow.invoke_m2(payload, TruncatedClient(), protocol=PROTOCOL_ID, configured_model="deepseek-flash")
    meta = json.loads((failure.value.evidence_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["finish_reason"] == "length"
    assert session.api_runs[-1]["finish_reason"] == "length"
    assert workflow.m2_retry_recommended()
    session = load_session(save_session(session, tmp_path / "retry.json"))
    workflow = Phase12Workflow(session, M1Assets.load(), tmp_path / "calls")
    assert workflow.m2_retry_recommended()
    retried = workflow.prepare_m2("retry", current_date=payload["control"]["current_date"])
    assert retried["requirements"] == payload["requirements"]
    assert retried["unresolved_items"] == payload["unresolved_items"]
    prompts = []

    class SuccessClient:
        def complete_json(self, system, payload, schema):
            prompts.append(system)
            return ApiResult(json.dumps(valid_result(payload), ensure_ascii=False), 12, {}, "ok", "fixture", finish_reason="stop")

    outcome = workflow.invoke_m2(retried, SuccessClient(), protocol=PROTOCOL_ID, configured_model="fixture", compact_retry=True)
    workflow.apply_m2(retried, outcome)
    assert not workflow.m2_retry_recommended()
    assert session.plan["status"] == "draft"
    assert "重新生成" in prompts[0]
    retry_meta = json.loads((outcome.evidence_dir / "meta.json").read_text(encoding="utf-8"))
    assert retry_meta["request_mode"] == "compact_retry"
    assert (outcome.evidence_dir / "system.txt").read_text(encoding="utf-8") == prompts[0]


@pytest.mark.parametrize("purpose", ["m3", "m4", "m5"])
def test_other_structured_generators_retain_truncation_diagnostics(purpose, tmp_path):
    if purpose == "m5":
        session = session_with_task()
        workflow = Phase12Workflow(session, M1Assets.load(), tmp_path)
        payload = workflow.prepare_m5("partial-m5", criterion_description="语气")
        with pytest.raises(M5CallFailure) as failure:
            workflow.invoke_m5(payload, TruncatedClient(), protocol=PROTOCOL_ID, configured_model="fixture")
        evidence = failure.value.evidence_dir
    else:
        session = make_session(with_binding=purpose == "m4")
        workflow = DeliveryWorkflow(session, evidence_root=tmp_path)
        payload = getattr(workflow, f"prepare_{purpose}")(f"partial-{purpose}", connection_version=1)
        outcome = getattr(workflow, f"invoke_{purpose}")(payload, TruncatedClient(), protocol=PROTOCOL_ID, configured_model="fixture")
        evidence = outcome.evidence_dir
        assert outcome.failure_kind == "truncated"
        assert outcome.parsed is None
    assert (evidence / "response.raw.txt").read_text(encoding="utf-8") == '{"plan":'
    meta = json.loads((evidence / "meta.json").read_text(encoding="utf-8"))
    check = json.loads((evidence / "check.json").read_text(encoding="utf-8"))
    assert meta["usage"] == {"completion_tokens": 8192}
    assert meta["provider_response_id"] == "partial-id"
    assert meta["finish_reason"] == check["finish_reason"] == "length"


def test_m2_ui_explicit_retry_keeps_requirements_and_main_action(app, monkeypatch):
    session = confirmed_session()
    app.session = session
    app.workflow.session = session
    app.delivery_workflow.session = session
    app.widgets["task_text"].insert("1.0", session.task_text)
    app.category_var.set(next(label for label, category in app.category_by_label.items() if category == session.selected_category))
    calls, messages = [], []
    old_requirements = deepcopy(session.requirements)

    class Client:
        def complete_json(self, system, payload, schema):
            calls.append(system)
            if len(calls) == 1:
                return TruncatedClient().complete_json()
            return ApiResult(json.dumps(valid_result(payload), ensure_ascii=False), 12, {}, "ok", "fixture", finish_reason="stop")

    monkeypatch.setattr(app, "_client", lambda config: Client())
    monkeypatch.setattr("promptsmith.ui.messagebox.showwarning", lambda *args, **kwargs: messages.append(args))
    app.refresh()
    app.run_primary_action()
    pump(app.root, app)
    assert len(calls) == 1
    assert session.requirements == old_requirements
    assert not session.pending_requests and not app.busy
    assert app.primary_action_var.get() == "重新生成方案"
    assert "需求已保留" in app.guidance_var.get()
    assert "重新生成方案" in messages[0][1]
    assert "请求与错误记录保存在" not in app.status_var.get()
    app.root.update()
    assert len(calls) == 1
    app.run_primary_action()
    pump(app.root, app)
    assert len(calls) == 2
    assert "重新生成" in calls[1]
    assert not app.busy and not session.pending_requests
    assert session.requirements == old_requirements
    assert session.plan["status"] == "draft"
