# Skill 整合与下游 AI 使用说明 — 2026-10-08

## 根因

1. 旧 `dist/PromptSmith_20261007_multi_source_v6/PromptSmith.exe` 包内 M4 契约没有 `search_metadata`，与用户截图错误一致。上一轮主 EXE 包内已含该值。两者都在运行，不能仅凭截图断定用户当时点的是哪个窗口。
2. 当前源码 M3/M4 的来源状态仍只接受 `remote_recorded/network_unverified`，与搜索模块实际输出 `metadata_only/search_result_only/source_read/source_verified` 不兼容。新增链路测试复现了所有四种状态被拒绝。这补充并纠正了上一轮仅归因于旧版本的结论。
3. 最终正文主要写方法动作与远程来源记录，缺少稳定的 Skill 名称、任务对应和本地路径；固定边界文案还会把已读正文写成未读。
4. 重建共享贡献时未删除旧来源字段，取消一个绑定后可能残留其来源。

## 修改与完成条件

M3/M4 输入契约接受搜索适配器实际产生的状态，保留证据差异、用户选用和步骤引用检查。M4 提示升级 v0.2，输入带名称和来源，输出面向下游 AI 的 Skill 使用说明。

最终正文从已选绑定确定名称、来源/本地路径、关键工作和步骤，明确要求下游 AI 查找或获取 Skill、读取 SKILL.md，并用于该任务。信息有限时要求使用前确认能力；跨机不可读时让用户提供文件及引用资源。复制和 Markdown 导出均使用同一正文。

来源字段随当前绑定重建，取消的 Skill 不再留在共享贡献来源中。读取/安装/执行状态如实保留，不把生成提示写成已执行。

## 验证

- `tests/test_skill_handoff.py`：新增 6 项先失败后通过，涵盖四种联网证据类型从 M3/M4 到确认、复制用提示、Markdown 导出和保存重开，本地路径与跨机说明，取消绑定后的来源清理。
- 业务回归批次包含上述文件及 `test_m3_m4.py`、`test_delivery_workflow.py`、`test_final_delivery.py`、`test_exporter.py`、`test_delivery_session_migration.py`、`test_skill_catalog_untrusted_data.py`：首次 103 通过、4 失败；4 项均为新增用例的会话 fixture 缺少方案来源快照。补齐 fixture 后 6 项全过，该批次共 107 项现均有通过证据，未重复运行已通过的其他 101 项。
- `test_ui_delivery_interactions.py`、`test_ui_skill_ai_flow.py`、`test_final_closure.py`：48 passed，退出码 0。
- 共 155 项相关检查分批通过。`compileall -q src tests` 退出码 0。
- 未重跑整个测试套件，上一轮 12 项无关历史失败仍记录于 `../agent_skill_target_20261007/results.md`，不宣称全量全绿。
- M4 调用使用离线响应测试数据；未请求真实模型或验证实时联网内容质量。

## 新发行包

路径：`dist/PromptSmith_20261008_skill_handoff/PromptSmith.exe`

构建命令：`.venv/Scripts/python.exe -m PyInstaller --noconfirm --clean --distpath dist/PromptSmith_20261008_skill_handoff PromptSmith.spec`，退出码 0。

时间：2026-10-08 00:31:32 +08:00。大小：14,237,576 字节。

SHA-256：`16218c4c63e3472d6a1c6147442fe8c2a23a755944d175c9fb4cc8301ee92c03`

从构建后的 EXE 读取资源，M3/M4 Schema 与 M4 v0.2 提示均与当前源码文件字节一致；包内状态枚举完整。项目目录与只含单个 EXE 的独立临时目录各执行一次 `--smoke-test`，等待退出，均返回 0。详见 `exe_build.json` 和 `build.log`。
