"""Conversation presentation derived from SessionState, with guarded UI actions.

The projection is deliberately read-only. Confirmation and invalidation continue
to belong to the existing session and workflow methods.
"""
from __future__ import annotations

from copy import deepcopy
import json
import logging
import tkinter as tk
from tkinter import ttk, font as tkfont

from .session import SessionStateError

from .finalization import render_task_prompt
from .composer import PromptComposer, SlimScrollbar, THEMES
from .response_ui import HERO_TEXT, PROMPT_SECTIONS, MarkdownText, MessageShell, ReplyButton, ResponseTrace, palette
from .response_workspace import ResponseWorkspaceMixin
from .typography import ui_font


def conversation_cards(session):
    """Reconstruct the current task conversation, including old saved sessions."""
    cards = []
    if not session.task_text:
        return [{"key": "welcome", "kind": "welcome", "title": "一起把目标变成可用的提示词",
                 "text": "描述你想完成的目标。我会逐步整理要求、提出关键问题，再和你一起核对方案。"}]
    cards.append({"key": "task", "kind": "user", "title": "你的目标", "text": session.task_text})
    traces = [r for r in session.control.get("response_traces", []) if isinstance(r, dict) and isinstance(r.get("id"), str)]
    def append_traces(count):
        for record in traces:
            position = record.get("history_count", len(session.question_history))
            if not isinstance(position, int):
                position = len(session.question_history)
            if min(max(0, position), len(session.question_history)) == count:
                cards.append({"key": "trace:"+record["id"], "kind": "trace", "title": "处理过程", "trace": record})
    for index, row in enumerate(session.question_history):
        append_traces(index)
        supplement = row.get("field") == "supplement"
        if not supplement:
            cards.append({"key": "question:" + row["answer_id"], "kind": "history_question",
                          "title": "此前的问题", "text": row.get("text") or row.get("question_text", ""),
                          "question_id": row["question_id"]})
        cards.append({"key": "answer:" + row["answer_id"], "kind": "user",
                      "title": "你的补充" if supplement else "你的回答",
                      "text": row.get("answer_text") or {"skipped": "先跳过", "unsure": "我不确定"}.get(row.get("disposition"), ""),
                      "question_id": None if supplement else row["question_id"],
                      "reanswer_key": "question:"+row["answer_id"],
                      "assessment": row.get("assessment_status")})
    append_traces(len(session.question_history))
    navigation = session.workspace_navigation()
    stage = navigation["stage"]
    if navigation["previous"] or navigation["next"]:
        cards.append({"key": "navigation", "kind": "navigation", "title": "回看与继续", **navigation})
    if (session.requirements or session.pending_proposals) and stage == "requirements":
        confirmed = session.confirmed_requirements_version == session.requirement_version
        cards.append({"key": "requirements", "kind": "requirements",
                      "title": "需求已确认" if confirmed else "一起核对需求",
                      "requirements": deepcopy(session.requirements), "proposals": deepcopy(session.pending_proposals),
                      "confirmed": confirmed})
    if stage == "interview" and session.questions_for_review():
        for index, question in enumerate(session.questions_for_review()):
            cards.append({"key": "active_question" if index == 0 else "question:"+question["question_id"], "kind": "question",
                          "title": f"补充问题 · {index+1} / {len(session.questions_for_review())}", "question": deepcopy(question), "remaining": len(session.questions_for_review()), "first": index == 0})
    elif stage == "interview":
        from .interview import rounds_used, round_limit
        remaining = session.questions_for_review(respect_interview_limit=False)
        if rounds_used(session) >= round_limit(session) and remaining:
            cards.append({"key": "interview_unknowns", "kind": "interview_unknowns", "title": "访谈收尾：核对剩余未知",
                          "text": "是否需要继续询问？以下内容仍未确定：\n" + "\n".join(
                              "• " + row["text"].split("\n")[0].removeprefix("请补充：").removeprefix("请补充： ") for row in remaining)})
    plan = session.plan
    if (plan.get("content") and (not navigation["revisiting"] or stage in {"plan", "skills", "result"})
            and (plan.get("status") != "confirmed" or stage == "plan")):
        cards.append({"key": "plan", "kind": "plan", "title": "一起核对方案",
                      "status": plan.get("status"), "content": deepcopy(plan["content"])})
    skill = session.skill_state
    if (not navigation["revisiting"] or stage in {"skills", "result"}) and (plan.get("status") == "confirmed" or skill.get("bindings")):
        batch = skill.get("candidate_batch") or {}
        result = batch.get("result") or {}
        cards.append({"key": "skills", "kind": "skills", "title": "选配 Skill",
                      "status": skill.get("status"), "candidates": deepcopy(result.get("candidates", [])),
                      "bindings": deepcopy(skill.get("bindings", []))})
    final = session.final_result
    if (not navigation["revisiting"] or stage == "result") and final.get("canonical_body"):
        cards.append({"key": "result", "kind": "result", "title": "你的任务提示词",
                      "status": final.get("status"), "text": render_task_prompt(final["canonical_body"], final.get("tone", "neutral"))})
    return cards


def conversation_plan_text(content):
    """Show all confirmation material inside the plan card."""
    goal = content.get("goal") or {}
    lines = [goal.get("summary", ""), "受众：" + goal.get("audience", ""), "范围：" + goal.get("scope", ""), ""]
    for step in sorted(content.get("steps", []), key=lambda s: s["order"]):
        lines.extend([f"{step['order']}. {step['title']}：{step['purpose']}", *step.get("actions", [])])
        for key, label in (("inputs", "输入"), ("outputs", "输出"), ("completion_criteria", "完成标准")):
            lines.append(label + "：" + "；".join(step.get(key, [])))
    lines.append("\n## 交付物")
    lines.extend(f"• {row['name']}：{row['description']}" for row in content.get("deliverables", []))
    lines.append("\n## 整体完成标准")
    lines.extend("• " + row["text"] for row in content.get("completion_criteria", []))
    lines.append("\n## 关键工作")
    for row in content.get("key_work", []):
        lines.append(f"• {row['title']}：{row['goal']}")
        for key, label in (("inputs", "输入"), ("outputs", "输出"), ("checkpoints", "检查")):
            lines.append(label + "：" + "；".join(row.get(key, [])))
    if content.get("unresolved_items"):
        lines.append("\n## 待补充事项")
        for row in content["unresolved_items"]:
            lines.extend(["• " + row["description"], "影响：" + row.get("impact", ""),
                          "可先进行：" + row.get("continuable_work", ""), "补充时机：" + row.get("confirm_by", "")])
    if content.get("suggestions"):
        lines.append("\n## AI 的可选建议")
        lines.extend("• " + row["text"] for row in content["suggestions"])
    return "\n".join(lines)


class ConversationWorkspaceMixin(ResponseWorkspaceMixin):
    def _apply_workspace_theme(self):
        """One continuous main surface; native settings controls keep their style."""
        theme = self.preferences["composer_theme"]
        colors = palette(theme)
        signature = (theme, self.preferences["font_size"])
        if signature != getattr(self, "_workspace_theme_signature", None):
            self.widgets["conversation_composer"].apply_theme()
            style = ttk.Style(self.root)
            style.configure("Flow.TNotebook", background=colors["bg"], borderwidth=0, padding=0)
            for name in ("Workspace.TFrame", "Workspace.TLabelframe", "Workspace.TCheckbutton", "Workspace.TButton"):
                style.configure(name, background=colors["bg"], foreground=colors["fg"])
            style.configure("Workspace.TLabel", background=colors["bg"], foreground=colors["fg"])
            style.configure("WorkspaceMuted.TLabel", background=colors["bg"], foreground=colors["muted"])
            style.configure("Workspace.Treeview", background=colors["bg"], fieldbackground=colors["bg"],
                            foreground=colors["fg"], borderwidth=0)
            style.configure("Workspace.Treeview.Heading", background=colors["bubble"], foreground=colors["fg"])
            # Vista's native field/header elements keep a white surface even
            # when ttk's background options are dark. Scope portable elements
            # to workspace tables; settings retain their platform components.
            table_elements={"Treeview.field":"Workspace.Treeview.field",
                            "Treeheading.cell":"Workspace.Treeheading.cell",
                            "Treeheading.border":"Workspace.Treeheading.border"}
            available=set(style.element_names())
            for source,target in table_elements.items():
                if target not in available:
                    style.element_create(target,"from","clam",source)
            def table_layout(nodes):
                result=[]
                for name,options in nodes:
                    options=dict(options)
                    if "children" in options:
                        options["children"]=table_layout(options["children"])
                    result.append((table_elements.get(name,name),options))
                return result
            style.layout("Workspace.Treeview",table_layout(style.layout("Treeview")))
            style.layout("Workspace.Treeview.Heading",table_layout(style.layout("Treeview.Heading")))
            style.map("Workspace.Treeview", background=[("selected", colors["bubble"])],
                      foreground=[("selected", colors["fg"])])
            self.root.configure(bg=colors["bg"])
            for name in ("workspace_shell", "workspace_header", "workspace_footer", "conversation_page",
                         "conversation_heading", "conversation_viewport", "conversation_hint", "workspace_status",
                         "workspace_guidance"):
                widget = self.widgets.get(name)
                if widget is not None:
                    widget.configure(bg=colors["bg"])
                    if isinstance(widget, tk.Label):
                        widget.configure(fg=colors["muted"])
            def header_theme(widget):
                if isinstance(widget, ReplyButton):
                    widget.apply_theme(theme)
                elif isinstance(widget, tk.Frame):
                    widget.configure(bg=colors["bg"])
                elif isinstance(widget, tk.Label):
                    widget.configure(bg=colors["bg"], fg=colors["muted"] if widget.cget("textvariable") else colors["fg"])
                for child in widget.winfo_children():
                    header_theme(child)
            header_theme(self.widgets["workspace_header"])
            header_theme(self.widgets["conversation_heading"])
            self.widgets["analyze_button"].apply_theme(theme)
            scroll = self.widgets["conversation_scrollbar"]
            scroll.palette = THEMES[theme]
            scroll.configure(bg=colors["bg"])
            scroll._draw()
            if getattr(self,"_workspace_popover",None):
                self._workspace_popover.close(immediate=True)
            self._workspace_theme_signature = signature
            logging.getLogger(__name__).debug("Unified workspace theme applied: theme=%s font_size=%s", *signature)

    def _theme_conversation_controls(self, widget):
        # Scope styles to the visible timeline/summary, leaving the default
        # components in settings and expanded editing details untouched.
        styles = {"TFrame": "Workspace.TFrame", "TLabel": "Workspace.TLabel",
                  "TLabelframe": "Workspace.TLabelframe", "TButton": "Workspace.TButton",
                  "TCheckbutton": "Workspace.TCheckbutton", "Treeview": "Workspace.Treeview"}
        kind = widget.winfo_class()
        if kind in styles:
            muted = kind == "TLabel" and "Muted" in str(widget.cget("style"))
            widget.configure(style="WorkspaceMuted.TLabel" if muted else styles[kind])
        elif isinstance(widget, tk.Text) and not isinstance(widget, MarkdownText):
            colors = palette(self.preferences["composer_theme"])
            widget.configure(bg=colors["bg"], fg=colors["fg"], insertbackground=colors["fg"])
        for child in widget.winfo_children():
            # Inline answers and the retained reasoning widget already own
            # their bubble/background and must not be overwritten here.
            if child in self._question_inputs.values() or isinstance(child, ResponseTrace):
                continue
            self._theme_conversation_controls(child)

    def _build_conversation_workspace(self, page):
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)
        self._conversation_signature = None
        self._workspace_popover = None
        self._conversation_labels = []
        self._conversation_buttons = {}
        self._conversation_frames = {}
        self._conversation_focus_key = "welcome"
        self._init_response_view()
        self.conversation_hint_var = tk.StringVar(value="发送你想完成的目标 · Enter 发送，Shift+Enter 换行")
        colors = palette(self.preferences["composer_theme"])
        heading = tk.Frame(page, bg=colors["bg"], padx=12, pady=6)
        heading.grid(row=0, column=0, sticky="ew")
        heading.columnconfigure(0, weight=1)
        self.conversation_title_var = tk.StringVar(value="新的任务")
        tk.Label(heading, textvariable=self.conversation_title_var, bg=colors["bg"], fg=colors["muted"],
                 font=ui_font(self.root)).grid(row=0, column=0, sticky="w")
        actions = self.widgets["workspace_actions"]
        summary_button = ReplyButton(actions,text="任务摘要",command=self.toggle_conversation_summary,theme=self.preferences["composer_theme"])
        summary_button.pack(side="left",padx=4)
        self.widgets.update(task_summary_button=summary_button)
        viewport = tk.Frame(page, bg=colors["bg"])
        viewport.grid(row=1, column=0, sticky="nsew")
        viewport.columnconfigure(0, weight=1)
        viewport.rowconfigure(0, weight=1)
        colors = palette(self.preferences["composer_theme"])
        canvas = tk.Canvas(viewport, highlightthickness=0, background=colors["bg"])
        canvas.grid(row=0, column=0, sticky="nsew")
        scroll = SlimScrollbar(viewport, THEMES[self.preferences["composer_theme"]], canvas.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scroll.set)
        content = tk.Frame(canvas, bg=colors["bg"], padx=32, pady=18)
        content.columnconfigure(0, weight=1)
        # A withdrawn host may not emit Canvas Configure yet. Give the
        # embedded column a width before labels start adapting their wrap;
        # otherwise their requested width feeds back into their allocation.
        initial_width = max(1, min(1060, canvas.winfo_reqwidth() - 24))
        window = canvas.create_window((0, 0), window=content, anchor="nw", width=initial_width)
        timeline = tk.Frame(content, bg=colors["bg"])
        timeline.grid(row=1, column=0, sticky="ew")
        timeline.columnconfigure(0, weight=1)
        hero = tk.Label(viewport, text=HERO_TEXT, bg=colors["bg"], fg=colors["fg"], font=ui_font(self.root, "title"), wraplength=900)
        self.widgets["conversation_hero"] = hero
        content.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")), add="+")

        def fit(event):
            width=max(1,min(1060,event.width-24))
            canvas.itemconfigure(window, width=width)
            canvas.coords(window,max(0,(event.width-width)/2),0)
            self.widgets["conversation_composer"].configure(width=width)
            hero.configure(wraplength=max(200, event.width-100))
        canvas.bind("<Configure>", fit, add="+")
        self._page_canvases.add(canvas)
        self._page_canvas_by_frame[str(page)] = canvas
        self.conversation_summary_var = tk.StringVar()
        self._conversation_summary_open = False
        composer = PromptComposer(page, self)
        composer.grid(row=3, column=0, padx=12, pady=(8, 10))
        continue_answers = ReplyButton(page, text="继续整理回答", command=self.run_primary_action,
                                       theme=self.preferences["composer_theme"])
        continue_answers.grid(row=2, column=0, sticky="e", padx=12)
        continue_answers.grid_remove()
        self.widgets["conversation_continue_answers"] = continue_answers
        entry, send = composer.entry, composer.send_button
        self._bind_context_menu(entry)
        self.widgets.update(conversation_timeline=timeline, conversation_input=entry, conversation_send_button=send,
                            conversation_composer=composer, conversation_model_button=composer.model_button,
                            conversation_page=page, conversation_heading=heading, conversation_viewport=viewport,
                            conversation_scrollbar=scroll,
                            requirements_page_canvas=canvas, requirements_page_content=content)
        logging.getLogger(__name__).debug("Conversation viewport ready: initial content width=%spx", initial_width)
        return page

    def _conversation_enter(self, event):
        if event.state & 0x0001:
            return None
        self.send_conversation_message()
        return "break"

    def _conversation_locked(self):
        return self.busy or self.delivery_busy or self._skill_search_busy

    def send_conversation_message(self):
        """A message is a goal or an answer/supplement, never implicit consent."""
        if self._conversation_locked():
            return
        entry = self.widgets["conversation_input"]
        text = entry.get("1.0", "end-1c").strip()
        if not text:
            entry.focus_set()
            return
        if not self.session.task_text:
            task = self.widgets["task_text"]
            task.delete("1.0", "end")
            task.insert("1.0", text)
            self._sync_input()
            entry.delete("1.0", "end")
            self.refresh()
            if self._missing_generation_config():
                self.status_var.set("目标已记录；请先在设置中确认模型，再继续整理。")
                self.show_settings()
            else:
                self.start_analysis()
        else:
            # The original goal remains intact; edits are sourced supplements.
            if not self.widgets["task_text"].get("1.0", "end-1c").strip():
                self.widgets["task_text"].insert("1.0", self.session.task_text)
            self.answer_var.set(text)
            self.submit_guided_answer()
            if not self.answer_var.get().strip():
                entry.delete("1.0", "end")
        self._conversation_scroll_latest(force=True)

    def toggle_conversation_summary(self):
        self._toggle_workspace_popover("summary")

    def toggle_requirements_review(self):
        self.show_workspace(0)
        self._conversation_focus_key = "requirements"
        self._conversation_scroll_latest(force=True)

    def toggle_plan_review(self):
        self.show_workspace(0)
        self._conversation_focus_key = "plan"
        self._conversation_scroll_latest(force=True)

    def toggle_conversation_result_options(self):
        self._toggle_workspace_popover("result")

    def _toggle_workspace_popover(self, kind):
        from .interaction_ui import AnchoredPanel
        previous = getattr(self._workspace_popover,"kind",None)
        if self._workspace_popover:
            self._workspace_popover.close(immediate=True)
            if previous==kind:
                return
        button, title = {"result": ("result_details", "语气和附注"),
                          "summary": ("task_summary_button", "当前任务摘要")}[kind]
        anchor=self._conversation_buttons[button] if kind == "result" else self.widgets[button]
        def closed():
            self._workspace_popover=None
            self._conversation_summary_open=False
        panel=AnchoredPanel(self,anchor,title,on_close=closed)
        panel.kind=kind
        self._workspace_popover=panel
        self._conversation_summary_open=kind=="summary"
        self._render_workspace_popover()
        logging.getLogger(__name__).info("Workspace review opened; task=%s kind=%s plan_status=%s",
                                        self.session.task_id, kind, self.session.plan.get("status"))

    def _render_workspace_popover(self):
        panel=self._workspace_popover
        if not panel or panel.closed:
            return
        if panel.kind == "result":
            anchor = self._conversation_buttons.get("result_details")
            if anchor is None or not anchor.winfo_exists():
                panel.close(immediate=True)
                return
            panel.anchor = anchor
        for child in panel.body.winfo_children():
            child.destroy()
        self._conversation_render_token=self._conversation_token()
        if panel.kind=="summary":
            self._conversation_reading(panel.body,self.conversation_summary_var.get(),height=12)
        elif panel.kind=="result":
            self._render_result_options(panel.body)
        self._theme_conversation_controls(panel.body)

    def _render_result_options(self, parent):
        final = self.session.final_result
        available = final.get("status") in {"draft", "confirmed"}
        self._conversation_label(parent, "提示词语气")
        tone = ttk.Combobox(parent, textvariable=self.final_tone_var, state="readonly" if available else "disabled",
                            values=("中性", "适度礼貌"), width=16)
        tone.pack(anchor="w", pady=(0, 8))
        tone.bind("<<ComboboxSelected>>", lambda _event: self.change_final_tone())
        self.widgets["conversation_final_tone"] = tone
        notes = (final.get("content") or {}).get("user_notes", [])
        if notes:
            self._conversation_reading(parent, "\n\n".join(row["text"] for row in notes), height=6)
        else:
            self._conversation_label(parent, "还没有附注。")
        self._conversation_button(parent, "add_final_note", "添加附注", self.add_final_note, enabled=available)

    def toggle_conversation_details(self, opened=None):
        # Compatibility for old navigation callers; duplicate details removed.
        if opened and self._workspace_popover is None:
            self.toggle_requirements_review()

    def _conversation_scroll_latest(self, *, force=False):
        canvas = self.widgets.get("requirements_page_canvas")
        if canvas is not None and (force or canvas.yview()[1] >= 0.96):
            self.root.update_idletasks()
            target = self._conversation_frames.get(self._conversation_focus_key)
            region = canvas.bbox("all")
            if target is not None and region and region[3] > 0:
                y = canvas.canvasy(0) + target.winfo_rooty() - canvas.winfo_rooty()
                canvas.yview_moveto(max(0, y-12) / region[3])
            else:
                canvas.yview_moveto(1)

    def _conversation_token(self):
        # Guard even references retained after a card was destroyed/replaced.
        return json.dumps({"instance": self._session_instance_token,
                           "task": self.session.task_id, "requirements": self.session.requirements_preview(),
                           "interview": {key: self.session.control.get(key) for key in ("interview_rounds_used", "interview_round_limit")},
                           "plan": self.session.plan_preview(), "skill": self.session.skill_state,
                           "final": self.session.final_result, "navigation": self.session.workspace_navigation()}, ensure_ascii=False, sort_keys=True)

    def navigate_workspace(self, direction):
        if self._conversation_locked():
            self.cancel_active_request()
        self.session.navigate_workspace(direction)
        self._answer_target_id = None
        self.show_workspace(0)
        self.refresh()
        self._conversation_focus_key = "navigation"
        self._conversation_scroll_latest(force=True)

    def _conversation_action(self, token, command, *, allow_locked=False, scope=None):
        if self._conversation_locked() and not allow_locked:
            return
        if allow_locked and scope != self._active_stop_token:
            return
        if token != self._conversation_token():
            self.status_var.set("内容已变化，请查看更新后的卡片再操作。")
            self.refresh()
            return
        command()
        self._conversation_scroll_latest(force=True)

    def _conversation_card(self, title, *, user=False):
        parent = self.widgets["conversation_timeline"]
        shell = MessageShell(parent, title, theme=self.preferences["composer_theme"], user=user)
        shell.grid(row=self._conversation_next_row, column=0, sticky="ew", pady=(0, 18))
        self._conversation_next_row += 1
        return shell.body

    def _conversation_label(self, parent, text):
        colors = getattr(parent, "_reply_colors", palette(self.preferences["composer_theme"]))
        label = tk.Label(parent, text=text, justify="left", anchor="w", bg=colors["bg"], fg=colors["fg"], font=ui_font(parent),
                         wraplength=max(100, min(getattr(parent, "_reply_wrap_limit", 2000),
                                                self.widgets["requirements_page_canvas"].winfo_width()-170)))
        label.pack(fill="x", anchor="w", pady=(0, 6))
        # Use allocated label space, including after a newly rendered batch.
        # The viewport can be wider than the capped conversation column.
        def fit_text(event):
            limit = getattr(parent, "_reply_wrap_limit", 2000)
            available = max(1, event.width - 2 * label.winfo_pixels(label.cget("padx"))
                            - 2 * label.winfo_pixels(label.cget("borderwidth")))
            wrap = min(limit, available)
            if label.winfo_pixels(label.cget("wraplength")) != wrap:
                label.configure(wraplength=wrap)
                logging.getLogger(__name__).debug("Conversation text reflow; width=%s wrap=%s chars=%s",
                                                  event.width, wrap, len(text))
        # User bubbles own their width and wrap in MessageShell.fit; a second
        # geometry callback there would compete and repeatedly relayout.
        if not hasattr(parent, "_reply_action_host"):
            label.bind("<Configure>", fit_text, add="+")
        self._conversation_labels.append(label)
        return label

    def _conversation_button(self, parent, key, label, command, *, enabled=True, allow_locked=False):
        token = self._conversation_render_token
        scope = self._active_stop_token
        button = ReplyButton(parent, text=label, command=lambda: self._conversation_action(token, command, allow_locked=allow_locked, scope=scope),
                             theme=self.preferences["composer_theme"],
                             state="normal" if enabled and (allow_locked or not self._conversation_locked()) else "disabled")
        # Individual rows keep every action reachable on small windows.
        button.pack(anchor="w", pady=3)
        self._conversation_buttons[key] = button
        return button

    def _conversation_reading(self, parent, text, *, height=10, section_titles=()):
        frame = tk.Frame(parent, bg=palette(self.preferences["composer_theme"])["bg"])
        frame.pack(fill="x", pady=5)
        widget = MarkdownText(frame, text, theme=self.preferences["composer_theme"], height=height, section_titles=section_titles)
        widget.pack(side="left", fill="both", expand=True)
        scroll = SlimScrollbar(frame, THEMES[self.preferences["composer_theme"]], widget.yview)
        widget.pack_forget()
        frame.columnconfigure(0, weight=1)
        widget.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        widget.configure(yscrollcommand=scroll.set)
        self._bind_context_menu(widget)
        return widget

    def _conversation_select_preview(self, key, operation):
        tree = self.widgets["requirements_preview_tree"]
        if tree.exists(key):
            tree.selection_set(key)
            operation()

    def _conversation_requirement_action(self, operation):
        tree = self.widgets.get("conversation_requirements_tree")
        if tree is not None and tree.winfo_exists() and tree.selection():
            key = tree.selection()[0]
            before = {row["item_id"] for row in self.session.requirements}
            logging.getLogger(__name__).info("Requirement table action; task=%s row=%s action=%s", self.session.task_id, key, operation.__name__)
            self._conversation_select_preview(key, operation)
            added = {row["item_id"] for row in self.session.requirements} - before
            current = self.widgets.get("conversation_requirements_tree")
            if key.startswith("r:") and len(added) == 1 and current is not None and current.winfo_exists():
                current.selection_set("r:" + added.pop())
                self._conversation_show_requirement_selection()

    def _conversation_show_requirement_selection(self, _event=None):
        tree = self.widgets.get("conversation_requirements_tree")
        if tree is None or not tree.winfo_exists():
            return
        selected = tree.selection()
        row = self._conversation_requirement_rows.get(selected[0]) if selected else None
        if selected:
            tree.see(selected[0])
        text = row.get("text", "") if row else "选中一行查看完整需求。"
        self._set_text_widget(self.widgets["conversation_requirement_details"], text)
        logging.getLogger(__name__).debug("Requirement table selection; task=%s row=%s", self.session.task_id, selected[0] if selected else None)
        unlocked = not self._conversation_locked()
        for key in ("edit_requirement", "remove_requirement"):
            self._conversation_buttons[key].configure(state="normal" if row and unlocked else "disabled")
        available = {"adopt_requirement": bool(row and selected[0].startswith("p:") and (
                     row.get("operation") in {"replace", "withdraw"} or row.get("kind") == "pending_interpretation"))}
        for key, applies in available.items():
            button = self._conversation_buttons[key]
            button.configure(state="normal" if applies and unlocked else "disabled")
            button.pack(side="left", padx=(0, 8), pady=3) if applies else button.pack_forget()

    def _conversation_requirements_table(self, parent, data):
        from .ui import FIELD_LABELS, KIND_LABELS
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=6)
        frame.columnconfigure(0, weight=1)
        columns = ("field", "text", "kind", "state")
        rows = [(prefix + ":" + row[idkey], row) for prefix, items, idkey in (
            ("r", data["requirements"], "item_id"), ("p", data["proposals"], "proposal_id")) for row in items]
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse", height=min(5, max(3, len(rows))))
        tree.grid(row=0, column=0, sticky="ew")
        for column, title, width in zip(columns, ("需求类型", "需求内容", "内容来源", "确认状态"), (110, 640, 110, 110)):
            tree.heading(column, text=title)
            tree.column(column, width=width, minwidth=180 if column == "text" else 90, stretch=column == "text")
        vertical = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        label_font = ui_font(self.root)
        fixed_width = max(110, label_font.measure("确认状态") + 24)
        for column in ("field", "kind", "state"):
            tree.column(column, width=fixed_width, minwidth=fixed_width)
        def fit_table(event):
            tree.column("text", width=max(180, event.width - 3 * fixed_width - 24))
        frame.bind("<Configure>", fit_table, add="+")
        self.widgets["conversation_requirements_tree"] = tree
        self.widgets["requirements_preview_tree"] = tree
        self._conversation_requirement_rows = dict(rows)
        for key, row in rows:
            if key.startswith("p:"):
                status = "待确认解释" if row.get("kind") == "pending_interpretation" else "待核对建议"
            else:
                status = "已确认" if row.get("confirmation") == "confirmed" else "待重新核对" if row.get("confirmation") == "review_needed" else "待确认"
            content = " ".join(row.get("text", "").split())
            field_name = FIELD_LABELS.get(row.get("field")) or {"background": "背景", "features": "功能范围",
                "existing_code": "项目材料", "runtime": "运行环境", "preferences": "风格偏好"}.get(row.get("field"), row.get("field", "要求"))
            tree.insert("", "end", iid=key, values=(field_name,
                content[:180] + ("…" if len(content) > 180 else ""), KIND_LABELS.get(row.get("kind"), "AI 建议"), status))
        self.widgets["conversation_requirement_details"] = self._conversation_reading(parent, "选中一行查看完整需求。", height=4)
        actions = ttk.Frame(parent)
        actions.pack(fill="x", pady=3)
        for key, label, operation in (
            ("edit_requirement", "修改选中需求", self.edit_preview_item),
            ("remove_requirement", "移除选中需求", self.remove_preview_item),
            ("adopt_requirement", "采用选中修改", self.adopt_preview_change),
        ):
            self._conversation_button(actions, key, label, lambda op=operation: self._conversation_requirement_action(op),
                                      enabled=False).pack_configure(side="left", padx=(0, 8))
        tree.bind("<<TreeviewSelect>>", self._conversation_show_requirement_selection)

    def _conversation_select_skill(self, candidate_id):
        self.select_skill_candidates([candidate_id])

    def _conversation_cancel_skill(self, binding_id):
        self.cancel_selected_skills([binding_id])

    def _conversation_question_option(self, text):
        self.widgets["conversation_input"].delete("1.0", "end")
        self.widgets["conversation_input"].insert("1.0", text)
        self.widgets["conversation_input"].focus_set()

    def _conversation_reopen_question(self, question_id):
        row = next((q for q in reversed(self.session.question_history) if q["question_id"] == question_id), None)
        if row is None:
            return
        logging.getLogger(__name__).info("Historical answer reopened: task=%s question=%s",self.session.task_id,question_id)
        self._answer_target_id = question_id
        self.question_context_var.set(self._format_guided_question_card(row))
        self.show_workspace(0)
        self.refresh()
        self.widgets["conversation_input"].focus_set()

    def _conversation_cancel_reanswer(self):
        self._answer_target_id = None
        self.refresh()

    def _conversation_find_skills(self):
        self.confirm_plan_and_find_skills()
        self.show_workspace(0)
        self.refresh()

    def _conversation_review_plan(self):
        try:
            self.session.mark_key_work_reviewed(list(self.session.plan.get("pending_key_work_review_ids", [])))
        except SessionStateError as exc:
            logging.getLogger(__name__).warning("Conversation plan review rejected", exc_info=True)
            self.status_var.set(str(exc))
        self.refresh()

    def _conversation_toggle_skills(self):
        self.show_all_skills_var.set(not self.show_all_skills_var.get())
        self.refresh()

    def _conversation_defer_interview_unknowns(self):
        if self._conversation_locked():
            return
        try:
            count = self.session.defer_remaining_interview_unknowns()
        except SessionStateError as exc:
            logging.getLogger(__name__).warning("Interview closing choice rejected; task=%s", self.session.task_id, exc_info=True)
            self.status_var.set(str(exc))
        else:
            self.status_var.set(f"已将 {count} 项未知保留到使用提示词时补充。请继续核对需求和方案。")
        self.refresh()
        self._conversation_scroll_latest(force=True)

    def _conversation_continue_interview(self):
        if self._conversation_locked():
            return
        if self._missing_generation_config():
            self.status_var.set("请先确认模型设置，再选择继续追问。")
            self.show_workspace(self._settings_page_index)
            return
        try:
            self.session.authorize_next_interview_round()
        except SessionStateError as exc:
            logging.getLogger(__name__).warning("Interview continuation rejected; task=%s", self.session.task_id, exc_info=True)
            self.status_var.set(str(exc))
            self.refresh()
            return
        self.status_var.set("已选择继续询问；回答整理后会再次核对是否需要补充。")
        self.refresh()
        self.start_analysis()

    def _refresh_conversation(self):
        if "conversation_timeline" not in self.widgets or getattr(self, "_conversation_refreshing", False):
            return
        self.widgets["conversation_composer"].refresh()
        self._apply_workspace_theme()
        cards = conversation_cards(self.session)
        shown = json.dumps([self._requirements_preview_shown, self._plan_preview_shown], ensure_ascii=False, sort_keys=True)
        business_token = self._conversation_token()
        signature = (business_token, shown, tuple(self._missing_generation_config()), self._visible_task_text(),
                     self._conversation_locked(), self._answer_target_id, self.notebook.select(),
                     self.skill_status_var.get(), self.status_var.get(), self.show_all_skills_var.get(),
                     self.skill_source_filter_var.get(),
                     self.preferences["display_limit"], self.preferences["font_size"], self.preferences["composer_theme"],
                     tuple((r.get("id"), r.get("status")) for r in self.session.control.get("response_traces", []) if isinstance(r, dict)))
        if signature == self._conversation_signature:
            return
        canvas = self.widgets["requirements_page_canvas"]
        old_y = canvas.yview()[0]
        follow = canvas.yview()[1] >= 0.96
        self._conversation_labels = []
        self._conversation_buttons = {}
        self._conversation_frames = {}
        self._conversation_render_token = business_token
        old_skill_tree = self.widgets.get("conversation_skill_candidates_tree")
        skill_selection = old_skill_tree.selection() if old_skill_tree is not None and old_skill_tree.winfo_exists() else ()
        skill_y = old_skill_tree.yview()[0] if old_skill_tree is not None and old_skill_tree.winfo_exists() else 0
        old_requirements = self.widgets.get("conversation_requirements_tree")
        requirement_selection = old_requirements.selection() if old_requirements is not None and old_requirements.winfo_exists() else ()
        requirement_y = old_requirements.yview()[0] if old_requirements is not None and old_requirements.winfo_exists() else 0
        timeline_path = str(self.widgets["conversation_timeline"]) + "."
        self._wheel_bound_widgets = [widget for widget in self._wheel_bound_widgets
                                     if not str(widget).startswith(timeline_path)]
        for key, widget in self._question_inputs.items():
            if widget.winfo_exists():
                self._question_drafts[key] = widget.get("1.0", "end-1c")
        self._question_inputs = {}
        colors = palette(self.preferences["composer_theme"])
        canvas.configure(bg=colors["bg"])
        self.widgets["requirements_page_content"].configure(bg=colors["bg"])
        self.widgets["conversation_timeline"].configure(bg=colors["bg"])
        for child in self.widgets["conversation_timeline"].winfo_children():
            if not isinstance(child, ResponseTrace):
                child.destroy()
        hero = self.widgets["conversation_hero"]
        hero.configure(bg=colors["bg"], fg=colors["fg"])
        if not self.session.task_text:
            hero.place(relx=.5, rely=.5, anchor="center")
        else:
            hero.place_forget()
        self._conversation_next_row = 0
        self._conversation_refreshing = True
        try:
            for card in cards:
                if card["kind"] == "welcome":
                    continue
                if self._answer_target_id and card["kind"] == "question":
                    continue
                self._render_conversation_card(card)
            new_requirements = self.widgets.get("conversation_requirements_tree")
            if new_requirements is not None and new_requirements.winfo_exists():
                retained = [key for key in requirement_selection if new_requirements.exists(key)]
                if retained:
                    new_requirements.selection_set(retained)
                    self._conversation_show_requirement_selection()
                new_requirements.yview_moveto(requirement_y)
            new_skill_tree = self.widgets.get("conversation_skill_candidates_tree")
            if new_skill_tree is not None and new_skill_tree.winfo_exists():
                retained = [key for key in skill_selection if new_skill_tree.exists(key)]
                if retained:
                    new_skill_tree.selection_set(*retained)
                new_skill_tree.yview_moveto(skill_y)
                self._show_skill_browser_selection("conversation_skill")
            if self._answer_target_id:
                card = self._conversation_card("补答历史问题")
                self._conversation_frames["reanswer"] = card
                self._conversation_label(card, self.question_context_var.get())
                self._conversation_button(card, "cancel_reanswer", "取消补答，回到当前问题", self._conversation_cancel_reanswer)
            action = self._primary_action()
            # Confirmation/actions live with the relevant reply. Only recovery
            # or unrepresented actions need the compact footer shortcut.
            self._conversation_buttons["primary"] = self.widgets["analyze_button"]
            continue_answers = self.widgets["conversation_continue_answers"]
            continue_answers.configure(state="normal" if action.enabled else "disabled")
            if action.kind == "analyze_answer":
                continue_answers.grid()
                self._conversation_buttons["primary"] = continue_answers
            else:
                continue_answers.grid_remove()
            represented = {"focus_question", "review_remaining_unknowns", "confirm_requirements", "confirm_plan_generate",
                           "view_plan", "focus_final", "integrate_skills", "generate_final", "busy", "focus_task", "analyze_answer", "continue_stage"}
            footer = self.widgets["workspace_footer"]
            if self.notebook.index(self.notebook.select()) != 0 or (self.session.task_text and action.kind not in represented):
                footer.grid()
            else:
                footer.grid_remove()
            if self._blocking_gaps() and not self.session.questions_for_review():
                card = tk.Frame(self.widgets["conversation_timeline"], bg=colors["bg"])
                card.grid(row=self._conversation_next_row, column=0, sticky="ew")
                self._conversation_next_row += 1
                explanation = (self._requirements_preview_shown or {}).get("draft_explanation", "")
                self._conversation_label(card, explanation)
                self._conversation_button(card, "draft", "保留未知，先做草稿", self.continue_with_draft,
                                          enabled=not self._preview_check(draft=True))
            stage = self.session.workspace_navigation()["stage"]
            control_basis = (self._session_instance_token, self.session.plan.get("plan_version"),
                             self.session.plan.get("status"), stage, "plan" in self._conversation_frames, self.delivery_busy)
            if control_basis != getattr(self, "_stage_controls_log_basis", None):
                self._stage_controls_log_basis = control_basis
                logging.getLogger(__name__).debug("Stage controls updated; task=%s stage=%s plan_visible=%s cancel_inline=%s",
                                                 self.session.task_id, stage, control_basis[-2], "cancel_request" in self._conversation_buttons)
            self.conversation_title_var.set((self.session.task_text.splitlines()[0][:38] if self.session.task_text else "新的任务"))
            heading = self.widgets["conversation_heading"]
            heading.grid() if self.session.task_text else heading.grid_remove()
            confirmed = self.session.confirmed_requirements_version == self.session.requirement_version
            plan_status = {"not_started": "未生成", "draft": "待确认", "confirmed": "已确认", "stale": "已过期"}.get(self.session.plan.get("status"), "待更新")
            self.conversation_summary_var.set(
                f"目标：{self.session.task_text or '尚未发送'}\n"
                f"需求：{'已确认' if confirmed else '待核对'} · {len(self.session.requirements)} 项 · "
                f"方案：{plan_status} · 已选 Skill：{len(self.session.skill_state.get('bindings', []))}\n"
                + "\n".join("• " + r["text"] for r in self.session.requirements if r.get("confirmation") == "confirmed"))
            self._render_workspace_popover()
            closing = "interview_unknowns" in self._conversation_frames
            phase = "核对待补充事项" if self.session.questions_for_review() else "核对剩余未知" if closing else "提示词已生成" if self.session.final_result.get("status") in {"draft", "confirmed"} else "Skill 可选" if self.session.plan.get("status") == "confirmed" else "核对方案" if self.session.plan.get("status") == "draft" else "核对需求" if self.session.sources else "描述目标"
            self._flow_progress.set("现在：" + phase)
            hint = "发送你想完成的目标" if not self.session.task_text else "回答当前问题" if self.session.questions_for_review() or self._answer_target_id else "请核对对话中的需求，确认后生成方案" if not confirmed and (self.session.requirements or self.session.pending_proposals) else "补充或修改要求，AI 会重新整理受影响的内容"
            self.conversation_hint_var.set(hint + " · Enter 发送，Shift+Enter 换行")
            self.widgets["conversation_composer"].refresh()
            self._theme_conversation_controls(self.widgets["conversation_timeline"])
            if self._answer_target_id:
                self._conversation_focus_key = "reanswer"
            elif self.session.questions_for_review():
                self._conversation_focus_key = "active_question"
            elif closing:
                self._conversation_focus_key = "interview_unknowns"
            elif self.session.final_result.get("status") in {"draft", "confirmed"}:
                self._conversation_focus_key = "result"
            elif self.session.plan.get("status") == "draft":
                self._conversation_focus_key = "plan"
            elif self.session.plan.get("status") == "confirmed":
                self._conversation_focus_key = "skills"
            else:
                self._conversation_focus_key = "requirements" if self.session.requirements or self.session.pending_proposals else "welcome"
            if self.session.workspace_navigation()["revisiting"]:
                self._conversation_focus_key = "navigation"
            self._bind_conversation_wheel(self.widgets["conversation_timeline"])
            self._conversation_signature = signature
        finally:
            self._conversation_refreshing = False
        self.root.update_idletasks()
        self._conversation_scroll_latest(force=True) if follow else canvas.yview_moveto(old_y)

    def _bind_conversation_wheel(self, widget):
        tags = widget.bindtags()
        if self._wheel_bindtag not in tags:
            widget.bindtags((tags[0], self._wheel_bindtag, *tags[1:]))
            self._wheel_bound_widgets.append(widget)
        for child in widget.winfo_children():
            self._bind_conversation_wheel(child)

    def _render_conversation_card(self, data):
        kind = data["kind"]
        if kind == "trace":
            self._render_response_trace(data["trace"])
            return
        card = self._conversation_card(data["title"], user=kind == "user")
        self._conversation_frames[data["key"]] = card
        if kind in {"welcome", "user", "history_question"}:
            self._conversation_label(card, data["text"])
            if kind == "user" and data.get("question_id"):
                from .interaction_ui import GlassButton
                host=card._reply_action_host
                host.grid(row=0,column=0,padx=(0,12))
                token=self._conversation_render_token
                question_id=data["question_id"]
                button=GlassButton(host,text="补答这个问题",icon_name="loop",palette=THEMES[self.preferences["composer_theme"]],
                                   command=lambda key=question_id:self._conversation_action(token,lambda:self._conversation_reopen_question(key)))
                button.pack()
                button.configure(state="disabled" if self._conversation_locked() else "normal")
                self._conversation_buttons[data["reanswer_key"]]=button
        elif kind == "navigation":
            if data["previous"]:
                self._conversation_button(card, "back_stage", "返回上一步", lambda: self.navigate_workspace("previous"), allow_locked=True)
            if data["next"]:
                self._conversation_button(card, "continue_stage", "继续下一步", lambda: self.navigate_workspace("next"))
        elif kind == "requirements":
            self._render_requirements_review(card, data)
            logging.getLogger(__name__).debug("Requirements review rendered in conversation; task=%s confirmed=%s",
                                             self.session.task_id, data["confirmed"])
        elif kind == "question":
            self._conversation_label(card, self._format_guided_question_card(data["question"]))
            if data["question"].get("clarification_scope") == "plan":
                self._conversation_label(card, "补答后重新核对；暂缓则保留未知。")
            self._inline_question(card, data["question"], first=data.get("first", True))
        elif kind == "interview_unknowns":
            self._conversation_label(card, data["text"])
            pending = any(q.get("assessment_status") == "pending" and q.get("disposition") == "answered"
                          for q in self.session.question_history)
            self._conversation_label(card, "请先整理已记录的回答，再核对清单。" if pending else
                                     "可以在输入框补充已知内容，或明确将清单中的未知留给下游 AI 核对；这不会自动确认需求或方案。")
            decisions = ttk.Frame(card)
            decisions.pack(fill="x", pady=3)
            self._conversation_button(decisions, "continue_interview", "继续，再问一轮",
                                      self._conversation_continue_interview, enabled=not pending).pack_configure(side="left", padx=(0, 8))
            self._conversation_button(decisions, "defer_interview_unknowns", "结束追问，使用时再补充",
                                      self._conversation_defer_interview_unknowns, enabled=not pending).pack_configure(side="left")
        elif kind == "plan":
            self._render_plan_review(card, data)
            log_basis = (self._session_instance_token, self.session.plan.get("plan_version"), data["status"])
            if log_basis != getattr(self, "_inline_plan_log_basis", None):
                self._inline_plan_log_basis = log_basis
                logging.getLogger(__name__).debug("Plan review rendered inline; task=%s version=%s status=%s",
                                                 self.session.task_id, log_basis[1], data["status"])
        elif kind == "skills":
            self._conversation_label(card, self.skill_status_var.get())
            self._conversation_label(card, "Skill 可用于具体步骤；你也可以直接跳过。")
            if self.delivery_busy:
                button = ReplyButton(card, text="取消本次整合", command=self.cancel_delivery_request,
                                     theme=self.preferences["composer_theme"])
                button.pack(anchor="w", pady=3)
                self._conversation_buttons["cancel_request"] = button
            basis_current = self._skill_basis_is_current()
            reviewed = not self.session.questions_for_review(respect_interview_limit=False)
            self._conversation_button(card, "find_skills", "查找本地 Skill", self.find_skills, enabled=reviewed and self.session.plan.get("status") == "confirmed")
            local = (self.session.skill_state.get("search_state") or {}).get("local") or {}
            self._conversation_button(card, "find_online", "继续联网查找", self.search_online_skills, enabled=reviewed and local.get("status") in {"ok", "no_match", "error", "cancelled"} and self.session.plan.get("status") == "confirmed")
            browser = ttk.Frame(card)
            browser.pack(fill="x", pady=6)
            self._build_skill_browser(browser, "conversation_skill")
            self._refresh_skill_browser("conversation_skill")
            if data["bindings"]:
                self._conversation_button(card, "integrate", "整合所选 Skill 并生成提示词", self.integrate_selected_skills, enabled=reviewed and basis_current)
                self._conversation_button(card, "direct_skills", "用已选 Skill 直接生成提示词", self.generate_no_skill_final, enabled=reviewed and basis_current)
            self._conversation_button(card, "skip_skills", "跳过 Skill，直接生成提示词", self.skip_skills, enabled=reviewed and self.session.plan.get("status") == "confirmed")
        elif kind == "result":
            self._conversation_label(card, {"draft": "提示词已生成，可复制和导出。", "confirmed": "提示词已确认，可复制和导出。", "stale": "来源已变化，这份旧提示词需要更新。"}.get(data["status"], data["status"]))
            self._conversation_reading(card, data["text"], height=14, section_titles=PROMPT_SECTIONS)
            available = data["status"] in {"draft", "confirmed"}
            self._conversation_button(card, "copy", "复制提示词", self.copy_current_prompt, enabled=available)
            self._conversation_button(card, "export", "导出方案和提示词", self.export_current_result, enabled=available)
            self._conversation_button(card, "save", "保存会话", self.save)
            if data["status"] == "draft":
                self._conversation_button(card, "confirm_final", "确认最终提示词", self.confirm_final_result,
                                          enabled=not (self.session.final_result.get("content") or {}).get("plan_review_pending"))
            self._conversation_button(card, "result_details", "语气和附注", self.toggle_conversation_result_options, enabled=available)

    def _render_plan_review(self, card, data):
        status = {"draft": "待确认", "confirmed": "已确认", "stale": "需求已变化，旧方案已过期"}.get(data["status"], data["status"])
        self._conversation_label(card, "方案状态：" + status)
        self.widgets["conversation_plan_reading"] = self._conversation_reading(card, conversation_plan_text(data["content"]), height=12)
        current = data["status"] in {"draft", "confirmed"}
        self._conversation_button(card, "edit_plan", "展开完整方案并编辑", lambda: self.show_workspace(1), enabled=current)
        if self.session.plan.get("pending_key_work_review_ids", []):
            self._conversation_button(card, "review_plan", "已核对修改后的关键工作", self._conversation_review_plan, enabled=current)
        if data["status"] == "draft":
            needs_review = bool(self.session.questions_for_review(respect_interview_limit=False))
            if needs_review:
                self._conversation_label(card, "还有待核对事项，请先逐项回答或明确暂缓，再确认方案。")
            self._conversation_button(card, "confirm_plan", "确认方案并生成提示词", self.confirm_plan_and_generate, enabled=not needs_review)
            self._conversation_button(card, "find_skills", "确认方案并查找 Skill", self._conversation_find_skills, enabled=not needs_review)

    def _render_requirements_review(self, card, data):
        self._conversation_label(card, "请核对下面的内容。AI 的建议和推测会单独标明，确认后才会形成方案。" if not data["confirmed"] else "这些是当前已经确认的要求。修改后会重新核对并更新方案。")
        suggested_result = (self._requirements_preview_shown or {}).get("suggested_task_result")
        if suggested_result:
            self._conversation_label(card, "想要的结果先按你的原任务整理：" + suggested_result)
        self._conversation_requirements_table(card, data)
        if self.session.open_conflicts:
            self._conversation_label(card,"需要核对的冲突：\n"+"\n".join(row["description"] for row in self.session.open_conflicts))
        if not data["confirmed"]:
            reason=self._preview_check()
            if reason:
                self._conversation_label(card,"确认前请处理："+reason)
            self._conversation_button(card, "confirm_requirements", "确认需求并生成方案", self.confirm_preview_and_plan,
                                      enabled=not self._preview_check() and not self._missing_generation_config())
            if self.session.analysis_basis_version != self.session.requirement_version:
                self._conversation_button(card, "reanalyze_requirements", "重新整理需求", self.start_analysis,
                                          enabled=not self._missing_generation_config())
