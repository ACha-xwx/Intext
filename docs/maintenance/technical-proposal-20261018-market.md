# 意织 Intext 技术方案：市场与同类产品公开资料核查

核查日期：2026-10-18。责任范围：公开市场背景、同类产品功能、Agent Skills 标准；未修改程序、未访问个人配置、未调用付费模型接口。本文件供技术方案撰写引用，产品功能边界依据本轮给定事实及当前 `HANDOFF.md`，外部事实依据以下实际读取的一手资料。

## 1. 目的、范围与完成标准

本次核查要解决三个问题：生成式 AI 的使用基础有多大；同类工具已经提供哪些能力；Agent Skills 的标准化为意织的交付方式提供什么依据。

完成标准：市场数字注明统计时点和口径；功能比较能够定位到官方原文；将官方事实、产品事实和待验证判断分别表达；不以生成式 AI 总体规模替代提示词工具市场规模，不编造意织的市场份额、付费需求或使用效果。

## 2. 可用于技术方案的结论

1. 生成式 AI 已具备广泛使用基础。CNNIC 最新可核实报告称，截至 2026 年上半年，我国生成式人工智能用户规模“突破 7 亿人，普及率超 50%”。该数字为 CNNIC 依据网络数据平台的测算值，适合说明行业背景。[S1]
2. 写作、办公等任务有可观察的使用基础，但不能据此推算意织的目标用户数。CNNIC 的调查数据中，生成处理文本、工作总结/会议纪要/PPT 的使用目的占比分别为 37.6%、32.5%；这些指标的调查截止时间是 **2025 年 12 月**，不能写成 2026 年上半年新调查。[S1][S2]
3. 多模型接入、提示编写和工作流组织已有成熟产品提供。Dify 官方资料包含模型管理、Prompt IDE、可视化工作流、RAG 与应用发布；OpenAI 官方资料说明 Custom GPTs 能通过指令、知识文档和第三方服务定制 ChatGPT。[S3][S4] 因此，技术方案不宜把“支持多模型”或“能生成提示词”单独表述为行业首创。
4. 意织当前可陈述的产品定位是：面向桌面使用场景，把初始目标经过澄清访谈、需求确认、方案确认和可选 Skill 选择，整理为可交给另一个 AI 使用的提示词。与 GPTs、Dify 的比较应围绕 **交付对象与操作流程** 展开，效果优劣须通过同任务比较或用户测试验证。
5. Agent Skills 已有公开格式和渐进披露机制。标准要求以 `SKILL.md` 作为入口，先提供名称和描述，需要时再读取正文及资源。[S6][S7] 这为“先发现、再解释和匹配、交付来源与任务用途”的设计提供技术背景。标准存在不等于任意下游 AI 都能读取或执行 Skill；意织当前也不负责安装或执行发现的 Skill。

## 3. 市场规模与使用趋势证据

### 3.1 最新总体用户规模

**来源与日期。** 中国互联网络信息中心《生成式人工智能应用发展报告（2026）》，PDF 封面日期为 2026 年 9 月；官方介绍页说明于 2026 年 9 月 29 日发布，介绍页显示时间为 2026 年 10 月 8 日 15:39。[S1]

**可引用原句。** PDF 印刷第 7 页（PDF 文件第 15 页）：

> 据测算，截至 2026 年上半年我国生成式人工智能用户规模突破 7 亿人，普及率超 50%。

同页脚注 12：

> 2026 年 6 月的生成式人工智能用户规模和普及率均为 CNNIC 依据网络数据平台测算得到。

**可用表述。** “据 CNNIC《生成式人工智能应用发展报告（2026）》，截至 2026 年上半年，我国生成式 AI 用户规模突破 7 亿人，普及率超过 50%，为面向 AI 使用者的辅助工具提供了广泛的使用背景。”

**口径限制。** 这是生成式 AI 产品或服务的总体使用规模，包含多种设备和使用目的；不是提示词优化软件、Windows 桌面工具或愿意自行配置 API 的用户规模。本次读取的相关页未披露这一测算值的完整算法，不应把它改写成精确的“7.00 亿人”、付费用户数或月活跃用户数。

### 3.2 可作历史参照的用户增长

**来源与日期。** CNNIC 第 57 次《中国互联网络发展状况统计报告》，官方页显示 2026 年 2 月 5 日 17:00，并说明当天发布。网页 URL 的路径含 `0304`，引用时应采用页面正文的发布日期，不从 URL 推断日期。[S2]

**可引用原句。** PDF 印刷第 41 页（PDF 文件第 49 页）：

> 截至 2025 年 12 月，我国生成式人工智能用户规模达 6.02 亿人，较 2024 年 12 月增长 3.53 亿人，规模增长达 141.7%；普及率达 42.8%，较 2024 年 12 月提升 25.2 个百分点。

同页脚注 64 对 42.8% 的解释：

> 指过去半年内，我国整体人口中使用过生成式人工智能产品或服务的比例为 42.8%。

**使用限制。** 42.8% 不是“占网民的比例”。2025 年调查与 2026 年网络数据平台测算的方法不同，不宜仅用两个规模数计算并宣称细分市场增速；可分别标注为两个时点的总体背景。

### 3.3 与意织使用场景相关的指标

| 指标 | 数值 | 时间与分母 | 解释边界 |
| --- | --- | --- | --- |
| 回答问题 | 76.0% | 第 57 次统计调查电话问卷；截止 2025-12；生成式 AI 用户的使用目的 | 可说明问答是常见场景；不能说明用户普遍缺少提示词能力 |
| 生成处理文本 | 37.6% | 同上 | 可说明文本任务具有使用基础；不能直接推算提示词工具购买意愿 |
| 生成处理工作总结/会议纪要/PPT | 32.5% | 同上 | 可作为办公场景选择依据；不代表这些用户会采用意织 |
| 电脑网页版 AI 应用 | 15.6% | 第 57 次统计调查线上问卷；截止 2025-12；网民使用方式 | 与下行电脑客户端是同一线上问卷口径，不能与电话问卷的产品使用率混算 |
| 电脑 AI 客户端 | 6.5% | 同上 | 说明桌面端存在使用场景，也提示移动端入口更普遍；不是意织可获取份额 |

前 3 行见 [S1] 印刷第 8 页（PDF 第 16 页）及脚注 14；后 2 行见印刷第 7 页（PDF 第 15 页）及脚注 13。第 57 次报告印刷第 45 页（PDF 第 53 页）另列“客户端应用”在生成式 AI 用户中的使用率为 24.7%，其分母与上述线上问卷的 6.5% 不同；技术方案无需同时使用，以免形成表面矛盾。

**趋势补充。** [S1] 印刷第 8—9 页（PDF 第 16—17 页）转引 QuestMobile TRUTH 人工智能洞察数据库：2026 年 7 月 AI 效率办公类应用使用次数同比增长 112.4%，AI 综合助手为 162.8%。这是 CNNIC 对第三方数据的引用，不属于本次直接获得的 QuestMobile 原始数据；指标是“使用次数”，不是用户数、营收或提示词工具市场增速。如采用，须写明转引关系；主文仅用 CNNIC 直接调查指标已足够。

### 3.4 本产品细分市场仍缺什么证据

本次未找到能够直接量化“中文 Windows 桌面、由用户配置模型 API、通过访谈确认需求、向其他 AI 交付提示词”的官方市场统计。技术方案可写目标人群和应用场景，不应填入未经验证的 TAM、SAM、SOM 或市场份额。

后续如需商业规模，可先调查目标群体的 Windows 使用、AI 任务频率、配置 API 的接受程度、跨 AI 交付习惯与付费意愿，再公开样本来源、有效样本数和估算假设。此处是研究建议，不是已取得的市场结果。

## 4. 同类产品比较：可确认的功能与边界

| 对象 | 官方可核实能力 | 当前定位与主要交付 | 允许写入技术方案的比较 |
| --- | --- | --- | --- |
| OpenAI Custom GPTs / GPT Actions | 通过指令、文档知识和第三方服务定制 ChatGPT；Actions 经 REST API 检索数据或执行外部动作 [S3] | 在 ChatGPT 内定制并运行特定用途助手 | 意织围绕任务澄清与确认后形成对外可交付的提示；GPTs 围绕 ChatGPT 内的定制助手。该差异不证明谁的完成效果更好 |
| Dify | 工作流、Prompt IDE、模型管理、RAG、Agent、可观测性及 API；支持云端和自托管；可发布 Web 应用或 API [S4] | 构建、运行和发布 AI 应用的平台 | 意织当前聚焦本地桌面任务准备与提示交付；Dify 覆盖应用开发和运行。Dify 已提供自托管，因此不能把“可在自己的环境运行”当作意织独有能力 |
| PromptPerfect | 官网标题为“AI Prompt Generator and Optimizer”；首页元描述说明针对 GPT-4、ChatGPT、Midjourney 等模型生成和优化提示 [S5] | 本次只能核实其公开的提示生成/优化定位 | 可列为提示优化方向的相关产品；尚不足以核实其完整交互、价格、实际支持模型、优化质量或是否具有需求访谈 |
| 意织 Intext | 本轮给定事实及当前交接：Windows 本地桌面；目标→澄清访谈→需求确认→方案确认→可选 Skill 检索→交付提示；五类供应商可配置；历史本地恢复 | 为下游 AI 整理任务说明、约束、方案及可选 Skill 引用与用途 | 这些是当前产品功能事实。其“降低返工”“提高结果质量”“节省时间”等价值仍须有匹配的模型比较或用户测试证据 |

比较对象的范围并不完全相同，应使用“相关产品”或“同类能力比较”，避免把大型应用平台当作只做提示改写的产品。除非对相应功能完成全面测试，不应使用“竞品不支持”“唯一具备”或“全面领先”等结论。

### 4.1 GPTs 的引用原文

[S3] OpenAI 官方开发文档《GPT Actions》：

> GPT Actions are stored in Custom GPTs, which enable users to customize ChatGPT for specific use cases by providing instructions, attaching documents as knowledge, and connecting to 3rd party services.

> GPT Actions empower ChatGPT users to interact with external applications via RESTful APIs calls outside of ChatGPT simply by using natural language.

该来源直接支持 GPTs 的定制能力与 Actions 的外部交互能力。本次未据此判断订阅限制、价格、中国大陆可用性或现行 GPT Store 分发规则。页面未显示可核实的独立发布日期，引用时使用“访问日期 2026-10-18”。

### 4.2 Dify 的引用原文

[S4] 官方文档首页：

> Dify is an open-source platform for building AI applications. Create agents, agentic workflows, and chatbots that draw on your own data, then publish them as web apps or integrate them through APIs.

官方 README 的 Prompt IDE 条目：

> Intuitive interface for crafting prompts, comparing model performance, and adding additional features such as text-to-speech to a chat-based app.

官方 README 的工作流条目：

> Build and test powerful AI workflows on a visual canvas, leveraging all the following features and beyond.

官方 Model Providers 文档：

> Use models with your AI credits, or connect your own provider accounts and keys

文档该页显示最后修改日期为 2026-07-29。README 在本次读取时的最近修改提交为 `f0a0ea807c4260996ead632d5b8080a876673563`，提交时间 `2026-10-10T06:34:46Z`。以上功能描述采用官方自述，不把其性能、部署耗时或使用门槛的宣传性描述作为本次实测结果。

### 4.3 PromptPerfect 的证据强度

[S5] 成功读取官方首页 HTML，标题为：

> PromptPerfect - AI Prompt Generator and Optimizer

元描述为：

> Unlock prompt optimization for models like GPT-4, ChatGPT and Midjourney. Generate and refine prompts to perfection, receiving improved outcomes in seconds.

元描述中的效果和速度属于供应商宣传，本次没有验证，不可转述成测试结论。首页主要为 JavaScript 应用壳，文档站请求发生 TLS 连接错误，所以目前只建议引用其产品定位。

## 5. Agent Skills：标准、渐进披露与产品衔接

[S6] Anthropic 工程文章《Equipping agents for the real world with Agent Skills》发表于 2025-10-16，页面另有 2025-12-18 更新，说明 Agent Skills 已作为开放标准发布以实现跨平台可移植性。

可引用原文：

> Agent Skills: organized folders of instructions, scripts, and resources that agents can discover and load dynamically to perform better at specific tasks.

> Progressive disclosure is the core design principle that makes Agent Skills flexible and scalable.

[S7] Agent Skills 官方概述：

> Agent Skills are a lightweight, open format for extending AI agent capabilities with specialized knowledge and workflows.

官方格式规范要求：

> The `SKILL.md` file must contain YAML frontmatter followed by Markdown content.

其 `name`、`description` 为必填字段，`scripts/`、`references/`、`assets/` 为可选资源组织方式。规范的渐进披露分为元数据、激活时的正文、按需资源三个层次。概述页将其解释为 Discovery、Activation、Execution：先识别名称和描述，再读取完整 `SKILL.md`，最后按需要读取资源或执行代码。

**与意织的关系。** 意织可把 Skill 的名称、来源和针对当前任务的使用位置交给下游 AI，帮助下游定位相应资源。格式标准和渐进披露支持这种“提供引用及读取用途”的设计思路，但不能据此声称意织已安装、运行或验证每个发现的 Skill，也不能保证不具备文件/网络访问能力的下游 AI 自动执行引用。Skill 格式和生态发展是外部技术事实；匹配效果仍是本产品需要验证的指标。

## 6. 资料获取与核查记录

采用 Python `urllib.request` 向公开官方站点发起匿名 GET；HTML 读取正文，官方 Markdown 页面读取原文；PDF 在内存中用 `pypdf` 提取文字。未调用搜索或模型付费 API，未登录站点，未读取用户浏览器、凭据或私人会话。未将下载 PDF、页面缓存或构建产物写入仓库。

| 编号 | 官方来源与实际读取结果 | 日期、引用定位与限制 |
| --- | --- | --- |
| S1 | [CNNIC 2026 报告介绍页](https://www.cnnic.net.cn/n4/2026/1008/c88-11704.html)；[官方 PDF](https://www.cnnic.net.cn/NMediaFile/2026/1008/MAIN1791445205224NIO3ZYE5MH.pdf)，均 HTTP 200；PDF 54 页 | 2026-09 报告，09-29 发布，10-08 网页；重点读取印刷第 7—9 页、对应 PDF 第 15—17 页，包含脚注 12—15 |
| S2 | [CNNIC 第 57 次报告介绍页](https://www.cnnic.net.cn/n4/2026/0304/c88-11549.html)；[官方 PDF](https://www.cnnic.net.cn/NMediaFile/2026/0304/MAIN1772588317069TUXN3827X8.pdf)，均 HTTP 200 | 页面日期 2026-02-05；重点读取印刷第 41—45 页、对应 PDF 第 49—53 页；印刷第 65 页调查总体为中国内地 31 省区市、有住宅固定电话或手机的 6 岁及以上居民 |
| S3 | [OpenAI GPT Actions](https://developers.openai.com/api/docs/actions/introduction)；[官方 Markdown](https://developers.openai.com/api/docs/actions/introduction.md)，均 HTTP 200 | 页面未明确显示独立发布日期，访问 2026-10-18；原 `platform.openai.com/docs/actions/introduction` 自动重定向至此。`openai.com/index/introducing-gpts/` 和帮助中心创建 GPT / GPTs FAQ 页面均返回 HTTP 403，没有将其未读内容作为证据 |
| S4 | [Dify 文档首页](https://docs.dify.ai/en/home)；[官方 README 固定版本](https://github.com/langgenius/dify/blob/f0a0ea807c4260996ead632d5b8080a876673563/README.md)；[Model Providers](https://docs.dify.ai/en/cloud/use-dify/workspace/model-providers) | 文档、README 的 raw 地址及匿名 GitHub 提交 API 均成功读取；模型供应商文档显示最后修改日期 2026-07-29；README 最近修改为 2026-10-10。功能未在本次实际部署测试 |
| S5 | [PromptPerfect 官网](https://promptperfect.jina.ai/)，HTTP 200 | 只读取首页标题和元描述；`docs.promptperfect.jina.ai` 首页及 quick-start 请求均报 `SSL: UNEXPECTED_EOF_WHILE_READING`。未读取完整文档，未测试产品 |
| S6 | [Anthropic 工程文章](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)，HTTP 200 | 发表 2025-10-16；页面更新说明开放标准日期 2025-12-18；访问 2026-10-18 |
| S7 | [Agent Skills 概述](https://agentskills.io/home)；[格式规范](https://agentskills.io/specification)，及对应 `.md` 页面均 HTTP 200 | 页面未显示可核实的独立发布日期，访问 2026-10-18；原 `what-are-skills` 路径自动重定向至 `home` |

本次验证属于公开资料读取与口径校对，不包含竞品实测、市场抽样调查、真实模型质量评估、商业可行性证明或意织用户测试。网页和开放标准会继续变化，正式提交前应检查关键链接和日期。
