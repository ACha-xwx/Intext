"""Tk-owner coordination for background history I/O and browser drafts."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import logging
import time
from datetime import datetime
from uuid import uuid4

LOG = logging.getLogger(__name__)


class HistoryWorkspace:
    def __init__(self, app, store):
        self.app = app
        self.store = store
        self.identity = None
        self.signature = None
        self.future = None
        self.last_check = 0.
        self.error = "；".join(store.issues)
        self.sequence = -1
        self.closed = False
        self.retry_after = 0.
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="session-history")
        self.rows = store.list()
        self.list_date = datetime.now().astimezone().date()

    def install(self):
        app = self.app
        original_open, original_shutdown = app.open_session, app.shutdown
        def open_file():
            self.checkpoint(force=True)
            old = app.session
            original_open()
            if app.session is not old:
                self.reset()
                self.checkpoint(force=True)
        def shutdown(*, wait):
            self.close()
            original_shutdown(wait=wait)
        app.new_session = self.new
        app.open_session = open_file
        app.shutdown = shutdown
        LOG.info("Local history enabled: directory=%s background_checkpoints=True", self.store.directory)

    def reset(self, identity=None):
        self.identity = identity
        self.signature = None
        self.sequence = -1

    def _completed(self):
        if self.future is not None and self.future.done():
            try:
                self.future.result()
                self.rows = self.store.list()
                self.error = ""
            except Exception:
                self.signature = None
                self.error = "历史会话保存未完成。现有内容仍在当前窗口，请点击重试保存；详细原因见 Debug。"
                self.retry_after = time.monotonic() + 10
                LOG.exception("History checkpoint failed; current in-memory session retained: id=%s", self.identity)
            self.future = None

    def checkpoint(self, *, force=False):
        if self.closed:
            return
        if force and self.future is not None:
            try:
                self.future.result()
            except Exception:
                pass  # _completed logs the complete cause and enables a retry.
        self._completed()
        interval = self.app.preferences.get("history_save_interval", 2.)
        if not force and (self.future is not None or time.monotonic()-self.last_check < interval or time.monotonic() < self.retry_after):
            return
        self.last_check = time.monotonic()
        data = self.app.session.to_dict()
        if "workspace_drafts" in data.get("control", {}):
            data["control"]["workspace_drafts"]["reanswer"] = self.app._answer_target_id
        drafts = data.get("control", {}).get("workspace_drafts", {})
        if not self.identity and not data.get("task_text") and not drafts.get("message") and not any(drafts.get("answers", {}).values()):
            return
        signature = hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if signature == self.signature:
            return
        self.identity = self.identity or uuid4().hex
        self.signature = signature
        self.future = self.executor.submit(self.store.save, data, self.identity)
        if force:
            # Switching never discards unsaved state after a failed checkpoint.
            self.future.result()
            self._completed()

    def new(self):
        self.checkpoint(force=True)
        self.app._install_session(self.app._new_preferred_session(), reason="history_new")
        self.reset()
        self.app.status_var.set("已开启新对话，之前的进度已保存在历史会话中。")
        LOG.info("History new conversation: previous checkpoint retained")

    def action(self, action, data):
        identity = data.get("id")
        self.checkpoint(force=True)
        if action == "history_retry":
            return
        if action == "history_open":
            if identity == self.identity:
                return
            # Load/validate before invalidating the current request or replacing state.
            session = self.store.load(identity)
            self.app._install_session(session, reason="history_open")
            self.reset(identity)
            self.app.status_var.set("已恢复历史会话，可继续当前步骤。")
        elif action == "history_rename":
            self.store.rename(identity, data.get("title"))
        elif action == "history_pin":
            self.store.pin(identity, data.get("pinned"))
        elif action == "history_delete":
            self.store.delete(identity)
            if identity == self.identity:
                self.app._install_session(self.app._new_preferred_session(), reason="history_delete")
                self.reset()
        else:
            raise ValueError("历史会话操作不存在。")
        self.rows = self.store.list()

    def update_drafts(self, data):
        if data.get("session") != self.app._session_instance_token:
            LOG.debug("Ignored late draft update from previous conversation")
            return
        restore_id = self.app.session.control.get("workspace_drafts", {}).get("answer_restore_id")
        if data.get("answer_restore_id") != restore_id:
            LOG.debug("Ignored draft update from before answer restoration")
            return
        sequence = data.get("sequence")
        if not isinstance(sequence, int) or sequence <= self.sequence:
            return
        message, answers = data.get("message", ""), data.get("answers", {})
        if not isinstance(message, str) or len(message) > 1000000 or not isinstance(answers, dict):
            raise ValueError("输入草稿格式无效。")
        pending = {q.get("question_id") for q in self.app.session.questions_for_review()}
        valid = {key: value for key, value in answers.items() if key in pending and isinstance(value, str) and len(value) <= 1000000}
        self.sequence = sequence
        self.app.session.control["workspace_drafts"] = dict(message=message, answers=valid,
            reanswer=self.app._answer_target_id, scroll=max(0, min(1e8, float(data.get("scroll", 0)))))
        if restore_id:
            self.app.session.control["workspace_drafts"]["answer_restore_id"] = restore_id
        self.app._question_drafts = deepcopy(valid)

    def snapshot(self):
        self.checkpoint()
        today = datetime.now().astimezone().date()
        if today != self.list_date:
            self.rows = self.store.list()
            self.list_date = today
        return dict(entries=self.rows, active=self.identity, error=self.error)

    def close(self):
        if self.closed:
            return
        try:
            self.checkpoint(force=True)
            LOG.info("History shutdown checkpoint completed: id=%s", self.identity)
        except Exception:
            LOG.exception("History shutdown checkpoint failed; last saved record preserved")
        finally:
            self.closed = True
            self.executor.shutdown(wait=True)
