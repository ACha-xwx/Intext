# 模型按钮箭头修复与目录诊断终止

## 当前有效范围（用户最新决定）

用户检查确认自定义配置卡住由软件外部原因造成，要求不再处理，只修复箭头翻转。因此已恢复api.py至本轮基点f46f127，移除本轮新增网关测试和原生验收的网关模式。API路由、HTML错误处理与配置逻辑没有本批改动；原诊断测试移入忽略证据目录。未推送的本轮1395cae已撤回为待提交变更，取消的接口处理不会进入GitHub历史。

保留底部模型按钮居中SVG、50%/50%旋转轴和6项浅深/三档字号逐帧回归。实际WebView2验收脚本仅新增箭头开关逐帧观察；目录/设置脚本继续使用基点原有localhost/v1协议。箭头DOM6项已通过，两个增量审阅轴0待修，恢复接口后最终EXE实际WebView2双启动24/24通过。

最终箭头产物70,411,122字节，SHA256 `94b7912a884f991d58ae87adb2cf2c5efbbca3e9ed365dcf0a45bdceacaac672`。桌面`Intext.exe`与`Intext-修复版.exe`均已覆盖为此产物且哈希一致。构建与原生证据在忽略目录`local_artifacts/model_arrow_20261014/`，运行日志仍无自动写盘。下面的网关26项与旧产物哈希只属历史证据，不能作为最终交付版本结论。安装包和逐页审查仍暂停；实现提交9172e9a已通过GitHub API原SHA同步并核对远端main一致。

## 取消前的诊断记录（历史，不属于最终实现）

用户截图：YUN/OpenAI/OpenAI Responses，接口为 `https://api.fengapi.top`，密钥已配置，但目录格式错误、教程第三步无法继续。用户随后证实 DeepSeek 官方目录可用。保存修复保持，当前任务聚焦目录及相同地址的后续调用路径。

无凭据公开 GET：`/models` 返回 200 text/html（网站），`/v1/models` 返回 401 application/json（API 认证）。未读取个人密钥或请求生成模型。目录未获取成功前不放宽教程就绪条件。

## 任务

|任务|文件/范围|验收|状态|
|---|---|---|---|
|G1|tests/test_gateway_base_url.py 外部本地 HTTP|根地址像截图一样返回网站、标准目录在 /v1/models；公共 list_models 精确红绿|完成：1红→11绿|
|G2|api.py 地址拼接/Debug|目录和生成采用一致API前缀，显式路径保持，官方DeepSeek不回归；无重试或付费探测|完成|
|G3|生产DOM/Controller/实际WebView2|根地址获取、持久化、教程继续和恢复通过；两个增量审查轴|完成，验证边界见下文|
|G4|spec/桌面产物/GitHub|重建独立EXE验证、桌面哈希与源码推送结果记录|EXE完成，源码推送中|

测试边界沿用用户此前认可的公共 WorkspaceController、生产DOM、外部 HTTP 与隔离实际 WebView2；不增加测试审批。增量审查基点 f46f127，需求来源是本页和本次截图/用户消息。安装包与全量审查继续暂停。

## 精确红绿及实现边界

`python -m pytest -o addopts='' -q tests/test_gateway_base_url.py` 首个用例修复前1失败，复现截图相同目录格式错误：GET `/models`收到网站HTML。修复后11项通过（0.66s，`local_artifacts/gateway_models_20261014/targeted.xml`）。目录和连接测试均通过公共client和真实localhost HTTP，不依赖私有方法。

根地址配置保持原值；仅对公开GET已确认的`api.fengapi.top`根地址，内部请求使用`/v1`前缀。不能仅按模型类别或协议推断任意服务的路由：其他自定义根地址保持根路径，显式API路径和DeepSeek官方根地址保持原行为。无额外探测或重试。内存DEBUG只记录协议/前缀，不记录Key。真实用户中转的已鉴权请求仍未验证。

既有原生验收脚本新增`--gateway-root`，子进程通过仅在本地工作的HTTP代理模拟上述确切域名，设置仍填写不带`/v1`的地址；默认显式`/v1`模式保留前轮覆盖。本地服务器仅`/v1/models`返回目录，其余路径返回HTML，防止通配fixture掩盖路由错误。新增保存和重启后地址未被改写的检查。

## 收尾恢复（2026-10-14）

Spec首轮指出按OpenAI/Anthropic/xAI类别给所有根地址加前缀会破坏合法根目录API。已收窄为确切已验证域名，并补原生根路径服务、相似域名不匹配等公共HTTP回归；16项网关测试和45项配置/协议相邻测试通过。此前207项组合和源码实际WebView2根地址23项通过的原始证据保留，最终完整相邻测试、两轴复审与新EXE验收将在当前代码上另行记录。

## 用户澄清、诊断与箭头验收

用户确认：同学关闭再打开后，自定义服务名称、接口地址和已配置密钥状态仍在，仅模型列表获取失败。因此本批不再扩展设置写盘逻辑；已保存配置和模型目录获取是两个独立结果。

收到HTML时明确说明返回了网页、需要核对服务API地址，保留HTTP状态200供诊断，不把网页正文或密钥写入日志。401/403认证错误、网络错误和其他JSON错误沿用原分类，无新增自动重试。两项公共client→本地HTTP测试先红后绿，覆盖HTML及text/plain误标网页。

底部模型按钮原CSS双边框箭头包含bottom margin，旋转后可见中心上移4.5px。替换为16px居中SVG，围绕50%/50%旋转；浅深主题和9/12/18三档字号的末态像素中心及rAF逐帧旋转轴均通过（6项）。思考折叠图标不改。原生检查器返回工作区时曾早于异步快照读取隐藏按钮；增加公开可见等待后源码实际WebView2双启动26/26通过，原始失败记录保留。

## 当前验证及发布边界

- 主批233项通过，`local_artifacts/gateway_models_20261014/final_regression.xml`。
- 相邻批81通过/12失败，`final_adjacent.xml`。12项在隔离副本使用基点f46f127的api.py全部复现，属于既有DeepSeek/Claude格式和公开摘要断言差异；未改协议或旧测试以消除它们。证据`baseline_effort.xml`、`baseline_effort.txt`。
- 上述与最终箭头6项按完整节点去重：326项，314通过/12既有失败。不是全套成功结论。
- 源码实际WebView2根地址双启动26项通过，证据`final_source_frames_retry/results.json`；仅localhost HTTP与临时合成密钥，没有真实中转鉴权或付费生成，也未验收同学现场。
- AST、JS语法、空白检查已通过；应用代码及新增逐帧测试/验收脚本的Spec、Standards两轴复审均0待修。Standards仅提出未来共用rAF采样器的非阻断建议；Spec前次429已恢复完成。
- 首次构建因dist/Intext.exe被占用而失败；改独立输出目录重建，保留用户进程，最终EXE验收及桌面交付已完成。安装包及逐页审查继续暂停。
- GitHub单次命令级无代理检查已恢复可达，远端main仍为da8dd8a；准备与本批修复一起推送先前保存修复提交，不改全局代理。

## 最终 EXE 与清理

独立输出`local_artifacts/gateway_models_20261014/dist/Intext.exe`构建成功；源码未再修改。最终EXE在独立临时目录实际WebView2双启动26/26通过，覆盖真实localhost目录获取、配置/加密密钥保存恢复、教程解锁、迁移、打开/关闭箭头逐帧及正常退出。证据`final_exe/results.json`。所有HTTP仅本地目录GET，没有模型生成，没有自动运行日志。

产物70,411,782字节，SHA256 `3f636fd5d73edc081a8219cb76a503e0a9620adea51d9f8fc135478fdc5379cf`。桌面`Intext.exe`及既有`Intext-修复版.exe`均更新为此产物并核对一致；未结束用户运行的进程。仓库旧`dist/Intext.exe`仍被进程占用，保留原文件，不能将其当本批交付；请以桌面或本批独立输出为准。

build、.pytest_cache及src/tests/docs中的4处Python生成缓存移入忽略目录的`cleanup/`，含恢复清单。移动前逐项验证路径位于仓库并无Git跟踪文件；源码、个人配置/会话、验证证据与正在使用的旧产物保留。构建输出、证据及缓存不入Git。


## 最终发布记录

仅箭头实现提交`9172e9aa0d4483b049c2fb09613171d2862a3f6f`已同步GitHub main，远端API读回精确一致。普通Git push直连443和本机旧代理不可用；改用现有Git凭据在内存中调用GitHub Git Data API，增量上传blob/tree/commit逐一核对原Git SHA，最后以force=false快进并再次读回。没有修改全局代理、打印/保存凭据或推送取消的1395cae。此前a6d0d1a保存修复及f46f127交付记录一起原SHA同步。API两次全树提交502后改为基点增量树成功；失败未更新分支。详细同步证据在忽略目录github_api_sync_result.json，最终发布文档提交不改变已验收应用/EXE。

R1完成、R2按用户取消、R3/R4完成。最终有效验证为箭头DOM6项、最终EXE实际WebView2双启动24项、限定范围两轴0待修；此前网关与12相邻旧失败只属取消前历史。
