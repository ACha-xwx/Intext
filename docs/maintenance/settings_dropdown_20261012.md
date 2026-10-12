# 设置页下拉箭头修复

目标：修复用户截图中服务名称箭头偏低，并统一设置页所有下拉字段。基线是当前工作树，前轮API请求兼容改动保留；本轮只改设置页呈现、共享SVG图标及测试/文档。

服务名称和模型ID是input+datalist，原生倒三角跟随基线，未按字段垂直中心定位；协议及其它枚举是select。现在用共同18px SVG细线箭头在字段中心绝对定位。select隐藏原生外观、留出文字间距，datalist原图标透明但保留原生命中区域；装饰图标不接收指针、不进入读屏/Tab顺序。原生控件及labels、预设联动、手动供应商/模型ID、设置提交/加密/确认不变。

每次表单构建增加一条Debug渲染诊断，仅记录下拉字段数，不记录用户值或密钥；重复快照不重建或刷日志。

按已授权生产浏览器DOM边界先红后绿；检查浅深主题、字号9/12/18、720/1440窗口内箭头居中和无叠加，预设联动/键盘选择/自定义值/刷新草稿/保存请求。Chromium私有picker伪元素的computedStyle不可靠，因此隐藏效果使用实际悬停截图核对（本地verification/settings_dropdown_20261012/after-field.png与before-field.png）。展开后的选项列表仍使用原生控件，本轮统一关闭状态的箭头与字段间距。

验证结果：`tests/test_settings_dropdowns.py` 5 passed（12.08s）；`tests/test_frontend_review_regressions.py` 与 `tests/test_web_workspace.py` 的 settings 子集 12 passed、57 deselected（19.70s），共17个不同检查通过。两个JavaScript文件 `node --check`、`git diff --check` 通过，CodeGraph已同步三个UI文件。独立需求/规范审查各0待修；没有改动设置提交、确认、密钥或状态保护逻辑。

没有读取个人设置或发模型请求，没有构建EXE/提交推送。本轮自动化与截图使用Chrome/Chromium，未进行真实WebView2或独立EXE验收。该修复用于默认WebView2设置页面，显式Tk回退保持原生控件。
