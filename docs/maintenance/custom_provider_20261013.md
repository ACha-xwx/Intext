# 自定义供应商保存与调用类型

用户要求自定义服务可保存，并必须从OpenAI、Anthropic、xAI、Google、DeepSeek选择对应模型供应商，后续按该类型调用。基线b3f4953；沿用公开设置、真实Controller、localhost HTTP、生产DOM和隔离WebView2测试边界，不读取个人settings或调用收费服务。

缺口：自定义名称仅字符串保存，没有模型类型；下拉及桥接只接受五预设；API参数根据内置model ID识别，别名ID无法依据用户选择路由。增添connection.model_provider仅用于自定义档案，显示名称与调用类型分别管理；协议默认随类型选择，允许现有协议选择能力。名称保留为凭据/目录隔离身份。旧无类型自定义配置保留密钥，但需选择类型后重新确认。

按C1–C4逐slice先红后绿，持续更新Debug及维护。完成标准：保存/重启/来源恢复、类型缺失提示且不调用、五类请求合同正确、密钥不进入浏览器/日志。

追加范围：官网元数据、当前输入Key显隐、已获取目录和默认模型；不添加备注、管理测速或手动添加入口。设置页服务下拉按所选五家类型分组，自定义可确认删除（持久层及内存均清理），内置入口不能删除。模型菜单不再新增custom类，未知ID按服务类型归类，保留未知能力状态。

## 最终行为

- 设置页的服务名称下拉按 OpenAI、Anthropic、xAI、Google、DeepSeek 分组。自定义服务放入用户明确选择的类型组；分组针对设置页，不新增第六个 custom 模型类别。
- 自定义服务可命名保存、切换和重启恢复。保存、确认、获取目录及使用前必须选择调用类型；新服务不继承上家的接口、模型或密钥，切换暂存源服务草稿。
- 自定义服务提供删除操作，先在 Web dialog 中确认。删除先原子写入 settings，再清理内存档案；同时删除该服务的接口、加密凭据、确认和目录，随后保存不会复活。失败保留原状态并允许重试；五家内置入口不可删除。删除取消恢复按钮焦点，成功将焦点交给可见服务输入框。
- 官网链接独立保存；修改官网不会撤销连接确认或清空目录。API Key 显隐仅针对本次输入，切换、提交和离页清空输入并恢复 password；已保存 Key 不回传浏览器。
- 已获取模型列表在设置页展示，模型 ID 字段明确为默认模型。底部模型列表仍仅使用获取目录；已知 ID 匹配本地介绍，未知 ID 不猜测推理或图像能力。
- 自定义别名模型按所选类型适配预算、思考、采样及结构化格式，实际请求 model ID 保持用户值；明确类型优先于冲突的已知 ID。官方接口返回已知 ID 仍按模型实际类别展示。

## 实现与兼容

|范围|文件|处理|
|---|---|---|
|档案与凭据|preferences.py、settings_ui.py、ui.py|自定义 connection.model_provider 必选，website 为元数据；DPAPI 和目录身份继续隔离服务；原子删除|
|公开桥接|web_workspace.py|公开 saved_providers/provider_families；类型缺失在业务变量变更前拒绝；保存失败保留可重试状态|
|请求与目录|api.py、model_catalog.py|显式类型适配别名请求及未知 ID 分类；实际 wire ID 不改，不产生 custom 类|
|设置交互|settings.js、workspace.css|分组图标、必选类型、Key 显隐、官网/目录、删除确认；动画、键盘、浅深及小窗保持|

旧官方四字段确认指纹保持兼容；旧自定义缺少类型时保留加密密钥，但撤销确认并要求明确选择类型。类型变更清空目录和确认，不删除该服务 Key。Debug 同步记录设置、切换、删除、失败及请求类型，不记录 Key 或请求正文；运行日志仍只在用户点击保存时写盘。

## 验收证据

263 个不同本地自动化节点最新全部通过；各批次存在交集，以下数量不能相加作为不同节点总数。去重收集记录为本地忽略目录 local_artifacts/custom-provider-collected.txt（263/264 collected，1 deselected）。

|批次|通过数|本地结果文件|
|---|---|---|
|API、19 预设矩阵、截断、流式及 composer|141|custom-provider-api-final.txt|
|档案与 Controller|34|custom-provider-controller-tests.txt|
|加密、确认与设置 UI|57|custom-provider-settings-tests.txt|
|既有设置浏览器回归|15|custom-provider-browser-tests.txt|
|新增生产 DOM 回归|5|custom-provider-browser-new.txt|
|新增档案及请求回归最终批|20|custom-provider-final-tests.txt|

新增测试为 tests/test_custom_provider_profiles.py（9 项）、test_custom_provider_requests.py（11 项）和 test_custom_provider_browser.py（5 项）。覆盖保存/重启/兼容、缺类型、分类/删除、原子失败重试、类型草稿切换、删除焦点、五家别名 localhost HTTP 和显式类型优先等；缺口逐 slice 先红后绿，不以静态源码匹配代替操作验证。

真实 WebView2 隔离验收 32 项全部通过，涵盖两个 OpenAI 自定义服务和一个 Anthropic 服务的保存、确认、获取、恢复、分类、删除取消/成功及重载。浅深主题、1440×810 和 720×500 的图标/行高，以及主模型列表无 custom 类均有检查。仅发生 3 次 localhost 目录 GET，未生成或测试真实模型，未读写个人配置，未自动保存日志。

可重跑脚本：[custom_provider_webview_check.py](custom_provider_webview_check.py)。结果和截图位于本地忽略目录 local_artifacts/custom_provider_20261013/，原生执行输出为 local_artifacts/custom-provider-native-output.txt。

独立审查：Spec 初审发现切到内置服务时源自定义类型草稿被过滤；Standards 初审发现删除成功焦点回到隐藏按钮。两项分别补生产 DOM 红灯并修复，最终两轴各 0 项待修。

## 旧基线与边界

- test_composer.py::test_send_is_persistent_but_disabled_for_empty_whitespace_and_busy 的替身 command 被 refresh 覆盖，已在修改前复现，本轮排除，不改正常发送逻辑。
- test_model_effort_parameters.py 的 12 项旧合同断言已在 b3f4953 独立副本全部复现，涉及 DeepSeek Messages 的 Claude native format 和 Claude adaptive display。记录在 local_artifacts/custom-provider-api-baseline.txt；这些节点不属于上述 263 项通过集合，不回退生产协议使旧断言通过。
- 原生探针首次一次性 Key 含中文导致 HTTP header Latin1 错误，已改 ASCII fixture；一次 Escape 仅清空搜索，探针按实际交互使用两次 Escape 关闭菜单。两者为验收脚本修正，没有据此改产品逻辑。
- 最后 16 个变更/新增 Python 文件 AST、settings.js 语法及 git diff --check 通过，交接相对链接检查通过。HANDOFF、architecture、ui-handoff 与维护账本已更新，C1–C4 完成；CodeGraph 同步 17 个变更文件并确认 current（224 files / 5683 nodes / 17890 edges）。
- 本轮未调用真实付费模型、验证实际中转或构建 EXE，不能据本地/原生 UI 验收宣称真实服务质量；尚未提交或推送。
