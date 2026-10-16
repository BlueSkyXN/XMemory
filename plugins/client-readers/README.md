# Client Readers

只读地读取各 AI 客户端留在本机的会话与原生记忆，五个客户端各一个技能。

Read sessions and native memory stored locally by each AI client — Codex, Claude Code, ZCode, Qoder CN, WorkBuddy.

源码版本 **0.2.1**。每个客户端一个 Skill 和自带的 `scripts/read.py`，提供四类命令：

| 命令 | 用途 |
|---|---|
| `projects` | 汇总项目候选、会话数、记忆数、别名与父子关系，供用户选择采集范围 |
| `sessions list/read/search` | 按项目、时间、标题或原生 ID 定位会话，检索正文并分页展开 |
| `memory locate/list/read/search` | 定位原生记忆，查看角色、归属和来源关系，分段读取或按关键词检索 |
| `doctor` | 检查数据根、当前 Python 与已有 zstd 后端；`--candidates` 另列已有解释器 |

读取结果可用于审阅、报告或工作接续；需要保存为记忆时，再按用户选定的记忆流程处理。

| 客户端 | Skill | 会话来源 | 原生记忆位置 |
|---|---|---|---|
| Codex | `read-codex` | rollout JSONL / JSONL.zst，原生状态索引辅助标题 | `~/.codex/memories/`、`memories_v2/`、`automations/<id>/memory.md` |
| Claude Code | `read-claude` | 项目 JSONL、可选子代理记录 | `~/.claude/projects/<编码目录>/memory/` |
| ZCode | `read-zcode` | SQLite session / message / part | `~/.zcode/cli/memories/projects/<slug>-<hash16>/memory/` |
| Qoder CN | `read-qodercn` | 项目 JSONL、桌面 main.sqlite | `~/.qoder-cn/projects/<编码>/memory/`、`memory/`、`memories/<用户ID>/projects/<编码>/<分类>/` 及旧 global 分类 |
| WorkBuddy | `read-workbuddy` | 项目 JSONL 的 message 与工具事件 | `<cwd>/.workbuddy/memory/`、`~/.workbuddy/MEMORY.md`、`memory/`、`user-*/` |

路径简写均相对同一行已列出的客户端根。各技能的 `references/memory.md` 说明布局、角色与归属规则。`memory`、`projects`、`doctor` 使用主目录下的默认客户端数据根；异地会话用 `sessions --root PATH` 指定。

Codex 压缩读取依次使用已有的 `compression.zstd`、`backports.zstd`、`zstandard`、PATH 上的 zstd 或常见安装前缀中的 zstd；全部缺失时按根目录汇总未读数量。已有 Python 后端时普通命令省去外部探测，`doctor` 仍列出全部可用后端。脚本以 UTF-8 输出 JSON 或 Markdown。

## 使用与安装边界

从 Conversation Readers 升级时，先通过客户端卸载 `conversation-readers`，保留需要的插件数据，再安装 `client-readers@xmemory-marketplace`。独立技能安装需移除旧的五个 `read-*-conversations` 目录，避免旧入口继续参与技能选择；记忆库和客户端原始会话沿用现有位置。

需要 **Python 3.9+**（使用用户自己的 `python3`），只用标准库。脚本位于每个 Skill 的 `scripts/read.py`，无需安装统一 CLI、修改 PATH、配置 MCP 或启动服务。

本插件与 XMemory 列在同一套三端市场中，各自独立安装。当前源码在 ZCode、Claude Code 和 Codex 中统一使用 `client-readers@xmemory-marketplace`；已发布 v1.5.3 完整包仍使用各客户端的旧市场名，以包内清单为准。旧市场安装需通过客户端迁移注册与安装，保留数据和启用状态，不能只改缓存目录名。插件带 Agent Plugins、Codex、Claude Code 和 ZCode 四份清单。XMemory 通过本插件读取会话、原生记忆或生成项目候选，两者各自安装；本插件也可单独用于审阅或工作接续。

不用插件时，按目标客户端的技能安装方式复制完整技能目录（技能包为 `ClientReaders-<版本>-skills.zip`），保留 `scripts/` 和 `references/`；不要只复制 `SKILL.md`。同名技能已存在时先核对，再选择替换或保留。

## 能做什么

- 按项目、标题／ID、时间筛选会话；检索可见正文并返回命中片段。
- 定位五端原生记忆，查看文件角色、索引、同会话、重复与迁移关系；项目归属未定时保留候选与缺口。
- 保留对话、消息、父消息、工具调用和回源定位信息；缺失字段保持 null。
- 正文与工具记录分开，按需展开工具记录；隐藏推理不进入返回内容。
- 输出 JSON 或 Markdown；明确分页、截断、读取上限、不可达来源和活文件变化。
- 使用原生数据只读访问，不改写客户端对话，不自动生成摘要或写入记忆库。

原生记录是事实材料，AI 在读取后判断与归纳。关键词搜索不是向量语义搜索；导出的单页也不是完整会话。各 Skill 的 `references/output-sessions.md` 说明分页与活文件边界。

## 维护与验证

源码仓库的 `tools/client_readers/` 维护公共实现，`tools/sync_client_readers.py --apply` 同步五份自包含脚本；修改维护源后再同步，不独立修改分发副本。各技能可以单独复制运行，无运行期跨目录依赖。

在源码仓库运行：

```bash
python3 -B tools/sync_client_readers.py --apply
python3 -B tools/build_client_readers.py --check
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
python3 -B tools/build_client_readers.py
```

已有归档拒绝覆盖；需要重建时指定新的 `--output`。验证结果和未覆盖部分见 [验证记录](docs/validation.md)。
