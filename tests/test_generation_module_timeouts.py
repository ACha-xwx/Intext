from __future__ import annotations

from copy import deepcopy
import json
from threading import Event

import pytest

from promptsmith.api import ApiError
from tests.test_ui_delivery_interactions import (
    _candidate,
    _configure_delivery_client,
    _DeliveryUiClient,
    _pump_until,
    _set_binding,
    _set_candidate_batch,
    delivery_app,
)


class TimeoutClient:
    def __init__(self):
        self.entered = Event()
        self.release = Event()
        self.payloads = []

    def complete_json(self, _system_prompt, payload, _schema):
        self.payloads.append(deepcopy(payload))
        self.entered.set()
        assert self.release.wait(timeout=3), "测试未释放超时响应。"
        raise ApiError("timeout", "fixture timeout", latency_ms=120001, timeout_seconds=120)


@pytest.mark.parametrize(
    ("purpose", "button_name", "label"),
    [
        ("m2", "generate_plan_button", "初始方案生成"),
        ("m3", "skill_analyze_button", "候选分析"),
        ("m4", "skill_integrate_button", "Agent Skill 指令整合"),
        ("m5", "m5_generate_button", "示例生成"),
    ],
)
def test_module_timeout_preserves_business_state_and_releases_ui(
    delivery_app, tmp_path, monkeypatch, purpose, button_name, label
):
    app, window = delivery_app
    _configure_delivery_client(app, monkeypatch, _DeliveryUiClient())
    if purpose in {"m3", "m4"}:
        candidate, binding = _candidate()
        if purpose == "m3":
            _set_candidate_batch(app, candidate)
        else:
            _set_binding(app, candidate, binding)
        # Preserve a real previous analysis or final draft across the failed replacement.
        app.widgets[button_name].invoke()
        _pump_until(window, lambda: not app.delivery_busy)
        assert not app.test_dialogs
        if purpose == "m3":
            assert app.session.skill_state["candidate_batch"]["m3_analysis"]
        else:
            assert app.session.final_result["content"]
    elif purpose == "m5":
        app.widgets["m5_criterion_entry"].delete(0, "end")
        app.widgets["m5_criterion_entry"].insert(0, "语气")

    client = TimeoutClient()
    configurations = []

    def client_for_request(config):
        configurations.append(config)
        return client

    monkeypatch.setattr(app, "_client", client_for_request)
    before = deepcopy(app.session.to_dict())
    button = app.widgets[button_name]
    try:
        button.invoke()
        assert client.entered.wait(timeout=2), "模块入口没有发起模型请求。"
        assert len(configurations) == 1
        assert configurations[0].timeout_seconds == 120
        assert str(button["state"]) == "disabled"
        if purpose in {"m3", "m4"}:
            assert app.delivery_busy
            assert app.delivery_workflow._requests
        else:
            assert app.busy and app.busy_kind == purpose
            assert app.session.pending_requests
    finally:
        client.release.set()
    _pump_until(window, lambda: not app.busy and not app.delivery_busy)

    assert len(client.payloads) == 1
    assert client.payloads[0]["schema_version"].startswith(purpose + ".")
    assert app.busy_kind is None
    assert app._active_delivery_request is None
    assert app._active_m5_request is None
    assert app.session.pending_requests == {}
    assert app.delivery_workflow._requests == {}
    assert str(button["state"]) == "normal"
    diagnostic_fields = {"updated_at", "api_runs", "errors", "pending_requests"}
    if purpose == "m5":
        diagnostic_fields.add("m5_state")
        assert app.session.m5_state["status"] == "error"
        assert app.session.m5_state["candidate_pending"] is False
    after = app.session.to_dict()
    for key, value in before.items():
        if key not in diagnostic_fields:
            assert after[key] == value, key
    assert app.session.api_runs[-1]["status"] == "timeout"
    assert app.session.api_runs[-1]["usage"] is None

    expected_message = f"{label}等待超过120秒"
    if purpose == "m5":
        assert expected_message in app.status_var.get()
        assert not app.test_dialogs
    else:
        assert len(app.test_dialogs) == 1
        assert app.test_dialogs[0][0] == ("warning" if purpose == "m2" else "error")
        assert expected_message in app.test_dialogs[0][1][1]
        assert "已有回答、需求和结果已保留" in app.test_dialogs[0][1][1]

    evidence = next(
        path.parent for path in tmp_path.rglob("check.json")
        if json.loads(path.read_text(encoding="utf-8")).get("failure_kind") == "timeout"
    )
    check = json.loads((evidence / "check.json").read_text(encoding="utf-8"))
    metadata = json.loads((evidence / "meta.json").read_text(encoding="utf-8"))
    assert check["schema"] == check["semantic"] == "not_reached"
    assert metadata["latency_ms"] == 120001
    assert metadata["usage"] is None
    assert metadata["request_parameters"]["timeout_seconds"] == 120
    assert metadata["request_parameters"]["max_tokens"] == 8192
    assert (evidence / "response.raw.txt").read_bytes() == b""
    assert json.loads((evidence / "input.json").read_text(encoding="utf-8")) == client.payloads[0]
