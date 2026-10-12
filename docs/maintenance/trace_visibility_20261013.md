# 思考入口显隐与计时布局

用户要求：没有思考内容（例如未返回公开思考的GPT）不显示内层思考下拉栏；计时和外层箭头不能相挤。

范围：`workspace.js`、`workspace.css` 和显式Tk回退的 `response_ui.py`；沿用SessionState、模型请求、思考强度及完整输出。实际返回的非空reasoning决定显隐，不凭模型名字禁用公开摘要；首个非空分片到达后恢复入口，保留用户折叠选择。活动、错误、计时和取消信息保留；新Debug只记录显隐变化及trace ID，无正文、逐帧日志或自动写盘。

根因：两种呈现均无条件显示内层按钮/正文容器；Web共用chevron只有右margin，旋转后的实际边界压进label约1.45px。最小修复同步内层显隐、隐藏时返回可见控件焦点，外层箭头单独增加10px左间距。

验收：空/空白及各种终态无空入口，首片/历史非空可读，重复快照保留展开，取消/恢复及计时继续工作；浅深、9/12/18字号、11.1–3600秒间距不小于8px，三位等宽变化箭头不抖动。测试使用已授权生产DOM快照/隔离Tk边界，不发收费请求或访问个人设置。

本轮增量基线：`local_artifacts/trace_visibility_20261013/before/`，应用diff保存在同级 `incremental.diff`；保留供应商和历史补答的已有未提交成果。

先红后绿记录：空Web入口1项、空Tk入口1项、浅深×三档字号间距6项，均捕获原症状再修复；隐藏焦点转移另有独立红绿。新增15项覆盖空白/四种状态、首片、用户开关、Unicode、活动与错误、计时、诊断去重和焦点。

最终执行以下集合，59个不同节点全部通过（含上述15项）：

```powershell
python -m pytest tests/test_thought_visibility.py tests/test_trace_timer.py tests/test_requirements_inline_browser.py tests/test_response_workspace.py tests/test_ui_refinement.py::test_thinking_animation_is_reversible_and_wheel_is_owned tests/test_popover_animation.py::test_reasoning_font_keeps_original_size_across_stream_and_theme -q
```

相关证据包含生产Chrome DOM快照与隔离Tk实际组件/流式，未调用真实模型、访问个人设置、验收原生WebView2或构建EXE；前轮未提交改动保留，本轮未提交/推送。Python AST、JS语法、diff空白通过；CodeGraph同步后current（226文件/5709节点/17899边）。

## Standards

独立只读审查0待修。显隐仅依据实际非空思考内容，不改SessionState、请求或取消路径；Web/Tk保留容器、用户展开状态和Unicode动画。Debug仅状态变化时记录ID/布尔值，符合手动保存规范，无正文或密钥；没有需单列的Fowler异味。

## Spec

独立只读审查0待修。无实际内容隐藏内层入口；首个非空分片恢复，保留用户折叠选择、计时、活动、错误和取消提示。间距只作用于外层箭头，不改变模型请求、强度或业务状态。

双轴各0待修。已核对离线Chrome浅深截图（临时成果在local_artifacts）；这些证据不代表实际WebView2、真实模型或EXE验收。
