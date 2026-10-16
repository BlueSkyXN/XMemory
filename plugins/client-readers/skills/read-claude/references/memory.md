# Claude Code 原生记忆

布局与目录编码依据本机实测；超长路径截断或 hash 规则尚未核实，无法按已知编码解释时标 `unsupported`。

- store：`~/.claude/projects/<编码目录>/memory/`，项目范围。`MEMORY.md` 为 `index`，其他 Markdown 为 `topic`。
- 编码将 cwd 中每个 `[^A-Za-z0-9]` 字符替换为 `-`；编码有损，中文目录可能撞名。
- 核对该目录所有会话实际出现的全部 cwd，不能只看第一条；恰一条编码吻合才用 `encoded_cwd`。多个吻合报 `ambiguous` 并列全部 candidates，不自动选择。
- 记忆命令只扫描有 memory/ 的编码目录；指定单文件或 store 时只扫描目标目录，其余文件仍参与重复检查。会话扫描告警跟随该 store 及文件；projects 扫描全部会话，并将告警归到来源涉及的项目。
- 没有会话时可用 `--project PATH` 正向确认，依据为 `project_arg`；否则为 `orphan`。没有 memory 的会话目录碰撞仍会在 `projects` 标记。
- `metadata.originSessionId` 与旧式顶层 `originSessionId` 都作为会话线索，不作为已核实身份。

分页、索引、分段和运行环境见 [输出契约](output-memory.md)。本技能只对应 Claude Code，不读取 Claude 桌面应用。
