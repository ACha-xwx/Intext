# Debug 图例与历史阅读验收

2026-10-12。源码已完成；默认 WebView2 与 Tk 回退均已同步。

## 修改范围

生产文件：`resources/ui/workspace/debug.html`、`debug.css`、`debug.js`、`src/promptsmith/debug_console.py`。测试：新增 `tests/test_debug_legend.py`，扩展 `tests/test_debug_console.py`。维护记录及当前交接同步；不修改 RuntimeLog 采集、脱敏、归档和模型流程。

本轮基线为开始工作时保存的 `before/`，保留原有未提交改动；`delta.patch` 与 `manifest.json` 对上述六个文件记录差异和 SHA-256。局部证据、图片与脚本保持本地忽略，不提交个人数据或生成物。

## 红灯与根因

真实生产 DOM 的初始反馈环三项失败：无图例；上翻 180px 后新增日志跳至 2057px；缓存淘汰后所读条目跳位。Tk 的正常 Typography 初始化夹具三项同样失败：无图例，history-14 跳到 history-59，anchor-24 跳到 anchor-43。

追加边界红灯发现 Web 长记录内裁剪跳 123.98px、Tk multi-15 跳到 multi-20；缓存上限改为 30 后无新日志仍显示 100 条；五轮闲置轮询产生 10 次状态 DOM 变更。均已修复并通过当前回归。

原因是无条件跟随底部、删除/重建没有具体行锚点，以及布局信息在恢复位置后更新。实现及计数定义见[维护说明](../../docs/maintenance/debug_legend_20261012.md)。

过程错误单列：直接创建 Tk 控制台的夹具缺少正常 Typography，先出现 setup 错误，修正夹具后才记录真实红灯；键盘筛选测试最初使用会随隐藏动作缩短的动态 nth 列表，改为逐项操作；原生首轮计数比较跨越 ready INFO 日志追加，隐藏日志等待又硬编码了初始 INFO 数，改为等待实际基数后严格比较，不调整生产代码满足断言。一次 PowerShell 使用 Bash heredoc 被解析器拒绝，未执行任何文件操作。WebView2 初轮端口占用由库另选端口，最后运行正常。

## 最新验证

- 52 个不同自动化节点全部通过：15 个新 Web DOM 场景、5 个新 Tk 交互场景及相邻日志/桥接/错误恢复测试。`final-targeted.xml` 与其后的 `final-browser.xml` 按节点取最新结果去重，0 失败/错误/跳过。
- 真实 WebView2：`scripts/native_debug.py` 加载生产 Debug 资源、真实 DebugApi/RuntimeLog 和合成日志，临时目录隔离，14/14 通过。包含显示/隐藏计数、灰显、历史位置、回到底部跟随、关闭跟随、闲置不刷日志、清空与完整手动保存；结果 `native-debug.json`，运行内核 Edg/154.0.0.0。
- Chromium 浅深及 600×400px/18pt 图片已目视检查，图例可达、隐藏灰显，日志区域可滚动。图片不冒充原生连续录像。
- 185项机械检查通过，涵盖 Python AST/JS 语法、六文件独立 SHA-256、局部差异空白及文档链接；CodeGraph 已同步且 current（210 files / 5342 nodes / 16810 edges）。需求与规范两轴最终均 0 项待修，详见[审查](review.md)。

主要自动化命令：

```powershell
python -m pytest -q tests/test_debug_legend.py tests/test_debug_console.py tests/test_web_debug.py tests/test_runtime_log.py tests/test_frontend_review_regressions.py::test_debug_recovery_clears_sync_error_but_retains_copy_error --tb=short --junitxml=verification/debug_legend_20261012/final-targeted.xml
python -m pytest -q tests/test_debug_legend.py tests/test_frontend_review_regressions.py::test_debug_recovery_clears_sync_error_but_retains_copy_error --tb=short --junitxml=verification/debug_legend_20261012/final-browser.xml
python verification/debug_legend_20261012/scripts/native_debug.py
```

本轮未运行完整仓库测试、真实模型或新版 EXE；不宣称全套或真实模型验收。无需调用模型即可验证本次 Debug 交互。没有个人设置/历史读写、提交或推送。
