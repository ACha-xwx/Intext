> 历史资料：仅用于追溯当时的设计与验证；当前状态以根目录 HANDOFF.md 为准。原始路径：`findings.md`。原始日志、截图及失效旧链接的查找方式见归档索引。

# 本轮发现

## 2026-10-08：比赛要求与展示升级依据

- 原始文件 `source file/JSAI2025 (1).pdf` 文件名含 2025，但正文为 2026 第八届全球校园人工智能算法精英大赛·算法创新赛；本项目对应赛题 2：AI+软件创新。全文已提取，PDF 实际第 3、4、5 页已渲染核对。
- 六项分值为创新性 20、技术实现 20、功能完整性 20、方案完整性 20、应用价值 15、总结与展望 5。没有独立 UI 美观分；体验与视觉表达应服务功能、实现、方案完整性和差异化展示。
- 提交要求：名称不超过 20 字、简介不超过 300 字、参照官方模板的方案 PDF 不超过 10M、MP4 视频 3–5 分钟且 300MB 以内、答辩 PPT 转 PDF、佐证合成一个 PDF、大文件统一网盘目录和命名。匿名要求覆盖方案、视频、PPT 等。
- 桌面 EXE 符合作品范围。规则要求软件说明、核心算法说明、测试报告及环境/部署说明；未规定必须改为网站。
- 论文可支撑研究背景与控制变量的评测思路，不能充当本软件新增需求引导或 Skill 功能的效果证据。最新 155 项相关检查为分批离线回归，不能宣传为全量通过或真实模型效果已验证。
- 当前文件未提供提交截止时间、现场答辩时长或 PPT 页数限制；官方方案模板只有下载链接，未获取模板正文。内部旧排期不是官方日期。

## 2026-10-08：整合契约及最终提示目标

- 使用 PyInstaller CArchiveReader 直接读取 EXE 内 M4 Schema：`multi_source_v6` 仅接受 `api_metadata/source_content`；上一轮 `dist/PromptSmith.exe` 已有 `search_metadata`。进程列表显示这两个版本及其他旧版同时运行，无法单凭截图确定具体窗口对应哪个进程。
- 当前代码仍有独立兼容问题：M3/M4 `verification_status` 枚举未跟进新搜索适配器。新回归分别用搜索摘要、API 元数据、已读正文和固定来源状态经过实际准备/整合/导出链路，证实并修复。
- 原最终提示保留方法动作和远程 provenance，但没有稳定的 Skill 名称与关键工作映射，本地 Skill 路径缺失；现在由程序从当前绑定添加 `skill_references`，不依赖模型复述来源。M4 v0.2 明确让下游 AI 获取/读取 Skill 并用于任务。
- 共享贡献取消一个绑定后旧 `provenance_sources` 可能残留，现每次重建都重新计算；已读正文的固定否认文案也已修正。
- 证据与已完成边界见 `verification/skill_handoff_20261008/results.md`。

## 2026-10-07：Agent Skill 搜索目标复核

- 当前网络架构由 `skill_network_discovery.py` 并行调用 Skill 索引、GitHub 和开放网页；索引/GitHub 读取仓库中的 `SKILL.md`，开放网页只将 `SKILL.md` URL 作为候选来源。
- 新增的防线分别位于索引结果归一化、远程来源记录建立和来源合并后 AI 审阅前；普通产品网页及没有 Skill 文件的一般 GitHub 仓库无法进入可选候选。
- 保留已确认的 skills.sh 索引条目，即使正文暂不可读也可按元数据参考；该路径依赖明确索引身份，不接受普通网页搜索结果摘要作为 Skill 身份。
- 搜索页和交付中原“方法”列/状态文案已改为 Agent Skill/指令；内部绑定和 `method_adaptation` 字段沿用现有契约，避免改变 M3/M4 数据结构。
- 截图中 `search_metadata` 枚举报错作为旧运行版本现象单独记录；当前 `M4_input_v0.1.schema.json` 已接受此值，本次没有修改 M4 Schema。
- 合并层最初仅检查 `source_url`/`source_path`，误拒绝了仅以规范 `skill_id` 保存 HTTPS `SKILL.md` 地址的来源记录；现在识别该地址，普通网页地址仍不能进入 AI 审阅。
- 最终相关验证和编译已完成；完整测试轮的无关失败与本轮修复证据分别记录于 `verification/agent_skill_target_20261007/results.md`，不将定向通过写成全量通过。

## 2026-09-28 最终交付 run03 复验

- 本轮新鲜全量回归为 `309 passed`，0 failures、0 errors、0 skipped；JUnit 证据位于 `output/prompt/_design/acceptance_20260928_final_delivery_run03/pytest_full.xml`。
- 当前 Tk、模拟 125% 和模拟 150% 的布局几何检查均通过，证据位于 `output/prompt/_design/acceptance_20260928_final_delivery_run03/ui_layout.json`；这不替代 Windows 系统 DPI 人工截图。
- 重新构建的单文件 `dist/PromptSmith.exe` 时间为 2026-09-28 10:07:22 +08:00，大小 13,460,571 字节，SHA-256 为 `B2A4F6AA27D8AA24D87531197AFDBA3761248043BC6A40DF5FC6409C15406545`。项目内和只含 EXE 的隔离目录烟测均等待进程结束并返回 0。
- T10 已有同一 Skill 服务多个关键工作、多个互补 Skill 服务一个关键工作的直接回归；T15 的目录变化保护在 UI 生产入口覆盖记录变化、无关变化和目录不可用，`DeliveryWorkflow` 直接调用仍不自行加载目录；T18 的长文本、替换失败、覆盖保护和取消导出回归已纳入本轮测试。
- M3/M4 仍没有真实模型内容调用；T20 只证明本地 stub 路径不执行注入命令且不改变已选绑定/已确认最终结果，T21 只覆盖离线最终组装层，T24 只达到本机 EXE 启动级证据。

## 2026-09-27 滚轮修复收尾

- 当前 Tk 事件回归和源码探针均通过；页面路由使用实例唯一 bindtag，位于控件默认类绑定之前，关闭时清理，避免重复注册和已销毁控件回调。
- 原生菜单窗口在本机 Tk 合成测试中会阻塞事件泵，因此自动用例只检查菜单不附加页面 bindtag；用户已完成实际滚轮人工验证，记录为人工证据，不冒充自动化菜单事件结果。
- 全量测试新鲜结果为 189 passed；本轮没有真实模型调用。
- 最终单文件发行包与源码滚轮实现对应，项目目录和只含 EXE 的隔离目录 `--smoke-test` 均在等待进程结束后返回 0。

## 2026-09-23 验收修复基线

- 独立验收不是泛化建议，已有生产路径复现：回答状态为 pending 时主按钮显示继续分析，但 `run_primary_action` 落入确认路径；方向性未知使每次点击只弹确认失败。
- 重复追问保护目前没有把已经 resolved 的缺口/问题历史作为稳定关联证据；相同 field、scope 和问题文本换 gap/question ID 可重新进入待回答。
- 模型列表迟到判断只比较当前快照值；地址从 A 改到 B 再改回 A 后，旧 A 请求仍被接收，必须绑定单调 `connection_version` 或请求身份。
- M2 的 `add_plan_step` 和 `edit_plan_step` 只要求标题、目的；确认入口未校验 actions、outputs、completion_criteria 的实际内容，因此空执行步骤能进入 confirmed 并持久化。
- 主页面已有部分右键能力，但动态创建的需求编辑 Entry 与 M2 单行弹窗没有统一绑定；树表也缺少复制完整选中内容和滚动条。
- 新要求明确将三种协议纳入当前范围。现有“供应商/协议分开展示”不等于协议已适配，需要重构 API 层而不改写 M1/M2 业务状态规则。

## 第一批根因与修复事实

- 主动作根因是 `_primary_action_text()` 和 `run_primary_action()` 各自维护条件顺序；新建 `PrimaryAction` 后由同一对象驱动标签、原因、禁用和命令分派。
- resolved 问题仍在 `question_history` 中且 assessment 为 `applied`，但旧校验只考虑 skipped/unsure 与 pending；新规则只对已关闭原 gap、没有更新用户来源、同 field/scope 且问题文本相同或高度重合的情况拦截。
- 空步骤结构可通过 M2 Schema，因为草稿允许不完整；确认需要独立的 `validate_plan_confirmable()`，不能收紧模型响应 Schema 使草稿无法保存。
- 配置快照值不足以识别 A→B→A；单调世代是必要的请求身份组成，且不应把模型 ID 的手工编辑当成目录所属配置改变。

## 2026-09-23 M2 最终实现事实

- M2 接入版为 `M2_system_v0.1`／`m2.v0.1`，独立于 M1 v0.5／`m1.v0.2`，但共用 DeepSeek 连接、后台执行、证据和 UI 基础设施。
- `SessionState.plan` 已从占位迁移为程序维护的方案对象；旧占位字符串保留为过期历史，合法结构化方案重开时重新校验引用与确认版本。
- M2 一次返回完整方案与 1–3 项关键工作；程序不把模型建议、ready 文案或局部 ID 当作用户确认。
- 结构化编辑覆盖全部主要栏目。目标／范围等广泛影响修改保守地要求全部关键工作复核；局部步骤／关键工作修改只复核相关项或该项。
- 初次布局几何验证真实发现 150% 裁切，经过定向布局修复后当前、125%、150% 三档均通过；界面捕获工具不可用，所以没有截图证据。
- 没有运行时 API 配置；所有新增 M2 结果明确标为离线程序或人工 fixture，未冒充真实模型内容效果。

## 2026-09-23 基线

- 当前实际 M1 为 `M1_system_v0.5`／`m1.v0.2`，冲突参与方完整性修复已在新证据目录通过，上一轮全量测试为 88 项；这些是基线而非本轮结果。
- `src/promptsmith/api.py` 仍把供应商与协议合并为内部标识 `deepseek_chat_completions`，只实现 Chat Completions POST，没有模型目录 GET。
- `SessionState.plan` 目前只有 `{version,status,content,confirmed_version}` 占位；没有 M2 请求、来源需求版本、草稿编辑、关键工作复核或确认逻辑。
- `workflow.py` 只有 M1 调用与证据写入；`PromptSmith.spec` 只打包 M1 v0.5 和 v0.2 两个 Schema。
- UI 仍是 M1 单页主体，确认需求后提示“方案生成尚未接入”；连接区尚未分开展示供应商与协议，也没有模型列表、通用右键菜单和 M2 页面。
- UI 已有单一 `busy` 防止 M1/连接测试重复提交，后台线程通过队列回主线程；需要扩展为带请求目的/配置版本的共用机制，避免模型列表、M1、M2 回调串扰。
- `set_task()` 会在任务实际变化时清空 M1 冲突/缺口并使下游失效；方案导航本身不能调用它，实际需求改变后应由 `_invalidate_downstream()` 将 M2 标记过期。
- 当前 Git 仓库没有已跟踪基线，所有项目文件为未跟踪；本轮直接在现有工作区修改并以测试和证据校验。

## 待核对

- 合并提示中 M2 编辑、关键工作、确认细节及错误码的完整段落。
- UI 当前控件层级、可测试接口和已有 stub 测试模式。
- DeepSeek 模型目录端点的官方当前规则；若进行公开事实核对，只记录规范，不接触用户密钥。

## DeepSeek 官方接口核对

- 2026-09-23 查阅 DeepSeek 官方 API 文档：OpenAI 格式默认 `base_url` 为 `https://api.deepseek.com`，模型目录为认证 GET `/models`，返回 `{object:"list", data:[{id,object,owned_by}]}`。
- 因此目录端点应把用户地址规范化回服务根地址后追加 `/models`：若地址结尾是 `/chat/completions` 则去掉该后缀；若仅结尾 `/v1`，保留该用户路径并追加 `/models`，不擅自切换域名或删除其他自定义前缀。
- 模型目录只使用返回的 `id`；不依据名称推断聊天、结构化输出、权限或可用性。认证继续使用 Bearer，密钥不进入日志或错误文案。

## 2026-09-27 鼠标滚轮修复基线

- `src/promptsmith/ui.py::_scrollable_page()` 为页面创建 Canvas 和滚动条，但当前没有主窗口滚轮路由；原始探针确认页面空白、标签、空任务 Text、空 Treeview 上的生成滚轮事件不移动外层 Canvas。
- 长 Text 和 Treeview 依靠 Tk 控件类绑定可以滚动，因此路由必须位于 Text/Treeview 默认类处理之前，并仅在内部内容已到边界时把后续事件交给外层页面。
- 页面内容 Frame 是 Canvas 的嵌入窗口；滚动条是页面 Frame 下的兄弟控件。鼠标归属需按页面层级识别，而不能假设所有目标都是 Canvas 后代。
- `PromptSmithApp.shutdown()` 会取消轮询并关闭 executor；滚轮 class binding 需要使用每实例唯一 tag，并在 shutdown 时解除，避免重复刷新或关闭后残留。
- 原基线观察文件留在 `acceptance_20260927_mousewheel/`；本轮复现、修复观察及命令结果写入新的 `acceptance_20260927_mousewheel_fix/`。
- Windows 物理滚轮验收只有在可调用的桌面自动化界面能够发现最终 EXE 窗口时才执行；生成事件回归、EXE 启动和物理滚轮输入分别报告，不互相替代。
