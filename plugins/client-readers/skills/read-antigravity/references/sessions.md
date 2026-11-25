# Antigravity CLI 来源格式

本适配器基于 Antigravity CLI 1.5.16 的实际记录结构实现，官方没有公开这些文件的格式；版本升级后先验证字段，不能把未知格式视为空历史。

数据根 `~/.gemini/antigravity-cli/`：

| 位置 | 用途 |
|---|---|
| `conversation_summaries.db` | 会话索引：标题、工作区、父会话、agent 名称与最近修改时间 |
| `brain/<会话ID>/.system_generated/logs/transcript_full.jsonl` | 会话正文，每行一个步骤 |
| 同目录 `transcript.jsonl` | 字段截断版；只有它时降级读取，报告 `truncated_transcript` 与逐条 `truncated_record` |

`conversations/<会话ID>.db` 的步骤以无公开 schema 的 protobuf 保存，`implicit/`、`annotations/` 和根目录的 `.pb`/`.pbtxt` 文件同样不解析。`brain/<会话ID>/` 下的 walkthrough 等产物和截图不纳入会话正文。Antigravity 2.0 桌面端与 IDE 的数据根本版未适配。

## 记录映射

每个步骤有 `step_index`、`source`、`type`、`status` 与 `created_at`，`record_id` 取 `step_index`；原件没有逐条会话 ID 与工作目录，`native_session_id` 和事件 `project` 为 null。

| source / type | 输出 |
|---|---|
| `USER_EXPLICIT` / `USER_INPUT` | 用户消息；`media` 为附件占位 |
| `MODEL` / `PLANNER_RESPONSE` | `content` 为助手消息；`tool_calls` 在 `--include-tools` 时输出为 `tool_call`；`thinking` 为隐藏推理，不输出 |
| `MODEL` / `GENERIC` | 工具结果，`--include-tools` 时输出为 `tool_result`，附原生 `status`（`DONE`、`RUNNING`、`ERROR` 等）；截图等媒体只记 `attachments` 数量 |
| `SYSTEM` / `CHECKPOINT` | 压缩后的续接摘要，`kind: summary`、`role: context` |
| `SYSTEM` 或 `SYSTEM_SDK` / `SYSTEM_MESSAGE` | 系统注入的提醒、看板与成员消息，`--include-tools` 时输出为 `kind: system_message`、`role: context` |
| `SYSTEM` / `ERROR_MESSAGE` | API 重试与失败通知，按元数据跳过 |

工具调用和结果按步骤顺序排列，原件不保存调用 ID，`call_id` 为 null，不补造配对。其他 source/type 组合或字段类型不符时报告 `unsupported_body`。

## 会话、子会话与项目

会话 ID 取 `brain/` 下的目录名，`id_origin: brain_directory`。标题来自索引库，`title_origin: native_index`；索引缺失或没有该会话时报告缺口，标题、项目与父会话为 null。`transcript` 字段标明读取的是 `full` 还是 `truncated` 正文。

索引中 `parent_conversation_id` 非空的会话是 swarm 成员或子代理，`variant: subagent`，`session_ref` 为 `antigravity:subagent:<ID>`，列表另给 `parent_session_id` 与 `agent_name`。默认只列顶层会话，加 `--include-subagents` 纳入；`--session` 点名子会话，或 `--root` 直接指定会话目录、正文文件时照常读取。`projects` 的会话计数同样只计顶层会话。

`projects` 与 `--project` 使用索引库的 `workspace_uris`：只识别本机 `file://` URI，百分号编码的中文等路径先解码。未运行过的空会话只有上传与草稿目录，不列出；索引记录有步骤却缺正文时报告 `transcript_missing`。

`--session` 接受原生 ID、`session_ref` 和 Antigravity 回答里的 `conversation://<ID>` 链接。`--root` 可指定数据根、`brain/` 目录、单个会话目录或正文文件；不在数据根内的来源报告 `index_unavailable`。正文文件可能仍在写入，后续分页传首次返回的 `--snapshot`。
