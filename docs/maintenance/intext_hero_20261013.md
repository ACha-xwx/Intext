# 意织 · Intext 启动 Hero

## 规格与边界

依据用户本轮要求，界面产品名改为 Intext；启动 Hero 标题为「意织 · Intext」，分隔点两侧留独立间距。用户进一步明确整个「意织 · Intext」一起离线转为一个SVG轮廓，不只转换英文；Orange Juice没有中文字形，用户随后提供AI生成的中文手绘PNG，提取其描边与排线路径，与英文轮廓合为一个SVG，字体等待已经解除。不随启动生成字库、不分发字体文件。Orange Juice字体内置许可注明个人/非营利用途免费，商业使用需字体作者授权。

两个启动分支均先显示用户提供的 MorphingSquare 动画（40px，6%→50%→6%圆角，0→180→360度，2秒 easeInOut循环）。本地工作区快照和标题资源就绪后：not_started 显示圆形银边开始按钮，使用提供的 play.svg；点击后进入工作区并开始操作教程。completed 直接进入工作区；skipped 沿用用户此前跳过选择，也直接进入，不冒充 completed。所有 Hero 元素作为一个组在整窗中央居中，浅深主题、窄窗和减少动画可用。

银边按钮复用参考的液态金属 shader、参数、空闲/悬停/点击速度、黑色内圈、按压和涟漪，静态降级不阻断进入。工作区不抢先显示教程；只有教程最后一步完成才保存 completed。模型目录后台刷新不阻塞 Hero、不产生模型调用。

品牌改动涵盖主窗/侧栏/Debug/原生回退/启动提示/导出与EXE名称；内部 Python 包、旧文件格式、加密上下文和 %LOCALAPPDATA%/PromptSmith 路径保留兼容，避免旧设置、密钥和历史失联。

## 任务与验收

|任务|主要范围|验收标准|依赖|状态|
|---|---|---|---|---|
|H1 启动分支|startup.js/css、index、tutorial/workspace、生产DOM|先加载；初次点开始才开教程；完成/跳过自动进入；重复快照不重开|无|complete|
|H2 标题与按钮|SVG、shader本地资源、Hero样式|字体轮廓和play原图、动画参数/生命周期、浅深及小窗居中|H1|complete|
|H3 品牌与Debug|窗口/导出/入口/spec、诊断|用户可见Intext，兼容旧数据，生命周期/错误完整脱敏、无逐帧日志|H1|complete|
|H4 回归与审查|相关公开测试、原生WebView2、双轴review|教程/设置不回退、异常可恢复、两轴发现关闭、准确记录边界|H1-H3|complete|
|H5 交接与索引|维护/交接/CodeGraph|记录与资源引用同步，不覆盖前轮未提交成果|H4|complete|

测试沿用前轮已授权的公开 WorkspaceController、生产 DOM、隔离设置和模拟 HTTP/模型边界；不读取个人会话或配置、不发送付费模型请求。TDD 逐个纵向切片实施。review固定点为本轮工作树before副本，非HEAD累计diff；用户本轮文字与本文件即Spec。此前全库72项原有失败与10项整套不稳定仍单列，不在本轮宣称解决。

## 记录

- 已读取组件参考；本机字体位于Windows用户字体目录，字体文件不进入项目。
- CodeGraph MCP未暴露，使用CLI；CLI对应符号命令是query，不是search。PowerShell不支持Bash heredoc，后续统一使用here-string。
- 用户明确暂停整个任务，待其选好中文字体后再继续。当前仅保存规格/检查点、下载shader参考包到忽略的local_artifacts、新增第一个生产DOM测试草稿；尚未修改应用界面或品牌，没有Hero实现，也没有提交或推送。不在暂停期间继续实现或扩大验证。
- 用户紧接着指示「你先做别的」，恢复除字体/SVG外的工作。完整标题SVG待中文字体选定，先保留同名文本占位；H1、按钮/加载动画、H3及相关验收继续。首个生产DOM回归已红：当前没有加载入口，尚未开始生产实现。


## 当前收尾规格与证据

用户中文手绘图已合入`resources/ui/workspace/brand/intext-wordmark.svg`；1062.56×182透明矢量，只有路径、不嵌字体/位图。浅深共用，字体许可与离线生成工具见brand/NOTICE.md。Hero标题最大640px、开始按钮60px、play20px；侧栏英文单独SVG高20px、浅黑/深白。

教程非操作区压暗25%、真实目标留洞；就绪一次礼花、不重复刷屏，第五步直接完成。用户编辑通知清单39项已逐项同步八个源码文件，原文档未改写；`local_artifacts/notification_copy_20261013/generated-after.md`隔离生成验证39/39匹配。

追加A6保存提示：只在window_width实际改变时说明下次启动生效，不在切换思考强度、主题或重复保存时错误提示。追加A7玻璃按钮：去掉额外亮内圈，保留外缘阴影、扫光动画和键盘焦点。

公开/生产DOM按slice红绿；本轮最新相关本地节点去重199项全绿，原生Hero38项及实际Controller教程16项通过。Spec和Standards最终各0待修；H1–H5及A1–A7全部完成。没有真实模型请求、个人设置访问、EXE构建、提交推送；原全库72项基线差异和10项整套不稳定仍单列。

## 最终验证与审查

|证据|范围与结果|
|---|---|
|本地回归|`hero-final.xml`、`log-workspace-export.xml`、`adjacent-final.xml`、`hero-tutorial-final.xml`、`settings-notice-glass.xml`、`latest-focused.xml`和`debug-final.xml`按classname/name去重，199个不同节点的最新结果全部通过；不是把重复运行相加。|
|实际WebView2|首次启动18项、completed10项、skipped10项；真实Controller教程16项，合计54项通过。使用隔离DPAPI设置、localhost模型目录及模拟模型边界。|
|通知文案|39/39与用户改稿及隔离生成盘点一致；原文档与备份逐字节相同，未运行会覆盖原稿的默认盘点入口。|
|Spec|固定本轮before增量；SVG/尺寸/教程最新规格、39文案、窗口提醒与单边玻璃按钮，最终0待修。|
|Standards|固定本轮before增量；资源生命周期、线程/保存边界、完整异常与Debug投影、交接一致性，最终0待修。|
|静态与资源|31个Python/spec AST、7个JS语法检查通过；19个HTML本地引用存在，两个SVG无text/image/字体依赖，spec递归收集22个工作区文件；13份文档310个相对链接存在，git diff --check通过，正常CRLF提醒另存原始检查输出。|
|CodeGraph|sync完成，current：261文件、6417节点、19717边。|

本地原始证据保存在忽略目录`local_artifacts/intext_hero_20261013/`；逐节点统计见`verified_nodes.json`，汇总见`final_summary.json`，静态检查见`static_checks.json`。交接和架构文档没有本轮before副本，只作为当前文档复核，不伪造增量。品牌资源见[完整字标](../../resources/ui/workspace/brand/intext-wordmark.svg)、[英文标识](../../resources/ui/workspace/brand/intext-english.svg)和[来源说明](../../resources/ui/workspace/brand/NOTICE.md)。

验收只证明本轮离线/模拟及实际WebView2边界；前轮[完整回归](full_regression_20261013.md)中的72项原有失败和10项整套不稳定未由本轮消除，不声称全仓库全绿或真实模型/EXE通过。
