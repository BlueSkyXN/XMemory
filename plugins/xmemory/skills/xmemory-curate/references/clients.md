# 客户端读取映射

XMemory 从各客户端已有的记忆和会话中抽取信息，加工成自己的记忆。各端文件名相同，含义却可能不同：`MEMORY.md` 在 ZCode、Claude Code、Qoder CLI 里是索引，在 QoderWork、Hermes 里是正文，在 Codex 里是 handbook。所以每个来源都要先回答四个问题：

1. 谁能读：是普通 Markdown、分条正文、JSONL 还是数据库；
2. 读到的含义：在 XMemory 里对应哪一层；
3. 归属：怎么判定属于哪个项目；
4. 可信度：按原生转述处理（证据等级 4 或 5），晋升前要找到项目证据或回原始会话核对。

所有来源一律只读。下表路径是这些客户端的常见默认位置，以本机实际和用户登记为准；本机不存在就跳过并注明，不搜索其他目录代替。

## 原生记忆（优先读取）

原生记忆已经由各客户端提炼过，密度高、成本低，应该先读。

| 客户端 | 读什么 | 在 XMemory 里对应 | 归属 |
|---|---|---|---|
| Codex | `~/.codex/memories/rollout_summaries/*.md`：头部含会话 ID、更新时间、原始会话路径、cwd；正文含偏好、步骤、知识与失败 | 足迹素材；`updated_at` 表示源更新时间，不是每条事件时间。已观察版本的摘要文件名时间为 UTC、rollout 文件名为生成机器本地时间：两者按配置时区换算后指向同一时刻，即可作为会话开始时刻落位；不一致或缺少其一时，只采用带时区字段/原始消息能确认的精度（只知日期或未知），不外推到所有版本和设备 | 按 cwd |
| Codex | `~/.codex/memories/MEMORY.md` 的 Task Group（含 scope、`applies_to: cwd=…`、keywords、可复用知识） | 主题候选 | 按 `applies_to` |
| Codex | `~/.codex/memories/memory_summary.md`（用户画像、偏好、通用技巧） | 画像候选 | personal |
| Codex | `~/.codex/memories/skills/` | 只记技能入口 | 按内容 |
| ZCode | `~/.zcode/cli/memories/projects/<slug>-<hash>/memory/*.md`：`MEMORY.md` 为索引，其余为主题文件，头部有 `name`、`description`、`metadata.type`、`originSessionId` | 主题候选 | 按项目别名（slug） |
| Claude Code | `~/.claude/projects/<路径编码>/memory/*.md`：结构同 ZCode | 主题候选 | 按项目别名（路径编码） |
| Qoder CLI | `~/.qoder-cn/memories/<用户>/projects/<路径编码>/<类别>/*.md`：按类别分目录（常见坑、决策、架构、技术栈、任务摘要、规范、环境等） | 主题候选 | 按项目别名 |
| QoderWork | `~/.qoderworkcn/awareness/main/`（国际版为 `~/.qoderwork/`）：`USER.md` 画像、`MEMORY.md` 以 `§` 分条的长期正文、`memory/YYYY-MM-DD.md` 按会话分块的日记、`.memory_evicted.log` 淘汰日志 | 画像候选；主题候选；对应日期的足迹素材；淘汰内容作退役线索 | 按内容提及 |
| WorkBuddy | 全局 `~/.workbuddy/memory/*_memory.md`；项目内 `.workbuddy/memory/MEMORY.md` 与 `YYYY-MM-DD.md` | 主题候选；对应日期的足迹素材 | 按项目路径或提及 |
| Trae | `~/.trae-cn/memory/projects/<路径编码>/<YYYYMMDD>/topics.md`、`user_profile.md` | 对应日期的足迹；画像候选 | 按项目别名 |
| Office Memory | 项目内 `.agents/` 下的 `awareness/AWARENESS.md`、`memory/MEMORY.md`、`memory/YYYY-MM-DD.md` | 按迁移规则一对一转入（见 [研究 demo 与已有资料](../docs/existing-data.md)） | 固定为该项目 |

类型映射：

| 原生类型 | XMemory 类型 |
|---|---|
| ZCode / Claude / Qoder 的 `user` | 偏好 |
| `feedback` | 经验或坑；用户纠正写成偏好 |
| `project` | 事实或决定 |
| `reference` | 事实（资料位置） |
| Qoder CLI 的常见坑 | 坑 |
| Qoder CLI 的决策 | 决定 |
| Qoder CLI 的规范 | 做法 |
| Qoder CLI 的架构、技术栈、环境 | 事实 |
| Qoder CLI 的任务摘要 | 足迹素材 |

增量：
- 记录文件/条目版本与读取覆盖；未变化且已完整处理的才跳过。未结清单中的活跃、部分读取或失败项仍需回补，不能仅看 mtime。
- 客户端会整体重写的聚合文件（如 Codex 的 `MEMORY.md`、QoderWork 的 `MEMORY.md`），按标题或条目定位，比对内容判断哪部分是新的，不用行号。
- 同一主张多个客户端都记了，由整理合并并挂多个来源；采集保留来源链，不能用文件数冒充独立证据。

## 会话（补缺口或用户点名时）

会话是证据等级最低的原件，但也是唯一有用户原话的地方。读取方式按优先顺序：

1. 宿主自带的只读历史查询；
2. 已安装的会话读取技能（例如 conversation-readers 提供的各端读取技能，按会话 ID、项目和时间段只读列出与读取）；
3. 用户提供的可靠导出。

没有可用的读取方式时说明限制，不自行解析未知数据库，不拿其他客户端的路径冒充。

| 客户端 | 常见位置 | 归属依据 |
|---|---|---|
| Codex | `~/.codex/sessions/`、`~/.codex/archived_sessions/` | 会话 cwd |
| Claude Code | `~/.claude/projects/<路径编码>/*.jsonl` | 会话 cwd |
| ZCode | `~/.zcode/cli/db/db.sqlite`（只读查询 session、message、part） | 会话 directory |
| Qoder CLI / 桌面 | `~/.qoder-cn/projects/`；桌面版应用数据目录下的 `main.sqlite` | 会话 cwd |
| WorkBuddy | `~/.workbuddy/projects/` | 会话目录 |

读取规则：
- 先列清单（会话 ID、标题、cwd、创建与更新时间），再读正文。
- 时间参数一律带时区。优先使用带时区的消息/事件字段；先确认字段含义，再换算。无时区文件名必须知道来源时区才能采用；来源更新时间不能替代事件时间。跨天摘要若缺少逐日事件依据，回原始消息或标明未能拆分的缺口；不凭会话开始时间把后续所有事件放在第一天。
- 只处理已过静默期的会话：最后活动超过配置的 `quiet_minutes`，默认 60 分钟。仍在写入的会话跳过，下次再采。
- 只读用户和助手的可见消息；需要确认执行结果时，再展开相关工具调用。
- 不读隐藏推理；不收录系统注入、技能装配内容、凭据。
- 子代理、工作流 actor 会话按其父会话归属；只在父会话缺少关键信息时读取。

## 工作区变化

在项目根内用 `git log`、`git diff` 和文件修改时间缩小候选，再读必要内容。新增、修改时间和 diff 只是线索，不能证明业务完成。

## 本地与云端各有一份的文档

足迹或主题的来源里写明各载体与主本。读取时先读主本，读不到时读副本并说明可能落后。两边一致是会变的事实，据此行动前要核实。

## 找不到原件

原件在本机找不到时说明“本机找不到这个原件（可能在别的机器上、存储没挂载或已移动）”，用记忆中的摘要回答并注明截至时间。不猜它在哪，也不因此认定原结论错误。只靠找不到的原件支撑、又会影响行动的结论，标为待确认。
