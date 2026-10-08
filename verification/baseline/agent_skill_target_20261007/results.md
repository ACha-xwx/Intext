# Agent Skill 搜索目标修正 — 2026-10-07

## 根因、范围与完成条件

普通页面和一般 GitHub 仓库曾可能通过元数据降级进入 Skill 候选；查询与 AI 提示未充分限定 Agent Skill 的专业含义，界面和交付中也残留“方法”称呼。

本轮范围为搜索词、各来源候选资格、来源合并、AI 筛选指令及 Skill 用户可见术语。保留本地扫描、Skill 索引、GitHub、开放网页、AI 筛选和用户选择架构，三个联网来源仍并行，每路独立 45 秒预算。内部绑定及 M3/M4 数据契约保持现有结构。

完成条件：普通网页/工具/一般仓库不能冒充 Agent Skill；真实 SKILL.md 或明确 Skill 索引条目可继续筛选；原候选展示选择和三路并行测试通过；执行一轮全量与最终编译，将无关历史问题单列。

## 修复与证据

- 查询包含 Agent Skill/SKILL.md 语义，AI 初筛与审阅明确针对供 AI Agent 使用的指令包。
- 索引、开放网页和来源合并执行候选资格检查；明确 skills.sh 索引项在原文暂不可读时仍可作为信息有限的参考。
- 全量轮发现合并层误拒绝仅在 `skill_id` 保存 HTTPS SKILL.md 地址的记录；已修复并新增正反例。来源正文存在时仍检查元数据和指令正文。
- 全量轮发现 Skill UI 测试替身按旧提示词短语返回结果，造成 JSON 形状错误。改为按 Schema 分支，保持生产路径测试。
- 文案编辑引入的 `finalization.py:435` 缩进错误已修复。原收集错误不再发生。

验证记录：

| 检查 | 结果 |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest -o addopts='' -q` | 721 passed、17 failed、1 skipped，123.78 秒，退出码 1 |
| 修复后 `tests/test_skill_network_discovery.py` | 7 passed，退出码 0；覆盖多源合并、去重、失败降级、三路并行预算、普通网页过滤及规范 Skill 地址 |
| 修复后 `tests/test_ui_skill_ai_flow.py` | 2 passed，退出码 0；覆盖本地结果、追加联网结果、来源说明、展示及选择 |
| 最后代码改动后 `compileall -q src tests` | 退出码 0 |

全量轮中本轮相关的 5 项失败已定向复测通过。没有重跑完整测试，因此不宣称全量测试全绿。未进行真实网络搜索或模型调用。

## 后续 EXE 交付

用户随后明确要求“创建exe”。已运行 `pwsh -NoProfile -File scripts/build.ps1`，退出码 0。构建结果为 `dist/PromptSmith.exe`，时间 2026-10-07 23:55:43 +08:00，14,232,246 字节，SHA-256 `01533448af9e5323d56b06ee1b2d62bf5f69b312988bcde185276efd7802702d`。

项目内和仅含同一 EXE 的独立临时目录均运行 `--smoke-test`，等待进程退出，退出码均为 0，独立副本哈希一致。启动烟测只证明程序窗口可初始化，不替代真实联网内容验收。机器记录见 `exe_build.json`，构建日志见 `build.log`。

## 无关既有测试/契约不一致（12 项）

以下不改变本轮搜索修复范围，保留失败事实，不通过修改产品或弱化断言消除它们：

- `test_experience_iteration.py::test_primary_action_navigates_to_current_delivery_work_without_model_call[selected_skill]`：旧测试期待只跳转技能页；当前 guided flow 的按钮直接触发整合。尝试更新文案和动作断言后进一步暴露旧导航契约，已撤回这两项测试改动。
- `test_fixed_demo_runner.py::test_m4_pending_change_cannot_be_bypassed_by_final_confirmation`：旧测试要求后置待复核阻止最终确认，与此前放宽最终阻断的行为不一致。
- `test_m1.py::test_assets_load_exact_current_versions`：期望 M1 v0.11，实际 v0.22。
- `test_m1.py::test_questions_are_rejected_when_budget_is_zero`：期望预算错误，实际为重复追问的语义错误。
- `test_m1_interpretation_guidance.py::test_existing_output_without_interpretation_extension_remains_valid`：解析会补入兼容 `model_judgment`，旧断言要求完全相等。
- `test_m1_interpretation_guidance.py::test_new_resources_keep_legacy_contract_and_do_not_encode_jgs_answer`：期望 M1 v0.11，实际 v0.22。
- `test_m1_model_authority_v07.py::test_v08_assets_make_quality_decision_model_led`：期望 M1 v0.18，实际 v0.22。
- `test_m1_truncation_ui.py::test_second_round_truncation_preserves_answers_and_requires_explicit_compact_retry` 两个参数案例：期望增量提示 v0.4，实际 v0.15。
- `test_m1_truncation_ui.py::test_nontruncation_failures_keep_distinct_kinds_and_do_not_offer_compact_retry[json_error]`：旧测试期望两次请求，现有 JSON 恢复路径实际四次。
- `test_status_version_label.py::test_status_label_matches_the_loaded_prompt_assets`：旧状态栏版本断言 v0.11，与当前 v0.22 不一致。
- `test_status_version_label.py::test_m1_current_prompt_file_exists_and_matches_the_declared_version`：旧版本断言 v0.11，与当前 v0.22 不一致。

截图中的 M4 `search_metadata` 枚举问题也单独保留：当前 Schema 已含此枚举，本轮未修改该契约或验证旧 EXE。
