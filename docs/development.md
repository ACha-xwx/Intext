# 开发、检查与打包

2026-10-14 首次配置回归使用真实WorkspaceController字段schema驱动生产DOM，覆盖空模型ID时先保存服务/密钥以及教程解锁。数值字段step按后端类型提供，不按JSON默认值是否恰为整数猜测。默认数据根迁移为Intext；原生验收脚本为`maintenance/provider_onboarding_webview_check_20261014.py`，支持源码与`--exe`，仅请求localhost模型目录。详见[维护](maintenance/provider_onboarding_20261014.md)。

2026-10-14 设置与品牌：重命名框统一输入样式，删除指定静态说明，五类简介精简且无句号；新增12项有实际运行接线的偏好并支持自动保存/启动恢复。图形品牌统一用户新LOGO，Hero完整字标和侧栏英文保留原黑白手绘SVG，运行不生成字体/图像。207个不同相关节点最新通过，实际源码WebView2隔离双启动21项通过，Spec/Standards最新各0项待修；完整逐页审查仍暂停，没有真实模型请求。EXE独立WebView2双启动21项及Tk构造烟测通过，最终Intext.exe已放桌面且哈希一致；实现提交99881a9已推送GitHub main并确认远端一致，详见[维护](maintenance/settings_brand_20261014.md)。

2026-10-13 Intext 启动：新增启动 Hero，加载就绪后按教程状态分流；本地液态金属 shader 和 Apache 许可随 workspace 整目录打包，运行不需要 Node/CDN。修改入口同时检查 `tests/test_startup_hero_browser.py`、tutorial、Debug/导出/偏好/历史相邻用例；原生隔离验收脚本为 `maintenance/intext_hero_webview_check_20261013.py` 与已适配 Hero 的 `maintenance/tutorial_webview_check_20261013.py`。这些检查不调用真实模型。EXE 名称现为 Intext，包名、旧设置/会话/加密上下文保持兼容；完整标题与侧栏英文SVG已就绪，本轮没有重新构建EXE，见[维护](maintenance/intext_hero_20261013.md)。

2026-10-12 团队启动修复：`run.bat` 固定项目目录、优先 `.venv/Scripts/python.exe`、默认传入 `--renderer web`，并保留参数、失败信息和退出码。缺 pywebview 时错误给出当前解释器的安装命令；不再通过此入口静默退回旧界面。直接 Python 的 auto 模式和显式 `--renderer tk` 仍保留。详见[跨机启动与 GPT 400 修复](maintenance/startup_responses_20261012.md)。

2026-10-12 GPT Responses：业务输出 Schema 中的可选属性、开放对象及不支持的组合关键字，在发送前选择 `text.format.type=json_object`，完整 Schema 放入 instructions，由原有本地解析处理；兼容 Schema 保留原生 strict 模式。仅当服务明确拒绝输出格式时允许一次无原生格式兼容请求，其他400不重试。GPT 原始思考不可见不影响正文；不向 GPT 添加 DeepSeek 的 thinking 参数。验证为本地 HTTP 合成服务，无真实模型调用。

同轮全模型检查覆盖19个预设与四档，Claude按独立Schema子集选择native或system契约，并显式请求公开摘要；DeepSeek Messages不发送不支持的Claude原生format。已知思考模型不再被实际会省略的采样组合提前阻止，未知模型检查仍保留。改动模型目录/协议参数后同时运行 `tests/test_provider_requests.py`、`tests/test_responses_schema_compatibility.py`、`tests/test_api.py` 与 streaming/预算相邻检查；不要把本地HTTP通过写成真实账号验收。

2026-10-11 访谈可靠性：新增 `tests/test_interview_reliability.py` 覆盖等待日志、判重/同 gap答案、提示规模及三协议完整请求；修改M1契约时同时运行当前资源、增量重试、来源/冲突与访谈完成相邻检查。请求诊断记录UTF-8字节和服务usage，字节降幅不是token或服务提速实测值。默认思考强度、max_tokens、timeout保持用户配置，不能通过降档或截断缩短等待。最新300节点296通过/4既有差异及其before复现见[验收](../verification/interview_reliability_20261011/results.md)；本轮无新真实请求或EXE。

2026-10-11 历史会话：新增 `session_history.py`、`history_workspace.py` 和 workspace/history.js；使用 `tests/test_session_history.py`、`tests/test_history_workspace.py` 验证索引懒加载、原子失败、旧导入、草稿和完整步骤恢复。后台历史文件会自动保存，Debug运行日志仍手动保存，两种合同不能混淆。spec已收集workspace整个目录，新增JS随源码资源进入打包声明；没有构建EXE。见[维护](maintenance/history_sidebar_20261011.md)和[验收](../verification/history_sidebar_20261011/results.md)。

2026-10-11 Windows源码默认WebView2：`python run_promptsmith.py` 或 `--renderer web` 打开浏览器主工作区及同窗设置，Debug为独立WebView2窗；`--renderer tk`保留原生回退。安装项目依赖会包含pywebview/pythonnet，电脑另需Microsoft Edge WebView2 Runtime。auto预检缺依赖/Runtime会回退，显式web显示启动提示；不会采用旧MSHTML。`--smoke-test`仍是Tk构造检查，不能用来证明Web呈现，Web源码烟测须实际打开并关闭浏览器。spec收集workspace全目录和webview数据/WinForms/EdgeChromium依赖声明；单独EXE最终需重新构建及脱离源码目录验收，本轮未构建。改动边界与225项定向/相邻、离线DOM和真实WebView2证据见[本轮报告](../verification/webview_workspace_20261011/results.md)。

2026-10-10 最新交互：全局原生字号改为125%；顶部需求核对/摘要锚定展开面板，删右上保存和旧需求详情/M5用户功能。底部采用用户玻璃按钮/圆角动画菜单的整理深度与任务类型；逐题紧凑圆角回答与图形发送/跳过，模型不生成可选建议；思考高度/chevron动画和独立滚轮已接入。当前范围与验证见[十项交互说明](maintenance/ui_refinement_20261010.md)，以下较早说明若冲突以本段及新说明为准。

整页样式限定于主工作区，保持默认设置组件。运行 `tests/test_response_workspace.py` 可验证连续主题、无原生分区和3000事件先完成/后流式消费的保存屏障；它应保持保存重开业务对象等价，不能用放宽断言替代时序修复。

2026-10-10 回复/流式检查：`streaming.py` 使用标准库处理三协议 SSE，`response_ui.py` 复用原生 Tk 和输入组件的图形按钮/细滚动条，没有新增字体、浏览器或 Markdown 运行依赖。重点运行 `tests/test_streaming.py`、`tests/test_response_workspace.py` 与对话/取消/访谈/Debug 相邻用例；localhost SSE 与合成模型返回属于离线证据，不能声称真实供应商质量。模型响应公开思考只展示/保存，不进入下一次输入；背景操作和异常日志仍仅手动保存。见 [维护说明](maintenance/response_workspace_20261010.md)。

2026-10-10 默认字体：自定义与混排链已撤除，`typography.ui_font()` 只派生平台默认字体的内存对象，不硬编码族名。没有字库缓存、字体准备线程、FontTools 运行依赖或动态打包模块。旧字体偏好读取忽略，普通保存/Debug 独立保存均剔除旧字段；不删除用户旧缓存。详见 [说明](maintenance/native_fonts_20261010.md) 与 [验收](../verification/native_fonts_20261010/results.md)。

2026-10-10 图标与组件：Pillow 仍是运行依赖，用于平滑图标缩放/选中勾；PyInstaller spec 保留模型图标和 `resources/ui/PromptSmith.manifest`。DPI 初始化在 Tk 创建前。模型菜单隐藏复用，主题/字号变化释放旧菜单；新增文本控件使用 `ui_font()`。当前源码验证不等于新版 EXE 验收，本轮未重建 EXE。

## 环境与首次启动

开发基线为 Windows、Python 3.11+、Tk 8.6。标准 Windows Python 安装须勾选 Tcl/Tk。当前发布验证围绕 Windows，不声称已完成其他平台验收。

在仓库根目录执行：

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m tkinter
.venv/Scripts/python.exe run_promptsmith.py --renderer web
```

`-m tkinter` 是可选的 Tk 安装检查，会打开测试窗口。依赖包括 jsonschema、Pillow、pywebview（Windows，附带 pythonnet）、pytest、PyInstaller；电脑还需安装 Microsoft Edge WebView2 Runtime。本地环境不提交 Git，无需从开发者机器复制虚拟环境。安装完成后可使用根目录 `run.bat`，其参数可覆盖默认模式，例如 `run.bat --renderer tk`。

## 模型与数据

桌面设置现在按五类保存，公开偏好集中在 `preferences.py`，UI 由 `settings_ui.py` 管理。新增设置同时补字段范围/默认、真正的运行接线、请求快照、确认失效、Debug 与定向验证；`settings.json` 存普通偏好、公开连接与 DPAPI 加密的 API Key，禁止明文或弱加密回退。加解密由 `credentials.py` 负责，日志只记录凭据是否存在和系统错误码，启动密钥先注册脱敏后使用。测试用 `evidence_root=tmp_path / "runs"` 或 `diagnostics_root=tmp_path` 隔离配置，避免污染生产目录；原生凭据测试仅用合成密钥。完整清单见 [设置盘点](maintenance/settings_audit_20261009.md)，安全边界见 [凭据保护](maintenance/settings_security_20261009.md)。

通过右上角“设置”选择服务与协议、填写 Base URL/API Key、获取并选择模型 ID。修改自动保存，有效配置自动生效；“测试连接”仅探测接口，启动后台模型目录刷新仅获取列表。普通启动不调用付费生成 API，真实分析、搜索查询/筛选及生成使用已生效配置。GitHub Token 是搜索增强项，使用者自行配置；不要把账号密码或 Token 写入代码。

环境选项以代码实际读取为准，如 `PROMPTSMITH_GITHUB_TOKEN`、`PROMPTSMITH_RESOURCE_ROOT`；后一项用于资源目录定位，不需要普通用户设置。会话 JSON 和运行记录位于 `%LOCALAPPDATA%/Intext/` 或用户选定位置，可能含用户输入，不作为默认 Git 素材。首次默认启动整体迁移旧 `PromptSmith` 数据目录；两目录均有内容时使用 `Intext`、保留旧目录且不合并覆盖。旧加密身份保持不变，显式测试目录不会触发默认目录迁移。

## 按改动范围验证

```powershell
# 资源加载与窗口初始化
.venv/Scripts/python.exe run_promptsmith.py --smoke-test

# 语法检查
.venv/Scripts/python.exe -m compileall -q src tests scripts

# 当前提示与 Skill 交接等关键路径示例
.venv/Scripts/python.exe -m pytest -q tests/test_m1_current_asset_versions.py tests/test_m5_asset_version.py tests/test_skill_handoff.py tests/test_ui_skill_ai_flow.py tests/test_ui_delivery_interactions.py

# 全量检查：现有历史失败详见 verification；不要以退出非零就推断本次修改引入
.venv/Scripts/python.exe -m pytest -o addopts='' -q
```

`tests/test_ui_*` 和滚轮测试会创建 Tk 窗口，需要可用桌面。测试通常通过 fixture/本地模拟服务验证程序行为；实际内容质量与用户感受另验。新改动只重跑对应检查；迁移资源等跨模块改动需要更广覆盖。

历史真实检查脚本：`run_m1_real_check.py`、`run_ui_real_smoke.py`、`run_fixed_d1_d2_real_check.py`、`verify_m2_generation_real.py`。它们会产生 API 费用，先读 `--help` 和脚本版本说明，按明确授权与预算运行。固定案例脚本保留历史语义，部分旧断言与现产品已有差异。

## 构建

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1
dist/Intext.exe --smoke-test
Get-FileHash -LiteralPath dist/Intext.exe -Algorithm SHA256
```

单文件 EXE 包含 Python、Tk、依赖和 spec 列出的运行资源，AI 模型仍通过网络服务调用。首次运行会解包到临时目录。构建不上传产物；源码仓库忽略 `build/` 与 `dist/`。

发布前记录提交 SHA、Python/依赖版本、构建时间、EXE 大小与 SHA-256；将 EXE 单独复制到临时目录验证启动，避免源目录掩盖漏打包的资源。真实跨机验证须在另一台电脑执行，独立目录测试不能替代。

## 资源改动

`resources/prompts/` 存放当前与兼容提示、Schema、人工样例。`paths.py`、各 `M*Assets.load()` 和 `PromptSmith.spec` 必须一致。历史提示可能仍被旧会话、测试或打包引用，不因文件名版本较低直接删除。

样例目录 `examples/`、`examples_m2/`、`fixtures_m3_m4/` 用于离线检查；它们不代表实际模型返回。文件夹原名保留以降低迁移风险。

`resources/skill_catalog/sources/` 是固定的第三方原文快照，目录记录校验文件字节。`.gitattributes` 对这些文件关闭换行转换，避免 Windows/Git 自动转换导致 SHA-256 不一致。升级原文时须同步来源、许可、内容哈希、记录哈希和目录版本。

`pyproject.toml` 提供源码项目元数据。当前正式分发路径是源码仓库或 PyInstaller EXE；没有将所有外部资源定义为可独立发布的 wheel，不能假定 `pip install` 后即可脱离资源目录运行。

## 出错时

先记录版本、复现输入、阶段、错误类别和日志位置，不在截图里暴露密钥。参照 [踩坑记录](pitfalls.md) 找对应入口。判断是网络/模型内容、结构契约、业务状态还是 UI 呈现，再做定向修改。

当前宽松接收机制优先让可用模型内容进入提示词；不能仅因多余字段、建议覆盖、Skill 前提未知或示例细节不齐而要求用户重做整个流程。修复动作记录为 WARNING 与结构化 normalization，未核对内容进入最终提示；内部来源、取消、版本和用户确认继续保护。检查命令为 `python -m pytest -q tests/test_model_output_recovery.py`，跨模块范围与原始回放结果见 [宽松接收验证](../verification/validation_relaxation_20261009/results.md)。新增失败分支需要用户下一步入口及完整 traceback，错误提示不能被刷新覆盖。

## 功能改动与 Debug 同步

每次新增或修改功能，都要在同一批改动中检查 Debug 诊断：记录开始/完成状态、后台任务标识、失败原因和完整异常链；新增降级分支不能静默吞掉错误；必要时补充定向测试和控制台展示。控制台颜色约定为 DEBUG 蓝色、INFO 白色、WARNING 黄色、ERROR 红色、CRITICAL 亮红色。运行日志只采集到内存，Debug 窗口的“保存日志”按钮才保存完整快照到应用数据目录的 logs 文件夹；定位故障后退出前保存，失败可重试。筛选和清屏不限制保存范围，既有模型 runs/ 证据保持原机制。功能验证完成前，同时确认不自动写盘、手动保存、脱敏和窗口呈现没有回归。

公共模型边界现记录 `Model JSON input cost`（system/payload/原 payload/schema UTF-8 字节、引用答案数）与 `Model response usage`（服务端提供的输入/输出/思考及推算可见 token）。缺失字段为 None，不用字节估算填充真实 usage；不记录正文或密钥。Skill 日志另记录模型步骤省略和查询缓存命中，没有逐帧或等待态重复日志。优化回归包括三协议原参数/来源可重建、查询缓存隔离/TTL/失败/取消、一次小集合内容核验与 Responses 明确格式兼容分支。离线合成计量及测试入口见[Token 效率验收](../verification/token_efficiency_20261012/results.md)，真实服务思考成本和加速须另用服务端 usage 验证。
