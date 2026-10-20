# 提示与契约资源

此目录由旧 `output/prompt/_design/` 迁移而来。当前与兼容提示、JSON Schema 和离线人工样例放在一起，保持原文件名便于引用与复放。

| 模块 | 当前装载 |
|---|---|
| M1 首轮 | `M1_contract_v0.1.txt` + `M1_system_v0.25.txt` |
| M1 增量 | `M1_contract_v0.1.txt` + `M1_incremental_v0.18.txt` |
| M1 输入/输出 | `M1_input_v0.5.schema.json` / `M1_output_v0.4.schema.json`；契约 `m1.v0.2` |
| M2 | `M2_system_v0.6.txt`；输入/输出 Schema v0.2，契约 `m2.v0.1` |
| M3 | `M3_system_v0.1.txt`；输入/输出 Schema v0.1 |
| M4 | `M4_system_v0.2.txt`；输入/输出 Schema v0.1 |
| M5 | `M5_system_v0.2.txt`；输入/输出 Schema v0.1 |

旧资源仍用于兼容或测试，清理前检查所有引用和 `PromptSmith.spec`。`examples`、`examples_m2`、`fixtures_m3_m4` 是离线样例，不代表真实模型调用结果。

M1 的 `comprehensive_batch` 策略先全面检查相关维度，不再限制一批最多三题。默认最多自动五轮，充分可提前结束，从第五轮结束起继续由用户逐轮授权；remaining=0 只整理回答、保留未知，不自行续问或确认。M2 的 `interview_context` 仅传问题、选择和答案 source ID，正文在 `relevant_materials` 传一次；复用已答/暂缓信息以减少方案阶段重复提问。

2026-10-11：五轮仅为自动上限，不设最低轮数；充分即停止。模型不要在面向用户的文字里显示轮次控制。源码/风格参考/数据等交给下游AI，不在PromptSmith索取实际文件或为未上传而追问。M2新增普通未知保留到方案与最终提示，不重新发起访谈；不把额外交付建议和普通工程取舍当作必答问题。历史版本保留作兼容证据。

历史设计说明已归档到 [docs/archive/prompt-design](../../docs/archive/prompt-design/)，原始路径映射见 [迁移清单](../../docs/maintenance/migration_manifest.json)。

2026-10-11 访谈输入精简：当前M1共同契约+首轮/增量直接替换旧基础+补丁叠加，保留来源、三档覆盖、充分即止、跳过语义、五轮授权和完整输出Schema。精简不降低模型接口思考强度、不删用户答案/来源或缩减输出预算。运行诊断增加每次请求字节、耗时和usage；真实服务加速仍须观察。见[维护说明](../../docs/maintenance/interview-reliability-20261011.md)。

2026-10-12 全流程输入精简：M2 v0.6 合并重复规则，旧 v0.5 保留；M4 根据 ID 合并顶层步骤/工作正文和 baseline.plan 元数据。公共传输只对 M1 历史答案与完整来源精确相同且节省超过说明成本时，省略重复 answer_text 并附 source ID 查找说明；本地验证/证据仍保存完整输入。Schema、思考强度和输出预算不变。见[实现说明](../../docs/maintenance/token-efficiency-20261012.md)与[离线验收](../../verification/token_efficiency_20261012/results.md)。
