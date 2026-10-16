# ZCode 原生记忆

已核对 ZCode 3.14.3 / CLI 0.16.9 的布局与 `project-root.ts` 映射；identity 分支有源码和合成测试，本机未见真实样本。新版本未知结构保留告警。

- 数据根 `~/.zcode/cli`。`ZCODE_DATA_BASE_DIR` 设置时提示核对，不隐式迁移来源。
- store：`memories/projects/<slug>-<hash16>/memory/`，项目范围。`MEMORY.md` 为 `index`，其他 Markdown 为 `topic`。
- 从只读 SQLite `db/db.sqlite` 的 `session.directory`、`workspace_id` 正向计算并比对。identity 去空白后非空时 key=identity、slug=`project`；否则 key=字面绝对路径（Windows 转小写），slug=basename 小写后将 `[^a-z0-9._-]+` 换成 `-`，去首尾 `-`，截断 48 字符，空则 `project`。hash 为 SHA256 前 16 位。
- 路径归一化不跟随 symlink。不同写法产生的不同 store 保留，项目总览按 inode 报告别名。多个项目命中同一 store 时列候选，不自动归属。
- 无会话项目可用 `memory locate --project PATH` 正向确认。孤儿保留 `orphan`，`near` 按同 slug 或正规 hash 前缀给出疑似正规目录；通用 slug `project` 只按 hash 前缀匹配。near 不能当成归属证明。
- `metadata.originSessionId` 只给原生会话线索；主题可能经多会话修改，不证明全文来自 origin。索引同时识别 Markdown 链接和 `[[名称]]`。
- `.zcode/db.sqlite`、`cli/db/sqlite.sqlite`、`v2/tasks-index.sqlite` 与 `cli/rollout/model-io-*` 是已知的非记忆路径，不能代替本客户端原生记忆。

分页、角色、备份、只读范围与运行环境见 [输出契约](output-memory.md)。
