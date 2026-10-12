"""Literal quote recovery; run with the deferred bug regression batch."""
from __future__ import annotations

import json
from copy import deepcopy

import pytest

from promptsmith.api import ApiResult
from promptsmith.m1 import M1Assets, M1ValidationError, parse_m1_response
from promptsmith.session import SessionState
from promptsmith.workflow import Phase12Workflow
from tests.test_ui_reliability import base_result


TASK = "我想把一个基于python + tkinter的软件的UI页面重新设计修改，主要是布局和各个元素的样式"


def _prepared(tmp_path, task=TASK):
    session = SessionState.new()
    session.set_task(task)
    workflow = Phase12Workflow(session, M1Assets.load(), tmp_path / "runs")
    payload = workflow.prepare_m1("quote-recovery")
    result = base_result(payload)
    result["proposals"] = [{
        "proposal_id": "p-ui", "operation": "new", "target_item_id": None,
        "field": "goal", "text": "重新设计 UI 布局和元素样式。", "kind": "user_decision",
        "strength": "unspecified", "scope": "当前任务", "depends_on": [],
        "source_refs": [{"source_id": payload["sources"][-1]["source_id"], "quote": "把...的UI页面重新设计修改"}],
        "reason": "根据用户目标整理，仍需用户核对。",
    }]
    return session, workflow, payload, result


@pytest.mark.parametrize(("quote", "expected"), [
    ("把...的UI页面重新设计修改", "把一个基于python + tkinter的软件的UI页面重新设计修改"),
    ("把……的UI页面重新设计修改", "把一个基于python + tkinter的软件的UI页面重新设计修改"),
    ("PYTHON+TKINTER", "python + tkinter"),
    ("UI 页 面 重新设计修改", "UI页面重新设计修改"),
])
def test_restore_quote_as_actual_source_without_changing_candidate(tmp_path, quote, expected):
    _session, workflow, payload, result = _prepared(tmp_path)
    result["proposals"][0]["source_refs"][0]["quote"] = quote
    before = deepcopy(result)
    report = []
    parsed = parse_m1_response(json.dumps(result, ensure_ascii=False), payload,
                               workflow.assets.output_schema, normalization_report=report)
    proposal = parsed["proposals"][0]
    assert proposal["source_refs"][0]["quote"] == expected
    assert expected in payload["sources"][-1]["text"]
    assert {key: value for key, value in proposal.items() if key != "source_refs"} == {
        key: value for key, value in before["proposals"][0].items() if key != "source_refs"}
    assert result == before
    assert report == [{"action": "restore_literal_source_quote",
                       "path": "$.proposals[0].source_refs[0].quote",
                       "source_id": payload["sources"][-1]["source_id"]}]


@pytest.mark.parametrize("invalid", ["unknown_source", "invented_quote", "reordered_quote", "ambiguous_quote"])
def test_quote_recovery_does_not_invent_or_guess_provenance(tmp_path, invalid):
    task = TASK if invalid != "ambiguous_quote" else TASK + "；另一个UI页面重新设计修改"
    _session, workflow, payload, result = _prepared(tmp_path, task)
    ref = result["proposals"][0]["source_refs"][0]
    if invalid == "unknown_source":
        ref["source_id"] = "invented-source"
    elif invalid == "invented_quote":
        ref["quote"] = "用户要求使用 React 并且接入数据库"
    elif invalid == "reordered_quote":
        ref["quote"] = "样式...布局"
    else:
        ref["quote"] = "UI 页 面 重新设计修改"
    with pytest.raises(M1ValidationError, match="逐字片段"):
        parse_m1_response(json.dumps(result, ensure_ascii=False), payload, workflow.assets.output_schema)


def test_quote_recovery_needs_one_model_call_and_preserves_raw_evidence(tmp_path, caplog):
    session, workflow, payload, result = _prepared(tmp_path)
    raw = json.dumps(result, ensure_ascii=False)

    class Client:
        calls = 0

        def complete_json(self, *_args):
            self.calls += 1
            return ApiResult(raw, 1, None, "offline-quote-fixture", "fixture-model")

    client = Client()
    outcome = workflow.invoke_m1(payload, client, protocol="offline", configured_model="fixture-model")
    workflow.apply_m1(payload, outcome)
    assert client.calls == 1
    assert session.errors == []
    assert session.requirements == []  # Recovery does not confirm a user's requirements.
    assert session.pending_proposals[0]["source_refs"][0]["quote"] in TASK
    assert (outcome.evidence_dir / "response.raw.txt").read_text(encoding="utf-8") == raw
    effective = json.loads((outcome.evidence_dir / "response.effective.json").read_text(encoding="utf-8"))
    assert effective == outcome.parsed
    assert "restore_literal_source_quote" in caplog.text
