"""User-facing progression on top of the existing session/workflow guards.

Viewing a section is read-only. The saved preview, not a freshly synthesized
snapshot at click time, is the authority for a consolidated user confirmation.
"""
from __future__ import annotations

from copy import deepcopy
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from .session import SessionState, SessionStateError
from .finalization import DeliveryValidationError


class GuidedFlowMixin:
    @staticmethod
    def _format_guided_question(question, *, number: int | None = None) -> str:
        """Render a follow-up question as one complete, readable context."""
        if not isinstance(question, dict):
            return "补充说明"
        text = str(question.get("text") or question.get("question_text") or "补充说明").strip()
        prefix = f"{number}. " if number is not None else ""
        body = [text]
        options = [str(value).strip() for value in question.get("options", []) if str(value).strip()]
        if options:
            body.append("可选内容包括：" + "、".join(options) + "。")
        reason = str(question.get("reason") or "").strip()
        if reason:
            body.append(reason)
        return prefix + "".join(body)

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
                         padx=8, pady=6, background="#f6f7f9", font=("Microsoft YaHei UI", 12))
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
        self._navigation_revision = 0
        self._plan_navigation_at_start = None
        self.guidance_var = tk.StringVar(value="先告诉我你想完成什么。")
        self.question_context_var = tk.StringVar()
        self.draft_explanation_var = tk.StringVar()
        self.preview_note_var = tk.StringVar()
        self._flow_progress = tk.StringVar(value="需求 → 方案 → 结果")
        self._shown_interpretations = {}
        shell = ttk.Frame(self.root, padding=(18, 12))
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)
        header = ttk.Frame(shell)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(header, text="PromptSmith", style="Title.TLabel").pack(side="left")
        ttk.Label(header, textvariable=self._flow_progress, style="Muted.TLabel").pack(side="left", padx=18)
        for label, index in (("当前需求", 0), ("方案", 1), ("结果", 3)):
            ttk.Button(header, text=label, command=lambda i=index: self.show_workspace(i)).pack(side="left", padx=3)
        ttk.Button(header, text="保存", command=self.save).pack(side="right")
        style = ttk.Style(self.root)
        style.layout("Flow.TNotebook.Tab", [])
        self.notebook = ttk.Notebook(shell, style="Flow.TNotebook")
        self.notebook.grid(row=1, column=0, sticky="nsew")
        self.widgets["notebook"] = self.notebook
        builders = (self._build_requirements_page, self._build_plan_page, self._build_skills_page, self._build_export_page)
        for key, title, builder in zip(("requirements", "plan", "skills", "export"),
                                       ("当前需求", "方案", "Skill（可选）", "结果"), builders):
            page, content = self._scrollable_page(key)
            self.notebook.add(page, text=title)
            builder(content)
        bottom = ttk.Frame(shell, padding=(0, 8, 0, 0))
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        guidance = ttk.Label(bottom, textvariable=self.guidance_var, wraplength=800)
        guidance.grid(row=0, column=0, sticky="ew", padx=(0, 15))
        primary = ttk.Button(bottom, textvariable=self.primary_action_var, command=self.run_primary_action)
        primary.grid(row=0, column=1, sticky="e")
        self.widgets["analyze_button"] = primary
        status = ttk.Label(shell, textvariable=self.status_var, style="Muted.TLabel", wraplength=1050)
        status.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        shell.bind("<Configure>", lambda e: guidance.configure(wraplength=max(360, e.width-300)), add="+")
        self.notebook.bind("<<NotebookTabChanged>>", self._workspace_changed, add="+")
        self.answer_var.trace_add("write", lambda *_: self._refresh_primary_action())
        self._register_page_wheel_routing()

    def _build_requirements_page(self, page):
        from .ui import CATEGORY_LABELS, PROTOCOL_LABELS, PROVIDER_PRESETS
        page.columnconfigure(0, weight=1)
        api = self._fold(page, "模型设置", 0, opened=True)
        self.widgets["connection_panel"] = api
        api.columnconfigure(1, weight=1)
        api.columnconfigure(3, weight=1)
        fields = (("服务名称", self.provider_var, tuple(PROVIDER_PRESETS), "provider_combo"),
                  ("协议", self.protocol_var, tuple(PROTOCOL_LABELS), "protocol_combo"))
        for i, (label, var, values, name) in enumerate(fields):
            ttk.Label(api, text=label).grid(row=0, column=2*i, sticky="w", padx=(0, 6))
            combo = ttk.Combobox(api, textvariable=var, values=values, state="readonly" if i else "normal")
            combo.grid(row=0, column=2*i+1, sticky="ew", padx=(0, 12))
            self.widgets[name] = combo
            self._bind_context_menu(combo)
        ttk.Label(api, text="接口地址").grid(row=1, column=0, sticky="w", pady=6)
        base = ttk.Entry(api, textvariable=self.api_base_var)
        base.grid(row=1, column=1, sticky="ew", padx=(0, 12))
        ttk.Label(api, text="模型 ID").grid(row=1, column=2, sticky="w")
        model = ttk.Combobox(api, textvariable=self.api_model_var)
        model.grid(row=1, column=3, sticky="ew", padx=(0, 12))
        ttk.Label(api, text="API Key").grid(row=2, column=0, sticky="w")
        key = ttk.Entry(api, textvariable=self.api_key_var, show="•")
        key.grid(row=2, column=1, sticky="ew", padx=(0, 12))
        fetch = ttk.Button(api, text="获取模型", command=self.fetch_models)
        fetch.grid(row=2, column=2, sticky="w")
        test = ttk.Button(api, text="测试连接", command=self.test_connection)
        test.grid(row=2, column=3, sticky="w")
        self.widgets.update(api_base_entry=base, api_model_entry=model, api_model_combo=model, api_key_entry=key,
                            model_list_button=fetch, test_connection_button=test)
        for widget in (base, model, key):
            self._bind_context_menu(widget)
        task = ttk.Frame(page, padding=(8, 8))
        task.grid(row=1, column=0, sticky="ew")
        task.columnconfigure(0, weight=1)
        ttk.Label(task, text="你想完成什么？", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        task_text = tk.Text(task, height=3, wrap="word", undo=True, font=("Microsoft YaHei UI", 12))
        task_text.grid(row=1, column=0, sticky="ew")
        task_text.bind("<<Modified>>", self._on_task_text_modified, add="+")
        category = ttk.Combobox(task, textvariable=self.category_var, values=["自动判断", *CATEGORY_LABELS.values()], state="readonly", width=18)
        category.grid(row=2, column=0, sticky="w", pady=(6, 0))
        category.bind("<<ComboboxSelected>>", self._on_category_selected)
        depth = ttk.Frame(task)
        depth.grid(row=3, column=0, sticky="w", pady=(7, 0))
        ttk.Label(depth, text="整理深度").pack(side="left", padx=(0, 6))
        thinking_labels = {
            "quick": "快速：先把基本任务说清",
            "standard": "标准：补齐常见关键信息",
            "deep": "深入：系统梳理复杂任务",
        }
        thinking_combo = ttk.Combobox(
            depth,
            textvariable=self.thinking_level_display_var,
            values=tuple(thinking_labels.values()),
            state="readonly",
            width=26,
        )
        self._thinking_labels = thinking_labels
        self._thinking_levels_by_label = {label: key for key, label in thinking_labels.items()}
        current_level = self.session.control.get("thinking_level", "standard")
        self.thinking_level_display_var.set(thinking_labels.get(current_level, thinking_labels["standard"]))
        self.thinking_level_var.set(current_level)
        thinking_combo.bind("<<ComboboxSelected>>", self._on_thinking_level_selected)
        thinking_combo.pack(side="left")
        ttk.Label(depth, text="问题会更少或更细，仍由信息是否足够决定是否继续。", style="Muted.TLabel").pack(side="left", padx=(8, 0))
        self.widgets.update(task_text=task_text, category_combo=category, thinking_level_combo=thinking_combo)
        self._bind_context_menu(task_text)
        question = ttk.LabelFrame(page, text="补充与回答", padding=12)
        question.grid(row=2, column=0, sticky="ew", pady=(8, 8))
        question.columnconfigure(0, weight=1)
        ttk.Label(question, textvariable=self.question_context_var, wraplength=1010).grid(row=0, column=0, sticky="ew")
        interpretation = ttk.Frame(question)
        interpretation.grid(row=1, column=0, sticky="ew", pady=(4, 3))
        interpretation.columnconfigure(0, weight=1)
        answer = ttk.Entry(question, textvariable=self.answer_var, font=("Microsoft YaHei UI", 12))
        answer.grid(row=2, column=0, sticky="ew", pady=(6, 6))
        answer.bind("<Return>", lambda _e: self.submit_guided_answer())
        options = ttk.Frame(question)
        options.grid(row=3, column=0, sticky="ew")
        skip = ttk.Button(options, text="先跳过", command=lambda: self.skip_guided_question("skipped"))
        skip.pack(side="left")
        unsure = ttk.Button(options, text="我不确定", command=lambda: self.skip_guided_question("unsure"))
        unsure.pack(side="left", padx=6)
        correct = ttk.Button(options, text="我来说明", command=self.correct_guided_interpretation)
        correct.pack(side="left")
        draft = ttk.Button(question, text="先做草稿", command=self.continue_with_draft)
        draft.grid(row=4, column=0, sticky="w")
        self.widgets.update(question_panel=question, answer_entry=answer, interpretation_panel=interpretation,
                            skip_question_button=skip, unsure_question_button=unsure, draft_continue_button=draft)
        self._bind_context_menu(answer)
        preview = ttk.LabelFrame(page, text="当前需求 · 在这里一起核对", padding=10)
        preview.grid(row=3, column=0, sticky="ew", pady=(4, 8))
        preview.columnconfigure(0, weight=1)
        ttk.Label(preview, textvariable=self.preview_note_var, style="Muted.TLabel", wraplength=1010).grid(row=0, column=0, sticky="ew")
        tree = self._tree(preview, ("text", "source"), (730, 180), height=5)
        tree.heading("text", text="需求内容")
        tree.heading("source", text="内容来源")
        tree._promptsmith_container.grid(row=1, column=0, sticky="ew", pady=6)
        tree.bind("<<TreeviewSelect>>", lambda _e: self.show_preview_details())
        editbar = ttk.Frame(preview)
        editbar.grid(row=2, column=0, sticky="ew")
        ttk.Button(editbar, text="编辑选中内容", command=self.edit_preview_item).pack(side="left")
        ttk.Button(editbar, text="移除选中内容", command=self.remove_preview_item).pack(side="left", padx=6)
        accept_understanding = ttk.Button(editbar, text="按这段理解", command=self.accept_selected_understanding)
        accept_understanding.pack(side="left")
        self.widgets["accept_understanding_button"] = accept_understanding
        change = ttk.Button(editbar, text="采用这项修改", command=self.adopt_preview_change)
        self.widgets["adopt_change_button"] = change
        detailframe, details = self._reading_text(preview, height=3)
        detailframe.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        self.widgets.update(requirements_preview_tree=tree, preview_panel=preview, preview_details_text=details)
        conflict_frame, conflict_text = self._reading_text(preview, height=4)
        conflict_frame.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        self.widgets.update(conflict_reading_panel=conflict_frame, conflict_reading_text=conflict_text)
        history = self._fold(page, "已回答和已跳过的问题 · 可以补答", 4)
        histree = self._tree(history, ("question", "answer", "choice"), (420, 390, 120), height=3)
        histree._promptsmith_container.grid(row=0, column=0, sticky="ew")
        ttk.Button(history, text="补答选中问题", command=self.reopen_selected_history).grid(row=1, column=0, sticky="w", pady=5)
        self.widgets.update(question_history_tree=histree, question_history_panel=history)
        # Existing editing/diagnostic widgets remain available behind details.
        advanced = self._fold(page, "来源、版本与详细操作", 5)
        ttk.Label(advanced, textvariable=self.summary_var).grid(row=0, column=0, sticky="w")
        ttk.Label(advanced, text=self._status_versions_text(), style="Muted.TLabel").grid(row=1, column=0, sticky="w")
        reqs = self._tree(advanced, ("field", "text", "status"), (140, 660, 120), height=3)
        reqs._promptsmith_container.grid(row=2, column=0, sticky="ew")
        props = self._tree(advanced, ("operation", "field", "text"), (100, 140, 660), height=3)
        props._promptsmith_container.grid(row=3, column=0, sticky="ew", pady=5)
        questions = self._tree(advanced, ("field", "text"), (150, 740), height=2)
        questions._promptsmith_container.grid(row=4, column=0, sticky="ew")
        detailframe, olddetails = self._reading_text(advanced, height=4)
        detailframe.grid(row=5, column=0, sticky="ew", pady=5)
        review = ttk.Button(advanced, text="复核选中需求", command=self.review_selected_requirements)
        review.grid(row=6, column=0, sticky="w")
        rounds = ttk.Button(advanced, text="继续整理当前回答", command=self.add_rounds)
        # Retained in the details area for old sessions; it does not expose a
        # question budget and is not part of the normal path.
        for widget, kind in ((reqs, "requirement"), (props, "proposal"), (questions, "question")):
            widget.bind("<<TreeviewSelect>>", lambda _e, k=kind: self._show_selected_details(k))
        self.widgets.update(requirements_tree=reqs, proposals_tree=props, questions_tree=questions,
                            details_text=olddetails, review_requirements_button=review, continue_button=rounds,
                            advanced_requirements_panel=advanced)
        m5 = self._fold(page, "用示例说明你的偏好（可选）", 6)
        self._build_guided_m5(m5)
        self.widgets["m5_panel"] = m5

    def _build_guided_m5(self, frame):
        criterion = ttk.Entry(frame)
        criterion.grid(row=0, column=0, sticky="ew")
        generate = ttk.Button(frame, text="生成示例", command=self.start_m5_generation)
        generate.grid(row=0, column=1, padx=6)
        ttk.Label(frame, textvariable=self.m5_status_var, wraplength=950).grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)
        container, examples = self._reading_text(frame, height=5)
        container.grid(row=2, column=0, columnspan=2, sticky="ew")
        choices = ttk.Frame(frame)
        choices.grid(row=3, column=0, columnspan=2, sticky="w", pady=5)
        self.widgets.update(m5_criterion_entry=criterion, m5_generate_button=generate, m5_examples_text=examples)
        for name, label, disposition in (("a", "更接近 A", "a"), ("b", "更接近 B", "b"), ("neither", "都不喜欢", "neither"), ("skip", "跳过", "skipped")):
            button = ttk.Button(choices, text=label, command=lambda d=disposition: self.select_m5_disposition(d))
            button.pack(side="left", padx=(0, 5))
            self.widgets[{"a": "m5_option_a_button", "b": "m5_option_b_button"}.get(name, f"m5_{name}_button")] = button
        feedback = ttk.Entry(frame)
        feedback.grid(row=4, column=0, sticky="ew")
        save = ttk.Button(frame, text="记录这项偏好", command=self.record_m5_feedback)
        save.grid(row=4, column=1, padx=6)
        self.widgets.update(m5_feedback_entry=feedback, m5_feedback_button=save)
        for widget in (criterion, feedback):
            self._bind_context_menu(widget)

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
        optional = ttk.Button(page, text="试运行、语气与完整方案（可选）", command=self.toggle_result_options)
        optional.grid(row=11, column=0, sticky="w", pady=8)
        self.widgets["result_optional_button"] = optional
        self._result_options_open = False
        self._result_optional_controls = controls

    def toggle_result_options(self):
        self._result_options_open = not self._result_options_open
        self._refresh_guided_visibility()

    def show_workspace(self, index):
        self.notebook.select(index)
        self._navigation_revision += 1
        self._refresh_primary_action()

    def _workspace_changed(self, _event=None):
        self._navigation_revision += 1
        self._refresh_primary_action()

    def _reset_guided_view(self):
        self._answer_target_id = None
        self.answer_var.set("")
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
        return [g for g in self.session.gaps if g.get("importance") == "blocking_direction"]

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
        if self.busy:
            return PrimaryAction("busy", "正在整理…", "正在处理，你可以查看已有内容。", False)
        if not self._visible_task_text():
            return PrimaryAction("focus_task", "先输入任务", "先告诉我你想完成什么。")
        if self.session.task_text and self._visible_task_text() != self.session.task_text.strip():
            missing = self._missing_generation_config()
            return PrimaryAction("focus_connection", "补全模型连接", "先填写模型连接，就可以开始整理。") if missing else PrimaryAction("analyze", "开始整理", "先整理你提供的信息，必要时只问关键问题。")
        page = self.notebook.index(self.notebook.select()) if self.notebook.select() else 0
        if page == 0 and self.answer_var.get().strip():
            return PrimaryAction("submit_answer", "提交回答", "这次提交会记录你的补充并继续整理，不用重复填写。")
        if self.session.confirmed_requirements_version == self.session.requirement_version:
            plan = self.session.plan
            if plan.get("status") == "draft":
                if page == 3 and (self.session.final_result.get("content") or {}).get("plan_review_pending"):
                    return PrimaryAction("focus_final", "查看草稿", "这是保留未知的草稿，可以直接保存或导出；以后说明含义再完善。")
                return PrimaryAction("confirm_plan_generate" if page == 1 else "view_plan", "确认方案并生成提示" if page == 1 else "查看方案", "核对方案后，直接生成可复制、保存和导出的提示；Skill 可选。")
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
                return PrimaryAction("generate_plan", "重新生成方案", "刚才的方案没有完整生成，你的需求已保留。点击这里重新生成，程序会减少重复说明。")
            return PrimaryAction("generate_plan", "生成方案", "基于当前需求生成方案，未知内容仍会注明。")
        if self.session.open_conflicts:
            return PrimaryAction("focus_conflict", "处理互相矛盾的要求", "下面的需求有冲突；请编辑或移除矛盾内容，再继续。")
        if self._last_m1_failure() or self.workflow.m1_retry_recommended():
            if self._missing_generation_config():
                return PrimaryAction("focus_connection", "补全模型连接", "你的回答已保留，补全连接后可重试分析。")
            return PrimaryAction("retry_compact" if self.workflow.m1_retry_recommended() else "analyze_answer", "重试分析", "刚才没有收到完整可用的结果，你的回答已保留。点击只重试一次。")
        if self.session.pending_questions:
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
        self.widgets["analyze_button"].configure(state="normal" if action.enabled else "disabled")

    def run_primary_action(self):
        if self.busy:
            return
        if self._visible_task_text():
            try:
                self._sync_input()
            except (ValueError, SessionStateError) as exc:
                messagebox.showerror("无法同步任务", str(exc), parent=self.root)
                return
        action = self._primary_action()
        if action.kind == "submit_answer":
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
        elif action.kind == "focus_question":
            self.show_workspace(0)
            self._reveal_guided(self.widgets["answer_entry"])
        elif action.kind == "focus_conflict":
            self.review_current_conflict()
        elif action.kind in {"focus_review", "focus_proposal"}:
            self.show_workspace(0)
            self._reveal_guided(self.widgets["requirements_preview_tree"])
        elif action.kind == "focus_connection":
            self.show_workspace(0)
            self.widgets["connection_panel"]._show(True)
            for key in ("api_base_entry", "api_model_entry", "api_key_entry"):
                if not self.widgets[key].get().strip():
                    self._reveal_guided(self.widgets[key])
                    break
        elif action.kind == "focus_final":
            self.show_workspace(3)
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

    def submit_guided_answer(self):
        if self.busy or not self.answer_var.get().strip():
            return
        text = self.answer_var.get().strip()
        try:
            self._sync_input()
            self._reject_displayed_interpretations()
            context_gap_ids = [gap["gap_id"] for gap in self.session.gaps]
            history_start = len(self.session.question_history)
            if self._answer_target_id:
                self.session.reopen_question(self._answer_target_id)
                self.session.record_question(self._answer_target_id, "answered", text, context_gap_ids=context_gap_ids)
            elif self.session.pending_questions:
                for question in list(self.session.pending_questions)[:3]:
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
            messagebox.showerror("无法记录补充", str(exc), parent=self.root)
            return
        self._answer_target_id = None
        self.answer_var.set("")
        self.refresh()
        self.start_analysis()

    def skip_guided_question(self, disposition):
        if self.busy:
            return
        try:
            if self._answer_target_id:
                self.session.reopen_question(self._answer_target_id)
            pending = self.session.pending_questions
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
            messagebox.showerror("无法记录选择", str(exc), parent=self.root)
            return
        self._answer_target_id = None
        self.answer_var.set("")
        self.status_var.set("已记录你的选择，你可以继续或以后补答。")
        self.refresh()

    def _reject_displayed_interpretations(self):
        for key in list(self._shown_interpretations):
            if any(p["proposal_id"] == key for p in self.session.pending_proposals):
                self.session.decide_interpretation(key, "rejected")

    def correct_guided_interpretation(self):
        if self.busy:
            return
        self._reject_displayed_interpretations()
        self.refresh()
        self._reveal_guided(self.widgets["answer_entry"])

    def reopen_guided_question(self, question_id):
        # Selection is view state; the existing question is reopened only on submit.
        self._answer_target_id = question_id
        row = next((q for q in reversed(self.session.question_history) if q["question_id"] == question_id), None)
        if row:
            self.question_context_var.set(self._format_guided_question(row))
        self.show_workspace(0)
        self._reveal_guided(self.widgets["answer_entry"])

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
            return
        self.generate_default_final()

    def generate_default_final(self):
        if self.busy:
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

    def confirm_plan_and_find_skills(self):
        if self.busy:
            return
        try:
            if self.session.plan.get("status") != "confirmed":
                self.session.confirm_plan_preview(self._plan_preview_shown)
        except (SessionStateError, ValueError) as exc:
            self.status_var.set(str(exc))
            return
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
        self.widgets["adopt_change_button"].pack_forget()
        selected = self.widgets["requirements_preview_tree"].selection()
        if not selected:
            self.widgets["accept_understanding_button"].configure(state="disabled")
            self._set_text_widget(self.widgets["preview_details_text"], "")
            return
        kind, key = selected[0].split(":", 1)
        name = "requirements_tree" if kind == "r" else "proposals_tree"
        self.widgets[name].selection_set(key)
        self._show_selected_details("requirement" if kind == "r" else "proposal")
        self._set_text_widget(self.widgets["preview_details_text"], self.widgets["details_text"].get("1.0", "end-1c"))
        row = next((p for p in self.session.pending_proposals if p["proposal_id"] == key), None) if kind == "p" else None
        self.widgets["accept_understanding_button"].configure(state="normal" if row and row.get("kind") == "pending_interpretation" and not self.busy else "disabled")
        if row and row.get("operation") in {"replace", "withdraw"} and row.get("kind") != "pending_interpretation":
            button = self.widgets["adopt_change_button"]
            button.configure(state="disabled" if self.busy else "normal")
            button.pack(side="left", padx=6)

    def adopt_preview_change(self):
        if self.busy:
            return
        selected = self.widgets["requirements_preview_tree"].selection()
        if not selected or not selected[0].startswith("p:"):
            return
        key = selected[0][2:]
        current = next((p for p in self.session.pending_proposals if p["proposal_id"] == key), None)
        shown = next((p for p in (self._requirements_preview_shown or {}).get("pending_proposals", []) if p["proposal_id"] == key), None)
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
            self.widgets["requirements_tree"].selection_set(key)
            self.edit_selected_requirement()
        else:
            row = next(p for p in self.session.pending_proposals if p["proposal_id"] == key)
            text = simpledialog.askstring("修改这项理解", "请用你的话说明：", initialvalue=row["text"], parent=self.root)
            if text and text.strip():
                working = deepcopy(self.session)
                link = row.get("interpretation_for")
                try:
                    if link:
                        working.decide_interpretation(key, "rejected")
                    else:
                        archived = deepcopy(row)
                        archived["deferred_reason"] = "user_corrected_candidate"
                        working.deferred_proposals.append(archived)
                        working._drop_candidate_ids({key})
                    correction = f"将候选“{row['text']}”改为：“{text.strip()}”。"
                    gap_ids = [link['gap_id']] if link else None
                    working.record_supplement(correction, gap_ids=gap_ids,
                                              context_gap_ids=[g['gap_id'] for g in working.gaps])
                except SessionStateError as exc:
                    self.status_var.set(str(exc))
                    return
                self.session.__dict__.update(deepcopy(working.__dict__))
                self.status_var.set("修改已记录，将重新整理受影响的内容。")
                self.refresh()
                self.start_analysis()

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
        from .ui import FIELD_LABELS, KIND_LABELS
        if not hasattr(self, "guidance_var"):
            return
        self._requirements_preview_shown = self.session.requirements_preview() if hasattr(self.session, "requirements_preview") else None
        self._plan_preview_shown = self.session.plan_preview() if hasattr(self.session, "plan_preview") else None
        tree = self.widgets["requirements_preview_tree"]
        selected = tree.selection()
        tree.delete(*tree.get_children())
        for prefix, rows, idkey in (("r", self.session.requirements, "item_id"), ("p", self.session.pending_proposals, "proposal_id")):
            for row in rows:
                source = KIND_LABELS.get(row.get("kind"), row.get("kind", "AI 建议"))
                if row.get("kind") == "pending_interpretation":
                    source = "AI 推测，请先判断"
                field = FIELD_LABELS.get(row.get("field"), row.get("field", "内容"))
                old = next((r["text"] for r in self.session.requirements if r["item_id"] == row.get("target_item_id")), None)
                text = f"{field}：{row.get('text', '请展开查看来源')}"
                if old and prefix == "p":
                    text = f"{field}：{old} → {row['text'] if row.get('operation') != 'withdraw' else '移除'}"
                tree.insert("", "end", iid=f"{prefix}:{row[idkey]}", values=(text, source))
        for item in selected:
            if tree.exists(item):
                tree.selection_set(item)
        self.preview_note_var.set("请核对这些内容，AI 建议会标明来源；重要推测需先单独判断。" if tree.get_children() else "")
        task_result = (self._requirements_preview_shown or {}).get("suggested_task_result")
        if task_result:
            self.preview_note_var.set(f"想要的结果先按你的原话“{task_result}”整理，不另加格式或篇幅要求。请核对下面的内容；需要调整时在上方说明。")
        self.widgets["preview_panel"].grid() if tree.get_children() else self.widgets["preview_panel"].grid_remove()
        if self.session.open_conflicts:
            requirements = {r["item_id"]: r["text"] for r in self.session.requirements}
            proposals = {r["proposal_id"]: r.get("text", "撤回这项要求") for r in self.session.pending_proposals}
            lines = ["这些内容互相矛盾，请在上方选中内容后编辑或移除；明确的替换建议可以选中后采用。"]
            for conflict in self.session.open_conflicts:
                lines.append(conflict.get("description", "要求需要核对"))
                lines.extend(f"当前需求：{requirements[key]}" for key in conflict.get("existing_item_ids", []) if key in requirements)
                lines.extend(f"候选修改：{proposals[key]}" for key in conflict.get("proposal_ids", []) if key in proposals)
            self._set_text_widget(self.widgets["conflict_reading_text"], "\n".join(lines))
            self.widgets["conflict_reading_panel"].grid()
        else:
            self.widgets["conflict_reading_panel"].grid_remove()
        history = self.widgets["question_history_tree"]
        old_selected = history.selection()
        history.delete(*history.get_children())
        for i, row in enumerate(self.session.question_history):
            history.insert("", "end", iid=str(i), values=(row.get("text", row.get("question_text", "")), row.get("answer_text", ""), {"answered": "已回答", "skipped": "已跳过", "unsure": "暂不确定"}.get(row["disposition"], "")))
        if old_selected and history.exists(old_selected[0]):
            history.selection_set(old_selected[0])
        self.widgets["question_history_panel"]._wrapper.grid() if self.session.question_history else self.widgets["question_history_panel"]._wrapper.grid_remove()
        blocking = self._blocking_gaps()
        pending = self.session.pending_questions
        if not self._answer_target_id:
            if pending:
                self.question_context_var.set(self._format_guided_questions(pending[:3]))
            elif blocking:
                self.question_context_var.set("还没确定：" + "；".join(g["description"] for g in blocking) + "。可以在这里补充。")
            elif not self._preview_check():
                self.question_context_var.set("请核对下方需求；没有要补充或修改的地方，点击底部“确认需求并生成方案”。需要调整也可以在这里说明。")
            elif "goal" in (self._requirements_preview_shown or {}).get("missing_direction_fields", []):
                self.question_context_var.set("你想让另一个 AI 帮你完成什么？在这里简单说明就好。")
            elif "deliverable" in (self._requirements_preview_shown or {}).get("missing_direction_fields", []):
                self.question_context_var.set("你希望另一个 AI 最后给出什么结果？在这里简单说明就好。")
            else:
                self.question_context_var.set("还有想补充或修改的地方？直接写在这里就好。")
        self.widgets["question_panel"].grid() if self.session.sources else self.widgets["question_panel"].grid_remove()
        for name in ("skip_question_button", "unsure_question_button"):
            button = self.widgets[name]
            button.pack(side="left", padx=6 if name == "unsure_question_button" else 0) if pending else button.pack_forget()
            button.configure(state="normal" if pending and not self.busy else "disabled")
        interpretations = [p for p in self.session.pending_proposals if p.get("interpretation_for")][:2]
        if interpretations:
            self.question_context_var.set(
                self._format_guided_context(
                    self.question_context_var.get(),
                    self._format_guided_interpretations(interpretations),
                )
            )
        explanation = (self._requirements_preview_shown or {}).get("draft_explanation", "")
        self.draft_explanation_var.set(explanation)
        self.question_context_var.set(
            self._format_guided_context(self.question_context_var.get(), explanation)
        )
        draftbutton = self.widgets["draft_continue_button"]
        if blocking:
            draftbutton.grid()
            problem = self._preview_check(draft=True) if hasattr(self.session, "confirm_requirements_preview") else "尚未就绪"
            draftbutton.configure(state="normal" if not problem and not self.busy else "disabled")
        else:
            draftbutton.grid_remove()
        self._render_interpretations()
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
        self.show_preview_details()
        self._refresh_primary_action()

    def _render_interpretations(self):
        frame = self.widgets["interpretation_panel"]
        for child in frame.winfo_children():
            child.destroy()
        rows = [p for p in self.session.pending_proposals if p.get("interpretation_for")][:2]
        self._shown_interpretations = {p["proposal_id"]: deepcopy(p) for p in rows}
        if rows:
            frame.grid()
        else:
            # An empty Tk frame retains its previous requested height.
            frame.grid_remove()
        for i, p in enumerate(rows):
            label = "是这个意思" if len(rows) == 1 else f"按解释 {i + 1}"
            ttk.Button(
                frame,
                text=label,
                command=lambda key=p["proposal_id"]: self.accept_guided_interpretation(key),
            ).grid(row=i, column=0, sticky="w", pady=(0, 6))
        # Interpretation controls are created after the initial page bindings.
        for child in frame.winfo_children():
            tags = child.bindtags()
            if self._wheel_bindtag not in tags:
                child.bindtags((tags[0], self._wheel_bindtag, *tags[1:]))

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
        for name, visible in (("trial_run_button", self._result_options_open),
                              ("m2_suggestions_tree", bool(content.get("suggestions", []))),
                              ("m4_changes_tree", bool(content.get("integration_changes", []))),
                              ("final_review_items_tree", bool(self._final_review_lookup))):
            widget = self.widgets[name]
            container = widget.master if name == "trial_run_button" else widget.master.master
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
