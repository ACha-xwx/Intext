"""Waiting is a read-only state; answered questions must not loop. Offline."""
import json
from copy import deepcopy

import pytest

from promptsmith.m1 import M1Assets, apply_m1_response, build_m1_input, parse_m1_response
from promptsmith.session import SessionState, SessionStateError
from promptsmith.storage import load_session, save_session
from promptsmith.m1 import m1_system_prompt
from promptsmith.workflow import Phase12Workflow
from promptsmith.api import ApiConfig, ApiResult, client_for_config
from tests.test_m1_model_authority_v11 import _base
from tests.test_conversation_workspace import app, install_session
from promptsmith.web_workspace import WorkspaceController


LAYOUT_QUESTION = "在功能和交互保持不变的前提下，布局结构和控件排布是否也可以调整，还是只改颜色、字体、间距等外观、保持现有布局不动？"


def layout_session(*, question_text=LAYOUT_QUESTION, with_shortcuts=False):
    session = SessionState.new()
    session.set_task("重新设计Python tkinter的软件UI，保留功能，优化布局和样式。")
    payload = build_m1_input(session, "first-layout")
    result = _base(payload)
    result["category"]["primary"] = "coding"
    result["gaps"] = [{"gap_id": "g-layout", "field": "features", "scope": "布局改动范围",
                       "description": "布局结构和控件排布是否允许调整", "importance": "can_defer",
                       "origin": "missing", "source_refs": [], "depends_on": []}]
    result["questions"] = [{"question_id": "q-layout", "gap_id": "g-layout", "field": "features",
                            "scope": "布局改动范围", "text": question_text, "options": [],
                            "reason": "明确改动范围", "depends_on": []}]
    result["next_action"] = "ask"
    if with_shortcuts:
        result["gaps"].append({**result["gaps"][0], "gap_id": "g-shortcuts", "description": "是否保留快捷键"})
        result["questions"].append({**result["questions"][0], "gap_id": "g-shortcuts",
                                    "question_id": "q-shortcuts", "text": "是否保留Ctrl+S快捷键？"})
    parsed = parse_m1_response(json.dumps(result, ensure_ascii=False), payload, M1Assets.load().output_schema)
    apply_m1_response(session, payload, parsed)
    return session


def test_waiting_confirmation_checks_do_not_append_logs_or_mutate_state(caplog):
    session = layout_session()
    before = deepcopy(session.to_dict())
    caplog.clear()
    with caplog.at_level("DEBUG"):
        for _ in range(100):
            with pytest.raises(SessionStateError, match="逐项回答或跳过"):
                session.validate_unknown_reviews()
    assert session.to_dict() == before
    assert not caplog.records, "Polling must not create fake repeated events in Debug."


def test_real_answer_still_logs_once_when_waiting_projection_is_quiet(caplog):
    session = layout_session()
    caplog.clear()
    with caplog.at_level("INFO"):
        session.record_question("q-layout", "answered", "布局结构和控件排布可以调整")
    events = [r for r in caplog.records if "User question decision" in r.getMessage()]
    assert len(events) == 1
    assert session.question_history[-1]["answer_text"] == "布局结构和控件排布可以调整"


def unresolved_layout_result(payload, *, wording=None):
    answer = next(row for row in reversed(payload["state"]["question_history"]) if row.get("gap_id") == "g-layout")
    result = _base(payload)
    result["category"]["primary"] = "coding"
    result["gaps"] = deepcopy(payload["state"]["gaps"])
    result["gap_updates"] = [{"update_id": "u-layout", "target_gap_id": "g-layout", "answer_id": answer["answer_id"],
                              "action": "unresolved", "remaining_description": "布局是否允许调整尚不明确",
                              "source_ref": {"source_id": answer["answer_source_id"], "quote": answer["answer_text"]},
                              "reason": "用户回答中仍包含是否，需要核对其意思"}]
    result["questions"] = [{"question_id": "q-layout-again", "gap_id": "g-layout", "field": "features",
                            "scope": "布局改动范围",
                            "text": wording or "这次改版的范围是只改颜色、字体、间距等外观，还是布局结构和控件排布也可以调整？",
                            "options": [], "reason": "确认范围", "depends_on": []}]
    result["next_action"] = "ask"
    return result


@pytest.mark.parametrize("wording", [None, LAYOUT_QUESTION])
def test_ambiguous_answer_gets_a_targeted_clarification_instead_of_repeating_original(wording, tmp_path, caplog):
    session = layout_session()
    session.record_question("q-layout", "answered", "布局结构和控件排布是否也可以调整")
    payload = build_m1_input(session, "summary-layout")
    raw = unresolved_layout_result(payload, wording=wording)
    before = deepcopy(raw)
    with caplog.at_level("INFO"):
        result = parse_m1_response(json.dumps(raw, ensure_ascii=False), payload,
                                   M1Assets.load().output_schema, incremental=True)
        apply_m1_response(session, payload, result)
    question = session.questions_for_review()[0]
    assert question["text"] != raw["questions"][0]["text"]
    assert "上一条回答" in question["text"] and "具体决定" in question["text"]
    assert "还是" not in question["text"]
    assert len(session.gaps) == 1  # Ambiguity is not silently resolved.
    assert session.confirmed_requirements_version is None
    assert session.question_history[-1]["answer_text"] == "布局结构和控件排布是否也可以调整"
    assert session.question_history[-1]["assessment_action"] == "unresolved"
    assert raw == before
    assert load_session(save_session(session, tmp_path / "clarification.json")).questions_for_review() == session.questions_for_review()
    assert "Repeated interview question converted" in caplog.text


@pytest.mark.parametrize("text", [
    "菜单入口是否需要保留在主窗口顶部？",
    "在功能和交互保持不变的前提下，针对手机端，布局结构和控件排布是否也可以调整，还是只改颜色、字体、间距等外观、保持现有布局不动？",
    "在功能和交互保持不变的前提下，布局结构和控件排布调整后，原有快捷键和交互是否也可以调整，还是只改颜色、字体、间距等外观？",
])
def test_genuinely_new_detail_in_same_scope_remains_a_new_question(text):
    session = layout_session()
    session.record_question("q-layout", "answered", "布局可以调整，但请保留菜单功能")
    payload = build_m1_input(session, "new-detail")
    raw = unresolved_layout_result(payload, wording=text)
    result = parse_m1_response(json.dumps(raw, ensure_ascii=False), payload,
                               M1Assets.load().output_schema, incremental=True)
    apply_m1_response(session, payload, result)
    assert session.questions_for_review()[0]["text"] == text


def test_lightly_rephrased_same_decision_is_clarified_without_reasking_it():
    session = layout_session(question_text="是否允许调整布局结构和控件排布？")
    session.record_question("q-layout", "answered", "布局可能可以改，具体还没想好")
    payload = build_m1_input(session, "same-decision-reworded")
    raw = unresolved_layout_result(payload, wording="布局结构和控件排布可以修改吗？")
    result = parse_m1_response(json.dumps(raw, ensure_ascii=False), payload,
                               M1Assets.load().output_schema, incremental=True)
    apply_m1_response(session, payload, result)
    assert "上一条回答" in session.questions_for_review()[0]["text"]
    assert len(session.gaps) == 1 and session.confirmed_requirements_version is None


def test_a_repeated_original_question_refers_to_the_latest_answer():
    session = layout_session()
    session.record_question("q-layout", "answered", "布局结构和控件排布是否也可以调整")
    payload = build_m1_input(session, "first-clarification")
    raw = unresolved_layout_result(payload)
    apply_m1_response(session, payload, parse_m1_response(json.dumps(raw, ensure_ascii=False), payload,
                      M1Assets.load().output_schema, incremental=True))
    session.record_question("q-layout-again", "answered", "主要窗口布局可以改，插件窗口还不确定")
    payload = build_m1_input(session, "second-clarification")
    raw = unresolved_layout_result(payload)
    raw["questions"][0]["question_id"] = "q-layout-again-2"
    apply_m1_response(session, payload, parse_m1_response(json.dumps(raw, ensure_ascii=False), payload,
                      M1Assets.load().output_schema, incremental=True))
    assert "主要窗口布局可以改，插件窗口还不确定" in session.questions_for_review()[0]["text"]


def test_clarifying_one_gap_never_quotes_another_gap_in_the_same_scope():
    session = layout_session(with_shortcuts=True)
    answer = "布局结构和控件排布是否也可以调整"
    session.record_question("q-layout", "answered", answer)
    session.record_question("q-shortcuts", "answered", "保留Ctrl+S快捷键")
    payload = build_m1_input(session, "parallel-gaps")
    raw = unresolved_layout_result(payload)
    shortcut = payload["state"]["question_history"][-1]
    raw["gap_updates"].append({"update_id": "u-shortcuts", "target_gap_id": "g-shortcuts",
                              "answer_id": shortcut["answer_id"], "action": "resolved",
                              "remaining_description": None, "reason": "用户明确保留",
                              "source_ref": {"source_id": shortcut["answer_source_id"], "quote": shortcut["answer_text"]}})
    raw["gaps"] = [g for g in raw["gaps"] if g["gap_id"] != "g-shortcuts"]
    apply_m1_response(session, payload, parse_m1_response(json.dumps(raw, ensure_ascii=False), payload,
                      M1Assets.load().output_schema, incremental=True))
    text = next(q["text"] for q in session.questions_for_review() if q["gap_id"] == "g-layout")
    assert answer in text and "Ctrl+S" not in text


@pytest.mark.parametrize("original,text", [
    ("新布局每行放2个输入框、每列放3个按钮，还是沿用现有窗口和控件排布并保持原有交互不变？",
     "新布局每行放3个输入框、每列放2个按钮，还是沿用现有窗口和控件排布并保持原有交互不变？"),
    ("是否允许调整布局结构和控件排布，还是不允许改变原有快捷键和交互并保持现有窗口外观不变？",
     "是否不允许调整布局结构和控件排布，还是允许改变原有快捷键和交互并保持现有窗口外观不变？"),
    ("是否不允许调整布局结构和控件排布，还是只修改颜色字体间距等现有外观并保留原有菜单？",
     "是否允许调整布局结构和控件排布，还是只修改颜色字体间距等现有外观并保留原有菜单？"),
])
def test_new_decisions_keep_numbers_and_negations_attached_to_their_objects(original, text):
    session = layout_session(question_text=original)
    session.record_question("q-layout", "answered", "还未确定具体布局安排")
    payload = build_m1_input(session, "changed-choices")
    raw = unresolved_layout_result(payload, wording=text)
    apply_m1_response(session, payload, parse_m1_response(json.dumps(raw, ensure_ascii=False), payload,
                      M1Assets.load().output_schema, incremental=True))
    assert session.questions_for_review()[0]["text"] == text


@pytest.mark.parametrize("original,text", [
    ("是否允许调整布局结构和控件排布？", "调整布局结构和控件排布时需要适配手机端吗？"),
    ("是否可以调整整个窗口的布局结构和所有控件排布？", "是否可以调整整个窗口的布局结构和所有控件排布为两列？"),
])
def test_new_detail_sharing_the_original_topic_words_is_not_rewritten(original, text):
    session = layout_session(question_text=original)
    session.record_question("q-layout", "answered", "可以调整布局")
    payload = build_m1_input(session, "new-layout-detail")
    raw = unresolved_layout_result(payload, wording=text)
    result = parse_m1_response(json.dumps(raw, ensure_ascii=False), payload,
                               M1Assets.load().output_schema, incremental=True)
    apply_m1_response(session, payload, result)
    assert session.questions_for_review()[0]["text"] == text


def test_active_gap_projection_clarifies_repeated_wording_and_user_can_reopen(tmp_path):
    session = layout_session()
    session.record_question("q-layout", "answered", "布局结构和控件排布是否也可以调整")
    payload = build_m1_input(session, "local-projection")
    raw = unresolved_layout_result(payload)
    raw["questions"] = []
    raw["gaps"][0]["description"] = LAYOUT_QUESTION
    raw["gap_updates"][0]["remaining_description"] = LAYOUT_QUESTION
    raw["next_action"] = "pause_with_unknowns"
    apply_m1_response(session, payload, parse_m1_response(json.dumps(raw, ensure_ascii=False), payload,
                      M1Assets.load().output_schema, incremental=True))
    assert "上一条回答" in session.questions_for_review()[0]["text"]
    session = load_session(save_session(session, tmp_path / "local.json"))
    question = session.reopen_question("q-layout")
    assert question["text"] == LAYOUT_QUESTION and question["user_requested_reopen"] is True


def test_repeated_web_waiting_snapshots_do_not_log_confirmation_events(app, caplog):
    install_session(app, layout_session())
    view = WorkspaceController(app)
    before = deepcopy(app.session.to_dict())
    caplog.clear()
    with caplog.at_level("DEBUG", logger="promptsmith.session"):
        for _ in range(30):
            view.snapshot()
    assert app.session.to_dict() == before
    assert not [r for r in caplog.records if r.name == "promptsmith.session"]


@pytest.mark.parametrize("mode", ["full", "incremental", "compact_retry"])
def test_current_interview_instructions_fit_a_bounded_input_without_legacy_overlays(mode):
    prompt = m1_system_prompt(M1Assets.load().system_prompt, mode=mode)
    assert len(prompt.encode("utf-8")) < 15000
    assert "每次响应最多返回3个问题" not in prompt
    assert "最多3个" not in prompt
    assert "可给0—3个简短选项" not in prompt
    assert "即使值为0或false" not in prompt
    for rule in ("interview_rounds_remaining", "context_gap_ids", "逐字", "pending_interpretation",
                 "不设最低轮数", "不要求用户给本程序上传/粘贴实际文件", "skipped", "显式确认"):
        assert rule in prompt


@pytest.mark.parametrize("mode", ["full", "incremental", "compact_retry"])
def test_all_interview_modes_receive_the_coverage_level_definitions(mode):
    prompt = m1_system_prompt(M1Assets.load().system_prompt, mode=mode)
    assert "quick：目标" in prompt and "standard：补查" in prompt and "deep：再审视" in prompt
    assert "区别于模型接口的思考强度" in prompt


def test_request_cost_and_reasoning_usage_are_logged_once_per_actual_call(tmp_path, caplog):
    session = layout_session()
    payload = build_m1_input(session, "cost-request")
    raw = _base(payload)
    raw["category"]["primary"] = "coding"
    raw["gaps"] = deepcopy(payload["state"]["gaps"])
    raw["next_action"] = "pause_with_unknowns"
    workflow = Phase12Workflow(session, M1Assets.load(), tmp_path)

    class Client:
        def complete_json(self, _prompt, sent, schema):
            assert sent == payload
            assert schema == M1Assets.load().output_schema
            return ApiResult(json.dumps(raw, ensure_ascii=False), 256431,
                             {"prompt_tokens": 10766, "completion_tokens": 55622,
                              "completion_tokens_details": {"reasoning_tokens": 54075}},
                             "offline-cost", "deepseek-flash", finish_reason="stop")

    with caplog.at_level("DEBUG", logger="promptsmith.workflow"):
        outcome = workflow.invoke_m1(payload, Client(), protocol="offline", configured_model="deepseek-flash")
    starts = [r.getMessage() for r in caplog.records if "M1 request input cost" in r.getMessage()]
    ends = [r.getMessage() for r in caplog.records if "M1 request completed" in r.getMessage()]
    assert len(starts) == len(ends) == 1
    assert "system_bytes=" in starts[0] and "payload_bytes=" in starts[0] and "schema_bytes=" in starts[0]
    assert "latency_ms=256431" in ends[0] and "reasoning_tokens=54075" in ends[0]
    assert "answer_tokens=1547" in ends[0] and "finish=stop" in ends[0]
    assert session.task_text not in caplog.text
    assert outcome.api_result.content == json.dumps(raw, ensure_ascii=False)


@pytest.mark.parametrize("protocol", ["openai_chat_completions", "openai_responses", "anthropic_messages"])
@pytest.mark.parametrize("pending", [False, True])
def test_optimized_workflow_keeps_selected_max_effort_and_complete_request(protocol, pending, tmp_path, monkeypatch):
    session = layout_session()
    if pending:
        session.record_question("q-layout", "answered", "布局结构和控件排布是否也可以调整")
    payload = build_m1_input(session, "same-effort")
    response = unresolved_layout_result(payload) if pending else _base(payload)
    if not pending:
        response["category"]["primary"] = "coding"
        response["gaps"] = deepcopy(payload["state"]["gaps"])
        response["next_action"] = "pause_with_unknowns"
    config = ApiConfig("https://api.deepseek.com", "deepseek-flash", "synthetic-only",
                       protocol=protocol, reasoning_effort="max", max_tokens=65536)
    client = client_for_config(config)
    seen = []
    def respond(_endpoint, body, _headers):
        seen.append(body)
        text = json.dumps(response, ensure_ascii=False)
        if protocol == "openai_chat_completions":
            return {"choices": [{"finish_reason": "stop", "message": {"content": text}}]}, 1
        if protocol == "openai_responses":
            return {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}, 1
        return {"stop_reason": "end_turn", "content": [{"type": "text", "text": text}]}, 1
    monkeypatch.setattr(client, "_post_json", respond)
    outcome = Phase12Workflow(session, M1Assets.load(), tmp_path).invoke_m1(
        payload, client, protocol=protocol, configured_model=config.model)
    assert len(seen) == 1
    body = seen[0]
    assert body["max_output_tokens" if protocol == "openai_responses" else "max_tokens"] == 65536
    if protocol == "openai_chat_completions":
        assert body["thinking"] == {"type": "enabled"} and body["reasoning_effort"] == "max"
        sent = json.loads(body["messages"][1]["content"])
    elif protocol == "openai_responses":
        assert body["reasoning"] == {"effort": "max"}
        sent = json.loads(body["input"][0]["content"][-1]["text"])
    else:
        assert body["thinking"] == {"type": "enabled"} and body["output_config"]["effort"] == "max"
        sent = json.loads(body["messages"][0]["content"])
    assert sent == payload and client.config == config
    assert outcome.api_result.content == json.dumps(response, ensure_ascii=False)
