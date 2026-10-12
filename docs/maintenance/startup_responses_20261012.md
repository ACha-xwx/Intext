# 跨机启动与全部模型调用兼容修复

基线：`bee1563333c15cb31f1bc86b5b86379eec7aa1d2`。范围为 Windows 源码启动入口，以及五家供应商全部19个预设的请求协议、结构化格式、采样与公开思考摘要适配。保留访谈流程、用户模型思考强度和输出预算。

## 根因与修复

队员报告实际 Python 导入 `webview` 得到 `ModuleNotFoundError`。旧 `run.bat` 只有 `python run_promptsmith.py`，使用 PATH Python 的 auto 模式；依赖导入失败后继续 Tk。因此相同 Git 源码仍可能打开不同界面。新的入口固定脚本所在目录、优先项目 `.venv`、明确 `--renderer web`，失败保留终端原因、修复命令和退出码，显式 `--renderer tk` 仍可使用。启动诊断提前记录解释器、工作目录及请求渲染模式，导入失败保留异常链。

首次在项目根目录运行：

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.\run.bat
```

不使用虚拟环境时，用启动所用 Python 执行 `python -m pip install -r requirements.txt`。电脑还需要 [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)。队员目前只证实缺 Python 包，未证实缺 Runtime。

GPT 截图报告 HTTP400，参数为 `text.format.schema`。当前 M1 输出 Schema 有可选属性，M2/M3/M4 有条件与组合规则，不能原样发送为 OpenAI strict Schema。原客户端无条件 strict=true。现发送前对文档支持的子集进行保守选择：不兼容时使用 `json_object`，将完整业务 Schema 放入 instructions；兼容的封闭/必填对象继续原生 strict。不修改业务 Schema、不删除内容或降低用户模型参数、不为一般400盲目重试。服务明确不支持原生输出格式时最多一次兼容请求，Schema 只放一次。

GPT 推理模型存在内部推理，但通常不公开原始思考文本；可见摘要与原始推理不同。当前响应解析允许无公开思考，正文仍正常完成。Responses 使用 reasoning.effort，Chat Completions 使用 reasoning_effort；GPT 请求不添加 DeepSeek thinking 字段。诊断只记录格式选择原因，保留既有失败/usage日志及脱敏/手动保存合同。

官方来源（本轮在线获取）：[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)、[Reasoning](https://developers.openai.com/api/docs/guides/reasoning)。

## 全部预设模型审查

|供应商|预设协议|推理强度字段|本轮结论|
|---|---|---|---|
|OpenAI（8项）|Responses|reasoning.effort|Schema不兼容时JSON模式；Chat兼容使用reasoning_effort/max_completion_tokens；无公开思考可正常完成|
|Claude（4项）|Anthropic Messages|output_config.effort|adaptive保留，并用display=summarized公开摘要；不兼容约束用完整system契约，原生支持可选字段不套OpenAI必填规则|
|Grok（3项）|Responses|reasoning.effort|4.7/4.6的Max映射xhigh，4.5映射high，吻合官方；JSON格式共用兼容选择|
|Google（2项）|OpenAI兼容Chat|reasoning_effort|Low/Medium/High与Max→High映射保留；不添加DeepSeek thinking|
|DeepSeek（2项）|Chat（另检Responses/Messages）|各协议独立字段|low/high/max与top_p下限0.95保留；Messages只传output_config.effort，不传Claude format|

另发现已知思考模型的采样参数会在请求时适配/省略，但 ApiConfig 仍按未适配参数提前阻止切换供应商，导致 Claude 无法使用其它模型遗留的 temperature/top_p。现只对确实要发送两个采样参数的未知 Messages 模型执行互斥检查；已知思考模型按原有请求规则处理，用户设置值保留。未知模型原有范围/互斥检查仍保留。

本轮查阅：[Claude结构化输出](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)、[Claude思考配置](https://platform.claude.com/docs/en/build-with-claude/thinking)、[Claude effort](https://platform.claude.com/docs/en/build-with-claude/effort)、[Grok推理](https://docs.x.ai/developers/model-capabilities/text/reasoning)、[Grok结构化输出](https://docs.x.ai/developers/model-capabilities/text/structured-outputs)、[Google OpenAI兼容](https://ai.google.dev/gemini-api/docs/openai)、[DeepSeek思考](https://api-docs.deepseek.com/guides/thinking_mode/)、[DeepSeek Messages兼容](https://api-docs.deepseek.com/guides/anthropic_api/)。

19个预设×四档×连接/文本/结构生成共228次本地合成HTTP检查，按每个预设一项回归测试统计，不当作228个独立测试或真实模型成功。自定义网关、额外发现的模型ID、账号权限及供应商动态限额仍需实际环境验证。

## 验证

测试边界为公开 `run.bat`/CLI 和真实 HTTP 请求到本地合成服务；无真实供应商调用，不代表真实 GPT 质量或队员机器已复测。

- 旧 batch 从其他目录启动失败，修复后实际 cmd 验证项目虚拟环境、含空格路径、默认 web、参数覆盖及失败退出码。
- `python -S` 隔离 site-packages 复现缺 pywebview，验证准确安装命令、不进入 Tk、不自动保存日志。
- 本地 HTTP 服务使用实际 M1 Schema 复现截图同类400，修复后一次请求成功，完整契约/用户输入/参数保留且无公开思考可完成。
- M2/M3/M4、嵌套可选字段、开放对象、条件结构与合法 strict 格式分别检查。

最终定向及相邻回归 **233 passed in 45.37s**，命令：

```powershell
python -B -m pytest -p no:cacheprovider -o addopts= -q --tb=short tests/test_api.py tests/test_streaming.py tests/test_api_truncation_diagnostics.py tests/test_token_efficiency.py tests/test_run_bat.py tests/test_main_diagnostics.py tests/test_workflow.py tests/test_m2_workflow.py tests/test_delivery_workflow.py tests/test_provider_requests.py tests/test_responses_schema_compatibility.py tests/test_generation_budget_recovery.py tests/test_preferences.py
```

另完成默认 `run.bat` 的实际 WebView2 启动烟测：隔离 LOCALAPPDATA，窗口打开后1800ms自动关闭，退出码0，未生成自动日志文件；完整烟测耗时11.45s，包含导入、初始化、窗口停留及退出，不是纯启动性能计时。

机械检查通过：7个修改/新增 Python 文件 AST、144个文档相对链接及 `git diff --check`。CodeGraph同步成功。规范与需求两轴独立审查均0项待修，L1–L3、G1–G3、A1–A3全部完成。此前红灯、夹具合同迁移及工具错误保留在维护进度中。

本轮没有调用真实供应商付费接口、读写个人设置/会话或构建EXE；未提交或推送。队员机器、自定义网关和真实模型服务仍需对应环境复测，不能从上述本地结果推断其已通过。
