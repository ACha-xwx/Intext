"""Build an editable, source-linked inventory; never reads settings or sessions."""
import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_name("notification_messages_20261013.md")
MODULES = ("ui", "guided_flow", "conversation", "response_workspace", "settings_ui", "web_workspace",
           "web_editors", "history_workspace", "model_directory_refresh", "web_debug", "session", "preferences")
STATUS = {"status_var", "settings_status_var", "skill_status_var", "final_status_var", "model_directory_status_var"}


def text(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(text(x) if isinstance(x, ast.Constant) else "{" + ast.unparse(x.value) + "}" for x in node.values)
    if isinstance(node, ast.IfExp):
        return text(node.body) + " ／ " + text(node.orelse)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return text(node.left) + text(node.right)
    return "{" + ast.unparse(node) + "}"


def cell(value):
    return str(value).replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


rows = []
suppressed = []
dynamic = []
errors = []
generation = []
for module in MODULES:
    path = ROOT / "src/promptsmith" / (module + ".py")
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}

    def owner(node):
        while node in parents:
            node = parents[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return node
        return None

    def add(target, node, level, title, body, route):
        function = owner(node)
        function_name = function.name if function else "模块初始化"
        location = "../../" + path.relative_to(ROOT).as_posix()
        target.append((level, title, body, f"{module}.{function_name}", route,
                       f"[{module}.py:{node.lineno}]({location}#L{node.lineno})"))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        name = node.func.attr
        if name in {"_show_error", "_show_info", "_show_warning"} and len(node.args) >= 2:
            add(rows, node, {"_show_error":"错误", "_show_info":"提示", "_show_warning":"警告"}[name],
                text(node.args[0]), text(node.args[1]), "原消息框 → Web通知")
        elif name == "set" and isinstance(node.func.value, ast.Attribute) and node.func.value.attr in STATUS and node.args:
            body = text(node.args[0])
            function = owner(node)
            search_progress = node.func.value.attr == "skill_status_var" and (
                body.startswith(("正在联网搜索 Skill", "正在查找本地 Skill")) or
                function is not None and function.name in {"_local_skill_search_progress", "_network_skill_search_progress"})
            target = suppressed if search_progress or body.startswith(("最终结果：", "目录状态：")) or body in ("", "有未保存的设置。", "有未保存设置。", "修改将自动保存。") or node.func.value.attr == "model_directory_status_var" else rows
            route = "搜索区当前进度及 Debug；不弹通知" if search_progress else node.func.value.attr + " → 通知"
            add(target, node, "随正文分类", "自动标题", body, route)
        elif name == "_set_busy" and len(node.args) > 1:
            add(rows, node, "随正文分类", "自动标题", text(node.args[1]), "业务操作状态 → 通知")
        elif name == "_set_status" and module == "model_directory_refresh" and len(node.args) > 1 and text(node.args[1]):
            add(rows, node, "随正文分类", "自动标题", "{provider}：" + text(node.args[1]), "全部供应商后台目录 → 通知")
    for node in ast.walk(tree):
        # Batch validation is surfaced by the public answer bridge. The rest
        # of SessionState is represented by its existing UI error boundaries.
        if module == "session":
            function = owner(node)
            if function is None or function.name not in {"record_question_answers", "_restore_answer_round"}:
                continue
            # Restoration validates internal fields before exposing a single
            # helpful SessionStateError. Internal cause strings stay in Debug.
            if function.name == "_restore_answer_round" and not (
                isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)
                and isinstance(node.exc.func, ast.Name) and node.exc.func.id == "SessionStateError"):
                continue
        if module == "preferences" and (owner(node) is None or owner(node).name != "rename_provider_profile"):
            continue
        if isinstance(node, ast.keyword) and node.arg in {"error", "sync_error"} and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str) and node.value.value:
            add(errors, node, "错误", "动态错误正文", text(node.value), "桥接/Debug返回用户错误")
        if isinstance(node, ast.Return) and module == "ui" and owner(node) and owner(node).name == "generation_failure_message" and node.value:
            add(dynamic, node, "错误", "模型失败帮助", text(node.value), "真实调用失败原因 → 状态/错误通知")
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = {ast.unparse(target).split(".")[-1] for target in targets}
            function = owner(node)
            if module == "ui" and function and function.name == "generation_failure_message":
                value = node.value
                mapping = value if isinstance(value, ast.Dict) else value.value if isinstance(value, ast.Subscript) and isinstance(value.value, ast.Dict) else value.func.value if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and isinstance(value.func.value, ast.Dict) else None
                if mapping is not None:
                    for key, branch in zip(mapping.keys, mapping.values):
                        add(generation, node, "错误", ", ".join(sorted(names)) + " / " + text(key),
                            text(branch), "模型失败帮助的用途分支")
                elif names & {"reason", "retained", "wait"}:
                    add(generation, node, "错误", ", ".join(sorted(names)), text(value), "模型失败帮助的条件/附加说明")
            if names & {"message", "text", "status_text", "_skill_search_status_text", "_delivery_status_text", "_settings_load_warning", "error"}:
                value = node.value
                if value and any(isinstance(part, (ast.Constant, ast.JoinedStr)) and (isinstance(part, ast.JoinedStr) or isinstance(part.value, str)) for part in ast.walk(value)):
                    function = owner(node)
                    if function and any(isinstance(part, ast.Call) and isinstance(part.func, ast.Attribute) and part.func.attr in {"set", "_show_error", "_show_info", "_show_warning", "_set_status", "_set_busy"} for part in ast.walk(function)):
                        add(dynamic, node, "附加/动态", ", ".join(sorted(names)), text(value), "上表动态占位来源；部分为兼容入口")
        elif isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and node.exc.args:
            add(errors, node, "错误/校验", "动态错误正文", text(node.exc.args[0]), "操作被拒绝 → 通知；部分为兼容入口")

front = []
def arguments(expression):
    result=[];start=0;depth=0;quote=None;escaped=False
    for index,char in enumerate(expression):
        if escaped: escaped=False;continue
        if char=="\\" and quote: escaped=True;continue
        if quote:
            if char==quote: quote=None
            continue
        if char in "\"'`": quote=char;continue
        if char in "([{": depth+=1
        elif char in ")]}": depth-=1
        elif char=="," and depth==0:
            result.append(expression[start:index].strip());start=index+1
    result.append(expression[start:].strip())
    return result

for name in ("workspace", "settings", "history", "editors", "debug", "tutorial"):
    path = ROOT / "resources/ui/workspace" / (name + ".js")
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        # Keep exact conditional/template expressions; they explain dynamic text.
        for match in re.finditer(r'(?:toast|this\.feedback|showError|promptsmithNotifications\.(?:show|sync))\(', line):
            if line.startswith("function toast") or line.startswith("function showError") or line.lstrip().startswith("feedback(text"):
                continue
            start = match.end(); depth = 1; quote = None; escaped = False; end = start
            for end in range(start, len(line)):
                char = line[end]
                if escaped: escaped = False; continue
                if char == "\\" and quote: escaped = True; continue
                if quote:
                    if char == quote: quote = None
                    continue
                if char in "\"'`": quote = char; continue
                if char == "(": depth += 1
                elif char == ")":
                    depth -= 1
                    if not depth: break
            expression = line[start:end]
            args = arguments(expression)
            body = args[1] if "sync" in match.group() or "showError" in match.group() else args[0]
            if body in ('""', "''") or body == "text":
                continue
            if not re.search("[\u4e00-\u9fff]", body) and not any(x in body for x in ("error", "status", "notice.body", "record.error", "next.error")):
                continue
            context = {"workspace":"工作区操作/同步/模型任务", "settings":"设置校验/自动保存/供应商操作", "history":"历史会话保存/重命名", "editors":"内容编辑", "debug":"Debug同步/复制/手动保存/目录", "tutorial":"教程完成/跳过状态保存"}[name]
            front.append((context, body, f"[{name}.js:{number}](../../resources/ui/workspace/{name}.js#L{number})"))


def table(title, prefix, values):
    result = ["\n## " + title + "\n", "|编号|级别|标题/变量|正文或模板|触发入口|来源/呈现|代码|", "|---|---|---|---|---|---|---|"]
    for index, row in enumerate(values, 1):
        result.append("|" + prefix + f"{index:03d}|" + "|".join(cell(x) for x in row) + "|")
    return "\n".join(result)


doc = """# 右上角通知文案总清单

本清单对应 2026-10-13 本轮源码。修改时可以直接告诉我编号与新表述，例如“把 F003 改成……”。花括号代表运行时内容；`／` 分隔同一位置的不同分支；`<br>` 代表换行。

## 阅读范围

- 当前 WebView2 工作区、设置、历史、编辑和独立 Debug 的操作反馈都通过右上角通知；每张有独立5秒倒计时条，右端向左匀速缩短，结束后自动收回，也可手动关闭。关闭后相同快照不重放；真实的新操作仍可发新消息。
- B 表包含 Python 全部消息框/业务状态产生点，不省略罕见分支。代码保留一些 Tk 兼容或旧操作入口，不能据此认为主界面重新增加了相应按钮。例如旧“确认模型/保存设置/最终复核”相关文字属于保留逻辑，当前正常设置流程自动保存、有效配置即可使用。
- D 表展开 B 表的变量与拼接来源，G 表逐条列出模型失败帮助的可枚举分支，E 表列 Web 操作校验的原始动态错误。`{str(exc)}`、`{error.message}`、服务返回正文、文件路径/模型/Skill名称等不是有限固定字符串，实际消息会按真实原因替换并脱敏；完整异常链留在 Debug。其余底层 API/会话/schema 异常也可能进入这些模板，未将数百种底层错误虚称为有限文案。
- 不把每条 INFO/DEBUG 日志弹到右上；提问、回答、需求/方案内容、显式核对或删除确认、静态字段帮助仍在原位置。表 S 是被明确过滤的派生状态，不属于当前会弹出的文案。
- 本地/联网 Skill 搜索进行中的逐文件、逐查询、逐候选进度只更新搜索区和 Debug，不触发右上通知。搜索完成（包括无匹配）、取消或整体失败保留汇总通知；动态正文只有满足这项过滤规则后才会弹出。
- WebView2 尚未启动时（缺少运行库、依赖或后端启动失败）的启动错误只能由启动器/原生系统提示显示；显式 `--renderer tk` 兼容模式继续使用原生反馈，右上卡片是正常 WebView2 的呈现。

## 四种自动标题

|类型|默认标题|图标颜色|
|---|---|---|
|成功|操作成功|绿色|
|提示|消息提示|默认文字色|
|警告|请注意|黄色|
|错误|操作未完成|红色|

Python `_show_*` 的原始标题优先；普通业务状态采用默认标题。状态正文含“失败/错误/未完成/无法/异常”显示错误；含未配置/过期/未保存等显示警告；已保存/已复制/成功等显示成功，其余显示提示。

## F：前端固定文案和动态通知入口

表达式保留条件及动态错误的来源，避免遗漏 `result.error` 等实际提示。括号中的 key 仅用于去重，不会显示给用户。

|编号|页面/触发类型|当前正文/条件表达式|代码|
|---|---|---|---|
"""
for index, (name, expression, location) in enumerate(front, 1):
    doc += "|F" + f"{index:03d}|{name}|{cell(expression)}|{location}|\n"
doc += table("B：业务消息与操作状态（全部产生点）", "B", rows)
doc += table("D：动态正文、附加说明和分支来源", "D", dynamic)
doc += table("G：模型失败提示中可枚举的全部原因与下一步", "G", generation)
doc += table("E：Web操作及编辑校验可能返回的错误正文", "E", errors)
doc += table("S：不弹出的草稿/派生状态（排除说明）", "S", suppressed)
doc += "\n\n## 运行时模板补充\n\n|编号|触发|正文|\n|---|---|---|\n|R001|日志保存成功|已保存 {saved_sequence} 条：{path}|\n|R002|日志保存失败|保存失败：{脱敏后的保存错误}|\n|R003|模型请求失败/思考任务失败|{record.error}；来自实际任务错误，可能含服务原因和下一步|\n|R004|历史后台保存失败|历史会话保存未完成。现有内容仍在当前窗口，请点击重试保存；详细原因见 Debug。|\n|R005|旧会话导入失败|旧会话导入未完成，可通过文件菜单打开；原文件已保留。|\n|R006|启动设置恢复警告|设置恢复提醒：{_settings_load_warning}|\n|R007|编辑必填为空|{字段中文名称}不能为空。|\n|R008|自动保存成功|已自动保存。模型配置可直接使用。 ／ 已自动保存。填写模型 ID 和 API Key 后即可使用。 ／ 已自动保存。启动窗口大小下次启动生效。|\n|R009|Web桥接未就绪/关闭/超时/同步错误|见 E 表 DesktopApi 分支；保持当前内容并重试|\n\n错误通知中的“重试保存”、设置页“重试自动保存”是动作标签，不属于错误正文。关闭按钮无正文，屏幕阅读器名称为“关闭通知”。\n"
OUT.write_text(doc, encoding="utf-8")
print(dict(frontend=len(front), business=len(rows), dynamic=len(dynamic), generation=len(generation), validation=len(errors), excluded=len(suppressed), output=str(OUT)))
