# 本地安装包与 WebView2（2026-10-14）

规格：用户要求把独立 EXE 改为可安装到本地的安装包，帮助用户安装 WebView2，完成后上传 GitHub，并把安装包 EXE 放桌面。当前同学电脑未提供具体错误；不能把打不开直接断言为缺 Runtime。

范围：可复现 Inno Setup 编译流程、微软官方签名 WebView2 离线安装器、按当前用户安装/快捷方式/卸载、依赖检测及失败提示、实际安装后 WebView2 启动验证、GitHub源码和Release产物。保留现有设置和会话路径、密钥保护、业务/UI/手动运行日志。安装日志与运行日志是不同合同。

|阶段|文件/范围|完成标准|状态|
|---|---|---|---|
|I1 分发依赖调研|官方文档、编译工具、运行入口|明确架构/系统/Runtime 检测与官方参数；记录未知根因|进行中|
|I2 安装闭环|installer/Intext.iss、构建脚本|可本地安装、快捷方式、修复/升级和卸载；缺 Runtime 自动安装，失败不假装成功|待完成|
|I3 定向验证与审阅|编译后的真实安装程序、外部依赖模拟、安装后实际WebView2|已装跳过、缺失安装、失败阻止、设置保留、正常卸载；Spec/Standards检查|待完成|
|I4 发布|GitHub、桌面Setup EXE、校验清单|提交推送，上传安装包与哈希，桌面副本一致|待完成|

沿用已授权公开边界：安装器 CLI/最终文件、注册表依赖检测、外部依赖安装进程、实际 WebView2，不访问用户私人配置，不请求真实模型。TDD按一条安装行为一轮红绿；编译测试专用可替代的外部 Runtime 安装器，不卸载本机共享 WebView2。

初始事实：上一版 Intext.exe 在本机隔离双启动可用，但未包含机器级 WebView2；`.venv`不存在，系统 Python 可构建。当前无 Inno Setup 编译器。完整逐页审查仍暂停，本轮只做安装交付。

2026-10-14 用户要求先等待同学启动报错，定位原因后再制作安装包。I1–I4暂停，尚未实现安装器代码、编译安装包或发布。先前依赖下载进程已退出（RemoteDisconnected），没有依赖安装操作；curl仅验证了Inno官方下载地址可访问。后续收到报错后从启动诊断续接，不假定缺WebView2。

## 用户假设定向检查：缺少 Python WebView 库

2026-10-14 用户暂时无法复现，要求检查是不是未安装Python WebView库。本次只诊断，安装包实现/发布继续暂停。当前桌面与dist EXE哈希一致（74898acf29a1bfcc342951d162ad782986e99845f6d638b0ae8ad1e80ee3297c）。直接读取PyInstaller归档，确认含Python311、webview、winforms/edgechromium、pythonnet/CLR、WebView2 Core/WinForms SDK及x64 WebView2Loader.dll。系统Microsoft Edge WebView2 Runtime不等于这些SDK/加载器，仍由目标Windows提供；WinForms检测还要求.NET Framework。

将当前EXE复制到独立临时目录，隔离LOCALAPPDATA、删除子进程Python相关环境与用户包搜索，将PATH仅留Windows System32、PYTHONHOME指向不存在目录。12项检查全部通过：8项归档依赖、PATH找不到Python、真实WebView2页面、Python bridge状态和正常退出。证据在忽略目录`local_artifacts/installer_20261014/bundled_webview_check.json`，浏览器Edg/155.0.4283.45。仅模拟排除外部Python搜索，不等于无Python的干净虚拟机或同学机器复现，不卸载本机Python/Runtime、不访问私人配置、不请求模型。

结论：当前交付EXE无需同学另装Python或pip pywebview；源码run.bat才依赖所用解释器安装requirements。此前同学ModuleNotFoundError是源码环境的已知问题，不能推定本次EXE相同原因。系统Runtime/.NET/安全拦截等仍需现场证据，目前未确定根因。公开启动检查保留，没有修改应用或重构打包。

工具小误差：CodeGraph CLI不支持context或--max-nodes，改用node文件路径；首次隔离脚本将环境dict按SystemRoot查找，实际键为SYSTEMROOT，启动前KeyError，修正后通过。先前native_exe_final超时是已保留首轮记录，真正已完成的双启动记录为native_exe_verified，没有混用失败报告。
