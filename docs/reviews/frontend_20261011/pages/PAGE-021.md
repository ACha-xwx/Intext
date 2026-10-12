# PAGE-021 · Web设置 · 诊断

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`settings / 诊断`。源码：`resources/ui/workspace/settings.js:1-116`。

Debug默认level/autoscroll/history/lines/开关；开启即新窗，保存日志仍是单独用户动作。

变体：未改/草稿/保存、忙/失败/恢复默认、隐藏再返回。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-184|分类Tab和标题 · `.settings-tabs / h1; resources/ui/workspace/settings.js:54`|[refactor](../components/BP-036.md)|FND-003, FND-010|已判定，范围见检查问题|
|CMP-185|返回工作区 · `.settings-heading / .settings-footer / 返回工作区; resources/ui/workspace/workspace.js:32`|[refactor](../components/BP-004.md)|FND-003|已判定，范围见检查问题|
|CMP-186|恢复本类默认 · `.settings-heading / .settings-footer / 恢复本类默认; resources/ui/workspace/workspace.js:32`|[refactor](../components/BP-004.md)|FND-003|已判定，范围见检查问题|
|CMP-187|保存设置 · `.settings-heading / .settings-footer / 保存设置; resources/ui/workspace/workspace.js:32`|[refactor](../components/BP-004.md)|FND-003|已判定，范围见检查问题|
|CMP-188|草稿/保存/请求/错误状态 · `.settings-status; resources/ui/workspace/settings.js:15`|[refactor](../components/BP-037.md)|FND-003|已判定，范围见检查问题|
|CMP-189|控制台默认显示级别 · `#settings-field-debug_level; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-190|控制台自动滚动 · `#settings-field-debug_autoscroll; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-191|控制台缓存条数 · `#settings-field-debug_history; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-192|控制台显示行数上限 · `#settings-field-debug_lines; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-193|开启 Debug 控制台 · `#settings-field-debug_console_enabled; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-194|日志目录与手动保存说明 · `.settings-diagnostics-note; resources/ui/workspace/settings.js:90`|[refactor](../components/BP-017.md)|FND-003|已判定，范围见检查问题|

本页SCN：SCN-034；EV：EV-005,EV-006,EV-007。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：FND-003、FND-010。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
