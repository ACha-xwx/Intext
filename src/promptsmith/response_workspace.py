"""Main-thread response events, persisted traces and inline question drafts."""
import logging
import queue
import time
import tkinter as tk

from .response_ui import ResponseTrace, palette
from .typography import ui_font


class ResponseWorkspaceMixin:
    def _init_response_view(self):
        self._response_events = queue.Queue()
        self._trace_widgets = {}
        self._trace_records = {}
        self._trace_started = {}
        self._question_drafts = {}
        self._question_inputs = {}
        self._response_deliveries = {}
        self._response_after = self.root.after(16, self._poll_response_events)

    def _close_response_view(self):
        self._close_workspace_popovers()
        if self._response_after is not None:
            self.root.after_cancel(self._response_after)
            self._response_after = None
        for widget in self._trace_widgets.values():
            widget.close()
        self._response_deliveries.clear()

    def _reset_response_view(self):
        self._close_workspace_popovers()
        for widget in self._trace_widgets.values():
            widget.destroy()
        self._trace_widgets = {}
        self._trace_records = {}
        self._trace_started = {}
        self._question_drafts = {}
        self._question_inputs = {}
        self._response_deliveries.clear()
        logging.getLogger(__name__).debug("Response view reset for new/open conversation; task=%s", self.session.task_id)

    def _close_workspace_popovers(self):
        panel=getattr(self,"_workspace_popover",None)
        if panel:
            panel.close(immediate=True)
        composer=self.widgets.get("conversation_composer")
        if composer and composer.choice_menu:
            composer.choice_menu.close(immediate=True)

    def _poll_response_events(self):
        self._response_after = None
        redraw = False
        chunks = {}
        started = time.perf_counter()
        for _ in range(2000):
            if time.perf_counter()-started > .006:
                break
            try:
                scope, session_token, delivery_owner, event = self._response_events.get_nowait()
            except queue.Empty:
                break
            if event["event"] == "completion_fence":
                event["ready"].set()
                continue
            if self._shutdown or scope.cancelled or session_token != self._session_instance_token or (delivery_owner is not None and delivery_owner.get("_stream_cancelled")):
                continue
            key = event.get("id")
            kind = event["event"]
            if kind == "start":
                record = {"id": key, "operation": event["operation"], "model": event.get("model"),
                          "protocol": event.get("protocol"), "activities": event.get("activities", []),
                          "history_count": event.get("history_count", len(self.session.question_history)),
                          "delivery_request_id": event.get("delivery_request_id"),
                          "reasoning": "", "status": "working", "elapsed": 0.}
                self.session.control.setdefault("response_traces", []).append(record)
                self._trace_records[key] = record
                self._trace_started[key] = time.monotonic()
                redraw = True
                logging.getLogger(__name__).info("Response trace started: id=%s model=%s", key, record["model"])
            elif kind == "reasoning" and key in self._trace_records:
                chunks.setdefault(key, []).append(event.get("text", ""))
            elif kind in {"end", "failed"} and key in self._trace_records:
                record = self._trace_records[key]
                record["status"] = "done" if kind == "end" else "failed"
                record["elapsed"] = time.monotonic()-self._trace_started[key]
                if kind == "failed":
                    record["error"] = event.get("text", "") + "\n已有内容保留，请检查模型设置或重试。"
                    logging.getLogger(__name__).warning("Response trace failed: id=%s reason=%s", key, event.get("text", ""))
                else:
                    logging.getLogger(__name__).debug("Response trace received: id=%s elapsed=%.3fs", key, record["elapsed"])
                redraw = True
            elif kind == "operation_failed":
                for record in self._trace_records.values():
                    if record.get("operation") == event["operation"]:
                        record["status"] = "failed"
                        record["error"] = event.get("text", "") + "\n已有内容保留，可以补充信息后重试。"
                        redraw = True
        for key, values in chunks.items():
            value = "".join(values)
            self._trace_records[key]["reasoning"] += value
            widget = self._trace_widgets.get(key)
            if widget is not None:
                widget.writer.feed(value)
        if redraw:
            self._conversation_signature = None
            self._refresh_conversation()
        for key, record in self._trace_records.items():
            widget = self._trace_widgets.get(key)
            if widget is not None and record.get("status") != "working" and not widget.writer.finished:
                widget.finish()
            elif widget is not None and record.get("status") == "working":
                record["elapsed"] = time.monotonic()-self._trace_started.get(key, time.monotonic())
                widget.update_status()
        # A completed request may be saved by its callback. Apply all stream
        # metadata first, without waiting for the visual typewriter to finish.
        for operation, (ready, callback, value) in list(self._response_deliveries.items()):
            if ready.is_set():
                self._response_deliveries.pop(operation, None)
                try:
                    callback(value)
                except Exception:
                    import sys
                    self._tk_root.report_callback_exception(*sys.exc_info())
        if not self._shutdown:
            self._response_after = self.root.after(16, self._poll_response_events)

    def _render_response_trace(self, record):
        key = record.get("id")
        if key not in self._trace_widgets:
            # A saved in-flight request cannot resume its old network socket.
            if record.get("status") == "working" and key not in self._trace_records:
                record["status"] = "cancelled"
            widget = ResponseTrace(self.widgets["conversation_timeline"], record, theme=self.preferences["composer_theme"])
            self._trace_widgets[key] = widget
        widget = self._trace_widgets[key]
        widget.apply_theme(self.preferences["composer_theme"])
        widget.grid(row=self._conversation_next_row, column=0, sticky="ew", pady=(3, 14))
        self._conversation_next_row += 1

    def _inline_question(self, card, question, *, first=False):
        from .interaction_ui import RoundedAnswer, SkipButton
        from .composer import GlyphButton, THEMES
        key = question["question_id"]
        colors = palette(self.preferences["composer_theme"])
        row = tk.Frame(card, bg=colors["bg"])
        row.pack(fill="x",pady=(7,6))
        row.columnconfigure(0,weight=1)
        surface = RoundedAnswer(row,self.preferences["composer_theme"])
        surface.grid(row=0,column=0,sticky="ew")
        answer = surface.entry
        answer.insert("1.0", self._question_drafts.get(key, ""))
        self._question_inputs[key] = answer
        token = self._conversation_render_token
        size = max(42,ui_font(card).metrics("linespace")+16)
        submit = GlyphButton(row,text="提交本轮已填写的回答",command=lambda:self._conversation_action(token,lambda:self._submit_inline_question(key)),
                             arrow=True,width=size,height=size,palette=THEMES[self.preferences["composer_theme"]],
                             state="normal" if self._question_drafts.get(key, "").strip() and not self._conversation_locked() else "disabled")
        submit.grid(row=0,column=1,padx=12)
        self._conversation_buttons["submit:"+key]=submit
        skip = SkipButton(row,lambda:self._conversation_action(token,lambda:self._skip_inline_question(key,"skipped")),self.preferences["composer_theme"])
        skip.grid(row=0,column=2)
        skip.configure(state="disabled" if self._conversation_locked() else "normal")
        self._conversation_buttons["skip" if first else "skipped:"+key]=skip
        self.widgets["conversation_question_inputs"] = self._question_inputs

        def changed(_event=None):
            if answer.edit_modified():
                text = answer.get("1.0", "end-1c")
                self._question_drafts[key] = text
                self._update_inline_answer_buttons()
                answer.edit_modified(False)
        answer.edit_modified(False)
        answer.bind("<<Modified>>", changed)
        def submit_key(_event):
            self._conversation_action(token, lambda: self._submit_inline_question(key))
            return "break"

        def newline(_event):
            if not self._conversation_locked() and str(answer.cget("state")) != "disabled":
                answer.insert("insert", "\n")
                answer.see("insert")
            return "break"

        for sequence in ("<Return>", "<KP_Enter>", "<Control-Return>"):
            answer.bind(sequence, submit_key)
        for sequence in ("<Shift-Return>", "<Shift-KP_Enter>"):
            answer.bind(sequence, newline)
        logging.getLogger(__name__).debug("Inline answer shortcuts ready: task=%s question=%s Enter=submit-batch Shift+Enter=newline",
                                          self.session.task_id, key)
        self._bind_context_menu(answer)
        answer.configure(state="disabled" if self._conversation_locked() else "normal")
        self._update_inline_answer_buttons()

    def _update_inline_answer_buttons(self):
        active = {row["question_id"] for row in self.session.questions_for_review()}
        filled = any(widget.get("1.0", "end-1c").strip()
                     for key, widget in self._question_inputs.items() if key in active)
        state = "normal" if filled and not self._conversation_locked() else "disabled"
        for key in self._question_inputs:
            submit = self._conversation_buttons.get("submit:" + key)
            if submit is not None:
                submit.configure(state=state)

    def _fill_inline_question(self, key, text):
        widget = self._question_inputs[key]
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.focus_set()

    def _submit_inline_question(self, key):
        active = self.session.questions_for_review()
        if not any(row["question_id"] == key for row in active) or self._conversation_locked():
            return
        answers = [{"question_id": row["question_id"], "text": self._question_inputs[row["question_id"]].get("1.0", "end-1c")}
                   for row in active if row["question_id"] in self._question_inputs]
        try:
            self.submit_guided_answers(answers)
        except Exception:
            logging.getLogger(__name__).exception("Inline answer batch failed; drafts retained: task=%s", self.session.task_id)
            self._show_error("回答未提交", "本轮回答未提交，输入已保留。请查看当前问题后重试。", parent=self.root)

    def _skip_inline_question(self, key, disposition):
        self._answer_target_id = key
        self.skip_guided_question(disposition)
