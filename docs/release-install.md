# XMemory 1.5.3 安装包

本文对应 1.5.3。下列包可由当前源码构建；正式安装包与校验文件见 [Releases](https://github.com/BlueSkyXN/XMemory/releases)。

市场名称统一为 `xmemory-marketplace` 的改动目前仅在源码中，尚未发布；以下命令用于当前源码构建的包。已发布的 v1.5.3 包仍使用 ZCode `xmemory`、Claude Code `xmemory-claude`、Codex `xmemory-codex`，以包内市场清单的 `name` 为准。

| 包 | 内容 |
|---|---|
| `XMemory-1.5.3.zip` | 三端完整市场，包含 XMemory 1.5.3 与独立 Conversation Readers 0.1.5 |
| `XMemory-1.5.3-skills.zip` | 八个 XMemory 技能、模板和只读 status；不含读取器 |
| `ConversationReaders-0.1.5-skills.zip` | 五端自包含读取技能，可选安装 |

Python 3.9+，无额外依赖。完整包解压后，ZCode 添加 `plugins/` 为市场根；Claude Code 与 Codex 添加解压根。三端都安装 `xmemory@xmemory-marketplace`；需要会话读取时另装 `conversation-readers@xmemory-marketplace`。

```bash
claude plugin marketplace add /absolute/path/to/XMemory-1.5.3
claude plugin install xmemory@xmemory-marketplace
```

```bash
codex plugin marketplace add /absolute/path/to/XMemory-1.5.3
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
