# 逐步整改计划

2026-10-11 修复后状态：TASK-001～013全部verified，TASK-015维持既有verified；TASK-014真实平台/EXE/服务补证仍blocked。完成范围、红绿证据及13项映射见[验收](../../../verification/frontend_fixes_20261011/results.md)。

原审查阶段为audit_plan，当时13项修复均未实施；本轮已按以下任务完成修复与复验。TASK-015是审查时已完成的补验。实际实施先恢复当前会话取消和键盘核对，再修共享浮层/小窗布局，最后清理诊断和测试契约；沿用WebView2。

共享改动顺序：makePopup命名/placement → 焦点进入返回 → 每调用者菜单模式；其它任务仅在依赖明确时排序。保持本次已验证的滑块/连续动画、默认字体、SessionState、DPAPI和手动日志。

## TASK-001 · 整合提示词忙态没有可见取消入口

阶段：1；负责人：前端/UI开发；状态：verified。依赖：无。

位置：resources/ui/workspace/workspace.js:33

- 渲染显式cancel_request，沿用command("button")/cancel_delivery_request和request scope；不能解除所有业务保护。
- 同步Debug诊断：事件、阶段、完整exception cause与脱敏；不自动写日志。

验收：模拟未返回整合→点取消→当前会话解锁；迟到内容丢弃，仍可重试/直接生成。

验证场景：SCN-001。

恢复：按局部补丁恢复展示/事件层，保留SessionState/DPAPI/历史格式与已保存数据；不恢复已取消旧产品能力。

风险：焦点/动画/版本检查互相影响；修复不绕过业务确认。

## TASK-002 · 最大字号下小窗header越界

阶段：2；负责人：前端/UI开发；状态：verified。依赖：无。

位置：resources/ui/workspace/index.html:5; resources/ui/workspace/workspace.js:32

- 按可用内容宽度让header换行/收纳，调整expanded断点；避免删任务入口或压缩字体回避。
- 同步Debug诊断：事件、阶段、完整exception cause与脱敏；不自动写日志。

验收：720×440/font9/12/18，展开/收起，长标题及浅深主题检查每一header控件不被截断。

验证场景：SCN-002。

恢复：按局部补丁恢复展示/事件层，保留SessionState/DPAPI/历史格式与已保存数据；不恢复已取消旧产品能力。

风险：焦点/动画/版本检查互相影响；修复不绕过业务确认。

## TASK-003 · 小窗大字号设置正文与保存区域被挤出

阶段：2；负责人：前端/UI开发；状态：verified。依赖：无。

位置：resources/ui/workspace/workspace.js:32; resources/ui/workspace/workspace.js:197; resources/ui/workspace/settings.js:54; resources/ui/workspace/settings.js:15; resources/ui/workspace/settings.js:37; resources/ui/workspace/settings.js:75

- 设置单一有界滚动，短窗允许footer入滚动内容或sticky精简；不要扩大应用最小窗口掩盖合法组合。
- 同步Debug诊断：事件、阶段、完整exception cause与脱敏；不自动写日志。

验收：干净与有草稿/错误长文两状态，五类在720×440/font18均能读完并点击完整保存按钮。

验证场景：SCN-003。

恢复：按局部补丁恢复展示/事件层，保留SessionState/DPAPI/历史格式与已保存数据；不恢复已取消旧产品能力。

风险：焦点/动画/版本检查互相影响；修复不绕过业务确认。

## TASK-004 · 模型浮层上界未约束，搜索和首供应商被裁切

阶段：2；负责人：前端/UI开发；状态：verified。依赖：无。

位置：resources/ui/workspace/workspace.js:260; resources/ui/workspace/workspace.js:309; resources/ui/workspace/workspace.js:334

- 内容完成后测量；按可用上/下空间选择placement，夹取四边，模型列表承担剩余高度；resize重算。
- 同步Debug诊断：事件、阶段、完整exception cause与脱敏；不自动写日志。

验收：重放四个font12/18+rail组合，菜单bounds>=0且<=viewport；查询输入与首供应商可点击。

验证场景：SCN-004。

恢复：按局部补丁恢复展示/事件层，保留SessionState/DPAPI/历史格式与已保存数据；不恢复已取消旧产品能力。

风险：焦点/动画/版本检查互相影响；修复不绕过业务确认。

## TASK-005 · 公共dialog浮层缺可访问名称

阶段：2；负责人：前端/UI开发；状态：verified。依赖：无。

位置：resources/ui/workspace/workspace.js:260

- makePopup接收label或labelledby/trigger；dialog显式命名，文件/选择菜单使用menu契约。
- 同步Debug诊断：事件、阶段、完整exception cause与脱敏；不自动写日志。

验收：逐个模型、需求、方案、摘要、结果和菜单检查可访问树名称/角色，真实读屏再验。

验证场景：SCN-005。

恢复：按局部补丁恢复展示/事件层，保留SessionState/DPAPI/历史格式与已保存数据；不恢复已取消旧产品能力。

风险：焦点/动画/版本检查互相影响；修复不绕过业务确认。

## TASK-006 · 浮层焦点进入、返回及展开语义不完整

阶段：2；负责人：前端/UI开发；状态：verified。依赖：TASK-005。

位置：resources/ui/workspace/workspace.js:32; resources/ui/workspace/workspace.js:260; resources/ui/workspace/history.js:56

- 存储触发器稳定标识（history id+action），打开初始化焦点；关闭重新查询fallback。非模态panel不强制trap；history模态保留现有trap。
- 同步Debug诊断：事件、阶段、完整exception cause与脱敏；不自动写日志。

验收：鼠标/Enter打开、Tab/ShiftTab、Escape、点外部、快速替换；后台快照重建时焦点仍有业务上下文。

验证场景：SCN-006。

恢复：按局部补丁恢复展示/事件层，保留SessionState/DPAPI/历史格式与已保存数据；不恢复已取消旧产品能力。

风险：焦点/动画/版本检查互相影响；修复不绕过业务确认。

## TASK-007 · 需求表只有鼠标选择，键盘无法编辑指定需求

阶段：1；负责人：前端/UI开发；状态：verified。依赖：无。

位置：resources/ui/workspace/workspace.js:290

- 每行加入原生单选/按钮或完整grid键盘模式；优先简单原生入口，传同一id保留后端selection校验。
- 同步Debug诊断：事件、阶段、完整exception cause与脱敏；不自动写日志。

验收：仅键盘选proposal/confirmed行，读全文、修改/取消、移除/取消；ID过期不误改邻行。

验证场景：SCN-007。

恢复：按局部补丁恢复展示/事件层，保留SessionState/DPAPI/历史格式与已保存数据；不恢复已取消旧产品能力。

风险：焦点/动画/版本检查互相影响；修复不绕过业务确认。

## TASK-008 · 收起思考后不可见内容仍进入Tab顺序

阶段：2；负责人：前端/UI开发；状态：verified。依赖：无。

位置：resources/ui/workspace/workspace.js:127; resources/ui/workspace/workspace.js:161

- 关闭开始设置inert；若包含焦点先回展开器；打开解除。别删连续展开动画。
- 同步Debug诊断：事件、阶段、完整exception cause与脱敏；不自动写日志。

验收：外/内两层分别关闭，Tab及ShiftTab跳过所有隐藏后代；动画反转和stream完成时保持一致。

验证场景：SCN-008。

恢复：按局部补丁恢复展示/事件层，保留SessionState/DPAPI/历史格式与已保存数据；不恢复已取消旧产品能力。

风险：焦点/动画/版本检查互相影响；修复不绕过业务确认。

## TASK-009 · 搜索和重命名Enter未保护中文组合输入

阶段：2；负责人：前端/UI开发；状态：verified。依赖：无。

位置：resources/ui/workspace/workspace.js:309; resources/ui/workspace/history.js:66

- 抽出共享组合输入判断并应用三个入口，按Edge154真实事件序列补验，不无理由扩大全站快捷键拦截。
- 同步Debug诊断：事件、阶段、完整exception cause与脱敏；不自动写日志。

验收：单元注入与真实Windows中文输入法均验：候选Enter不dispatch；正常Enter只一次。

验证场景：SCN-009。

恢复：按局部补丁恢复展示/事件层，保留SessionState/DPAPI/历史格式与已保存数据；不恢复已取消旧产品能力。

风险：焦点/动画/版本检查互相影响；修复不绕过业务确认。

## TASK-010 · 设置Tab声明角色但缺方向键与单TabStop

阶段：2；负责人：前端/UI开发；状态：verified。依赖：无。

位置：resources/ui/workspace/settings.js:54

- 复用供应商tab现有键盘模式，按水平设置Left/Right；状态由category唯一拥有。
- 同步Debug诊断：事件、阶段、完整exception cause与脱敏；不自动写日志。

验收：键盘遍历五类、保持未保存连接/数字草稿、返回再开；只有选中Tab在TabStop。

验证场景：SCN-010。

恢复：按局部补丁恢复展示/事件层，保留SessionState/DPAPI/历史格式与已保存数据；不恢复已取消旧产品能力。

风险：焦点/动画/版本检查互相影响；修复不绕过业务确认。

## TASK-011 · Debug同步恢复后残留过期红色错误

阶段：3；负责人：前端/UI开发；状态：verified。依赖：无。

位置：resources/ui/workspace/debug.js:22

- 错误按operation归属；成功poll只清sync错误，动作结果清各自错误；更新Debug生命周期测试。
- 同步Debug诊断：事件、阶段、完整exception cause与脱敏；不自动写日志。

验收：同步失败→恢复、保存失败→同步成功、复制失败→重试成功三序列分别核对。

验证场景：SCN-011。

恢复：按局部补丁恢复展示/事件层，保留SessionState/DPAPI/历史格式与已保存数据；不恢复已取消旧产品能力。

风险：焦点/动画/版本检查互相影响；修复不绕过业务确认。

## TASK-012 · 原生保存创建目录失败未进入恢复提示

阶段：3；负责人：前端/UI开发；状态：verified。依赖：无。

位置：resources/ui/workspace/workspace.js:307; src/promptsmith/web_workspace.py:112; src/promptsmith/ui.py:4990

- 目录准备/选择/实际保存统一异常边界，明确无权限提示；保留用户取消为正常退出，Debug含完整cause。
- 同步Debug诊断：事件、阶段、完整exception cause与脱敏；不自动写日志。

验收：mkdir、写入、rename权限失败与用户取消分别验；原生与Web都保留当前会话，另存可恢复。

验证场景：SCN-012。

恢复：按局部补丁恢复展示/事件层，保留SessionState/DPAPI/历史格式与已保存数据；不恢复已取消旧产品能力。

风险：焦点/动画/版本检查互相影响；修复不绕过业务确认。

## TASK-013 · 14项旧UI测试仍依赖退役控件和旧合同

阶段：3；负责人：测试维护者；状态：verified。依赖：无。

位置：tests/test_experience_iteration.py; tests/test_guided_ui.py; tests/test_ui_delivery_interactions.py; tests/test_composer.py; tests/test_ui_contract.py

- 逐项迁移断言到当前入口和同等用户结果；保留历史失败记录；不可为测试恢复已删除界面或盲删安全断言。
- 同步Debug诊断：事件、阶段、完整exception cause与脱敏；不自动写日志。

验收：当前14失败节点迁移后专项通过，需求确认/冲突/复制/多行编辑等原目标继续保留。

验证场景：SCN-013。

恢复：按局部补丁恢复展示/事件层，保留SessionState/DPAPI/历史格式与已保存数据；不恢复已取消旧产品能力。

风险：焦点/动画/版本检查互相影响；修复不绕过业务确认。

## TASK-014 · 补齐平台与真实服务验收

阶段：4；负责人：Windows验收者/模型集成开发；状态：blocked。依赖：TASK-001,TASK-002,TASK-003,TASK-004,TASK-005,TASK-006,TASK-007,TASK-008,TASK-009,TASK-010,TASK-011,TASK-012,TASK-013。

位置：verification/ 下一批验收记录；PromptSmith.spec；真实Windows目标设备

- 按verification-handoff逐条运行真实候选输入/读屏/跨DPI/180Hz和独立EXE测试
- 真实模型及联网Skill仅使用下一轮获准凭据和预算；保留失败样本、推荐结果与完整脱敏日志

验收：每个blocked检查附对应环境/步骤/结果，不以DOM模拟替代真实平台；13项本轮问题复验及EXE/真实模型界限分别报告

验证场景：SCN-048。

恢复：只补证；如需应用改动另以局部任务执行，不操作用户原历史或覆盖生产settings。

风险：服务成本、不同电脑运行时与输入法事件差异；当前不能承诺180Hz或完整WCAG符合性。

## TASK-015 · 补齐本地逐实例条件动作与生命周期证据

阶段：0；负责人：UI开发/离线验收；状态：verified。依赖：无。

位置：各CMP定位；本目录scripts与evidence

- 按not_checked检查逐实例补合法状态/动作，不用页面构造替代回调
- 性能仅测实际独立计时器/缓存/布局；无独立生命周期的静态叶子注明归属父单元

验收：not_checked逐条闭合，证据包含实例、前提、步骤、结果；继续区分真实平台blocked，不伪造通过

验证场景：SCN-049。

恢复：只增补隔离证据，恢复临时目录，不写个人配置或修改应用。

风险：原生条件控件和测试旧合同可能混淆；保持明确当前入口。
