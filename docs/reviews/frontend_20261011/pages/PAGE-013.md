# PAGE-013 · 历史会话操作菜单

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`history / menu`。源码：`resources/ui/workspace/history.js:35-47`。

历史菜单已实现Up/Down、置顶/取消与危险删除；Escape后入口aria-expanded归零。回落焦点仍有重建边界。

变体：置顶/非置顶、键盘/鼠标、关闭。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-108|历史菜单外壳 · `.history-menu; resources/ui/workspace/workspace.js:260`|[refactor](../components/BP-022.md)|FND-006|已判定，范围见检查问题|
|CMP-109|重命名 · `.history-menu / 重命名; resources/ui/workspace/history.js:38`|[retain](../components/BP-032.md)|无确定发现|已判定，范围见检查问题|
|CMP-110|置顶/取消置顶 · `.history-menu / 置顶/取消置顶; resources/ui/workspace/history.js:38`|[retain](../components/BP-032.md)|无确定发现|已判定，范围见检查问题|
|CMP-111|删除 · `.history-menu / 删除; resources/ui/workspace/history.js:38`|[retain](../components/BP-032.md)|无确定发现|已判定，范围见检查问题|

本页SCN：SCN-026；EV：EV-005,EV-006,EV-007。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：FND-006。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
