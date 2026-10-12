# PAGE-008 · 语气和附注

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`workspace / panel:result`。源码：`resources/ui/workspace/workspace.js:274-302`。

语气/附注无旧界面跳转。附注使用原生短输入，当前审查只测取消/静态路径；真实系统IME待补。

变体：空/有内容、打开/更新/关闭、忙/可用。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-077|面板外壳与关闭 · `.review-panel; resources/ui/workspace/workspace.js:260`|[refactor](../components/BP-022.md)|FND-005, FND-006|已判定，范围见检查问题|
|CMP-078|提示词语气 · `select[aria-label=提示词语气]; resources/ui/workspace/workspace.js:298`|[retain](../components/BP-024.md)|无确定发现|已判定，范围见检查问题|
|CMP-079|用户附注/空说明 · `.reading / .notice; resources/ui/workspace/workspace.js:299`|[retain](../components/BP-025.md)|无确定发现|已判定，范围见检查问题|
|CMP-080|添加附注 · `[data-action=add_final_note]; resources/ui/workspace/workspace.js:33`|[retain](../components/BP-009.md)|无确定发现|已判定，范围见检查问题|

本页SCN：SCN-021；EV：EV-005,EV-006,EV-007。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：FND-005、FND-006。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
