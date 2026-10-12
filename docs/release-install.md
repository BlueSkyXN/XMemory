# XMemory 1.5.1 安装包

本文对应 1.5.1 开发构建，尚未发布；已发布稳定版见 [1.5.0 Release](https://github.com/BlueSkyXN/XMemory/releases/tag/v1.5.0)。

| 包 | 内容 |
|---|---|
| `XMemory-1.5.1.zip` | 三端完整市场，包含 XMemory 1.5.1 与独立 Conversation Readers 0.1.4 |
| `XMemory-1.5.1-skills.zip` | 八个 XMemory 技能、模板和只读 status；不含读取器 |
| `ConversationReaders-0.1.4-skills.zip` | 五端自包含读取技能，可选安装 |

Python 3.9+，无额外依赖。完整包解压后，ZCode 添加 `plugins/` 为市场根；Claude Code 与 Codex 添加解压根。分别安装 `xmemory@xmemory`、`xmemory@xmemory-claude` 或 `xmemory@xmemory-codex`。

```bash
claude plugin marketplace add /absolute/path/to/XMemory-1.5.1
claude plugin install xmemory@xmemory-claude
```

```bash
codex plugin marketplace add /absolute/path/to/XMemory-1.5.1
codex plugin add xmemory@xmemory-codex
```

独立技能包将八个目录一起复制到客户端的技能目录，保持相对结构；同一客户端不要同时启用同名插件技能与独立技能。

首次让代理按 `xmemory-setup` 创建 `xmemory/v1.5` 库、选择来源，然后用 `xmemory-run` 更新记忆。唯一程序是：

```bash
python3 <技能目录>/xmemory/scripts/xmemory.py --root <记忆根> status
```

来源默认关闭；读取器另装可选。安装不触发采集或建库。旧 1.4 库保留，用户确认新目录或归档后再重建，不直接改格式名。
