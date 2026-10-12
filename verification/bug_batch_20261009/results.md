# 本批 BUG 统一回归 — 2026-10-09 至 2026-10-10

本批源码修复及离线验收完成。已选 Skill 在对话/详情表格显示“已选中该 Skill”并禁用；取消后恢复。重复选用不再递增版本或让最终提示失效。

1000 个当前测试节点均有执行证据。分批全覆盖后定向复验，按最新节点结果合并为 **991 passed / 8 failed / 1 skipped**；41 项实际 Windows/Tk 检查通过。8 项失败为已记录的旧测试契约，逐项列在下方，不能宣称全量全绿或将此合并结果描述为一次完整重跑。

## 验收范围

- 试运行移除：入口、设置、后台调用和旧会话字段兼容忽略；复制、导出及 M5 保留。
- 会话切换：新建/打开立即解除旧忙状态，旧成功/失败/排队回调丢弃，新请求不等待旧 HTTP；取消后停止后续自动修正。
- M1：来源省略、空格与大小写差异的本地还原；中间恢复 WARN、最终失败 ERROR、成功 INFO 与完整异常；不把无依据引用变成事实。
- Skill：两处比较表、来源筛选、推荐名额分配、本地/联网双向累计、刷新/重开状态、取消、多选及不同来源/版本快照；重复绑定无业务状态变化。
- HTTP：请求头、官方 GitHub token 域名/端口、重定向隔离、缓存、403/429/521 分类、限流暂停、部分来源可用、凭据和 URL 脱敏、调用上下文及取消边界。
- 相关业务：需求/方案/Skill/最终交付、未知说明、宽松解析、设置持久化与 DPAPI、Debug 分级颜色和手动完整日志保存。

## 测试环境与方法

Windows 系统 Python 3.11.9、pytest、jsonschema、真实 Tcl/Tk。统一 runner 去除供应商/项目密钥环境变量，将 LOCALAPPDATA 指向隔离目录，并禁止非 localhost socket；用例另以 tmp_path 隔离应用数据。未读取或覆盖生产 settings.json / API Key。

使用合成凭据、离线 fixture、注入响应及本机 HTTP 服务；模型实际调用数为零。真实本地 Skill 扫描仍可读取本机已安装 Skill 的公开元数据，不安装或执行 Skill。

证据位于 Git 忽略的 `local_artifacts/bug_batch_20261009/`。JUnit 的 classname/name 映射到当前收集节点，仅为已改参数标签及 M1 测试重命名提供明确别名；1000 节点无遗漏、无无法映射项。`aggregate_results.py` / `aggregate_results.json` 保留合并依据，中间失败 XML 不删除。

## 分批结果

| 检查 | 原始结果 / 最新结论 | 本地证据 |
| --- | --- | --- |
| 本批七份定向文件，90 节点 | 首轮 88 passed / 2 failed；两节点修正夹具后通过，最新 90 passed | targeted.xml / targeted_fix.xml |
| 其余全部文件，910 节点 | 885 passed / 24 failed / 1 skipped，904.71 秒 | broader.xml |
| UI 契约定向复验，16 节点 | 16 passed，63.51 秒；解决上述 15 个失败，另含一个相邻参数 | contracts_fix.xml |
| M1/UI 设置收尾，4 节点 | 3 passed / 1 failed；发现 JSON 兜底丢失类别 | focused_final.xml |
| M1 类别首次补验 | 1 failed；自动类别实际为 null，首次补丁只覆盖 auto | m1_category_check.xml |
| M1 恢复/引用/会话取消/超时复验，72 节点 | 72 passed，140.22 秒；含原场景及详细日志证据 | m1_final.xml |
| 最新逐节点合并 | 991 passed / 8 failed / 1 skipped，当前共 1000 节点 | collected.txt / aggregate_results.json |
| 实际 Tk 窗口验收 | 41 项通过，两张截图已目视核对 | ui_report.json / ui_acceptance.txt |
| 最后源码启动 smoke | 退出 0，无自动日志文件，隔离应用数据 | final_smoke.json / final_smoke.txt |
| compileall src tests scripts、git diff --check | 退出 0 | 收尾命令结果 |

首批两处失败为测试准备问题：显示候选的伪造来源哈希不能用于真实交付、旧试运行入口测试未同步 UI 目标编辑框。均修正夹具，保留产品来源保护。

15 个 UI 失败与当前统一对话及环境契约有关：默认留在对话、隐藏详情要先展开、固定输入接收焦点、M2 恢复为 WARNING、内置 Skill 用例应固定发现结果而不依赖本机 345 个 Skill 的排名。调整测试后仍检查真实业务状态、请求次数、选择/取消/整合与保存重开；未恢复旧分页入口或扩大模型预算。未预期 error/warning 对话框现在直接让自动测试失败，避免人工弹框阻塞。

M1 兜底类别丢失是本批发现的实际问题，已修复并复验：自动类别 null/auto 沿用请求前有效类别，用户显式类别优先。损坏 JSON 经三次失败后继续访谈，不采用损坏内容或自动确认。用例验证回答、来源、类别、需求、方案、Skill、交付保留，下一步问题可回答，三份失败原文/check/完整堆栈及有效恢复结果保留。网络/超时仍为一次失败并提供重试。

## 实际窗口检查

1440×810 默认 16:9；1440×810、960×640、720×405 下输入、发送、设置、保存可达。混合来源同表显示，默认推荐仍可见本地项；两表选用后标签和禁用状态一致，实际取消及 JSON 重开恢复正确。

已选 Skill 名称和来源进入最终提示，重复选用保留版本和结果；复制、Markdown 导出及新建/重开可用，活跃界面没有试运行入口。Windows CF_UNICODETEXT 与完整 Unicode 提示逐字一致；Tcl clipboard_get 在约 4000 UTF-8 字节边界出现读取差异，属于读取器限制，本次未改实际复制逻辑。观察保留于 clipboard_observation.json。

Debug 窗口的 DEBUG 蓝、INFO 白、WARNING 黄、ERROR 红、CRITICAL 亮红均通过；只点击保存才写日志，所有级别、完整底层 cause 和外层 traceback、脱敏凭据均在文件内。无 Tk 回调异常。截图为 selected_skill_details.png / debug_manual_save.png，使用合成任务和凭据，仅保存在本地忽略目录。

## 保留的 8 个旧测试契约失败

均可在 [2026-10-07 历史清单](../baseline/agent_skill_target_20261007/results.md) 找到；本轮未通过修改生产逻辑、弱化断言或隐藏失败使其通过。

| 节点（tests/ 下） | 失败原因及当前行为 |
| --- | --- |
| test_fixed_demo_runner.py::test_m4_pending_change_cannot_be_bypassed_by_final_confirmation | 期待未处理后置变化阻止最终确认；当前一般未知和建议随最终提示交给下游，不恢复旧 M4 门槛。 |
| test_m1.py::test_assets_load_exact_current_versions | 期待 M1_system_v0.11，当前 v0.22。 |
| test_m1.py::test_questions_are_rejected_when_budget_is_zero | 旧预算断言；该响应实际因用户已明确修改却又重复追问被拒绝，不是预算错误。 |
| test_m1_interpretation_guidance.py::test_existing_output_without_interpretation_extension_remains_valid | 要求解析对象逐字相等；当前缺 model_judgment 时补入兼容判断，原内容仍保留。 |
| test_m1_interpretation_guidance.py::test_new_resources_keep_legacy_contract_and_do_not_encode_jgs_answer | 期待 M1 v0.11，当前 v0.22；本项首个版本断言失败，后续断言未执行。 |
| test_m1_model_authority_v07.py::test_v08_assets_make_quality_decision_model_led | 期待 M1 v0.18，当前 v0.22；本项首个版本断言失败，后续断言未执行。 |
| test_status_version_label.py::test_status_label_matches_the_loaded_prompt_assets | 期待 M1 v0.11 / M2 v0.2；标签从当前资源派生为 M1 v0.22 / M2 v0.3。 |
| test_status_version_label.py::test_m1_current_prompt_file_exists_and_matches_the_declared_version | 期待 M1 v0.11，当前 v0.22。 |

唯一跳过：`test_local_skill_search.py::test_symlinked_directory_is_not_traversed`，本机 Windows 创建符号链接权限不足，未把它算作通过。

## 验证边界

没有真实模型/付费 API、真实外部网站访问、EXE 重建/运行、提交或推送。HTTP 拒绝/缓存/降级的离线通过不证明各网站 403 已消除；真实推荐质量、当前模型速度及完整真实服务流程仍待用户环境验证。新版功能目前由源码运行，旧 EXE 不包含这批修改。

CodeGraph 最终状态：136 files / 3579 nodes / 11095 edges，索引最新。维护文件、HANDOFF 与当前架构/UI 指南已同步本报告，历史延期记录仍保留其原日期；本地证据和构建输出继续忽略。

收尾静态核对：13 份当前文档的 87 个相对链接有效，45 个新增文件的文本空白检查通过；本批 verification 只开放 results.md，不包含原始任务、凭据或截图。
