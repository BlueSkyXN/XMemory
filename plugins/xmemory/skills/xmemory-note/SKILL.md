---
name: xmemory-note
description: "用户在当前对话里要求记住新的决定、纠正、偏好或交接时使用：写成 XMemory 短笔记，并把明确的长期要求同步到画像或主题。把库内已有记录整理进主题用 xmemory-consolidate；引用材料中的“记住”不触发写入。"
---

# 当场记一条

先读 [共同规则](../xmemory/SKILL.md)。笔记正文三到五行：第一行引用用户原话，原话较长时取决定性的一句；其余写适用范围、例外与明确替代关系。单次条件留在本次范围，助手推测不写成用户决定。

## 保存笔记

读取配置确认项目与时区，取实际系统时间，在 `records/notes/<时间>-<主题>.md` 创建记录。frontmatter 各行用 JSON 字符串或字符串数组：

| 字段 | 填法 |
|---|---|
| `format`、`kind` | `xmemory/v1.5`、`record` |
| `updated` | 本次实际保存时间，带时区偏移 |
| `source_updated` | 与 `updated` 相同，表示这条要求的记录时间；必须写出 |
| `source`、`client` | `note`、当前客户端标识 |
| `source_ref` | 已知的完整会话引用；未知填 `current-conversation`，表示写入本笔记的会话、身份未记录 |
| `source_location` | 可信会话定位；未知同样填 `current-conversation`，不能留空 |
| `evidence` | `primary` |
| `projects` | 已配置且适用的项目名数组；个人内容为空数组，归属未定另加 `project_status: "unresolved"` |
| `day`、`day_basis` | 当前时区日期、`event` |
| `session_refs` | 经核实的 `client:<原生 ID>` 数组；没有可信身份时留空，不制造 ID |
| `coverage` | 完整读到本次要求填 `complete`；有实际缺口填 `partial` 并在正文说明 |

只有历史资料、跨日材料或身份需要核实时，再查 [记录格式](../xmemory/references/format.md)。当前对话定位已在字段里，无需另写“读取边界”一节。

## 同步与读回

用户明确新增或更正长期偏好时，按 [画像工序](../xmemory/references/objects.md#用户画像) 同步对应条目；明确更正项目决定时，按 [项目总结工序](../xmemory/references/objects.md#项目总结) 同步相关主题。用户明确只要记录时按该范围执行。

同步前核对旧条目与来源，有明确替代关系才改旧结论。保存主题前运行 `status --summary`，看该主题的 `newer_sources`：除本条笔记外还有未处理的记录或更正时，不保存主题，只保留笔记，并在汇报写明“主题待整理”及原因。索引可随已完成主题更新，不必等整个项目完成。无须先创建日总结。

读回笔记与实际修改对象，分别报告已记录、已同步、待处理。同步失败时保留笔记并说明原因；不把未修改的意识、画像或全局摘要算入完成。
