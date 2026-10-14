# 阶段按钮均分与附注精简（2026-10-14）

本项为用户暂停全量审查后的第二个新问题。第一项 Skill 区域显隐已完成；第三项仍待用户提供，完整组合回归继续延后。

## 范围与验收

- 需求核对删除“采用选中修改”，保留修改、移除和确认；方案操作、Skill 查找三按钮与选用后的五按钮，均使用提供的玻璃按钮参考样式并等宽铺满整行。
- 结果删除“保存会话”和“确认最终提示词”，保留复制、导出与“附注”三个玻璃按钮。附注面板只提供添加附注，不再提供语气切换或重复的附注列表。
- 浅深主题、悬停/按下动画、禁用及减少动画偏好保持；窄窗口按卡片宽度换行，每行等宽铺满，不截断文字或制造横向滚动。
- 保留文件菜单保存、既有业务确认方法与旧会话语气数据。SessionState、请求与版本检查、Tk owner 线程不改变。显式 Tk 兼容界面的控件删减及标签同步；本次玻璃均分布局针对正常 WebView2 工作区。

## 根因与实现

`workspace.js` 的通用 `actions()` 原本创建按内容宽度排列的 flex 按钮，右侧因此留下大面积空白。结果的附注入口单独放在该行外；`renderReview()` 同时提供语气选择。Tk owner 生成的操作字典也包含待删除入口，需求选择更新器还直接引用采用按钮，不能只隐藏浏览器节点。

- `workspace.js/css`：阶段行按实际可见操作数生成等宽 grid，需求、方案、Skill 与结果共用。玻璃外缘、阴影、遮光层和光带按用户参考复刻，保留250ms动画；遵循用户先前要求，不恢复额外锐利内圈。卡片宽度不超过700px时两列，奇数末项铺满；不超过380px时单列。
- `conversation.py`：删需求采用控件及其选择更新依赖；删结果保存/最终确认控件；“语气和附注”改“附注”，面板只添加附注。
- 添加附注继续使用现有 Web note editor 和 SessionState finalization 路径，不新增模型请求，不调整旧 tone。文件菜单仍可保存会话。
- Debug：阶段行渲染记录操作 keys、数量及均分布局；附注控件渲染记录可用状态和无语气控件。现有编辑生命周期日志继续覆盖打开/保存/取消/失败；不记录正文或密钥，不增加逐帧事件和自动日志文件。

## 定点反馈

公开边界沿用现有授权：生产 Chromium DOM、WorkspaceController/Tk owner 操作、SessionState 与保存重开。仅执行本问题的红绿反馈和受改动影响的定点检查，没有恢复逐页审查或完整组合回归。

1. 正确红灯复现：阶段行最右侧空白510.5px。初次测试未补完整方案动作的旧演示快照，得到2个按钮，属于夹具合同问题；按现有真实动作补齐后，断言确实捕获整行留白。
2. 第一版修复5失败/7通过：后置 `.actions {display:flex}` 覆盖 `.stage-actions` 的同级选择器。改为 `.actions.stage-actions` 后解决；没有放宽均分断言。
3. `python -X utf8 -m pytest tests/test_action_rows_browser.py --tb=short -p no:cacheprovider --show-capture=no`：当时12项通过，20.19秒。覆盖五种按钮数量/阶段×浅色1440px/深色720px、均分铺满、无溢出、删除控件、附注只添加、动作派发及减少动画。
4. `python -X utf8 -m pytest tests/test_conversation_requirements_table.py::test_table_keeps_ai_interpretation_and_replacement_actions_explicit tests/test_skipped_delivery.py::test_result_options_stay_in_conversation_and_update_prompt --tb=short -p no:cacheprovider --show-capture=no`：旧采用按钮测试1失败，附注浅深2项通过，16.31秒。旧测试仍引用已按用户要求删除的控件；不是编辑卡死或附注写入失败。
5. 将该旧测试更新为待确认解释/替换项可选、可编辑、可移除且无采用入口，经真实 Controller 操作验证，不删除后台采用业务方法。
6. `python -X utf8 -m pytest tests/test_conversation_requirements_table.py tests/test_action_rows_browser.py::test_actual_result_controls_open_web_note_editor_and_preserve_saved_tone --tb=short -p no:cacheprovider --show-capture=no`：6项通过，16.14秒。含长文本表格、编辑使旧成果失效、移除/重开、忙态、待确认项编辑移除，以及真实 Controller 快照→生产 DOM→Web附注编辑保存→保留旧语气/保存重开。

最新20个不同定点节点通过；新增浏览器测试文件现为13项，其中最后新增的Controller联动节点单独执行通过，前12项没有因测试追加而重复运行。仅生产 Chrome DOM与隔离Tk/Controller；未执行实际WebView2或EXE验收，未调用真实模型、读取个人配置、提交或推送。

静态检查：4个Python文件AST、workspace.js语法与5个增量文件空白检查通过。增量基线在忽略的 `local_artifacts/action_rows_20261014/before/`，比较本项源码及测试，不将整个未提交工作树归于本次改动。

独立只读增量复核完成：Spec 0发现；Standards硬违反0、判断性异味0。两轴仅比较本项增量且没有重复运行测试。收尾5个已有增量文件及1个新增测试的空白检查、新增维护链接检查通过；检查脚本两次把Git的LF/CRLF转换警告当作失败，最终改用命令局部`core.safecrlf=false`后通过，未修改仓库配置或文件换行。CodeGraph同步5个文件后current（290 files / 7103 nodes / 21315 edges）。完整组合回归仍等待第三项。

2026-10-14 本批收尾：第三项简介评分已完成，S1–S3和相邻路径326个不同节点最新全部通过，两轴各0待修。本页初期的延期说明已结束；全项目审查仍暂停，原始组合失败及夹具纠正见[第三项与组合回归](skill_summary_scoring_20261014.md)。
