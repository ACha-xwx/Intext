# 统一对话工作区验证（2026-10-09）

## 实现结果

默认工作区为中央滚动时间线和底部固定输入框。发送目标、逐题回答、需求确认、方案核对、可选 Skill 的选用/取消/整合、最终提示的复制/导出/保存均可在索引 0 完成。摘要在时间线中展开，需求详情默认折叠；复杂方案编辑和结果可选操作保留详情入口。

`conversation.py` 从 SessionState 派生只读卡片，已发送问答和补充沿用 question_history 保存。重新打开旧会话可恢复当前阶段对象与已记录问答，不添加独立聊天事实库，不虚构旧模型回复。发送文字不表示需求/方案确认；按钮操作核对显示快照。需求变化、取消 Skill 与来源变化仍通过既有业务方法使旧方案/结果失效。

## 离线检查

本轮相关范围共 115 个独立测试节点有通过证据，分批执行，没有运行整个仓库的完整套件。

| 范围 | 结果与说明 |
|---|---|
| `test_conversation_workspace.py`、`test_guided_ui.py`、`test_guided_jgs_chain.py` | 34 项通过；统一工作区的 11 项又在后续布局/刷新修改后通过 |
| 设置、滚轮、Skill 搜索/AI 流程、交付交互、M1 截断恢复、M2 引导、统一工作区 | 92 项中 88 项通过、4 项旧滚轮夹具失败；其它业务断言通过 |
| 滚轮夹具适配后 `test_mousewheel.py` | 13 项全部通过；四个失败节点已恢复，内部/页面滚动、弹窗隔离、横向滚动和弹出列表断言保留 |
| 实际 Tk 窗口几何与截图 | 48 项检查通过；默认 1440×810 与 720×405，摘要/详情展开及模拟缩放，回调异常为 0 |
| `python -m compileall -q src tests` | 退出 0 |
| `python run_promptsmith.py --smoke-test` | 退出 0，源码启动烟测 |
| `git diff --check` | 通过，记录于维护进度 |

覆盖重点：目标只提交一次；运行中保留未发送文本；修改模型须重新确认；追问只记录当前题，最后汇总全部回答；发送补充使旧方案和旧提示过期；需求/方案确认明确；完整无 Skill 本地 HTTP 链路；Skill 选用/整合/取消及迟到响应丢弃；保存重开保持派生卡片一致；显示快照拒绝过期操作。

可重复执行的命令：

```powershell
python -m pytest tests/test_conversation_workspace.py tests/test_guided_ui.py tests/test_guided_jgs_chain.py -q
python -m pytest tests/test_ui_settings.py tests/test_mousewheel.py tests/test_ui_skill_ai_flow.py tests/test_ui_skill_search.py tests/test_ui_delivery_interactions.py tests/test_m1_truncation_ui.py tests/test_m2_guidance_ui.py -q
python -m compileall -q src tests
python run_promptsmith.py --smoke-test
git diff --check
codegraph sync
codegraph status
```

## 修正与边界

中间验证发现结果卡片引用未注册控件、确认卡片未随显示预览重新渲染，均已修正。旧滚轮夹具现先展开详情并将控件移动到视口；没有删除有效断言来隐藏问题。

模型内容为合成响应，网络请求只使用测试本机 HTTP；M4 使用离线客户端。没有付费模型质量验证、真实供应商请求、Skill 安装/执行、下游任务执行、EXE 重建或远程发布。仓库历史全量失败不由本次局部通过取代。125%/150% 为 Tk 缩放模拟，不是另一台电脑的真实 Windows DPI 验收。

截图和原始几何报告放在本地忽略目录 `local_artifacts/unified_conversation_20261009/`：`welcome.png`、`plan.png`、`result.png`、`small.png`、`layout.json`。图片为本进程 PrintWindow 捕获，已查看，无密钥；不依赖前台桌面截屏。CodeGraph 同步结果见 [维护进度](../../docs/maintenance/progress.md)。
