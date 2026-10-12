"""Public request boundaries: lossless context compaction, offline only."""
import json
from copy import deepcopy

import pytest

from promptsmith.api import ApiConfig, client_for_config
from promptsmith.m1 import M1Assets, build_m1_input
from tests.test_interview_reliability import layout_session


PROTOCOLS = ["openai_chat_completions", "openai_responses", "anthropic_messages"]


@pytest.mark.parametrize("protocol", PROTOCOLS)
@pytest.mark.parametrize("matching_source", [True, False, "missing", "short", "multiple"])
def test_m1_request_sends_answer_body_once_without_losing_evidence(protocol, matching_source, monkeypatch):
    session = layout_session()
    answer = "允许重新调整布局，但必须保留原有功能、菜单和键盘快捷键。"
    session.record_question("q-layout", "answered", answer)
    payload = build_m1_input(session, "compact-answer")
    if matching_source is False:
        payload["state"]["question_history"][-1]["answer_text"] = "旧会话保留的不同正文"
    elif matching_source == "missing":
        source_id = payload["state"]["question_history"][-1]["answer_source_id"]
        payload["sources"] = [row for row in payload["sources"] if row["source_id"] != source_id]
    elif matching_source == "short":
        history = payload["state"]["question_history"][-1]
        history["answer_text"] = "好"
        next(row for row in payload["sources"] if row["source_id"] == history["answer_source_id"])["text"] = "好"
    elif matching_source == "multiple":
        history = deepcopy(payload["state"]["question_history"][-1])
        history.update(answer_source_id="source-another", answer_text=answer + "另一个范围内的详细回答。")
        payload["state"]["question_history"].append(history)
        payload["sources"].append({"source_id": "source-another", "text": history["answer_text"]})
    before = deepcopy(payload)
    client = client_for_config(ApiConfig(
        "https://api.deepseek.com", "deepseek-flash", "synthetic-only",
        protocol=protocol, reasoning_effort="max", max_tokens=65536,
    ))
    seen = []

    def respond(_endpoint, body, _headers):
        seen.append(body)
        if protocol == "openai_chat_completions":
            return {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}, 1
        if protocol == "openai_responses":
            return {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": "{}"}]}]}, 1
        return {"stop_reason": "end_turn", "content": [{"type": "text", "text": "{}"}]}, 1

    monkeypatch.setattr(client, "_post_json", respond)
    client.complete_json(M1Assets.load().system_prompt, payload, M1Assets.load().output_schema)
    body = seen[0]
    wire = (body["input"][0]["content"][-1]["text"] if protocol == "openai_responses" else
            body["messages"][1 if protocol == "openai_chat_completions" else 0]["content"])
    sent = json.loads(wire)
    history = sent["state"]["question_history"][-1]
    if matching_source is True or matching_source == "multiple":
        if matching_source is True:
            assert wire.count(answer) == 1
        for row in sent["state"]["question_history"]:
            if "answer_source_id" in row:
                assert "answer_text" not in row
                row["answer_text"] = next(source["text"] for source in sent["sources"]
                                          if source["source_id"] == row["answer_source_id"])
    elif matching_source is False:
        assert history["answer_text"] == "旧会话保留的不同正文"
    else:
        assert history["answer_text"] == ("好" if matching_source == "short" else answer)
    assert sent == payload
    assert payload == before
    assert len(seen) == 1
    assert body["max_output_tokens" if protocol == "openai_responses" else "max_tokens"] == 65536


def test_planning_prompt_removes_repeated_rules_but_keeps_context_contract():
    from promptsmith.m2 import M2Assets
    prompt = M2Assets.load().system_prompt
    assert len(prompt.encode("utf-8")) < 4200
    for term in ("interview_context", "answer_source_id", "relevant_materials", "skipped", "source_gap_id",
                 "requirement_coverage", "下游", "不重新访谈", "硬约束"):
        assert term in prompt


def test_search_query_planning_uses_work_signals_without_bookkeeping():
    from types import SimpleNamespace
    from promptsmith.open_skill_search import generate_skill_search_queries
    captured = []

    class Client:
        def complete_json(self, prompt, payload, schema):
            captured.append(payload)
            return SimpleNamespace(content='{"queries":["ui design SKILL.md"]}')

    work = {"key_work_id": "ui", "title": "设计 UI", "goal": "改进布局", "inputs": ["源码"],
            "outputs": ["新 UI"], "checkpoints": ["原功能可用"],
            "requirement_ids": ["r1"], "source_refs": [{"quote": "unused bookkeeping" * 500}],
            "step_ids": ["s1"], "reviewed_at": "unused"}
    before = deepcopy(work)
    assert generate_skill_search_queries([work], context_text="优化界面", client=Client())
    sent = captured[0]["key_works"][0]
    assert "source_refs" not in sent and "reviewed_at" not in sent
    assert sent["goal"] == work["goal"] and sent["checkpoints"] == work["checkpoints"]
    assert work == before


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_every_protocol_logs_input_cost_and_server_usage(protocol, monkeypatch, caplog):
    import promptsmith.api as api
    from io import BytesIO
    client = client_for_config(ApiConfig("http://127.0.0.1", "model", "synthetic-only", protocol=protocol))
    usage = {"prompt_tokens": 50, "completion_tokens": 90, "completion_tokens_details": {"reasoning_tokens": 80}}
    if protocol == "openai_chat_completions":
        envelope = {"usage": usage, "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}
    elif protocol == "openai_responses":
        envelope = {"usage": usage, "status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": "{}"}]}]}
    else:
        envelope = {"usage": usage, "stop_reason": "end_turn", "content": [{"type": "text", "text": "{}"}]}
    monkeypatch.setattr(api, "urlopen", lambda *a, **kw: BytesIO(json.dumps(envelope).encode()))
    with caplog.at_level("DEBUG"):
        client.complete_json("do not log this user content", {"task": "PRIVATE-CONTENT"}, {"type": "object"})
    assert "Model JSON input cost" in caplog.text
    records = [r.getMessage() for r in caplog.records if "Model response usage" in r.getMessage()]
    assert len(records) == 1
    assert "input_tokens=50" in records[0] and "reasoning_tokens=80" in records[0]
    assert "answer_tokens=10" in records[0]
    assert "PRIVATE-CONTENT" not in caplog.text and "do not log" not in caplog.text
