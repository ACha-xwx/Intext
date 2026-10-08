# 提示与契约资源

此目录由旧 `output/prompt/_design/` 迁移而来。当前与兼容提示、JSON Schema 和离线人工样例放在一起，保持原文件名便于引用与复放。

| 模块 | 当前装载 |
|---|---|
| M1 首轮 | `M1_system_v0.18.txt` + `M1_system_v0.22.txt` |
| M1 增量 | `M1_incremental_v0.11.txt` + `M1_incremental_v0.15.txt` |
| M1 输入/输出 | `M1_input_v0.4.schema.json` / `M1_output_v0.3.schema.json`；契约 `m1.v0.2` |
| M2 | `M2_system_v0.2.txt`；输入/输出 Schema v0.1 |
| M3 | `M3_system_v0.1.txt`；输入/输出 Schema v0.1 |
| M4 | `M4_system_v0.2.txt`；输入/输出 Schema v0.1 |
| M5 | `M5_system_v0.2.txt`；输入/输出 Schema v0.1 |

旧资源仍用于兼容或测试，清理前检查所有引用和 `PromptSmith.spec`。`examples`、`examples_m2`、`fixtures_m3_m4` 是离线样例，不代表真实模型调用结果。

历史设计说明已归档到 [docs/archive/prompt-design](../../docs/archive/prompt-design/)，原始路径映射见 [迁移清单](../../docs/maintenance/migration_manifest.json)。
