> 历史资料：仅用于追溯当时的设计与验证；当前状态以根目录 HANDOFF.md 为准。原始路径：`docs/superpowers/plans/2026-09-28-demo-walkthrough.md`。原始日志、截图及失效旧链接的查找方式见归档索引。

# 演示功能补全与真实走查 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在现有 M1-M4 上补齐方案确认后的导航、可选 M5 局部示例和短文本试运行，并完成 D1/D2、离线测试与发行交接。

**Architecture:** 复用现有 SessionState、Tkinter 页面、三协议 API 和 DeliveryWorkflow。M5 只产出待确认候选；试运行使用独立纯文本调用和 append-only `trial_runs`，不改变需求、方案或最终结果。导航只聚焦已有页面与控件。

**Tech Stack:** Python 3.11、Tkinter/ttk、JSON Schema、urllib、pytest、PyInstaller。

---

### Task 1: 主操作导航

**Files:** `src/promptsmith/ui.py`, `tests/test_experience_iteration.py`

- [ ] 为方案确认后的 Skill、跳过后的最终页、最终待复核、最终已确认、失效状态分别写回归检查。
- [ ] 让 `_primary_action` 返回对应动作，`run_primary_action` 只导航或聚焦，不自动重复调用模型。
- [ ] 更新需求页和方案页下一步文案，运行定向 UI 测试。

### Task 2: M5 可选局部示例

**Files:** `src/promptsmith/m5.py`, `src/promptsmith/ui.py`, `tests/test_m5.py`

- [ ] 覆盖正常 A/B、都不喜欢/跳过、迟到响应和保存重开。
- [ ] 接入单次请求、反馈候选与现有候选确认流程，保留失败状态。
- [ ] 运行 M5 定向测试和编译检查。

### Task 3: 短文本试运行

**Files:** `src/promptsmith/trial.py`, `src/promptsmith/ui.py`, `src/promptsmith/session.py`, `tests/test_trial.py`

- [ ] 记录 final revision、正文 hash、语气、协议/模型、延迟、usage、输出和错误类别。
- [ ] 以当前已确认正文发起受限纯文本调用，保护重复点击、失效版本和迟到响应。
- [ ] 增加三协议离线 stub 测试与保存重开测试。

### Task 4: 固定案例与证据

**Files:** `output/prompt/_design/acceptance_20260928_demo_walkthrough_run01/`, `docs/开发交接.md`, `output/prompt/_design/README.md`

- [ ] 分别记录 D1 无 Skill、D2 有 Skill 的真实调用或凭据缺失状态。
- [ ] 区分离线程序测试、真实模型内容检查、EXE 业务链，不混写结论。

### Task 5: 发行验证

**Files:** `dist/PromptSmith.exe`, `PromptSmith.spec`, `scripts/build.ps1`

- [ ] 运行定向及全量测试、compileall、源码烟测。
- [ ] 构建单文件 EXE，在项目外只含 EXE 的临时目录完成可控本地桩业务链并记录退出码、哈希和未验证边界。
