> 历史资料：仅用于追溯当时的设计与验证；当前状态以根目录 HANDOFF.md 为准。原始路径：`README.md`。原始日志、截图及失效旧链接的查找方式见归档索引。

# PromptSmith

“需求引导式提示构建助手”的可运行版本，覆盖 M1 需求提取与动态追问、M2 完整初始方案、M3/M4 本地 Skill 候选分析与增量整合、M5 可选局部示例，以及末端交付闭环：无 Skill 最终草稿、受控语气、短文本试运行、提示复制、Markdown 导出和 JSON 保存重开。

核心分工是**程序维护确认、版本、失效、预算、保存和权限；模型只提出候选、缺口、问题和下一步建议**。模型输出只进入候选区，不能自动确认需求或方案，也不能启动下游步骤。

> 当前实现为流程简化与 JGS 复测迭代，见[本轮交接](<../reports/verification/guided_flow_20261001/修复与交接.md>)。历史截断、超时、输入同步和 Skill 验证记录保留。真实模型、离线程序测试和 EXE 业务链分开记录，不把合成内容当成真实模型结果。

## 源码启动

需要 Python 3.11 及 Tk 8.6：

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe run_promptsmith.py
```

连接区将服务名称、协议、接口地址、模型 ID 和运行时密钥分开显示。默认服务为 DeepSeek，默认使用 OpenAI Chat Completions 兼容接口；也可选择 OpenAI Responses、Anthropic Messages，或填写自定义服务名称和非预设模型 ID。模型目录按当前服务和协议获取，手工填写值不会被自动覆盖。API Key 只保存在当前进程内存，不写入会话或运行日志。

M1—M5 生成请求默认等待阈值为 120 秒，连接测试和模型列表为 15 秒。结构化生成输出上限为 8192 tokens。超时会保留已有回答和需求并恢复操作入口，只有用户再次点击才会重试。

M1 评估已提交回答时使用独立增量提示，只要求返回本轮更新。程序保留未返回的旧未知与冲突，仍严格校验来源、冲突参与方和确认条件。若收到长度截断，不提交半截结果；原回答保留，主按钮提供“重试分析”（内部保留精简重试机制）。每次明确点击只请求一次，失败后可调整模型再试，不会后台循环调用。保存重开后恢复对应入口，密钥仍需重新输入。首轮默认提示、模型 Schema 和旧实验资源保留。

正文和表格使用 12 pt 微软雅黑界面字体；需求、候选、问题、步骤和关键工作表格均有横纵滚动条，长内容可在详情区或右键“复制选中内容”查看。常用输入框和多行编辑弹窗支持右键剪切、复制、粘贴、全选及可用时撤销。主页面提供纵向滚动条，1120×780 下在较高缩放时仍可到达底部内容。

默认顺序：输入任务 → 必要时补充回答 → 一次核对需求并生成方案 → 一次核对方案并生成提示 → 复制、保存或导出。回答提交与分析合并为一次操作；未处理候选可暂存，不要求先采用全部候选。Skill、局部示例和试运行均为可选入口，默认无 Skill 路径不再要求先点“跳过 Skill”。

跳过方向性问题后，补充入口仍留在当前位置，主按钮不会错误引导确认。AI 推测与仍未知事项分别说明；采用解释是明确的单项选择。用户了解影响后可点“先做草稿”，保留未知和未核对方案标记，直接得到可查看、添加附注、复制、保存和导出的草稿。正式确认仍需要满足原有完整性与版本条件。

一次回答可以包含多个信息。程序保存提交时已有的未知项范围，模型只能对其中已有事项提出有真实原文依据的更新；不因为用户跳过、模型省略或字段存在就关闭未知。

M2 只读取程序保存的当前已确认需求快照。生成失败或迟到返回不会覆盖旧方案；普通方案编辑只递增方案版本，不改变需求版本。实际修改任务、类别或需求会保留旧方案并标记为过期，重新确认需求后可基于新需求生成新方案，旧方案进入归档。

选中需求、候选或问题后，下方详情区会显示完整内容、来源原话、用户事实／决定／系统建议、硬约束／偏好、适用范围及修改前后内容。任务、类别或关键要求改变后，旧分析依据失效，必须重新分析并复核才能确认。

末端交付：无 Skill 路径为纯程序组装，不额外调用模型；有 Skill 路径只读取本地已核验目录摘要，选择后保存绑定快照与来源，取消后按来源归属重建贡献。已确认的最终提示可主动做一次短文本试运行，输出、失败、取消、迟到响应和用量缺失都会记录并随会话保存。语气切换只改包装，不改变正文、正文 hash 或语义版本。

本地目录 `0.1.1` 的软件语境可由已确认任务描述补充，具体规格工作仍须由关键工作提供。匹配理由分别标明“任务描述”和“关键工作”的命中依据。旧 `to-spec` 绑定会因记录哈希变化进入待重新选择状态，需要重新筛选、选择并复核最终结果；原绑定快照保留。未匹配时仍可跳过 Skill。

## 检查与构建

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe run_promptsmith.py --smoke-test
pwsh -NoProfile -File scripts/build.ps1
dist/PromptSmith.exe --smoke-test
```

构建结果是单文件 `dist/PromptSmith.exe`，包含 Python、Tk、程序依赖、当前 M1-M5 提示与 Schema 以及本地 Skill 目录摘要，可以直接发送这一份文件。首次启动会由 PyInstaller 解包到系统临时目录，因此可能比后续启动稍慢。另一台 Windows 电脑仍需单独验证。

真实 API 检查脚本通过隐藏输入读取密钥，不从命令行参数接收：

```powershell
.venv/Scripts/python.exe scripts/run_m1_real_check.py
.venv/Scripts/python.exe scripts/run_ui_real_smoke.py
.venv/Scripts/python.exe scripts/run_fixed_d1_d2_real_check.py
```

这些脚本会产生调用费用，并消耗固定案例的调用预算。`verification/` 中的现有记录注明了真实模型、人工样例或本地模拟的证据类型；不要把 fixture 结果称为真实模型结果。

## 数据位置

- 用户选择的会话文件：JSON 格式，当前会话结构为 `promptsmith.session.v0.2`，旧版本可按迁移规则重开。
- 默认会话目录：`%LOCALAPPDATA%\PromptSmith\sessions`。
- 应用运行证据：`%LOCALAPPDATA%\PromptSmith\runs`。

## 代码与资产入口

| 内容 | 路径 |
|---|---|
| 启动入口 | `run_promptsmith.py`、`src/promptsmith/main.py` |
| 会话与状态 | `src/promptsmith/session.py`、`src/promptsmith/workflow.py` |
| 保存重开 | `src/promptsmith/storage.py` |
| 多协议接口与模型目录 | `src/promptsmith/api.py` |
| M1 组装、解析与校验 | `src/promptsmith/m1.py` |
| M2 组装、解析与校验 | `src/promptsmith/m2.py` |
| 运行证据与日志 | `src/promptsmith/runlog.py` |
| Tkinter 界面 | `src/promptsmith/ui.py` |
| 末端交付与 Skill | `src/promptsmith/finalization.py`、`delivery_workflow.py`、`skill_catalog.py`、`exporter.py`、`trial.py` |
| 本地 Skill 目录 | `resources/skill_catalog/catalog_v0.1.json`、`resources/skill_catalog/NOTICE.md` |
| 打包配置 | `PromptSmith.spec`、`scripts/build.ps1` |
| 提示资产与验收记录 | `output/prompt/_design/` |

## 当前提示与契约

| 模块 | 提示 | 契约 |
|---|---|---|
| M1 需求提取与动态追问 | `M1_system_v0.10.txt`；有待评估回答时用 `M1_incremental_v0.3.txt` | `m1.v0.2` 兼容扩展（`M1_input_v0.4.schema.json`／`M1_output_v0.3.schema.json`） |
| M2 完整初始方案 | `M2_system_v0.1.txt` | `m2.v0.1` |
| M3 Skill 候选分析 | `M3_system_v0.1.txt` | `m3.v0.1` |
| M4 增量整合 | `M4_system_v0.1.txt` | `m4.v0.1` |
| M5 局部示例与反馈 | `M5_system_v0.2.txt` | `m5.v0.1` |

提示正文与输出 Schema 在应用控制的指令层发送，实例输入 JSON 放在数据消息中。提示文案变化不自动升 Schema；结构或语义契约变化才升契约版本。历史提示、旧 Schema、人工 fixture 和验收证据全部保留，不追改成新版本的证据。

## 验证边界

| 检查 | 证据与结论 |
|---|---|
| 全量自动化测试 | 本轮实跑 **553 passed in 124.48s**，退出码 0；[原始日志](<../README.md>) |
| 当前单文件发行包 | [dist/PromptSmith.exe](<../README.md>)；2026-10-01 04:40:49 +08:00 构建，13,836,789 字节。旧发行保留并安装新包，没有强制关闭用户窗口；[安装记录](<../README.md>) |
| 发行链离线验证 | 源码、项目内及只含一个 EXE 的临时目录烟测退出 0；冻结 EXE 的默认无 Skill 链和第二轮截断／保存重开／主动重试链通过。[完整证据](<../README.md>) |
| 可见推测选择 | 补走接受与纠正两条桌面路径，修复空推测容器占位；5 次本地合成 HTTP 校验通过，未夹带资料预算。见[检查结果](<../README.md>)，不是实际模型效果验证 |
| 本轮 JGS 真实调用 | 修复前两次真实返回：首轮通过，第二轮没有超时／截断，但跨缺口回答语义校验失败；已据此修复并离线回放通过。修复后真实复测尚待新进程连接配置，详见[本轮交接](<../reports/verification/guided_flow_20261001/修复与交接.md>) |
| Skill 离线复放 | 原 D2 的 k1/k2/k3 均匹配 to-spec；6 个反例无匹配、旧绑定失效、来源与哈希共 14 项检查通过。[实际输出](<../README.md>)，不代表真实 M3/M4 内容通过 |
| 固定 D2 真实无 Skill 链 | M1 两轮真实调用、需求确认、M2 生成与确认、实际目录检查（结果 `no_match`）、跳过、最终提示确认、短文本试运行、保存重开与 Markdown 导出；证据见 `verification/acceptance_20260929_demo_features/real_d2_completion_20260929_$(Get-Date -Format yyyyMMdd_HHmmss)/` |
| 固定 D1 真实链 | **部分完成**：停在 M1 复核，尚未完成 M2、最终提示、真实试运行和保存重开；证据见同目录 `real_d1_d2_20260929_090433_3a76e7/` |
| 真实模型内容质量 | **仍未验收**。M3/M4 真实内容、真实有 Skill 链路、F1-F3 内容问题均未通过验收 |
| 跨机与系统 DPI | **仍未验证**：另一台 Windows 电脑、真实 125%／150% 系统 DPI 截图 |

离线测试、compileall、smoke、HTTP stub 和模拟缩放都只证明**程序链**，不代表真实模型内容质量。历史报告中的另外三组测试数与 EXE 指纹对应更早的构建，保留作历史证据，不代表当前状态。

## 相关文档

- 完整交接、已实现行为与未完成范围：[开发交接](<../development/开发交接.md>)
- 提示设计与逐轮证据索引：`output/prompt/_design/README.md`
- 固定案例与判据：`output/prompt/_design/acceptance_20260929_demo_features/固定案例与证据边界.md`
- 最新验收记录：`output/prompt/_design/acceptance_20260929_demo_features/验收结果_20260929.md`
