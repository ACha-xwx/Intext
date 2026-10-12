# PAGE-001 · 主工作区与历史侧栏

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`workspace`。源码：`resources/ui/workspace/index.html:5-22`。

默认主入口；历史元数据启动读取，正文点击才加载。720×440与字号18的展开侧栏存在header越界。

变体：Hero、历史空/有/失败、展开/收起、忙/恢复、浅/深/小窗。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-001|外壳与页内滚动 · `#workspace-shell / #viewport; resources/ui/workspace/index.html:5`|[refactor](../components/BP-001.md)|FND-002|已判定，范围见检查问题|
|CMP-002|Hero目标说明 · `#hero; resources/ui/workspace/index.html:13`|[retain](../components/BP-002.md)|无确定发现|已判定，范围见检查问题|
|CMP-003|品牌与历史日期组 · `#sidebar .sidebar-brand / .history-group h2; resources/ui/workspace/history.js:42`|[retain](../components/BP-003.md)|无确定发现|已判定，范围见检查问题|
|CMP-004|新建对话 · `header / sidebar / 新建对话; resources/ui/workspace/workspace.js:32`|[retain](../components/BP-004.md)|无确定发现|已判定，范围见检查问题|
|CMP-005|搜索历史 · `header / sidebar / 搜索历史; resources/ui/workspace/workspace.js:32`|[retain](../components/BP-004.md)|无确定发现|已判定，范围见检查问题|
|CMP-006|收起/展开 · `header / sidebar / 收起/展开; resources/ui/workspace/workspace.js:32`|[retain](../components/BP-004.md)|无确定发现|已判定，范围见检查问题|
|CMP-007|文件 · `header / sidebar / 文件; resources/ui/workspace/workspace.js:32`|[retain](../components/BP-004.md)|无确定发现|已判定，范围见检查问题|
|CMP-008|核对需求 · `header / sidebar / 核对需求; resources/ui/workspace/workspace.js:32`|[refactor](../components/BP-004.md)|FND-002, FND-006|已判定，范围见检查问题|
|CMP-009|核对方案 · `header / sidebar / 核对方案; resources/ui/workspace/workspace.js:32`|[refactor](../components/BP-004.md)|FND-002, FND-006|已判定，范围见检查问题|
|CMP-010|任务摘要 · `header / sidebar / 任务摘要; resources/ui/workspace/workspace.js:32`|[refactor](../components/BP-004.md)|FND-002, FND-006|已判定，范围见检查问题|
|CMP-011|设置 · `header / sidebar / 设置; resources/ui/workspace/workspace.js:32`|[refactor](../components/BP-004.md)|FND-002|已判定，范围见检查问题|
|CMP-012|历史记录选择模板 · `.history-select; resources/ui/workspace/history.js:26`|[retain](../components/BP-005.md)|无确定发现|已判定，范围见检查问题|
|CMP-013|历史悬停菜单入口 · `.history-more; resources/ui/workspace/history.js:32`|[retain](../components/BP-006.md)|无确定发现|已判定，范围见检查问题|
|CMP-014|历史失败与重试 · `#history-status; resources/ui/workspace/history.js:51`|[retain](../components/BP-007.md)|无确定发现|已判定，范围见检查问题|
|CMP-015|Toast操作反馈 · `#toast; resources/ui/workspace/workspace.js:65`|[retain](../components/BP-008.md)|无确定发现|已判定，范围见检查问题|
|CMP-016|下一步恢复动作 · `#recovery [data-action=primary]; resources/ui/workspace/workspace.js:33`|[retain](../components/BP-009.md)|无确定发现|已判定，范围见检查问题|
|CMP-017|消息输入 · `#message; resources/ui/workspace/workspace.js:79`|[investigate](../components/BP-010.md)|无确定发现|behavior|
|CMP-018|选择模型 · `#composer .toolbar / 选择模型; resources/ui/workspace/workspace.js:32`|[retain](../components/BP-004.md)|无确定发现|已判定，范围见检查问题|
|CMP-019|整理深度 · `#composer .toolbar / 整理深度; resources/ui/workspace/workspace.js:32`|[retain](../components/BP-004.md)|无确定发现|已判定，范围见检查问题|
|CMP-020|任务类型 · `#composer .toolbar / 任务类型; resources/ui/workspace/workspace.js:32`|[retain](../components/BP-004.md)|无确定发现|已判定，范围见检查问题|
|CMP-021|发送消息 · `#composer .toolbar / 发送消息; resources/ui/workspace/workspace.js:32`|[retain](../components/BP-004.md)|无确定发现|已判定，范围见检查问题|

本页SCN：SCN-014；EV：EV-005,EV-006,EV-007。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：FND-002、FND-006。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
