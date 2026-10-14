# 右上角通知文案总清单

本清单对应 2026-10-13 本轮源码。修改时可以直接告诉我编号与新表述，例如“把 F003 改成……”。花括号代表运行时内容；`／` 分隔同一位置的不同分支；`<br>` 代表换行。

## 阅读范围

- 当前 WebView2 工作区、设置、历史、编辑和独立 Debug 的操作反馈都通过右上角通知；每张有独立5秒倒计时条，右端向左匀速缩短，结束后自动收回，也可手动关闭。关闭后相同快照不重放；真实的新操作仍可发新消息。
- B 表包含 Python 全部消息框/业务状态产生点，不省略罕见分支。代码保留一些 Tk 兼容或旧操作入口，不能据此认为主界面重新增加了相应按钮。例如旧“确认模型/保存设置/最终复核”相关文字属于保留逻辑，当前正常设置流程自动保存、有效配置即可使用。
- D 表展开 B 表的变量与拼接来源，G 表逐条列出模型失败帮助的可枚举分支，E 表列 Web 操作校验的原始动态错误。`{str(exc)}`、`{error.message}`、服务返回正文、文件路径/模型/Skill名称等不是有限固定字符串，实际消息会按真实原因替换并脱敏；完整异常链留在 Debug。其余底层 API/会话/schema 异常也可能进入这些模板，未将数百种底层错误虚称为有限文案。
- 不把每条 INFO/DEBUG 日志弹到右上；提问、回答、需求/方案内容、显式核对或删除确认、静态字段帮助仍在原位置。表 S 是被明确过滤的派生状态，不属于当前会弹出的文案。
- 本地/联网 Skill 搜索进行中的逐文件、逐查询、逐候选进度只更新搜索区和 Debug，不触发右上通知。搜索完成（包括无匹配）、取消或整体失败保留汇总通知；动态正文只有满足这项过滤规则后才会弹出。
- WebView2 尚未启动时（缺少运行库、依赖或后端启动失败）的启动错误只能由启动器/原生系统提示显示；显式 `--renderer tk` 兼容模式继续使用原生反馈，右上卡片是正常 WebView2 的呈现。

## 四种自动标题

|类型|默认标题|图标颜色|
|---|---|---|
|成功|操作成功|绿色|
|提示|消息提示|默认文字色|
|警告|请注意|黄色|
|错误|操作未完成|红色|

Python `_show_*` 的原始标题优先；普通业务状态采用默认标题。状态正文含“失败/错误/未完成/无法/异常”显示错误；含未配置/过期/未保存等显示警告；已保存/已复制/成功等显示成功，其余显示提示。

## F：前端固定文案和动态通知入口

表达式保留条件及动态错误的来源，避免遗漏 `result.error` 等实际提示。括号中的 key 仅用于去重，不会显示给用户。

|编号|页面/触发类型|当前正文/条件表达式|代码|
|---|---|---|---|
|F001|工作区操作/同步/模型任务|"内容已变化，请查看当前内容再操作。"|[workspace.js:78](../../resources/ui/workspace/workspace.js#L78)|
|F002|工作区操作/同步/模型任务|result.error\|\|"操作未完成，请重试。"|[workspace.js:80](../../resources/ui/workspace/workspace.js#L80)|
|F003|工作区操作/同步/模型任务|"暂时无法完成操作，请重试。"|[workspace.js:83](../../resources/ui/workspace/workspace.js#L83)|
|F004|工作区操作/同步/模型任务|result.error|[workspace.js:136](../../resources/ui/workspace/workspace.js#L136)|
|F005|工作区操作/同步/模型任务|"选择未应用，请重试。"|[workspace.js:139](../../resources/ui/workspace/workspace.js#L139)|
|F006|工作区操作/同步/模型任务|result.error\|\|"停止未完成，请重试。"|[workspace.js:165](../../resources/ui/workspace/workspace.js#L165)|
|F007|工作区操作/同步/模型任务|"停止未完成，请重试。"|[workspace.js:167](../../resources/ui/workspace/workspace.js#L167)|
|F008|工作区操作/同步/模型任务|result.error\|\|"返回未完成，请重试。"|[workspace.js:178](../../resources/ui/workspace/workspace.js#L178)|
|F009|工作区操作/同步/模型任务|"返回未完成，请重试。"|[workspace.js:179](../../resources/ui/workspace/workspace.js#L179)|
|F010|工作区操作/同步/模型任务|record.error\|\|""|[workspace.js:247](../../resources/ui/workspace/workspace.js#L247)|
|F011|工作区操作/同步/模型任务|next.sync_error\|\|""|[workspace.js:340](../../resources/ui/workspace/workspace.js#L340)|
|F012|工作区操作/同步/模型任务|notice.body\|\|notice.text|[workspace.js:360](../../resources/ui/workspace/workspace.js#L360)|
|F013|工作区操作/同步/模型任务|"页面同步暂未完成，程序会继续尝试。"|[workspace.js:571](../../resources/ui/workspace/workspace.js#L571)|
|F014|工作区操作/同步/模型任务|"页面处理出现错误，请重试。"|[workspace.js:574](../../resources/ui/workspace/workspace.js#L574)|
|F015|工作区操作/同步/模型任务|"页面操作未完成，请重试。"|[workspace.js:575](../../resources/ui/workspace/workspace.js#L575)|
|F016|设置校验/自动保存/供应商操作|"请填写有效的设置值，修正后会自动保存。"|[settings.js:308](../../resources/ui/workspace/settings.js#L308)|
|F017|设置校验/自动保存/供应商操作|invalid?"请填写有效的设置值，修正后会自动保存。":"请选择模型供应商，选择后会自动保存。"|[settings.js:315](../../resources/ui/workspace/settings.js#L315)|
|F018|设置校验/自动保存/供应商操作|error.message\|\|"自动保存失败，请重试。"|[settings.js:336](../../resources/ui/workspace/settings.js#L336)|
|F019|设置校验/自动保存/供应商操作|"请填写新的服务名称。"|[settings.js:368](../../resources/ui/workspace/settings.js#L368)|
|F020|设置校验/自动保存/供应商操作|"请选择模型供应商，再保存或使用此自定义服务。"|[settings.js:417](../../resources/ui/workspace/settings.js#L417)|
|F021|历史会话保存/重命名|"会话草稿暂未保存，请重试。"|[history.js:41](../../resources/ui/workspace/history.js#L41)|
|F022|历史会话保存/重命名|next.error\|\|""|[history.js:67](../../resources/ui/workspace/history.js#L67)|
|F023|历史会话保存/重命名|"请输入会话名称。"|[history.js:87](../../resources/ui/workspace/history.js#L87)|
|F024|内容编辑|editor.error\|\|""|[editors.js:13](../../resources/ui/workspace/editors.js#L13)|
|F025|内容编辑|(event.target.getAttribute("aria-label")\|\|"内容")+"不能为空。"|[editors.js:27](../../resources/ui/workspace/editors.js#L27)|
|F026|Debug同步/复制/手动保存/目录|status|[debug.js:81](../../resources/ui/workspace/debug.js#L81)|
|F027|Debug同步/复制/手动保存/目录|"日志同步暂未完成，程序会继续尝试。"|[debug.js:85](../../resources/ui/workspace/debug.js#L85)|
|F028|Debug同步/复制/手动保存/目录|"已复制当前显示的日志。"|[debug.js:90](../../resources/ui/workspace/debug.js#L90)|
|F029|Debug同步/复制/手动保存/目录|"复制未完成，请选中文本后按Ctrl+C。"|[debug.js:90](../../resources/ui/workspace/debug.js#L90)|
|F030|Debug同步/复制/手动保存/目录|result.ok?"":result.error|[debug.js:91](../../resources/ui/workspace/debug.js#L91)|
|F031|Debug同步/复制/手动保存/目录|"保存日志未完成，请重试。"|[debug.js:91](../../resources/ui/workspace/debug.js#L91)|
|F032|Debug同步/复制/手动保存/目录|result.ok?"":result.error|[debug.js:92](../../resources/ui/workspace/debug.js#L92)|
|F033|Debug同步/复制/手动保存/目录|"日志目录未能打开，请重试。"|[debug.js:92](../../resources/ui/workspace/debug.js#L92)|
|F034|Debug同步/复制/手动保存/目录|"日志页面处理出现错误，请重试。"|[debug.js:93](../../resources/ui/workspace/debug.js#L93)|
|F035|Debug同步/复制/手动保存/目录|"日志页面操作未完成，请重试。"|[debug.js:94](../../resources/ui/workspace/debug.js#L94)|
|F036|教程完成/跳过状态保存|"教程状态未能保存，请再试一次。"|[tutorial.js:76](../../resources/ui/workspace/tutorial.js#L76)|

## B：业务消息与操作状态（全部产生点）

|编号|级别|标题/变量|正文或模板|触发入口|来源/呈现|代码|
|---|---|---|---|---|---|---|
|B001|随正文分类|自动标题|已切换供应商；修改自动保存。 ／ 已切换供应商；各供应商的未保存输入已暂存，仅保存当前供应商。|ui._on_provider_changed|settings_status_var → 通知|[ui.py:1223](../../src/promptsmith/ui.py#L1223)|
|B002|随正文分类|自动标题|正在从当前供应商获取模型列表...|ui.fetch_models|业务操作状态 → 通知|[ui.py:1310](../../src/promptsmith/ui.py#L1310)|
|B003|随正文分类|自动标题|{text}|ui._models_ok|业务操作状态 → 通知|[ui.py:1345](../../src/promptsmith/ui.py#L1345)|
|B004|随正文分类|自动标题|获取模型列表失败：{exc}|ui._models_failed|业务操作状态 → 通知|[ui.py:1360](../../src/promptsmith/ui.py#L1360)|
|B005|错误|获取模型列表失败|{exc}<br>仍可手动填写模型 ID。|ui._models_failed|原消息框 → Web通知|[ui.py:1361](../../src/promptsmith/ui.py#L1361)|
|B006|随正文分类|自动标题|正在测试模型连接...|ui.test_connection|业务操作状态 → 通知|[ui.py:1968](../../src/promptsmith/ui.py#L1968)|
|B007|随正文分类|自动标题|连接失败：{exc}|ui._connection_failed|业务操作状态 → 通知|[ui.py:1983](../../src/promptsmith/ui.py#L1983)|
|B008|错误|连接失败|{str(exc)}|ui._connection_failed|原消息框 → Web通知|[ui.py:1984](../../src/promptsmith/ui.py#L1984)|
|B009|随正文分类|自动标题|正在分析需求...|ui.start_analysis|业务操作状态 → 通知|[ui.py:2022](../../src/promptsmith/ui.py#L2022)|
|B010|随正文分类|自动标题|{status}|ui._analysis_ok|业务操作状态 → 通知|[ui.py:2072](../../src/promptsmith/ui.py#L2072)|
|B011|随正文分类|自动标题|分析失败：{message}{evidence}|ui._analysis_failed|业务操作状态 → 通知|[ui.py:2138](../../src/promptsmith/ui.py#L2138)|
|B012|错误|需求分析失败|{message}{evidence}<br>任务输入和已有需求未丢失。|ui._analysis_failed|原消息框 → Web通知|[ui.py:2140](../../src/promptsmith/ui.py#L2140)|
|B013|随正文分类|自动标题|已由用户确认需求版本 {version}，可生成完整初始方案。|ui.confirm_requirements|status_var → 通知|[ui.py:2267](../../src/promptsmith/ui.py#L2267)|
|B014|随正文分类|自动标题|正在依据已确认需求生成完整初始方案...|ui.start_plan_generation|业务操作状态 → 通知|[ui.py:2287](../../src/promptsmith/ui.py#L2287)|
|B015|随正文分类|自动标题|方案草稿已生成。{guidance}|ui._plan_ok|业务操作状态 → 通知|[ui.py:2340](../../src/promptsmith/ui.py#L2340)|
|B016|随正文分类|自动标题|{message}|ui._plan_failed|业务操作状态 → 通知|[ui.py:2383](../../src/promptsmith/ui.py#L2383)|
|B017|警告|本次方案尚未生成|{message}{evidence}|ui._plan_failed|原消息框 → Web通知|[ui.py:2385](../../src/promptsmith/ui.py#L2385)|
|B018|随正文分类|自动标题|方案目标已修改，请重新复核。|ui.save_plan_goal|status_var → 通知|[ui.py:2398](../../src/promptsmith/ui.py#L2398)|
|B019|随正文分类|自动标题|选中的关键工作已由用户复核。|ui.review_selected_key_work|status_var → 通知|[ui.py:2638](../../src/promptsmith/ui.py#L2638)|
|B020|随正文分类|自动标题|已由用户确认方案版本 {version}。|ui.confirm_plan|status_var → 通知|[ui.py:2814](../../src/promptsmith/ui.py#L2814)|
|B021|随正文分类|自动标题|已返回需求页。|ui.go_to_requirements|status_var → 通知|[ui.py:2819](../../src/promptsmith/ui.py#L2819)|
|B022|随正文分类|自动标题|回答原话已记录。|ui.record_question|status_var → 通知|[ui.py:2832](../../src/promptsmith/ui.py#L2832)|
|B023|随正文分类|自动标题|选中的受影响需求已由用户复核。|ui.review_selected_requirements|status_var → 通知|[ui.py:2842](../../src/promptsmith/ui.py#L2842)|
|B024|随正文分类|自动标题|已允许模型继续根据未解决的问题整理；不会改变你的需求内容。|ui.add_rounds|status_var → 通知|[ui.py:2850](../../src/promptsmith/ui.py#L2850)|
|B025|随正文分类|自动标题|{self._skill_search_status_text}|ui._skill_search_result_is_current|skill_status_var → 通知|[ui.py:3146](../../src/promptsmith/ui.py#L3146)|
|B026|随正文分类|自动标题|{self._skill_search_status_text}|ui._local_skill_search_ok|skill_status_var → 通知|[ui.py:3295](../../src/promptsmith/ui.py#L3295)|
|B027|随正文分类|自动标题|{self._skill_search_status_text}|ui._local_skill_search_error|skill_status_var → 通知|[ui.py:3310](../../src/promptsmith/ui.py#L3310)|
|B028|随正文分类|自动标题|{self._skill_search_status_text}|ui.find_skills|skill_status_var → 通知|[ui.py:3351](../../src/promptsmith/ui.py#L3351)|
|B029|随正文分类|自动标题|{self._skill_search_status_text}|ui._network_skill_search_ok|skill_status_var → 通知|[ui.py:3467](../../src/promptsmith/ui.py#L3467)|
|B030|随正文分类|自动标题|{self._skill_search_status_text}|ui._network_skill_search_error|skill_status_var → 通知|[ui.py:3519](../../src/promptsmith/ui.py#L3519)|
|B031|随正文分类|自动标题|{self._skill_search_status_text}|ui.search_online_skills|skill_status_var → 通知|[ui.py:3569](../../src/promptsmith/ui.py#L3569)|
|B032|随正文分类|自动标题|已选用 {len(existing)} 项 Agent Skill。|ui.select_skill_candidates|skill_status_var → 通知|[ui.py:3799](../../src/promptsmith/ui.py#L3799)|
|B033|随正文分类|自动标题|已取消选中的 Agent Skill。|ui.cancel_selected_skills|skill_status_var → 通知|[ui.py:3820](../../src/promptsmith/ui.py#L3820)|
|B034|随正文分类|自动标题|{message}|ui._delivery_request_failed|status_var → 通知|[ui.py:4006](../../src/promptsmith/ui.py#L4006)|
|B035|错误|AI调用失败|{message}|ui._delivery_request_failed|原消息框 → Web通知|[ui.py:4008](../../src/promptsmith/ui.py#L4008)|
|B036|随正文分类|自动标题|{message}|ui._set_delivery_feedback|skill_status_var → 通知|[ui.py:4023](../../src/promptsmith/ui.py#L4023)|
|B037|随正文分类|自动标题|{feedback}|ui.cancel_active_request|业务操作状态 → 通知|[ui.py:4065](../../src/promptsmith/ui.py#L4065)|
|B038|随正文分类|自动标题|适配前提已记录为用户说明；此前草稿因来源变化需要重新整合。|ui.update_selected_skill_prerequisite|skill_status_var → 通知|[ui.py:4150](../../src/promptsmith/ui.py#L4150)|
|B039|随正文分类|自动标题|变化已接受；请继续处理其余变化并复核最终草稿。 ／ 变化已拒绝；请继续处理其余变化并复核最终草稿。|ui._decide_selected_m4_change|status_var → 通知|[ui.py:4236](../../src/promptsmith/ui.py#L4236)|
|B040|随正文分类|自动标题|提示词已生成，可以复制或导出。|ui.generate_no_skill_final|final_status_var → 通知|[ui.py:4254](../../src/promptsmith/ui.py#L4254)|
|B041|随正文分类|自动标题|已保留所选 Skill 的名称、来源和用途。 ／ 提示词已从当前已确认方案生成。|ui.generate_no_skill_final|status_var → 通知|[ui.py:4255](../../src/promptsmith/ui.py#L4255)|
|B042|随正文分类|自动标题|已确认最终结果版本 {revision}。|ui.confirm_final_result|status_var → 通知|[ui.py:4496](../../src/promptsmith/ui.py#L4496)|
|B043|随正文分类|自动标题|已复制当前已确认的正式提示。|ui.copy_final_prompt|status_var → 通知|[ui.py:4513](../../src/promptsmith/ui.py#L4513)|
|B044|随正文分类|自动标题|已导出：{path}|ui._export_delivery|status_var → 通知|[ui.py:4575](../../src/promptsmith/ui.py#L4575)|
|B045|随正文分类|自动标题|用户附注已加入草稿，最终确认已撤销。|ui.add_final_note|status_var → 通知|[ui.py:4595](../../src/promptsmith/ui.py#L4595)|
|B046|随正文分类|自动标题|已接受选中的建议。|ui.accept_selected_m2_suggestion|status_var → 通知|[ui.py:4668](../../src/promptsmith/ui.py#L4668)|
|B047|随正文分类|自动标题|已拒绝选中的建议，该建议不会进入执行要求。|ui.reject_selected_m2_suggestion|status_var → 通知|[ui.py:4681](../../src/promptsmith/ui.py#L4681)|
|B048|随正文分类|自动标题|已新建会话。|ui.new_session|status_var → 通知|[ui.py:5229](../../src/promptsmith/ui.py#L5229)|
|B049|随正文分类|自动标题|已打开：{path}|ui.open_session|status_var → 通知|[ui.py:5280](../../src/promptsmith/ui.py#L5280)|
|B050|随正文分类|自动标题|已保存：{self.session_path}|ui.save|status_var → 通知|[ui.py:5309](../../src/promptsmith/ui.py#L5309)|
|B051|随正文分类|自动标题|{self._settings_load_warning}|ui.__init__|settings_status_var → 通知|[ui.py:311](../../src/promptsmith/ui.py#L311)|
|B052|随正文分类|自动标题|{self._settings_load_warning}|ui.__init__|status_var → 通知|[ui.py:389](../../src/promptsmith/ui.py#L389)|
|B053|随正文分类|自动标题|模型配置已保存，可以返回工作区继续。|ui.confirm_model_settings|status_var → 通知|[ui.py:1174](../../src/promptsmith/ui.py#L1174)|
|B054|随正文分类|自动标题|模型设置已确认并保存；下次启动自动恢复，可以返回工作区继续。|ui.confirm_model_settings|status_var → 通知|[ui.py:1177](../../src/promptsmith/ui.py#L1177)|
|B055|随正文分类|自动标题|{text}|ui._set_busy|status_var → 通知|[ui.py:1294](../../src/promptsmith/ui.py#L1294)|
|B056|随正文分类|自动标题|连接配置已变化，可重新获取模型列表。|ui._models_ok|业务操作状态 → 通知|[ui.py:1329](../../src/promptsmith/ui.py#L1329)|
|B057|随正文分类|自动标题|连接配置已变化，已忽略旧模型列表的失败结果。|ui._models_failed|业务操作状态 → 通知|[ui.py:1358](../../src/promptsmith/ui.py#L1358)|
|B058|随正文分类|自动标题|接口已响应：{result.model or self.api_model_var.get()} · {result.latency_ms} ms；探针输出被截断，生成未验证；{confirmation}|ui._connection_ok|业务操作状态 → 通知|[ui.py:1975](../../src/promptsmith/ui.py#L1975)|
|B059|随正文分类|自动标题|连接成功：{result.model or self.api_model_var.get()} · {result.latency_ms} ms；{confirmation}|ui._connection_ok|业务操作状态 → 通知|[ui.py:1980](../../src/promptsmith/ui.py#L1980)|
|B060|随正文分类|自动标题|连接配置已变化，已忽略旧需求分析结果。|ui._analysis_ok|业务操作状态 → 通知|[ui.py:2052](../../src/promptsmith/ui.py#L2052)|
|B061|随正文分类|自动标题|连接配置已变化，已忽略旧需求分析失败结果。|ui._analysis_failed|业务操作状态 → 通知|[ui.py:2105](../../src/promptsmith/ui.py#L2105)|
|B062|提示|没有候选|请选择候选或等待模型返回。|ui._accept_proposals|原消息框 → Web通知|[ui.py:2157](../../src/promptsmith/ui.py#L2157)|
|B063|提示|请选择一项|请选择一条需求进行编辑。|ui.edit_selected_requirement|原消息框 → Web通知|[ui.py:2175](../../src/promptsmith/ui.py#L2175)|
|B064|提示|请选择一项|请选择一条需求进行撤销。|ui.withdraw_selected_requirement|原消息框 → Web通知|[ui.py:2248](../../src/promptsmith/ui.py#L2248)|
|B065|随正文分类|自动标题|连接配置已变化。|ui._plan_ok|业务操作状态 → 通知|[ui.py:2318](../../src/promptsmith/ui.py#L2318)|
|B066|随正文分类|自动标题|方案已生成，可以点击上方“方案”查看。{guidance}|ui._plan_ok|status_var → 通知|[ui.py:2357](../../src/promptsmith/ui.py#L2357)|
|B067|随正文分类|自动标题|连接配置已变化，已忽略旧方案失败结果。|ui._plan_failed|业务操作状态 → 通知|[ui.py:2371](../../src/promptsmith/ui.py#L2371)|
|B068|提示|尚无方案|请先生成初始方案。|ui.edit_plan_goal_details|原消息框 → Web通知|[ui.py:2405](../../src/promptsmith/ui.py#L2405)|
|B069|提示|请选择栏目|请选择一个可编辑的方案栏目。|ui.edit_selected_plan_section|原消息框 → Web通知|[ui.py:2426](../../src/promptsmith/ui.py#L2426)|
|B070|提示|请选择步骤|请选择一个方案步骤。|ui.edit_selected_plan_step|原消息框 → Web通知|[ui.py:2466](../../src/promptsmith/ui.py#L2466)|
|B071|提示|请选择步骤|请选择一个方案步骤。|ui.delete_selected_plan_step|原消息框 → Web通知|[ui.py:2607](../../src/promptsmith/ui.py#L2607)|
|B072|提示|请选择步骤|请选择一个方案步骤。|ui.move_selected_plan_step|原消息框 → Web通知|[ui.py:2622](../../src/promptsmith/ui.py#L2622)|
|B073|提示|请选择关键工作|请选择一项关键工作。|ui.edit_selected_key_work|原消息框 → Web通知|[ui.py:2644](../../src/promptsmith/ui.py#L2644)|
|B074|提示|请选择问题|请选择一条问题。|ui.record_question|原消息框 → Web通知|[ui.py:2824](../../src/promptsmith/ui.py#L2824)|
|B075|随正文分类|自动标题|{message}|ui._refresh_selected_catalog|skill_status_var → 通知|[ui.py:3113](../../src/promptsmith/ui.py#L3113)|
|B076|随正文分类|自动标题|所选 Agent Skill 目录记录已变化，请重新核验 Skill 或跳过。|ui._refresh_selected_catalog|final_status_var → 通知|[ui.py:3114](../../src/promptsmith/ui.py#L3114)|
|B077|错误|暂不能查找 Skill|请先确认当前初始方案。|ui.find_skills|原消息框 → Web通知|[ui.py:3317](../../src/promptsmith/ui.py#L3317)|
|B078|错误|暂不能联网搜索|请先确认当前初始方案。|ui.search_online_skills|原消息框 → Web通知|[ui.py:3526](../../src/promptsmith/ui.py#L3526)|
|B079|提示|请先查找本地 Skill|先完成本地 Skill 查找，再决定是否继续联网搜索。|ui.search_online_skills|原消息框 → Web通知|[ui.py:3532](../../src/promptsmith/ui.py#L3532)|
|B080|随正文分类|自动标题|{self._skill_search_status_text}|ui.search_online_skills|skill_status_var → 通知|[ui.py:3537](../../src/promptsmith/ui.py#L3537)|
|B081|错误|候选已过期|当前方案已变化，请重新筛选本地目录。|ui.select_skill_candidates|原消息框 → Web通知|[ui.py:3742](../../src/promptsmith/ui.py#L3742)|
|B082|提示|请选择候选|请选择至少一个目录候选。|ui.select_skill_candidates|原消息框 → Web通知|[ui.py:3746](../../src/promptsmith/ui.py#L3746)|
|B083|随正文分类|自动标题|已取消 Agent Skill 选用，请重新整合并确认。|ui.cancel_selected_skills|status_var → 通知|[ui.py:3825](../../src/promptsmith/ui.py#L3825)|
|B084|随正文分类|自动标题|最终结果已过期（Agent Skill 选用已变化），请重新整合并确认。|ui.cancel_selected_skills|final_status_var → 通知|[ui.py:3826](../../src/promptsmith/ui.py#L3826)|
|B085|提示|需要模型配置|{message}|ui.analyze_skill_candidates|原消息框 → Web通知|[ui.py:3844](../../src/promptsmith/ui.py#L3844)|
|B086|提示|尚无可分析候选|请先基于当前已确认方案筛选 Agent Skill 候选。|ui.analyze_skill_candidates|原消息框 → Web通知|[ui.py:3847](../../src/promptsmith/ui.py#L3847)|
|B087|错误|Agent Skill 选用已过期|请基于当前已确认方案重新筛选并选用 Agent Skill。|ui.integrate_selected_skills|原消息框 → Web通知|[ui.py:3870](../../src/promptsmith/ui.py#L3870)|
|B088|提示|尚未选用 Agent Skill|请先选用至少一个 Agent Skill，或选择全部跳过。|ui.integrate_selected_skills|原消息框 → Web通知|[ui.py:3873](../../src/promptsmith/ui.py#L3873)|
|B089|提示|需要模型配置|{message}|ui.integrate_selected_skills|原消息框 → Web通知|[ui.py:3879](../../src/promptsmith/ui.py#L3879)|
|B090|随正文分类|自动标题|Skill 整合草稿已生成，可到结果页确认。|ui._apply_delivery_response|status_var → 通知|[ui.py:3992](../../src/promptsmith/ui.py#L3992)|
|B091|随正文分类|自动标题|{self._skill_search_status_text}|ui.cancel_active_request|skill_status_var → 通知|[ui.py:4050](../../src/promptsmith/ui.py#L4050)|
|B092|提示|请选择适配前提|先选择一项适配前提，再保存核对结果。|ui.update_selected_skill_prerequisite|原消息框 → Web通知|[ui.py:4118](../../src/promptsmith/ui.py#L4118)|
|B093|错误|核对结果无效|请选择满足、仍未知或不兼容。|ui.update_selected_skill_prerequisite|原消息框 → Web通知|[ui.py:4123](../../src/promptsmith/ui.py#L4123)|
|B094|错误|Agent Skill 选用已变化|请重新选择当前有效的 Agent Skill。|ui.update_selected_skill_prerequisite|原消息框 → Web通知|[ui.py:4128](../../src/promptsmith/ui.py#L4128)|
|B095|错误|前提已变化|该前提已不属于当前绑定，请重新选择。|ui.update_selected_skill_prerequisite|原消息框 → Web通知|[ui.py:4136](../../src/promptsmith/ui.py#L4136)|
|B096|提示|请选择变化|请先选择一项待处理的变化。|ui._decide_selected_m4_change|原消息框 → Web通知|[ui.py:4217](../../src/promptsmith/ui.py#L4217)|
|B097|错误|变化已过期|该变化已不属于当前最终草稿。|ui._decide_selected_m4_change|原消息框 → Web通知|[ui.py:4226](../../src/promptsmith/ui.py#L4226)|
|B098|提示|不能接受该变化|该变化影响已确认硬约束，请回到需求或方案阶段处理。|ui._decide_selected_m4_change|原消息框 → Web通知|[ui.py:4229](../../src/promptsmith/ui.py#L4229)|
|B099|提示|暂无可复制草稿|只有草稿或来源已变化的结果可通过“复制草稿提示”复制。|ui.copy_draft_prompt|原消息框 → Web通知|[ui.py:4520](../../src/promptsmith/ui.py#L4520)|
|B100|随正文分类|自动标题|已复制过期草稿。|ui.copy_draft_prompt|status_var → 通知|[ui.py:4532](../../src/promptsmith/ui.py#L4532)|
|B101|随正文分类|自动标题|已复制草稿提示，尚未确认。|ui.copy_draft_prompt|status_var → 通知|[ui.py:4534](../../src/promptsmith/ui.py#L4534)|
|B102|提示|请选择建议|请选择一项建议。|ui.accept_selected_m2_suggestion|原消息框 → Web通知|[ui.py:4661](../../src/promptsmith/ui.py#L4661)|
|B103|提示|请选择建议|请选择一项建议。|ui.reject_selected_m2_suggestion|原消息框 → Web通知|[ui.py:4674](../../src/promptsmith/ui.py#L4674)|
|B104|提示|请选择建议|请选择一项需要上游处理的建议。|ui.process_selected_m2_suggestion|原消息框 → Web通知|[ui.py:4687](../../src/promptsmith/ui.py#L4687)|
|B105|提示|无需上游处理|该建议可在此接受或拒绝。|ui.process_selected_m2_suggestion|原消息框 → Web通知|[ui.py:4690](../../src/promptsmith/ui.py#L4690)|
|B106|错误|无法定位建议|当前方案中找不到这项建议，请重新生成方案。|ui.process_selected_m2_suggestion|原消息框 → Web通知|[ui.py:4701](../../src/promptsmith/ui.py#L4701)|
|B107|提示|请选择复核项|请选择一项阻断或待复核内容。|ui.process_selected_final_review_item|原消息框 → Web通知|[ui.py:4863](../../src/promptsmith/ui.py#L4863)|
|B108|随正文分类|自动标题|{status_text}|ui._refresh_delivery_pages|skill_status_var → 通知|[ui.py:5012](../../src/promptsmith/ui.py#L5012)|
|B109|随正文分类|自动标题|模型设置未确认：{exc}|ui.confirm_model_settings|status_var → 通知|[ui.py:1166](../../src/promptsmith/ui.py#L1166)|
|B110|错误|无法确认模型设置|{str(exc)}|ui.confirm_model_settings|原消息框 → Web通知|[ui.py:1167](../../src/promptsmith/ui.py#L1167)|
|B111|错误|配置不完整|{str(exc)}|ui.fetch_models|原消息框 → Web通知|[ui.py:1304](../../src/promptsmith/ui.py#L1304)|
|B112|错误|配置不完整|{str(exc)}|ui.test_connection|原消息框 → Web通知|[ui.py:1965](../../src/promptsmith/ui.py#L1965)|
|B113|错误|无法开始分析|{str(exc)}|ui.start_analysis|原消息框 → Web通知|[ui.py:2019](../../src/promptsmith/ui.py#L2019)|
|B114|随正文分类|自动标题|已拒绝旧返回：{exc}|ui._analysis_ok|业务操作状态 → 通知|[ui.py:2060](../../src/promptsmith/ui.py#L2060)|
|B115|错误|无法接受候选|{str(exc)}|ui._accept_proposals|原消息框 → Web通知|[ui.py:2162](../../src/promptsmith/ui.py#L2162)|
|B116|错误|无法编辑|{str(exc)}|ui.edit_selected_requirement|原消息框 → Web通知|[ui.py:2187](../../src/promptsmith/ui.py#L2187)|
|B117|错误|无法撤销|{str(exc)}|ui.withdraw_selected_requirement|原消息框 → Web通知|[ui.py:2255](../../src/promptsmith/ui.py#L2255)|
|B118|错误|暂不能确认|{str(exc)}|ui.confirm_requirements|原消息框 → Web通知|[ui.py:2265](../../src/promptsmith/ui.py#L2265)|
|B119|错误|无法生成方案|{str(exc)}|ui.start_plan_generation|原消息框 → Web通知|[ui.py:2283](../../src/promptsmith/ui.py#L2283)|
|B120|随正文分类|自动标题|已拒绝旧方案返回：{exc}|ui._plan_ok|业务操作状态 → 通知|[ui.py:2325](../../src/promptsmith/ui.py#L2325)|
|B121|错误|无法修改目标|{str(exc)}|ui.save_plan_goal|原消息框 → Web通知|[ui.py:2396](../../src/promptsmith/ui.py#L2396)|
|B122|错误|无法修改目标|{str(exc)}|ui.edit_plan_goal_details|原消息框 → Web通知|[ui.py:2419](../../src/promptsmith/ui.py#L2419)|
|B123|错误|无法编辑栏目|{str(exc)}|ui.edit_selected_plan_section|原消息框 → Web通知|[ui.py:2458](../../src/promptsmith/ui.py#L2458)|
|B124|错误|无法编辑步骤|{str(exc)}|ui.edit_selected_plan_step|原消息框 → Web通知|[ui.py:2478](../../src/promptsmith/ui.py#L2478)|
|B125|错误|无法新增步骤|{str(exc)}|ui.add_plan_step|原消息框 → Web通知|[ui.py:2490](../../src/promptsmith/ui.py#L2490)|
|B126|错误|内容不完整|步骤标题和目的不能为空。|ui.save|原消息框 → Web通知|[ui.py:2577](../../src/promptsmith/ui.py#L2577)|
|B127|错误|无法删除步骤|{str(exc)}|ui.delete_selected_plan_step|原消息框 → Web通知|[ui.py:2614](../../src/promptsmith/ui.py#L2614)|
|B128|错误|无法调整顺序|{str(exc)}|ui.move_selected_plan_step|原消息框 → Web通知|[ui.py:2627](../../src/promptsmith/ui.py#L2627)|
|B129|错误|无法完成复核|{str(exc)}|ui.review_selected_key_work|原消息框 → Web通知|[ui.py:2636](../../src/promptsmith/ui.py#L2636)|
|B130|错误|无法编辑关键工作|{str(exc)}|ui.edit_selected_key_work|原消息框 → Web通知|[ui.py:2659](../../src/promptsmith/ui.py#L2659)|
|B131|错误|内容不完整|关键工作标题和目标不能为空。|ui.save|原消息框 → Web通知|[ui.py:2734](../../src/promptsmith/ui.py#L2734)|
|B132|错误|暂不能确认方案|{str(exc)}|ui.confirm_plan|原消息框 → Web通知|[ui.py:2812](../../src/promptsmith/ui.py#L2812)|
|B133|错误|无法记录|{str(exc)}|ui.record_question|原消息框 → Web通知|[ui.py:2829](../../src/promptsmith/ui.py#L2829)|
|B134|错误|无法完成复核|{str(exc)}|ui.review_selected_requirements|原消息框 → Web通知|[ui.py:2840](../../src/promptsmith/ui.py#L2840)|
|B135|随正文分类|自动标题|{message}|ui._refresh_selected_catalog|skill_status_var → 通知|[ui.py:3078](../../src/promptsmith/ui.py#L3078)|
|B136|随正文分类|自动标题|所选本地 Skill 文件已变化；最终结果已过期。|ui._refresh_selected_catalog|final_status_var → 通知|[ui.py:3079](../../src/promptsmith/ui.py#L3079)|
|B137|随正文分类|自动标题|{message}|ui._refresh_selected_catalog|skill_status_var → 通知|[ui.py:3102](../../src/promptsmith/ui.py#L3102)|
|B138|随正文分类|自动标题|所选 Agent Skill 来源待核验；最终结果已过期。可返回重新筛选或跳过 Skill。|ui._refresh_selected_catalog|final_status_var → 通知|[ui.py:3103](../../src/promptsmith/ui.py#L3103)|
|B139|随正文分类|自动标题|{self._skill_search_status_text}|ui.search_online_skills|skill_status_var → 通知|[ui.py:3544](../../src/promptsmith/ui.py#L3544)|
|B140|错误|不能选用|该候选当前不可选，可能缺少可用来源信息或与当前任务不兼容。|ui.select_skill_candidates|原消息框 → Web通知|[ui.py:3755](../../src/promptsmith/ui.py#L3755)|
|B141|错误|无法跳过 Skill|{str(exc)}|ui.skip_skills|原消息框 → Web通知|[ui.py:3835](../../src/promptsmith/ui.py#L3835)|
|B142|错误|无法分析候选|{message}|ui.analyze_skill_candidates|原消息框 → Web通知|[ui.py:3859](../../src/promptsmith/ui.py#L3859)|
|B143|错误|无法准备 Agent Skill 整合|{message}|ui.integrate_selected_skills|原消息框 → Web通知|[ui.py:3891](../../src/promptsmith/ui.py#L3891)|
|B144|随正文分类|自动标题|{message}|ui._apply_delivery_response|status_var → 通知|[ui.py:3980](../../src/promptsmith/ui.py#L3980)|
|B145|错误|AI调用未接收|{message}|ui._apply_delivery_response|原消息框 → Web通知|[ui.py:3981](../../src/promptsmith/ui.py#L3981)|
|B146|错误|无法保存前提判断|{str(exc)}|ui.update_selected_skill_prerequisite|原消息框 → Web通知|[ui.py:4148](../../src/promptsmith/ui.py#L4148)|
|B147|错误|无法处理 M4 变化|{str(exc)}|ui._decide_selected_m4_change|原消息框 → Web通知|[ui.py:4234](../../src/promptsmith/ui.py#L4234)|
|B148|错误|无法生成最终草稿|{str(exc)}|ui.generate_no_skill_final|原消息框 → Web通知|[ui.py:4248](../../src/promptsmith/ui.py#L4248)|
|B149|随正文分类|自动标题|{str(exc)}|ui.change_final_tone|status_var → 通知|[ui.py:4482](../../src/promptsmith/ui.py#L4482)|
|B150|错误|暂不能确认最终结果|{str(exc)}|ui.confirm_final_result|原消息框 → Web通知|[ui.py:4494](../../src/promptsmith/ui.py#L4494)|
|B151|提示|不能复制正式提示|当前结果尚未确认或已经过期。<br>{exc}|ui.copy_final_prompt|原消息框 → Web通知|[ui.py:4508](../../src/promptsmith/ui.py#L4508)|
|B152|错误|导出失败|{str(exc)}|ui._export_delivery|原消息框 → Web通知|[ui.py:4540](../../src/promptsmith/ui.py#L4540)|
|B153|错误|导出失败|{str(exc)}|ui._export_delivery|原消息框 → Web通知|[ui.py:4573](../../src/promptsmith/ui.py#L4573)|
|B154|错误|无法添加附注|{str(exc)}|ui.add_final_note|原消息框 → Web通知|[ui.py:4593](../../src/promptsmith/ui.py#L4593)|
|B155|错误|无法接受建议|{str(exc)}|ui.accept_selected_m2_suggestion|原消息框 → Web通知|[ui.py:4666](../../src/promptsmith/ui.py#L4666)|
|B156|错误|无法拒绝建议|{str(exc)}|ui.reject_selected_m2_suggestion|原消息框 → Web通知|[ui.py:4679](../../src/promptsmith/ui.py#L4679)|
|B157|随正文分类|自动标题|最终结果已过期，不能正式复制或确认 · 版本 {result.get('revision', 0)}|ui._refresh_delivery_pages|final_status_var → 通知|[ui.py:5040](../../src/promptsmith/ui.py#L5040)|
|B158|错误|打开失败|{str(exc)}|ui.open_session|原消息框 → Web通知|[ui.py:5277](../../src/promptsmith/ui.py#L5277)|
|B159|随正文分类|自动标题|会话保存失败，请更换目录后重试。|ui.save|status_var → 通知|[ui.py:5306](../../src/promptsmith/ui.py#L5306)|
|B160|错误|保存失败|{message}|ui.save|原消息框 → Web通知|[ui.py:5307](../../src/promptsmith/ui.py#L5307)|
|B161|随正文分类|自动标题|{message}|ui.set_debug_console_enabled|status_var → 通知|[ui.py:450](../../src/promptsmith/ui.py#L450)|
|B162|随正文分类|自动标题|{message}|ui.set_debug_console_enabled|settings_status_var → 通知|[ui.py:451](../../src/promptsmith/ui.py#L451)|
|B163|错误|无法同步任务|{str(exc)}|ui._legacy_run_primary_action|原消息框 → Web通知|[ui.py:1750](../../src/promptsmith/ui.py#L1750)|
|B164|随正文分类|自动标题|方案已保留；草稿提示尚未生成：{exc}|ui._plan_ok|status_var → 通知|[ui.py:2347](../../src/promptsmith/ui.py#L2347)|
|B165|随正文分类|自动标题|{str(exc)}|ui.confirm_plan|status_var → 通知|[ui.py:2808](../../src/promptsmith/ui.py#L2808)|
|B166|错误|草稿来源无效|{str(exc)}|ui.copy_draft_prompt|原消息框 → Web通知|[ui.py:4526](../../src/promptsmith/ui.py#L4526)|
|B167|随正文分类|自动标题|{{'quick': '已选择快速整理：先说清任务基本信息。', 'standard': '已选择标准整理：补齐常见的关键信息。', 'deep': '已选择深入整理：复杂任务会从更多关联角度继续核对。'}[level]}|guided_flow._on_thinking_level_selected|status_var → 通知|[guided_flow.py:450](../../src/promptsmith/guided_flow.py#L450)|
|B168|随正文分类|自动标题|已记录你的选择，你可以继续或以后补答。|guided_flow.skip_guided_question|status_var → 通知|[guided_flow.py:669](../../src/promptsmith/guided_flow.py#L669)|
|B169|随正文分类|自动标题|请先逐项回答或跳过待补充问题，再核对需求和方案。|guided_flow._return_to_unknown_questions|status_var → 通知|[guided_flow.py:758](../../src/promptsmith/guided_flow.py#L758)|
|B170|随正文分类|自动标题|已选中一项相关要求，可在上方编辑或移除。|guided_flow.review_current_conflict|status_var → 通知|[guided_flow.py:574](../../src/promptsmith/guided_flow.py#L574)|
|B171|随正文分类|自动标题|这项修改已经变化，请先查看当前内容。|guided_flow.adopt_preview_change|status_var → 通知|[guided_flow.py:808](../../src/promptsmith/guided_flow.py#L808)|
|B172|随正文分类|自动标题|这段理解已经变化，请先查看当前内容。|guided_flow.accept_selected_understanding|status_var → 通知|[guided_flow.py:825](../../src/promptsmith/guided_flow.py#L825)|
|B173|随正文分类|自动标题|这段解释已经变化，请查看当前内容后再选择。|guided_flow.accept_guided_interpretation|status_var → 通知|[guided_flow.py:920](../../src/promptsmith/guided_flow.py#L920)|
|B174|随正文分类|自动标题|已记录你确认的这段理解；其他建议仍可在下方核对。|guided_flow.accept_guided_interpretation|status_var → 通知|[guided_flow.py:928](../../src/promptsmith/guided_flow.py#L928)|
|B175|随正文分类|自动标题|已确认这些要求可以并存，继续核对其余内容。|guided_flow.review_current_conflict|status_var → 通知|[guided_flow.py:571](../../src/promptsmith/guided_flow.py#L571)|
|B176|错误|无法记录补充|{str(exc)}|guided_flow.submit_guided_answer|原消息框 → Web通知|[guided_flow.py:633](../../src/promptsmith/guided_flow.py#L633)|
|B177|随正文分类|自动标题|这段推测先不采用；你可以直接说明，也可以先做草稿。|guided_flow.skip_guided_question|status_var → 通知|[guided_flow.py:656](../../src/promptsmith/guided_flow.py#L656)|
|B178|错误|无法记录选择|{str(exc)}|guided_flow.skip_guided_question|原消息框 → Web通知|[guided_flow.py:665](../../src/promptsmith/guided_flow.py#L665)|
|B179|随正文分类|自动标题|{str(exc)}|guided_flow.confirm_preview_and_plan|status_var → 通知|[guided_flow.py:715](../../src/promptsmith/guided_flow.py#L715)|
|B180|随正文分类|自动标题|{str(exc)}|guided_flow.confirm_plan_and_generate|status_var → 通知|[guided_flow.py:730](../../src/promptsmith/guided_flow.py#L730)|
|B181|随正文分类|自动标题|{str(exc)}|guided_flow.generate_default_final|status_var → 通知|[guided_flow.py:749](../../src/promptsmith/guided_flow.py#L749)|
|B182|随正文分类|自动标题|{str(exc)}|guided_flow.confirm_plan_and_find_skills|status_var → 通知|[guided_flow.py:771](../../src/promptsmith/guided_flow.py#L771)|
|B183|随正文分类|自动标题|{str(exc)}|guided_flow.accept_selected_understanding|status_var → 通知|[guided_flow.py:834](../../src/promptsmith/guided_flow.py#L834)|
|B184|随正文分类|自动标题|修改已保存。请核对当前内容；需要重新整理时可主动发起。|guided_flow.edit_preview_item|status_var → 通知|[guided_flow.py:862](../../src/promptsmith/guided_flow.py#L862)|
|B185|随正文分类|自动标题|{str(exc)}|guided_flow.remove_preview_item|status_var → 通知|[guided_flow.py:883](../../src/promptsmith/guided_flow.py#L883)|
|B186|随正文分类|自动标题|{str(exc)}|guided_flow.accept_guided_interpretation|status_var → 通知|[guided_flow.py:926](../../src/promptsmith/guided_flow.py#L926)|
|B187|错误|无法同步任务|{str(exc)}|guided_flow.run_primary_action|原消息框 → Web通知|[guided_flow.py:488](../../src/promptsmith/guided_flow.py#L488)|
|B188|随正文分类|自动标题|{str(exc)}|guided_flow.review_current_conflict|status_var → 通知|[guided_flow.py:569](../../src/promptsmith/guided_flow.py#L569)|
|B189|错误|回答已保存|回答已保存，但暂时无法继续整理，请重试。|guided_flow.submit_guided_answers|原消息框 → Web通知|[guided_flow.py:604](../../src/promptsmith/guided_flow.py#L604)|
|B190|随正文分类|自动标题|需求内容未变化，无需重新整理。|guided_flow.edit_preview_item|status_var → 通知|[guided_flow.py:853](../../src/promptsmith/guided_flow.py#L853)|
|B191|随正文分类|自动标题|{str(exc)}|guided_flow.edit_preview_item|status_var → 通知|[guided_flow.py:860](../../src/promptsmith/guided_flow.py#L860)|
|B192|随正文分类|自动标题|已选择继续询问。|conversation._conversation_continue_interview|status_var → 通知|[conversation.py:691](../../src/promptsmith/conversation.py#L691)|
|B193|随正文分类|自动标题|内容已变化，请查看更新后的卡片再操作。|conversation._conversation_action|status_var → 通知|[conversation.py:468](../../src/promptsmith/conversation.py#L468)|
|B194|随正文分类|自动标题|已将 {count} 项未知保留到使用提示词时补充。请继续核对需求和方案。|conversation._conversation_defer_interview_unknowns|status_var → 通知|[conversation.py:672](../../src/promptsmith/conversation.py#L672)|
|B195|随正文分类|自动标题|请先在设置中填写有效模型配置，再选择继续追问。 ／ 请先确认模型设置，再选择继续追问。|conversation._conversation_continue_interview|status_var → 通知|[conversation.py:680](../../src/promptsmith/conversation.py#L680)|
|B196|随正文分类|自动标题|目标已记录；请先在设置中填写有效模型配置，再继续整理。 ／ 目标已记录；请先在设置中确认模型，再继续整理。|conversation.send_conversation_message|status_var → 通知|[conversation.py:322](../../src/promptsmith/conversation.py#L322)|
|B197|随正文分类|自动标题|{str(exc)}|conversation._conversation_review_plan|status_var → 通知|[conversation.py:656](../../src/promptsmith/conversation.py#L656)|
|B198|随正文分类|自动标题|{str(exc)}|conversation._conversation_defer_interview_unknowns|status_var → 通知|[conversation.py:670](../../src/promptsmith/conversation.py#L670)|
|B199|随正文分类|自动标题|{str(exc)}|conversation._conversation_continue_interview|status_var → 通知|[conversation.py:688](../../src/promptsmith/conversation.py#L688)|
|B200|错误|回答未提交|本轮回答未提交，输入已保留。请查看当前问题后重试。|response_workspace._submit_inline_question|原消息框 → Web通知|[response_workspace.py:221](../../src/promptsmith/response_workspace.py#L221)|
|B201|随正文分类|自动标题|已恢复确认过的模型设置，可以继续使用。|settings_ui._restore_model_settings_confirmation|status_var → 通知|[settings_ui.py:127](../../src/promptsmith/settings_ui.py#L127)|
|B202|随正文分类|自动标题|{category}已恢复默认值，保存后生效。|settings_ui.restore_settings_category|settings_status_var → 通知|[settings_ui.py:273](../../src/promptsmith/settings_ui.py#L273)|
|B203|随正文分类|自动标题|设置已保存。{model_status}启动窗口大小下次启动生效。|settings_ui.save_settings|settings_status_var → 通知|[settings_ui.py:309](../../src/promptsmith/settings_ui.py#L309)|
|B204|随正文分类|自动标题|模型设置已保存。|settings_ui.save_settings|settings_status_var → 通知|[settings_ui.py:311](../../src/promptsmith/settings_ui.py#L311)|
|B205|随正文分类|自动标题|设置已保存。|settings_ui._apply_saved_preferences|status_var → 通知|[settings_ui.py:344](../../src/promptsmith/settings_ui.py#L344)|
|B206|随正文分类|自动标题|{self._settings_load_warning}|settings_ui._restore_model_settings_confirmation|settings_status_var → 通知|[settings_ui.py:117](../../src/promptsmith/settings_ui.py#L117)|
|B207|随正文分类|自动标题|{self._settings_load_warning}|settings_ui._restore_model_settings_confirmation|settings_status_var → 通知|[settings_ui.py:124](../../src/promptsmith/settings_ui.py#L124)|
|B208|随正文分类|自动标题|设置未保存：{exc} 请修改后重试。|settings_ui.save_settings|settings_status_var → 通知|[settings_ui.py:297](../../src/promptsmith/settings_ui.py#L297)|
|B209|随正文分类|自动标题|{self.settings_status_var.get()}|settings_ui.save_settings|status_var → 通知|[settings_ui.py:298](../../src/promptsmith/settings_ui.py#L298)|
|B210|错误|设置未保存|{str(exc)}|settings_ui.save_settings|原消息框 → Web通知|[settings_ui.py:299](../../src/promptsmith/settings_ui.py#L299)|
|B211|随正文分类|自动标题|已重命名供应商，接口、密钥和模型列表已保留。|web_workspace.settings_action|settings_status_var → 通知|[web_workspace.py:206](../../src/promptsmith/web_workspace.py#L206)|
|B212|随正文分类|自动标题|已删除自定义供应商及其保存的密钥和模型列表。|web_workspace.settings_action|settings_status_var → 通知|[web_workspace.py:226](../../src/promptsmith/web_workspace.py#L226)|
|B213|随正文分类|自动标题|已自动保存。启动窗口大小下次启动生效。|web_workspace.settings_action|settings_status_var → 通知|[web_workspace.py:264](../../src/promptsmith/web_workspace.py#L264)|
|B214|随正文分类|自动标题|已自动保存。模型配置可直接使用。 ／ 填写模型 ID 和 API Key 后即可使用。|web_workspace.settings_action|settings_status_var → 通知|[web_workspace.py:331](../../src/promptsmith/web_workspace.py#L331)|
|B215|随正文分类|自动标题|修改已保存，请核对当前内容。|web_editors.action|status_var → 通知|[web_editors.py:167](../../src/promptsmith/web_editors.py#L167)|
|B216|随正文分类|自动标题|已开启新对话，之前的进度已保存在历史会话中。|history_workspace.new|status_var → 通知|[history_workspace.py:99](../../src/promptsmith/history_workspace.py#L99)|
|B217|随正文分类|自动标题|已恢复历史会话，可继续当前步骤。|history_workspace.action|status_var → 通知|[history_workspace.py:114](../../src/promptsmith/history_workspace.py#L114)|
|B218|随正文分类|自动标题|{provider}：{text}|model_directory_refresh._complete|全部供应商后台目录 → 通知|[model_directory_refresh.py:115](../../src/promptsmith/model_directory_refresh.py#L115)|
|B219|随正文分类|自动标题|{provider}：正在自动获取模型列表，已有列表仍可使用。|model_directory_refresh.start|全部供应商后台目录 → 通知|[model_directory_refresh.py:59](../../src/promptsmith/model_directory_refresh.py#L59)|
|B220|随正文分类|自动标题|{provider}：{app.runtime_log.redact(f'自动获取模型列表失败：{error}。已有列表保留，可点击“获取模型”重试。')}|model_directory_refresh._complete|全部供应商后台目录 → 通知|[model_directory_refresh.py:101](../../src/promptsmith/model_directory_refresh.py#L101)|
|B221|随正文分类|自动标题|{provider}：无法自动获取模型列表，请核对接口配置后点击“获取模型”。|model_directory_refresh.start|全部供应商后台目录 → 通知|[model_directory_refresh.py:54](../../src/promptsmith/model_directory_refresh.py#L54)|
## D：动态正文、附加说明和分支来源

|编号|级别|标题/变量|正文或模板|触发入口|来源/呈现|代码|
|---|---|---|---|---|---|---|
|D001|错误|模型失败帮助|{label}{wait}，{retained}，可检查网络、调整模型后点击重试。{continuation}|ui.generation_failure_message|真实调用失败原因 → 状态/错误通知|[ui.py:206](../../src/promptsmith/ui.py#L206)|
|D002|错误|模型失败帮助|AI 这次没有生成完整方案，你的需求和已有方案已保留。点击“重新生成方案”再试一次。|ui.generation_failure_message|真实调用失败原因 → 状态/错误通知|[ui.py:169](../../src/promptsmith/ui.py#L169)|
|D003|错误|模型失败帮助|{exc}<br><br>下一步：{next_step}|ui.generation_failure_message|真实调用失败原因 → 状态/错误通知|[ui.py:199](../../src/promptsmith/ui.py#L199)|
|D004|附加/动态|_delivery_status_text||ui.__init__|上表动态占位来源；部分为兼容入口|[ui.py:256](../../src/promptsmith/ui.py#L256)|
|D005|附加/动态|_skill_search_status_text||ui.__init__|上表动态占位来源；部分为兼容入口|[ui.py:266](../../src/promptsmith/ui.py#L266)|
|D006|附加/动态|message|{generation_failure_message('m1', exc, timeout_seconds)}|ui._analysis_failed|上表动态占位来源；部分为兼容入口|[ui.py:2116](../../src/promptsmith/ui.py#L2116)|
|D007|附加/动态|message|{generation_failure_message('m2', exc, timeout_seconds)}|ui._plan_failed|上表动态占位来源；部分为兼容入口|[ui.py:2382](../../src/promptsmith/ui.py#L2382)|
|D008|附加/动态|text|{self.widgets['plan_goal_text'].get('1.0', 'end-1c')}|ui.save_plan_goal|上表动态占位来源；部分为兼容入口|[ui.py:2392](../../src/promptsmith/ui.py#L2392)|
|D009|附加/动态|_skill_search_status_text|方案已变化，已丢弃迟到的 Skill 搜索结果；请重新查找。|ui._skill_search_result_is_current|上表动态占位来源；部分为兼容入口|[ui.py:3145](../../src/promptsmith/ui.py#L3145)|
|D010|附加/动态|_skill_search_status_text| 累计保留 {len(candidates)} 项（含已有联网结果），已选 {len(bindings)} 项。|ui._local_skill_search_ok|上表动态占位来源；部分为兼容入口|[ui.py:3294](../../src/promptsmith/ui.py#L3294)|
|D011|附加/动态|_skill_search_status_text|本地 Skill 查找失败：{exc}；可以重试或跳过。|ui._local_skill_search_error|上表动态占位来源；部分为兼容入口|[ui.py:3309](../../src/promptsmith/ui.py#L3309)|
|D012|附加/动态|_skill_search_status_text|正在查找本地 Skill…|ui.find_skills|上表动态占位来源；部分为兼容入口|[ui.py:3350](../../src/promptsmith/ui.py#L3350)|
|D013|附加/动态|_skill_search_status_text|联网搜索失败：{exc}；已有候选和已选 Skill 已保留。可以选用现有结果、跳过 Skill，或稍后重试联网搜索。|ui._network_skill_search_error|上表动态占位来源；部分为兼容入口|[ui.py:3518](../../src/promptsmith/ui.py#L3518)|
|D014|附加/动态|_skill_search_status_text|正在联网搜索 Skill（并行：Skill 索引、GitHub、开放网页）：生成检索词并收集公开信息…|ui.search_online_skills|上表动态占位来源；部分为兼容入口|[ui.py:3568](../../src/promptsmith/ui.py#L3568)|
|D015|附加/动态|message|{generation_failure_message(request['purpose'], exc, request.get('timeout_seconds'))}|ui._delivery_request_failed|上表动态占位来源；部分为兼容入口|[ui.py:4004](../../src/promptsmith/ui.py#L4004)|
|D016|附加/动态|text|{simpledialog.askstring('添加用户附注', '附注内容：', parent=self.root)}|ui.add_final_note|上表动态占位来源；部分为兼容入口|[ui.py:4587](../../src/promptsmith/ui.py#L4587)|
|D017|错误|模型失败帮助|{reason}。{retained}点击“重新生成方案”再试；若重复出现，可更换模型后重试。暂未确定的任务细节可以留在最终提示中补充。|ui.generation_failure_message|真实调用失败原因 → 状态/错误通知|[ui.py:176](../../src/promptsmith/ui.py#L176)|
|D018|错误|模型失败帮助|{exc}<br>{retained}<br>建议：{getattr(exc, 'recovery_action', '') or '核对任务目标和希望得到的成果。'}<br>可返回“当前需求”补充说明后继续；细节暂时不知道时，可注明“使用提示时再确认”。|ui.generation_failure_message|真实调用失败原因 → 状态/错误通知|[ui.py:179](../../src/promptsmith/ui.py#L179)|
|D019|错误|模型失败帮助|暂时无法连接模型服务。{retained}检查网络和模型地址，再点击“重新生成方案”。|ui.generation_failure_message|真实调用失败原因 → 状态/错误通知|[ui.py:182](../../src/promptsmith/ui.py#L182)|
|D020|错误|模型失败帮助|模型服务未接受当前访问凭据或权限。{retained}请在设置页核对密钥及模型访问权限，测试连接后重新生成。|ui.generation_failure_message|真实调用失败原因 → 状态/错误通知|[ui.py:186](../../src/promptsmith/ui.py#L186)|
|D021|错误|模型失败帮助|模型服务暂时限流或额度不足。{retained}稍后重试，或检查服务额度、切换可用模型。|ui.generation_failure_message|真实调用失败原因 → 状态/错误通知|[ui.py:188](../../src/promptsmith/ui.py#L188)|
|D022|错误|模型失败帮助|模型服务拒绝了本次生成请求。{retained}请在设置页核对连接地址、接口类型和模型名称，测试连接后重新生成；反复失败时可提供诊断记录排查。|ui.generation_failure_message|真实调用失败原因 → 状态/错误通知|[ui.py:190](../../src/promptsmith/ui.py#L190)|
|D023|附加/动态|_settings_load_warning|当前接口配置与保存时不同，未恢复 API Key。请在模型设置中重新输入密钥并确认。|ui.__init__|上表动态占位来源；部分为兼容入口|[ui.py:310](../../src/promptsmith/ui.py#L310)|
|D024|附加/动态|text|已获取 {len(result.model_ids)} 个模型 ID；当前手填值保持不变。已记住列表。 ／ 保存当前供应商设置后可记住列表。|ui._models_ok|上表动态占位来源；部分为兼容入口|[ui.py:1342](../../src/promptsmith/ui.py#L1342)|
|D025|附加/动态|text|供应商返回空模型列表；可继续手动填写模型 ID。|ui._models_ok|上表动态占位来源；部分为兼容入口|[ui.py:1344](../../src/promptsmith/ui.py#L1344)|
|D026|附加/动态|message|本轮需求分析输出被长度限制截断，未提交不完整结果；已有回答和需求已保留。点击“重试分析”可以再试一次；如仍失败，可更换模型或分批补充。|ui._analysis_failed|上表动态占位来源；部分为兼容入口|[ui.py:2127](../../src/promptsmith/ui.py#L2127)|
|D027|附加/动态|message|{'；'.join(assessment['reasons'])}|ui._refresh_selected_catalog|上表动态占位来源；部分为兼容入口|[ui.py:3108](../../src/promptsmith/ui.py#L3108)|
|D028|附加/动态|message|{message} 原绑定快照已保留，请重新筛选/选用或跳过 Skill。|ui._refresh_selected_catalog|上表动态占位来源；部分为兼容入口|[ui.py:3109](../../src/promptsmith/ui.py#L3109)|
|D029|附加/动态|_skill_search_status_text|正在查找本地 Skill：{message}|ui._local_skill_search_progress|上表动态占位来源；部分为兼容入口|[ui.py:3222](../../src/promptsmith/ui.py#L3222)|
|D030|附加/动态|_skill_search_status_text|已收集 {files.scanned_files} 个本地 Skill 文件和 {len(catalog_candidates)} 项内置目录候选，保留 {len(candidates)} 项；AI 筛选暂不可用，可先查看并手动选择。 {ai_review_error}|ui._local_skill_search_ok|上表动态占位来源；部分为兼容入口|[ui.py:3282](../../src/promptsmith/ui.py#L3282)|
|D031|附加/动态|_skill_search_status_text|已索引 {files.scanned_files} 个本地文件，本轮保留 {len(selected)} 项参考候选。 ／ 本地索引含 {files.scanned_files} 个 Skill 文件，少量候选核验后没有适配项；可继续联网搜索或跳过。|ui._local_skill_search_ok|上表动态占位来源；部分为兼容入口|[ui.py:3287](../../src/promptsmith/ui.py#L3287)|
|D032|附加/动态|_skill_search_status_text|内置目录读取不完整：{catalog_error}|ui._local_skill_search_ok|上表动态占位来源；部分为兼容入口|[ui.py:3293](../../src/promptsmith/ui.py#L3293)|
|D033|附加/动态|_skill_search_status_text|正在联网搜索 Skill：{message}|ui._network_skill_search_progress|上表动态占位来源；部分为兼容入口|[ui.py:3387](../../src/promptsmith/ui.py#L3387)|
|D034|附加/动态|message|{result.error.get('message', '搜索来源暂不可用。')}|ui._network_skill_search_ok|上表动态占位来源；部分为兼容入口|[ui.py:3395](../../src/promptsmith/ui.py#L3395)|
|D035|附加/动态|_skill_search_status_text|联网搜索完成：找到 {len(result.candidates)} 项候选；合并后共 {len(candidates)} 项。|ui._network_skill_search_ok|上表动态占位来源；部分为兼容入口|[ui.py:3446](../../src/promptsmith/ui.py#L3446)|
|D036|附加/动态|_skill_search_status_text| AI 筛选暂不可用，联网候选仅经名称/描述粗筛，请核对用途后选用。|ui._network_skill_search_ok|上表动态占位来源；部分为兼容入口|[ui.py:3459](../../src/promptsmith/ui.py#L3459)|
|D037|附加/动态|_skill_search_status_text| 来源状态：{source_summary}。|ui._network_skill_search_ok|上表动态占位来源；部分为兼容入口|[ui.py:3461](../../src/promptsmith/ui.py#L3461)|
|D038|附加/动态|_skill_search_status_text| 部分来源不可用：{source_errors[0][:120]}|ui._network_skill_search_ok|上表动态占位来源；部分为兼容入口|[ui.py:3463](../../src/promptsmith/ui.py#L3463)|
|D039|附加/动态|_skill_search_status_text| 已跳过被拒绝或受限的入口；可以选用现有结果，或稍后重试联网搜索。|ui._network_skill_search_ok|上表动态占位来源；部分为兼容入口|[ui.py:3466](../../src/promptsmith/ui.py#L3466)|
|D040|附加/动态|_skill_search_status_text|AI 联网筛选 Skill 需要先补全：{'、'.join(missing)}。|ui.search_online_skills|上表动态占位来源；部分为兼容入口|[ui.py:3536](../../src/promptsmith/ui.py#L3536)|
|D041|附加/动态|message|AI分析候选需要先补全：{'、'.join(missing)}。候选和现有分析会保留。|ui.analyze_skill_candidates|上表动态占位来源；部分为兼容入口|[ui.py:3842](../../src/promptsmith/ui.py#L3842)|
|D042|附加/动态|message|AI整合所选 Agent Skill 需要先补全：{'、'.join(missing)}。也可点击“用已选 Skill 直接生成提示词”，保留当前选择。|ui.integrate_selected_skills|上表动态占位来源；部分为兼容入口|[ui.py:3877](../../src/promptsmith/ui.py#L3877)|
|D043|附加/动态|_skill_search_status_text|已停止 Skill 搜索，已有候选与选择保留；可重新查找或继续联网搜索。|ui.cancel_active_request|上表动态占位来源；部分为兼容入口|[ui.py:4049](../../src/promptsmith/ui.py#L4049)|
|D044|附加/动态|message|本次模型将全部 {output_tokens} 个输出 token 用于思考，尚未返回正文；未自动重试，已有回答和需求已保留。如果只是在核对表里修改候选，可直接确认，无需再整理；否则可更换模型，或自行调整思考强度后重试。|ui._analysis_failed|上表动态占位来源；部分为兼容入口|[ui.py:2132](../../src/promptsmith/ui.py#L2132)|
|D045|附加/动态|message|本次返回没有形成可用结果；未自动重试。已有回答和需求已保留，可以主动重试或更换模型。|ui._analysis_failed|上表动态占位来源；部分为兼容入口|[ui.py:2135](../../src/promptsmith/ui.py#L2135)|
|D046|附加/动态|message|本地 Skill 来源已变化或不可用：{source}。原绑定已保留，请重新查找。|ui._refresh_selected_catalog|上表动态占位来源；部分为兼容入口|[ui.py:3074](../../src/promptsmith/ui.py#L3074)|
|D047|附加/动态|message|本地 Skill 目录暂不可用，已选 Agent Skill 快照待核验；原绑定内容已保留。{exc}|ui._refresh_selected_catalog|上表动态占位来源；部分为兼容入口|[ui.py:3098](../../src/promptsmith/ui.py#L3098)|
|D048|附加/动态|_skill_search_status_text|联网搜索完成：收集 {collected} 项 Skill 信息，但 AI 筛选暂不可用；没有足够相关的候选可保留。已有结果和选择保留，可以重试或跳过 Skill。|ui._network_skill_search_ok|上表动态占位来源；部分为兼容入口|[ui.py:3453](../../src/promptsmith/ui.py#L3453)|
|D049|附加/动态|_skill_search_status_text|无法开始 AI 联网筛选 Skill：{exc}|ui.search_online_skills|上表动态占位来源；部分为兼容入口|[ui.py:3543](../../src/promptsmith/ui.py#L3543)|
|D050|附加/动态|message|{generation_failure_message('m3', exc, None)}|ui.analyze_skill_candidates|上表动态占位来源；部分为兼容入口|[ui.py:3857](../../src/promptsmith/ui.py#L3857)|
|D051|附加/动态|message|{generation_failure_message('m4', exc, None)}|ui.integrate_selected_skills|上表动态占位来源；部分为兼容入口|[ui.py:3889](../../src/promptsmith/ui.py#L3889)|
|D052|附加/动态|message|{generation_failure_message(purpose, exc, request.get('timeout_seconds'))}|ui._apply_delivery_response|上表动态占位来源；部分为兼容入口|[ui.py:3978](../../src/promptsmith/ui.py#L3978)|
|D053|附加/动态|status_text|；绑定来源已过期，请重新筛选|ui._refresh_delivery_pages|上表动态占位来源；部分为兼容入口|[ui.py:5008](../../src/promptsmith/ui.py#L5008)|
|D054|附加/动态|status_text|；候选已完成 AI 分析|ui._refresh_delivery_pages|上表动态占位来源；部分为兼容入口|[ui.py:5011](../../src/promptsmith/ui.py#L5011)|
|D055|附加/动态|message|{exc}<br><br>请在设置 → 会话与导出中更换可写的会话目录，再从文件菜单选择另存为重试。原文件和当前会话已保留。|ui.save|上表动态占位来源；部分为兼容入口|[ui.py:5305](../../src/promptsmith/ui.py#L5305)|
|D056|附加/动态|message|控制台已切换，但开关未保存。请检查设置文件权限或点击“保存设置”后重试。|ui.set_debug_console_enabled|上表动态占位来源；部分为兼容入口|[ui.py:449](../../src/promptsmith/ui.py#L449)|
|D057|附加/动态|message|本次返回的内容关联不一致，未采用，也未自动重试。已有回答和需求已保留；可修改内容或点击“重试分析”。|ui._analysis_failed|上表动态占位来源；部分为兼容入口|[ui.py:2137](../../src/promptsmith/ui.py#L2137)|
|D058|附加/动态|_skill_search_status_text|联网搜索完成：收集 {collected} 项 Skill 信息，AI 未发现适合当前任务的匹配。已有结果和选择保留，可以调整检索方向、重试或跳过 Skill。|ui._network_skill_search_ok|上表动态占位来源；部分为兼容入口|[ui.py:3455](../../src/promptsmith/ui.py#L3455)|
|D059|附加/动态|_skill_search_status_text|联网搜索完成：没有找到新的 Skill 信息，已有结果和选择保留。可以重试或跳过 Skill。|ui._network_skill_search_ok|上表动态占位来源；部分为兼容入口|[ui.py:3457](../../src/promptsmith/ui.py#L3457)|
|D060|附加/动态|status_text|{search_state['last_error']}|ui._refresh_delivery_pages|上表动态占位来源；部分为兼容入口|[ui.py:4986](../../src/promptsmith/ui.py#L4986)|
|D061|附加/动态|status_text|本地找到 {count} 项候选。 ／ 本地查找完成：没有找到适配候选，可继续联网搜索或跳过。|ui._refresh_delivery_pages|上表动态占位来源；部分为兼容入口|[ui.py:4989](../../src/promptsmith/ui.py#L4989)|
|D062|附加/动态|status_text|联网搜索完成：找到 {count} 项候选；合并后共 {merged_count} 项。 ／ 联网搜索完成：没有找到新的候选。|ui._refresh_delivery_pages|上表动态占位来源；部分为兼容入口|[ui.py:4993](../../src/promptsmith/ui.py#L4993)|
|D063|附加/动态|status_text|{self.session.skill_state.get('last_error') or f'目录状态：{status_label}'}|ui._refresh_delivery_pages|上表动态占位来源；部分为兼容入口|[ui.py:5006](../../src/promptsmith/ui.py#L5006)|
|D064|附加/动态|status_text| 来源状态：{source_summary}。|ui._refresh_delivery_pages|上表动态占位来源；部分为兼容入口|[ui.py:5001](../../src/promptsmith/ui.py#L5001)|
|D065|附加/动态|text|{simpledialog.askstring('修改这项理解', '请用你的话说明：', initialvalue=row['text'], parent=self.root)}|guided_flow.edit_preview_item|上表动态占位来源；部分为兼容入口|[guided_flow.py:849](../../src/promptsmith/guided_flow.py#L849)|
|D066|附加/动态|text|{entry.get('1.0', 'end-1c').strip()}|conversation.send_conversation_message|上表动态占位来源；部分为兼容入口|[conversation.py:310](../../src/promptsmith/conversation.py#L310)|
|D067|附加/动态|_settings_load_warning||settings_ui.save_settings|上表动态占位来源；部分为兼容入口|[settings_ui.py:302](../../src/promptsmith/settings_ui.py#L302)|
|D068|附加/动态|_settings_load_warning|启动时的模型配置已变更，请在设置页核对后点击“确认”。|settings_ui._restore_model_settings_confirmation|上表动态占位来源；部分为兼容入口|[settings_ui.py:116](../../src/promptsmith/settings_ui.py#L116)|
|D069|附加/动态|_settings_load_warning|已保存的模型配置无法使用，请在设置页修正后重新确认。|settings_ui._restore_model_settings_confirmation|上表动态占位来源；部分为兼容入口|[settings_ui.py:123](../../src/promptsmith/settings_ui.py#L123)|
|D070|附加/动态|text|已自动获取 {len(ids)} 个模型。 ／ 供应商返回空模型列表，可手动填写模型 ID。|model_directory_refresh._complete|上表动态占位来源；部分为兼容入口|[model_directory_refresh.py:112](../../src/promptsmith/model_directory_refresh.py#L112)|
|D071|附加/动态|text|列表暂未保存，可点击“获取模型”重试。|model_directory_refresh._complete|上表动态占位来源；部分为兼容入口|[model_directory_refresh.py:114](../../src/promptsmith/model_directory_refresh.py#L114)|
## G：模型失败提示中可枚举的全部原因与下一步

|编号|级别|标题/变量|正文或模板|触发入口|来源/呈现|代码|
|---|---|---|---|---|---|---|
|G001|错误|label / m1|需求分析|ui.generation_failure_message|模型失败帮助的用途分支|[ui.py:200](../../src/promptsmith/ui.py#L200)|
|G002|错误|label / m2|初始方案生成|ui.generation_failure_message|模型失败帮助的用途分支|[ui.py:200](../../src/promptsmith/ui.py#L200)|
|G003|错误|label / m3|候选分析|ui.generation_failure_message|模型失败帮助的用途分支|[ui.py:200](../../src/promptsmith/ui.py#L200)|
|G004|错误|label / m4|Agent Skill 指令整合|ui.generation_failure_message|模型失败帮助的用途分支|[ui.py:200](../../src/promptsmith/ui.py#L200)|
|G005|错误|label / m5|示例生成|ui.generation_failure_message|模型失败帮助的用途分支|[ui.py:200](../../src/promptsmith/ui.py#L200)|
|G006|错误|wait|等待超过{timeout_seconds}秒 ／ 等待超时|ui.generation_failure_message|模型失败帮助的条件/附加说明|[ui.py:202](../../src/promptsmith/ui.py#L202)|
|G007|错误|retained|已有回答和需求已保留 ／ 已有回答、需求和结果已保留|ui.generation_failure_message|模型失败帮助的条件/附加说明|[ui.py:203](../../src/promptsmith/ui.py#L203)|
|G008|错误|continuation / m3|也可直接选用候选 Skill。|ui.generation_failure_message|模型失败帮助的用途分支|[ui.py:204](../../src/promptsmith/ui.py#L204)|
|G009|错误|continuation / m4|也可点击“用已选 Skill 直接生成提示词”。|ui.generation_failure_message|模型失败帮助的用途分支|[ui.py:204](../../src/promptsmith/ui.py#L204)|
|G010|错误|continuation / m5|也可跳过示例并直接回答。|ui.generation_failure_message|模型失败帮助的用途分支|[ui.py:204](../../src/promptsmith/ui.py#L204)|
|G011|错误|retained|你的回答、已确认需求和已有方案已保留，不用重新回答。|ui.generation_failure_message|模型失败帮助的条件/附加说明|[ui.py:172](../../src/promptsmith/ui.py#L172)|
|G012|错误|next_step / m1|回答已保留。可以补充一句说明后重新整理，或点击重试分析；已有需求可继续核对。|ui.generation_failure_message|模型失败帮助的用途分支|[ui.py:192](../../src/promptsmith/ui.py#L192)|
|G013|错误|next_step / m2|需求已保留。可以补充目标或范围后重新生成方案，或在设置中检查模型连接。|ui.generation_failure_message|模型失败帮助的用途分支|[ui.py:192](../../src/promptsmith/ui.py#L192)|
|G014|错误|next_step / m3|候选已保留。可以直接选用合适的 Skill，无需等待候选分析成功。|ui.generation_failure_message|模型失败帮助的用途分支|[ui.py:192](../../src/promptsmith/ui.py#L192)|
|G015|错误|next_step / m4|所选 Skill 已保留。可以点击“用已选 Skill 直接生成提示词”，或重试模型整合。|ui.generation_failure_message|模型失败帮助的用途分支|[ui.py:192](../../src/promptsmith/ui.py#L192)|
|G016|错误|next_step / m5|可以跳过示例，直接回答当前问题，或修改评价标准后重试。|ui.generation_failure_message|模型失败帮助的用途分支|[ui.py:192](../../src/promptsmith/ui.py#L192)|
|G017|错误|reason|AI 返回的方案结构或关联信息不完整 ／ AI 返回的内容格式暂时无法读取|ui.generation_failure_message|模型失败帮助的条件/附加说明|[ui.py:175](../../src/promptsmith/ui.py#L175)|
## E：Web操作及编辑校验可能返回的错误正文

|编号|级别|标题/变量|正文或模板|触发入口|来源/呈现|代码|
|---|---|---|---|---|---|---|
|E001|错误/校验|动态错误正文|请在设置页面填写有效的接口、模型 ID 和 API Key 后再继续。 ／ 请在设置页面点击“确认”，确认当前模型设置后再继续。|ui._api_config|操作被拒绝 → 通知；部分为兼容入口|[ui.py:1117](../../src/promptsmith/ui.py#L1117)|
|E002|错误/校验|动态错误正文|{request.get('ai_client_error') or '未配置可用的 AI 模型，已保留搜集到的本地候选。'}|ui._local_skill_search_operation|操作被拒绝 → 通知；部分为兼容入口|[ui.py:3189](../../src/promptsmith/ui.py#L3189)|
|E003|错误/校验|动态错误正文|选择导出位置期间会话内容已变化，请复核后重新导出。|ui._export_delivery|操作被拒绝 → 通知；部分为兼容入口|[ui.py:4561](../../src/promptsmith/ui.py#L4561)|
|E004|错误/校验|动态错误正文|确认导出期间会话内容已变化，请复核后重新导出。|ui._export_delivery|操作被拒绝 → 通知；部分为兼容入口|[ui.py:4570](../../src/promptsmith/ui.py#L4570)|
|E005|错误/校验|动态错误正文|正在处理当前任务，请稍候或停止后再提交。|guided_flow.submit_guided_answers|操作被拒绝 → 通知；部分为兼容入口|[guided_flow.py:579](../../src/promptsmith/guided_flow.py#L579)|
|E006|错误/校验|动态错误正文|无法初始化对话工作区。|web_workspace.run_web_workspace|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:782](../../src/promptsmith/web_workspace.py#L782)|
|E007|错误/校验|动态错误正文|对话工作区后台已关闭。|web_workspace.run_web_workspace|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:808](../../src/promptsmith/web_workspace.py#L808)|
|E008|错误/校验|动态错误正文|设置已在其它操作中更新，请重新打开设置核对后再提交。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:168](../../src/promptsmith/web_workspace.py#L168)|
|E009|错误/校验|动态错误正文|设置操作不存在。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:244](../../src/promptsmith/web_workspace.py#L244)|
|E010|错误/校验|动态错误正文|正在处理当前请求，完成或取消后再提交设置。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:246](../../src/promptsmith/web_workspace.py#L246)|
|E011|错误/校验|动态错误正文|设置内容格式不正确。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:250](../../src/promptsmith/web_workspace.py#L250)|
|E012|错误/校验|动态错误正文|模型连接字段无效。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:268](../../src/promptsmith/web_workspace.py#L268)|
|E013|错误/校验|动态错误正文|协议不存在。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:270](../../src/promptsmith/web_workspace.py#L270)|
|E014|错误/校验|动态错误正文|密钥操作无效。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:294](../../src/promptsmith/web_workspace.py#L294)|
|E015|错误/校验|动态错误正文|请输入新的 API Key，或选择保留已配置密钥。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:296](../../src/promptsmith/web_workspace.py#L296)|
|E016|错误/校验|动态错误正文|操作参数格式不正确。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:449](../../src/promptsmith/web_workspace.py#L449)|
|E017|错误/校验|动态错误正文|内容已变化，请查看更新后的内容再操作。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:498](../../src/promptsmith/web_workspace.py#L498)|
|E018|错误/校验|动态错误正文|正在处理当前任务，请稍候或取消本次请求。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:539](../../src/promptsmith/web_workspace.py#L539)|
|E019|错误/校验|动态错误正文|WebView2 renderer is not available|web_workspace.ensure_webview2|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:668](../../src/promptsmith/web_workspace.py#L668)|
|E020|错误/校验|动态错误正文|无法启用 WebView2。请安装 Microsoft Edge WebView2 Runtime，并检查项目依赖；也可使用 --renderer tk 启动。|web_workspace.ensure_webview2|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:670](../../src/promptsmith/web_workspace.py#L670)|
|E021|错误/校验|动态错误正文|正在处理当前请求，完成或取消后再重命名供应商。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:174](../../src/promptsmith/web_workspace.py#L174)|
|E022|错误/校验|动态错误正文|请选择当前已保存的自定义供应商后重命名。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:176](../../src/promptsmith/web_workspace.py#L176)|
|E023|错误/校验|动态错误正文|请填写有效的新服务名称。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:178](../../src/promptsmith/web_workspace.py#L178)|
|E024|错误/校验|动态错误正文|这个服务名称已存在，请使用另一个名称。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:181](../../src/promptsmith/web_workspace.py#L181)|
|E025|错误/校验|动态错误正文|正在处理当前请求，完成或取消后再删除供应商。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:214](../../src/promptsmith/web_workspace.py#L214)|
|E026|错误/校验|动态错误正文|内置供应商不能删除。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:216](../../src/promptsmith/web_workspace.py#L216)|
|E027|错误/校验|动态错误正文|自定义供应商不存在，请重新打开设置。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:218](../../src/promptsmith/web_workspace.py#L218)|
|E028|错误/校验|动态错误正文|目录设置不存在。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:232](../../src/promptsmith/web_workspace.py#L232)|
|E029|错误/校验|动态错误正文|Debug 开关值无效。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:238](../../src/promptsmith/web_workspace.py#L238)|
|E030|错误/校验|动态错误正文|设置更新字段无效。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:256](../../src/promptsmith/web_workspace.py#L256)|
|E031|错误/校验|动态错误正文|供应商选择已变化，请重新核对后切换。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:274](../../src/promptsmith/web_workspace.py#L274)|
|E032|错误/校验|动态错误正文|请先完成模型配置并发送一个目标，再完成教程。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:454](../../src/promptsmith/web_workspace.py#L454)|
|E033|错误/校验|动态错误正文|面板不存在。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:470](../../src/promptsmith/web_workspace.py#L470)|
|E034|错误/校验|动态错误正文|会话已变化，不能停止新会话的任务。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:478](../../src/promptsmith/web_workspace.py#L478)|
|E035|错误/校验|动态错误正文|处理任务已变化，请查看当前任务再停止。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:480](../../src/promptsmith/web_workspace.py#L480)|
|E036|错误/校验|动态错误正文|会话或处理任务已变化，请查看当前内容再返回。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:485](../../src/promptsmith/web_workspace.py#L485)|
|E037|错误/校验|动态错误正文|当前步骤已变化，请查看当前内容再返回。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:488](../../src/promptsmith/web_workspace.py#L488)|
|E038|错误/校验|动态错误正文|内容已变化，请查看更新后的内容再返回。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:490](../../src/promptsmith/web_workspace.py#L490)|
|E039|错误/校验|动态错误正文|回答草稿格式不正确，当前内容已保留。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:494](../../src/promptsmith/web_workspace.py#L494)|
|E040|错误/校验|动态错误正文|历史会话尚未启用。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:503](../../src/promptsmith/web_workspace.py#L503)|
|E041|错误/校验|动态错误正文|当前操作尚不可用，请查看最新内容。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:525](../../src/promptsmith/web_workspace.py#L525)|
|E042|错误/校验|动态错误正文|普通设置更新不能包含密钥操作。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:259](../../src/promptsmith/web_workspace.py#L259)|
|E043|错误/校验|动态错误正文|设置更新缺少对应值。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:261](../../src/promptsmith/web_workspace.py#L261)|
|E044|错误/校验|动态错误正文|模型参数草稿无效。|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:287](../../src/promptsmith/web_workspace.py#L287)|
|E045|错误/校验|动态错误正文|{app.settings_status_var.get()}|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:327](../../src/promptsmith/web_workspace.py#L327)|
|E046|错误/校验|动态错误正文|请选择一条需求进行编辑。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:530](../../src/promptsmith/web_workspace.py#L530)|
|E047|错误/校验|动态错误正文|本轮回答格式不正确，请重新提交。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:551](../../src/promptsmith/web_workspace.py#L551)|
|E048|错误|动态错误正文|界面同步暂未完成，请稍候重试；详细原因已记录到 Debug 控制台。|web_workspace._publish_sync_error|桥接/Debug返回用户错误|[web_workspace.py:636](../../src/promptsmith/web_workspace.py#L636)|
|E049|错误|动态错误正文|程序正在关闭。|web_workspace.dispatch|桥接/Debug返回用户错误|[web_workspace.py:641](../../src/promptsmith/web_workspace.py#L641)|
|E050|错误/校验|动态错误正文|{app.settings_status_var.get()}|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:335](../../src/promptsmith/web_workspace.py#L335)|
|E051|错误/校验|动态错误正文|这个问题已更新。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:559](../../src/promptsmith/web_workspace.py#L559)|
|E052|错误|动态错误正文|程序正在关闭。|web_workspace.dispatch|桥接/Debug返回用户错误|[web_workspace.py:646](../../src/promptsmith/web_workspace.py#L646)|
|E053|错误/校验|动态错误正文|{app.settings_status_var.get() or '模型设置未确认，请修改后重试。'}|web_workspace.settings_action|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:340](../../src/promptsmith/web_workspace.py#L340)|
|E054|错误/校验|动态错误正文|模型不存在。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:567](../../src/promptsmith/web_workspace.py#L567)|
|E055|错误/校验|动态错误正文|思考强度不正确。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:571](../../src/promptsmith/web_workspace.py#L571)|
|E056|错误/校验|动态错误正文|任务类型不正确。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:575](../../src/promptsmith/web_workspace.py#L575)|
|E057|错误|动态错误正文|操作未完成，请重试；详细原因已记录到 Debug 控制台。|web_workspace.poll|桥接/Debug返回用户错误|[web_workspace.py:731](../../src/promptsmith/web_workspace.py#L731)|
|E058|错误/校验|动态错误正文|整理深度不正确。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:580](../../src/promptsmith/web_workspace.py#L580)|
|E059|错误/校验|动态错误正文|这条需求已更新。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:587](../../src/promptsmith/web_workspace.py#L587)|
|E060|错误/校验|动态错误正文|来源不正确。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:597](../../src/promptsmith/web_workspace.py#L597)|
|E061|错误/校验|动态错误正文|语气不正确。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:604](../../src/promptsmith/web_workspace.py#L604)|
|E062|错误/校验|动态错误正文|未知操作。|web_workspace._dispatch|操作被拒绝 → 通知；部分为兼容入口|[web_workspace.py:613](../../src/promptsmith/web_workspace.py#L613)|
|E063|错误/校验|动态错误正文|正在处理当前任务，请完成或停止后再编辑。|web_editors.open|操作被拒绝 → 通知；部分为兼容入口|[web_editors.py:48](../../src/promptsmith/web_editors.py#L48)|
|E064|错误/校验|动态错误正文|编辑内容已变化，请重新打开后操作。|web_editors.action|操作被拒绝 → 通知；部分为兼容入口|[web_editors.py:118](../../src/promptsmith/web_editors.py#L118)|
|E065|错误/校验|动态错误正文|正在处理当前任务，请完成或停止后再保存。|web_editors.action|操作被拒绝 → 通知；部分为兼容入口|[web_editors.py:126](../../src/promptsmith/web_editors.py#L126)|
|E066|错误/校验|动态错误正文|这条需求已变化，请重新选择。|web_editors.open|操作被拒绝 → 通知；部分为兼容入口|[web_editors.py:54](../../src/promptsmith/web_editors.py#L54)|
|E067|错误/校验|动态错误正文|编辑操作不存在。|web_editors.action|操作被拒绝 → 通知；部分为兼容入口|[web_editors.py:151](../../src/promptsmith/web_editors.py#L151)|
|E068|错误/校验|动态错误正文|编辑字段格式不正确。|web_editors.action|操作被拒绝 → 通知；部分为兼容入口|[web_editors.py:154](../../src/promptsmith/web_editors.py#L154)|
|E069|错误/校验|动态错误正文|当前没有可编辑的最终草稿。|web_editors.open|操作被拒绝 → 通知；部分为兼容入口|[web_editors.py:60](../../src/promptsmith/web_editors.py#L60)|
|E070|错误/校验|动态错误正文|请先返回完整方案编辑。|web_editors.action|操作被拒绝 → 通知；部分为兼容入口|[web_editors.py:130](../../src/promptsmith/web_editors.py#L130)|
|E071|错误/校验|动态错误正文|请选择当前方案中的项目。|web_editors.action|操作被拒绝 → 通知；部分为兼容入口|[web_editors.py:138](../../src/promptsmith/web_editors.py#L138)|
|E072|错误/校验|动态错误正文|{field['label']}不能为空。|web_editors.action|操作被拒绝 → 通知；部分为兼容入口|[web_editors.py:158](../../src/promptsmith/web_editors.py#L158)|
|E073|错误/校验|动态错误正文|方案编辑栏目不存在。|web_editors.action|操作被拒绝 → 通知；部分为兼容入口|[web_editors.py:134](../../src/promptsmith/web_editors.py#L134)|
|E074|错误/校验|动态错误正文|步骤移动方向无效。|web_editors.action|操作被拒绝 → 通知；部分为兼容入口|[web_editors.py:142](../../src/promptsmith/web_editors.py#L142)|
|E075|错误/校验|动态错误正文|关联项目已变化，请重新选择。|web_editors.action|操作被拒绝 → 通知；部分为兼容入口|[web_editors.py:162](../../src/promptsmith/web_editors.py#L162)|
|E076|错误/校验|动态错误正文|这项冲突已经变化，请查看当前需求。|web_editors.open|操作被拒绝 → 通知；部分为兼容入口|[web_editors.py:68](../../src/promptsmith/web_editors.py#L68)|
|E077|错误/校验|动态错误正文|编辑内容不存在。|web_editors.open|操作被拒绝 → 通知；部分为兼容入口|[web_editors.py:103](../../src/promptsmith/web_editors.py#L103)|
|E078|错误/校验|动态错误正文|当前方案尚不可编辑，请先生成或更新方案。|web_editors.open|操作被拒绝 → 通知；部分为兼容入口|[web_editors.py:78](../../src/promptsmith/web_editors.py#L78)|
|E079|错误/校验|动态错误正文|方案步骤已变化，请重新选择。|web_editors.open|操作被拒绝 → 通知；部分为兼容入口|[web_editors.py:90](../../src/promptsmith/web_editors.py#L90)|
|E080|错误/校验|动态错误正文|方案内容已变化，请重新选择。|web_editors.open|操作被拒绝 → 通知；部分为兼容入口|[web_editors.py:99](../../src/promptsmith/web_editors.py#L99)|
|E081|错误/校验|动态错误正文|输入草稿格式无效。|history_workspace.update_drafts|操作被拒绝 → 通知；部分为兼容入口|[history_workspace.py:141](../../src/promptsmith/history_workspace.py#L141)|
|E082|错误/校验|动态错误正文|历史会话操作不存在。|history_workspace.action|操作被拒绝 → 通知；部分为兼容入口|[history_workspace.py:125](../../src/promptsmith/history_workspace.py#L125)|
|E083|错误|动态错误正文|日志未保存，请检查目录权限或磁盘空间后重试。|web_debug.save|桥接/Debug返回用户错误|[web_debug.py:191](../../src/promptsmith/web_debug.py#L191)|
|E084|错误|动态错误正文|日志目录尚未创建，请先保存日志。|web_debug.open_directory|桥接/Debug返回用户错误|[web_debug.py:203](../../src/promptsmith/web_debug.py#L203)|
|E085|错误|动态错误正文|无法打开日志目录，请查看错误记录后重试。|web_debug.open_directory|桥接/Debug返回用户错误|[web_debug.py:208](../../src/promptsmith/web_debug.py#L208)|
|E086|错误/校验|动态错误正文|这轮回答的恢复记录不完整，当前内容已保留。可继续当前步骤，或从文件菜单重新打开会话。|session._restore_answer_round|操作被拒绝 → 通知；部分为兼容入口|[session.py:554](../../src/promptsmith/session.py#L554)|
|E087|错误/校验|动态错误正文|本轮回答格式不正确，请重新提交。|session.record_question_answers|操作被拒绝 → 通知；部分为兼容入口|[session.py:2474](../../src/promptsmith/session.py#L2474)|
|E088|错误/校验|动态错误正文|本轮回答格式不正确，请重新提交。|session.record_question_answers|操作被拒绝 → 通知；部分为兼容入口|[session.py:2480](../../src/promptsmith/session.py#L2480)|
|E089|错误/校验|动态错误正文|本轮问题已变化或重复，请查看当前问题；回答仍保留。|session.record_question_answers|操作被拒绝 → 通知；部分为兼容入口|[session.py:2485](../../src/promptsmith/session.py#L2485)|
|E090|错误/校验|动态错误正文|只能重命名已保存的自定义供应商。|preferences.rename_provider_profile|操作被拒绝 → 通知；部分为兼容入口|[preferences.py:415](../../src/promptsmith/preferences.py#L415)|
|E091|错误/校验|动态错误正文|请填写有效的新服务名称。|preferences.rename_provider_profile|操作被拒绝 → 通知；部分为兼容入口|[preferences.py:417](../../src/promptsmith/preferences.py#L417)|
|E092|错误/校验|动态错误正文|自定义供应商尚未保存，请先填写有效配置。|preferences.rename_provider_profile|操作被拒绝 → 通知；部分为兼容入口|[preferences.py:422](../../src/promptsmith/preferences.py#L422)|
|E093|错误/校验|动态错误正文|这个服务名称已存在，请使用另一个名称。|preferences.rename_provider_profile|操作被拒绝 → 通知；部分为兼容入口|[preferences.py:424](../../src/promptsmith/preferences.py#L424)|
|E094|错误/校验|动态错误正文|供应商档案已变化，请重新打开设置后重试。|preferences.rename_provider_profile|操作被拒绝 → 通知；部分为兼容入口|[preferences.py:436](../../src/promptsmith/preferences.py#L436)|
|E095|错误/校验|动态错误正文|重命名后的 API Key 无法恢复，原供应商已保留，请重试。|preferences.rename_provider_profile|操作被拒绝 → 通知；部分为兼容入口|[preferences.py:464](../../src/promptsmith/preferences.py#L464)|
|E096|错误/校验|动态错误正文|重命名时未能安全迁移 API Key，原供应商已保留，请重试。|preferences.rename_provider_profile|操作被拒绝 → 通知；部分为兼容入口|[preferences.py:447](../../src/promptsmith/preferences.py#L447)|
## S：不弹出的草稿/派生状态（排除说明）

|编号|级别|标题/变量|正文或模板|触发入口|来源/呈现|代码|
|---|---|---|---|---|---|---|
|S001|随正文分类|自动标题|{self.model_directory_refresh.statuses.get(provider, '')}|ui._on_provider_changed|model_directory_status_var → 通知|[ui.py:1225](../../src/promptsmith/ui.py#L1225)|
|S002|随正文分类|自动标题|{self._skill_search_status_text}|ui._local_skill_search_progress|搜索区当前进度及 Debug；不弹通知|[ui.py:3223](../../src/promptsmith/ui.py#L3223)|
|S003|随正文分类|自动标题|{self._skill_search_status_text}|ui._network_skill_search_progress|搜索区当前进度及 Debug；不弹通知|[ui.py:3388](../../src/promptsmith/ui.py#L3388)|
|S004|随正文分类|自动标题|最终结果：{status_labels.get(result.get('status'), result.get('status'))} · 版本 {result.get('revision', 0)}|ui._refresh_delivery_pages|final_status_var → 通知|[ui.py:5017](../../src/promptsmith/ui.py#L5017)|
|S005|随正文分类|自动标题|有未保存的设置。|settings_ui._settings_roots_modified|settings_status_var → 通知|[settings_ui.py:257](../../src/promptsmith/settings_ui.py#L257)|
|S006|随正文分类|自动标题|有未保存的设置。|settings_ui._build_categorized_settings|settings_status_var → 通知|[settings_ui.py:249](../../src/promptsmith/settings_ui.py#L249)|
|S007|随正文分类|自动标题|{text}|model_directory_refresh._set_status|model_directory_status_var → 通知|[model_directory_refresh.py:36](../../src/promptsmith/model_directory_refresh.py#L36)|

## 运行时模板补充

|编号|触发|正文|
|---|---|---|
|R001|日志保存成功|已保存 {saved_sequence} 条：{path}|
|R002|日志保存失败|保存失败：{脱敏后的保存错误}|
|R003|模型请求失败/思考任务失败|{record.error}；来自实际任务错误，可能含服务原因和下一步|
|R004|历史后台保存失败|历史会话保存未完成。现有内容仍在当前窗口，请点击重试保存；详细原因见 Debug。|
|R005|旧会话导入失败|旧会话导入未完成，可通过文件菜单打开；原文件已保留。|
|R006|启动设置恢复警告|设置恢复提醒：{_settings_load_warning}|
|R007|编辑必填为空|{字段中文名称}不能为空。|
|R008|自动保存成功|已自动保存。模型配置可直接使用。 ／ 已自动保存。填写模型 ID 和 API Key 后即可使用。 ／ 已自动保存。启动窗口大小下次启动生效。|
|R009|Web桥接未就绪/关闭/超时/同步错误|见 E 表 DesktopApi 分支；保持当前内容并重试|

错误通知中的“重试保存”、设置页“重试自动保存”是动作标签，不属于错误正文。关闭按钮无正文，屏幕阅读器名称为“关闭通知”。
