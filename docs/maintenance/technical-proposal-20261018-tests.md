# 意织 Intext 技术方案：历史测试与研发证据核查

核查日期：2026-10-18。范围：现有 `tests/`、`verification/`、`docs/maintenance/` 与验收脚本；只核查记录，不改程序、不访问私人配置、不发起真实模型或付费 API 请求。

目标是为技术方案提供可定位、可区分验证层级的事实。完成条件：盘点当前测试文件并按功能分组；给出约十个包含输入、预期、历史实际结果、日期及文件依据的代表用例；独立列出完整回归失败与未测限制。各批次存在交集，不累计为“全套通过”。

## 完成状态与可信度

核查已完成。最强的现成证据是可定位的测试输入/断言、维护文档保留的红绿过程，以及本机实际 WebView2/安装交付记录。它们足以说明研发过程和异常分支覆盖，不足以证明当前版本全仓库全绿、真实模型质量或其他电脑已验收。

本轮重新解析了仓库交接的两份现存 JUnit：`pytest.xml` 为 746 节点（710 通过、35 失败、1 跳过），`pytest_migration_fix.xml` 为 44 节点且全部通过，与报告一致。其余下列通过数按历史结果文档引用，本轮没有重跑程序。部分报告所指 XML/JSON 保存在忽略目录或当前工作区不再存在；例如访谈可靠性报告存在，但 `green-exact-choice-final.xml`、`final-exact-decisions.xml`、`baseline-four.xml` 本次未找到。因此应区分“读到历史报告”与“本轮重新解析原始工件”。

## 证据使用规则

1. 测试文件证明覆盖意图，结果文档证明历史执行结论；不能仅凭存在测试函数就写“已通过”。
2. 离线解析/会话测试、模拟 HTTP、生产浏览器 DOM、真实 WebView2、冻结包内检查、真实模型请求分开标注。
3. `local_artifacts/`、`runs/` 内证据不属于本轮读取范围。维护文档指向这些文件时，标为“历史记录引用”，不假称本轮打开原始工件复核。
4. 历史产物只解释对应日期和源码，不据旧 EXE/旧模型运行推导当前发布版质量。

## 当前测试清单

2026-10-18 当前磁盘共有 **166 个 `tests/test_*.py` 模块**、**34 份 `verification/**/results.md`**、**11 份 `docs/maintenance/*webview*.py`**。模块数由文件清单统计；报告数包含当前磁盘上被 Git 忽略的报告。它们不是测试节点数或通过数，也不能把每份报告相加。

以下按主要职责给每个测试模块只分配一次；跨层测试仍可能同时覆盖其他功能。`test_model_output_recovery.py`、`test_history_workspace.py`、`test_reliability.py` 计入会话交付组。

|功能组|模块数|代表文件与主要覆盖|
|---|---:|---|
|访谈、回答与 M1|26|`test_m1*.py`、`test_interview*.py`、`test_batch_answers*.py`、`test_answer_backtracking*.py`；来源、追问、批量提交、回退、主动补答|
|需求、方案与 M2|14|`test_m2*.py`、`test_requirements*.py`、`test_plan_inline.py`、`test_conflict_participant_integrity.py`；未知、冲突、确认、编辑失效|
|Skill 检索、选用与 M3/M4|22|`test_skill*.py`、`test_local_skill*.py`、`test_network_skill*.py`、`test_m3_m4.py`；资格、来源、预算、排序、绑定、交接|
|会话、交付与兼容|21|`test_session*.py`、`test_delivery*.py`、`test_final*.py`、`test_storage.py`、`test_exporter.py`、M5 兼容；持久化、版本、取消、结果与导出|
|API 协议、传输与预算|15|`test_api*.py`、`test_provider_requests.py`、`test_custom_provider_requests.py`、`test_responses*.py`、流式/Stop/超时/token；真实本地 HTTP 与合成应答|
|设置、凭据与供应商|24|`test_credentials.py`、`test_provider*.py`、`test_custom_provider_{profiles,browser}.py`、`test_settings*.py`、迁移/目录/偏好；DPAPI、原子保存、档案隔离|
|Debug 与诊断|7|`test_debug*.py`、`test_runtime_log.py`、`test_runlog.py`、`test_web_debug.py`、`test_main_diagnostics.py`；异常链、脱敏、手动完整保存|
|打包、安装与演示验收|5|`test_installer_cli.py`、`test_installer_distribution.py`、`test_release_chain.py`、`test_run_bat.py`、`test_fixed_demo_runner.py`|
|工作区、呈现与交互|32|生产 DOM、Tk 回退、教程、通知、历史界面、字体、动画、滚动、桥接、输入与可达性|
|合计|**166**|仅文件盘点，未执行 pytest collection 或完整测试|

[conftest.py](../../tests/conftest.py) 自动隔离 `LOCALAPPDATA`、移除项目凭据环境变量，并让未替换的错误/警告弹框使测试失败；Tk 使用会话级解释器。该 fixture 本身没有实现“所有网络全局禁止”，网络限制应按各个测试或 runner 的记录说明。

## 十个可引用的代表用例

### 1. 忙时返回，恢复整轮回答并隔离迟到结果

- **输入与预期**：向 `q1–q3` 提交“恢复回答1–3”，模拟模型在后台等待；通过公开 Controller 返回。预期立即解锁，三题全文回到未提交输入，迟到损坏 JSON 不新增错误/答案/待处理请求，再提交只增加一次新调用。另一用例使用“完整回答1 👩‍💻”等 Unicode 文本核对整轮恢复。
- **历史实际结果（2026-10-13）**：精确红例修复后，相关 **165 个不同节点的最新结果均通过**；大批原为 164 通过/1 条旧断言失败，后单节点复验通过，不是一次运行 165 全绿。实际 WebView2 浅深 **28 项**通过，使用合成 bridge 与隔离存储。
- **依据与边界**：[测试及断言](../../tests/test_answer_backtracking.py)（`test_busy_back_cancels_request_restores_inputs_and_ignores_late_result`）、[历史结果](backtrack-answers-20261013.md)、[原生脚本](backtrack_answers_webview_check_20261013.py)。取消证明本地任务退役和迟到隔离；不证明远端立即停止推理或计费。

### 2. 已答问题换措辞后，澄清原回答而不重复二选一

- **输入与预期**：任务为重新设计 Tkinter UI；已答“布局结构和控件排布是否也可以调整”，合成模型再次输出原问题或交换二选一分句，并仍判 `unresolved`。预期题卡引用“上一条回答”、要求“具体决定”，保留一个未知、不擅自确认；保存重开相同。手机端、快捷键、两列、新数量和否定关系仍作为新问题保留。只读等待校验 100 次不写重复日志，真实回答仍记录一次。
- **历史实际结果（2026-10-11）**：**30 项新增回归通过**；最后受影响组 **114 通过**；多批按节点最新去重 **300 个中 296 通过、4 个既有合同差异**，四项均以 before 模块复现。上述数字相互有交集。
- **依据与边界**：[具体输入/断言](../../tests/test_interview_reliability.py)、[验收报告](../../verification/interview_reliability_20261011/results.md)、[维护解释](interview-reliability-20261011.md)。属于离线解析/会话/桥接；有限归一化不能保证识别任意语义改写。

### 3. 自定义别名按所选供应商协议调用，保留真实模型 ID

- **输入与预期**：自定义名称、模型 `private-alias`，分别明确选择 OpenAI/Anthropic/xAI/Google/DeepSeek，强度 `max`、预算 16384，通过 localhost 接收请求。核对 `/responses`、`/messages` 等路径及各家思考/采样字段，wire `model` 保持 `private-alias`；另以冲突已知 ID `gemini-3.8-flash` 检查明确类型优先。任务和合成 Key 不进入 Debug。
- **历史实际结果（2026-10-13）**：新增请求文件 **11 项**、档案 **9 项**、生产 DOM **5 项**有通过记录；本批相关 **263 个不同节点最新通过**，不能相加为 288。实际 WebView2 **32 项**通过，仅 3 次 localhost 目录 GET。另 **12 项旧参数断言差异**在 `b3f4953` 副本复现，未计入 263。
- **依据与边界**：[请求测试](../../tests/test_custom_provider_requests.py)、[批次与旧失败](custom-provider-20261013.md)。这是生产客户端加模拟 HTTP，不是五家真实账号/中转成功证明。[Responses 专项](responses-gateway-20261012.md)另有消息列表、`store=false`、完整 Schema 契约及不盲重试回归，289 个不同节点最新通过，也不能与本批累加。

### 4. DPAPI 保存、身份绑定、篡改与失败恢复

- **输入与预期**：合成 Key `disposable-test-key-测试` 加密两次，应产生不同密文且均可往返；更改服务/协议/接口或篡改密文字节应拒绝，单改模型 ID 仍可解密。替换 Key、清空、重启、原子写入失败、解密失败分别检查旧档案保留、普通偏好保留和无明文降级。
- **历史实际结果（2026-10-09）**：各批按节点最新去重 **101 通过**；三个真实子进程（保存/重启/损坏密文）**35 项检查通过**；设置布局 **113 项 Tk 检查通过**，三种计数是不同验证层级。
- **依据与边界**：[测试](../../tests/test_credentials.py)、[UI 失败恢复](../../tests/test_ui_encrypted_settings.py)、[结果](../../verification/settings_encryption_20261009/results.md)。Windows 当前用户 DPAPI 为真实实现；跨 Windows 用户/电脑迁移未实测，也不声称同一已登录用户的恶意进程无法取得运行时密钥。

### 5. 首次自定义服务保存不被隐藏小数字段阻断

- **输入与预期**：首次教程中新建 `YUN`/OpenAI，输入合成网关地址与 Key，模型为空且焦点仍留 Key 框；预期自动保存、教程第二步解锁，Key 不出现在浏览器快照/磁盘明文，字段随后清空；不代用户测试连接。三类 Key：无前缀、Anthropic 形状、长 token；数值 `thinking_speed=1.3` 合法，整数 `conversation_width=900.5` 非法。
- **历史实际结果（2026-10-14）**：生产 DOM→真实 Controller→DPAPI 的 `stepMismatch` 精确红例修绿；相关 **203 个不同本地节点最新通过**。源码、独立冻结 EXE **各 21 项实际 WebView2 双启动检查通过**，包括 localhost 模型目录和旧数据目录迁移。
- **依据与边界**：[输入及断言](../../tests/test_provider_onboarding_browser.py)、[结果](provider-onboarding-20261014.md)、[原生脚本](provider_onboarding_webview_check_20261014.py)。只证明本机隔离路径；维护记录明确没有同学电脑新版现场验收，不使用真实 Key/模型生成。

### 6. 联网 Skill 简介评分有序、低分排除，取消不降级回写

- **输入与预期**：合成技术文档任务收到 `pdf=.96`、`technical-docs=.81`、`video=.05`；预期按前两者顺序推荐，低于 .4 排除。JSON 代码块、字符串分数和单个坏引用保留有效分；正文 403 的已确认 Skill 可基于简介评分，并注明未阅读全文；`matches=[]` 应是评分失败，真实低分无匹配应与之区别。评分中取消，迟到成功/网络错误均不生成降级结果。
- **历史实际结果（2026-10-14）**：评分文件最终 **15 项全部通过**；六个受影响模块 **61 项通过**。与首次 323 项组合（322 通过/1 旧前置断言失败）按节点去重，最终 **326 个不同节点最新全部通过**。不能把 323+61 写成总量。
- **依据与边界**：[具体夹具和断言](../../tests/test_network_skill_summary_scoring.py)、[结果](skill-summary-scoring-20261014.md)。模型/HTTP 是合成替身，桌面链路含真实 Tk owner、Controller 与生产 Chrome DOM；该批未做原生 WebView2/EXE 或真实 Gemini/DeepSeek 推荐质量验收。普通网页资格过滤的历史正反例另见[2026-10-07结果](../../verification/baseline/agent_skill_target_20261007/results.md)。

### 7. M4 损坏 JSON 不混入最终提示词、导出或保存重开

- **输入与预期**：从合法合成 M4 响应删最后闭合符，或在 JSON 前后放说明/代码块/额外对象。实际 `prepare→invoke→apply→validate→export→save/load` 后，正文和 Markdown 不含 `schema_version`、`contributions`、`proposed_changes` 等技术响应，保留 Skill 名称、来源与未知；原始响应仍进证据、Debug 不重复原文、调用数为一。多 Skill、错身份、重复键、非法数值、取消/迟到均有保护用例。
- **历史实际结果（2026-10-14）**：损坏响应 **1 红→1 绿**，包装 **1 红→2 绿**，其他三类 **3 红→绿**；最终相关 **205 个不同节点中 204 通过/1 基点旧失败**。独立 EXE 包内实际 M4 字节码 **8 项离线检查通过**，实际 WebView2/bridge/依赖/退出 **12 项通过**。
- **依据与边界**：[端到端断言](../../tests/test_model_output_recovery.py)、[结果](m4-response-isolation-20261014.md)。旧失败为 `test_final_closure.py::test_explicit_latest_user_evidence_can_reopen_skipped_question_and_persists`，`1045489` 隔离副本同样报 `g-web` 不存在。截图没有原始 JSON，不能断言远端具体损坏位置；旧污染正文需要重新整合，不能自动修改旧哈希和用户编辑。

### 8. 实际 WebView2 中教程依赖真实操作，不自动调用模型

- **输入与预期**：临时目录首次启动，打开设置、输入合成 Key、从 localhost 获取 `fixture-model`、选择并保存；前四步未完成相应操作不可前进，第五步可直接点击完成。检查 not_started/skipped/completed、重看、失败重试、浅深与窄窗，保留密钥加密。HTTP 服务拒绝 POST，模型启动仅记录合成调用。
- **历史实际结果（2026-10-13）**：教程 **20 个公开/生产 DOM 节点**与设置相邻 **14 节点**通过；真实 Controller+WebView2 **14 项**通过。前五套 115 项加教程 14 项的 **129 项**是同日不同原生场景汇总，不是 129 个模型调用或独立 pytest 节点。
- **依据与边界**：[规格与结果](tutorial-20261013.md)、[原生脚本](tutorial_webview_check_20261013.py)、[完整回归的原生分项表](full-regression-20261013.md)。实际宿主和页面是真的，目录/生成边界为本地模拟；该批没有 EXE 验收。

### 9. onedir 安装避免每次临时解包，依赖失败不假成功

- **输入与预期**：旧单文件和新 onedir 分别在隔离 TEMP 启动，观察 `_MEI*`；模拟已装/缺失 Runtime、安装器退出 7、退出 0 但未注册、低空间。预期已装跳过、缺失使用 `/silent /install` 后复查，失败/空间不足在应用落地前阻止。最终安装到中文/空格目录，移除 PATH Python，升级/重启/卸载保留隔离设置和历史标记。
- **历史实际结果（2026-10-14）**：旧单文件 **1 红→onedir 1 绿**；最终编译安装器 **CLI 5 项**通过；正式安装包实际安装/升级/双 WebView2/卸载 **22 项**通过，另包内 M4 **8 项**通过。最终 Setup 为 **56,558,711 字节**，SHA256 `d3149e2ff12ebbac0019337559294d0789d206942694ec9d4bc78844aaac8fde`；历史记录核对桌面/Release 一致。
- **依据与边界**：[CLI 测试](../../tests/test_installer_cli.py)、[冻结启动测试](../../tests/test_installer_distribution.py)、[结果与发布](installer-20261014.md)。缺 Runtime/失败使用私有注册表和可替换外部进程 fixture，没有卸载共享 WebView2 或实际填满磁盘。10 月 14 日真实安装验收机器已有 Runtime；缺依赖安装需要联网。该日记录不覆盖干净 VM 或组员电脑，后续跨设备补充单列在安装维护记录中，不冒充完整真实会话迁移。

### 10. Debug 显示裁剪不损失手动保存的完整脱敏日志

- **输入与预期**：内存 `history_limit=2` 记录 DEBUG/INFO/WARNING/ERROR 和带异常链的 CRITICAL，登记合成敏感串。快照只见最后两条且脱敏，点击 Save 前无日志目录，手动 Save 后包含全部五级和完整异常、没有敏感原文。另检验筛选/清空/三行显示限制下复制只取可见内容，手动归档仍完整。
- **历史实际结果（2026-10-13）**：重叠批次 58、2、10 按节点去重为 **60 通过**；独立真实 WebView2 Debug 窗口 **13 项**通过，包含宽窄/浅深、历史位置、筛选及保存前不写盘。
- **依据与边界**：[归档与脱敏断言](../../tests/test_web_debug.py)、[显示/复制测试](../../tests/test_debug_log_view.py)、[结果](debug-log-view-20261013.md)。这是合成日志与本机 UI 检查；旧[运行日志报告](../../verification/runtime_log_20261009/results.md)中的自动文件写入属于历史初版，不能作为当前行为说明。

## 历史真实模型证据应如何引用

现有范围可以证实曾有真实服务事件，主要用于诊断，而非当前版本成功率或质量评分：

|记录日期/依据|记录内容|可支持与不可支持的结论|
|---|---|---|
|2026-10-11 [访谈可靠性报告](../../verification/interview_reliability_20261011/results.md)及[维护](interview-reliability-20261011.md)|既有 runs 元数据：256431 ms，输入10766 tokens，输出55622，其中 reasoning54075、正文约1547，finish=stop、无自动修正重试|能说明该次长等待主要来自一次模型推理；精简 system 的 UTF-8 字节下降不能换算为当前 token/耗时提升|
|2026-10-12 [单请求与停止报告](../../verification/requirements_stop_20261012/results.md)|旧隐式修正两次214244ms/166757ms，37284/28511 reasoning tokens；另有单次402745ms、65536输出token全为思考、finish=length、正文为空|能支持移除隐式追加请求和解释 reasoning-only 耗尽的研发动机；不能保证 max 强度及时产正文、Stop 停止远端计费|
|2026-10-12 [流式错误复诊](stream-service-error-20261012.md)|用户已有 HTTP 成功后的 `response.failed`，通用 `invalid_request`，没有 param，有 request_id|能支持完整传播服务错误的必要性；不能确认是哪一参数被拒绝或真实网关已修复|

本轮没有读取私人 runs、个人配置、原始会话或密钥，只使用上述已有脱敏结果文档。[run_m1_real_check.py](../../scripts/run_m1_real_check.py)、[verify_m2_generation_real.py](../../scripts/verify_m2_generation_real.py)、[run_ui_real_smoke.py](../../scripts/run_ui_real_smoke.py)、[run_fixed_d1_d2_real_check.py](../../scripts/run_fixed_d1_d2_real_check.py) 是真实调用工具；其存在不能替代执行报告。D1/D2 runner 明确区分 `real_model`/`offline_fixture`，属于源码内容走查，不能写成 EXE/UI 验收。M5 等旧演示入口也不能自动代表当前产品界面。

在本职责限定目录内，未取得一份能将“当前安装版、固定成功案例、真实模型输出、人工内容评分”连在一起的完整结果。真实模型当前版本质量、用户提升比例和试用满意度不据此量化。

## 完整回归与失败口径

|日期与范围|准确结果|解释|
|---|---|---|
|2026-10-07 [Skill 目标修正全量轮](../../verification/baseline/agent_skill_target_20261007/results.md)|721通过、17失败、1跳过，后本轮相关5失败定向复验通过|未重新执行全量；12项无关历史差异单列，不能称全绿|
|2026-10-08 [仓库迁移全量轮](../../verification/repository_handoff_20261008/results.md)|710通过、35失败、1跳过；迁移定向44通过|本轮重解析两份 JUnit 与报告一致；35失败分23迁移相关/12历史，定向通过不能代替全量再跑|
|2026-10-13 [完整回归](full-regression-20261013.md)|单次 **1746通过、82失败、1跳过，1829节点，1921.36秒**|这是最近可读的完整运行结论|
|同日修改前失败复跑|原82失败中72失败、10通过；10项当前隔离复验亦通过|72项含旧Tk/提示/移除合同及业务基线差异，不能一概称测试过时；10项稳定性根因未完全定位|
|同日按节点最后结果汇总|**1764通过、72失败、1跳过，1837个不同节点**|多次运行合并，不是一次完整通过结果，也不是2026-10-18新跑结果|

2026-10-14 的专项结果只能说明各自改变后的范围，没有新的完整全仓结果。已撤回的网关路由改动及其旧 EXE 验证不可用于最终交付；[gateway-models-20261014.md](gateway-models-20261014.md)的最新用户澄清优先于其中早期诊断。Spec/Standards “0待修”是限定增量静态审查，不是额外执行测试或发布认证。

## 验收脚本的范围与未测限制

|脚本类型|当前可证明的范围|不得外推|
|---|---|---|
|[verify_exe_chain.py](../../scripts/verify_exe_chain.py)、[verify_m2_release.py](../../scripts/verify_m2_release.py)|源码/冻结入口到本地 HTTP stub、确认、保存重开、导出；后者明确 `real_model_call=False`|真实供应商输出质量、当前所有 UI 入口完整有效|
|[verify_ui_layout.py](../../scripts/verify_ui_layout.py)|历史 Tk 控件与缩放几何|当前 WebView2 全页、真实 IME、跨 DPI、读屏、180Hz 实屏|
|11份维护 WebView2 脚本|实际 Windows 宿主/生产页面；不同脚本分别使用合成 bridge、真实 Controller、localhost目录或隔离日志|所有脚本都是完整业务后端、所有平台与实际模型均通过|
|[build.ps1](../../scripts/build.ps1)、[build-installer.ps1](../../scripts/build-installer.ps1)|可重复构建入口；结合实际历史产物验收解释|仅因存在脚本就认定构建成功或新源码已进入旧产物|

仍需保留的限制：完整回归72项失败与10项隔离不复现稳定性问题；真实模型和第三方 Skill 推荐质量；跨用户 DPAPI；干净 VM、缺 Runtime 的真实安装；长期资源、大量真实历史、真实输入法、读屏、跨 DPI 与高刷屏。组员电脑上的一次跨设备可用性验证由用户于 2026 年 10 月 20 日确认，详细环境与步骤未留存，见[安装维护记录](installer-20261014.md)。完整逐页审查当时暂停，不能据专项成功声称已恢复完成。浏览器 DOM/Tk/WebView2 中的合成内容不会变成真实用户效果数据。

## 本轮核查记录

仅新增本文件。没有运行测试、构建、安装、外部网络、模型请求、提交或发布；没有修改任何程序或并行工作。核查中一次 Windows rg 通配符参数、一次 PowerShell 管道写法失败，均改为明确路径/有效语法后完成文件盘点，不属于产品失败；对被忽略报告追加使用 `--no-ignore`，仅查验收文档，不读取原始私人数据。

文档机械检查：48 处本地 Markdown 引用全部存在，10 个代表用例齐备，功能组模块数合计166，无尾随空白。该检查只验证文档完整性，不新增产品通过证据。
