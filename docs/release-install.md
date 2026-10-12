# XMemory 1.4.0 安装包

## 三种包

- `XMemory-1.4.0.zip`：ZCode、Claude Code、Codex 三端市场完整包。三份市场清单都列出两个插件：XMemory 1.4.0（一个运行时 + 八个技能）与 Conversation Readers（各客户端会话只读读取）。解压保留整个目录结构。
- `XMemory-1.4.0-skills.zip`：XMemory 的八个技能（`skills/` 整个目录，运行时在 `skills/xmemory/scripts/`）。
- `ConversationReaders-<版本>-skills.zip`：Conversation Readers 五个自包含技能。

运行时需要 Python 3.9+ 和 git（macOS 自带的 `python3` 即可）。安装不建库、不读取会话、不修改客户端规则。

## ZCode

在“插件市场 → 添加 → 添加插件市场”粘贴解压根下的 `plugins/` 绝对路径，在“个人 → xmemory”安装 XMemory（`xmemory@xmemory`）。已添加过源码目录的同名市场时，刷新原市场并更新插件，不重复添加。

## Claude Code

路径替换为解压根（不是 `plugins/` 子目录），由用户执行：

```bash
claude plugin marketplace add /absolute/path/to/XMemory-1.4.0
claude plugin install xmemory@xmemory-claude
```

## Codex

```bash
codex plugin marketplace add /absolute/path/to/XMemory-1.4.0
codex plugin add xmemory@xmemory-codex
```

其他版本先查看实际的 `codex plugin --help`。

## 独立技能

把 `skills/` 下八个技能目录一起复制到客户端的用户级技能目录（Codex `~/.agents/skills/`、Claude Code `~/.claude/skills/`、ZCode `~/.zcode/skills/`）；任务技能通过相对路径调用 `xmemory` 技能里的运行时，缺了它就不能用。同一客户端不要同时启用插件和同名独立技能。

## 首次使用

见插件内 `docs/install.md`：`init` 建库 → `project add` 登记项目 → `scan`、`import codex` → 在客户端里让代理运行管线 → `notice` 生成告知段落，由用户决定合并进哪些客户端的用户级规则文件。

## 从 1.x 升级

1.x 库（`xmemory/v1`）不兼容，运行时不会接管。先把旧目录移走或归档，再 `init`；Office Memory 用 `import office-memory` 从原件重新转录。
