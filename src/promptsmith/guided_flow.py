"""User-facing progression on top of the existing session/workflow guards.

Viewing a section is read-only. The saved preview, not a freshly synthesized
snapshot at click time, is the authority for a consolidated user confirmation.
"""
from __future__ import annotations

from .typography import ui_font

from copy import deepcopy
import logging
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from .session import SessionState, SessionStateError
from .finalization import DeliveryValidationError
from .conversation import ConversationWorkspaceMixin
from .settings_ui import SettingsMixin
from .response_ui import ReplyButton, palette


class GuidedFlowMixin(ConversationWorkspaceMixin, SettingsMixin):
    @staticmethod
    def _format_guided_question(question, *, number: int | None = None) -> str:
        """Render a follow-up question as one complete, readable context."""
        if not isinstance(question, dict):
            return "补充说明"
        text = str(question.get("text") or question.get("question_text") or "补充说明").strip()
        prefix = f"{number}. " if number is not None else ""
        body = [text]
        reason = str(question.get("reason") or "").strip()
        if reason:
            body.append(reason)
        return prefix + "".join(body)

    @staticmethod
    def _format_guided_question_card(question, *, number: int | None = None) -> str:
        """Render only the user-facing question and its answer choices."""
        if not isinstance(question, dict):
            return "请补充你想说明的内容。"
        text = str(question.get("text") or question.get("question_text") or "请补充你想说明的内容。").strip()
        prefix = f"{number}. " if number is not None else ""
        return prefix + text

    @classmethod
    def _format_guided_questions(cls, questions) -> str:
        rows = [row for row in questions if isinstance(row, dict)]
        return "\n\n".join(
            cls._format_guided_question(row, number=index)
            for index, row in enumerate(rows, start=1)
        )

    @staticmethod
    def _format_guided_interpretations(interpretations) -> str:
        """Keep model interpretations in the same readable question context."""
        rows = [row for row in interpretations if isinstance(row, dict)]
        parts = []
        for row in rows:
            text = str(row.get("text") or "可能的理解").strip()
            link = row.get("interpretation_for")
            link = link if isinstance(link, dict) else {}
            reason = str(link.get("reason") or row.get("reason") or "").strip()
            body = f"AI 可能的理解：{text}。"
            if reason and reason not in body:
                body += reason
            parts.append(body)
        return "\n\n".join(parts)

    @staticmethod
    def _format_guided_context(question_text: str, explanation: str) -> str:
        question_text = question_text.strip()
        explanation = explanation.strip()
        if not explanation or explanation in question_text:
            return question_text
        return f"{question_text}{explanation}" if question_text else explanation

    def _fold(self, parent, title, row, *, opened=False):
        wrapper = ttk.Frame(parent)
        wrapper.grid(row=row, column=0, sticky="ew", pady=(5, 3))
        wrapper.columnconfigure(0, weight=1)
        body = ttk.Frame(wrapper, padding=(8, 6))
        body.columnconfigure(0, weight=1)
        button = ttk.Button(wrapper, text=("▾ " if opened else "▸ ") + title)
        button.grid(row=0, column=0, sticky="w")
        def toggle():
            show(not bool(body.winfo_manager()))
        def show(value=True):
            if value:
                body.grid(row=1, column=0, sticky="ew")
            else:
                body.grid_remove()
            button.configure(text=("▾ " if value else "▸ ") + title)
        button.configure(command=toggle)
        show(opened)
        body._show = show
        body._wrapper = wrapper
        return body

    def _reading_text(self, parent, *, height=5):
        frame = ttk.Frame(parent)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        widget = tk.Text(frame, height=height, wrap="word", state="disabled", relief="flat",
                         padx=8, pady=6, background="#f6f7f9", font=ui_font(self.root))
        widget.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(frame, command=widget.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        widget.configure(yscrollcommand=scroll.set)
        self._bind_context_menu(widget)
        return frame, widget

    def _build_layout(self):
        self._requirements_preview_shown = None
        self._plan_preview_shown = None
        self._answer_target_id = None
        self._conversation_refreshing = False
        self._navigation_revision = 0
        self._plan_navigation_at_start = None
        self._settings_page_index = 4
        self._settings_return_index = 0
        self.guidance_var = tk.StringVar(value="先告诉我你想完成什么。")
        self.question_context_var = tk.StringVar()
        self.question_progress_var = tk.StringVar()
        self.draft_explanation_var = tk.StringVar()
        self.preview_note_var = tk.StringVar()
        self._flow_progress = tk.StringVar(value="需求 → 方案 → 结果")
        self._shown_interpretations = {}
        colors = palette(self.preferences["composer_theme"])
        shell = tk.Frame(self.root, bg=colors["bg"], padx=18, pady=12)
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)
        header = tk.Frame(shell, bg=colors["bg"])
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        header.columnconfigure(1, weight=1)
        identity = tk.Frame(header, bg=colors["bg"])
        identity.grid(row=0, column=0, sticky="w")
        brand = tk.Label(identity, text="Intext", bg=colors["bg"], fg=colors["fg"], font=ui_font(self.root, "title", "bold"))
        brand.pack(side="left")
        flow = tk.Label(identity, textvariable=self._flow_progress, bg=colors["bg"], fg=colors["muted"], font=ui_font(self.root))
        flow.pack(side="left", padx=18)
        navigation = tk.Frame(header, bg=colors["bg"])
        navigation.grid(row=0, column=1, sticky="w")
        for label, index in (("对话", 0),):
            ReplyButton(navigation, text=label, command=lambda i=index: self.show_workspace(i), theme=self.preferences["composer_theme"]).pack(side="left", padx=3)
        actions = tk.Frame(header, bg=colors["bg"])
        actions.grid(row=0, column=2, sticky="e")
        settings = ReplyButton(actions, text="设置", command=self.show_settings, theme=self.preferences["composer_theme"])
        settings.pack(side="right", padx=(0, 8))
        self.widgets.update(settings_button=settings, workspace_actions=actions)

        def fit_header(event):
            identity_width = brand.winfo_reqwidth()
            flow_width = flow.winfo_reqwidth() + 36
            show_flow = event.width >= identity_width + flow_width + actions.winfo_reqwidth()
            if show_flow:
                if not flow.winfo_manager():
                    flow.pack(side="left", padx=18)
                identity_width += flow_width
            else:
                flow.pack_forget()
            required_width = identity_width + navigation.winfo_reqwidth() + actions.winfo_reqwidth()
            row = 1 if event.width < required_width else 0
            if int(navigation.grid_info()["row"]) != row:
                navigation.grid_configure(row=row, column=0 if row else 1,
                                          columnspan=3 if row else 1, pady=(6, 0) if row else 0)

        header.bind("<Configure>", fit_header, add="+")
        style = ttk.Style(self.root)
        style.layout("Flow.TNotebook.Tab", [])
        # Keep the page navigation contract without a native panel border.
        style.layout("Flow.TNotebook", [])
        style.configure("Flow.TNotebook", background=colors["bg"], borderwidth=0, padding=0)
        self.notebook = ttk.Notebook(shell, style="Flow.TNotebook")
        self.notebook.grid(row=1, column=0, sticky="nsew")
        self.widgets["notebook"] = self.notebook
        builders = (self._build_requirements_page, self._build_plan_page, self._build_skills_page,
                    self._build_export_page, self._build_settings_page)
        for key, title, builder in zip(("requirements", "plan", "skills", "export", "settings"),
                                       ("当前需求", "方案", "Skill（可选）", "结果", "设置"), builders):
            if key == "requirements":
                page = tk.Frame(self.notebook, bg=colors["bg"])
                content = page
            else:
                page, content = self._scrollable_page(key)
            self.notebook.add(page, text=title)
            builder(content)
        bottom = tk.Frame(shell, bg=colors["bg"], pady=4)
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        guidance = tk.Label(bottom, textvariable=self.guidance_var, wraplength=800, anchor="w", justify="left",
                            bg=colors["bg"], fg=colors["muted"], font=ui_font(self.root, 10))
        guidance.grid(row=0, column=0, sticky="ew", padx=(0, 15))
        primary = ReplyButton(bottom, text=self.primary_action_var.get(), command=self.run_primary_action,
                              theme=self.preferences["composer_theme"])
        primary.grid(row=0, column=1, sticky="e")
        self.widgets["analyze_button"] = primary
        self.widgets.update(workspace_shell=shell, workspace_header=header, workspace_footer=bottom,
                            workspace_guidance=guidance)
        shell.bind("<Configure>", lambda e: guidance.configure(wraplength=max(360, e.width-300)), add="+")
        self.notebook.bind("<<NotebookTabChanged>>", self._workspace_changed, add="+")
        self.answer_var.trace_add("write", lambda *_: self._refresh_primary_action())
        self._register_page_wheel_routing()

    def _build_settings_page(self, page):
        self._build_categorized_settings(page)

    def _build_requirements_page(self, page):
        self._thinking_labels = {"quick": "快速：先把基本任务说清", "standard": "标准：补齐常见关键信息", "deep": "深入：系统梳理复杂任务"}
        self._thinking_levels_by_label = {label:key for key,label in self._thinking_labels.items()}
        current = self.session.control.get("thinking_level", "standard")
        self.thinking_level_var.set(current)
        self.thinking_level_display_var.set(self._thinking_labels.get(current,self._thinking_labels["standard"]))
        self._build_conversation_workspace(page)
        # Unmapped task buffer preserves existing save/workflow input contracts;
        # the composer is the sole visible goal editor.
        task = tk.Text(page, font=ui_font(self.root), undo=True)
        task.bind("<<Modified>>",self._on_task_text_modified,add="+")
        self.widgets["task_text"] = task

    def _build_plan_page(self, page):
        page.columnconfigure(0, weight=1)
        ttk.Label(page, text="核对方案", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(page, text="目标、要求、步骤和关键工作一起看；需要调整时展开下面的编辑区。", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=6)
        frame, reading = self._reading_text(page, height=20)
        frame.grid(row=2, column=0, sticky="ew")
        self.widgets["plan_reading_text"] = reading
        options = ttk.Frame(page)
        options.grid(row=3, column=0, sticky="ew", pady=8)
        skill = ttk.Button(options, text="确认方案并查找 Skill（可选）", command=self.confirm_plan_and_find_skills)
        skill.pack(side="left")
        ttk.Button(options, text="返回当前需求", command=lambda: self.show_workspace(0)).pack(side="right")
        self.widgets["optional_skill_button"] = skill
        editor = self._fold(page, "编辑方案内容", 4)
        self._legacy_build_plan_page(editor)
        self.widgets["plan_editor_panel"] = editor

    def _build_export_page(self, page):
        self._legacy_build_export_page(page)
        # Keep existing review controls, but avoid showing empty optional panels.
        controls = self.widgets["copy_final_button"].master
        controls.grid_remove()
        simple = ttk.Frame(page)
        simple.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(simple, text="复制提示", command=self.copy_current_prompt).pack(side="left")
        ttk.Button(simple, text="导出方案和提示", command=self.export_current_result).pack(side="left", padx=6)
        ttk.Button(simple, text="保存会话", command=self.save).pack(side="left")
        ttk.Button(simple, text="修改方案", command=lambda: self.show_workspace(1)).pack(side="right")
        self.widgets["result_simple_controls"] = simple
        # The prompt itself is the primary content; complete structured data is optional.
        self.widgets["final_preview_text"].configure(height=8)
        self.widgets["final_task_prompt_text"].configure(height=13)
        for row in (3, 5, 6, 7):
            page.rowconfigure(row, weight=0)
        for child in page.grid_slaves(row=3):
            child.grid_remove()
        optional = ttk.Button(page, text="语气与完整方案（可选）", command=self.toggle_result_options)
        optional.grid(row=11, column=0, sticky="w", pady=8)
        self.widgets["result_optional_button"] = optional
        self._result_options_open = False
        if "conversation_input" in self.widgets:
            self.widgets["conversation_input"].delete("1.0", "end")
            self._conversation_signature = None
            self.toggle_conversation_details(False)
        self._result_optional_controls = controls

    def toggle_result_options(self):
        self._result_options_open = not self._result_options_open
        self._refresh_guided_visibility()

    def show_workspace(self, index):
        if index == self._settings_page_index:
            current = self.notebook.index(self.notebook.select())
            if current != self._settings_page_index:
                self._settings_return_index = current
        self.notebook.select(index)
        self._navigation_revision += 1
        self._refresh_primary_action()

    def show_settings(self):
        self.show_workspace(self._settings_page_index)

    def return_from_settings(self):
        index = self._settings_return_index
        if self.notebook.tab(index, "state") != "normal":
            index = 0
        self.show_workspace(index)

    def _workspace_changed(self, _event=None):
        self._navigation_revision += 1
        self._refresh_primary_action()

    def _reset_guided_view(self):
        self._reset_response_view()
        self._answer_target_id = None
        self.answer_var.set("")
        if "conversation_input" in self.widgets:
            self.widgets["conversation_input"].delete("1.0", "end")
        self._conversation_signature = None
        self._shown_interpretations = {}
        self._requirements_preview_shown = None
        self._plan_preview_shown = None
        self._result_options_open = False
        self._navigation_revision += 1
        self._plan_navigation_at_start = None
        self.show_workspace(0)
        for canvas in self._page_canvases:
            canvas.yview_moveto(0)

    def _reveal_guided(self, widget):
        """Bring the next editable control into view without changing business state."""
        details = self.widgets.get("conversation_details")
        parent = widget
        while parent is not None:
            if parent is details:
                self.toggle_conversation_details(True)
                break
            parent = getattr(parent, "master", None)
        self.root.update_idletasks()
        canvas = self._page_canvas_by_frame.get(str(self.notebook.select()))
        if canvas is not None and widget.winfo_ismapped():
            top = widget.winfo_rooty() - canvas.winfo_rooty()
            bottom = top + widget.winfo_height()
            if top < 12 or bottom > canvas.winfo_height() - 12:
                region = canvas.bbox("all")
                if region and region[3] > region[1]:
                    # Place the field below its question/context when possible.
                    absolute_y = canvas.canvasy(0) + top
                    canvas.yview_moveto(max(0, absolute_y - 110) / (region[3] - region[1]))
        widget.focus_set()

    def _blocking_gaps(self):
        return self.session._blocking_gap_snapshot()

    def _last_m1_failure(self):
        for run in reversed(self.session.api_runs):
            if str(run.get("contract_version", "")).startswith("m1."):
                if run.get("base_version") == self.session.requirement_version and run.get("status") in {"timeout", "truncated", "network", "json_error", "api_error", "validation_error"}:
                    return run
                return None
        return None

    def _preview_check(self, *, draft=False):
        if not self._requirements_preview_shown:
            return "请先查看当前需求。"
        probe = deepcopy(self.session)
        try:
            probe.confirm_requirements_preview(
                self._requirements_preview_shown, allow_draft=draft,
                use_task_as_deliverable=bool(self._requirements_preview_shown.get("suggested_task_result")),
            )
        except (SessionStateError, ValueError, KeyError, TypeError) as exc:
            return str(exc)
        return None

    def _primary_action(self):
        from .ui import PrimaryAction
        page = self.notebook.index(self.notebook.select()) if self.notebook.select() else 0
        if page == self._settings_page_index:
            if getattr(self, "_automatic_model_settings", False):
                reason = "模型配置可直接使用；返回工作区继续当前任务。" if self._model_settings_confirmed() else "请填写有效模型配置后继续；测试连接只检查接口。"
            else:
                reason = "模型设置已确认；返回工作区继续当前任务。" if self._model_settings_confirmed() else "测试连接只检查接口；请点击模型设置中的“确认”后继续。"
            return PrimaryAction("return_from_settings", "返回工作区", reason)
        if self.busy or self.delivery_busy or self._skill_search_busy:
            return PrimaryAction("busy", "正在整理…", "正在处理，你可以查看已有内容。", False)
        if not self._visible_task_text():
            return PrimaryAction("focus_task", "先输入任务", "先告诉我你想完成什么。")
        if self.session.task_text and self._visible_task_text() != self.session.task_text.strip():
            missing = self._missing_generation_config()
            return PrimaryAction("focus_connection", "补全模型连接", "先填写模型连接，就可以开始整理。") if missing else PrimaryAction("analyze", "开始整理", "先整理你提供的信息，必要时只问关键问题。")
        if self.session.workspace_navigation()["revisiting"]:
            return PrimaryAction("continue_stage", "继续下一步", "继续使用已经保存的成果，不重新调用模型。")
        if page == 0 and self.answer_var.get().strip():
            return PrimaryAction("submit_answer", "提交回答", "这次提交会记录你的补充并继续整理，不用重复填写。")
        if self.session.questions_for_review():
            return PrimaryAction("focus_question", "逐项核对待补充内容", "先回答或跳过当前问题，核对完再确认需求和方案。")
        from .interview import rounds_used, round_limit
        if rounds_used(self.session) >= round_limit(self.session) and self.session.questions_for_review(respect_interview_limit=False):
            pending_answers = any(q.get("assessment_status") == "pending" and q.get("disposition") == "answered"
                                  for q in self.session.question_history)
            if not pending_answers:
                return PrimaryAction("review_remaining_unknowns", "决定是否继续追问", "本轮已完成；请核对剩余未知，选择再问一轮，或保留到使用提示词时补充。")
        if self.session.confirmed_requirements_version == self.session.requirement_version:
            plan = self.session.plan
            if plan.get("status") == "draft":
                if page == 3 and (self.session.final_result.get("content") or {}).get("plan_review_pending"):
                    return PrimaryAction("focus_final", "查看草稿", "这是保留未知的草稿，可以直接保存或导出；以后说明含义再完善。")
                can_confirm_here = page in {0, 1}
                return PrimaryAction("confirm_plan_generate" if can_confirm_here else "view_plan", "确认方案并生成提示" if can_confirm_here else "查看方案", "请核对方案；未定信息交由下游 AI 处理，Skill 可选。")
            if plan.get("status") == "confirmed":
                final = self.session.final_result
                if final.get("status") in {"draft", "confirmed"}:
                    return PrimaryAction("focus_final", "查看方案和提示", "结果可以复制、保存和导出；需要调整时返回方案。")
                if self.session.skill_state.get("bindings"):
                    return PrimaryAction("integrate_skills", "生成方案", "将已选 Skill 用于最终方案。")
                return PrimaryAction("generate_final", "生成提示", "按当前方案直接生成提示，不需要添加 Skill。")
            if self._missing_generation_config():
                return PrimaryAction("focus_connection", "补全模型连接", "需求已保存；补全连接后可生成方案。")
            if self.workflow.m2_retry_recommended():
                return PrimaryAction("generate_plan", "重新生成方案", "上次未得到可用方案，你的回答和需求已保留。可直接重试；重复失败时查看状态提示，按提示调整连接或补充任务说明。")
            return PrimaryAction("generate_plan", "生成方案", "基于当前需求生成方案，未知内容仍会注明。")
        if self.session.open_conflicts:
            return PrimaryAction("focus_conflict", "处理互相矛盾的要求", "下面的需求有冲突；请编辑或移除矛盾内容，再继续。")
        if self._last_m1_failure() or self.workflow.m1_retry_recommended():
            if self._missing_generation_config():
                return PrimaryAction("focus_connection", "补全模型连接", "你的回答已保留，补全连接后可重试分析。")
            return PrimaryAction("retry_compact" if self.workflow.m1_retry_recommended() else "analyze_answer", "重试分析", "刚才没有收到完整可用的结果，你的回答已保留。点击只重试一次。")
        if self.session.questions_for_review():
            return PrimaryAction("focus_question", "回答问题", "在当前问题下方直接回答；暂时不知道也可以跳过。")
        if any(q.get("assessment_status") == "pending" and q.get("disposition") == "answered" for q in self.session.question_history):
            if self._missing_generation_config():
                return PrimaryAction("focus_connection", "补全模型连接", "回答已保留，补全连接后继续分析。")
            return PrimaryAction("analyze_answer", "继续整理回答", "刚才的回答已记录，继续整理它们。")
        interpretations = [p for p in self.session.pending_proposals if p.get("interpretation_for")]
        if interpretations:
            return PrimaryAction("focus_question", "看看是否是这个意思", "这是 AI 根据已有信息提出的解释，请在上方确认或纠正。")
        if self._blocking_gaps():
            return PrimaryAction("focus_question", "补充说明", "影响内容方向的信息还没确定。可以原地说明，也可以先做草稿。")
        if self.session.pending_review_item_ids and not self.session.requirements:
            return PrimaryAction("focus_review", "核对当前需求", "原会话记录需要核对，请查看当前需求及来源。")
        if self.session.requirements or self.session.pending_proposals:
            reason = self._preview_check() if hasattr(self.session, "confirm_requirements_preview") else "当前需求需要核对。"
            if reason:
                if self.session.analysis_basis_version != self.session.requirement_version:
                    if self.session.pending_proposals and not self.session.requirements:
                        return PrimaryAction("focus_review", "核对当前需求", "请核对下面的内容；不完整的旧候选可以移除或补充说明。")
                    if self._missing_generation_config():
                        return PrimaryAction("focus_connection", "补全模型连接", "修改已保留；补全连接后整理受影响的内容，再核对需求。")
                    return PrimaryAction("analyze", "整理修改后的内容", "内容已改变；整理受影响的部分后再核对。")
                missing = (self._requirements_preview_shown or {}).get("missing_direction_fields", [])
                if missing:
                    return PrimaryAction("focus_question", "说明想要的结果" if missing == ["deliverable"] else "说明想做的任务", "请在上方回答这一个问题，再点击提交回答继续。")
                return PrimaryAction("focus_review", "核对当前需求", reason)
            if self._missing_generation_config():
                return PrimaryAction("focus_connection", "补全模型连接", "需求已整理好；生成方案前请补全模型连接。")
            return PrimaryAction("confirm_requirements", "确认需求并生成方案", "请核对上方这份需求。确认后会直接生成方案，未确定的细节仍会保留。")
        missing = self._missing_generation_config()
        return PrimaryAction("focus_connection", "补全模型连接", "先填写模型连接，就可以开始整理。") if missing else PrimaryAction("analyze", "开始整理", "先整理你的任务，必要时再补充。")

    def _next_step_text(self):
        return self._primary_action().reason

    def _on_thinking_level_selected(self, _event=None):
        label = self.thinking_level_display_var.get()
        level = getattr(self, "_thinking_levels_by_label", {}).get(label, "standard")
        self.thinking_level_var.set(level)
        self.session.control["thinking_level"] = level
        self.session.control["thinking_policy"] = "coverage_based"
        self.status_var.set({
            "quick": "已选择快速整理：先说清任务基本信息。",
            "standard": "已选择标准整理：补齐常见的关键信息。",
            "deep": "已选择深入整理：复杂任务会从更多关联角度继续核对。",
        }[level])
        self._refresh_primary_action()

    def _sync_thinking_level_display(self) -> None:
        """Keep the visible choice aligned with a loaded or newly created session."""
        labels = getattr(self, "_thinking_labels", {})
        if not labels:
            return
        level = self.session.control.get("thinking_level", "standard")
        if level not in labels:
            level = "standard"
            self.session.control["thinking_level"] = level
        self.thinking_level_var.set(level)
        self.thinking_level_display_var.set(labels[level])

    def _refresh_primary_action(self):
        if not hasattr(self, "guidance_var") or "analyze_button" not in self.widgets:
            return
        action = self._primary_action()
        self.primary_action_var.set(action.label)
        self.guidance_var.set(action.reason)
        self.widgets["analyze_button"].configure(text=action.label, state="normal" if action.enabled else "disabled")
        self._refresh_conversation()

    def run_primary_action(self):
        if self.notebook.index(self.notebook.select()) == self._settings_page_index:
            self.return_from_settings()
            return
        if self._conversation_locked():
            return
        if self._visible_task_text():
            try:
                self._sync_input()
            except (ValueError, SessionStateError) as exc:
                self._show_error("无法同步任务", str(exc), parent=self.root)
                return
        action = self._primary_action()
        if action.kind == "continue_stage":
            self.navigate_workspace("next")
        elif action.kind == "submit_answer":
            self.submit_guided_answer()
        elif action.kind == "confirm_requirements":
            self.confirm_preview_and_plan()
        elif action.kind == "confirm_plan_generate":
            self.confirm_plan_and_generate()
        elif action.kind == "generate_final":
            self.generate_default_final()
        elif action.kind == "integrate_skills":
            self.integrate_selected_skills()
        elif action.kind == "view_plan":
            self.show_workspace(1)
        elif action.kind == "review_remaining_unknowns":
            self.show_workspace(0)
            self._conversation_focus_key = "interview_unknowns"
            self._conversation_scroll_latest(force=True)
        elif action.kind == "focus_question":
            self.show_workspace(0)
            self.widgets["conversation_input"].focus_set()
            self._conversation_scroll_latest(force=True)
        elif action.kind == "focus_conflict":
            self.review_current_conflict()
        elif action.kind in {"focus_review", "focus_proposal"}:
            self.show_workspace(0)
            if self._workspace_popover is None:
                self.toggle_requirements_review()
        elif action.kind == "focus_connection":
            self.show_settings()
            for key in ("api_base_entry", "api_model_entry", "api_key_entry"):
                if not self.widgets[key].get().strip():
                    self._reveal_guided(self.widgets[key])
                    break
            else:
                self._reveal_guided(self.widgets["confirm_model_settings_button"])
        elif action.kind == "focus_final":
            if self.notebook.index(self.notebook.select()) == 0:
                self._conversation_scroll_latest(force=True)
            else:
                self.show_workspace(3)
        elif action.kind == "focus_task":
            self.show_workspace(0)
            self.widgets["conversation_input"].focus_set()
        else:
            self._legacy_run_primary_action()

    def review_current_conflict(self):
        if not self.session.open_conflicts:
            return
        conflict = self.session.open_conflicts[0]
        requirements = {row["item_id"]: row["text"] for row in self.session.requirements}
        proposals = {row["proposal_id"]: row.get("text", "移除这项要求") for row in self.session.pending_proposals}
        participants = [requirements[key] for key in conflict.get("existing_item_ids", []) if key in requirements]
        participants += [proposals[key] for key in conflict.get("proposal_ids", []) if key in proposals]
        self.show_workspace(0)
        if self._workspace_popover is None or self._workspace_popover.kind != "requirements":
            self.toggle_requirements_review()
        tree = self.widgets["requirements_preview_tree"]
        for kind, keys in (("r", conflict.get("existing_item_ids", [])), ("p", conflict.get("proposal_ids", []))):
            first = next((f"{kind}:{key}" for key in keys if tree.exists(f"{kind}:{key}")), None)
            if first:
                tree.selection_set(first)
                tree.see(first)
                self.show_preview_details()
                break
        self._reveal_guided(tree)
        details = "\n".join(f"{number}. {value}" for number, value in enumerate(participants, 1))
        compatible = messagebox.askyesno(
            "核对这些要求",
            f"{conflict.get('description', '这些要求可能有冲突')}\n\n{details}\n\n"
            "如果这些要求可以同时成立，选“是”继续；否则选“否”，编辑或移除已选中的内容。",
            parent=self.root,
        )
        if compatible:
            try:
                self.session.mark_conflict_compatible(conflict["conflict_id"])
            except SessionStateError as exc:
                self.status_var.set(str(exc))
            else:
                self.status_var.set("已确认这些要求可以并存，继续核对其余内容。")
            self.refresh()
        else:
            self.status_var.set("已选中一项相关要求，可在上方编辑或移除。")

    def submit_guided_answers(self, answers):
        """Save one batch before refreshing or starting a single reassessment."""
        if self._conversation_locked():
            raise SessionStateError("正在处理当前任务，请稍候或停止后再提交。")
        self._sync_input()
        shown = [key for key in self._shown_interpretations
                 if any(row["proposal_id"] == key for row in self.session.pending_proposals)]
        submitted = self.session.record_question_answers(
            answers, context_gap_ids=[gap["gap_id"] for gap in self.session.active_gaps()],
            reject_interpretation_ids=shown,
        )
        if not submitted:
            return []
        for key in submitted:
            self._question_drafts.pop(key, None)
            # Do not let the render's draft capture restore committed text.
            self._question_inputs.pop(key, None)
        self._answer_target_id = None
        self.refresh()
        remaining = len(self.session.questions_for_review())
        analyze = not remaining and not self._missing_generation_config()
        logging.getLogger(__name__).debug("Answer batch next action: task=%s remaining=%s analyze=%s",
                                          self.session.task_id, remaining, analyze)
        if analyze:
            try:
                self.start_analysis()
            except Exception:
                logging.getLogger(__name__).exception("Answers saved but reassessment could not start: task=%s", self.session.task_id)
                self._show_error("回答已保存", "回答已保存，但暂时无法继续整理，请重试。", parent=self.root)
        return submitted

    def submit_guided_answer(self):
        if self._conversation_locked() or not self.answer_var.get().strip():
            return
        text = self.answer_var.get().strip()
        try:
            self._sync_input()
            self._reject_displayed_interpretations()
            context_gap_ids = [gap["gap_id"] for gap in self.session.active_gaps()]
            history_start = len(self.session.question_history)
            if self._answer_target_id:
                if not any(q["question_id"] == self._answer_target_id for q in self.session.questions_for_review()):
                    self.session.reopen_question(self._answer_target_id)
                self.session.record_question(self._answer_target_id, "answered", text, context_gap_ids=context_gap_ids)
            elif self.session.questions_for_review():
                question = self.session.questions_for_review()[0]
                self.session.record_question(question["question_id"], "answered", text, context_gap_ids=context_gap_ids)
            else:
                shown_gaps = (self._requirements_preview_shown or {}).get("gaps", [])
                gap_ids = [g["gap_id"] for g in shown_gaps if g.get("importance") == "blocking_direction"]
                self.session.record_supplement(text, gap_ids=gap_ids, context_gap_ids=context_gap_ids)
            submitted = self.session.question_history[history_start:]
            if submitted:
                group = f"guided:{submitted[0]['answer_id']}"
                for answer in submitted:
                    answer['submission_group_id'] = group
        except SessionStateError as exc:
            self._show_error("无法记录补充", str(exc), parent=self.root)
            return
        self._answer_target_id = None
        self.answer_var.set("")
        self.refresh()
        # Keep collecting the visible question cards before asking the model
        # to reassess the task. The final request then contains the complete
        # question history instead of an intermediate partial answer.
        if not self.session.questions_for_review() and not self._missing_generation_config():
            self.start_analysis()

    def skip_guided_question(self, disposition):
        if self._conversation_locked():
            return
        try:
            if self._answer_target_id and not any(q["question_id"] == self._answer_target_id for q in self.session.questions_for_review()):
                self.session.reopen_question(self._answer_target_id)
            pending = self.session.questions_for_review()
            inferred = next((p for p in self.session.pending_proposals if p.get("interpretation_for") and p["proposal_id"] in self._shown_interpretations), None)
            if inferred:
                self.session.decide_interpretation(inferred["proposal_id"], "skipped")
                self._answer_target_id = None
                self.answer_var.set("")
                self.status_var.set("这段推测先不采用；你可以直接说明，也可以先做草稿。")
                self.refresh()
                return
            if pending:
                target = next((q for q in pending if q["question_id"] == self._answer_target_id), pending[0])
                self.session.record_question(target["question_id"], disposition)
            else:
                return
        except SessionStateError as exc:
            self._show_error("无法记录选择", str(exc), parent=self.root)
            return
        self._answer_target_id = None
        self.answer_var.set("")
        self.status_var.set("已记录你的选择，你可以继续或以后补答。")
        self.refresh()
        if (not self.session.questions_for_review()
                and any(q.get("assessment_status") == "pending" and q.get("disposition") == "answered"
                        for q in self.session.question_history)
                and not self._missing_generation_config()):
            self.start_analysis()

    def _reject_displayed_interpretations(self):
        for key in list(self._shown_interpretations):
            if any(p["proposal_id"] == key for p in self.session.pending_proposals):
                self.session.decide_interpretation(key, "rejected")

    def correct_guided_interpretation(self):
        if self.busy:
            return
        self._reject_displayed_interpretations()
        self.refresh()
        self.widgets["conversation_input"].focus_set()

    def reopen_guided_question(self, question_id):
        # Selection is view state; the existing question is reopened only on submit.
        self._answer_target_id = question_id
        row = next((q for q in reversed(self.session.question_history) if q["question_id"] == question_id), None)
        if row:
            self.question_progress_var.set("补答历史问题")
            self.question_context_var.set(self._format_guided_question_card(row))
        self.show_workspace(0)
        self.widgets["conversation_input"].focus_set()

    def reopen_selected_history(self):
        selected = self.widgets["question_history_tree"].selection()
        if selected:
            row = self.session.question_history[int(selected[0])]
            self.reopen_guided_question(row["question_id"])

    def confirm_preview_and_plan(self, *, draft=False):
        if self.busy:
            return
        try:
            self._sync_input()
            self.session.confirm_requirements_preview(
                self._requirements_preview_shown, allow_draft=draft,
                use_task_as_deliverable=bool((self._requirements_preview_shown or {}).get("suggested_task_result")),
            )
        except (SessionStateError, ValueError) as exc:
            self.status_var.set(str(exc))
            self.refresh()
            return
        self.refresh()
        self.start_plan_generation()

    def continue_with_draft(self):
        self.confirm_preview_and_plan(draft=True)

    def confirm_plan_and_generate(self):
        if self.busy:
            return
        try:
            self.session.confirm_plan_preview(self._plan_preview_shown)
        except (SessionStateError, ValueError) as exc:
            self.status_var.set(str(exc))
            self.refresh()
            if self.session.questions_for_review():
                self.show_workspace(0)
            return
        self.session.control.pop("workspace_navigation", None)
        self.generate_default_final()

    def generate_default_final(self):
        if self.busy:
            return
        if self._return_to_unknown_questions():
            return
        if self.session.skill_state.get("bindings"):
            self.integrate_selected_skills()
            return
        try:
            self.session.set_skill_state(status="skipped", basis=self._delivery_basis(), candidate_batch=self.session.skill_state.get("candidate_batch"), bindings=[])
        except (SessionStateError, ValueError) as exc:
            self.status_var.set(str(exc))
            return
        self.generate_no_skill_final()

    def _return_to_unknown_questions(self):
        if not self.session.questions_for_review(respect_interview_limit=False):
            return False
        logging.getLogger(__name__).info("Workflow returned to clarification; task=%s questions=%d",
                                        self.session.task_id, len(self.session.questions_for_review(respect_interview_limit=False)))
        self.status_var.set("请先逐项回答或跳过待补充问题，再核对需求和方案。")
        self.refresh()
        self.show_workspace(0)
        self._conversation_scroll_latest(force=True)
        return True

    def confirm_plan_and_find_skills(self):
        if self.busy:
            return
        try:
            self.session.validate_unknown_reviews()
            self.session.confirm_plan_preview(self._plan_preview_shown)
        except (SessionStateError, ValueError) as exc:
            self.status_var.set(str(exc))
            self.refresh()
            if self.session.questions_for_review():
                self.show_workspace(0)
            return
        self.session.control.pop("workspace_navigation", None)
        self.find_skills()
        self.show_workspace(2)

    def copy_current_prompt(self):
        if self.session.final_result.get("status") == "confirmed":
            self.copy_final_prompt()
        else:
            self.copy_draft_prompt()

    def export_current_result(self):
        if self.session.final_result.get("status") == "confirmed":
            self.export_final_markdown()
        else:
            self.export_draft_markdown()

    def show_preview_details(self):
        self._conversation_show_requirement_selection()

    def adopt_preview_change(self):
        if self.busy:
            return
        selected = self.widgets["requirements_preview_tree"].selection()
        if not selected or not selected[0].startswith("p:"):
            return
        key = selected[0][2:]
        current = next((p for p in self.session.pending_proposals if p["proposal_id"] == key), None)
        shown = next((p for p in (self._requirements_preview_shown or {}).get("pending_proposals", []) if p["proposal_id"] == key), None)
        if current and current == shown and current.get("kind") == "pending_interpretation":
            self.accept_selected_understanding()
            return
        if not current or current != shown or current.get("operation") not in {"replace", "withdraw"}:
            self.status_var.set("这项修改已经变化，请先查看当前内容。")
            self.refresh()
            return
        self._accept_proposals([key])

    def accept_selected_understanding(self):
        if self.busy:
            return
        selected = self.widgets["requirements_preview_tree"].selection()
        if not selected or not selected[0].startswith("p:"):
            return
        key = selected[0][2:]
        row = next((p for p in self.session.pending_proposals if p["proposal_id"] == key), None)
        if not row or row.get("kind") != "pending_interpretation":
            return
        shown = next((p for p in (self._requirements_preview_shown or {}).get("pending_proposals", []) if p["proposal_id"] == key), None)
        if row != shown:
            self.status_var.set("这段理解已经变化，请先查看当前内容。")
            self.refresh()
            return
        if row.get("interpretation_for"):
            self.accept_guided_interpretation(key)
            return
        try:
            self.session.accept_generic_interpretation(key)
        except SessionStateError as exc:
            self.status_var.set(str(exc))
        self.refresh()

    def edit_preview_item(self):
        if self.busy:
            return
        selected = self.widgets["requirements_preview_tree"].selection()
        if not selected:
            self.widgets["requirements_preview_tree"].focus_set()
            return
        kind, key = selected[0].split(":", 1)
        if kind == "r":
            self.edit_selected_requirement(item_id=key)
        else:
            row = next(p for p in self.session.pending_proposals if p["proposal_id"] == key)
            text = simpledialog.askstring("修改这项理解", "请用你的话说明：", initialvalue=row["text"], parent=self.root)
            if text and text.strip():
                import re
                if re.sub(r"[ \t]+", " ", text.strip()) == re.sub(r"[ \t]+", " ", row["text"].strip()):
                    self.status_var.set("需求内容未变化，无需重新整理。")
                    logging.getLogger(__name__).info("Requirement edit unchanged; task=%s proposal=%s; model_request=False",
                                                     self.session.task_id, key)
                    return
                try:
                    self.session.edit_proposal(key, text)
                except SessionStateError as exc:
                    self.status_var.set(str(exc))
                    return
                self.status_var.set("修改已保存。请核对当前内容；需要重新整理时可主动发起。")
                self.refresh()

    def remove_preview_item(self):
        if self.busy:
            return
        selected = self.widgets["requirements_preview_tree"].selection()
        if not selected:
            return
        kind, key = selected[0].split(":", 1)
        try:
            if kind == "r":
                self.session.withdraw_requirement(key)
            else:
                row = next(p for p in self.session.pending_proposals if p["proposal_id"] == key)
                if row.get("interpretation_for"):
                    self.session.decide_interpretation(key, "rejected")
                else:
                    self.session._drop_candidate_ids({key})
                    self.session.touch()
        except SessionStateError as exc:
            self.status_var.set(str(exc))
        self.refresh()

    def _refresh_guided(self):
        if not hasattr(self, "guidance_var"):
            return
        self._requirements_preview_shown = self.session.requirements_preview()
        self._plan_preview_shown = self.session.plan_preview()
        self._shown_interpretations = {p["proposal_id"]:deepcopy(p) for p in self.session.pending_proposals if p.get("interpretation_for")}
        pending = self.session.questions_for_review()
        if pending and not self._answer_target_id:
            self.question_context_var.set(self._format_guided_question_card(pending[0]))
        self.draft_explanation_var.set((self._requirements_preview_shown or {}).get("draft_explanation", ""))
        plancontent = self.session.plan.get("content")
        if isinstance(plancontent, dict):
            lines = [plancontent.get("goal", {}).get("summary", ""), self._plan_overview(plancontent), "\n步骤："]
            for step in sorted(plancontent.get("steps", []), key=lambda s: s["order"]):
                lines.extend([f"{step['order']}. {step['title']}：{step['purpose']}", "\n".join(f"  {a}" for a in step.get("actions", []))])
                lines.extend([f"  输入：{'；'.join(step.get('inputs', []))}", f"  输出：{'；'.join(step.get('outputs', []))}", f"  完成标准：{'；'.join(step.get('completion_criteria', []))}"])
            lines.append("\n关键工作（随方案一起核对）：")
            for work in plancontent.get("key_work", []):
                lines.extend([f"• {work['title']}：{work['goal']}", f"  输入：{'；'.join(work.get('inputs', []))}", f"  输出：{'；'.join(work.get('outputs', []))}", f"  检查：{'；'.join(work.get('checkpoints', []))}"])
                steps_by_id = {s['step_id']: s['title'] for s in plancontent.get('steps', [])}
                lines.append("  关联步骤：" + "；".join(steps_by_id.get(s, s) for s in work.get('step_ids', [])))
            self._set_text_widget(self.widgets["plan_reading_text"], "\n".join(lines))
        else:
            self._set_text_widget(self.widgets["plan_reading_text"], "核对需求后，方案会显示在这里。")
        self._refresh_guided_visibility()
        self._refresh_primary_action()
        self._refresh_conversation()

    def accept_guided_interpretation(self, proposal_id):
        if self.busy:
            return
        shown = self._shown_interpretations.get(proposal_id)
        current = next((p for p in self.session.pending_proposals if p["proposal_id"] == proposal_id), None)
        if shown is None or current != shown:
            self.status_var.set("这段解释已经变化，请查看当前内容后再选择。")
            self.refresh()
            return
        try:
            self.session.decide_interpretation(proposal_id, "accepted")
        except SessionStateError as exc:
            self.status_var.set(str(exc))
        else:
            self.status_var.set("已记录你确认的这段理解；其他建议仍可在下方核对。")
        self.refresh()

    def _refresh_guided_visibility(self):
        if "result_optional_button" not in self.widgets:
            return
        content = self.session.final_result.get("content") or {}
        for name, visible in (("m2_suggestions_tree", bool(content.get("suggestions", []))),
                              ("m4_changes_tree", bool(content.get("integration_changes", []))),
                              ("final_review_items_tree", bool(self._final_review_lookup))):
            widget = self.widgets[name]
            container = widget.master.master
            if visible:
                container.grid()
            else:
                container.grid_remove()
        if self._result_options_open:
            self.widgets["final_preview_text"].grid()
            self._result_optional_controls.grid(row=12, column=0, sticky="ew")
        else:
            self.widgets["final_preview_text"].grid_remove()
            self._result_optional_controls.grid_remove()
