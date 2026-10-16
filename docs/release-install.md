# XMemory 1.6.1 安装与升级

## 第一步：先卸载 conversation-readers

从旧读取器升级时，先记录插件 ID、启用状态和需要保留的插件数据，再通过客户端卸载 `conversation-readers`。下例使用统一市场名；旧市场安装请替换为实际 ID。

```bash
claude plugin uninstall conversation-readers@xmemory-marketplace --keep-data
codex plugin remove conversation-readers@xmemory-marketplace
```

ZCode 在插件管理中卸载 Conversation Readers。独立技能安装需移除旧的五个 `read-*-conversations` 目录，再复制新技能，避免旧入口继续被发现。XMemory 记忆库和客户端原始数据沿用现有位置。

## 下载与安装

本版包含 XMemory 1.6.1 与 Client Readers 0.2.1，文件格式仍为 `xmemory/v1.5`。安装包与对应 `.zip.sha256` 见 [Releases](https://github.com/BlueSkyXN/XMemory/releases)。下载后先按校验文件核对 SHA256，再解压完整目录。

本版三个客户端的市场名称统一为 `xmemory-marketplace`，以下命令适用于本版安装包。旧 v1.5.3 包仍使用 ZCode `xmemory`、Claude Code `xmemory-claude`、Codex `xmemory-codex`，以包内市场清单的 `name` 为准。

| 包 | 内容 |
|---|---|
| `XMemory-1.6.1.zip` | 三端完整市场，包含 XMemory 1.6.1 与独立 Client Readers 0.2.1 |
| `XMemory-1.6.1-skills.zip` | 八个 XMemory 技能、模板和只读 status；不含读取器 |
| `ClientReaders-0.2.1-skills.zip` | 五端自包含读取技能，可选安装 |

Python 3.9+，无额外依赖。完整包解压后，ZCode 添加 `plugins/` 为市场根；Claude Code 与 Codex 添加解压根。三端都安装 `xmemory@xmemory-marketplace`；需要读取会话、原生记忆或生成项目候选时另装 `client-readers@xmemory-marketplace`。

```bash
claude plugin marketplace add /absolute/path/to/XMemory-1.6.1
claude plugin install xmemory@xmemory-marketplace
claude plugin install client-readers@xmemory-marketplace
```

```bash
codex plugin marketplace add /absolute/path/to/XMemory-1.6.1
codex plugin add xmemory@xmemory-marketplace
codex plugin add client-readers@xmemory-marketplace
```

独立技能包将八个目录一起复制到客户端的技能目录，保持相对结构；同一客户端不要同时启用同名插件技能与独立技能。

安装后确认 XMemory 为 1.6.1、Client Readers 为 0.2.1，旧 conversation-readers 已移除，并在新会话确认八个 XMemory 技能与所需的 `read-<client>` 技能可用。读取器的 `doctor` 可检查当前 Python 和已有 zstd 后端；缺失后端时根据输出选择处理方式。

旧市场安装不会因源码改名而自动迁移。先记录启用状态并保留配置、插件数据与记忆库，再通过客户端移除旧插件及旧市场、注册新市场并恢复原有安装；不要直接覆盖缓存。完整市场包内的 `plugins/xmemory/docs/install.md` 说明迁移边界。

首次让代理按 `xmemory-setup` 创建 `xmemory/v1.5` 库、选择来源，然后用 `xmemory-run` 更新记忆。唯一程序是：

```bash
python3 <技能目录>/xmemory/scripts/xmemory.py --root <记忆根> status
```

来源默认关闭；读取器另装可选。安装不触发采集或建库。旧 1.4 库保留，用户确认新目录或归档后再重建，不直接改格式名。

客户端原生记忆继续使用和维护，XMemory 提供跨客户端补充。升级已有告知时保留原生入口，并带上新版联合查阅及会话排除规则。

1.5.x 库无需转换格式。1.5.4 新增可选的 `project_status: "unresolved"` 与身份检查提示；1.5.3 的 status 仍能读取新库，但不会识别未定归属，会沿旧语义把空项目列表算作 personal。安装不会自动重写已有记录、转换 Skysight 内容或创建定时任务；需要这些操作时按用户选择另行执行。

启用 Skysight 后，日常更新直接核对来源窗口与日总结覆盖说明，即使没有新记录或 status 提示也需检查。活动只留在日总结，不进入主题、意识或画像；原件通常约 7 天滚动清除，保留期不作固定保证。实际整理质量与客户端调度需要单独验收。
