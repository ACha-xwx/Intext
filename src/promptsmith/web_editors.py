"""Nonblocking Web editor drafts; business writes stay on the Tk owner thread."""
from copy import deepcopy
import logging
from uuid import uuid4

from .session import SessionStateError

LOG = logging.getLogger(__name__)
SECTIONS = {
    "deliverable": ("deliverables", "deliverable_id", "交付物", {"name": "名称", "description": "说明"}),
    "criterion": ("completion_criteria", "criterion_id", "完成标准", {"text": "完成标准"}),
    "unresolved": ("unresolved_items", "unresolved_id", "未决事项", {"description": "未决事项", "impact": "影响", "continuable_work": "可继续工作", "confirm_by": "确认时点"}),
    "suggestion": ("suggestions", "suggestion_id", "建议", {"text": "建议", "reason": "理由"}),
    "key_work": ("key_work", "key_work_id", "关键工作", {"title": "标题", "goal": "目标", "inputs": "输入", "outputs": "输出", "checkpoints": "检查点", "step_ids": "关联步骤", "requirement_ids": "关联需求"}),
}
STEP_FIELDS = {"title": "标题", "purpose": "目的", "inputs": "必要输入", "actions": "关键行动", "outputs": "预期输出", "completion_criteria": "完成标准", "depends_on_step_ids": "依赖步骤", "requirement_ids": "关联需求"}
PLAN_FORMS = {"goal", "goal_details", "step", "step_new", "step_delete", *SECTIONS}


def field(key, label, value, *, choices=None):
    is_list = isinstance(value, list)
    return dict(key=key, label=label + ("（每行一项）" if is_list and choices is None else ""),
                value="\n".join(value) if is_list else str(value),
                type="choices" if choices is not None else "lines" if is_list else "text",
                choices=choices, required=not is_list)


class WebEditors:
    def __init__(self, app, stamp):
        self.app = app
        self.stamp = stamp
        self.current = None
        self.owner = None
        self.basis = None

    def snapshot(self):
        if self.current and (self.owner != self.app._session_instance_token or self.basis != self.stamp()):
            self.close("stale")
        return deepcopy(self.current)

    def close(self, reason="cancel"):
        if self.current:
            LOG.info("Web editor closed: kind=%s reason=%s task=%s", self.current["kind"], reason, self.app.session.task_id)
        self.current = self.owner = self.basis = None

    def open(self, kind, target=None):
        if kind != "new" and self.app._conversation_locked():
            raise ValueError("正在处理当前任务，请完成或停止后再编辑。")
        if kind == "requirement":
            prefix, key = str(target).split(":", 1)
            rows, idkey = (self.app.session.requirements, "item_id") if prefix == "r" else (self.app.session.pending_proposals, "proposal_id")
            row = next((r for r in rows if r[idkey] == key), None)
            if prefix not in {"r", "p"} or row is None:
                raise ValueError("这条需求已变化，请重新选择。")
            title = "编辑需求" if prefix == "r" else "修改这项理解"
            fields = [field("text", "需求内容", row["text"])]
        elif kind == "note":
            from .finalization import validate_current_final
            if self.app.session.final_result.get("status") not in {"draft", "confirmed"}:
                raise ValueError("当前没有可编辑的最终草稿。")
            validate_current_final(self.app.session)
            title, fields = "添加用户附注", [field("text", "附注内容", "")]
        elif kind == "new":
            title, fields = "新建对话", []
        elif kind == "conflict":
            row = next((r for r in self.app.session.open_conflicts if target is None or r["conflict_id"] == target), None)
            if row is None:
                raise ValueError("这项冲突已经变化，请查看当前需求。")
            target = row["conflict_id"]
            participants = [r["text"] for r in self.app.session.requirements if r["item_id"] in row.get("existing_item_ids", [])]
            participants += [r["text"] for r in self.app.session.pending_proposals if r["proposal_id"] in row.get("proposal_ids", [])]
            title, fields = "核对这些要求", []
            message = row.get("description", "这些要求可能有冲突") + "\n\n" + "\n".join(f"{i}. {text}" for i, text in enumerate(participants, 1)) + "\n\n这些要求可以同时成立吗？如果需要修改，请取消后编辑或移除相应需求。"
        elif kind == "plan" or kind in PLAN_FORMS:
            plan = self.app.session.plan
            content = plan.get("content")
            if not content or plan["status"] not in {"draft", "confirmed"}:
                raise ValueError("当前方案尚不可编辑，请先生成或更新方案。")
            requirements = [dict(id=r["item_id"], label=r["text"]) for r in self.app.session.requirements]
            steps = [dict(id=r["step_id"], label=r["title"]) for r in sorted(content["steps"], key=lambda r: r["order"])]
            if kind == "plan":
                title, fields = "完整方案编辑", []
            elif kind in {"goal", "goal_details"}:
                keys = {"summary": "目标"} if kind == "goal" else {"audience": "主要受众", "scope": "方案范围"}
                title = "编辑目标" if kind == "goal" else "编辑受众与范围"
                fields = [field(k, label, content["goal"][k]) for k, label in keys.items()]
            elif kind in {"step", "step_new", "step_delete"}:
                row = {} if kind == "step_new" else next((r for r in content["steps"] if r["step_id"] == target), None)
                if row is None:
                    raise ValueError("方案步骤已变化，请重新选择。")
                title = {"step": "编辑方案步骤", "step_new": "新增方案步骤", "step_delete": "删除方案步骤"}[kind]
                fields = [] if kind == "step_delete" else [field(k, label, row.get(k, "" if k in {"title", "purpose"} else []),
                    choices=[s for s in steps if s["id"] != target] if k == "depends_on_step_ids" else requirements if k == "requirement_ids" else None)
                    for k, label in STEP_FIELDS.items()]
            else:
                collection, idkey, label, keys = SECTIONS[kind]
                row = next((r for r in content[collection] if r[idkey] == target), None)
                if row is None:
                    raise ValueError("方案内容已变化，请重新选择。")
                title = "编辑" + label
                fields = [field(k, label, row[k], choices=steps if k == "step_ids" else requirements if k == "requirement_ids" else None) for k, label in keys.items()]
        else:
            raise ValueError("编辑内容不存在。")
        self.current = dict(id=uuid4().hex, kind=kind, target=target, title=title, fields=fields, error="")
        if kind == "plan":
            self.current.update(content=deepcopy(content), pending=list(plan.get("pending_key_work_review_ids", [])))
        if kind in {"new", "step_delete"}:
            self.current["message"] = "新建对话？请先保存当前内容。" if kind == "new" else "确认删除此方案步骤？仍被引用的步骤会保留，并提示原因。"
        if kind == "conflict":
            self.current["message"] = message
        self.owner = self.app._session_instance_token
        self.basis = self.stamp()
        LOG.info("Web editor opened: kind=%s task=%s renderer=webview2", kind, self.app.session.task_id)

    def action(self, action, data):
        current = self.snapshot()
        if not current or data.get("id") != current["id"]:
            raise ValueError("编辑内容已变化，请重新打开后操作。")
        if action == "editor_cancel":
            if current["kind"] in PLAN_FORMS:
                self.open("plan")
            else:
                self.close()
            return
        if current["kind"] != "new" and self.app._conversation_locked():
            raise ValueError("正在处理当前任务，请完成或停止后再保存。")
        try:
            if action in {"editor_open", "editor_move", "editor_review"}:
                if current["kind"] != "plan":
                    raise ValueError("请先返回完整方案编辑。")
                target = data.get("target")
                if action == "editor_open":
                    if data.get("kind") not in PLAN_FORMS:
                        raise ValueError("方案编辑栏目不存在。")
                    self.open(data["kind"], target)
                    return
                if not isinstance(target, str):
                    raise ValueError("请选择当前方案中的项目。")
                if action == "editor_move":
                    offset = data.get("offset")
                    if type(offset) is not int or offset not in {-1, 1}:
                        raise ValueError("步骤移动方向无效。")
                    self.app.session.move_plan_step(target, offset)
                else:
                    self.app.session.mark_key_work_reviewed([target])
                LOG.info("Web plan action: action=%s task=%s", action, self.app.session.task_id)
                self.app.refresh()
                self.open("plan")
                return
            if action != "editor_save" or current["kind"] == "plan":
                raise ValueError("编辑操作不存在。")
            values = data.get("values")
            if not isinstance(values, dict) or set(values) != {f["key"] for f in current["fields"]} or any(not isinstance(v, str) for v in values.values()):
                raise ValueError("编辑字段格式不正确。")
            values = {k: v.strip() for k, v in values.items()}
            for field in current["fields"]:
                if field.get("required") and not values[field["key"]]:
                    raise ValueError(field["label"] + "不能为空。")
                if field.get("type") in {"lines", "choices"}:
                    items = list(dict.fromkeys(line.strip() for line in values[field["key"]].splitlines() if line.strip()))
                    if field.get("type") == "choices" and set(items) - {c["id"] for c in field["choices"]}:
                        raise ValueError("关联项目已变化，请重新选择。")
                    values[field["key"]] = items
            self.save(current, values)
            LOG.info("Web editor saved: kind=%s task=%s model_request=False", current["kind"], self.app.session.task_id)
            self.close("saved")
            self.app.status_var.set("修改已保存，请核对当前内容。")
            self.app.refresh()
            if current["kind"] in PLAN_FORMS:
                self.open("plan")
        except (ValueError, SessionStateError) as exc:
            if self.current:
                self.current["error"] = str(exc)
            LOG.warning("Web editor save rejected: kind=%s reason=%s", current["kind"], exc)
            raise
        except Exception:
            if self.current:
                self.current["error"] = "修改未保存，请重试；详细原因已记录到 Debug 控制台。"
            LOG.exception("Web editor save failed: kind=%s", current["kind"])
            raise

    def save(self, current, values):
        session = self.app.session
        kind, target = current["kind"], current["target"]
        if kind == "requirement":
            prefix, key = target.split(":", 1)
            if prefix == "r":
                session.edit_requirement(key, values["text"])
            else:
                session.edit_proposal(key, values["text"])
        elif kind == "goal":
            session.edit_plan_goal(values["summary"])
        elif kind == "goal_details":
            session.edit_plan_goal_details(**values)
        elif kind == "step":
            session.edit_plan_step(target, **values)
        elif kind == "step_new":
            session.add_plan_step(**values)
        elif kind == "step_delete":
            session.delete_plan_step(target)
        elif kind in SECTIONS:
            if kind == "key_work":
                row = next(r for r in session.plan["content"]["key_work"] if r["key_work_id"] == target)
                values["depends_on_key_work_ids"] = list(row.get("depends_on_key_work_ids", []))
            session.edit_plan_section(kind, target, values)
        elif kind == "note":
            from .finalization import edit_final_note
            edit_final_note(session, "note-" + uuid4().hex, values["text"])
        elif kind == "new":
            self.app._install_session(self.app._new_preferred_session(), reason="new_session")
        elif kind == "conflict":
            session.mark_conflict_compatible(target)
