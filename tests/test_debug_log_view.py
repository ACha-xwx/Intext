"""Compact console behavior at the public log/API and production DOM boundaries."""
from datetime import datetime
import logging
import pytest

from promptsmith.runtime_log import RuntimeLog
from promptsmith.web_debug import DebugApi, WebDebugConsole
from promptsmith.web_workspace import DesktopApi
from tests.test_debug_legend import browser, debug_page, push


@pytest.mark.parametrize("raw,visible", [
    ("Settings saved; encrypted API Key present=True deferred_window_size=False", "设置已保存"),
    ("Web desktop settings autosaved: fields=['window_width'] deferred_window_size=True", "设置已自动保存；启动窗口大小下次启动生效"),
    ("Browser 新手教程步骤完成: step=2 celebration=true", "教程第 2 步完成；播放礼花"),
])
def test_new_settings_and_tutorial_diagnostics_have_compact_console_text(tmp_path, raw, visible):
    logs=RuntimeLog(tmp_path/"logs")
    logs.record("promptsmith.web_workspace",logging.INFO,raw)
    entry=DebugApi(WebDebugConsole(logs,DesktopApi())).snapshot()["entries"][0]
    assert entry["message"]==visible
    assert raw in entry["text"]
    assert not logs.directory.exists()


def test_startup_console_is_concise_but_manual_log_preserves_diagnostics(tmp_path):
    logs = RuntimeLog(tmp_path/"logs")
    api = DebugApi(WebDebugConsole(logs, DesktopApi()))
    raw = "Browser 启动页加载完成: tutorial_status=completed"
    failure = "Browser 启动按钮使用静态银边: Error: WebGL unavailable\n完整异常位置"
    wordmark = "Browser 启动标题已就绪: source=intext-logo.png"
    logs.record("promptsmith.web_workspace",logging.INFO,raw)
    logs.record("promptsmith.web_workspace",logging.WARNING,failure)
    logs.record("promptsmith.web_workspace",logging.DEBUG,wordmark)
    entries = api.snapshot()["entries"]
    assert entries[0]["message"] == "启动页加载完成；教程已完成"
    assert entries[1]["message"] == failure
    assert entries[2]["message"] == "启动标题已就绪"
    assert not logs.directory.exists()
    path = logs.save()
    saved = path.read_text(encoding="utf-8")
    assert raw in saved and failure in saved and wordmark in saved
    assert path.name.startswith("Intext_")


def test_network_search_console_summaries_preserve_full_manual_log(tmp_path):
    logs = RuntimeLog(tmp_path / "logs")
    api = DebugApi(WebDebugConsole(logs, DesktopApi()))
    raw = "Network Skill relevance summary: collected=20 selected=2 review=failed fallback_rejected=18"
    logs.record("promptsmith.skill_network_discovery", logging.INFO, raw)
    entry = api.snapshot()["entries"][0]
    assert entry["message"] == "联网 Skill：收集 20 项，保留 2 项，AI 筛选未完成；降级排除 18 项"
    assert raw in entry["text"] and not logs.directory.exists()


def test_debug_snapshot_separates_short_metadata_from_complete_redacted_record(tmp_path):
    logs = RuntimeLog(tmp_path / "logs")
    logs.register_secret("disposable-display-key")
    record = logging.LogRecord("promptsmith.web_workspace", logging.INFO, "fixture.py", 5,
                               "状态已更新 disposable-display-key", (), None)
    record.created = datetime(2026, 10, 13, 15, 12, 34).timestamp()
    logs.handle(record)
    entry = DebugApi(WebDebugConsole(logs, DesktopApi())).snapshot()["entries"][0]
    assert entry["time"] == "15:12:34"
    assert entry["source"] == "web_workspace"
    assert entry["message"] == "状态已更新 [REDACTED]"
    assert "2026-10-13 15:12:34" in entry["text"]
    assert "promptsmith.web_workspace" in entry["text"]
    assert "disposable-display-key" not in str(entry)
    assert not logs.directory.exists()


def test_console_rows_use_reference_columns_and_wrap_long_messages(debug_page):
    page = debug_page
    push(page, [dict(level=10, time="15:12:34", source="工作区", message="菜单已展开",
                     text="[2026-10-13 15:12:34.123] [Thread-3645/DEBUG] [promptsmith.web_workspace]: 菜单已展开")])
    row = page.locator(".log-line")
    assert row.locator(".log-time").inner_text() == "15:12:34"
    assert row.locator(".log-level").inner_text() == "DBG"
    assert row.locator(".log-source").inner_text() == "[工作区]"
    assert row.locator(".log-message").inner_text() == "菜单已展开"
    assert "Thread-3645" not in row.inner_text()
    for width in (1120, 600):
        page.set_viewport_size(dict(width=width, height=640))
        push(page, [dict(level=40, time="15:12:35", source="api", message="错误 details/" * 120,
                         text="complete original error")])
        area = page.locator("#debug-scroll")
        assert area.evaluate("e=>e.scrollWidth<=e.clientWidth+1")
        body = page.locator(".log-message").last
        assert body.bounding_box()["height"] > 30
    assert "monospace" in row.first.evaluate("e=>getComputedStyle(e).fontFamily")


def test_common_console_messages_are_short_but_copy_and_saved_log_remain_complete(tmp_path):
    logs = RuntimeLog(tmp_path / "logs")
    api = DebugApi(WebDebugConsole(logs, DesktopApi()))
    messages = [
        "Web workspace action completed: action=drafts task=task-disposable-12345",
        "Browser settings suggestions opened: settings-field-connection-provider",
        "Browser settings suggestions closed: settings-field-connection-provider reason=outside",
    ]
    for message in messages:
        logs.record("promptsmith.web_workspace", logging.DEBUG, message)
    entries = api.snapshot()["entries"]
    assert [entry["message"] for entry in entries] == ["草稿已同步", "展开服务名称菜单", "收起服务名称菜单"]
    assert all(original in entry["text"] for original, entry in zip(messages, entries))
    assert not logs.directory.exists()
    assert api.save()["ok"]
    content = logs.path.read_text(encoding="utf-8")
    assert all(original in content for original in messages)


def test_settings_and_background_lifecycle_summaries_retain_useful_context(tmp_path):
    logs = RuntimeLog(tmp_path / "logs")
    api = DebugApi(WebDebugConsole(logs, DesktopApi()))
    messages = [
        "Browser settings autosave started: fields=connection.model,temperature",
        "Web settings submitted: action=settings_autosave fields=['temperature', 'max_tokens'] credential_action=keep",
        "Settings applied; changed fields=['composer_theme']",
        "Browser settings category: 诊断",
        "Background operation started: PromptSmithApp.run_m1.<locals>.<lambda>; task=task-12345",
        "Browser custom service model provider selected: OpenAI",
    ]
    for text in messages:
        logs.record("promptsmith.web_workspace", logging.DEBUG, text)
    shown = [entry["message"] for entry in api.snapshot()["entries"]]
    assert shown == ["自动保存：2项修改", "提交设置：2项参数，保留密钥", "设置已应用：composer_theme", "切换设置分类：诊断", "后台任务已启动：run_m1", "服务调用类型：OpenAI"]
    logs.record("external.module", logging.WARNING, messages[0])
    assert api.snapshot()["entries"][-1]["message"] == messages[0]


def test_errors_keep_full_exception_chain_in_compact_projection_and_saved_log(tmp_path):
    import sys
    logs = RuntimeLog(tmp_path / "logs")
    logs.register_secret("disposable-error-key")
    api = DebugApi(WebDebugConsole(logs, DesktopApi()))
    try:
        try:
            raise ValueError("cause disposable-error-key")
        except ValueError as exc:
            raise RuntimeError("outer 中文🧪") from exc
    except RuntimeError:
        logs.record("promptsmith.api", logging.ERROR, "模型请求失败", exc_info=sys.exc_info())
    entry = api.snapshot()["entries"][0]
    assert all(value in entry["message"] for value in ("模型请求失败", "Traceback", "ValueError", "RuntimeError", "direct cause", "中文🧪"))
    assert "disposable-error-key" not in str(entry)
    logs.register_secret("outer")
    assert "outer" not in api.snapshot()["entries"][0]["message"]
    assert api.save()["ok"]
    assert "RuntimeError" in logs.path.read_text(encoding="utf-8")


def test_console_copy_uses_full_original_records_after_compact_rendering(debug_page):
    page = debug_page
    page.evaluate("Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>window.copied=text},configurable:true})")
    original = "[2026-10-13 15:12:34.123] [Worker/DEBUG] [promptsmith.web_workspace]: task=task-123 草稿记录"
    push(page, [dict(level=10, time="15:12:34", source="web_workspace", message="草稿已同步", text=original)])
    page.get_by_role("button", name="复制日志", exact=True).click()
    page.wait_for_function("window.copied!==undefined")
    assert page.evaluate("copied") == original


def test_wrapped_unicode_history_keeps_visible_text_when_new_records_arrive(debug_page):
    page = debug_page
    page.set_viewport_size(dict(width=600, height=640))
    message = "前缀中文🧪🪷内容 " * 250 + "定位文本🧪" + " 继续查看 " * 200
    push(page, [dict(level=40, time="15:12:34", source="api", message=message, text=message)])
    def mark_and_top(move=False):
        return page.locator(".log-message").first.evaluate("""(el,move)=>{
          const text=el.firstChild,start=text.data.indexOf('定位文本');
          const range=document.createRange();range.setStart(text,start);range.setEnd(text,start+4);
          const area=document.querySelector('#debug-scroll');
          if(move)area.scrollTop+=range.getBoundingClientRect().top-area.getBoundingClientRect().top-30;
          return range.getBoundingClientRect().top;
        }""", move)
    before = mark_and_top(True)
    push(page, [dict(level=20, time="15:12:35", source="ui", message="新记录", text="新记录")])
    assert abs(mark_and_top() - before) < 2


def test_copy_respects_display_line_limit_and_severity_filter(debug_page):
    page = debug_page
    page.evaluate("prefs.debug_lines=3;Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>window.copied=text},configurable:true})")
    push(page, [dict(level=40, text="header\nfirst\nsecond\nthird"), dict(level=20, text="last-visible")])
    page.get_by_role("button", name="复制日志", exact=True).click()
    page.wait_for_function("window.copied!==undefined")
    assert page.evaluate("copied") == "second\nthird\nlast-visible"
    page.get_by_role("button", name="关闭通知", exact=True).click()
    page.locator(".legend-info").click()
    page.get_by_role("button", name="复制日志", exact=True).click()
    page.wait_for_function("copied==='first\\nsecond\\nthird'")
