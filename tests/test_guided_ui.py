from copy import deepcopy
import tkinter as tk

import pytest

from promptsmith.m1 import M1Assets, build_m1_input, parse_m1_response, apply_m1_response
from promptsmith.session import SessionState
from promptsmith.ui import PromptSmithApp
from tests.test_generation_timeout_ui import jgs_response
from tests.test_final_delivery import confirmed_plan_session
import json


@pytest.fixture
def app(tk_root, tmp_path, monkeypatch):
    root = tk.Toplevel(tk_root)
    root.withdraw()
    app = PromptSmithApp(root, evidence_root=tmp_path / 'calls')
    app.api_base_var.set('https://example.invalid/v1')
    app.api_model_var.set('fixture-model')
    app.api_key_var.set('test-key')
    app.confirm_model_settings()
    app.errors = []
    monkeypatch.setattr('promptsmith.ui.messagebox.showerror', lambda *a, **k: app.errors.append(a))
    yield app
    app.shutdown(wait=True)
    root.destroy()


def stage_jgs(app):
    app.widgets['task_text'].insert('1.0', '讲解JGS')
    app._sync_input()
    payload = build_m1_input(app.session, 'first')
    parsed = parse_m1_response(json.dumps(jgs_response(payload), ensure_ascii=False), payload, M1Assets.load().output_schema)
    apply_m1_response(app.session, payload, parsed)
    app.refresh()


def test_visible_task_uses_plain_start_label(app):
    app.widgets['task_text'].insert('1.0', '讲一下JGS')
    app.refresh()
    assert app.primary_action_var.get() == '开始整理'
    assert app.session.task_text == ''


def test_one_submit_records_and_analyzes_without_accepting_candidates(app, monkeypatch):
    stage_jgs(app)
    before = deepcopy(app.session.pending_proposals)
    calls = []
    monkeypatch.setattr(app, '_submit', lambda *args: calls.append(args))
    app.answer_var.set('数值分析领域')
    assert app.primary_action_var.get() == '提交回答'
    app.widgets['analyze_button'].invoke()
    assert not app.errors
    assert len(calls) == 0
    assert [row['question_id'] for row in app.session.question_history] == ['q1']
    assert [row['question_id'] for row in app.session.pending_questions] == ['q2']

    app.answer_var.set('学生学习讲义')
    app.widgets['analyze_button'].invoke()
    assert not app.errors
    assert len(calls) == 1
    assert [{k: v for k, v in r.items() if k != 'valid_for_version'} for r in app.session.pending_proposals] == [
        {k: v for k, v in r.items() if k != 'valid_for_version'} for r in before]
    assert all(r['valid_for_version'] == app.session.requirement_version for r in app.session.pending_proposals)
    assert app.session.question_history
    assert app.busy
    app.run_primary_action()
    assert len(calls) == 1


def test_each_followup_answer_targets_one_question_and_m1_receives_all_answers(app, monkeypatch):
    app.widgets["task_text"].insert("1.0", "重构现有桌面软件")
    app._sync_input()
    app.session.pending_questions = [
        {
            "question_id": "q-context", "gap_id": None, "field": "use_context",
            "scope": "软件使用场景", "text": "这个软件主要给谁使用？",
            "options": ["个人", "团队", "教学演示"],
            "reason": "软件的实际使用场景会影响设计复杂度。", "depends_on": [],
        },
        {
            "question_id": "q-code", "gap_id": None, "field": "constraints",
            "scope": "代码可用性", "text": "现有代码是否可以提供？",
            "options": ["可以提供代码", "目前没有代码"],
            "reason": "代码可用性影响实施方案。", "depends_on": [],
        },
    ]
    app.refresh()
    assert app.question_context_var.get() == "这个软件主要给谁使用？"
    assert "现有代码是否可以提供" not in app.question_context_var.get()
    assert "reason" not in app.question_context_var.get()
    assert app.question_progress_var.get() == ""
    assert set(app._question_inputs) == {"q-context", "q-code"}

    submitted_payloads = []
    monkeypatch.setattr(
        app,
        "start_analysis",
        lambda: submitted_payloads.append(build_m1_input(app.session, "all-followup-answers")),
    )
    app.answer_var.set("主要给项目组成员使用")
    app.submit_guided_answer()

    assert submitted_payloads == []
    assert [row["question_id"] for row in app.session.question_history] == ["q-context"]
    assert [row["question_id"] for row in app.session.pending_questions] == ["q-code"]
    assert app.question_context_var.get() == "现有代码是否可以提供？"

    app.answer_var.set("可以提供代码")
    app.submit_guided_answer()

    assert len(submitted_payloads) == 1
    payload = submitted_payloads[0]
    assert [row["question_id"] for row in payload["state"]["question_history"]] == ["q-context", "q-code"]
    assert [row["answer_text"] for row in payload["state"]["question_history"]] == [
        "主要给项目组成员使用", "可以提供代码"
    ]


def test_skipped_direction_has_inline_reanswer_and_no_false_confirm(app):
    stage_jgs(app)
    app.session.accept_proposals([r['proposal_id'] for r in app.session.pending_proposals])
    for q in list(app.session.pending_questions):
        app.session.record_question(q['question_id'], 'skipped')
    app.refresh()
    assert app._primary_action().kind == 'confirm_requirements'
    assert app.session.confirmed_requirements_version is None
    assert not app.session.questions_for_review()
    before = deepcopy(app.session.question_history)
    app.reopen_guided_question('q1')
    assert app.session.question_history == before
    assert app._answer_target_id == 'q1'
    assert app.widgets['conversation_input'] is not None


def test_preview_confirmation_goes_directly_to_m2(app, monkeypatch):
    session = confirmed_plan_session()
    session.confirmed_requirements_version = None
    session.plan = SessionState.new().plan
    app.session = session
    app.workflow.session = session
    app.category_var.set('学习与讲解' if '学习与讲解' in app.category_by_label else next(k for k, v in app.category_by_label.items() if v == session.selected_category))
    app.widgets['task_text'].insert('1.0', session.task_text)
    app.refresh()
    calls = []
    monkeypatch.setattr(app, 'start_plan_generation', lambda: calls.append('m2'))
    app.widgets['analyze_button'].invoke()
    assert app.session.confirmed_requirements_version == app.session.requirement_version
    assert calls == ['m2']


def test_confirmed_plan_default_does_not_require_skill_visit(app):
    app.session = confirmed_plan_session()
    app.workflow.session = app.session
    app.delivery_workflow.session = app.session
    app.category_var.set(next(k for k, v in app.category_by_label.items() if v == app.session.selected_category))
    app.widgets['task_text'].insert('1.0', app.session.task_text)
    app.refresh()
    assert app._primary_action().kind == 'generate_final'
    app.widgets['analyze_button'].invoke()
    assert not app.errors
    assert app.session.skill_state['status'] == 'skipped'
    assert app.session.final_result['canonical_body']
    assert app.notebook.index(app.notebook.select()) == 0
    assert "copy" in app._conversation_buttons


def test_viewing_existing_sections_does_not_mutate_session(app):
    app.session = confirmed_plan_session()
    app.widgets['task_text'].insert('1.0', app.session.task_text)
    before = deepcopy(app.session.to_dict())
    app.show_workspace(1)
    app.show_workspace(0)
    assert app.session.to_dict() == before


@pytest.mark.parametrize('action', ['new', 'open'])
def test_switching_session_clears_inline_answer_selection(app, action, tmp_path, monkeypatch):
    from promptsmith.storage import save_session
    stage_jgs(app)
    app._answer_target_id = 'q1'
    app.answer_var.set('上一会话的未提交回答')
    monkeypatch.setattr('promptsmith.ui.messagebox.askyesno', lambda *a, **k: True)
    path = save_session(SessionState.new(), tmp_path / 'other.json')
    monkeypatch.setattr('promptsmith.ui.filedialog.askopenfilename', lambda **k: str(path))
    app.new_session() if action == 'new' else app.open_session()
    assert app._answer_target_id is None
    assert app.answer_var.get() == ''
    assert not app._shown_interpretations


def test_answer_action_reveals_question_and_view_does_not_mutate_state(app):
    stage_jgs(app)
    root = app.root
    root.deiconify()
    root.geometry('1100x650')
    root.update()
    before = deepcopy(app.session.to_dict())
    app.run_primary_action()
    root.update()
    answer = app._question_inputs['q1']
    assert answer.winfo_ismapped()
    assert root.winfo_rooty() <= answer.winfo_rooty()
    assert answer.winfo_rooty() + answer.winfo_height() <= root.winfo_rooty() + root.winfo_height()
    assert app.session.to_dict() == before


def test_understanding_accept_button_disabled_without_selected_interpretation(app):
    stage_jgs(app)
    app.toggle_requirements_review()
    tree = app.widgets['conversation_requirements_tree']
    tree.selection_remove(*tree.selection())
    app._conversation_show_requirement_selection()
    assert str(app._conversation_buttons['accept_requirement'].cget('state')) == 'disabled'
    assert app.session.confirmed_requirements_version is None


def test_editing_candidate_keeps_correction_and_retires_old_text(app, monkeypatch):
    stage_jgs(app)
    app.toggle_requirements_review()
    old=deepcopy(app.session.pending_proposals[0])
    app.widgets['requirements_preview_tree'].selection_set('p:'+old['proposal_id'])
    calls=[]
    monkeypatch.setattr('tkinter.simpledialog.askstring',lambda *a,**k:'改为三页讲义')
    monkeypatch.setattr(app,'start_analysis',lambda: calls.append('analyze'))
    app.edit_preview_item()
    assert not any(p['proposal_id']==old['proposal_id'] for p in app.session.pending_proposals)
    assert any(p['proposal_id']==old['proposal_id'] and p['deferred_reason']=='user_corrected_candidate' for p in app.session.deferred_proposals)
    assert '改为三页讲义' in app.session.question_history[-1]['answer_text']
    assert old['text'] in app.session.question_history[-1]['answer_text']
    assert calls==['analyze']


def test_conflict_preview_shows_both_sides_and_can_apply_explicit_replacement(app):
    from tests.test_guided_state import staged_session
    from tests.test_session import proposal, m1_result
    session = staged_session()
    old = session.accept_proposals(['p1'])[0]
    changed = proposal('p-change', '改成一页课堂提纲', field='deliverable')
    changed.update(operation='replace', target_item_id=old['item_id'])
    result = m1_result(proposals=[changed])
    result['conflicts']=[{'conflict_id':'c1','existing_item_ids':[old['item_id']], 'proposal_ids':['p-change'], 'description':'交付形式发生变化', 'change_intent':'explicit_change'}]
    request = session.begin_request('change')
    session.stage_m1_result('change', request['base_version'], result)
    app.session = app.workflow.session = session
    app.widgets['task_text'].insert('1.0', session.task_text)
    app.refresh()
    app.toggle_requirements_review()
    tree = app.widgets['conversation_requirements_tree']
    for key, expected in [('r:'+old['item_id'], old['text']), ('p:p-change', changed['text'])]:
        tree.selection_set(key)
        app._conversation_show_requirement_selection()
        assert app.widgets['conversation_requirement_details'].get('1.0','end-1c') == expected
    assert app._primary_action().kind == 'focus_conflict'
    app.widgets['requirements_preview_tree'].selection_set('p:p-change')
    app.show_preview_details()
    app._conversation_buttons['adopt_requirement'].invoke()
    assert not app.errors
    assert not session.open_conflicts
    assert not any(r['item_id']==old['item_id'] for r in session.requirements)
    assert any(r['text']==changed['text'] for r in session.requirements)


def test_conflict_action_opens_user_resolution_and_allows_compatible_requirements(app, monkeypatch):
    from tests.test_conflict_participant_integrity import conflict_session
    session = conflict_session()
    app.session = app.workflow.session = session
    app.widgets['task_text'].insert('1.0', session.task_text)
    app.refresh()
    prompts = []
    monkeypatch.setattr('promptsmith.guided_flow.messagebox.askyesno', lambda *args, **kwargs: prompts.append(args) or True)

    assert app._primary_action().kind == 'focus_conflict'
    app.widgets['analyze_button'].invoke()

    assert prompts and session.requirements[1]['text'] in prompts[0][1]
    assert not session.open_conflicts
    assert app._primary_action().kind != 'focus_conflict'


def test_conflict_action_selects_participant_when_user_wants_to_edit(app, monkeypatch):
    from tests.test_conflict_participant_integrity import conflict_session
    session = conflict_session()
    app.session = app.workflow.session = session
    app.widgets['task_text'].insert('1.0', session.task_text)
    app.refresh()
    monkeypatch.setattr('promptsmith.guided_flow.messagebox.askyesno', lambda *args, **kwargs: False)

    app.widgets['analyze_button'].invoke()

    assert app.widgets['requirements_preview_tree'].selection() == ('r:r2',)
    assert '已选中' in app.status_var.get()


def test_initial_window_fits_small_screen_at_high_system_scaling(tk_root, tmp_path, monkeypatch):
    root=tk.Toplevel(tk_root)
    root.withdraw()
    # Approximate 1366x768 at 150%: Tk sees logical screen coordinates.
    monkeypatch.setattr(root,'winfo_screenwidth',lambda: 910)
    monkeypatch.setattr(root,'winfo_screenheight',lambda: 512)
    application=PromptSmithApp(root,evidence_root=tmp_path/'small')
    try:
        root.update_idletasks()
        assert root.minsize()[0] < 910
        assert root.minsize()[1] < 512-50
        root.deiconify()
        root.update()
        assert root.winfo_width() < 910
        assert root.winfo_height() < 512-50
        primary=application.widgets['analyze_button']
        assert primary.winfo_rooty()+primary.winfo_height() <= root.winfo_rooty()+root.winfo_height()
    finally:
        application.shutdown(wait=True)
        root.destroy()
