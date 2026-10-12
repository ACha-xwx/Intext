# 回复组件、流式思考与整页融合验收

更新：2026-10-10。回复组件与整页连续浅深主题已完成源码验收。五份完成报告按最新 classname/name 去重合并为 **342 passed / 0 failed / 0 error / 0 skipped**；Windows Tk 最终探针 38 项不同检查通过（主题反复切换共94次断言），0回调/弹框错误。源码 smoke 退出0；无真实模型或新版EXE验收。

## 范围

- 空任务中央 Hero、用户圆角气泡、AI 无外框正文、点阵/折叠/细线思考区和真实上下文条。
- 连续浅深外壳/导航/对话/输入框外围/底部状态；去 Notebook 原生外框和重复下一步，保留必要恢复操作，设置内部继续默认组件。
- 三协议 SSE，DeepSeek `thinking.enabled` 和 `delta.reasoning_content`；缓冲 JSON 代理兼容。部分失败证据、拒绝、用量、token 截断和请求取消保留。
- 16ms 有界自适应增量，完整 Unicode、段落单换行、结束继续逐帧追赶，不同步跳到末尾。
- Markdown H1–H6/Setext/HTML 标题和固定提示词分节；显示标签不改变复制/导出正文。
- 所有问题独立回答、空白禁用、选项填该题、乱序收集、主题刷新保持草稿、最后统一整理一次。
- 五轮后逐轮授权、需求/方案明确确认、Skill/交付、会话保存重开、取消隔离、默认字体、DPAPI 和手动 Debug 保存。
- 流式完成屏障：3000 个事件的完成回调刻意先到，仍在全部元数据应用后才保存，不等待动画排空；成功/失败状态重开保持等价。

## 环境与边界

Windows Python 3.11、真实 Tcl/Tk 8.6、pytest。隔离 LOCALAPPDATA、合成凭据、localhost SSE 和离线注入响应；网络 runner 拒绝非 loopback 连接。没有调用真实模型或读取生产密钥，没有构建 EXE、提交或推送。

原始 JUnit、脚本、截图和性能数据保存在 Git 忽略的 `local_artifacts/response_workspace_20261010/`。API 协议通过证明本机实现与分块合同，不代表真实供应商的质量、速度或网关一定支持流式思考。仅 JSON 代理收到完整包后才显示思考，不称作真正实时。

## 自动化结果

| 检查 | 当前结果 | 原始证据 |
| --- | --- | --- |
| 整页/回复/逐题/取消与保存、JGS、交付、引导对话 | 88 passed / 0 failed / 0 error / 0 skipped，295.111 秒 | fused_ui.xml |
| SSE/API/截断诊断/模型强度 | 137 passed / 0 failed / 0 error / 0 skipped，19.951 秒 | transport_latest.xml |
| 最终设置/主题/访谈/会话/滚动/Debug 相邻复验 | 146 passed，362.339 秒 | boundaries_final.xml |
| 直接 refresh 的整页主题同步集中复验 | 40 passed，221.341 秒 | theme_reply_final.xml |
| 需求长原文及表格操作，修复滚动条高度反馈 | 5 passed，16.476 秒 | table_final.xml |
| 最新分批去重合并 | 342 passed，无失败/错误/跳过 | aggregate_results.py / aggregate_results.json |
| 最终源码入口 smoke | 退出 0，含导入/退出5.169秒，无自动日志/字体输出 | smoke.py |

中间失败保留原始证据，不计作当前成功：initial.xml 两项为旧底部回答合同和 tuple/list 保存差异；final_ui.xml 一项为新测试误猜错误类别；adjacent.xml 两项为 gap 测试夹具缺 field/scope 及本轮真实完成/保存时序。夹具补齐并保留原引导断言，保存时序通过完成屏障修复，fused_ui.xml 复验通过；没有放宽保存等价或业务校验。

最后相邻批 `boundaries_latest` 因真实布局循环手动中止，无完整 JUnit，不纳入通过统计。它此前发现直接 refresh 的外壳/输入主题不同步，集中40项复验已修复。表格单独用 pytest 超时堆栈和 `idle_diagnostic.py` 定位到默认高度的 SlimScrollbar 撑高短 Text，显示/隐藏让时间线在1761/1932px持续振荡；有限1500步诊断明确失败。改滚动条自然高度为1，表格5项复验通过，再执行 `boundaries_final.xml`。两次被中止诊断不算通过，未停止用户自启应用。

## 实际窗口与性能

最新独立 Windows Tk 进程 `acceptance.py` 已通过 94 次断言（38 个不同断言，主题多次切换重复核对）；0 回调/弹框错误。浅深 Hero、正在思考、逐题表单、最终结果及小窗口共10张截图已目视核对。探针明确放宽其minimum后核对真实client为960×640与720×405，输入/发送/设置/保存可达；默认应用仍按屏幕适配16:9与正常minimum。之前图片名720实际960×540的版本为探针尺寸不足，已覆盖为明确几何验证后的720×405。

最终首次显示3.731秒，包含Python导入和初始化。约16万Unicode字符连续追赶3.233秒，161次独立心跳；236帧增量，最大单帧4098字符（完整字素边界略超过4096），文字tick p95 0.891ms、max 1.451ms。前次3.261秒首次显示属于滚动条修复前版本，最终数据以acceptance.json为准。16ms是Tk调度间隔，非显示器FPS；这是合成内容及本机性能，非真实模型响应速度。

Debug 验证新增生命周期和完整错误链；运行日志留在内存，只有点击保存日志后出现 `.log`，合成密钥脱敏。模型 `runs/` 证据遵循原合同。探针初次复用旧手动保存目录，错误识别旧 `.log` 为自动写盘，现每次使用唯一隔离 profile，不删除旧证据。

整页截图发现的原生细框和输入圆角白角已修复：Notebook 采用空布局保留页切换，composer Canvas 自身使用当前主题背景。设置页控件仍使用默认样式。

## 收尾

compileall src/tests、git diff --check通过；54项spec提示资源存在，FontTools依赖未恢复；7份当前文档的109个相对链接有效。CodeGraph sync/status最新：159 files / 4091 nodes / 12835 edges，up to date。维护三文件、交接、架构、UI和开发指南已同步。只开放本results.md到共享材料，原始日志、截图、隔离设置和证据仍忽略。

历史全量失败清单仍见 [本批旧契约](../bug_batch_20261009/results.md)，本轮342项是相关模块分批与定向复验，不宣称整个仓库全量全绿。没有真实API、付费调用、外部站点验证、EXE重建、提交或推送；用户试用仍单列。
