# PAGE-031 · Tk简短输入（附注/目标/新增需求）

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`native dialog / Tk简短输入（附注/目标/新增需求）`。源码：`src/promptsmith/ui.py:4453`。

多个askstring调用归成相同系统对话等价类；具体业务消费者逐项源码检查，系统候选输入待验证。

变体：鼠标/键盘、保存/取消/错误、长内容/小屏。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-437|单行输入 · `native / 单行输入; src/promptsmith/ui.py:4453`|[investigate](../components/BP-058.md)|无确定发现|semantics_accessibility|
|CMP-438|确定 · `native / 确定; src/promptsmith/ui.py:4453`|[investigate](../components/BP-058.md)|无确定发现|semantics_accessibility|
|CMP-439|取消 · `native / 取消; src/promptsmith/ui.py:4453`|[investigate](../components/BP-058.md)|无确定发现|semantics_accessibility|

本页SCN：SCN-044；EV：EV-017。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：当前没有确定缺陷；不代表未执行环境通过。。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
