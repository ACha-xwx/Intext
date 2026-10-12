"""Explicit exclusions across interview, planning, export and saved sessions."""
import hashlib
import json
from copy import deepcopy

import pytest

from promptsmith.conversation import conversation_cards
from promptsmith.exporter import export_markdown
from promptsmith.finalization import build_final_draft, stage_final_draft, validate_current_final, render_canonical_body, _baseline
from promptsmith.m1 import M1Assets, build_m1_input, parse_m1_response
from promptsmith.m2 import M2Assets, apply_m2_response, build_m2_input
from promptsmith.storage import load_session, save_session
from tests.test_m2 import confirmed_session
from tests.test_m2_unknown_recovery import parse, unknown
from tests.test_m1_model_authority_v11 import _base
from tests.test_conversation_workspace import app, install_session
from tests.test_ui_refinement import show, pump
from tests.test_delivery_workflow import make_session
from promptsmith.delivery_workflow import DeliveryWorkflow


DESCRIPTION = "哪些页面先改、哪些页面后改尚未明确。"


def interview(importance="blocking_direction"):
    session = confirmed_session(with_unknown=False)
    session.confirmed_requirements_version = None
    session.gaps = [{"gap_id": "g-skip", "field": "scope", "scope": "页面改造顺序",
                     "description": DESCRIPTION, "importance": importance, "origin": "not_provided",
                     "source_refs": [], "depends_on": ["r1"]}]
    return session


def skip_and_confirm(importance="blocking_direction"):
    session = interview(importance)
    session.record_question(session.questions_for_review()[0]["question_id"], "skipped")
    assert session.confirmed_requirements_version is None
    session.confirm_requirements_preview(session.requirements_preview())
    return session


@pytest.mark.parametrize("importance", ["can_defer", "blocking_direction"])
def test_skip_is_excluded_from_confirm_preview_and_model_unknowns(importance, caplog):
    with caplog.at_level("INFO"):
        session = skip_and_confirm(importance)
    assert session.gaps[0]["origin"] == "user_skipped"  # History is retained.
    assert not session._blocking_gap_snapshot() and not session.plan_unresolved_items()
    assert not session.requirements_preview()["gaps"] and not session.requirements_preview()["draft_explanation"]
    assert not build_m1_input(session, "m1")["state"]["gaps"]
    payload = build_m2_input(session, "m2")
    assert not payload["unresolved_items"]
    assert payload["interview_context"][0]["disposition"] == "skipped"
    assert "Skipped question excluded" in caplog.text


def test_unsure_remains_a_real_unknown_and_draft_choice_keeps_it():
    session = interview("can_defer")
    session.record_question(session.questions_for_review()[0]["question_id"], "unsure")
    session.confirm_requirements_preview(session.requirements_preview())
    assert session.plan_unresolved_items()[0]["description"] == DESCRIPTION
    assert build_m2_input(session, "m2")["unresolved_items"]
    draft = interview()
    draft.confirm_requirements_preview(draft.requirements_preview(), allow_draft=True)
    assert draft.question_history[0]["disposition"] == "unsure"
    assert draft.current_draft_authorization()


def test_model_echo_and_saved_source_cannot_put_skipped_item_in_export(tmp_path, caplog):
    session = skip_and_confirm()
    with caplog.at_level("INFO"):
        payload, parsed, _ = parse(session, [unknown("echo", None, DESCRIPTION), unknown("valid", None, "实际部署权限未知。")])
        apply_m2_response(session, payload, parsed)
    assert DESCRIPTION not in str(session.plan["content"]["unresolved_items"])
    assert "Excluded skipped items from model plan" in caplog.text
    session.confirm_plan_preview(session.plan_preview())
    # An older snapshot with linked and unlinked copies is still filtered.
    session.plan["source_snapshot"]["unresolved_items"].append(deepcopy(session.gaps[0]))
    session.plan["content"]["unresolved_items"].append(unknown("old", "g-skip", DESCRIPTION))
    final = build_final_draft(session)
    assert DESCRIPTION not in final["canonical_body"]
    assert "实际部署权限未知" in final["canonical_body"]
    assert "用户选择先做草稿" not in final["canonical_body"]
    stage_final_draft(session, final)
    validate_current_final(session)
    path = export_markdown(session, tmp_path / "prompt.md", mode="draft")
    assert DESCRIPTION not in path.read_text(encoding="utf-8")
    reopened = load_session(save_session(session, tmp_path / "session.json"))
    validate_current_final(reopened)
    assert not reopened.questions_for_review(respect_interview_limit=False)


def test_reopening_and_answering_skipped_question_restores_context():
    session = skip_and_confirm()
    question_id = session.question_history[0]["question_id"]
    session.reopen_question(question_id)
    assert session.active_gaps()
    session.record_question(question_id, "answered", "全部页面一起改，顺序由下游AI安排。")
    assert session.active_gaps() and session.gaps[0]["origin"] == "ambiguous"
    assert session.confirmed_requirements_version is None
    assert session.question_history[-1]["answer_source_id"]


@pytest.mark.parametrize("legacy", [False, True])
def test_old_final_is_cleaned_once_preserves_original_history_and_unsure(tmp_path, caplog, legacy):
    session = skip_and_confirm()
    payload, parsed, _ = parse(session, [unknown("valid", None, "实际部署权限未知。")])
    apply_m2_response(session, payload, parsed)
    session.confirm_plan_preview(session.plan_preview())
    stage_final_draft(session, build_final_draft(session))
    before = deepcopy(session.final_result)
    if legacy:
        session.final_result["content"]["baseline"] = _baseline(session, legacy=True)
    baseline = session.final_result["content"]["baseline"]
    old_unknown = unknown("old", "g-skip", DESCRIPTION)
    session.plan["source_snapshot"]["unresolved_items"].append(deepcopy(session.gaps[0]))
    session.plan["content"]["unresolved_items"].append(deepcopy(old_unknown))
    baseline["unknown"].append(old_unknown)
    baseline["plan"]["unresolved_items"].append(old_unknown)
    baseline["draft_authorization"] = {"unresolved_items": deepcopy(session.gaps), "explanation": DESCRIPTION}
    session.final_result["canonical_body"] = render_canonical_body(session.final_result["content"])
    session.final_result["body_sha256"] = hashlib.sha256(session.final_result["canonical_body"].encode()).hexdigest()
    original = deepcopy(session.final_result)
    with caplog.at_level("INFO"):
        reopened = load_session(save_session(session, tmp_path / "old.json"))
    assert DESCRIPTION not in reopened.final_result["canonical_body"]
    assert "实际部署权限未知" in reopened.final_result["canonical_body"]
    assert reopened.final_archive[-1]["content"] == original["content"]
    assert reopened.final_result["revision"] == before["revision"] + 1
    assert reopened.final_result["recovery_notice"]
    assert "Removed skipped unknowns" in caplog.text
    validate_current_final(reopened)
    twice = load_session(save_session(reopened, tmp_path / "again.json"))
    assert twice.final_result["canonical_body"] == reopened.final_result["canonical_body"]
    assert len(twice.final_archive) == len(reopened.final_archive)
    twice.validate_plan()  # Historical raw plan/source stay mutually valid.
    edited = deepcopy(twice)
    deliverable = edited.plan["content"]["deliverables"][0]
    edited.edit_plan_section("deliverable", deliverable["deliverable_id"], {"name": "新的交付名称"})
    edited.confirm_plan_preview(edited.plan_preview())
    assert DESCRIPTION not in build_final_draft(edited)["canonical_body"]


@pytest.mark.parametrize("renamed", [False, True])
def test_m1_repeated_skipped_question_is_discarded_locally_without_retry(renamed):
    session = skip_and_confirm()
    payload = build_m1_input(session, "repeat")
    result = _base(payload)
    result["category"]["primary"] = "coding"
    result["gaps"] = [{**session.gaps[0], "origin": "missing"}]
    result["questions"] = [{"question_id": "echo", "gap_id": "g-skip", "field": "scope", "scope": "页面改造顺序",
                            "text": "请确认页面顺序？", "options": [], "reason": "顺序影响安排", "depends_on": []}]
    result["readiness"]["blocking_gap_ids"] = ["g-skip"]
    result["model_judgment"] = {"answer_assessment": "partial", "continue_interview": True,
                                "critical_gap_ids": ["g-skip"], "confidence": "high", "reason": "顺序未定"}
    result["next_action"] = "ask"
    if renamed:
        result["gaps"][0]["gap_id"] = "g-renamed"
        result["questions"][0]["gap_id"] = "g-renamed"
        result["readiness"]["blocking_gap_ids"] = ["g-renamed"]
        result["model_judgment"]["critical_gap_ids"] = ["g-renamed"]
    repairs = []
    parsed = parse_m1_response(json.dumps(result), payload, M1Assets.load().output_schema, normalization_report=repairs)
    assert not parsed["questions"] and not parsed["gaps"]
    assert parsed["next_action"] == "pause_with_unknowns"
    assert any(row["action"] == "exclude_user_skipped_followups" for row in repairs)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_result_options_stay_in_conversation_and_update_prompt(app, monkeypatch, theme, caplog):
    app.preferences["composer_theme"] = theme
    session = skip_and_confirm()
    payload, parsed, _ = parse(session, [])
    apply_m2_response(session, payload, parsed)
    session.confirm_plan_preview(session.plan_preview())
    install_session(app, session)
    stage_final_draft(session, build_final_draft(session))
    app.refresh()
    show(app)
    assert session.final_result["status"] == "draft"
    assert str(app._conversation_buttons["result_details"].cget("state")) == "normal"
    assert not any(card["kind"] in {"question", "interview_unknowns"} for card in conversation_cards(session))
    with caplog.at_level("DEBUG"):
        app._conversation_buttons["result_details"].invoke()
        pump(app, .5)
    assert app.notebook.index(app.notebook.select()) == 0
    assert app._workspace_popover.kind == "result"
    tone = app.widgets["conversation_final_tone"]
    app.final_tone_var.set("适度礼貌")
    tone.event_generate("<<ComboboxSelected>>")
    pump(app, .05)
    assert session.final_result["tone"] == "polite"
    monkeypatch.setattr("promptsmith.ui.simpledialog.askstring", lambda *a, **kw: "请优先复刻提供的组件。")
    app._conversation_buttons["add_final_note"].invoke()
    assert "请优先复刻提供的组件" in session.final_result["canonical_body"]
    assert app._workspace_popover.kind == "result" and app.notebook.index(app.notebook.select()) == 0
    assert "Final prompt note added" in caplog.text
    app._conversation_buttons["result_details"].invoke()
    assert app._workspace_popover is None


def test_active_prompts_distinguish_skip_and_unsure():
    assert "skipped 是用户排除的题" in M2Assets.load().system_prompt
    assert "unsure 才保留未知" in M2Assets.load().system_prompt


@pytest.mark.parametrize("stage", ["m3", "m4"])
def test_skill_analysis_inputs_and_direct_prompt_exclude_skipped_unknowns(stage, tmp_path):
    session = make_session(with_binding=stage == "m4")
    gap = {"gap_id": "g-skip", "field": "scope", "scope": "页面顺序", "description": DESCRIPTION,
           "importance": "blocking_direction", "origin": "user_skipped", "source_refs": [], "depends_on": []}
    session.gaps.append(gap)
    session.plan["content"]["unresolved_items"].append(unknown("echo", "g-skip", DESCRIPTION))
    workflow = DeliveryWorkflow(session, evidence_root=tmp_path / "offline")
    payload = getattr(workflow, "prepare_" + stage)("offline-" + stage, connection_version=1)
    assert DESCRIPTION not in json.dumps(payload, ensure_ascii=False)
    assert "仓库结构尚未提供" in json.dumps(payload, ensure_ascii=False)
    final = build_final_draft(session)
    assert DESCRIPTION not in final["canonical_body"]
    if stage == "m4":
        assert final["content"]["skill_contributions"]


def test_mixed_draft_authorization_removes_only_skipped_warning(tmp_path):
    session = interview()
    session.gaps.append({**deepcopy(session.gaps[0]), "gap_id": "g-unsure", "scope": "其它方向",
                         "description": "交付形式尚不确定。"})
    session.confirm_requirements_preview(session.requirements_preview(), allow_draft=True)
    # Compatibility: an older session recorded one skipped item after draft consent.
    session.gaps[0]["origin"] = "user_skipped"
    session.question_history.append({**session.question_history[0], "answer_id": "a3", "disposition": "skipped"})
    current = session.current_draft_authorization()
    assert current and DESCRIPTION not in current["explanation"]
    assert [row["gap_id"] for row in current["unresolved_items"]] == ["g-unsure"]
    assert load_session(save_session(session, tmp_path / "mixed.json")).current_draft_authorization() == current
