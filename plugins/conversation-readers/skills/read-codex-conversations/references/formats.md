# Codex 来源格式

本适配器基于实际记录结构实现；版本升级后先验证字段，不能把未知格式视为空历史。

~/.codex/sessions/ 与 ~/.codex/archived_sessions/ 的 rollout JSONL；可用时只读 state_*.sqlite 的 threads 表补标题。

response_item 的 user/assistant 消息和 function/custom tool 调用；event_msg 是重复投影，不重复显示。明确标记压缩摘要，不输出 reasoning 或 analysis。

支持 `list`、`search`、`read`。`--root` 可指定单个 rollout JSONL 或包含它的目录；state_*.sqlite 不能作为 `--root`，指定 `--root` 时也不用它补标题。默认来源不存在时明确报告。可迁移到其他系统，但不同系统的路径需由用户明确指定，本版未宣称完成所有操作系统和客户端版本验收。

列表时间来自原生元数据，缺失时使用文件修改时间；未找到原生标题则返回 null，不把首句或 AI 推测当原生标题。图片和附件仅在格式支持时返回占位，不解码二进制；不输出隐藏推理。
