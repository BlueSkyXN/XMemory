# 设计来源与采用边界

核对日期：Qoder、Codex、ZCode、Claude Code 部分为 2026-10-06；Cognition（AMR 与 Devin）、OMPI、Anthropic 部分为 2026-10-08。下面区分官方公开说明、本机静态观察和 XMemory 自己的选择。不复制产品内部数据或原始提示词；产品更新后应重新核对。

## Qoder 与 QoderWork 分开看

### Qoder CLI

官方 [Memory](https://docs.qoder.com/cli/memory.md) 说明 Markdown 索引、主题记忆及记住/忘记等管理操作。

采用：可编辑文件、短索引、主题详情，以及删除后同步清理入口。不能据此推断 QoderWork 使用同样的记忆根或加载机制，也不把 CLI 特性笼统说成 Qoder IDE 已全部实现。

Qoder 的 [IDE Skills](https://docs.qoder.com/extensions/skills.md) 与 [CLI Skills](https://docs.qoder.com/cli/Skills.md) 分别描述技能发现方式；两者重复名称优先级不能混用。本包建议避免同名多份安装。

### QoderWork

专门的 [Awareness 文档](https://docs.qoder.com/qoderwork/memory) 直接列出了：

- `SOUL.md`：协作/沟通偏好；
- `AGENTS.md`：工作与行为指导；
- `USER.md`：用户背景与偏好；
- `MEMORY.md`：长期知识与结论；
- `memory/`：每日摘要与临时记录。

该文档另有本地搜索索引、自动维护和定期反思说明。因此不能把 QoderWork 的 `MEMORY.md` 说成 Claude/ZCode 式的纯导航索引，也不能把文件布局说成其完整实现。

采用：指令、用户背景、长期结论和时间记录分开；当前理解需要维护而不是只追加。XMemory 不新建人格文件，不自动画像，不继承自动反思或本地索引服务。索引技术、排序、上下文预算、反思频率与精确项目隔离机制，本次没有据此确认。

技能安装另见 [QoderWork Skills](https://docs.qoder.com/qoderwork/skills)。Awareness 数据位置与技能目录是不同对象，不混为一谈。

## Codex

官方 [Memories](https://learn.chatgpt.com/docs/customization/memories?surface=app) 描述宿主支持的记忆能力；公开源码中的 [固定提交版整理提示](https://github.com/openai/codex/blob/594283af5c0a4c99cdede91b0d7951524b2535fb/codex-rs/memories/write/templates/memories/consolidation_v2.md) 展示来源驱动的整理、纠错/删除传播及无需更新时不写。

采用：先有工作证据，再整理；保留来源和未确认部分；删除影响派生内容；把记忆当资料而不是指令。固定提交只说明那一版代码，不代表所有 Codex 客户端都启用了相同记忆流水线。

不采用：异步后台整理、原生数据库、自动注入或私有数据格式。技能发现依据 [Build skills](https://learn.chatgpt.com/docs/build-skills)，不据此声称插件能访问全部历史会话。

## ZCode

官方 [项目记忆](https://zcode.z.ai/cn/docs/memory) 说明入口和主题文件、后续会话使用记忆等原生行为。[Skill](https://zcode.z.ai/cn/docs/skill) 与 [Plugin](https://zcode.z.ai/cn/docs/plugin) 分别说明方法和插件包装。

本次还对本机安装包 `glm/zcode.cjs` 做了只读静态核对：存在索引加事实文件的行为约定、按 workspace 身份计算记忆分区，以及默认索引加载逻辑。未读取任何个人记忆；这是安装包快照观察，不是运行验收。公开文档中的后台提取也不能外推为 XMemory 自带功能。

采用：入口简短、主题拆分、范围隔离和去重更新。XMemory 的“一条记忆”是一个稳定主题和主张，不规定每句话建文件。原生自动加载预算和目录算法不复制到插件，也不承诺插件文件自动进入每次会话。

## Claude Code

官方 [Memory](https://code.claude.com/docs/en/memory) 区分项目指令和自动记忆，并描述启动时读取原生 `MEMORY.md` 的有限内容、主题文件按需展开。[Skills](https://code.claude.com/docs/en/skills) 描述技能与配套资源。

采用：短入口、按需读取主题、指令和经验分开。XMemory 数据不会因文件同名就获得 Claude 原生记忆的启动加载待遇；`CLAUDE.md` 接入必须明确配置，不能把记忆当上级指令。

## Cognition：Agent Memory Repo 与 Devin Memory

[AMR 仓库](https://github.com/AgentMemoryRepo/agentmemoryrepo)（固定提交 `8798cb2`，2026-10-06）公开了文件格式和一个参考技能：`MEMORY.md` 是入口，`## Index` 上方放每次会话都需要的条目；条目一行一条，末尾可带 `[key: value]` 元数据，推荐 `source` 和 `added`；文件之间用 `[[path]]` 链接。参考技能只在被调用时工作，自述不带 Hook、定时任务和启动脚本；它要求记忆放在独立 Git 仓库、写前工作区干净、每次编辑都提交。周期性 Dreaming 只出现在 README 的描述中，参考包里没有实现。

[Devin Memory](https://docs.devin.ai/zh/product-guides/memory) 是基于 AMR 的产品实现：记忆存放在持久 Git 仓库，每个会话载入 `MEMORY.md`，其他笔记按需检索；被纠正、说明偏好或总结出经验时编辑笔记；保存时提交并合并其他会话的修改；大约每天运行一次后台 Dreaming。它明确只存偏好、纠正、决定及理由、仓库和环境中的坑，不存会话摘要、任务状态、可轻易重新获取的信息和凭据；由自动化启动的会话不读写记忆。

采用：记忆层只放长期沿用的内容，任务状态放接续层；入口放常驻条目加索引；整理集中在定期运行的一处；自动化任务不写记忆。

不采用：不以 Git 作为必需机制；不依赖宿主自动载入，改为读取协议；记忆文件头部用 YAML 而不是行尾元数据，以便与 OMPI 的记忆对象对应。不宣称与 AMR 格式兼容。Devin 的行为来自官方文档，本次没有运行验证。

## OMPI：开放记忆协议工作草案

[OMPI](https://ai-disclosures.org/ompi) 由 AI Disclosures Project（Code for Science & Society 下属项目）主办，Mozilla、IBM 为合作方，Letta 担任技术作者，目前处于 1.0 之前的早期阶段。2026-10-02 的 [编辑工作草案 v0.1](https://github.com/The-AI-Disclosures-Project/Open-Memory-Protocol/blob/a6c40e64969e0089ff7cad7397aea27a335a8c81/working-group/exchange-and-runtime/2026-10-02-working-spec-v0.1.md) 明确不是已采纳的标准，其中的规范性语句都还处于提议状态。

草案要点：记忆是头部加正文，正文推荐 Markdown，运行时可用 YAML front matter 呈现；`type` 指正文媒体类型而非语义分类；生效时间与记录时间分开；`provenance` 列出所有写入者，整理、遗忘等维护程序也要列入；证据只记录来源，不证明内容为真；遗忘要留下墓碑（何时、谁、为何，不含原文），并防止从旧档案复活；Markdown 加载档以根 `MEMORY.md` 为入口、深层文件按需读取；召回方式不做标准化；凭据不属于记忆。

采用：含义相同的地方使用草案字段名；语义类型放 `tags`；撤回墓碑记录执行者和原因；整理者写进 `provenance`。

不采用：导出清单、导入回执、迁移意图、MCP 运行时绑定、审计档（校验和、不可变修订链）。草案仍在变化，XMemory 不宣称符合。

## Anthropic：Managed Agents 记忆库与 Dreams

[记忆库](https://platform.claude.com/docs/en/managed-agents/memory)（beta `agent-memory-2026-07-22`）是工作区内的一组文本文件，挂载到会话沙箱的 `/mnt/memory/<名称>/`，Agent 用普通文件工具读写。每次修改都生成不可变版本，一般保留 30 天，在用记忆的近期版本始终保留；历史版本可以脱敏；更新可带内容哈希前置条件，防止覆盖他人的修改。文档提醒：可写的记忆库可能被提示注入写入恶意内容，参考资料应只读挂载。

[Dreams](https://platform.claude.com/docs/en/managed-agents/dreams)（研究预览，`dreaming-2026-04-21`）读取一个记忆库和 1 到 100 个历史会话，产出一个新的记忆库。输入库从不修改，由用户审阅后决定是否切换。

采用：记忆就是普通文件，用普通文件工具读写；自动整理不擅自改动需要判断的内容，所以定时整理分为记账类和判断类；记忆是资料不是指令，参考资料只读。

不采用：云端接口和托管的版本历史。

## Office Memory

本地原有方法提供了日期记录、当前交接、长期结论的分工，以及来源只读、冲突核实、未完成项检查和整理后试查。这里提炼方法，不把项目私有内容、硬体量限制、来源适配脚本或固定 schema 复制进公开插件。

采用：日期记录（对应当日文件）；长期条目的复查日期（对应 `review`）；整理时写明实际检查过的来源（对应近况的"本次读过 / 未读"）；引用会被整体重写的聚合文件时用标题锚点而不用行号；重写当前认知前核对待办（对应当日文件的"状态变化"）；读取规则写进根 AGENTS.md（对应读取协议）。

实际使用中暴露过三种压力：单一长期记忆文件接近体量上限后难以新增条目；待确认清单只增不减；同一项目的多条工作线挤在一份认知文件里。对应做法是：记忆按主题拆分，久无进展的待办移入积压，近况按工作线分节。

## 本版自己的设计

五技能名称、`personal` 与 `project:<id>` 范围、两层结构、事件文件与当日文件、"是否处理过以当日文件为准"、分级整理、四类地址、主本与同步点，以及文件格式 `xmemory/v1`，都是 XMemory 的约定，不是上述任何产品或草案的官方标准。研究 demo 是设计输入，不是正式旧版，也不构成升级兼容关系。

[Agent Skills 规范](https://agentskills.io/specification#file-references) 推荐相对技能根引用配套文件。正式插件和便携包的每个技能都包含自身所需的资源，不使用 `../../` 依赖相邻目录。仓库开发工具从共用文档同步这些静态副本并检查一致性，使用插件时不运行同步工具。

2026-10-07 另核对了三端包装：[Claude 插件规范](https://code.claude.com/docs/en/plugins-reference)、[Claude 市场规范](https://code.claude.com/docs/en/plugin-marketplaces)、[Codex 插件与市场](https://developers.openai.com/plugins/build/plugins)。Claude 使用 `.claude-plugin/plugin.json` 与其独立市场清单；Codex 使用官方当前推荐的根 `plugin.json` 与 `.agents/plugins/marketplace.json`；ZCode 保持 `.zcode-plugin/plugin.json` 和原本地市场。三端市场字段不同，不以同一 JSON 冒充所有规范。真实发现、安装和加载效果仍需宿主验证。

归纳起来，借鉴的是文件组织、信息分层、整理判断和生命周期约定，不是把各产品的名词、原生后台能力或目录全部拼在一起。
