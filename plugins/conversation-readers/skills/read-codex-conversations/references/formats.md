# Codex 来源格式

本适配器基于实际记录结构实现；版本升级后先验证字段，不能把未知格式视为空历史。

~/.codex/sessions/ 与 ~/.codex/archived_sessions/ 的 rollout JSONL；可用时只读 state_*.sqlite 的 threads 表补标题。

response_item 的 user/assistant 消息和 function/custom tool 调用；event_msg 是重复投影，不重复显示。明确标记压缩摘要，不输出 reasoning 或 analysis。

支持 `list`、`search`、`read`。`--root` 可指定单个 rollout JSONL 或包含它的目录；state_*.sqlite 不能作为 `--root`，指定 `--root` 时也不用它补标题。默认来源不存在时明确报告。可迁移到其他系统，但不同系统的路径需由用户明确指定，本版未宣称完成所有操作系统和客户端版本验收。

## 项目根与存储位置

会话按日期树 `sessions/YYYY/MM/DD/rollout-<时间>-<uuid>.jsonl` 存放，与项目无关；项目信息在 `session_meta` 的 `cwd`，`--project` 按 cwd 匹配。Codex `local_thread_store_compression` 开启后冷会话被改写为同主干 `.jsonl.zst`：本读取器发现即读取（需系统 `zstd` 命令，缺失时按 `zstd_missing` 报告未读数量，不静默漏掉）。`token_usage_record`、`world_state`、`inter_agent_communication_metadata` 为遥测/状态信封，按元数据处理，不当正文。

列表时间来自原生元数据，缺失时使用文件修改时间；未找到原生标题则返回 null，不把首句或 AI 推测当原生标题。图片和附件仅在格式支持时返回占位，不解码二进制；不输出隐藏推理。
