from __future__ import annotations

import hashlib
import logging
import os
import queue
import sys
import time
import tkinter as tk
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable
from urllib.parse import urlsplit
from uuid import uuid4

from .streaming import observe_stream

from .api import (
    ANTHROPIC_MESSAGES_PROTOCOL,
    OPENAI_RESPONSES_PROTOCOL,
    PROTOCOL_ID,
    DEFAULT_GENERATION_TIMEOUT_SECONDS,
    CONNECTION_TIMEOUT_SECONDS,
    structured_request_parameters,
    sampling_request_parameters,
    ApiConfig,
    ApiError,
    ModelListResult,
    client_for_config,
)
from .categories import CATEGORY_LABELS
from .task_scope import TaskScope, check_cancelled
from .m1 import M1Assets, M1ValidationError
from .m2 import M2Assets, M2ValidationError
from .m5 import M5Assets
from .paths import application_data_dir, resource_root
from .exporter import export_markdown
from .finalization import (
    DeliveryValidationError,
    blocking_review_required_ids,
    build_final_draft,
    confirm_final,
    decide_m2_suggestion,
    decide_m4_change,
    edit_final_note,
    render_task_prompt,
    set_final_tone,
    stage_final_draft,
    validate_current_final,
)
from .delivery_workflow import (
    DeliveryCallFailure,
    DeliveryStaleResponseError,
    DeliveryWorkflow,
    DeliveryWorkflowError,
)
from .skill_catalog import SkillCatalog, SkillCatalogError
from .local_skill_search import (
    LocalSkillSearchResult,
    search_local_skill_files as _search_local_skill_files,
    discover_local_skill_candidates,
)
from .skill_ai_selection import SkillAiSelectionError, select_skill_candidates_with_ai
from .skill_network_discovery import search_network_skill_candidates
from .local_skill_index import warm_local_skill_index
from .skill_recommendation import recommendation_score, shortlist_candidates
from .skill_browser import SOURCE_FILTERS, source_group, table_rows, visible_rows
from .open_skill_search import OPEN_WEB_SEARCH_URL
from .skill_search import (
    GITHUB_API_BASE,
    SkillSearchError,
    merge_candidates,
    search_online_skills,
)
from .session import SessionState, SessionStateError, StaleResponseError
from .storage import load_session, save_session
from .workflow import M1CallFailure, M1CallOutcome, M2CallFailure, M2CallOutcome, Phase12Workflow
from .guided_flow import GuidedFlowMixin
from .debug_console import DebugConsole
from .runtime_log import RuntimeLog
from .preferences import FIELDS, update_debug_preference
from .credentials import credential_context
from .model_catalog import PROVIDER_PRESETS
from .typography import Typography, ui_font



search_local_skill_files = _search_local_skill_files


@dataclass(frozen=True)
class StepSpec:
    title: str
    enabled: bool
    description: str


@dataclass(frozen=True)
class PrimaryAction:
    kind: str
    label: str
    reason: str
    enabled: bool = True


STEP_SPECS = (
    StepSpec("输入与需求", True, "输入任务，提取候选要求并完成需求确认。"),
    StepSpec("初始方案", True, "基于已确认需求生成、编辑、复核并确认完整初始方案。"),
    StepSpec("Skill 增强", True, "方案确认后查找本地和联网的 Agent Skill，可随时跳过。"),
    StepSpec("导出", True, "复核最终方案、切换受控语气、复制提示或导出 Markdown。"),
)

KIND_LABELS = {
    "user_fact": "用户事实",
    "user_decision": "用户决定",
    "system_suggestion": "系统建议",
    "pending_interpretation": "待用户确认的理解",
}
STRENGTH_LABELS = {"hard": "硬约束", "preference": "偏好"}
OPERATION_LABELS = {"new": "新增", "replace": "替换", "withdraw": "撤回"}
CONFIRMATION_LABELS = {"pending": "待确认", "confirmed": "已确认", "review_needed": "待复核"}
IMPORTANCE_LABELS = {"blocking_direction": "影响方向", "can_defer": "可暂缓"}
_PREREQUISITE_SOURCE_LABELS = {
    "user_reported": "用户说明",
    "catalog_evidence": "本地目录记录",
    "program_check": "程序检查",
    "remote_source_review": "远程来源复核",
}
FIELD_LABELS = {
    "goal": "目标",
    "deliverable": "交付物",
    "purpose": "用途",
    "use_context": "使用场景",
    "context": "背景",
    "constraints": "限制条件",
    "audience": "受众",
    "output_format": "输出形式",
    "success_criteria": "成功标准",
}
PROTOCOL_LABELS = {
    "OpenAI Chat Completions": PROTOCOL_ID,
    "OpenAI Responses": OPENAI_RESPONSES_PROTOCOL,
    "Anthropic Messages": ANTHROPIC_MESSAGES_PROTOCOL,
}
PROTOCOL_NAMES = {value: key for key, value in PROTOCOL_LABELS.items()}


def api_config_summary(config: ApiConfig) -> dict[str, Any]:
    return {
        "provider": config.provider,
        "protocol": config.protocol,
        "base_url": config.base_url,
        "model": config.model,
        "timeout_seconds": config.timeout_seconds,
    }


def json_request_parameters(config: ApiConfig) -> dict[str, Any]:
    return {**api_config_summary(config), **structured_request_parameters(config), **sampling_request_parameters(config)}


def generation_failure_message(purpose: str, exc: Exception, timeout_seconds: float | None) -> str:
    if purpose == "m2" and getattr(exc, "kind", None) == "truncated":
        return "AI 这次没有生成完整方案，你的需求和已有方案已保留。点击“重新生成方案”再试一次，程序会减少重复说明。"
    if purpose == "m2":
        kind = getattr(exc, "kind", None)
        retained = "你的回答、已确认需求和已有方案已保留，不用重新回答。"
        if kind in {"validation_error", "invalid_response"}:
            stage = getattr(exc, "validation_stage", None)
            reason = "AI 返回的方案结构或关联信息不完整" if stage == "semantic" else "AI 返回的内容格式暂时无法读取"
            return (f"{reason}。{retained}点击“重新生成方案”再试；若重复出现，可更换模型后重试。"
                    "暂未确定的任务细节可以留在最终提示中补充。")
        if kind == "content_error":
            return (f"{exc}\n{retained}\n建议：{getattr(exc, 'recovery_action', '') or '核对任务目标和希望得到的成果。'}"
                    "\n可返回“当前需求”补充说明后继续；细节暂时不知道时，可注明“使用提示时再确认”。")
        if kind in {"network_error", "network"}:
            return f"暂时无法连接模型服务。{retained}检查网络和模型地址，再点击“重新生成方案”。"
        result = getattr(exc, "api_result", None)
        status = getattr(exc, "status_code", None) or getattr(result, "status_code", None)
        if status in {401, 403} or kind == "authentication":
            return f"模型服务未接受当前访问凭据或权限。{retained}请在设置页核对密钥及模型访问权限，测试连接并点击“确认”后重新生成。"
        if status == 429 or kind == "rate_limit":
            return f"模型服务暂时限流或额度不足。{retained}稍后重试，或检查服务额度、切换可用模型。"
        if kind in {"http_error", "http"}:
            return f"模型服务拒绝了本次生成请求。{retained}请在设置页核对连接地址、接口类型和模型名称，测试连接并点击“确认”后重新生成；反复失败时可提供诊断记录排查。"
    if getattr(exc, "kind", None) != "timeout":
        next_step = {
            "m1": "回答已保留。可以补充一句说明后重新整理，或点击重试分析；已有需求可继续核对。",
            "m2": "需求已保留。可以补充目标或范围后重新生成方案，或在设置中检查模型连接。",
            "m3": "候选已保留。可以直接选用合适的 Skill，无需等待候选分析成功。",
            "m4": "所选 Skill 已保留。可以点击“用已选 Skill 直接生成提示词”，或重试模型整合。",
            "m5": "可以跳过示例，直接回答当前问题，或修改评价标准后重试。",
        }.get(purpose, "现有内容已保留，可以重试。")
        return f"{exc}\n\n下一步：{next_step}"
    label = {"m1": "需求分析", "m2": "初始方案生成", "m3": "候选分析",
             "m4": "Agent Skill 指令整合", "m5": "示例生成"}[purpose]
    wait = f"等待超过{timeout_seconds:g}秒" if timeout_seconds is not None else "等待超时"
    retained = "已有回答和需求已保留" if purpose == "m1" else "已有回答、需求和结果已保留"
    continuation = {"m3": "也可直接选用候选 Skill。", "m4": "也可点击“用已选 Skill 直接生成提示词”。",
                    "m5": "也可跳过示例并直接回答。"}.get(purpose, "")
    return f"{label}{wait}，{retained}，可检查网络、调整模型后点击重试。{continuation}"


class PromptSmithApp(GuidedFlowMixin):
    def __init__(
        self,
        root: tk.Tk,
        *,
        session: SessionState | None = None,
        assets: M1Assets | None = None,
        m2_assets: M2Assets | None = None,
        evidence_root: str | Path | None = None,
        runtime_log: RuntimeLog | None = None,
        diagnostics_root: str | Path | None = None,
        debug_console_factory=None,
    ):
        startup_started = time.perf_counter()
        self.root = root
        data_root = Path(diagnostics_root or (
            runtime_log.directory.parent if runtime_log is not None else
            (Path(evidence_root).parent if Path(evidence_root).name == "runs" else Path(evidence_root))
            if evidence_root is not None else application_data_dir()
        ))
        self.runtime_log = runtime_log or RuntimeLog(data_root / "logs").start()
        self._init_preferences(data_root)
        self.runtime_log.set_history_limit(self.preferences["debug_history"])
        self._owns_runtime_log = runtime_log is None
        self.debug_console = None
        self._debug_console_factory = debug_console_factory or DebugConsole
        self._shutdown = False
        self._tk_root = self.root._root()
        self._previous_callback_exception = self._tk_root.report_callback_exception
        self._tk_root.report_callback_exception = self._report_callback_exception
        self.runtime_log.register_secret(os.environ.get("PROMPTSMITH_GITHUB_TOKEN"))
        self.runtime_log.register_secret(os.environ.get("PROMPTSMITH_API_KEY"))
        logging.getLogger(__name__).info("Initializing desktop application; Python %s", sys.version)
        self.session = session or self._new_preferred_session()
        self.assets = assets or M1Assets.load()
        self.m2_assets = m2_assets or M2Assets.load()
        self.evidence_root = Path(evidence_root or (application_data_dir() / "runs"))
        self.workflow = Phase12Workflow(
            self.session, self.assets, self.evidence_root, self.m2_assets
        )
        self._session_instance_token = uuid4().hex
        self.delivery_workflow = DeliveryWorkflow(
            self.session,
            evidence_root=self.evidence_root,
            session_instance_token=self._session_instance_token,
        )
        self.delivery_busy = False
        self._delivery_status_text = ""
        self._delivery_status_basis = None
        self._active_delivery_request: dict[str, Any] | None = None
        # Tests and deployments may provide an opener without changing the
        # GitHub normalization or the rest of the delivery workflow.
        self.skill_search_opener: Callable[..., Any] | None = None
        self.skill_search_token = os.environ.get("PROMPTSMITH_GITHUB_TOKEN")
        self.skill_search_timeout = self.preferences["search_timeout"]
        self._skill_search_request: dict[str, Any] | None = None
        self._skill_search_busy = False
        self._skill_search_status_text = ""
        self.catalog: SkillCatalog | None = None
        self._catalog_path = resource_root() / "resources" / "skill_catalog" / "catalog_v0.1.json"
        try:
            self.catalog = SkillCatalog.load(self._catalog_path, source_root=resource_root())
        except (FileNotFoundError, SkillCatalogError):
            logging.getLogger(__name__).exception("Built-in Skill catalog unavailable: %s", self._catalog_path)
            self.catalog = None
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="promptsmith")
        self._retired_executors: list[ThreadPoolExecutor] = []
        self._session_tasks = TaskScope()
        self._active_stop_token = uuid4().hex
        self._application_tasks = TaskScope()
        self._background_futures: dict[Future, TaskScope] = {}
        self._background_lock = Lock()
        self.completions: queue.Queue[tuple[Callable[[Any], None], Any]] = queue.Queue()
        self.session_path: Path | None = None
        self.busy = False
        self.busy_kind: str | None = None
        self.connection_version = 0
        self._connection_state: tuple[Any, ...] | None = None
        self._confirmed_connection_state: tuple[Any, ...] | None = None
        self.model_directory_version = 0
        self._model_directory_state: tuple[str, str, str, str] | None = None
        self._last_provider = "DeepSeek"
        self._suppress_provider_callback = False
        self.widgets: dict[str, Any] = {}
        self.category_by_label = {label: key for key, label in CATEGORY_LABELS.items()}
        self.category_by_label["自动判断"] = None

        self.status_var = tk.StringVar(value="就绪。真实模型尚未连接。")
        self.debug_console_enabled_var = self.preference_vars["debug_console_enabled"]
        self.provider_var = tk.StringVar(value=os.environ.get("PROMPTSMITH_PROVIDER", self._saved_connection.get("provider", "DeepSeek")))
        self.protocol_var = tk.StringVar(value=self._saved_connection.get("protocol") if self._saved_connection.get("protocol") in PROTOCOL_LABELS else "OpenAI Chat Completions")
        self.api_base_var = tk.StringVar(value=os.environ.get("PROMPTSMITH_API_BASE_URL", self._saved_connection.get("base_url", "https://api.deepseek.com")))
        self.api_model_var = tk.StringVar(value=os.environ.get("PROMPTSMITH_MODEL", self._saved_connection.get("model", "deepseek-flash")))
        self._last_provider = self.provider_var.get()
        current_connection = {"provider": self.provider_var.get(), "protocol": self.protocol_var.get(),
                              "base_url": self.api_base_var.get()}
        if self._saved_api_key and credential_context(current_connection) != credential_context(self._saved_connection):
            self._saved_api_key = ""
            self._settings_load_warning = "当前接口配置与保存时不同，未恢复 API Key。请在模型设置中重新输入密钥并确认。"
            self.settings_status_var.set(self._settings_load_warning)
            logging.getLogger(__name__).warning("Saved API Key not reused: startup connection identity changed")
        self.api_key_var = tk.StringVar(value=self._saved_api_key)
        self._saved_api_key = ""
        self.api_key_var.trace_add("write", lambda *_: self.runtime_log.register_secret(self.api_key_var.get()))
        self.model_confirmation_var = tk.StringVar(value="尚未确认模型设置。测试连接只检查接口；点击“确认”后用于任务。")
        self.category_var = tk.StringVar(value=CATEGORY_LABELS.get(self.session.selected_category, "自动判断"))
        # The interview depth is a user preference for coverage, not a hard
        # question/round budget.  Keep it in the session so it survives a
        # save/reopen and reaches the M1 input contract.
        self.thinking_level_var = tk.StringVar(
            value=self.session.control.get("thinking_level", "standard")
        )
        self.thinking_level_display_var = tk.StringVar(value="")
        self.answer_var = tk.StringVar(value="")
        self.assistant_var = tk.StringVar(value="尚未运行需求分析。")
        self.summary_var = tk.StringVar(value="当前需求 v0 · 未确认 · AI 会根据未解决的问题继续判断")
        self.next_step_var = tk.StringVar(value="下一步：输入任务并开始分析。")
        self.primary_action_var = tk.StringVar(value="开始分析")
        self.plan_summary_var = tk.StringVar(value="尚未生成初始方案。")
        self.plan_next_step_var = tk.StringVar(value="先在需求页确认当前需求。")
        self.plan_section_var = tk.StringVar(value="")
        self.skill_status_var = tk.StringVar(value="尚未查找本地 Skill 目录。")
        self.show_all_skills_var = tk.BooleanVar(value=False)
        self.skill_source_filter_var = tk.StringVar(value="全部来源")
        self.skill_search_url_var = tk.StringVar(
            value=(
                self.session.control.get("skill_search_url")
                or os.environ.get("PROMPTSMITH_SKILL_SEARCH_URL", self.preferences["skill_search_url"])
            )
        )
        self.skill_next_step_var = tk.StringVar(value="确认初始方案后，可查找本地或联网 Agent Skill，也可直接跳过。")
        self.final_status_var = tk.StringVar(value="尚未生成最终草稿。")
        self.final_tone_var = tk.StringVar(value="中性")
        self.final_prompt_var = tk.StringVar(value="")
        self.skill_prerequisite_status_var = tk.StringVar(value="仍未知")
        self._selected_skill_binding_id: str | None = None
        self._plan_section_lookup: dict[str, tuple[str, str]] = {}
        self._final_review_lookup: dict[str, dict[str, Any]] = {}
        self._rendered_plan_token: tuple[Any, ...] | None = None
        self._page_canvases: set[tk.Canvas] = set()
        self._page_canvas_by_frame: dict[str, tk.Canvas] = {}
        self._wheel_bindtag = f"PromptSmithWheel_{uuid4().hex}"
        self._wheel_bound_widgets: list[tk.Misc] = []
        self._wheel_context: tuple[str, ...] | None = None
        self._wheel_direction = 0
        self._wheel_remainder = 0
        self._wheel_binding_registered = False

        self._configure_root()
        self._build_menu()
        self._build_layout()
        self._apply_visual_preferences()
        self._connection_state = self._generation_snapshot()
        self._model_directory_state = self._model_directory_snapshot()
        self.provider_var.trace_add("write", self._on_provider_changed)
        for variable in (
            self.provider_var,
            self.protocol_var,
            self.api_base_var,
            self.api_model_var,
            self.api_key_var,
        ):
            variable.trace_add("write", self._on_connection_changed)
        for key, variable in self.preference_vars.items():
            if FIELDS[key].category == "模型":
                variable.trace_add("write", self._on_connection_changed)
        self._restore_model_settings_confirmation()
        self._refresh_model_confirmation()
        self.refresh()
        if self._settings_load_warning:
            self.status_var.set(self._settings_load_warning)
        for name in ("status_var", "skill_status_var"):
            variable = getattr(self, name)
            variable.trace_add("write", lambda *_args, var=variable, source=name:
                               logging.getLogger("promptsmith.status").info("%s: %s", source, var.get()))
        logging.getLogger(__name__).info("Desktop ready: initialization=%.3fs native_font=%s; model evidence directory: %s",
                                         time.perf_counter()-startup_started, self.typography.family, self.evidence_root)
        if self.debug_console_enabled_var.get():
            self.set_debug_console_enabled(persist=False)
        self._completion_after_id = self.root.after(50, self._poll_completions)
        roots = self._skill_roots()
        self._submit(lambda: warm_local_skill_index(roots), lambda _value: None, lambda _exc: None,
                     session_scoped=False)

    def _report_callback_exception(self, exc_type, value, traceback) -> None:
        logging.getLogger(__name__).error("Unhandled Tk callback exception",
                                          exc_info=(exc_type, value, traceback))
        self._previous_callback_exception(exc_type, value, traceback)

    def _show_error(self, title, message, **options):
        logging.getLogger("promptsmith.ui.error").error(
            "%s: %s", title, message,
            exc_info=sys.exc_info() if sys.exc_info()[0] is not None else None,
        )
        return messagebox.showerror(title, message, **options)

    def _show_info(self, title, message, **options):
        logging.getLogger("promptsmith.ui.notice").info(
            "%s: %s", title, message, exc_info=sys.exc_info() if sys.exc_info()[0] else None,
        )
        return messagebox.showinfo(title, message, **options)

    def _show_warning(self, title, message, **options):
        logging.getLogger("promptsmith.ui.notice").warning(
            "%s: %s", title, message, exc_info=sys.exc_info() if sys.exc_info()[0] else None,
        )
        return messagebox.showwarning(title, message, **options)

    def set_debug_console_enabled(self, *, persist: bool = True) -> None:
        enabled = self.debug_console_enabled_var.get()
        if enabled and self.debug_console is None:
            self.debug_console = self._debug_console_factory(self.root, self.runtime_log, self._close_debug_console)
            self.debug_console.apply_preferences(self.preferences)
            logging.getLogger(__name__).info("Debug console opened")
        elif not enabled and self.debug_console is not None:
            self.debug_console.close()
            self.debug_console = None
            logging.getLogger(__name__).info("Debug console closed; in-memory log collection continues")
        elif enabled:
            self.debug_console.window.lift()
        if persist:
            try:
                update_debug_preference(self._preferences_path, enabled)
                self.preferences["debug_console_enabled"] = enabled
                logging.getLogger(__name__).debug("Debug window preference saved to settings.json: enabled=%s", enabled)
            except (OSError, ValueError):
                logging.getLogger(__name__).exception("Cannot save debug console preference")
                message = "控制台已切换，但开关未保存。请检查设置文件权限或点击“保存设置”后重试。"
                self.status_var.set(message)
                self.settings_status_var.set(message)

    def _close_debug_console(self) -> None:
        self.debug_console_enabled_var.set(False)
        self.set_debug_console_enabled()

    def _configure_root(self) -> None:
        from .display import display_scale
        self.root.title("PromptSmith · 需求引导式提示构建助手")
        # Tk may see a smaller logical desktop under Windows display scaling.
        # Keep the fixed next-step bar on-screen and let page content scroll.
        available_width = max(320, self.root.winfo_screenwidth() - 40)
        available_height = max(240, self.root.winfo_screenheight() - 100)
        # Target 1440×810, fitting both dimensions together to keep 16:9.
        scale = display_scale(self.root)
        size_units = min(round(self.preferences["window_width"] * scale) // 16, available_width // 16, available_height // 9)
        width, height = size_units * 16, size_units * 9
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(min(960, width), min(540, height))
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        logging.getLogger(__name__).info("Desktop display: tk_scaling=%.3f density=%.3f window=%sx%s",
                                         float(self.root.tk.call("tk", "scaling")), scale, width, height)
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        self.typography = Typography(self.root, self.preferences)
        style.configure("Title.TLabel", font=ui_font(self.root, "title", "bold"))
        style.configure("Section.TLabel", font=ui_font(self.root, "body", "bold"))
        style.configure("Muted.TLabel", foreground="#5f6368")
        style.configure("Danger.TLabel", foreground="#a1362f")
        style.configure("Treeview", rowheight=max(34,ui_font(self.root).metrics("linespace")+12), font=ui_font(self.root))
        style.configure("Treeview.Heading", font=ui_font(self.root, "heading", "bold"))
        style.configure("TLabel", font=ui_font(self.root))
        style.configure("TButton", font=ui_font(self.root))
        style.configure("TEntry", font=ui_font(self.root))

    def _build_menu(self) -> None:
        menu = tk.Menu(self.root, font=ui_font(self.root))
        file_menu = tk.Menu(menu, tearoff=False, font=ui_font(self.root))
        file_menu.add_command(label="新建会话", command=self.new_session)
        file_menu.add_command(label="打开会话...", command=self.open_session)
        file_menu.add_command(label="保存", command=self.save)
        file_menu.add_command(label="另存为...", command=lambda: self.save(save_as=True))
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.close)
        menu.add_cascade(label="文件", menu=file_menu)
        self.root.configure(menu=menu)

    def _legacy_build_layout(self) -> None:
        shell = ttk.Frame(self.root, padding=(18, 14, 18, 10))
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(2, weight=1)

        ttk.Label(shell, text="PromptSmith", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            shell,
            text="把模糊任务逐步整理成可确认的需求。模型只提出候选，确认与版本由程序维护。",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 12))

        self.notebook = ttk.Notebook(shell)
        self.notebook.grid(row=2, column=0, sticky="nsew")
        self.widgets["notebook"] = self.notebook
        for index, step in enumerate(STEP_SPECS):
            page_key = ("requirements", "plan", "skills", "export")[index]
            page, content = self._scrollable_page(page_key)
            self.notebook.add(page, text=f"{index + 1}. {step.title}")
            if index == 0:
                self._build_requirements_page(content)
            elif index == 1:
                self._build_plan_page(content)
            elif index == 2:
                self._build_skills_page(content)
            else:
                self._build_export_page(content)

        status = ttk.Frame(shell)
        status.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        status.columnconfigure(0, weight=1)
        ttk.Label(status, textvariable=self.status_var, anchor="w").grid(row=0, column=0, sticky="ew")
        ttk.Label(status, text=self._status_versions_text(), style="Muted.TLabel").grid(
            row=0, column=1, sticky="e"
        )
        self._register_page_wheel_routing()

    @staticmethod
    def _status_versions_text() -> str:
        """Report the prompt revisions the running build actually loads.

        The status bar used to hard-code this string, so it drifted out of date
        silently whenever a prompt revision was bumped.  Keep it derived from the
        asset dataclasses instead of re-typing the version numbers here.
        """
        m1_suffix = M1Assets.prompt_version.removeprefix("M1_system_")
        m2_suffix = M2Assets.prompt_version.removeprefix("M2_system_")
        m5_suffix = M5Assets.prompt_version.removeprefix("M5_system_")
        return " · ".join(
            (
                f"M1 {m1_suffix} / {M1Assets.contract_version}",
                f"M2 {m2_suffix} / {M2Assets.contract_version}",
                f"M5 {m5_suffix} / {M5Assets.contract_version}",
            )
        )

    def _scrollable_page(self, name: str, *, parent=None) -> tuple[ttk.Frame, ttk.Frame]:
        page = ttk.Frame(parent or self.notebook)
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)
        canvas = tk.Canvas(page, highlightthickness=0, borderwidth=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(page, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)
        content = ttk.Frame(canvas, padding=12)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def update_region(_event: tk.Event | None = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def fit_content(event: tk.Event) -> None:
            canvas.itemconfigure(window_id, width=max(1, event.width))
            update_region()

        content.bind("<Configure>", update_region, add="+")
        canvas.bind("<Configure>", fit_content, add="+")
        self._page_canvases.add(canvas)
        self._page_canvas_by_frame[str(page)] = canvas
        self.widgets[f"{name.lower().replace(' ', '_')}_page_canvas"] = canvas
        self.widgets[f"{name.lower().replace(' ', '_')}_page_content"] = content
        return page, content

    def _register_page_wheel_routing(self) -> None:
        self.root.bind_class(self._wheel_bindtag, "<MouseWheel>", self._route_page_mousewheel)
        self._wheel_binding_registered = True

        def visit(widget: tk.Misc) -> None:
            tags = widget.bindtags()
            if self._wheel_bindtag not in tags:
                widget.bindtags((tags[0], self._wheel_bindtag, *tags[1:]))
                self._wheel_bound_widgets.append(widget)
            for child in widget.winfo_children():
                visit(child)

        for page_path in self._page_canvas_by_frame:
            visit(self.root.nametowidget(page_path))

    def _route_page_mousewheel(self, event: tk.Event) -> str | None:
        delta = int(event.delta)
        active_page = str(self.notebook.select())
        canvas = self._page_canvas_by_frame.get(active_page)
        if canvas is None:
            self._reset_wheel_accumulator()
            return "break"
        try:
            grab = self.root.grab_current()
            if grab is not None and str(grab) != str(self.root):
                self._reset_wheel_accumulator()
                return "break"
        except (KeyError, tk.TclError):
            self._reset_wheel_accumulator()
            return "break"
        try:
            pointer_widget = self.root.winfo_containing(event.x_root, event.y_root)
        except (KeyError, tk.TclError):
            pointer_widget = None
        if pointer_widget is not None:
            try:
                if str(pointer_widget.winfo_toplevel()) != str(self.root):
                    self._reset_wheel_accumulator()
                    return "break"
            except tk.TclError:
                self._reset_wheel_accumulator()
                return "break"
        pointer_widget = self._widget_at_page_point(active_page, canvas, int(event.x_root), int(event.y_root))
        if pointer_widget is None:
            self._reset_wheel_accumulator()
            return "break"

        internal = self._nearest_inner_scrollable(pointer_widget, canvas)
        if event.state & 0x0001:
            if internal is not None and self._can_scroll_axis(internal, delta, "x"):
                context = (str(self.root), active_page, str(pointer_widget), "x", str(internal))
                steps = self._wheel_steps(delta, context)
                if steps:
                    direction = 1 if delta > 0 else -1
                    try:
                        internal.xview_scroll(-direction * min(steps * 3, 60), "units")
                    except tk.TclError:
                        self._reset_wheel_accumulator()
            else:
                self._reset_wheel_accumulator()
            return "break"

        scroll_target = internal if internal is not None and self._can_scroll(internal, delta) else canvas
        context = (str(self.root), active_page, str(pointer_widget), "y", str(scroll_target))
        steps = self._wheel_steps(delta, context)
        if steps:
            units = min(steps, 20) if scroll_target is canvas else min(steps * 3, 60)
            direction = 1 if delta > 0 else -1
            try:
                scroll_target.yview_scroll(-direction * units, "units")
            except tk.TclError:
                self._reset_wheel_accumulator()
        return "break"

    def _widget_at_page_point(
        self, page_path: str, canvas: tk.Canvas, x: int, y: int
    ) -> tk.Misc | None:
        try:
            if not self.root.winfo_rootx() <= x < self.root.winfo_rootx() + self.root.winfo_width():
                return None
            if not self.root.winfo_rooty() <= y < self.root.winfo_rooty() + self.root.winfo_height():
                return None
        except tk.TclError:
            return None

        canvas_path = str(canvas)
        matches: list[tk.Misc] = []
        for widget in self._wheel_bound_widgets:
            path = str(widget)
            if path != page_path and not path.startswith(page_path + "."):
                continue
            try:
                if not widget.winfo_ismapped():
                    continue
                left, top = widget.winfo_rootx(), widget.winfo_rooty()
                right, bottom = left + widget.winfo_width(), top + widget.winfo_height()
                if not (left <= x < right and top <= y < bottom):
                    continue
                if path.startswith(canvas_path + ".") and not (
                    canvas.winfo_rootx() <= x < canvas.winfo_rootx() + canvas.winfo_width()
                    and canvas.winfo_rooty() <= y < canvas.winfo_rooty() + canvas.winfo_height()
                ):
                    continue
                if any(path.startswith(str(inner) + ".") and not (
                    inner.winfo_rootx() <= x < inner.winfo_rootx()+inner.winfo_width()
                    and inner.winfo_rooty() <= y < inner.winfo_rooty()+inner.winfo_height()
                ) for inner in self._page_canvases if inner is not canvas):
                    continue
            except tk.TclError:
                continue
            matches.append(widget)
        if not matches:
            return None
        return max(matches, key=lambda widget: str(widget).count("."))

    @staticmethod
    def _nearest_inner_scrollable(widget: tk.Misc, page_canvas: tk.Canvas) -> tk.Misc | None:
        current = widget
        while current is not page_canvas:
            if current.winfo_class() in {"Text", "Treeview", "Listbox", "Canvas"}:
                return current
            parent_name = current.winfo_parent()
            if not parent_name:
                break
            try:
                current = current.nametowidget(parent_name)
            except (KeyError, tk.TclError):
                break
        return None

    @staticmethod
    def _can_scroll(widget: tk.Misc, delta: int) -> bool:
        return PromptSmithApp._can_scroll_axis(widget, delta, "y")

    @staticmethod
    def _can_scroll_axis(widget: tk.Misc, delta: int, axis: str) -> bool:
        if not delta:
            return False
        try:
            first, last = map(float, getattr(widget, f"{axis}view")())
        except (AttributeError, tk.TclError, TypeError, ValueError):
            return False
        if delta > 0:
            return first > 0.0001
        return last < 0.9999

    def _wheel_steps(self, delta: int, context: tuple[str, ...]) -> int:
        if delta == 0:
            self._reset_wheel_accumulator()
            return 0
        direction = 1 if delta > 0 else -1
        if context != self._wheel_context or direction != self._wheel_direction:
            self._wheel_remainder = 0
        total = abs(delta) + self._wheel_remainder
        steps, self._wheel_remainder = divmod(total, 120)
        self._wheel_context = context
        self._wheel_direction = direction
        return steps

    def _reset_wheel_accumulator(self) -> None:
        self._wheel_context = None
        self._wheel_direction = 0
        self._wheel_remainder = 0

    def _legacy_build_plan_page(self, page: ttk.Frame) -> None:
        page.columnconfigure(0, weight=1)
        page.rowconfigure(2, weight=1)

        header = ttk.Frame(page)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        ttk.Label(header, text="完整初始方案", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, textvariable=self.plan_summary_var, style="Muted.TLabel").grid(
            row=0, column=1, sticky="e"
        )
        ttk.Label(page, textvariable=self.plan_next_step_var, style="Section.TLabel", wraplength=1000).grid(
            row=1, column=0, sticky="ew", pady=(5, 8)
        )

        content = ttk.Panedwindow(page, orient="horizontal")
        content.grid(row=2, column=0, sticky="nsew")
        left = ttk.Frame(content)
        right = ttk.Frame(content)
        content.add(left, weight=3)
        content.add(right, weight=2)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(3, weight=1, minsize=100)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=3, minsize=90)
        right.rowconfigure(3, weight=2, minsize=70)

        ttk.Label(left, text="目标", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        goal = tk.Text(left, height=3, wrap="word", undo=True, font=ui_font(self.root))
        goal.grid(row=1, column=0, sticky="ew", pady=(4, 4))
        goal_buttons = ttk.Frame(left)
        goal_buttons.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(goal_buttons, text="保存目标修改", command=self.save_plan_goal).pack(side="left")
        ttk.Button(goal_buttons, text="编辑受众与范围", command=self.edit_plan_goal_details).pack(
            side="left", padx=6
        )
        ttk.Button(goal_buttons, text="生成 / 重新生成", command=self.start_plan_generation).pack(
            side="right"
        )

        steps = self._tree(left, ("order", "title", "purpose"), (55, 190, 350), height=7)
        steps._promptsmith_container.grid(row=3, column=0, sticky="nsew")
        steps.bind("<<TreeviewSelect>>", lambda _event: self._show_selected_plan_step())
        step_buttons = ttk.Frame(left)
        step_buttons.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(step_buttons, text="编辑步骤", command=self.edit_selected_plan_step).pack(side="left")
        ttk.Button(step_buttons, text="新增步骤", command=self.add_plan_step).pack(side="left", padx=6)
        ttk.Button(step_buttons, text="删除步骤", command=self.delete_selected_plan_step).pack(side="left")
        ttk.Button(step_buttons, text="上移", command=lambda: self.move_selected_plan_step(-1)).pack(
            side="left", padx=(12, 6)
        )
        ttk.Button(step_buttons, text="下移", command=lambda: self.move_selected_plan_step(1)).pack(
            side="left"
        )

        section_bar = ttk.Frame(right)
        section_bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        section_bar.columnconfigure(0, weight=1)
        section_combo = ttk.Combobox(
            section_bar, textvariable=self.plan_section_var, state="readonly"
        )
        section_combo.grid(row=0, column=0, sticky="ew")
        ttk.Button(section_bar, text="编辑选中栏目", command=self.edit_selected_plan_section).grid(
            row=0, column=1, padx=(6, 0)
        )
        overview = tk.Text(
            right, height=8, wrap="word", state="disabled", background="#f4f5f7", font=ui_font(self.root)
        )
        overview.grid(row=1, column=0, sticky="nsew", pady=(4, 8))
        overview_scroll = ttk.Scrollbar(right, orient="vertical", command=overview.yview)
        overview_scroll.grid(row=1, column=1, sticky="ns", pady=(4, 8))
        overview.configure(yscrollcommand=overview_scroll.set)

        ttk.Label(right, text="关键工作", style="Section.TLabel").grid(row=2, column=0, sticky="w")
        key_work = self._tree(right, ("title", "status"), (260, 100), height=3)
        key_work._promptsmith_container.grid(row=3, column=0, sticky="nsew", pady=(4, 4))
        key_work.bind("<<TreeviewSelect>>", lambda _event: self._show_selected_key_work())
        key_buttons = ttk.Frame(right)
        key_buttons.grid(row=4, column=0, sticky="nsew")
        ttk.Button(key_buttons, text="编辑关键工作", command=self.edit_selected_key_work).pack(
            side="left"
        )
        review_key_work_button = ttk.Button(key_buttons, text="标记已复核", command=self.review_selected_key_work)
        review_key_work_button.pack(side="left")
        ttk.Button(key_buttons, text="修改需求", command=self.go_to_requirements).pack(side="left", padx=6)
        ttk.Button(key_buttons, text="确认当前方案", command=self.confirm_plan).pack(side="right")

        self.widgets.update(
            {
                "plan_goal_text": goal,
                "plan_steps_tree": steps,
                "plan_overview_text": overview,
                "plan_section_combo": section_combo,
                "plan_key_work_tree": key_work,
                "review_key_work_button": review_key_work_button,
                "generate_plan_button": next(
                    child for child in goal_buttons.winfo_children() if child.cget("text") == "生成 / 重新生成"
                ),
                "confirm_plan_button": next(
                    child for child in key_buttons.winfo_children() if child.cget("text") == "确认当前方案"
                ),
            }
        )
        for widget in (goal, section_combo, overview):
            self._bind_context_menu(widget)

    def _build_skills_page(self, page: ttk.Frame) -> None:
        page.columnconfigure(0, weight=1)
        page.rowconfigure(4, minsize=270)
        ttk.Label(page, text="Agent Skill 参考", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(page, textvariable=self.skill_next_step_var, style="Section.TLabel", wraplength=1000).grid(
            row=1, column=0, sticky="ew", pady=(5, 8)
        )
        controls = ttk.Frame(page)
        controls.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        find_button = ttk.Button(controls, text="查找本地 Skill", command=self.find_skills)
        find_button.pack(side="left")
        online_button = ttk.Button(controls, text="继续联网搜索", command=self.search_online_skills)
        online_button.pack(side="left", padx=6)
        search_url_label = ttk.Label(controls, text="自定义 Skill 索引地址（可选）")
        search_url_label.pack(side="left", padx=(8, 4))
        search_url = ttk.Entry(controls, textvariable=self.skill_search_url_var, width=34)
        search_url.pack(side="left", padx=(0, 6))
        select_button = ttk.Button(controls, text="选用所选", command=lambda: self._select_skill_browser_rows("skill"))
        select_button.pack(side="left", padx=6)
        analyze_button = ttk.Button(controls, text="AI分析候选", command=self.analyze_skill_candidates)
        cancel_button = ttk.Button(controls, text="取消选用", command=self.cancel_selected_skills)
        cancel_button.pack(side="left")
        cancel_request_button = ttk.Button(
            controls, text="取消本次 AI 请求", command=self.cancel_delivery_request, state="disabled"
        )
        skip_button = ttk.Button(controls, text="跳过 Skill", command=self.skip_skills)
        skip_button.pack(side="left", padx=6)
        integrate_button = ttk.Button(controls, text="AI整合所选 Skill", command=self.integrate_selected_skills)
        feedback = ttk.Frame(page)
        feedback.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        feedback.columnconfigure(0, weight=1)
        ttk.Label(feedback, textvariable=self.skill_status_var, style="Muted.TLabel", wraplength=1000).grid(
            row=0, column=0, sticky="ew"
        )
        direct_button = ttk.Button(feedback, text="用已选 Skill 直接生成提示词", command=self.generate_no_skill_final, state="disabled")
        direct_button.grid(row=1, column=0, sticky="w", pady=(5, 0))

        candidate_frame = ttk.Frame(page)
        candidate_frame.grid(row=4, column=0, sticky="nsew")
        candidate_frame.columnconfigure(0, weight=1)
        candidates = self._build_skill_browser(candidate_frame, "skill")
        selected_frame = ttk.Frame(page)
        selected_frame.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        selected_frame.columnconfigure(0, weight=1)
        ttk.Label(selected_frame, text="已选 Skill", style="Section.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 5)
        )
        selected = self._tree(selected_frame, ("skill", "work", "mode", "status"), (220, 180, 160, 120), height=3)
        selected._promptsmith_container.grid(row=1, column=0, sticky="ew")
        detail = tk.Text(page, height=7, wrap="word", state="disabled", background="#f4f5f7", font=ui_font(self.root))
        detail.grid(row=6, column=0, sticky="ew", pady=(8, 0))
        prerequisite_frame = ttk.LabelFrame(page, text="适配前提核对", padding=8)
        prerequisite_frame.grid(row=7, column=0, sticky="ew", pady=(8, 0))
        prerequisite_frame.columnconfigure(0, weight=1)
        prerequisites = self._tree(
            prerequisite_frame, ("prerequisite", "status", "source"), (440, 130, 150), height=3
        )
        prerequisites._promptsmith_container.grid(row=0, column=0, sticky="ew")
        prerequisite_controls = ttk.Frame(prerequisite_frame)
        prerequisite_controls.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        ttk.Label(prerequisite_controls, text="核对结果").pack(side="left")
        prerequisite_status = ttk.Combobox(
            prerequisite_controls,
            textvariable=self.skill_prerequisite_status_var,
            state="readonly",
            values=("已满足", "仍未知", "不兼容"),
            width=12,
        )
        prerequisite_status.pack(side="left", padx=6)
        update_prerequisite_button = ttk.Button(
            prerequisite_controls, text="保存前提判断", command=self.update_selected_skill_prerequisite
        )
        update_prerequisite_button.pack(side="left")
        selected.bind("<<TreeviewSelect>>", lambda _event: self._show_selected_skill_binding())
        prerequisites.bind("<<TreeviewSelect>>", lambda _event: self._show_selected_skill_prerequisite())
        self.widgets.update({
            "skill_candidates_tree": candidates,
            "skill_selected_tree": selected,
            "skill_details_text": detail,
            "skill_find_button": find_button,
            "skill_online_button": online_button,
            "skill_search_url_label": search_url_label,
            "skill_search_url_entry": search_url,
            "skill_select_button": select_button,
            "skill_analyze_button": analyze_button,
            "skill_cancel_button": cancel_button,
            "skill_cancel_request_button": cancel_request_button,
            "skill_skip_button": skip_button,
            "skill_integrate_button": integrate_button,
            "skill_direct_button": direct_button,
            "skill_prerequisites_tree": prerequisites,
            "skill_prerequisite_status_combo": prerequisite_status,
            "skill_update_prerequisite_button": update_prerequisite_button,
        })
        self._bind_context_menu(detail)

    def _legacy_build_export_page(self, page: ttk.Frame) -> None:
        page.columnconfigure(0, weight=1)
        page.rowconfigure(3, weight=2)
        page.rowconfigure(5, weight=1)
        page.rowconfigure(6, weight=1)
        page.rowconfigure(7, weight=1)
        ttk.Label(page, text="最终方案与任务提示", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(page, textvariable=self.final_status_var, style="Section.TLabel", wraplength=1000).grid(
            row=1, column=0, sticky="ew", pady=(5, 8)
        )
        controls = ttk.Frame(page)
        controls.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(controls, text="生成无 Skill 草稿", command=self.generate_no_skill_final).pack(side="left")
        ttk.Button(controls, text="确认当前最终结果", command=self.confirm_final_result).pack(side="left", padx=6)
        ttk.Label(controls, text="语气").pack(side="left", padx=(16, 4))
        tone = ttk.Combobox(controls, textvariable=self.final_tone_var, state="readonly", values=("中性", "适度礼貌"), width=10)
        tone.pack(side="left")
        tone.bind("<<ComboboxSelected>>", lambda _event: self.change_final_tone())
        copy_draft_button = ttk.Button(controls, text="复制草稿提示", command=self.copy_draft_prompt)
        copy_draft_button.pack(side="right")
        copy_final_button = ttk.Button(controls, text="复制正式提示", command=self.copy_final_prompt)
        copy_final_button.pack(side="right", padx=6)
        ttk.Button(controls, text="导出 Markdown", command=self.export_final_markdown).pack(side="right", padx=6)
        ttk.Button(controls, text="导出草稿", command=self.export_draft_markdown).pack(side="right")
        preview = tk.Text(page, wrap="word", state="disabled", font=ui_font(self.root))
        preview.grid(row=3, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(page, orient="vertical", command=preview.yview)
        scroll.grid(row=3, column=1, sticky="ns")
        preview.configure(yscrollcommand=scroll.set)

        ttk.Label(page, text="最终任务提示预览", style="Section.TLabel").grid(
            row=4, column=0, sticky="w", pady=(8, 4)
        )
        task_prompt = tk.Text(page, height=6, wrap="word", state="disabled", font=ui_font(self.root))
        task_prompt.grid(row=5, column=0, sticky="nsew")
        task_prompt_scroll = ttk.Scrollbar(page, orient="vertical", command=task_prompt.yview)
        task_prompt_scroll.grid(row=5, column=1, sticky="ns")
        task_prompt.configure(yscrollcommand=task_prompt_scroll.set)

        suggestions_frame = ttk.LabelFrame(page, text="M2 建议", padding=8)
        suggestions_frame.grid(row=7, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        suggestions_frame.columnconfigure(0, weight=1)
        suggestions_frame.rowconfigure(0, weight=1)
        suggestions = self._tree(suggestions_frame, ("text", "kind", "status"), (440, 160, 100), height=4)
        suggestions._promptsmith_container.grid(row=0, column=0, sticky="nsew")
        suggestion_details = tk.Text(
            suggestions_frame, height=3, wrap="word", state="disabled", background="#f4f5f7", font=ui_font(self.root)
        )
        suggestion_details.grid(row=1, column=0, sticky="ew", pady=(4, 4))
        suggestion_buttons = ttk.Frame(suggestions_frame)
        suggestion_buttons.grid(row=2, column=0, sticky="ew")
        accept_suggestion_button = ttk.Button(
            suggestion_buttons, text="接受选中建议", command=self.accept_selected_m2_suggestion
        )
        accept_suggestion_button.pack(side="left")
        reject_suggestion_button = ttk.Button(
            suggestion_buttons, text="拒绝选中建议", command=self.reject_selected_m2_suggestion
        )
        reject_suggestion_button.pack(side="left", padx=6)
        process_suggestion_button = ttk.Button(
            suggestion_buttons, text="返回方案处理", command=self.process_selected_m2_suggestion
        )
        process_suggestion_button.pack(side="left")
        suggestions.bind("<<TreeviewSelect>>", lambda _event: self._show_selected_m2_suggestion())

        m4_frame = ttk.LabelFrame(page, text="Skill 后置建议（可选）", padding=8)
        m4_frame.grid(row=8, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        m4_frame.columnconfigure(0, weight=1)
        m4_frame.rowconfigure(0, weight=1)
        m4_changes = self._tree(m4_frame, ("text", "kind", "status"), (440, 150, 100), height=3)
        m4_changes._promptsmith_container.grid(row=0, column=0, sticky="nsew")
        m4_details = tk.Text(
            m4_frame, height=3, wrap="word", state="disabled", background="#f4f5f7", font=ui_font(self.root)
        )
        m4_details.grid(row=1, column=0, sticky="ew", pady=(4, 4))
        m4_buttons = ttk.Frame(m4_frame)
        m4_buttons.grid(row=2, column=0, sticky="ew")
        accept_m4_button = ttk.Button(
            m4_buttons, text="接受选中变化", command=self.accept_selected_m4_change
        )
        accept_m4_button.pack(side="left")
        reject_m4_button = ttk.Button(
            m4_buttons, text="拒绝选中变化", command=self.reject_selected_m4_change
        )
        reject_m4_button.pack(side="left", padx=6)
        m4_changes.bind("<<TreeviewSelect>>", lambda _event: self._show_selected_m4_change())

        review_frame = ttk.LabelFrame(page, text="需先处理的上游事项", padding=8)
        review_frame.grid(row=9, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        review_frame.columnconfigure(0, weight=1)
        review_frame.rowconfigure(0, weight=1)
        review_items = self._tree(review_frame, ("kind", "text", "status"), (150, 440, 100), height=4)
        review_items._promptsmith_container.grid(row=0, column=0, sticky="nsew")
        review_details = tk.Text(
            review_frame, height=3, wrap="word", state="disabled", background="#f4f5f7", font=ui_font(self.root)
        )
        review_details.grid(row=1, column=0, sticky="ew", pady=(4, 4))
        process_review_button = ttk.Button(
            review_frame, text="处理选中项", command=self.process_selected_final_review_item
        )
        process_review_button.grid(row=2, column=0, sticky="w")
        review_items.bind("<<TreeviewSelect>>", lambda _event: self._show_selected_final_review_item())

        notes = ttk.Frame(page)
        notes.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(notes, text="添加用户附注", command=self.add_final_note).pack(side="left")
        ttk.Label(notes, text="正文由结构化方案统一渲染；原需求和步骤变化请返回上游修改。", style="Muted.TLabel").pack(side="left", padx=10)
        self.widgets.update({
            "final_preview_text": preview,
            "final_task_prompt_text": task_prompt,
            "final_tone_combo": tone,
            "copy_final_button": copy_final_button,
            "copy_draft_button": copy_draft_button,
            "m2_suggestions_tree": suggestions,
            "m2_suggestion_details_text": suggestion_details,
            "accept_m2_suggestion_button": accept_suggestion_button,
            "reject_m2_suggestion_button": reject_suggestion_button,
            "process_m2_suggestion_button": process_suggestion_button,
            "m4_changes_tree": m4_changes,
            "m4_change_details_text": m4_details,
            "accept_m4_change_button": accept_m4_button,
            "reject_m4_change_button": reject_m4_button,
            "final_review_items_tree": review_items,
            "final_review_details_text": review_details,
            "process_final_review_item_button": process_review_button,
        })
        for widget in (preview, task_prompt, suggestion_details, m4_details, review_details):
            self._bind_context_menu(widget)

    def _tree(self, parent: tk.Misc, columns: tuple[str, ...], widths: tuple[int, ...], *, height: int) -> ttk.Treeview:
        container = ttk.Frame(parent)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)
        tree = ttk.Treeview(container, columns=columns, show="headings", height=height, selectmode="extended")
        labels = {
            "field": "字段",
            "text": "内容",
            "status": "状态",
            "operation": "动作",
            "order": "顺序",
            "title": "标题",
            "purpose": "目的",
            "work": "关键工作",
            "skill": "Agent Skill",
            "capability": "能力",
            "compatibility": "适配状态",
            "mode": "Skill 参考方式",
            "kind": "类型",
            "prerequisite": "适配前提",
            "source": "来源",
        }
        for column, width in zip(columns, widths):
            tree.heading(column, text=labels.get(column, column))
            tree.column(column, width=width, minwidth=60, stretch=column == "text")
        vertical = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        horizontal = ttk.Scrollbar(container, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        tree._promptsmith_container = container
        tree.bind("<Button-3>", lambda event, target=tree: self._show_tree_context_menu(event, target), add="+")
        tree.bind("<Control-c>", lambda _event, target=tree: self._copy_tree_selection(target), add="+")
        tree.bind("<Control-a>", lambda _event, target=tree: self._select_tree_all(target), add="+")
        return tree

    def _api_config(self, *, timeout_seconds: float | None = None) -> ApiConfig:
        if not self._model_settings_confirmed():
            raise ValueError("请在设置页面点击“确认”，确认当前模型设置后再继续。")
        return self._draft_api_config(timeout_seconds=timeout_seconds)

    def _draft_api_config(self, *, timeout_seconds: float | None = None) -> ApiConfig:
        values = self._model_preference_values()
        return ApiConfig(
            base_url=self.api_base_var.get().strip(),
            model=self.api_model_var.get().strip(),
            api_key=self.api_key_var.get(),
            timeout_seconds=values["generation_timeout"] if timeout_seconds is None else timeout_seconds,
            provider=self.provider_var.get().strip(),
            protocol=PROTOCOL_LABELS[self.protocol_var.get()],
            max_tokens=values["max_tokens"] or None,
            temperature="auto" if values["temperature"] == "auto" else float(values["temperature"]) if values["temperature"] else None,
            top_p=float(values["top_p"]) if values["top_p"] else None,
            reasoning_effort=values["reasoning_effort"],
        )

    def _model_settings_confirmed(self) -> bool:
        return self._confirmed_connection_state == self._generation_snapshot()

    def _refresh_model_confirmation(self) -> None:
        confirmed = self._model_settings_confirmed()
        self.model_confirmation_var.set(
            "模型设置已确认，可以返回工作区继续。"
            if confirmed else "模型设置待确认。测试连接只检查接口；点击“确认”后用于任务。"
        )
        self.widgets["confirm_model_settings_button"].configure(
            state="disabled" if confirmed or self.busy else "normal"
        )

    def confirm_model_settings(self) -> None:
        if self.busy:
            return
        try:
            self._draft_api_config()
        except ValueError as exc:
            self.status_var.set(f"模型设置未确认：{exc}")
            self._show_error("无法确认模型设置", str(exc), parent=self.root)
            return
        if not self.save_settings(model_only=True, confirm_model=True):
            return
        self._confirmed_connection_state = self._generation_snapshot()
        self._refresh_model_confirmation()
        self.status_var.set("模型设置已确认并保存；下次启动自动恢复，可以返回工作区继续。")
        logging.getLogger(__name__).info("Model settings explicitly confirmed and persisted")
        self._refresh_primary_action()

    def _client(self, config: ApiConfig):
        return client_for_config(config)

    def _connection_snapshot(self) -> tuple[str, str, str, str]:
        return (
            self.provider_var.get().strip(),
            PROTOCOL_LABELS[self.protocol_var.get()],
            self.api_base_var.get().strip(),
            self.api_key_var.get(),
        )

    def _generation_snapshot(self) -> tuple[Any, ...]:
        parameters = tuple(self.preference_vars[key].get() for key, spec in FIELDS.items() if spec.category == "模型")
        return (*self._connection_snapshot(), self.api_model_var.get().strip(), *parameters)

    def _model_directory_snapshot(self) -> tuple[str, str, str, str]:
        return self._connection_snapshot()

    def _on_provider_changed(self, *_args: Any) -> None:
        if self._suppress_provider_callback:
            return
        provider = self.provider_var.get().strip()
        if provider == self._last_provider:
            return
        self._last_provider = provider
        self._suppress_provider_callback = True
        try:
            self.api_key_var.set("")
            if "api_model_combo" in self.widgets:
                self.widgets["api_model_combo"].configure(values=())
            preset = PROVIDER_PRESETS.get(provider)
            if preset:
                self.api_base_var.set(preset["base_url"])
                self.protocol_var.set(PROTOCOL_NAMES[preset["protocol"]])
                self.api_model_var.set(preset["model"])
        finally:
            self._suppress_provider_callback = False

    def _on_connection_changed(self, *_args: Any) -> None:
        current = self._generation_snapshot()
        directory_current = self._model_directory_snapshot()
        if self._connection_state is None or self._model_directory_state is None:
            self._connection_state = current
            self._model_directory_state = directory_current
            return
        if current != self._connection_state:
            if self._confirmed_connection_state is not None:
                logging.getLogger(__name__).info("Model confirmation invalidated: model settings edited; reconfirmation required")
            self.connection_version += 1
            self._connection_state = current
            self._confirmed_connection_state = None
        previous_directory = self._model_directory_state
        if directory_current != previous_directory:
            self.model_directory_version += 1
            self._model_directory_state = directory_current
            if "api_model_combo" in self.widgets:
                self.widgets["api_model_combo"].configure(values=())
            service_changed = previous_directory[0] != directory_current[0]
            host_changed = previous_directory[2] != directory_current[2]
            if (service_changed or host_changed) and self.api_key_var.get():
                self.api_key_var.set("")
        self._refresh_model_confirmation()
        self._refresh_primary_action()

    def _model_directory_config(self) -> ApiConfig:
        return ApiConfig(
            base_url=self.api_base_var.get().strip(),
            model=self.api_model_var.get().strip() or "directory-only",
            api_key=self.api_key_var.get(),
            timeout_seconds=self._model_preference_values()["connection_timeout"],
            provider=self.provider_var.get().strip(),
            protocol=PROTOCOL_LABELS[self.protocol_var.get()],
        )

    def _set_busy(self, busy: bool, text: str | None = None) -> None:
        self.busy = busy
        if not busy:
            self.busy_kind = None
        state = "disabled" if busy else "normal"
        self.widgets["analyze_button"].configure(state=state)
        self.widgets["test_connection_button"].configure(state=state)
        self.widgets["model_list_button"].configure(state=state)
        if "generate_plan_button" in self.widgets:
            self.widgets["generate_plan_button"].configure(state=state)
            self.widgets["confirm_plan_button"].configure(state=state)
        if text:
            self.status_var.set(text)
        self._refresh_model_confirmation()
        self._refresh_primary_action()

    def fetch_models(self) -> None:
        if self.busy:
            return
        try:
            config = self._model_directory_config()
        except ValueError as exc:
            self._show_error("配置不完整", str(exc), parent=self.root)
            return
        snapshot = self._model_directory_snapshot()
        request_connection_version = self.model_directory_version
        self.busy_kind = "model_list"
        self._set_busy(True, "正在从当前供应商获取模型列表...")
        client = self._client(config)
        self._submit(
            client.list_models,
            lambda result: self._models_ok(snapshot, result, request_connection_version),
            lambda exc: self._models_failed(snapshot, exc, request_connection_version),
        )

    def _models_ok(
        self,
        snapshot: tuple[str, str, str, str],
        result: ModelListResult,
        request_connection_version: int | None = None,
    ) -> None:
        if (
            snapshot != self._connection_snapshot()
            or request_connection_version is not None
            and request_connection_version != self.model_directory_version
        ):
            self._set_busy(False, "连接配置已变化，已忽略旧模型列表；可重新获取。")
            return
        self.widgets["api_model_combo"].configure(values=tuple(result.model_ids))
        if result.model_ids:
            text = f"已获取 {len(result.model_ids)} 个模型 ID；当前手填值保持不变。"
        else:
            text = "供应商返回空模型列表；可继续手动填写模型 ID。"
        self._set_busy(False, text)

    def _models_failed(
        self,
        snapshot: tuple[str, str, str, str],
        exc: Exception,
        request_connection_version: int | None = None,
    ) -> None:
        if (
            snapshot != self._connection_snapshot()
            or request_connection_version is not None
            and request_connection_version != self.model_directory_version
        ):
            self._set_busy(False, "连接配置已变化，已忽略旧模型列表失败结果。")
            return
        self._set_busy(False, f"获取模型列表失败：{exc}")
        self._show_error("获取模型列表失败", f"{exc}\n仍可手动填写模型 ID。", parent=self.root)

    def _bind_context_menu(self, widget: tk.Misc) -> None:
        widget.bind("<Button-3>", lambda event, target=widget: self._show_context_menu(event, target), add="+")
        widget.bind("<Control-a>", lambda _event, target=widget: self._select_all(target), add="+")
        widget.bind("<Control-c>", lambda _event, target=widget: self._perform_context_action(target, "copy"), add="+")
        widget.bind("<Control-v>", lambda _event, target=widget: self._perform_context_action(target, "paste"), add="+")
        widget.bind("<Control-x>", lambda _event, target=widget: self._perform_context_action(target, "cut"), add="+")
        if isinstance(widget, tk.Text):
            widget.bind("<Control-z>", lambda _event, target=widget: self._perform_context_action(target, "undo"), add="+")

    @staticmethod
    def _perform_context_action(widget: tk.Misc, action: str) -> str:
        state = str(widget.cget("state")) if "state" in widget.keys() else "normal"
        editable = state not in {"disabled", "readonly"}
        if action == "select_all":
            PromptSmithApp._select_all(widget)
            return "break"
        if action == "undo":
            if editable and isinstance(widget, tk.Text):
                try:
                    widget.edit_undo()
                except tk.TclError:
                    pass
            return "break"
        if action == "copy" or action == "cut":
            try:
                if isinstance(widget, tk.Text):
                    if not widget.tag_ranges("sel"):
                        return "break"
                    selected = widget.get("sel.first", "sel.last")
                    if action == "cut" and editable:
                        widget.delete("sel.first", "sel.last")
                else:
                    if not widget.selection_present():
                        return "break"
                    selected = widget.selection_get()
                    if action == "cut" and editable:
                        widget.delete("sel.first", "sel.last")
                widget.clipboard_clear()
                widget.clipboard_append(selected)
            except tk.TclError:
                pass
            return "break"
        if action == "paste" and editable:
            try:
                pasted = widget.clipboard_get()
                if isinstance(widget, tk.Text):
                    if widget.tag_ranges("sel"):
                        widget.delete("sel.first", "sel.last")
                    widget.insert("insert", pasted)
                else:
                    if widget.selection_present():
                        widget.delete("sel.first", "sel.last")
                    widget.insert("insert", pasted)
            except tk.TclError:
                pass
            return "break"
        try:
            widget.event_generate(f"<<{action.title()}>>")
        except tk.TclError:
            pass
        return "break"

    def _context_menu_capabilities(self, widget: tk.Misc) -> dict[str, bool]:
        state = str(widget.cget("state")) if "state" in widget.keys() else "normal"
        editable = state not in {"disabled", "readonly"}
        is_text = isinstance(widget, tk.Text)
        return {
            "cut": editable,
            "copy": True,
            "paste": editable,
            "select_all": True,
            "undo": editable and is_text and bool(str(widget.cget("undo")) not in {"0", "false"}),
        }

    def _has_selection(self, widget: tk.Misc) -> bool:
        try:
            if isinstance(widget, tk.Text):
                return bool(widget.tag_ranges("sel"))
            return bool(widget.selection_present())
        except (tk.TclError, AttributeError):
            return False

    def _show_context_menu(self, event: tk.Event, widget: tk.Misc) -> tk.Menu:
        capabilities = self._context_menu_capabilities(widget)
        has_selection = self._has_selection(widget)
        menu = tk.Menu(self.root, tearoff=False, font=ui_font(self.root))

        def add(label: str, action: str, enabled: bool) -> None:
            menu.add_command(
                label=label,
                state="normal" if enabled else "disabled",
                command=lambda: self._perform_context_action(
                    widget,
                    {"<<Undo>>": "undo", "<<Cut>>": "cut", "<<Copy>>": "copy", "<<Paste>>": "paste"}[action],
                ),
            )

        add("撤销", "<<Undo>>", capabilities["undo"])
        menu.add_separator()
        add("剪切", "<<Cut>>", capabilities["cut"] and has_selection)
        add("复制", "<<Copy>>", capabilities["copy"] and has_selection)
        add("粘贴", "<<Paste>>", capabilities["paste"])
        menu.add_separator()
        menu.add_command(
            label="全选",
            state="normal" if capabilities["select_all"] else "disabled",
            command=lambda: self._select_all(widget),
        )
        menu.tk_popup(event.x_root, event.y_root)
        return menu

    def _copy_tree_selection(self, tree: ttk.Treeview) -> str:
        rows = [self._tree_item_copy_text(tree, item_id) for item_id in tree.selection()]
        rows = [row for row in rows if row]
        if not rows:
            return "break"
        try:
            tree.clipboard_clear()
            tree.clipboard_append("\n".join(rows))
        except tk.TclError:
            pass
        return "break"

    def _tree_item_copy_text(self, tree: ttk.Treeview, item_id: str) -> str:
        content = self.session.plan.get("content") or {}
        if tree is self.widgets.get("requirements_tree"):
            row = next((item for item in self.session.requirements if item["item_id"] == item_id), None)
            if row:
                return f"{row['field']}\n{row['text']}\n{row.get('scope', '')}"
        elif tree is self.widgets.get("proposals_tree"):
            row = next((item for item in self.session.pending_proposals if item["proposal_id"] == item_id), None)
            if row:
                return f"{row['operation']}\n{row['field']}\n{row['text']}\n{row.get('scope', '')}\n{row.get('reason', '')}"
        elif tree is self.widgets.get("questions_tree"):
            row = next((item for item in self.session.questions_for_review() if item["question_id"] == item_id), None)
            if row:
                return f"{row['text']}\n适用范围：{row.get('scope', '')}\n可选回答：{'、'.join(row.get('options', []))}"
        elif tree is self.widgets.get("plan_steps_tree"):
            row = next((item for item in content.get("steps", []) if item["step_id"] == item_id), None)
            if row:
                return (
                    f"步骤 {row['order']} · {row['title']}\n目的：{row['purpose']}\n"
                    f"输入：{'；'.join(row.get('inputs', []))}\n行动：{'；'.join(row.get('actions', []))}\n"
                    f"输出：{'；'.join(row.get('outputs', []))}\n完成标准：{'；'.join(row.get('completion_criteria', []))}\n"
                    f"依赖：{'；'.join(row.get('depends_on_step_ids', []))}\n关联需求：{'；'.join(row.get('requirement_ids', []))}"
                )
        elif tree is self.widgets.get("plan_key_work_tree"):
            row = next((item for item in content.get("key_work", []) if item["key_work_id"] == item_id), None)
            if row:
                return (
                    f"{row['title']}\n目标：{row['goal']}\n输入：{'；'.join(row.get('inputs', []))}\n"
                    f"输出：{'；'.join(row.get('outputs', []))}\n检查点：{'；'.join(row.get('checkpoints', []))}\n"
                    f"关联步骤：{'；'.join(row.get('step_ids', []))}\n关联需求：{'；'.join(row.get('requirement_ids', []))}"
                )
        values = tree.item(item_id, "values")
        return "\t".join(str(value) for value in values) if values else ""

    @staticmethod
    def _select_tree_all(tree: ttk.Treeview) -> str:
        tree.selection_set(tree.get_children())
        return "break"

    def _show_tree_context_menu(self, event: tk.Event, tree: ttk.Treeview) -> tk.Menu:
        row_id = tree.identify_row(event.y)
        if row_id and row_id not in tree.selection():
            tree.selection_set(row_id)
        menu = tk.Menu(self.root, tearoff=False, font=ui_font(self.root))
        selected = bool(tree.selection())
        menu.add_command(
            label="\u590d\u5236\u9009\u4e2d\u5185\u5bb9",
            state="normal" if selected else "disabled",
            command=lambda: self._copy_tree_selection(tree),
        )
        menu.tk_popup(event.x_root, event.y_root)
        return menu

    @staticmethod
    def _select_all(widget: tk.Misc) -> None:
        try:
            if isinstance(widget, tk.Text):
                widget.tag_add("sel", "1.0", "end-1c")
                widget.mark_set("insert", "1.0")
            else:
                widget.selection_range(0, "end")
                widget.icursor("end")
        except tk.TclError:
            return

    def _missing_generation_config(self) -> list[str]:
        missing = []
        if not self.api_base_var.get().strip():
            missing.append("接口地址")
        if not self.api_model_var.get().strip():
            missing.append("模型 ID")
        if not self.api_key_var.get().strip():
            missing.append("API Key")
        if not missing and not self._model_settings_confirmed():
            missing.append("确认模型设置")
        return missing

    def _delivery_primary_action(self) -> PrimaryAction:
        """Choose the next delivery page without starting a model request.

        The primary action is deliberately derived from persisted state.  It is
        navigation only once the initial plan is confirmed; generation and
        integration remain explicit buttons on their respective pages.
        """
        plan_status = self.session.plan.get("status")
        skill_state = self.session.skill_state
        skill_status = skill_state.get("status", "not_started")
        final_status = self.session.final_result.get("status", "not_started")

        # An upstream plan change must be repaired before using any delivery
        # snapshot that was built from the old plan.
        if plan_status == "stale":
            return PrimaryAction(
                "view_plan",
                "修复并重新生成方案",
                "当前方案来源已变化，请回到初始方案页处理失效内容。",
            )

        # A stale final result can be caused by a changed binding or an
        # incomplete M4 decision.  Keep the user at the actionable delivery
        # page; the controls there explain the specific repair.
        if final_status == "stale":
            if skill_status in {"selected", "candidates_ready", "no_match"}:
                return PrimaryAction(
                    "focus_skills",
                    "处理 Skill 变化",
                    "当前最终结果已过期，请在 Skill 页重新整合、取消绑定或跳过 Skill。",
                )
            return PrimaryAction(
                "focus_final",
                "复核失效结果",
                "当前最终结果已过期，请查看失效原因后重新生成或回到上游修复。",
            )

        if final_status == "draft":
            return PrimaryAction(
                "focus_final",
                "复核最终结果",
                "最终草稿已经生成，请复核正文；后置建议已写入提示词，可直接确认。",
            )
        if final_status == "confirmed":
            return PrimaryAction(
                "focus_final",
                "继续最终交付",
                "最终结果已确认，可复制或导出。",
            )

        # No final result yet: Skill is an optional post-plan decision.  The
        # page offers both directory lookup and an explicit skip path.
        if skill_status in {"not_started", "stale", "candidates_ready", "no_match", "selected"}:
            if skill_status == "selected":
                return PrimaryAction(
                    "focus_skills",
                    "整合所选 Agent Skill",
                    "所选 Agent Skill 尚未整合；可继续整合，也可以取消选用后跳过。",
                )
            if skill_status in {"candidates_ready", "no_match"}:
                return PrimaryAction(
                    "focus_skills",
                    "选择或跳过 Skill",
                    "请核对本地目录候选，或直接跳过并生成无 Skill 最终草稿。",
                )
            return PrimaryAction(
                "focus_skills",
                "决定是否使用 Skill",
                "初始方案已确认。可查找已核验目录，也可以直接跳过并生成最终草稿。",
            )

        if skill_status == "skipped":
            return PrimaryAction(
                "focus_skills",
                "生成无 Skill 草稿",
                "当前选择是不使用 Skill，请在 Skill 页生成无 Skill 最终草稿。",
            )

        return PrimaryAction(
            "focus_skills",
            "继续交付流程",
            "请在 Skill 页确认要选用的 Agent Skill，或跳过后生成最终草稿。",
        )

    def _visible_task_text(self) -> str:
        return self.widgets["task_text"].get("1.0", "end-1c").strip()

    def _on_task_text_modified(self, _event: tk.Event | None = None) -> None:
        widget = self.widgets["task_text"]
        if not widget.edit_modified():
            return
        widget.edit_modified(False)
        # Typing, paste, cut and undo only refresh the label. Commit task
        # changes through _sync_input when the user performs an action.
        self._refresh_primary_action()

    def _legacy_primary_action(self) -> PrimaryAction:
        if self.busy:
            return PrimaryAction("busy", "处理中…", "当前请求尚未结束。", False)
        if not self._visible_task_text():
            return PrimaryAction("focus_task", "先输入任务", "请先输入要完成的任务，例如交付物、对象和背景。")
        if self.session.open_conflicts:
            conflict = self.session.open_conflicts[0]
            return PrimaryAction(
                "focus_conflict",
                "处理冲突",
                f"先处理冲突：{conflict.get('description', conflict.get('conflict_id', '未命名冲突'))}",
            )
        if self.session.questions_for_review():
            question = self.session.questions_for_review()[0]
            return PrimaryAction(
                "focus_question",
                "回答问题",
                f"当前问题：{question.get('text', '')} 可回答、跳过或标记不确定。",
            )
        if self.session.pending_proposals:
            return PrimaryAction(
                "focus_proposal", "核对候选", "先核对模型候选；未处理内容会继续作为草稿保留。"
            )
        if self.session.pending_review_item_ids:
            return PrimaryAction("focus_review", "复核需求", "先复核受修改影响的需求，再继续确认。")
        if self.workflow.m1_retry_recommended():
            missing = self._missing_generation_config()
            if missing:
                return PrimaryAction(
                    "focus_connection", "补全模型连接", f"回答已保留；重试前请补全：{'、'.join(missing)}。"
                )
            return PrimaryAction(
                "retry_compact", "重新分析",
                "已有回答已保留。重新分析会让 AI 继续判断刚才的回答和未解决的问题。",
            )
        if any(row.get("assessment_status") == "pending" for row in self.session.question_history):
            missing = self._missing_generation_config()
            if missing:
                return PrimaryAction(
                    "focus_connection",
                    "补全模型连接",
                    f"回答已保存；继续分析前请补全：{'、'.join(missing)}。",
                )
            return PrimaryAction(
                "analyze_answer", "继续分析回答", "把刚才的回答交给 AI 判断，必要时继续追问。"
            )
        if self.session.confirmed_requirements_version == self.session.requirement_version:
            plan_status = self.session.plan.get("status")
            if plan_status == "draft":
                return PrimaryAction("view_plan", "复核初始方案", "查看方案、步骤和关键工作并完成复核。")
            if plan_status == "confirmed":
                return self._delivery_primary_action()
            if plan_status == "stale":
                return PrimaryAction(
                    "view_plan",
                    "修复并重新生成方案",
                    "当前方案来源已变化，请回到初始方案页处理失效内容。",
                )
            label = "生成初始方案"
            missing = self._missing_generation_config()
            if missing:
                return PrimaryAction(
                    "focus_connection", "补全模型连接", f"生成方案前请补全：{'、'.join(missing)}。"
                )
            return PrimaryAction("generate_plan", label, "依据当前已确认需求生成完整初始方案草稿。")
        if self.session.requirements and self.session.analysis_basis_version == self.session.requirement_version:
            return PrimaryAction("confirm_requirements", "确认当前需求", "核对当前有效需求后再明确确认。")
        missing = self._missing_generation_config()
        if missing:
            return PrimaryAction(
                "focus_connection", "补全模型连接", f"开始分析前请补全：{'、'.join(missing)}。"
            )
        return PrimaryAction("analyze", "分析当前任务", "提取需求并提出少量必要问题。")

    def _primary_action_text(self) -> str:
        return self._primary_action().label

    def _legacy_refresh_primary_action(self) -> None:
        action = self._primary_action()
        self.primary_action_var.set(action.label)
        if "analyze_button" in self.widgets:
            self.widgets["analyze_button"].configure(state="normal" if action.enabled else "disabled")

    def _legacy_run_primary_action(self) -> None:
        if self.busy:
            return
        if self._visible_task_text():
            version_before = self.session.requirement_version
            try:
                self._sync_input()
            except (ValueError, SessionStateError) as exc:
                self._show_error("无法同步任务", str(exc), parent=self.root)
                return
            if self.session.requirement_version != version_before:
                self.refresh()
        # Empty input remains an editable UI draft, never set_task("").
        # Re-evaluate after synchronization because it may invalidate old work.
        action = self._primary_action()
        self._refresh_primary_action()
        if not action.enabled:
            return
        if action.kind == "focus_conflict":
            self.widgets["details_text"].focus_set()
        elif action.kind == "focus_question":
            question_id = self.session.questions_for_review()[0]["question_id"]
            self.widgets["questions_tree"].selection_set(question_id)
            self.widgets["questions_tree"].see(question_id)
            self._show_selected_details("question")
            self.widgets["answer_entry"].focus_set()
        elif action.kind == "focus_proposal":
            self.widgets["proposals_tree"].focus_set()
        elif action.kind == "focus_review":
            self.widgets["requirements_tree"].focus_set()
        elif action.kind == "focus_task":
            self.widgets["task_text"].focus_set()
        elif action.kind == "focus_connection":
            for name in ("api_base_entry", "api_model_entry", "api_key_entry"):
                widget = self.widgets[name]
                if not str(widget.get()).strip():
                    widget.focus_set()
                    break
        elif action.kind == "focus_skills":
            self.notebook.select(2)
            # Put focus on the first actionable control without triggering it.
            for name in (
                "skill_integrate_button",
                "skill_skip_button",
                "skill_find_button",
                "skill_candidates_tree",
            ):
                widget = self.widgets.get(name)
                if widget is not None and str(widget.cget("state")) != "disabled":
                    widget.focus_set()
                    break
        elif action.kind == "focus_final":
            self.notebook.select(3)
            review_tree = self.widgets.get("final_review_items_tree")
            if review_tree is not None:
                rows = review_tree.get_children()
                if rows:
                    review_tree.selection_set(rows[0])
                    review_tree.see(rows[0])
                    self._show_selected_final_review_item()
                    button = self.widgets.get("process_final_review_item_button")
                    if button is not None and str(button.cget("state")) != "disabled":
                        button.focus_set()
                        return
            for name in (
                "confirm_final_button",
                "copy_final_button",
                "export_final_button",
                "final_preview_text",
            ):
                widget = self.widgets.get(name)
                if widget is not None and str(widget.cget("state")) != "disabled":
                    widget.focus_set()
                    break
        elif action.kind == "view_plan":
            self.notebook.select(1)
        elif action.kind == "generate_plan":
            self.start_plan_generation()
        elif action.kind == "confirm_requirements":
            self.confirm_requirements()
        elif action.kind in {"analyze", "analyze_answer"}:
            self.start_analysis()
        elif action.kind == "retry_compact":
            self.start_analysis(compact_retry=True)

    def _submit(self, operation: Callable[[], Any], success: Callable[[Any], None],
                error: Callable[[Exception], None], *, session_scoped: bool = True) -> None:
        label = getattr(operation, "__qualname__", type(operation).__name__)
        task_id = self.session.task_id
        scope = self._session_tasks if session_scoped else self._application_tasks
        session_token = self._session_instance_token
        operation_id = uuid4().hex
        if session_scoped:
            self._active_stop_token = operation_id
        stream_ready = Event()
        stream_seen = False
        delivery_owner = self._active_delivery_request
        capture = session_scoped and getattr(operation, "__name__", "") not in {"test_connection", "list_models"}
        history_count = len(self.session.question_history)
        activities = [["当前目标", self.session.task_text[:45]]]
        if self.session.confirmed_requirements_version == self.session.requirement_version and self.session.requirements:
            activities.append(["读取已确认要求", f"{len(self.session.requirements)} 项"])
        if self.session.question_history:
            activities.append(["汇总用户回答", f"{len(self.session.question_history)} 条"])
        if self.session.plan.get("content"):
            activities.append(["参考当前方案", f"{len(self.session.plan['content'].get('steps', []))} 个步骤"])
        if self.session.skill_state.get("bindings"):
            activities.append(["已选 Skill", f"{len(self.session.skill_state['bindings'])} 项"])
        def capture_event(event):
            nonlocal stream_seen
            stream_seen = True
            self._response_events.put((scope, session_token, delivery_owner,
                {**event, "operation": operation_id, "activities": activities, "history_count": history_count,
                 "delivery_request_id": delivery_owner.get("request_id") if delivery_owner is not None else None}))

        def logged_operation():
            started = time.perf_counter()
            logger = logging.getLogger("promptsmith.worker")
            logger.debug("Background operation started: %s; task=%s", label, task_id)
            try:
                with scope.activate(), observe_stream(capture_event if capture else None):
                    result = operation()
                    scope.check()
            except CancelledError:
                logger.info("Background operation cancelled: %s; task=%s; elapsed=%.3fs",
                            label, task_id, time.perf_counter() - started)
                raise
            except Exception as exc:
                if capture:
                    capture_event({"event": "operation_failed", "text": str(exc)})
                logger.exception("Background operation failed: %s; task=%s; elapsed=%.3fs",
                                 label, task_id, time.perf_counter() - started)
                raise
            logger.debug("Background operation completed: %s; task=%s; elapsed=%.3fs",
                         label, task_id, time.perf_counter() - started)
            return result
        future = self.executor.submit(logged_operation)
        with self._background_lock:
            self._background_futures[future] = scope

        def deliver(callback, value):
            # Check on the Tk thread too: the result can already be queued when
            # the user creates/opens another conversation.
            if self._shutdown or scope.cancelled or (delivery_owner is not None and delivery_owner.get("_stream_cancelled")):
                logging.getLogger("promptsmith.worker").debug(
                    "Discarded completion from cancelled scope: %s; task=%s", label, task_id)
                return
            if not stream_ready.is_set():
                self._response_deliveries[operation_id] = (stream_ready, lambda item: deliver(callback, item), value)
                logging.getLogger("promptsmith.worker").debug("Completion waits for stream metadata: operation=%s task=%s", operation_id, task_id)
                return
            callback(value)

        def done(completed: Future) -> None:
            if stream_seen:
                capture_event({"event": "completion_fence", "ready": stream_ready})
            else:
                stream_ready.set()
            try:
                value = completed.result()
            except CancelledError:
                logging.getLogger("promptsmith.worker").debug(
                    "Cancelled background task has no UI completion: %s; task=%s", label, task_id)
            except Exception as exc:
                self.completions.put((lambda value: deliver(error, value), exc))
            else:
                self.completions.put((lambda value: deliver(success, value), value))
            finally:
                with self._background_lock:
                    self._background_futures.pop(completed, None)

        future.add_done_callback(done)

    def _cancel_session_tasks(self, reason: str, *, reset_skill_view: bool = True) -> None:
        scope = self._session_tasks
        scope.cancel()
        with self._background_lock:
            futures = [future for future, owner in self._background_futures.items() if owner is scope]
        cancelled = sum(future.cancel() for future in futures)
        if any(not future.done() for future in futures):
            # Retire any still-unwinding transport or custom client so new work
            # can start immediately in its own executor.
            previous_executor = self.executor
            self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="promptsmith")
            previous_executor.shutdown(wait=False)
            self._retired_executors.append(previous_executor)
        self._session_tasks = TaskScope()
        self._active_stop_token = uuid4().hex
        if reset_skill_view:
            self.skill_source_filter_var.set("全部来源")
            self.show_all_skills_var.set(False)
            self._skill_browser_lookup = {}
        logging.getLogger("promptsmith.worker").info(
            "Conversation background tasks invalidated; reason=%s task=%s active=%d queued_cancelled=%d",
            reason, self.session.task_id, len(futures), cancelled)

    def _phase_request_is_current(self, payload: dict[str, Any], session_token: str | None) -> bool:
        current = (not self._shutdown and payload.get("task_id") == self.session.task_id
                   and (session_token is None or session_token == self._session_instance_token))
        if not current:
            logging.getLogger("promptsmith.worker").debug(
                "Ignored old model callback; request=%s task=%s", payload.get("request_id"), payload.get("task_id"))
        return current

    def _poll_completions(self) -> None:
        while True:
            try:
                callback, value = self.completions.get_nowait()
            except queue.Empty:
                break
            try:
                callback(value)
            except Exception:
                self._tk_root.report_callback_exception(*sys.exc_info())
        if not self._shutdown:
            self._completion_after_id = self.root.after(50, self._poll_completions)

    def test_connection(self) -> None:
        if self.busy:
            return
        try:
            config = self._draft_api_config(timeout_seconds=self._model_preference_values()["connection_timeout"])
        except ValueError as exc:
            self._show_error("配置不完整", str(exc), parent=self.root)
            return
        self.busy_kind = "connection_test"
        self._set_busy(True, "正在测试模型连接，窗口仍可移动和重绘...")
        client = self._client(config)
        self._submit(client.test_connection, self._connection_ok, self._connection_failed)

    def _connection_ok(self, result: Any) -> None:
        confirmation = "模型设置已确认" if self._model_settings_confirmed() else "模型设置尚未确认，请点击“确认”"
        if result.probe_truncated:
            self._set_busy(
                False,
                f"接口已响应：{result.model or self.api_model_var.get()} · {result.latency_ms} ms；探针输出被截断，生成未验证；{confirmation}",
            )
        else:
            self._set_busy(False, f"连接成功：{result.model or self.api_model_var.get()} · {result.latency_ms} ms；{confirmation}")

    def _connection_failed(self, exc: Exception) -> None:
        self._set_busy(False, f"连接失败：{exc}")
        self._show_error("连接失败", str(exc), parent=self.root)

    def _sync_input(self) -> None:
        text = self.widgets["task_text"].get("1.0", "end-1c").strip()
        if text != self.session.task_text:
            self.session.set_task(text)
        selected = self.category_by_label[self.category_var.get()]
        if selected != self.session.selected_category:
            self.session.choose_category(selected)
        level = self.thinking_level_var.get()
        if level not in {"quick", "standard", "deep"}:
            level = "standard"
        self.session.control["thinking_level"] = level
        self.session.control["thinking_policy"] = "coverage_based"
        # Keep the configurable network Skill endpoint in the session as soon
        # as normal user actions synchronize the other input controls. This
        # prevents saving from introducing an otherwise invisible state change.
        self.session.control["skill_search_url"] = self._normalized_skill_search_url()

    def _normalized_skill_search_url(self) -> str:
        """Persist only an explicit endpoint; the standard Skill index is implicit."""
        value = self.skill_search_url_var.get().strip().rstrip("/")
        return "" if not value or value == "https://skills.sh" else value

    def start_analysis(self, *, compact_retry: bool = False) -> None:
        if self.busy:
            return
        try:
            self._sync_input()
            config = self._api_config()
            connection_snapshot = self._generation_snapshot()
            request_id = f"req-{uuid4().hex}"
            payload = self.workflow.prepare_m1(request_id)
            self.session.bind_request_connection_version(request_id, self.connection_version)
        except (ValueError, SessionStateError, M1ValidationError) as exc:
            self._show_error("无法开始分析", str(exc), parent=self.root)
            return
        self.busy_kind = "m1"
        self._set_busy(True, "正在分析需求；返回前可查看界面，但不要关闭程序...")
        client = self._client(config)
        workflow = self.workflow
        session_token = self._session_instance_token
        operation = lambda: workflow.invoke_m1(
            payload,
            client,
            protocol=config.protocol,
            configured_model=config.model,
            request_parameters=json_request_parameters(config),
            compact_retry=compact_retry,
        )
        self._submit(
            operation,
            lambda outcome: self._analysis_ok(payload, outcome, connection_snapshot, session_token=session_token),
            lambda exc: self._analysis_failed(payload, exc, connection_snapshot, config.timeout_seconds,
                                              session_token=session_token),
        )

    def _analysis_ok(
        self,
        payload: dict[str, Any],
        outcome: M1CallOutcome,
        connection_snapshot: tuple[str, str, str, str] | None = None,
        *, session_token: str | None = None,
    ) -> None:
        if not self._phase_request_is_current(payload, session_token):
            return
        if connection_snapshot is not None and connection_snapshot != self._generation_snapshot():
            self.session.pending_requests.pop(payload["request_id"], None)
            self._set_busy(False, "连接配置已变化，已忽略旧需求分析结果。")
            self.refresh()
            return
        before_progress = self._m1_progress_signature()
        try:
            self._sync_input()
            self.workflow.apply_m1(payload, outcome)
        except StaleResponseError as exc:
            self._set_busy(False, f"已拒绝旧返回：{exc}")
            self.refresh()
            return
        except SkillAiSelectionError as exc:
            self._analysis_failed(payload, exc, connection_snapshot)
            return
        if outcome.recovery_mode == "program_recovery":
            status = "已保留当前信息；AI 还没有形成可靠判断，请继续补充或查看下一步问题。"
        elif self._m1_progress_signature() == before_progress:
            status = "本轮没有形成新进展；可补充或修改任务后显式重试。"
        else:
            status = f"需求分析已通过本地校验 · {outcome.api_result.latency_ms} ms"
        self._set_busy(False, status)
        self.refresh()

    def _m1_progress_signature(self) -> tuple[Any, ...]:
        def frozen(rows: Any) -> str:
            import json

            return json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

        return (
            frozen(self.session.pending_proposals),
            frozen(self.session.open_conflicts),
            frozen(self.session.gaps),
            frozen(self.session.questions_for_review()),
            tuple(self.session.pending_review_item_ids),
            frozen(self.session.gap_update_history),
            frozen(self.session.question_reopen_history),
            frozen(self.session.last_model_judgment or {}),
            self.session.analysis_basis_version,
        )

    def _analysis_failed(
        self,
        payload: dict[str, Any],
        exc: Exception,
        connection_snapshot: tuple[str, str, str, str] | None = None,
        timeout_seconds: float | None = None,
        *, session_token: str | None = None,
    ) -> None:
        if not self._phase_request_is_current(payload, session_token):
            return
        if connection_snapshot is not None and connection_snapshot != self._generation_snapshot():
            self.session.pending_requests.pop(payload["request_id"], None)
            self._set_busy(False, "连接配置已变化，已忽略旧需求分析失败结果。")
            self.refresh()
            return
        if not isinstance(exc, M1CallFailure):
            self.session.pending_requests.pop(payload["request_id"], None)
            kind = exc.kind if isinstance(exc, ApiError) else type(exc).__name__
            self.session.errors.append(
                {"request_id": payload["request_id"], "kind": kind, "message": str(exc)}
            )
            self.session.touch()
        evidence = f"；请求与错误记录保存在 {exc.evidence_dir}" if isinstance(exc, M1CallFailure) else ""
        message = generation_failure_message("m1", exc, timeout_seconds)
        kind = getattr(exc, "kind", None)
        if kind == "truncated":
            result = getattr(exc, "api_result", None)
            usage = (getattr(result, "usage", None) or getattr(exc, "response_usage", None) or {})
            details = usage.get("completion_tokens_details") or {}
            reasoning_tokens = details.get("reasoning_tokens") if isinstance(details, dict) else None
            output_tokens = usage.get("completion_tokens")
            reasoning_only = (not (getattr(result, "content", None) or getattr(exc, "response_content", "")).strip()
                              and isinstance(reasoning_tokens, int) and isinstance(output_tokens, int)
                              and output_tokens > 0 and reasoning_tokens >= output_tokens)
            message = (
                "本轮需求分析输出被长度限制截断，未提交不完整结果；已有回答和需求已保留。"
                "点击“重试分析”可以再试一次；如仍失败，可更换模型或分批补充。"
            )
            if reasoning_only:
                message = (f"本次模型将全部 {output_tokens:,} 个输出 token 用于思考，尚未返回正文；未自动重试，已有回答和需求已保留。"
                           "如果只是在核对表里修改候选，可直接确认，无需再整理；否则可更换模型，或自行调整思考强度后重试。")
        elif kind == "json_error":
            message = "本次返回没有形成可用结果；未自动重试。已有回答和需求已保留，可以主动重试或更换模型。"
        elif kind == "validation_error":
            message = "本次返回的内容关联不一致，未采用，也未自动重试。已有回答和需求已保留；可修改内容或点击“重试分析”。"
        self._set_busy(False, f"分析失败：{message}{evidence}")
        self.refresh()
        self._show_error("需求分析失败", f"{message}{evidence}\n任务输入和已有需求未丢失。", parent=self.root)

    def _on_category_selected(self, _event: tk.Event | None = None) -> None:
        selected = self.category_by_label[self.category_var.get()]
        if selected != self.session.selected_category:
            self.session.choose_category(selected)
            self.refresh()

    def accept_selected_proposals(self) -> None:
        selected = list(self.widgets["proposals_tree"].selection())
        self._accept_proposals(selected)

    def accept_all_proposals(self) -> None:
        self._accept_proposals([row["proposal_id"] for row in self.session.pending_proposals])

    def _accept_proposals(self, proposal_ids: list[str]) -> None:
        if not proposal_ids:
            self._show_info("没有候选", "请选择候选，或等待模型返回。", parent=self.root)
            return
        try:
            self.session.accept_proposals(proposal_ids)
        except SessionStateError as exc:
            self._show_error("无法接受候选", str(exc), parent=self.root)
        self.refresh()

    def dismiss_proposals(self) -> None:
        if not self.session.pending_proposals:
            return
        if messagebox.askyesno("忽略候选", "忽略当前所有模型候选？已确认需求不会改变。", parent=self.root):
            self.session.dismiss_proposals()
            self.refresh()

    def edit_selected_requirement(self, item_id=None) -> None:
        selected = (item_id,) if item_id else self.widgets["requirements_tree"].selection()
        if len(selected) != 1:
            self._show_info("请选择一项", "请选择一条需求进行编辑。", parent=self.root)
            return
        item = next(row for row in self.session.requirements if row["item_id"] == selected[0])
        result = self._multi_text_dialog(
            "\u7f16\u8f91\u9700\u6c42",
            [("text", "\u9700\u6c42\u5185\u5bb9", item["text"])],
        )
        if result is None:
            return
        try:
            self.session.edit_requirement(item["item_id"], result["text"])
        except SessionStateError as exc:
            self._show_error("无法编辑", str(exc), parent=self.root)
        self.refresh()

    def _multi_text_dialog(
        self,
        title: str,
        fields: list[tuple[str, str, str]],
        *,
        width: int = 760,
        height: int = 560,
    ) -> dict[str, str] | None:
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.geometry(f"{width}x{height}")
        dialog.minsize(min(width, 680), min(height, 480))
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)
        shell = ttk.Frame(dialog, padding=12)
        shell.grid(row=0, column=0, sticky="nsew")
        shell.columnconfigure(0, weight=1)
        for index in range(len(fields)):
            shell.rowconfigure(index * 2 + 1, weight=1)
        editors: dict[str, tk.Text] = {}
        for index, (key, label, initial) in enumerate(fields):
            ttk.Label(shell, text=label, style="Section.TLabel").grid(
                row=index * 2, column=0, sticky="w", pady=(4 if index else 0, 0)
            )
            frame = ttk.Frame(shell)
            frame.grid(row=index * 2 + 1, column=0, sticky="nsew", pady=(3, 8))
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)
            editor = tk.Text(frame, height=5 if len(fields) > 1 else 12, wrap="word", undo=True, font=ui_font(self.root))
            editor.grid(row=0, column=0, sticky="nsew")
            scroll = ttk.Scrollbar(frame, orient="vertical", command=editor.yview)
            scroll.grid(row=0, column=1, sticky="ns")
            editor.configure(yscrollcommand=scroll.set)
            editor.insert("1.0", initial)
            self._bind_context_menu(editor)
            editors[key] = editor
        result: dict[str, str] | None = None

        def save() -> None:
            nonlocal result
            result = {key: editor.get("1.0", "end-1c").strip() for key, editor in editors.items()}
            dialog.destroy()

        buttons = ttk.Frame(shell)
        buttons.grid(row=len(fields) * 2, column=0, sticky="e", pady=(4, 0))
        ttk.Button(buttons, text="\u53d6\u6d88", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="\u4fdd\u5b58", command=save).pack(side="right", padx=(0, 8))
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.grab_set()
        next(iter(editors.values())).focus_set()
        self.root.wait_window(dialog)
        return result

    def withdraw_selected_requirement(self) -> None:
        selected = self.widgets["requirements_tree"].selection()
        if len(selected) != 1:
            self._show_info("请选择一项", "请选择一条需求进行撤销。", parent=self.root)
            return
        if not messagebox.askyesno("撤销需求", "撤销选中的需求？旧值会保留在会话历史中。", parent=self.root):
            return
        try:
            self.session.withdraw_requirement(selected[0])
        except SessionStateError as exc:
            self._show_error("无法撤销", str(exc), parent=self.root)
        self.refresh()

    def confirm_requirements(self) -> None:
        if self._return_to_unknown_questions():
            return
        try:
            self._sync_input()
            version = self.session.confirm_requirements()
        except SessionStateError as exc:
            self._show_error("暂不能确认", str(exc), parent=self.root)
            return
        self.status_var.set(f"已由用户确认需求版本 {version}，可生成完整初始方案。")
        self.refresh()

    def start_plan_generation(self) -> None:
        if self.busy:
            return
        if self._return_to_unknown_questions():
            return
        try:
            self._sync_input()
            config = self._api_config()
            connection_snapshot = self._generation_snapshot()
            request_id = f"m2-{uuid4().hex}"
            payload = self.workflow.prepare_m2(request_id)
            self.session.bind_request_connection_version(request_id, self.connection_version)
        except (ValueError, SessionStateError, M2ValidationError) as exc:
            self._show_error("无法生成方案", str(exc), parent=self.root)
            return
        self.busy_kind = "m2"
        self._plan_navigation_at_start = (self._navigation_revision, self.notebook.select())
        self._set_busy(True, "正在依据已确认需求生成完整初始方案...")
        client = self._client(config)
        workflow = self.workflow
        session_token = self._session_instance_token
        compact_retry = workflow.m2_retry_recommended()
        operation = lambda: workflow.invoke_m2(
            payload,
            client,
            protocol=config.protocol,
            configured_model=config.model,
            request_parameters=json_request_parameters(config),
            compact_retry=compact_retry,
        )
        self._submit(
            operation,
            lambda outcome: self._plan_ok(payload, outcome, connection_snapshot, session_token=session_token),
            lambda exc: self._plan_failed(payload, exc, connection_snapshot, config.timeout_seconds,
                                          session_token=session_token),
        )

    def _plan_ok(
        self,
        payload: dict[str, Any],
        outcome: M2CallOutcome,
        connection_snapshot: tuple[str, str, str, str],
        *, session_token: str | None = None,
    ) -> None:
        if not self._phase_request_is_current(payload, session_token):
            return
        if connection_snapshot != self._generation_snapshot():
            self.session.pending_requests.pop(payload["request_id"], None)
            self._set_busy(False, "连接配置已变化，已忽略旧方案返回。")
            self.refresh()
            return
        try:
            self._sync_input()
            self.workflow.apply_m2(payload, outcome)
        except StaleResponseError as exc:
            self._set_busy(False, f"已拒绝旧方案返回：{exc}")
            self.refresh()
            return
        except Exception as exc:
            self._plan_failed(payload, exc, connection_snapshot)
            return
        unknown_count = len(self.session.plan["content"].get("unresolved_items", []))
        question_count = len(self.session.questions_for_review())
        guidance = (
            f"有 {question_count} 项内容需要逐项核对；请回答或跳过这些问题。"
            if question_count else f"已保留 {unknown_count} 项未定信息供下游 AI 处理，请核对方案后确认。"
            if unknown_count else "请核对方案，确认后即可生成提示。"
        )
        logging.getLogger(__name__).info("Plan clarification review ready; task=%s unknowns=%d questions=%d",
                                        self.session.task_id, unknown_count, question_count)
        self._set_busy(False, f"方案草稿已生成。{guidance}")
        draft_ready = self.session.current_draft_authorization() is not None and not question_count
        if draft_ready:
            try:
                draft = build_final_draft(self.session, allow_unconfirmed_plan=True)
                stage_final_draft(self.session, draft, expected_basis=draft["basis"])
            except (SessionStateError, DeliveryValidationError) as exc:
                self.status_var.set(f"方案已保留；草稿提示尚未生成：{exc}")
                draft_ready = False
        self.refresh()
        origin = getattr(self, "_plan_navigation_at_start", None)
        if origin is None or origin == (self._navigation_revision, self.notebook.select()):
            if self.notebook.index(self.notebook.select()) == 0:
                self._conversation_scroll_latest(force=True)
            else:
                self.show_workspace(3 if draft_ready else 1)
        else:
            self.status_var.set(f"方案已生成，可以点击上方“方案”查看；当前编辑位置已保留。{guidance}")

    def _plan_failed(
        self,
        payload: dict[str, Any],
        exc: Exception,
        connection_snapshot: tuple[str, str, str, str],
        timeout_seconds: float | None = None,
        *, session_token: str | None = None,
    ) -> None:
        if not self._phase_request_is_current(payload, session_token):
            return
        if connection_snapshot != self._generation_snapshot():
            self.session.pending_requests.pop(payload["request_id"], None)
            self._set_busy(False, "连接配置已变化，已忽略旧方案失败结果。")
            self.refresh()
            return
        if not isinstance(exc, M2CallFailure):
            self.session.pending_requests.pop(payload["request_id"], None)
            kind = exc.kind if isinstance(exc, ApiError) else type(exc).__name__
            self.session.errors.append(
                {"request_id": payload["request_id"], "kind": f"m2_{kind}", "message": str(exc)}
            )
            self.session.touch()
        evidence = f"\n诊断记录：{exc.evidence_dir}" if isinstance(exc, M2CallFailure) else ""
        message = generation_failure_message("m2", exc, timeout_seconds)
        self._set_busy(False, message)
        self.refresh()
        self._show_warning(
            "本次方案尚未生成", f"{message}{evidence}", parent=self.root
        )

    def save_plan_goal(self) -> None:
        if self.busy:
            return
        text = self.widgets["plan_goal_text"].get("1.0", "end-1c")
        try:
            self.session.edit_plan_goal(text)
        except SessionStateError as exc:
            self._show_error("无法修改目标", str(exc), parent=self.root)
            return
        self.status_var.set("方案目标已修改，方案确认已失效，关键工作需要重新复核。")
        self.refresh()

    def edit_plan_goal_details(self) -> None:
        content = self.session.plan.get("content") or {}
        goal = content.get("goal")
        if not goal:
            self._show_info("尚无方案", "请先生成初始方案。", parent=self.root)
            return
        values = self._multi_text_dialog(
            "\u7f16\u8f91\u65b9\u6848\u76ee\u6807",
            [
                ("audience", "\u4e3b\u8981\u53d7\u4f17", goal["audience"]),
                ("scope", "\u65b9\u6848\u8303\u56f4", goal["scope"]),
            ],
        )
        if values is None:
            return
        try:
            self.session.edit_plan_goal_details(**values)
        except SessionStateError as exc:
            self._show_error("无法修改目标", str(exc), parent=self.root)
        self.refresh()

    def edit_selected_plan_section(self) -> None:
        selected = self.plan_section_var.get()
        target = self._plan_section_lookup.get(selected)
        if target is None:
            self._show_info("请选择栏目", "请选择一个可编辑的方案栏目。", parent=self.root)
            return
        section_type, entity_id = target
        content = self.session.plan.get("content") or {}
        specs = {
            "deliverable": ("deliverables", "deliverable_id", (("name", "名称"), ("description", "说明"))),
            "criterion": ("completion_criteria", "criterion_id", (("text", "完成标准"),)),
            "unresolved": (
                "unresolved_items",
                "unresolved_id",
                (("description", "未决事项"), ("impact", "影响"), ("continuable_work", "可继续工作"), ("confirm_by", "确认时点")),
            ),
            "suggestion": ("suggestions", "suggestion_id", (("text", "建议"), ("reason", "理由"))),
        }
        collection, id_key, fields = specs[section_type]
        row = next(item for item in content[collection] if item[id_key] == entity_id)
        dialog_fields = [
            (key, label, "\n".join(row[key]) if isinstance(row[key], list) else str(row[key]))
            for key, label in fields
        ]
        values = self._multi_text_dialog("\u7f16\u8f91\u65b9\u6848\u680f\u76ee", dialog_fields)
        if values is None:
            return
        updates = {
            key: [line.strip() for line in value.splitlines() if line.strip()]
            if isinstance(row[key], list)
            else value
            for key, value in values.items()
        }
        try:
            self.session.edit_plan_section(section_type, entity_id, updates)
        except SessionStateError as exc:
            self._show_error("无法编辑栏目", str(exc), parent=self.root)
        self.refresh()

    def edit_selected_plan_step(self) -> None:
        if self.busy:
            return
        selected = self.widgets["plan_steps_tree"].selection()
        if len(selected) != 1:
            self._show_info("请选择步骤", "请选择一个方案步骤。", parent=self.root)
            return
        content = self.session.plan.get("content") or {}
        step = next((row for row in content.get("steps", []) if row["step_id"] == selected[0]), None)
        if step is None:
            return
        values = self._plan_step_dialog(step)
        if values is None:
            return
        try:
            self.session.edit_plan_step(step["step_id"], **values)
        except SessionStateError as exc:
            self._show_error("无法编辑步骤", str(exc), parent=self.root)
        self.refresh()

    def add_plan_step(self) -> None:
        if self.busy:
            return
        values = self._plan_step_dialog(None)
        if values is None:
            return
        try:
            self.session.add_plan_step(**values)
        except SessionStateError as exc:
            self._show_error("无法新增步骤", str(exc), parent=self.root)
        self.refresh()

    @staticmethod
    def _lines(text: tk.Text) -> list[str]:
        return [line.strip() for line in text.get("1.0", "end-1c").splitlines() if line.strip()]

    def _plan_step_dialog(self, step: dict[str, Any] | None) -> dict[str, Any] | None:
        content = self.session.plan.get("content") or {}
        current_id = step.get("step_id") if step else None
        dialog = tk.Toplevel(self.root)
        dialog.title("编辑方案步骤" if step else "新增方案步骤")
        dialog.transient(self.root)
        dialog.geometry("820x680")
        dialog.minsize(700, 580)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)
        shell = ttk.Frame(dialog, padding=12)
        shell.grid(row=0, column=0, sticky="nsew")
        shell.columnconfigure(0, weight=1)
        shell.columnconfigure(1, weight=1)
        for row in range(3):
            shell.rowconfigure(row * 2 + 1, weight=1)

        specs = (
            ("title", "标题", 0, 0),
            ("purpose", "目的", 0, 1),
            ("inputs", "必要输入（每行一项，可为空）", 2, 0),
            ("actions", "关键行动（每行一项）", 2, 1),
            ("outputs", "预期输出（每行一项）", 4, 0),
            ("completion_criteria", "完成标准（每行一项）", 4, 1),
        )
        editors: dict[str, tk.Text] = {}
        for key, label, row, column in specs:
            ttk.Label(shell, text=label, style="Section.TLabel").grid(
                row=row, column=column, sticky="w", padx=(0 if column == 0 else 6, 6 if column == 0 else 0)
            )
            editor = tk.Text(shell, height=3, wrap="word", undo=True, font=ui_font(self.root))
            editor.grid(
                row=row + 1,
                column=column,
                sticky="nsew",
                padx=(0 if column == 0 else 6, 6 if column == 0 else 0),
                pady=(3, 8),
            )
            initial = ""
            if step:
                value = step.get(key, "")
                initial = "\n".join(value) if isinstance(value, list) else str(value)
            editor.insert("1.0", initial)
            self._bind_context_menu(editor)
            editors[key] = editor

        link_frame = ttk.Frame(shell)
        link_frame.grid(row=6, column=0, columnspan=2, sticky="nsew")
        link_frame.columnconfigure(0, weight=1)
        link_frame.columnconfigure(1, weight=1)
        ttk.Label(link_frame, text="依赖步骤", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(link_frame, text="关联需求", style="Section.TLabel").grid(row=0, column=1, sticky="w", padx=(8, 0))
        step_list = tk.Listbox(link_frame, selectmode="multiple", exportselection=False, height=5, font=ui_font(self.root))
        req_list = tk.Listbox(link_frame, selectmode="multiple", exportselection=False, height=5, font=ui_font(self.root))
        step_list.grid(row=1, column=0, sticky="nsew")
        req_list.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        dependency_ids = []
        for row in sorted(content.get("steps", []), key=lambda item: item["order"]):
            if row["step_id"] == current_id:
                continue
            dependency_ids.append(row["step_id"])
            step_list.insert("end", f"{row['step_id']} · {row['title']}")
        requirement_ids = []
        for row in self.session.requirements:
            requirement_ids.append(row["item_id"])
            req_list.insert("end", f"{row['item_id']} · {row['text']}")
        for index, value in enumerate(dependency_ids):
            if step and value in step.get("depends_on_step_ids", []):
                step_list.selection_set(index)
        for index, value in enumerate(requirement_ids):
            if step and value in step.get("requirement_ids", []):
                req_list.selection_set(index)

        result: dict[str, Any] | None = None

        def save() -> None:
            nonlocal result
            title = editors["title"].get("1.0", "end-1c").strip()
            purpose = editors["purpose"].get("1.0", "end-1c").strip()
            if not title or not purpose:
                self._show_error("内容不完整", "步骤标题和目的不能为空。", parent=dialog)
                return
            result = {
                "title": title,
                "purpose": purpose,
                "inputs": self._lines(editors["inputs"]),
                "actions": self._lines(editors["actions"]),
                "outputs": self._lines(editors["outputs"]),
                "completion_criteria": self._lines(editors["completion_criteria"]),
                "depends_on_step_ids": [dependency_ids[index] for index in step_list.curselection()],
                "requirement_ids": [requirement_ids[index] for index in req_list.curselection()],
            }
            dialog.destroy()

        buttons = ttk.Frame(shell)
        buttons.grid(row=7, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="取消", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="保存草稿", command=save).pack(side="right", padx=(0, 8))
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.grab_set()
        editors["title"].focus_set()
        self.root.wait_window(dialog)
        return result

    def delete_selected_plan_step(self) -> None:
        if self.busy:
            return
        selected = self.widgets["plan_steps_tree"].selection()
        if len(selected) != 1:
            self._show_info("请选择步骤", "请选择一个方案步骤。", parent=self.root)
            return
        if not messagebox.askyesno("删除步骤", "删除选中步骤？", parent=self.root):
            return
        try:
            self.session.delete_plan_step(selected[0])
        except SessionStateError as exc:
            self._show_error("无法删除步骤", str(exc), parent=self.root)
        self.refresh()

    def move_selected_plan_step(self, offset: int) -> None:
        if self.busy:
            return
        selected = self.widgets["plan_steps_tree"].selection()
        if len(selected) != 1:
            self._show_info("请选择步骤", "请选择一个方案步骤。", parent=self.root)
            return
        try:
            self.session.move_plan_step(selected[0], offset)
        except SessionStateError as exc:
            self._show_error("无法调整顺序", str(exc), parent=self.root)
        self.refresh()
        self.widgets["plan_steps_tree"].selection_set(selected[0])

    def review_selected_key_work(self) -> None:
        selected = list(self.widgets["plan_key_work_tree"].selection())
        try:
            self.session.mark_key_work_reviewed(selected)
        except SessionStateError as exc:
            self._show_error("无法完成复核", str(exc), parent=self.root)
            return
        self.status_var.set("选中的关键工作已由用户复核。")
        self.refresh()

    def edit_selected_key_work(self) -> None:
        selected = self.widgets["plan_key_work_tree"].selection()
        if len(selected) != 1:
            self._show_info("请选择关键工作", "请选择一项关键工作。", parent=self.root)
            return
        content = self.session.plan.get("content") or {}
        row = next(
            (item for item in content.get("key_work", []) if item["key_work_id"] == selected[0]),
            None,
        )
        if row is None:
            return
        values = self._key_work_dialog(row)
        if values is None:
            return
        try:
            self.session.edit_plan_section("key_work", row["key_work_id"], values)
        except SessionStateError as exc:
            self._show_error("无法编辑关键工作", str(exc), parent=self.root)
        self.refresh()

    def _key_work_dialog(self, row: dict[str, Any]) -> dict[str, Any] | None:
        content = self.session.plan.get("content") or {}
        dialog = tk.Toplevel(self.root)
        dialog.title("编辑关键工作")
        dialog.transient(self.root)
        dialog.geometry("820x650")
        dialog.minsize(700, 560)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)
        shell = ttk.Frame(dialog, padding=12)
        shell.grid(row=0, column=0, sticky="nsew")
        shell.columnconfigure(0, weight=1)
        shell.columnconfigure(1, weight=1)
        for index in (1, 3, 5):
            shell.rowconfigure(index, weight=1)
        specs = (
            ("title", "标题", 0, 0),
            ("goal", "目标", 0, 1),
            ("inputs", "输入（每行一项）", 2, 0),
            ("outputs", "输出（每行一项）", 2, 1),
            ("checkpoints", "检查点（每行一项）", 4, 0),
        )
        editors: dict[str, tk.Text] = {}
        for key, label, grid_row, column in specs:
            ttk.Label(shell, text=label, style="Section.TLabel").grid(
                row=grid_row, column=column, sticky="w", padx=(0 if column == 0 else 6, 6 if column == 0 else 0)
            )
            editor = tk.Text(shell, height=3, wrap="word", undo=True, font=ui_font(self.root))
            editor.grid(
                row=grid_row + 1,
                column=column,
                sticky="nsew",
                padx=(0 if column == 0 else 6, 6 if column == 0 else 0),
                pady=(3, 8),
            )
            value = row.get(key, "")
            editor.insert("1.0", "\n".join(value) if isinstance(value, list) else str(value))
            self._bind_context_menu(editor)
            editors[key] = editor

        links = ttk.Frame(shell)
        links.grid(row=4, column=1, rowspan=2, sticky="nsew", padx=(6, 0))
        links.columnconfigure(0, weight=1)
        links.columnconfigure(1, weight=1)
        ttk.Label(links, text="关联步骤", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(links, text="关联需求", style="Section.TLabel").grid(row=0, column=1, sticky="w", padx=(6, 0))
        step_list = tk.Listbox(links, selectmode="multiple", exportselection=False, font=ui_font(self.root))
        req_list = tk.Listbox(links, selectmode="multiple", exportselection=False, font=ui_font(self.root))
        step_list.grid(row=1, column=0, sticky="nsew")
        req_list.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        step_ids = []
        for step in sorted(content.get("steps", []), key=lambda item: item["order"]):
            step_ids.append(step["step_id"])
            step_list.insert("end", f"{step['step_id']} · {step['title']}")
        req_ids = []
        for requirement in self.session.requirements:
            req_ids.append(requirement["item_id"])
            req_list.insert("end", f"{requirement['item_id']} · {requirement['text']}")
        for index, value in enumerate(step_ids):
            if value in row.get("step_ids", []):
                step_list.selection_set(index)
        for index, value in enumerate(req_ids):
            if value in row.get("requirement_ids", []):
                req_list.selection_set(index)

        result: dict[str, Any] | None = None

        def save() -> None:
            nonlocal result
            title = editors["title"].get("1.0", "end-1c").strip()
            goal = editors["goal"].get("1.0", "end-1c").strip()
            if not title or not goal:
                self._show_error("内容不完整", "关键工作标题和目标不能为空。", parent=dialog)
                return
            result = {
                "title": title,
                "goal": goal,
                "inputs": self._lines(editors["inputs"]),
                "outputs": self._lines(editors["outputs"]),
                "checkpoints": self._lines(editors["checkpoints"]),
                "step_ids": [step_ids[index] for index in step_list.curselection()],
                "requirement_ids": [req_ids[index] for index in req_list.curselection()],
                "depends_on_key_work_ids": list(row.get("depends_on_key_work_ids", [])),
            }
            dialog.destroy()

        buttons = ttk.Frame(shell)
        buttons.grid(row=6, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text="取消", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="保存草稿", command=save).pack(side="right", padx=(0, 8))
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.grab_set()
        editors["title"].focus_set()
        self.root.wait_window(dialog)
        return result

    def _set_plan_overview_text(self, text: str) -> None:
        overview = self.widgets["plan_overview_text"]
        overview.configure(state="normal")
        overview.delete("1.0", "end")
        overview.insert("1.0", text)
        overview.configure(state="disabled")

    def _show_selected_plan_step(self) -> None:
        selected = self.widgets["plan_steps_tree"].selection()
        if len(selected) != 1:
            return
        content = self.session.plan.get("content") or {}
        row = next((item for item in content.get("steps", []) if item["step_id"] == selected[0]), None)
        if row is None:
            return

        def lines(values: list[str]) -> str:
            return "\n".join(f"• {value}" for value in values) if values else "• 无"

        self._set_plan_overview_text(
            f"步骤 {row['order']} · {row['title']}\n\n目的\n{row['purpose']}\n\n"
            f"输入\n{lines(row['inputs'])}\n\n行动\n{lines(row['actions'])}\n\n"
            f"输出\n{lines(row['outputs'])}\n\n完成标准\n{lines(row['completion_criteria'])}\n\n"
            f"依赖步骤\n{lines(row['depends_on_step_ids'])}\n\n需求关联\n{lines(row['requirement_ids'])}"
        )

    def _show_selected_key_work(self) -> None:
        selected = self.widgets["plan_key_work_tree"].selection()
        if len(selected) != 1:
            return
        content = self.session.plan.get("content") or {}
        row = next((item for item in content.get("key_work", []) if item["key_work_id"] == selected[0]), None)
        if row is None:
            return

        def lines(values: list[str]) -> str:
            return "\n".join(f"• {value}" for value in values) if values else "• 无"

        self._set_plan_overview_text(
            f"关键工作 · {row['title']}\n\n目标\n{row['goal']}\n\n输入\n{lines(row['inputs'])}\n\n"
            f"输出\n{lines(row['outputs'])}\n\n检查点\n{lines(row['checkpoints'])}\n\n"
            f"关联步骤\n{lines(row['step_ids'])}\n\n需求关联\n{lines(row['requirement_ids'])}"
        )

    def confirm_plan(self) -> None:
        try:
            version = self.session.confirm_plan()
        except (SessionStateError, M2ValidationError) as exc:
            if self.session.questions_for_review():
                self.status_var.set(str(exc))
                self.refresh()
                self.show_workspace(0)
                return
            self._show_error("暂不能确认方案", str(exc), parent=self.root)
            return
        self.status_var.set(f"已由用户确认方案版本 {version}。")
        self.refresh()

    def go_to_requirements(self) -> None:
        self.notebook.select(0)
        self.status_var.set("已返回需求页；只有实际修改需求才会使当前方案过期。")

    def record_question(self, disposition: str) -> None:
        selected = self.widgets["questions_tree"].selection()
        if len(selected) != 1:
            self._show_info("请选择问题", "请选择一条问题。", parent=self.root)
            return
        try:
            self.session.record_question(selected[0], disposition, self.answer_var.get())
        except SessionStateError as exc:
            self._show_error("无法记录", str(exc), parent=self.root)
            return
        self.answer_var.set("")
        self.status_var.set("回答原话已记录，相关未知仍保留；点击“分析 / 继续”判断是否已补足。")
        self.refresh()

    def review_selected_requirements(self) -> None:
        selected = list(self.widgets["requirements_tree"].selection())
        try:
            self.session.mark_requirements_reviewed(selected)
        except SessionStateError as exc:
            self._show_error("无法完成复核", str(exc), parent=self.root)
            return
        self.status_var.set("选中的受影响需求已由用户复核。")
        self.refresh()

    def add_rounds(self) -> None:
        """Compatibility action for old saved layouts; it no longer changes a budget."""
        self.session.control["allow_questions"] = True
        self.session.pending_requests.clear()
        self.session.touch()
        self.status_var.set("已允许模型继续根据未解决的问题整理；不会改变你的需求内容。")
        self.refresh()

    def refresh(self) -> None:
        confirmed = self.session.confirmed_requirements_version
        confirmed_text = f"已确认 v{confirmed}" if confirmed is not None else "未确认"
        self.summary_var.set(
            f"当前需求 v{self.session.requirement_version} · {confirmed_text} · "
            "AI 会根据未解决的问题继续判断"
        )
        self.assistant_var.set(self.session.last_assistant_text or "尚未运行需求分析。")
        self.next_step_var.set(self._next_step_text())
        self._refresh_primary_action()
        self._fill_tree(
            "requirements_tree",
            self.session.requirements,
            "item_id",
            lambda row: (
                FIELD_LABELS.get(row["field"], row["field"]),
                row["text"],
                CONFIRMATION_LABELS.get(row["confirmation"], row["confirmation"]),
            ),
        )
        self._fill_tree(
            "proposals_tree",
            self.session.pending_proposals,
            "proposal_id",
            lambda row: (
                OPERATION_LABELS.get(row["operation"], row["operation"]),
                FIELD_LABELS.get(row["field"], row["field"]),
                row["text"],
            ),
        )
        self._fill_tree(
            "questions_tree",
            self.session.questions_for_review(),
            "question_id",
            lambda row: (FIELD_LABELS.get(row["field"], row["field"]), row["text"]),
        )
        self._refresh_plan_page()
        self._refresh_delivery_pages()
        self._refresh_guided()

    def _refresh_plan_page(self) -> None:
        plan = self.session.plan
        content = plan.get("content") if isinstance(plan.get("content"), dict) else None
        source_version = plan.get("source_requirements_version")
        confirmed_plan = plan.get("confirmed_plan_version")
        status_labels = {
            "not_started": "未生成",
            "draft": "草稿待核对",
            "confirmed": "已确认",
            "stale": "来源需求已变化",
        }
        self.plan_summary_var.set(
            f"方案 {status_labels.get(plan.get('status'), plan.get('status'))} · "
            f"版本 {plan.get('plan_version', 0)} · 来源需求 v{source_version if source_version is not None else '-'}"
            + (f" · 已确认 v{confirmed_plan}" if confirmed_plan is not None else "")
        )
        if plan.get("status") == "stale":
            next_text = "下一步：返回需求页完成复核和确认，再点击“基于新需求重新生成”。旧方案仍保留。"
        elif content is None:
            next_text = "下一步：先确认当前需求，再生成完整初始方案。"
        elif plan.get("pending_key_work_review_ids"):
            next_text = "下一步：核对方案与关键工作，完成必要修改后标记关键工作已复核。"
        elif plan.get("status") == "confirmed":
            next_text = "当前方案已经确认；如改变任务目标或硬约束，请使用“修改需求”。"
        else:
            next_text = "下一步：核对目标、覆盖、步骤、交付物、完成标准和未决事项，然后确认当前方案。"
        self.plan_next_step_var.set(next_text)

        goal_widget: tk.Text = self.widgets["plan_goal_text"]
        current_goal = goal_widget.get("1.0", "end-1c")
        goal = content.get("goal", {}).get("summary", "") if content else ""
        render_token = (
            plan.get("plan_id"),
            plan.get("plan_version"),
            plan.get("status"),
            goal,
        )
        if self._rendered_plan_token != render_token or not goal_widget.edit_modified():
            goal_widget.delete("1.0", "end")
            goal_widget.insert("1.0", goal)
            goal_widget.edit_modified(False)
        self._rendered_plan_token = render_token

        steps = content.get("steps", []) if content else []
        self._fill_tree(
            "plan_steps_tree",
            sorted(steps, key=lambda row: row["order"]),
            "step_id",
            lambda row: (row["order"], row["title"], row["purpose"]),
        )
        pending = set(plan.get("pending_key_work_review_ids", []))
        key_work = content.get("key_work", []) if content else []
        self._fill_tree(
            "plan_key_work_tree",
            key_work,
            "key_work_id",
            lambda row: (row["title"], "待复核" if row["key_work_id"] in pending else "已复核"),
        )
        section_values: list[str] = []
        section_lookup: dict[str, tuple[str, str]] = {}
        if content:
            for row in content["deliverables"]:
                label = f"交付物 · {row['name']}"
                section_values.append(label)
                section_lookup[label] = ("deliverable", row["deliverable_id"])
            for index, row in enumerate(content["completion_criteria"], 1):
                label = f"完成标准 {index} · {row['text'][:24]}"
                section_values.append(label)
                section_lookup[label] = ("criterion", row["criterion_id"])
            for index, row in enumerate(content["unresolved_items"], 1):
                label = f"未决事项 {index} · {row['description'][:24]}"
                section_values.append(label)
                section_lookup[label] = ("unresolved", row["unresolved_id"])
            for index, row in enumerate(content["suggestions"], 1):
                label = f"系统建议 {index} · {row['text'][:24]}"
                section_values.append(label)
                section_lookup[label] = ("suggestion", row["suggestion_id"])
        self._plan_section_lookup = section_lookup
        self.widgets["plan_section_combo"].configure(values=tuple(section_values))
        if self.plan_section_var.get() not in section_lookup:
            self.plan_section_var.set(section_values[0] if section_values else "")
        overview = self.widgets["plan_overview_text"]
        overview.configure(state="normal")
        overview.delete("1.0", "end")
        overview.insert("1.0", self._plan_overview(content))
        overview.configure(state="disabled")
        if not self.busy:
            try:
                self.session.validate_m2_entry()
            except SessionStateError:
                generate_state = "disabled"
            else:
                generate_state = "normal"
            self.widgets["generate_plan_button"].configure(state=generate_state)
            can_confirm = (
                plan.get("status") == "draft"
                and not plan.get("pending_key_work_review_ids")
                and plan.get("source_requirements_version") == self.session.requirement_version
            )
            self.widgets["confirm_plan_button"].configure(
                state="normal" if can_confirm else "disabled"
            )

    def _plan_overview(self, content: dict[str, Any] | None) -> str:
        if not content:
            return "尚未生成方案。M2 只使用程序保存的当前已确认需求快照。"
        lines = [
            f"受众：{content['goal']['audience']}",
            f"范围：{content['goal']['scope']}",
            "",
            "需求覆盖：",
        ]
        lines.extend(
            f"• {row['requirement_id']}：{row['summary']}" for row in content["requirement_coverage"]
        )
        lines.append("\n交付物：")
        lines.extend(f"• {row['name']}：{row['description']}" for row in content["deliverables"])
        lines.append("\n整体完成标准：")
        lines.extend(f"• {row['text']}" for row in content["completion_criteria"])
        lines.append("\n未决事项：")
        if content["unresolved_items"]:
            lines.append("这些细节会保留到最终提示，当前可以继续；使用提示时再补充即可。")
            lines.extend(
                f"• {'AI 规划时提出，待确认：' if row.get('source_gap_id') is None else ''}"
                f"{row['description']}；影响：{row['impact']}；确认时点：{row['confirm_by']}"
                for row in content["unresolved_items"]
            )
        else:
            lines.append("• 无")
        lines.append("\n系统建议（不自动成为需求）：")
        if content["suggestions"]:
            lines.extend(
                f"• {row['text']}（{'需用户确认' if row['requires_user_confirmation'] else '可选优化'}）"
                for row in content["suggestions"]
            )
        else:
            lines.append("• 无")
        return "\n".join(lines)

    def _delivery_basis(self) -> dict[str, Any]:
        plan = self.session.plan
        return {
            "task_id": self.session.task_id,
            "requirement_version": self.session.requirement_version,
            "plan_id": plan.get("plan_id"),
            "plan_version": plan.get("plan_version"),
        }

    def _key_works(self) -> list[dict[str, Any]]:
        content = self.session.plan.get("content") or {}
        return list(content.get("key_work", []))

    def _skill_basis_is_current(self) -> bool:
        skill_state = self.session.skill_state
        if skill_state.get("status") == "selected" and skill_state.get("bindings"):
            if not self._refresh_selected_catalog():
                return False
        basis = skill_state.get("basis")
        return (
            self.session.plan.get("status") == "confirmed"
            and skill_state.get("status") in {"candidates_ready", "selected"}
            and isinstance(basis, dict)
            and basis == self._delivery_basis()
        )

    def _refresh_selected_catalog(self) -> bool:
        state = self.session.skill_state
        bindings = state.get("bindings", [])
        if state.get("status") != "selected" or not bindings:
            return True
        for binding in bindings:
            if binding.get("origin") != "local_file":
                continue
            record = binding.get("record_snapshot") or {}
            source = Path(str(record.get("source_path") or binding.get("source_path") or ""))
            expected = record.get("local_source_snapshot_sha256")
            try:
                current_hash = hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None
            except OSError:
                current_hash = None
            if not expected or current_hash != expected:
                message = f"本地 Skill 来源已变化或不可用：{source}。原绑定已保留，请重新查找。"
                self.session.invalidate_delivery("selected_skill_file_changed", invalidate_selection=True)
                self.session.skill_state["last_error"] = message
                self.session.touch()
                self.skill_status_var.set(message)
                self.final_status_var.set("所选本地 Skill 文件已变化；最终结果已过期。")
                return False
        # Indexed catalog records have a separate catalog snapshot check.
        local_bindings = [
            binding for binding in bindings if binding.get("origin", "local") == "local"
        ]
        if not local_bindings:
            return True
        try:
            current = SkillCatalog.load(
                self._catalog_path,
                source_root=resource_root(),
                # The one-file build ships the catalog summary but not the
                # referenced source files.  In that runtime the binding's
                # record hash is the available provenance; source-file
                # rechecks remain enabled for normal source-tree runs.
                verify_sources=not bool(getattr(sys, "_MEIPASS", None)),
            )
        except (FileNotFoundError, SkillCatalogError) as exc:
            message = f"本地 Skill 目录暂不可用，已选 Agent Skill 快照待核验；原绑定内容已保留。{exc}"
            self.session.invalidate_delivery("selected_skill_catalog_unavailable", invalidate_selection=True)
            self.session.skill_state["last_error"] = message
            self.session.touch()
            self.skill_status_var.set(message)
            self.final_status_var.set("所选 Agent Skill 来源待核验；最终结果已过期。可返回重新筛选或跳过 Skill。")
            return False
        self.catalog = current
        assessment = current.assess_bindings(local_bindings)
        if assessment["status"] == "stale":
            message = "；".join(assessment["reasons"])
            message = f"{message} 原绑定快照已保留，请重新筛选/选用或跳过 Skill。"
            self.session.invalidate_delivery("selected_skill_catalog_changed", invalidate_selection=True)
            self.session.skill_state["last_error"] = message
            self.session.touch()
            self.skill_status_var.set(message)
            self.final_status_var.set("所选 Agent Skill 目录记录已变化；最终结果已过期。请重新核验 Skill 或跳过。")
            return False
        return True

    def _record_skill_search_state(self, **updates: Any) -> None:
        state = deepcopy(self.session.skill_state.get("search_state") or {})
        state.update(updates)
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.session.skill_state["search_state"] = state
        self.session.touch()

    def _skill_search_is_current(self, request: dict[str, Any]) -> bool:
        return bool(
            self._skill_search_busy
            and self._skill_search_request is request
            and request.get("session_token") == self._session_instance_token
        )

    def _skill_search_result_is_current(self, request: dict[str, Any]) -> bool:
        """Accept a worker result only when it belongs to the same plan basis."""
        if not self._skill_search_is_current(request):
            return False
        if request.get("basis") == self._delivery_basis():
            return True
        self._finish_skill_search(request)
        search_key = "local" if request.get("kind") == "local" else "network"
        self._record_skill_search_state(
            status="error",
            **{search_key: {"status": "stale", "count": 0}},
            last_error="确认方案已变化，已丢弃迟到的 Skill 搜索结果。",
        )
        self._skill_search_status_text = "方案已变化，已丢弃迟到的 Skill 搜索结果；请重新查找。"
        self.skill_status_var.set(self._skill_search_status_text)
        self.refresh()
        return False

    def _finish_skill_search(self, request: dict[str, Any]) -> None:
        if self._skill_search_request is request:
            self._skill_search_request = None
            self._skill_search_busy = False

    def _local_skill_search_operation(self, request: dict[str, Any]):
        preferences = request.get("preferences", self.preferences)
        def progress(message):
            check_cancelled()
            self.completions.put((lambda value: self._local_skill_search_progress(request, value), message))
        progress("正在复用并更新本地 Skill 索引…")
        root_options = {"roots": request["skill_roots"]} if request.get("skill_roots") is not None else {}
        files = discover_local_skill_candidates(request["key_works"], context_text=request["task_text"],
                                                max_candidates=preferences["local_candidates"], **root_options)
        index = files.diagnostics
        progress(f"索引含 {files.scanned_files} 个文件；复用 {index.get('cache_hits', 0)} 项，粗筛保留 {len(files.candidates)} 项")
        collected = list(files.candidates)
        seen = {
            (str(row.get("skill_id", "")), str(row.get("key_work_id", "")))
            for row in collected
            if isinstance(row, dict)
        }
        catalog_candidates: list[dict[str, Any]] = []
        catalog_error = None
        catalog = request.get("catalog")
        if catalog is not None:
            try:
                match = catalog.match(request["key_works"], context_text=request["task_text"])
                for row in match.candidates:
                    key = (str(row.get("skill_id", "")), str(row.get("key_work_id", "")))
                    if key not in seen:
                        seen.add(key)
                        catalog_candidates.append(row)
                        collected.append(row)
            except Exception as exc:
                logging.getLogger(__name__).exception("Built-in Skill matching failed")
                catalog_error = str(exc)
        try:
            if request.get("client") is None:
                raise SkillAiSelectionError(
                    request.get("ai_client_error") or "\u672a\u914d\u7f6e\u53ef\u7528\u7684 AI \u6a21\u578b\uff0c\u5df2\u4fdd\u7559\u641c\u96c6\u5230\u7684\u672c\u5730\u5019\u9009\u3002"
                )
            review_diagnostics: dict[str, Any] = {}
            selected = select_skill_candidates_with_ai(
                request["client"], collected,
                task_text=request["task_text"], key_works=request["key_works"],
                progress=progress,
                diagnostics=review_diagnostics,
                **self._skill_review_options(preferences),
            )
            files.diagnostics["ai_review"] = review_diagnostics
            ai_review_status = "completed"
            ai_review_error = None
        except CancelledError:
            raise
        except Exception as exc:
            # Preserve the local scan if the optional model review fails.
            logging.getLogger(__name__).warning("Local Skill AI review unavailable; using shortlist", exc_info=True)
            selected = shortlist_candidates(collected, task_text=request["task_text"], key_works=request["key_works"],
                                             limit=preferences["shortlist_limit"])
            ai_review_status = "unavailable"
            ai_review_error = str(exc)
            for row in selected:
                row["ai_review_status"] = ai_review_status
                row["ai_review_error"] = ai_review_error
                row["recommendation_score"] = recommendation_score(row)
                row["recommendation_basis"] = "名称/描述粗筛，AI 尚未核验"
                row.setdefault("match_reason", "已收集本地 Skill 信息，AI 筛选暂未完成，可先查看内容后自行判断。")
        return files, collected, catalog_candidates, selected, ai_review_status, ai_review_error, catalog_error

    def _local_skill_search_progress(self, request: dict[str, Any], message: str) -> None:
        if self._skill_search_is_current(request):
            self._skill_search_status_text = f"正在查找本地 Skill：{message}"
            self.skill_status_var.set(self._skill_search_status_text)

    def _local_skill_search_ok(self, request: dict[str, Any], value: Any) -> None:
        if not self._skill_search_result_is_current(request):
            return
        files, collected, catalog_candidates, selected, ai_review_status, ai_review_error, catalog_error = value
        batch = files.to_dict()
        if catalog_candidates:
            catalog = request.get("catalog")
            catalog_hash = getattr(catalog, "snapshot_hash", "")
            if catalog_hash:
                file_hash = str(batch.get("catalog_hash", ""))
                batch["catalog_hash"] = (
                    hashlib.sha256(f"{file_hash}:{catalog_hash}".encode("utf-8")).hexdigest()
                    if file_hash and file_hash != catalog_hash
                    else catalog_hash
                )
        batch["result"]["candidates"] = selected
        batch["result"]["status"] = "ok" if selected else "no_match"
        batch["sources"] = ["local_file"] + (["local_catalog"] if catalog_candidates else [])
        batch["collected_candidate_count"] = len(collected)
        batch["catalog_candidate_count"] = len(catalog_candidates)
        batch["ai_reviewed"] = ai_review_status == "completed"
        batch["ai_review_status"] = ai_review_status
        batch["ai_review_error"] = ai_review_error
        # Older built-in catalog rows may omit origin in a local search.
        for row in selected:
            row.setdefault("origin", (row.get("record_snapshot") or {}).get("origin") or "local")
        previous = self.session.skill_state.get("candidate_batch") or {}
        previous_rows = self._candidate_rows() if self._skill_basis_is_current() else []
        merged = merge_candidates(previous_rows, selected, catalog_hash=batch.get("catalog_hash", ""))
        batch["result"] = merged["result"]
        batch["catalog_hash"] = merged["catalog_hash"]
        batch["sources"] = merged["sources"]
        for key in ("network_batch_id", "network_catalog_hash", "query"):
            if previous_rows and key in previous:
                batch[key] = previous[key]
        candidates = batch["result"]["candidates"]
        bindings = list(self.session.skill_state.get("bindings", []))
        status = "selected" if bindings else "candidates_ready" if candidates else "no_match"
        try:
            self.session.set_skill_state(
                status=status,
                basis=self._delivery_basis(),
                candidate_batch=batch,
                bindings=bindings,
            )
        except SessionStateError as exc:
            self._local_skill_search_error(request, exc)
            return
        self._record_skill_search_state(
            status="local_done",
            local={"status": "ok" if selected else "no_match", "count": len(selected),
                   "scanned_files": files.scanned_files,
                   "catalog_count": len(catalog_candidates)},
            last_error=None,
        )
        self._finish_skill_search(request)
        if ai_review_status == "unavailable":
            self._skill_search_status_text = (
                f"\u5df2\u6536\u96c6 {files.scanned_files} \u4e2a\u672c\u5730 Skill \u6587\u4ef6\u548c {len(catalog_candidates)} \u9879\u5185\u7f6e\u76ee\u5f55\u5019\u9009\uff0c"
                f"\u4fdd\u7559 {len(candidates)} \u9879\uff1bAI \u7b5b\u9009\u6682\u4e0d\u53ef\u7528\uff0c\u53ef\u5148\u67e5\u770b\u5e76\u624b\u52a8\u9009\u62e9\u3002 {ai_review_error}"
            )
        else:
            self._skill_search_status_text = (
            f"已索引 {files.scanned_files} 个本地文件，本轮保留 {len(selected)} 项参考候选。"
            if selected
            else f"本地索引含 {files.scanned_files} 个 Skill 文件，少量候选核验后没有适配项；可继续联网搜索或跳过。"
            )
        if catalog_error:
            self._skill_search_status_text += f"\u5185\u7f6e\u76ee\u5f55\u8bfb\u53d6\u4e0d\u5b8c\u6574\uff1a{catalog_error}"
        self._skill_search_status_text += f" 累计保留 {len(candidates)} 项（含已有联网结果），已选 {len(bindings)} 项。"
        self.skill_status_var.set(self._skill_search_status_text)
        logging.getLogger(__name__).info("Local Skill results accumulated: task=%s previous=%d incoming=%d total=%d selected=%d",
            self.session.task_id, len(previous_rows), len(selected), len(candidates), len(bindings))
        self.refresh()

    def _local_skill_search_error(self, request: dict[str, Any], exc: Exception) -> None:
        if not self._skill_search_result_is_current(request):
            return
        self._record_skill_search_state(
            status="error",
            local={"status": "error", "count": len(self._candidate_rows())},
            last_error=str(exc),
        )
        self._finish_skill_search(request)
        self._skill_search_status_text = f"本地 Skill 查找失败：{exc}；可以重试或跳过。"
        self.skill_status_var.set(self._skill_search_status_text)
        self.refresh()

    def find_skills(self) -> None:
        if self._return_to_unknown_questions():
            return
        if self.session.plan.get("status") != "confirmed":
            self._show_error("暂不能查找 Skill", "请先确认当前初始方案。", parent=self.root)
            return
        if self._skill_search_busy:
            return
        if self.session.skill_state.get("bindings") and not self._refresh_selected_catalog():
            self.refresh()
            return
        client = None
        ai_client_error = None
        missing = self._missing_generation_config()
        if missing:
            ai_client_error = f"未配置可用的 AI 模型：{'、'.join(missing)}。"
        else:
            try:
                client = self._client(self._api_config(timeout_seconds=self.preferences["search_model_timeout"]))
            except (ValueError, ApiError) as exc:
                ai_client_error = f"无法连接 AI 筛选服务：{exc}"
        request = {
            "kind": "local",
            "session_token": self._session_instance_token,
            "token": uuid4().hex,
            "basis": deepcopy(self._delivery_basis()),
            "key_works": deepcopy(self._key_works()),
            "task_text": self.session.task_text,
            "client": client,
            "ai_client_error": ai_client_error,
            "catalog": self.catalog,
            "preferences": dict(self.preferences),
            "skill_roots": self._skill_roots(),
        }
        request["previous_search_state"] = deepcopy(self.session.skill_state.get("search_state") or {})
        self._skill_search_request = request
        self._skill_search_busy = True
        self._skill_search_status_text = "正在查找本地 Skill…"
        self.skill_status_var.set(self._skill_search_status_text)
        self._record_skill_search_state(
            status="local_running",
            local={"status": "running", "count": 0},
            last_error=None,
        )
        self._refresh_delivery_pages()
        self._submit(
            lambda: self._local_skill_search_operation(request),
            lambda value: self._local_skill_search_ok(request, value),
            lambda exc: self._local_skill_search_error(request, exc),
        )

    def _network_skill_search_operation(self, request: dict[str, Any]):
        return search_network_skill_candidates(
            request["key_works"],
            task_text=request["task_text"],
            client=request["client"],
            token=request.get("github_token"),
            timeout_seconds=request.get("timeout_seconds", self.skill_search_timeout),
            opener=request.get("opener"),
            search_url=request["search_url"],
            web_search_url=request["web_search_url"],
            max_verified_candidates=request.get("preferences", self.preferences)["network_candidates"],
            review_options=self._skill_review_options(request.get("preferences", self.preferences)),
            cache_ttl_seconds=request.get("preferences", self.preferences)["network_cache_seconds"],
            progress=lambda message: self.completions.put((
                lambda value: self._network_skill_search_progress(request, value), message
            )),
        )

    def _network_skill_search_progress(self, request: dict[str, Any], message: str) -> None:
        if self._skill_search_is_current(request):
            self._skill_search_status_text = f"正在联网搜索 Skill：{message}"
            self.skill_status_var.set(self._skill_search_status_text)

    def _network_skill_search_ok(self, request: dict[str, Any], result: Any) -> None:
        if not self._skill_search_result_is_current(request):
            return
        if not result.candidates and result.error:
            message = result.error.get("message", "搜索来源暂不可用。")
            self._network_skill_search_error(request, SkillSearchError("network", message))
            return
        local_batch = self.session.skill_state.get("candidate_batch") or {}
        local_result = local_batch.get("result", {}) if isinstance(local_batch, dict) else {}
        local_candidates = local_result.get("candidates", []) if isinstance(local_result, dict) else []
        merged = merge_candidates(
            local_candidates,
            result.candidates,
            catalog_hash=str(local_batch.get("catalog_hash", "")) if isinstance(local_batch, dict) else "",
        )
        merged["query"] = result.query
        merged["network_batch_id"] = result.batch_id
        merged["network_catalog_hash"] = result.catalog_hash
        candidates = merged["result"]["candidates"]
        bindings = list(self.session.skill_state.get("bindings", []))
        status = "selected" if bindings else "candidates_ready" if candidates else "no_match"
        diagnostics = result.diagnostics if isinstance(result.diagnostics, dict) else {}
        source_errors = diagnostics.get("errors", [])
        source_errors = [str(error) for error in source_errors if isinstance(error, str) and error.strip()]
        source_diagnostics = diagnostics.get("source_diagnostics", {})
        source_summary = self._network_source_summary(source_diagnostics)
        try:
            self.session.set_skill_state(
                status=status,
                basis=self._delivery_basis(),
                candidate_batch=merged,
                bindings=bindings,
            )
        except SessionStateError as exc:
            self._network_skill_search_error(request, exc)
            return
        self._record_skill_search_state(
            status="network_done",
            network={
                "status": "ok" if result.candidates else "no_match",
                "count": len(result.candidates),
                "merged_count": len(candidates),
                "source_errors": source_errors,
                "source_diagnostics": deepcopy(source_diagnostics) if isinstance(source_diagnostics, dict) else {},
                "http": deepcopy(diagnostics.get("http", {})),
            },
            last_error=None,
        )
        self._finish_skill_search(request)
        if result.candidates:
            self._skill_search_status_text = (
                f"联网搜索完成：找到 {len(result.candidates)} 项候选；"
                f"合并后共 {len(candidates)} 项。"
            )
        else:
            self._skill_search_status_text = "联网搜索完成：没有找到新的候选，已保留本地结果。"
        if source_summary:
            self._skill_search_status_text += f" 来源状态：{source_summary}。"
        if source_errors:
            self._skill_search_status_text += f" 部分来源不可用：{source_errors[0][:120]}"
        access_issues = (diagnostics.get("http") or {}).get("access_issues", [])
        if access_issues:
            self._skill_search_status_text += " 已跳过被拒绝或受限的入口；可以选用现有结果，或稍后重试联网搜索。"
        self.skill_status_var.set(self._skill_search_status_text)
        logging.getLogger(__name__).info("Network Skill results accumulated: task=%s previous=%d incoming=%d total=%d selected=%d",
            self.session.task_id, len(local_candidates), len(result.candidates), len(candidates), len(bindings))
        self.refresh()

    @staticmethod
    def _network_source_summary(source_diagnostics: Any) -> str:
        """Render compact per-source counts so a completed search is explainable."""

        if not isinstance(source_diagnostics, dict):
            return ""
        labels = {
            "skill_index": "索引",
            "github": "GitHub",
            "open_web": "开放网页",
        }
        parts: list[str] = []
        for source in ("skill_index", "github", "open_web"):
            row = source_diagnostics.get(source)
            if not isinstance(row, dict):
                continue
            label = labels[source]
            if source == "open_web" and isinstance(row.get("search_engines"), list):
                engines = [name[:30] for name in row["search_engines"][:3] if isinstance(name, str) and name]
                if engines:
                    label += f"（{'→'.join(engines)}）"
            status = str(row.get("status") or "unknown")
            verified = row.get("collected_count", row.get("candidate_count", row.get("verified_count", 0)))
            try:
                verified_text = str(max(0, int(verified)))
            except (TypeError, ValueError):
                verified_text = "?"
            if status == "error":
                parts.append(f"{label}失败")
            elif status == "partial":
                parts.append(f"{label}部分可用，收集{verified_text}项")
            elif status == "no_match":
                parts.append(f"{label}无匹配")
            else:
                parts.append(f"{label}收集{verified_text}项")
        return "、".join(parts)

    def _network_skill_search_error(self, request: dict[str, Any], exc: Exception) -> None:
        if not self._skill_search_result_is_current(request):
            return
        self._record_skill_search_state(
            status="error",
            network={"status": "error", "count": 0},
            last_error=str(exc),
        )
        self._finish_skill_search(request)
        self._skill_search_status_text = f"联网搜索失败：{exc}；已有候选和已选 Skill 已保留。可以选用现有结果、跳过 Skill，或稍后重试联网搜索。"
        self.skill_status_var.set(self._skill_search_status_text)
        self.refresh()

    def search_online_skills(self) -> None:
        if self._return_to_unknown_questions():
            return
        if self.session.plan.get("status") != "confirmed":
            self._show_error("暂不能联网搜索", "请先确认当前初始方案。", parent=self.root)
            return
        if self._skill_search_busy:
            return
        search_state = self.session.skill_state.get("search_state") or {}
        if search_state.get("local") is None and not self._candidate_rows():
            self._show_info("请先查找本地 Skill", "先完成本地 Skill 查找，再决定是否继续联网搜索。", parent=self.root)
            return
        missing = self._missing_generation_config()
        if missing:
            self._skill_search_status_text = f"AI 联网筛选 Skill 需要先补全：{'、'.join(missing)}。"
            self.skill_status_var.set(self._skill_search_status_text)
            self.refresh()
            return
        try:
            client = self._client(self._api_config(timeout_seconds=self.preferences["search_model_timeout"]))
        except (ValueError, ApiError) as exc:
            self._skill_search_status_text = f"无法开始 AI 联网筛选 Skill：{exc}"
            self.skill_status_var.set(self._skill_search_status_text)
            self.refresh()
            return
        search_url = self.skill_search_url_var.get().strip() or "https://skills.sh"
        self.session.control["skill_search_url"] = self._normalized_skill_search_url()
        self.session.touch()
        request = {
            "kind": "network",
            "session_token": self._session_instance_token,
            "request_id": uuid4().hex,
            "basis": deepcopy(self._delivery_basis()),
            "search_url": search_url,
            "key_works": deepcopy(self._key_works()),
            "task_text": self.session.task_text,
            "client": client,
            "github_token": self.skill_search_token or os.environ.get("PROMPTSMITH_GITHUB_TOKEN"),
            "opener": self.skill_search_opener,
            "web_search_url": os.environ.get("PROMPTSMITH_WEB_SEARCH_URL", self.preferences["web_search_url"]),
            "timeout_seconds": self.skill_search_timeout,
            "preferences": dict(self.preferences),
        }
        request["previous_search_state"] = deepcopy(self.session.skill_state.get("search_state") or {})
        self._skill_search_request = request
        self._skill_search_busy = True
        self._skill_search_status_text = "正在联网搜索 Skill（并行：Skill 索引、GitHub、开放网页）：生成检索词并收集公开信息…"
        self.skill_status_var.set(self._skill_search_status_text)
        self._record_skill_search_state(
            status="network_running",
            network={"status": "running", "count": 0},
            last_error=None,
        )
        self._refresh_delivery_pages()
        self._submit(
            lambda: self._network_skill_search_operation(request),
            lambda value: self._network_skill_search_ok(request, value),
            lambda exc: self._network_skill_search_error(request, exc),
        )

    def _build_skill_browser(self, parent: ttk.Frame, prefix: str) -> ttk.Treeview:
        """The conversation and detail page share filters and table semantics."""
        parent.columnconfigure(0, weight=1)
        header = ttk.Frame(parent)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        ttk.Label(header, text="来源").pack(side="left")
        source = ttk.Combobox(header, textvariable=self.skill_source_filter_var,
                              values=SOURCE_FILTERS, state="readonly", width=10)
        source.pack(side="left", padx=6)
        source.bind("<<ComboboxSelected>>", lambda _event: self._skill_browser_filter_changed())
        show_all = ttk.Checkbutton(header, text="显示全部候选", variable=self.show_all_skills_var,
                                   command=self._skill_browser_filter_changed)
        show_all.pack(side="left", padx=6)
        self.widgets[prefix + "_source_filter"] = source
        self.widgets[prefix + "_show_all"] = show_all
        count = ttk.Label(parent, style="Muted.TLabel", wraplength=640)
        count.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        tree = self._tree(parent, ("status", "skill", "source", "score", "reason", "work"),
                          (85, 185, 150, 100, 290, 185), height=7)
        tree.heading("status", text="选用状态")
        tree.heading("score", text="推荐系数")
        tree.heading("reason", text="任务用途")
        tree.column("reason", stretch=True, minwidth=160)
        tree._promptsmith_container.grid(row=2, column=0, sticky="ew")
        tree.bind("<<TreeviewSelect>>", lambda _event: self._show_skill_browser_selection(prefix))
        self.widgets[prefix + "_candidates_tree"] = tree
        self.widgets[prefix + "_candidate_count"] = count
        if prefix == "conversation_skill":
            actions = ttk.Frame(parent)
            actions.grid(row=3, column=0, sticky="ew", pady=6)
            token = self._conversation_render_token
            for key, label, operation in (
                ("select_skills", "选用所选", self._select_skill_browser_rows),
                ("cancel_skills", "取消所选", self._cancel_skill_browser_rows),
            ):
                button = ttk.Button(actions, text=label, state="disabled",
                    command=lambda op=operation: self._conversation_action(token, lambda: op(prefix)))
                button.pack(side="left", padx=(0, 8))
                self.widgets[prefix + "_" + key] = button
                self._conversation_buttons[key] = button
            detail_frame, details = self._reading_text(parent, height=5)
            detail_frame.grid(row=4, column=0, sticky="ew", pady=(0, 6))
            self.widgets[prefix + "_details_text"] = details
        return tree

    def _skill_browser_filter_changed(self) -> None:
        logging.getLogger(__name__).debug("Skill table filter changed: task=%s source=%s show_all=%s",
            self.session.task_id, self.skill_source_filter_var.get(), self.show_all_skills_var.get())
        self.refresh()

    def _refresh_skill_browser(self, prefix: str) -> None:
        tree = self.widgets[prefix + "_candidates_tree"]
        previous = tree.selection()
        yview = tree.yview()[0]
        candidates = self._candidate_rows()
        bindings = self.session.skill_state.get("bindings", [])
        rows = table_rows(candidates, bindings)
        shown = visible_rows(rows, source=self.skill_source_filter_var.get(),
                             show_all=self.show_all_skills_var.get(), limit=self.preferences["display_limit"])
        lookup = getattr(self, "_skill_browser_lookup", {})
        lookup[prefix] = {row["candidate_id"]: row for row in rows}
        self._skill_browser_lookup = lookup
        work_titles = {row["key_work_id"]: row.get("title") or row["key_work_id"] for row in self._key_works()}
        self._fill_tree(prefix + "_candidates_tree", shown, "candidate_id", lambda row: (
            "已选快照" if row.get("_binding_only") else "已选" if row.get("_binding_ids") else
                "已选其他版本" if row.get("_already_selected") else
                "可选" if row.get("selection_allowed") else "不可选",
            row.get("name") or (row.get("record_snapshot") or {}).get("name") or row.get("skill_id", ""),
            self._candidate_display_source(row),
            "—" if row.get("_binding_only") else f"{recommendation_score(row):.2f}" +
                ("（初筛）" if row.get("ai_review_status") == "unavailable" else ""),
            " ".join(self._candidate_display_reason(row).split()),
            work_titles.get(row.get("key_work_id"), row.get("key_work_id", "")),
        ))
        retained = [key for key in previous if tree.exists(key)]
        if retained:
            tree.selection_set(*retained)
        tree.yview_moveto(yview)
        counts = {group: sum(source_group(row) == group for row in candidates) for group in ("本地", "联网", "内置")}
        self.widgets[prefix + "_candidate_count"].configure(text=(
            f"本地 {counts['本地']} · 联网 {counts['联网']} · 内置 {counts['内置']} · 已选 {len(bindings)} · 当前展示 {len(shown)} 项\n"
            "推荐名额在来源间分配，当前筛选内的已选项始终保留；系数 0～1 越高越推荐。选中行查看详情，Ctrl / Shift 可多选。"))
        self._show_skill_browser_selection(prefix)
        logging.getLogger(__name__).debug("Skill table rendered: task=%s table=%s source=%s counts=%s selected=%d shown=%d",
            self.session.task_id, prefix, self.skill_source_filter_var.get(), counts, len(bindings), len(shown))

    def _show_skill_browser_selection(self, prefix: str) -> None:
        tree = self.widgets.get(prefix + "_candidates_tree")
        if tree is None or not tree.winfo_exists():
            return
        lookup = getattr(self, "_skill_browser_lookup", {}).get(prefix, {})
        rows = [lookup[key] for key in tree.selection() if key in lookup]
        locked = self._conversation_locked()
        all_selected = bool(rows) and all(row.get("_already_selected") for row in rows)
        select_label = ("已选中该 Skill" if len(rows) == 1 else "所选 Skill 均已选中") if all_selected else (
            "选用此 Skill" if len(rows) == 1 else "选用所选")
        selectable = not locked and self._skill_basis_is_current() and any(
            row.get("selection_allowed") and not row.get("_already_selected") for row in rows)
        cancellable = any(row.get("_binding_ids") for row in rows)
        if prefix == "skill":
            cancellable = cancellable or bool(self.widgets["skill_selected_tree"].selection())
        select_key = "skill_select_button" if prefix == "skill" else prefix + "_select_skills"
        cancel_key = "skill_cancel_button" if prefix == "skill" else prefix + "_cancel_skills"
        self.widgets[select_key].configure(text=select_label, state="normal" if selectable else "disabled")
        self.widgets[cancel_key].configure(state="normal" if not locked and cancellable else "disabled")
        if prefix == "skill":
            self._show_selected_skill()
            return
        text = (self._candidate_detail_with_analysis(rows[0]) if len(rows) == 1 else
                f"已选中 {len(rows)} 行，可批量选用或取消；选中单行查看完整用途、来源和限制。" if rows else
                "选中一行查看完整用途、来源路径和限制；已选快照保留原选用内容。")
        self._set_text_widget(self.widgets[prefix + "_details_text"], text)

    def _select_skill_browser_rows(self, prefix: str) -> None:
        lookup = self._skill_browser_lookup.get(prefix, {})
        ids = [key for key in self.widgets[prefix + "_candidates_tree"].selection()
               if key in lookup and lookup[key].get("selection_allowed")
               and not lookup[key].get("_already_selected") and not lookup[key].get("_binding_only")]
        if ids:
            self.select_skill_candidates(ids)

    def _cancel_skill_browser_rows(self, prefix: str) -> None:
        lookup = self._skill_browser_lookup.get(prefix, {})
        ids = [binding_id for key in self.widgets[prefix + "_candidates_tree"].selection()
               for binding_id in lookup.get(key, {}).get("_binding_ids", [])]
        if ids:
            self.cancel_selected_skills(ids)

    def _candidate_rows(self) -> list[dict[str, Any]]:
        batch = self.session.skill_state.get("candidate_batch") or {}
        result = batch.get("result") if isinstance(batch, dict) else {}
        return list(result.get("candidates", [])) if isinstance(result, dict) else []

    @staticmethod
    def _candidate_display_reason(row: dict[str, Any]) -> str:
        record = row.get("record_snapshot") or {}
        return str(
            row.get("ai_relevance_reason")
            or row.get("match_reason")
            or row.get("description")
            or record.get("adaptation_summary")
            or record.get("description")
            or "查看详情"
        )

    @staticmethod
    def _candidate_display_source(row: dict[str, Any]) -> str:
        group = source_group(row)
        if group == "本地":
            return "本地文件"
        if group == "联网":
            source_url = row.get("source_url") or (row.get("record_snapshot") or {}).get("source_url")
            host = urlsplit(source_url).hostname if isinstance(source_url, str) else None
            return "联网 · " + host if host else "联网 Skill"
        return "内置目录"

    def select_skill_candidates(self, candidate_ids: list[str] | None = None) -> None:
        if not self._skill_basis_is_current():
            self._show_error("候选已过期", "当前方案已变化，请重新筛选本地目录。", parent=self.root)
            return
        selected_ids = list(self.widgets["skill_candidates_tree"].selection()) if candidate_ids is None else candidate_ids
        if not selected_ids:
            self._show_info("请选择候选", "请选择至少一个目录候选。", parent=self.root)
            return
        candidates = {row["candidate_id"]: row for row in self._candidate_rows()}
        existing = list(self.session.skill_state.get("bindings", []))
        previous_count = len(existing)
        seen = {(row.get("skill_id"), row.get("key_work_id"), row.get("usage_mode", "method_adaptation")) for row in existing}
        for candidate_id in selected_ids:
            candidate = candidates.get(candidate_id)
            if not candidate or not candidate.get("selection_allowed"):
                self._show_error("不能选用", "该候选当前不可选，可能缺少可用来源信息或与当前任务不兼容。", parent=self.root)
                return
            key = (candidate["skill_id"], candidate["key_work_id"], candidate.get("usage_mode", "method_adaptation"))
            if key in seen:
                continue
            record_snapshot = candidate.get("record_snapshot") or {}
            prerequisite_source = (
                "remote_source_review"
                if candidate.get("origin") == "remote" or record_snapshot.get("origin") == "remote"
                else "catalog_evidence"
            )
            existing.append({
                "binding_id": f"binding-{uuid4().hex}",
                "skill_id": candidate["skill_id"],
                "record_hash": candidate["record_hash"],
                "record_snapshot": record_snapshot,
                "key_work_id": candidate["key_work_id"],
                "step_ids": list(candidate.get("step_ids", [])),
                "usage_mode": candidate.get("usage_mode", "method_adaptation"),
                "capability_ids": list(candidate.get("capability_ids", [])),
                "precondition_assessments": [
                    {"prerequisite_id": value, "status": "unknown", "source": prerequisite_source}
                    for value in candidate.get("adaptation_prerequisite_ids", [])
                ],
                "origin": candidate.get("origin", "local"),
                "source_kind": candidate.get("source_kind", candidate.get("origin", "local")),
                "source_url": candidate.get("source_url") or candidate.get("record_snapshot", {}).get("source_url", ""),
                "repository": candidate.get("repository") or candidate.get("record_snapshot", {}).get("repository", ""),
                "fixed_commit": candidate.get("fixed_commit") or candidate.get("record_snapshot", {}).get("fixed_commit", ""),
                "verification_status": candidate.get("verification_status") or candidate.get("record_snapshot", {}).get("verification", {}).get("verification_status", "unknown"),
                "method_adaptation_allowed": bool(candidate.get("method_adaptation_allowed", True)),
                "limitations": list(candidate.get("limitations", [])),
            })
            seen.add(key)
        if len(existing) == previous_count:
            logging.getLogger(__name__).debug("Duplicate Skill selection ignored: task=%s requested=%d selected=%d",
                self.session.task_id, len(selected_ids), previous_count)
            return
        self.session.set_skill_state(
            status="selected",
            basis=self.session.skill_state.get("basis"),
            candidate_batch=self.session.skill_state.get("candidate_batch"),
            bindings=existing,
        )
        self.skill_status_var.set(f"已选用 {len(existing)} 项 Agent Skill；尚未整合为最终草稿。")
        logging.getLogger(__name__).info("Skill selection updated: task=%s requested=%d selected=%d",
            self.session.task_id, len(selected_ids), len(existing))
        self.refresh()

    def cancel_selected_skills(self, binding_ids: list[str] | None = None) -> None:
        selected_ids = set(self.widgets["skill_selected_tree"].selection() if binding_ids is None else binding_ids)
        if binding_ids is None:
            lookup = getattr(self, "_skill_browser_lookup", {}).get("skill", {})
            selected_ids.update(binding_id for key in self.widgets["skill_candidates_tree"].selection()
                                for binding_id in lookup.get(key, {}).get("_binding_ids", []))
        if not selected_ids:
            return
        had_final_result = self.session.final_result.get("status") in {"draft", "confirmed", "stale"}
        bindings = [row for row in self.session.skill_state.get("bindings", []) if row.get("binding_id") not in selected_ids]
        self.session.set_skill_state(
            status="selected" if bindings else "candidates_ready",
            basis=self.session.skill_state.get("basis"),
            candidate_batch=self.session.skill_state.get("candidate_batch"),
            bindings=bindings,
        )
        self.skill_status_var.set("已取消选中的 Agent Skill；需要重新整合最终草稿。")
        logging.getLogger(__name__).info("Skill selection cancelled: task=%s requested=%d remaining=%d",
            self.session.task_id, len(selected_ids), len(bindings))
        self.refresh()
        if had_final_result:
            self.status_var.set("已取消 Agent Skill 选用；原最终结果已过期，请重新整合并确认。")
            self.final_status_var.set("最终结果已过期（Agent Skill 选用已变化），请重新整合并确认。")

    def skip_skills(self) -> None:
        if self._return_to_unknown_questions():
            return
        try:
            self.session.set_skill_state(status="skipped", basis=self._delivery_basis(), candidate_batch=self.session.skill_state.get("candidate_batch"), bindings=[])
            self.generate_no_skill_final()
        except SessionStateError as exc:
            self._show_error("无法跳过 Skill", str(exc), parent=self.root)

    def analyze_skill_candidates(self) -> None:
        if self.delivery_busy:
            return
        missing = self._missing_generation_config()
        if missing:
            message = f"AI分析候选需要先补全：{'、'.join(missing)}。候选和现有分析会保留。"
            self._set_delivery_feedback(message)
            self._show_info("需要模型配置", message, parent=self.root)
            return
        if not self._skill_basis_is_current() or not self._candidate_rows():
            self._show_info("尚无可分析候选", "请先基于当前已确认方案筛选 Agent Skill 候选。", parent=self.root)
            return
        try:
            config = self._api_config()
            request_id = f"m3-{uuid4().hex}"
            payload = self.delivery_workflow.prepare_m3(
                request_id, connection_version=self.connection_version
            )
        except (DeliveryWorkflowError, SessionStateError, ValueError) as exc:
            logging.getLogger(__name__).exception("M3 request preparation failed; task=%s", self.session.task_id)
            message = generation_failure_message("m3", exc, None)
            self._set_delivery_feedback(message)
            self._show_error("无法分析候选", message, parent=self.root)
            self.refresh()
            return
        self._start_delivery_request("m3", payload, config)

    def integrate_selected_skills(self) -> None:
        if self._return_to_unknown_questions():
            return
        if self.delivery_busy:
            return
        if not self._skill_basis_is_current() or self.session.skill_state.get("status") != "selected":
            self._show_error("Agent Skill 选用已过期", "请基于当前已确认方案重新筛选并选用 Agent Skill。", parent=self.root)
            return
        if not self.session.skill_state.get("bindings"):
            self._show_info("尚未选用 Agent Skill", "请先选用至少一个 Agent Skill，或选择全部跳过。", parent=self.root)
            return
        missing = self._missing_generation_config()
        if missing:
            message = f"AI整合所选 Agent Skill 需要先补全：{'、'.join(missing)}。也可点击“用已选 Skill 直接生成提示词”，保留当前选择。"
            self._set_delivery_feedback(message)
            self._show_info("需要模型配置", message, parent=self.root)
            return
        try:
            config = self._api_config()
            request_id = f"m4-{uuid4().hex}"
            payload = self.delivery_workflow.prepare_m4(
                request_id, connection_version=self.connection_version
            )
        except (DeliveryWorkflowError, SessionStateError, ValueError) as exc:
            logging.getLogger(__name__).exception("M4 request preparation failed; task=%s", self.session.task_id)
            message = generation_failure_message("m4", exc, None)
            self._set_delivery_feedback(message)
            self._show_error("无法准备 Agent Skill 整合", message, parent=self.root)
            self.refresh()
            return
        self._start_delivery_request("m4", payload, config)

    def _start_delivery_request(self, purpose: str, payload: dict[str, Any], config: ApiConfig) -> None:
        if self.delivery_busy:
            return
        workflow = self.delivery_workflow
        request = {
            "purpose": purpose,
            "request_id": payload["request_id"],
            "payload": payload,
            "connection_version": self.connection_version,
            "session_token": self._session_instance_token,
            "workflow": workflow,
            "timeout_seconds": config.timeout_seconds,
        }
        self._active_delivery_request = request
        self.delivery_busy = True
        self._set_delivery_feedback("正在进行 AI 候选分析…" if purpose == "m3" else "正在用 AI 整合所选 Agent Skill…")
        self._refresh_delivery_controls()
        client = self._client(config)
        if purpose == "m3":
            operation = lambda: workflow.invoke_m3(
                payload,
                client,
                protocol=config.protocol,
                configured_model=config.model,
                request_parameters=json_request_parameters(config),
            )
        else:
            operation = lambda: workflow.invoke_m4(
                payload,
                client,
                protocol=config.protocol,
                configured_model=config.model,
                request_parameters=json_request_parameters(config),
            )
        self._submit(
            operation,
            lambda outcome: self._apply_delivery_response(request, outcome),
            lambda exc: self._delivery_request_failed(request, exc),
        )

    def _delivery_request_is_current(self, request: dict[str, Any]) -> bool:
        active = self._active_delivery_request
        return bool(
            self.delivery_busy
            and active is request
            and request["session_token"] == self._session_instance_token
            and request["workflow"] is self.delivery_workflow
        )

    def _apply_delivery_response(self, request: dict[str, Any], outcome: Any) -> None:
        if not self._delivery_request_is_current(request):
            return
        workflow = request["workflow"]
        purpose = request["purpose"]
        if purpose == "m4" and not self._refresh_selected_catalog():
            self._finish_delivery_request(request)
            self.refresh()
            return
        try:
            if purpose == "m3":
                workflow.apply_m3(
                    request["payload"],
                    outcome,
                    connection_version=request["connection_version"],
                    current_session_token=self._session_instance_token,
                )
            else:
                workflow.apply_m4(
                    request["payload"],
                    outcome,
                    connection_version=request["connection_version"],
                    current_session_token=self._session_instance_token,
                )
        except DeliveryStaleResponseError as exc:
            logging.getLogger(__name__).warning("%s response discarded as stale; request=%s", purpose, request["request_id"], exc_info=True)
            self._finish_delivery_request(request)
            self._set_delivery_feedback(f"模型返回时来源已变化，本次结果已丢弃：{exc}。请重新选择 Skill 或生成提示词。")
            self.refresh()
            return
        except Exception as exc:
            logging.getLogger(__name__).exception("%s response application failed; request=%s", purpose, request["request_id"])
            self._finish_delivery_request(request)
            message = generation_failure_message(purpose, exc, request.get("timeout_seconds"))
            self._set_delivery_feedback(f"AI{'分析' if purpose == 'm3' else '整合'}失败；原有结果已保留。{message}")
            self.status_var.set(message)
            self._show_error("AI调用未接收", message, parent=self.root)
            self.refresh()
            return

        self._finish_delivery_request(request)
        if purpose == "m3":
            self._set_delivery_feedback("AI候选分析完成；分析结果仅供参考，请自行选用或忽略候选。")
            self.refresh()
            self.notebook.select(2)
        else:
            self._set_delivery_feedback("已将所选 Skill 的来源和任务用途写入提示词；未知和建议随正文保留，可直接复制或导出。")
            self.status_var.set("Skill 整合草稿已生成；后置建议已写入提示词，可到结果页确认。")
            self.refresh()
            if self.notebook.index(self.notebook.select()) == 0:
                self._conversation_scroll_latest(force=True)
            else:
                self.notebook.select(3)

    def _delivery_request_failed(self, request: dict[str, Any], exc: Exception) -> None:
        if not self._delivery_request_is_current(request):
            return
        request["workflow"].cancel(request["request_id"])
        self._finish_delivery_request(request)
        message = generation_failure_message(request["purpose"], exc, request.get("timeout_seconds"))
        self._set_delivery_feedback(f"AI调用未完成；现有候选和最终结果已保留：{message}")
        self.status_var.set(message)
        self.refresh()
        self._show_error("AI调用失败", message, parent=self.root)

    def _finish_delivery_request(self, request: dict[str, Any]) -> None:
        if self._active_delivery_request is not request:
            return
        self.delivery_busy = False
        self._active_delivery_request = None
        self._refresh_delivery_controls()

    def _delivery_feedback_basis(self) -> tuple[Any, ...]:
        return (self._session_instance_token, self._delivery_basis(), self.session.skill_state.get("revision", 0))

    def _set_delivery_feedback(self, message: str) -> None:
        self._delivery_status_text = message
        self._delivery_status_basis = self._delivery_feedback_basis()
        self.skill_status_var.set(message)

    def cancel_delivery_request(self) -> None:
        self.cancel_active_request()

    def cancel_active_request(self) -> None:
        """Stop work in this session without clearing its answers or results."""
        if not self._conversation_locked():
            return
        request = self._active_delivery_request
        operation_token = self._active_stop_token
        search_request = self._skill_search_request
        stage = self.busy_kind or ("delivery" if request is not None else "skill_search")
        if request is not None:
            request["_stream_cancelled"] = True
            request["workflow"].cancel(request["request_id"])
            self._finish_delivery_request(request)
        self._cancel_session_tasks("user_stop", reset_skill_view=False)
        self.session.pending_requests.clear()
        self._skill_search_request = None
        self._skill_search_busy = False
        if search_request is not None:
            key = "local" if search_request.get("kind") == "local" else "network"
            prior = (search_request.get("previous_search_state") or {}).get(key)
            source = deepcopy(prior) if isinstance(prior, dict) and prior.get("status") != "running" else {"status": "cancelled", "count": 0}
            self._record_skill_search_state(status="cancelled", **{key: source}, last_error=None)
            self._skill_search_status_text = "已停止 Skill 搜索，已有候选与选择保留；可重新查找或继续联网搜索。"
            self.skill_status_var.set(self._skill_search_status_text)
        self._response_deliveries.clear()
        for record in self._trace_records.values():
            if (record.get("status") == "working" or record.get("operation") == operation_token
                    or request is not None and record.get("delivery_request_id") == request["request_id"]):
                record["status"] = "cancelled"
                record["elapsed"] = time.monotonic() - self._trace_started.get(record["id"], time.monotonic())
                widget = self._trace_widgets.get(record["id"])
                if widget is not None:
                    widget.close()
                    widget.finish()
        feedback = "已停止本次处理，自动重试已取消。已有回答和成果已保留；可继续整理或重新生成。"
        if request is not None:
            self._set_delivery_feedback(feedback)
        self.session.touch()
        self._set_busy(False, feedback)
        self.refresh()
        logging.getLogger(__name__).info("User stopped active request; task=%s stage=%s; retries_disabled=True results_preserved=True",
                                        self.session.task_id, stage)

    def _reset_delivery_workflow(self) -> None:
        self._delivery_status_text = ""
        self._delivery_status_basis = None
        active = self._active_delivery_request
        if active is not None:
            active["workflow"].cancel(active["request_id"])
        self._active_delivery_request = None
        self.delivery_busy = False
        self._skill_search_request = None
        self._skill_search_busy = False
        self._skill_search_status_text = ""
        self._selected_skill_binding_id = None
        self._session_instance_token = uuid4().hex
        self.delivery_workflow = DeliveryWorkflow(
            self.session,
            evidence_root=self.evidence_root,
            session_instance_token=self._session_instance_token,
        )
        self._refresh_delivery_controls()

    def _refresh_delivery_controls(self) -> None:
        self._refresh_selected_catalog()
        if "skill_cancel_request_button" in self.widgets:
            self.widgets["skill_cancel_request_button"].configure(
                state="normal" if self.delivery_busy else "disabled"
            )
        if "skill_analyze_button" in self.widgets:
            available = self._skill_basis_is_current() and bool(self._candidate_rows())
            self.widgets["skill_analyze_button"].configure(
                state="normal" if available and not self.delivery_busy and not self.busy else "disabled"
            )
        if "skill_integrate_button" in self.widgets:
            available = (
                self._skill_basis_is_current()
                and self.session.skill_state.get("status") == "selected"
                and bool(self.session.skill_state.get("bindings"))
            )
            self.widgets["skill_integrate_button"].configure(
                state="normal" if available and not self.delivery_busy and not self.busy else "disabled"
            )
            self.widgets["skill_direct_button"].configure(
                state="normal" if available and not self.delivery_busy and not self.busy and not self._skill_search_busy else "disabled"
            )
        self._refresh_primary_action()

    def update_selected_skill_prerequisite(self) -> None:
        selected = self.widgets["skill_prerequisites_tree"].selection()
        if len(selected) != 1 or not self._selected_skill_binding_id:
            self._show_info("请选择适配前提", "先选择一项适配前提，再保存核对结果。", parent=self.root)
            return
        statuses = {"已满足": "satisfied", "仍未知": "unknown", "不兼容": "incompatible"}
        status = statuses.get(self.skill_prerequisite_status_var.get())
        if status is None:
            self._show_error("核对结果无效", "请选择满足、仍未知或不兼容。", parent=self.root)
            return
        bindings = deepcopy(self.session.skill_state.get("bindings", []))
        binding = next((row for row in bindings if row.get("binding_id") == self._selected_skill_binding_id), None)
        if binding is None:
            self._show_error("Agent Skill 选用已变化", "请重新选择当前有效的 Agent Skill。", parent=self.root)
            return
        prerequisite_id = selected[0]
        assessment = next(
            (row for row in binding.get("precondition_assessments", []) if row.get("prerequisite_id") == prerequisite_id),
            None,
        )
        if assessment is None:
            self._show_error("前提已变化", "该前提已不属于当前绑定，请重新选择。", parent=self.root)
            return
        assessment["status"] = status
        assessment["source"] = "user_reported"
        try:
            self.session.set_skill_state(
                status="selected",
                basis=self.session.skill_state.get("basis"),
                candidate_batch=self.session.skill_state.get("candidate_batch"),
                bindings=bindings,
            )
        except SessionStateError as exc:
            self._show_error("无法保存前提判断", str(exc), parent=self.root)
            return
        self.skill_status_var.set("适配前提已记录为用户说明；此前草稿因来源变化需要重新整合。")
        self.refresh()

    def _show_selected_skill_prerequisite(self) -> None:
        selected = self.widgets["skill_prerequisites_tree"].selection()
        if len(selected) != 1 or not self._selected_skill_binding_id:
            return
        binding = next(
            (row for row in self.session.skill_state.get("bindings", []) if row.get("binding_id") == self._selected_skill_binding_id),
            None,
        )
        if binding is None:
            return
        assessment = next(
            (row for row in binding.get("precondition_assessments", []) if row.get("prerequisite_id") == selected[0]),
            None,
        )
        if assessment:
            labels = {"satisfied": "已满足", "unknown": "仍未知", "incompatible": "不兼容"}
            self.skill_prerequisite_status_var.set(labels.get(assessment.get("status"), "仍未知"))

    def _show_selected_m4_change(self) -> None:
        selected = self.widgets["m4_changes_tree"].selection()
        if len(selected) != 1:
            self._set_text_widget(self.widgets["m4_change_details_text"], "选择一项 M4 变化查看内容。")
            self.widgets["accept_m4_change_button"].configure(state="disabled")
            self.widgets["reject_m4_change_button"].configure(state="disabled")
            return
        row = next(
            (item for item in self.session.final_result.get("content", {}).get("pending_changes", [])
             if item.get("change_id") == selected[0]),
            None,
        )
        if row is None:
            return
        decision = row.get("decision", "pending")
        hard = bool(row.get("affects_hard_constraints"))
        self._set_text_widget(
            self.widgets["m4_change_details_text"],
            f"变化：{row.get('text', row.get('description', ''))}\n"
            f"原因：{row.get('reason', '无')}\n"
            f"类型：{row.get('kind', '未标注')}\n"
            f"影响已确认硬约束：{'是' if hard else '否'}\n"
            f"当前决定：{'待处理' if decision == 'pending' else '已拒绝'}",
        )
        enabled = decision == "pending" and not self.delivery_busy
        self.widgets["accept_m4_change_button"].configure(
            state="normal" if enabled and not hard else "disabled"
        )
        self.widgets["reject_m4_change_button"].configure(state="normal" if enabled else "disabled")

    def _refresh_m4_change_actions(self) -> None:
        if self.widgets["m4_changes_tree"].selection():
            self._show_selected_m4_change()
        else:
            self.widgets["accept_m4_change_button"].configure(state="disabled")
            self.widgets["reject_m4_change_button"].configure(state="disabled")

    def accept_selected_m4_change(self) -> None:
        self._decide_selected_m4_change("accepted")

    def reject_selected_m4_change(self) -> None:
        self._decide_selected_m4_change("rejected")

    def _decide_selected_m4_change(self, decision: str) -> None:
        selected = self.widgets["m4_changes_tree"].selection()
        if len(selected) != 1:
            self._show_info("请选择变化", "请先选择一项待处理的 M4 变化。", parent=self.root)
            return
        change_id = selected[0]
        row = next(
            (item for item in self.session.final_result.get("content", {}).get("pending_changes", [])
             if item.get("change_id") == change_id),
            None,
        )
        if row is None:
            self._show_error("变化已过期", "该变化已不属于当前最终草稿。", parent=self.root)
            return
        if decision == "accepted" and row.get("affects_hard_constraints"):
            self._show_info("不能接受该变化", "该变化影响已确认硬约束，请回到需求或方案阶段处理。", parent=self.root)
            return
        try:
            decide_m4_change(self.session, change_id, decision)
        except (DeliveryValidationError, SessionStateError) as exc:
            self._show_error("无法处理 M4 变化", str(exc), parent=self.root)
            return
        self.status_var.set("M4变化已接受；请继续处理其余变化并复核最终草稿。" if decision == "accepted" else "M4变化已拒绝；请继续处理其余变化并复核最终草稿。")
        self.refresh()

    def generate_no_skill_final(self) -> None:
        if self.busy or self.delivery_busy or self._skill_search_busy:
            return
        if self._return_to_unknown_questions():
            return
        try:
            draft = build_final_draft(self.session)
            stage_final_draft(self.session, draft, expected_basis=draft["basis"])
        except (DeliveryValidationError, SessionStateError) as exc:
            self._show_error("无法生成最终草稿", str(exc), parent=self.root)
            return
        has_skills = bool(self.session.skill_state.get("bindings"))
        if has_skills:
            self._set_delivery_feedback("已用当前选用的 Skill 生成提示词；格式和前提待下游 AI 核对，可以复制或导出。")
        logging.getLogger(__name__).info("Generated prompt directly; selected_skills=%d", len(self.session.skill_state.get("bindings", [])))
        self.final_status_var.set("提示词已生成，可以复制或导出。")
        self.status_var.set("已保留所选 Skill 的名称、来源和用途；未验证信息由下游 AI 继续核对。" if has_skills else "提示词已从当前已确认方案生成。")
        self.refresh()
        if self.notebook.index(self.notebook.select()) == 0:
            self._conversation_scroll_latest(force=True)
        else:
            self.notebook.select(3)







    def _show_selected_skill(self) -> None:
        selected = self.widgets["skill_candidates_tree"].selection()
        if len(selected) != 1:
            self._set_text_widget(self.widgets["skill_details_text"], "选中单行查看完整用途、来源和限制；Ctrl / Shift 可多选。")
            return
        row = getattr(self, "_skill_browser_lookup", {}).get("skill", {}).get(selected[0])
        if row is None:
            return
        self._set_text_widget(self.widgets["skill_details_text"], self._candidate_detail_with_analysis(row))

    def _candidate_detail_with_analysis(self, row: dict[str, Any]) -> str:
        details = self._skill_detail_text(row, binding=bool(row.get("_binding_only")))
        if row.get("_already_selected") and not row.get("_binding_ids"):
            details += "\n\n此 Skill 已用于该关键工作，当前选用的是其他来源或版本。可在已选快照中查看、取消，再选用此版本。"
        batch = self.session.skill_state.get("candidate_batch") or {}
        analysis = batch.get("m3_analysis", {}).get("result", {}) if isinstance(batch, dict) else {}
        assessment = next(
            (item for item in analysis.get("assessments", []) if item.get("candidate_id") == row.get("candidate_id")),
            None,
        ) if isinstance(analysis, dict) else None
        if assessment:
            decision_labels = {"recommend": "建议匹配", "conditional": "有条件匹配", "no_match": "不建议匹配"}
            details += "\n\nAI候选分析（仅供参考）：\n"
            details += f"判断：{decision_labels.get(assessment.get('decision'), assessment.get('decision', ''))}\n"
            details += f"理由：{assessment.get('reason', '无')}\n"
            details += f"计划输入：{'；'.join(assessment.get('planned_inputs', [])) or '未提供'}\n"
            details += f"预期输出：{'；'.join(assessment.get('expected_outputs', [])) or '未提供'}\n"
            details += f"限制：{'；'.join(assessment.get('limitations', [])) or '未提供'}"
        return details

    def _show_selected_skill_binding(self) -> None:
        self._show_skill_browser_selection("skill")
        selected = self.widgets["skill_selected_tree"].selection()
        self._selected_skill_binding_id = selected[0] if len(selected) == 1 else None
        self._fill_tree("skill_prerequisites_tree", [], "prerequisite_id", lambda _row: ("", "", ""))
        if len(selected) != 1:
            self.widgets["skill_update_prerequisite_button"].configure(state="disabled")
            return
        row = next((item for item in self.session.skill_state.get("bindings", []) if item.get("binding_id") == selected[0]), None)
        if row:
            record = row.get("record_snapshot") or {}
            assessments = {
                item.get("prerequisite_id"): item
                for item in row.get("precondition_assessments", [])
                if isinstance(item, dict)
            }
            prerequisite_rows = []
            seen: set[str] = set()
            for item in record.get("adaptation_prerequisites", []):
                prerequisite_id = item.get("prerequisite_id")
                if not prerequisite_id:
                    continue
                seen.add(prerequisite_id)
                assessment = assessments.get(prerequisite_id, {})
                prerequisite_rows.append({
                    "prerequisite_id": prerequisite_id,
                    "description": item.get("description", prerequisite_id),
                    "status": assessment.get("status", "unknown"),
                    "source": assessment.get("source", "catalog_evidence"),
                })
            for prerequisite_id, assessment in assessments.items():
                if prerequisite_id not in seen:
                    prerequisite_rows.append({
                        "prerequisite_id": prerequisite_id,
                        "description": assessment.get("description", prerequisite_id),
                        "status": assessment.get("status", "unknown"),
                        "source": assessment.get("source", "catalog_evidence"),
                    })
            self._fill_tree(
                "skill_prerequisites_tree",
                prerequisite_rows,
                "prerequisite_id",
                lambda item: (
                    item["description"],
                    {"satisfied": "已满足", "unknown": "仍未知", "incompatible": "不兼容"}.get(item["status"], item["status"]),
                    {"user_reported": "用户说明", "catalog_evidence": "目录证据", "program_check": "程序检查"}.get(item["source"], item["source"]),
                ),
            )
            self.widgets["skill_update_prerequisite_button"].configure(
                state="normal" if prerequisite_rows and not self.delivery_busy else "disabled"
            )
            details = self._skill_detail_text(row, binding=True)
            result_content = self.session.final_result.get("content")
            contributions = result_content.get("skill_contributions", []) if isinstance(result_content, dict) else []
            related = [
                item for item in contributions
                if row.get("binding_id") in set(item.get("origin_binding_ids", [])) | {item.get("binding_id")}
            ]
            if related:
                lines = [details, "已整合的 Agent Skill 指令："]
                for item in related:
                    lines.extend([
                        f"- 行动：{'；'.join(item.get('method_actions', [])) or '未列出'}",
                        f"  输入：{'；'.join(item.get('planned_inputs', [])) or '未列出'}",
                        f"  输出：{'；'.join(item.get('expected_outputs', [])) or '未列出'}",
                        f"  检查点：{'；'.join(item.get('checkpoints', [])) or '未列出'}",
                        f"  替代做法：{'；'.join(item.get('fallback_actions', [])) or '未列出'}",
                    ])
                details = "\n".join(lines)
            self._set_text_widget(self.widgets["skill_details_text"], details)

    @staticmethod
    def _skill_usage_mode_label(value: Any) -> str:
        if value == "method_adaptation":
            return "参考 Agent Skill 指令"
        return str(value or "未标注")

    @staticmethod
    def _skill_detail_text(row: dict[str, Any], *, binding: bool = False) -> str:
        record = row.get("record_snapshot") if isinstance(row.get("record_snapshot"), dict) else {}
        lines = [
            f"{'已选 Agent Skill' if binding else 'Agent Skill'}：{record.get('name', row.get('skill_id', ''))}",
            f"用于关键工作：{row.get('key_work_id', '')}",
            f"参考内容：{PromptSmithApp._skill_usage_mode_label(row.get('usage_mode', 'method_adaptation'))}",
            f"{'绑定编号' if binding else '候选编号'}：{row.get('binding_id', row.get('candidate_id', ''))}",
            f"来源类型：{'联网 Skill' if row.get('origin', record.get('origin')) == 'remote' else '本地文件' if row.get('origin', record.get('origin')) == 'local_file' else '内置目录'}",
            f"来源：{row.get('source_path', record.get('source_path', '目录快照'))}",
            f"简介：{row.get('description') or record.get('description', '未提供')}",
            f"适配理由：{row.get('match_reason', '待查看')}",
            f"适配说明：{record.get('adaptation_summary', '无')}",
            "能力与输入输出：",
        ]
        if not binding:
            lines.append(f"推荐系数：{recommendation_score(row):.2f}（相对推荐强度，不是成功概率）")
            lines.append(f"评分依据：{row.get('recommendation_basis', '历史匹配记录，当前未重新核验')}")
        if row.get("origin", record.get("origin")) == "remote":
            source_url = row.get("source_url") or record.get("source_url") or row.get("repository") or record.get("repository")
            if source_url:
                lines.insert(6, f"Skill 地址：{source_url}")
            hash_kind = row.get("provenance", {}).get("content_hash_kind") or record.get("content_hash_kind") or "未说明"
            lines.insert(7, f"来源版本：{row.get('fixed_commit') or record.get('fixed_commit') or '未固定'}；证据哈希（{hash_kind}）：{row.get('content_sha256') or record.get('content_sha256') or '未记录'}")
            lines.insert(8, "联网候选仅作 Skill 指令参考，尚未安装，也不会自动执行远程内容。")
        evidence_level = row.get("evidence_level")
        if not evidence_level:
            verification = record.get("verification") if isinstance(record.get("verification"), dict) else {}
            evidence_level = "full_skill" if verification.get("source_read") else "metadata"
        evidence_labels = {
            "skill_excerpt": "SKILL.md 节选（完整文件哈希已核验）",
            "full_skill": "已读取 Skill 内容",
            "metadata": "公开元数据或 README 摘要",
            "search_result": "搜索结果线索",
            "search_result_only": "搜索结果线索",
        }
        evidence_basis = row.get("evidence_basis") or []
        lines.append(f"当前证据：{evidence_labels.get(evidence_level, evidence_level)}" + (f"（{'、'.join(evidence_basis)}）" if evidence_basis else ""))
        limitations = row.get("evidence_limitations") or row.get("limitations") or []
        if limitations:
            lines.append(f"信息限制：{'；'.join(str(item) for item in limitations if item)}")
        if row.get("ai_review_status") == "unavailable":
            lines.append("AI 筛选状态：暂不可用，当前候选仅作参考。")
        capabilities = {
            item.get("capability_id"): item
            for item in record.get("capabilities", [])
            if isinstance(item, dict)
        }
        capability_ids = row.get("capability_ids", [])
        if capability_ids:
            for capability_id in capability_ids:
                capability = capabilities.get(capability_id, {})
                lines.extend([
                    f"- {capability_id}：{capability.get('summary', '未提供能力说明')}",
                    f"  输入：{'；'.join(capability.get('inputs', [])) or '未列出'}",
                    f"  输出：{'；'.join(capability.get('outputs', [])) or '未列出'}",
                    f"  限制：{'；'.join(capability.get('limitations', [])) or '无'}",
                ])
        else:
            lines.append("- 无已选能力")

        prerequisite_rows = [
            item for item in record.get("adaptation_prerequisites", []) if isinstance(item, dict)
        ]
        assessments = {
            item.get("prerequisite_id"): item
            for item in row.get("precondition_assessments", [])
            if isinstance(item, dict)
        }
        lines.append("Agent Skill 使用前提：")
        if prerequisite_rows:
            for prerequisite in prerequisite_rows:
                prerequisite_id = prerequisite.get("prerequisite_id", "")
                assessment = assessments.get(prerequisite_id, {})
                status = assessment.get("status", "unknown")
                status_label = {
                    "satisfied": "已满足",
                    "unsatisfied": "未满足",
                    "incompatible": "不兼容",
                    "unknown": "未知",
                }.get(status, status)
                blocking = assessment.get("blocking", prerequisite.get("blocking", False))
                lines.append(
                    f"- {prerequisite.get('description', prerequisite_id)}；状态：{status_label}；"
                    f"{'阻断' if blocking else '非阻断'}；来源：{_PREREQUISITE_SOURCE_LABELS.get(assessment.get('source'), assessment.get('source', '目录记录'))}"
                )
        else:
            lines.append("- 无额外适配前提")
        if binding:
            declared_ids = {item.get("prerequisite_id") for item in prerequisite_rows}
            for prerequisite_id, assessment in assessments.items():
                if prerequisite_id not in declared_ids:
                    lines.append(
                        f"- {prerequisite_id}；状态：{assessment.get('status', 'unknown')}；"
                        f"{'阻断' if assessment.get('blocking') else '非阻断'}；来源：{_PREREQUISITE_SOURCE_LABELS.get(assessment.get('source'), assessment.get('source', '用户复核'))}"
                    )
        lines.append(f"兼容性：{row.get('compatibility', '已选')}")
        return "\n".join(lines)

    def change_final_tone(self) -> None:
        if not self._refresh_selected_catalog():
            self.refresh()
            return
        tone = "polite" if self.final_tone_var.get() == "适度礼貌" else "neutral"
        try:
            set_final_tone(self.session, tone)
        except DeliveryValidationError as exc:
            self.status_var.set(str(exc))
            return
        logging.getLogger(__name__).info("Final prompt tone changed; task=%s tone=%s", self.session.task_id, tone)
        self.refresh()

    def confirm_final_result(self) -> None:
        if not self._refresh_selected_catalog():
            self.refresh()
            return
        try:
            revision = confirm_final(self.session)
        except (DeliveryValidationError, SessionStateError) as exc:
            self._show_error("暂不能确认最终结果", str(exc), parent=self.root)
            return
        self.status_var.set(f"已确认最终结果版本 {revision}。")
        self.refresh()

    def copy_final_prompt(self) -> None:
        result = self.session.final_result
        body = result.get("canonical_body")
        if not self._refresh_selected_catalog():
            self.refresh()
            return
        try:
            validate_current_final(self.session, require_confirmed=True)
        except DeliveryValidationError as exc:
            self._show_info("不能复制正式提示", f"当前结果尚未确认或已经过期。\n{exc}", parent=self.root)
            return
        prompt = render_task_prompt(body, result.get("tone", "neutral"))
        self.root.clipboard_clear()
        self.root.clipboard_append(prompt)
        self.status_var.set("已复制当前已确认的正式提示。")

    def copy_draft_prompt(self) -> None:
        result = self.session.final_result
        status = result.get("status")
        body = result.get("canonical_body")
        if not body or status not in {"draft", "stale"}:
            self._show_info("暂无可复制草稿", "只有草稿或来源已变化的结果可通过“复制草稿提示”复制。", parent=self.root)
            return
        if status == "draft":
            try:
                validate_current_final(self.session)
            except DeliveryValidationError as exc:
                self._show_error("草稿来源无效", str(exc), parent=self.root)
                return
        prompt = render_task_prompt(body, result.get("tone", "neutral"))
        self.root.clipboard_clear()
        self.root.clipboard_append(prompt)
        if status == "stale":
            self.status_var.set("已复制过期草稿；来源已变化，请勿当作正式结果。")
        else:
            self.status_var.set("已复制草稿提示，尚未确认。")

    def _export_delivery(self, mode: str) -> None:
        try:
            self._sync_input()
        except SessionStateError as exc:
            self._show_error("导出失败", str(exc), parent=self.root)
            return
        session_at_start = self.session
        session_token = self._session_instance_token
        session_snapshot = session_at_start.to_dict()

        default = f"{self.session.task_id}_{'final' if mode == 'final' else 'draft'}.md"
        target = filedialog.asksaveasfilename(parent=self.root, title="导出 Markdown", initialfile=default,
                                            initialdir=self.preferences["export_directory"] or None,
                                            defaultextension=".md", filetypes=[("Markdown", "*.md")])
        if not target:
            return

        def export_basis_is_current() -> bool:
            if self.session is not session_at_start or self._session_instance_token != session_token:
                return False
            self._sync_input()
            return self.session.to_dict() == session_snapshot

        try:
            if not export_basis_is_current():
                raise DeliveryValidationError("选择导出位置期间会话内容已变化，请复核后重新导出。")
            overwrite = Path(target).expanduser().resolve().exists()
            if overwrite and not messagebox.askyesno(
                "确认覆盖",
                f"文件已存在，是否覆盖？\n{Path(target).expanduser().resolve()}",
                parent=self.root,
            ):
                return
            if not export_basis_is_current():
                raise DeliveryValidationError("确认导出期间会话内容已变化，请复核后重新导出。")
            path = export_markdown(self.session, target, mode=mode, overwrite=overwrite)
        except (OSError, ValueError, DeliveryValidationError, SessionStateError) as exc:
            self._show_error("导出失败", str(exc), parent=self.root)
            return
        self.status_var.set(f"已导出：{path}")

    def export_final_markdown(self) -> None:
        if not self._refresh_selected_catalog():
            self.refresh()
            return
        self._export_delivery("final")

    def export_draft_markdown(self) -> None:
        self._export_delivery("draft")

    def add_final_note(self) -> None:
        text = simpledialog.askstring("添加用户附注", "附注内容：", parent=self.root)
        if not text:
            return
        try:
            edit_final_note(self.session, f"note-{uuid4().hex}", text)
        except DeliveryValidationError as exc:
            self._show_error("无法添加附注", str(exc), parent=self.root)
            return
        self.status_var.set("用户附注已加入草稿，最终确认已撤销。")
        logging.getLogger(__name__).info("Final prompt note added; task=%s revision=%s characters=%s", self.session.task_id,
                                        self.session.final_result.get("revision"), len(text))
        self.refresh()

    def _selected_m2_suggestion(self) -> dict[str, Any] | None:
        selected = self.widgets["m2_suggestions_tree"].selection()
        if len(selected) != 1:
            return None
        content = self.session.plan.get("content") or {}
        return next(
            (row for row in content.get("suggestions", []) if row.get("suggestion_id") == selected[0]),
            None,
        )

    def _show_selected_m2_suggestion(self) -> None:
        row = self._selected_m2_suggestion()
        if row is None:
            self._set_text_widget(self.widgets["m2_suggestion_details_text"], "请选择一项建议查看详情。")
            return
        decisions = {
            item.get("suggestion_id"): item.get("decision")
            for item in self.session.final_result.get("suggestion_decisions", [])
        }
        decision = decisions.get(row.get("suggestion_id"), "pending")
        decision_label = {"pending": "待决定", "accepted": "已接受", "rejected": "已拒绝"}.get(decision, decision)
        lines = [
            f"建议：{row.get('text', '')}",
            f"理由：{row.get('reason', '未说明')}",
            f"类型：{row.get('kind', '未分类')}",
            f"当前决定：{decision_label}",
        ]
        if row.get("requires_user_confirmation"):
            lines.append("影响：可能改变范围或重要决定；需返回初始方案处理，不能在此直接接受。")
        else:
            lines.append("影响：可作为可选优化；接受后会明确加入最终提示。")
        self._set_text_widget(self.widgets["m2_suggestion_details_text"], "\n".join(lines))
        self._refresh_m2_suggestion_actions()

    def _refresh_m2_suggestion_actions(self) -> None:
        row = self._selected_m2_suggestion()
        result = self.session.final_result
        decisions = {
            item.get("suggestion_id"): item.get("decision")
            for item in result.get("suggestion_decisions", [])
        }
        current_final = result.get("status") in {"draft", "confirmed"}
        if current_final:
            try:
                validate_current_final(self.session)
            except DeliveryValidationError:
                current_final = False
        pending = bool(row) and decisions.get(row.get("suggestion_id"), "pending") == "pending"
        self.widgets["accept_m2_suggestion_button"].configure(
            state="normal" if current_final and pending and not row.get("requires_user_confirmation") else "disabled"
        )
        self.widgets["reject_m2_suggestion_button"].configure(
            state="normal" if current_final and pending else "disabled"
        )
        self.widgets["process_m2_suggestion_button"].configure(
            state="normal" if pending and row.get("requires_user_confirmation") else "disabled"
        )

    def accept_selected_m2_suggestion(self) -> None:
        row = self._selected_m2_suggestion()
        if row is None:
            self._show_info("请选择建议", "请选择一项 M2 建议。", parent=self.root)
            return
        try:
            decide_m2_suggestion(self.session, row["suggestion_id"], "accepted")
        except DeliveryValidationError as exc:
            self._show_error("无法接受建议", str(exc), parent=self.root)
            return
        self.status_var.set("已接受选中的 M2 建议；最终结果仍需重新确认。")
        self.refresh()

    def reject_selected_m2_suggestion(self) -> None:
        row = self._selected_m2_suggestion()
        if row is None:
            self._show_info("请选择建议", "请选择一项 M2 建议。", parent=self.root)
            return
        try:
            decide_m2_suggestion(self.session, row["suggestion_id"], "rejected")
        except DeliveryValidationError as exc:
            self._show_error("无法拒绝建议", str(exc), parent=self.root)
            return
        self.status_var.set("已拒绝选中的 M2 建议；该建议不会进入执行要求。")
        self.refresh()

    def process_selected_m2_suggestion(self) -> None:
        row = self._selected_m2_suggestion()
        if row is None:
            self._show_info("请选择建议", "请选择一项需要上游处理的 M2 建议。", parent=self.root)
            return
        if not row.get("requires_user_confirmation"):
            self._show_info("无需上游处理", "该建议可在此接受或拒绝。", parent=self.root)
            return
        target = next(
            (
                label
                for label, (kind, item_id) in self._plan_section_lookup.items()
                if kind == "suggestion" and item_id == row.get("suggestion_id")
            ),
            None,
        )
        if target is None:
            self._show_error("无法定位建议", "当前方案中找不到这项建议，请重新生成方案。", parent=self.root)
            return
        self.notebook.select(1)
        self.plan_section_var.set(target)
        self.widgets["plan_section_combo"].focus_set()

    def _final_review_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        plan = self.session.plan
        content = plan.get("content") if isinstance(plan.get("content"), dict) else {}
        key_work = {row.get("key_work_id"): row for row in content.get("key_work", [])}
        for key_work_id in plan.get("pending_key_work_review_ids", []):
            item = key_work.get(key_work_id, {})
            rows.append({
                "review_id": f"key_work:{key_work_id}",
                "kind": "关键工作复核",
                "text": item.get("title", key_work_id),
                "status": "待复核",
                "action": "key_work",
                "target_id": key_work_id,
                "details": "返回初始方案页，选中该关键工作并使用现有“标记已复核”操作。",
            })
        requirement_by_id = {row.get("item_id"): row for row in self.session.requirements}
        for item_id in self.session.pending_review_item_ids:
            item = requirement_by_id.get(item_id, {})
            rows.append({
                "review_id": f"requirement:{item_id}",
                "kind": "需求复核",
                "text": item.get("text", item_id),
                "status": "待复核",
                "action": "requirement",
                "target_id": item_id,
                "details": "返回需求页，选中该项并使用现有“标记已复核”操作。",
            })
        for gap in self.session.gaps:
            if gap.get("importance") == "blocking_direction":
                gap_id = gap.get("gap_id", "")
                rows.append({
                    "review_id": f"gap:{gap_id}",
                    "kind": "方向阻断项",
                    "text": gap.get("description", gap_id),
                    "status": "需先处理",
                    "action": "requirements",
                    "target_id": gap_id,
                    "details": "该未知会影响任务方向。返回需求页回答相关问题，或明确调整任务范围。",
                })

        binding_by_prerequisite: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
        for binding in self.session.skill_state.get("bindings", []):
            record = binding.get("record_snapshot") or {}
            prerequisite_map = {
                item.get("prerequisite_id"): item
                for item in record.get("adaptation_prerequisites", [])
                if isinstance(item, dict)
            }
            for assessment in binding.get("precondition_assessments", []):
                if isinstance(assessment, dict):
                    binding_by_prerequisite[assessment.get("prerequisite_id")] = (binding, prerequisite_map.get(assessment.get("prerequisite_id"), {}))
        final_content = self.session.final_result.get("content") or {}
        contributions = final_content.get("skill_contributions", [])
        pending_changes = final_content.get("pending_changes", [])
        live_binding_ids = {
            row.get("binding_id") for row in self.session.skill_state.get("bindings", [])
            if row.get("binding_id")
        }
        for review_id in blocking_review_required_ids(self.session):
            if review_id.startswith("m4-change:"):
                _, request_id, change_id = (review_id.split(":", 2) + [None, None])[0:3]
                change = next((
                    row for row in pending_changes
                    if row.get("change_id") == change_id
                    and (row.get("generation_request_id") or self.session.final_result.get("generation_request_id")) == request_id
                ), None)
                if change is not None:
                    rows.append({
                        "review_id": review_id,
                        "kind": "M4变化决定",
                        "text": change.get("text", change.get("description", change_id)),
                        "status": "待处理",
                        "action": "m4_change",
                        "target_id": change_id,
                        "details": "返回导出页并接受或拒绝这项 Agent Skill 建议。",
                    })
                    continue

            if review_id.startswith("m4-fallback-required:"):
                _, request_id, change_id = (review_id.split(":", 2) + [None, None])[0:3]
                affected: list[str] = []
                for contribution in contributions:
                    disabled = contribution.get("disabled_by_rejected_changes", [])
                    if not any(
                        isinstance(item, dict)
                        and item.get("generation_request_id") == request_id
                        and item.get("change_id") == change_id
                        for item in disabled
                    ):
                        continue
                    origins = list(contribution.get("origin_binding_ids", []))
                    if contribution.get("binding_id"):
                        origins.append(contribution["binding_id"])
                    affected.extend(binding_id for binding_id in origins if binding_id in live_binding_ids)
                affected = list(dict.fromkeys(affected))
                if affected:
                    change = next((
                        item for item in pending_changes
                        if item.get("change_id") == change_id
                        and (item.get("generation_request_id") or self.session.final_result.get("generation_request_id")) == request_id
                    ), None)
                    rows.append({
                        "review_id": review_id,
                        "kind": "Skill 替代指引",
                        "text": (change or {}).get("text", "被拒绝的 Skill 建议没有可用替代步骤。"),
                        "status": "需先处理",
                        "action": "fallback_binding",
                        "target_id": affected,
                        "details": "返回 Skill 页取消相关 Agent Skill，再重新生成最终草稿。",
                    })
                    continue

            found = binding_by_prerequisite.get(review_id)
            if found:
                binding, prerequisite = found
                rows.append({
                    "review_id": f"prerequisite:{binding.get('binding_id')}:{review_id}",
                    "kind": "Agent Skill 使用前提",
                    "text": prerequisite.get("description", review_id),
                    "status": "待复核",
                    "action": "binding",
                    "target_id": binding.get("binding_id"),
                    "details": f"当前判断：{review_id}；返回 Skill 页核对前提，或取消该 Agent Skill。",
                })
            else:
                rows.append({
                    "review_id": f"final:{review_id}",
                    "kind": "最终结果复核",
                    "text": review_id,
                    "status": "待复核",
                    "action": "plan",
                    "target_id": review_id,
                    "details": "该结果要求人工复核；先回到对应方案或 Skill 内容检查来源。",
                })
        return rows

    def _show_selected_final_review_item(self) -> None:
        selected = self.widgets["final_review_items_tree"].selection()
        if len(selected) != 1:
            self._set_text_widget(self.widgets["final_review_details_text"], "当前没有选中的阻断项。")
            self.widgets["process_final_review_item_button"].configure(state="disabled")
            return
        row = self._final_review_lookup.get(selected[0])
        if row is None:
            self.widgets["process_final_review_item_button"].configure(state="disabled")
            return
        self._set_text_widget(
            self.widgets["final_review_details_text"],
            f"{row['kind']}：{row['text']}\n处理入口：{row['details']}",
        )
        self.widgets["process_final_review_item_button"].configure(state="normal")

    def process_selected_final_review_item(self) -> None:
        selected = self.widgets["final_review_items_tree"].selection()
        if len(selected) != 1 or selected[0] not in self._final_review_lookup:
            self._show_info("请选择复核项", "请选择一项阻断或待复核内容。", parent=self.root)
            return
        row = self._final_review_lookup[selected[0]]
        action = row["action"]
        target_id = row["target_id"]
        if action == "key_work":
            self.notebook.select(1)
            self.widgets["plan_key_work_tree"].selection_set(target_id)
            self.widgets["plan_key_work_tree"].see(target_id)
            self._show_selected_key_work()
        elif action == "requirement":
            self.notebook.select(0)
            if self._workspace_popover is None or self._workspace_popover.kind!="requirements":
                self.toggle_requirements_review()
            tree=self.widgets["conversation_requirements_tree"]
            key="r:"+target_id
            if tree.exists(key):
                tree.selection_set(key)
                tree.see(key)
                self._conversation_show_requirement_selection()
        elif action == "requirements":
            self.show_workspace(0)
            question = next(
                (item for item in self.session.questions_for_review() if item.get("gap_id") == target_id),
                None,
            )
            self.question_context_var.set(
                self._format_guided_question_card(question)
                if question else f"还没确定：{row['text']}。请在这里补充。"
            )
            self.widgets["conversation_input"].focus_set()
        elif action == "binding":
            self.notebook.select(2)
            self.widgets["skill_selected_tree"].selection_set(target_id)
            self.widgets["skill_selected_tree"].see(target_id)
            self._show_selected_skill_binding()
            self.widgets["skill_cancel_button"].focus_set()
        elif action == "fallback_binding":
            binding_ids = target_id if isinstance(target_id, list) else [target_id]
            self.notebook.select(2)
            self.widgets["skill_selected_tree"].selection_set(*binding_ids)
            if binding_ids:
                self.widgets["skill_selected_tree"].see(binding_ids[0])
            self._show_selected_skill_binding()
            self.widgets["skill_cancel_button"].focus_set()
        elif action == "m4_change":
            self.notebook.select(3)
            tree = self.widgets["m4_changes_tree"]
            tree.selection_set(target_id)
            tree.see(target_id)
            self._show_selected_m4_change()
            decision_button = self.widgets["accept_m4_change_button"]
            if str(decision_button.cget("state")) == "disabled":
                decision_button = self.widgets["reject_m4_change_button"]
            decision_button.focus_set()
        else:
            self.notebook.select(1)
            self.widgets["plan_section_combo"].focus_set()

    def _refresh_delivery_pages(self) -> None:
        plan_confirmed = self.session.plan.get("status") == "confirmed"
        self.notebook.tab(2, state="normal" if plan_confirmed else "disabled")
        export_available = plan_confirmed or self.session.final_result.get("status") in {"draft", "confirmed", "stale"}
        self.notebook.tab(3, state="normal" if export_available else "disabled")
        candidates = self._candidate_rows()
        if "skill_candidates_tree" in self.widgets:
            self._refresh_skill_browser("skill")
            bindings = self.session.skill_state.get("bindings", [])
            selected_tree = self.widgets["skill_selected_tree"]
            selected_before = selected_tree.selection()
            self._fill_tree("skill_selected_tree", bindings, "binding_id", lambda row: (
                (row.get("record_snapshot") or {}).get("name") or row.get("skill_id", ""),
                row.get("key_work_id", ""), self._skill_usage_mode_label(row.get("usage_mode")), "已选"
            ))
            retained_bindings = [key for key in selected_before if selected_tree.exists(key)]
            if retained_bindings:
                selected_tree.selection_set(*retained_bindings)
            basis_current = self._skill_basis_is_current()
            search_state = self.session.skill_state.get("search_state") or {}
            local_state = search_state.get("local") if isinstance(search_state, dict) else None
            local_ready = isinstance(local_state, dict) and local_state.get("status") in {
                "ok", "no_match", "error", "cancelled"
            }
            search_running = self._skill_search_busy
            self.widgets["skill_find_button"].configure(
                state=(
                    "normal"
                    if plan_confirmed and not search_running and not self.delivery_busy
                    else "disabled"
                )
            )
            self.widgets["skill_online_button"].configure(
                state=(
                    "normal"
                    if plan_confirmed and local_ready and not search_running and not self.delivery_busy
                    else "disabled"
                )
            )
            self._show_skill_browser_selection("skill")
            self.widgets["skill_integrate_button"].configure(
                state=(
                    "normal"
                    if basis_current and self.session.skill_state.get("status") == "selected" and bindings
                    and not self.delivery_busy and not self.busy
                    else "disabled"
                )
            )
            self.widgets["skill_analyze_button"].configure(
                state=(
                    "normal"
                    if basis_current and plan_confirmed and candidates and not self.delivery_busy and not self.busy
                    else "disabled"
                )
            )
            self.widgets["skill_skip_button"].configure(
                state="normal" if plan_confirmed and not self.delivery_busy and not search_running else "disabled"
            )
            status = self.session.skill_state.get("status", "not_started")
            if self._delivery_status_text and self._delivery_status_basis == self._delivery_feedback_basis():
                status_text = self._delivery_status_text
            elif self._skill_search_status_text:
                status_text = self._skill_search_status_text
            elif search_state.get("status") == "error" and search_state.get("last_error"):
                status_text = search_state["last_error"]
            elif search_state.get("status") == "local_done":
                count = (search_state.get("local") or {}).get("count", len(candidates))
                status_text = f"本地找到 {count} 项候选。" if count else "本地查找完成：没有找到适配候选，可继续联网搜索或跳过。"
            elif search_state.get("status") == "network_done":
                count = (search_state.get("network") or {}).get("count", 0)
                merged_count = (search_state.get("network") or {}).get("merged_count", len(candidates))
                status_text = (
                    f"联网搜索完成：找到 {count} 项候选；合并后共 {merged_count} 项。"
                    if count else "联网搜索完成：没有找到新的候选。"
                )
                source_summary = self._network_source_summary(
                    (search_state.get("network") or {}).get("source_diagnostics", {})
                )
                if source_summary:
                    status_text += f" 来源状态：{source_summary}。"
            else:
                status_label={"not_started":"尚未开始","collecting":"正在收集","analyzing":"正在筛选",
                              "searching":"正在搜索","ready":"已完成","failed":"未完成",
                              "stale":"需要重新搜索"}.get(status,"等待更新")
                status_text = self.session.skill_state.get("last_error") or f"目录状态：{status_label}"
            if bindings and not basis_current:
                status_text += "；绑定来源已过期，请重新筛选"
            batch = self.session.skill_state.get("candidate_batch") or {}
            if isinstance(batch, dict) and batch.get("m3_analysis"):
                status_text += "；候选已完成 AI 分析"
            self.skill_status_var.set(status_text)
            self._refresh_delivery_controls()
        if "final_preview_text" in self.widgets:
            result = self.session.final_result
            status_labels = {"not_started": "未生成", "draft": "草稿待确认", "confirmed": "已确认", "stale": "来源已变化，需重建"}
            self.final_status_var.set(f"最终结果：{status_labels.get(result.get('status'), result.get('status'))} · 版本 {result.get('revision', 0)}")
            tone = "适度礼貌" if result.get("tone") == "polite" else "中性"
            self.final_tone_var.set(tone)
            preview = self.widgets["final_preview_text"]
            body = result.get("canonical_body") or "尚未生成最终草稿。"
            self._set_text_widget(preview, body)
            task_prompt = result.get("canonical_body")
            self._set_text_widget(
                self.widgets["final_task_prompt_text"],
                render_task_prompt(task_prompt, result.get("tone", "neutral"))
                if task_prompt else "尚未生成最终任务提示。",
            )

            try:
                validate_current_final(self.session, require_confirmed=True)
            except DeliveryValidationError:
                formal_copy = False
            else:
                formal_copy = True
            draft_copy = result.get("status") in {"draft", "stale"} and bool(result.get("canonical_body"))
            self.widgets["copy_final_button"].configure(state="normal" if formal_copy else "disabled")
            self.widgets["copy_draft_button"].configure(state="normal" if draft_copy else "disabled")
            if result.get("status") == "stale":
                self.final_status_var.set(
                    f"最终结果已过期，不能正式复制或确认 · 版本 {result.get('revision', 0)}"
                )

            suggestions = list((self.session.plan.get("content") or {}).get("suggestions", []))
            decisions = {
                row.get("suggestion_id"): row.get("decision")
                for row in result.get("suggestion_decisions", [])
            }
            suggestion_rows = []
            for row in suggestions:
                decision = decisions.get(row.get("suggestion_id"), "pending")
                suggestion_rows.append({**row, "decision": decision})
            self._fill_tree(
                "m2_suggestions_tree",
                suggestion_rows,
                "suggestion_id",
                lambda row: (
                    row.get("text", ""),
                    row.get("kind", ""),
                    {"pending": "待决定", "accepted": "已接受", "rejected": "已拒绝"}.get(row.get("decision"), row.get("decision", "")),
                ),
            )
            self._set_text_widget(
                self.widgets["m2_suggestion_details_text"],
                "选择一项建议查看理由、影响和处理入口。" if suggestion_rows else "当前方案没有 M2 建议。",
            )
            self._refresh_m2_suggestion_actions()

            pending_changes = [
                row for row in (result.get("content") or {}).get("pending_changes", [])
                if row.get("change_id")
            ]
            self._fill_tree(
                "m4_changes_tree",
                pending_changes,
                "change_id",
                lambda row: (
                    row.get("text", row.get("description", "")),
                    row.get("kind", ""),
                    "待使用时补充" if row.get("decision", "pending") == "pending" else "已拒绝",
                ),
            )
            self._set_text_widget(
                self.widgets["m4_change_details_text"],
                "选择一项后置建议查看内容；未采纳的建议不会阻止确认和导出。" if pending_changes else "当前没有后置建议。",
            )
            self._refresh_m4_change_actions()

            review_rows = self._final_review_rows()
            self._final_review_lookup = {row["review_id"]: row for row in review_rows}
            review_tree = self.widgets["final_review_items_tree"]
            previous_selection = review_tree.selection()
            self._fill_tree(
                "final_review_items_tree",
                review_rows,
                "review_id",
                lambda row: (row.get("kind", ""), row.get("text", ""), row.get("status", "")),
            )
            retained_selection = tuple(item for item in previous_selection if review_tree.exists(item))
            if retained_selection:
                review_tree.selection_set(*retained_selection)
            self._set_text_widget(
                self.widgets["final_review_details_text"],
                "当前没有阻断或待复核项。" if not review_rows else "选择一项查看对应处理入口。",
            )
            self._show_selected_final_review_item()
    def _legacy_next_step_text(self) -> str:
        if self.session.open_conflicts:
            return "下一步：处理仍未解决的冲突，再继续确认。"
        if self.session.questions_for_review():
            return "下一步：回答、跳过或标记不确定；候选草稿会保留。"
        if self.session.pending_proposals:
            return "下一步：核对模型候选，选择接受或忽略。"
        if self.session.pending_review_item_ids:
            return "下一步：查看受修改影响的需求，并标记已复核。"
        if any(
            row.get("assessment_status") == "pending"
            for row in self.session.question_history
        ):
            return "下一步：继续分析刚才的回答；在模型建议通过校验前，相关未知仍保留。"
        if self.session.confirmed_requirements_version == self.session.requirement_version:
            if self.session.plan.get("status") == "stale":
                return "下一步：当前旧方案已过期，请基于重新确认的需求生成新方案。"
            if self.session.plan.get("status") == "draft":
                return "下一步：切换到“初始方案”页，核对并复核当前方案草稿。"
            if self.session.plan.get("status") == "confirmed":
                return f"下一步：{self._delivery_primary_action().reason}"
            return "下一步：基于当前已确认需求生成完整初始方案。"
        if (
            self.session.requirements
            and self.session.analysis_basis_version == self.session.requirement_version
        ):
            return "下一步：核对当前有效需求；无误后确认当前版本。"
        return "下一步：开始或继续分析当前任务。"

    def _source_text(self, refs: list[dict[str, Any]]) -> str:
        sources = {row["source_id"]: row for row in self.session.sources}
        lines = []
        for ref in refs:
            source = sources.get(ref.get("source_id"), {})
            role = "用户原话" if source.get("role") == "user" else "来源"
            lines.append(f"{role}：{ref.get('quote', '')}")
        return "\n".join(lines) or "无"

    def _show_selected_details(self, record_type: str) -> None:
        tree_name = {
            "requirement": "requirements_tree",
            "proposal": "proposals_tree",
            "question": "questions_tree",
        }[record_type]
        selected = self.widgets[tree_name].selection()
        if len(selected) != 1:
            return
        row_id = selected[0]
        if record_type == "requirement":
            row = next((item for item in self.session.requirements if item["item_id"] == row_id), None)
            if row is None:
                return
            lines = [
                "需求详情",
                f"完整内容：{row['text']}",
                f"来源类型：{KIND_LABELS.get(row['kind'], row['kind'])}",
                f"约束强度：{STRENGTH_LABELS.get(row['strength'], row['strength'])}",
                f"适用范围：{row['scope']}",
                f"确认状态：{CONFIRMATION_LABELS.get(row['confirmation'], row['confirmation'])}",
                f"来源原话：\n{self._source_text(row.get('source_refs', []))}",
            ]
        elif record_type == "proposal":
            row = next((item for item in self.session.pending_proposals if item["proposal_id"] == row_id), None)
            if row is None:
                return
            old = next(
                (item for item in self.session.requirements if item["item_id"] == row.get("target_item_id")),
                None,
            )
            lines = [
                "候选详情",
                f"动作：{OPERATION_LABELS.get(row['operation'], row['operation'])}",
                f"修改前：{old['text'] if old else '无（新增）'}",
                f"修改后：{row['text'] if row['operation'] != 'withdraw' else '撤回该需求'}",
                f"来源类型：{KIND_LABELS.get(row['kind'], row['kind'])}",
                f"约束强度：{STRENGTH_LABELS.get(row['strength'], row['strength'])}",
                f"适用范围：{row['scope']}",
                f"提出理由：{row.get('reason', '无')}",
                f"来源原话：\n{self._source_text(row.get('source_refs', []))}",
            ]
        else:
            row = next((item for item in self.session.questions_for_review() if item["question_id"] == row_id), None)
            if row is None:
                return
            options = "、".join(row.get("options", [])) or "自由回答"
            lines = [
                "问题详情",
                f"完整问题：{row['text']}",
                f"适用范围：{row['scope']}",
                f"可选回答：{options}",
                f"提问原因：{row.get('reason', '无')}",
            ]
        widget = self.widgets["details_text"]
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", "\n".join(lines))
        widget.configure(state="disabled")

    def _fill_tree(
        self, name: str, rows: list[dict[str, Any]], id_key: str, values: Callable[[dict[str, Any]], tuple[Any, ...]]
    ) -> None:
        tree: ttk.Treeview = self.widgets.get(name)
        if tree is None:
            return
        tree.delete(*tree.get_children())
        for row in rows:
            tree.insert("", "end", iid=row[id_key], values=values(row))

    @staticmethod
    def _set_text_widget(widget: tk.Text, value: str) -> None:
        was_disabled = str(widget.cget("state")) == "disabled"
        if was_disabled:
            widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        if was_disabled:
            widget.configure(state="disabled")

    def new_session(self) -> None:
        if not messagebox.askyesno("新建会话", "新建会话？请先保存当前内容。", parent=self.root):
            return
        self._install_session(self._new_preferred_session(), reason="new_session")
        self.status_var.set("已新建会话。")

    def _install_session(self, session: SessionState, *, path=None, reason="open_session") -> None:
        """Install an already loaded checkpoint on the owner thread."""
        self._cancel_session_tasks(reason)
        self.session = session
        self.workflow = Phase12Workflow(self.session, self.assets, self.evidence_root, self.m2_assets)
        self._reset_delivery_workflow()
        self._set_busy(False)
        self.session_path = Path(path) if path else None
        self._rendered_plan_token = None
        self.widgets["task_text"].delete("1.0", "end")
        self.widgets["task_text"].insert("1.0", session.task_text)
        self._reset_guided_view()
        self.category_var.set(CATEGORY_LABELS.get(session.selected_category, "自动判断"))
        self.skill_search_url_var.set(session.control.get("skill_search_url")
            or os.environ.get("PROMPTSMITH_SKILL_SEARCH_URL", self.preferences["skill_search_url"]))
        self.thinking_level_var.set(session.control.get("thinking_level", "standard"))
        self.thinking_level_display_var.set({
            "quick": "快速：先把基本任务说清", "standard": "标准：补齐常见关键信息",
            "deep": "深入：系统梳理复杂任务",
        }.get(self.thinking_level_var.get(), "标准：补齐常见关键信息"))
        drafts = session.control.get("workspace_drafts", {})
        if isinstance(drafts, dict):
            self._question_drafts = dict(drafts.get("answers", {}))
            self.widgets["conversation_input"].insert("1.0", drafts.get("message", ""))
            target = drafts.get("reanswer")
            if target and any(q.get("question_id") == target for q in session.question_history):
                self._answer_target_id = target
                self.question_context_var.set(next(q.get("text", "") for q in session.question_history if q.get("question_id") == target))
        # Navigation may have rendered empty question inputs before drafts were
        # installed. Do not harvest those empty controls over the restored text.
        self._question_inputs = {}
        self._conversation_signature = None
        self.refresh()
        logging.getLogger(__name__).info("Conversation checkpoint installed: task=%s reason=%s", session.task_id, reason)

    def open_session(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="打开PromptSmith会话",
            filetypes=[("PromptSmith JSON", "*.json"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            session = load_session(path)
        except Exception as exc:
            self._show_error("打开失败", str(exc), parent=self.root)
            return
        self._install_session(session, path=path)
        self.status_var.set(f"已打开：{path}")

    def save(self, *, save_as: bool = False) -> None:
        target = self.session_path
        try:
            logging.getLogger("promptsmith.ui").debug("Session save started; save_as=%s", save_as)
            if save_as or target is None:
                default_dir = Path(self.preferences["session_directory"]).expanduser() if self.preferences["session_directory"] else application_data_dir() / "sessions"
                default_dir.mkdir(parents=True, exist_ok=True)
                chosen = filedialog.asksaveasfilename(
                    parent=self.root,
                    title="保存PromptSmith会话",
                    initialdir=default_dir,
                    initialfile=f"{self.session.task_id}.json",
                    defaultextension=".json",
                    filetypes=[("PromptSmith JSON", "*.json")],
                )
                if not chosen:
                    logging.getLogger("promptsmith.ui").debug("Session save cancelled by user")
                    return
                target = Path(chosen)
            self._sync_input()
            self.session.control["skill_search_url"] = self._normalized_skill_search_url()
            self.session_path = save_session(self.session, target)
        except Exception as exc:
            message = f"{exc}\n\n请在设置 → 会话与导出中更换可写的会话目录，再从文件菜单选择另存为重试。原文件和当前会话已保留。"
            self.status_var.set("会话保存失败，请更换目录后重试。")
            self._show_error("保存失败", message, parent=self.root)
            return
        self.status_var.set(f"已保存：{self.session_path}")
        logging.getLogger("promptsmith.ui").info("Session saved: %s", self.session_path)

    def close(self) -> None:
        self.shutdown(wait=False)
        self.root.destroy()

    def shutdown(self, *, wait: bool) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        self._close_response_view()
        self.typography.close()
        self._session_tasks.cancel()
        self._application_tasks.cancel()
        logging.getLogger(__name__).info("Desktop shutting down; wait_for_workers=%s", wait)
        if self.debug_console is not None:
            self.debug_console.close()
            self.debug_console = None
        if self._tk_root.report_callback_exception == self._report_callback_exception:
            self._tk_root.report_callback_exception = self._previous_callback_exception
        if self._active_delivery_request is not None:
            request = self._active_delivery_request
            request["workflow"].cancel(request["request_id"])
            self._active_delivery_request = None
            self.delivery_busy = False
        if self._completion_after_id:
            self.root.after_cancel(self._completion_after_id)
            self._completion_after_id = None
        if self._wheel_binding_registered:
            for widget in self._wheel_bound_widgets:
                try:
                    widget.bindtags(tuple(tag for tag in widget.bindtags() if tag != self._wheel_bindtag))
                except tk.TclError:
                    pass
            self._wheel_bound_widgets.clear()
            try:
                self.root.unbind_class(self._wheel_bindtag, "<MouseWheel>")
            except tk.TclError:
                pass
            self._wheel_binding_registered = False
            self._reset_wheel_accumulator()
        self.executor.shutdown(wait=wait, cancel_futures=True)
        for executor in self._retired_executors:
            executor.shutdown(wait=wait, cancel_futures=True)
        self._retired_executors.clear()
        if self._owns_runtime_log:
            self.runtime_log.close()
