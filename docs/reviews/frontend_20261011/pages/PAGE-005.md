# PAGE-005 · 一起核对需求

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`workspace / panel:requirements`。源码：`resources/ui/workspace/workspace.js:274-302`。

四列需求表可鼠标读全文，但缺键盘选行入口；浮层缺名称和焦点进入/回落。

变体：空/有内容、打开/更新/关闭、忙/可用。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-058|面板外壳与关闭 · `.review-panel; resources/ui/workspace/workspace.js:260`|[refactor](../components/BP-022.md)|FND-005, FND-006|已判定，范围见检查问题|
|CMP-059|需求表头/行/选择 · `.review-panel / 需求表头/行/选择; resources/ui/workspace/workspace.js:290`|[refactor](../components/BP-023.md)|FND-007|已判定，范围见检查问题|
|CMP-060|完整需求详情 · `.review-panel / 完整需求详情; resources/ui/workspace/workspace.js:290`|[refactor](../components/BP-023.md)|FND-007|已判定，范围见检查问题|
|CMP-061|冲突与确认前原因 · `.review-panel / 冲突与确认前原因; resources/ui/workspace/workspace.js:290`|[refactor](../components/BP-023.md)|FND-007|已判定，范围见检查问题|
|CMP-062|edit_requirement · `[data-action=edit_requirement]; resources/ui/workspace/workspace.js:33`|[retain](../components/BP-009.md)|无确定发现|已判定，范围见检查问题|
|CMP-063|remove_requirement · `[data-action=remove_requirement]; resources/ui/workspace/workspace.js:33`|[retain](../components/BP-009.md)|无确定发现|已判定，范围见检查问题|
|CMP-064|accept_requirement · `[data-action=accept_requirement]; resources/ui/workspace/workspace.js:33`|[retain](../components/BP-009.md)|无确定发现|已判定，范围见检查问题|
|CMP-065|adopt_requirement · `[data-action=adopt_requirement]; resources/ui/workspace/workspace.js:33`|[retain](../components/BP-009.md)|无确定发现|已判定，范围见检查问题|
|CMP-066|confirm_requirements · `[data-action=confirm_requirements]; resources/ui/workspace/workspace.js:33`|[retain](../components/BP-009.md)|无确定发现|已判定，范围见检查问题|

本页SCN：SCN-018；EV：EV-005,EV-006,EV-007。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：FND-005、FND-006、FND-007。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
