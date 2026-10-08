# 开发、检查与打包

## 环境与首次启动

开发基线为 Windows、Python 3.11+、Tk 8.6。标准 Windows Python 安装须勾选 Tcl/Tk。当前发布验证围绕 Windows，不声称已完成其他平台验收。

在仓库根目录执行：

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m tkinter
.venv/Scripts/python.exe run_promptsmith.py
```

`-m tkinter` 是可选的 Tk 安装检查，会打开测试窗口。依赖包括 jsonschema、pytest、PyInstaller；本地环境不提交 Git。无需从开发者机器复制虚拟环境。

## 模型与数据

在界面选择协议、填写 Base URL/模型 ID/API Key。普通启动不自动调用付费 API，真实分析、搜索查询/筛选、生成和试运行需要模型配置。GitHub Token 是搜索增强项，使用者自行配置；不要把账号密码或 Token 写入代码。

环境选项以代码实际读取为准，如 `PROMPTSMITH_GITHUB_TOKEN`、`PROMPTSMITH_RESOURCE_ROOT`；后一项用于资源目录定位，不需要普通用户设置。会话 JSON 和运行记录位于 `%LOCALAPPDATA%/PromptSmith/` 或用户选定位置，可能含用户输入，不作为默认 Git 素材。

## 按改动范围验证

```powershell
# 资源加载与窗口初始化
.venv/Scripts/python.exe run_promptsmith.py --smoke-test

# 语法检查
.venv/Scripts/python.exe -m compileall -q src tests scripts

# 当前提示与 Skill 交接等关键路径示例
.venv/Scripts/python.exe -m pytest -q tests/test_m1_current_asset_versions.py tests/test_m5_asset_version.py tests/test_skill_handoff.py tests/test_ui_skill_ai_flow.py tests/test_ui_delivery_interactions.py

# 全量检查：现有历史失败详见 verification；不要以退出非零就推断本次修改引入
.venv/Scripts/python.exe -m pytest -o addopts='' -q
```

`tests/test_ui_*` 和滚轮测试会创建 Tk 窗口，需要可用桌面。测试通常通过 fixture/本地模拟服务验证程序行为；实际内容质量与用户感受另验。新改动只重跑对应检查；迁移资源等跨模块改动需要更广覆盖。

历史真实检查脚本：`run_m1_real_check.py`、`run_ui_real_smoke.py`、`run_fixed_d1_d2_real_check.py`、`verify_m2_generation_real.py`。它们会产生 API 费用，先读 `--help` 和脚本版本说明，按明确授权与预算运行。固定案例脚本保留历史语义，部分旧断言与现产品已有差异。

## 构建

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1
dist/PromptSmith.exe --smoke-test
Get-FileHash -LiteralPath dist/PromptSmith.exe -Algorithm SHA256
```

单文件 EXE 包含 Python、Tk、依赖和 spec 列出的运行资源，AI 模型仍通过网络服务调用。首次运行会解包到临时目录。构建不上传产物；源码仓库忽略 `build/` 与 `dist/`。

发布前记录提交 SHA、Python/依赖版本、构建时间、EXE 大小与 SHA-256；将 EXE 单独复制到临时目录验证启动，避免源目录掩盖漏打包的资源。真实跨机验证须在另一台电脑执行，独立目录测试不能替代。

## 资源改动

`resources/prompts/` 存放当前与兼容提示、Schema、人工样例。`paths.py`、各 `M*Assets.load()` 和 `PromptSmith.spec` 必须一致。历史提示可能仍被旧会话、测试或打包引用，不因文件名版本较低直接删除。

样例目录 `examples/`、`examples_m2/`、`fixtures_m3_m4/` 用于离线检查；它们不代表实际模型返回。文件夹原名保留以降低迁移风险。

`resources/skill_catalog/sources/` 是固定的第三方原文快照，目录记录校验文件字节。`.gitattributes` 对这些文件关闭换行转换，避免 Windows/Git 自动转换导致 SHA-256 不一致。升级原文时须同步来源、许可、内容哈希、记录哈希和目录版本。

`pyproject.toml` 提供源码项目元数据。当前正式分发路径是源码仓库或 PyInstaller EXE；没有将所有外部资源定义为可独立发布的 wheel，不能假定 `pip install` 后即可脱离资源目录运行。

## 出错时

先记录版本、复现输入、阶段、错误类别和日志位置，不在截图里暴露密钥。参照 [踩坑记录](pitfalls.md) 找对应入口。判断是网络/模型内容、结构契约、业务状态还是 UI 呈现，再做定向修改。
