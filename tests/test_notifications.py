"""Feedback via the Tk-owner controller projection, no real requests."""
from tests.test_conversation_workspace import app
from promptsmith.web_workspace import WorkspaceController


def test_status_feedback_is_redacted_and_emitted_once_across_snapshots(app):
    view = WorkspaceController(app)
    app.runtime_log.register_secret("disposable-notification-key")
    app.status_var.set("请求失败 disposable-notification-key；可以重试。")
    first = view.snapshot()["notifications"]
    assert first and first[-1]["body"] == "请求失败 [REDACTED]；可以重试。"
    assert first[-1]["level"] == "error"
    assert view.snapshot()["notifications"] == first


def test_operation_error_replaces_related_status_and_retains_guidance(app):
    view = WorkspaceController(app)
    view.install_native_bridge()
    app.status_var.set("获取模型列表失败：模拟服务拒绝")
    app._show_error("获取模型列表失败","模拟服务拒绝\n仍可手动填写模型 ID。")
    notices=view.snapshot()["notifications"]
    assert notices[-1]["key"]==notices[-2]["key"]
    assert "仍可手动填写" in notices[-1]["body"]


def test_passive_render_status_and_per_keystroke_drafts_do_not_notify(app):
    view = WorkspaceController(app)
    app.settings_status_var.set("有未保存的设置。")
    app.final_status_var.set("最终结果：未生成 · 版本 0")
    app.skill_status_var.set("目录状态：尚未开始")
    assert view.snapshot()["notifications"]==[]


def test_same_body_different_native_events_keep_title_and_level(app):
    view=WorkspaceController(app)
    view.install_native_bridge()
    app._show_info("配置消息","保留输入")
    app._show_warning("需要核对","保留输入")
    app._show_info("配置消息","保留输入")
    messages=view.snapshot()["notifications"]
    assert [(n["title"],n["level"]) for n in messages]==[("配置消息","info"),("需要核对","warn"),("配置消息","info")]
