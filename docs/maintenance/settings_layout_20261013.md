# 设置页字段错位修复

用户截图中“删除供应商”在左、生成timeout标签在右，随后120/15/0/auto控件全部错列。用户明确本轮仅修错位，不新增设置功能。

根因：模型表单直接交替追加标签和输入控件，新增删除按钮只占一格，随后网格自动排版整体错一格。公开生产DOM复现label左631/input左313且不同行；单变量仅增加按钮跨列后label左313/input左631且同行。原来供应商验收覆盖交互与图标，但缺少“显示删除按钮后参数行布局”的回归，这是本次补齐的边界。

最小修复：删除按钮复用settings-full，独占整行；原字段、控件、分类、持久化和删除逻辑保持。已有构建Debug补full_width_actions数量，只构建时记录，不包含正文、设置值或密钥。

验收：内置→自定义→内置切换、浅深、720/824/1440px宽和12/18字号下，每个参数的标签与控件正确对应；宽窗同行左标签右控件，窄窗上下顺序。沿用获授权的公开DOM/隔离WebView2边界，不使用个人设置或收费请求。

增量固定点：local_artifacts/settings_layout_20261013/before。diff命令：git diff --no-index -- local_artifacts/settings_layout_20261013/before/resources/ui/workspace/settings.js resources/ui/workspace/settings.js；本轮没有新增提交。聚合结果保存在同级incremental.diff，不混入前轮供应商、补答及trace增量。

首个回归1 failed（3.64s）→1 passed（4.06s）。最终6项尺寸/主题/字号/内置往返矩阵及保存/删除/菜单相邻，共26项通过（65.99s）：

```powershell
python -m pytest tests/test_settings_layout.py tests/test_custom_provider_browser.py tests/test_provider_profiles_browser.py tests/test_settings_dropdowns.py -q -o addopts=
```

实际WebView2使用隔离存储和合成设置快照，9个场景的全部参数布局及轮询无错误共10项通过，已核对原生深色截图。辅助脚本仅留local_artifacts/settings_layout_20261013，不作为运行依赖。首次辅助Bridge.snapshot漏stamp参数造成轮询错误，修正测试签名后再验无错误；不是应用代码故障。没有个人设置、模型请求或EXE验证。

JS语法、Python AST及diff空白检查通过。Spec与Standards独立增量审查均0项发现：布局复用既有整行类，内置供应商隐藏按钮不残留占位，Debug只扩充构建计数且不含用户值。CodeGraph同步2个文件后确认current（227files/5714nodes/17978edges）。

L1–L3完成，交接和维护账本同步。验证范围为生产浏览器DOM、相邻设置交互及隔离原生WebView2合成快照，不代表完整业务保存或独立EXE验收。本轮未提交或推送；前轮未提交成果保留。
