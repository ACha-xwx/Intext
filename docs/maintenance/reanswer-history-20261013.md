# 历史回答补答入口与图标居中

用户要求已经送入模型的问题/回答暂时不显示圆形补答按钮，同时修正按钮图标偏歪。本轮仅调整对话呈现，前轮供应商未提交改动保留。

根因：Web 和 Tk 原先对所有带 question_id 的历史回答无条件加按钮，没有区分是否已经提交模型；Web 的 42px 按钮加 10px padding 后内容不足 22px，SVG 仍沿文字基线排版。

共享 conversation_cards 根据现有请求/运行记录 base_version、思考记录 history_count 及回答 assessment 派生 can_reanswer；已提交、已处理及失败/取消后的历史回答隐藏入口，尚未发送的一批回答和跳过项仍可补答，新回答独立处理。该字段仅为显示投影，不写入会话或模型请求，不改回答正文、确认或失效语义。Web 与 Tk 使用同一判定，Tk 刷新签名包含可修改回答集合。

Web 圆按钮改为无 padding 的居中网格，SVG 使用 block；保持 42px 圆形尺寸、原 loop 路径、玻璃效果和悬停动画。Debug 只在当前任务的可修改回答集合变化时记录数量，不含回答正文，闲置刷新不重复记录，日志仍只在用户点击保存后写盘。

验证按两个 slice 先红后绿：发送后历史按钮数原为 1、应为 0；浅深主题及字号 9/12/18 的 6 项居中检查全部出现至少水平 1px 偏差。修复后单行/多行气泡中心均对齐；新增保存重开、处理/失败/取消历史、新回答、跳过入口与 Debug 去重检查。

最后命令：`python -m pytest -q tests/test_reanswer_visibility.py tests/test_reanswer_icon.py tests/test_web_workspace.py tests/test_conversation_workspace.py tests/test_requirements_inline_browser.py --tb=short --show-capture=no`。60 个不同节点全部通过，其中 11 项为新增回归。2 个 Python 文件 AST、workspace.js 语法及 diff 空白检查通过。

Spec 与 Standards 独立只读审查最终各 0 项待修；交接相对链接通过。CodeGraph 同步 3 个文件后确认 current（225 files / 5695 nodes / 17895 edges），R1–R3 关闭。

验证为隔离 SessionState/Controller、真实 Tk 控件及离线 Chrome 生产 DOM；失败/取消等状态为合成 fixture。未调用真实模型、读写个人设置、构建 EXE或进行原生 WebView2 验收，不把本地浏览器结果当作实屏验证。首个测试探针曾用简化 questions fixture 经 prepare_m1 触发 null gap_id 契约错误，改用公开 begin_request 建立正确请求边界后才记录真实红灯，没有因此调整生产 Schema。
