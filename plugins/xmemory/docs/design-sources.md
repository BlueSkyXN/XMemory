# 设计来源与采用边界

核对日期：Qoder、Codex、ZCode、Claude Code 的官方说明为 2026-10-06；Cognition、OMPI、Anthropic 为 2026-10-08；1.2.0 的增补（各产品机制对照、OpenClaw、Hermes、腾讯与阿里候选、WorkBuddy、Trae）为 2026-10-10，依据是对公开源码、安装包和官方文档的静态研究，以及对本机各端记忆目录的只读观察。

下面区分官方公开说明、静态观察和 XMemory 自己的选择。不复制产品内部数据或原始提示词；产品更新后应重新核对。静态观察说明“代码里有这条链”，不等于用户本机已启用或已经运行。

## Codex

官方 [Memories](https://learn.chatgpt.com/docs/customization/memories?surface=app) 描述宿主支持的记忆能力；公开源码的 [固定提交版整理提示](https://github.com/openai/codex/blob/594283af5c0a4c99cdede91b0d7951524b2535fb/codex-rs/memories/write/templates/memories/consolidation_v2.md) 展示来源驱动的整理、纠错与删除传播，以及无需更新时不写。

静态观察：
- **总开关**默认关闭，开启后在新回合开始时触发后台流程。
- **第一阶段**：处理过去已闲置的交互会话，逐会话用模型提取摘要并存入数据库；同时生成逐会话摘要文件，文件头部有会话 ID、更新时间、cwd、分支。
- **第二阶段**：全局只有一个整理任务，持有租约，成功后有冷却期；以 Git 基线和 diff 判断变化，生成 handbook 式 `MEMORY.md` 和紧凑摘要。
- **常驻**：紧凑摘要约 2500 tokens，注入 developer 通道。
- **范围**：数据库查询不按 cwd 过滤，项目范围只在 handbook 中用 `applies_to: cwd=` 语义表达。

采用：
- 两阶段结构：逐会话提取对应采集，单写者合并对应整理；
- 允许“没有可记内容”；
- 保留来源和未确认部分；
- 删除要影响派生内容；
- 记忆是资料而不是指令；
- 把 Codex 的逐会话摘要和 Task Group 当作采集的首选输入。

不采用：内置后台进程（改由宿主定时任务触发）、原生数据库、developer 通道自动注入、按引用次数排序（纯技能的调取只读，无法记录使用次数）。固定提交只代表那一版代码。

## ZCode

官方 [项目记忆](https://zcode.z.ai/cn/docs/memory) 说明入口、主题文件和后续会话使用记忆；[Skill](https://zcode.z.ai/cn/docs/skill) 与 [Plugin](https://zcode.z.ai/cn/docs/plugin) 分别说明方法和插件包装。

静态观察（安装包 `glm/zcode.cjs`，只读）：
- 成功的普通回合结束后，启动受限的后台提取，最多 5 轮；出错时不推进游标；没有值得保存的内容就输出“Nothing to save.”。
- 默认加载索引，主题按需读。
- 主题文件头部为 `name`、`description`、`metadata.type`（user/feedback/project/reference），可附 `originSessionId`。
- 项目分区目录是 `<目录名小写>-<hash>`。

采用：入口简短，主题拆分；主题头部沿用 `name`、`description`、`type`；把分区目录名登记为项目别名；出错不推进进度。原生自动加载预算和目录算法不复制到插件，也不承诺插件文件自动进入每次会话。

## Claude Code

官方 [Memory](https://code.claude.com/docs/en/memory) 区分项目指令和自动记忆，启动时读原生 `MEMORY.md` 的有限内容，主题文件按需展开；[Skills](https://code.claude.com/docs/en/skills) 描述技能与配套资源。

静态观察：
- 保存是“先写主题文件，再更新索引一行”的模型约定，不是事务。
- 写入时打上的 `modified` 时间不等于事件发生时间。
- 有门控的 Dream 整理提示要求：合并近似重复、把相对日期改为绝对日期、删除被推翻的旧事实、压缩索引。

采用：短入口加主题按需读；指令和经验分开；整理时把相对日期换算为绝对日期；区分写入时间和事件时间。XMemory 数据不会因文件同名就获得 Claude 原生记忆的启动加载待遇；`CLAUDE.md` 接入必须明确配置，不能把记忆当上级指令。

## Qoder CN、Qoder CLI 与 QoderWork

### Qoder CN / CLI

官方 [Memory](https://docs.qoder.com/cli/memory.md) 说明 Markdown 索引、主题记忆以及记住、忘记等操作。静态观察：
- 索引和主题按用户、项目两种范围分区，主题有四种类型；
- CLI 的项目记忆还按类别分目录（常见坑、决策、架构、技术栈、任务摘要、规范、环境等）；
- 技能建议要经过接受、新的人工回合和内容 hash 一致才会写入。

采用：项目分区；按类别映射到 XMemory 的六种主题类型；“建议”和“写入”是不同状态，XMemory 只给技能建议，不自动写技能。

### QoderWork

专门的 [Awareness 文档](https://docs.qoder.com/qoderwork/memory) 列出：`SOUL.md`（协作和沟通偏好）、`AGENTS.md`（工作指导）、`USER.md`（用户背景与偏好）、`MEMORY.md`（长期知识与结论）、`memory/`（每日摘要与临时记录）。

静态观察：
- `MEMORY.md` 是以 `§` 分条的长期正文，工具写入上限 10 KiB；`USER.md` 上限 4 KiB。
- 日记按本地日期分文件，每个会话一块。
- 回合结束按累计得分决定是否写入。
- 反思定期检查变化后执行，有备份和回滚，并做关键信息（路径、版本、数字等）保全检查。
- 用量超过 80% 时按重要度和新旧淘汰，淘汰内容写进日志。

采用：
- 画像（`USER.md`，只收工作相关内容，由整理维护）；
- 意识（`AWARENESS.md`）；
- 按日期的每日记忆，足迹按会话落在当天；
- 重写前备份；
- 关键信息保全核对；
- 按重要度淘汰并记录去向。

不采用：人格文件 `SOUL.md`、宿主内置的定时反思进程、本地全文索引服务。“意识”这个名称沿用 QoderWork 的 Awareness。

## OpenClaw 与 Hermes

[OpenClaw](https://github.com/openclaw/openclaw) 稳定版的默认记忆插件静态观察：
- `USER.md`、`MEMORY.md`、按日的 `memory/YYYY-MM-DD.md` 和给人审阅的 `DREAMS.md` 分工明确；
- 压缩上下文前，把要点只追加地写进当天日记；
- 重置会话时读取最近两天日记，并标注为不可信的工作区笔记；
- 默认 cron 运行 Dreaming：light、REM 不写长期事实，deep 晋升需同时满足分数、总信号数、不同用户查询数门槛；
- 晋升前重读原始来源并核对指纹，已有条目损失超过阈值就退回只追加；
- 遗忘先写 tombstone，再清理按来源 lineage 追踪到的派生数据。

[Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory) 静态观察：
- `MEMORY.md` 和 `USER.md` 以 `§` 分条，默认上限 2200 和 1375 字符；
- 超容量时报错并要求合并，不静默丢弃；
- 会话内提示词冻结，压缩时重载。

采用：
- 压缩前写足迹（Hook 模板）；
- 延续任务时读最近两天每日记忆；
- 晋升需要多个独立信号并回原件核对；
- 整理记录给人审阅、不作为事实来源；
- 已有条目损失核对；
- 撤回留标识；
- 超容量时不静默截断。

不采用：内置 cron、派生数据库、向量检索。

## 腾讯与阿里的记忆服务候选

[TencentDB Agent Memory](https://github.com/TencentCloud/TencentDB-Agent-Memory) 静态观察：
- 粒度分四层：L0 原对话 → L1 原子记忆 → L2 场景 → L3 画像。
- L1 有七类（画像、经历、指令、工作事实、任务、方法、产物），记录来源消息 ID，按日分片。
- 当前代理只常驻注入 L3 正文和 L2 索引，L1 用只读工具按需查。
- 模型抽取失败时游标仍会推进，在一定条件下会漏掉增量。

阿里的上下文服务客户端插件在会话开始和用户提问时组装上下文，会话结束时请求抽取；但请求被接受不等于抽取完成。

采用：
- 四层粒度（原件、足迹、主题与每日、常驻），与内容类型分成两条轴；
- 足迹条目参照 L1 七类；
- 常驻层只放顶层概括；
- 来源进度只在成功后推进；
- “接受、保存、生成、可检索、生效”分开报告。

不采用：服务端数据库、向量检索、团队权限模型。两个原名产品的身份尚未确认，这里只研究官方候选。

## WorkBuddy 与 Trae

WorkBuddy 5.5.3 静态观察：
- 桌面端读取工作区 `MEMORY.md`、用户本地 `MEMORY.md` 和云端 profile，并按字符上限注入；
- 每轮提示模型追加工作区日记；
- “30 天后蒸馏”是提示词要求，不是已证实的后台任务。

Trae 的 Chronicle 屏幕观察：
- 摘要标注为不可信观察，带时间窗和来源 ID；
- 普通记忆按项目和日期分目录。

采用：工作区日记和按日期目录的时间轴；观察类内容一律作低信任线索，不自动升级为偏好或事实。不采用：云端 profile 和屏幕采集。

## Cognition：Agent Memory Repo 与 Devin Memory

[AMR 仓库](https://github.com/AgentMemoryRepo/agentmemoryrepo)（固定提交 `8798cb2`）公开了文件格式和参考技能：
- `MEMORY.md` 是入口，条目一行一条，推荐 `source` 和 `added`，文件之间用 `[[path]]` 链接；
- 参考技能只在被调用时工作；
- 周期性 Dreaming 只出现在 README 的描述中。

[Devin Memory](https://docs.devin.ai/zh/product-guides/memory) 基于 AMR：每个会话载入 `MEMORY.md`，其他笔记按需检索；被纠正、说明偏好或总结出经验时编辑笔记；大约每天一次后台 Dreaming；只存偏好、纠正、决定及理由、坑，不存会话摘要和凭据。

采用：主记忆只放长期结论；入口放常驻要点；整理集中在定期运行的一处。不采用：Git 作为必需机制；不宣称与 AMR 格式兼容。

## OMPI：开放记忆协议工作草案

[OMPI 编辑工作草案 v0.1](https://github.com/The-AI-Disclosures-Project/Open-Memory-Protocol/blob/a6c40e64969e0089ff7cad7397aea27a335a8c81/working-group/exchange-and-runtime/2026-10-02-working-spec-v0.1.md) 明确不是已采纳的标准。

采用其理念：生效时间与记录时间分开；出处列出写入者；证据只记录来源、不证明内容为真；遗忘留下不含原文的墓碑并防止复活；凭据不属于记忆。

1.2.0 的主题头部改为与 Claude Code、ZCode 的主题文件对齐（`name`、`description`、`type`），不再沿用草案字段名。不宣称符合草案。

## Anthropic：Managed Agents 记忆库与 Dreams

[记忆库](https://platform.claude.com/docs/en/managed-agents/memory) 是挂载到沙箱的一组文本文件，用普通文件工具读写，每次修改生成版本，并提醒可写记忆库可能被提示注入写入恶意内容。[Dreams](https://platform.claude.com/docs/en/managed-agents/dreams) 读取记忆库和历史会话，产出新的记忆库，由用户审阅后切换。

采用：记忆就是普通文件；参考资料只读；整理的判断类改动在无人值守时只写成候选，由用户确认。不采用：云端接口和托管的版本历史。

## Office Memory（此前的自有实践）

Office Memory 是我们此前在单个项目中的自有实践，不是行业标准。它提供了整理引擎：
- 6 级证据；
- 候选归一（对象、主张、范围、观察时间、状态时间、证据、边界）；
- 11 种处置；
- 日期记录、当前认知、长期结论三层分工；
- 当前认知五节结构与轮转副本；
- 聚合文件用标题锚点；
- 会话按工作目录归属并设静默期；
- 整理后做调取检查。

采用：上述整理引擎完整继承，并从单项目推广到全部项目和 personal。当前认知五节对应意识，日期记录对应每日记忆，长期条目对应主题，复查日期对应 `review`。

实际使用中暴露过三种压力：单一长期记忆文件接近体量上限；待确认清单只增不减；多条工作线挤在一份认知文件里。对应做法是：主记忆拆成要点加主题、意识中设“搁置”小节、意识按工作线分组。

不复制项目私有内容、固定体量或来源适配脚本。

## 本版自己的设计

以下都是 XMemory 自己的约定，不是上述任何产品或草案的官方标准：
- 五技能名称；
- `personal` 与 `project:<项目名>` 范围；
- 四层结构与目录命名；
- 足迹按事件日期落位；
- “是否已整理以每日记忆的已吸收足迹为准”；
- 采集清单与来源进度；
- 晋升门槛、意识改写比例自检、三项写后核对；
- 地址写法；
- 文件格式 `xmemory/v1`。

研究 demo 是设计输入，不是正式旧版。

[Agent Skills 规范](https://agentskills.io/specification#file-references) 推荐相对技能根引用配套文件。正式插件和便携包的每个技能都包含自身所需的资源，不使用 `../../` 依赖相邻目录；仓库开发工具从共用文档同步这些静态副本并检查一致性。三端包装分别遵循 [Claude 插件规范](https://code.claude.com/docs/en/plugins-reference)、[Claude 市场规范](https://code.claude.com/docs/en/plugin-marketplaces)、[Codex 插件与市场](https://developers.openai.com/plugins/build/plugins) 和 ZCode 本地市场；真实发现、安装和加载效果仍需宿主验证。

归纳起来，借鉴的是流水线结构、信息分层、整理判断和生命周期约定，不是把各产品的名词、原生后台能力或目录全部拼在一起。
