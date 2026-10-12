# PAGE-033 · Tk菜单/审查浮层/模型菜单

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`native dialog / Tk菜单/审查浮层/模型菜单`。源码：`src/promptsmith/interaction_ui.py:1; src/promptsmith/composer.py:1`。

兼容模型/菜单/核对自绘弹层已有焦点键盘与动画测试；Canvas的真实读屏表现、跨DPI待补证。

变体：鼠标/键盘、保存/取消/错误、长内容/小屏。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-448|文件菜单（新建/打开/保存/另存/退出） · `native / 文件菜单（新建/打开/保存/另存/退出）; src/promptsmith/interaction_ui.py:1; src/promptsmith/composer.py:1`|[investigate](../components/BP-060.md)|无确定发现|semantics_accessibility|
|CMP-449|需求核对表与操作 · `native / 需求核对表与操作; src/promptsmith/interaction_ui.py:1; src/promptsmith/composer.py:1`|[investigate](../components/BP-060.md)|无确定发现|semantics_accessibility|
|CMP-450|方案核对章节与操作 · `native / 方案核对章节与操作; src/promptsmith/interaction_ui.py:1; src/promptsmith/composer.py:1`|[investigate](../components/BP-060.md)|无确定发现|semantics_accessibility|
|CMP-451|任务摘要 · `native / 任务摘要; src/promptsmith/interaction_ui.py:1; src/promptsmith/composer.py:1`|[investigate](../components/BP-060.md)|无确定发现|semantics_accessibility|
|CMP-452|语气和附注 · `native / 语气和附注; src/promptsmith/interaction_ui.py:1; src/promptsmith/composer.py:1`|[investigate](../components/BP-060.md)|无确定发现|semantics_accessibility|
|CMP-453|模型搜索/清空/目录 · `native / 模型搜索/清空/目录; src/promptsmith/interaction_ui.py:1; src/promptsmith/composer.py:1`|[investigate](../components/BP-060.md)|无确定发现|semantics_accessibility|
|CMP-454|五供应商选择 · `native / 五供应商选择; src/promptsmith/interaction_ui.py:1; src/promptsmith/composer.py:1`|[investigate](../components/BP-060.md)|无确定发现|semantics_accessibility|
|CMP-455|四档思考选择 · `native / 四档思考选择; src/promptsmith/interaction_ui.py:1; src/promptsmith/composer.py:1`|[investigate](../components/BP-060.md)|无确定发现|semantics_accessibility|
|CMP-456|任务类型与整理深度菜单 · `native / 任务类型与整理深度菜单; src/promptsmith/interaction_ui.py:1; src/promptsmith/composer.py:1`|[investigate](../components/BP-060.md)|无确定发现|semantics_accessibility|
|CMP-492|Canvas键盘焦点与激活 · `GlyphButton focus/Return/space; src/promptsmith/composer.py:94-176`|[investigate](../components/BP-068.md)|无确定发现|semantics_accessibility|

本页SCN：SCN-046；EV：EV-012,EV-020。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：当前没有确定缺陷；不代表未执行环境通过。。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
