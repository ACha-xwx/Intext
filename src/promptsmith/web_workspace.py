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
        self.history = history
        self.panel_kind = None
        self.panel_frame = None
        self.panel_token = None
        self.notifications = []
        self.notification_sequence = 0
        self.icons = {}
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
            self.notification_sequence += 1
            safe = app.runtime_log.redact(f"{title}：{message}")
            self.notifications.append(dict(id=self.notification_sequence, level=level, text=safe))
            self.notifications[:] = self.notifications[-8:]
            severity = {"error": logging.ERROR, "warn": logging.WARNING, "info": logging.INFO}[level]
            LOG.log(severity, "Web feedback: %s", safe, exc_info=sys.exc_info() if sys.exc_info()[0] else None)
        app._show_error = lambda title, message, **options: notify("error", title, message, **options)
        app._show_info = lambda title, message, **options: notify("info", title, message, **options)
        app._show_warning = lambda title, message, **options: notify("warn", title, message, **options)
        app.review_current_conflict = lambda: self.editors.open("conflict")

    def settings_snapshot(self):
        from .preferences import FIELDS
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
                        minimum=spec.minimum, maximum=spec.maximum, choices=list(spec.choices)) for key, spec in FIELDS.items()},
            providers={name: dict(base_url=preset["base_url"], protocol=PROTOCOL_NAMES[preset["protocol"]], model=preset["model"])
                       for name, preset in PROVIDER_PRESETS.items()}, protocols=list(PROTOCOL_LABELS),
            available_models=list(app.widgets["api_model_combo"].cget("values")),
            confirmed=app._model_settings_confirmed(), confirmation=app.model_confirmation_var.get(),
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
        if action not in {"settings_save", "settings_confirm", "settings_test", "settings_models", "settings_provider"}:
            raise ValueError("设置操作不存在。")
        if app.busy:
            raise ValueError("正在处理当前请求，完成或取消后再提交设置。")
        connection = data.get("connection")
        values = data.get("values")
        if not isinstance(connection, dict) or not isinstance(values, dict):
            raise ValueError("设置内容格式不正确。")
        if set(connection) != {"provider", "protocol", "base_url", "model"} or any(not isinstance(v, str) or len(v) > 4096 for v in connection.values()):
            raise ValueError("模型连接字段无效。")
        if connection["protocol"] not in PROTOCOL_LABELS:
            raise ValueError("协议不存在。")
        if action == "settings_provider":
            from .model_catalog import PROVIDERS
            if data.get("target") not in PROVIDERS or connection["provider"] != current["connection"]["provider"]:
                raise ValueError("供应商选择已变化，请重新核对后切换。")
        else:
            validate_public_url(connection["base_url"])
        if action == "settings_save":
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
        if key_action != "keep":
            app.api_key_var.set(new_key if key_action == "replace" else "")
        for key, value in normalized.items():
            if str(app.preference_vars[key].get()) != str(value):
                app.preference_vars[key].set(value)
        if action == "settings_save":
            roots = app.widgets["setting_extra_skill_roots"]
            roots.delete("1.0", "end")
            roots.insert("1.0", normalized["extra_skill_roots"])
        LOG.info("Web settings submitted: action=%s fields=%s credential_action=%s", action, list(normalized), key_action)
        if action == "settings_provider":
            app.provider_var.set(data["target"])
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
                rows = visible_rows(table_rows(card["candidates"], card["bindings"]),
                    source=app.skill_source_filter_var.get(), show_all=app.show_all_skills_var.get(), limit=app.preferences["display_limit"])
                card["rows"] = [dict(id=r["candidate_id"], name=r.get("name", ""), source=source_group(r),
                    score=recommendation_score(r), selected=r.get("_already_selected", False),
                    allowed=bool(r.get("selection_allowed")) and not r.get("_already_selected", False),
                    bindings=r.get("_binding_ids", []), description=r.get("description", ""),
                    details="\n".join(str(r.get(k, "")) for k in ("fit_reason", "usage_suggestion", "source_url", "local_path"))) for r in rows]
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
            navigation=app.session.workspace_navigation(),
            history=self.history.snapshot() if self.history is not None else None,
            drafts=deepcopy(app.session.control.get("workspace_drafts", {})),
            page=page, settings=self.settings_snapshot() if page == "settings" else None, notifications=list(self.notifications),
            locked=app._conversation_locked(), stop_scope=app._active_stop_token,
            status=app.status_var.get(), theme=app.preferences["composer_theme"],
            window_width=app.preferences["window_width"],
            font_size=app.preferences["font_size"], model=app.api_model_var.get(),
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
        from .model_catalog import EFFORTS
        app = self.app
        if not isinstance(data, dict):
            raise ValueError("操作参数格式不正确。")
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
            app.navigate_workspace("previous")
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
            key = data.get("id")
            if key not in app._question_inputs:
                raise ValueError("这个问题已更新，请回答当前问题。")
            widget = app._question_inputs[key]
            widget.delete("1.0", "end")
            widget.insert("1.0", str(data.get("text", "")))
            app._submit_inline_question(key)
            if key not in {q["question_id"] for q in app.session.questions_for_review()}:
                app.session.control.setdefault("workspace_drafts", {}).setdefault("answers", {}).pop(key, None)
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
                        request["result"] = dict(ok=False, error=str(exc))
                    except Exception:
                        LOG.exception("Web workspace action failed: action=%s", request["action"])
                        request["result"] = dict(ok=False, error="操作未完成，请重试；详细原因已记录到 Debug 控制台。")
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
            window = webview.create_window("PromptSmith", str(resource_root()/"resources/ui/workspace/index.html"),
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
            webview.start(watch_shutdown, gui="edgechromium", storage_path=profile, private_mode=True, http_server=True)
    finally:
        api._closing.set()
        thread.join()
        LOG.info("Web workspace closed; native workers released")
    if failed:
        raise RuntimeError("对话工作区后台已关闭。") from failed[0]
    return 0
