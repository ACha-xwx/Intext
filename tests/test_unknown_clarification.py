"""Pre-stage direction reviews and downstream planning unknowns; offline only."""
import pytest
from copy import deepcopy

from promptsmith.finalization import build_final_draft, DeliveryValidationError
from promptsmith.m1 import build_m1_input
from promptsmith.m2 import apply_m2_response
from promptsmith.session import SessionStateError, SessionState
from promptsmith.storage import save_session, load_session
from tests.test_m2_unknown_recovery import parse, unknown
from tests.test_m2 import confirmed_session
from tests.test_session import proposal
from promptsmith.clarification import review_key

def plan_with_new_unknowns():
    session = confirmed_session()
    payload, parsed, _ = parse(session, [
        unknown("format", description="交付形式未确认：代码，还是设计说明和截图？"),
        unknown("materials", description="现有项目代码和运行说明尚未提供。"),
    ])
    apply_m2_response(session, payload, parsed)
    return session

def test_can_defer_does_not_mean_user_has_deferred():
    session = confirmed_session()
    session.confirmed_requirements_version = None
    session.gaps[0].update(field="deliverable", origin="not_provided", description="代码还是设计稿未确认")
    q = session.questions_for_review()[0]
    with pytest.raises(SessionStateError, match="逐项"):
        session.confirm_requirements_preview(session.requirements_preview())
    session.record_question(q["question_id"], "unsure")
    assert session.confirmed_requirements_version is None
    assert not session.questions_for_review()
    session.confirm_requirements_preview(session.requirements_preview())
    assert session.confirmed_requirements_version == session.requirement_version

def test_draft_flag_alone_cannot_bypass_unreviewed_requirements():
    session = confirmed_session()
    session.gaps[0]["origin"] = "not_provided"
    with pytest.raises(SessionStateError, match="逐项"):
        session.confirm_requirements(allow_draft=True)

def test_requirement_id_rewrite_does_not_reask_unchanged_deferred_gap():
    session = confirmed_session()
    session.confirmed_requirements_version = None
    session.gaps[0].update(origin="not_provided", depends_on=["r1"])
    question = session.questions_for_review()[0]
    session.record_question(question["question_id"], "skipped")
    replacement = proposal("replace", "可运行的报名网站与设计说明", operation="replace", target="r1", field="deliverable")
    session.pending_proposals = [replacement]
    session.confirm_requirements_preview(session.requirements_preview())
    assert session.confirmed_requirements_version == session.requirement_version
    assert not session.questions_for_review()


def legacy_plan_question(session, index=0):
    item=session.plan["content"]["unresolved_items"][index]
    key=review_key(session,"plan",item)
    return {"question_id":"review-"+key,"gap_id":None,"field":"supplement","scope":"方案待补充事项",
            "text":"请补充："+item["description"],"options":[],"reason":"旧版自动方案题","depends_on":[],
            "clarification_key":key,"clarification_scope":"plan","plan_unknown":deepcopy(item)}


def test_plan_unknowns_wait_for_explicit_confirmation_without_restarting_interview(caplog):
    with caplog.at_level("INFO"):
        session=plan_with_new_unknowns()
    before=session.to_dict()
    assert not session.questions_for_review(respect_interview_limit=False)
    session.requirements_preview(); session.plan_preview()
    assert session.to_dict()==before
    assert session.plan["status"]=="draft"
    assert session.plan["pending_key_work_review_ids"]
    with pytest.raises(DeliveryValidationError):
        build_final_draft(session)
    session.confirm_plan_preview(session.plan_preview())
    assert session.plan["status"]=="confirmed"
    assert "no automatic post-plan interview" in caplog.text


def test_unknowns_keep_full_content_and_origin_through_save_export(tmp_path):
    session=plan_with_new_unknowns()
    unknowns=deepcopy(session.plan["content"]["unresolved_items"])
    history=deepcopy(session.question_history)
    session.confirm_plan_preview(session.plan_preview())
    reopened=load_session(save_session(session,tmp_path/"downstream.json"))
    assert not reopened.questions_for_review(respect_interview_limit=False)
    assert reopened.plan["content"]["unresolved_items"]==unknowns
    assert reopened.question_history==history  # No fabricated answers or deferrals.
    body=build_final_draft(reopened)["canonical_body"]
    assert "交付形式未确认" in body and "运行说明尚未提供" in body
    assert all(item.get("source_gap_id") is None for item in unknowns[:2])


def test_edit_or_regenerate_plan_does_not_turn_new_unknowns_into_questions():
    session=plan_with_new_unknowns()
    session.edit_plan_goal("重新核对全软件的布局及样式")
    assert not session.questions_for_review(respect_interview_limit=False)
    content=deepcopy(session.plan["content"])
    content["unresolved_items"][0]["description"]="是否打包可执行文件可由下游实际使用时确定。"
    session.begin_m2_request("regen")
    session.stage_m2_result("regen",session.requirement_version,content,prompt_version="offline",contract_version="m2.v0.1")
    assert not session.questions_for_review()
    session.confirm_plan_preview(session.plan_preview())
    assert "是否打包可执行文件" in build_final_draft(session)["canonical_body"]


@pytest.mark.parametrize("confirmed",[False,True])
def test_old_automatic_plan_queue_is_retired_on_reload_without_changing_unknowns(tmp_path,caplog,confirmed):
    session=plan_with_new_unknowns()
    if confirmed:
        session.confirm_plan_preview(session.plan_preview())
    original=deepcopy(session.plan)
    session.pending_questions=[legacy_plan_question(session)]
    assert not session.questions_for_review(respect_interview_limit=False)
    with caplog.at_level("INFO"):
        reopened=load_session(save_session(session,tmp_path/"old-plan.json"))
    assert reopened.pending_questions==[]
    assert reopened.plan==original
    assert reopened.question_history==[]
    assert "Retired automatic planning follow-ups" in caplog.text
    if not confirmed:
        reopened.confirm_plan_preview(reopened.plan_preview())
    assert "运行说明尚未提供" in build_final_draft(reopened)["canonical_body"]


def test_user_can_reopen_old_plan_question_and_answer_invalidates_plan(tmp_path):
    session=plan_with_new_unknowns()
    session.confirm_plan_preview(session.plan_preview())
    q=legacy_plan_question(session)
    session.question_history.append({**q,"disposition":"skipped","answer_id":"a1","answer_source_id":None,
                                     "answer_text":"","assessment_status":"not_applicable"})
    question=session.reopen_question(q["question_id"])
    assert question["user_requested_reopen"]
    session=load_session(save_session(session,tmp_path/"active-reanswer.json"))
    assert [row["question_id"] for row in session.questions_for_review()]==[q["question_id"]]
    before=session.to_dict()
    with pytest.raises(SessionStateError,match="不能为空"):
        session.record_question(q["question_id"],"answered"," ")
    assert session.to_dict()==before
    source=session.record_question(q["question_id"],"answered","交付完整代码即可")
    assert session.sources[-1]["source_id"]==source
    assert session.plan["status"]=="stale" and session.confirmed_requirements_version is None
    assert build_m1_input(session,"reassess")["state"]["question_history"][-1]["answer_text"]=="交付完整代码即可"
    with pytest.raises(DeliveryValidationError):
        build_final_draft(session)


def test_direct_supplement_invalidates_confirmed_plan_and_delivery():
    session=plan_with_new_unknowns()
    session.confirm_plan_preview(session.plan_preview())
    session.final_result=build_final_draft(session)
    session.record_supplement("需要增加深色主题")
    assert session.plan["status"]==session.final_result["status"]=="stale"
    assert session.confirmed_requirements_version is None
    assert not session.questions_for_review()
