# 供应商独立密钥与模型目录

用户需求：OpenAI、Anthropic、xAI、Google、DeepSeek通过下拉分别配置/保存API Key；输入框仅使用设置中获取的模型列表，本地匹配介绍/能力。参考提供的“好看的下拉菜单”复刻圆角、图标、阴影、弹出/退出动画，不照搬示例业务。

增量基线：44b6fc0；本轮before副本在忽略的local_artifacts/provider_profiles_20261012/before，初始工作区干净。沿用已授权公开设置/本地HTTP/生产DOM/隔离WebView2测试边界，不调用收费服务、不读取个人配置。不新增审批或自动提交。按diagnosing-bugs、TDD逐slice红绿，planning-and-task-breakdown及planning-with-files维护V1–V4；code-review最终按需求/规范独立双轴。

根因/范围：原文件仅一份connection/credentials，切供应商清Key和目录，picker_models总拼入19内置项。保留version2顶层活动投影兼容旧程序/确认合同，增添model_profiles：每家connection、DPAPI credentials、model_values、model_confirmation、model_directory。旧单配置首次保存迁移；活动投影为读取权威，避免损坏顶层被副本默默掩盖。密钥不进入浏览器快照/会话导出，启动恢复各家密钥并注册日志脱敏。

供应商切换在Tk线程捕获源草稿并恢复目标；未保存内容只在Python内存，显式保存/确认仅存当前家，采样/预算/强度按档案恢复。确认、连接版本和旧结果隔离保持。浏览器发settings_provider含源草稿和目标ID，返回仅公开配置/has_key；同名重选不清Key，仍可输入自定义服务。

获取/models结果与接口/协议/Key匹配后更新当前目录。已保存同身份仅缓存目录，不保存别类草稿或隐式确认；新身份需点击保存。修改Key/接口即清目录；目录持久化指纹排除model，选择另一个同接口ID不清列表。缓存写失败保留本次结果并在Debug记录完整异常、状态提示需保存。

底部汇总各家实际获取ID，携service_provider；匹配本地目录展示名称/介绍/能力，未知ID无猜测推理/图像标签。相同ID来自两接口可分别选择，始终使用来源接口凭据。未获取无内置候选，提供设置引导；新快照更新展开菜单，不覆盖搜索。

独立审查：Spec 0项；Standards复现2项持久化边界风险。旧活动投影已经清钥/撤确认后，保存其它家会从副本复活旧值；跨家保存必须始终同步旧活动投影。读取现有文件一次PermissionError却继续覆盖会丢失其它家；保存只允许修复格式损坏，I/O失败应中止并由既有UI错误路径提示重试、记录完整异常。两项公开持久化回归均先红后绿。读取失败测试使用一次文件系统边界故障和临时设置，断言原字节不变、公开load仍能恢复其它家，恢复后再次保存成功；没有访问个人配置。

记录过程错误：首个缩短except补丁匹配到load_settings而非save_preferences，测试仍红；立即恢复load的容错并以日志上下文准确修改save，回归通过。未改变启动容错合同。

## 验证证据

最终原生验收36项全部通过，Spec/Standards复审各0项待修，V1–V4已完成。

本轮自动化均使用临时设置和一次性凭据。综合受影响检查260项全部通过（420.701s），包括前端回归、下拉、Web桥接、API协议/请求、凭据/确认、加密UI及composer；保存边界修复后65项持久化/凭据/确认/加密UI通过（153.169s）；新增勾尺寸修复后15项浏览器下拉检查通过（38.439s）。按JUnit classname/name去重取最新结果，共264节点全部通过，未执行全仓测试套件。

命令与结果文件（证据保留在忽略目录，不随Git发布）：

- `python -m pytest tests/test_frontend_review_regressions.py tests/test_settings_dropdowns.py tests/test_provider_profiles_browser.py tests/test_web_workspace.py tests/test_provider_profiles.py tests/test_api.py tests/test_provider_requests.py tests/test_credentials.py tests/test_model_confirmation_settings.py tests/test_ui_encrypted_settings.py tests/test_ui_settings.py tests/test_composer.py -k 'not default_window_fits_screen_at_16_9 and not send_is_persistent_but_disabled_for_empty_whitespace_and_busy' --junitxml=local_artifacts/provider_profiles_20261012/final.xml -q`
- `python -m pytest tests/test_provider_profiles.py tests/test_credentials.py tests/test_model_confirmation_settings.py tests/test_ui_encrypted_settings.py -q --junitxml=local_artifacts/provider_profiles_20261012/persistence-final.xml`
- `python -m pytest tests/test_provider_profiles_browser.py tests/test_settings_dropdowns.py -q --junitxml=local_artifacts/provider_profiles_20261012/browser-final.xml`

本批初次相邻试跑出现旧fixture/契约断言：外部设置桥接新增settings_provider后需返回目标档案；旧菜单fixture需要明确提供实际获取ID；provider返回原已确认档案应恢复其确认。这些保留原行为目标并更新夹具，最新结果通过。另4项失败在44b6fc0 before副本独立重现，证据baseline.xml/.txt：`test_send_is_persistent_but_disabled_for_empty_whitespace_and_busy`替换Tk按钮command的断言失效；`test_default_window_fits_screen_at_16_9`三个参数要求旧save按钮映射。这4项未计入本轮通过数，也未为了通过改动无关生产代码。

真实WebView2使用[独立脚本](provider_profiles_webview_check.py)执行实际鼠标/键盘、Python设置桥接和临时LOCALAPPDATA；仅请求localhost五家目录，禁止生成POST。验证五家确认/获取/切换/接口/密钥恢复、浅深/小窗图标与行高、底部只展示获取ID、未知无能力、本地介绍匹配、来源接口选择、无浏览器密钥与自动日志。截图及结构结果位于local_artifacts/provider_profiles_20261012/。

最初原生脚本用wait_for_function位置参数发生测试脚本异常，改为arg关键字后通过；截图核对再发现选中SVG缺class/尺寸，新增浅深宽窄红绿回归后18×18修复，真实WebView2尺寸断言补齐。主题验证改为通过设置实际保存主题，避免仅改DOM dataset造成图标与实际主题不一致。9个Python AST、两JS语法及git diff --check通过，CodeGraph已同步。

## Standards

初审2项持久化问题：读取I/O失败覆盖、旧活动密钥/确认副本复活；均已修复并先红后绿。独立复审0项待修，既有保存失败UI保留输入、Debug完整堆栈及重试提示保持。

## Spec

初审及最终图标尺寸复审均0项待修。五家独立配置、目录驱动、本地资料匹配、来源凭据隔离符合需求。

范围边界：真实收费模型/中转、队员环境及EXE未验证；没有读写个人配置、自动落运行日志、提交或推送。
