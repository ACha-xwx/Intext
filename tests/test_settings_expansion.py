"""Runtime preferences through the public settings and desktop boundaries."""
import pytest
from promptsmith.preferences import load_settings, save_desktop_preferences, validate_preferences
from tests.test_conversation_workspace import app


EXPANDED = dict(model_directory_autorefresh=False, model_directory_workers=3,
    skill_min_score=.7, skill_description_chars=1000, skill_brief_chars=1500,
    skill_task_chars=9000, conversation_width=900, notification_seconds=8.,
    thinking_autoscroll=False, thinking_speed=2., history_save_interval=5., debug_refresh_ms=400)


def test_expanded_settings_save_restore_and_validate_ranges(tmp_path):
    values = validate_preferences(EXPANDED)
    for key, value in EXPANDED.items():
        assert values[key] == value
    path = tmp_path / 'settings.json'
    save_desktop_preferences(path, EXPANDED)
    assert all(load_settings(path).preferences[k] == v for k, v in EXPANDED.items())
    for key, invalid in dict(skill_min_score=1.1, thinking_speed=0, notification_seconds=0,
                            model_directory_workers=6, debug_refresh_ms=0).items():
        with pytest.raises(ValueError):
            validate_preferences({key: invalid})


def test_desktop_autosave_projects_live_display_preferences(app):
    from promptsmith.web_workspace import WorkspaceController
    view = WorkspaceController(app)
    snap = view.settings_snapshot()
    view.settings_action('settings_autosave', dict(revision=snap['revision'],
        connection=snap['connection'], values=dict(snap['values'], **EXPANDED),
        changed_fields=list(EXPANDED), key_action='keep', key=''))
    state = view.snapshot()
    for name in ('conversation_width','notification_seconds','thinking_autoscroll','thinking_speed'):
        assert state['display_preferences'][name] == EXPANDED[name]
    assert load_settings(app._preferences_path).preferences['history_save_interval'] == 5


def test_network_scoring_uses_user_threshold_and_introduction_budgets():
    from tests.test_network_skill_summary_scoring import SummaryModel
    from tests.test_network_skill_relevance import Http, TASK, WORKS
    from promptsmith.skill_network_discovery import search_network_skill_candidates, clear_network_skill_cache
    clear_network_skill_cache()
    model = SummaryModel()
    result = search_network_skill_candidates(WORKS, task_text=TASK, client=model,
        opener=Http([('technical-docs', 'Write technical documentation ' * 100)]),
        review_options=dict(min_score=.95, description_chars=200, brief_chars=250, task_chars=9000))
    assert result.diagnostics['ai_review_status'] == 'completed'
    assert not result.candidates  # Fixture score is .93; configured minimum is .95.
    assert len(model.reviews) == 1
    assert all(len(row['description']) <= 200 and len(row['brief']) <= 250
               for row in model.reviews[0][1]['skills'])


def test_large_task_can_use_an_expanded_skill_context_budget():
    from tests.test_network_skill_summary_scoring import SummaryModel
    from tests.test_network_skill_relevance import Http, TASK, WORKS
    from promptsmith.skill_network_discovery import search_network_skill_candidates, clear_network_skill_cache
    clear_network_skill_cache()
    model = SummaryModel()
    task = TASK + ' technical documentation' * 280
    result = search_network_skill_candidates(WORKS, task_text=task, client=model,
        opener=Http([('technical-docs', 'Write accurate technical documentation')]),
        review_options=dict(task_chars=9000))
    assert result.diagnostics['ai_review_status'] == 'completed'
    assert model.reviews[0][1]['task_text'] == task


def test_online_low_scores_remain_a_completed_review_at_a_high_threshold():
    from tests.test_network_skill_summary_scoring import SummaryModel
    from tests.test_network_skill_relevance import Http, TASK, WORKS
    from promptsmith.skill_network_discovery import search_network_skill_candidates, clear_network_skill_cache

    class AllScoresModel(SummaryModel):
        def complete_json(self, prompt, payload, schema):
            if 'matches' in schema['required']:
                assert '包括低于门槛的候选' in prompt
            return super().complete_json(prompt, payload, schema)

    clear_network_skill_cache()
    result = search_network_skill_candidates(WORKS, task_text=TASK, client=AllScoresModel(),
        opener=Http([('technical-docs', 'Write accurate technical documentation')]),
        review_options=dict(min_score=.95))
    assert result.diagnostics['ai_review_status'] == 'completed'
    assert result.candidates == []


def test_local_review_honors_a_lower_user_threshold(tmp_path):
    from tests.test_skill_ai_selection import ScriptedClient, _skill
    from promptsmith.local_skill_search import discover_local_skill_candidates
    from promptsmith.skill_ai_selection import select_skill_candidates_with_ai
    _skill(tmp_path, 'teaching', 'Agent teaching workflow', 'Use examples to teach a lesson.')
    works = [dict(key_work_id='math', title='讲解分部积分法', step_ids=[])]
    discovered = discover_local_skill_candidates(works, roots=[tmp_path])
    model = ScriptedClient([dict(matches=[dict(candidate_id=discovered.candidates[0]['candidate_id'],
        key_work_id='math', reason='用于组织教学示例，但与当前题目仅间接相关。', recommendation_score=.3)])])
    selected = select_skill_candidates_with_ai(model, discovered.candidates,
        task_text='讲解分部积分法', key_works=works, min_score=.2)
    assert len(selected) == 1 and selected[0]['recommendation_score'] == .3
    assert '更低应排除' not in model.calls[0][0]
    assert '最低分为0.2' in model.calls[0][0]


def test_history_interval_delays_background_save_but_never_forced_save(app, tmp_path, monkeypatch):
    from promptsmith.history_workspace import HistoryWorkspace
    from promptsmith.session_history import SessionHistory
    from tests.test_conversation_workspace import install_session
    from tests.test_final_delivery import confirmed_plan_session
    clock = [100.]
    monkeypatch.setattr('promptsmith.history_workspace.time.monotonic', lambda: clock[0])
    install_session(app, confirmed_plan_session())
    app.preferences['history_save_interval'] = 10.
    store = SessionHistory(tmp_path/'interval-history')
    history = HistoryWorkspace(app, store)
    try:
        history.checkpoint(force=True)
        identity = history.identity
        history.update_drafts(dict(session=app._session_instance_token, sequence=1,
                                   message='Changed draft', answers={}))
        clock[0] = 105.
        history.checkpoint()
        assert store.load(identity).control.get('workspace_drafts', {}).get('message') != 'Changed draft'
        history.checkpoint(force=True)
        assert store.load(identity).control['workspace_drafts']['message'] == 'Changed draft'
    finally:
        history.close()


def test_notification_duration_updates_an_already_open_debug_window(app, tmp_path):
    from promptsmith.runtime_log import RuntimeLog
    from promptsmith.web_debug import DebugApi, WebDebugConsole, concise_message
    from promptsmith.web_workspace import WorkspaceController
    from tests.test_debug_log_view import DesktopApi
    logs = RuntimeLog(tmp_path/'manual-logs')
    console = WebDebugConsole(logs, DesktopApi())
    console.apply_preferences(app.preferences)
    app.debug_console = console
    app.set_debug_console_enabled = lambda **kwargs: None
    view = WorkspaceController(app)
    snap = view.settings_snapshot()
    view.settings_action('settings_autosave', dict(revision=snap['revision'], connection=snap['connection'],
        values=dict(snap['values'],notification_seconds=9), changed_fields=['notification_seconds'],key_action='keep',key=''))
    assert DebugApi(console).snapshot()['preferences']['notification_seconds'] == 9
    assert concise_message('Browser 启动标题已就绪: source=intext-logo.png',20) == '启动标题已就绪'
    app.debug_console = None
