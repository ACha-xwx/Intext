# PAGE-030 · Tk关键工作编辑

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`native dialog / Tk关键工作编辑`。源码：`src/promptsmith/ui.py:2578`。

真实关键工作保存/取消和依赖数组形状已验；业务确认独立。

变体：鼠标/键盘、保存/取消/错误、长内容/小屏。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-427|title · `native / title; src/promptsmith/ui.py:2578`|[investigate](../components/BP-057.md)|无确定发现|semantics_accessibility|
|CMP-428|goal · `native / goal; src/promptsmith/ui.py:2578`|[investigate](../components/BP-057.md)|无确定发现|semantics_accessibility|
|CMP-429|inputs · `native / inputs; src/promptsmith/ui.py:2578`|[investigate](../components/BP-057.md)|无确定发现|semantics_accessibility|
|CMP-430|outputs · `native / outputs; src/promptsmith/ui.py:2578`|[investigate](../components/BP-057.md)|无确定发现|semantics_accessibility|
|CMP-431|checkpoints · `native / checkpoints; src/promptsmith/ui.py:2578`|[investigate](../components/BP-057.md)|无确定发现|semantics_accessibility|
|CMP-432|关联步骤 · `native / 关联步骤; src/promptsmith/ui.py:2578`|[investigate](../components/BP-057.md)|无确定发现|semantics_accessibility|
|CMP-433|关联需求 · `native / 关联需求; src/promptsmith/ui.py:2578`|[investigate](../components/BP-057.md)|无确定发现|semantics_accessibility|
|CMP-434|取消 · `native / 取消; src/promptsmith/ui.py:2578`|[investigate](../components/BP-057.md)|无确定发现|semantics_accessibility|
|CMP-435|保存草稿 · `native / 保存草稿; src/promptsmith/ui.py:2578`|[investigate](../components/BP-057.md)|无确定发现|semantics_accessibility|
|CMP-436|校验错误 · `native / 校验错误; src/promptsmith/ui.py:2578`|[investigate](../components/BP-057.md)|无确定发现|semantics_accessibility|

本页SCN：SCN-043；EV：EV-010。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：当前没有确定缺陷；不代表未执行环境通过。。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
