# PAGE-023 · Tk统一对话回退

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`native notebook:0`。源码：`src/promptsmith/guided_flow.py:177-187`。

显式Tk统一对话回退，包含底部自绘、Skill/结果动态ReplyButton；正常默认Web不以此页替代。

变体：浅/深、空/有/失效、滚动/小窗、业务条件可见。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-204|页面壳与滚动区 · `notebook[0]; src/promptsmith/guided_flow.py:177`|[investigate](../components/BP-044.md)|无确定发现|semantics_accessibility|
|CMP-205|为零基础学习者规划 7 天 Python 入门 · `.!frame.!notebook.!frame.!frame.!label; src/promptsmith/conversation.py:819`|[investigate](../components/BP-045.md)|无确定发现|semantics_accessibility|
|CMP-206|requirements_page_canvas · `.!frame.!notebook.!frame.!frame2.!canvas; src/promptsmith/conversation.py:819`|[investigate](../components/BP-046.md)|无确定发现|semantics_accessibility|
|CMP-207|为零基础学习者规划 7 天 Python 入门 · `.!frame.!notebook.!frame.!frame2.!canvas.!frame.!frame.!messageshell19.!frame.!canvas.!frame.!label; src/promptsmith/conversation.py:819`|[investigate](../components/BP-045.md)|无确定发现|semantics_accessibility|
|CMP-208|选配 Skill · `.!frame.!notebook.!frame.!frame2.!canvas.!frame.!frame.!messageshell20.!frame.!label; src/promptsmith/conversation.py:819`|[investigate](../components/BP-045.md)|无确定发现|semantics_accessibility|
|CMP-209|目录状态：尚未开始 · `.!frame.!notebook.!frame.!frame2.!canvas.!frame.!frame.!messageshell20.!frame.!label2; src/promptsmith/conversation.py:819`|[investigate](../components/BP-045.md)|无确定发现|semantics_accessibility|
|CMP-210|Skill 可用于具体步骤；你也可以直接跳过。 · `.!frame.!notebook.!frame.!frame2.!canvas.!frame.!frame.!messageshell20.!frame.!label3; src/promptsmith/conversation.py:819`|[investigate](../components/BP-045.md)|无确定发现|semantics_accessibility|
|CMP-211|来源 · `.!frame.!notebook.!frame.!frame2.!canvas.!frame.!frame.!messageshell20.!frame.!frame.!frame.!label; src/promptsmith/conversation.py:819`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-212|conversation_skill_source_filter · `.!frame.!notebook.!frame.!frame2.!canvas.!frame.!frame.!messageshell20.!frame.!frame.!frame.!combobox; src/promptsmith/conversation.py:819`|[investigate](../components/BP-048.md)|无确定发现|semantics_accessibility|
|CMP-213|conversation_skill_show_all · `.!frame.!notebook.!frame.!frame2.!canvas.!frame.!frame.!messageshell20.!frame.!frame.!frame.!checkbutton; src/promptsmith/conversation.py:819`|[investigate](../components/BP-049.md)|无确定发现|semantics_accessibility|
|CMP-214|conversation_skill_candidate_count · `.!frame.!notebook.!frame.!frame2.!canvas.!frame.!frame.!messageshell20.!frame.!frame.!label; src/promptsmith/conversation.py:819`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-215|conversation_skill_candidates_tree · `.!frame.!notebook.!frame.!frame2.!canvas.!frame.!frame.!messageshell20.!frame.!frame.!frame2.!treeview; src/promptsmith/conversation.py:819`|[investigate](../components/BP-050.md)|无确定发现|semantics_accessibility|
|CMP-216|conversation_skill_select_skills · `.!frame.!notebook.!frame.!frame2.!canvas.!frame.!frame.!messageshell20.!frame.!frame.!frame3.!button; src/promptsmith/conversation.py:819`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-217|conversation_skill_cancel_skills · `.!frame.!notebook.!frame.!frame2.!canvas.!frame.!frame.!messageshell20.!frame.!frame.!frame3.!button2; src/promptsmith/conversation.py:819`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-218|conversation_skill_details_text · `.!frame.!notebook.!frame.!frame2.!canvas.!frame.!frame.!messageshell20.!frame.!frame.!frame4.!text; src/promptsmith/conversation.py:819`|[investigate](../components/BP-052.md)|无确定发现|behavior, semantics_accessibility|
|CMP-219|你的任务提示词 · `.!frame.!notebook.!frame.!frame2.!canvas.!frame.!frame.!messageshell21.!frame.!label; src/promptsmith/conversation.py:819`|[investigate](../components/BP-045.md)|无确定发现|semantics_accessibility|
|CMP-220|提示词已生成，可复制和导出。 · `.!frame.!notebook.!frame.!frame2.!canvas.!frame.!frame.!messageshell21.!frame.!label2; src/promptsmith/conversation.py:819`|[investigate](../components/BP-045.md)|无确定发现|semantics_accessibility|
|CMP-221|Text · `.!frame.!notebook.!frame.!frame2.!canvas.!frame.!frame.!messageshell21.!frame.!frame.!markdowntext; src/promptsmith/conversation.py:819`|[investigate](../components/BP-052.md)|无确定发现|behavior, semantics_accessibility|
|CMP-222|conversation_scrollbar · `.!frame.!notebook.!frame.!frame2.!slimscrollbar; src/promptsmith/conversation.py:819`|[investigate](../components/BP-046.md)|无确定发现|semantics_accessibility|
|CMP-223|conversation_hero · `.!frame.!notebook.!frame.!frame2.!label; src/promptsmith/conversation.py:819`|[investigate](../components/BP-045.md)|无确定发现|semantics_accessibility|
|CMP-224|conversation_composer · `.!frame.!notebook.!frame.!promptcomposer; src/promptsmith/conversation.py:819`|[investigate](../components/BP-046.md)|无确定发现|semantics_accessibility|
|CMP-225|conversation_input · `.!frame.!notebook.!frame.!promptcomposer.!frame.!composertext; src/promptsmith/conversation.py:819`|[investigate](../components/BP-052.md)|无确定发现|behavior, semantics_accessibility|
|CMP-226|conversation_model_button · `.!frame.!notebook.!frame.!promptcomposer.!frame.!frame2.!glyphbutton; src/promptsmith/conversation.py:819`|[investigate](../components/BP-046.md)|无确定发现|semantics_accessibility|
|CMP-227|conversation_send_button · `.!frame.!notebook.!frame.!promptcomposer.!frame.!frame2.!glyphbutton2; src/promptsmith/conversation.py:819`|[investigate](../components/BP-046.md)|无确定发现|semantics_accessibility|
|CMP-228|描述你想完成的目标… · `.!frame.!notebook.!frame.!promptcomposer.!frame.!label; src/promptsmith/conversation.py:819`|[investigate](../components/BP-045.md)|无确定发现|semantics_accessibility|
|CMP-463|动态回复动作 · 查找本地 Skill · `ConversationWorkspaceMixin._conversation_buttons / 查找本地 Skill; src/promptsmith/response_ui.py:23-52`|[investigate](../components/BP-062.md)|无确定发现|semantics_accessibility|
|CMP-464|动态回复动作 · 继续联网查找 · `ConversationWorkspaceMixin._conversation_buttons / 继续联网查找; src/promptsmith/response_ui.py:23-52`|[investigate](../components/BP-062.md)|无确定发现|semantics_accessibility|
|CMP-465|动态回复动作 · 整合所选 Skill · `ConversationWorkspaceMixin._conversation_buttons / 整合所选 Skill; src/promptsmith/response_ui.py:23-52`|[investigate](../components/BP-062.md)|无确定发现|semantics_accessibility|
|CMP-466|动态回复动作 · 用已选 Skill 直接生成 · `ConversationWorkspaceMixin._conversation_buttons / 用已选 Skill 直接生成; src/promptsmith/response_ui.py:23-52`|[investigate](../components/BP-062.md)|无确定发现|semantics_accessibility|
|CMP-467|动态回复动作 · 跳过 Skill · `ConversationWorkspaceMixin._conversation_buttons / 跳过 Skill; src/promptsmith/response_ui.py:23-52`|[investigate](../components/BP-062.md)|无确定发现|semantics_accessibility|
|CMP-468|动态回复动作 · 复制提示词 · `ConversationWorkspaceMixin._conversation_buttons / 复制提示词; src/promptsmith/response_ui.py:23-52`|[investigate](../components/BP-062.md)|无确定发现|semantics_accessibility|
|CMP-469|动态回复动作 · 导出方案和提示词 · `ConversationWorkspaceMixin._conversation_buttons / 导出方案和提示词; src/promptsmith/response_ui.py:23-52`|[investigate](../components/BP-062.md)|无确定发现|semantics_accessibility|
|CMP-470|动态回复动作 · 保存会话 · `ConversationWorkspaceMixin._conversation_buttons / 保存会话; src/promptsmith/response_ui.py:23-52`|[investigate](../components/BP-062.md)|无确定发现|semantics_accessibility|
|CMP-471|动态回复动作 · 确认最终提示词 · `ConversationWorkspaceMixin._conversation_buttons / 确认最终提示词; src/promptsmith/response_ui.py:23-52`|[investigate](../components/BP-062.md)|无确定发现|semantics_accessibility|
|CMP-472|动态回复动作 · 语气和附注 · `ConversationWorkspaceMixin._conversation_buttons / 语气和附注; src/promptsmith/response_ui.py:23-52`|[investigate](../components/BP-062.md)|无确定发现|semantics_accessibility|
|CMP-473|动态回复动作 · 取消本次整合 · `ConversationWorkspaceMixin._conversation_buttons / 取消本次整合; src/promptsmith/response_ui.py:23-52`|[investigate](../components/BP-062.md)|无确定发现|semantics_accessibility|
|CMP-474|动态回复动作 · 继续询问 · `ConversationWorkspaceMixin._conversation_buttons / 继续询问; src/promptsmith/response_ui.py:23-52`|[investigate](../components/BP-062.md)|无确定发现|semantics_accessibility|
|CMP-475|动态回复动作 · 结束追问 · `ConversationWorkspaceMixin._conversation_buttons / 结束追问; src/promptsmith/response_ui.py:23-52`|[investigate](../components/BP-062.md)|无确定发现|semantics_accessibility|
|CMP-476|玻璃动作 · 补答loop · `conversation/composer Canvas 补答loop; src/promptsmith/interaction_ui.py:135-236`|[investigate](../components/BP-063.md)|无确定发现|semantics_accessibility|
|CMP-477|玻璃动作 · 整理深度 · `conversation/composer Canvas 整理深度; src/promptsmith/interaction_ui.py:135-236`|[investigate](../components/BP-063.md)|无确定发现|semantics_accessibility|
|CMP-478|玻璃动作 · 任务类型 · `conversation/composer Canvas 任务类型; src/promptsmith/interaction_ui.py:135-236`|[investigate](../components/BP-063.md)|无确定发现|semantics_accessibility|
|CMP-479|逐题 · 题意全文 · `_inline_question / 题意全文; src/promptsmith/interaction_ui.py:410-449; conversation.py:513`|[investigate](../components/BP-064.md)|无确定发现|behavior, semantics_accessibility|
|CMP-480|逐题 · 多行回答 · `_inline_question / 多行回答; src/promptsmith/interaction_ui.py:410-449; conversation.py:513`|[investigate](../components/BP-064.md)|无确定发现|behavior, semantics_accessibility|
|CMP-481|逐题 · 圆形提交 · `_inline_question / 圆形提交; src/promptsmith/interaction_ui.py:410-449; conversation.py:513`|[investigate](../components/BP-064.md)|无确定发现|behavior, semantics_accessibility|
|CMP-482|逐题 · 红色跳过 · `_inline_question / 红色跳过; src/promptsmith/interaction_ui.py:410-449; conversation.py:513`|[investigate](../components/BP-064.md)|无确定发现|behavior, semantics_accessibility|
|CMP-483|思考 · 处理外展开 · `ResponseTrace / 处理外展开; src/promptsmith/response_ui.py:244-396`|[investigate](../components/BP-065.md)|无确定发现|semantics_accessibility|
|CMP-484|思考 · 思考子展开 · `ResponseTrace / 思考子展开; src/promptsmith/response_ui.py:244-396`|[investigate](../components/BP-065.md)|无确定发现|semantics_accessibility|
|CMP-485|思考 · 独立思考滚动 · `ResponseTrace / 独立思考滚动; src/promptsmith/response_ui.py:244-396`|[investigate](../components/BP-065.md)|无确定发现|semantics_accessibility|
|CMP-486|思考 · 活动内容 · `ResponseTrace / 活动内容; src/promptsmith/response_ui.py:244-396`|[investigate](../components/BP-065.md)|无确定发现|semantics_accessibility|
|CMP-487|正文 · 用户气泡 · `MessageShell / MarkdownText / 用户气泡; src/promptsmith/response_ui.py:142-241`|[investigate](../components/BP-066.md)|无确定发现|semantics_accessibility|
|CMP-488|正文 · 提示词标题与正文 · `MessageShell / MarkdownText / 提示词标题与正文; src/promptsmith/response_ui.py:142-241`|[investigate](../components/BP-066.md)|无确定发现|semantics_accessibility|
|CMP-489|底部 · 占位/插入光标/文本 · `PromptComposer / 占位/插入光标/文本; src/promptsmith/composer.py:263-568`|[investigate](../components/BP-067.md)|无确定发现|behavior, semantics_accessibility|
|CMP-490|底部 · 选择模型 · `PromptComposer / 选择模型; src/promptsmith/composer.py:263-568`|[investigate](../components/BP-067.md)|无确定发现|behavior, semantics_accessibility|
|CMP-491|底部 · 常驻发送 · `PromptComposer / 常驻发送; src/promptsmith/composer.py:263-568`|[investigate](../components/BP-067.md)|无确定发现|behavior, semantics_accessibility|

本页SCN：SCN-036；EV：EV-010,EV-007,EV-020。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：当前没有确定缺陷；不代表未执行环境通过。。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
