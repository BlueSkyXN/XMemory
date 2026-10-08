# Qoder CN 来源格式

本适配器基于实际记录结构实现；版本升级后先验证字段，不能把未知格式视为空历史。

~/.qoder-cn/projects/ 的 JSONL；macOS 桌面端 ~/Library/Application Support/com.qodercn.app.stable/main.sqlite。

桌面端读取 chat_sessions 与 chat_session_messages；优先读取 parts，避免 text/tools 双份投影重复。JSONL 和桌面库中的同 ID 分别列出，不自动合并迁移副本。旧 Qoder CN IDE 专有数据库尚未适配。

支持 `list`、`search`、`read`。`--root` 可指定单个 JSONL、项目目录、main.sqlite 文件或直接包含 main.sqlite 的目录；默认来源不存在时明确报告。可迁移到其他系统，但不同系统的路径需由用户明确指定，本版未宣称完成所有操作系统和客户端版本验收。

列表时间来自原生元数据，缺失时使用文件修改时间；未找到原生标题则返回 null，不把首句或 AI 推测当原生标题。图片和附件仅在格式支持时返回占位，不解码二进制；不输出隐藏推理。
