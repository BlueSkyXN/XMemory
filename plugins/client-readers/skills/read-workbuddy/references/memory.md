# WorkBuddy 原生记忆

布局来自本机实测；人设文件由谁写入及是否随使用更新尚未核实。

- 工作区 `<cwd>/.workbuddy/memory/` 从会话 cwd 和 `--project` 发现；`MEMORY.md` 为 `consolidated`，`YYYY-MM-DD.md` 为 `daily`。无中央目录索引，不只按浅层目录搜索。
- 用户级 `~/.workbuddy/MEMORY.md` 与 `~/.workbuddy/memory/<UUID>_memory.md` 为 `consolidated`；`*.bak` 为 `backup`，默认不读正文。
- 人设 `~/.workbuddy/user-*/`：`USER.md` 为 `profile`，`IDENTITY.md`、`SOUL.md` 为 `persona`，`MEMORY.md` 为 `consolidated`。
- 同 `(st_dev,st_ino)` 的工作区记忆只列一次，其他大小写或 symlink 写法放进 aliases。`<cwd>/.workbuddy` 解析后等于用户数据根时只列用户级 store。不同目录不自动合并。
- 用户与人设的 MEMORY.md 内容可能相同；按原始字节 SHA256 互标 `duplicate_of`，不自动删除或选胜。
- 空的 `app/memory/` 不列；日志、连接器、workspace-state.json 和用户状态文件不是记忆。

分页、备份和只读边界见 [输出契约](output-memory.md)。
