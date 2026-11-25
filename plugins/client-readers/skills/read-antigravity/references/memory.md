# Antigravity CLI 原生记忆

已核对 Antigravity CLI 1.5.16 的数据根 `~/.gemini/antigravity-cli/`，未发现原生记忆存储。

- `memory locate` 返回空 store 列表；`known_non_memory` 列出实际存在的 `brain/`、`conversations/`、`implicit/`、`annotations/`。这些是会话正文、产物与内部状态，不能代替原生记忆。
- 项目 `AGENTS.md`、`~/.gemini/config/` 下的技能和插件属于项目或宿主配置，不是本客户端的原生记忆，按普通文件读取。
- `projects` 仍可用，项目候选来自会话索引的工作区路径，见 [会话来源](sessions.md)。

分页、角色、只读范围与运行环境见 [输出契约](output-memory.md)。
