# Codex 原生记忆

规则依据开源 Codex `bb64b894fd`、桌面版 26.1007.71326 与本机只读探测；远端开关和每个会话的双写状态未取得。

| 位置 | 角色或范围 |
|---|---|
| `~/.codex/memories/`、`~/.codex/memories_v2/` | `codex-v1` / `codex-v2`，全局 store |
| `memory_summary.md` | `index`，含导航及二手画像、偏好、经验 |
| V1 `MEMORY.md`、`raw_memories.md` | `consolidated` / `raw_extract`；先 `--outline` 再分段 |
| `rollout_summaries/` | `session_summary`；头部 cwd 给文件级项目，thread_id 给会话线索，rollout_path 保留原样 |
| `extensions/ad_hoc/notes/`、`extensions/*/instructions.md` | `note` / `instructions` |
| `extensions/skysight/resources/` | `activity` |
| V1 `skills/<名称>/SKILL.md` | `skill`，官方整理产物，通常不在客户端技能清单里 |
| `~/.codex/automations/<id>/memory.md` | `automation`；同目录 automation.toml 的 cwds 给项目，多个 cwd 保留候选；名称和调度作为元数据 |
| V1 `automations/`、`local/` | 单列 `unofficial` store，Markdown 为 `process_log` |

两版都列出。V2 按设计没有 MEMORY.md、raw_memories.md、skills，不报缺失。同 thread_id 的摘要互标 `same_session_as`，不因 V2 或较新保存时间判胜；完全相同内容另标 `duplicate_of`。`.git/` 与 `.DS_Store` 跳过。

正规 V1/V2 store 的 `last_written` 是最新文件时间。仅 `memory locate` 计算 `recent_injection`：扫最近 7 天主会话头部，按用户/自动化分列实际出现的库根，无会话为 null；头部注入后的普通用户提及不计数，摘要正文提及另一套目录也不作为注入证据。它不证明双写开关。`memory list/read/search` 不扫描会话；多 cwd 自动化文件按全部候选路径参与项目筛选。

`projects` 只读每个 rollout 首行 session_meta，包括经已有 zstd 后端读取的压缩文件，不检查中途 turn_context。精确事件项目用 `sessions read`。

输出与运行环境见 [记忆契约](output-memory.md)，会话压缩、身份与偏移见 [会话契约](output-sessions.md)。
