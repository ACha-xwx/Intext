# 平台默认字体与旧设置兼容验收

日期：2026-10-10。Windows，Python 3.11，Tk 8.6。全部为源码离线检查，合成凭据使用实际当前用户 DPAPI；未读取或覆盖用户真实 settings.json，没有付费模型调用、新版 EXE 构建或远程 Git 操作。

## 结果

| 检查 | 结果与范围 |
| --- | --- |
| 定向回归 | 174 passed，0 failed / error / skipped，306.041 秒；不是全仓测试 |
| 实际 Tk | 两个独立进程各 36 项，共 72 项通过；无回调/弹框异常 |
| 首次窗口显示 | 从脚本开始计时，含导入和 Tk 创建：旧设置首次恢复 3.336 秒，新保存设置恢复 3.535 秒；为本机源码采样，不是 EXE 或通用耗时保证 |
| 默认来源 | 实际观察 `TkDefaultFont` 的族名为 Segoe UI，仅为本机结果；代码不固定任何族名，原生 Tk 命名字体未被修改 |
| 字体资源与线程 | 两次进程未导入 FontTools、未发现 `ui-font` 线程；Python open audit 未发现字体/缓存访问，无新 TTF/TTC/OTF 输出，原旧缓存保留 |
| 浅深主题 | 输入框、模型菜单、设置页与 Debug 控件字体核对通过；High、图标与独立勾保持，截图已人工查看 |
| 设置兼容 | 不存在/格式损坏的旧字体设置被忽略；普通保存/Debug 独立保存剔除旧字段，合成 DPAPI 密钥和模型确认恢复，明文密钥不在文件/日志中 |
| 字号调整 | 16pt 内存更新与菜单释放正常，输入草稿/SessionState/连接版本/模型确认保留 |
| Debug | 蓝/白/黄/红/CRITICAL 颜色保留；无自动日志文件，点击 Save Logs 后新增完整快照；默认来源和旧设置兼容日志可见 |
| 源码入口 | 独立 `main --smoke-test` 退出 0，4.350 秒包含启动、一次绘制和关闭；未输出字体文件或自动日志 |
| 静态检查 | compileall、PyInstaller spec 语法、依赖撤除、文档链接和 diff 空白检查通过 |
| CodeGraph | 同步 8 个代码文件；154 files / 3911 nodes / 11930 edges，状态 up to date |

## 覆盖与证据

回归范围为 `test_typography`、`test_typography_startup`、`test_ui_clarity`、`test_ui_preferences`、`test_model_confirmation_settings`、`test_composer`、`test_debug_console`、`test_runtime_log`、`test_preferences`、`test_credentials`、`test_ui_encrypted_settings`、`test_ui_session_cancellation`、`test_conversation_workspace`、`test_main_diagnostics` 共 14 个模块。移除了仅验证已删除字库功能的用例，替换为默认字体、无后台准备和旧设置兼容用例；相邻业务用例不改契约。

离线 pytest runner 清理环境凭据、隔离 LOCALAPPDATA 并禁止外部联网。实际窗口脚本也隔离数据、禁网并禁用本机 Skill 索引预热，重点验证字体/恢复路径；并未将该脚本称为真实搜索或模型验收。

JUnit、独立进程 JSON、12 张截图及离线脚本保存在忽略目录 `local_artifacts/native_fonts_20261010/`。旧自定义字体/字形/ClearType报告是之前行为的历史证据，不代表当前实现；当前入口见 [默认字体维护说明](../../docs/maintenance/native-fonts-20261010.md)。

工具记录：修改测试时补丁工具拒绝同一路径 delete+add，无部分写入；改用完整覆盖专项测试文件。本轮回归与实际窗口首次运行全部通过，没有产品故障被忽略。
