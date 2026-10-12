# 确认问题与复验

13个合并根因（2项P1、11项P2）已修复并完成本地复验，当前均resolved。原失败描述与证据保留用于追溯；真实系统IME/读屏/EXE等仍见TASK-014，不据此宣称发布就绪。

|问题|修复摘要|本轮证据|
|---|---|---|
|FND-001|忙态投影漏掉取消。显示原取消动作，按动作签名保留节点与焦点；沿用真实请求取消及迟到隔离。|EV-023；[red-001.txt](../../../verification/frontend_fixes_20261011/red-001.txt)|
|FND-002|侧栏占宽后操作行不换行。顶部按剩余宽度换行，覆盖浅深、侧栏双态及9/12/18字号。|EV-024；[red-002.txt](../../../verification/frontend_fixes_20261011/red-002.txt)|
|FND-003|正文收缩使保存区超出短窗。改为小窗整页滚动，五类均可读且保存可达，错误与草稿仍保留。|EV-025；[red-003.txt](../../../verification/frontend_fixes_20261011/red-003.txt)|
|FND-004|内容挂载前测量且上边界未夹取。ResizeObserver/rAF在内容完成后测量，限制四边，resize重排并关闭清理。|EV-026；[red-004.txt](../../../verification/frontend_fixes_20261011/red-004.txt)|
|FND-005|公共浮层无名称、用途都套dialog。添加中文名称，并按用途区分具名dialog/menu及menuitem键盘契约。|EV-027；[red-005.txt](../../../verification/frontend_fixes_20261011/red-005.txt)|
|FND-006|入口节点重建后旧引用失效。稳定入口标识支持打开入焦、关闭返回，关闭阶段inert，展开状态同步。|EV-028；[red-006.txt](../../../verification/frontend_fixes_20261011/red-006.txt)|
|FND-007|行仅响应click。新增原生选择按钮；桥接成功后更新，pending/忙态禁用，失败保留后台有效选择。|EV-029；[red-007.txt](../../../verification/frontend_fixes_20261011/red-007.txt)|
|FND-008|只视觉裁切，隐藏内容仍进入Tab。两层折叠设inert，内部焦点归还展开器；保留连续反向动画。|EV-030；[red-008.txt](../../../verification/frontend_fixes_20261011/red-008.txt)|
|FND-009|模型搜索、历史搜索及重命名缺组合输入保护。isComposing/keyCode229时不派发Enter，普通Enter仍执行。|EV-031；[red-009.txt](../../../verification/frontend_fixes_20261011/red-009.txt)|
|FND-010|只有tab角色而无键盘合同。添加左右/Home/End切换与单一Tab入口，编辑草稿保留。|EV-032；[red-010.txt](../../../verification/frontend_fixes_20261011/red-010.txt)|
|FND-011|同步与操作错误共用字段。分操作保留错误，成功同步只清同步错误并记录INFO，复制等错误仍可见。|EV-033；[red-011.txt](../../../verification/frontend_fixes_20261011/red-011.txt)|
|FND-012|创建目录及文件选择在异常边界外。统一捕获mkdir/chooser/write/replace故障，保留旧文件/会话并提示更换目录后另存；正常取消无误报。|EV-034；[red-012.txt](../../../verification/frontend_fixes_20261011/red-012.txt)|
|FND-013|旧控件/选项/跳过/模型数合同未同步。迁移到需求弹层、逐题回答、明确跳过及8款OpenAI，保留原业务断言；相邻可靠性旧入口也同步。|EV-035；[red-013.xml](../../../verification/frontend_fixes_20261011/red-013.xml)|

最新汇总：[修复验收](../../../verification/frontend_fixes_20261011/results.md)。

## FND-001 · P1 · 整合提示词忙态没有可见取消入口

位置：PAGE-002；DEF-009。实例：CMP-462。

实际：真实busy快照有cancel_request，Web无对应按钮；用户只能等请求或切换会话。

预期与影响：整合期间可取消当前请求并保留本会话与已选Skill。 整合期间可取消当前请求并保留本会话与已选Skill。目前不能保证；整合等待时不能在当前会话停止。

根因（confirmed）：workspace.js只消费列举卡片动作；recovery受!locked限制，遗漏动态cancel_request投影。

复现：真实busy快照有cancel_request，Web无对应按钮；用户只能等请求或切换会话。；按evidence对应脚本重放并检查原始actual/expected值

证据：EV-005,EV-014（[台账证据索引](audit.json)）。

修改机制：渲染显式cancel_request，沿用command("button")/cancel_delivery_request和request scope；不能解除所有业务保护。

复验：模拟未返回整合→点取消→当前会话解锁；迟到内容丢弃，仍可重试/直接生成。

负责人：前端/UI开发；任务：TASK-001；状态resolved。修复：忙态投影漏掉取消。显示原取消动作，按动作签名保留节点与焦点；沿用真实请求取消及迟到隔离。 复验：EV-023、EV-036，原失败EV保留。

## FND-002 · P2 · 最大字号下小窗header越界

位置：PAGE-001；DEF-001,DEF-004。实例：CMP-001,CMP-008,CMP-009,CMP-010,CMP-011。

实际：720×440/font18展开侧栏，header右端超出窗口，设置按钮无法完整看见。

预期与影响：合法最小窗口与设置字号组合下顶部核心操作可达。 合法最小窗口与设置字号组合下顶部核心操作可达。目前不能保证；可恢复但影响操作/诊断或回归可信度。

根因（confirmed）：展开侧栏固定占258px，header-actions不换行，响应式缩短仅覆盖收起侧栏。

复现：720×440/font18展开侧栏，header右端超出窗口，设置按钮无法完整看见。；按evidence对应脚本重放并检查原始actual/expected值

证据：EV-005,EV-011（[台账证据索引](audit.json)）。

修改机制：按可用内容宽度让header换行/收纳，调整expanded断点；避免删任务入口或压缩字体回避。

复验：720×440/font9/12/18，展开/收起，长标题及浅深主题检查每一header控件不被截断。

负责人：前端/UI开发；任务：TASK-002；状态resolved。修复：侧栏占宽后操作行不换行。顶部按剩余宽度换行，覆盖浅深、侧栏双态及9/12/18字号。 复验：EV-024、EV-036，原失败EV保留。

## FND-003 · P2 · 小窗大字号设置正文与保存区域被挤出

位置：PAGE-017,PAGE-018,PAGE-019,PAGE-020,PAGE-021；DEF-004,DEF-017,DEF-036,DEF-037,DEF-038,DEF-039。实例：CMP-126,CMP-127,CMP-128,CMP-129,CMP-130,CMP-131,CMP-132,CMP-133,CMP-134,CMP-135,CMP-136,CMP-137,CMP-138,CMP-139,CMP-140,CMP-141,CMP-142,CMP-143,CMP-144,CMP-145,CMP-146,CMP-147,CMP-148,CMP-149,CMP-150,CMP-151,CMP-152,CMP-153,CMP-154,CMP-155,CMP-156,CMP-157,CMP-158,CMP-159,CMP-160,CMP-161,CMP-162,CMP-163,CMP-164,CMP-165,CMP-166,CMP-167,CMP-168,CMP-169,CMP-170,CMP-171,CMP-172,CMP-173,CMP-174,CMP-175,CMP-176,CMP-177,CMP-178,CMP-179,CMP-180,CMP-181,CMP-182,CMP-183,CMP-184,CMP-185,CMP-186,CMP-187,CMP-188,CMP-189,CMP-190,CMP-191,CMP-192,CMP-193,CMP-194。

实际：清洁720×440/font18：五类scroll仅36px；footer底488.5px，保存按钮跨422.5–488.5px，超过440px窗口。

预期与影响：设置正文可阅读且保存/恢复/返回全部能滚动到达。 设置正文可阅读且保存/恢复/返回全部能滚动到达。目前不能保证；可恢复但影响操作/诊断或回归可信度。

根因（confirmed）：settings布局将heading/tabs/footer固定而scroll独自收缩；父容器overflow hidden无整页补偿。

复现：清洁720×440/font18：五类scroll仅36px；footer底488.5px，保存按钮跨422.5–488.5px，超过440px窗口。；按evidence对应脚本重放并检查原始actual/expected值

证据：EV-005,EV-006,EV-011（[台账证据索引](audit.json)）。

修改机制：设置单一有界滚动，短窗允许footer入滚动内容或sticky精简；不要扩大应用最小窗口掩盖合法组合。

复验：干净与有草稿/错误长文两状态，五类在720×440/font18均能读完并点击完整保存按钮。

负责人：前端/UI开发；任务：TASK-003；状态resolved。修复：正文收缩使保存区超出短窗。改为小窗整页滚动，五类均可读且保存可达，错误与草稿仍保留。 复验：EV-025、EV-036，原失败EV保留。

## FND-004 · P2 · 模型浮层上界未约束，搜索和首供应商被裁切

位置：PAGE-009；DEF-022,DEF-026,DEF-027。实例：CMP-081,CMP-082,CMP-083,CMP-084,CMP-085,CMP-086,CMP-087,CMP-088,CMP-089。

实际：展开720×440：font12菜单top=-21px，font18=-78px且搜索top=-67px；收起font18菜单top=-3.5px。

预期与影响：菜单搜索、五供应商和四档强度在窗口内，可通过内部滚动查看模型。 菜单搜索、五供应商和四档强度在窗口内，可通过内部滚动查看模型。目前不能保证；可恢复但影响操作/诊断或回归可信度。

根因（confirmed）：makePopup在填入内容前测量；用anchor bottom推位置，未针对最终高度钳制top。

复现：展开720×440：font12菜单top=-21px，font18=-78px且搜索top=-67px；收起font18菜单top=-3.5px。；按evidence对应脚本重放并检查原始actual/expected值

证据：EV-006,EV-011（[台账证据索引](audit.json)）。

修改机制：内容完成后测量；按可用上/下空间选择placement，夹取四边，模型列表承担剩余高度；resize重算。

复验：重放四个font12/18+rail组合，菜单bounds>=0且<=viewport；查询输入与首供应商可点击。

负责人：前端/UI开发；任务：TASK-004；状态resolved。修复：内容挂载前测量且上边界未夹取。ResizeObserver/rAF在内容完成后测量，限制四边，resize重排并关闭清理。 复验：EV-026、EV-036，原失败EV保留。

## FND-005 · P2 · 公共dialog浮层缺可访问名称

位置：PAGE-005,PAGE-006,PAGE-007,PAGE-008,PAGE-009,PAGE-010,PAGE-011,PAGE-012；DEF-022。实例：CMP-058,CMP-067,CMP-075,CMP-077,CMP-081,CMP-096,CMP-100,CMP-103。

实际：模型与核对面板role=dialog没有aria-label/labelledby，标题div未关联。

预期与影响：dialog有各自用途名称；菜单使用与交互一致的menu角色。 dialog有各自用途名称；菜单使用与交互一致的menu角色。目前不能保证；可恢复但影响操作/诊断或回归可信度。

根因（confirmed）：makePopup统一role=dialog，调用者没有传名称；renderReview标题未赋ID。

复现：模型与核对面板role=dialog没有aria-label/labelledby，标题div未关联。；按evidence对应脚本重放并检查原始actual/expected值

证据：EV-002,EV-005（[台账证据索引](audit.json)）。

修改机制：makePopup接收label或labelledby/trigger；dialog显式命名，文件/选择菜单使用menu契约。

复验：逐个模型、需求、方案、摘要、结果和菜单检查可访问树名称/角色，真实读屏再验。

负责人：前端/UI开发；任务：TASK-005；状态resolved。修复：公共浮层无名称、用途都套dialog。添加中文名称，并按用途区分具名dialog/menu及menuitem键盘契约。 复验：EV-027、EV-036，原失败EV保留。

## FND-006 · P2 · 浮层焦点进入、返回及展开语义不完整

位置：PAGE-001,PAGE-005,PAGE-006,PAGE-007,PAGE-008,PAGE-009,PAGE-010,PAGE-011,PAGE-012,PAGE-013,PAGE-014,PAGE-015,PAGE-016；DEF-004,DEF-022,DEF-033。实例：CMP-058,CMP-067,CMP-075,CMP-077,CMP-081,CMP-096,CMP-100,CMP-103,CMP-108,CMP-112,CMP-116,CMP-121,CMP-008,CMP-009,CMP-010。

实际：review打开焦点仍在header；模型/深度Escape后焦点落body；rename退出时原行已重建导致returnFocus失效。review触发器无aria-expanded。

预期与影响：进入浮层时焦点到标题/首控件；关闭返回存活触发器，消失则合理后继；展开状态同步。 进入浮层时焦点到标题/首控件；关闭返回存活触发器，消失则合理后继；展开状态同步。目前不能保证；可恢复但影响操作/诊断或回归可信度。

根因（confirmed）：公共closePopup不保存anchor；review不focus。历史保存旧DOM节点但后台重建整行。

复现：review打开焦点仍在header；模型/深度Escape后焦点落body；rename退出时原行已重建导致returnFocus失效。review触发器无aria-expanded。；按evidence对应脚本重放并检查原始actual/expected值

证据：EV-005,EV-006,EV-002（[台账证据索引](audit.json)）。

修改机制：存储触发器稳定标识（history id+action），打开初始化焦点；关闭重新查询fallback。非模态panel不强制trap；history模态保留现有trap。

复验：鼠标/Enter打开、Tab/ShiftTab、Escape、点外部、快速替换；后台快照重建时焦点仍有业务上下文。

负责人：前端/UI开发；任务：TASK-006；状态resolved。修复：入口节点重建后旧引用失效。稳定入口标识支持打开入焦、关闭返回，关闭阶段inert，展开状态同步。 复验：EV-028、EV-036，原失败EV保留。

## FND-007 · P1 · 需求表只有鼠标选择，键盘无法编辑指定需求

位置：PAGE-005；DEF-023。实例：CMP-059,CMP-060,CMP-061。

实际：tbody tr没有tabIndex或button/input，仅click能选；键盘不能选择行读全文再编辑/移除。

预期与影响：键盘用户能选择任意需求、阅读详情并执行已授权核对。 键盘用户能选择任意需求、阅读详情并执行已授权核对。目前不能保证；键盘核心任务被阻断。

根因（confirmed）：renderReview用tr.click完成selection，没有相应键盘可聚焦选择入口。

复现：tbody tr没有tabIndex或button/input，仅click能选；键盘不能选择行读全文再编辑/移除。；按evidence对应脚本重放并检查原始actual/expected值

证据：EV-005,EV-002（[台账证据索引](audit.json)）。

修改机制：每行加入原生单选/按钮或完整grid键盘模式；优先简单原生入口，传同一id保留后端selection校验。

复验：仅键盘选proposal/confirmed行，读全文、修改/取消、移除/取消；ID过期不误改邻行。

负责人：前端/UI开发；任务：TASK-007；状态resolved。修复：行仅响应click。新增原生选择按钮；桥接成功后更新，pending/忙态禁用，失败保留后台有效选择。 复验：EV-029、EV-036，原失败EV保留。

## FND-008 · P2 · 收起思考后不可见内容仍进入Tab顺序

位置：PAGE-002；DEF-014,DEF-015。实例：CMP-031,CMP-032,CMP-033。

实际：关闭外trace后Tab进入隐藏子展开按钮；thought tabindex=0也仍可达。

预期与影响：视觉关闭区不可聚焦；展开后恢复原键盘路径，动画继续。 视觉关闭区不可聚焦；展开后恢复原键盘路径，动画继续。目前不能保证；可恢复但影响操作/诊断或回归可信度。

根因（confirmed）：reveal只使用grid0fr/opacity/overflow裁切，没有inert或tabindex状态处理。

复现：关闭外trace后Tab进入隐藏子展开按钮；thought tabindex=0也仍可达。；按evidence对应脚本重放并检查原始actual/expected值

证据：EV-005,EV-002（[台账证据索引](audit.json)）。

修改机制：关闭开始设置inert；若包含焦点先回展开器；打开解除。别删连续展开动画。

复验：外/内两层分别关闭，Tab及ShiftTab跳过所有隐藏后代；动画反转和stream完成时保持一致。

负责人：前端/UI开发；任务：TASK-008；状态resolved。修复：只视觉裁切，隐藏内容仍进入Tab。两层折叠设inert，内部焦点归还展开器；保留连续反向动画。 复验：EV-030、EV-036，原失败EV保留。

## FND-009 · P2 · 搜索和重命名Enter未保护中文组合输入

位置：PAGE-009,PAGE-014,PAGE-015；DEF-026,DEF-034。实例：CMP-082,CMP-083,CMP-084,CMP-113,CMP-117。

实际：注入isComposing=true/keyCode229的Enter：历史搜索触发open，重命名触发save，模型搜索触发model选择。真实系统候选序列尚未记录。

预期与影响：候选确认不执行打开/保存/模型选择，下一次正常Enter按约定操作。 候选确认不执行打开/保存/模型选择，下一次正常Enter按约定操作。目前不能保证；可恢复但影响操作/诊断或回归可信度。

根因（confirmed）：这些keydown分支直接处理Enter，未使用消息输入已有的composition保护。

复现：注入isComposing=true/keyCode229的Enter：历史搜索触发open，重命名触发save，模型搜索触发model选择。真实系统候选序列尚未记录。；按evidence对应脚本重放并检查原始actual/expected值

证据：EV-005,EV-006,EV-002（[台账证据索引](audit.json)）。

修改机制：抽出共享组合输入判断并应用三个入口，按Edge154真实事件序列补验，不无理由扩大全站快捷键拦截。

复验：单元注入与真实Windows中文输入法均验：候选Enter不dispatch；正常Enter只一次。

负责人：前端/UI开发；任务：TASK-009；状态resolved。修复：模型搜索、历史搜索及重命名缺组合输入保护。isComposing/keyCode229时不派发Enter，普通Enter仍执行。 复验：EV-031、EV-036，原失败EV保留。

## FND-010 · P2 · 设置Tab声明角色但缺方向键与单TabStop

位置：PAGE-017,PAGE-018,PAGE-019,PAGE-020,PAGE-021；DEF-036。实例：CMP-126,CMP-147,CMP-165,CMP-173,CMP-184。

实际：ArrowRight不切类别，五个role=tab都留在Tab序列；浅深一致。

预期与影响：tablist具方向键/Home/End与selected roving tabindex，字段草稿不丢。 tablist具方向键/Home/End与selected roving tabindex，字段草稿不丢。目前不能保证；可恢复但影响操作/诊断或回归可信度。

根因（confirmed）：selectCategory仅hidden与aria-selected，build未注册keydown/tabIndex。

复现：ArrowRight不切类别，五个role=tab都留在Tab序列；浅深一致。；按evidence对应脚本重放并检查原始actual/expected值

证据：EV-005,EV-002（[台账证据索引](audit.json)）。

修改机制：复用供应商tab现有键盘模式，按水平设置Left/Right；状态由category唯一拥有。

复验：键盘遍历五类、保持未保存连接/数字草稿、返回再开；只有选中Tab在TabStop。

负责人：前端/UI开发；任务：TASK-010；状态resolved。修复：只有tab角色而无键盘合同。添加左右/Home/End切换与单一Tab入口，编辑草稿保留。 复验：EV-032、EV-036，原失败EV保留。

## FND-011 · P2 · Debug同步恢复后残留过期红色错误

位置：PAGE-022；DEF-043。实例：CMP-203。

实际：snapshot先抛错再恢复成功，#debug-error仍显示同步未完成；新日志已正常显示。

预期与影响：成功同步清除该次同步错误，同时不误清复制/保存/目录错误。 成功同步清除该次同步错误，同时不误清复制/保存/目录错误。目前不能保证；可恢复但影响操作/诊断或回归可信度。

根因（confirmed）：poll.catch调用showError，成功分支不清，所有错误共用一个字符串。

复现：snapshot先抛错再恢复成功，#debug-error仍显示同步未完成；新日志已正常显示。；按evidence对应脚本重放并检查原始actual/expected值

证据：EV-005,EV-002（[台账证据索引](audit.json)）。

修改机制：错误按operation归属；成功poll只清sync错误，动作结果清各自错误；更新Debug生命周期测试。

复验：同步失败→恢复、保存失败→同步成功、复制失败→重试成功三序列分别核对。

负责人：前端/UI开发；任务：TASK-011；状态resolved。修复：同步与操作错误共用字段。分操作保留错误，成功同步只清同步错误并记录INFO，复制等错误仍可见。 复验：EV-033、EV-036，原失败EV保留。

## FND-012 · P2 · 原生保存创建目录失败未进入恢复提示

位置：PAGE-012,PAGE-034；DEF-031,DEF-061。实例：CMP-458,CMP-461,CMP-106,CMP-107。

实际：Path.mkdir权限失败从app.save直接抛出，_show_error未调用；Web外层有通用捕获，但原生用户没有保存位置的下一步提示。

预期与影响：失败保留会话和旧文件，提示选择其它目录或重试。 失败保留会话和旧文件，提示选择其它目录或重试。目前不能保证；可恢复但影响操作/诊断或回归可信度。

根因（confirmed）：创建默认目录在save的try之外，捕获只围绕_sync_input和save_session。

复现：Path.mkdir权限失败从app.save直接抛出，_show_error未调用；Web外层有通用捕获，但原生用户没有保存位置的下一步提示。；按evidence对应脚本重放并检查原始actual/expected值

证据：EV-015,EV-003（[台账证据索引](audit.json)）。

修改机制：目录准备/选择/实际保存统一异常边界，明确无权限提示；保留用户取消为正常退出，Debug含完整cause。

复验：mkdir、写入、rename权限失败与用户取消分别验；原生与Web都保留当前会话，另存可恢复。

负责人：前端/UI开发；任务：TASK-012；状态resolved。修复：创建目录及文件选择在异常边界外。统一捕获mkdir/chooser/write/replace故障，保留旧文件/会话并提示更换目录后另存；正常取消无误报。 复验：EV-034、EV-036，原失败EV保留。

## FND-013 · P2 · 14项旧UI测试仍依赖退役控件和旧合同

位置：项目回归基线；测试文件。实例：不伪造页面实例。

实际：退役details/requirements/answer/category控件KeyError；旧options、skipped必须补答、两款OpenAI与新合同不符；当前回归不能直接全绿。

预期与影响：测试按当前同一工作区、显式跳过、无选项建议、八款OpenAI核对实际用户结果。 测试按当前同一工作区、显式跳过、无选项建议、八款OpenAI核对实际用户结果。目前不能保证；可恢复但影响操作/诊断或回归可信度。

根因（confirmed）：多轮UI迁移保留旧用例未同步，当前active布局不再构造其查询键。

复现：退役details/requirements/answer/category控件KeyError；旧options、skipped必须补答、两款OpenAI与新合同不符；当前回归不能直接全绿。；按evidence对应脚本重放并检查原始actual/expected值

证据：EV-012,EV-001（[台账证据索引](audit.json)）。

修改机制：逐项迁移断言到当前入口和同等用户结果；保留历史失败记录；不可为测试恢复已删除界面或盲删安全断言。

复验：当前14失败节点迁移后专项通过，需求确认/冲突/复制/多行编辑等原目标继续保留。

负责人：测试维护者；任务：TASK-013；状态resolved。修复：旧控件/选项/跳过/模型数合同未同步。迁移到需求弹层、逐题回答、明确跳过及8款OpenAI，保留原业务断言；相邻可靠性旧入口也同步。 复验：EV-035、EV-036，原失败EV保留。
