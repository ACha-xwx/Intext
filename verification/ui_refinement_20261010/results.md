# 十项UI调整与输入重叠修复验收

任务开始于2026-10-10，最终验收于2026-10-11。源码范围和交互说明见[维护记录](../../docs/maintenance/ui_refinement_20261010.md)。本轮使用隔离LOCALAPPDATA、合成凭据、离线或localhost响应；未调用真实供应商模型，未构建EXE、提交或推送。

## 当前结论

当前21个定向/相邻测试模块中，242个不同测试节点全部通过，无失败、错误或跳过。按当前pytest收集清单合并每个节点最新完成的JUnit，避免重复计数，也没有把中间失败当作通过。

独立Windows Tk进程19项检查通过，0回调/错误弹框；15张浅深主题、字号切换、菜单、核对/摘要和小窗口截图已核对。源码入口smoke正常退出，含导入/创建/关闭3.846秒；没有自动日志或字体文件输出。16ms是动画调度间隔，不代表已验证显示器稳定60fps。

## 需求与证据

| 内容 | 结果与验证 |
| --- | --- |
| 全局125%字号 | 默认基准12pt实际显示15pt；语义/固定字号、Markdown避免二次缩放，字号9/12/16/18pt切换及默认字体/旧设置恢复通过。 |
| 输入光标和提示 | Text与placeholder共享字体和首行dlineinfo；取消额外padding，同用xterm。提示放置后提升层级，已通过映射/堆叠断言及图像检查。 |
| 工具栏重叠 | 不再依赖字号变化时滞后的winfo_reqheight，按当前行高、行数和按钮高度计算；Text自然宽设1，重排原生子窗。实际多档字号截图没有旧按钮残影，文字和工具栏互不遮挡。 |
| 动画与独立滚轮 | 可逆高度缓动、图形chevron旋转、玻璃hover和菜单弹簧进出接入。可见思考折叠记录310、303、272、207、85、28、9、1等中间高度；思考自身滚轮和边界不带动整页。 |
| 紧凑逐题回答 | 两行圆角输入、圆形提交、红色跳过/图形×同排。空白/忙态禁用、草稿保留、乱序逐题收集和最后聚合一次通过；删除旧不确定/使用时补充按钮与问题options呈现。 |
| 需求核对与摘要 | 顶部锚定面板可打开、关闭、编辑/移除、确认解释、核对完整文本；浏览不改变SessionState。信息齐备时提示顶部核对入口；仍需明确确认需求及方案。 |
| 删除重复入口 | 右上保存、需求详情、重复来源/问答/表单、M5桌面入口与设置项移除；文件菜单保存和旧M5数据重开兼容通过。 |
| 菜单及限宽 | 对话和composer共同居中，最大1060px；整理深度/任务类型玻璃按钮和选中状态保留业务。1440、960、720宽度下可达，菜单末行完整可读。 |
| 浅深主题 | Vista工作区表格采用独立field/cell/border元素，避免白底白字；默认平台主题及设置组件不变。深色有数据需求表、浅色表格和菜单截图已核对。 |
| 会话与诊断 | M1/M2新建/打开即时解锁，迟到输出/失败不改新会话；五轮后逐轮授权、未知保留、流式保存恢复、DPAPI和确认恢复通过。Debug级别颜色、脱敏和仅手动保存通过；新布局/字号/弹层日志已同步。 |

## 回归批次

原始JUnit与机器/个人路径信息保留在被忽略的local_artifacts，下面仅列可复查文件名。批次数字不能直接相加。

| 完成批次 | 节点/中间失败 | 说明 |
| --- | --- | --- |
| ui_refinement_final.xml | 141 / 1 | 前轮完成批；新问题夹具把next_action写成ask_questions，现已改为schema的ask并通过复验。 |
| ui_refinement_controls_final.xml | 83 / 1 | UI、表格、输入、偏好、旧功能撤除；新增桌面hit-test被前景其它应用遮挡，改为Tk层级和独立截图核对。 |
| ui_refinement_layout_final.xml | 26 / 9 | 滚轮新夹具未注册测试自有控件；125%改变了旧无溢出视口。补正确测试环境后复验通过，保留原边界/防重复/状态不变断言。 |
| ui_refinement_wheel_final.xml | 14 / 0 | 多档输入布局与完整滚轮专项通过。 |
| ui_refinement_boundaries_final.xml | 89 / 13 | 76通过；旧用例访问已删除unsure和M5桌面方法。按当前跳过入口与M1/M2取消场景更新，未降低版本/取消检查。 |
| ui_refinement_boundaries_retry.xml | 20 / 0 | 最新会话取消、逐项暂缓/旧卡片保护复验通过。 |
| ui_refinement_theme_final.xml | 37 / 0 | 最新组件、需求表格、回复区及工作区表格样式隔离通过。 |

四个M5桌面取消参数场景随该用户功能退役，不计为通过。当前test_ui_m5继续检查桌面入口已删除和历史数据兼容。合并脚本collect_results.py按当前收集节点输出regression_summary.json，最终242 passed。

较早ui_refinement_workflow.xml另观察到test_m1的两个历史契约差异：硬编码旧prompt版本和零问题预算。它们不在本轮选定集合中，本报告不宣称全仓库测试全部通过；没有为配合旧断言恢复过时业务逻辑。历史背景见[基线](../baseline/agent_skill_target_20261007/results.md)。

## 独立窗口与静态检查

probe.py在正常mainloop下记录19项检查到acceptance.json；截图包括light-thinking、light-question、light-input-after-font-change、input-font-9/12/16/18、light-depth、light-requirements、light-summary、dark-plan、dark-skills、dark-category、dark-requirements和dark-small。小窗口为真实720×500，模型/问题/需求是本地合成数据。

Python compileall、git diff空白检查通过；PromptSmith.spec的58个资源入口均存在，当前M1提示/schema与加载路径对齐。七份当前文档115个相对链接全部存在；CodeGraph161个文件、4159个节点、12917条边，状态up to date。原生字体无生成、注册或磁盘缓存；诊断仅在点击保存日志时落盘。
