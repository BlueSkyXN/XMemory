# XMemory 1.5.4 安装包

本版包含 XMemory 1.5.4 与 Conversation Readers 0.1.6，文件格式仍为 `xmemory/v1.5`。安装包与校验文件见 [Releases](https://github.com/BlueSkyXN/XMemory/releases)。

本版三个客户端的市场名称统一为 `xmemory-marketplace`，以下命令适用于本版安装包。旧 v1.5.3 包仍使用 ZCode `xmemory`、Claude Code `xmemory-claude`、Codex `xmemory-codex`，以包内市场清单的 `name` 为准。

| 包 | 内容 |
|---|---|
| `XMemory-1.5.4.zip` | 三端完整市场，包含 XMemory 1.5.4 与独立 Conversation Readers 0.1.6 |
| `XMemory-1.5.4-skills.zip` | 八个 XMemory 技能、模板和只读 status；不含读取器 |
| `ConversationReaders-0.1.6-skills.zip` | 五端自包含读取技能，可选安装 |

Python 3.9+，无额外依赖。完整包解压后，ZCode 添加 `plugins/` 为市场根；Claude Code 与 Codex 添加解压根。三端都安装 `xmemory@xmemory-marketplace`；需要会话读取时另装 `conversation-readers@xmemory-marketplace`。

```bash
claude plugin marketplace add /absolute/path/to/XMemory-1.5.4
claude plugin install xmemory@xmemory-marketplace
```

```bash
codex plugin marketplace add /absolute/path/to/XMemory-1.5.4
codex plugin add xmemory@xmemory-marketplace
```

独立技能包将八个目录一起复制到客户端的技能目录，保持相对结构；同一客户端不要同时启用同名插件技能与独立技能。

旧市场安装不会因源码改名而自动迁移。先记录启用状态并保留配置、插件数据与记忆库，再通过客户端移除旧插件及旧市场、注册新市场并恢复原有安装；不要直接覆盖缓存。完整市场包内的 `plugins/xmemory/docs/install.md` 说明迁移边界。

首次让代理按 `xmemory-setup` 创建 `xmemory/v1.5` 库、选择来源，然后用 `xmemory-run` 更新记忆。唯一程序是：

```bash
python3 <技能目录>/xmemory/scripts/xmemory.py --root <记忆根> status
```

来源默认关闭；读取器另装可选。安装不触发采集或建库。旧 1.4 库保留，用户确认新目录或归档后再重建，不直接改格式名。

客户端原生记忆继续使用和维护，XMemory 提供跨客户端补充。升级已有告知时保留原生入口，并带上新版联合查阅及会话排除规则。

1.5.x 库无需转换格式。1.5.4 新增可选的 `project_status: "unresolved"` 与身份检查提示；1.5.3 的 status 仍能读取新库，但不会识别未定归属，会沿旧语义把空项目列表算作 personal。安装不会自动重写已有记录、转换 Skysight 内容或创建定时任务；需要这些操作时按用户选择另行执行。

启用 Skysight 后，日常更新直接核对来源窗口与日总结覆盖说明，即使没有新记录或 status 提示也需检查。活动只留在日总结，不进入主题、意识或画像；原件通常约 7 天滚动清除，保留期不作固定保证。实际整理质量与客户端调度需要单独验收。
