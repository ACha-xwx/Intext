from __future__ import annotations

import json
import time
import tkinter as tk
from threading import Event

import pytest

from promptsmith.api import ApiError, ApiResult
from promptsmith.finalization import edit_final_note
from promptsmith.session import SessionState
from promptsmith.storage import load_session, save_session
from promptsmith.ui import PromptSmithApp
from tests.test_final_delivery import confirmed_plan_session


def _pump_until(window: tk.Misc, predicate, timeout: float = 4.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        window.update()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("UI 异步回调未在限定时间内完成。")


def _m5_response(payload: dict) -> str:
    return json.dumps(
        {
            "schema_version": "m5.v0.1",
            "request_id": payload["request_id"],
            "task_id": payload["task_id"],
            "base_version": payload["base_version"],
            "status": "ok",
            "error": None,
            "example": {
                "dimension": "语气",
                "shared_assumptions": ["保持社团招新主题"],
                "option_a": "摄影社将于 2026-11-02 举办活动，联系人王老师。",
                "option_b": "欢迎加入摄影社，王老师将于 2026-11-02 带领大家体验。",
                "difference_summary": "B 更有号召感。",
                "unsupported_assumptions": ["日期和联系人均未由用户提供"],
            },
        },
        ensure_ascii=False,
    )


class _Client:
    def __init__(self, *, entered: Event | None = None, release: Event | None = None,
                 fail_text: bool = False):
        self.entered = entered
        self.release = release
        self.fail_text = fail_text
        self.m5_payloads: list[dict] = []
        self.text_calls: list[tuple[str, str, int]] = []

    def complete_json(self, _system_prompt: str, payload: dict, _schema: dict) -> ApiResult:
        self.m5_payloads.append(payload)
        if self.entered:
            self.entered.set()
        if self.release:
            self.release.wait(timeout=4)
        return ApiResult(_m5_response(payload), 7, {"total_tokens": 21}, "m5-ui-stub", "fixture")

    def complete_text(self, system_prompt: str, user_text: str, *, max_output_tokens: int = 512) -> ApiResult:
        self.text_calls.append((system_prompt, user_text, max_output_tokens))
        if self.entered:
            self.entered.set()
        if self.release:
            self.release.wait(timeout=4)
        if self.fail_text:
            raise ApiError("network", "fixture network failure", latency_ms=9)
        return ApiResult("本地 stub 生成的短文本结果。", 9, {"total_tokens": 13}, "trial-ui-stub", "fixture")


def _app(tk_root: tk.Tk, tmp_path, *, session: SessionState | None = None,
         client: _Client | None = None, monkeypatch=None):
    window = tk.Toplevel(tk_root)
    window.withdraw()
    app = PromptSmithApp(window, session=session or SessionState.new(), evidence_root=tmp_path / "runs")
    app.widgets["task_text"].delete("1.0", "end")
    app.widgets["task_text"].insert("1.0", app.session.task_text)
    app.api_base_var.set("https://api.example.test")
    app.api_model_var.set("fixture-model")
    app.api_key_var.set("fixture-key")
    stub = client or _Client()
    if monkeypatch is not None:
        monkeypatch.setattr(app, "_client", lambda _config: stub)
        monkeypatch.setattr("promptsmith.ui.messagebox.showerror", lambda *args, **kwargs: None)
        monkeypatch.setattr("promptsmith.ui.messagebox.showinfo", lambda *args, **kwargs: None)
        monkeypatch.setattr("promptsmith.ui.messagebox.showwarning", lambda *args, **kwargs: None)
        monkeypatch.setattr("promptsmith.ui.messagebox.askyesno", lambda *args, **kwargs: False)
    else:
        app._client = lambda _config: stub
    return app, window, stub


def _require_widgets(app: PromptSmithApp, names: tuple[str, ...]) -> None:
    missing = [name for name in names if name not in app.widgets]
    assert not missing, f"缺少 M5/试运行 UI 控件：{missing}"


@pytest.fixture
def m5_app(tk_root, tmp_path, monkeypatch):
    session = SessionState.new()
    session.set_task("为海风摄影社写一则招新通知；语气自然，不能虚构日期或联系人。")
    app, window, client = _app(tk_root, tmp_path, session=session, monkeypatch=monkeypatch)
    try:
        yield app, window, client
    finally:
        app.shutdown(wait=True)
        window.destroy()


def _generate_m5(app: PromptSmithApp, window: tk.Misc, client: _Client) -> dict:
    _require_widgets(
        app,
        (
            "m5_criterion_entry",
            "m5_generate_button",
            "m5_option_a_button",
            "m5_option_b_button",
            "m5_neither_button",
            "m5_skip_button",
            "m5_feedback_entry",
            "m5_feedback_button",
        ),
    )
    criterion = app.widgets["m5_criterion_entry"]
    criterion.delete(0, "end")
    criterion.insert(0, "语气")
    app.widgets["m5_generate_button"].invoke()
    _pump_until(window, lambda: bool(app.session.m5_examples) or app.session.m5_state["status"] == "error")
    assert app.session.m5_state["status"] == "ready"
    assert len(client.m5_payloads) == 1
    return client.m5_payloads[0]


def test_m5_uses_current_task_version_and_feedback_candidate_excludes_example_assumptions(
    m5_app,
) -> None:
    app, window, client = m5_app
    _require_widgets(app, ("proposals_tree",))
    task = "为海风摄影社写一则招新通知；语气自然，不能虚构日期或联系人。"
    app.widgets["task_text"].delete("1.0", "end")
    app.widgets["task_text"].insert("1.0", task)
    app.session.set_task(task)
    expected_version = app.session.requirement_version

    payload = _generate_m5(app, window, client)
    assert payload["task"]["text"] == task
    assert payload["base_version"] == expected_version
    assert app.session.m5_examples[0]["base_version"] == expected_version

    feedback = app.widgets["m5_feedback_entry"]
    feedback.insert(0, "B 的直接表达更合适，但不要口号。")
    app.widgets["m5_option_b_button"].invoke()
    app.widgets["m5_feedback_button"].invoke()

    proposals = app.session.pending_proposals
    assert len(proposals) == 1
    assert proposals[0]["source"] == "m5_feedback"
    assert proposals[0]["kind"] == "pending_interpretation"
    assert "B 的直接表达更合适，但不要口号" in proposals[0]["text"]
    assert "2026-11-02" not in proposals[0]["text"]
    assert "王老师" not in proposals[0]["text"]
    assert len(app.session.m5_feedback) == 1

    app.accept_all_proposals()
    assert len(app.session.requirements) == 1
    assert app.session.requirements[0]["confirmation"] == "pending"
    assert "B 的直接表达更合适" in app.session.requirements[0]["text"]
    assert "2026-11-02" not in app.session.requirements[0]["text"]
    assert "王老师" not in app.session.requirements[0]["text"]
    source_ref = app.session.requirements[0]["source_refs"][0]
    assert source_ref["quote"] == "B 的直接表达更合适，但不要口号。"
    assert any(source["source_id"] == source_ref["source_id"]
               and source["text"] == source_ref["quote"]
               for source in app.session.sources)
    path = app.evidence_root.parent / "m5-roundtrip.json"
    save_session(app.session, path)
    restored = load_session(path)
    assert restored.requirements == app.session.requirements
    assert restored.sources == app.session.sources
    assert len(restored.m5_examples) == len(restored.m5_feedback) == 1


@pytest.mark.parametrize("choice_widget", ["m5_neither_button", "m5_skip_button"])
def test_m5_neither_or_skip_records_no_requirement_proposal(m5_app, choice_widget: str) -> None:
    app, window, client = m5_app
    _generate_m5(app, window, client)
    app.widgets["m5_feedback_entry"].insert(0, "这两个例子都不合适。")

    app.widgets[choice_widget].invoke()
    app.widgets["m5_feedback_button"].invoke()

    assert app.session.pending_proposals == []
    assert len(app.session.m5_feedback) == 1
    assert app.session.m5_feedback[0]["candidate"] is None


def test_m5_response_after_session_switch_does_not_change_new_session(tk_root, tmp_path, monkeypatch) -> None:
    entered, release = Event(), Event()
    client = _Client(entered=entered, release=release)
    session = SessionState.new()
    session.set_task("为旧任务生成示例。")
    app, window, _ = _app(tk_root, tmp_path, session=session, client=client, monkeypatch=monkeypatch)
    try:
        _require_widgets(app, ("m5_criterion_entry", "m5_generate_button"))
        criterion = app.widgets["m5_criterion_entry"]
        criterion.insert(0, "语气")
        app.widgets["m5_generate_button"].invoke()
        assert entered.wait(timeout=2), "M5 请求没有进入 stub worker。"

        previous = app.session
        monkeypatch.setattr("promptsmith.ui.messagebox.askyesno", lambda *args, **kwargs: True)
        app.new_session()
        release.set()
        _pump_until(window, lambda: not app.busy)

        assert app.session is not previous
        assert app.session.m5_examples == []
        assert app.session.pending_proposals == []
        assert previous.m5_examples == []
    finally:
        release.set()
        app.shutdown(wait=True)
        window.destroy()


def test_trial_is_explicit_records_and_renders_output_without_changing_final(tk_root, tmp_path, monkeypatch) -> None:
    client = _Client()
    app, window, _ = _app(
        tk_root, tmp_path, session=confirmed_plan_session(), client=client, monkeypatch=monkeypatch
    )
    try:
        _require_widgets(app, ("trial_run_button", "trial_cancel_button", "trial_output_text"))
        app.skip_skills()
        app.generate_no_skill_final()
        app.confirm_final_result()
        final_revision = app.session.final_result["revision"]
        assert app.session.final_result["status"] == "confirmed"
        assert client.text_calls == []

        app.trial_tokens_var.set("128")
        app.widgets["trial_run_button"].invoke()
        _pump_until(window, lambda: bool(app.session.trial_runs))

        assert len(client.text_calls) == 1
        assert client.text_calls[0][2] == 128
        assert len(app.session.trial_runs) == 1
        assert app.session.trial_runs[0]["status"] == "completed"
        assert app.session.trial_runs[0]["final_revision"] == final_revision
        assert "本地 stub 生成的短文本结果" in app.widgets["trial_output_text"].get("1.0", "end")
        assert app.session.final_result["status"] == "confirmed"
        assert app.session.final_result["revision"] == final_revision
        assert app.session.requirements == confirmed_plan_session().requirements
    finally:
        app.shutdown(wait=True)
        window.destroy()


def test_late_trial_response_is_stale_and_failure_does_not_mutate_final(tk_root, tmp_path, monkeypatch) -> None:
    entered, release = Event(), Event()
    client = _Client(entered=entered, release=release)
    app, window, _ = _app(
        tk_root, tmp_path, session=confirmed_plan_session(), client=client, monkeypatch=monkeypatch
    )
    try:
        _require_widgets(app, ("trial_run_button", "trial_output_text"))
        app.skip_skills()
        app.generate_no_skill_final()
        app.confirm_final_result()
        app.widgets["trial_run_button"].invoke()
        assert entered.wait(timeout=2), "试运行请求没有进入 stub worker。"

        edit_final_note(app.session, "note-ui-trial", "补充本地演示的核对说明。")
        assert app.session.final_result["status"] == "draft"
        release.set()
        _pump_until(window, lambda: bool(app.session.trial_runs))
        assert app.session.trial_runs[-1]["status"] == "rejected_stale"
        assert app.session.final_result["status"] == "draft"
        assert "本地 stub 生成的短文本结果" not in app.widgets["trial_output_text"].get("1.0", "end")
    finally:
        release.set()
        app.shutdown(wait=True)
        window.destroy()

    failed_client = _Client(fail_text=True)
    failed_app, failed_window, _ = _app(
        tk_root, tmp_path, session=confirmed_plan_session(), client=failed_client, monkeypatch=monkeypatch
    )
    try:
        _require_widgets(failed_app, ("trial_run_button", "trial_output_text"))
        failed_app.skip_skills()
        failed_app.generate_no_skill_final()
        failed_app.confirm_final_result()
        before = failed_app.session.final_result.copy()
        failed_app.widgets["trial_run_button"].invoke()
        _pump_until(failed_window, lambda: bool(failed_app.session.trial_runs))

        assert failed_app.session.trial_runs[-1]["status"] == "failed"
        assert failed_app.session.final_result["status"] == before["status"] == "confirmed"
        assert failed_app.session.final_result["revision"] == before["revision"]
        assert failed_app.session.requirements == confirmed_plan_session().requirements
    finally:
        failed_app.shutdown(wait=True)
        failed_window.destroy()
