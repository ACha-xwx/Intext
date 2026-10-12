# 历史资料索引

这里保留有价值的旧文档，帮助理解决策与踩坑。**当前入口是根目录 [HANDOFF.md](../../HANDOFF.md)**；历史计划中的执行命令、时间节点和“下一步”不是当前任务指令。

| 目录 | 内容 |
|---|---|
| `handoffs/` | 旧 HANDOFF 与阶段交接 |
| `development-history/` | 旧 README、task_plan、findings、progress |
| `development/` | 原 docs 下的阶段说明和设计计划 |
| `project-plans/` | 历次产品方案、分工与调研 |
| `prompt-design/` | 提示/契约映射、变更说明与历史执行提示 |
| `reports/` | 原 verification 与 output 中的文字验收报告 |
| `troubleshooting/` | 缓存探测手册与配套诊断脚本；执行前先阅读其采集范围 |

运行资源已迁至 [resources/prompts](../../resources/prompts/)，比赛资料已归入 [competition](../competition/README.md)。原路径到新路径的逐项对应见 [migration_manifest.json](../maintenance/migration_manifest.json) 的 `mapping`。

## 原始证据

仓库管理员本机将历史原始诊断资料保存在仓库外的 `PromptSmith-local-artifacts-20261012/`，其中包含日志、JSON、报告、诊断脚本和截图等文件。它不属于运行或构建所需资源，也不随 GitHub 仓库分发；迁移清单仍记录旧路径的来源与哈希。

该本地目录不会提交 Git，克隆仓库不会自动得到。原始证据可能包含个人任务、响应内容与机器路径；需要复核具体案例时向管理员索取相关条目，审阅后通过团队存储共享。已整理的文字报告和最近基线随 Git 交接。

旧报告中指向未跟随 Git 的运行文件、已失效旧位置或 EXE 的链接，统一导向本索引，原始路径可在未改写的 ZIP 原件与迁移清单中查找。历史内容中的版本/时间事实保留，不能替代当前验收。

## 本次保留原则

- 源码、所有测试、运行提示/Schema、人工 fixture、第三方引用许可证和有用文字文档保留。
- 虚拟环境、Python/pytest 缓存、PyInstaller 中间产物可重新生成，不进入 Git。
- GitHub 目录旧文件先完整备份并迁出，`.git` 与远程关联保留。旧开发工作副本仍保留，未批量删除。
- 历史 EXE 留在旧工作副本/备份；协作仓库的本地 `dist/` 只保留最新功能基线及本轮整理构建。

整理细节与当前验证见 [维护记录](../maintenance/repository_cleanup_20261008.md)。
