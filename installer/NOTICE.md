# 安装器第三方来源与许可

安装器由 Inno Setup 6.7.3 编译，其安装引擎及界面版权归 Jordan Russell、Martijn Laan 等上游作者，保留原有版权和网站信息。许可证全文见 [INNO-LICENSE.txt](INNO-LICENSE.txt)，来源为官方编译器发行包的 License.txt；项目网址：<https://jrsoftware.org/>。

`ChineseSimplified.isl` 来自官方仓库 `jrsoftware/issrc` 的 `Files/Languages/ChineseSimplified.isl`，上游 Git blob `d0d44258f51aa3127fc0d1167a7c8be328a9bdcf`，未修改译文。文件记录维护者 Zhenghan Yang (Kira) 及其 [翻译项目](https://github.com/kira-96/Inno-Setup-Chinese-Simplified-Translation)。该翻译项目明确采用 MIT License；原文见 [TRANSLATION-LICENSE.txt](TRANSLATION-LICENSE.txt)，由其 GitHub license API 取得并保留版权声明。本说明、两份许可证随安装后的程序放入 `licenses/InnoSetup/`。

WebView2 bootstrapper 从微软官方地址 <https://go.microsoft.com/fwlink/p/?LinkId=2124703> 获取。构建脚本检查有效 Microsoft Corporation 签名，不修改此二进制；目标机缺少 Runtime 时联网运行微软安装器。WebView2 由 Microsoft 提供并按其安装条款使用，升级和卸载 Intext 不删除共享 Runtime。分发文档：<https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution>。

本说明仅记录这些第三方安装依赖，不授予 Intext 项目本身新的开源或商业许可。
