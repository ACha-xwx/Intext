# 意织 · Intext

需求引导式提示构建助手：将模糊想法整理为明确需求、执行方案和可交给其他 AI 使用的提示，并按任务选配 Agent Skill。

Python / WebView2 Windows 桌面应用，Tk 保留为业务线程与兼容界面。AI 功能调用用户配置的模型接口；软件提供需求确认、方案管理、Skill 检索与选择、保存和导出。

## 接手入口

**新队员先读 [HANDOFF.md](HANDOFF.md)**，再按职责阅读：

| 工作 | 入口 |
|---|---|
| 功能开发、架构与状态逻辑 | [架构与数据流](docs/architecture.md) |
| UI 设计与实现 | [UI 接手指南](docs/ui-handoff.md) |
| 启动、检查、打包 | [开发与验证](docs/development.md) |
| 既往问题与已知限制 | [踩坑与防回归](docs/pitfalls.md) |
| 比赛要求、PPT、技术文档和视频 | [比赛与展示资料](docs/competition/README.md) |
| GitHub Desktop、三人协作与提交 | [协作说明](CONTRIBUTING.md) |

## 启动

普通用户使用 `Intext-Setup-2026.10.14.exe` 安装，无需安装 Python。安装位置可选择其他盘；已存在的 WebView2 会保留，缺失时由微软安装器联网安装。需要 Windows 10 1809 或更高版本（x64），系统盘建议至少保留 1 GB 空间。安装后的程序直接读取已安装文件，避免单文件 EXE 每次启动全量解包；卸载不会删除 `%LOCALAPPDATA%/Intext/` 中的设置、密钥和会话。构建说明见 [开发与验证](docs/development.md#安装包)。

在仓库根目录使用 Python 3.11 或更高版本（须包含 Tk）：

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe run_promptsmith.py --renderer web
```

首次使用还需要安装 [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)。以后可双击根目录 `run.bat`：它自动切到项目目录，优先使用 `.venv`，默认明确启动 WebView2。缺依赖时显示错误和安装命令，不自动切换到 Tk；`run.bat --renderer tk` 可显式打开兼容界面。直接运行 `python run_promptsmith.py` 仍为 auto 模式，环境不满足时会回退 Tk。

源码相同不代表 Python 环境相同。若看到 `No module named 'webview'`，用启动脚本显示的那个 Python 执行 `-m pip install -r requirements.txt`；安装到其他 Python 或虚拟环境不会生效。

界面中填写服务、协议、接口地址、模型 ID 和自己的 API Key。支持 OpenAI Chat Completions、OpenAI Responses、Anthropic Messages。连接测试通过只说明探测请求成功，正式结构化生成仍需验证服务支持。

每个供应商分别保存接口、加密 API Key 和模型列表。修改自动保存，有效配置自动生效。以后启动会在后台刷新所有已保存密钥的供应商列表，刷新期间可以使用之前的列表；失败时保留缓存并提示重试。“获取模型”按钮仍可随时手动刷新。

程序启动先显示「意织 · Intext」与加载动画。首次使用点击圆形开始按钮进入操作式教程；完成或跳过教程后，之后启动会在加载结束自动进入工作区。设置页可重新查看教程。完整标题以透明 SVG 显示，中文手绘与 Orange Juice 英文一起保存为路径，不依赖电脑字体。教程前四步操作完成才解锁，第五步可直接完成；非操作区域压暗25%，当前步骤首次完成播放礼花。

```powershell
.venv/Scripts/python.exe run_promptsmith.py --smoke-test
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1
```

`--smoke-test` 仅检查 Tk 构造，不代表 WebView2 启动验收。

构建产物为 `dist/Intext.exe`。EXE、虚拟环境、运行日志和个人会话不提交 Git；分发软件时使用 GitHub Release 或团队共享文件。默认用户数据位于 `%LOCALAPPDATA%/Intext/`，首次启动会把旧 `PromptSmith` 目录整体迁移，保留设置、加密密钥和历史；若两个目录均已有数据，则使用 `Intext` 并保留旧目录，不覆盖合并。运行时密钥不随会话保存。

## 仓库结构

```text
HANDOFF.md / README.md       当前交接和导航
CONTRIBUTING.md / AGENTS.md  人员与 AI 协作约定
src/promptsmith/             UI、业务逻辑、模型与检索实现
resources/prompts/          M1–M5 提示、Schema、兼容资源和测试样例
resources/skill_catalog/    内置参考目录及来源说明
tests/                      自动化测试
scripts/                    构建、离线验证及显式真实 API 检查
docs/                       架构、UI、开发、踩坑说明
  competition/              比赛规则、研究基础、包装与答辩规划
  archive/                  历史设计、计划和验收文字记录
  maintenance/              本次整理清单和进度
verification/               经整理的基线与本次验证结论
local_artifacts/            本地历史原始证据压缩档（忽略）
```

运行资源已从旧 `output/prompt/_design/` 移到 `resources/prompts/`。旧文件位置可通过 [迁移清单](docs/maintenance/migration_manifest.json) 查询。

## 当前状态

功能基线为 2026-10-08 的 Skill 交接修复版：最终提示带 Skill 名称、来源、本地路径及对应工作/步骤，供下游 AI 获取、阅读和使用。程序不会安装或执行检索到的 Skill。

前一轮有 155 项相关检查分批通过；同时仍存在已单列的 12 项历史测试/契约不一致。真实模型全链内容质量、真实用户效果与跨机兼容性需要补充验收。**当前仓库不宣称全量测试全绿。** 本次整理的验证结果见 [交接验证](verification/repository_handoff_20261008/results.md)。

参赛方向为 2026 第八届全球校园人工智能算法精英大赛“AI+软件创新”。技术、功能与方案完整性需要实际证据支撑；比赛资料中的后续 UI 和演示方案属于待执行计划。
