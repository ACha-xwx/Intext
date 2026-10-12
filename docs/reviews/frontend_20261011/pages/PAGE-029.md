# PAGE-029 · Tk步骤编辑

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`native dialog / Tk步骤编辑`。源码：`src/promptsmith/ui.py:2413`。

真实步骤编辑title/purpose必填失败留开，保存返回actions和真实关联；不是模型步骤已被自动认可。

变体：鼠标/键盘、保存/取消/错误、长内容/小屏。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-416|title · `native / title; src/promptsmith/ui.py:2413`|[investigate](../components/BP-056.md)|无确定发现|semantics_accessibility|
|CMP-417|purpose · `native / purpose; src/promptsmith/ui.py:2413`|[investigate](../components/BP-056.md)|无确定发现|semantics_accessibility|
|CMP-418|inputs · `native / inputs; src/promptsmith/ui.py:2413`|[investigate](../components/BP-056.md)|无确定发现|semantics_accessibility|
|CMP-419|actions · `native / actions; src/promptsmith/ui.py:2413`|[investigate](../components/BP-056.md)|无确定发现|semantics_accessibility|
|CMP-420|outputs · `native / outputs; src/promptsmith/ui.py:2413`|[investigate](../components/BP-056.md)|无确定发现|semantics_accessibility|
|CMP-421|completion_criteria · `native / completion_criteria; src/promptsmith/ui.py:2413`|[investigate](../components/BP-056.md)|无确定发现|semantics_accessibility|
|CMP-422|依赖步骤 · `native / 依赖步骤; src/promptsmith/ui.py:2413`|[investigate](../components/BP-056.md)|无确定发现|semantics_accessibility|
|CMP-423|关联需求 · `native / 关联需求; src/promptsmith/ui.py:2413`|[investigate](../components/BP-056.md)|无确定发现|semantics_accessibility|
|CMP-424|取消 · `native / 取消; src/promptsmith/ui.py:2413`|[investigate](../components/BP-056.md)|无确定发现|semantics_accessibility|
|CMP-425|保存草稿 · `native / 保存草稿; src/promptsmith/ui.py:2413`|[investigate](../components/BP-056.md)|无确定发现|semantics_accessibility|
|CMP-426|校验错误 · `native / 校验错误; src/promptsmith/ui.py:2413`|[investigate](../components/BP-056.md)|无确定发现|semantics_accessibility|

本页SCN：SCN-042；EV：EV-010。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：当前没有确定缺陷；不代表未执行环境通过。。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
