# PAGE-012 · 文件菜单

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`workspace / menu:file`。源码：`resources/ui/workspace/workspace.js:303-307,345`。

文件菜单保留新建/打开/保存/另存，Ctrl+S；保存目录mkdir在异常捕获之外。原生OS选择器交互待验证。

变体：打开/关闭、当前选择、忙态/键盘、长标题。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-103|浮层菜单外壳 · `.popup; resources/ui/workspace/workspace.js:260`|[refactor](../components/BP-022.md)|FND-005, FND-006|已判定，范围见检查问题|
|CMP-104|new · `.menu-row / new; resources/ui/workspace/workspace.js:307`|[retain](../components/BP-031.md)|无确定发现|已判定，范围见检查问题|
|CMP-105|open · `.menu-row / open; resources/ui/workspace/workspace.js:307`|[retain](../components/BP-031.md)|无确定发现|已判定，范围见检查问题|
|CMP-106|save · `.menu-row / save; resources/ui/workspace/workspace.js:307`|[refactor](../components/BP-031.md)|FND-012|已判定，范围见检查问题|
|CMP-107|save_as · `.menu-row / save_as; resources/ui/workspace/workspace.js:307`|[refactor](../components/BP-031.md)|FND-012|已判定，范围见检查问题|

本页SCN：SCN-025；EV：EV-005,EV-006,EV-007。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：FND-005、FND-006、FND-012。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
