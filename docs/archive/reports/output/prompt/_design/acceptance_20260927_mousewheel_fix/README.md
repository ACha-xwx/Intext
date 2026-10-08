> 历史资料：仅用于追溯当时的设计与验证；当前状态以根目录 HANDOFF.md 为准。原始路径：`output/prompt/_design/acceptance_20260927_mousewheel_fix/README.md`。原始日志、截图及失效旧链接的查找方式见归档索引。

# 鼠标滚轮修复验收记录

本目录保存 2026-09-27 滚轮修复的新增复现、事件回归、运行结果和发行包记录。原始失败证据仍保存在同级 `acceptance_20260927_mousewheel/`，不覆盖。

## 验收范围

- 主窗口当前页上页面空白、标签、按钮、单行输入框、空 Text 和空 Treeview 的滚轮可推动页面。
- 长 Text、只读详情和长 Treeview 优先内部滚动；到达边界后的下一次事件交给页面。
- 需求页与有溢出的方案页互不串滚；无溢出时不抖动。
- 弹窗和其他顶层窗口隔离；未展开 Combobox 不改变选择，展开下拉列表不穿透主页面。
- 正负、大小、连续小 delta、方向/目标切换、delta=0、重复 refresh、关闭和多实例清理。
- 纵横滚动条、文本、配置、需求版本和确认状态保持不变。

## 证据类型

事件回归使用 Tk `event_generate` 并设置屏幕坐标，使已注册的 bindtag 与真实控件事件路径参与处理；它不等价于物理鼠标输入。发行包 smoke test 只证明可启动和退出，不证明最终 EXE 的物理滚轮体验。

## 本轮结果（2026-09-27）

- `tests/test_mousewheel.py`：13 项通过。菜单用例验证原生 `Menu` 不附加页面滚轮 bindtag；原生菜单窗口的实际弹出与滚轮由人工验收覆盖，避免 Tk 合成菜单事件在测试环境中阻塞。
- 全量 `.venv/Scripts/python.exe -m pytest -o addopts='' -q --junitxml=pytest_full_final.xml`：189 项通过，0 失败；报告见 `pytest_full_final.xml`。
- `.venv/Scripts/python.exe -m compileall -q src run_promptsmith.py scripts`：退出码 0。
- `scripts/verify_ui_layout.py layout_final.json`：1120×780、当前 Tk scaling 及模拟 125%/150% 均通过。模拟缩放不等同于 Windows 系统 DPI 实测。
- `probe_mousewheel_fix.py observed_mousewheel_fix_final.json`：7/7 检查通过，Tk 8.6.12/win32，无回调错误；模型调用数为 0。旧的 3 单位滚动探针 `observed_mousewheel_fix.json` 保留作历史迭代证据。
- 用户已在最终修复后手动验证滚轮体验；该记录覆盖自动化无法稳定驱动的真实菜单/窗口交互，但未扩展为另一台电脑或不同系统 DPI 验收。

## 发行验证

- `pwsh -NoProfile -File scripts/build.ps1` 成功。
- 当前 `dist/PromptSmith.exe`：2026-09-27 13:27:50 +08:00，13,339,481 字节，SHA-256 `BEAEB563453E4CFC7E2E63285B6985D294433A9AF65EBAB24E7A9ED658ED2B2C`。
- 项目目录与只含一个 EXE 的临时目录 `C:\Users\yph\AppData\Local\Temp\PromptSmith_mousewheel_final_0ec6742d7b8c43b9a003a7af1abcc718` 均用 `Start-Process -Wait ... --smoke-test` 退出码 0；隔离目录只含 `PromptSmith.exe`。

## 限制

- 本轮没有真实模型调用，滚轮修复不依赖模型。
- 当前桌面自动化接口没有可用窗口；用户人工验证已完成，但另一台 Windows 电脑和真实 125%/150% 系统 DPI 仍待团队复核。
