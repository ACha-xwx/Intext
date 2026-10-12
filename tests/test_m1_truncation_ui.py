from __future__ import annotations

from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time

import pytest

from promptsmith.api import ApiError
from promptsmith.m1 import M1Assets, M1_INCREMENTAL_PROMPT_VERSION, m1_system_prompt
from tests.test_generation_timeout_ui import app, jgs_response
from tests.test_ui_reliability import envelope, pump


ROOT = Path(__file__).resolve().parents[1]
ANSWERS = [("q1", "数值分析里面的"), ("q2", "就是学生学习的讲解")]
DIAGNOSTIC_FIELDS = {"updated_at", "api_runs", "errors", "pending_requests"}
PARTIAL_JSON = '{"schema_version":"m1.v0.2","proposals":['
PARTIAL_USAGE = {"prompt_tokens": 1500, "completion_tokens": 8192, "total_tokens": 9692}


def _assert_preserved(before: dict, after: dict) -> None:
    for key, value in before.items():
        if key == "control":
            # New request traces are diagnostics; old traces and every other
            # persisted control field must remain intact on transport failure.
            for field, previous in value.items():
                if field == "response_traces":
                    assert after[key][field][:len(previous)] == previous
                else:
                    assert after[key][field] == previous, field
        elif key not in DIAGNOSTIC_FIELDS:
            assert after[key] == value, key


def _start_and_answer(app) -> None:
    app.widgets["task_text"].insert("1.0", "讲解JGS")
    app.widgets["analyze_button"].invoke()
    pump(app.root, app)
    assert len(app.session.pending_questions) == 2, app.status_var.get()
    app.accept_all_proposals()
    for question_id, answer in ANSWERS:
        # Set up answered-but-not-yet-analyzed state through SessionState;
        # the deleted tree UI is unrelated to the transport recovery seam.
        app.session.record_question(question_id, "answered", answer)
    app.refresh()
    assert app.primary_action_var.get() == "继续整理回答"
    assert app.session.pending_questions == []
    assert [row["answer_text"] for row in app.session.question_history] == [row[1] for row in ANSWERS]
    assert all(row["assessment_status"] == "pending" for row in app.session.question_history)


def _evidence_by_request(root: Path) -> dict[str, tuple[Path, dict, dict]]:
    result = {}
    for path in root.rglob("meta.json"):
        metadata = json.loads(path.read_text(encoding="utf-8"))
        check = json.loads((path.parent / "check.json").read_text(encoding="utf-8"))
        result[metadata["request_id"]] = (path.parent, metadata, check)
    return result


def _pump_idle(app, seconds: float = 0.15) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.root.update()
        time.sleep(0.01)


def _round_trip_through_ui(app, tmp_path, monkeypatch) -> None:
    app.session_path = tmp_path / "after-truncation.json"
    app.save()
    saved = deepcopy(app.session.to_dict())
    monkeypatch.setattr("promptsmith.ui.filedialog.askopenfilename", lambda **_kwargs: str(app.session_path))
    app.open_session()
    assert app.session.to_dict() == saved
    assert app.primary_action_var.get() == "重试分析"
    assert app._primary_action().kind == "retry_compact"
    assert not app.session.pending_requests and not app.busy


@pytest.mark.parametrize("retry_truncated", [False, True], ids=["retry-success", "retry-still-truncated"])
def test_second_round_truncation_preserves_answers_and_requires_explicit_compact_retry(
    app, tmp_path, monkeypatch, retry_truncated
):
    received = []
    request_entered = {2: threading.Event(), 3: threading.Event()}
    release_response = {2: threading.Event(), 3: threading.Event()}
    handler_errors = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                payload = json.loads(body["messages"][1]["content"])
                received.append({"body": body, "payload": payload})
                call = len(received)
                if call in request_entered:
                    request_entered[call].set()
                    assert release_response[call].wait(timeout=3), "测试没有释放本地截断响应。"
                if call == 2 or (call == 3 and retry_truncated):
                    raw = json.dumps({
                        "id": f"truncated-{call}", "model": "local-truncation-model",
                        "choices": [{"finish_reason": "length", "message": {"content": PARTIAL_JSON}}],
                        "usage": PARTIAL_USAGE,
                    }, ensure_ascii=False).encode("utf-8")
                else:
                    raw = envelope(jgs_response(payload))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            except Exception as exc:
                handler_errors.append(repr(exc))

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    messages = []
    monkeypatch.setattr("promptsmith.ui.messagebox.showerror", lambda *args, **_kwargs: messages.append(args))
    app.api_base_var.set(f"http://127.0.0.1:{server.server_port}")
    app.api_key_var.set("test-only-key")
    app.confirm_model_settings()
    try:
        _start_and_answer(app)
        assert not messages
        before = deepcopy(app.session.to_dict())

        app.widgets["analyze_button"].invoke()
        assert request_entered[2].wait(timeout=2)
        assert app.busy and str(app.widgets["analyze_button"]["state"]) == "disabled"
        app.run_primary_action()
        app.start_analysis()
        app.widgets["analyze_button"].invoke()
        assert len(received) == 2
        release_response[2].set()
        pump(app.root, app)
        _pump_idle(app)

        assert not handler_errors
        assert len(received) == 2  # No automatic retry after a completed truncated response.
        assert not app.busy and app.busy_kind is None
        assert str(app.widgets["analyze_button"]["state"]) == "normal"
        assert app.session.pending_requests == {}
        _assert_preserved(before, app.session.to_dict())
        assert app.primary_action_var.get() == "重试分析"
        assert app._primary_action().kind == "retry_compact"
        assert len(messages) == 1 and "截断" in messages[0][1]
        assert "回答" in messages[0][1] and "保留" in messages[0][1]
        assert app.session.api_runs[-1]["status"] == "truncated"
        assert app.session.api_runs[-1]["usage"] == PARTIAL_USAGE

        second_payload = received[1]["payload"]
        # The wire contract excludes local clarification/submission metadata;
        # full session preservation is checked independently above and below.
        allowed = M1Assets.load().input_schema["properties"]["state"]["properties"]["question_history"]["items"]["properties"]
        expected_history = [{key: value for key, value in row.items() if key in allowed}
                            for row in before["question_history"]]
        assert second_payload["state"]["question_history"] == expected_history
        assert second_payload["sources"] == before["sources"]
        failed, metadata, check = _evidence_by_request(tmp_path / "calls")[second_payload["request_id"]]
        assert check["failure_kind"] == "truncated"
        assert check["schema"] == check["semantic"] == "not_reached"
        assert (failed / "response.raw.txt").read_text(encoding="utf-8") == PARTIAL_JSON
        assert metadata["usage"] == PARTIAL_USAGE
        assert metadata["provider_response_id"] == "truncated-2"
        assert metadata["model"] == "local-truncation-model"
        assert metadata["request_mode"] == "incremental"
        assert metadata["prompt_version"] == M1_INCREMENTAL_PROMPT_VERSION
        incremental_prompt = m1_system_prompt(
            M1Assets.load().system_prompt,
            mode="incremental",
        )
        assert (failed / "system.txt").read_text(encoding="utf-8") == incremental_prompt
        failed_files = {path.name: path.read_bytes() for path in failed.iterdir()}

        _round_trip_through_ui(app, tmp_path, monkeypatch)
        _assert_preserved(before, app.session.to_dict())
        start_calls = []
        original_start = app.start_analysis

        def traced_start(*args, **kwargs):
            start_calls.append((args, kwargs))
            return original_start(*args, **kwargs)

        monkeypatch.setattr(app, "start_analysis", traced_start)
        app.widgets["analyze_button"].invoke()  # The user's single explicit compact retry.
        assert start_calls == [((), {"compact_retry": True})]
        assert request_entered[3].wait(timeout=2)
        assert app.busy
        app.run_primary_action()
        app.widgets["analyze_button"].invoke()
        assert len(received) == 3
        release_response[3].set()
        pump(app.root, app)
        _pump_idle(app)

        assert not handler_errors
        assert len(received) == 3
        assert not app.busy and app.busy_kind is None
        assert app.session.pending_requests == {}
        assert str(app.widgets["analyze_button"]["state"]) == "normal"
        retry_payload = received[2]["payload"]
        assert retry_payload["request_id"] != second_payload["request_id"]
        assert retry_payload["state"]["question_history"] == second_payload["state"]["question_history"]
        assert retry_payload["sources"] == before["sources"]
        retry_dir, retry_metadata, retry_check = _evidence_by_request(tmp_path / "calls")[retry_payload["request_id"]]
        assert retry_metadata["request_mode"] == "compact_retry"
        assert retry_metadata["prompt_version"] == M1_INCREMENTAL_PROMPT_VERSION
        assert (retry_dir / "system.txt").read_text(encoding="utf-8").startswith(incremental_prompt)
        assert (retry_dir / "system.txt").read_text(encoding="utf-8") != incremental_prompt
        assert all(row["body"]["max_tokens"] == 8192 for row in received)
        assert {path.name: path.read_bytes() for path in failed.iterdir()} == failed_files
        assert app.session.sources == before["sources"]

        if retry_truncated:
            _assert_preserved(before, app.session.to_dict())
            assert len(messages) == 2 and "截断" in messages[1][1]
            assert "模型" in messages[1][1] and "分批" in messages[1][1]
            assert retry_check["failure_kind"] == "truncated"
            assert retry_check["schema"] == retry_check["semantic"] == "not_reached"
            assert (retry_dir / "response.raw.txt").read_text(encoding="utf-8") == PARTIAL_JSON
            _round_trip_through_ui(app, tmp_path, monkeypatch)
        else:
            assert len(messages) == 1
            assert retry_check["schema"] == retry_check["semantic"] == "passed"
            assert app.session.api_runs[-1]["status"] == "accepted_as_candidate"
            assert app.session.requirements == before["requirements"]
            assert not app.session.gaps and not app.session.pending_questions
            assert all(row["assessment_status"] == "applied" for row in app.session.question_history)
            assert app._primary_action().kind != "retry_compact"

        (tmp_path / "verification_summary.json").write_text(json.dumps({
            "verification_kind": "offline_local_http_ui_truncation_and_explicit_compact_retry",
            "real_api_calls": 0, "local_requests": len(received),
            "retry_result": "truncated" if retry_truncated else "success",
            "answers_preserved_on_failure": True,
            "saved_session_retry_entry_preserved": True,
            "partial_response_retained_as_diagnostic_only": True,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        for event in release_response.values():
            event.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("failure_kind", ["json_error", "network", "timeout"])
def test_nontruncation_errors_recover_or_keep_distinct_failure_guidance(
    app, tmp_path, monkeypatch, caplog, failure_kind
):
    received = []
    malformed = '{"schema_version":'

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            payload = json.loads(body["messages"][1]["content"])
            received.append(payload)
            if len(received) == 1:
                raw = envelope(jgs_response(payload))
            else:
                raw = json.dumps({
                    "id": "malformed-completed", "model": "malformed-fixture",
                    "choices": [{"finish_reason": "stop", "message": {"content": malformed}}],
                    "usage": {"total_tokens": 30},
                }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *_args):
            pass

    class FailingClient:
        def __init__(self):
            self.calls = 0

        def complete_json(self, *_args):
            self.calls += 1
            if failure_kind == "timeout":
                raise ApiError("timeout", "fixture timeout", latency_ms=120001, timeout_seconds=120)
            raise ApiError("network", "无法连接模型接口，请检查网络。", latency_ms=20)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    messages = []
    monkeypatch.setattr("promptsmith.ui.messagebox.showerror", lambda *args, **_kwargs: messages.append(args))
    app.api_base_var.set(f"http://127.0.0.1:{server.server_port}")
    app.api_key_var.set("test-only-key")
    app.confirm_model_settings()
    try:
        _start_and_answer(app)
        before = deepcopy(app.session.to_dict())
        fake = FailingClient()
        if failure_kind != "json_error":
            monkeypatch.setattr(app, "_client", lambda _config: fake)
        app.widgets["analyze_button"].invoke()
        pump(app.root, app)
        _pump_idle(app)
        assert not app.busy and app.busy_kind is None
        assert app.session.pending_requests == {}
        if failure_kind == "json_error":
            # Program recovery may ask a new question, but cannot adopt the
            # malformed model output, lose answers, or confirm requirements.
            after = app.session.to_dict()
            for field in ("task_id", "task_text", "selected_category", "category_suggestion",
                          "requirements", "confirmed_requirements_version", "sources",
                          "question_history", "gaps", "plan", "skill_state", "final_result"):
                assert after[field] == before[field], field
            assert app.session.pending_questions
            assert app.session.last_model_judgment["answer_assessment"] == "unclear"
            assert "下一步问题" in app.status_var.get()
            assert app._primary_action().kind != "retry_compact"
            assert not messages and len(received) == 2
            last = app.session.api_runs[-1]
            recovered = Path(last["evidence_dir"])
            check = json.loads((recovered / "check.json").read_text(encoding="utf-8"))
            assert last["status"] == "accepted_as_candidate"
            assert check["valid"] and check["recovery_fallback"]["mode"] == "program_recovery"
            failures = check["recovery_fallback"]["previous_evidence_dirs"]
            assert len(failures) == 1
            for failed in map(Path, failures):
                failure_check = json.loads((failed / "check.json").read_text(encoding="utf-8"))
                assert failure_check["failure_kind"] == "json_error"
                assert (failed / "response.raw.txt").read_text(encoding="utf-8") == malformed
            effective = json.loads((recovered / "response.effective.json").read_text(encoding="utf-8"))
            assert effective["category"] == before["category_suggestion"]
            assert any(row.name == "promptsmith.runlog" and row.exc_info for row in caplog.records)
            return
        _assert_preserved(before, app.session.to_dict())
        assert app.primary_action_var.get() == "重试分析"
        assert app._primary_action().kind == "analyze_answer"
        assert app.session.api_runs[-1]["status"] == failure_kind
        assert app.session.errors[-1]["kind"] == failure_kind
        assert len(messages) == 1
        assert "截断" not in messages[0][1]
        last = app.session.api_runs[-1]
        failed = Path(last["evidence_dir"])
        check = json.loads((failed / "check.json").read_text(encoding="utf-8"))
        assert check["failure_kind"] == failure_kind
        assert fake.calls == 1 and len(received) == 1
        assert check["schema"] == check["semantic"] == "not_reached"
        assert (failed / "response.raw.txt").read_bytes() == b""
        assert "120" in messages[0][1] if failure_kind == "timeout" else "网络" in messages[0][1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
