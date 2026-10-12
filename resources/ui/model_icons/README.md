# 模型图标

`deepseek.svg` 原样复制自用户提供的 DeepSeek-icon.svg；其它四个 SVG 从用户提供的模型选择 TSX 示例提取，Google 的 JSX 动态标识转为固定 SVG 标识。颜色及图形沿用提供的资源。

72×72 PNG 是 Tk 使用的预渲染资源，运行时通过 Pillow LANCZOS 平滑缩放至当前显示密度对应的尺寸，再交给 Tk。避免 PhotoImage.subsample 的直接像素抽样；不需要浏览器或 SVG 解析依赖。开发时可用 `python scripts/build_model_icons.py` 重新生成（需要 CairoSVG）；源文件与 PNG 均随软件打包。商标仍属于相应提供商。

`*_dark.png` 为深色主题图标，单色图形变为浅色以保持对比度，彩色品牌图形沿用原色。应用在组件主题切换时重新选择对应资源，运行时仍无需 CairoSVG。
