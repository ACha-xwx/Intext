# PAGE-026 · Tk结果高级选项

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`native notebook:3`。源码：`src/promptsmith/guided_flow.py:177-187`。

结果高级选项原生回退页；隐藏旧buffer/旧控制有引用所以不删。取消问题不重新写最终提示。

变体：浅/深、空/有/失效、滚动/小窗、业务条件可见。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-288|页面壳与滚动区 · `notebook[3]; src/promptsmith/guided_flow.py:177`|[investigate](../components/BP-044.md)|无确定发现|semantics_accessibility|
|CMP-289|export_page_canvas · `.!frame.!notebook.!frame4.!canvas; src/promptsmith/ui.py:935`|[investigate](../components/BP-046.md)|无确定发现|semantics_accessibility|
|CMP-290|最终方案与任务提示 · `.!frame.!notebook.!frame4.!canvas.!frame.!label; src/promptsmith/ui.py:935`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-291|最终结果：草稿待确认 · 版本 1 · `.!frame.!notebook.!frame4.!canvas.!frame.!label2; src/promptsmith/ui.py:935`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-292|生成无 Skill 草稿 · `.!frame.!notebook.!frame4.!canvas.!frame.!frame.!button; src/promptsmith/ui.py:935`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-293|确认当前最终结果 · `.!frame.!notebook.!frame4.!canvas.!frame.!frame.!button2; src/promptsmith/ui.py:935`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-294|语气 · `.!frame.!notebook.!frame4.!canvas.!frame.!frame.!label; src/promptsmith/ui.py:935`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-295|final_tone_combo · `.!frame.!notebook.!frame4.!canvas.!frame.!frame.!combobox; src/promptsmith/ui.py:935`|[investigate](../components/BP-048.md)|无确定发现|semantics_accessibility|
|CMP-296|copy_draft_button · `.!frame.!notebook.!frame4.!canvas.!frame.!frame.!button3; src/promptsmith/ui.py:935`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-297|copy_final_button · `.!frame.!notebook.!frame4.!canvas.!frame.!frame.!button4; src/promptsmith/ui.py:935`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-298|导出 Markdown · `.!frame.!notebook.!frame4.!canvas.!frame.!frame.!button5; src/promptsmith/ui.py:935`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-299|导出草稿 · `.!frame.!notebook.!frame4.!canvas.!frame.!frame.!button6; src/promptsmith/ui.py:935`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-300|final_preview_text · `.!frame.!notebook.!frame4.!canvas.!frame.!text; src/promptsmith/ui.py:935`|[investigate](../components/BP-052.md)|无确定发现|behavior, semantics_accessibility|
|CMP-301|最终任务提示预览 · `.!frame.!notebook.!frame4.!canvas.!frame.!label3; src/promptsmith/ui.py:935`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-302|final_task_prompt_text · `.!frame.!notebook.!frame4.!canvas.!frame.!text2; src/promptsmith/ui.py:935`|[investigate](../components/BP-052.md)|无确定发现|behavior, semantics_accessibility|
|CMP-303|m2_suggestions_tree · `.!frame.!notebook.!frame4.!canvas.!frame.!labelframe.!frame.!treeview; src/promptsmith/ui.py:935`|[investigate](../components/BP-050.md)|无确定发现|semantics_accessibility|
|CMP-304|m2_suggestion_details_text · `.!frame.!notebook.!frame4.!canvas.!frame.!labelframe.!text; src/promptsmith/ui.py:935`|[investigate](../components/BP-052.md)|无确定发现|behavior, semantics_accessibility|
|CMP-305|accept_m2_suggestion_button · `.!frame.!notebook.!frame4.!canvas.!frame.!labelframe.!frame2.!button; src/promptsmith/ui.py:935`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-306|reject_m2_suggestion_button · `.!frame.!notebook.!frame4.!canvas.!frame.!labelframe.!frame2.!button2; src/promptsmith/ui.py:935`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-307|process_m2_suggestion_button · `.!frame.!notebook.!frame4.!canvas.!frame.!labelframe.!frame2.!button3; src/promptsmith/ui.py:935`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-308|m4_changes_tree · `.!frame.!notebook.!frame4.!canvas.!frame.!labelframe2.!frame.!treeview; src/promptsmith/ui.py:935`|[investigate](../components/BP-050.md)|无确定发现|semantics_accessibility|
|CMP-309|m4_change_details_text · `.!frame.!notebook.!frame4.!canvas.!frame.!labelframe2.!text; src/promptsmith/ui.py:935`|[investigate](../components/BP-052.md)|无确定发现|behavior, semantics_accessibility|
|CMP-310|accept_m4_change_button · `.!frame.!notebook.!frame4.!canvas.!frame.!labelframe2.!frame2.!button; src/promptsmith/ui.py:935`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-311|reject_m4_change_button · `.!frame.!notebook.!frame4.!canvas.!frame.!labelframe2.!frame2.!button2; src/promptsmith/ui.py:935`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-312|final_review_items_tree · `.!frame.!notebook.!frame4.!canvas.!frame.!labelframe3.!frame.!treeview; src/promptsmith/ui.py:935`|[investigate](../components/BP-050.md)|无确定发现|semantics_accessibility|
|CMP-313|final_review_details_text · `.!frame.!notebook.!frame4.!canvas.!frame.!labelframe3.!text; src/promptsmith/ui.py:935`|[investigate](../components/BP-052.md)|无确定发现|behavior, semantics_accessibility|
|CMP-314|process_final_review_item_button · `.!frame.!notebook.!frame4.!canvas.!frame.!labelframe3.!button; src/promptsmith/ui.py:935`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-315|添加用户附注 · `.!frame.!notebook.!frame4.!canvas.!frame.!frame2.!button; src/promptsmith/ui.py:935`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-316|正文由结构化方案统一渲染；原需求和步骤变化请返回上游修改。 · `.!frame.!notebook.!frame4.!canvas.!frame.!frame2.!label; src/promptsmith/ui.py:935`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-317|复制提示 · `.!frame.!notebook.!frame4.!canvas.!frame.!frame3.!button; src/promptsmith/ui.py:935`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-318|导出方案和提示 · `.!frame.!notebook.!frame4.!canvas.!frame.!frame3.!button2; src/promptsmith/ui.py:935`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-319|保存会话 · `.!frame.!notebook.!frame4.!canvas.!frame.!frame3.!button3; src/promptsmith/ui.py:935`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-320|修改方案 · `.!frame.!notebook.!frame4.!canvas.!frame.!frame3.!button4; src/promptsmith/ui.py:935`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-321|result_optional_button · `.!frame.!notebook.!frame4.!canvas.!frame.!button; src/promptsmith/ui.py:935`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|

本页SCN：SCN-039；EV：EV-010,EV-007,EV-017,EV-020。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：当前没有确定缺陷；不代表未执行环境通过。。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
