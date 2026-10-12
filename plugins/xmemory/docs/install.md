# 安装与首次使用

当前版本 **1.4.0**，文件格式 `xmemory/v1.4`。安装的是技能和运行时，不是记忆数据：安装本身不建库、不读取会话、不修改客户端规则。

运行时需要 Python 3.11+ 和 git。

## 三种清单

| 客户端 | 插件清单 | 市场清单与根 |
|---|---|---|
| ZCode | 插件内 `.zcode-plugin/plugin.json` | `plugins/marketplace.json`；市场根为 `plugins/` |
| Claude Code | 插件内 `.claude-plugin/plugin.json` | 仓库根 `.claude-plugin/marketplace.json`；市场根为仓库根 |
| Codex | 插件内 `.codex-plugin/plugin.json` | 仓库根 `.agents/plugins/marketplace.json`；市场根为仓库根 |

三个市场都列出 XMemory 与 Conversation Readers 两个插件。XMemory 有八个技能，共用 `xmemory` 技能里的同一个运行时；它已内置会话读取运行时（含 `session` 命令），不依赖 Conversation Readers。

## ZCode

1. 打开“插件市场 → 添加 → 添加插件市场”，选择源码仓库的 `plugins/` 绝对路径（分发包选择解压根下的 `plugins/`）。
2. 在“个人 → xmemory”安装 XMemory（插件 ID `xmemory@xmemory`）。
3. 已添加过本市场时，刷新市场并更新插件即可，不重复添加。

## Claude Code

由用户执行，路径替换为源码仓库或完整分发包解压后的根：

```bash
claude plugin marketplace add /absolute/path/to/XMemory
claude plugin install xmemory@xmemory-claude
```

## Codex

```bash
codex plugin marketplace add /absolute/path/to/XMemory
codex plugin add xmemory@xmemory-codex
```

其他版本先查看实际的 `codex plugin --help`。市场发现、安装和启用是不同状态。

## 独立技能

`XMemory-<版本>-skills.zip` 内是完整的 `skills/` 目录（八个技能）。**八个技能要一起复制**到客户端的用户级技能目录，例如 Codex 的 `~/.agents/skills/`、Claude Code 的 `~/.claude/skills/`、ZCode 的 `~/.zcode/skills/`：任务技能通过相对路径调用 `xmemory` 技能里的运行时。同一客户端不要同时启用插件和同名独立技能。

## 首次使用

以下命令中 `S` 指 `skills/xmemory/scripts/xmemory.py`。日常使用时不必手敲，对代理说出意图即可，对应技能会调用这些命令。

```bash
python3 "$S" init --timezone Asia/Shanghai          # 在 ~/.agents/memory 建库；已有其他内容的目录会被拒绝
python3 "$S" project add <项目名> --path <项目根>     # 只有登记的项目会生成提取任务
python3 "$S" import office-memory --project <项目名> --path <项目根>/.agents   # 可选
python3 "$S" scan                                   # 默认最近 7 天，--days N 可改
python3 "$S" import codex
python3 "$S" status
```

之后在任一客户端对代理说“更新记忆”，`xmemory-run` 技能会循环 `next` → 提取 → `submit`，再对有新输入的范围做整合。回填更早的历史时，把 `config.toml` 的 `backfill_days` 调大或用 `scan --days N`，再重复这一轮。

## 告知各客户端

```bash
python3 "$S" notice
```

把输出的段落合并进各客户端的用户级规则文件（例如 `~/.codex/AGENTS.md`、`~/.claude/CLAUDE.md`、`~/.zcode/AGENTS.md`）。合并前先读现有内容，不覆盖已有规则，不重复添加。之后由 AI 自己决定何时查阅。

## 定时运行

XMemory 没有后台进程。需要定期运行时，把 `skills/xmemory-setup/templates/automation-prompt.md` 填好客户端标识和每轮任务上限，挂到客户端自己的自动化功能上（如 Codex 自动化）。

Codex 在受限沙箱中运行时，可能无法写入 `~/.agents/memory`。可以把自动化的工作目录设为记忆根，或按 Codex 当前版本的配置授予该目录写权限；首次运行后用 `status` 和 `check` 确认确实写入。

## 从 1.x 升级

1.x 的库（`xmemory/v1`）与 1.4 不兼容，运行时不会接管它。把旧目录移走或归档后再 `init`；需要保留的 Office Memory 用 `import office-memory` 从原件重新转录。
