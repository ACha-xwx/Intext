# 前端审查问题修复计划 · 2026-10-11

范围：用户授权修复 FND-001～013，依据 docs/reviews/frontend_20261011/findings.md。保留现有工作区改动；不调用真实模型、不写个人历史、不构建EXE。

测试接口：真实资源的DOM键盘/鼠标/布局及现有DesktopApi/WorkspaceController、PromptSmithApp.save。系统边界可模拟；业务取消/版本保护沿用现有真实会话测试。修复前快照为 verification/frontend_fixes_20261011/before，不用HEAD混入先前改动。

每项顺序：一条失败测试→确认根因→最小修复→原测试通过。公共弹层顺序004→005→006；其余独立。每2～3项记录checkpoint；最后规范/需求双轴review。

|任务|验收|涉及|依赖|验证|
|---|---|---|---|---|
|FND-001 整合忙态取消|Web按钮可达并调用原取消桥接；迟到结果隔离|workspace.js|无|定向回归 red→green，必要原生补验|
|FND-002 小窗顶部|720×440、9/12/18字号、侧栏双态与浅深主题全部操作不越界|workspace.css|无|定向回归 red→green，必要原生补验|
|FND-003 小窗设置|五类正文可滚动，保存与返回可达|workspace.css|无|定向回归 red→green，必要原生补验|
|FND-004 模型边界|内容完成后定位；四边夹取；resize；内部滚动|workspace.js/workspace.css|无|定向回归 red→green，必要原生补验|
|FND-005 弹层名称|dialog明确名称；选择菜单使用menu角色|workspace.js|004|定向回归 red→green，必要原生补验|
|FND-006 焦点生命周期|打开入焦；Escape归还；重建历史行仍返回有效入口；展开状态正确|workspace.js/history.js|005|定向回归 red→green，必要原生补验|
|FND-007 需求键盘选择|Tab和Enter/Space选取完整原文；既有编辑/移除仍可用|workspace.js|无|定向回归 red→green，必要原生补验|
|FND-008 折叠思考|折叠内容不进入Tab；内部焦点回退；反向动画保留|workspace.js|无|定向回归 red→green，必要原生补验|
|FND-009 输入法|模型/搜索/重命名composition Enter不提交；普通Enter正常|workspace.js/history.js|无|定向回归 red→green，必要原生补验|
|FND-010 设置分类键盘|方向键/Home/End切类；单个Tab入口；草稿保留|settings.js|无|定向回归 red→green，必要原生补验|
|FND-011 Debug恢复|成功同步仅清同步错误；保留复制/保存/目录错误|debug.js|无|定向回归 red→green，必要原生补验|
|FND-012 保存错误边界|建目录/文件选择/写入错误不逸出；保留会话与旧文件；换目录重试|ui.py|无|定向回归 red→green，必要原生补验|
|FND-013 旧测试迁移|14个过期合同迁到当前操作与结果，不恢复已删功能|五个测试模块|无|定向回归 red→green，必要原生补验|

风险：IME事件注入不等于真实输入法；headless尺寸不等于180Hz显示；真实读屏/跨DPI/EXE仍单列未验证。审查前EV保持原样；修复后证据另存。

## 完成记录

13项修复、相邻复验及双轴审查已完成。最终313不同节点通过，真实WebView2主窗8+7及Debug独立窗通过；追加隐藏Tk初始宽度循环修复、可靠性旧入口迁移。平台补证保持独立blocked，详见[验收](../verification/frontend_fixes_20261011/results.md)。

## 追加：访谈可靠性三项反馈

R1等待日志：session.validate_unknown_reviews读操作无日志副作用；真实确认/回答/状态变化仍诊断。验收：反复业务校验+Web快照不新增相同日志。

R2重复问题：M1返回与本地review投影联合防重；字段/范围相同不代表问题相同，需保留真正澄清/新事项。验收：截图原题/重编号/轻改措辞不再出现；新细节与主动重开仍可用；保存恢复一致。

R3耗时：测当前system/payload/schema实际字节，精简矛盾规则和无关契约开销；所有阶段保持当前思考强度，只精简提示和上下文。验收：请求完整、不减少max_tokens、无超时强制中断、诊断记录实际模式/开销，离线协议参数验证。

最后按本轮before快照两轴review、相邻回归与CodeGraph同步，真实服务加速仅作为待用户使用观察。

完成记录：30项本轮新增和114项受影响回归通过，300个最新不同节点296通过/4既有差异，before模块已逐一复现4项；Standards/Spec各0待修。访谈system字节减少72.29%/62.38%，未减少用户上下文或模型强度/预算，有限问句归一化的边界及诊断在[本轮维护](../docs/maintenance/interview_reliability_20261011.md)和[验收](../verification/interview_reliability_20261011/results.md)记录。

## 2026-10-12 侧栏动画修复

A1：按钮触发收起逐帧位置/可见性测试，先红灯；A2：消除全高居中重排、保留顶部控件和水平退出，原DOM功能/焦点及事件诊断；A3：浅深/720小窗、反向/减少动画、真实WebView2及相邻回归，两轴diff和交接。主要文件workspace.css/history.js，验收同maintenance/task_plan。本轮前快照独立保存，不混入HEAD未提交UI工作。

完成：A1/A2/A3全部关闭。实际生产范围为resources/ui/workspace/index.html、workspace.css、history.js；新增tests/test_sidebar_animation.py。65浏览器/25真实WebView2通过，两轴0待修、机械检查和索引current。详见[维护](../docs/maintenance/sidebar_animation_20261012.md)与[验收](../verification/sidebar_animation_20261012/results.md)。


## 2026-10-12 思考区读秒

T1：通过applySnapshot与可见计时按钮、受控浏览器时间复现停顿；T2：修复显示时钟而保留后端终态/正文动画，验证迟到快照及切换清理；T3：相邻回归、实际WebView2和两轴diff、诊断/文档/索引。预计workspace.js和局部数字样式，不涉及模型或业务状态。验收以0.1秒连续进展、终态冻结、会话隔离和原思考动画为准。


完成：T1/T2/T3全部验收，73浏览器/13真实WebView2呈现、双轴0发现、机械验收与索引current。生产仅workspace.js；诊断仅生命周期，无逐帧刷日志。证据见[读秒验收](../verification/trace_timer_20261012/results.md)。


## 2026-10-12 需求核对内联、轻量编辑与停止请求

目标：回答充分后把完整需求核对表和操作呈现在对话；删除顶部需求入口及“是这个意思”；格式编辑不触发模型；忙态发送按钮停止当前处理并阻止自动重试。保留显式确认、SessionState版本、已完成成果与迟到事件隔离。

|任务|范围|验收|状态|
|---|---|---|---|
|U1 单次整理与本地编辑|workflow/guided_flow/session及动作回归|M1一次操作一次请求；明确编辑本地保存，当前分析有效时确认后直接M2|complete|
|U2 需求内联|conversation/web_workspace/workspace资源|充分时完整表格与操作可达，访谈时不显示；移除两个入口|complete|
|U3 停止请求|TaskScope/API/UI/桥接与底部按钮|M1/M2/交付可取消；中止流读取、无重试、保留成果、新请求可继续|complete|
|U4 收尾|相邻回归、双轴diff、Debug与文档/索引|定向及相邻通过，独立WebView2检查；说明真实服务边界|complete|

测试接口沿用已授权真实UI动作、SessionState/workflow/API以及生产浏览器DOM/桥接边界。按slice先红→修复→绿。before快照verification/requirements_stop_20261012/before，不以HEAD覆盖历史未提交修改。无真实收费API、个人设置写入或EXE构建。

- [complete] U6 思考外层默认收起，保留用户开关；取消后清动画积压，恢复取消记录静态全文。

完成：357个不同节点最新全部通过，真实WebView2合成快照28项通过，双轴各0待修。402.745秒为单次max思考耗尽65536输出预算而无正文，现有准确提示与Stop；不自动降低强度/预算。旧测试合同迁移及首次准备超时均留证，无新收费API/EXE/提交。详见[验收](../verification/requirements_stop_20261012/results.md)。


## 2026-10-12 全流程Token效率

目标：检查需求访谈、方案、Skill搜索/筛选、整合和最终提示的调用链，减少不必要请求与重复输入。保持当前所有阶段思考强度、完整用户信息、输出预算、显式确认、取消/版本保护和手动保存日志。以本轮before文件快照为基线，不混入先前未提交工作。

- [complete] E1 建立公共API/工作流离线反馈环，统计各阶段请求数、system/payload/schema序列化字节及可用token估计。
- [complete] E2 按实测根因优化协议公共输入表示与阶段上下文/提示冗余；每slice先红后绿，不猜测删用户信息。
- [complete] E3 检查访谈停止条件、Skill重复调用/输出和交付一致性，修复可复现的多余处理。
- [complete] E4 定向及相邻回归、Debug诊断、前后量化、独立diff审查、交接文档与索引。

验收：同样的任务事实、来源、功能和模型设置保留，协议传入约束有效；代表性全流程输入量较before减少、重复请求不增加，给出真实计量边界而不把字节当真实模型token。无付费调用、EXE或提交。


完成：E1–E4全部关闭；代表普通阶段输入cl100k_base估算减少8.20%，不冒充真实服务token/耗时。473个不同回归节点最新470通过/3已复现旧合同差异，公共边界186/186与最新API72/72通过，两轴各0待修。371机械检查全绿，18文件manifest闭合，CodeGraph209files/5294nodes/16547edges且current。源码、Debug与交接同步，无收费模型/个人文件/EXE/提交。见[验收](../verification/token_efficiency_20261012/results.md)。


## 2026-10-12 方案核对内联与逐阶段返回

目标：把原方案面板全部内容/编辑关键工作/确认及Skill操作移至对话，删顶部核对方案与修改方案目标；需求确认后隐藏需求表；每个后续阶段有返回上一步，恢复上一阶段核对开始位置。沿用完整用户信息、SessionState版本/取消/显式确认、Debug手动完整保存。

|任务|文件/范围|验收与验证|依赖|状态|
|---|---|---|---|---|
|P1 方案内联/需求隐藏|conversation、web_workspace、index/workspace资源|生产DOM和Tk完整方案可见、无旧入口；确认需求后不留重复表；先红后绿|无|complete|
|P2 阶段返回状态|SessionState/会话动作|返回保留成果/版本/问答，不产生模型调用；保存重开恢复；实际改动原规则失效；SessionState/桥接回归|P1|complete|
|P3 返回控件与定位|conversation、web_workspace/workspace|方案→需求、Skill→方案、结果→实际前一步，访谈/核对可回看；顶部定位、忙态Stop先取消；生产DOM/Tk回归|P2|complete|
|P4 验收/审查/交接|定向相邻、维护及index|Debug生命周期记录不刷屏，真实WebView2合成验收、两轴独立diff及当前文档|P3|complete|

测试边界沿用前序用户已授权的生产DOM applySnapshot/真实桌面桥接 dispatch、Tk公开动作、SessionState与workflow输入/取消。不新增私有mock seam，不向个人设置写入，不调用真实模型或构建EXE。计划与任务表按本轮用户明确授权执行；按slice实施后review，保留既有未提交改动，以本轮before为基线。


完成：P1–P4全部关闭，203个不同自动化节点最新全部通过；真实WebView2浅深22项通过，Standards/Spec各0待修。独立16文件before/current指纹闭合，Debug与交接同步。范围及过程失败完整保留于[验收](../verification/plan_inline_20261012/results.md)。无真实模型/个人设置或会话写入/EXE/提交。


## 2026-10-12 阶段UI精简
C1方案确认后隐藏核对卡，返回方案恢复；C2取消整合移到对应步骤，停止/取消保护不变；C3定向回归与独立diff审查、交接/Debug/索引同步。沿用已授权公开边界，基线verification/stage_cleanup_20261012/before。


## 2026-10-12 Web 编辑窗口迁移

W1 需求/候选真实复现与非阻塞 Web 编辑；W2 方案全字段/步骤/关键工作与附注迁移；W3 Debug、版本隔离、浅深/小窗/键盘/实际 WebView2 与双轴复核。范围和验收见 ../docs/maintenance/web_editors_20261012.md。

## 2026-10-12 团队启动与全部模型请求

L1 run.bat固定目录/优先.venv/显式Web/失败可见；L2记录实际解释器与同解释器修复命令；G1 GPT400的Schema发送前兼容选择；A1–A2检查五家全部19预设，Claude/DeepSeek Messages独立契约与公开摘要、采样适配；G2/A3公开HTTP及启动边界回归；L3/G3定向相邻、独立规范/需求审查与交接。详见[维护](../docs/maintenance/startup_responses_20261012.md)及[状态](../docs/maintenance/task_plan.md)。无付费请求，不改个人配置，不构建EXE。

完成：L1–L3、G1–G3、A1–A3全部关闭。最终233项定向及相邻回归通过、实际默认WebView2启动烟测退出0且无自动日志、规范/需求双轴各0待修。源码和交接已更新；队员及真实模型服务仍待对应环境验证，本轮未提交推送。

## 2026-10-12 真实网关流式错误复诊

S1公开客户端→本地HTTP复现服务error/response.failed细节丢失；S2修复ApiError/界面/Debug错误说明与失败元数据传播，保留脱敏/手动日志/取消和单请求；S3定向相邻、独立两轴diff审查、交接和索引。基线f473fd5，远端具体原因等待用户stream_error原文，不调用收费网关。详见[复诊记录](../docs/maintenance/stream_service_error_20261012.md)。

诊断修复S1–S3完成：172项定向/相邻、3文件AST、diff检查通过，双轴各0待修，CodeGraph已同步。真实网关错误原因待用户原文，未宣称远端已修复。


## 2026-10-12 Responses请求兼容续修

R1（api.py/公开HTTP测试）：连接、文本、结构化请求统一标准消息列表与store=false，流式/非流式单请求且内容不丢失。R2（同模块/受影响合同测试，依赖R1）：不兼容原生strict时保留完整提示Schema，不强加json_object；简单合法strict及明确格式400兼容策略保留。R3（依赖R2）：Debug与相邻回归、双轴只读审查、维护/交接/索引同步。每slice先红后绿，保持模型/强度/预算和Stop，无收费API/个人设置/EXE/远端提交。

R1–R3全部完成：289个不同节点最新全部通过，Standards/Spec各0待修；Debug/索引/交接同步，真实中转仍需新版源码复测。

## 2026-10-12 设置下拉显示

D1统一select及input+datalist的箭头、间距和焦点；D2验证原生键盘、自定义值、预设联动、草稿/保存并完成Debug、双轴审查和交接。两项均complete，17项检查通过，Spec/Standards各0待修。详见[维护](../docs/maintenance/settings_dropdown_20261012.md)；本轮无真实WebView2/EXE或模型验收，未提交推送。

追加D3/D4：用户实际要求是预设切换和下方协议可点击。生产DOM测试应从已填DeepSeek展开完整预设、选择另一个服务、再选择协议，覆盖自定义输入/草稿/保存与弹层生命周期；之后用隔离WebView2验证，记录Debug并做增量双轴审查。基线为本轮开始的工作树，依赖D3后完成D4；不改业务确认、密钥、API请求。

追加J1/J2：对照队员旧json_object的param=input修复，在本地复杂契约及strict明确不支持后的兼容路径增加input可见JSON指令，原wire独立；本地HTTP先红后绿，保持模型/强度/预算/单请求/错误详情，相关回归与审查后收尾。D3/D4/J1/J2已完成，255节点最新通过、实际WebView220项通过、双轴0待修。见[维护](../docs/maintenance/settings_choice_interaction_20261012.md)，无收费请求/个人配置/EXE/提交推送。
