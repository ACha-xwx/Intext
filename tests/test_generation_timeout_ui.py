from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
import tkinter as tk

import pytest

from promptsmith.ui import PromptSmithApp
from tests.test_ui_reliability import base_result, envelope, pump


@pytest.fixture
def app(tk_root, tmp_path):
    window = tk.Toplevel(tk_root)
    window.withdraw()
    application = PromptSmithApp(window, evidence_root=tmp_path / "calls")
    application.api_base_var.set("https://example.invalid/v1")
    application.api_model_var.set("timeout-fixture")
    application.api_key_var.set("test-only-key")
    application.confirm_model_settings()
    yield application
    application.shutdown(wait=True)
    window.destroy()


def test_generation_and_probe_timeouts_are_independent(app, monkeypatch):
    assert app._api_config().timeout_seconds == 120
    assert app._model_directory_config().timeout_seconds == 15
    captured = []
    class ProbeClient:
        def test_connection(self):
            raise AssertionError("Probe should not run in this config-only check")
    monkeypatch.setattr(app, "_client", lambda config: (captured.append(config) or ProbeClient()))
    monkeypatch.setattr(app, "_submit", lambda *_args: None)
    app.test_connection()
    assert captured[0].timeout_seconds == 15
    assert app._api_config().timeout_seconds == 120


def jgs_response(payload):
    result = base_result(payload)
    result["category"] = {"primary": "learning", "secondary": [], "reason": "学生学习讲解。"}
    history = payload["state"]["question_history"]
    if not history:
        result["proposals"] = [{
            "proposal_id": "p-explain", "operation": "new", "target_item_id": None,
            "field": "deliverable", "text": "讲解JGS", "kind": "user_decision", "strength": "hard",
            "scope": "当前讲解", "source_refs": [{"source_id": payload["current_source_id"], "quote": "讲解JGS"}],
            "depends_on": [], "reason": "用户提出讲解任务。",
        }]
        result["gaps"] = [{
            "gap_id": f"g{index}", "field": field, "scope": "当前讲解", "description": description,
            "importance": "blocking_direction", "origin": "missing", "source_refs": [], "depends_on": [],
        } for index, field, description in [(1, "goal", "JGS所指领域未知"), (2, "audience", "讲解对象未知")]]
        result["questions"] = [{
            "question_id": f"q{index}", "gap_id": f"g{index}", "field": field, "scope": "当前讲解",
            "text": text, "options": [], "reason": "明确讲解方向。", "depends_on": [],
        } for index, field, text in [(1, "goal", "JGS是哪个领域的？"), (2, "audience", "讲解给谁学习？")]]
        result["readiness"]["blocking_gap_ids"] = ["g1", "g2"]
        result["next_action"] = "ask"
    else:
        result["gap_updates"] = [{
            "update_id": f"update-{row['answer_id']}", "target_gap_id": row["gap_id"],
            "answer_id": row["answer_id"], "action": "resolved",
            "source_ref": {"source_id": row["answer_source_id"], "quote": row["answer_text"]},
            "remaining_description": None, "reason": "用户已回答此项。",
        } for row in history]
    return result


def test_second_round_timeout_preserves_answers_then_explicit_retry_succeeds(app, tmp_path, monkeypatch):
    received = []
    slow_request_finished = threading.Event()
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            payload = json.loads(body["messages"][1]["content"])
            received.append({"body": body, "payload": payload})
            is_timeout_attempt = len(received) == 2
            if is_timeout_attempt:
                time.sleep(0.35)
            elif len(received) == 3:
                # Slower than the test's old short timeout, within the new 120s config.
                time.sleep(0.2)
            raw = envelope(jgs_response(payload))
            try:
                self.send_response(200)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            finally:
                if is_timeout_attempt:
                    slow_request_finished.set()
        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    messages = []
    monkeypatch.setattr("promptsmith.ui.messagebox.showerror", lambda *args, **_kwargs: messages.append(args))
    app.api_base_var.set(f"http://127.0.0.1:{server.server_port}")
    app.api_key_var.set("test-only-key")
    app.confirm_model_settings()
    default_config = app._api_config
    try:
        app.widgets["task_text"].insert("1.0", "讲解JGS")
        app.widgets["analyze_button"].invoke()
        pump(app.root, app)
        assert not messages
        assert len(app.session.pending_questions) == 2
        app.accept_all_proposals()
        for question, answer in [("q1", "数值分析里面的"), ("q2", "就是学生学习的讲解")]:
            app.widgets["questions_tree"].selection_set(question)
            app.answer_var.set(answer)
            app.record_question("answered")
        assert app.primary_action_var.get() == "继续整理回答"
        before = deepcopy(app.session.to_dict())
        monkeypatch.setattr(app, "_api_config", lambda: replace(default_config(), timeout_seconds=0.1))
        app.widgets["analyze_button"].invoke()
        assert app.busy and str(app.widgets["analyze_button"]["state"]) == "disabled"
        app.run_primary_action()
        app.start_analysis()
        app.widgets["analyze_button"].invoke()
        pump(app.root, app)
        assert slow_request_finished.wait(2)
        app.root.update()
        assert len(received) == 2  # No automatic retry, including after the late response.
        assert not app.busy and app.busy_kind is None
        assert str(app.widgets["analyze_button"]["state"]) == "normal"
        assert app.primary_action_var.get() == "重试分析"
        assert app.session.pending_requests == {}
        after = app.session.to_dict()
        # Only request tracking and diagnostics may change on failure.
        for key, value in before.items():
            if key not in {"updated_at", "api_runs", "errors", "pending_requests"}:
                assert after[key] == value, key
        assert app.session.api_runs[-1]["status"] == "timeout"
        assert app.session.api_runs[-1]["usage"] is None
        assert all(row["disposition"] == "answered" and row["assessment_status"] == "pending"
                   for row in received[1]["payload"]["state"]["question_history"])
        failed = next(path.parent for path in (tmp_path / "calls").rglob("check.json")
                      if json.loads(path.read_text(encoding="utf-8")).get("failure_kind") == "timeout")
        check = json.loads((failed / "check.json").read_text(encoding="utf-8"))
        metadata = json.loads((failed / "meta.json").read_text(encoding="utf-8"))
        assert check["schema"] == check["semantic"] == "not_reached"
        assert (failed / "response.raw.txt").read_bytes() == b""
        assert metadata["request_parameters"]["timeout_seconds"] == 0.1
        assert metadata["usage"] is None and metadata["latency_ms"] >= 90
        saved_input = json.loads((failed / "input.json").read_text(encoding="utf-8"))
        assert saved_input == received[1]["payload"]
        assert len(messages) == 1
        assert "需求分析等待超过0.1秒" in messages[0][1]
        assert "已有回答和需求已保留" in messages[0][1]
        failed_files = {path.name: path.read_bytes() for path in failed.iterdir()}

        monkeypatch.setattr(app, "_api_config", default_config)
        app.widgets["analyze_button"].invoke()  # User's explicit retry.
        pump(app.root, app)
        assert len(received) == 3 and len(messages) == 1
        assert received[1]["payload"]["request_id"] != received[2]["payload"]["request_id"]
        assert received[1]["payload"]["state"]["question_history"] == received[2]["payload"]["state"]["question_history"]
        assert not app.session.pending_requests and not app.busy
        assert not app.session.pending_questions and not app.session.gaps
        assert app.session.requirements == before["requirements"]
        assert app.session.api_runs[-1]["status"] == "accepted_as_candidate"
        checks = [json.loads(path.read_text(encoding="utf-8")) for path in (tmp_path / "calls").rglob("check.json")]
        assert sum(row["schema"] == row["semantic"] == "passed" for row in checks) == 2
        assert {path.name: path.read_bytes() for path in failed.iterdir()} == failed_files
        successful_meta = [json.loads(path.read_text(encoding="utf-8"))
                           for path in (tmp_path / "calls").rglob("meta.json")
                           if path.parent != failed]
        assert all(meta["request_parameters"]["timeout_seconds"] == 120 for meta in successful_meta)
        assert all(row["body"]["max_tokens"] == 8192 for row in received)
        (tmp_path / "verification_summary.json").write_text(json.dumps({
            "verification_kind": "offline_local_http_ui_second_round_timeout_and_manual_retry",
            "real_api_calls": 0, "local_requests": 3, "answers_preserved": True,
            "failure_schema": check["schema"], "failure_kind": check["failure_kind"],
            "short_timeout_seconds": 0.1, "normal_timeout_seconds": 120,
            "retry_schema_and_semantics_passed": True,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        server.shutdown()
        thread.join(timeout=2)
