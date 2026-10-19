# 启动自动模型目录刷新

用户要求：保留获取模型按钮，每次启动时已保存API Key的供应商自动获取目录；完成后清理项目并上传GitHub。

范围：启动后台刷新所有已保存且可解密的Key对应目录，不自动确认模型；先展示缓存，失败保留缓存并提示手动重试。独立后台避免影响业务任务；Tk owner thread处理结果，拒绝修改配置、删除供应商、手动刷新或退出后的旧结果。沿用PromptSmithApp/WorkspaceController、本地HTTP与隔离存储测试边界，无个人配置或收费模型请求。

审查固定点：本轮开始工作树副本，发布同时保留前轮已完成修改。临时固定点与本地原始验收产物在清理阶段移除，保留本报告。

实现：新增model_directory_refresh.py持有独立最多2线程后台池，不占业务executor或busy；每个保存Key的供应商启动刷新一次。目录请求沿用已保存协议的HTTP客户端，只有GET，不调用模型或连接探针。结果经completions队列回Tk线程，核对scope/现有档案/连接和Key身份；手动获取、配置变更、删除或关闭均可退役旧请求。目录只落到原已保存身份，保留当前活动供应商、草稿、默认模型和显式确认。Web及Tk模型设置显示独立进度、成功/失败/重试状态。

红绿：首个公开启动回归1 failed（7.83s）→1 passed（3.76s）；状态反馈2 failed（8.62s）→3 passed（6.33s）。最终新增13项HTTP/桌面检查与1项生产DOM检查共14 passed（25.92s）：

```powershell
python -m pytest tests/test_startup_model_directory.py tests/test_startup_model_directory_browser.py -q -o addopts= --tb=short
```

覆盖保存Key自动获取/持久化、全服务与无Key跳过、慢请求期间缓存和设置可用、403保留缓存/手动重试、改Key/删除/退出拒绝迟到、手动请求优先，以及Chat Completions/Responses/Messages路径和鉴权。生产DOM核对进度/失败/成功原位更新、手动按钮保持可用、未保存输入不丢失。

实际WebView2：隔离LOCALAPPDATA、一次性DPAPI凭据、真实启动及CDP交互8项通过。两个本地延迟GET（/gpt/v1/models、/ds/v1/models），没有模型生成/测试连接POST；启动缓存可用、设置能切换、两家目录自动更新/持久化、确认保留、浏览器不见Key及零自动日志均通过。本轮未验证个人配置、真实服务质量或独立EXE。

## Standards

0项发现。独立线程池经队列回Tk主线程，保存只更新原身份目录，完整异常链和密钥脱敏保持，日志只手动保存。独立审查为只读，未重跑测试。

## Spec

0项发现。自动刷新全部已保存可解密Key的服务，保留手动按钮与缓存；失败可恢复且不锁对话，不隐式确认；配置修改/手动获取/删除/关闭均阻止迟到结果。

9个相邻模块100 passed（218.77s），与14项新增检查没有重复节点，共114项通过；包括档案/自定义CRUD、菜单、设置错位/下拉、加密/确认和重启恢复。不是全套测试或真实模型质量验收。

```powershell
python -m pytest tests/test_provider_profiles.py tests/test_custom_provider_profiles.py tests/test_provider_profiles_browser.py tests/test_custom_provider_browser.py tests/test_settings_layout.py tests/test_settings_dropdowns.py tests/test_model_confirmation_settings.py tests/test_ui_encrypted_settings.py tests/test_credentials.py -q -o addopts= --tb=short
```

6个Python AST、settings.js语法、diff空白检查通过；CodeGraph已current（230files/5770nodes/18084edges）。最后没有应用追加修改，避免重复已通过回归。清理和发布结果在收尾追加。

清理：缓存及原始验收工件移出仓库，存入本机临时目录的可恢复清理归档；包含pytest缓存、src/tests字节码、local_artifacts以及966个未跟踪的verification临时工件（25,136,707字节）。保留正式Markdown报告、跟踪的基线证据、全部程序/测试/资源/文档和CodeGraph开发索引；不触碰LOCALAPPDATA下PromptSmith用户设置/Key/历史。新增gitignore防止未跟踪日志及根logs/runs进入提交。直接永久删除被工具执行策略拒绝，改为可恢复移动后完成清理。

清理后232个当前交接相对链接、56个源码AST及运行资源目录核验通过。发布包括此前已完成的自定义供应商、历史补答、思考入口和设置错位修复；这些已有各自维护与验证记录。

发布：功能与清理交付提交d1bdbd3（Automatically refresh saved provider models at startup），已正常推送origin/main；git ls-remote核对GitHub main完整SHA为d1bdbd37f749b4d6ae84bf3cf2b16ac8cd4ac846，与本地HEAD一致，工作树干净。此后仅补本交付记录与任务完成状态，再作普通文档提交推送，不修改应用或重复测试。
