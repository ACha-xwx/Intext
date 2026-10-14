from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .finalization import DeliveryValidationError, render_task_prompt, validate_current_final
from .session import SessionState


def _safe_json(value: Any) -> str:
    return str(value) if value is not None else ""


def _markdown(session: SessionState, *, mode: str) -> str:
    result = session.final_result
    status = str(result.get("status", "not_started"))
    if mode == "final":
        if status != "confirmed" or result.get("confirmed_revision") != result.get("revision"):
            raise DeliveryValidationError("正式导出需要先确认当前最终结果。")
        validate_current_final(session, require_confirmed=True)
        marker = "最终版本"
    elif mode == "draft":
        if status == "not_started" or not result.get("canonical_body", "").strip():
            raise DeliveryValidationError("尚未生成可导出的最终草稿。")
        validate_current_final(session)
        marker = "草稿" if status == "draft" else f"{status} 版本"
    else:
        raise ValueError("导出模式必须是 final 或 draft。")
    if session.current_draft_authorization():
        marker = "草稿（已核对当前内容，仍含明确保留的未知）"
    content = result.get("content") or {}
    body = result.get("canonical_body") or ""
    prompt = render_task_prompt(body, result.get("tone", "neutral")) if body else ""
    basis = result.get("basis") or {}
    lines = [
        f"# Intext 最终交付（{marker}）",
        "",
        f"- 任务：{session.task_text}",
        f"- 结果状态：{status}",
        f"- 需求版本：{_safe_json(basis.get('requirement_version'))}",
        f"- 方案：{_safe_json(basis.get('plan_id'))} / {_safe_json(basis.get('plan_version'))}",
        f"- 正文 SHA-256：{_safe_json(result.get('body_sha256'))}",
        f"- 导出时间：{datetime.now(timezone.utc).isoformat()}",
        "",
        "## 完整方案正文",
        "",
        body,
        "",
        "## 最终任务提示",
        "",
        "```text",
        prompt.replace("```", "``\\`") if prompt else "（暂无正文）",
        "```",
        "",
        "## 未决事项与待决定建议",
        "",
    ]
    unknown = (content.get("baseline") or {}).get("unknown", [])
    if unknown:
        lines.extend(f"- {row.get('description', row.get('text', ''))}" for row in unknown)
    else:
        lines.append("- 无")
    pending = content.get("pending_changes", [])
    pending_suggestions = [row for row in pending if row.get("suggestion_id") and not row.get("change_id")]
    post_delivery_items = [row for row in pending if row.get("change_id")]
    if pending_suggestions:
        lines.extend(f"- 待决定：{row.get('text', '')}；{row.get('reason', '')}" for row in pending_suggestions)
    if post_delivery_items:
        lines.extend(["", "### 使用时补充的后置事项", ""])
        lines.extend(
            f"- {'未采纳' if row.get('decision') == 'rejected' else '待使用时补充'}："
            f"{row.get('text', row.get('description', ''))}；{row.get('reason', '')}"
            for row in post_delivery_items
        )
    lines.extend(["", "## Agent Skill 指令参考与核验边界", ""])
    contributions = content.get("skill_contributions", [])
    if not contributions:
        lines.append("本结果未采用外部 Agent Skill。")
    else:
        for row in contributions:
            lines.append(f"- {row.get('binding_id', '')}：{'；'.join(row.get('method_actions', []))}")
            lines.append(f"  - 前提：{'；'.join(row.get('prerequisite_ids', [])) or '无额外前提'}")
            provenance = row.get("provenance")
            if isinstance(provenance, dict) and provenance.get("origin") == "remote":
                lines.extend([
                    f"  - GitHub 地址：{_safe_json(provenance.get('source_url'))}",
                    f"  - 仓库：{_safe_json(provenance.get('repository'))}",
                    f"  - 固定提交：{_safe_json(provenance.get('fixed_commit'))}",
                    f"  - 内容哈希类型：{_safe_json(provenance.get('content_hash_kind'))}",
                    f"  - 内容哈希：{_safe_json(provenance.get('content_sha256'))}",
                    f"  - 核验状态：{_safe_json(provenance.get('verification_status'))}",
                    f"  - 正文已读取：{'是' if provenance.get('source_read') else '否'}",
                    f"  - 已安装：{'是' if provenance.get('installed') else '否'}",
                    f"  - 已执行测试：{'是' if provenance.get('execution_tested') else '否'}",
                    "  - 使用时请由下游 AI 读取对应 Skill，并确认当前环境所需工具和依赖。",
                ])
            for source in row.get("provenance_sources", []):
                if isinstance(source, dict) and source.get("origin") == "remote":
                    lines.append(
                        f"  - 远程来源：{_safe_json(source.get('source_url'))}；固定提交：{_safe_json(source.get('fixed_commit'))}"
                    )
            lines.append("  - 以上是交给下游 AI 的 Skill 使用说明；实际使用情况由执行任务的 AI 确认。")
    return "\n".join(lines) + "\n"


def export_markdown(
    session: SessionState,
    path: str | Path,
    *,
    mode: str,
    overwrite: bool = False,
) -> Path:
    target = Path(path).expanduser().resolve()
    if target.exists() and not overwrite:
        raise FileExistsError(f"目标文件已存在，需明确允许覆盖：{target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    text = _markdown(session, mode=mode)
    temporary = target.with_name(f".{target.name}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, target)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return target
