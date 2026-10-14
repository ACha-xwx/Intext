"""WebView2 Debug presentation; all data here is independent of Tk objects."""
from copy import deepcopy
import ast
import logging
import os
import re
import threading
from uuid import uuid4

from .paths import resource_root

LOG = logging.getLogger(__name__)


def concise_message(message, level):
    """Shorten known routine events; preserve failures and unknown messages."""
    if level >= logging.WARNING or "\n" in message:
        return message
    scoring_started = re.fullmatch(r"AI Skill scoring started: mode=(summary|source) candidates=(\d+) input_chars=(\d+)", message)
    if scoring_started:
        return f"AI 正在{'按简介评分' if scoring_started[1] == 'summary' else '复核内容'}：{scoring_started[2]} 项 Skill"
    scoring_done = re.fullmatch(r"AI Skill selection completed: shortlisted=(\d+) reviewed=(\d+) selected=(\d+) calls=(\d+) input_chars=(\d+) low_score_rejected=(\d+) mode=(summary|source)", message)
    if scoring_done:
        return f"Skill {'简介评分' if scoring_done[7] == 'summary' else '内容复核'}完成：处理 {scoring_done[2]} 项，推荐 {scoring_done[3]} 项，低分排除 {scoring_done[6]} 项"
    settings_saved = re.fullmatch(r"(?:Settings saved; encrypted API Key present=(?:True|False)|Web desktop settings autosaved: fields=\[.*\]) deferred_window_size=(True|False)", message)
    if settings_saved:
        label = "设置已自动保存" if message.startswith("Web ") else "设置已保存"
        return label + ("；启动窗口大小下次启动生效" if settings_saved[1] == "True" else "")
    tutorial_complete = re.fullmatch(r"Browser 新手教程步骤完成: step=(\d+) celebration=(true|false)", message)
    if tutorial_complete:
        return f"教程第 {tutorial_complete[1]} 步完成" + ("；播放礼花" if tutorial_complete[2] == "true" else "")
    startup = re.fullmatch(r"Browser 启动页加载完成: tutorial_status=(not_started|completed|skipped|legacy)", message)
    if startup:
        status = {"not_started":"等待开始教程","completed":"教程已完成","skipped":"教程已跳过","legacy":"工作区已就绪"}[startup[1]]
        return "启动页加载完成；" + status
    entered = re.fullmatch(r"Browser 进入工作区: tutorial=(true|false)", message)
    if entered:
        return "已进入工作区" + ("；开始新手教程" if entered[1] == "true" else "")
    startup_routines = {"Browser 启动页等待开始: tutorial_pending=true":"等待点击开始",
                        "Browser 启动按钮动画已就绪: engine=WebGL2":"启动按钮动画已就绪",
                        "Browser 启动标题已就绪: source=intext-logo.png":"启动标题已就绪"}
    if message in startup_routines:
        return startup_routines[message]
    restored = re.fullmatch(r"Answer round restored: task=\S+ questions=(\d+) answers=(\d+) version=\d+ model_requests=0", message)
    if restored:
        return f"已返回本轮 {restored[1]} 个问题，恢复 {restored[2]} 份未提交回答"
    resumed = re.fullmatch(r"Workspace cancelled search resumed: task=\S+ kind=(local|network)", message)
    if resumed:
        return "继续已停止的" + ("本地" if resumed[1] == "local" else "联网") + " Skill 搜索"
    if message == "Ignored draft update from before answer restoration":
        return "已忽略回退前的过期草稿"
    progress = re.fullmatch(r"Network Skill progress: (.*)", message)
    if progress:
        return progress[1]
    ranked = re.fullmatch(r"(?:Open-web )?Skill sources ranked before reads: discovered=(\d+) budget=(\d+)", message)
    if ranked:
        return f"Skill 来源初排：{ranked[1]} 项，最多读取 {ranked[2]} 项"
    relevance = re.fullmatch(r"Network Skill relevance summary: collected=(\d+) selected=(\d+) review=(\w+) fallback_rejected=(\d+)", message)
    if relevance:
        return f"联网 Skill：收集 {relevance[1]} 项，保留 {relevance[2]} 项，" + ("AI 已筛选" if relevance[3] == "completed" else "AI 筛选未完成") + f"；降级排除 {relevance[4]} 项"
    batch = re.fullmatch(r"Question answer batch (started|saved): task=\S+ count=(\d+) questions=\[.*\] (?:chars|remaining)=(\d+)", message)
    if batch:
        return (f"准备提交 {batch[2]} 个回答（{batch[3]} 字）" if batch[1] == "started"
                else f"已提交 {batch[2]} 个回答，剩余 {batch[3]} 个问题")
    next_action = re.fullmatch(r"Answer batch next action: task=\S+ remaining=(\d+) analyze=(True|False)", message)
    if next_action:
        if next_action[1] != "0":
            return f"等待补充：剩余 {next_action[1]} 个问题"
        return "回答已收齐，开始整理" if next_action[2] == "True" else "回答已收齐，等待配置模型"
    rename = re.fullmatch(r"Custom provider renamed; credential preserved=(True|False) models=(\d+)", message)
    if rename:
        return f"服务已重命名，保留 {rename[2]} 个模型" + ("和加密密钥" if rename[1] == "True" else "")
    renamed_ui = re.fullmatch(r"Web custom provider rename applied; models=(\d+)", message)
    if renamed_ui:
        return f"服务名称已更新，{renamed_ui[1]} 个模型可继续使用"
    skill_toolbar = re.fullmatch(r"Browser skill table toolbar rendered: source=(.+) rows=(\d+) show_all=(true|false)", message)
    if skill_toolbar:
        return f"Skill 表格：{skill_toolbar[1]}，{skill_toolbar[2]} 项，" + ("全部" if skill_toolbar[3] == "true" else "推荐")
    action = re.fullmatch(r"Web workspace action completed: action=(\S+) task=\S+", message)
    if action:
        name = {"drafts": "草稿已同步", "settings_autosave": "设置已自动保存", "settings_provider": "服务已切换",
                "settings_back": "返回工作区", "answer": "回答已提交", "send": "消息已提交",
                "navigate": "流程位置已更新", "model": "模型选择已应用", "settings_rename_provider": "供应商已重命名"}.get(action[1])
        if name:
            return name
    menu = re.fullmatch(r"Browser settings suggestions (opened|closed): settings-field-(\S+?)(?: reason=\S+)?", message)
    if menu:
        from .preferences import FIELDS
        key = menu[2]
        label = {"connection-provider": "服务名称", "connection-model_provider": "模型供应商",
                 "connection-protocol": "协议", "connection-model": "模型"}.get(key)
        if label is None and key in FIELDS:
            label = FIELDS[key].label
        if label:
            return ("展开" if menu[1] == "opened" else "收起") + label + "菜单"
    saving = re.fullmatch(r"Browser settings autosave started: fields=(.*)", message)
    if saving:
        return f"自动保存：{len([field for field in saving[1].split(',') if field])}项修改"
    submitted = re.fullmatch(r"Web settings submitted: action=\S+ fields=(\[.*\]) credential_action=(keep|replace|clear)", message)
    if submitted:
        try:
            count = len(ast.literal_eval(submitted[1]))
        except (ValueError, SyntaxError, TypeError):
            return message
        action = {"keep": "保留密钥", "replace": "更新密钥", "clear": "清除密钥"}[submitted[2]]
        return f"提交设置：{count}项参数，{action}"
    applied = re.fullmatch(r"Settings applied; changed fields=(\[.*\])", message)
    if applied:
        try:
            fields = ast.literal_eval(applied[1])
        except (ValueError, SyntaxError, TypeError):
            return message
        return "设置已应用" + ("：" + ", ".join(map(str, fields)) if fields else "")
    category = re.fullmatch(r"Browser settings category: (.+)", message)
    if category:
        return "切换设置分类：" + category[1]
    family = re.fullmatch(r"Browser custom service model provider selected: (.+)", message)
    if family:
        return "服务调用类型：" + family[1]
    background = re.fullmatch(r"Background operation started: PromptSmithApp\.([^. ;]+)(?:\..*)?; task=\S+", message)
    if background:
        return "后台任务已启动：" + background[1]
    routine = {
        "Application data directory migrated; settings, protected credentials and history retained": "应用数据已迁移到 Intext；设置、密钥和历史已保留",
        "Custom provider rename started; encrypted_key=True": "准备迁移服务名称及加密密钥",
        "Custom provider rename started; encrypted_key=False": "准备迁移服务名称",
        "Browser custom provider rename dialog opened: ": "打开服务重命名面板",
        "Browser custom provider rename dialog closed: cancel": "取消服务重命名",
        "Browser custom provider rename dialog closed: saved": "关闭服务重命名面板：已保存",
        "Browser settings autosave completed: ": "设置已自动保存",
        "Debug browser console ready: Chromium log view; logs remain in memory until manual save": "控制台已就绪；日志仅在点击保存后写入文件",
        "Runtime logging started; manual saving enabled": "日志采集已启动；手动保存",
        "Web Debug window opened: engine=WebView2 severity_colors=preserved": "Debug 窗口已打开",
        "Web Debug window closed by user; collection continues in memory": "Debug 窗口已关闭；继续在内存中记录",
    }
    return routine.get(message, message)


class WebDebugConsole:
    """Minimal native-console adapter. Tk only publishes plain preferences."""
    def __init__(self, logs, desktop_api):
        self.logs = logs
        self.desktop_api = desktop_api
        self.identity = uuid4().hex
        self.lock = threading.Lock()
        self.preferences = {}
        self.preference_revision = 0
        self.closed = False
        self.focus_requested = False
        self.window = self  # Existing settings use console.window.lift().

    def apply_preferences(self, values):
        with self.lock:
            self.preferences = deepcopy(values)
            self.preference_revision += 1

    def update_palette(self, values):
        with self.lock:
            for key in ("composer_theme", "font_size"):
                self.preferences[key] = values[key]

    def lift(self):
        with self.lock:
            self.focus_requested = True

    def close(self):
        with self.lock:
            self.closed = True

    def user_closed(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
        self.desktop_api._debug_closed(self.identity)
        LOG.info("Web Debug window closed by user; collection continues in memory")


class DebugApi:
    """Read redacted logs, explicitly save, or open the fixed logs directory."""
    def __init__(self, console):
        self._console = console

    def snapshot(self, since=0):
        if isinstance(since, bool) or not isinstance(since, (int, float)) or since < 0:
            since = 0
        console = self._console
        with console.lock:
            preferences = deepcopy(console.preferences)
            revision = console.preference_revision
        logs = console.logs
        entries = logs.entries_after(int(since))
        return dict(entries=[dict(id=e.sequence, level=e.level, text=logs.redact(e.text),
                                 time=e.time, source=logs.redact(e.source.removeprefix("promptsmith.")),
                                 message=concise_message(logs.redact(e.message), e.level)) for e in entries],
                    sequence=entries[-1].sequence if entries else int(since), cached=len(logs.entries_after()),
                    saved_sequence=logs.saved_sequence, path=str(logs.path) if logs.path else "",
                    error=logs.file_error, directory_exists=logs.directory.is_dir(), preferences=preferences,
                    preference_revision=revision)

    def save(self):
        try:
            path = self._console.logs.save()
            return dict(ok=True, path=str(path))
        except OSError:
            return dict(ok=False, error="日志未保存，请检查目录权限或磁盘空间后重试。")

    def diagnostic(self, level, event, detail):
        levels = {"debug": logging.DEBUG, "info": logging.INFO, "warn": logging.WARNING, "error": logging.ERROR}
        self._console.logs.record(__name__, levels.get(level, logging.DEBUG),
                                  "Debug browser %s: %s" % (str(event)[:120], str(detail)[:12000]))
        return True

    def open_directory(self):
        try:
            directory = self._console.logs.directory
            if not directory.is_dir():
                return dict(ok=False, error="日志目录尚未创建，请先保存日志。")
            os.startfile(directory)
            return dict(ok=True)
        except OSError:
            LOG.exception("Web Debug could not open log directory")
            return dict(ok=False, error="无法打开日志目录，请查看错误记录后重试。")


class DebugWindowManager:
    """Create and close Chromium windows from pywebview's worker thread."""
    def __init__(self, desktop_api, logs):
        self.desktop_api, self.logs = desktop_api, logs
        self.lock = threading.Lock()
        self.consoles = []
        self.windows = {}

    def create_console(self, _parent, _logs, _on_close):
        console = WebDebugConsole(self.logs, self.desktop_api)
        with self.lock:
            self.consoles.append(console)
        return console

    def sync(self):
        import webview
        with self.lock:
            consoles = list(self.consoles)
        for console in consoles:
            with console.lock:
                closed, focus = console.closed, console.focus_requested
                console.focus_requested = False
            window = self.windows.get(console.identity)
            if closed:
                if window:
                    self.windows.pop(console.identity)
                    if not window.events.closed.is_set():
                        window.destroy()
                with self.lock:
                    if console in self.consoles:
                        self.consoles.remove(console)
                continue
            try:
                if window is None:
                    window = webview.create_window("Intext · Debug 控制台",
                        str(resource_root()/"resources/ui/workspace/debug.html"), js_api=DebugApi(console),
                        width=1120, height=640, min_size=(600, 320), background_color="#171717", text_select=True)
                    window.events.closed += console.user_closed
                    self.windows[console.identity] = window
                    LOG.info("Web Debug window opened: engine=WebView2 severity_colors=preserved")
                elif focus:
                    window.show()
            except Exception:
                LOG.exception("Web Debug window operation failed; will retry")

    def close_all(self):
        with self.lock:
            consoles = list(self.consoles)
        for console in consoles:
            console.close()
        self.sync()
