# PAGE-034 · Windows文件对话框

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`native dialog / Windows文件对话框`。源码：`src/promptsmith/web_workspace.py:112; src/promptsmith/ui.py:4990`。

平台提供打开/保存/目录/覆盖UI，界面操作没有用文件API模拟当真机证据。磁盘历史、DPAPI、取消保护已由其它检查覆盖。

变体：鼠标/键盘、保存/取消/错误、长内容/小屏。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-457|打开会话 · `native / 打开会话; src/promptsmith/web_workspace.py:112; src/promptsmith/ui.py:4990`|[investigate](../components/BP-061.md)|无确定发现|behavior, layout_content, performance_lifecycle, semantics_accessibility, states|
|CMP-458|保存/另存会话 · `native / 保存/另存会话; src/promptsmith/web_workspace.py:112; src/promptsmith/ui.py:4990`|[refactor](../components/BP-061.md)|FND-012|layout_content, performance_lifecycle, semantics_accessibility|
|CMP-459|导出Markdown · `native / 导出Markdown; src/promptsmith/web_workspace.py:112; src/promptsmith/ui.py:4990`|[investigate](../components/BP-061.md)|无确定发现|behavior, layout_content, performance_lifecycle, semantics_accessibility, states|
|CMP-460|设置目录选择 · `native / 设置目录选择; src/promptsmith/web_workspace.py:112; src/promptsmith/ui.py:4990`|[investigate](../components/BP-061.md)|无确定发现|behavior, layout_content, performance_lifecycle, semantics_accessibility, states|
|CMP-461|覆盖/取消/无权限错误 · `native / 覆盖/取消/无权限错误; src/promptsmith/web_workspace.py:112; src/promptsmith/ui.py:4990`|[refactor](../components/BP-061.md)|FND-012|layout_content, performance_lifecycle, semantics_accessibility|

本页SCN：SCN-047；EV：。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：FND-012。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
