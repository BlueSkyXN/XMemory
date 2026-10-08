# XMemory

**用五个技能把记忆做清楚：设置、记录、采集、整理、调取。**

当前版本 **1.1.0**：用户级 `~/.agents/memory/` 集中库分为记忆层和接续层，提供写进 AGENTS.md / CLAUDE.md 的读取协议和可挂到任一客户端的定时提示词；保留 Claude Code、ZCode、Codex 三端插件与市场包装，文件格式名为 `xmemory/v1`。`local/xmemory/` 只是研究 demo，不属于正式产品版本线。

XMemory 是纯技能、文件式记忆插件。现有 AI 客户端负责执行，Markdown 保存结果，TOML 登记项目和来源。不依赖 Git，不带运行期独立工具、MCP、数据库、Hook 程序、后台任务、锁或额外模型服务。

## 五技能与两层文件

| 技能 | 职责 | 写入 |
|---|---|---|
| `xmemory-setup` 设置 | 数据根、项目身份、只读来源、读取协议与定时提示词 | 配置与入口 |
| `xmemory-record` 记录 | 当前对话中的偏好、纠正、决定和交接 | 只新建文件 |
| `xmemory-collect` 采集 | 登记来源或点名资料中的变化 | 只新建事件文件 |
| `xmemory-curate` 整理 | 近况、当日文件、积压、入口、经验、更正与忘记 | 除配置外唯一修改已有文件；定时运行只做记账类改动 |
| `xmemory-recall` 调取 | 按读取协议检索与工作接续 | 不写 |

- **记忆层**：入口 `MEMORY.md`（常驻条目和索引）、记忆 `notes/`（偏好、纠正、决定及理由、坑、经验）。
- **接续层**：近况 `CURRENT.md`，以及 `records/` 下的事件文件（一件事一份、只新建）和当日文件（每次整理追加一节，也用来判断哪些事件已处理）。
- **辅助**：`BACKLOG.md` 积压、`WITHDRAWN.md` 撤回墓碑、`config.toml` 配置。

同一台机器上的客户端共用该用户的记忆根。多台机器使用**同一逻辑记忆库**，各机器默认位置为 **`~/.agents/memory/`**，通过用户选择的同步方式保持内容一致。项目记忆位于库内 `projects/<id>/`，不分散存到各工作区，也不需要项目软链接。项目身份优先看项目根 AGENTS.md 中的“XMemory 项目 ID”，其次是 Git 远程地址和候选路径。相同路径不代表已完成同步。

整理先保存结果并回读确认，最后在当日文件登记已处理事件；失败后停止当前范围，重试只补缺失步骤。未处理事件不按年龄排除，近 30 天只决定正文阅读优先级。定时整理可以更新接续状态、处理登记和已声明关系的状态，不自行合并、改写或删除长期记忆正文；旧未完成项和待确认建议重写后保留或说明去向。

Office Memory 后续迁入集中库并停用旧流程，迁移尚未实施前保持只读接入。完整对照见 [需求覆盖](plugins/xmemory/docs/requirements.md)。

## 三端插件与市场

```text
.claude-plugin/marketplace.json       Claude 市场，根为本仓库
.agents/plugins/marketplace.json      Codex 市场，根为本仓库
plugins/
├── marketplace.json                 ZCode 市场，根为 plugins/
└── xmemory/
    ├── plugin.json                  Codex/Agent Plugins 清单
    ├── .claude-plugin/plugin.json    Claude 清单
    ├── .zcode-plugin/plugin.json     ZCode 清单
    ├── skills/                      五个自包含技能
    ├── references/                  共用文档源
    ├── templates/                   共用模板源
    ├── integrations/                读取协议与定时提示词
    ├── examples/                    虚构闭环示例
    └── docs/                        设计、来源、安装、验收
```

每个正式技能的配套文件均在其自身目录内，没有跨目录资源依赖。开发工具维护静态副本一致性，不进入插件载荷。

| 客户端 | 添加的实际市场根 | 插件 ID |
|---|---|---|
| ZCode | 本仓库 `plugins/` | `xmemory@dev-xmemory-8c7a38ae` |
| Claude Code | 本仓库根 | `xmemory@xmemory-claude` |
| Codex | 本仓库根 | `xmemory@xmemory-codex` |

[三端安装说明](plugins/xmemory/docs/install.md) 包含真实命令、版本边界和接入步骤。创建市场清单不等于注册或安装。独立技能包仍可用于上述客户端和 Qoder/QoderWork；同一客户端不要同时安装重复入口。

## 设计与验证

借鉴 Devin Memory 的两层分工、AMR 的入口结构、OMPI 工作草案的字段和墓碑、Anthropic Dreams 的非破坏性整理、Office Memory 的日期记录与复查，以及 Qoder、Codex、ZCode、Claude Code 的短入口与按需读取。原生后台能力不会自动成为插件功能。

- [设计](plugins/xmemory/docs/design.md)
- [产品实现与官方规范依据](plugins/xmemory/docs/design-sources.md)
- [研究 demo 与已有资料](plugins/xmemory/docs/existing-data.md)
- [原始需求覆盖](plugins/xmemory/docs/requirements.md)
- [验收标准](plugins/xmemory/docs/acceptance.md)
- [本次验证结果](docs/validation.md)
- [分发包说明](docs/release-install.md)

## 开发检查与构建

独立的 [Conversation Readers 扩展](plugins/conversation-readers/README.md) 提供 Codex、Claude Code、ZCode、Qoder CN、WorkBuddy 各一个 `Skill + scripts`，用于对话列表、检索、按 ID 读取和分页展开。它需要 Python 3.11+，独立检查与打包，不自动写入记忆，也未加入现有 XMemory 市场。下述命令仍针对原记忆插件；扩展命令见其说明。

Python 3.11+ 仅供维护仓库使用，不是插件运行依赖。

```bash
python3 -B tools/sync_skill_resources.py --apply
python3 -B tools/check_package.py
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
python3 -B tools/build_release.py
```

修改共用文档后同步静态技能资源，检查器会拒绝漂移。构建输出三端完整包、五技能包和 SHA-256；已有同名归档拒绝覆盖，可指定新 `--output`。`tools/`、`tests/`、研究 demo 和个人资料不进入包。

GitHub Actions 在 PR、`main` 更新和手动触发时，使用 Ubuntu 与 Python 3.11 运行包装检查、全部单元测试和临时目录构建。自动检查不执行真实客户端安装、Agent 行为场景或跨设备同步验收。

## 边界

没有程序级锁、事务、跨设备同步或组织权限；靠“采集只新建、整理单点修改、写前确认、当日文件记账”降低风险。原生来源与现有 Office Memory 只读；不自动采集完整历史或改写业务 Skill。可追溯摘要不等于防篡改审计，记忆增多不保证模型更准确。

许可证：[GNU GPL v3](LICENSE)。
