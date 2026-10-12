# PAGE-017 · Web设置 · 模型

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`settings / 模型`。源码：`resources/ui/workspace/settings.js:1-116`。

连接字段、推理、budget、timeout全部纳入。测试只测试/确认独立，DPAPI与公开snapshot无key已验。

变体：未改/草稿/保存、忙/失败/恢复默认、隐藏再返回。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-126|分类Tab和标题 · `.settings-tabs / h1; resources/ui/workspace/settings.js:54`|[refactor](../components/BP-036.md)|FND-003, FND-010|已判定，范围见检查问题|
|CMP-127|返回工作区 · `.settings-heading / .settings-footer / 返回工作区; resources/ui/workspace/workspace.js:32`|[refactor](../components/BP-004.md)|FND-003|已判定，范围见检查问题|
|CMP-128|恢复本类默认 · `.settings-heading / .settings-footer / 恢复本类默认; resources/ui/workspace/workspace.js:32`|[refactor](../components/BP-004.md)|FND-003|已判定，范围见检查问题|
|CMP-129|保存设置 · `.settings-heading / .settings-footer / 保存设置; resources/ui/workspace/workspace.js:32`|[refactor](../components/BP-004.md)|FND-003|已判定，范围见检查问题|
|CMP-130|草稿/保存/请求/错误状态 · `.settings-status; resources/ui/workspace/settings.js:15`|[refactor](../components/BP-037.md)|FND-003|已判定，范围见检查问题|
|CMP-131|connection.provider · `#settings-field-connection-provider; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-132|connection.protocol · `#settings-field-connection-protocol; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-133|connection.base_url · `#settings-field-connection-base_url; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-134|connection.model · `#settings-field-connection-model; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-135|API Key输入与保存保护 · `#settings-key; resources/ui/workspace/settings.js:75`|[refactor](../components/BP-039.md)|FND-003|behavior|
|CMP-136|清空密钥 · `.settings-model-actions / .settings-input-row / 清空密钥; resources/ui/workspace/workspace.js:32`|[refactor](../components/BP-004.md)|FND-003|已判定，范围见检查问题|
|CMP-137|获取模型 · `.settings-model-actions / .settings-input-row / 获取模型; resources/ui/workspace/workspace.js:32`|[refactor](../components/BP-004.md)|FND-003|已判定，范围见检查问题|
|CMP-138|测试连接 · `.settings-model-actions / .settings-input-row / 测试连接; resources/ui/workspace/workspace.js:32`|[refactor](../components/BP-004.md)|FND-003|已判定，范围见检查问题|
|CMP-139|确认 · `.settings-model-actions / .settings-input-row / 确认; resources/ui/workspace/workspace.js:32`|[refactor](../components/BP-004.md)|FND-003|已判定，范围见检查问题|
|CMP-140|模型确认依据 · `.settings-status; resources/ui/workspace/settings.js:22`|[refactor](../components/BP-037.md)|FND-003|已判定，范围见检查问题|
|CMP-141|生成 timeout（秒） · `#settings-field-generation_timeout; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-142|连接 / 模型列表 timeout（秒） · `#settings-field-connection_timeout; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-143|max_tokens（0 = 自动） · `#settings-field-max_tokens; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-144|temperature（auto / 留空 / 数值） · `#settings-field-temperature; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-145|top_p（留空 = 不发送） · `#settings-field-top_p; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-146|思考强度 · `#settings-field-reasoning_effort; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|

本页SCN：SCN-030；EV：EV-005,EV-006,EV-007。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：FND-003、FND-010。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
