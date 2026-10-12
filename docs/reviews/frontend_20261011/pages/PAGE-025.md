# PAGE-025 · Tk Skill详情

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`native notebook:2`。源码：`src/promptsmith/guided_flow.py:177-187`。

原生Skill表和当前绑定/前提详情；只有明确展开才出现兼容信息，不强制它成为最终交付阻断。

变体：浅/深、空/有/失效、滚动/小窗、业务条件可见。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-260|页面壳与滚动区 · `notebook[2]; src/promptsmith/guided_flow.py:177`|[investigate](../components/BP-044.md)|无确定发现|semantics_accessibility|
|CMP-261|skills_page_canvas · `.!frame.!notebook.!frame3.!canvas; src/promptsmith/ui.py:839`|[investigate](../components/BP-046.md)|无确定发现|semantics_accessibility|
|CMP-262|Agent Skill 参考 · `.!frame.!notebook.!frame3.!canvas.!frame.!label; src/promptsmith/ui.py:839`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-263|确认初始方案后，可查找本地或联网 Agent Skill，也可直接跳过。 · `.!frame.!notebook.!frame3.!canvas.!frame.!label2; src/promptsmith/ui.py:839`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-264|skill_find_button · `.!frame.!notebook.!frame3.!canvas.!frame.!frame.!button; src/promptsmith/ui.py:839`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-265|skill_online_button · `.!frame.!notebook.!frame3.!canvas.!frame.!frame.!button2; src/promptsmith/ui.py:839`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-266|skill_search_url_label · `.!frame.!notebook.!frame3.!canvas.!frame.!frame.!label; src/promptsmith/ui.py:839`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-267|skill_search_url_entry · `.!frame.!notebook.!frame3.!canvas.!frame.!frame.!entry; src/promptsmith/ui.py:839`|[investigate](../components/BP-053.md)|无确定发现|behavior, semantics_accessibility|
|CMP-268|skill_select_button · `.!frame.!notebook.!frame3.!canvas.!frame.!frame.!button3; src/promptsmith/ui.py:839`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-269|skill_analyze_button · `.!frame.!notebook.!frame3.!canvas.!frame.!frame.!button4; src/promptsmith/ui.py:839`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-270|skill_cancel_button · `.!frame.!notebook.!frame3.!canvas.!frame.!frame.!button5; src/promptsmith/ui.py:839`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-271|skill_cancel_request_button · `.!frame.!notebook.!frame3.!canvas.!frame.!frame.!button6; src/promptsmith/ui.py:839`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-272|skill_skip_button · `.!frame.!notebook.!frame3.!canvas.!frame.!frame.!button7; src/promptsmith/ui.py:839`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-273|skill_integrate_button · `.!frame.!notebook.!frame3.!canvas.!frame.!frame.!button8; src/promptsmith/ui.py:839`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-274|目录状态：尚未开始 · `.!frame.!notebook.!frame3.!canvas.!frame.!frame2.!label; src/promptsmith/ui.py:839`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-275|skill_direct_button · `.!frame.!notebook.!frame3.!canvas.!frame.!frame2.!button; src/promptsmith/ui.py:839`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-276|来源 · `.!frame.!notebook.!frame3.!canvas.!frame.!frame3.!frame.!label; src/promptsmith/ui.py:839`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-277|skill_source_filter · `.!frame.!notebook.!frame3.!canvas.!frame.!frame3.!frame.!combobox; src/promptsmith/ui.py:839`|[investigate](../components/BP-048.md)|无确定发现|semantics_accessibility|
|CMP-278|skill_show_all · `.!frame.!notebook.!frame3.!canvas.!frame.!frame3.!frame.!checkbutton; src/promptsmith/ui.py:839`|[investigate](../components/BP-049.md)|无确定发现|semantics_accessibility|
|CMP-279|skill_candidate_count · `.!frame.!notebook.!frame3.!canvas.!frame.!frame3.!label; src/promptsmith/ui.py:839`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-280|skill_candidates_tree · `.!frame.!notebook.!frame3.!canvas.!frame.!frame3.!frame2.!treeview; src/promptsmith/ui.py:839`|[investigate](../components/BP-050.md)|无确定发现|semantics_accessibility|
|CMP-281|已选 Skill · `.!frame.!notebook.!frame3.!canvas.!frame.!frame4.!label; src/promptsmith/ui.py:839`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-282|skill_selected_tree · `.!frame.!notebook.!frame3.!canvas.!frame.!frame4.!frame.!treeview; src/promptsmith/ui.py:839`|[investigate](../components/BP-050.md)|无确定发现|semantics_accessibility|
|CMP-283|skill_details_text · `.!frame.!notebook.!frame3.!canvas.!frame.!text; src/promptsmith/ui.py:839`|[investigate](../components/BP-052.md)|无确定发现|behavior, semantics_accessibility|
|CMP-284|skill_prerequisites_tree · `.!frame.!notebook.!frame3.!canvas.!frame.!labelframe.!frame.!treeview; src/promptsmith/ui.py:839`|[investigate](../components/BP-050.md)|无确定发现|semantics_accessibility|
|CMP-285|核对结果 · `.!frame.!notebook.!frame3.!canvas.!frame.!labelframe.!frame2.!label; src/promptsmith/ui.py:839`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-286|skill_prerequisite_status_combo · `.!frame.!notebook.!frame3.!canvas.!frame.!labelframe.!frame2.!combobox; src/promptsmith/ui.py:839`|[investigate](../components/BP-048.md)|无确定发现|semantics_accessibility|
|CMP-287|skill_update_prerequisite_button · `.!frame.!notebook.!frame3.!canvas.!frame.!labelframe.!frame2.!button; src/promptsmith/ui.py:839`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|

本页SCN：SCN-038；EV：EV-010,EV-012,EV-018,EV-020。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：当前没有确定缺陷；不代表未执行环境通过。。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
