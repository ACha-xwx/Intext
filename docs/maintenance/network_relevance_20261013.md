# 联网 Skill 相关性与进度反馈

目标：给比赛程序项目写技术文档时，优先检索文档写作、准确性检查、PDF等实际能力；避免热榜前几项挤占读取预算、低分无关候选展示及逐项通知轰炸。Gemini与DeepSeek共用此路径。空匹配允许，不强迫推荐，不新增自动模型重试。

## 任务及验收

|任务|文件/范围|验收标准|状态|
|---|---|---|---|
|W1 查询/读取预算|skill_search、open_skill_search、skill_recommendation；模拟HTTP|索引使用短能力词；文档/PDF查询保留；截断前按任务相关元数据排序；GitHub目录优先相关文件|complete|
|W2 推荐/空结果|skill_ai_selection、skill_network_discovery、ui；模拟模型|排除明确低于0.4项；AI失败仅保留有用途证据的未核验项；空匹配/来源失败清楚区分|complete|
|W3 进度/通知|web_workspace、workspace.js、web_debug；公开Controller/生产DOM|逐项过程只在搜索区与Debug，最终汇总保留；进度更新不重建表格或丢阅读位置|complete|
|W4 本批统一验收|本项及前三项回归、双轴审查、交接/索引|四项全部实现后统一执行，记录模拟/浏览器与真实服务边界|complete|

公开测试边界沿用本会话授权：网络搜索器/发现入口与模拟HTTP/模型、Session/Controller和生产DOM；不访问个人配置或付费模型。用户“四项一起回归”优先于技能即时红灯顺序：测试先写，执行延后，第四项完成后对before副本验证失败，再验证修复版本。

证据：用户提供候选列表只含浏览器/视频/社交/查找Skill，模型返回空matches合理；Gemini显示0.03–0.05候选与失败降级路径相符，但没有日志证明Gemini具体失败原因。源码确认索引未保留名称/描述、各来源排序前截断、AI低分未落实排除、每次skill_status更新进入通知队列。不得把推测当远端实证。

## 修复后的检索与呈现

- 查询规划优先短英文能力词；索引去除AI Agent/Skill/SKILL.md通用标记，最多6条，保留documentation/docx/pdf等实际能力。
- 各查询完整结果先粗排再分份额，合并后先粗排再取48条落地页预算；取得真实Skill来源后再次粗排，再按正文读取预算截断。依据名称/描述/路径，不以热度或查询文本本身作为用途证据。
- 各个关键工作预留最高正分来源，避免同一能力的大量命中挤掉其他能力；GitHub集合无具体Skill时按相关目录路径选择，不默认首项。
- AI明确评分低于0.4的项排除，不增加强迫选择或无限重试。AI失败仅展示能力可解释、领域相符的少量未核验候选，并保留失败原因。
- 空结果分别提示“未收集到Skill信息”“已筛选但无匹配”“AI筛选失败”，提供重试或跳过；部分来源失败不会覆盖已有信息。
- 逐项过程留在搜索区与Debug，右上只报完成/取消/失败汇总。进度更新不重建表格，保留展开详情及阅读位置；Debug显示简明数量，完整异常、原文和手动保存不变。

## 本批统一验收证据

四项核心45项通过；本批及相邻检查按节点去重共275个通过，不将重复批次累加。节点清单保存在本地忽略目录 `local_artifacts/network_relevance_20261013/verified_nodes.json`。覆盖Session/Controller、真实隔离DPAPI、模拟HTTP/模型、生产Chrome DOM、既有Tk回退及Debug；不代表全仓库测试全部通过。

实际WebView2使用合成bridge、浅深主题进行22项检查，全部通过：Enter批量回答、Shift+Enter、表格归属、内联进度保留节点/详情、重命名位置/应用/不回传密钥；无模型桥接动作和自动PromptSmith日志。可复用脚本：[four_fixes_webview_check_20261013.py](four_fixes_webview_check_20261013.py)。本地结果：`local_artifacts/network_relevance_20261013/native-results.json`。

旧版隔离副本中14个新增复现均失败，正确覆盖短词/预算排序/各能力保留/GitHub目录/失败降级/低分排除/通知与表格节点。两条预算用例最初因HTTP替身没有视频正文而KeyError，补足模拟结果后旧版明确返回video-0而非pdf、修复版两条均通过；根因断言没有放宽。红灯文本在同一忽略目录的 `red_results.txt` 与 `red_budget_results.txt`。

其余验收修正：批量DOM等待回调、重命名/表格模拟过宽、联网UI测试未完成本地搜索前置均改为准确测试合同；原生脚本曾误把WebView2自身数据库.log算作程序日志，限定PromptSmith/logs后22项通过。没有为这些测试前置错误改生产逻辑。

Spec/Standards双轴最终各0待修。Spec发现开放搜索单查询份额与合并48项两处仍提前截断，已改为先排序后取额并新增跨查询/同查询第25项回归。标准轴确认预算、来源校验、取消与可信降级合同保持。

公开索引真实GET（无密钥/模型）：documentation、docx、pdf各返回100项，前列分别有documentation-writer、docx、pdf。证明相关Skill确实存在并可检索；没有访问个人API Key或调用真实Gemini/DeepSeek，不能宣称真实模型推荐质量已复测。未构建EXE、提交或推送，原有工作树成果保留。

收尾：51个变化/新增Python文件AST、workspace/settings JS语法及diff空白通过，700项交接/维护/清单相对链接有效。CodeGraph同步25文件后确认current（249files/6182nodes/18919edges）；维护三文件及团队交接已更新。
