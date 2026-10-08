"""Controlled offline release check through the application's UI commands."""

from __future__ import annotations

import json
import os
import time
import tkinter as tk
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from .m1 import M1_INCREMENTAL_PROMPT_VERSION
from .paths import m1_asset_dir
from .storage import load_session
from .ui import PromptSmithApp


DEMO_TASK = (
    "为摄影社写一则发在新生微信群的招新通知，500 字以内。我希望语气自然，但拿不准应该活泼到什么程度。"
    "活动是 2026 年 10 月 10 日 14:00–16:00 在校园南广场的手机摄影体验，报名截止 2026 年 10 月 8 日；"
    "报名链接为演示用 https://example.com/photo-signup。不要添加未提供的负责人、收费或器材要求。"
)


def _wait_until(root: tk.Tk, predicate, label: str, *, timeout: float = 20) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        root.update()
        if predicate():
            return
        time.sleep(0.03)
    raise TimeoutError(f"等待{label}超时")


def _dialog_error(title: str, message: str, **_kwargs) -> None:
    raise RuntimeError(f"{title}：{message}")


def run_release_chain(directory: str | Path) -> int:
    if os.environ.get("PROMPTSMITH_RELEASE_SCENARIO") == "m1_truncation":
        return _run_m1_truncation_chain(directory)
    target = Path(directory).resolve()
    target.mkdir(parents=True, exist_ok=True)
    report_path = target / "chain_result.json"
    session_path = target / "session.json"
    markdown_path = target / "final.md"
    root: tk.Tk | None = None
    app: PromptSmithApp | None = None
    report: dict[str, object] = {"verification_kind": "offline_http_stub_ui_commands"}
    try:
        base_url = os.environ["PROMPTSMITH_RELEASE_STUB_URL"]
        root = tk.Tk()
        root.withdraw()
        app = PromptSmithApp(root, evidence_root=target / "calls")
        with (
            patch("tkinter.messagebox.showerror", side_effect=_dialog_error),
            patch("tkinter.messagebox.showinfo", side_effect=_dialog_error),
            patch("tkinter.filedialog.asksaveasfilename", side_effect=[str(session_path), str(markdown_path)]),
            patch("tkinter.filedialog.askopenfilename", return_value=str(session_path)),
        ):
            app.provider_var.set("Local verification stub")
            app.api_base_var.set(base_url)
            app.api_model_var.set("release-stub")
            app.api_key_var.set("local-verification-only")
            app.confirm_model_settings()
            app.widgets["task_text"].insert("1.0", DEMO_TASK)

            # Exercise the first click before M5 or any other action can sync
            # the input as a side effect and conceal a primary-button defect.
            root.update()
            report["task_input_only_before_click"] = (
                app.session.task_text == ""
                and app.widgets["task_text"].get("1.0", "end-1c") == DEMO_TASK
            )
            report["task_input_label"] = app.primary_action_var.get()
            if not report["task_input_only_before_click"] or report["task_input_label"] != "开始整理":
                raise AssertionError("任务只写入控件时主按钮未正确就绪")
            app.widgets["analyze_button"].invoke()
            report["primary_button_started_m1"] = (
                app.session.task_text == DEMO_TASK and app.busy_kind == "m1"
            )
            if not report["primary_button_started_m1"]:
                raise AssertionError("任务主按钮未同步并发起 M1")
            _wait_until(root, lambda: not app.busy, "需求分析")
            if not app.session.pending_proposals:
                raise AssertionError("M1 没有产生需求候选")

            report["m5_entry_reachable"] = "m5_generate_button" in app.widgets
            if not report["m5_entry_reachable"]:
                raise AssertionError("M5 入口不存在")
            try:
                app.start_m5_generation()
            except RuntimeError as exc:
                if "无法生成示例" not in str(exc):
                    raise
            else:
                raise AssertionError("空标准应在 M5 发起前被拒绝")
            report["m5_validation_failure_recoverable"] = app.session.m5_state.get("status") == "not_started"
            if not report["m5_validation_failure_recoverable"]:
                raise AssertionError("M5 无效输入改变了会话")

            if app.primary_action_var.get() != "确认需求并生成方案":
                raise AssertionError("需求预览没有直接确认并生成方案的入口")
            app.widgets["analyze_button"].invoke()
            report["requirements_confirmed"] = (
                app.session.confirmed_requirements_version == app.session.requirement_version
            )
            if not report["requirements_confirmed"]:
                raise AssertionError("需求未确认")

            _wait_until(root, lambda: not app.busy, "方案生成")
            if not app.session.plan.get("content"):
                raise AssertionError("M2 没有产生方案")
            if app.primary_action_var.get() != "确认方案并生成提示":
                raise AssertionError("方案核对没有直接生成提示的入口")
            app.widgets["analyze_button"].invoke()
            report["plan_confirmed"] = app.session.plan.get("status") == "confirmed"
            if not report["plan_confirmed"]:
                raise AssertionError("方案未确认")

            report["skill_status"] = app.session.skill_state.get("status")
            if app.session.final_result.get("status") != "draft":
                raise AssertionError("无 Skill 最终草稿未生成")
            app.confirm_final_result()
            report["final_status"] = app.session.final_result.get("status")
            if report["final_status"] != "confirmed":
                raise AssertionError("最终结果未确认")

            report["trial_entry_reachable"] = (
                "trial_run_button" in app.widgets
                and str(app.widgets["trial_run_button"].cget("state")) != "disabled"
            )
            if not report["trial_entry_reachable"]:
                raise AssertionError("已确认最终结果的试运行入口不可用")
            app.trial_tokens_var.set("0")
            try:
                app.start_trial_run()
            except RuntimeError as exc:
                if "无法开始试运行" not in str(exc):
                    raise
            else:
                raise AssertionError("无效输出上限应在试运行发起前被拒绝")
            app.trial_tokens_var.set("256")
            report["trial_validation_failure_recoverable"] = (
                app.session.final_result.get("status") == "confirmed"
                and not app.session.trial_runs
            )
            if not report["trial_validation_failure_recoverable"]:
                raise AssertionError("试运行无效输入改变了最终结果")

            before_reopen = app.session.to_dict()
            app.save()
            app.open_session()
            before_reopen["final_result"].setdefault("recovery_notice", None)
            report["reopened_consistent"] = app.session.to_dict() == before_reopen
            if not report["reopened_consistent"]:
                after_reopen = app.session.to_dict()
                report["reopen_changed_fields"] = [
                    key for key in before_reopen if before_reopen[key] != after_reopen.get(key)
                ]
                raise AssertionError("保存重开后的会话状态不一致")
            app.export_final_markdown()
            body = markdown_path.read_text(encoding="utf-8")
            report["markdown_contains_final_prompt"] = (
                "摄影社" in body and "https://example.com/photo-signup" in body
            )
            if not report["markdown_contains_final_prompt"]:
                raise AssertionError("Markdown 缺少最终任务提示的关键事实")
            loaded = load_session(session_path)
            if loaded.final_result.get("status") != "confirmed":
                raise AssertionError("磁盘会话未保留最终确认")
        report["success"] = True
        return 0
    except Exception as exc:
        report["success"] = False
        report["error"] = f"{type(exc).__name__}: {exc}"
        return 1
    finally:
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if app is not None:
            app.shutdown(wait=True)
        if root is not None:
            root.destroy()


def _run_m1_truncation_chain(directory: str | Path) -> int:
    """Verify the incremental resource and explicit recovery through real UI commands."""
    target = Path(directory).resolve()
    target.mkdir(parents=True, exist_ok=True)
    report_path = target / "chain_result.json"
    failed_session_path = target / "session_after_truncation.json"
    completed_session_path = target / "session_after_retry.json"
    root: tk.Tk | None = None
    app: PromptSmithApp | None = None
    dialogs: list[dict[str, str]] = []
    report: dict[str, object] = {
        "verification_kind": "offline_http_stub_ui_m1_truncation",
        "scenario": "m1_truncation",
        "real_api_calls": 0,
    }

    def capture_error(title: str, message: str, **_kwargs) -> None:
        dialogs.append({"title": title, "message": message})

    def assert_business_preserved(before: dict, after: dict) -> None:
        changed = [
            key for key, value in before.items()
            if key not in {"updated_at", "api_runs", "errors", "pending_requests"}
            and after.get(key) != value
        ]
        if changed:
            raise AssertionError(f"截断改变了已有业务字段：{changed}")

    def evidence_for(run: dict) -> tuple[Path, dict, dict]:
        evidence = Path(run["evidence_dir"])
        metadata = json.loads((evidence / "meta.json").read_text(encoding="utf-8"))
        check = json.loads((evidence / "check.json").read_text(encoding="utf-8"))
        return evidence, metadata, check

    try:
        base_url = os.environ["PROMPTSMITH_RELEASE_STUB_URL"]
        incremental_prompt = (m1_asset_dir() / f"{M1_INCREMENTAL_PROMPT_VERSION}.txt").read_text(
            encoding="utf-8-sig"
        )
        root = tk.Tk()
        root.withdraw()
        app = PromptSmithApp(root, evidence_root=target / "calls")
        with (
            patch("tkinter.messagebox.showerror", side_effect=capture_error),
            patch("tkinter.messagebox.showinfo", side_effect=_dialog_error),
            patch("tkinter.filedialog.askopenfilename", return_value=str(failed_session_path)),
        ):
            app.provider_var.set("Local verification stub")
            app.api_base_var.set(base_url)
            app.api_model_var.set("release-stub")
            app.api_key_var.set("local-verification-only")
            app.confirm_model_settings()
            app.widgets["task_text"].insert("1.0", "讲解JGS")
            root.update()
            if app.session.task_text or app.primary_action_var.get() != "开始整理":
                raise AssertionError("任务只写入控件时主按钮未正确就绪")
            app.widgets["analyze_button"].invoke()
            if app.session.task_text != "讲解JGS" or app.busy_kind != "m1":
                raise AssertionError("首次点击没有同步任务并开始 M1")
            _wait_until(root, lambda: not app.busy, "第一轮需求分析")
            if dialogs or len(app.session.pending_questions) != 2:
                raise AssertionError("第一轮没有成功产生两道问题")
            app.accept_all_proposals()
            for question_id, answer in (("q1", "数值分析里面的"), ("q2", "就是学生学习的讲解")):
                app.widgets["questions_tree"].selection_set(question_id)
                app.answer_var.set(answer)
                app.record_question("answered")
            if app.primary_action_var.get() != "继续整理回答":
                raise AssertionError("两条回答后未进入继续分析入口")
            before = deepcopy(app.session.to_dict())

            app.widgets["analyze_button"].invoke()
            if not app.busy or str(app.widgets["analyze_button"]["state"]) != "disabled":
                raise AssertionError("第二轮未进入防止重复提交的忙碌状态")
            # Exercise duplicate user commands before the UI processes a response.
            app.run_primary_action()
            app.start_analysis()
            app.widgets["analyze_button"].invoke()
            _wait_until(root, lambda: not app.busy, "第二轮截断")
            if len(dialogs) != 1 or "截断" not in dialogs[0]["message"]:
                raise AssertionError("截断没有作为独立失败显示")
            assert_business_preserved(before, app.session.to_dict())
            if app.session.pending_requests or app.busy_kind is not None:
                raise AssertionError("截断未清理待处理请求或忙碌状态")
            if app._primary_action().kind != "retry_compact" or app.primary_action_var.get() != "重试分析":
                raise AssertionError("截断后没有明确的精简重试入口")
            report["failure_preserved_business_state"] = True
            report["failure_cleared_pending_and_busy"] = True
            report["retry_button_after_failure"] = app.primary_action_var.get()

            failed_run = app.session.api_runs[-1]
            if failed_run["status"] != "truncated":
                raise AssertionError("截断错误类型被改变")
            failed_dir, failed_meta, failed_check = evidence_for(failed_run)
            partial_raw = (failed_dir / "response.raw.txt").read_text(encoding="utf-8")
            if not partial_raw or failed_meta["usage"] is None or not failed_meta["provider_response_id"]:
                raise AssertionError("截断响应可用诊断没有保留")
            if failed_check["schema"] != "not_reached" or failed_check["semantic"] != "not_reached":
                raise AssertionError("半截 JSON 不应进入校验或状态提交")
            if failed_meta["request_mode"] != "incremental" or failed_meta["prompt_version"] != M1_INCREMENTAL_PROMPT_VERSION:
                raise AssertionError("第二轮未使用增量提示")
            if (failed_dir / "system.txt").read_text(encoding="utf-8") != incremental_prompt:
                raise AssertionError("实际增量提示与运行资源不一致")
            failed_input = json.loads((failed_dir / "input.json").read_text(encoding="utf-8"))
            if failed_input["state"]["question_history"] != before["question_history"]:
                raise AssertionError("第二轮没有发送原有两条 pending 回答")
            if failed_input["sources"] != before["sources"]:
                raise AssertionError("第二轮意外追加了错误文本或重复来源")
            failed_files = {path.name: path.read_bytes() for path in failed_dir.iterdir()}
            report["incremental_resource_loaded"] = True
            report["partial_raw_chars"] = len(partial_raw)
            report["truncation_usage"] = failed_meta["usage"]
            report["truncation_response_id"] = failed_meta["provider_response_id"]
            report["failure_check"] = failed_check

            app.session_path = failed_session_path
            app.save()
            saved = deepcopy(app.session.to_dict())
            app.open_session()
            if app.session.to_dict() != saved or app._primary_action().kind != "retry_compact":
                raise AssertionError("保存重开没有保留回答或精简重试入口")
            report["reopened_after_failure_consistent"] = True
            report["retry_button_after_reopen"] = app.primary_action_var.get()
            # Give the event queue time to prove reopening did not itself retry.
            idle_until = time.monotonic() + 0.2
            while time.monotonic() < idle_until:
                root.update()
                time.sleep(0.02)
            if len(app.session.api_runs) != 2 or app.busy:
                raise AssertionError("保存重开后发生了自动重试")

            app.widgets["analyze_button"].invoke()
            if not app.busy:
                raise AssertionError("精简重试点击未发起请求")
            app.run_primary_action()
            app.widgets["analyze_button"].invoke()
            _wait_until(root, lambda: not app.busy, "精简重试成功")
            if len(dialogs) != 1 or len(app.session.api_runs) != 3:
                raise AssertionError("精简重试没有仅提交一次成功请求")
            if app.session.pending_requests or app.busy_kind is not None:
                raise AssertionError("重试后请求或 busy 未清理")
            if app.session.requirements != before["requirements"] or app.session.sources != before["sources"]:
                raise AssertionError("重试重复提取历史需求或追加错误上下文")
            if app.session.gaps or app.session.pending_questions:
                raise AssertionError("有效回答重试成功后未关闭对应缺口")
            if not all(row["assessment_status"] == "applied" for row in app.session.question_history):
                raise AssertionError("重试未完成两条回答评估")
            if app._primary_action().kind == "retry_compact":
                raise AssertionError("成功后仍停留在截断重试入口")
            retry_run = app.session.api_runs[-1]
            retry_dir, retry_meta, retry_check = evidence_for(retry_run)
            if retry_run["status"] != "accepted_as_candidate":
                raise AssertionError("重试未通过现有状态应用")
            if retry_check["schema"] != "passed" or retry_check["semantic"] != "passed":
                raise AssertionError("重试未经过 Schema 和语义校验")
            if retry_meta["request_mode"] != "compact_retry" or retry_meta["prompt_version"] != M1_INCREMENTAL_PROMPT_VERSION:
                raise AssertionError("显式重试未使用精简增量提示")
            retry_system = (retry_dir / "system.txt").read_text(encoding="utf-8")
            if not retry_system.startswith(incremental_prompt) or "【精简重试】" not in retry_system:
                raise AssertionError("精简重试未加载同一增量资源及短重试指令")
            if {path.name: path.read_bytes() for path in failed_dir.iterdir()} != failed_files:
                raise AssertionError("重试覆盖了截断证据")
            app.session_path = completed_session_path
            app.save()
            if load_session(completed_session_path).to_dict() != app.session.to_dict():
                raise AssertionError("重试成功后的磁盘会话不一致")
            report["request_modes"] = [row.get("request_mode") for row in app.session.api_runs]
            report["request_statuses"] = [row["status"] for row in app.session.api_runs]
            report["retry_check"] = retry_check
            report["retry_button_after_success"] = app.primary_action_var.get()
            report["reopened_after_retry_consistent"] = True
            report["session_request_count"] = len(app.session.api_runs)
            report["no_automatic_retry"] = True
            report["success"] = True
        return 0
    except Exception as exc:
        report["success"] = False
        report["error"] = f"{type(exc).__name__}: {exc}"
        return 1
    finally:
        report["dialogs"] = dialogs
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if app is not None:
            app.shutdown(wait=True)
        if root is not None:
            root.destroy()
