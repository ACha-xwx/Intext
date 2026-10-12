# WebView2与模型菜单验收

日期：2026-10-11。交付为源码，未调用真实模型、未构建新版EXE，未修改用户生产配置。

## 定向与相邻回归

13模块共225个不同测试节点，按每个节点最新完成JUnit结果合并：225 passed，0 failed/error/skipped。覆盖Web桥接及过期动作、逐题/跳过、会话取消/SSE、充分提前结束、模型参数、确认恢复/加密设置、RuntimeLog/Debug和启动回退。不是整个仓库全量或真实模型质量结果。

本地证据在忽略目录 `local_artifacts/ui_performance_20261011/`：`final-tests.json`列出节点与来源。合并来源为`bridge-model-first.xml`、`settings-debug-final.xml`、`bridge-final.xml`、`adjacent-final.xml`、`startup-final.xml`、`animation-test-final.xml`，同节点以最后一次完成结果为准。

初次设置两项失败定位到不存在的`_set_text`，生产代码改为Text.delete/insert，后续131项组通过。新预检fixture两项因webview.guilib同名None属性误patch而失败，改显式模块后6项通过。相邻组初次83/84通过：一项Tk回退动画固定0.5秒等待未覆盖最后一帧，改为有界等待真实progress=1，浅深两项复验通过。初次失败文件保留，不计作成功。

## 浏览器离线检查

35项Chrome真实DOM检查通过，DesktopApi为模拟接口。覆盖图2能力胶囊右侧居中、名称旁勾、原信号尺寸/颜色及两组同步、8款OpenAI、DeepSeek仅推理/图标比例、供应商滑动、强度连续切换无灰显、设置五类/125%/草稿和焦点保留/Key清空、忙态Debug开关、720×440小窗、思考独立滚动/外层快速双向滚动、Enter/Shift+Enter和首次同步失败恢复。无未捕获JS错误。

证据：`browser-checks.json`及`picker-light.png`、`picker-dark.png`、`settings-dark.png`、`settings-model-dark.png`、`settings-small.png`、`conversation-light.png`。截图已目视核对；合成任务不代表真实模型回答。

## 真实WebView2检查

本机pywebview6.2.1，实际Edge154。`native_web_checks.py`使用真实WebView2与Tk所属线程桥接，隔离LOCALAPPDATA/测试凭据，未执行模型请求。

- 主窗八项通过：每次折叠都有中间布局、无超过85ms的过渡布局空档、设置同窗且Tk隐藏、明确模型确认、确认不提交非模型草稿、Key输入清空、字号保存反映、长Unicode持续渐进显示。
- 实际创建主窗与Debug两窗，Debug未保存时无文件，手动保存后完整档案含五级及显示缓存外/清屏前记录。自身JS ErrorEvent的堆栈记录入ERROR且可保存，级别颜色/100%字号生效，退出无窗口或桥接错误。
- 独立源码Web启动烟测退出0。预检缺Runtime时auto回退/显式web提示通过离线测试；未在真实缺Runtime电脑复现。

证据：`native-web-checks.json`和`smoke_web.py`。Debug快照字号13pt→17.3333px，仍为100%，用于核对比例而非固定字体族。

## 性能测量

| 相同折叠交互 | Tk真实mainloop基线 | WebView2最终rAF/DOM布局采样 |
|---|---|---|
| 内层每次实际高度变化 | 6–8次 | 63–64次 |
| 最大过渡布局空档 | 144.7ms，部分展开130.9ms | 最终八次均不超过27.8ms |
| 长Unicode显示 | 保留原功能作回退 | 123次渐进更新，不整段跳到末尾 |

Tk基线见`before-repeat/metrics.json`，失败实验仅存在本地隔离目录，未进入生产。Web八次包含内层/外层展开收起，最终详见`native-web-checks.json`。两个引擎动画时长、布局组件和采样方式有差异，表格用于判断原跳变是否缓解，不是公平的GPU吞吐基准，也不能证明180Hz实际呈现、用户显卡上的撕裂或所有场景流畅。

## 静态及发布边界

Python编译、三个JS语法、63个spec资源入口/7个workspace文件及HTML引用、137个当前文档相对链接和差异空白检查通过。CodeGraph已按最终源码同步：172files/4462nodes/14084edges，包含3个JS文件，Index is up to date。spec收集workspace全目录及webview数据与平台依赖声明，但当前只有源码启动证据；新EXE打包、跨机启动、无Python/Node环境及缺Runtime体验须另验。复杂编辑仍可能打开Tk兼容窗，主工作区/设置/Debug的迁移不等于所有编辑窗口重写。

实现与约束见[本轮维护](../../docs/maintenance/webview_workspace_20261011.md)。
