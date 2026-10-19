> 历史资料：仅用于追溯当时的设计与验证；当前状态以根目录 HANDOFF.md 为准。原始路径：`output/prompt/_design/acceptance_20260928_delivery_fix_run01/execution_plan.md`。原始日志、截图及失效旧链接的查找方式见归档索引。

# 末端交付缺陷修复执行计划

目标：让 M4 决定、Skill 绑定、最终正文、确认状态和导出文件始终对应同一份当前有效方案。

## 实施顺序

1. 基线：记录工作区状态、现有验收资料、定向/全量测试结果和现有 EXE 指纹；不改历史证据。
2. P1 决定安全：在 `tests/test_final_delivery.py` 和 `tests/test_delivery_workflow.py` 建立拒绝 fallback/阻断、重建草稿和同名 `change_id` 轮次隔离的红灯；再改 `src/promptsmith/finalization.py`、`src/promptsmith/delivery_workflow.py` 与必要的会话字段。
3. P1 导出门槛：在 `tests/test_exporter.py` 与 `tests/test_ui_delivery_interactions.py` 验证草稿为空、确认后来源变化、对话框期间状态变化、显式覆盖/取消；再修改 `src/promptsmith/exporter.py` 和 `src/promptsmith/ui.py`。
4. P2 恢复与目录：验证 v0.1/v0.2 会话迁移和 Skill 选择状态；补 Skill 来源字段与核验等级，修正弱词匹配，并确保目录变更仍会使绑定过期。
5. 正文与 UI：让 canonical Markdown 同源呈现关键工作、需求覆盖、方法适配和阻断项；在 UI 暴露 M4 决定、定位复核和覆盖确认。
6. 端到端验证：运行新增场景、全量 pytest、compileall、源码 smoke、构建；备份旧 EXE 后验证项目目录和仅含 EXE 的临时目录业务链。
7. 交接：将 R01-R20 的通过/失败/未执行写入本目录，更新开发交接、提示索引和 CHANGELOG；真实模型内容质量与 fixture 验证分开记录。

## 完成门槛

- 决绝的变化不会留下仍可确认的依赖动作；fallback 生效或呈现具体阻断。
- 正式导出在实际写入前重新验证；空正文、过期来源和待处理阻断不能写为正式文件。
- M4 新轮次与历史决策隔离，迟到响应不能改写已变化的会话。
- v0.2 重开保持原 Skill 状态；普通文案任务不因弱词匹配软件 Skill。
- canonical 正文独立可读，UI 可完成复核、保存、重开和导出。
- 所有验证按实际命令结果报告；本地测试不得描述为真实模型测试。

## 当前状态

- [ ] 基线测试及 EXE 指纹
- [ ] P1 M4 决定、fallback 和轮次隔离
- [ ] P1 写入前导出验证
- [ ] P2 会话恢复及 Skill 目录
- [ ] canonical 正文和 UI 闭环
- [ ] 全量验证、构建与交接
