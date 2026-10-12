from __future__ import annotations

import gc
import json
import time
from copy import deepcopy
from threading import Event
from pathlib import Path
import tkinter as tk

import pytest

from promptsmith.api import ApiResult
from promptsmith.finalization import build_final_draft, confirm_final, edit_final_note, render_task_prompt
from promptsmith.delivery_workflow import DeliveryWorkflow
from promptsmith.skill_catalog import SkillCatalog, _record_hash
from promptsmith.storage import load_session
from promptsmith.ui import PromptSmithApp
from tests.test_final_delivery import confirmed_plan_session


@pytest.fixture
def delivery_app(tk_root, tmp_path, monkeypatch):
    window = tk.Toplevel(tk_root)
    window.withdraw()
    app = PromptSmithApp(window, session=confirmed_plan_session(), evidence_root=tmp_path)
    app.widgets["task_text"].insert("1.0", app.session.task_text)
    selected_category = next(
        (label for label, key in app.category_by_label.items() if key == app.session.selected_category),
        "自动判断",
    )
    app.category_var.set(selected_category)
    app.test_dialogs = []
    monkeypatch.setattr(
        "promptsmith.ui.messagebox.showerror",
        lambda *args, **kwargs: app.test_dialogs.append(("error", args)),
    )
    monkeypatch.setattr(
        "promptsmith.ui.messagebox.showinfo",
        lambda *args, **kwargs: app.test_dialogs.append(("info", args)),
    )
    monkeypatch.setattr(
        "promptsmith.ui.messagebox.showwarning",
        lambda *args, **kwargs: app.test_dialogs.append(("warning", args)),
    )
    monkeypatch.setattr("promptsmith.ui.messagebox.askyesno", lambda *args, **kwargs: False)
    yield app, window
    app.shutdown(wait=True)
    gc.collect()
    window.destroy()


def _candidate(*, candidate_id: str = "candidate-1", binding_id: str = "binding-1") -> tuple[dict, dict]:
    from promptsmith.skill_catalog import _default_catalog_path

    record = SkillCatalog.load(_default_catalog_path()).get("to-spec")
    assert record is not None
    capability = record["capabilities"][0]
    prerequisite_ids = [row["prerequisite_id"] for row in record["adaptation_prerequisites"]]
    candidate = {
        "candidate_id": candidate_id,
        "skill_id": "to-spec",
        "key_work_id": "k1",
        "record_hash": record["record_hash"],
        "record_snapshot": record,
        "step_ids": ["s1"],
        "capability_ids": [capability["capability_id"]],
        "usage_mode": "method_adaptation",
        "adaptation_prerequisite_ids": prerequisite_ids,
        "limitations": list(capability.get("limitations", [])),
        "compatibility": "compatible",
        "selection_allowed": True,
    }
    binding = {
        "binding_id": binding_id,
        "skill_id": "to-spec",
        "record_hash": record["record_hash"],
        "record_snapshot": record,
        "key_work_id": "k1",
        "step_ids": ["s1"],
        "usage_mode": "method_adaptation",
        "capability_ids": [capability["capability_id"]],
        "precondition_assessments": [
            {
                "prerequisite_id": prerequisite_id,
                "status": "unknown",
                "source": "catalog_evidence",
                "blocking": True,
            }
            for prerequisite_id in prerequisite_ids
        ],
    }
    return candidate, binding


class _DeliveryUiClient:
    def __init__(self, *, changes: list[dict] | None = None, response_override: dict | None = None,
                 entered: Event | None = None, release: Event | None = None):
        self.changes = deepcopy(changes or [])
        self.response_override = deepcopy(response_override)
        self.entered = entered
        self.release = release
        self.payloads: list[dict] = []

    def complete_json(self, _system_prompt: str, payload: dict, _schema: dict) -> ApiResult:
        self.payloads.append(deepcopy(payload))
        if self.entered:
            self.entered.set()
        if self.release:
            self.release.wait(timeout=5)
        if self.response_override is not None:
            result = self.response_override
        elif payload["schema_version"] == "m3.v0.1":
            candidate_work_ids = {row["key_work_id"] for row in payload["candidates"]}
            result = {
                "schema_version": "m3.v0.1",
                "request_id": payload["request_id"],
                "task_id": payload["task_id"],
                "status": "ok",
                "assessments": [
                    {
                        "candidate_id": row["candidate_id"],
                        "decision": "recommend",
                        "capability_ids": [row["capabilities"][0]["capability_id"]],
                        "reason": "该能力对应当前关键工作。",
                        "planned_inputs": ["当前任务背景"],
                        "expected_outputs": ["可复核结果"],
                        "prerequisite_ids": [],
                        "limitations": ["只适配方法，不执行原 Skill。"],
                    }
                    for row in payload["candidates"]
                ],
                "unmatched_key_work_ids": sorted(
                    row["key_work_id"]
                    for row in payload["key_work"]
                    if row["key_work_id"] not in candidate_work_ids
                ),
                "error": None,
            }
        else:
            result = self._m4_result(payload)
        return ApiResult(json.dumps(result, ensure_ascii=False), 3, {"input_tokens": 10}, "ui-stub", "ui-stub")

    def _m4_result(self, payload: dict) -> dict:
        changes_by_binding: dict[str, list[str]] = {row["binding_id"]: [] for row in payload["bindings"]}
        for change in self.changes:
            for binding_id in change["binding_ids"]:
                changes_by_binding[binding_id].append(change["change_id"])
        contributions = []
        for binding in payload["bindings"]:
            unresolved = [
                row["prerequisite_id"] for row in binding["prerequisite_assessments"]
                if row["status"] == "unknown" and row["blocking"]
            ]
            contributions.append({
                "binding_id": binding["binding_id"],
                "step_id": binding["step_ids"][0],
                "capability_ids": list(binding["capability_ids"]),
                "method_actions": ["按模型分析选择的办法逐步整理。"],
                "planned_inputs": ["当前任务背景"],
                "expected_outputs": ["模型整合后的工作草稿"],
                "checkpoints": ["核对每项需求和未知。"],
                "prerequisite_ids": unresolved,
                "fallback_actions": ["缺少前提时保留未知并使用无依赖的步骤。"],
                "proposed_change_ids": changes_by_binding[binding["binding_id"]],
            })
        return {
            "schema_version": "m4.v0.1",
            "request_id": payload["request_id"],
            "task_id": payload["task_id"],
            "status": "ok",
            "contributions": contributions,
            "proposed_changes": deepcopy(self.changes),
            "error": None,
        }


def _configure_delivery_client(app: PromptSmithApp, monkeypatch, client: _DeliveryUiClient) -> None:
    app.api_base_var.set("https://api.example.test")
    app.api_model_var.set("fixture-model")
    app.api_key_var.set("fixture-key")
    app.confirm_model_settings()
    monkeypatch.setattr(app, "_client", lambda _config: client)


def _pump_until(window: tk.Misc, predicate, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        window.update()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("UI 异步回调未在限定时间内完成。")


def _set_candidate_batch(app: PromptSmithApp, candidate: dict) -> None:
    app.session.set_skill_state(
        status="candidates_ready",
        basis=app._delivery_basis(),
        candidate_batch={
            "batch_id": "batch-ui-1",
            "catalog_hash": "b" * 64,
            "result": {"candidates": [candidate]},
        },
        bindings=[],
    )
    app.refresh()


def _set_binding(app: PromptSmithApp, candidate: dict, binding: dict) -> None:
    app.session.set_skill_state(
        status="selected",
        basis=app._delivery_basis(),
        candidate_batch={
            "batch_id": "batch-ui-1",
            "catalog_hash": "b" * 64,
            "result": {"candidates": [candidate]},
        },
        bindings=[binding],
    )
    app.refresh()


def _write_catalog_with_record_change(path, skill_id: str, *, remove: bool = False) -> None:
    import promptsmith.skill_catalog as catalog_module

    source = catalog_module._default_catalog_path()
    payload = json.loads(source.read_text(encoding="utf-8"))
    records = []
    for row in payload["records"]:
        if row["skill_id"] == skill_id and remove:
            continue
        row = dict(row)
        if row["skill_id"] == skill_id and not remove:
            row["description"] += "（外部更新）"
            row["record_hash"] = _record_hash(row)
        records.append(row)
    payload["records"] = records
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _select_to_spec_binding(app: PromptSmithApp, tmp_path) -> dict:
    from promptsmith.skill_catalog import _default_catalog_path

    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(_default_catalog_path().read_text(encoding="utf-8"), encoding="utf-8")
    app._catalog_path = catalog_path
    app.catalog = SkillCatalog.load(catalog_path)
    work = app.session.plan["content"]["key_work"][0]
    _set_software_spec_key_work(work)
    app.find_skills()
    _pump_until(app.root, lambda: not app._skill_search_busy)
    candidate = next(row for row in app._candidate_rows() if row["skill_id"] == "to-spec")
    app.widgets["skill_candidates_tree"].selection_set(candidate["candidate_id"])
    app.select_skill_candidates()
    return app.session.skill_state["bindings"][0]


def _set_software_spec_key_work(work: dict) -> None:
    work.update({
        "title": "为活动报名软件整理需求规格",
        "goal": "将已确认的软件需求、用户故事、实现决定和测试决定整理为可验证的规格文档",
        "inputs": ["已确认的软件需求", "范围边界"],
        "outputs": ["软件需求规格文档"],
        "checkpoints": ["每项需求都有来源及验收条件"],
    })


def _stage_confirmed_skill_draft(app: PromptSmithApp, binding: dict) -> None:
    from promptsmith.finalization import stage_final_draft

    prerequisite_ids = [
        row["prerequisite_id"]
        for row in binding["record_snapshot"].get("adaptation_prerequisites", [])
        if row.get("prerequisite_id")
    ]
    contribution = {
        "binding_id": binding["binding_id"],
        "origin_binding_ids": [binding["binding_id"]],
        "step_id": binding["step_ids"][0],
        "method_actions": ["按选定方法整理需求规格。"],
        "planned_inputs": ["已确认需求"],
        "expected_outputs": ["规格草稿"],
        "checkpoints": ["核对需求覆盖"],
        "prerequisite_ids": prerequisite_ids,
        "fallback_actions": ["前提未确认时保留原方案，不执行依赖方法的步骤。"],
    }
    draft = build_final_draft(app.session, selected_contributions=[contribution])
    stage_final_draft(app.session, draft, expected_basis=draft["basis"])
    confirm_final(app.session)


def test_explicit_candidate_analysis_uses_delivery_m3_workflow(delivery_app, monkeypatch) -> None:
    app, window = delivery_app
    candidate, _binding = _candidate()
    _set_candidate_batch(app, candidate)
    client = _DeliveryUiClient()
    _configure_delivery_client(app, monkeypatch, client)

    app.widgets["skill_analyze_button"].invoke()
    _pump_until(window, lambda: not app.delivery_busy)

    analysis = app.session.skill_state["candidate_batch"]["m3_analysis"]
    assert client.payloads[0]["schema_version"] == "m3.v0.1"
    assert analysis["result"]["assessments"][0]["candidate_id"] == candidate["candidate_id"]
    assert app.session.skill_state["bindings"] == []
    app.widgets["skill_candidates_tree"].selection_set(candidate["candidate_id"])
    app.select_skill_candidates()
    assert len(app.session.skill_state["bindings"]) == 1
    app.widgets["skill_integrate_button"].invoke()
    _pump_until(window, lambda: not app.delivery_busy)
    assert client.payloads[1]["schema_version"] == "m4.v0.1"
    assert app.session.final_result["generation_request_id"] == client.payloads[1]["request_id"]
    assert app.session.final_result["content"]["skill_contributions"][0]["method_actions"] == [
        "按模型分析选择的办法逐步整理。"
    ]


def test_m3_validation_failure_preserves_previous_analysis(delivery_app, monkeypatch) -> None:
    app, window = delivery_app
    candidate, _binding = _candidate()
    _set_candidate_batch(app, candidate)
    client = _DeliveryUiClient()
    _configure_delivery_client(app, monkeypatch, client)
    app.widgets["skill_analyze_button"].invoke()
    _pump_until(window, lambda: not app.delivery_busy)
    previous_analysis = deepcopy(app.session.skill_state["candidate_batch"]["m3_analysis"])

    client.response_override = {}
    app.widgets["skill_analyze_button"].invoke()
    _pump_until(window, lambda: not app.delivery_busy)

    assert app.session.skill_state["candidate_batch"]["m3_analysis"] == previous_analysis


def test_selected_prerequisite_is_updated_as_user_reported_before_m4(delivery_app, monkeypatch) -> None:
    app, window = delivery_app
    candidate, binding = _candidate()
    _set_binding(app, candidate, binding)
    client = _DeliveryUiClient()
    _configure_delivery_client(app, monkeypatch, client)

    app.widgets["skill_selected_tree"].selection_set(binding["binding_id"])
    app._show_selected_skill_binding()
    app.widgets["skill_prerequisites_tree"].selection_set(
        binding["precondition_assessments"][0]["prerequisite_id"]
    )
    app.widgets["skill_prerequisite_status_combo"].set("已满足")
    app.widgets["skill_update_prerequisite_button"].invoke()
    app.widgets["skill_integrate_button"].invoke()
    _pump_until(window, lambda: not app.delivery_busy)

    assessment = app.session.skill_state["bindings"][0]["precondition_assessments"][0]
    assert assessment["status"] == "satisfied"
    assert assessment["source"] == "user_reported"
    assert client.payloads[0]["schema_version"] == "m4.v0.1"
    assert client.payloads[0]["bindings"][0]["prerequisite_assessments"][0]["source"] == "user_reported"


def test_m4_missing_key_preserves_selected_binding_and_skip_path(delivery_app, monkeypatch) -> None:
    app, _window = delivery_app
    candidate, binding = _candidate()
    _set_binding(app, candidate, binding)
    app.api_key_var.set("")
    notices: list[tuple] = []
    monkeypatch.setattr("promptsmith.ui.messagebox.showinfo", lambda *args, **kwargs: notices.append(args))
    monkeypatch.setattr("promptsmith.ui.messagebox.showerror", lambda *args, **kwargs: notices.append(args))
    before_final = deepcopy(app.session.final_result)

    app.widgets["skill_integrate_button"].invoke()

    assert notices
    assert "API Key" in notices[-1][1]
    assert app.session.skill_state["status"] == "selected"
    assert app.session.skill_state["bindings"] == [binding]
    assert app.session.final_result == before_final
    app.widgets["skill_skip_button"].invoke()
    assert app.session.skill_state["status"] == "skipped"
    assert app.session.final_result["status"] == "draft"
    assert app.session.final_result["content"]["skill_contributions"] == []


def test_selected_binding_is_integrated_by_m4_and_changes_are_decided_individually(
    delivery_app, monkeypatch
) -> None:
    app, window = delivery_app
    candidate, binding = _candidate()
    _set_binding(app, candidate, binding)
    changes = [
        {
            "change_id": "change-extra-checklist",
            "binding_ids": [binding["binding_id"]],
            "kind": "scope",
            "description": "增加一份检查清单。",
            "reason": "让关键步骤便于复核。",
            "affects_hard_constraints": False,
        },
        {
            "change_id": "change-ignore-no-payment",
            "binding_ids": [binding["binding_id"]],
            "kind": "scope",
            "description": "忽略一项已确认的硬约束。",
            "reason": "测试硬约束边界。",
            "affects_hard_constraints": True,
        },
    ]
    client = _DeliveryUiClient(changes=changes)
    _configure_delivery_client(app, monkeypatch, client)

    app.widgets["skill_integrate_button"].invoke()
    _pump_until(window, lambda: not app.delivery_busy)

    final = app.session.final_result
    assert client.payloads[0]["schema_version"] == "m4.v0.1"
    assert final["generation_request_id"] == client.payloads[0]["request_id"]
    assert final["content"]["skill_contributions"][0]["method_actions"] == ["按模型分析选择的办法逐步整理。"]
    changes_tree = app.widgets["m4_changes_tree"]
    changes_tree.selection_set("change-extra-checklist")
    app._show_selected_m4_change()
    app.widgets["accept_m4_change_button"].invoke()
    assert app.session.final_result["content"]["accepted_additions"][-1]["source_change_id"] == "change-extra-checklist"
    remaining_m4 = [
        row for row in app.session.final_result["content"]["pending_changes"]
        if row.get("change_id")
    ]
    assert [row["change_id"] for row in remaining_m4] == ["change-ignore-no-payment"]
    assert app.session.final_result["review_required_ids"] == []

    changes_tree.selection_set("change-ignore-no-payment")
    app._show_selected_m4_change()
    assert str(app.widgets["accept_m4_change_button"].cget("state")) == "disabled"
    app.widgets["reject_m4_change_button"].invoke()
    hard_decision = next(
        row for row in app.session.final_result["change_decisions"]
        if row["change_id"] == "change-ignore-no-payment"
    )
    assert hard_decision["decision"] == "rejected"
    assert app.session.final_result["review_required_ids"] == []


def test_m4_partial_response_recovers_and_user_cancel_preserves_current_final(delivery_app, monkeypatch) -> None:
    app, window = delivery_app
    candidate, binding = _candidate()
    _set_binding(app, candidate, binding)
    client = _DeliveryUiClient()
    _configure_delivery_client(app, monkeypatch, client)
    app.widgets["skill_integrate_button"].invoke()
    _pump_until(window, lambda: not app.delivery_busy)
    previous_final = deepcopy(app.session.final_result)

    client.response_override = {}
    app.widgets["skill_integrate_button"].invoke()
    _pump_until(window, lambda: not app.delivery_busy)
    assert app.session.final_result["status"] == "draft"
    assert "to-spec" in app.session.final_result["canonical_body"]
    assert "尚未完整验证" in app.session.final_result["canonical_body"]
    assert app.session.final_archive[-1]["final_id"] == previous_final["final_id"]
    previous_final = deepcopy(app.session.final_result)

    entered, release = Event(), Event()
    client.response_override = None
    client.entered, client.release = entered, release
    app.widgets["skill_integrate_button"].invoke()
    assert entered.wait(timeout=2)
    app.widgets["skill_cancel_request_button"].invoke()
    assert app.session.final_result == previous_final
    release.set()
    _pump_until(window, lambda: app.completions.empty() and not app.delivery_busy)
    assert app.session.final_result == previous_final


def test_late_m3_response_after_session_switch_does_not_write_into_new_session(delivery_app, monkeypatch) -> None:
    app, window = delivery_app
    candidate, _binding = _candidate()
    _set_candidate_batch(app, candidate)
    entered, release = Event(), Event()
    client = _DeliveryUiClient(entered=entered, release=release)
    _configure_delivery_client(app, monkeypatch, client)
    old_token = app._session_instance_token

    app.widgets["skill_analyze_button"].invoke()
    assert entered.wait(timeout=2)
    monkeypatch.setattr("promptsmith.ui.messagebox.askyesno", lambda *args, **kwargs: True)
    app.new_session()
    assert app._session_instance_token != old_token
    assert app.delivery_workflow.session is app.session
    assert app.delivery_workflow.session_instance_token == app._session_instance_token
    release.set()
    _pump_until(window, lambda: app.completions.empty() and not app.delivery_busy)

    assert app.session.skill_state["candidate_batch"] is None


def test_open_session_rebuilds_delivery_workflow_with_new_instance_token(delivery_app, monkeypatch, tmp_path) -> None:
    app, _window = delivery_app
    old_token = app._session_instance_token
    path = tmp_path / "saved-session.json"
    from promptsmith.storage import save_session

    saved = confirmed_plan_session()
    save_session(saved, path)
    monkeypatch.setattr("promptsmith.ui.filedialog.askopenfilename", lambda **_kwargs: str(path))

    app.open_session()

    assert app._session_instance_token != old_token
    assert app.delivery_workflow.session is app.session
    assert app.delivery_workflow.session_instance_token == app._session_instance_token


def test_no_skill_ui_flow_confirms_saves_and_reopens_consistently(delivery_app, monkeypatch, tmp_path) -> None:
    app, _window = delivery_app
    path = tmp_path / "no-skill-session.json"
    app.widgets["skill_skip_button"].invoke()
    assert app.session.final_result["status"] == "draft"
    app.confirm_final_result()
    assert app.session.final_result["status"] == "confirmed"
    app.session_path = path

    app.save()
    assert path.exists(), (app.status_var.get(), app.test_dialogs)
    saved = load_session(path)
    monkeypatch.setattr("promptsmith.ui.filedialog.askopenfilename", lambda **_kwargs: str(path))
    app.open_session()

    assert app.session.final_result == saved.final_result
    assert app.session.skill_state["status"] == "skipped"
    assert app.session.final_result["content"]["skill_contributions"] == []


def test_cancel_binding_then_skip_removes_old_skill_content_and_preserves_independent_note(
    delivery_app, monkeypatch
) -> None:
    app, window = delivery_app
    candidate, binding = _candidate()
    _set_binding(app, candidate, binding)
    client = _DeliveryUiClient()
    _configure_delivery_client(app, monkeypatch, client)
    app.widgets["skill_integrate_button"].invoke()
    _pump_until(window, lambda: not app.delivery_busy)
    edit_final_note(app.session, "note-independent", "保留这条独立附注。")
    edit_final_note(
        app.session,
        "note-binding",
        "这条附注依赖所选方法。",
        depends_on_binding_ids=[binding["binding_id"]],
    )
    app.refresh()

    app.widgets["skill_selected_tree"].selection_set(binding["binding_id"])
    app.cancel_selected_skills()
    assert app.session.final_result["status"] == "stale"
    app.widgets["skill_skip_button"].invoke()

    final = app.session.final_result
    assert final["status"] == "draft"
    assert final["content"]["skill_contributions"] == []
    assert [row["text"] for row in final["content"]["user_notes"]] == ["保留这条独立附注。"]
    assert any(row.get("text") == "这条附注依赖所选方法。" for row in final["unapplied_edits"])


def test_task_prompt_preview_and_copy_actions_are_distinct_and_state_gated(delivery_app, monkeypatch) -> None:
    app, _window = delivery_app
    app.session.final_result = build_final_draft(app.session)
    copied: list[str] = []
    notices: list[tuple] = []
    monkeypatch.setattr(app.root, "clipboard_clear", lambda: None)
    monkeypatch.setattr(app.root, "clipboard_append", copied.append)
    monkeypatch.setattr("promptsmith.ui.messagebox.showinfo", lambda *args, **kwargs: notices.append(args))
    monkeypatch.setattr("promptsmith.ui.messagebox.askyesno", lambda *args, **kwargs: True)
    app.refresh()

    assert app.widgets["final_task_prompt_text"] is not app.widgets["final_preview_text"]
    body = app.session.final_result["canonical_body"]
    assert app.widgets["final_task_prompt_text"].get("1.0", "end-1c") == render_task_prompt(body, "neutral")
    assert str(app.widgets["copy_final_button"].cget("state")) == "disabled"
    assert str(app.widgets["copy_draft_button"].cget("state")) == "normal"

    app.copy_final_prompt()
    assert copied == []
    assert notices
    app.copy_draft_prompt()
    assert copied == [render_task_prompt(body, "neutral")]
    assert "草稿" in app.status_var.get()

    confirm_final(app.session)
    app.refresh()
    assert str(app.widgets["copy_final_button"].cget("state")) == "normal"
    app.copy_final_prompt()
    assert copied[-1] == render_task_prompt(body, "neutral")


def test_m2_suggestion_can_be_decided_individually(delivery_app) -> None:
    app, _window = delivery_app
    app.session.final_result = build_final_draft(app.session)
    app.refresh()

    tree = app.widgets["m2_suggestions_tree"]
    tree.selection_set("sg1")
    app.accept_selected_m2_suggestion()

    assert app.session.final_result["suggestion_decisions"][-1]["suggestion_id"] == "sg1"
    assert app.session.final_result["suggestion_decisions"][-1]["decision"] == "accepted"
    assert app.session.final_result["content"]["accepted_additions"][0]["source_suggestion_id"] == "sg1"
    assert app.session.final_result["status"] == "draft"


def test_high_impact_suggestion_routes_to_its_plan_section(delivery_app) -> None:
    app, _window = delivery_app
    app.session.plan["content"]["suggestions"][0]["requires_user_confirmation"] = True
    app.session.final_result = build_final_draft(app.session)
    app.refresh()
    tree = app.widgets["m2_suggestions_tree"]
    tree.selection_set("sg1")
    app._show_selected_m2_suggestion()

    assert str(app.widgets["accept_m2_suggestion_button"].cget("state")) == "disabled"
    assert str(app.widgets["process_m2_suggestion_button"].cget("state")) == "normal"
    app.process_selected_m2_suggestion()

    assert app.notebook.index(app.notebook.select()) == 1
    assert app.plan_section_var.get().startswith("系统建议")


def test_review_blocker_routes_to_existing_key_work_review_control(delivery_app) -> None:
    app, _window = delivery_app
    app.session.final_result = build_final_draft(app.session)
    app.session.final_result["status"] = "stale"
    app.session.plan["status"] = "draft"
    app.session.plan["pending_key_work_review_ids"] = ["k1"]
    app.refresh()

    blockers = app.widgets["final_review_items_tree"]
    assert "key_work:k1" in blockers.get_children()
    blockers.selection_set("key_work:k1")
    app.process_selected_final_review_item()

    assert app.notebook.index(app.notebook.select()) == 1
    assert app.widgets["plan_key_work_tree"].selection() == ("k1",)


def test_skill_details_show_inputs_outputs_and_prerequisite_state(delivery_app) -> None:
    app, _window = delivery_app
    candidate, binding = _candidate()
    app.session.set_skill_state(
        status="candidates_ready",
        basis=app._delivery_basis(),
        candidate_batch={"result": {"candidates": [candidate]}},
        bindings=[],
    )
    app.refresh()

    app.widgets["skill_candidates_tree"].selection_set(candidate["candidate_id"])
    app._show_selected_skill()
    candidate_detail = app.widgets["skill_details_text"].get("1.0", "end-1c")
    capability = binding["record_snapshot"]["capabilities"][0]
    prerequisite = binding["record_snapshot"]["adaptation_prerequisites"][0]
    assert f"输入：{capability['inputs'][0]}" in candidate_detail
    assert f"输出：{capability['outputs'][0]}" in candidate_detail
    assert prerequisite["description"] in candidate_detail

    app.session.set_skill_state(
        status="selected",
        basis=app._delivery_basis(),
        candidate_batch={"result": {"candidates": [candidate]}},
        bindings=[binding],
    )
    app.refresh()
    app.widgets["skill_selected_tree"].selection_set(binding["binding_id"])
    app._show_selected_skill_binding()
    binding_detail = app.widgets["skill_details_text"].get("1.0", "end-1c")
    assert f"输入：{capability['inputs'][0]}" in binding_detail
    assert f"输出：{capability['outputs'][0]}" in binding_detail
    assert "未知" in binding_detail
    assert "阻断" in binding_detail


def test_canceling_binding_clearly_marks_final_result_stale(delivery_app, monkeypatch) -> None:
    app, window = delivery_app
    errors: list[tuple] = []
    monkeypatch.setattr("promptsmith.ui.messagebox.showerror", lambda *args, **kwargs: errors.append(args))
    candidate, binding = _candidate()
    app.session.set_skill_state(
        status="selected",
        basis=app._delivery_basis(),
        candidate_batch={"result": {"candidates": [candidate]}},
        bindings=[binding],
    )
    app.refresh()
    client = _DeliveryUiClient()
    _configure_delivery_client(app, monkeypatch, client)
    app.integrate_selected_skills()
    _pump_until(window, lambda: not app.delivery_busy)
    assert not errors
    confirm_final(app.session)
    app.refresh()
    app.widgets["skill_selected_tree"].selection_set(binding["binding_id"])
    app.cancel_selected_skills()

    assert app.session.final_result["status"] == "stale"
    assert "过期" in app.final_status_var.get() or "需重建" in app.final_status_var.get()


def test_selected_catalog_record_change_marks_final_stale_and_blocks_confirmation(delivery_app, tmp_path) -> None:
    app, _window = delivery_app
    binding = _select_to_spec_binding(app, tmp_path)
    _stage_confirmed_skill_draft(app, binding)
    path = app._catalog_path
    _write_catalog_with_record_change(path, "to-spec")

    app.confirm_final_result()

    assert app.session.skill_state["status"] == "stale"
    assert app.session.skill_state["bindings"][0]["record_hash"] == binding["record_hash"]
    assert app.session.final_result["status"] == "stale"
    assert "目录记录已变化" in app.session.skill_state["last_error"]


def test_unrelated_catalog_record_change_keeps_selected_final_current(delivery_app, tmp_path) -> None:
    app, _window = delivery_app
    binding = _select_to_spec_binding(app, tmp_path)
    _stage_confirmed_skill_draft(app, binding)
    _write_catalog_with_record_change(app._catalog_path, "domain-modeling")

    app.confirm_final_result()

    assert app.session.skill_state["status"] == "selected"
    assert app.session.final_result["status"] == "confirmed"
    assert app.session.skill_state["bindings"][0]["record_hash"] == binding["record_hash"]


def test_unavailable_catalog_preserves_selected_snapshot_and_allows_explicit_skip(delivery_app, tmp_path) -> None:
    app, _window = delivery_app
    binding = _select_to_spec_binding(app, tmp_path)
    _stage_confirmed_skill_draft(app, binding)
    app._catalog_path.unlink()

    app.confirm_final_result()

    assert app.session.skill_state["status"] == "stale"
    assert app.session.skill_state["bindings"][0]["record_snapshot"] == binding["record_snapshot"]
    assert app.session.final_result["status"] == "stale"
    assert "待核验" in app.session.skill_state["last_error"]

    app.skip_skills()
    assert app.session.skill_state["status"] == "skipped"
    assert app.session.final_result["status"] == "draft"
    assert app.session.final_result["content"]["skill_contributions"] == []


@pytest.mark.parametrize("change", ["modify", "remove"])
def test_selected_skill_source_change_marks_final_stale(delivery_app, tmp_path, monkeypatch, change) -> None:
    app, _window = delivery_app
    binding = _select_to_spec_binding(app, tmp_path)
    _stage_confirmed_skill_draft(app, binding)

    source_root = tmp_path / "resource-root"
    source_path = source_root / binding["record_snapshot"]["source_path"]
    source_path.parent.mkdir(parents=True)
    original_source = Path(__file__).resolve().parents[1] / binding["record_snapshot"]["source_path"]
    source_path.write_bytes(original_source.read_bytes())
    monkeypatch.setattr("promptsmith.ui.resource_root", lambda: source_root)

    if change == "modify":
        source_path.write_text(source_path.read_text(encoding="utf-8") + "\n外部变更\n", encoding="utf-8")
    else:
        source_path.unlink()

    app.confirm_final_result()

    assert app.session.skill_state["status"] == "stale"
    assert app.session.final_result["status"] == "stale"
    assert app.session.skill_state["bindings"][0]["record_hash"] == binding["record_hash"]
    assert "本地来源文件" in app.session.skill_state["last_error"]


def test_selected_skill_catalog_only_runtime_keeps_final_current(delivery_app, tmp_path, monkeypatch) -> None:
    app, _window = delivery_app
    binding = _select_to_spec_binding(app, tmp_path)
    _stage_confirmed_skill_draft(app, binding)

    bundled_root = tmp_path / "bundled-root"
    catalog_dir = bundled_root / "resources" / "skill_catalog"
    catalog_dir.mkdir(parents=True)
    catalog_dir.joinpath("catalog_v0.1.json").write_text(
        app._catalog_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr("promptsmith.ui.resource_root", lambda: bundled_root)
    monkeypatch.setattr("sys._MEIPASS", str(bundled_root), raising=False)

    app.confirm_final_result()

    assert app.session.skill_state["status"] == "selected"
    assert app.session.final_result["status"] == "confirmed"
    assert app.session.skill_state["bindings"][0]["record_hash"] == binding["record_hash"]


def test_no_skill_final_does_not_depend_on_catalog_availability(delivery_app, tmp_path) -> None:
    app, _window = delivery_app
    _select_to_spec_binding(app, tmp_path)
    app.skip_skills()
    app.confirm_final_result()
    app._catalog_path.unlink()

    app.confirm_final_result()

    assert app.session.skill_state["status"] == "skipped"
    assert app.session.final_result["status"] == "confirmed"


def test_one_skill_can_be_selected_for_multiple_key_works(delivery_app) -> None:
    app, _window = delivery_app
    first = app.session.plan["content"]["key_work"][0]
    _set_software_spec_key_work(first)
    second = deepcopy(first)
    second.update({"key_work_id": "k2", "title": "为活动管理软件模块补充需求规格", "step_ids": ["s1"]})
    app.session.plan["content"]["key_work"].append(second)
    app.find_skills()
    _pump_until(app.root, lambda: not app._skill_search_busy)

    matching = [row for row in app._candidate_rows() if row["skill_id"] == "to-spec"]
    assert {row["key_work_id"] for row in matching} == {first["key_work_id"], "k2"}
    app.widgets["skill_candidates_tree"].selection_set(*(row["candidate_id"] for row in matching))
    app.select_skill_candidates()

    selected = [row for row in app.session.skill_state["bindings"] if row["skill_id"] == "to-spec"]
    assert {row["key_work_id"] for row in selected} == {first["key_work_id"], "k2"}


def test_complementary_skills_can_be_selected_for_one_key_work(delivery_app, monkeypatch) -> None:
    from promptsmith.local_skill_search import LocalSkillSearchResult

    monkeypatch.setattr("promptsmith.ui.discover_local_skill_candidates", lambda *_args, **_kwargs:
                        LocalSkillSearchResult("no_match", [], "fixture", 0, [], "fixture"))
    app, _window = delivery_app
    work = app.session.plan["content"]["key_work"][0]
    work.update({
        "title": "为校园活动报名软件整理需求规格和用户故事",
        "goal": "澄清领域模型实体关系，并定义目标提示的结束条件、停止边界和验收证据",
        "inputs": ["已确认的软件需求", "范围边界", "活动报名业务规则"],
        "outputs": ["软件需求规格文档", "领域模型实体关系说明", "可验证的目标提示"],
        "checkpoints": ["需求、领域关系和提示验收条件均可追溯"],
    })
    app.find_skills()
    _pump_until(app.root, lambda: not app._skill_search_busy)

    matching = [
        row for row in app._candidate_rows()
        if row["key_work_id"] == work["key_work_id"] and row.get("origin") != "local_file"
    ]
    assert {row["skill_id"] for row in matching} == {"to-spec", "domain-modeling", "goal-prompt"}
    app.widgets["skill_candidates_tree"].selection_set(*(row["candidate_id"] for row in matching))
    app.select_skill_candidates()

    selected = [row for row in app.session.skill_state["bindings"] if row["key_work_id"] == work["key_work_id"]]
    assert {row["skill_id"] for row in selected} == {"to-spec", "domain-modeling", "goal-prompt"}


def test_canceling_overwrite_confirmation_preserves_existing_export(delivery_app, monkeypatch, tmp_path) -> None:
    app, _window = delivery_app
    app.skip_skills()
    app.confirm_final_result()
    target = tmp_path / "existing.md"
    target.write_text("existing content", encoding="utf-8")
    monkeypatch.setattr("promptsmith.ui.filedialog.asksaveasfilename", lambda **_kwargs: str(target))
    confirmations = []
    monkeypatch.setattr(
        "promptsmith.ui.messagebox.askyesno",
        lambda *args, **kwargs: confirmations.append(args) or False,
    )

    app.export_final_markdown()

    assert confirmations
    assert target.read_text(encoding="utf-8") == "existing content"


def test_confirming_overwrite_replaces_existing_export(delivery_app, monkeypatch, tmp_path) -> None:
    app, _window = delivery_app
    app.skip_skills()
    app.confirm_final_result()
    target = tmp_path / "existing.md"
    target.write_text("existing content", encoding="utf-8")
    monkeypatch.setattr("promptsmith.ui.filedialog.asksaveasfilename", lambda **_kwargs: str(target))
    monkeypatch.setattr("promptsmith.ui.messagebox.askyesno", lambda *args, **kwargs: True)

    app.export_final_markdown()

    assert target.read_text(encoding="utf-8") != "existing content"
    assert "PromptSmith 最终交付" in target.read_text(encoding="utf-8")


def test_export_preserves_existing_file_if_session_changes_during_overwrite_confirmation(
    delivery_app, monkeypatch, tmp_path
) -> None:
    from promptsmith.finalization import edit_final_note

    app, _window = delivery_app
    app.skip_skills()
    app.confirm_final_result()
    target = tmp_path / "existing.md"
    target.write_text("existing content", encoding="utf-8")
    monkeypatch.setattr("promptsmith.ui.filedialog.asksaveasfilename", lambda **_kwargs: str(target))
    confirmations = []

    def confirm_after_session_edit(*args, **_kwargs):
        confirmations.append(args)
        edit_final_note(app.session, "note-during-overwrite-confirmation", "确认期间加入的附注")
        return True

    monkeypatch.setattr("promptsmith.ui.messagebox.askyesno", confirm_after_session_edit)

    app.export_final_markdown()

    assert confirmations
    assert target.read_text(encoding="utf-8") == "existing content"
    assert any(kind == "error" for kind, _args in app.test_dialogs)


def test_export_refuses_session_change_during_file_picker(delivery_app, monkeypatch, tmp_path) -> None:
    from promptsmith.finalization import edit_final_note

    app, _window = delivery_app
    app.skip_skills()
    target = tmp_path / "draft.md"

    def choose_after_edit(**_kwargs):
        edit_final_note(app.session, "note-during-dialog", "在文件选择期间修改的内容")
        return str(target)

    monkeypatch.setattr("promptsmith.ui.filedialog.asksaveasfilename", choose_after_edit)

    app.export_draft_markdown()

    assert not target.exists()
    assert any(kind == "error" for kind, _args in app.test_dialogs)


def test_pending_hard_m4_change_is_not_a_final_review_blocker(delivery_app) -> None:
    app, _window = delivery_app
    app.skip_skills()
    result = deepcopy(app.session.final_result)
    result["generation_request_id"] = "m4-review-run"
    result["content"]["pending_changes"] = [{
        "change_id": "change-review-target",
        "generation_request_id": "m4-review-run",
        "text": "增加一项方法建议。",
        "reason": "需要单独决定。",
        "kind": "scope",
        "decision": "pending",
        "affects_hard_constraints": True,
        "binding_ids": [],
    }]
    result["review_required_ids"] = ["m4-change:m4-review-run:change-review-target"]
    app.session.final_result = result
    app.refresh()

    assert app._final_review_lookup == {}
    assert app.widgets["final_review_items_tree"].get_children() == ()
    assert str(app.widgets["process_final_review_item_button"].cget("state")) == "disabled"
    app.widgets["m4_changes_tree"].selection_set("change-review-target")
    app._show_selected_m4_change()
    assert str(app.widgets["accept_m4_change_button"].cget("state")) == "disabled"
    assert str(app.widgets["reject_m4_change_button"].cget("state")) == "normal"


def test_direction_review_action_reveals_answer_field(delivery_app) -> None:
    app, window = delivery_app
    window.deiconify()
    window.geometry("1100x650")
    window.update()
    app.skip_skills()
    app.session.gaps.append({
        "gap_id": "gap-direction",
        "field": "deliverable",
        "scope": "最终交付",
        "importance": "blocking_direction",
        "description": "请说明最后希望交付的文件形式",
    })
    app.refresh()

    tree = app.widgets["final_review_items_tree"]
    tree.selection_set("gap:gap-direction")
    app._show_selected_final_review_item()
    source = app.widgets["process_final_review_item_button"]
    window.focus_force()
    source.focus_force()
    window.update()
    source.invoke()

    assert app.notebook.index(app.notebook.select()) == 0
    assert "最后希望交付的文件形式" in app.question_context_var.get()
    # A user-initiated supplement focuses the composer without creating
    # another interview question after the plan has already been generated.
    assert not app.session.questions_for_review()
    assert app.widgets["conversation_input"].get("1.0", "end-1c") == ""
    assert not app.session.final_result.get("confirmed_at")
    window.update()
    answer = app.widgets["conversation_input"]
    assert answer.winfo_ismapped()
    assert window.winfo_rooty() <= answer.winfo_rooty()
    assert answer.winfo_rooty() + answer.winfo_height() <= window.winfo_rooty() + window.winfo_height()
    assert window.focus_get() is answer


def test_noncritical_m4_change_is_absent_from_blocking_review_list(delivery_app) -> None:
    app, _window = delivery_app
    app.skip_skills()
    result = app.session.final_result
    result["generation_request_id"] = "m4-followup-run"
    result["content"]["pending_changes"] = [{
        "change_id": "change-followup",
        "generation_request_id": "m4-followup-run",
        "text": "补充术语核对记录。",
        "reason": "便于使用时核对。",
        "kind": "assumption",
        "decision": "pending",
        "affects_hard_constraints": False,
        "binding_ids": [],
    }]
    result["review_required_ids"] = ["m4-change:m4-followup-run:change-followup"]
    app.refresh()

    assert app._final_review_lookup == {}
    assert app.widgets["final_review_items_tree"].get_children() == ()


def test_m4_fallback_review_navigates_to_affected_binding_cancel(delivery_app) -> None:
    app, _window = delivery_app
    candidate, binding = _candidate()
    _set_binding(app, candidate, binding)
    _stage_confirmed_skill_draft(app, binding)
    result = app.session.final_result
    contribution = result["content"]["skill_contributions"][0]
    contribution["method_actions"] = []
    contribution["disabled_by_rejected_changes"] = [{
        "generation_request_id": "m4-review-run",
        "change_id": "change-without-fallback",
    }]
    result["review_required_ids"] = [
        "m4-fallback-required:m4-review-run:change-without-fallback"
    ]
    result["status"] = "draft"
    result["confirmed_revision"] = None
    app.refresh()

    review_id = next(iter(app._final_review_lookup))
    app.widgets["final_review_items_tree"].selection_set(review_id)
    app.process_selected_final_review_item()

    assert app.notebook.index(app.notebook.select()) == 2
    assert app.widgets["skill_selected_tree"].selection() == (binding["binding_id"],)
    assert str(app.widgets["skill_cancel_button"].cget("state")) == "normal"


def test_delivery_recovery_guidance_survives_refresh_and_tracks_selection(delivery_app) -> None:
    app, _window = delivery_app
    candidate, binding = _candidate()
    _set_binding(app, candidate, binding)
    message = "整合失败。下一步：用已选 Skill 直接生成提示词。"
    app._set_delivery_feedback(message)
    app.refresh()
    assert app.skill_status_var.get() == message
    assert app.widgets["skill_direct_button"].instate(["!disabled"])
    app.session.set_skill_state(status="skipped", basis=app._delivery_basis(), bindings=[])
    app.refresh()
    assert message not in app.skill_status_var.get()


def test_m4_missing_config_keeps_direct_generation_guidance(delivery_app, monkeypatch) -> None:
    app, _window = delivery_app
    candidate, binding = _candidate()
    _set_binding(app, candidate, binding)
    monkeypatch.setattr(app, "_missing_generation_config", lambda: ["模型"])
    app.integrate_selected_skills()
    app.refresh()
    assert "直接生成提示词" in app.skill_status_var.get()
    assert app.widgets["skill_direct_button"].instate(["!disabled"])


def test_m4_preparation_failure_keeps_guidance_and_full_traceback(delivery_app, monkeypatch, caplog) -> None:
    from promptsmith.delivery_workflow import DeliveryWorkflowError
    app, _window = delivery_app
    candidate, binding = _candidate()
    _set_binding(app, candidate, binding)
    _configure_delivery_client(app, monkeypatch, _DeliveryUiClient())

    def fail(*args, **kwargs):
        raise DeliveryWorkflowError("offline preparation failure")

    monkeypatch.setattr(app.delivery_workflow, "prepare_m4", fail)
    app.integrate_selected_skills()
    app.refresh()
    assert not app.delivery_busy
    assert "直接生成提示词" in app.skill_status_var.get()
    assert len(app.session.skill_state["bindings"]) == 1
    assert "Traceback" in caplog.text and "offline preparation failure" in caplog.text
