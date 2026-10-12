# PAGE-009 · 模型选择

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`workspace / model-picker`。源码：`resources/ui/workspace/workspace.js:309-339`。

五供应商、模型搜索、能力图标、四档键盘及Unicode动态已验；小窗菜单上界缺钳制。

变体：五供应商、搜索无/有、自定义模型、四档强度、快切/失败。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-081|模型浮层外壳 · `.picker; resources/ui/workspace/workspace.js:260`|[refactor](../components/BP-022.md)|FND-004, FND-005, FND-006|已判定，范围见检查问题|
|CMP-082|搜索模型 · `.picker-search input; resources/ui/workspace/workspace.js:309`|[refactor](../components/BP-026.md)|FND-004, FND-009|已判定，范围见检查问题|
|CMP-083|清空搜索 · `.clear-search; resources/ui/workspace/workspace.js:309`|[refactor](../components/BP-026.md)|FND-004, FND-009|已判定，范围见检查问题|
|CMP-084|模型列表与无结果 · `.models; resources/ui/workspace/workspace.js:309`|[refactor](../components/BP-026.md)|FND-004, FND-009|已判定，范围见检查问题|
|CMP-085|OpenAI供应商与图标 · `[data-provider=OpenAI]; resources/ui/workspace/workspace.js:334`|[refactor](../components/BP-027.md)|FND-004|已判定，范围见检查问题|
|CMP-086|Anthropic供应商与图标 · `[data-provider=Anthropic]; resources/ui/workspace/workspace.js:334`|[refactor](../components/BP-027.md)|FND-004|已判定，范围见检查问题|
|CMP-087|Google供应商与图标 · `[data-provider=Google]; resources/ui/workspace/workspace.js:334`|[refactor](../components/BP-027.md)|FND-004|已判定，范围见检查问题|
|CMP-088|xAI供应商与图标 · `[data-provider=xAI]; resources/ui/workspace/workspace.js:334`|[refactor](../components/BP-027.md)|FND-004|已判定，范围见检查问题|
|CMP-089|DeepSeek供应商与图标 · `[data-provider=DeepSeek]; resources/ui/workspace/workspace.js:334`|[refactor](../components/BP-027.md)|FND-004|已判定，范围见检查问题|
|CMP-090|模型名称/说明/能力图标/选中勾 · `.model-row; resources/ui/workspace/workspace.js:329`|[retain](../components/BP-028.md)|无确定发现|已判定，范围见检查问题|
|CMP-091|思考强度 low · `[data-effort=low]; resources/ui/workspace/workspace.js:320`|[retain](../components/BP-029.md)|无确定发现|已判定，范围见检查问题|
|CMP-092|思考强度 medium · `[data-effort=medium]; resources/ui/workspace/workspace.js:320`|[retain](../components/BP-029.md)|无确定发现|已判定，范围见检查问题|
|CMP-093|思考强度 high · `[data-effort=high]; resources/ui/workspace/workspace.js:320`|[retain](../components/BP-029.md)|无确定发现|已判定，范围见检查问题|
|CMP-094|思考强度 max · `[data-effort=max]; resources/ui/workspace/workspace.js:320`|[retain](../components/BP-029.md)|无确定发现|已判定，范围见检查问题|
|CMP-095|思考强度信号与滑块 · `.effort-indicator / .thinking-indicator; resources/ui/workspace/workspace.js:32`|[retain](../components/BP-030.md)|无确定发现|已判定，范围见检查问题|

本页SCN：SCN-022；EV：EV-005,EV-006,EV-007。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：FND-004、FND-005、FND-006、FND-009。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
