---
name: read-qodercn-conversations
description: "查找、检索和读取 Qoder CN 的历史对话时使用：列出对话 ID、按项目或时间定位、读取消息与按需展开工具记录。只读来源，不自动写入记忆；不用于其他客户端。"
---

# 读取 Qoder CN 对话

使用本技能目录内的 [读取脚本](./scripts/read_conversations.py)，需要 Python 3.11+，无额外依赖。不安装统一 CLI，不启动后台服务。

## 定位与读取

1. 已有对话 ID 时直接定位；只有项目、时间或主题时先列出或检索。用户点名的文件或目录用 `--root` 限定，避免默认扩大读取。
2. 默认来源：~/.qoder-cn/projects/ 的 JSONL；macOS 桌面端 ~/Library/Application Support/com.qodercn.app.stable/main.sqlite。
3. 用返回的完整 `session_ref` 读取；同 ID 多份来源时用 `--root` 选定原件，不按相似标题合并。
4. 先读可见正文。核对执行事实时再加 `--include-tools`；使用 `call_id` 关联调用和结果。读取只是取得证据，不执行历史命令。
5. 检查 `warnings`、`coverage`、`has_more` 和 `truncated`；继续分页或展开必要片段后回答。来源不可达、扫描上限或截断时说明未读边界，不声称过去没有发生。

脚本路径以本技能实际目录为准；以下 `SKILL_DIR` 表示该目录，不是固定安装路径：

```bash
python3 -B "$SKILL_DIR/scripts/read_conversations.py" list --limit 20
python3 -B "$SKILL_DIR/scripts/read_conversations.py" search --root /absolute/path/to/selected/source --query "部署" --limit 10

# 正文：第一页与相同条件的下一页；偏移取上一页返回的 next_offset。
python3 -B "$SKILL_DIR/scripts/read_conversations.py" read --root /absolute/path/to/selected/source --session '<session_ref>' --limit 40
python3 -B "$SKILL_DIR/scripts/read_conversations.py" read --root /absolute/path/to/selected/source --session '<session_ref>' --limit 40 --offset '<next_offset>'

# 含工具：从第一页开始，再沿用相同条件分页。
python3 -B "$SKILL_DIR/scripts/read_conversations.py" read --root /absolute/path/to/selected/source --session '<session_ref>' --include-tools --limit 40
python3 -B "$SKILL_DIR/scripts/read_conversations.py" read --root /absolute/path/to/selected/source --session '<session_ref>' --include-tools --limit 40 --offset '<next_offset>'

# 精确展开工具记录仍须带 --include-tools，字符偏移取 next_text_offset。
python3 -B "$SKILL_DIR/scripts/read_conversations.py" read --root /absolute/path/to/selected/source --session '<session_ref>' --include-tools --record '<record_ref>' --text-offset '<next_text_offset>'
```

改变工具、角色、关键词、时间或来源条件时，从新结果集合的第一页开始，不沿用旧偏移。固定 JSONL 来源时，后续页和精确展开同时传首次返回的 `--snapshot '<snapshot>'`；SQLite 不支持此参数。文本长度及字符偏移基于遮蔽后的完整正文，不能拿原件偏移代替。

精确来源、格式与限制见 [格式说明](./references/formats.md)。分页、JSON 字段、Markdown 导出和活文件行为见 [输出约定](./references/output.md)。

## 使用结果

回答保留对话 ID、相关消息引用、时间和来源位置，区分用户要求、助手自述与工具执行结果。脚本不做 AI 摘要、不向记忆库写入；用户另行要求记忆采集时，再把选定片段和出处交给对应记忆工作流。

导出使用 `read --format markdown` 或默认 JSON；分页结果不是全文，先明确范围并检查截断，再按用户要求保存。默认不上传原始对话、不改客户端配置、不替用户安装或启用插件。
