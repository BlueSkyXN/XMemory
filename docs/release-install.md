# XMemory 1.3.1 安装包

## 三种包

- `XMemory-1.3.1.zip`：ZCode、Claude Code、Codex 三端市场完整包。三份市场清单都列出两个插件：XMemory 1.3.1（记忆，五个技能）与 Conversation Readers 0.1.2（各客户端会话只读读取，五个技能）。解压保留整个目录结构。
- `XMemory-1.3.1-skills.zip`：XMemory 五个自包含技能。
- `ConversationReaders-0.1.2-skills.zip`：Conversation Readers 五个自包含技能，各带只读 Python 脚本。

技能包按客户端方式安装 `skills/` 下完整目录，不假定整个 ZIP 可一键导入。

两个插件各自独立安装。XMemory 不依赖读取插件也能工作；需要按会话采集（而不只是读取各客户端的原生记忆）时，再安装 Conversation Readers，它需要 Python 3.11+。

插件代码、技能、市场目录和记忆数据彼此独立。同一台机器上的客户端共用该用户的记忆根，默认位置为 `~/.agents/memory/`；多台机器通过用户选择的同步方式保持内容一致。库内分常驻层（`USER.md`、`AWARENESS.md`、`MEMORY.md`）、主题与每日层（`topics/`、`daily/`）、足迹层（`daily/<日期>/`），项目在 `projects/<项目名>/` 下同构存放，项目名取平台项目根目录名；不在各项目另建数据根或软链接，不依赖 Git。安装不初始化个人数据、不采集历史、不修改客户端规则、不创建 Hook 或定时任务。Office Memory（此前的自有实践）后续迁入集中库并停用旧流程，本次不自动接管。

## ZCode

在“插件市场 → 添加 → 添加插件市场”粘贴解压根下的 `plugins/` 实际绝对路径。在“个人 → xmemory”安装 XMemory 1.3.1（插件 ID `xmemory@xmemory`），需要时再安装 Conversation Readers 0.1.2（`conversation-readers@xmemory`），安装后在“设置 → 插件”管理。

如果已添加源码目录的同名市场，继续刷新原市场，不重复添加解压目录。从开发期市场名 `dev-xmemory-8c7a38ae` 升级时，先移除旧市场再添加本市场。

## Claude Code

将下面的路径替换成解压根（不是 plugins/ 子目录），由用户执行：

```bash
claude plugin marketplace add /absolute/path/to/XMemory-1.3.1
claude plugin install xmemory@xmemory-claude
claude plugin install conversation-readers@xmemory-claude   # 需要按会话采集时
```

Claude 市场清单在解压根的 `.claude-plugin/marketplace.json`，相对 source 从解压根解析。

## Codex

Codex 市场清单在解压根的 `.agents/plugins/marketplace.json`，插件清单为各插件的 `.codex-plugin/plugin.json`。已核对的 CLI 0.162.1 支持以下命令，其他版本先查看实际帮助：

```bash
codex plugin marketplace add /absolute/path/to/XMemory-1.3.1
codex plugin add xmemory@xmemory-codex
codex plugin add conversation-readers@xmemory-codex   # 需要按会话采集时
```

桌面端也可通过其插件目录选择该市场安装。生成清单不是已安装或已启用。

## 独立技能

完整复制或导入每个技能目录：Codex 为 `~/.agents/skills/`，Claude Code 为 `~/.claude/skills/`，ZCode 为 `~/.zcode/skills/`，Qoder IDE/CLI 为 `~/.qoder/skills/`，QoderWork 为 `~/.qoderwork/skills/`。读取技能要保留 `scripts/` 和 `references/`。已存在同名内容先核对，不直接覆盖；同一客户端不要同时启用插件和同名独立技能。

## 接入客户端、Hook、定时与首次回填

安装后不会自动生效到日常对话。需要时由用户明确要求：

1. 把读取协议合并到各客户端实际生效的全局或项目根 AGENTS.md / CLAUDE.md。完整包在 `plugins/xmemory/integrations/entry.md`，技能包在 `skills/xmemory-setup/integrations/entry.md`。项目根规则文件可另加一行“XMemory 项目：<项目名>”。
2. 首次导入各客户端已有记忆和历史会话时，按同目录的 `backfill.md` 分批执行，先在测试目录试跑。
3. 需要被动采集时，按同目录的 `hooks.md` 配置会话开始、压缩前、会话结束的提醒。
4. 需要后台采集与整理时，填好同目录的 `scheduled.md`，挂到任一客户端的定时任务上。同一时间只在一处运行，首次先在测试目录手动跑一次。

## 试用与校验

新建任务，选择 XMemory 设置，在明确指定的空测试目录初始化 demo 项目；记录“代码已改、尚未部署”的交接，预期只在当天的项目足迹目录新建一份足迹；再用调取技能只读回答部署是否完成，预期回答未验证并指出来源，不新增或修改文件。

包外附 `.zip.sha256`，包内 `SHA256SUMS` 覆盖内容文件。XMemory 载荷只有技能、文档、模板、清单和许可证；Conversation Readers 的每个技能另带只读读取脚本。开发验证、资源同步和打包脚本不进入包，不是运行依赖。原有 Office Memory 与研究 demo 均不自动迁移。
