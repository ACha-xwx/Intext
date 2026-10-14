"""WebView2 presentation over the existing Tk-owned workflow and settings.

Only this module crosses the desktop boundary. Web API threads exchange plain
data with the Tk thread through a queue; they never touch a Tk object.
Saved keys remain in Python/credential storage; the browser receives only
public settings and a credential-present flag.
"""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
import logging
import queue
import sys
import tempfile
import threading
import time

from .paths import resource_root

LOG = logging.getLogger(__name__)
PANEL_ACTIONS = {
    "result": ("add_final_note",),
    "summary": (),
}


def view_stamp(app):
    return hashlib.sha256(app._conversation_token().encode("utf-8")).hexdigest()


class WorkspaceController:
    """All methods run on the thread that created PromptSmithApp."""
    def __init__(self, app, history=None):
        self.app = app
        from .preferences import load_tutorial_status
        self.tutorial_status = load_tutorial_status(app._preferences_path)
        app._automatic_model_settings = True
        app._refresh_model_confirmation()
        app._refresh_primary_action()
        LOG.debug("Web settings automatic readiness enabled; valid configuration requires no confirmation")
        self.history = history
        self.panel_kind = None
        self.panel_frame = None
        self.panel_token = None
        self.notifications = []
        self.notification_sequence = 0
        self._feedback_action = None
        self._feedback_values = {}
        for name in ("status_var", "settings_status_var", "skill_status_var", "final_status_var", "model_directory_status_var"):
            variable = getattr(app, name, None)
            if variable is not None:
                self._feedback_values[name] = variable.get()
                variable.trace_add("write", lambda *_args, name=name, variable=variable: self._status_feedback(name, variable.get()))
        self.icons = {}
        app._notify_directory_feedback = lambda provider, text: self._status_feedback("directory:" + provider, f"{provider}：{text}" if text else "")
        if getattr(app, "_settings_load_warning", ""):
            self._notify("warn", "设置恢复提醒", app._settings_load_warning, key="settings:restore")
        from .web_editors import WebEditors
        self.editors = WebEditors(app, lambda: view_stamp(app))
        for theme in ("light", "dark"):
            self.icons[theme] = {}
            for provider in ("OpenAI", "Anthropic", "Google", "xAI", "DeepSeek"):
                path = resource_root() / "resources/ui/model_icons" / (provider.lower() + ("_dark.png" if theme == "dark" else ".png"))
                if path.is_file():
                    self.icons[theme][provider] = "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")

    def install_native_bridge(self):
        """Keep settings navigation and feedback inside the browser window."""
        app = self.app
        if self.history is not None:
            self.history.install()
        original = app.show_workspace
        def show_workspace(index):
            original(app._settings_page_index if index == app._settings_page_index else 0)
            app.root.withdraw()
            if index == 1:
                self.editors.open("plan")
            LOG.debug("Web navigation: native_index=%s settings_in_browser=%s", index, index == app._settings_page_index)
        app.show_workspace = show_workspace
        def notify(level, title, message, **_options):
            self._notify(level, title, message)
            severity = {"error": logging.ERROR, "warn": logging.WARNING, "info": logging.INFO}[level]
            LOG.log(severity, "Web feedback: %s", app.runtime_log.redact(f"{title}：{message}"), exc_info=sys.exc_info() if sys.exc_info()[0] else None)
        app._show_error = lambda title, message, **options: notify("error", title, message, **options)
        app._show_info = lambda title, message, **options: notify("info", title, message, **options)
        app._show_warning = lambda title, message, **options: notify("warn", title, message, **options)
        app.review_current_conflict = lambda: self.editors.open("conflict")

    def _notify(self, level, title, message, key=None):
        safe_title = self.app.runtime_log.redact(str(title))
        body = self.app.runtime_log.redact(str(message))
        if self._feedback_action:
            key = "action:" + self._feedback_action
        if key is None and self.notifications:
            previous = self.notifications[-1]
            # One operation often updates status then shows a richer error.
            # Replace that status card instead of showing two failure cards.
            first_line = body.split("\n", 1)[0]
            if str(previous.get("key") or "").startswith("status:") and previous["body"] in (body, f"{safe_title}：{first_line}"):
                key = previous["key"]
        self.notification_sequence += 1
        self.notifications.append(dict(id=self.notification_sequence, level=level,
            title=safe_title, body=body, text=f"{safe_title}：{body}" if safe_title else body, key=key))
        self.notifications[:] = self.notifications[-32:]
        LOG.debug("User notification queued; id=%s level=%s source=%s", self.notification_sequence, level, key or "dialog")

    def _status_feedback(self, name, text):
        if self._feedback_values.get(name) == text:
            return
        self._feedback_values[name] = text
        # Per-keystroke draft indicators and empty resets are not operation feedback.
        if not text or text in ("有未保存设置。", "有未保存的设置。", "修改将自动保存。"):
            return
        if name == "model_directory_status_var" or text.startswith(("最终结果：", "目录状态：")):
            return
        if name == "skill_status_var" and text.startswith(("正在联网搜索 Skill", "正在查找本地 Skill")):
            # Per-query/per-file progress is projected inline and logged by the
            # search lifecycle. Only completion, cancellation or failure notifies.
            return
        if any(word in text for word in ("失败", "错误", "未完成", "无法", "异常")):
            level = "error"
        elif any(word in text for word in ("请先", "尚未", "未配置", "过期", "不一致", "需要重新", "请填写", "请选择", "未保存", "不完整", "不可用", "空模型列表")):
            level = "warn"
        elif any(word in text for word in ("已保存", "已复制", "已导出", "已删除", "已恢复", "成功", "已生成", "已确认")):
            level = "success"
        else:
            level = "info"
        self._notify(level, "", text, key="status:" + name)

    def settings_snapshot(self):
        from .preferences import FIELDS
        from .model_catalog import callable_model_ids
        from .ui import PROVIDER_PRESETS, PROTOCOL_LABELS, PROTOCOL_NAMES
        app = self.app
        values = {key: variable.get() for key, variable in app.preference_vars.items()}
        values["extra_skill_roots"] = app.widgets["setting_extra_skill_roots"].get("1.0", "end-1c")
        public = dict(connection=app._public_model_connection(), values=values,
                      has_key=bool(app.api_key_var.get().strip()))
        # Includes connection_version, so replacing a key invalidates stale edits
        # without hashing or projecting the key itself.
        revision = hashlib.sha256(json.dumps([public, app.connection_version], sort_keys=True).encode()).hexdigest()
        return dict(**public, revision=revision,
            fields={key: dict(category=spec.category, label=spec.label, default=spec.default,
                        minimum=spec.minimum, maximum=spec.maximum, choices=list(spec.choices),
                        step=1 if type(spec.default) is int else "any") for key, spec in FIELDS.items()},
            providers={name: dict(base_url=preset["base_url"], protocol=PROTOCOL_NAMES[preset["protocol"]], model=preset["model"])
                       for name, preset in PROVIDER_PRESETS.items()}, protocols=list(PROTOCOL_LABELS),
            saved_providers=list(app._provider_profiles),
            provider_families={name: name if name in PROVIDER_PRESETS else profile.connection.get("model_provider", "")
                              for name, profile in app._provider_profiles.items()},
            available_models=list(callable_model_ids(app.widgets["api_model_combo"].cget("values"))),
            confirmed=app._model_settings_confirmed(), confirmation=app.model_confirmation_var.get(),
            directory_status=app.model_directory_status_var.get(),
            status=app.settings_status_var.get(), operation_status=app.status_var.get(),
            busy=app.busy, log_directory=str(app.runtime_log.directory))

    def settings_action(self, action, data):
        from .preferences import FIELDS, normalize_value, validate_preferences, validate_public_url
        from .ui import PROTOCOL_LABELS
        app = self.app
        if action == "settings_back":
            app.show_workspace(0)
            return
        current = self.settings_snapshot()
        if data.get("revision") != current["revision"]:
            raise ValueError("设置已在其它操作中更新，请重新打开设置核对后再提交。")
        if action == "settings_rename_provider":
            from .model_catalog import PROVIDERS
            from .preferences import rename_provider_profile
            target, name = data.get("target"), data.get("name")
            if app.busy:
                raise ValueError("正在处理当前请求，完成或取消后再重命名供应商。")
            if not isinstance(target, str) or target in PROVIDERS or target not in app._provider_profiles or target != current["connection"]["provider"]:
                raise ValueError("请选择当前已保存的自定义供应商后重命名。")
            if not isinstance(name, str) or not name.strip() or len(name.strip()) >= 4096:
                raise ValueError("请填写有效的新服务名称。")
            name = name.strip()
            if any(key.casefold() == name.casefold() and key != target for key in (*PROVIDERS, *app._provider_profiles)):
                raise ValueError("这个服务名称已存在，请使用另一个名称。")
            if name == target:
                return dict(settings=current)
            # A failed encryption/write must not alter the current Tk state.
            profile = rename_provider_profile(app._preferences_path, target, name)
            app.model_directory_refresh.supersede(target)
            app._provider_profiles = {name if key == target else key: profile if key == target else value
                                      for key, value in app._provider_profiles.items()}
            suppressed = app._suppress_provider_callback
            app._suppress_provider_callback = True
            try:
                app._last_provider = name
                app.provider_var.set(name)
                # Renaming is not switching to another interface; keep its key
                # and directory rather than taking the normal switch callback.
                app.connection_version += 1
                app.model_directory_version += 1
                app._connection_state = app._generation_snapshot()
                app._model_directory_state = app._model_directory_snapshot()
                app._confirmed_connection_state = app._connection_state if profile.model_confirmed else None
                app.widgets["provider_combo"].configure(values=tuple(dict.fromkeys((*PROVIDERS, *app._provider_profiles))))
            finally:
                app._suppress_provider_callback = suppressed
            app._refresh_model_confirmation()
            app._refresh_primary_action()
            app.settings_status_var.set("已重命名供应商，接口、密钥和模型列表已保留。")
            LOG.info("Web custom provider rename applied; models=%s", len(profile.model_ids))
            return dict(settings=self.settings_snapshot())
        if action == "settings_delete_provider":
            from .model_catalog import PROVIDERS
            from .preferences import delete_provider_profile
            target = data.get("target")
            if app.busy:
                raise ValueError("正在处理当前请求，完成或取消后再删除供应商。")
            if target in PROVIDERS:
                raise ValueError("内置供应商不能删除。")
            if not isinstance(target, str) or target not in app._provider_profiles:
                raise ValueError("自定义供应商不存在，请重新打开设置。")
            # Commit deletion before changing memory; failed writes leave drafts intact.
            delete_provider_profile(app._preferences_path, target)
            app.model_directory_refresh.supersede(target)
            if app.provider_var.get() == target:
                app.provider_var.set("DeepSeek")
            app._provider_profiles.pop(target, None)
            app.widgets["provider_combo"].configure(values=tuple(dict.fromkeys((*PROVIDERS, *app._provider_profiles))))
            app.settings_status_var.set("已删除自定义供应商及其保存的密钥和模型列表。")
            LOG.info("Web custom provider deleted; active fallback=%s", app.provider_var.get() == "DeepSeek")
            return dict(settings=self.settings_snapshot())
        if action == "settings_browse":
            key = data.get("key")
            if key not in {"session_directory", "export_directory"}:
                raise ValueError("目录设置不存在。")
            from tkinter import filedialog
            path = filedialog.askdirectory(parent=app.root, initialdir=data.get("initial") or None)
            return dict(path=path or "")
        if action == "settings_debug":
            if not isinstance(data.get("enabled"), bool):
                raise ValueError("Debug 开关值无效。")
            app.debug_console_enabled_var.set(data["enabled"])
            app.set_debug_console_enabled()
            LOG.info("Web settings Debug toggle: enabled=%s", data["enabled"])
            return
        if action not in {"settings_autosave", "settings_save", "settings_confirm", "settings_test", "settings_models", "settings_provider"}:
            raise ValueError("设置操作不存在。")
        if app.busy:
            raise ValueError("正在处理当前请求，完成或取消后再提交设置。")
        connection = data.get("connection")
        values = data.get("values")
        if not isinstance(connection, dict) or not isinstance(values, dict):
            raise ValueError("设置内容格式不正确。")
        changed_fields = data.get("changed_fields")
        if action == "settings_autosave" and changed_fields is not None:
            if not isinstance(changed_fields, list) or any(not isinstance(key, str) or
                    (key not in FIELDS and key not in {"connection." + k for k in
                        ("provider", "protocol", "base_url", "model", "model_provider", "website")}) for key in changed_fields):
                raise ValueError("设置更新字段无效。")
            if changed_fields and all(key in FIELDS and FIELDS[key].category != "模型" for key in changed_fields):
                if data.get("key_action", "keep") != "keep" or data.get("key"):
                    raise ValueError("普通设置更新不能包含密钥操作。")
                if any(key not in values for key in changed_fields):
                    raise ValueError("设置更新缺少对应值。")
                changes = {key: normalize_value(key, values[key]) for key in changed_fields}
                window_changed = "window_width" in changes and changes["window_width"] != app.preferences["window_width"]
                app.save_desktop_settings(changes)
                window_notice = "启动窗口大小下次启动生效。" if window_changed else ""
                app.settings_status_var.set(f"已自动保存。{window_notice}")
                LOG.info("Web desktop settings autosaved: fields=%s deferred_window_size=%s", list(changes), window_changed)
                return dict(settings=self.settings_snapshot())
        if not {"provider", "protocol", "base_url", "model"} <= set(connection) or set(connection) - {"provider", "protocol", "base_url", "model", "model_provider", "website"} or any(not isinstance(v, str) or len(v) > 4096 for v in connection.values()):
            raise ValueError("模型连接字段无效。")
        if connection["protocol"] not in PROTOCOL_LABELS:
            raise ValueError("协议不存在。")
        if action == "settings_provider":
            target = data.get("target")
            if not isinstance(target, str) or not target.strip() or len(target) >= 4096 or connection["provider"] != current["connection"]["provider"]:
                raise ValueError("供应商选择已变化，请重新核对后切换。")
        else:
            from .model_catalog import validate_model_provider
            validate_model_provider(connection)
            validate_public_url(connection["base_url"])
            if connection.get("website"):
                validate_public_url(connection["website"])
        if action in {"settings_save", "settings_autosave"}:
            normalized = validate_preferences(values)
        elif action == "settings_provider":
            # Incomplete numeric drafts must not trap the user on this provider.
            normalized = {key: values.get(key, current["values"][key]) for key, spec in FIELDS.items() if spec.category == "模型"}
            if any(not isinstance(value, (str, int, float)) or len(str(value)) > 4096 for value in normalized.values()):
                raise ValueError("模型参数草稿无效。")
        else:
            normalized = {key: normalize_value(key, values.get(key, current["values"][key]))
                          for key, spec in FIELDS.items() if spec.category == "模型"}
        key_action = data.get("key_action", "keep")
        new_key = data.get("key", "")
        if key_action not in {"keep", "replace", "clear"} or not isinstance(new_key, str) or len(new_key) > 16384:
            raise ValueError("密钥操作无效。")
        if key_action == "replace" and not new_key.strip():
            raise ValueError("请输入新的 API Key，或选择保留已配置密钥。")
        if new_key:
            app.runtime_log.register_secret(new_key)
        for key, variable in (("provider", app.provider_var), ("protocol", app.protocol_var),
                              ("base_url", app.api_base_var), ("model", app.api_model_var)):
            if variable.get() != connection[key]:
                variable.set(connection[key])
        if "model_provider" in connection and app.model_provider_var.get() != connection["model_provider"]:
            app.model_provider_var.set(connection["model_provider"])
            # Restore an explicitly selected supported protocol after the family default.
            app.protocol_var.set(connection["protocol"])
        app.provider_website_var.set(connection.get("website", ""))
        if key_action != "keep":
            app.api_key_var.set(new_key if key_action == "replace" else "")
        for key, value in normalized.items():
            if str(app.preference_vars[key].get()) != str(value):
                app.preference_vars[key].set(value)
        if action in {"settings_save", "settings_autosave"}:
            roots = app.widgets["setting_extra_skill_roots"]
            roots.delete("1.0", "end")
            roots.insert("1.0", normalized["extra_skill_roots"])
        LOG.info("Web settings submitted: action=%s fields=%s credential_action=%s", action, list(normalized), key_action)
        if action == "settings_provider":
            app.provider_var.set(data["target"])
        elif action == "settings_autosave":
            ready = bool(app.api_key_var.get().strip() and app.api_model_var.get().strip())
            if ready:
                app._draft_api_config()
            if not app.save_settings(confirm_model=ready):
                if app._last_settings_save_error is not None:
                    raise app._last_settings_save_error
                raise ValueError(app.settings_status_var.get())
            app._confirmed_connection_state = app._generation_snapshot() if ready else None
            app._refresh_model_confirmation()
            app._refresh_primary_action()
            app.settings_status_var.set("已自动保存。" + ("模型配置可直接使用。" if ready else "填写模型 ID 和 API Key 后即可使用。"))
            LOG.info("Web settings autosaved: ready=%s credential_present=%s", ready, bool(app.api_key_var.get().strip()))
        elif action == "settings_save":
            if not app.save_settings():
                raise ValueError(app.settings_status_var.get())
        elif action == "settings_confirm":
            app._draft_api_config()
            app.confirm_model_settings()
            if not app._model_settings_confirmed():
                raise ValueError(app.settings_status_var.get() or "模型设置未确认，请修改后重试。")
        elif action == "settings_test":
            app._draft_api_config(timeout_seconds=app._model_preference_values()["connection_timeout"])
            app.test_connection()
        else:
            app._model_directory_config()
            app.fetch_models()
        return dict(settings=self.settings_snapshot())

    def prepare_panel(self):
        import tkinter as tk
        from .conversation import conversation_cards
        if self.panel_kind not in PANEL_ACTIONS:
            return
        token = (self.panel_kind, view_stamp(self.app), self.app._conversation_signature)
        if token == self.panel_token and self.panel_frame and self.panel_frame.winfo_exists():
            return
        selection = ()
        tree = self.app.widgets.get("conversation_requirements_tree")
        if tree is not None and tree.winfo_exists():
            selection = tree.selection()
        if self.panel_frame is not None:
            self.panel_frame.destroy()
        self.panel_frame = tk.Frame(self.app.root)
        cards = conversation_cards(self.app.session)
        self.app._conversation_render_token = self.app._conversation_token()
        if self.panel_kind == "result":
            self.app._render_result_options(self.panel_frame)
        self.panel_token = token

    def snapshot(self):
        from dataclasses import asdict
        from .conversation import conversation_cards, conversation_plan_text
        from .model_catalog import find_model
        from .skill_browser import table_rows, visible_rows, source_group
        from .skill_recommendation import recommendation_score
        from .ui import FIELD_LABELS, KIND_LABELS
        app = self.app
        if app.debug_console is not None and hasattr(app.debug_console, "update_palette"):
            app.debug_console.update_palette(app.preferences)
        self.prepare_panel()
        cards = conversation_cards(app.session)
        for card in cards:
            if card["kind"] == "plan":
                card["text"] = conversation_plan_text(card["content"])
            if card["kind"] == "skills":
                card["progress"] = app.skill_status_var.get()
                rows = visible_rows(table_rows(card["candidates"], card["bindings"]),
                    source=app.skill_source_filter_var.get(), show_all=app.show_all_skills_var.get(), limit=app.preferences["display_limit"])
                card["rows"] = [dict(id=r["candidate_id"], name=r.get("name", ""), source=source_group(r),
                    score=recommendation_score(r), selected=r.get("_already_selected", False),
                    allowed=bool(r.get("selection_allowed")) and not r.get("_already_selected", False),
                    bindings=r.get("_binding_ids", []), description=r.get("description", ""),
                    details="\n".join(str(r.get(k, "")) for k in ("match_reason", "fit_reason", "usage_suggestion",
                                      "recommendation_basis", "ai_evidence_note", "source_url", "local_path") if r.get(k))) for r in rows]
                # Full Skill files are unnecessary for presentation/selection.
                card.pop("candidates", None)
                card.pop("bindings", None)
        buttons = {}
        for key, button in app._conversation_buttons.items():
            if button.winfo_exists():
                text = button.text if hasattr(button, "text") else button.cget("text")
                buttons[key] = dict(text=str(text), enabled=str(button.cget("state")) != "disabled")
        req_rows = []
        for prefix, rows, idkey in (("r", app.session.requirements, "item_id"), ("p", app.session.pending_proposals, "proposal_id")):
            for row in rows:
                req_rows.append(dict(id=prefix+":"+row[idkey], field=FIELD_LABELS.get(row.get("field"), row.get("field", "要求")),
                    text=row.get("text", ""), kind=KIND_LABELS.get(row.get("kind"), "AI 建议"),
                    status="待确认解释" if prefix == "p" else "已确认" if row.get("confirmation") == "confirmed" else "待确认"))
        tree = app.widgets.get("conversation_requirements_tree")
        selection = tree.selection() if tree is not None and tree.winfo_exists() else ()
        page = "settings" if app.notebook.index(app.notebook.select()) == app._settings_page_index else "workspace"
        return dict(stamp=view_stamp(app), session=app._session_instance_token, cards=cards, buttons=buttons,
            navigation=app.session.workspace_navigation(), tutorial_status=self.tutorial_status,
            history=self.history.snapshot() if self.history is not None else None,
            drafts=deepcopy(app.session.control.get("workspace_drafts", {})),
            page=page, settings=self.settings_snapshot() if page == "settings" else None, notifications=list(self.notifications),
            locked=app._conversation_locked(), stop_scope=app._active_stop_token,
            status=app.status_var.get(), theme=app.preferences["composer_theme"],
            window_width=app.preferences["window_width"],
            font_size=app.preferences["font_size"], model=app.api_model_var.get(),
            display_preferences={key: app.preferences[key] for key in
                ("conversation_width", "notification_seconds", "thinking_autoscroll", "thinking_speed")},
            active_service=app.provider_var.get(),
            model_info=asdict(find_model(app.api_model_var.get())) if find_model(app.api_model_var.get()) else None,
            models=[asdict(m) for m in app.available_picker_models()],
            icons=self.icons, effort=app.preference_vars["reasoning_effort"].get(),
            category=app.category_var.get(), categories=list(app.category_by_label),
            depth=app.thinking_level_var.get(), depths=app._thinking_labels,
            summary=app.conversation_summary_var.get(), requirement_rows=req_rows, requirement_selection=list(selection),
            requirement_reason=app._preview_check(), conflicts=[r["description"] for r in app.session.open_conflicts],
            panel=self.panel_kind, editor=self.editors.snapshot(), source=app.skill_source_filter_var.get(), show_all=app.show_all_skills_var.get(),
            tone=app.final_tone_var.get(), notes=(app.session.final_result.get("content") or {}).get("user_notes", []),
            reanswer=app._answer_target_id, reanswer_text=app.question_context_var.get())

    def dispatch(self, action, data, stamp):
        previous = self._feedback_action
        self._feedback_action = action if action != "drafts" else None
        # A new explicit operation may legitimately report the same outcome.
        # Render/selection/draft polling must retain source de-duplication.
        if action in {"save", "save_as", "settings_autosave", "settings_debug", "history_retry", "send", "editor_save", "button", "stop", "navigate"}:
            self._feedback_values.pop("status_var", None)
            self._feedback_values.pop("settings_status_var", None)
        try:
            return self._dispatch(action, data, stamp)
        finally:
            self._feedback_action = previous

    def _dispatch(self, action, data, stamp):
        from .model_catalog import EFFORTS
        app = self.app
        if not isinstance(data, dict):
            raise ValueError("操作参数格式不正确。")
        if action in {"tutorial_finish", "tutorial_skip"}:
            from .preferences import save_tutorial_status
            if action == "tutorial_finish" and stamp != view_stamp(app):
                raise ValueError("页面已更新，请重新点击完成教程。")
            status = "completed" if action == "tutorial_finish" else "skipped"
            save_tutorial_status(app._preferences_path, status)
            self.tutorial_status = status
            return dict(tutorial_status=status)
        if action == "debug_closed":
            console = app.debug_console
            if console is not None and getattr(console, "identity", None) == data.get("id"):
                app._close_debug_console()
            return
        if action == "drafts":
            if self.history is not None:
                self.history.update_drafts(data)
            return
        if action == "panel":
            if data.get("kind") not in PANEL_ACTIONS and data.get("kind") is not None:
                raise ValueError("面板不存在。")
            self.panel_kind = data.get("kind")
            self.panel_token = None
            self.prepare_panel()
            LOG.debug("Web workspace panel: kind=%s", self.panel_kind)
            return
        if action == "stop":
            if data.get("session") != app._session_instance_token:
                raise ValueError("会话已变化，不能停止新会话的任务。")
            if data.get("scope") != app._active_stop_token:
                raise ValueError("处理任务已变化，请查看当前任务再停止。")
            app.cancel_active_request()
            return
        if action == "navigate":
            if data.get("session") != app._session_instance_token or data.get("scope") != app._active_stop_token:
                raise ValueError("会话或处理任务已变化，请查看当前内容再返回。")
            navigation = app.session.workspace_navigation()
            if data.get("direction") != "previous" or data.get("stage") != navigation["stage"] or not navigation["previous"]:
                raise ValueError("当前步骤已变化，请查看当前内容再返回。")
            if stamp != view_stamp(app):
                raise ValueError("内容已变化，请查看更新后的内容再返回。")
            drafts = data.get("answer_drafts")
            if drafts is not None and (not isinstance(drafts, dict)
                    or any(not isinstance(key, str) or not isinstance(text, str) for key, text in drafts.items())):
                raise ValueError("回答草稿格式不正确，当前内容已保留。")
            app.navigate_workspace("previous", answer_drafts=drafts)
            return
        if stamp != view_stamp(app):
            raise ValueError("内容已变化，请查看更新后的内容再操作。")
        if action.startswith("editor_"):
            return self.editors.action(action, data)
        if action.startswith("history_"):
            if self.history is None:
                raise ValueError("历史会话尚未启用。")
            self.history.action(action, data)
            self.panel_kind = self.panel_token = None
            return
        if action.startswith("settings_"):
            return self.settings_action(action, data)
        # Opening/saving/settings/cancel remain usable while a model is busy.
        if action in {"new", "open", "save", "save_as", "settings"}:
            self.editors.close("navigation")
            if action == "new" and self.history is None:
                self.editors.open("new")
                return
            method = {"new": app.new_session, "open": app.open_session, "save": app.save,
                      "save_as": lambda: app.save(save_as=True), "settings": app.show_settings}[action]
            method()
            if action in {"new", "open"}:
                self.panel_kind = self.panel_token = None
            return
        if action == "button":
            self.prepare_panel()
            button = app._conversation_buttons.get(data.get("key"))
            if button is None or not button.winfo_exists() or str(button.cget("state")) == "disabled":
                raise ValueError("当前操作尚不可用，请查看最新内容。")
            if data.get("key") == "edit_requirement":
                tree = app.widgets.get("conversation_requirements_tree")
                selected = tree.selection() if tree is not None else ()
                if len(selected) != 1:
                    raise ValueError("请选择一条需求进行编辑。")
                self.editors.open("requirement", selected[0])
                return
            if data.get("key") in {"edit_plan", "add_final_note"}:
                self.editors.open("plan" if data["key"] == "edit_plan" else "note")
                return
            button.invoke()
            return
        if app._conversation_locked():
            raise ValueError("正在处理当前任务，请稍候或取消本次请求。")
        if action == "send":
            entry = app.widgets["conversation_input"]
            entry.delete("1.0", "end")
            entry.insert("1.0", str(data.get("text", "")))
            app.send_conversation_message()
            if not app.widgets["conversation_input"].get("1.0", "end-1c"):
                app.session.control.setdefault("workspace_drafts", {})["message"] = ""
        elif action == "answer":
            # Retain the legacy single-answer contract for existing callers.
            rows = data.get("answers", [{"id": data.get("id"), "text": data.get("text", "")}])
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise ValueError("本轮回答格式不正确，请重新提交。")
            submitted = app.submit_guided_answers([
                {"question_id": row.get("id"), "text": row.get("text")} for row in rows
            ])
            return {"submitted": submitted}
        elif action == "skip":
            key = data.get("id")
            if key not in app._question_inputs:
                raise ValueError("这个问题已更新。")
            app._skip_inline_question(key, "skipped")
            app.session.control.setdefault("workspace_drafts", {}).setdefault("answers", {}).pop(key, None)
        elif action == "model":
            models = app.available_picker_models()
            model = next((m for m in models if m.id == data.get("id") and
                (not data.get("service") or m.service_provider == data["service"])), None)
            if model is None:
                raise ValueError("模型不存在。")
            app.widgets["conversation_composer"].choose_model(model)
        elif action == "effort":
            if data.get("value") not in EFFORTS:
                raise ValueError("思考强度不正确。")
            app.widgets["conversation_composer"].choose_effort(data["value"])
        elif action == "category":
            if data.get("value") not in app.category_by_label:
                raise ValueError("任务类型不正确。")
            app.category_var.set(data["value"])
            app._on_category_selected()
        elif action == "depth":
            if data.get("value") not in app._thinking_labels:
                raise ValueError("整理深度不正确。")
            app.thinking_level_display_var.set(app._thinking_labels[data["value"]])
            app._on_thinking_level_selected()
        elif action == "requirement_row":
            tree = app.widgets.get("conversation_requirements_tree")
            key = data.get("id")
            if tree is None or not tree.winfo_exists() or not tree.exists(key):
                raise ValueError("这条需求已更新。")
            tree.selection_set(key)
            app._conversation_show_requirement_selection()
        elif action == "select_skill":
            app.select_skill_candidates([str(data.get("id", ""))])
        elif action == "remove_skill":
            app.cancel_selected_skills(list(data.get("ids", [])))
        elif action == "source":
            from .skill_browser import SOURCE_FILTERS
            if data.get("value") not in SOURCE_FILTERS:
                raise ValueError("来源不正确。")
            app.skill_source_filter_var.set(data["value"])
            app.refresh()
        elif action == "show_all":
            app._conversation_toggle_skills()
        elif action == "tone":
            if data.get("value") not in {"中性", "适度礼貌"}:
                raise ValueError("语气不正确。")
            app.final_tone_var.set(data["value"])
            app.change_final_tone()
            app.refresh()
        elif action == "reanswer":
            app._conversation_reopen_question(str(data.get("id", "")))
        elif action == "cancel_reanswer":
            app._conversation_cancel_reanswer()
        else:
            raise ValueError("未知操作。")
        if action in {"model", "effort"}:
            return dict(model=app.api_model_var.get(), effort=app.preference_vars["reasoning_effort"].get(), active_service=app.provider_var.get())


class DesktopApi:
    """The only methods exposed to JavaScript. Never expose the app itself."""
    def __init__(self):
        self._queue = queue.Queue()
        self._lock = threading.Lock()
        self._state = None
        self._version = 0
        self._closing = threading.Event()

    def snapshot(self, since=0):
        with self._lock:
            if since == self._version:
                return None
            return dict(version=self._version, state=deepcopy(self._state))

    def _publish_sync_error(self):
        """Recover even if the first snapshot failed, without inventing state."""
        with self._lock:
            self._state = dict(self._state or {}, sync_error="界面同步暂未完成，请稍候重试；详细原因已记录到 Debug 控制台。")
            self._version += 1

    def dispatch(self, action, data, stamp):
        if self._closing.is_set():
            return dict(ok=False, error="程序正在关闭。")
        request = dict(action=action, data=data, stamp=stamp, done=threading.Event(), result=None)
        self._queue.put(request)
        while not request["done"].wait(.1):
            if self._closing.is_set():
                return dict(ok=False, error="程序正在关闭。")
        return request["result"]

    def diagnostic(self, level, event, detail):
        levels = {"debug": logging.DEBUG, "info": logging.INFO, "warn": logging.WARNING, "error": logging.ERROR}
        LOG.log(levels.get(level, logging.DEBUG), "Browser %s: %s", str(event)[:120], str(detail)[:12000])
        return True

    def _debug_closed(self, identity):
        self._queue.put(dict(action="debug_closed", data={"id": identity}, stamp=None,
                            done=threading.Event(), result=None))


class WebRendererUnavailable(RuntimeError):
    """Preflight failure before any workflow or native backend is started."""


def ensure_webview2():
    from webview.guilib import initialize
    try:
        gui = initialize("edgechromium")
        if gui.renderer != "edgechromium":
            raise RuntimeError("WebView2 renderer is not available")
    except Exception as exc:
        raise WebRendererUnavailable("无法启用 WebView2。请安装 Microsoft Edge WebView2 Runtime，并检查项目依赖；也可使用 --renderer tk 启动。") from exc


def run_web_workspace(logs, *, automatic_close=None):
    """Run Chromium on the main thread; retain native workflow on its Tk thread."""
    import webview
    from .display import enable_dpi_awareness
    enable_dpi_awareness()
    ensure_webview2()
    api = DesktopApi()
    from .web_debug import DebugWindowManager
    debug_windows = DebugWindowManager(api, logs)
    ready = threading.Event()
    failed = []

    def backend():
        import tkinter as tk
        from .ui import PromptSmithApp
        root = None
        app = None
        controller = None
        try:
            root = tk.Tk()
            root.withdraw()
            app = PromptSmithApp(root, runtime_log=logs, debug_console_factory=debug_windows.create_console)
            from .session_history import SessionHistory
            from .history_workspace import HistoryWorkspace
            from .paths import application_data_dir
            store = SessionHistory()
            try:
                store.import_directory(application_data_dir() / "sessions")
                if app.preferences["session_directory"]:
                    store.import_directory(app.preferences["session_directory"])
            except OSError:
                LOG.exception("Earlier session import could not finish; current workspace remains usable")
                store.issues.append("旧会话导入未完成，可通过文件菜单打开；原文件已保留。")
            controller = WorkspaceController(app, HistoryWorkspace(app, store))
            controller.install_native_bridge()
            root.protocol("WM_DELETE_WINDOW", root.withdraw)
            last_serialized = None
            last_publish = 0.
            def poll():
                nonlocal last_serialized, last_publish
                if api._closing.is_set():
                    app.close()
                    return
                dirty = False
                for _ in range(8):
                    try:
                        request = api._queue.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        result = controller.dispatch(request["action"], request["data"], request["stamp"])
                        request["result"] = dict(ok=True, data=result)
                        LOG.debug("Web workspace action completed: action=%s task=%s", request["action"], app.session.task_id)
                    except ValueError as exc:
                        LOG.info("Web workspace action requires refresh: action=%s reason=%s", request["action"], exc)
                        request["result"] = dict(ok=False, error=logs.redact(str(exc)), error_kind="validation")
                    except Exception:
                        LOG.exception("Web workspace action failed: action=%s", request["action"])
                        request["result"] = dict(ok=False, error="操作未完成，请重试；详细原因已记录到 Debug 控制台。", error_kind="persistence" if request["action"] == "settings_autosave" else "operation")
                    finally:
                        request["done"].set()
                    dirty = True
                if dirty or time.monotonic()-last_publish >= .1:
                    try:
                        state = controller.snapshot()
                        serialized = json.dumps(state, ensure_ascii=False, sort_keys=True)
                        if serialized != last_serialized:
                            with api._lock:
                                api._state = state
                                api._version += 1
                            last_serialized = serialized
                    except Exception:
                        LOG.exception("Web snapshot failed; bridge will retry")
                        api._publish_sync_error()
                        # Retry without stopping Tk's event loop or queued actions.
                    last_publish = time.monotonic()
                ready.set()
                root.after(16, poll)
            poll()
            root.mainloop()
        except Exception as exc:
            LOG.exception("Web workspace native backend failed")
            failed.append(exc)
            api._closing.set()
            ready.set()
        finally:
            api._closing.set()
            if app is not None:
                app.shutdown(wait=True)
                app.executor.shutdown(wait=True, cancel_futures=True)
            if root is not None:
                try:
                    root.destroy()
                except tk.TclError:
                    pass
            # Tcl objects must be released on their owning thread as well.
            if app is not None:
                app.widgets.clear()
            import gc
            app = None
            controller = None
            root = None
            gc.collect()

    thread = threading.Thread(target=backend, name="promptsmith-ui", daemon=True)
    thread.start()
    ready.wait()
    if failed:
        thread.join()
        raise RuntimeError("无法初始化对话工作区。") from failed[0]
    try:
        with tempfile.TemporaryDirectory(prefix="promptsmith-webview-") as profile:
            with api._lock:
                width = int((api._state or {}).get("window_width", 1440))
            window = webview.create_window("Intext", str(resource_root()/"resources/ui/workspace/index.html"),
                js_api=api, width=width, height=round(width*9/16), min_size=(720, 440), background_color="#ffffff", text_select=True)
            window.events.closed += api._closing.set
            def loaded():
                LOG.info("Web workspace loaded: engine=WebView2 renderer=%s", window.evaluate_js("navigator.userAgent"))
                if automatic_close:
                    threading.Timer(int(automatic_close)/1000, window.destroy).start()
            window.events.loaded += loaded
            def watch_shutdown():
                while not api._closing.wait(.1):
                    debug_windows.sync()
                debug_windows.close_all()
                if not window.events.closed.is_set():
                    window.destroy()
            LOG.info("Web workspace starting: animation=browser scrolling=browser backend=native")
            from .branding import brand_path
            webview.start(watch_shutdown, gui="edgechromium", storage_path=profile,
                          private_mode=True, http_server=True, icon=str(brand_path()))
    finally:
        api._closing.set()
        thread.join()
        LOG.info("Web workspace closed; native workers released")
    if failed:
        raise RuntimeError("对话工作区后台已关闭。") from failed[0]
    return 0
