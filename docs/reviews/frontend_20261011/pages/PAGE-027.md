# PAGE-027 · Tk五类设置

> 本文主体是修复前的逐页/组件审查与目标蓝图，原失败描述保留追溯。13项问题已按[当前台账](../audit.json)完成本地修复；见[修复验收](../../../../verification/frontend_fixes_20261011/results.md)。真实平台缺口仍待TASK-014，蓝图不等于所有平台均已验收。

入口：`native notebook:4`。源码：`src/promptsmith/guided_flow.py:177-187`。

五个设置分类与37个连接/偏好实际控件；额外目录Text独立读取。当前原生样式是兼容默认，而非Web。

变体：浅/深、空/有/失效、滚动/小窗、业务条件可见。

本页全部逻辑实例（不是抽样）：

|实例|单元/定位|处置|问题|未闭合维度|
|---|---|---|---|---|
|CMP-322|页面壳与滚动区 · `notebook[4]; src/promptsmith/guided_flow.py:177`|[investigate](../components/BP-044.md)|无确定发现|semantics_accessibility|
|CMP-323|settings_page_canvas · `.!frame.!notebook.!frame5.!canvas; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-046.md)|无确定发现|semantics_accessibility|
|CMP-324|设置 · `.!frame.!notebook.!frame5.!canvas.!frame.!frame.!label; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-325|settings_return_button · `.!frame.!notebook.!frame5.!canvas.!frame.!frame.!button; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-326|settings_category_0_page_canvas · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-046.md)|无确定发现|semantics_accessibility|
|CMP-327|服务名称 · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!frame.!label; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-328|provider_combo · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!frame.!combobox; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-329|协议 · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!frame.!label2; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-330|protocol_combo · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!frame.!combobox2; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-331|接口地址 · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!frame.!label3; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-332|api_base_entry · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!frame.!entry; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-333|模型 ID · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!frame.!label4; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-334|api_model_entry · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!frame.!combobox3; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-335|API Key · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!frame.!label5; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-336|api_key_entry · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!frame.!entry2; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-337|model_list_button · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!frame.!frame.!button; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-338|test_connection_button · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!frame.!frame.!button2; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-339|confirm_model_settings_button · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!frame.!frame.!button3; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-340|模型设置已确认，可以返回工作区继续。 · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!frame.!label6; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-341|生成 timeout（秒） · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!label; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-342|setting_generation_timeout · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!spinbox; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-343|连接 / 模型列表 timeout（秒） · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!label2; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-344|setting_connection_timeout · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!spinbox2; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-345|max_tokens（0 = 自动） · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!label3; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-346|setting_max_tokens · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!spinbox3; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-347|temperature（auto / 留空 / 数值） · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!label4; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-348|setting_temperature · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!entry; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-349|top_p（留空 = 不发送） · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!label5; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-350|setting_top_p · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!entry2; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-351|思考强度 · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!label6; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-352|setting_reasoning_effort · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame.!canvas.!frame.!combobox; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-353|settings_category_1_page_canvas · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-046.md)|无确定发现|semantics_accessibility|
|CMP-354|筛选模型 timeout（秒） · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!label; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-355|setting_search_model_timeout · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!spinbox; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-356|每个联网来源 timeout（秒） · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!label2; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-357|setting_search_timeout · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!spinbox2; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-358|本地正文粗查上限 · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!label3; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-359|setting_local_candidates · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!spinbox3; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-360|名称 / 描述初筛上限 · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!label4; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-361|setting_shortlist_limit · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!spinbox4; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-362|AI 内容核验上限 · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!label5; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-363|setting_review_limit · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!spinbox5; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-364|默认展示推荐数量 · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!label6; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-365|setting_display_limit · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!spinbox6; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-366|每个联网来源收集上限 · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!label7; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-367|setting_network_candidates · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!spinbox7; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-368|联网来源缓存秒数（0 = 不复用） · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!label8; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-369|setting_network_cache_seconds · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!spinbox8; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-370|AI 筛选累计输入字符上限 · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!label9; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-371|setting_input_budget · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!spinbox9; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-372|每项 Skill 正文节选字符上限 · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!label10; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-373|setting_excerpt_chars · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!spinbox10; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-374|额外本地 Skill 目录（每行一个） · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!label11; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-375|setting_extra_skill_roots · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!text; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-376|Skill 索引地址 · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!label12; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-377|setting_skill_search_url · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!entry; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-378|网页检索地址（含 {query}） · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!label13; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-379|setting_web_search_url · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame2.!canvas.!frame.!entry2; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-380|settings_category_2_page_canvas · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame3.!canvas; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-046.md)|无确定发现|semantics_accessibility|
|CMP-381|启动窗口宽度（保持 16:9） · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame3.!canvas.!frame.!label; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-382|setting_window_width · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame3.!canvas.!frame.!spinbox; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-383|字号基准（pt，显示为125%） · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame3.!canvas.!frame.!label2; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-384|setting_font_size · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame3.!canvas.!frame.!spinbox2; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-385|输入区与模型菜单主题 · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame3.!canvas.!frame.!label3; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-386|setting_composer_theme · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame3.!canvas.!frame.!combobox; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-387|settings_category_3_page_canvas · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame4.!canvas; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-046.md)|无确定发现|semantics_accessibility|
|CMP-388|新会话思考深度 · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame4.!canvas.!frame.!label; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-389|setting_default_thinking · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame4.!canvas.!frame.!combobox; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-390|默认交付语气 · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame4.!canvas.!frame.!label2; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-391|setting_default_tone · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame4.!canvas.!frame.!combobox2; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-392|会话保存目录（留空 = 默认） · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame4.!canvas.!frame.!label3; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-393|setting_session_directory · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame4.!canvas.!frame.!entry; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-394|浏览… · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame4.!canvas.!frame.!button; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-395|Markdown 导出目录（留空 = 默认） · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame4.!canvas.!frame.!label4; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-396|setting_export_directory · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame4.!canvas.!frame.!entry2; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-397|浏览… · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame4.!canvas.!frame.!button2; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-398|settings_category_4_page_canvas · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame5.!canvas; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-046.md)|无确定发现|semantics_accessibility|
|CMP-399|控制台默认显示级别 · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame5.!canvas.!frame.!label; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-400|setting_debug_level · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame5.!canvas.!frame.!combobox; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-401|控制台自动滚动 · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame5.!canvas.!frame.!label2; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-402|setting_debug_autoscroll · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame5.!canvas.!frame.!checkbutton; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-403|控制台缓存条数 · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame5.!canvas.!frame.!label3; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-404|setting_debug_history · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame5.!canvas.!frame.!spinbox; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-405|控制台显示行数上限 · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame5.!canvas.!frame.!label4; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-406|setting_debug_lines · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame5.!canvas.!frame.!spinbox2; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-407|debug_console_toggle · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame5.!canvas.!frame.!checkbutton2; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-054.md)|无确定发现|behavior, semantics_accessibility|
|CMP-408|%TEMP%\PromptSmith\logs · `.!frame.!notebook.!frame5.!canvas.!frame.!notebook.!frame5.!canvas.!frame.!label5; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-409|模型设置已保存，其它分类的编辑需单独保存。 · `.!frame.!notebook.!frame5.!canvas.!frame.!frame2.!label; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-047.md)|无确定发现|semantics_accessibility|
|CMP-410|settings_restore_button · `.!frame.!notebook.!frame5.!canvas.!frame.!frame2.!button; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|
|CMP-411|settings_save_button · `.!frame.!notebook.!frame5.!canvas.!frame.!frame2.!button2; src/promptsmith/settings_ui.py:1`|[investigate](../components/BP-051.md)|无确定发现|semantics_accessibility|

本页SCN：SCN-040；EV：EV-010,EV-007,EV-019,EV-020。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。

本页问题：当前没有确定缺陷；不代表未执行环境通过。。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。
