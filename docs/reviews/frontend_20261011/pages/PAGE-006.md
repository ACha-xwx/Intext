# PAGE-006 · 核对方案

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`workspace / panel:plan`。源码：`resources/ui/workspace/workspace.js:274-302`。

整个方案移到右上角；details章节展开保存。高级编辑继续原生兼容，不把它当独立Web已适配。

变体：空/有内容、打开/更新/关闭、忙/可用。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-067|面板外壳与关闭 · `.review-panel; resources/ui/workspace/workspace.js:260`|[refactor](../components/BP-022.md)|FND-005, FND-006|已判定，范围见检查问题|
|CMP-068|方案状态 · `.notice; resources/ui/workspace/workspace.js:287`|[retain](../components/BP-017.md)|无确定发现|已判定，范围见检查问题|
|CMP-069|方案全文与折叠章节 · `.reading details; resources/ui/workspace/workspace.js:40`|[retain](../components/BP-021.md)|无确定发现|已判定，范围见检查问题|
|CMP-070|edit_plan_goal · `[data-action=edit_plan_goal]; resources/ui/workspace/workspace.js:33`|[retain](../components/BP-009.md)|无确定发现|已判定，范围见检查问题|
|CMP-071|edit_plan · `[data-action=edit_plan]; resources/ui/workspace/workspace.js:33`|[retain](../components/BP-009.md)|无确定发现|已判定，范围见检查问题|
|CMP-072|review_plan · `[data-action=review_plan]; resources/ui/workspace/workspace.js:33`|[retain](../components/BP-009.md)|无确定发现|已判定，范围见检查问题|
|CMP-073|confirm_plan · `[data-action=confirm_plan]; resources/ui/workspace/workspace.js:33`|[retain](../components/BP-009.md)|无确定发现|已判定，范围见检查问题|
|CMP-074|find_skills · `[data-action=find_skills]; resources/ui/workspace/workspace.js:33`|[retain](../components/BP-009.md)|无确定发现|已判定，范围见检查问题|

本页SCN：SCN-019；EV：EV-005,EV-006,EV-007。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：FND-005、FND-006。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
