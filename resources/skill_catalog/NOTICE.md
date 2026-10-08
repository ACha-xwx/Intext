# PromptSmith 本地 Skill 目录说明

本目录保存三个内置 Skill 的事实摘要、核验哈希和适配边界；`sources/` 保留引用原文及许可证。程序读取资料并生成下游使用建议，不执行原版 Skill、安装依赖、发布 issue 或启动 `/goal`。

| 条目 | 原始来源 | 许可资料 |
| --- | --- | --- |
| `to-spec` | `resources/skill_catalog/sources/mattpocock_to-spec.md` | Matt Pocock 的 `mattpocock_LICENSE.txt`，MIT |
| `domain-modeling` | `resources/skill_catalog/sources/mattpocock_domain-modeling.md` | Matt Pocock 的 `mattpocock_LICENSE.txt`，MIT |
| `goal-prompt` | `resources/skill_catalog/sources/trailofbits_goal-prompt.md` | Trail of Bits 的 `trailofbits_LICENSE.txt`，CC BY-SA 4.0 |

每条记录的 `local_source_snapshot_sha256` 与 `record_hash` 用于读取时核对。显式执行来源核验时，缺失或哈希变化会使候选不可选。历史仅带目录摘要的发行形态保留兼容；本次 spec 同时包含 `sources/`，来源可读性按实际文件判断。`installed` 和 `execution_tested` 默认为 `false`，资料读取不能证明原版宿主、脚本、模板或执行条件可用。内部 `method_adaptation` 是历史字段名，用户最终选用的是 Agent Skill 参考。

目录版本 `0.1.2` 只迁移来源路径与记录哈希；三条引用原文的字节和内容哈希保持不变。旧会话中的内置绑定可能因记录哈希变化而需要重新选用，原快照保留。
