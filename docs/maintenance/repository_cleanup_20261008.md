# 仓库整理与团队交接记录

日期：2026-10-08。目标远程：`https://github.com/ACha-xwx/PromptSmith.git`。

## 原因与范围

GitHub Desktop 使用的 PromptSmith 目录与日常功能开发目录分离。GitHub 副本只有初始提交和较早的未提交代码，缺少最新 Skill/交付功能与资源；开发目录积累了多轮文档、原始日志、缓存和构建产物。

本次将 2026-10-08 功能基线同步到正式仓库，统一运行资源、文档和交接结构。用户随后明确要求提交并推送远程。

## 整理动作

- 对原 GitHub 目录生成完整 ZIP 快照并校验；旧文件另迁到仓库外备份，保留 `.git`、远程和原 `.gitattributes`。
- 同步最新 `src/`、`tests/`、`scripts/`、依赖与构建配置。
- `output/prompt/_design/` 中运行提示、Schema、兼容资源和 fixture 迁至 `resources/prompts/`。24 个源码/测试/脚本/spec 文件仅同步资源路径。
- 比赛规划、历史主方案、原始比赛规则与论文归入 `docs/competition/`；第三方 Skill 原文及许可证归入 `resources/skill_catalog/sources/`，保持原文字节与内容哈希。
- 旧交接、开发过程、提示设计、计划和验收说明归档到 `docs/archive/`；文档本机链接转换为仓库内相对链接。
- 新增根交接、架构、UI、开发、踩坑、协作说明与 AI 工作约定。后续不需要从数百份旧文档中猜当前状态。
- 原始运行资料集中到 Git 忽略的本地压缩档，保留原路径与哈希清单。
- Git 忽略缓存、构建包、原始资料、个人配置与运行数据。没有从历史记录复制 API Key 到配置文件。

## 恢复信息

管理员本机的仓库外备份目录：`Documents/ChatGPT/aicomp_versions/PromptSmith_handoff_20261008_084446/`。

- `github-before-cleanup.zip`：原 GitHub 目录快照（含 `.git`）。SHA-256：`efdbe01ee062a58bd6d3b91c7d2cf059808dc31ef510ffc96c8d344cffd51878`。
- `previous_checkout/`：保留原 GitHub 工作目录文件，未覆盖 `.git`。
- `operation.json`：本机路径与操作记录。
- 旧 `Documents/ChatGPT/aicomp/` 功能工作副本保留；后续日常协作以 GitHub 克隆为准。

自动执行策略曾拦截批量删除；最终采用完整迁出备份方式完成整理，没有为删除操作切换工具绕过限制。

## 完成条件与进度

- [x] 确认 GitHub Desktop 项目与远程地址，保留原未提交内容。
- [x] 最新源码、资源与有用文档归位，提供逐项迁移清单。
- [x] 新队员有系统的架构/UI/踩坑交接和比赛资料入口。
- [x] 在正式仓库的新虚拟环境完成资源与相关程序验证，历史失败单列。
- [x] 构建新 EXE，核对打包资源与独立目录启动。
- [x] 检查链接、隐私、待提交内容和 Git 差异。
- [x] 提交并推送远程，核对远端提交一致。

验证过程只因资源路径迁移执行一次全量检查。通过项不重复测试；发现迁移引入失败时定向修复复验。无关历史失败不扩大本次修改范围。

首轮检查发现内置目录仍引用旧 `source file/` 路径，引发来源校验相关失败；修复目录路径并将元数据升级为 0.1.2，重算记录哈希，spec 包含原文及许可证。旧内置绑定按现有失效机制提示重新选用，保留旧快照。

结果见 [verification/repository_handoff_20261008](../../verification/repository_handoff_20261008/results.md)。

主体交接提交 `f87442d` 已推送到 `origin/main`，远端指向已核对。本记录的完成状态随随后文档提交同步；最新 SHA 以 Git 历史为准。后续队员从根 `HANDOFF.md` 开始即可。
