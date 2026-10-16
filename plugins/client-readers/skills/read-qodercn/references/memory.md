# Qoder CN 原生记忆

三种布局与两套编码规则来自本机实测，不包含 QoderWork CN。

| Store | 映射 | 角色 |
|---|---|---|
| `~/.qoder-cn/projects/<编码>/memory/` | cwd 的 `[^A-Za-z0-9]` 全换为 `-`，按会话全部 cwd 比对 | MEMORY.md 为 index，其余 Markdown 为 topic |
| `~/.qoder-cn/memory/` | 用户范围 | MEMORY.md 为 index，qoderwork-daily-* 为 daily，其余为 topic |
| `~/.qoder-cn/memories/<用户ID>/projects/<编码>/<分类>/` | 只将 `/` 换为 `-`，去掉开头 `-`；中文与点号保留 | topic，frontmatter.category 取分类目录名 |

旧版 global 分类目录保留全局范围。`Qoder-Chats` 等无法从原生 cwd 或 `--project` 比对的目录保留原名，项目范围报 orphan；不套用 CLI 编码猜归属。CLI 编码可能撞名，多个候选报 ambiguous。

会话扫描告警按来源分配：CLI store 编码目录内的来源跟随该 store 及文件；其他目录与桌面库的告警保留为全局，因为旧分类归属仍使用全部会话 cwd。

旧分类的块式 `keywords` 列表、普通标量续写和任意键下一层映射按 [frontmatter 子集](output-memory.md) 读取；超出子集的键不输出值，条目的 `frontmatter_partial` 列出键名。每个旧分类仍是一个 store，`locate.summary` 先汇总所选 store 的布局与状态，再用分页逐项查看。

只读 `~/Library/Application Support/com.qodercn.app.stable/memoryMigration.sqlite`。命中 `memory_import_target_files` 的文件给出 `migrated={imported_at,unchanged}`，unchanged 比较当前内容 hash。旧版 store 给最新文件时间；不同名称的迁移前后文件不能据名称判断独立性。

`memory_migration_ledger` 的 imported/skipped/filtered 行数与目标文件数不是同一统计口径；不能按行数推定一对一迁移。读取器只标目标表可核实的信息，不解释未确认的迁移状态语义。

输出字段、索引与运行环境见 [输出契约](output-memory.md)。
