# PAGE-016 · 删除历史

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`history / dialog:delete`。源码：`resources/ui/workspace/history.js:54-99`。

删除仅作用受管history副本；取消不删除外部会话。两次真实WebView2重建应用删除active后新会话可用。

变体：取消/成功/失败、长名/同名/空、IME/键盘。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-121|模态框与关闭 · `.history-dialog; resources/ui/workspace/history.js:56`|[refactor](../components/BP-033.md)|FND-006|已判定，范围见检查问题|
|CMP-122|取消 · `.history-dialog .actions / 取消; resources/ui/workspace/workspace.js:32`|[retain](../components/BP-004.md)|无确定发现|已判定，范围见检查问题|
|CMP-123|删除 · `.history-dialog .actions / 删除; resources/ui/workspace/workspace.js:32`|[retain](../components/BP-004.md)|无确定发现|已判定，范围见检查问题|
|CMP-124|字段/操作错误 · `.dialog-error; resources/ui/workspace/history.js:65`|[retain](../components/BP-008.md)|无确定发现|已判定，范围见检查问题|
|CMP-125|删除范围说明 · `.history-dialog p; resources/ui/workspace/history.js:73`|[retain](../components/BP-017.md)|无确定发现|已判定，范围见检查问题|

本页SCN：SCN-029；EV：EV-005,EV-006,EV-007。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：FND-006。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
