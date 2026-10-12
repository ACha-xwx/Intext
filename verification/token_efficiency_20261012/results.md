# 全流程 Token 效率验收 · 2026-10-12

本轮目标是减少达到目标所需的重复输入和不必要请求，同时保留用户信息、来源、确认、取消、版本保护、当前思考强度与完整输出预算。没有调用收费模型、读取个人设置或历史、构建 EXE。

## 已完成的根因修复

|范围|修复|保留边界|
|---|---|---|
|M1|完整来源与回答正文逐字相同且节省量超过引用说明时，传输视图用 `answer_source_id` 重建；缺来源、短答案、不同正文和多条回答保留原文。|SessionState、来源、校验和运行证据不变；三协议请求仍单次。|
|M2|系统提示 v0.6 合并未知处理、下游材料和不后置访谈的重复规则。|需求覆盖、步骤、建议/事实、未知、跳过、确认和 Schema 保留；v0.5 作为兼容资源保留。|
|M4|顶层步骤/关键工作保留正文，`baseline.plan` 按 ID 保留依赖、需求覆盖和额外字段。|原 SessionState 与最终草稿从原计划生成，不丢工作内容。|
|Skill|少量候选直接做一次正文核验；大集合仍先名称/描述初筛再核验。|来源哈希、节选、评分、绑定、取消和无匹配保留。联网检索词只发送工作能力信号。|
|联网查询|成功的检索词规划按完整任务、关键工作和 ApiConfig 哈希短期内存缓存；失败/取消不缓存，TTL=0、配置/任务/工作变化或手动清理会重新规划。|Key 仅参与哈希，不保存或写日志；候选来源仍重新核验。|
|Responses|只有 HTTP 400 明确表示 JSON 格式主体不支持或未知格式参数时，才发送一次同 Schema 的文本兼容请求。|Schema 关键字错误、模型/权限/普通参数错误不重发。|
|Debug|公共传输记录输入字节和服务端真实 usage；Skill 记录步骤省略/缓存命中。|不记录正文或 Key，不逐帧刷屏，不改变仅手动保存日志。|

## 离线回归

`final-public-boundaries.xml` 覆盖 API、停止/流式传输、Skill 选择/搜索、UI 调用和运行日志，186/186 通过。新增分类与小 Skill 迁移为 `green-classification-and-skill.xml` 19/19；查询缓存、来源边界和 M1 重建为 `green-cache-and-source-final.xml` 20/20；M2 当前提示与未知恢复为 `final-m2.xml` 49/49。

合并不同测试节点后共 473 项，其中 470 项通过，3 项保留为历史合同差异：旧测试仍要求自动第二次 M1 请求、已移除的顶部 requirements 面板、已删除的 M5 入口。三项在本轮固定 before 源码中同样失败，分别记录于 `final-adjacent.xml` 和 `baseline-historical.xml`/`baseline-release/verification_summary.json`；没有恢复这些已退役行为来迎合旧测试。最后新增两条嵌套 schema 参数分类红灯并修复，完整 API 模块 `final-api-classification.xml` 72/72 通过。按当前收集节点剔除已迁移的旧测试签名，去重结果保存在 `test-summary.json`。

## 输入成本对照

使用实际 serializer、固定 ID/时钟和内存 HTTP 应答，不联网。以下为 Chat Completions 代表夹具的 UTF-8 请求字节和 `cl100k_base` 估算（不是 DeepSeek 计费 tokenizer，也不是完整真实用户流程）：

|指标|before|current|变化|
|---|---:|---:|---:|
|请求次数|9|8|-11.11%|
|输入 UTF-8 字节|74,455|69,300|-6.92%|
|cl100k_base 估算|21,385|19,712|-7.82%|

M1 增量输入减少 1.40%，M2 方案输入减少 22.07%，M4 输入减少 1.51%；少量 Skill 复核由 2 次/4,582 字节变为 1 次/2,774 字节。三种协议保持相同的调用数量趋势；每项请求仍携带既定 max_tokens/reasoning_effort/timeout。

集合包含一个 M5 兼容样例；它不是当前用户流程的入口。去掉这个样例后，普通阶段集合为 8→7 次、20,396→18,723 个估算 token（-8.20%）。各阶段使用独立代表夹具，实际访谈轮数、计划长度、是否选用 Skill 会改变总量。缓存复用的额外收益用请求次数回归验证，没有叠加进这组百分比。

这些数据证明了重复输入和重复复核的离线变化，不能证明服务端总思考 token、网络等待或 400 秒案例一定下降。真实服务仍需查看 Debug 的 `Model response usage`，并由用户决定是否点击 Stop。

## 审查与边界

Standards 审查 0 项，Spec 审查 0 项。18 个本轮差异文件的 manifest SHA-256 与磁盘一致；机械收尾核对 Python AST、Schema/资源、相对文档链接与 `git diff --check` 共 371 项通过，结果写入 `mechanical.json`。CodeGraph 同步 15 个变化文件，状态为 current（209 files / 5294 nodes / 16547 edges），before 快照保持忽略，不纳入索引。

## 复验入口

当前源码、提示与测试的固定差异由 [refresh_delta.py](refresh_delta.py) 生成到 `delta.patch` 和 `manifest.json`；基线是 [before](before/)，保留此前未提交工作。原始红灯和过程失败没有被最终结果覆盖；脚本/原始证据为本机验收附件，仓库只跟踪本报告与[审查](review.md)。

```powershell
python verification/token_efficiency_20261012/measure.py --before --output verification/token_efficiency_20261012/metrics-before.json
python verification/token_efficiency_20261012/measure.py --output verification/token_efficiency_20261012/metrics-current.json
python verification/token_efficiency_20261012/summarize_tests.py
```

各阶段输入明细保存在 `metrics-before.json`、`metrics-current.json`。各协议独立序列化，没有把 M5 兼容调用或缓存收益伪装为普通流程必需请求。服务端总思考/真实质量、网络站点、EXE 跨机和用户实屏仍未验收。
