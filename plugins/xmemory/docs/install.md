# 三端插件安装与独立技能

当前版本 **1.2.0**：用户级集中记忆中心，分常驻层（画像、意识、主记忆）、主题与每日层、足迹层；提供读取协议、Hook 模板、定时提示词和首次回填提示词，文件格式名仍是 `xmemory/v1`；研究 demo 不计入正式版本线。

安装的是技能方法，不是记忆数据。安装不初始化数据根、不导入历史、不更改客户端规则、不创建 Hook 或定时任务。

## 三种清单分别维护

| 客户端 | 插件清单 | 市场清单与根 |
|---|---|---|
| ZCode | 插件内 `.zcode-plugin/plugin.json` | `plugins/marketplace.json`；市场根为 `plugins/` |
| Claude Code | 插件内 `.claude-plugin/plugin.json` | 仓库根 `.claude-plugin/marketplace.json`；市场根为仓库根 |
| Codex | 插件内 `plugin.json`，Agent Plugins schema 1.0.0 | 仓库根 `.agents/plugins/marketplace.json`；市场根为仓库根 |

三个入口指向同一个 `plugins/xmemory/`，但市场 schema 不互相冒充。每个技能都自带必要的引用资源，引用相对于实际 SKILL.md 所在目录。找不到配套文件时停止相关动作，不跳过共同规则。

## ZCode

1. 打开“插件市场 → 添加 → 添加插件市场”。
2. 选择源码仓库的 `plugins/` 绝对路径；使用分发包时，选择解压根下的 `plugins/`。
3. 在“个人 → xmemory”找到 XMemory 1.2.0 并安装。
4. 在“设置 → 插件”管理启用状态。新建任务，从插件/技能选择器选择技能。

插件 ID：`xmemory@xmemory`（市场名 `xmemory`，2026-10-10 由开发期路径名 `dev-xmemory-8c7a38ae` 改名）。更新时刷新原市场，再执行插件更新，不重复添加同名不同目录市场；从旧市场名升级时，先移除旧市场再添加本市场，不保留两份。

## Claude Code

在用户确认要安装的环境执行，下列路径必须替换为源码仓库或完整分发包解压后的真实根：

```bash
claude plugin marketplace add /absolute/path/to/XMemory
claude plugin install xmemory@xmemory-claude
```

市场名为 `xmemory-claude`。可先只做验证：

```bash
claude plugin validate /absolute/path/to/XMemory/plugins/xmemory --strict
claude plugin validate /absolute/path/to/XMemory/.claude-plugin/marketplace.json --strict
```

安装后在新会话通过技能选择器或客户端实际列出的 namespaced 命令调用。不要把这里的示例当作本次已执行安装。

## Codex

市场名为 `xmemory-codex`。官方文档规定项目目录清单位于 `.agents/plugins/marketplace.json`，并支持显式添加市场根。本次 CLI 在未配置来源的隔离环境中没有自动列出该市场；临时配置明确指向市场根后成功识别插件。因此不依赖隐式发现，建议按下面步骤添加市场，实际安装由用户操作。

本次核对的 Codex CLI 0.160.0 提供：

```bash
codex plugin marketplace add /absolute/path/to/XMemory
codex plugin add xmemory@xmemory-codex
```

其他版本先查看实际 `codex plugin --help`；桌面端按插件目录中的市场入口安装。市场发现、插件安装和启用是不同状态，不能只看文件存在。

本插件没有联网工具或认证配置。市场中的 `authentication = "ON_INSTALL"` 是官方示例要求的目录策略字段，不表示 XMemory 增加了登录或外部 API 依赖。

## 自包含技能包

`XMemory-<版本>-skills.zip` 是五技能分发包，不是所有客户端都支持的一键导入格式。解压后完整安装 `skills/` 下的技能目录，不要只复制 SKILL.md。

| 客户端 | 用户级技能目录 |
|---|---|
| Codex | `~/.agents/skills/<技能名>/` |
| Claude Code | `~/.claude/skills/<技能名>/` |
| ZCode | `~/.zcode/skills/<技能名>/` |
| Qoder IDE / CLI | `~/.qoder/skills/<技能名>/` |
| QoderWork | `~/.qoderwork/skills/<技能名>/` |

同一客户端选择插件或独立技能一种方式，避免重复。已有同名内容先核对，不覆盖用户改动。路径依据见 [设计来源](design-sources.md)；实际宿主发现和调用仍需验证，不能以规范兼容代替运行验收。

## 数据与首次试用

同一台机器上的客户端共用该用户的记忆根。多台机器使用同一逻辑记忆库，各机器默认位置为 `~/.agents/memory/`，通过用户选择的同步方式保持内容一致。项目只是库内 `projects/<项目名>/` 分区（项目名等于平台项目根目录名），不在工作区另建数据根或软链接。受限宿主无法访问用户目录时应报告权限边界，不偷偷回退到项目内保存。目录关系及原始需求覆盖见 [需求对照](requirements.md)。

已明确配置其他集中根的使用者继续按实际入口读取，不自动迁移或合并；需要变更时另行指定。Office Memory 后续迁入并停用，当前安装不执行该迁移。

新建任务，选择“XMemory 设置”：

> 在我指定的空测试目录初始化 XMemory，时区按本机填写，登记 demo-api 项目，不读取个人来源、不修改任何客户端规则。

预期只有配置（含时区）和入口。接着按 [最小闭环](../examples/walkthrough.md) 记录、整理和调取。

## 接入客户端、Hook、定时与首次回填

安装不会自动修改 AGENTS.md 或 CLAUDE.md，也不会创建 Hook 或定时任务。需要时由用户明确要求，按下面的顺序：

1. **读取协议**：把 [读取协议](../integrations/entry.md) 合并到各客户端实际生效的全局或项目根规则文件，Agent 才会在继续工作、查历史决定时按顺序读取记忆。项目根规则文件可另加一行“XMemory 项目：<项目名>”。
2. **首次回填**：按 [首次回填提示词](../integrations/backfill.md) 分批导入各客户端已有的记忆和历史会话：先设置并确认项目，再原生记忆、会话补缺口、整理、验收。
3. **被动采集（可选）**：按 [Hook 模板](../integrations/hooks.md) 在会话开始、压缩前、会话结束时提醒 Agent 读取或记录。
4. **后台运行**：按 [定时提示词](../integrations/scheduled.md) 填好范围、来源和同步命令，挂到任一客户端的定时任务上。同一时间只在一处运行；首次运行前先在测试目录手动跑一次。
