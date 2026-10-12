# PAGE-003 · Skill选择

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`workspace / skills`。源码：`resources/ui/workspace/workspace.js:196-208`。

本地与联网累计展示、已选禁用/可取消已验。受控候选不证明真实网络403修复或真实推荐质量。

变体：无结果/多来源、选中/取消、来源过滤、推荐/全部、搜索/整合失败。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-036|Skill阶段说明 · `.message p.notice; resources/ui/workspace/workspace.js:197`|[retain](../components/BP-017.md)|无确定发现|已判定，范围见检查问题|
|CMP-037|find_skills · `[data-action=find_skills]; resources/ui/workspace/workspace.js:33`|[retain](../components/BP-009.md)|无确定发现|已判定，范围见检查问题|
|CMP-038|find_online · `[data-action=find_online]; resources/ui/workspace/workspace.js:33`|[retain](../components/BP-009.md)|无确定发现|已判定，范围见检查问题|
|CMP-039|integrate · `[data-action=integrate]; resources/ui/workspace/workspace.js:33`|[retain](../components/BP-009.md)|无确定发现|已判定，范围见检查问题|
|CMP-040|direct_skills · `[data-action=direct_skills]; resources/ui/workspace/workspace.js:33`|[retain](../components/BP-009.md)|无确定发现|已判定，范围见检查问题|
|CMP-041|skip_skills · `[data-action=skip_skills]; resources/ui/workspace/workspace.js:33`|[retain](../components/BP-009.md)|无确定发现|已判定，范围见检查问题|
|CMP-042|来源 全部来源 · `.actions / 全部来源; resources/ui/workspace/workspace.js:199`|[retain](../components/BP-018.md)|无确定发现|已判定，范围见检查问题|
|CMP-043|来源 本地 · `.actions / 本地; resources/ui/workspace/workspace.js:199`|[retain](../components/BP-018.md)|无确定发现|已判定，范围见检查问题|
|CMP-044|来源 联网 · `.actions / 联网; resources/ui/workspace/workspace.js:199`|[retain](../components/BP-018.md)|无确定发现|已判定，范围见检查问题|
|CMP-045|来源 内置 · `.actions / 内置; resources/ui/workspace/workspace.js:199`|[retain](../components/BP-018.md)|无确定发现|已判定，范围见检查问题|
|CMP-046|来源 已选 · `.actions / 已选; resources/ui/workspace/workspace.js:199`|[retain](../components/BP-018.md)|无确定发现|已判定，范围见检查问题|
|CMP-047|推荐/全部切换 · `显示全部/只显示推荐; resources/ui/workspace/workspace.js:200`|[retain](../components/BP-018.md)|无确定发现|已判定，范围见检查问题|
|CMP-048|Skill名称/来源/推荐列 · `.table-wrap table; resources/ui/workspace/workspace.js:201`|[retain](../components/BP-019.md)|无确定发现|已判定，范围见检查问题|
|CMP-049|选用此Skill/已选中 · `.table-wrap tbody / 选用此Skill/已选中; resources/ui/workspace/workspace.js:203`|[retain](../components/BP-020.md)|无确定发现|已判定，范围见检查问题|
|CMP-050|取消选用 · `.table-wrap tbody / 取消选用; resources/ui/workspace/workspace.js:203`|[retain](../components/BP-020.md)|无确定发现|已判定，范围见检查问题|
|CMP-051|用途摘要与详细说明 · `.table-wrap tbody / 用途摘要与详细说明; resources/ui/workspace/workspace.js:203`|[retain](../components/BP-020.md)|无确定发现|已判定，范围见检查问题|

本页SCN：SCN-016；EV：EV-005,EV-006,EV-007。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：当前没有确定缺陷；不代表未执行环境通过。。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
