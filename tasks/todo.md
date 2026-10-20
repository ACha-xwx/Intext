# 前端修复任务

## 2026-10-14 安装交付

- [x] I1 复现单文件临时解包并核对官方 WebView2 分发
- [x] I2 onedir 与当前用户安装/缺失依赖安装/低空间阻止
- [x] I3 实际安装、WebView2、升级数据保留、卸载及 Spec/Standards
- [ ] I4 GitHub 源码和 Release、桌面安装包与哈希

- [x] FND-001 整合忙态取消
- [x] FND-002 小窗顶部
- [x] FND-003 小窗设置
- [x] FND-004 模型边界
- [x] FND-005 弹层名称
- [x] FND-006 焦点生命周期
- [x] FND-007 需求键盘选择
- [x] FND-008 折叠思考
- [x] FND-009 输入法
- [x] FND-010 设置分类键盘
- [x] FND-011 Debug恢复
- [x] FND-012 保存错误边界
- [x] FND-013 旧测试迁移
- [x] 相邻回归与真实WebView2/Tk补验
- [x] 双轴review、台账、交接与CodeGraph

## 访谈可靠性追加

- [x] R1等待日志静默与真实事件日志
- [x] R2已答问题防重与针对性澄清
- [x] R3访谈耗时优化与完整输出
- [x] 相邻回归、双轴审查、进度/诊断/交接/索引

## 2026-10-12 侧栏动画

- [x] A1逐帧最小复现与根因
- [x] A2顶部稳定/平滑收起/反向与诊断
- [x] A3浏览器和WebView2复验、两轴审查、交接索引


## 2026-10-12 思考区读秒

- [x] T1真实DOM计时红灯与根因
- [x] T2读秒/终态/切换/正文/诊断修复
- [x] T3相邻及WebView2、双轴审查、交接与索引


## 2026-10-12 需求核对与停止

- [x] U1 格式编辑与明确本地修改
- [x] U2 充分后内联完整需求核对
- [x] U3 全阶段停止及网络中断/迟到保护
- [x] U4 回归、双轴审查、Debug/交接/索引

- [x] U5 继续整理回答位置迁到输入框上方右侧，浅深/小窗与动作验证

- [x] U6 默认收起、开关保留与取消动画/恢复


## 2026-10-12 全流程Token效率

- [x] E1 可复现输入/调用成本基线
- [x] E2 公共协议与阶段冗余最小修复
- [x] E3 全流程多余处理/重复调用回归
- [x] E4 成本比较、Debug/回归、diff与交接索引


## 2026-10-12 方案核对内联与返回
- [x] P1 方案内联、需求确认后隐藏
- [x] P2 保留成果的阶段返回/恢复状态
- [x] P3 每阶段返回控件与顶部定位
- [x] P4 相邻回归、WebView2、审查和交接/索引


## 2026-10-12 阶段UI精简
- [x] C1 已确认方案隐藏/返回恢复，先红后绿。
- [x] C2 整合取消按钮对应步骤/底部无重复，真实取消可用。
- [x] C3 定向相邻验收、双轴审查及交接。


## 2026-10-12 Web 编辑窗口迁移

- [x] W1 需求/候选编辑与卡死修复
- [x] W2 完整方案编辑与附注迁移
- [x] W3 生命周期/回归/审查/交接

## 2026-10-12 团队启动与全部模型请求

- [x] L1/L2 复现环境差异、修复batch与启动诊断。
- [x] G1/G2 GPT Responses 400、JSON兼容选择及协议隔离。
- [x] A1/A2 五家文档核对、Claude/DeepSeek Messages与采样适配。
- [x] A3 19预设×四档×三动作离线请求检查。
- [x] L3/G3 最终定向回归、独立规范/需求审查与文档。

## 2026-10-12 真实网关流式错误复诊

- [x] S1 公开HTTP先红后绿复现错误细节丢失。
- [x] S2 错误详情、完整Debug说明、失败元数据及脱敏。
- [x] S3 定向相邻、两轴审查、维护和CodeGraph同步。
- [x] 取得队员旧证据stream_error原文；仅泛化错误，具体远端原因未确定。


## 2026-10-12 Responses请求兼容续修
- [x] R1 消息列表输入与store=false，公开HTTP红绿。
- [x] R2 业务Schema提示契约兼容及合法strict/错误请求数回归。
- [x] R3 Debug/相邻回归/独立双轴审查/交接与索引；289节点最新全绿，双轴0待修。

## 2026-10-12 设置下拉显示

- [x] D1 统一原生select与可输入建议列表箭头，浅深/字号/窄窗验证。
- [x] D2 原生交互/草稿/保存相邻回归、Debug/索引及独立双轴审查；17项检查通过。
- [x] D3 已填值时展开全部预设并切换、协议可选择，先红后绿。
- [x] D4 键盘/弹层生命周期/真实WebView2/相邻回归、Debug/双轴审查与交接。
- [x] J1 队员JSON输入报告对照、input可见指令/独立业务块红绿。
- [x] J2 API/业务相邻、Debug/双轴审查与交接；本轮255节点及20项实际WebView2通过。


## 2026-10-14 Targeted fixes

- [x] S1 Hide Skill search/selection after prompt generation; preserve return/state and Debug coverage (5 focused checks, both review axes clear).
- [x] S2 Equal glass action rows and notes-only controls; 20 focused checks passed, both review axes clear.
- [x] S3 Introduction-based online AI scoring, robust response handling and accurate recommendation display.
- [x] Run combined regression after S1-S3 (326 distinct latest nodes passed; initial obsolete reachability fixture preserved in evidence).


- [x] S2a Full-width equal glass action rows and remove adoption button.
- [x] S2b Result controls and notes-only panel, focused feedback/Debug/review.

- [x] S3a One summary scoring pass, 0–1 scores and concrete usage.
- [x] S3b Partial response recovery, status/details/Debug and cancellation.
- [x] S3c Incremental two-axis review and S1–S3 combined regression.


- [x] B1 重命名输入样式与指定文案
- [x] B2 运行设置扩充/保存恢复
- [x] B3 全入口用户品牌
- [x] B4 定向验证/双轴审阅/交接

- [x] B5a 修复EXE打包资源遗漏，独立验收及桌面复制
- [x] B5b GitHub提交推送和远端身份确认

- [x] I1 官方WebView2分发与环境要求
- [x] I2 Intext当前用户安装包/依赖闭环
- [x] I3 实际安装与WebView2启动/定向回归/双轴复审（CLI5/原生22/包内8，两轴0待修）
- [x] I4 GitHub Release及桌面安装包（v2026.10.14-setup/648ea1d，两项资产与桌面SHA256一致）


- [x] P1 生产DOM/真实schema复现首次供应商不写盘、教程禁用
- [x] P2 后端数值类型提供step，最小修复、Debug无值诊断
- [x] P4 默认Intext目录迁移/冲突保留/隔离根及DPAPI历史恢复
- [x] P3a 最终EXE原生双启动验收、桌面修复版哈希核对
- [x] P3b a6d0d1a已与本批9172e9a原SHA同步GitHub，远端核对一致

相关回归、源码原生及两轴复审已完成；详见[本批计划](../docs/maintenance/provider-onboarding-20261014.md)。安装包/全量审查保持暂停。


2026-10-14 - [x] G1 根地址中转目录外部HTTP失败复现（1红→11绿）
- [x] G2 用户取消接口处理，api.py及本轮网关测试已撤回
- [x] G3 取消前诊断证据保留，最终验收改为箭头范围
- [x] G4 箭头修复独立EXE与GitHub同步（9172e9a）


- [x] R1 用户确认配置重启仍在，当前交付EXE隔离双启动23项通过
- [x] R2 用户确认外部原因，取消本轮软件接口处理
- [x] R3 底部模型箭头末态中心/逐帧旋转轴红绿
- [x] R4 增量审阅/重建/桌面与GitHub核对（限定范围两轴0待修/EXE24项/远端9172e9a）


- [x] J1 原始 JSON 混入整合/导出红绿
- [x] J2 包装恢复/额外对象/纯文本说明
- [x] J3 多 Skill、保存重开及身份取消迟到保护
- [x] J4 双轴审阅、维护交接与最终产物
