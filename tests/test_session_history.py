"""Offline persistence/recovery contracts using disposable history directories."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from promptsmith.session import SessionState
from promptsmith.session_history import SessionHistory, history_group, atomic_json
from tests.test_final_delivery import confirmed_plan_session


def goal(text="重新设计软件界面"):
    session = SessionState.new()
    session.set_task(text)
    return session


@pytest.mark.parametrize("days,group", [(0,"今天"),(1,"昨天"),(2,"七天内"),(6,"七天内"),
                                      (7,"30天内"),(29,"30天内"),(30,"更早"),(100,"更早")])
def test_date_groups_are_mutually_exclusive(days, group):
    now = datetime(2026,10,11,0,5,tzinfo=timezone(timedelta(hours=8)))
    assert history_group((now-timedelta(days=days)).isoformat(),now)==group


def test_date_group_uses_local_calendar_not_elapsed_24_hours():
    now = datetime(2026,10,11,0,5,tzinfo=timezone(timedelta(hours=8)))
    assert history_group("2026-10-10T15:59:00Z",now)=="昨天"
    assert history_group("not a time",now)=="更早"


def test_healthy_startup_reads_only_index_and_requested_body(tmp_path, monkeypatch):
    store=SessionHistory(tmp_path)
    ids=[store.save(goal(str(i)).to_dict()) for i in range(12)]
    original=Path.read_text
    reads=[]
    def track(path,*args,**kwargs):
        reads.append(path)
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,"read_text",track)
    restarted=SessionHistory(tmp_path)
    assert len(restarted.list())==12
    assert reads==[store.index_path]
    assert restarted.load(ids[3]).task_text=="3"
    assert reads[-1]==store._path(ids[3]) and len(reads)==2


def test_rename_and_pin_survive_autosave_restart_without_changing_business_state(tmp_path):
    store=SessionHistory(tmp_path)
    session=goal()
    identity=store.save(session.to_dict())
    store.rename(identity,"我的UI任务")
    timestamp=store.entries[identity]["updated_at"]
    store.pin(identity,True)
    assert store.entries[identity]["updated_at"]==timestamp
    store.save(session.to_dict(),identity)
    restarted=SessionHistory(tmp_path)
    row=restarted.list()[0]
    assert row["title"]=="我的UI任务" and row["group"]=="置顶"
    assert restarted.load(identity).requirement_version==session.requirement_version
    restarted.pin(identity,False)
    assert restarted.list()[0]["group"]=="今天"


@pytest.mark.parametrize("title", ["", "   ", "a"*101, "hello\nworld"])
def test_invalid_title_does_not_modify_record(tmp_path,title):
    store=SessionHistory(tmp_path);identity=store.save(goal().to_dict())
    before=store._path(identity).read_bytes()
    with pytest.raises(ValueError):store.rename(identity,title)
    assert before==store._path(identity).read_bytes()


@pytest.mark.parametrize("identity", ["../settings", "", "C:/file", "a"*31, "x"*32])
def test_paths_cannot_escape_managed_directory(tmp_path,identity):
    store=SessionHistory(tmp_path)
    with pytest.raises(ValueError):store._path(identity)


def test_orphan_and_newer_record_recover_interrupted_index_commit(tmp_path,monkeypatch):
    store=SessionHistory(tmp_path)
    identity=store.save(goal("first").to_dict())
    def fail():raise OSError("index disk full")
    monkeypatch.setattr(store,"_write_index",fail)
    with pytest.raises(OSError):store.save(goal("newer").to_dict(),identity)
    orphan="f"*32
    with pytest.raises(OSError):store.save(goal("orphan").to_dict(),orphan)
    restarted=SessionHistory(tmp_path)
    assert restarted.load(identity).task_text=="newer"
    assert restarted.load(orphan).task_text=="orphan"


def test_corrupt_index_rebuilds_and_corrupt_record_is_retained(tmp_path):
    store=SessionHistory(tmp_path);identity=store.save(goal().to_dict())
    store.index_path.write_text("broken",encoding="utf-8")
    restarted=SessionHistory(tmp_path)
    assert restarted.issues and restarted.load(identity).task_text
    restarted._path(identity).write_text("damaged",encoding="utf-8")
    recovered=SessionHistory(tmp_path)
    assert recovered.list()[0]["unavailable"] and recovered._path(identity).exists()
    with pytest.raises(ValueError):recovered.load(identity)


def test_delete_never_deletes_external_exports_and_does_not_reappear(tmp_path):
    store=SessionHistory(tmp_path/"history");identity=store.save(goal().to_dict())
    external=tmp_path/"external.json";external.write_text("keep",encoding="utf-8")
    store.delete(identity)
    assert external.read_text()=="keep"
    assert SessionHistory(tmp_path/"history").list()==[]
    assert not store._path(identity).exists()


def test_failed_delete_rolls_back_index_and_record(tmp_path,monkeypatch):
    store=SessionHistory(tmp_path);identity=store.save(goal().to_dict())
    def fail():raise OSError("cannot write index")
    monkeypatch.setattr(store,"_write_index",fail)
    with pytest.raises(OSError):store.delete(identity)
    assert store.load(identity).task_text and identity in store.entries
    assert SessionHistory(tmp_path).load(identity).task_text


@pytest.mark.parametrize("committed", [True,False])
def test_deletion_crash_tombstone_is_finished_or_rolled_back(tmp_path,committed):
    store=SessionHistory(tmp_path);identity=store.save(goal().to_dict())
    store._path(identity).rename(store._path(identity).with_suffix(".deleted"))
    if committed:atomic_json(store.index_path,{"version":1,"entries":{}})
    restarted=SessionHistory(tmp_path)
    assert bool(restarted.list()) is not committed
    if not committed:assert restarted.load(identity).task_text


def test_full_confirmed_progress_and_drafts_are_restored_without_runtime_key(tmp_path):
    session=confirmed_plan_session()
    session.runtime_api_key="secret-runtime-key"
    session.control["workspace_drafts"]={"message":"草稿", "answers":{"q1":"回答草稿"},"scroll":77}
    before=session.to_dict()
    store=SessionHistory(tmp_path);identity=store.save(before)
    restored=SessionHistory(tmp_path).load(identity)
    assert all(restored.plan[key]==value for key,value in session.plan.items())
    assert restored.requirements==session.requirements
    assert restored.confirmed_requirements_version==session.confirmed_requirements_version
    assert restored.control["workspace_drafts"]==session.control["workspace_drafts"]
    assert not restored.runtime_api_key
    assert "secret-runtime-key" not in store._path(identity).read_text(encoding="utf-8")


def test_inflight_request_restores_as_retryable_not_old_network_work(tmp_path):
    session=goal();session.pending_requests={"old": {"purpose":"analyze", "base_version":1}}
    store=SessionHistory(tmp_path);identity=store.save(session.to_dict())
    restored=store.load(identity)
    assert restored.pending_requests=={}
    assert any(e["kind"]=="request_interrupted_on_load" for e in restored.errors)


def test_atomic_write_failure_keeps_last_good_record(tmp_path,monkeypatch):
    store=SessionHistory(tmp_path);identity=store.save(goal("good").to_dict())
    import promptsmith.session_history as module
    replace=module.os.replace
    def fail(source,target):
        if Path(target)==store._path(identity):raise OSError("write denied")
        return replace(source,target)
    monkeypatch.setattr(module.os,"replace",fail)
    with pytest.raises(OSError):store.save(goal("new").to_dict(),identity)
    assert store.load(identity).task_text=="good"
    assert not list(store.records.glob("*.tmp"))


def test_earlier_manual_sessions_import_once_preserve_dates_and_stay_deleted(tmp_path,monkeypatch):
    from promptsmith.storage import save_session
    exports=tmp_path/"exports";store=SessionHistory(tmp_path/"history")
    session=goal();session.updated_at="2026-10-01T12:00:00Z"
    path=save_session(session,exports/"old.json")
    store.import_directory(exports)
    assert len(store.list())==1 and store.list()[0]["updated_at"]==session.updated_at
    identity=store.list()[0]["id"]
    restarted=SessionHistory(tmp_path/"history")
    original=Path.read_text
    reads=[]
    def track(path,*a,**kw):reads.append(path);return original(path,*a,**kw)
    monkeypatch.setattr(Path,"read_text",track)
    restarted.import_directory(exports)
    assert reads==[]
    restarted.delete(identity)
    SessionHistory(tmp_path/"history").import_directory(exports)
    assert SessionHistory(tmp_path/"history").list()==[] and path.exists()


def test_skill_binding_and_generated_prompt_resume_as_usable_result(tmp_path):
    from promptsmith.finalization import build_final_draft, stage_final_draft, confirm_final, render_task_prompt
    session=confirmed_plan_session()
    basis={"task_id":session.task_id,"requirement_version":session.requirement_version,
           "plan_id":session.plan["plan_id"],"plan_version":session.plan["plan_version"]}
    binding={"binding_id":"binding-1","skill_id":"local-method","record_hash":"record-hash",
             "record_snapshot":{"skill_id":"local-method","record_hash":"record-hash","method_adaptation_allowed":True,"capabilities":[]},
             "key_work_id":"k1","step_ids":["s1"],"usage_mode":"method_adaptation"}
    session.set_skill_state(status="selected",basis=basis,bindings=[binding])
    contribution={"binding_id":"binding-1","origin_binding_ids":["binding-1"],"step_id":"s1",
                  "method_actions":["按方法整理规格"],"planned_inputs":["当前需求"],"expected_outputs":["规格草稿"],
                  "checkpoints":["核对硬约束"],"prerequisite_ids":[],"fallback_actions":["保留原方案"]}
    draft=build_final_draft(session,selected_contributions=[contribution])
    stage_final_draft(session,draft,expected_basis=draft["basis"])
    confirm_final(session)
    store=SessionHistory(tmp_path);identity=store.save(session.to_dict());restored=store.load(identity)
    assert restored.skill_state["bindings"][0]["skill_id"]=="local-method"
    assert restored.final_result["status"]=="confirmed"
    assert restored.final_result["canonical_body"]==session.final_result["canonical_body"]
    assert render_task_prompt(restored.final_result["canonical_body"])==render_task_prompt(session.final_result["canonical_body"])


def test_failed_index_repair_keeps_catalogue_usable(tmp_path,monkeypatch):
    store=SessionHistory(tmp_path);identity=store.save(goal().to_dict())
    store.index_path.write_text("invalid",encoding="utf-8")
    def fail(self):raise OSError("permission denied")
    monkeypatch.setattr(SessionHistory,"_write_index",fail)
    restarted=SessionHistory(tmp_path)
    assert restarted.issues and restarted.load(identity).task_text
