# WebView2工作区、设置与模型菜单

日期：2026-10-11。当前呈现以本文为准，早期Tk说明保留作回退和历史证据。

## 目标与根因

用户录屏中的思考折叠会带动下方问答多层布局，实际Tk mainloop最小复现出现约130–145ms布局空档，多次局部flush、同步高度、定时和双缓冲实验没有稳定解决。用户已允许必要时换渲染引擎，因此采用pywebview/WebView2负责文字、滚动和动画，Python保留业务。后续追加的设置迁移、Debug统一风格、模型图标和滑动效果一并完成。

## 当前实现

- Windows `--renderer auto` 默认WebView2；`--renderer web`明确使用Web，`--renderer tk`保留原生回退。主工作区和五类设置同窗，Debug独立WebView2窗。复杂方案/需求编辑仍可能打开Tk兼容窗，本次未将所有编辑器重写。
- 主界面和设置125%字号，模型菜单、思考正文和Debug100%；浏览器用系统默认字体，Tk回退从平台默认字体派生内存对象，无字库生成/写盘。
- 菜单参照用户最后图2及TSX：能力胶囊右侧垂直居中，SVG对勾紧邻模型名；左供应商背景滑动，DeepSeek图标31px而其它24px以补偿视觉留白。DeepSeek只展示推理图标。
- 四柱信号高度5/7.5/10/12.5px，宽3px/间距2px，已点亮用前景色、未点亮用边框色；底部信号、思考强度、Low/Medium/High/Max滑块同行。供应商与强度300ms cubic-bezier(.22,1,.36,1)，保留连续动画。
- model/effort独立顺序保存队列、即时强度反馈，不触发全局pending灰显。新会话丢弃旧队列及迟到选择回包；已获取/当前自定义模型也可选择，未知ID被拒绝。
- 删除空任务按钮、输入框紫色焦点框、菜单底部接口说明。OpenAI目录按用户截图补齐8款建议；预设不表示接口或账户实际支持，未调用供应商验证。
- 问题逐条回答/跳过、Enter提交/Shift+Enter换行，需求/方案/任务摘要锚定弹层及Skill表格/结果操作继续使用现有SessionState。动画由CSS/rAF承担，思考保留grapheme逐步追赶和独立滚轮。

## 线程、设置与诊断

`WorkspaceController`在创建Tk的线程读取/更新原有业务。Web API线程只交换普通JSON数据，`DesktopApi`排队动作/读取锁内快照。会话stamp、设置revision、原workflow确认及取消保护继续有效。首次快照失败能显示重试；后续同步恢复不会抹掉编辑草稿。关窗解除等待并释放业务和Debug窗口。

五类设置复用FIELDS及原保存/测试/确认/获取模型/目录处理。测试不确认；确认只提交模型分类，其他草稿保持，已有确认可加密保存和恢复。已保存密钥只返回has_key，不返回明文；新输入仅提交Python并立即注册脱敏，成功后清空浏览器输入。持久化仍为Windows当前用户DPAPI，无明文回退。

Debug使用普通数据适配器，不持有Tk对象。后台忙时可独立开启。级别筛选/清屏只影响显示，保存使用RuntimeLog的完整记录，包含缓存外历史与异常原因。INFO白、WARN黄、ERROR红、DEBUG蓝、CRITICAL亮红，字号100%。窗口开关、业务动作、同步错误、浏览器未捕获异常/拒绝和主线程长任务均有日志；仍只有点击保存日志才写运行日志文件，模型runs证据保持原合同。

WebView2预检在业务启动前进行，拒绝旧MSHTML。缺运行时或依赖时auto回退Tk；显式web有安装Runtime/回退启动提示。spec加入整个workspace目录及webview数据/WinForms/EdgeChromium依赖声明。

## 验收与边界

最新13模块225个去重定向/相邻检查、35项Chrome离线DOM，以及实际WebView2双窗/设置/动画/长Unicode/Debug保存检查通过。Tk基线与Web布局采样比较见[验收报告](../../verification/webview_workspace_20261011/results.md)。所有测试使用隔离数据目录和合成任务，不调用真实模型或改个人生产配置。实际布局采样不能证明屏幕180Hz呈现或消除所有显卡/合成撕裂；用户录屏反馈仍是实际体验的后续依据。新版EXE与跨机Runtime/CLR依赖需独立构建验收。

## 主要文件

`src/promptsmith/web_workspace.py`、`web_debug.py`负责桥接/生命周期；`resources/ui/workspace/`包含主工作区、设置和Debug。`ui.py`只增加可选Debug工厂；`main.py`选择呈现引擎。`model_catalog.py`和`api.py`维护模型建议/协议参数，`settings_ui.py`保留Tk回退并修复恢复默认的旧Text更新错误。

记录维护于[任务计划](task_plan.md)、[发现](findings.md)、[进度](progress.md)；没有提交、推送或构建EXE。
