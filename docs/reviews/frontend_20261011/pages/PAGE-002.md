# PAGE-002 · 访谈与模型处理

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`workspace / interview`。源码：`resources/ui/workspace/workspace.js:127-211`。

逐题回答采用实际投影；五轮是上限，充分可提前结束。DOM验证IME只为注入事件；真实Windows候选需另验。整合忙态cancel_request遗漏。

变体：首轮、逐题回答、已回答/跳过、补答、达到五轮/可继续、流式/失败/取消。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-022|用户目标与回答气泡 · `.user .bubble; resources/ui/workspace/workspace.js:180`|[retain](../components/BP-011.md)|无确定发现|已判定，范围见检查问题|
|CMP-023|补答按钮 · `.reanswer; resources/ui/workspace/workspace.js:181`|[retain](../components/BP-012.md)|无确定发现|已判定，范围见检查问题|
|CMP-024|AI问题全文 · `.question-title; resources/ui/workspace/workspace.js:185`|[retain](../components/BP-013.md)|无确定发现|已判定，范围见检查问题|
|CMP-025|逐题回答框 · `.answer-input; resources/ui/workspace/workspace.js:79`|[investigate](../components/BP-010.md)|无确定发现|behavior|
|CMP-026|提交回答 · `.answer-row .send; resources/ui/workspace/workspace.js:32`|[retain](../components/BP-004.md)|无确定发现|已判定，范围见检查问题|
|CMP-027|跳过该题 · `.skip; resources/ui/workspace/workspace.js:32`|[retain](../components/BP-004.md)|无确定发现|已判定，范围见检查问题|
|CMP-028|历史问题文本 · `.history_question; resources/ui/workspace/workspace.js:185`|[retain](../components/BP-013.md)|无确定发现|已判定，范围见检查问题|
|CMP-029|取消补答 · `#reanswer-context button; resources/ui/workspace/workspace.js:32`|[retain](../components/BP-004.md)|无确定发现|已判定，范围见检查问题|
|CMP-030|继续询问/结束追问 · `.interview_unknowns .actions; resources/ui/workspace/workspace.js:33`|[retain](../components/BP-009.md)|无确定发现|已判定，范围见检查问题|
|CMP-031|处理状态与点阵 · `.trace > button; resources/ui/workspace/workspace.js:127`|[refactor](../components/BP-014.md)|FND-008|已判定，范围见检查问题|
|CMP-032|思考子展开器 · `.trace-body > button; resources/ui/workspace/workspace.js:127`|[refactor](../components/BP-014.md)|FND-008|已判定，范围见检查问题|
|CMP-033|思考内容与独立滚动 · `.thought; resources/ui/workspace/workspace.js:161`|[refactor](../components/BP-015.md)|FND-008|已判定，范围见检查问题|
|CMP-034|检索活动记录 · `.activities; resources/ui/workspace/workspace.js:156`|[retain](../components/BP-016.md)|无确定发现|已判定，范围见检查问题|
|CMP-035|模型失败文字 · `.trace-error; resources/ui/workspace/workspace.js:159`|[retain](../components/BP-008.md)|无确定发现|已判定，范围见检查问题|
|CMP-462|整合忙态取消入口（当前Web遗漏） · `state.buttons.cancel_request / 缺少DOM渲染; resources/ui/workspace/workspace.js:33`|[refactor](../components/BP-009.md)|FND-001|已判定，范围见检查问题|

本页SCN：SCN-015；EV：EV-005,EV-006,EV-007。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：FND-001、FND-008。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
