# PAGE-032 · Tk Debug回退

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`native dialog / Tk Debug回退`。源码：`src/promptsmith/debug_console.py:1`。

真实Tk Debug颜色、after清理、不开自动日志保存已验。个别目录失败只有日志提示需补强恢复文案。

变体：鼠标/键盘、保存/取消/错误、长内容/小屏。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-440|级别筛选 · `native / 级别筛选; src/promptsmith/debug_console.py:1`|[investigate](../components/BP-059.md)|无确定发现|semantics_accessibility|
|CMP-441|自动滚动 · `native / 自动滚动; src/promptsmith/debug_console.py:1`|[investigate](../components/BP-059.md)|无确定发现|semantics_accessibility|
|CMP-442|复制 · `native / 复制; src/promptsmith/debug_console.py:1`|[investigate](../components/BP-059.md)|无确定发现|semantics_accessibility|
|CMP-443|清空显示 · `native / 清空显示; src/promptsmith/debug_console.py:1`|[investigate](../components/BP-059.md)|无确定发现|semantics_accessibility|
|CMP-444|保存日志 · `native / 保存日志; src/promptsmith/debug_console.py:1`|[investigate](../components/BP-059.md)|无确定发现|semantics_accessibility|
|CMP-445|日志目录 · `native / 日志目录; src/promptsmith/debug_console.py:1`|[investigate](../components/BP-059.md)|无确定发现|semantics_accessibility|
|CMP-446|日志正文与严重颜色 · `native / 日志正文与严重颜色; src/promptsmith/debug_console.py:1`|[investigate](../components/BP-059.md)|无确定发现|semantics_accessibility|
|CMP-447|错误与保存状态 · `native / 错误与保存状态; src/promptsmith/debug_console.py:1`|[investigate](../components/BP-059.md)|无确定发现|semantics_accessibility|

本页SCN：SCN-045；EV：EV-010,EV-007。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：当前没有确定缺陷；不代表未执行环境通过。。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
