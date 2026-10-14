# 提示词生成后隐藏 Skill 选择区（2026-10-14）

用户要求：“生成提示词之后就应该把查找选择 skill 的页面给隐藏了”。本项为暂停全量审查后的三个新问题中的第一项；其余两项等待用户提供，完整组合回归延后。

## 范围与验收

- 提示词生成成功后，对话中不再显示 Skill 搜索说明、搜索/生成按钮、来源工具栏及候选表格。
- 返回到 Skill 步骤时完整恢复选择区域，继续下一步后再次隐藏；候选、绑定、提示词及其确认状态不删除。
- 生成尚未成功时保留 Skill 步骤的操作和恢复入口。Web 与显式 Tk 兼容界面共用同一显示判定；Debug 去重记录显隐，不增加轮询刷屏或自动日志文件。

## 根因与实现

`conversation_cards()` 原本在方案确认后持续添加 Skill 卡片，并明确允许 `result` 阶段显示。因此问题发生在共用对话投影，前端忠实显示了多余卡片。`workspace_navigation()` 已正确进入结果阶段，Web DOM 也已有移除退役卡片的逻辑，无需调整导航业务或另加 CSS 隐藏。

修改 `conversation.py`：仅当前 `stage == "skills"` 时添加完整 Skill 卡片。继续使用 SessionState 的业务状态和返回路径。已有 Stage controls updated 日志加入 `skills_visible` 并纳入原去重依据；不记录正文、Key 或逐帧事件。

## 定点反馈与证据边界

沿用已授权的公开接口：`conversation_cards()`、SessionState、保存/读取、WorkspaceController 与生产 Chromium DOM。测试先于源码修改创建。

- 红灯：`python -X utf8 -m pytest tests/test_skill_stage_visibility.py -k prompt_hides --tb=short -p no:cacheprovider`，2 项均在“生成后仍有 Skill 卡片”断言失败（草稿、已确认结果）。
- 最终定点反馈：`python -X utf8 -m pytest tests/test_skill_stage_visibility.py --tb=short -p no:cacheprovider --show-capture=no`，5 项通过，13.39 秒。
- 覆盖：草稿/已确认结果、返回/继续、不变的绑定及正文、保存重开、真实 Tk owner/Controller 加浅深主题生产 Chrome DOM，以及 Debug 显隐和重复刷新不刷日志。
- 首次联动探针 3 过/2 失败：测试使用虚构目录记录，Tk 刷新依法标记其绑定过期，无法生成。改用项目内已有真实目录测试记录，保留原业务校验后 5 项通过。这是夹具问题，未修改生成校验。
- 一次脱离 pytest 的 Python 检查因没有 `src` 导入路径失败；后续使用现有 pytest 公开边界，不改项目路径配置。
- 文档补丁首次因错误的 UI 文档标题锚点未写入，读取真实标题后重新应用；应用源码修复不受影响。

本次只执行该问题的定点反馈环，没有恢复逐页审查或执行完整组合回归，没有真实模型请求、个人数据访问、EXE 构建、提交或推送。增量基线和差异保存在忽略的 `local_artifacts/skill_stage_visibility_20261014/`，不把整个 dirty 工作树当作本次改动。

独立只读差异复核：Spec 0 项待修，Standards 0 项待修。两轴仅审查本次增量源码与测试，没有再次运行测试。

2026-10-14 本批收尾：S1–S3及相邻30模块组合和最终受影响路径，326个不同节点最新全部通过，首轮旧取消夹具失败与纠正保留。此更新替代上述当时“回归延后”状态；全项目审查仍暂停，准确证据见[第三项与组合回归](skill_summary_scoring_20261014.md)。
