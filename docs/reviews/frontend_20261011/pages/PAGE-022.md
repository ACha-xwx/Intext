# PAGE-022 · Web Debug控制台

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`debug.html`。源码：`resources/ui/workspace/debug.html`。

独立Debug日志内存完整归档，显示可截断；同步失败后恢复仍残留旧错误为已复现缺陷。

变体：全部级别/过滤、清空/复制/保存失败、滚动/缓存截断、浅/深/小窗。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-195|Debug标题与缓存计数 · `header / #count; resources/ui/workspace/debug.html:6`|[retain](../components/BP-040.md)|无确定发现|已判定，范围见检查问题|
|CMP-196|日志级别 · `#level; resources/ui/workspace/debug.js:26`|[retain](../components/BP-041.md)|无确定发现|已判定，范围见检查问题|
|CMP-197|自动滚动 · `#autoscroll; resources/ui/workspace/debug.js:26`|[retain](../components/BP-041.md)|无确定发现|已判定，范围见检查问题|
|CMP-198|复制日志 · `#copy; resources/ui/workspace/debug.js:26`|[retain](../components/BP-041.md)|无确定发现|已判定，范围见检查问题|
|CMP-199|清空显示 · `#clear; resources/ui/workspace/debug.js:26`|[retain](../components/BP-041.md)|无确定发现|已判定，范围见检查问题|
|CMP-200|保存日志 · `#save; resources/ui/workspace/debug.js:26`|[retain](../components/BP-041.md)|无确定发现|已判定，范围见检查问题|
|CMP-201|打开日志目录 · `#directory; resources/ui/workspace/debug.js:26`|[retain](../components/BP-041.md)|无确定发现|已判定，范围见检查问题|
|CMP-202|日志正文与颜色 · `#log-lines / #debug-scroll; resources/ui/workspace/debug.js:7`|[retain](../components/BP-042.md)|无确定发现|已判定，范围见检查问题|
|CMP-203|保存状态和错误 · `#save-status / #debug-error; resources/ui/workspace/debug.js:22`|[refactor](../components/BP-043.md)|FND-011|已判定，范围见检查问题|

本页SCN：SCN-035；EV：EV-005,EV-006,EV-007。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：FND-011。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
