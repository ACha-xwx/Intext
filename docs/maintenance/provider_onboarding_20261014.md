# 首次自定义服务自动保存与教程（2026-10-14）

用户现象：另一台电脑可启动EXE；首次配置自定义YUN/OpenAI、地址和Key后仍显示未配置，教程第2步不能继续。截图不包含实际保存异常。安装包与全量审查保持暂停，优先修复此问题。

目标/范围：修正设置DOM数值有效性导致的跨分类保存阻断，保留供应商身份隔离、DPAPI原子保存、输入保留与真实教程就绪判断。先通过公开设置UI/Controller/保存加载接口补回归，再实际WebView2及EXE验收。无真实模型请求、无个人Key或会话访问。

根因已复现确认：field()用Number.isInteger(default)选择step=1；thinking_speed默认1、min=.25与history_save_interval默认2、min=.5造成HTML stepMismatch。drainSaves()检查所有分类，隐藏字段阻止任何模型保存，设置文件确实没有写入；旧浏览器fixture缺这两个新增字段而未覆盖。生产Controller按Python设置字段类型输出step，浏览器照用；整数限制仍保留，小数合法值不再阻断保存。新增诊断只含字段ID及stepMismatch，不含输入值或密钥。

|任务|文件|验收|状态|
|---|---|---|---|
|P1 复现|生产DOM与真实设置schema测试|自定义供应商+Key、空模型应保存并解锁第2步；先出现精确红例|complete|
|P2 最小修复|settings.js、必要的schema及Debug|整数设置仍拒绝小数，小数设置默认/合法值通过；密钥安全与失败保留|complete|
|P3 回归与审阅|相邻设置/教程、原生WebView2及冻结EXE|首次保存→获取本地模拟目录→选择→教程；重启恢复；Spec/Standards审阅|complete（源码提交待推送）|
|P4 数据目录改名|paths及所有默认存储入口、迁移与测试|新默认%LOCALAPPDATA%/Intext，旧设置/密钥/历史可继续读取，迁移不覆盖或丢失数据|complete|

验收接口沿用已授权的公开Controller、生产DOM、磁盘设置加载/系统DPAPI与本地HTTP模型列表边界。定位与测试日志在忽略的local_artifacts/provider_onboarding_20261014/；完整运行日志仍仅手动保存。

## 数据迁移与兼容边界

新路径为`%LOCALAPPDATA%/Intext`，无该环境变量时为`~/.intext`。默认main/App/SessionHistory读取前整体重命名旧目录，保持设置字节、DPAPI身份/密文、模型确认、教程状态、历史和runs证据；不改Python包名或密钥加密常量。新目录为空也可迁移；两目录均非空时优先Intext并保留旧目录，不合并覆盖。迁移失败保留原数据，Debug保留完整异常原因并阻止假装成功启动。

显式evidence_root、diagnostics_root或外部runtime_log的隔离存储不触发默认迁移。Standards初审发现只检查evidence_root不足，已补两种隔离构造的精确红例再修正；复审两轴各0待修。显式保存的外部会话/导出路径仍按用户原值，不批量改写路径字符串。

## 已取得证据

- `red.xml`：生产DOM→真实Controller→DPAPI保存的教程解锁失败；修复后同路径绿。
- `adjacent.xml`：14个相关模块185项全通过，设置/教程/档案/历史/入口等覆盖；之后仅按受影响范围增补检查。
- `migration_red.xml`、`isolation_red.xml`：旧默认路径和两类隔离构造先失败；`migration_green.xml`最终8项通过，含冲突不覆盖、注入重命名失败及真实DPAPI/历史恢复。
- `native_source/results.json`：实际源码WebView2双启动21项通过，首次自定义服务保存→获取localhost目录→选择模型→教程完成→模拟旧目录→重启恢复。无真实模型生成，无个人配置访问。
- 原生脚本首轮在CDP已就绪但页面仍about:blank时StopIteration；已让检查器等待真实index.html导航后重新通过，该失败属于验收脚本时序，不是产品保存异常。

用户追加密钥长度/前缀询问：输入不限制sk前缀或固定长度，Controller安全上限16384字符、DPAPI上限32768 UTF-8字节。回归增加无前缀、Anthropic形状及长token三类合成密钥，验证保存后完整恢复且不出现在浏览器快照/磁盘明文；不改变既有调用协议规则。

## 最终验证与产物

相关185项、后续迁移8项和密钥/凭据23项按(classname,name)去重，最终203个不同本地测试节点均通过。AST9文件、settings.js语法和git diff空白检查通过。生产源码与独立复制的冻结EXE各通过21项实际WebView2双启动验收；仅本地HTTP GET模型目录，没有付费模型请求。Spec、Standards最终复审各0待修；完整逐页审查未恢复，也不声称同学电脑已验证本次新版。

Windows x64、Python3.11.9、PyInstaller6.20.0以PromptSmith.spec重建。产物70,409,255字节，SHA256 `8b5a642a7e92347c1148cf3a9a50a747833e6b998d98e72d0c8bb0162f42f0a7`。旧桌面Intext.exe被运行进程占用，首次复制失败，未中断该进程；改为桌面`Intext-修复版.exe`，与dist/Intext.exe哈希一致。用户应退出旧程序后启动修复版，再让同学重测。安装包制作仍暂停；产物和本地证据不提交源码Git。
