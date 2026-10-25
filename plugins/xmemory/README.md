# XMemory 1.8.0

由 Agent 维护跨客户端长期记忆，正式内容全部为 Markdown，固定保存在用户 home 下的 `.agents/memory/`。模型和文件工具由宿主提供，Python 只是可选检查工具。

| Skill | 职责 |
|---|---|
| [xmemory-update](skills/xmemory-update/SKILL.md) | 采集选定来源并整理，也可只执行指定阶段 |
| [xmemory-recall](skills/xmemory-recall/SKILL.md) | 按需只读查阅 |
| [xmemory-note](skills/xmemory-note/SKILL.md) | 记住当前对话的要求、结论或更正 |

入口 `memory_summary.md` 提供少量要点和导航，`MEMORY.md` 保存当前有效知识，`notes/YYYY-MM/` 保留有用工作与变化。没有新增价值可以不写文件。

先按 [安装说明](docs/install.md)接入宿主，再说“整理这个项目的选定材料”或“查上次的决定”。客户端原生记忆可作为只读输入，Client Readers 按需要独立安装。

[使用指南](docs/usage.md) · [设计说明](docs/design.md) · [内容约定](skills/xmemory/references/format.md) · [可选 status](skills/xmemory/references/status.md)

本版采用三层 Markdown，旧对象库不会自动迁移或覆盖。实际验证范围见 [仓库验证记录](https://github.com/BlueSkyXN/XMemory/blob/main/docs/validation.md)。

许可证：[GNU GPL v3](LICENSE)。
