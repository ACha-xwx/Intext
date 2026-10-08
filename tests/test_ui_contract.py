from __future__ import annotations

import tkinter as tk
import time
import json
import threading
import gc
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from promptsmith.api import ANTHROPIC_MESSAGES_PROTOCOL, OPENAI_RESPONSES_PROTOCOL, PROTOCOL_ID, ApiConfig
from promptsmith.session import SessionState
from promptsmith.storage import load_session
from promptsmith.ui import PROTOCOL_NAMES, STEP_SPECS, PromptSmithApp, api_config_summary
from tests.test_final_delivery import confirmed_plan_session
from tests.test_ui_delivery_interactions import _DeliveryUiClient, _pump_until


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "resources" / "prompts"


@pytest.fixture
def tk_window(tk_root):
    window = tk.Toplevel(tk_root)
    window.withdraw()
    yield window
    gc.collect()
    window.destroy()


def test_four_step_shell_exposes_the_final_delivery_phases() -> None:
    assert [step.title for step in STEP_SPECS] == ["输入与需求", "初始方案", "Skill 增强", "导出"]
    assert [step.enabled for step in STEP_SPECS] == [True, True, True, True]


def test_public_api_summary_never_contains_key() -> None:
    config = ApiConfig(
        base_url="https://api.deepseek.com",
        model="configured-model",
        api_key="sk-private",
    )

    summary = api_config_summary(config)

    assert summary == {
        "provider": "deepseek",
        "protocol": "openai_chat_completions",
        "base_url": "https://api.deepseek.com",
        "model": "configured-model",
        "timeout_seconds": 120,
    }
    assert "sk-private" not in repr(summary)


def test_ui_current_custom_service_and_protocol_select_real_m1_adapter(tmp_path, tk_window) -> None:
    payload_seen: dict = {}
    expected = json.loads((DESIGN / "examples" / "01_报名网站.expected.json").read_text(encoding="utf-8"))

    class ResponsesHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers["Content-Length"])
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            payload = json.loads(body["input"])
            payload_seen.update(path=self.path, authorization=self.headers.get("Authorization"), model=body["model"])
            result = json.loads(json.dumps(expected, ensure_ascii=False))
            for key in ("schema_version", "request_id", "task_id", "base_version"):
                result[key] = payload[key]
            result["gap_updates"] = []
            result["question_reopens"] = []
            response = {
                "id": "custom-responses-fixture",
                "model": body["model"],
                "status": "completed",
                "output": [
                    {"type": "reasoning", "summary": []},
                    {"type": "message", "content": [{"type": "output_text", "text": json.dumps(result, ensure_ascii=False)}]},
                ],
                "usage": {"input_tokens": 11, "output_tokens": 14},
            }
            raw = json.dumps(response, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format: str, *args) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), ResponsesHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    app = PromptSmithApp(tk_window, evidence_root=tmp_path)
    try:
        app.provider_var.set("My Custom Responses Service")
        app.protocol_var.set(PROTOCOL_NAMES[OPENAI_RESPONSES_PROTOCOL])
        app.api_base_var.set(f"http://127.0.0.1:{server.server_port}/v1")
        app.api_model_var.set("not-in-preset-model-47")
        app.api_key_var.set("service-responses-key")
        app.confirm_model_settings()
        app.widgets["task_text"].insert("1.0", "帮我做一个活动报名网站，不做付款。")

        app.start_analysis()
        deadline = time.time() + 5
        while app.busy and time.time() < deadline:
            tk_window.update()
            time.sleep(0.01)

        assert not app.busy
        assert len(app.session.pending_proposals) == 3
        assert payload_seen == {
            "path": "/v1/responses",
            "authorization": "Bearer service-responses-key",
            "model": "not-in-preset-model-47",
        }
        evidence = list(tmp_path.rglob("meta.json"))
        assert evidence
        request = json.loads(evidence[0].read_text(encoding="utf-8"))
        assert request["protocol"] == OPENAI_RESPONSES_PROTOCOL
        assert request["model"] == "not-in-preset-model-47"
        assert request["request_parameters"]["provider"] == "My Custom Responses Service"
    finally:
        app.shutdown(wait=True)
        server.shutdown()
        thread.join(timeout=2)


def test_ui_current_custom_service_and_protocol_select_real_m2_adapter(tmp_path, tk_window, monkeypatch) -> None:
    dialogs: list[tuple] = []
    monkeypatch.setattr("promptsmith.ui.messagebox.showerror", lambda *args, **_kwargs: dialogs.append(args))
    fixture = json.loads(
        (DESIGN / "examples_m2" / "01_报名网站.output.fixture.json").read_text(encoding="utf-8")
    )
    received: list[dict] = []

    class AnthropicHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers["Content-Length"])
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            payload = json.loads(body["messages"][0]["content"])
            received.append(
                {
                    "path": self.path,
                    "x_api_key": self.headers.get("x-api-key"),
                    "anthropic_version": self.headers.get("anthropic-version"),
                    "model": body["model"],
                    "max_tokens": body["max_tokens"],
                }
            )
            result = json.loads(json.dumps(fixture, ensure_ascii=False))
            for key in ("request_id", "task_id", "source_requirements_version"):
                result[key] = payload[key]
            response = {
                "id": "custom-anthropic-fixture",
                "type": "message",
                "role": "assistant",
                "model": body["model"],
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 12, "output_tokens": 24},
            }
            raw = json.dumps(response, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format: str, *args) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), AnthropicHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    session = SessionState.new()
    session.set_task("幫我做一個活動報名網站，不做付款。")
    session.selected_category = "coding"
    session.requirements = [
        {
            "item_id": item_id,
            "field": field,
            "text": text,
            "kind": "user_decision",
            "strength": "hard",
            "scope": "整体",
            "source_refs": [],
            "depends_on": [],
            "confirmation": "confirmed",
        }
        for item_id, field, text in (
            ("r1", "deliverable", "交付可演示网站"),
            ("r2", "constraints", "排除付款功能"),
            ("r3", "use_context", "按课堂演示场景控制深度"),
        )
    ]
    session.gaps = [
        {
            "gap_id": "g1",
            "field": "runtime",
            "scope": "部署方式",
            "description": "最终部署位置尚未决定。",
            "importance": "can_defer",
            "origin": "user_unsure",
            "source_refs": [],
            "depends_on": ["r1"],
        }
    ]
    session.analysis_basis_version = session.requirement_version
    session.confirm_requirements()
    app = PromptSmithApp(tk_window, session=session, evidence_root=tmp_path)
    try:
        # Mirror the state restored by the application's Open Session action.
        # _sync_input reads the editable task control before building M2 input.
        app.widgets["task_text"].insert("1.0", session.task_text)
        category_label = next(
            label for label, category in app.category_by_label.items()
            if category == session.selected_category
        )
        app.category_var.set(category_label)
        app.provider_var.set("My Custom Messages Service")
        app.protocol_var.set(PROTOCOL_NAMES[ANTHROPIC_MESSAGES_PROTOCOL])
        app.api_base_var.set(f"http://127.0.0.1:{server.server_port}/v1")
        app.api_model_var.set("custom-plan-model-abc")
        app.api_key_var.set("custom-messages-key")
        app.confirm_model_settings()

        app.start_plan_generation()
        deadline = time.time() + 5
        while app.busy and time.time() < deadline:
            tk_window.update()
            time.sleep(0.01)

        assert not app.busy
        assert app.session.plan["status"] == "draft", (
            f"status={app.status_var.get()!r}; errors={app.session.errors!r}; "
            f"dialogs={dialogs!r}; received={received!r}"
        )
        assert received == [
            {
                "path": "/v1/messages",
                "x_api_key": "custom-messages-key",
                "anthropic_version": "2023-06-01",
                "model": "custom-plan-model-abc",
                "max_tokens": 8192,
            }
        ]
        evidence = list(tmp_path.rglob("meta.json"))
        assert evidence
        request = json.loads(evidence[0].read_text(encoding="utf-8"))
        assert request["protocol"] == ANTHROPIC_MESSAGES_PROTOCOL
        assert request["model"] == "custom-plan-model-abc"
        assert request["request_parameters"]["provider"] == "My Custom Messages Service"
    finally:
        app.shutdown(wait=True)
        server.shutdown()
        thread.join(timeout=2)


def test_application_constructs_required_delivery_controls(tk_window) -> None:
    app = PromptSmithApp(tk_window)
    try:
        assert len(app.notebook.tabs()) == 5
        assert app.notebook.tab(1, "state") == "normal"
        assert app.notebook.tab(2, "state") == "disabled"
        assert app.notebook.tab(3, "state") == "disabled"
        assert app.notebook.tab(4, "state") == "normal"
        assert app.notebook.tab(4, "text") == "设置"
        for name in (
            "task_text",
            "category_combo",
            "analyze_button",
            "requirements_tree",
            "proposals_tree",
            "questions_tree",
            "api_key_entry",
            "plan_goal_text",
            "plan_steps_tree",
            "plan_key_work_tree",
            "generate_plan_button",
            "confirm_plan_button",
            "skill_candidates_tree",
            "skill_selected_tree",
            "skill_find_button",
            "skill_skip_button",
            "final_preview_text",
            "final_tone_combo",
        ):
            assert name in app.widgets
        assert app.widgets["api_key_entry"].cget("show") != ""
    finally:
        app.shutdown(wait=True)


def test_ui_no_skill_delivery_tone_export_and_save_reopen(tmp_path, tk_window, monkeypatch) -> None:
    session = confirmed_plan_session()
    exported = tmp_path / "delivery.md"
    saved = tmp_path / "session.json"
    app = PromptSmithApp(tk_window, session=session, evidence_root=tmp_path / "runs")
    try:
        app.widgets["task_text"].insert("1.0", session.task_text)
        app.category_var.set(next(label for label, value in app.category_by_label.items() if value == session.selected_category))
        assert app.notebook.tab(2, "state") == "normal"
        assert app.notebook.tab(3, "state") == "normal"

        app.skip_skills()
        assert app.session.skill_state["status"] == "skipped"
        assert app.session.final_result["status"] == "draft"
        revision = app.session.final_result["revision"]
        body_hash = app.session.final_result["body_sha256"]

        app.confirm_final_result()
        app.final_tone_var.set("适度礼貌")
        app.change_final_tone()
        assert app.session.final_result["status"] == "confirmed"
        assert app.session.final_result["revision"] == revision
        assert app.session.final_result["body_sha256"] == body_hash
        assert app.session.final_result["tone"] == "polite"
        assert "每天 30 分钟" in app.widgets["final_preview_text"].get("1.0", "end")

        monkeypatch.setattr("promptsmith.ui.filedialog.asksaveasfilename", lambda **_kwargs: str(exported))
        app.export_final_markdown()
        assert exported.exists()
        assert "最终任务提示" in exported.read_text(encoding="utf-8")

        monkeypatch.setattr("promptsmith.ui.filedialog.asksaveasfilename", lambda **_kwargs: str(saved))
        app.save(save_as=True)
        assert load_session(saved).final_result["confirmed_revision"] == revision

        app.final_tone_var.set("中性")
        app.change_final_tone()
        monkeypatch.setattr("promptsmith.ui.filedialog.askopenfilename", lambda **_kwargs: str(saved))
        app.open_session()
        assert app.session.final_result["status"] == "confirmed"
        assert app.session.final_result["tone"] == "polite"
        assert app.session.final_result["body_sha256"] == body_hash
        assert app.session.skill_state["status"] == "skipped"
    finally:
        app.shutdown(wait=True)


def test_ui_local_skill_can_be_selected_cancelled_and_integrated(tk_window, monkeypatch) -> None:
    session = confirmed_plan_session()
    session.plan["content"]["key_work"][0]["title"] = "为活动报名软件系统整理需求规格和用户故事"
    app = PromptSmithApp(tk_window, session=session)
    try:
        app.find_skills()
        _pump_until(tk_window, lambda: not app._skill_search_busy)
        candidate = next(row for row in app._candidate_rows() if row["skill_id"] == "to-spec")
        candidates_tree = app.widgets["skill_candidates_tree"]
        candidates_tree.selection_set(candidate["candidate_id"])
        app.select_skill_candidates()
        assert len(app.session.skill_state["bindings"]) == 1
        assert app.session.skill_state["status"] == "selected"

        binding = app.session.skill_state["bindings"][0]
        app.widgets["skill_selected_tree"].selection_set(binding["binding_id"])
        app.cancel_selected_skills()
        assert app.session.skill_state["bindings"] == []
        assert app.session.skill_state["status"] == "candidates_ready"

        candidates_tree.selection_set(candidate["candidate_id"])
        app.select_skill_candidates()
        app.api_base_var.set("https://api.example.test")
        app.api_model_var.set("fixture-model")
        app.api_key_var.set("fixture-key")
        app.confirm_model_settings()
        monkeypatch.setattr(app, "_client", lambda _config: _DeliveryUiClient())
        app.integrate_selected_skills()
        _pump_until(tk_window, lambda: not app.delivery_busy)
        assert app.session.final_result["status"] == "draft"
        contribution = app.session.final_result["content"]["skill_contributions"][0]
        assert contribution["origin_binding_ids"] == [app.session.skill_state["bindings"][0]["binding_id"]]
        assert app.notebook.select() == str(app.notebook.tabs()[3])
    finally:
        app.shutdown(wait=True)


def test_ui_skill_search_uses_confirmed_task_context(tk_window) -> None:
    session = confirmed_plan_session()
    session.task_text = "为社团活动报名工具整理可供开发者使用的需求规格与测试要点。"
    session.plan["content"]["key_work"] = [
        {
            "key_work_id": "k1",
            "title": "功能需求规格编写",
            "goal": "把成员和管理员功能整理为结构化需求。",
            "inputs": ["已确认需求", "范围边界"],
            "outputs": ["功能需求规格初稿"],
            "checkpoints": ["每项功能均有对应需求条目"],
            "step_ids": ["s1"],
        },
        {
            "key_work_id": "k2",
            "title": "测试要点编写",
            "goal": "为已确认的功能和规则整理可核对的测试要点。",
            "inputs": ["功能需求规格初稿"],
            "outputs": ["测试要点初稿"],
            "checkpoints": ["测试要点与需求条目一一对应"],
            "step_ids": ["s1"],
        },
        {
            "key_work_id": "k3",
            "title": "开发者可用性与演示标准复核",
            "goal": "复核规格和测试要点能否支撑开发者与比赛演示。",
            "inputs": ["需求规格", "测试要点"],
            "outputs": ["复核意见与修订稿"],
            "checkpoints": ["核心流程可支撑演示", "详略程度符合比赛定位"],
            "step_ids": ["s1"],
        },
    ]
    app = PromptSmithApp(tk_window, session=session)
    try:
        app.find_skills()
        _pump_until(tk_window, lambda: not app._skill_search_busy)

        candidates = [row for row in app._candidate_rows() if row["skill_id"] == "to-spec"]
        assert {row["key_work_id"] for row in candidates} == {"k1", "k2", "k3"}
        assert all("报名工具" in row["match_reason"] for row in candidates)
    finally:
        app.shutdown(wait=True)


def test_ui_rejects_skill_candidates_after_plan_basis_changes(tk_window, monkeypatch) -> None:
    session = confirmed_plan_session()
    session.plan["content"]["key_work"][0]["title"] = "为活动报名软件系统整理需求规格和用户故事"
    app = PromptSmithApp(tk_window, session=session)
    errors: list[tuple] = []
    monkeypatch.setattr("promptsmith.ui.messagebox.showerror", lambda *args, **_kwargs: errors.append(args))
    try:
        app.find_skills()
        _pump_until(tk_window, lambda: not app._skill_search_busy)
        candidate = app._candidate_rows()[0]
        app.widgets["skill_candidates_tree"].selection_set(candidate["candidate_id"])
        app.session.plan["plan_version"] += 1
        app.session.plan["confirmed_plan_version"] = app.session.plan["plan_version"]
        app.refresh()

        app.select_skill_candidates()
        app.integrate_selected_skills()
        assert app.session.skill_state["bindings"] == []
        assert str(app.widgets["skill_select_button"].cget("state")) == "disabled"
        assert len(errors) == 2
    finally:
        app.shutdown(wait=True)


def test_background_errors_are_delivered_to_ui_callback(tk_window) -> None:
    app = PromptSmithApp(tk_window)
    received: list[str] = []
    try:
        def fail():
            raise RuntimeError("background-failure")

        app._submit(fail, lambda _value: None, lambda exc: received.append(str(exc)))
        deadline = time.time() + 2
        while not received and time.time() < deadline:
            tk_window.update()
            time.sleep(0.01)

        assert received == ["background-failure"]
    finally:
        app.shutdown(wait=True)


def test_ui_runs_m1_over_background_http_and_stages_candidates(tmp_path, tk_window) -> None:
    expected_template = json.loads(
        (DESIGN / "examples" / "01_报名网站.expected.json").read_text(encoding="utf-8")
    )

    class M1Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers["Content-Length"])
            request_body = json.loads(self.rfile.read(length).decode("utf-8"))
            payload = json.loads(request_body["messages"][1]["content"])
            result = json.loads(json.dumps(expected_template, ensure_ascii=False))
            for key in ("schema_version", "request_id", "task_id", "base_version"):
                result[key] = payload[key]
            result["gap_updates"] = []
            result["question_reopens"] = []
            envelope = {
                "id": "local-fixture",
                "model": "fixture-model",
                "choices": [{"message": {"content": json.dumps(result, ensure_ascii=False)}}],
                "usage": {"total_tokens": 100},
            }
            raw = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format: str, *args) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), M1Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    app = PromptSmithApp(tk_window, evidence_root=tmp_path)
    try:
        app.api_base_var.set(f"http://127.0.0.1:{server.server_port}")
        app.api_model_var.set("fixture-model")
        app.api_key_var.set("fixture-key")
        app.confirm_model_settings()
        app.widgets["task_text"].insert("1.0", "帮我做一个活动报名网站，不做付款。")

        app.start_analysis()
        deadline = time.time() + 5
        while app.busy and time.time() < deadline:
            tk_window.update()
            time.sleep(0.01)

        assert app.busy is False
        assert len(app.session.pending_proposals) == 3
        assert app.session.pending_questions[0]["field"] == "use_context"
        assert list(tmp_path.rglob("response.raw.txt"))
    finally:
        app.shutdown(wait=True)
        server.shutdown()
        thread.join(timeout=2)
