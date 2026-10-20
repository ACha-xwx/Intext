# 设置持久化与 API Key 加密验证

日期：2026-10-09。当前源码交付，Windows / Python 3.11.9 / 原生 Tk；没有真实模型请求、EXE 构建、提交或推送。只使用合成 API Key 和隔离临时目录，没有读取生产密钥。安全边界见 [凭据保护](../../docs/maintenance/settings-security-20261009.md)。

## 实现范围

- 32 项普通偏好（含 Debug 开关）、公开连接和版本化 DPAPI 密文统一保存到 `%LOCALAPPDATA%/PromptSmith/settings.json`，启动自动恢复。
- Windows 当前用户 CryptProtectData/CryptUnprotectData；绑定服务、协议和接口地址，不含硬编码密码，不允许明文降级。
- 保存全部 / 模型独立确认 / 只测试连接的边界保持；启动恢复不自动确认，清空后保存删除密文。
- Debug 开关兼容旧 diagnostics.json，独立更新保留密文和已保存模型配置，不提交其它草稿。日志仍手动保存。
- 解密失败保留普通偏好、显示重新输入指引；加密/原子替换失败保留旧配置、编辑值和完整脱敏异常栈。
- 长失败提示与保存按钮分行，滚动区高度包含 Notebook 标签和页边距，小窗口/18pt 不裁切保存动作。

## 自动化证据

| 批次 | 结果 | 内容 |
|---|---|---|
| targeted.xml | 65 passed / 2 测试问题 | 新凭据、设置、UI 与 Debug；失败为测试注入影响日志保存、测试默认 GBK 读取 UTF-8 |
| repair.xml | 20 passed | 显式编码及内存堆栈检查修复后，复验对应节点和修改的凭据测试 |
| regression.xml | 33 passed | 旧设置、RuntimeLog、启动诊断、生成超时/UI |
| layout.xml | 3 passed / 1 布局问题 | 长提示恢复与新父 Canvas 内按钮断言；初次高度计算漏掉标签行 |
| layout-repair.xml | 1 passed | 标签行高度纳入计算，长提示 / 18pt 按钮在父 Canvas 内 |

按测试 classname/name 去重并采用最新结果：**101 passed，0 failures/errors/skips**。首批旧“恢复密钥为空”断言（32 passed / 1 failed）已按本次需求更新；被后续 targeted 结果取代。不代表运行了完整历史套件，历史 Skill 粗筛差异仍单列在此前验证。

覆盖：真实 DPAPI 随机密文与往返、身份绑定、密文篡改、模型 ID 可变、替换/删除、格式损坏、无 DPAPI 不能明文降级、原子替换失败保留旧密文、解密失败保留偏好、启动脱敏、测试连接不保存/确认、确认失败可重试、环境变量改变接口不复用密钥、Debug 草稿隔离及迁移优先级、默认应用数据路径。

JUnit 及实际窗口记录在忽略目录 `local_artifacts/settings_encryption_20261009/`。主要命令：

```powershell
python -m pytest tests/test_credentials.py tests/test_ui_encrypted_settings.py tests/test_ui_preferences.py tests/test_debug_console.py tests/test_preferences.py -q
python -m pytest tests/test_ui_settings.py tests/test_runtime_log.py tests/test_main_diagnostics.py tests/test_generation_timeout_ui.py -q
python local_artifacts/settings_encryption_20261009/preview.py
python local_artifacts/settings_20261009/preview.py
```

## 实际进程与窗口

三个独立子进程（保存、重启、损坏密文）**35 项检查通过**；确认新进程恢复临时 API Key、模型/温度/超时/字号/会话默认/Debug，运行时模型参数正确，重新输入提示存在，API Key 控件保持遮蔽；没有真实 API 调用或自动日志。1440×810 和 960×640 / 18pt 的恢复、故障截图经本进程 PrintWindow 捕获并实际目视检查。

当前布局重新运行五类别 / 1440×810、960×640 / 12pt、18pt 的 **113 项实际 Tk 检查通过**；分类滚动、保存/默认/返回动作和对话输入可达，无回调错误，无自动日志。长提示另有严格父 Canvas 内断言，不仅依赖根窗口位置。

隔离 `%LOCALAPPDATA%` 后 `python run_promptsmith.py --smoke-test` 退出 0，不创建日志目录；编译与 Git 空白检查通过。CodeGraph 最新：129 files / 3425 nodes / 10515 edges。

## 限制

DPAPI 的跨 Windows 用户/电脑迁移未实测；身份绑定和篡改失效在本机实测，不等价于跨用户实测。保护对象是静态保存的凭据；不能保证同一已登录用户下的恶意进程无法读取运行时密钥。原生缓冲清零不等价于所有 Python/Tk 内存副本可靠擦除。没有运行真实供应商、打包 EXE 或另一台 Windows 的用户验收。
