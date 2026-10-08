# ZCode 来源格式

本适配器基于实际记录结构实现；版本升级后先验证字段，不能把未知格式视为空历史。

~/.zcode/cli/db/db.sqlite 的 session、message、part 表。

按 session_id 定位消息和内容块，保留原生序号与工具 callID；不以运行日志冒充完整对话。不输出 reasoning、synthetic 或 ignored 内容。

支持 `list`、`search`、`read`。`--root` 可指定 db.sqlite 文件或直接包含它的目录；ZCode 不读取 JSONL。默认来源不存在时明确报告。可迁移到其他系统，但不同系统的路径需由用户明确指定，本版未宣称完成所有操作系统和客户端版本验收。

列表时间来自原生元数据，缺失时使用文件修改时间；未找到原生标题则返回 null，不把首句或 AI 推测当原生标题。图片和附件仅在格式支持时返回占位，不解码二进制；不输出隐藏推理。
