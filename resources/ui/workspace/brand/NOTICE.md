# 意织 · Intext 字标

`intext-wordmark.svg` 是一个完整透明矢量资源，仅含路径；中文来自用户提供的 AI 手绘字样，保留描边与排线；分隔点和英文使用本机 Orange Juice 2.0 字体离线转为轮廓。没有嵌入字体或原 PNG，不依赖用户电脑字体，不在启动时生成或写入字库。

中文原图 SHA-256 记录在 SVG metadata 中。构建入口为 `scripts/build_wordmark_svg.py`，参数依次是中文原图、字体和输出 SVG；OpenCV/fontTools 仅为离线构建工具，不是应用运行依赖。

`intext-english.svg` 使用同一英文轮廓单独导出，侧栏浅色主题为黑色、深色主题反白；构建时加 `--english-output` 指定该资源路径。

Orange Juice 字体内置版权与许可原文：

> Copyright (c) 2013 by Brittney Murphy. All rights reserved.
> Free for personal and non-profit use. Commercial use is $5.

该许可适用于英文字形；矢量轮廓转换不改变其许可条件。项目不分发字体文件。
