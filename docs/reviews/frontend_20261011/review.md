# PromptSmith 完整前端审查（2026-10-11）

2026-10-11 后续修复已完成：13项确认问题均resolved，313个不同回归节点最新全部通过；两套实际WebView2主窗8+7项及Debug独立窗检查通过。Tk隐藏窗口初始宽度循环也已修复。[修复验收](../../../verification/frontend_fixes_20261011/results.md)与[audit.json](audit.json)为当前状态；下文是修复前审查快照，保留原失败与版本。真实系统/EXE/服务门槛仍blocked，未宣称发布就绪。

已核对全部可得入口，覆盖34个逻辑页、68个共享定义、492个实例；每实例八维检查和唯一处置、每定义十维蓝图已落盘。审查与方案已交付，**运行覆盖尚未完全闭合，产品不满足发布门槛**。未修改应用源码。

基线为`6fd857659ec6fe1c8e83c4fb61841e50d593731b`加当前未提交工作树，[源码SHA256](evidence/source-manifest.json)固定版本。应用源码与运行资源未改，HANDOFF/UI指南仅新增审查入口；初始SHA256清单保留，最终差异见[evidence/final-integrity.json](evidence/final-integrity.json)。已有用户/前轮改动全部保留；默认WebView2、独立Debug、可达Tk兼容编辑/显式回退、OS文件选择器全部在范围。历史archive不是本轮指令。

重点是2项P1：整合忙态未渲染取消按钮，需求表不能用键盘选择。另有11项P2，包含小窗header/设置/模型菜单裁切、dialog名称/焦点、隐藏思考进入Tab、三个输入的组合确认误触、设置Tab键盘、Debug过期错误、原生保存目录错误和旧回归合同。见[全部问题](findings.md)。

|验证层|本轮证据与边界|
|---|---|
|Chrome154真实资源/模拟桌面桥接|100+27项观察；88符合、39差异，差异不能直接等于39个bug；按根因合并并剔除工具模拟文案误判|
|真实WebView2/Edge154|主窗8项、两次应用重建历史13项、Debug完整保存/异常捕获；同一进程源码运行，非EXE/付费模型|
|真实Tk|首批21项与五页记录，随后93项补验全部通过：18项编辑/短输入、47项字段保存/非法值、25项剩余入口/滚动/清理、3项玻璃按钮生命周期。回调/OS返回模拟与实际控件操作已分开|
|定向/相邻pytest|三批定向/相邻检查合并430个不同节点；最新416通过、14旧UI合同失败。一次批量Skill多工作等待超时隔离复验通过，保留前证据|
|视觉与性能|已目视首批28张Web和12张Tk截图联系表；8次真实展开动画有中间帧、最大变化间隔27.8ms；长Unicode123次渐进更新。另8项Chrome生命周期与100次布局采样通过，中位0.9ms/p95=1.6ms/最大2.2ms；不能推出180Hz/长期堆内存达标|

检查共4138条：{'failed': 148, 'passed': 3077, 'blocked': 369, 'not_applicable': 544}。`blocked`仅表示真实候选/读屏/跨DPI/EXE/服务与原生OS自动化缺口；本地`not_checked`已归零；静态叶子无独立生命周期明确`not_applicable`，不冒充性能通过。全部实例方案：{'refactor': 108, 'retain': 96, 'investigate': 288}；investigate逐实例说明真实平台缺口并链接TASK-014；本地补验记录见TASK-015。**发现与全实例方案覆盖完整；本地可执行补验已收尾，真实系统/EXE/服务运行覆盖仍未闭合。**

发现渠道已核对：HTML虚拟页、所有Web条件分支与31项偏好/连接字段、Tk构造清单、真实运行导航、现行产品交接。初始461实例之外，补登记动态Canvas/ReplyButton及遗漏的取消入口；装饰包装归父组件检查，重复数据按不同职责/来源/状态等价类登记。无限记录与输入不宣称穷举。

保留现有已验证行为：逐题批量回答、充分就停的访谈、显式确认、选用禁重复与来源累计、结果仍在Web、跳过不入最终提示、历史草稿和版本隔离、系统默认字体与局部100%、Windows当前用户DPAPI、诊断内存完整归档与手动保存。没有证据支持再次换渲染引擎或删除复刻动画。

13项缺陷修复任务均未实施；TASK-015本地补验已verified，TASK-014平台补证仍blocked。Debug覆盖与异常cause要求随每项变更同步。DPAPI保护依赖Windows当前用户，不能称抵御同用户恶意进程的绝对安全。

入口索引：

- [机器台账](audit.json) / [机械覆盖结果](coverage.md)
- [13项问题详单](findings.md) / [整改任务与依赖](refactor-plan.md)
- [真实验收交接与全部缺口](verification-handoff.md)
- 34份页面报告见下表；68份组件蓝图及全部实例方案从对应页面进入。

|页面|入口报告|
|---|---|
|PAGE-001 主工作区与历史侧栏|[全部实例](pages/PAGE-001.md)|
|PAGE-002 访谈与模型处理|[全部实例](pages/PAGE-002.md)|
|PAGE-003 Skill选择|[全部实例](pages/PAGE-003.md)|
|PAGE-004 最终提示词|[全部实例](pages/PAGE-004.md)|
|PAGE-005 一起核对需求|[全部实例](pages/PAGE-005.md)|
|PAGE-006 核对方案|[全部实例](pages/PAGE-006.md)|
|PAGE-007 任务摘要|[全部实例](pages/PAGE-007.md)|
|PAGE-008 语气和附注|[全部实例](pages/PAGE-008.md)|
|PAGE-009 模型选择|[全部实例](pages/PAGE-009.md)|
|PAGE-010 整理深度菜单|[全部实例](pages/PAGE-010.md)|
|PAGE-011 任务类型菜单|[全部实例](pages/PAGE-011.md)|
|PAGE-012 文件菜单|[全部实例](pages/PAGE-012.md)|
|PAGE-013 历史会话操作菜单|[全部实例](pages/PAGE-013.md)|
|PAGE-014 搜索历史|[全部实例](pages/PAGE-014.md)|
|PAGE-015 重命名历史|[全部实例](pages/PAGE-015.md)|
|PAGE-016 删除历史|[全部实例](pages/PAGE-016.md)|
|PAGE-017 Web设置 · 模型|[全部实例](pages/PAGE-017.md)|
|PAGE-018 Web设置 · Skill 搜索|[全部实例](pages/PAGE-018.md)|
|PAGE-019 Web设置 · 界面|[全部实例](pages/PAGE-019.md)|
|PAGE-020 Web设置 · 会话与导出|[全部实例](pages/PAGE-020.md)|
|PAGE-021 Web设置 · 诊断|[全部实例](pages/PAGE-021.md)|
|PAGE-022 Web Debug控制台|[全部实例](pages/PAGE-022.md)|
|PAGE-023 Tk统一对话回退|[全部实例](pages/PAGE-023.md)|
|PAGE-024 Tk方案兼容编辑|[全部实例](pages/PAGE-024.md)|
|PAGE-025 Tk Skill详情|[全部实例](pages/PAGE-025.md)|
|PAGE-026 Tk结果高级选项|[全部实例](pages/PAGE-026.md)|
|PAGE-027 Tk五类设置|[全部实例](pages/PAGE-027.md)|
|PAGE-028 Tk多文本编辑（需求/目标/栏目）|[全部实例](pages/PAGE-028.md)|
|PAGE-029 Tk步骤编辑|[全部实例](pages/PAGE-029.md)|
|PAGE-030 Tk关键工作编辑|[全部实例](pages/PAGE-030.md)|
|PAGE-031 Tk简短输入（附注/目标/新增需求）|[全部实例](pages/PAGE-031.md)|
|PAGE-032 Tk Debug回退|[全部实例](pages/PAGE-032.md)|
|PAGE-033 Tk菜单/审查浮层/模型菜单|[全部实例](pages/PAGE-033.md)|
|PAGE-034 Windows文件对话框|[全部实例](pages/PAGE-034.md)|

依据：当前用户/交接合同、WAI-ARIA APG dialog/tabs/menu建议、MDN isComposing与本轮实际DOM；未声明WCAG等级合规。参见正式依据使用https://www.w3.org/WAI/ARIA/apg/patterns/ 与 https://developer.mozilla.org/en-US/docs/Web/API/KeyboardEvent/isComposing 。
