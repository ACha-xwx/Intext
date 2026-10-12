# 设置预设无法选择与 JSON 输入兼容

## 范围与依据

用户澄清设置页下拉问题是“已填 DeepSeek 后无法切换预设，下面协议也点击不了”。此前箭头外观修复没有覆盖此操作。本轮使用当前未提交工作树作为增量基线，保留 Responses/API 既有修复；测试边界沿用生产浏览器 DOM、实际设置桥接及客户端→本地 HTTP。

用户随后提供队员 `responses_json_input_20261012.md`：旧 f473fd5 请求在当前中转上明确报错 `Response input messages must contain the word 'json' ...`，参数为 input。其真实调用成功数据属于队员报告，本轮没有调用收费服务，也没有读取个人 Key 或设置。

## 设置交互

原生 input+datalist 按当前输入过滤，已填 DeepSeek 时只显示该项；弹层不受应用 DOM 控制。旧测试仅 fill+Tab，未验证完整列表展开或选择。新增“已填值→点击箭头→选择另一预设→点击协议”回归，先失败再修复。

服务名称与模型 ID 改为可输入 combobox：箭头或点击字段展开全部预设，输入时按名称筛选，保留自定义值；键盘上下选择、Enter 提交、Escape/Tab/点击外部关闭。列表在表单内展开，不遮盖下方协议；切分类、离页、忙态或重建同步关闭。协议及其它枚举继续使用原生 select。原有草稿、预设联动、确认及密钥清理语义保留，同一已保存预设再次选择不清空密钥。手动输入完整预设名再点同名选项也应用联动字段。

Debug 记录建议列表打开、关闭原因与选用生命周期，仅记录字段 ID，不记录选项内容、用户文本或密钥；轮询相同快照不重复打开或刷日志，日志仍手动保存。

## JSON 输入

已核对 [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)：JSON 模式要求明确 JSON 指令。队员报告进一步指出实际中转单独检查 input，而非只检查 instructions。

当前本地复杂 Schema 已使用提示契约，没有强制 text.format=json_object；因此不将队员旧版本错误直接认定为当前请求的唯一远端根因。仍同步输入可见原则：复杂 Schema 和明确不支持原生格式后的兼容请求，在 user 消息中增加一个 JSON 指令 input_text，原始精简业务输入作为另一个 input_text 逐字独立保留。完整 Schema 继续放在 instructions；原生 strict 初始请求、普通文本、模型、强度、预算及单请求保护不变。不重新开启强制 JSON 模式或泛化重试。

Debug 记录输入契约策略，不输出正文或 Key。此前服务错误详情、request_id、失败状态、部分输出及脱敏修复保留。

## 验证

255个不同自动化节点的最新结果全部通过：

- API/Schema/供应商/流式错误/token六模块首批155 passed、4项旧兼容输入相等断言失败（39.01s），按新JSON指令合同保留原业务块逐字相等后4 passed（2.37s），该批159项最新全部通过。
- 交付/访谈/UI合同/生成预算四模块74 passed（39.73s）。
- 设置下拉10项及相邻设置12项，最终22 passed、57 deselected（52.93s）。

真实 WebView2 使用CDP鼠标/键盘、实际 Python 设置保存，浅深主题和1440×810、720×500窗口共20项全部通过。选项完整展开、预设及协议切换、自定义保存、保存不自动确认、分类/离页关闭及零自动日志均验证。截图和本地验收脚本保留于已忽略的 verification/settings_choice_interaction_20261012/。

独立 Spec 与 Standards 审查各0待修，8文件 Python AST及JavaScript语法检查通过，CodeGraph同步9个可索引变化文件；最终文档与diff检查单列于进度。此前原生datalist外观检查仅为历史，本轮已覆盖真实选择行为。

完整过程记录在 progress.md。本轮未读写个人配置/会话、调用收费模型、构建 EXE 或提交推送；真实服务结果来自队员报告，本机新版源码仍需对应中转复测。
