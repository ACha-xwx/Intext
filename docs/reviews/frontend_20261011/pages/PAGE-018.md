# PAGE-018 · Web设置 · Skill 搜索

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`settings / Skill 搜索`。源码：`resources/ui/workspace/settings.js:1-116`。

名称粗筛/正文上限/AI预算/URL/缓存均有设置；不是保证所有安装Skill语义匹配。

变体：未改/草稿/保存、忙/失败/恢复默认、隐藏再返回。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-147|分类Tab和标题 · `.settings-tabs / h1; resources/ui/workspace/settings.js:54`|[refactor](../components/BP-036.md)|FND-003, FND-010|已判定，范围见检查问题|
|CMP-148|返回工作区 · `.settings-heading / .settings-footer / 返回工作区; resources/ui/workspace/workspace.js:32`|[refactor](../components/BP-004.md)|FND-003|已判定，范围见检查问题|
|CMP-149|恢复本类默认 · `.settings-heading / .settings-footer / 恢复本类默认; resources/ui/workspace/workspace.js:32`|[refactor](../components/BP-004.md)|FND-003|已判定，范围见检查问题|
|CMP-150|保存设置 · `.settings-heading / .settings-footer / 保存设置; resources/ui/workspace/workspace.js:32`|[refactor](../components/BP-004.md)|FND-003|已判定，范围见检查问题|
|CMP-151|草稿/保存/请求/错误状态 · `.settings-status; resources/ui/workspace/settings.js:15`|[refactor](../components/BP-037.md)|FND-003|已判定，范围见检查问题|
|CMP-152|筛选模型 timeout（秒） · `#settings-field-search_model_timeout; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-153|每个联网来源 timeout（秒） · `#settings-field-search_timeout; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-154|本地正文粗查上限 · `#settings-field-local_candidates; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-155|名称 / 描述初筛上限 · `#settings-field-shortlist_limit; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-156|AI 内容核验上限 · `#settings-field-review_limit; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-157|默认展示推荐数量 · `#settings-field-display_limit; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-158|每个联网来源收集上限 · `#settings-field-network_candidates; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-159|联网来源缓存秒数（0 = 不复用） · `#settings-field-network_cache_seconds; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-160|AI 筛选累计输入字符上限 · `#settings-field-input_budget; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-161|每项 Skill 正文节选字符上限 · `#settings-field-excerpt_chars; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-162|额外本地 Skill 目录（每行一个） · `#settings-field-extra_skill_roots; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-163|Skill 索引地址 · `#settings-field-skill_search_url; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|
|CMP-164|网页检索地址（含 {query}） · `#settings-field-web_search_url; resources/ui/workspace/settings.js:37`|[refactor](../components/BP-038.md)|FND-003|已判定，范围见检查问题|

本页SCN：SCN-031；EV：EV-005,EV-006,EV-007。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：FND-003、FND-010。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
