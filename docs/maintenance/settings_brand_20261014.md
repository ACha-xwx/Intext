# 设置扩充与统一品牌（2026-10-14）

本批规格来自用户五项新要求。全量逐页审查继续暂停；前轮修改保留。本轮增量比较起点为 `local_artifacts/settings_brand_20261014/before/`，不以整个 dirty diff 作为本轮实现。

|任务|范围|验收|状态|
|---|---|---|---|
|B1 输入框与文案|settings.js/workspace.css|重命名框复用设置输入样式；指定静态提示删除；两处简介缩短；错误仍可反馈|完成|
|B2 实际设置扩充|preferences/settings_ui及对应运行模块|字段分类、校验、自动保存和重启恢复；每项影响对应运行行为，默认兼容|完成|
|B3 品牌|用户图3、Hero/侧栏/Debug/原生窗口/spec|所有软件品牌用新图，供应商图标保留；透明浅深、小尺寸及打包入口正确|完成|
|B4 验证与增量审阅|公开Controller/生产DOM/模拟模型/资源|相邻回归、双轴审阅、交接和准确验证边界|完成|
|B5 发布交付|GitHub、PyInstaller、独立WebView2启动、桌面产物|源码推送成功；EXE离开源码目录可启动并恢复设置；桌面副本哈希一致|进行中|

新增设置范围：启动模型列表自动刷新及并发、AI推荐最低分及简介/任务上下文预算、对话宽度、通知时长、思考输出跟随及打字速度、会话自动保存检查间隔、Debug刷新间隔。参数需实际接线，不恢复已移除字体、试运行或确认按钮，不改变五轮上限/充分即停止原则。

根因：重命名弹窗输入框在 `.settings-form` 外，遗漏表单输入的局部CSS；静态提示分散在设置构建及每次快照更新。现有图标仅部分网页字标，原生窗口和EXE尚无统一品牌入口。

验证区分离线/生产Chrome DOM/实际WebView2/EXE/真实模型；不使用个人配置、密钥或会话，不请求付费模型。用户最新明确授权本轮完成后提交GitHub，构建最终EXE并放桌面；沿用授权直接执行。

用户追加：新LOGO是图形标识；Hero下方中文/英文完整字标和侧栏英文仍用之前黑白手绘SVG，浅黑深白。启动等待图形与字标均decode就绪，异常文字回退保留。

验证过程中两个小窗发现logo元素宽高约束不同，已改为正方形统一width约束；旧读秒测试在Hero进入前冻结时钟导致8项前置超时，修为先进入生产页面后安装测试时钟。目录并发测试先因私有属性名写错失败，改为通过持久化目录读取验收。Tk图形复用窗口已加载图像，避免额外加载/缺资源导致布局启动失败。所有初轮结果保留。

## 新增设置及生效范围

|字段|默认|范围及生效|
|---|---|---|
|model_directory_autorefresh|开启|启动自动目录刷新开关，手动获取仍可用|
|model_directory_workers|2|1～5，后台目录并发，下次启动生效|
|skill_min_score|0.4|0～1，按真实展示分数过滤；本地及联网共用|
|skill_description_chars|1600|200～8000，联网每项简介预算|
|skill_brief_chars|2000|200～12000，联网每项公开摘要预算|
|skill_task_chars|6000|1000～30000，任务及关键工作上下文预算|
|conversation_width|1060px|640～1800，仅WebView2，对话及输入区实时更新|
|notification_seconds|5秒|1～30，仅WebView2，已打开Debug同步，新通知采用新值，旧倒计时继续|
|thinking_autoscroll|开启|仅WebView2，思考内容是否跟随输出|
|thinking_speed|1倍|0.25～4，仅WebView2，16ms追赶倍率，保留Unicode字符|
|history_save_interval|2秒|0.5～60，后台历史检查间隔；强制保存不受限|
|debug_refresh_ms|150ms|100～2000，Web串行轮询及Tk显示更新|

全部字段校验、自动保存、启动恢复。没有新增运行字体生成。图形LOGO离线生成PNG和ICO，旧整体/英文SVG字标原样保留。

## 验证与审阅

- 当前两批XML按测试节点合并：207个不同相关节点最新全部通过，无跳过。`adjacent.xml`首轮176项有1个旧品牌日志夹具失败；`final_core_latest.xml`69项全过并覆盖该节点，保留首轮证据。源码AST/编译、五个修改JS语法检查通过。
- Spec和Standards首审问题均整改，两轴最新各0项待修：响应式宽度、阈值提示、已打开Debug通知时长、Web专属标签、减少动画恢复及品牌日志映射。
- 联网评分必须返回每项真实评分，包括低于门槛的候选，再由程序过滤，避免合法全低分误报AI失败。本地低阈值模拟覆盖0.2门槛保留0.3候选。
- 实际源码WebView2隔离双启动21项通过：真实Python bridge自动保存/恢复、重命名框共享样式、删除文案、新PNG与旧SVG、浅深主题、正常退出、没有自动运行日志。脚本见[原生验收](settings_brand_webview_check_20261014.py)，原始结果/截图在`local_artifacts/settings_brand_20261014/native_source_final/`。
- 原生脚本最初把统一输入框圆角误写为10px、把数值字符串断言为2而非2.0；改为比较真实表单样式和数值，不涉及应用修改，失败证据保留。
- 完整逐页审查仍暂停；未调用真实模型，模拟评分不能证明真实服务质量。EXE结果单独记录。

## EXE与发布

使用系统Python 3.11.9、PyInstaller 6.20构建（本机没有`.venv`），命令为`python -m PyInstaller --noconfirm PromptSmith.spec`。首份EXE在创建窗口前复现可选JSON格式校验器缺少`rfc3987_syntax/syntax_rfc3987.lark`；spec增加精确数据收集后重建，源码依赖契约不变，Standards增量复审0待修。

最终产物70,409,166字节（约67.15MiB），SHA-256：`74898acf29a1bfcc342951d162ad782986e99845f6d638b0ae8ad1e80ee3297c`。已确认归档包含该语法文件、新PNG/ICO、旧完整/英文SVG及设置脚本。

脱离源码目录，将EXE复制至系统临时独立目录，以空密钥/隔离LOCALAPPDATA启动实际WebView2；两次启动21项全部通过，与源码21项合计42项原生检查。自动保存、重启恢复、品牌、重命名样式和正常退出通过，无自动运行日志。独立Tk构造烟测退出0，无日志文件；它只证明兼容构造，不代替实际WebView2检查。结果分别在`local_artifacts/settings_brand_20261014/native_exe_verified/`和`exe_tk_smoke.json`，首份失败证据保留在`native_exe_final/`。

最终桌面文件为`Intext.exe`，与构建产物SHA-256一致。EXE包含Python运行环境，目标电脑仍需Microsoft Edge WebView2 Runtime；没有声称跨机器或真实API验证。个人配置、会话、缓存、构建产物与本地证据不提交Git。GitHub发布按本轮用户授权执行，提交身份由Git历史及最终交付记录追踪。
