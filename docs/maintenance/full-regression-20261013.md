# 完整回归与失败归因（2026-10-13）

## 结论与边界

完整全仓库运行：**1746通过、82失败、1跳过，1829个节点，1921.36秒**。不能据定向或原生验收称全套全绿。

在本轮修改前工作树的只读投影中复跑原82个失败：**72失败、10通过**；这72项不是教程新增失败，其中包含旧Tk控件/旧提示词/已移除自动修复合同，以及已有业务基线差异，不能一概说产品无问题。其余10项在当前代码隔离复验也通过（流式错误/Stop/目录相邻21项、目录变更单项），属于完整运行中出现但隔离不能复现的失败，**根因未完全定位，不能称已修复测试稳定性**。

最后教程及设置相邻34项全通过：教程20项（3个公开Controller、17个生产DOM），相邻设置14项。包括修改后补入的8个节点、真实保存最后快照后无变化的解锁、当前会话发送成功、重看显示模型页、窄窗说明与最后发送区域。旧介绍轮播版本证据不用于本次完成结论。

按每个节点最后一次结果去重，当前证据合计**1764通过、72失败、1跳过，1837个不同节点**；这是多个运行的最新结果汇总，不是一次全仓库通过结果。

## 前几轮与新教程原生验收

真实Windows WebView2加载生产HTML/CSS/JS，但使用隔离settings.json/日志与模拟HTTP/模型边界。

|范围|通过检查|方式|
|---|---:|---|
|设置复刻/自动保存/目录/服务切换|22|真实Controller、Tk owner、localhost目录GET|
|通知分类/5秒条/补位/无临时滚动条/模态迁移|30|生产主窗口与Debug，合成bridge/日志|
|Debug内部样式/筛选/阅读锚点/手动完整脱敏保存|13|真实RuntimeLog/DebugApi，临时日志|
|批量回答/重命名/Skill表格工具栏|22|生产页面、合成bridge，浅深主题|
|回答撤回/取消请求/阶段返回/重新确认|28|生产页面、合成bridge，浅深主题|
|操作教程/真实配置/最后发送/完成/重看|14|真实Controller、localhost目录，仅替换生成启动|
|合计|129|没有真实模型调用或EXE验收|

前五套脚本通过临时bootstrap将OUT重定向到本轮证据子目录，保留之前验收工件。真实设置脚本在临时配置明确设置教程skipped，使其继续验证设置功能；独立教程脚本正常验证首次not_started。通知脚本收尾SDK销毁期间有ObjectDisposedException输出，但30项检查和退出码均成功；不把该收尾日志混为功能断言失败。

本轮没有访问个人会话/配置、调用付费模型、构建EXE或提交推送。参考范围见[教程维护](tutorial-20261013.md)和[计划](task_plan.md)。

## 原82项失败逐项对照

本轮前投影复制当前src/resources，再覆盖before中本轮触及文件；运行在隔离存储，PYTHONPATH与前端资源指向投影。测试集合/未触及代码保持当前状态。源码release链子进程显式使用根目录入口，其源码不由该投影切换；该项还涉及旧M5/交付脚本合同，需单列核查。没有通过删除、跳过或放宽旧测试制造全绿。

|测试节点|修改前复跑|当前结论|
|---|---|---|
|`tests/test_composer.py::test_send_is_persistent_but_disabled_for_empty_whitespace_and_busy`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_conversation_workspace.py::test_plan_can_be_edited_and_confirmed_in_conversation`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_experience_acceptance_fix.py::test_main_page_scroll_keeps_details_reachable_at_150_percent_scaling`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_experience_acceptance_fix.py::test_ui_exposes_service_and_protocol_selectors_and_uses_selected_adapter`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_experience_iteration.py::test_read_only_requirement_list_context_menu_copies_complete_selected_text`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_experience_iteration.py::test_requirement_table_scrollbars_scroll_both_axes_with_long_content`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_experience_iteration.py::test_requirement_editor_is_multiline_and_context_menu_paste_works`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_final_closure.py::test_explicit_latest_user_evidence_can_reopen_skipped_question_and_persists`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_fixed_demo_runner.py::test_m4_pending_change_cannot_be_bypassed_by_final_confirmation`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_generation_module_timeouts.py::test_module_timeout_preserves_business_state_and_releases_ui[m2-generate_plan_button-\u521d\u59cb\u65b9\u6848\u751f\u6210]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_generation_module_timeouts.py::test_module_timeout_preserves_business_state_and_releases_ui[m3-skill_analyze_button-\u5019\u9009\u5206\u6790]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_generation_module_timeouts.py::test_module_timeout_preserves_business_state_and_releases_ui[m4-skill_integrate_button-Agent Skill \u6307\u4ee4\u6574\u5408]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_generation_module_timeouts.py::test_module_timeout_preserves_business_state_and_releases_ui[m5-m5_generate_button-\u793a\u4f8b\u751f\u6210]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_generation_timeout_ui.py::test_second_round_timeout_preserves_answers_then_explicit_retry_succeeds`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_guided_jgs_chain.py::test_jgs_skip_then_same_region_supplement_closes_gap_without_rewriting_task`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_guided_jgs_chain.py::test_jgs_skip_then_one_draft_click_produces_copyable_exportable_reopenable_result`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_guided_jgs_chain.py::test_deciding_interpretation_reclaims_space_for_requirements[accept]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_guided_jgs_chain.py::test_deciding_interpretation_reclaims_space_for_requirements[correct]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_guided_jgs_chain.py::test_explicit_guess_choice_leaves_unrelated_budget_unadopted[accept]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_guided_jgs_chain.py::test_explicit_guess_choice_leaves_unrelated_budget_unadopted[correct]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_guided_ui.py::test_understanding_accept_button_disabled_without_selected_interpretation`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_guided_ui.py::test_editing_candidate_keeps_correction_and_retires_old_text`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_guided_ui.py::test_conflict_action_opens_user_resolution_and_allows_compatible_requirements`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_guided_ui.py::test_conflict_action_selects_participant_when_user_wants_to_edit`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_interview_completion.py::test_plan_review_lives_inline_with_all_content_actions[light]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_interview_completion.py::test_plan_review_lives_inline_with_all_content_actions[dark]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_interview_coverage.py::test_repair_and_failure_do_not_consume_interview_rounds`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_m1.py::test_assets_load_exact_current_versions`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_m1.py::test_questions_are_rejected_when_budget_is_zero`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_m1_interpretation_guidance.py::test_existing_output_without_interpretation_extension_remains_valid`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_m1_interpretation_guidance.py::test_new_resources_keep_legacy_contract_and_do_not_encode_jgs_answer`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_m1_model_authority_v07.py::test_v08_assets_make_quality_decision_model_led`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_m1_model_authority_v07.py::test_m1_gives_model_one_contextual_self_correction_attempt`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_m1_model_authority_v07.py::test_m1_gives_model_two_content_correction_attempts`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_m1_model_authority_v07.py::test_input_error_is_repaired_as_a_normal_interview_response`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_m1_model_authority_v11.py::test_v021_correction_prompt_makes_model_judgment_mandatory`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_m1_model_authority_v11.py::test_v021_semantic_bridge_requires_continuable_normal_interview`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_m1_model_bridge_v08.py::test_old_skipped_question_is_not_repeated_without_new_context`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_m1_model_recovery_v09.py::test_repeated_semantic_input_error_becomes_continuable_interview`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_m1_semantic_bridge_v10.py::test_semantic_input_error_uses_a_context_bridge_prompt`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_model_effort_parameters.py::test_deepseek_documented_effort_mapping_across_all_request_types[low-low-deepseek-flash-anthropic_messages]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_model_effort_parameters.py::test_deepseek_documented_effort_mapping_across_all_request_types[low-low-deepseek-v4-pro-anthropic_messages]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_model_effort_parameters.py::test_deepseek_documented_effort_mapping_across_all_request_types[medium-high-deepseek-flash-anthropic_messages]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_model_effort_parameters.py::test_deepseek_documented_effort_mapping_across_all_request_types[medium-high-deepseek-v4-pro-anthropic_messages]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_model_effort_parameters.py::test_deepseek_documented_effort_mapping_across_all_request_types[high-high-deepseek-flash-anthropic_messages]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_model_effort_parameters.py::test_deepseek_documented_effort_mapping_across_all_request_types[high-high-deepseek-v4-pro-anthropic_messages]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_model_effort_parameters.py::test_deepseek_documented_effort_mapping_across_all_request_types[max-max-deepseek-flash-anthropic_messages]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_model_effort_parameters.py::test_deepseek_documented_effort_mapping_across_all_request_types[max-max-deepseek-v4-pro-anthropic_messages]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_model_effort_parameters.py::test_latest_claude_uses_adaptive_effort_and_preserves_format[claude-fable-5-1]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_model_effort_parameters.py::test_latest_claude_uses_adaptive_effort_and_preserves_format[claude-opus-5-5]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_model_effort_parameters.py::test_latest_claude_uses_adaptive_effort_and_preserves_format[claude-sonnet-5-5]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_model_effort_parameters.py::test_latest_claude_uses_adaptive_effort_and_preserves_format[claude-haiku-5-5]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_release_chain.py::test_source_release_chain_uses_http_and_persists_final_artifacts`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_reliability.py::test_same_field_scope_known_requirement_does_not_close_budget_unknown`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_reliability.py::test_different_scopes_can_repeat_field_but_same_scope_cannot`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_startup_model_directory.py::test_manual_fetch_supersedes_inflight_startup_result`|通过|当前隔离复验通过；完整运行稳定性待定位|
|`tests/test_startup_model_directory.py::test_startup_directory_uses_saved_protocol_and_auth[DeepSeek-OpenAI Chat Completions-/v1/models-Bearer disposable-protocol]`|通过|当前隔离复验通过；完整运行稳定性待定位|
|`tests/test_startup_model_directory.py::test_startup_directory_uses_saved_protocol_and_auth[OpenAI-OpenAI Responses-/v1/models-Bearer disposable-protocol]`|通过|当前隔离复验通过；完整运行稳定性待定位|
|`tests/test_startup_model_directory.py::test_startup_directory_uses_saved_protocol_and_auth[Anthropic-Anthropic Messages-/v1/models?limit=1000-disposable-protocol]`|通过|当前隔离复验通过；完整运行稳定性待定位|
|`tests/test_status_version_label.py::test_status_label_matches_the_loaded_prompt_assets`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_status_version_label.py::test_m1_current_prompt_file_exists_and_matches_the_declared_version`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_stop_transport.py::test_stop_interrupts_blocked_stream_read_without_waiting_for_next_chunk`|通过|当前隔离复验通过；完整运行稳定性待定位|
|`tests/test_stream_service_errors.py::test_service_error_is_visible_in_api_failure_debug_and_stream_feedback`|通过|当前隔离复验通过；完整运行稳定性待定位|
|`tests/test_stream_service_errors.py::test_failed_response_preserves_nested_service_reason_usage_and_partial_output`|通过|当前隔离复验通过；完整运行稳定性待定位|
|`tests/test_stream_service_errors.py::test_stream_error_details_are_redacted_and_complete_in_debug[openai_chat_completions-deepseek-flash]`|通过|当前隔离复验通过；完整运行稳定性待定位|
|`tests/test_stream_service_errors.py::test_stream_error_details_are_redacted_and_complete_in_debug[openai_responses-gpt-6.1-sol]`|通过|当前隔离复验通过；完整运行稳定性待定位|
|`tests/test_task_input_sync.py::test_typing_updates_label_and_connection_changes_without_sync`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_task_input_sync.py::test_paste_cut_and_undo_refresh_without_mutating_session[right_click]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_task_input_sync.py::test_paste_cut_and_undo_refresh_without_mutating_session[ctrl_v]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_task_input_sync.py::test_questions_remain_primary_for_unchanged_visible_task`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_task_result_guidance.py::test_jgs_missing_result_has_visible_offer_and_one_click_to_m2`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_task_result_guidance.py::test_missing_result_reveals_specific_question_if_model_has_not_identified_it`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_thinking_level_ui.py::test_thinking_level_choice_is_plainly_selectable_and_reaches_m1`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_ui_clarity.py::test_picker_cache_reused_check_centered_and_no_extra_actions`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_ui_contract.py::test_ui_current_custom_service_and_protocol_select_real_m1_adapter`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_ui_contract.py::test_ui_current_custom_service_and_protocol_select_real_m2_adapter`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_ui_delivery_interactions.py::test_selected_catalog_record_change_marks_final_stale_and_blocks_confirmation`|通过|当前隔离复验通过；完整运行稳定性待定位|
|`tests/test_ui_refinement.py::test_top_panel_is_read_only_bounded_and_closes_on_new_session[summary]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_ui_reliability.py::test_complete_ui_path_allows_answer_before_draft_review_and_round_trips`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_ui_settings.py::test_default_window_fits_screen_at_16_9[screen0-expected0]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_ui_settings.py::test_default_window_fits_screen_at_16_9[screen1-expected1]`|失败|原有失败，待按当前合同或业务问题核查|
|`tests/test_ui_settings.py::test_default_window_fits_screen_at_16_9[screen2-expected2]`|失败|原有失败，待按当前合同或业务问题核查|

## 可定位证据

完整运行XML、控制台文本、before投影与失败逐项JSON、最后节点去重JSON、原生结果和截图保存于忽略的 `local_artifacts/tutorial_20261013/`。对应文件名：

- `full-regression.xml` / `full-regression.txt`
- `failure-baseline.xml` / `failure-baseline.txt` / `failure-comparison.json`
- `final-focused.xml` / `final-focused.txt`
- `transport-recheck.xml` / `catalog-recheck.xml`
- `latest-node-results.json`
- `native-results.json`、`light-goal.png`、`dark-settings.png`
- `prior_native/*/native-results.json`

Code-review按本轮工作树before增量复核，Spec/Standards最终各0待修；静态复审不能替代上述执行证据。
