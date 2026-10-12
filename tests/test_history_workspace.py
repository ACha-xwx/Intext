"""Real Tk-owner history bridge scenarios with isolated records and no APIs."""
from threading import Event
import time

import pytest

from promptsmith.history_workspace import HistoryWorkspace
from promptsmith.session_history import SessionHistory
from promptsmith.web_workspace import WorkspaceController, view_stamp
from tests.test_conversation_workspace import app, install_session
from tests.test_final_delivery import confirmed_plan_session
from tests.test_response_workspace import questions


def enabled(app,tmp_path):
    history=HistoryWorkspace(app,SessionHistory(tmp_path/"history"))
    view=WorkspaceController(app,history)
    view.install_native_bridge()
    return view,history


def test_empty_new_sessions_are_not_accumulated(app,tmp_path):
    view,history=enabled(app,tmp_path)
    for _ in range(3):view.dispatch("new",{},view_stamp(app))
    assert history.store.list()==[]


def test_switch_and_restart_resume_question_drafts_and_confirmed_plan(app,tmp_path):
    app.widgets["task_text"].insert("1.0","重新设计UI");app._sync_input()
    app.session.pending_questions=questions();app.refresh()
    view,history=enabled(app,tmp_path)
    token=app._session_instance_token
    view.dispatch("drafts",dict(session=token,sequence=1,message="补充草稿",answers={"q1":"我的回答"},scroll=42),None)
    history.checkpoint(force=True);first=history.identity
    view.dispatch("new",{},view_stamp(app))
    install_session(app,confirmed_plan_session());history.checkpoint(force=True);second=history.identity
    version=app.session.requirement_version
    view.dispatch("history_open",{"id":first},view_stamp(app))
    assert app.session.task_text=="重新设计UI" and app.session.pending_questions
    assert app._question_inputs["q1"].get("1.0","end-1c")=="我的回答"
    assert app.widgets["conversation_input"].get("1.0","end-1c")=="补充草稿"
    assert app._session_instance_token!=token and not app._conversation_locked()
    view.dispatch("history_open",{"id":second},view_stamp(app))
    assert app.session.plan["status"]=="confirmed" and app.session.requirement_version==version
    history.close()
    restarted=SessionHistory(tmp_path/"history")
    assert len(restarted.list())==2 and restarted.load(second).plan["status"]=="confirmed"


def test_old_or_out_of_order_drafts_cannot_contaminate_session(app,tmp_path):
    view,history=enabled(app,tmp_path);old=app._session_instance_token
    view.dispatch("drafts",dict(session=old,sequence=2,message="新草稿"),None)
    view.dispatch("drafts",dict(session=old,sequence=1,message="过时草稿"),None)
    assert app.session.control["workspace_drafts"]["message"]=="新草稿"
    view.dispatch("new",{},view_stamp(app))
    view.dispatch("drafts",dict(session=old,sequence=99,message="迟到"),None)
    assert "workspace_drafts" not in app.session.control


def test_history_changes_need_current_stamp_and_delete_active_unlocks(app,tmp_path):
    install_session(app,confirmed_plan_session());view,history=enabled(app,tmp_path)
    history.checkpoint(force=True);identity=history.identity
    with pytest.raises(ValueError,match="内容已变化"):view.dispatch("history_delete",{"id":identity},"old stamp")
    view.dispatch("history_rename",{"id":identity,"title":"设计任务"},view_stamp(app))
    view.dispatch("history_pin",{"id":identity,"pinned":True},view_stamp(app))
    assert view.snapshot()["history"]["entries"][0]["title"]=="设计任务"
    app._set_busy(True)
    view.dispatch("history_delete",{"id":identity},view_stamp(app))
    assert not app.session.task_text and not app.busy and history.store.list()==[]


def test_checkpoint_failure_keeps_active_state_and_retries(app,tmp_path,monkeypatch):
    install_session(app,confirmed_plan_session());view,history=enabled(app,tmp_path)
    original=history.store.save
    def fail(*args):raise OSError("offline disk full")
    monkeypatch.setattr(history.store,"save",fail)
    previous=app.session
    with pytest.raises(OSError):view.dispatch("new",{},view_stamp(app))
    assert app.session is previous
    history._completed()
    assert "保存未完成" in history.error
    monkeypatch.setattr(history.store,"save",original)
    view.dispatch("history_retry",{},view_stamp(app))
    assert not history.error and history.store.load(history.identity).plan["status"]=="confirmed"


def test_late_background_completion_is_ignored_after_history_open(app,tmp_path):
    install_session(app,confirmed_plan_session());view,history=enabled(app,tmp_path)
    history.checkpoint(force=True);identity=history.identity
    view.dispatch("new",{},view_stamp(app))
    release,entered=Event(),Event()
    def work():entered.set();assert release.wait(5);return "old response"
    app._submit(work,lambda value:app.status_var.set(value),lambda exc:app.status_var.set(str(exc)))
    assert entered.wait(2)
    view.dispatch("history_open",{"id":identity},view_stamp(app))
    status=app.status_var.get()
    release.set()
    deadline=time.monotonic()+4
    while app._background_futures and time.monotonic()<deadline:app.root.update();time.sleep(.01)
    app.root.update()
    assert app.status_var.get()==status and app.session.plan["status"]=="confirmed"


def test_external_open_imports_managed_copy_without_deleting_source(app,tmp_path,monkeypatch):
    from promptsmith.storage import save_session
    view,history=enabled(app,tmp_path)
    path=save_session(confirmed_plan_session(),tmp_path/"external.json")
    monkeypatch.setattr("promptsmith.ui.filedialog.askopenfilename",lambda **kw:str(path))
    view.dispatch("open",{},view_stamp(app));identity=history.identity
    assert identity and app.session_path==path
    view.dispatch("history_delete",{"id":identity},view_stamp(app))
    assert path.exists()
