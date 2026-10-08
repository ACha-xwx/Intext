> 历史资料：仅用于追溯当时的设计与验证；当前状态以根目录 HANDOFF.md 为准。原始路径：`output/prompt/_design/acceptance_20260928_final_delivery_run03/baseline.md`。原始日志、截图及失效旧链接的查找方式见归档索引。

# 最终交付与 Skill 增强：基线记录

记录时间：2026-09-28（Asia/Shanghai）。本目录是本轮新证据；`acceptance_20260928_final_delivery_run01/baseline.xml` 保留不动。

## 工作区状态

- 项目：`C:\Users\yph\Documents\ChatGPT\aicomp`
- Python：项目 `.venv/Scripts/python.exe`
- 当前源码、测试、资源及文档在 Git 中均显示为未跟踪文件；按 v0.3 约束直接在原工作区推进，不执行清理、重置或全量暂存。
- 最近一次定向基线：`.venv/Scripts/python.exe -m pytest -o addopts='' tests/test_final_delivery.py tests/test_exporter.py tests/test_skill_catalog.py tests/test_ui_contract.py -q`，35 passed。
- F1–F3：只登记于既有专项报告，本轮不修复、不复测。

## 旧发行包基线

- 路径：`dist/PromptSmith.exe`
- 长度：13,339,481 字节
- 最后修改：2026-09-27 13:27:50（本机时间）
- SHA-256：`BEAEB563453E4CFC7E2E63285B6985D294433A9AF65EBAB24E7A9ED658ED2B2C`
- 旧包仅含原 M1/M2 提示与 Schema 及 Skill 目录资源；新 M3/M4 提示与 Schema 尚未纳入当前 spec。

## 当前 M1/M2 资源基线

| 资源 | SHA-256 |
|---|---|
| `M1_system_v0.5.txt` | `6B9A9A31383337EDD8311DF027BA8F135BB62B1FB23A70F75B0EA2E481B825A0` |
| `M1_input_v0.2.schema.json` | `8A407B698CCD3F25F258C9812918971541F522D838174587D2DEE9861342D341` |
| `M1_output_v0.2.schema.json` | `E7AE1A374F22D0BA2C3707DFF6FC4AE4F10711071208BBB3BF0AD5204ECF3848` |
| `M2_system_v0.1.txt` | `730DBDEE8007C39AF0CC9CA4173ED8219C18E0F0E628702FE8C49F4ADDE0C178` |
| `M2_input_v0.1.schema.json` | `F1AF8E6A98E0E449CE096D623CAB452C1B0C84DB32004E5AF1F0CE733A8EEEB1` |
| `M2_output_v0.1.schema.json` | `41AF58A6954175B75FE749677F755743A77380850AA60AE79C5107086C1E842D` |

此记录不证明旧 EXE 的任何本轮新增能力。最终构建、运行和资源核验结果另记于本目录。
