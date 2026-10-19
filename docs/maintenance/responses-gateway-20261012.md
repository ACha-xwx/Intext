# Responses 网关请求兼容修复

基线：`f473fd5`（工作树）；包含前续流式错误详情修复。目标是排查用户“换中转仍失败，怀疑请求方式”的反馈，通过更通用的标准请求结构减少中转兼容失败，不降低模型、思考强度或输出预算，不增加盲目付费重试。

## 事实与适用边界

用户实际事件是 HTTP 成功之后的 `response.failed`，错误只有 `invalid_request` 和通用参数说明，没有 `param`。这能证实拒绝发生在请求处理，但不能定位某一参数。未读取个人Key或主动请求收费模型；以下验证均为本地模拟网关。

官方 Responses 支持字符串简写及消息数组输入、`store=false`、可选 `text.format`。旧字符串输入本身符合官方标准，但部分中转/OAuth上游要求显式消息列表。公开网关Sub2API的转换代码说明了这些上游限制，但不能据此认定实例的部署版本或账号类型。保留输出预算，由中转负责其上游适配。

参考（本轮实际读取官方创建文档，公开网关源码为前续只读证据）：

- [Responses创建接口](https://developers.openai.com/api/reference/resources/responses/methods/create)
- [公开网关转换实现](https://github.com/Wei-Shaw/sub2api/blob/main/backend/internal/service/openai_codex_transform.go)

## 最终行为

- Responses连接测试、文本、结构生成统一为 `input=[{role:user, content:[{type:input_text,text:...}]}]`，显式 `store=false`。原始换行/Unicode/用户内容完整保留。
- 不适用原生strict的M1–M4 Schema放在完整instructions契约中，不再额外强制 `text.format=json_object`；本地阶段解析/校验不变。简单合法Schema仍使用原生strict。
- 仅原生format确实已发送且HTTP400明确说明格式不支持时，保留既有一次兼容请求。没有format时不重发相同请求；泛化invalid_request/SSE服务错误不触发自动重试。
- 非流式或流式失败均保留服务原因、request_id及响应元数据；Debug完整脱敏错误，界面短说明，缓冲JSON失败也不能被误标成功。已有取消/版本隔离及手动Save Logs继续保留。
- Debug每次请求记录消息表示、store和输出格式类型，不记录任务正文、Schema正文或Key；其它协议不发送Responses字段。

## TDD与回归

沿用用户授权的公开客户端→真实本地HTTP边界，独立构造限制；并非访问真实网关。

1. 消息列表限制：三个入口×两种传输6红→6绿。
2. 显式store=false限制：6红→12绿（含第一slice）。
3. 业务Schema/json_object限制：M1–M4×两种传输8红→20绿，完整Schema/输入/强度/预算未丢失。
4. 已无format却误按400格式词重发：捕获2次请求，1红→单请求21绿。
5. HTTP200/failed非流式丢失原因：1红/1绿→23绿，追加流式请求被缓冲为JSON的失败覆盖。

首批6模块158 passed in 37.84s。最终15模块首次246 passed/2 failed（82.19s）；两项失败是M3/M4本地HTTP夹具仍把新消息列表直接json.loads，迁移后delivery/interview/UI合同三模块63 passed in 30.51s。未放松业务断言；289个不同节点最新全部通过（17模块），其中24个新增网关兼容节点。包括三协议流式/非流式、19模型预设、M1/M2/M3/M4、预算/截断、token完整性、日志与Stop。

最终批次命令：

```powershell
python -B -m pytest -p no:cacheprovider -o addopts= -q --tb=short tests/test_responses_gateway_compatibility.py tests/test_responses_schema_compatibility.py tests/test_stream_service_errors.py tests/test_api.py tests/test_streaming.py tests/test_provider_requests.py tests/test_generation_budget_recovery.py tests/test_api_truncation_diagnostics.py tests/test_token_efficiency.py tests/test_runlog.py tests/test_stop_transport.py tests/test_request_stop.py tests/test_m1_single_request.py tests/test_m2_workflow.py tests/test_delivery_workflow.py
python -B -m pytest -p no:cacheprovider -o addopts= -q --tb=short tests/test_delivery_workflow.py tests/test_interview_reliability.py tests/test_ui_contract.py
```

两个只读审查代理按code-review分轴复核固定基线到工作树：Standards 0待修，Spec 0待修；最后三个夹具迁移的增量审查亦0待修。12个Python文件AST、182个相对文档链接及diff空白检查通过，CodeGraph已同步。一次索引完成后的摘要打印因终端GBK不能编码圆点失败，仅影响探针输出，索引同步本身已成功。

本地通过不能证明队员新中转已成功。若仍拒绝，将显示服务错误及request_id，支持定位该次请求，无需反复生成或猜测；不宣称真实模型质量、EXE或队员环境验收。没有本轮提交推送。
