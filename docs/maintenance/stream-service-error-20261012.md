# 真实网关流式错误复诊

基线：`f473fd5`。目标是查明队员在上一轮兼容修复后仍失败的原因，并修复服务端流式错误无法在界面和Debug中读取的问题。

## 已确认事实与未决原因

用户提供的2026-10-12 21:40手动日志确认：Web渲染和新版Responses JSON模式均已启用；gpt-6.1-sol以high、8192输出预算请求第三方Responses网关。1.899秒后，consume_sse因服务端错误事件抛出异常，正文与公开思考均未产生。不是120秒超时，也不能从这份日志认定仍为旧strict Schema400。

日志只显示通用StreamError，具体服务端message/code/param未传播到ApiError，因而Debug、页面反馈和check摘要均缺失原因。原始事件已在既有模型证据response.envelope.json的stream_error字段中保存，通常无需再次调用模型即可读取。用户已提供原文：response.failed嵌套error仅通用invalid_request说明，无param，含服务request_id。不能据此确定拒绝的字段。

原先拟按具体错误区分：输出格式/参数不兼容（预期param指向text.format等）、模型或账号权限（预期model/permission类错误）、网关上游故障（预期server/overload类错误）。本地合成测试只证明错误传播缺陷，不用于推断真实网关的具体原因。

## 修复范围

- HTTP错误与SSE服务错误共用错误字段提取和密钥/Bearer脱敏；嵌套response.failed.response.error也可读取。
- ApiError与既有失败事件包含简短服务说明，Debug额外保留完整错误字段说明，不记录整份输入或输出。已有模型证据合同保留，运行日志仍只在手动保存时落盘。
- response.failed保留最新响应id/model/usage/status/error及不完整原因，已接收的正文和公开摘要继续保留为诊断，失败不会变成成功。
- 无服务细节时不编造HTTP状态或故障原因，不改变模型、协议、预算、强度、取消及一般错误单请求规则，不新增自动重试。

## 回归与审查

使用已授权的公开客户端→真实本地HTTP服务边界：HTTP200返回SSE error/response.failed。第一项错误原因不可见、第二项嵌套原因与失败元数据缺失均先独立红灯再修复；另检查三协议的完整长错误、密钥/Bearer脱敏、无用户输入泄漏、空错误及单请求。

第一slice API/流式相邻97项通过，第二slice两项通过；最终8模块 **172 passed in 37.17s**，包含6项新增回归。命令：

```powershell
python -B -m pytest -p no:cacheprovider -o addopts= -q --tb=short tests/test_stream_service_errors.py tests/test_streaming.py tests/test_api.py tests/test_responses_schema_compatibility.py tests/test_provider_requests.py tests/test_runlog.py tests/test_api_truncation_diagnostics.py tests/test_token_efficiency.py
```

3个改动/新增Python文件AST与git diff空白检查通过；CodeGraph同步3文件完成，规范与需求两轴终审均0待修。诊断修复S1–S3完成。原始事件已收到但未说明具体远端原因，本轮不宣称网关调用已修复；未调用收费接口、读取个人Key/配置、构建EXE或提交推送。


追加S5已完成：服务request_id带明确字段名传播至界面/Debug并去重脱敏，最新4模块109 passed in 28.17s、双轴0待修。用户再次反馈换中转失败，后续请求结构兼容修复见[独立维护](responses-gateway-20261012.md)，不把旧泛化错误当成已证实的单字段根因。
