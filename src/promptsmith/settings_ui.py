"""Categorized desktop preferences and their explicit save boundary."""
from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from .debug_console import load_debug_preference
from .preferences import FIELDS, load_settings, normalize_value, save_preferences, update_debug_preference, validate_preferences
from .typography import ui_font


class SettingsMixin:
    def _init_preferences(self, data_root):
        self._preferences_path = Path(data_root) / "settings.json"
        loaded = load_settings(self._preferences_path)
        self.preferences, self._saved_connection = loaded.preferences, loaded.connection
        self._saved_api_key = loaded.api_key
        self._saved_model_confirmed = loaded.model_confirmed
        self._settings_load_warning = loaded.warning
        self.runtime_log.register_secret(loaded.api_key)
        legacy_path = Path(data_root) / "diagnostics.json"
        if not loaded.has_debug_preference and legacy_path.exists():
            self.preferences["debug_console_enabled"] = load_debug_preference(legacy_path)
            try:
                update_debug_preference(self._preferences_path, self.preferences["debug_console_enabled"])
                logging.getLogger(__name__).info("Legacy Debug preference migrated to settings.json")
            except (OSError, ValueError):
                logging.getLogger(__name__).exception("Cannot migrate legacy Debug preference; using it for this launch")
        self.preference_vars = {
            key: (tk.BooleanVar(master=self.root, value=value) if isinstance(value, bool)
                  else tk.StringVar(master=self.root, value=str(value)))
            for key, value in self.preferences.items()
        }
        self.settings_status_var = tk.StringVar(master=self.root, value=loaded.warning)

    def _model_preference_values(self):
        return {key: normalize_value(key, self.preference_vars[key].get())
                for key, spec in FIELDS.items() if spec.category == "模型"}

    def _public_model_connection(self):
        return {"provider": self.provider_var.get().strip(), "protocol": self.protocol_var.get().strip(),
                "base_url": self.api_base_var.get().strip(), "model": self.api_model_var.get().strip()}

    def _restore_model_settings_confirmation(self):
        if not self._saved_model_confirmed:
            return
        saved = {key: self._saved_connection.get(key, "").strip() for key in self._public_model_connection()}
        if self._public_model_connection() != saved or not self.api_key_var.get().strip():
            logging.getLogger(__name__).info("Model confirmation not restored: startup model or connection changed")
            if not self._settings_load_warning:
                self._settings_load_warning = "启动时的模型配置已变更，请在设置页核对后点击“确认”。"
                self.settings_status_var.set(self._settings_load_warning)
            return
        try:
            self._draft_api_config()
        except ValueError:
            logging.getLogger(__name__).warning("Model confirmation not restored: saved configuration is invalid", exc_info=True)
            self._settings_load_warning = "已保存的模型配置无法使用，请在设置页修正后重新确认。"
            self.settings_status_var.set(self._settings_load_warning)
            return
        self._confirmed_connection_state = self._generation_snapshot()
        self.status_var.set("已恢复确认过的模型设置，可以继续使用。")
        logging.getLogger(__name__).info("Model confirmation restored; saved configuration ready without reconfirmation")

    def _build_categorized_settings(self, page):
        from .ui import PROTOCOL_LABELS, PROVIDER_PRESETS
        page.columnconfigure(0, weight=1)
        heading = ttk.Frame(page)
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(heading, text="设置", style="Section.TLabel").pack(side="left")
        back = ttk.Button(heading, text="返回工作区", command=self.return_from_settings)
        back.pack(side="right")
        self.widgets["settings_return_button"] = back
        tabs = ttk.Notebook(page, height=380)
        tabs.grid(row=1, column=0, sticky="ew")
        self.widgets["settings_categories"] = tabs
        self._settings_pages = {}
        for index, category in enumerate(("模型", "Skill 搜索", "界面", "会话与导出", "诊断")):
            tab_page, tab = self._scrollable_page(f"settings_category_{index}", parent=tabs)
            tab.columnconfigure(1, weight=1)
            tabs.add(tab_page, text=category)
            self._settings_pages[category] = tab
        model_page = self._settings_pages["模型"]
        api = ttk.Frame(model_page)
        api.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        api.columnconfigure(1, weight=1)
        self.widgets["connection_panel"] = api
        fields = (
            ("服务名称", self.provider_var, tuple(PROVIDER_PRESETS), "provider_combo"),
            ("协议", self.protocol_var, tuple(PROTOCOL_LABELS), "protocol_combo"),
            ("接口地址", self.api_base_var, None, "api_base_entry"),
            ("模型 ID", self.api_model_var, (), "api_model_combo"),
            ("API Key", self.api_key_var, None, "api_key_entry"),
        )
        for row, (label, variable, options, name) in enumerate(fields):
            ttk.Label(api, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
            widget = (ttk.Entry(api, textvariable=variable, show="*" if name == "api_key_entry" else "")
                      if options is None else ttk.Combobox(api, textvariable=variable, values=options,
                                                          state="readonly" if name == "protocol_combo" else "normal"))
            widget.grid(row=row, column=1, sticky="ew", pady=4)
            self.widgets[name] = widget
            self._bind_context_menu(widget)
        self.widgets["api_model_entry"] = self.widgets["api_model_combo"]
        actions = ttk.Frame(api)
        actions.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        for label, command, name in (("获取模型", self.fetch_models, "model_list_button"),
                                     ("测试连接", self.test_connection, "test_connection_button"),
                                     ("确认", self.confirm_model_settings, "confirm_model_settings_button")):
            button = ttk.Button(actions, text=label, command=command)
            button.pack(side="left", padx=(0, 8))
            self.widgets[name] = button
        label = ttk.Label(api, textvariable=self.model_confirmation_var, style="Muted.TLabel", wraplength=600)
        label.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        api.bind("<Configure>", lambda e: label.configure(wraplength=max(200, e.width-24)), add="+")
        rows = {category: (1 if category == "模型" else 0) for category in self._settings_pages}
        for key, spec in FIELDS.items():
            if key == "debug_console_enabled":
                continue
            tab = self._settings_pages[spec.category]
            row = rows[spec.category]
            rows[spec.category] += 1
            variable = self.preference_vars[key]
            label = ttk.Label(tab, text=spec.label, wraplength=320)
            label.grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
            if isinstance(spec.default, bool):
                widget = ttk.Checkbutton(tab, variable=variable)
            elif spec.choices:
                labels = {"reasoning_effort": {"auto": "自动", "omit": "不发送", "low": "Low", "medium": "Medium", "high": "High", "max": "Max"},
                          "composer_theme": {"light": "浅色", "dark": "深色"},
                          "default_thinking": {"quick": "快速", "standard": "标准", "deep": "深入"},
                          "default_tone": {"neutral": "中性", "polite": "适度礼貌"}}.get(key)
                if labels:
                    display = tk.StringVar(master=self.root, value=labels[variable.get()])
                    inverse = {v: k for k, v in labels.items()}
                    widget = ttk.Combobox(tab, textvariable=display, values=tuple(labels.values()), state="readonly")
                    variable.trace_add("write", lambda *_args, v=variable, d=display, m=labels: d.set(m.get(v.get(), v.get())))
                    widget.bind("<<ComboboxSelected>>", lambda _e, v=variable, d=display, m=inverse: v.set(m[d.get()]))
                else:
                    widget = ttk.Combobox(tab, textvariable=variable, values=spec.choices, state="readonly")
            elif spec.minimum is not None:
                widget = ttk.Spinbox(tab, textvariable=variable, from_=spec.minimum, to=spec.maximum,
                                     increment=1 if isinstance(spec.default, int) else 5)
            elif key == "extra_skill_roots":
                widget = tk.Text(tab, height=3, wrap="none", font=ui_font(self.root))
                widget.insert("1.0", variable.get())
            else:
                widget = ttk.Entry(tab, textvariable=variable)
            widget.grid(row=row, column=1, sticky="ew", pady=4)
            self.widgets[f"setting_{key}"] = widget
            if key in {"session_directory", "export_directory"}:
                ttk.Button(tab, text="浏览…", command=lambda v=variable: self._choose_settings_directory(v)).grid(
                    row=row, column=2, padx=(8, 0))
        diagnostics = self._settings_pages["诊断"]
        debug = ttk.Checkbutton(diagnostics, text="开启 Debug 控制台", variable=self.debug_console_enabled_var,
                                command=self.set_debug_console_enabled)
        debug.grid(row=rows["诊断"], column=0, columnspan=2, sticky="w", pady=8)
        self.widgets["debug_console_toggle"] = debug
        ttk.Label(diagnostics, text=str(self.runtime_log.directory), style="Muted.TLabel", wraplength=580).grid(
            row=rows["诊断"]+1, column=0, columnspan=2, sticky="ew")
        footer = ttk.Frame(page)
        footer.grid(row=2, column=0, sticky="ew", pady=12)
        footer.columnconfigure(0, weight=1)
        status = ttk.Label(footer, textvariable=self.settings_status_var, style="Muted.TLabel", wraplength=500)
        status.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        restore = ttk.Button(footer, text="恢复本类默认", command=self.restore_settings_category)
        restore.grid(row=1, column=1, padx=8)
        save = ttk.Button(footer, text="保存设置", command=self.save_settings)
        save.grid(row=1, column=2)
        canvas = self.widgets["settings_page_canvas"]
        def fit_settings(_event=None):
            status.configure(wraplength=max(140, canvas.winfo_width()-48))
            tab_header = max(32, tabs.winfo_reqheight()-int(tabs.cget("height")))
            available = canvas.winfo_height()-heading.winfo_reqheight()-footer.winfo_reqheight()-tab_header-58
            tabs.configure(height=max(100, available))
        canvas.bind("<Configure>", fit_settings, add="+")
        footer.bind("<Configure>", fit_settings, add="+")
        self.widgets.update(settings_save_button=save, settings_restore_button=restore)
        for variable in (*self.preference_vars.values(), self.provider_var, self.protocol_var, self.api_base_var, self.api_model_var, self.api_key_var):
            variable.trace_add("write", lambda *_: self.settings_status_var.set("有未保存的设置。"))
        roots = self.widgets["setting_extra_skill_roots"]
        roots.edit_modified(False)
        roots.bind("<<Modified>>", self._settings_roots_modified)

    def _settings_roots_modified(self, _event):
        roots = self.widgets["setting_extra_skill_roots"]
        if roots.edit_modified():
            self.settings_status_var.set("有未保存的设置。")
            roots.edit_modified(False)

    def _choose_settings_directory(self, variable):
        selected = filedialog.askdirectory(parent=self.root, initialdir=variable.get() or None)
        if selected:
            variable.set(selected)

    def restore_settings_category(self):
        tabs = self.widgets["settings_categories"]
        category = tabs.tab(tabs.select(), "text")
        for key, spec in FIELDS.items():
            if spec.category == category:
                self.preference_vars[key].set(spec.default)
        if category == "Skill 搜索":
            self.widgets["setting_extra_skill_roots"].delete("1.0", "end")
        self.settings_status_var.set(f"{category}已恢复默认值，保存后生效。")
        logging.getLogger(__name__).info("Settings defaults staged: category=%s", category)

    def save_settings(self, *, model_only=False, confirm_model=False):
        try:
            values = dict(self.preferences)
            if model_only:
                values.update(self._model_preference_values())
            else:
                values = {key: variable.get() for key, variable in self.preference_vars.items()}
                values["extra_skill_roots"] = self.widgets["setting_extra_skill_roots"].get("1.0", "end-1c")
                values = validate_preferences(values)
            # Validate protocol-specific model options without requiring a key
            # when saving unrelated desktop preferences.
            if self.api_key_var.get().strip() and self.api_model_var.get().strip():
                self._draft_api_config()
            connection = self._public_model_connection()
            save_preferences(self._preferences_path, values, connection, api_key=self.api_key_var.get(),
                             model_confirmed=confirm_model or self._model_settings_confirmed())
        except (ValueError, OSError) as exc:
            logging.getLogger(__name__).exception("Cannot save settings")
            self.settings_status_var.set(f"设置未保存：{exc} 请修改后重试。")
            self.status_var.set(self.settings_status_var.get())
            self._show_error("设置未保存", str(exc), parent=self.root)
            return False
        changed = [key for key, value in values.items() if value != self.preferences[key]]
        self.preferences = values
        self._settings_load_warning = ""
        self.skill_search_timeout = values["search_timeout"]
        if "skill_search_url" in changed:
            self.skill_search_url_var.set(values["skill_search_url"])
        self._apply_visual_preferences()
        self.runtime_log.set_history_limit(values["debug_history"])
        if self.debug_console is not None and any(key.startswith("debug_") for key in changed):
            self.debug_console.apply_preferences(values)
        if not model_only:
            self.set_debug_console_enabled(persist=False)
        logging.getLogger(__name__).info("Settings saved; changed fields=%s; encrypted API Key present=%s", changed, bool(self.api_key_var.get().strip()))
        model_status = "已确认的模型设置下次启动自动恢复。" if self._model_settings_confirmed() or confirm_model else "模型参数需点击“确认”。"
        self.settings_status_var.set(f"设置已保存。{model_status}启动窗口大小下次启动生效。")
        if model_only:
            self.settings_status_var.set("模型设置已保存，其它分类的编辑需单独保存。")
        else:
            roots = self.widgets["setting_extra_skill_roots"]
            roots.edit_modified(False)
        if not model_only:
            self.status_var.set("设置已保存。")
            self.refresh()
        return True

    def _apply_visual_preferences(self):
        size = self.preferences["font_size"]
        font_changed = size != self.typography.values["font_size"]
        if font_changed:
            self.typography.apply(self.preferences)
            composer = self.widgets.get("conversation_composer")
            if composer is not None:
                composer.discard_picker()
                if composer.choice_menu:
                    composer.choice_menu.close(immediate=True)
                for button in (composer.depth_button,composer.category_button):
                    font=ui_font(self.root,11)
                    button.configure(width=font.measure(button.text)+38,height=max(44,font.metrics("linespace")+18))
        style = ttk.Style(self.root)
        for name in ("TLabel", "TButton", "TEntry", "TCombobox", "TSpinbox", "TCheckbutton", "TRadiobutton", "Treeview"):
            style.configure(name, font=ui_font(self.root))
        style.configure("Title.TLabel", font=ui_font(self.root, "title", "bold"))
        style.configure("Section.TLabel", font=ui_font(self.root, "body", "bold"))
        style.configure("TNotebook.Tab", font=ui_font(self.root))
        style.configure("Treeview", rowheight=max(34, ui_font(self.root).metrics("linespace")+12))
        style.configure("Treeview.Heading", font=ui_font(self.root, "heading", "bold"))
        composer = self.widgets.get("conversation_composer")
        if composer is not None:
            composer.apply_theme()
            if font_changed:
                composer.changed()

    def _skill_roots(self, preferences=None):
        from .local_skill_search import _default_roots
        values = preferences or self.preferences
        extra = [Path(line.strip()).expanduser() for line in values["extra_skill_roots"].splitlines() if line.strip()]
        return _default_roots() + extra if extra else None

    @staticmethod
    def _skill_review_options(values):
        return {"shortlist_limit": values["shortlist_limit"], "review_limit": values["review_limit"],
                "input_budget_chars": values["input_budget"], "excerpt_chars": values["excerpt_chars"]}

    def _new_preferred_session(self):
        from .session import SessionState
        session = SessionState.new()
        session.control["thinking_level"] = self.preferences["default_thinking"]
        session.control["default_tone"] = self.preferences["default_tone"]
        return session
