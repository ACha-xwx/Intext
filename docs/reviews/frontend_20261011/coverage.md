# 前端审查覆盖索引

项目：PromptSmith

目标：PromptSmith 仓库根目录

访问范围：source_runtime；发现状态：reconciled

> 本文件由台账生成。结构校验不验证证据真实性，也不等于产品认证。

## 覆盖结论

- schema_valid: True
- audit_coverage_closed: False
- plan_complete: True
- production_gates_satisfied: False

## 分母与状态

~~~json
{
  "pages_in_scope": 34,
  "pages_excluded": 0,
  "definitions": 68,
  "instances_in_scope": 492,
  "checks": {
    "blocked": 369,
    "not_applicable": 544,
    "passed": 3225
  },
  "scenarios": {
    "blocked": 2,
    "passed": 47
  },
  "findings": {
    "P1": 2,
    "P2": 11
  },
  "component_plans": 492,
  "tasks": 15
}
~~~

## 页面与组件实例

| 页面 | 路由 | 组件实例 | 已通过 / 失败 / 阻塞 / 未检查 / 不适用 |
|---|---|---|---|
| PAGE-001 主工作区与历史侧栏 | workspace | 21 | 153 / 0 / 1 / 0 / 19 |
| PAGE-002 访谈与模型处理 | workspace / interview | 15 | 113 / 0 / 1 / 0 / 11 |
| PAGE-003 Skill选择 | workspace / skills | 16 | 117 / 0 / 0 / 0 / 15 |
| PAGE-004 最终提示词 | workspace / result | 6 | 47 / 0 / 0 / 0 / 5 |
| PAGE-005 一起核对需求 | workspace / panel:requirements | 9 | 68 / 0 / 0 / 0 / 8 |
| PAGE-006 核对方案 | workspace / panel:plan | 8 | 62 / 0 / 0 / 0 / 6 |
| PAGE-007 任务摘要 | workspace / panel:summary | 2 | 20 / 0 / 0 / 0 / 0 |
| PAGE-008 语气和附注 | workspace / panel:result | 4 | 33 / 0 / 0 / 0 / 3 |
| PAGE-009 模型选择 | workspace / model-picker | 15 | 113 / 0 / 0 / 0 / 11 |
| PAGE-010 整理深度菜单 | workspace / menu:depth | 4 | 33 / 0 / 0 / 0 / 3 |
| PAGE-011 任务类型菜单 | workspace / menu:category | 3 | 26 / 0 / 0 / 0 / 2 |
| PAGE-012 文件菜单 | workspace / menu:file | 5 | 40 / 0 / 0 / 0 / 4 |
| PAGE-013 历史会话操作菜单 | history / menu | 4 | 33 / 0 / 0 / 0 / 3 |
| PAGE-014 搜索历史 | history / dialog:search | 4 | 33 / 0 / 1 / 0 / 3 |
| PAGE-015 重命名历史 | history / dialog:rename | 5 | 40 / 0 / 1 / 0 / 4 |
| PAGE-016 删除历史 | history / dialog:delete | 5 | 40 / 0 / 0 / 0 / 4 |
| PAGE-017 Web设置 · 模型 | settings / 模型 | 21 | 151 / 0 / 1 / 0 / 21 |
| PAGE-018 Web设置 · Skill 搜索 | settings / Skill 搜索 | 18 | 130 / 0 / 0 / 0 / 18 |
| PAGE-019 Web设置 · 界面 | settings / 界面 | 8 | 60 / 0 / 0 / 0 / 8 |
| PAGE-020 Web设置 · 会话与导出 | settings / 会话与导出 | 11 | 81 / 0 / 0 / 0 / 11 |
| PAGE-021 Web设置 · 诊断 | settings / 诊断 | 11 | 81 / 0 / 0 / 0 / 11 |
| PAGE-022 Web Debug控制台 | debug.html | 9 | 68 / 0 / 0 / 0 / 8 |
| PAGE-023 Tk统一对话回退 | native notebook:0 | 54 | 317 / 0 / 64 / 0 / 65 |
| PAGE-024 Tk方案兼容编辑 | native notebook:1 | 31 | 177 / 0 / 34 / 0 / 44 |
| PAGE-025 Tk Skill详情 | native notebook:2 | 28 | 157 / 0 / 30 / 0 / 43 |
| PAGE-026 Tk结果高级选项 | native notebook:3 | 34 | 199 / 0 / 39 / 0 / 43 |
| PAGE-027 Tk五类设置 | native notebook:4 | 90 | 467 / 0 / 126 / 0 / 167 |
| PAGE-028 Tk多文本编辑（需求/目标/栏目） | native dialog / Tk多文本编辑（需求/目标/栏目） | 4 | 32 / 0 / 4 / 0 / 0 |
| PAGE-029 Tk步骤编辑 | native dialog / Tk步骤编辑 | 11 | 81 / 0 / 11 / 0 / 0 |
| PAGE-030 Tk关键工作编辑 | native dialog / Tk关键工作编辑 | 10 | 74 / 0 / 10 / 0 / 0 |
| PAGE-031 Tk简短输入（附注/目标/新增需求） | native dialog / Tk简短输入（附注/目标/新增需求） | 3 | 22 / 0 / 3 / 0 / 3 |
| PAGE-032 Tk Debug回退 | native dialog / Tk Debug回退 | 8 | 60 / 0 / 8 / 0 / 0 |
| PAGE-033 Tk菜单/审查浮层/模型菜单 | native dialog / Tk菜单/审查浮层/模型菜单 | 10 | 73 / 0 / 10 / 0 / 1 |
| PAGE-034 Windows文件对话框 | native dialog / Windows文件对话框 | 5 | 20 / 0 / 24 / 0 / 0 |

## 组件处置

| 实例 | 蓝图 | 处置 | 任务 | 理由 |
|---|---|---|---|---|
| CMP-001 | BP-001 | refactor | TASK-002 | 本位置 PAGE-001 / 外壳与页内滚动：已复现 FND-002，按共享根因修改本调用处。 |
| CMP-002 | BP-002 | retain |  | 本位置 PAGE-001 / Hero目标说明：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-003 | BP-003 | retain |  | 本位置 PAGE-001 / 品牌与历史日期组：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-004 | BP-004 | retain |  | 本位置 PAGE-001 / 新建对话：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-005 | BP-004 | retain |  | 本位置 PAGE-001 / 搜索历史：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-006 | BP-004 | retain |  | 本位置 PAGE-001 / 收起/展开：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-007 | BP-004 | retain |  | 本位置 PAGE-001 / 文件：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-008 | BP-004 | refactor | TASK-002, TASK-006 | 本位置 PAGE-001 / 核对需求：已复现 FND-002,FND-006，按共享根因修改本调用处。 |
| CMP-009 | BP-004 | refactor | TASK-002, TASK-006 | 本位置 PAGE-001 / 核对方案：已复现 FND-002,FND-006，按共享根因修改本调用处。 |
| CMP-010 | BP-004 | refactor | TASK-002, TASK-006 | 本位置 PAGE-001 / 任务摘要：已复现 FND-002,FND-006，按共享根因修改本调用处。 |
| CMP-011 | BP-004 | refactor | TASK-002 | 本位置 PAGE-001 / 设置：已复现 FND-002，按共享根因修改本调用处。 |
| CMP-012 | BP-005 | retain |  | 本位置 PAGE-001 / 历史记录选择模板：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-013 | BP-006 | retain |  | 本位置 PAGE-001 / 历史悬停菜单入口：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-014 | BP-007 | retain |  | 本位置 PAGE-001 / 历史失败与重试：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-015 | BP-008 | retain |  | 本位置 PAGE-001 / Toast操作反馈：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-016 | BP-009 | retain |  | 本位置 PAGE-001 / 下一步恢复动作：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-017 | BP-010 | investigate | TASK-014 | 本位置 PAGE-001 / 消息输入：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-018 | BP-004 | retain |  | 本位置 PAGE-001 / 选择模型：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-019 | BP-004 | retain |  | 本位置 PAGE-001 / 整理深度：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-020 | BP-004 | retain |  | 本位置 PAGE-001 / 任务类型：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-021 | BP-004 | retain |  | 本位置 PAGE-001 / 发送消息：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-022 | BP-011 | retain |  | 本位置 PAGE-002 / 用户目标与回答气泡：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-023 | BP-012 | retain |  | 本位置 PAGE-002 / 补答按钮：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-024 | BP-013 | retain |  | 本位置 PAGE-002 / AI问题全文：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-025 | BP-010 | investigate | TASK-014 | 本位置 PAGE-002 / 逐题回答框：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-026 | BP-004 | retain |  | 本位置 PAGE-002 / 提交回答：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-027 | BP-004 | retain |  | 本位置 PAGE-002 / 跳过该题：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-028 | BP-013 | retain |  | 本位置 PAGE-002 / 历史问题文本：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-029 | BP-004 | retain |  | 本位置 PAGE-002 / 取消补答：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-030 | BP-009 | retain |  | 本位置 PAGE-002 / 继续询问/结束追问：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-031 | BP-014 | refactor | TASK-008 | 本位置 PAGE-002 / 处理状态与点阵：已复现 FND-008，按共享根因修改本调用处。 |
| CMP-032 | BP-014 | refactor | TASK-008 | 本位置 PAGE-002 / 思考子展开器：已复现 FND-008，按共享根因修改本调用处。 |
| CMP-033 | BP-015 | refactor | TASK-008 | 本位置 PAGE-002 / 思考内容与独立滚动：已复现 FND-008，按共享根因修改本调用处。 |
| CMP-034 | BP-016 | retain |  | 本位置 PAGE-002 / 检索活动记录：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-035 | BP-008 | retain |  | 本位置 PAGE-002 / 模型失败文字：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-036 | BP-017 | retain |  | 本位置 PAGE-003 / Skill阶段说明：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-037 | BP-009 | retain |  | 本位置 PAGE-003 / find_skills：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-038 | BP-009 | retain |  | 本位置 PAGE-003 / find_online：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-039 | BP-009 | retain |  | 本位置 PAGE-003 / integrate：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-040 | BP-009 | retain |  | 本位置 PAGE-003 / direct_skills：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-041 | BP-009 | retain |  | 本位置 PAGE-003 / skip_skills：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-042 | BP-018 | retain |  | 本位置 PAGE-003 / 来源 全部来源：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-043 | BP-018 | retain |  | 本位置 PAGE-003 / 来源 本地：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-044 | BP-018 | retain |  | 本位置 PAGE-003 / 来源 联网：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-045 | BP-018 | retain |  | 本位置 PAGE-003 / 来源 内置：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-046 | BP-018 | retain |  | 本位置 PAGE-003 / 来源 已选：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-047 | BP-018 | retain |  | 本位置 PAGE-003 / 推荐/全部切换：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-048 | BP-019 | retain |  | 本位置 PAGE-003 / Skill名称/来源/推荐列：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-049 | BP-020 | retain |  | 本位置 PAGE-003 / 选用此Skill/已选中：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-050 | BP-020 | retain |  | 本位置 PAGE-003 / 取消选用：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-051 | BP-020 | retain |  | 本位置 PAGE-003 / 用途摘要与详细说明：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-052 | BP-021 | retain |  | 本位置 PAGE-004 / 提示词分层正文：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-053 | BP-009 | retain |  | 本位置 PAGE-004 / copy：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-054 | BP-009 | retain |  | 本位置 PAGE-004 / export：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-055 | BP-009 | retain |  | 本位置 PAGE-004 / save：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-056 | BP-009 | retain |  | 本位置 PAGE-004 / confirm_final：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-057 | BP-004 | retain |  | 本位置 PAGE-004 / 语气和附注：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-058 | BP-022 | refactor | TASK-005, TASK-006 | 本位置 PAGE-005 / 面板外壳与关闭：已复现 FND-005,FND-006，按共享根因修改本调用处。 |
| CMP-059 | BP-023 | refactor | TASK-007 | 本位置 PAGE-005 / 需求表头/行/选择：已复现 FND-007，按共享根因修改本调用处。 |
| CMP-060 | BP-023 | refactor | TASK-007 | 本位置 PAGE-005 / 完整需求详情：已复现 FND-007，按共享根因修改本调用处。 |
| CMP-061 | BP-023 | refactor | TASK-007 | 本位置 PAGE-005 / 冲突与确认前原因：已复现 FND-007，按共享根因修改本调用处。 |
| CMP-062 | BP-009 | retain |  | 本位置 PAGE-005 / edit_requirement：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-063 | BP-009 | retain |  | 本位置 PAGE-005 / remove_requirement：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-064 | BP-009 | retain |  | 本位置 PAGE-005 / accept_requirement：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-065 | BP-009 | retain |  | 本位置 PAGE-005 / adopt_requirement：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-066 | BP-009 | retain |  | 本位置 PAGE-005 / confirm_requirements：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-067 | BP-022 | refactor | TASK-005, TASK-006 | 本位置 PAGE-006 / 面板外壳与关闭：已复现 FND-005,FND-006，按共享根因修改本调用处。 |
| CMP-068 | BP-017 | retain |  | 本位置 PAGE-006 / 方案状态：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-069 | BP-021 | retain |  | 本位置 PAGE-006 / 方案全文与折叠章节：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-070 | BP-009 | retain |  | 本位置 PAGE-006 / edit_plan_goal：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-071 | BP-009 | retain |  | 本位置 PAGE-006 / edit_plan：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-072 | BP-009 | retain |  | 本位置 PAGE-006 / review_plan：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-073 | BP-009 | retain |  | 本位置 PAGE-006 / confirm_plan：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-074 | BP-009 | retain |  | 本位置 PAGE-006 / find_skills：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-075 | BP-022 | refactor | TASK-005, TASK-006 | 本位置 PAGE-007 / 面板外壳与关闭：已复现 FND-005,FND-006，按共享根因修改本调用处。 |
| CMP-076 | BP-021 | retain |  | 本位置 PAGE-007 / 当前摘要全文：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-077 | BP-022 | refactor | TASK-005, TASK-006 | 本位置 PAGE-008 / 面板外壳与关闭：已复现 FND-005,FND-006，按共享根因修改本调用处。 |
| CMP-078 | BP-024 | retain |  | 本位置 PAGE-008 / 提示词语气：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-079 | BP-025 | retain |  | 本位置 PAGE-008 / 用户附注/空说明：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-080 | BP-009 | retain |  | 本位置 PAGE-008 / 添加附注：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-081 | BP-022 | refactor | TASK-004, TASK-005, TASK-006 | 本位置 PAGE-009 / 模型浮层外壳：已复现 FND-004,FND-005,FND-006，按共享根因修改本调用处。 |
| CMP-082 | BP-026 | refactor | TASK-004, TASK-009 | 本位置 PAGE-009 / 搜索模型：已复现 FND-004,FND-009，按共享根因修改本调用处。 |
| CMP-083 | BP-026 | refactor | TASK-004, TASK-009 | 本位置 PAGE-009 / 清空搜索：已复现 FND-004,FND-009，按共享根因修改本调用处。 |
| CMP-084 | BP-026 | refactor | TASK-004, TASK-009 | 本位置 PAGE-009 / 模型列表与无结果：已复现 FND-004,FND-009，按共享根因修改本调用处。 |
| CMP-085 | BP-027 | refactor | TASK-004 | 本位置 PAGE-009 / OpenAI供应商与图标：已复现 FND-004，按共享根因修改本调用处。 |
| CMP-086 | BP-027 | refactor | TASK-004 | 本位置 PAGE-009 / Anthropic供应商与图标：已复现 FND-004，按共享根因修改本调用处。 |
| CMP-087 | BP-027 | refactor | TASK-004 | 本位置 PAGE-009 / Google供应商与图标：已复现 FND-004，按共享根因修改本调用处。 |
| CMP-088 | BP-027 | refactor | TASK-004 | 本位置 PAGE-009 / xAI供应商与图标：已复现 FND-004，按共享根因修改本调用处。 |
| CMP-089 | BP-027 | refactor | TASK-004 | 本位置 PAGE-009 / DeepSeek供应商与图标：已复现 FND-004，按共享根因修改本调用处。 |
| CMP-090 | BP-028 | retain |  | 本位置 PAGE-009 / 模型名称/说明/能力图标/选中勾：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-091 | BP-029 | retain |  | 本位置 PAGE-009 / 思考强度 low：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-092 | BP-029 | retain |  | 本位置 PAGE-009 / 思考强度 medium：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-093 | BP-029 | retain |  | 本位置 PAGE-009 / 思考强度 high：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-094 | BP-029 | retain |  | 本位置 PAGE-009 / 思考强度 max：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-095 | BP-030 | retain |  | 本位置 PAGE-009 / 思考强度信号与滑块：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-096 | BP-022 | refactor | TASK-005, TASK-006 | 本位置 PAGE-010 / 浮层菜单外壳：已复现 FND-005,FND-006，按共享根因修改本调用处。 |
| CMP-097 | BP-031 | retain |  | 本位置 PAGE-010 / quick：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-098 | BP-031 | retain |  | 本位置 PAGE-010 / standard：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-099 | BP-031 | retain |  | 本位置 PAGE-010 / deep：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-100 | BP-022 | refactor | TASK-005, TASK-006 | 本位置 PAGE-011 / 浮层菜单外壳：已复现 FND-005,FND-006，按共享根因修改本调用处。 |
| CMP-101 | BP-031 | retain |  | 本位置 PAGE-011 / 自动判断：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-102 | BP-031 | retain |  | 本位置 PAGE-011 / CATEGORY_LABELS全枚举：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-103 | BP-022 | refactor | TASK-005, TASK-006 | 本位置 PAGE-012 / 浮层菜单外壳：已复现 FND-005,FND-006，按共享根因修改本调用处。 |
| CMP-104 | BP-031 | retain |  | 本位置 PAGE-012 / new：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-105 | BP-031 | retain |  | 本位置 PAGE-012 / open：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-106 | BP-031 | refactor | TASK-012 | 本位置 PAGE-012 / save：已复现 FND-012，按共享根因修改本调用处。 |
| CMP-107 | BP-031 | refactor | TASK-012 | 本位置 PAGE-012 / save_as：已复现 FND-012，按共享根因修改本调用处。 |
| CMP-108 | BP-022 | refactor | TASK-006 | 本位置 PAGE-013 / 历史菜单外壳：已复现 FND-006，按共享根因修改本调用处。 |
| CMP-109 | BP-032 | retain |  | 本位置 PAGE-013 / 重命名：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-110 | BP-032 | retain |  | 本位置 PAGE-013 / 置顶/取消置顶：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-111 | BP-032 | retain |  | 本位置 PAGE-013 / 删除：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-112 | BP-033 | refactor | TASK-006 | 本位置 PAGE-014 / 模态框与关闭：已复现 FND-006，按共享根因修改本调用处。 |
| CMP-113 | BP-034 | refactor | TASK-009, TASK-014 | 本位置 PAGE-014 / 搜索/名称输入：已复现 FND-009，按共享根因修改本调用处。 |
| CMP-114 | BP-035 | retain |  | 本位置 PAGE-014 / 搜索匹配记录：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-115 | BP-017 | retain |  | 本位置 PAGE-014 / 没有匹配说明：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-116 | BP-033 | refactor | TASK-006 | 本位置 PAGE-015 / 模态框与关闭：已复现 FND-006，按共享根因修改本调用处。 |
| CMP-117 | BP-034 | refactor | TASK-009, TASK-014 | 本位置 PAGE-015 / 搜索/名称输入：已复现 FND-009，按共享根因修改本调用处。 |
| CMP-118 | BP-004 | retain |  | 本位置 PAGE-015 / 取消：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-119 | BP-004 | retain |  | 本位置 PAGE-015 / 保存：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-120 | BP-008 | retain |  | 本位置 PAGE-015 / 字段/操作错误：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-121 | BP-033 | refactor | TASK-006 | 本位置 PAGE-016 / 模态框与关闭：已复现 FND-006，按共享根因修改本调用处。 |
| CMP-122 | BP-004 | retain |  | 本位置 PAGE-016 / 取消：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-123 | BP-004 | retain |  | 本位置 PAGE-016 / 删除：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-124 | BP-008 | retain |  | 本位置 PAGE-016 / 字段/操作错误：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-125 | BP-017 | retain |  | 本位置 PAGE-016 / 删除范围说明：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-126 | BP-036 | refactor | TASK-003, TASK-010 | 本位置 PAGE-017 / 分类Tab和标题：已复现 FND-003,FND-010，按共享根因修改本调用处。 |
| CMP-127 | BP-004 | refactor | TASK-003 | 本位置 PAGE-017 / 返回工作区：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-128 | BP-004 | refactor | TASK-003 | 本位置 PAGE-017 / 恢复本类默认：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-129 | BP-004 | refactor | TASK-003 | 本位置 PAGE-017 / 保存设置：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-130 | BP-037 | refactor | TASK-003 | 本位置 PAGE-017 / 草稿/保存/请求/错误状态：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-131 | BP-038 | refactor | TASK-003 | 本位置 PAGE-017 / connection.provider：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-132 | BP-038 | refactor | TASK-003 | 本位置 PAGE-017 / connection.protocol：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-133 | BP-038 | refactor | TASK-003 | 本位置 PAGE-017 / connection.base_url：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-134 | BP-038 | refactor | TASK-003 | 本位置 PAGE-017 / connection.model：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-135 | BP-039 | refactor | TASK-003, TASK-014 | 本位置 PAGE-017 / API Key输入与保存保护：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-136 | BP-004 | refactor | TASK-003 | 本位置 PAGE-017 / 清空密钥：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-137 | BP-004 | refactor | TASK-003 | 本位置 PAGE-017 / 获取模型：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-138 | BP-004 | refactor | TASK-003 | 本位置 PAGE-017 / 测试连接：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-139 | BP-004 | refactor | TASK-003 | 本位置 PAGE-017 / 确认：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-140 | BP-037 | refactor | TASK-003 | 本位置 PAGE-017 / 模型确认依据：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-141 | BP-038 | refactor | TASK-003 | 本位置 PAGE-017 / 生成 timeout（秒）：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-142 | BP-038 | refactor | TASK-003 | 本位置 PAGE-017 / 连接 / 模型列表 timeout（秒）：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-143 | BP-038 | refactor | TASK-003 | 本位置 PAGE-017 / max_tokens（0 = 自动）：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-144 | BP-038 | refactor | TASK-003 | 本位置 PAGE-017 / temperature（auto / 留空 / 数值）：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-145 | BP-038 | refactor | TASK-003 | 本位置 PAGE-017 / top_p（留空 = 不发送）：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-146 | BP-038 | refactor | TASK-003 | 本位置 PAGE-017 / 思考强度：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-147 | BP-036 | refactor | TASK-003, TASK-010 | 本位置 PAGE-018 / 分类Tab和标题：已复现 FND-003,FND-010，按共享根因修改本调用处。 |
| CMP-148 | BP-004 | refactor | TASK-003 | 本位置 PAGE-018 / 返回工作区：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-149 | BP-004 | refactor | TASK-003 | 本位置 PAGE-018 / 恢复本类默认：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-150 | BP-004 | refactor | TASK-003 | 本位置 PAGE-018 / 保存设置：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-151 | BP-037 | refactor | TASK-003 | 本位置 PAGE-018 / 草稿/保存/请求/错误状态：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-152 | BP-038 | refactor | TASK-003 | 本位置 PAGE-018 / 筛选模型 timeout（秒）：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-153 | BP-038 | refactor | TASK-003 | 本位置 PAGE-018 / 每个联网来源 timeout（秒）：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-154 | BP-038 | refactor | TASK-003 | 本位置 PAGE-018 / 本地正文粗查上限：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-155 | BP-038 | refactor | TASK-003 | 本位置 PAGE-018 / 名称 / 描述初筛上限：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-156 | BP-038 | refactor | TASK-003 | 本位置 PAGE-018 / AI 内容核验上限：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-157 | BP-038 | refactor | TASK-003 | 本位置 PAGE-018 / 默认展示推荐数量：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-158 | BP-038 | refactor | TASK-003 | 本位置 PAGE-018 / 每个联网来源收集上限：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-159 | BP-038 | refactor | TASK-003 | 本位置 PAGE-018 / 联网来源缓存秒数（0 = 不复用）：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-160 | BP-038 | refactor | TASK-003 | 本位置 PAGE-018 / AI 筛选累计输入字符上限：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-161 | BP-038 | refactor | TASK-003 | 本位置 PAGE-018 / 每项 Skill 正文节选字符上限：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-162 | BP-038 | refactor | TASK-003 | 本位置 PAGE-018 / 额外本地 Skill 目录（每行一个）：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-163 | BP-038 | refactor | TASK-003 | 本位置 PAGE-018 / Skill 索引地址：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-164 | BP-038 | refactor | TASK-003 | 本位置 PAGE-018 / 网页检索地址（含 {query}）：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-165 | BP-036 | refactor | TASK-003, TASK-010 | 本位置 PAGE-019 / 分类Tab和标题：已复现 FND-003,FND-010，按共享根因修改本调用处。 |
| CMP-166 | BP-004 | refactor | TASK-003 | 本位置 PAGE-019 / 返回工作区：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-167 | BP-004 | refactor | TASK-003 | 本位置 PAGE-019 / 恢复本类默认：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-168 | BP-004 | refactor | TASK-003 | 本位置 PAGE-019 / 保存设置：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-169 | BP-037 | refactor | TASK-003 | 本位置 PAGE-019 / 草稿/保存/请求/错误状态：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-170 | BP-038 | refactor | TASK-003 | 本位置 PAGE-019 / 启动窗口宽度（保持 16:9）：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-171 | BP-038 | refactor | TASK-003 | 本位置 PAGE-019 / 字号基准（pt，显示为125%）：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-172 | BP-038 | refactor | TASK-003 | 本位置 PAGE-019 / 输入区与模型菜单主题：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-173 | BP-036 | refactor | TASK-003, TASK-010 | 本位置 PAGE-020 / 分类Tab和标题：已复现 FND-003,FND-010，按共享根因修改本调用处。 |
| CMP-174 | BP-004 | refactor | TASK-003 | 本位置 PAGE-020 / 返回工作区：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-175 | BP-004 | refactor | TASK-003 | 本位置 PAGE-020 / 恢复本类默认：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-176 | BP-004 | refactor | TASK-003 | 本位置 PAGE-020 / 保存设置：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-177 | BP-037 | refactor | TASK-003 | 本位置 PAGE-020 / 草稿/保存/请求/错误状态：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-178 | BP-038 | refactor | TASK-003 | 本位置 PAGE-020 / 新会话思考深度：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-179 | BP-038 | refactor | TASK-003 | 本位置 PAGE-020 / 默认交付语气：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-180 | BP-038 | refactor | TASK-003 | 本位置 PAGE-020 / 会话保存目录（留空 = 默认）：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-181 | BP-038 | refactor | TASK-003 | 本位置 PAGE-020 / Markdown 导出目录（留空 = 默认）：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-182 | BP-004 | refactor | TASK-003 | 本位置 PAGE-020 / 会话目录浏览：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-183 | BP-004 | refactor | TASK-003 | 本位置 PAGE-020 / 导出目录浏览：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-184 | BP-036 | refactor | TASK-003, TASK-010 | 本位置 PAGE-021 / 分类Tab和标题：已复现 FND-003,FND-010，按共享根因修改本调用处。 |
| CMP-185 | BP-004 | refactor | TASK-003 | 本位置 PAGE-021 / 返回工作区：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-186 | BP-004 | refactor | TASK-003 | 本位置 PAGE-021 / 恢复本类默认：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-187 | BP-004 | refactor | TASK-003 | 本位置 PAGE-021 / 保存设置：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-188 | BP-037 | refactor | TASK-003 | 本位置 PAGE-021 / 草稿/保存/请求/错误状态：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-189 | BP-038 | refactor | TASK-003 | 本位置 PAGE-021 / 控制台默认显示级别：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-190 | BP-038 | refactor | TASK-003 | 本位置 PAGE-021 / 控制台自动滚动：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-191 | BP-038 | refactor | TASK-003 | 本位置 PAGE-021 / 控制台缓存条数：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-192 | BP-038 | refactor | TASK-003 | 本位置 PAGE-021 / 控制台显示行数上限：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-193 | BP-038 | refactor | TASK-003 | 本位置 PAGE-021 / 开启 Debug 控制台：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-194 | BP-017 | refactor | TASK-003 | 本位置 PAGE-021 / 日志目录与手动保存说明：已复现 FND-003，按共享根因修改本调用处。 |
| CMP-195 | BP-040 | retain |  | 本位置 PAGE-022 / Debug标题与缓存计数：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-196 | BP-041 | retain |  | 本位置 PAGE-022 / 日志级别：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-197 | BP-041 | retain |  | 本位置 PAGE-022 / 自动滚动：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-198 | BP-041 | retain |  | 本位置 PAGE-022 / 复制日志：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-199 | BP-041 | retain |  | 本位置 PAGE-022 / 清空显示：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-200 | BP-041 | retain |  | 本位置 PAGE-022 / 保存日志：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-201 | BP-041 | retain |  | 本位置 PAGE-022 / 打开日志目录：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-202 | BP-042 | retain |  | 本位置 PAGE-022 / 日志正文与颜色：源码及可得证据未发现确定偏差；保留当前职责，限定在已执行条件。 |
| CMP-203 | BP-043 | refactor | TASK-011 | 本位置 PAGE-022 / 保存状态和错误：已复现 FND-011，按共享根因修改本调用处。 |
| CMP-204 | BP-044 | investigate | TASK-014 | 本位置 PAGE-023 / 页面壳与滚动区：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-205 | BP-045 | investigate | TASK-014 | 本位置 PAGE-023 / 为零基础学习者规划 7 天 Python 入门：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-206 | BP-046 | investigate | TASK-014 | 本位置 PAGE-023 / requirements_page_canvas：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-207 | BP-045 | investigate | TASK-014 | 本位置 PAGE-023 / 为零基础学习者规划 7 天 Python 入门：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-208 | BP-045 | investigate | TASK-014 | 本位置 PAGE-023 / 选配 Skill：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-209 | BP-045 | investigate | TASK-014 | 本位置 PAGE-023 / 目录状态：尚未开始：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-210 | BP-045 | investigate | TASK-014 | 本位置 PAGE-023 / Skill 可用于具体步骤；你也可以直接跳过。：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-211 | BP-047 | investigate | TASK-014 | 本位置 PAGE-023 / 来源：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-212 | BP-048 | investigate | TASK-014 | 本位置 PAGE-023 / conversation_skill_source_filter：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-213 | BP-049 | investigate | TASK-014 | 本位置 PAGE-023 / conversation_skill_show_all：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-214 | BP-047 | investigate | TASK-014 | 本位置 PAGE-023 / conversation_skill_candidate_count：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-215 | BP-050 | investigate | TASK-014 | 本位置 PAGE-023 / conversation_skill_candidates_tree：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-216 | BP-051 | investigate | TASK-014 | 本位置 PAGE-023 / conversation_skill_select_skills：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-217 | BP-051 | investigate | TASK-014 | 本位置 PAGE-023 / conversation_skill_cancel_skills：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-218 | BP-052 | investigate | TASK-014 | 本位置 PAGE-023 / conversation_skill_details_text：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-219 | BP-045 | investigate | TASK-014 | 本位置 PAGE-023 / 你的任务提示词：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-220 | BP-045 | investigate | TASK-014 | 本位置 PAGE-023 / 提示词已生成，可复制和导出。：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-221 | BP-052 | investigate | TASK-014 | 本位置 PAGE-023 / Text：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-222 | BP-046 | investigate | TASK-014 | 本位置 PAGE-023 / conversation_scrollbar：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-223 | BP-045 | investigate | TASK-014 | 本位置 PAGE-023 / conversation_hero：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-224 | BP-046 | investigate | TASK-014 | 本位置 PAGE-023 / conversation_composer：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-225 | BP-052 | investigate | TASK-014 | 本位置 PAGE-023 / conversation_input：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-226 | BP-046 | investigate | TASK-014 | 本位置 PAGE-023 / conversation_model_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-227 | BP-046 | investigate | TASK-014 | 本位置 PAGE-023 / conversation_send_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-228 | BP-045 | investigate | TASK-014 | 本位置 PAGE-023 / 描述你想完成的目标…：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-229 | BP-044 | investigate | TASK-014 | 本位置 PAGE-024 / 页面壳与滚动区：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-230 | BP-046 | investigate | TASK-014 | 本位置 PAGE-024 / plan_page_canvas：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-231 | BP-047 | investigate | TASK-014 | 本位置 PAGE-024 / 核对方案：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-232 | BP-047 | investigate | TASK-014 | 本位置 PAGE-024 / 目标、要求、步骤和关键工作一起看；需要调整时展开下面的编辑区。：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-233 | BP-052 | investigate | TASK-014 | 本位置 PAGE-024 / plan_reading_text：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-234 | BP-051 | investigate | TASK-014 | 本位置 PAGE-024 / optional_skill_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-235 | BP-051 | investigate | TASK-014 | 本位置 PAGE-024 / 返回当前需求：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-236 | BP-047 | investigate | TASK-014 | 本位置 PAGE-024 / 完整初始方案：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-237 | BP-047 | investigate | TASK-014 | 本位置 PAGE-024 / 方案 已确认 · 版本 1 · 来源需求 v1 · 已确认 v1：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-238 | BP-047 | investigate | TASK-014 | 本位置 PAGE-024 / 当前方案已经确认；如改变任务目标或硬约束，请使用“修改需求”。：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-239 | BP-047 | investigate | TASK-014 | 本位置 PAGE-024 / 目标：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-240 | BP-052 | investigate | TASK-014 | 本位置 PAGE-024 / plan_goal_text：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-241 | BP-051 | investigate | TASK-014 | 本位置 PAGE-024 / 保存目标修改：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-242 | BP-051 | investigate | TASK-014 | 本位置 PAGE-024 / 编辑受众与范围：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-243 | BP-051 | investigate | TASK-014 | 本位置 PAGE-024 / generate_plan_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-244 | BP-050 | investigate | TASK-014 | 本位置 PAGE-024 / plan_steps_tree：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-245 | BP-051 | investigate | TASK-014 | 本位置 PAGE-024 / 编辑步骤：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-246 | BP-051 | investigate | TASK-014 | 本位置 PAGE-024 / 新增步骤：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-247 | BP-051 | investigate | TASK-014 | 本位置 PAGE-024 / 删除步骤：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-248 | BP-051 | investigate | TASK-014 | 本位置 PAGE-024 / 上移：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-249 | BP-051 | investigate | TASK-014 | 本位置 PAGE-024 / 下移：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-250 | BP-048 | investigate | TASK-014 | 本位置 PAGE-024 / plan_section_combo：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-251 | BP-051 | investigate | TASK-014 | 本位置 PAGE-024 / 编辑选中栏目：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-252 | BP-052 | investigate | TASK-014 | 本位置 PAGE-024 / plan_overview_text：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-253 | BP-047 | investigate | TASK-014 | 本位置 PAGE-024 / 关键工作：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-254 | BP-050 | investigate | TASK-014 | 本位置 PAGE-024 / plan_key_work_tree：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-255 | BP-051 | investigate | TASK-014 | 本位置 PAGE-024 / 编辑关键工作：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-256 | BP-051 | investigate | TASK-014 | 本位置 PAGE-024 / review_key_work_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-257 | BP-051 | investigate | TASK-014 | 本位置 PAGE-024 / 修改需求：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-258 | BP-051 | investigate | TASK-014 | 本位置 PAGE-024 / confirm_plan_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-259 | BP-051 | investigate | TASK-014 | 本位置 PAGE-024 / ▸ 编辑方案内容：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-260 | BP-044 | investigate | TASK-014 | 本位置 PAGE-025 / 页面壳与滚动区：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-261 | BP-046 | investigate | TASK-014 | 本位置 PAGE-025 / skills_page_canvas：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-262 | BP-047 | investigate | TASK-014 | 本位置 PAGE-025 / Agent Skill 参考：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-263 | BP-047 | investigate | TASK-014 | 本位置 PAGE-025 / 确认初始方案后，可查找本地或联网 Agent Skill，也可直接跳过。：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-264 | BP-051 | investigate | TASK-014 | 本位置 PAGE-025 / skill_find_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-265 | BP-051 | investigate | TASK-014 | 本位置 PAGE-025 / skill_online_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-266 | BP-047 | investigate | TASK-014 | 本位置 PAGE-025 / skill_search_url_label：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-267 | BP-053 | investigate | TASK-014 | 本位置 PAGE-025 / skill_search_url_entry：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-268 | BP-051 | investigate | TASK-014 | 本位置 PAGE-025 / skill_select_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-269 | BP-051 | investigate | TASK-014 | 本位置 PAGE-025 / skill_analyze_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-270 | BP-051 | investigate | TASK-014 | 本位置 PAGE-025 / skill_cancel_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-271 | BP-051 | investigate | TASK-014 | 本位置 PAGE-025 / skill_cancel_request_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-272 | BP-051 | investigate | TASK-014 | 本位置 PAGE-025 / skill_skip_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-273 | BP-051 | investigate | TASK-014 | 本位置 PAGE-025 / skill_integrate_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-274 | BP-047 | investigate | TASK-014 | 本位置 PAGE-025 / 目录状态：尚未开始：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-275 | BP-051 | investigate | TASK-014 | 本位置 PAGE-025 / skill_direct_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-276 | BP-047 | investigate | TASK-014 | 本位置 PAGE-025 / 来源：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-277 | BP-048 | investigate | TASK-014 | 本位置 PAGE-025 / skill_source_filter：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-278 | BP-049 | investigate | TASK-014 | 本位置 PAGE-025 / skill_show_all：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-279 | BP-047 | investigate | TASK-014 | 本位置 PAGE-025 / skill_candidate_count：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-280 | BP-050 | investigate | TASK-014 | 本位置 PAGE-025 / skill_candidates_tree：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-281 | BP-047 | investigate | TASK-014 | 本位置 PAGE-025 / 已选 Skill：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-282 | BP-050 | investigate | TASK-014 | 本位置 PAGE-025 / skill_selected_tree：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-283 | BP-052 | investigate | TASK-014 | 本位置 PAGE-025 / skill_details_text：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-284 | BP-050 | investigate | TASK-014 | 本位置 PAGE-025 / skill_prerequisites_tree：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-285 | BP-047 | investigate | TASK-014 | 本位置 PAGE-025 / 核对结果：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-286 | BP-048 | investigate | TASK-014 | 本位置 PAGE-025 / skill_prerequisite_status_combo：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-287 | BP-051 | investigate | TASK-014 | 本位置 PAGE-025 / skill_update_prerequisite_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-288 | BP-044 | investigate | TASK-014 | 本位置 PAGE-026 / 页面壳与滚动区：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-289 | BP-046 | investigate | TASK-014 | 本位置 PAGE-026 / export_page_canvas：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-290 | BP-047 | investigate | TASK-014 | 本位置 PAGE-026 / 最终方案与任务提示：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-291 | BP-047 | investigate | TASK-014 | 本位置 PAGE-026 / 最终结果：草稿待确认 · 版本 1：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-292 | BP-051 | investigate | TASK-014 | 本位置 PAGE-026 / 生成无 Skill 草稿：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-293 | BP-051 | investigate | TASK-014 | 本位置 PAGE-026 / 确认当前最终结果：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-294 | BP-047 | investigate | TASK-014 | 本位置 PAGE-026 / 语气：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-295 | BP-048 | investigate | TASK-014 | 本位置 PAGE-026 / final_tone_combo：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-296 | BP-051 | investigate | TASK-014 | 本位置 PAGE-026 / copy_draft_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-297 | BP-051 | investigate | TASK-014 | 本位置 PAGE-026 / copy_final_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-298 | BP-051 | investigate | TASK-014 | 本位置 PAGE-026 / 导出 Markdown：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-299 | BP-051 | investigate | TASK-014 | 本位置 PAGE-026 / 导出草稿：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-300 | BP-052 | investigate | TASK-014 | 本位置 PAGE-026 / final_preview_text：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-301 | BP-047 | investigate | TASK-014 | 本位置 PAGE-026 / 最终任务提示预览：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-302 | BP-052 | investigate | TASK-014 | 本位置 PAGE-026 / final_task_prompt_text：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-303 | BP-050 | investigate | TASK-014 | 本位置 PAGE-026 / m2_suggestions_tree：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-304 | BP-052 | investigate | TASK-014 | 本位置 PAGE-026 / m2_suggestion_details_text：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-305 | BP-051 | investigate | TASK-014 | 本位置 PAGE-026 / accept_m2_suggestion_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-306 | BP-051 | investigate | TASK-014 | 本位置 PAGE-026 / reject_m2_suggestion_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-307 | BP-051 | investigate | TASK-014 | 本位置 PAGE-026 / process_m2_suggestion_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-308 | BP-050 | investigate | TASK-014 | 本位置 PAGE-026 / m4_changes_tree：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-309 | BP-052 | investigate | TASK-014 | 本位置 PAGE-026 / m4_change_details_text：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-310 | BP-051 | investigate | TASK-014 | 本位置 PAGE-026 / accept_m4_change_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-311 | BP-051 | investigate | TASK-014 | 本位置 PAGE-026 / reject_m4_change_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-312 | BP-050 | investigate | TASK-014 | 本位置 PAGE-026 / final_review_items_tree：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-313 | BP-052 | investigate | TASK-014 | 本位置 PAGE-026 / final_review_details_text：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-314 | BP-051 | investigate | TASK-014 | 本位置 PAGE-026 / process_final_review_item_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-315 | BP-051 | investigate | TASK-014 | 本位置 PAGE-026 / 添加用户附注：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-316 | BP-047 | investigate | TASK-014 | 本位置 PAGE-026 / 正文由结构化方案统一渲染；原需求和步骤变化请返回上游修改。：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-317 | BP-051 | investigate | TASK-014 | 本位置 PAGE-026 / 复制提示：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-318 | BP-051 | investigate | TASK-014 | 本位置 PAGE-026 / 导出方案和提示：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-319 | BP-051 | investigate | TASK-014 | 本位置 PAGE-026 / 保存会话：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-320 | BP-051 | investigate | TASK-014 | 本位置 PAGE-026 / 修改方案：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-321 | BP-051 | investigate | TASK-014 | 本位置 PAGE-026 / result_optional_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-322 | BP-044 | investigate | TASK-014 | 本位置 PAGE-027 / 页面壳与滚动区：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-323 | BP-046 | investigate | TASK-014 | 本位置 PAGE-027 / settings_page_canvas：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-324 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 设置：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-325 | BP-051 | investigate | TASK-014 | 本位置 PAGE-027 / settings_return_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-326 | BP-046 | investigate | TASK-014 | 本位置 PAGE-027 / settings_category_0_page_canvas：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-327 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 服务名称：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-328 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / provider_combo：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-329 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 协议：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-330 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / protocol_combo：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-331 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 接口地址：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-332 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / api_base_entry：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-333 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 模型 ID：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-334 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / api_model_entry：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-335 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / API Key：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-336 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / api_key_entry：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-337 | BP-051 | investigate | TASK-014 | 本位置 PAGE-027 / model_list_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-338 | BP-051 | investigate | TASK-014 | 本位置 PAGE-027 / test_connection_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-339 | BP-051 | investigate | TASK-014 | 本位置 PAGE-027 / confirm_model_settings_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-340 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 模型设置已确认，可以返回工作区继续。：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-341 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 生成 timeout（秒）：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-342 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_generation_timeout：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-343 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 连接 / 模型列表 timeout（秒）：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-344 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_connection_timeout：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-345 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / max_tokens（0 = 自动）：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-346 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_max_tokens：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-347 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / temperature（auto / 留空 / 数值）：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-348 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_temperature：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-349 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / top_p（留空 = 不发送）：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-350 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_top_p：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-351 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 思考强度：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-352 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_reasoning_effort：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-353 | BP-046 | investigate | TASK-014 | 本位置 PAGE-027 / settings_category_1_page_canvas：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-354 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 筛选模型 timeout（秒）：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-355 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_search_model_timeout：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-356 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 每个联网来源 timeout（秒）：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-357 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_search_timeout：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-358 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 本地正文粗查上限：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-359 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_local_candidates：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-360 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 名称 / 描述初筛上限：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-361 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_shortlist_limit：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-362 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / AI 内容核验上限：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-363 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_review_limit：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-364 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 默认展示推荐数量：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-365 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_display_limit：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-366 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 每个联网来源收集上限：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-367 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_network_candidates：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-368 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 联网来源缓存秒数（0 = 不复用）：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-369 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_network_cache_seconds：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-370 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / AI 筛选累计输入字符上限：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-371 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_input_budget：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-372 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 每项 Skill 正文节选字符上限：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-373 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_excerpt_chars：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-374 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 额外本地 Skill 目录（每行一个）：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-375 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_extra_skill_roots：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-376 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / Skill 索引地址：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-377 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_skill_search_url：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-378 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 网页检索地址（含 {query}）：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-379 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_web_search_url：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-380 | BP-046 | investigate | TASK-014 | 本位置 PAGE-027 / settings_category_2_page_canvas：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-381 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 启动窗口宽度（保持 16:9）：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-382 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_window_width：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-383 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 字号基准（pt，显示为125%）：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-384 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_font_size：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-385 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 输入区与模型菜单主题：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-386 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_composer_theme：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-387 | BP-046 | investigate | TASK-014 | 本位置 PAGE-027 / settings_category_3_page_canvas：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-388 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 新会话思考深度：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-389 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_default_thinking：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-390 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 默认交付语气：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-391 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_default_tone：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-392 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 会话保存目录（留空 = 默认）：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-393 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_session_directory：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-394 | BP-051 | investigate | TASK-014 | 本位置 PAGE-027 / 浏览…：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-395 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / Markdown 导出目录（留空 = 默认）：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-396 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_export_directory：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-397 | BP-051 | investigate | TASK-014 | 本位置 PAGE-027 / 浏览…：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-398 | BP-046 | investigate | TASK-014 | 本位置 PAGE-027 / settings_category_4_page_canvas：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-399 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 控制台默认显示级别：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-400 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_debug_level：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-401 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 控制台自动滚动：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-402 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_debug_autoscroll：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-403 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 控制台缓存条数：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-404 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_debug_history：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-405 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 控制台显示行数上限：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-406 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / setting_debug_lines：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-407 | BP-054 | investigate | TASK-014 | 本位置 PAGE-027 / debug_console_toggle：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-408 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / %TEMP%\PromptSmith\logs：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-409 | BP-047 | investigate | TASK-014 | 本位置 PAGE-027 / 模型设置已保存，其它分类的编辑需单独保存。：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-410 | BP-051 | investigate | TASK-014 | 本位置 PAGE-027 / settings_restore_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-411 | BP-051 | investigate | TASK-014 | 本位置 PAGE-027 / settings_save_button：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-412 | BP-055 | investigate | TASK-014 | 本位置 PAGE-028 / 动态字段标签：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-413 | BP-055 | investigate | TASK-014 | 本位置 PAGE-028 / 文本编辑与滚动：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-414 | BP-055 | investigate | TASK-014 | 本位置 PAGE-028 / 取消：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-415 | BP-055 | investigate | TASK-014 | 本位置 PAGE-028 / 保存：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-416 | BP-056 | investigate | TASK-014 | 本位置 PAGE-029 / title：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-417 | BP-056 | investigate | TASK-014 | 本位置 PAGE-029 / purpose：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-418 | BP-056 | investigate | TASK-014 | 本位置 PAGE-029 / inputs：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-419 | BP-056 | investigate | TASK-014 | 本位置 PAGE-029 / actions：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-420 | BP-056 | investigate | TASK-014 | 本位置 PAGE-029 / outputs：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-421 | BP-056 | investigate | TASK-014 | 本位置 PAGE-029 / completion_criteria：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-422 | BP-056 | investigate | TASK-014 | 本位置 PAGE-029 / 依赖步骤：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-423 | BP-056 | investigate | TASK-014 | 本位置 PAGE-029 / 关联需求：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-424 | BP-056 | investigate | TASK-014 | 本位置 PAGE-029 / 取消：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-425 | BP-056 | investigate | TASK-014 | 本位置 PAGE-029 / 保存草稿：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-426 | BP-056 | investigate | TASK-014 | 本位置 PAGE-029 / 校验错误：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-427 | BP-057 | investigate | TASK-014 | 本位置 PAGE-030 / title：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-428 | BP-057 | investigate | TASK-014 | 本位置 PAGE-030 / goal：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-429 | BP-057 | investigate | TASK-014 | 本位置 PAGE-030 / inputs：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-430 | BP-057 | investigate | TASK-014 | 本位置 PAGE-030 / outputs：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-431 | BP-057 | investigate | TASK-014 | 本位置 PAGE-030 / checkpoints：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-432 | BP-057 | investigate | TASK-014 | 本位置 PAGE-030 / 关联步骤：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-433 | BP-057 | investigate | TASK-014 | 本位置 PAGE-030 / 关联需求：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-434 | BP-057 | investigate | TASK-014 | 本位置 PAGE-030 / 取消：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-435 | BP-057 | investigate | TASK-014 | 本位置 PAGE-030 / 保存草稿：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-436 | BP-057 | investigate | TASK-014 | 本位置 PAGE-030 / 校验错误：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-437 | BP-058 | investigate | TASK-014 | 本位置 PAGE-031 / 单行输入：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-438 | BP-058 | investigate | TASK-014 | 本位置 PAGE-031 / 确定：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-439 | BP-058 | investigate | TASK-014 | 本位置 PAGE-031 / 取消：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-440 | BP-059 | investigate | TASK-014 | 本位置 PAGE-032 / 级别筛选：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-441 | BP-059 | investigate | TASK-014 | 本位置 PAGE-032 / 自动滚动：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-442 | BP-059 | investigate | TASK-014 | 本位置 PAGE-032 / 复制：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-443 | BP-059 | investigate | TASK-014 | 本位置 PAGE-032 / 清空显示：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-444 | BP-059 | investigate | TASK-014 | 本位置 PAGE-032 / 保存日志：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-445 | BP-059 | investigate | TASK-014 | 本位置 PAGE-032 / 日志目录：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-446 | BP-059 | investigate | TASK-014 | 本位置 PAGE-032 / 日志正文与严重颜色：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-447 | BP-059 | investigate | TASK-014 | 本位置 PAGE-032 / 错误与保存状态：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-448 | BP-060 | investigate | TASK-014 | 本位置 PAGE-033 / 文件菜单（新建/打开/保存/另存/退出）：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-449 | BP-060 | investigate | TASK-014 | 本位置 PAGE-033 / 需求核对表与操作：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-450 | BP-060 | investigate | TASK-014 | 本位置 PAGE-033 / 方案核对章节与操作：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-451 | BP-060 | investigate | TASK-014 | 本位置 PAGE-033 / 任务摘要：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-452 | BP-060 | investigate | TASK-014 | 本位置 PAGE-033 / 语气和附注：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-453 | BP-060 | investigate | TASK-014 | 本位置 PAGE-033 / 模型搜索/清空/目录：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-454 | BP-060 | investigate | TASK-014 | 本位置 PAGE-033 / 五供应商选择：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-455 | BP-060 | investigate | TASK-014 | 本位置 PAGE-033 / 四档思考选择：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-456 | BP-060 | investigate | TASK-014 | 本位置 PAGE-033 / 任务类型与整理深度菜单：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-457 | BP-061 | investigate | TASK-014 | 本位置 PAGE-034 / 打开会话：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-458 | BP-061 | refactor | TASK-012, TASK-014 | 本位置 PAGE-034 / 保存/另存会话：已复现 FND-012，按共享根因修改本调用处。 |
| CMP-459 | BP-061 | investigate | TASK-014 | 本位置 PAGE-034 / 导出Markdown：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-460 | BP-061 | investigate | TASK-014 | 本位置 PAGE-034 / 设置目录选择：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-461 | BP-061 | refactor | TASK-012, TASK-014 | 本位置 PAGE-034 / 覆盖/取消/无权限错误：已复现 FND-012，按共享根因修改本调用处。 |
| CMP-462 | BP-009 | refactor | TASK-001 | 本位置 PAGE-002 / 整合忙态取消入口（当前Web遗漏）：已复现 FND-001，按共享根因修改本调用处。 |
| CMP-463 | BP-062 | investigate | TASK-014 | 本位置 PAGE-023 / 动态回复动作 · 查找本地 Skill：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-464 | BP-062 | investigate | TASK-014 | 本位置 PAGE-023 / 动态回复动作 · 继续联网查找：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-465 | BP-062 | investigate | TASK-014 | 本位置 PAGE-023 / 动态回复动作 · 整合所选 Skill：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-466 | BP-062 | investigate | TASK-014 | 本位置 PAGE-023 / 动态回复动作 · 用已选 Skill 直接生成：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-467 | BP-062 | investigate | TASK-014 | 本位置 PAGE-023 / 动态回复动作 · 跳过 Skill：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-468 | BP-062 | investigate | TASK-014 | 本位置 PAGE-023 / 动态回复动作 · 复制提示词：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-469 | BP-062 | investigate | TASK-014 | 本位置 PAGE-023 / 动态回复动作 · 导出方案和提示词：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-470 | BP-062 | investigate | TASK-014 | 本位置 PAGE-023 / 动态回复动作 · 保存会话：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-471 | BP-062 | investigate | TASK-014 | 本位置 PAGE-023 / 动态回复动作 · 确认最终提示词：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-472 | BP-062 | investigate | TASK-014 | 本位置 PAGE-023 / 动态回复动作 · 语气和附注：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-473 | BP-062 | investigate | TASK-014 | 本位置 PAGE-023 / 动态回复动作 · 取消本次整合：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-474 | BP-062 | investigate | TASK-014 | 本位置 PAGE-023 / 动态回复动作 · 继续询问：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-475 | BP-062 | investigate | TASK-014 | 本位置 PAGE-023 / 动态回复动作 · 结束追问：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-476 | BP-063 | investigate | TASK-014 | 本位置 PAGE-023 / 玻璃动作 · 补答loop：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-477 | BP-063 | investigate | TASK-014 | 本位置 PAGE-023 / 玻璃动作 · 整理深度：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-478 | BP-063 | investigate | TASK-014 | 本位置 PAGE-023 / 玻璃动作 · 任务类型：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-479 | BP-064 | investigate | TASK-014 | 本位置 PAGE-023 / 逐题 · 题意全文：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-480 | BP-064 | investigate | TASK-014 | 本位置 PAGE-023 / 逐题 · 多行回答：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-481 | BP-064 | investigate | TASK-014 | 本位置 PAGE-023 / 逐题 · 圆形提交：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-482 | BP-064 | investigate | TASK-014 | 本位置 PAGE-023 / 逐题 · 红色跳过：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-483 | BP-065 | investigate | TASK-014 | 本位置 PAGE-023 / 思考 · 处理外展开：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-484 | BP-065 | investigate | TASK-014 | 本位置 PAGE-023 / 思考 · 思考子展开：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-485 | BP-065 | investigate | TASK-014 | 本位置 PAGE-023 / 思考 · 独立思考滚动：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-486 | BP-065 | investigate | TASK-014 | 本位置 PAGE-023 / 思考 · 活动内容：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-487 | BP-066 | investigate | TASK-014 | 本位置 PAGE-023 / 正文 · 用户气泡：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-488 | BP-066 | investigate | TASK-014 | 本位置 PAGE-023 / 正文 · 提示词标题与正文：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-489 | BP-067 | investigate | TASK-014 | 本位置 PAGE-023 / 底部 · 占位/插入光标/文本：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-490 | BP-067 | investigate | TASK-014 | 本位置 PAGE-023 / 底部 · 选择模型：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-491 | BP-067 | investigate | TASK-014 | 本位置 PAGE-023 / 底部 · 常驻发送：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |
| CMP-492 | BP-068 | investigate | TASK-014 | 本位置 PAGE-033 / Canvas键盘焦点与激活：源码及可得证据未发现确定偏差；具体运行/平台证据不足，先补证后决定保留或变更。 |

## 问题索引

| 问题 | 级别 | 置信度 | 状态 | 页面 / 实例 |
|---|---|---|---|---|
| FND-001 整合提示词忙态没有可见取消入口 | P1 | confirmed | resolved | PAGE-002, CMP-462 |
| FND-002 最大字号下小窗header越界 | P2 | confirmed | resolved | PAGE-001, CMP-001, CMP-008, CMP-009, CMP-010, CMP-011 |
| FND-003 小窗大字号设置正文与保存区域被挤出 | P2 | confirmed | resolved | PAGE-017, PAGE-018, PAGE-019, PAGE-020, PAGE-021, CMP-126, CMP-127, CMP-128, CMP-129, CMP-130, CMP-131, CMP-132, CMP-133, CMP-134, CMP-135, CMP-136, CMP-137, CMP-138, CMP-139, CMP-140, CMP-141, CMP-142, CMP-143, CMP-144, CMP-145, CMP-146, CMP-147, CMP-148, CMP-149, CMP-150, CMP-151, CMP-152, CMP-153, CMP-154, CMP-155, CMP-156, CMP-157, CMP-158, CMP-159, CMP-160, CMP-161, CMP-162, CMP-163, CMP-164, CMP-165, CMP-166, CMP-167, CMP-168, CMP-169, CMP-170, CMP-171, CMP-172, CMP-173, CMP-174, CMP-175, CMP-176, CMP-177, CMP-178, CMP-179, CMP-180, CMP-181, CMP-182, CMP-183, CMP-184, CMP-185, CMP-186, CMP-187, CMP-188, CMP-189, CMP-190, CMP-191, CMP-192, CMP-193, CMP-194 |
| FND-004 模型浮层上界未约束，搜索和首供应商被裁切 | P2 | confirmed | resolved | PAGE-009, CMP-081, CMP-082, CMP-083, CMP-084, CMP-085, CMP-086, CMP-087, CMP-088, CMP-089 |
| FND-005 公共dialog浮层缺可访问名称 | P2 | confirmed | resolved | PAGE-005, PAGE-006, PAGE-007, PAGE-008, PAGE-009, PAGE-010, PAGE-011, PAGE-012, CMP-058, CMP-067, CMP-075, CMP-077, CMP-081, CMP-096, CMP-100, CMP-103 |
| FND-006 浮层焦点进入、返回及展开语义不完整 | P2 | confirmed | resolved | PAGE-001, PAGE-005, PAGE-006, PAGE-007, PAGE-008, PAGE-009, PAGE-010, PAGE-011, PAGE-012, PAGE-013, PAGE-014, PAGE-015, PAGE-016, CMP-058, CMP-067, CMP-075, CMP-077, CMP-081, CMP-096, CMP-100, CMP-103, CMP-108, CMP-112, CMP-116, CMP-121, CMP-008, CMP-009, CMP-010 |
| FND-007 需求表只有鼠标选择，键盘无法编辑指定需求 | P1 | confirmed | resolved | PAGE-005, CMP-059, CMP-060, CMP-061 |
| FND-008 收起思考后不可见内容仍进入Tab顺序 | P2 | confirmed | resolved | PAGE-002, CMP-031, CMP-032, CMP-033 |
| FND-009 搜索和重命名Enter未保护中文组合输入 | P2 | confirmed | resolved | PAGE-009, PAGE-014, PAGE-015, CMP-082, CMP-083, CMP-084, CMP-113, CMP-117 |
| FND-010 设置Tab声明角色但缺方向键与单TabStop | P2 | confirmed | resolved | PAGE-017, PAGE-018, PAGE-019, PAGE-020, PAGE-021, CMP-126, CMP-147, CMP-165, CMP-173, CMP-184 |
| FND-011 Debug同步恢复后残留过期红色错误 | P2 | confirmed | resolved | PAGE-022, CMP-203 |
| FND-012 原生保存创建目录失败未进入恢复提示 | P2 | confirmed | resolved | PAGE-012, PAGE-034, CMP-458, CMP-461, CMP-106, CMP-107 |
| FND-013 14项旧UI测试仍依赖退役控件和旧合同 | P2 | confirmed | resolved |  |

## 任务顺序

| 任务 | 阶段 | 负责人 | 依赖 | 状态 |
|---|---|---|---|---|
| TASK-015 补齐本地逐实例条件动作与生命周期证据 | 0 | UI开发/离线验收 |  | verified |
| TASK-001 整合提示词忙态没有可见取消入口 | 1 | 前端/UI开发 |  | verified |
| TASK-007 需求表只有鼠标选择，键盘无法编辑指定需求 | 1 | 前端/UI开发 |  | verified |
| TASK-002 最大字号下小窗header越界 | 2 | 前端/UI开发 |  | verified |
| TASK-003 小窗大字号设置正文与保存区域被挤出 | 2 | 前端/UI开发 |  | verified |
| TASK-004 模型浮层上界未约束，搜索和首供应商被裁切 | 2 | 前端/UI开发 |  | verified |
| TASK-005 公共dialog浮层缺可访问名称 | 2 | 前端/UI开发 |  | verified |
| TASK-006 浮层焦点进入、返回及展开语义不完整 | 2 | 前端/UI开发 | TASK-005 | verified |
| TASK-008 收起思考后不可见内容仍进入Tab顺序 | 2 | 前端/UI开发 |  | verified |
| TASK-009 搜索和重命名Enter未保护中文组合输入 | 2 | 前端/UI开发 |  | verified |
| TASK-010 设置Tab声明角色但缺方向键与单TabStop | 2 | 前端/UI开发 |  | verified |
| TASK-011 Debug同步恢复后残留过期红色错误 | 3 | 前端/UI开发 |  | verified |
| TASK-012 原生保存创建目录失败未进入恢复提示 | 3 | 前端/UI开发 |  | verified |
| TASK-013 14项旧UI测试仍依赖退役控件和旧合同 | 3 | 测试维护者 |  | verified |
| TASK-014 补齐平台与真实服务验收 | 4 | Windows验收者/模型集成开发 | TASK-001, TASK-002, TASK-003, TASK-004, TASK-005, TASK-006, TASK-007, TASK-008, TASK-009, TASK-010, TASK-011, TASK-012, TASK-013 | blocked |

## 发布门槛

| 门槛 | 必需 | 状态 | 证据 / 理由 |
|---|---|---|---|
| 核心流程的当前取消与键盘核对入口 | True | passed | EV-005, EV-014, EV-023, EV-029, EV-037, EV-042 对应根因本地修复与回归通过；真实平台发布条件由GATE-004独立保留blocked。 |
| 支持小窗+合法字号不阻断核心操作 | True | passed | EV-005, EV-006, EV-024, EV-025, EV-026, EV-042 对应根因本地修复与回归通过；真实平台发布条件由GATE-004独立保留blocked。 |
| 密钥/草稿/完整诊断与业务版本保护 | True | passed | EV-007, EV-008, EV-009, EV-013, EV-037, EV-040, EV-041, EV-043 本轮离线及真实源码环境内验证通过，非跨机证明 |
| 独立EXE与系统输入/真实模型/长期性能 | True | blocked |  缺独立EXE、真输入法/读屏/跨DPI/180Hz实屏及真实服务质量证据 |
| 当前UI回归合同可执行且没有未解释失败 | True | passed | EV-012, EV-039, EV-040, EV-043 对应根因本地修复与回归通过；真实平台发布条件由GATE-004独立保留blocked。 |

## 缺口


## 下一步

- 按TASK-014与verification-handoff补真实平台/独立EXE/服务证据；本轮13修复任务均verified
