"""One visible freeform answer can carry evidence for several existing gaps."""
from copy import deepcopy
import json

import pytest

from promptsmith.m1 import M1Assets, M1ValidationError, apply_m1_response, build_m1_input, parse_m1_response
from promptsmith.session import SessionState, SessionStateError
from promptsmith.storage import save_session, load_session
from tests.test_ui_reliability import base_result


def setup_answer(*, guided=True):
    s = SessionState.new()
    s.set_task('讲一下JGS')
    initial = build_m1_input(s, 'initial')
    result = base_result(initial)
    result['category'] = {'primary': 'learning', 'secondary': [], 'reason': '学习任务'}
    result['gaps'] = [
        {'gap_id': gid, 'field': field, 'scope': scope, 'description': scope,
         'importance': importance, 'origin': 'missing', 'source_refs': [], 'depends_on': []}
        for gid, field, scope, importance in [('g1', 'goal', 'JGS的含义', 'blocking_direction'), ('g2', 'deliverable', '材料形式', 'can_defer')]]
    result['questions'] = [{'question_id':'q1', 'gap_id':'g1', 'field':'goal', 'scope':'JGS的含义', 'text':'JGS具体指什么？', 'options':[], 'reason':'需要明确范围', 'depends_on':[]}]
    result['readiness']['blocking_gap_ids'] = ['g1']
    result['next_action'] = 'ask'
    parsed = parse_m1_response(json.dumps(result, ensure_ascii=False), initial, M1Assets.load().output_schema)
    apply_m1_response(s, initial, parsed)
    kwargs = {'context_gap_ids':['g1', 'g2']} if guided else {}
    s.record_question('q1', 'answered', '数值分析里面的，做成学生学习讲义', **kwargs)
    payload = build_m1_input(s, 'second')
    result = base_result(payload)
    result['category'] = {'primary':'learning', 'secondary':[], 'reason':'学习任务'}
    answer = payload['state']['question_history'][-1]
    result['gap_updates'] = [
        {'update_id':'gu1', 'target_gap_id':'g1', 'answer_id':answer['answer_id'], 'action':'partial',
         'source_ref':{'source_id':answer['answer_source_id'], 'quote':'数值分析里面的'}, 'remaining_description':'具体方法仍不确定', 'reason':'只确定领域'},
        {'update_id':'gu2', 'target_gap_id':'g2', 'answer_id':answer['answer_id'], 'action':'resolved',
         'source_ref':{'source_id':answer['answer_source_id'], 'quote':'做成学生学习讲义'}, 'remaining_description':None, 'reason':'明确了材料形式'}]
    result['readiness']['blocking_gap_ids'] = ['g1']
    result['next_action'] = 'pause_with_unknowns'
    return s, payload, result


def test_freeform_answer_updates_two_existing_gaps_with_separate_evidence(tmp_path):
    s, payload, result = setup_answer()
    parsed = parse_m1_response(json.dumps(result, ensure_ascii=False), payload, M1Assets.load().output_schema, incremental=True)
    apply_m1_response(s, payload, parsed)
    assert [g['gap_id'] for g in s.gaps] == ['g1']
    assert s.gaps[0]['description'] == '具体方法仍不确定'
    assert len(s.question_history) == 1
    assert s.question_history[0]['assessment_status'] == 'applied'
    assert s.question_history[0]['assessment_action'] == 'partial'
    assert set(s.question_history[0]['assessed_gap_ids']) == {'g1','g2'}
    assert len(s.gap_update_history) == 2
    saved = save_session(s, tmp_path/'multi.json')
    assert load_session(saved).to_dict() == s.to_dict()


def test_old_single_gap_answers_remain_strict():
    s, payload, result = setup_answer(guided=False)
    before = deepcopy(s.to_dict())
    with pytest.raises(M1ValidationError, match='不一致'):
        parse_m1_response(json.dumps(result, ensure_ascii=False), payload, M1Assets.load().output_schema, incremental=True)
    with pytest.raises(SessionStateError, match='不一致'):
        s.stage_m1_result(payload['request_id'], payload['base_version'], result)
    after = s.to_dict()
    assert after.pop("pending_requests") == {}
    before.pop("pending_requests")
    assert after == before


@pytest.mark.parametrize('mutation', ['unknown_gap', 'duplicate_gap', 'invented_quote'])
def test_multi_gap_permission_does_not_bypass_reference_and_evidence_guards(mutation):
    s, payload, result = setup_answer()
    if mutation == 'unknown_gap':
        result['gap_updates'][1]['target_gap_id']='not-in-user-context'
    elif mutation == 'duplicate_gap':
        result['gap_updates'][1]['target_gap_id']='g1'
    else:
        result['gap_updates'][1]['source_ref']['quote']='用户没有说的话'
    with pytest.raises(M1ValidationError):
        parse_m1_response(json.dumps(result, ensure_ascii=False), payload, M1Assets.load().output_schema, incremental=True)


def test_extra_gap_only_update_leaves_original_answer_pending():
    s, payload, result = setup_answer()
    result['gap_updates'] = result['gap_updates'][1:]
    parsed = parse_m1_response(json.dumps(result, ensure_ascii=False), payload, M1Assets.load().output_schema, incremental=True)
    apply_m1_response(s, payload, parsed)
    assert s.question_history[0]['assessment_status'] == 'pending'
    assert s.question_history[0]['assessed_gap_ids'] == ['g2']


def test_one_inline_submission_to_two_questions_has_no_unprocessed_duplicate():
    s, _, result = setup_answer()
    s.pending_requests.pop('second')
    s.pending_questions.append({'question_id':'q2','gap_id':'g2','field':'deliverable','scope':'材料形式',
                                'text':'要哪种材料？','options':[],'reason':'确定产出','depends_on':[]})
    s.record_question('q2','answered','数值分析里面的，做成学生学习讲义',context_gap_ids=['g1','g2'])
    for row in s.question_history:
        row['submission_group_id']='guided:a1'
    payload=build_m1_input(s,'second')
    result['base_version']=payload['base_version']
    # The model may cite the same combined message for both pieces of evidence.
    parsed=parse_m1_response(json.dumps(result,ensure_ascii=False),payload,M1Assets.load().output_schema,incremental=True)
    apply_m1_response(s,payload,parsed)
    assert len(s.question_history)==2
    assert all(row['assessment_status']=='applied' for row in s.question_history)
    assert s.question_history[1]['assessment_action']=='resolved'
