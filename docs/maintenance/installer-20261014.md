# 本地安装包与 WebView2（2026-10-14）

## 2026-10-14 恢复交付：磁盘空间不足

用户提供 errno 28 并确认同学 C 盘仅剩 98 MB；已核对当前单文件启动解包约 139 MB。这与空间不足吻合，未取得同学完整堆栈，不认定所有错误都来自解包。Python/pywebview 已包含，无需另装 pip 库。

按此前“收到报错并定位后制作安装包”的授权恢复 I1–I4。使用 onedir 一次安装，允许选择其他盘；缺少 WebView2 时安装微软签名依赖；保留应用数据。实际安装 CLI、外部依赖进程、最终文件和实际 WebView2 是本文件已确认边界；不卸载共享 Runtime，不访问私人配置，不请求模型。审查基点 15858f8。原先暂停及旧产物证据保持为历史，完整逐页审查继续暂停。

规格：用户要求把独立 EXE 改为可安装到本地的安装包，帮助用户安装 WebView2，完成后上传 GitHub，并把安装包 EXE 放桌面。当前同学电脑未提供具体错误；不能把打不开直接断言为缺 Runtime。

当前范围：可复现 Inno Setup 编译流程、微软官方签名 WebView2 bootstrapper、按当前用户安装/快捷方式/卸载、依赖检测及失败提示、实际安装后 WebView2 启动验证、GitHub源码和Release产物。bootstrapper 仅约1.8 MB，减少安装临时空间；目标机缺 Runtime 时需要联网，不承诺离线安装。保留现有设置和会话路径、密钥保护、业务/UI/手动运行日志。安装日志与运行日志是不同合同。

|阶段|文件/范围|完成标准|状态|
|---|---|---|---|
|I1 分发依赖调研|官方文档、编译工具、运行入口|明确架构/系统/Runtime 检测与官方参数；记录未知根因|完成：单文件_MEI回归1红→onedir1绿|
|I2 安装闭环|installer/Intext.iss、构建脚本|可本地安装、快捷方式、修复/升级和卸载；缺 Runtime 自动安装，失败不假装成功|完成：全流程编译成功，安装版无需全量临时解包|
|I3 定向验证与审阅|编译后的真实安装程序、外部依赖模拟、安装后实际WebView2|已装跳过、缺失安装、失败阻止、设置保留、正常卸载；Spec/Standards检查|完成：最终CLI5项/原生22项/包内M4 8项；两轴0待修|
|I4 发布|GitHub、桌面Setup EXE、校验清单|提交推送，上传安装包与哈希，桌面副本一致|完成：源码648ea1d、已发布标签与源码一致，两项资产/桌面SHA256一致|

沿用已授权公开边界：安装器 CLI/最终文件、注册表依赖检测、外部依赖安装进程、实际 WebView2，不访问用户私人配置，不请求真实模型。TDD按一条安装行为一轮红绿；编译测试专用可替代的外部 Runtime 安装器，不卸载本机共享 WebView2。

初始事实：上一版 Intext.exe 在本机隔离双启动可用，但未包含机器级 WebView2；`.venv`不存在，系统 Python 可构建。当前无 Inno Setup 编译器。完整逐页审查仍暂停，本轮只做安装交付。

## 最终安装产物与验证

Windows x64 / Python 3.11.9 / PyInstaller 6.20.0 / Inno Setup 6.7.3。构建脚本全流程成功；微软 bootstrapper 与 Inno 编译器均验证有效发布者签名。最终安装包 `dist/installer/Intext-Setup-2026.10.14.exe` 为56,558,711字节，SHA-256 `d3149e2ff12ebbac0019337559294d0789d206942694ec9d4bc78844aaac8fde`。程序主体目录包139,673,593字节，安装后直接读取，空间检查为Windows/临时/用户数据目录至少512MB，建议1GB；系统已有Runtime不重装。

公开启动测试：旧单文件1红→新onedir1绿；5项最终编译安装器CLI检查通过，私有注册表与外部Runtime fixture覆盖已装/缺失/退出失败/未注册/低空间阻止。未填满实际磁盘或卸载共享WebView2。

最终含许可安装包实际22项通过：中文/空格目录安装，真实WebView2双启动（Edg/155.0.4283.45），移除PATH Python与隔离LocalAppData，实际桥接保存主题和教程状态，升级后设置字节不变/历史保留、重开恢复，卸载程序而保留用户数据，无_MEI和自动应用日志；三份许可随安装保留。历史保留用隔离目录标记，不冒充完整用户业务会话/密钥现场测试。另8项最终包内M4字节码离线回归通过，保持上一批原始JSON隔离修复。AST/空白检查通过；Spec和Standards增量复审各0待修。首轮许可遗漏和具名fixture建议已修。

证据在忽略目录 `local_artifacts/installer_20261014/`，不是干净虚拟机、同学电脑或真实模型质量验收。所有应用代码/协议/思考强度保持，不请求真实模型。源码发布至当前用户更名后的 `ACha-xwx/Intext`；构建产物、测试数据、编译器和本地日志不入Git。

## GitHub 与桌面交付完成

源码实现提交 `648ea1d31ada6c2a3d1ae3c032e2efce0db68d9c` 已原 SHA 同步 GitHub main；未重写此前两次用户提交。安装版标签 `v2026.10.14-setup` 指向此实现，[Release 已发布](https://github.com/ACha-xwx/Intext/releases/tag/v2026.10.14-setup)，安装包和 `SHA256SUMS.txt` 两项资产均为 uploaded，GitHub 返回的 SHA256 与最终本地产物一致。发布后再次只读核对标签、发布状态、最终下载 URL 和桌面副本，全部一致；报告在 `local_artifacts/installer_20261014/release-verified.json`。

桌面交付为 `Intext-Setup-2026.10.14.exe` 和 `Intext-Setup-SHA256SUMS.txt`。建议同学先为 C 盘腾出至少 1 GB；可选择其他盘安装，但临时文件、WebView2 和用户数据仍需要相应磁盘空间。仓库为私有，Release 下载需要有访问权限的 GitHub 账号。构建缓存已可恢复移入忽略清理目录，测试数据和产物不入库；并行演示视频文档不混入本轮提交。收尾仅更新文档，无程序或构建变化，不重复已通过验收。

## 2026-10-20 跨设备验证补充

用户确认，当前安装包已在组员电脑验证可用。该次验证没有保存设备型号、Windows 版本、安装过程记录或日志，因此此处只记录一次组员设备上的可用性验证，不据此推定干净虚拟机、缺少 WebView2 时的联网安装、升级/卸载流程或长期运行均已覆盖。10 月 14 日的安装验收数据仍仅对应原记录列出的本机测试范围。

## 以下为恢复交付前的历史诊断

2026-10-14 用户要求先等待同学启动报错，定位原因后再制作安装包。I1–I4暂停，尚未实现安装器代码、编译安装包或发布。先前依赖下载进程已退出（RemoteDisconnected），没有依赖安装操作；curl仅验证了Inno官方下载地址可访问。后续收到报错后从启动诊断续接，不假定缺WebView2。

## 用户假设定向检查：缺少 Python WebView 库

2026-10-14 用户暂时无法复现，要求检查是不是未安装Python WebView库。本次只诊断，安装包实现/发布继续暂停。当前桌面与dist EXE哈希一致（74898acf29a1bfcc342951d162ad782986e99845f6d638b0ae8ad1e80ee3297c）。直接读取PyInstaller归档，确认含Python311、webview、winforms/edgechromium、pythonnet/CLR、WebView2 Core/WinForms SDK及x64 WebView2Loader.dll。系统Microsoft Edge WebView2 Runtime不等于这些SDK/加载器，仍由目标Windows提供；WinForms检测还要求.NET Framework。

将当前EXE复制到独立临时目录，隔离LOCALAPPDATA、删除子进程Python相关环境与用户包搜索，将PATH仅留Windows System32、PYTHONHOME指向不存在目录。12项检查全部通过：8项归档依赖、PATH找不到Python、真实WebView2页面、Python bridge状态和正常退出。证据在忽略目录`local_artifacts/installer_20261014/bundled_webview_check.json`，浏览器Edg/155.0.4283.45。仅模拟排除外部Python搜索，不等于无Python的干净虚拟机或同学机器复现，不卸载本机Python/Runtime、不访问私人配置、不请求模型。

结论：当前交付EXE无需同学另装Python或pip pywebview；源码run.bat才依赖所用解释器安装requirements。此前同学ModuleNotFoundError是源码环境的已知问题，不能推定本次EXE相同原因。系统Runtime/.NET/安全拦截等仍需现场证据，目前未确定根因。公开启动检查保留，没有修改应用或重构打包。

工具小误差：CodeGraph CLI不支持context或--max-nodes，改用node文件路径；首次隔离脚本将环境dict按SystemRoot查找，实际键为SYSTEMROOT，启动前KeyError，修正后通过。先前native_exe_final超时是已保留首轮记录，真正已完成的双启动记录为native_exe_verified，没有混用失败报告。
