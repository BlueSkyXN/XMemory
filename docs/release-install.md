# XMemory 1.5.3 安装包

本文对应 1.5.3。下列包可由当前源码构建；正式安装包与校验文件见 [Releases](https://github.com/BlueSkyXN/XMemory/releases)。

| 包 | 内容 |
|---|---|
| `XMemory-1.5.3.zip` | 三端完整市场，包含 XMemory 1.5.3 与独立 Conversation Readers 0.1.5 |
| `XMemory-1.5.3-skills.zip` | 八个 XMemory 技能、模板和只读 status；不含读取器 |
| `ConversationReaders-0.1.5-skills.zip` | 五端自包含读取技能，可选安装 |

Python 3.9+，无额外依赖。完整包解压后，ZCode 添加 `plugins/` 为市场根；Claude Code 与 Codex 添加解压根。分别安装 `xmemory@xmemory`、`xmemory@xmemory-claude` 或 `xmemory@xmemory-codex`。

```bash
claude plugin marketplace add /absolute/path/to/XMemory-1.5.3
claude plugin install xmemory@xmemory-claude
```

```bash
codex plugin marketplace add /absolute/path/to/XMemory-1.5.3
codex plugin add xmemory@xmemory-codex
```

独立技能包将八个目录一起复制到客户端的技能目录，保持相对结构；同一客户端不要同时启用同名插件技能与独立技能。

首次让代理按 `xmemory-setup` 创建 `xmemory/v1.5` 库、选择来源，然后用 `xmemory-run` 更新记忆。唯一程序是：

```bash
python3 <技能目录>/xmemory/scripts/xmemory.py --root <记忆根> status
```

来源默认关闭；读取器另装可选。安装不触发采集或建库。旧 1.4 库保留，用户确认新目录或归档后再重建，不直接改格式名。

客户端原生记忆继续使用和维护，XMemory 提供跨客户端补充。升级已有告知时保留原生入口，并带上新版联合查阅及会话排除规则。
