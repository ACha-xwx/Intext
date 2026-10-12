# PAGE-024 · Tk方案兼容编辑

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`native notebook:1`。源码：`src/promptsmith/guided_flow.py:177-187`。

Web“完整方案并编辑”仍可到达；兼容折叠编辑壳与步骤/关键工作窗口已检查。主内容是guided入口而非legacy入口。

变体：浅/深、空/有/失效、滚动/小窗、业务条件可见。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-229|页面壳与滚动区 · `notebook[1]; src/promptsmith/guided_flow.py:177`|[investigate](../components/BP-044.md)|无确定发现|semantics_accessibility|
|CMP-230|plan_page_canvas · `.!frame.!notebook.!frame2.!canvas; src/promptsmith/ui.py:733`|[investigate](../components/BP-046.md)|无确定发现|semantics_accessibility|
|CMP-231|核对方案 · `.!frame.!notebook.!frame2.!canvas.!frame.!label; src/promptsmith/ui.py:733`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-232|目标、要求、步骤和关键工作一起看；需要调整时展开下面的编辑区。 · `.!frame.!notebook.!frame2.!canvas.!frame.!label2; src/promptsmith/ui.py:733`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-233|plan_reading_text · `.!frame.!notebook.!frame2.!canvas.!frame.!frame.!text; src/promptsmith/ui.py:733`|[investigate](../components/BP-052.md)|无确定发现|behavior, semantics_accessibility|
|CMP-234|optional_skill_button · `.!frame.!notebook.!frame2.!canvas.!frame.!frame2.!button; src/promptsmith/ui.py:733`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-235|返回当前需求 · `.!frame.!notebook.!frame2.!canvas.!frame.!frame2.!button2; src/promptsmith/ui.py:733`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-236|完整初始方案 · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!frame.!label; src/promptsmith/ui.py:733`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-237|方案 已确认 · 版本 1 · 来源需求 v1 · 已确认 v1 · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!frame.!label2; src/promptsmith/ui.py:733`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-238|当前方案已经确认；如改变任务目标或硬约束，请使用“修改需求”。 · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!label; src/promptsmith/ui.py:733`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-239|目标 · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!panedwindow.!frame.!label; src/promptsmith/ui.py:733`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-240|plan_goal_text · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!panedwindow.!frame.!text; src/promptsmith/ui.py:733`|[investigate](../components/BP-052.md)|无确定发现|behavior, semantics_accessibility|
|CMP-241|保存目标修改 · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!panedwindow.!frame.!frame.!button; src/promptsmith/ui.py:733`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-242|编辑受众与范围 · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!panedwindow.!frame.!frame.!button2; src/promptsmith/ui.py:733`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-243|generate_plan_button · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!panedwindow.!frame.!frame.!button3; src/promptsmith/ui.py:733`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-244|plan_steps_tree · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!panedwindow.!frame.!frame2.!treeview; src/promptsmith/ui.py:733`|[investigate](../components/BP-050.md)|无确定发现|semantics_accessibility|
|CMP-245|编辑步骤 · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!panedwindow.!frame.!frame3.!button; src/promptsmith/ui.py:733`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-246|新增步骤 · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!panedwindow.!frame.!frame3.!button2; src/promptsmith/ui.py:733`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-247|删除步骤 · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!panedwindow.!frame.!frame3.!button3; src/promptsmith/ui.py:733`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-248|上移 · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!panedwindow.!frame.!frame3.!button4; src/promptsmith/ui.py:733`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-249|下移 · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!panedwindow.!frame.!frame3.!button5; src/promptsmith/ui.py:733`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-250|plan_section_combo · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!panedwindow.!frame2.!frame.!combobox; src/promptsmith/ui.py:733`|[investigate](../components/BP-048.md)|无确定发现|semantics_accessibility|
|CMP-251|编辑选中栏目 · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!panedwindow.!frame2.!frame.!button; src/promptsmith/ui.py:733`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-252|plan_overview_text · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!panedwindow.!frame2.!text; src/promptsmith/ui.py:733`|[investigate](../components/BP-052.md)|无确定发现|behavior, semantics_accessibility|
|CMP-253|关键工作 · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!panedwindow.!frame2.!label; src/promptsmith/ui.py:733`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-254|plan_key_work_tree · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!panedwindow.!frame2.!frame2.!treeview; src/promptsmith/ui.py:733`|[investigate](../components/BP-050.md)|无确定发现|semantics_accessibility|
|CMP-255|编辑关键工作 · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!panedwindow.!frame2.!frame3.!button; src/promptsmith/ui.py:733`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-256|review_key_work_button · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!panedwindow.!frame2.!frame3.!button2; src/promptsmith/ui.py:733`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-257|修改需求 · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!panedwindow.!frame2.!frame3.!button3; src/promptsmith/ui.py:733`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-258|confirm_plan_button · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!frame.!panedwindow.!frame2.!frame3.!button4; src/promptsmith/ui.py:733`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-259|▸ 编辑方案内容 · `.!frame.!notebook.!frame2.!canvas.!frame.!frame3.!button; src/promptsmith/ui.py:733`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|

本页SCN：SCN-037；EV：EV-010,EV-012,EV-017,EV-020。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：当前没有确定缺陷；不代表未执行环境通过。。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
