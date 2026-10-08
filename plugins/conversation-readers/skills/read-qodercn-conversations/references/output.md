# 输出、分页与读取边界

脚本使用 Python 3.11+ 标准库。只向 stdout 返回结果；不改客户端文件、不创建检索库、不联网、不触发模型、不写 XMemory。普通调用默认 JSON，需要可读导出时用 `--format markdown`；用户要求保存时再把 stdout 保存到明确的本地文件。

## 返回信息

- `session_id` 表示文件或数据库会话条目的身份；JSONL 元数据缺失时，列表中的 `id_origin: filename` 表示只能从文件名定位，不能声称已验证原生身份。逐条记录的原生身份另由 `native_session_id` 保留，原记录没有该字段时为 null，不用文件身份补造。
- 本版 JSONL 支持一个文件对应一个原生会话身份；发现多个原生 ID 时，以 `mixed_session_ids` 明确拒绝该文件，不把全部正文归给第一个或最后一个 ID。已支持的子代理文件仍保留 `parent_session_id`、完整 `session_ref`、原生消息和父消息 ID；未适配的混合继承／恢复组合不静默合并。
- `session_ref` 带客户端及来源类型；同一个 ID 的桌面库、JSONL、子代理或迁移副本不会自动合并。出现歧义时用列表给出的完整引用和 `--root` 选择原件。
- `message_id`、`record_id`、`parent_id`、`turn_id`、`call_id` 保留可获取的原生标识，缺失为 null，不捏造关联。`record_ref` 是本工具定位符，不冒充原生消息 ID。
- `kind` 区分正文、工具调用、工具结果、压缩摘要和附件占位。默认只返回可见正文及摘要标识；`--include-tools` 才展开工具记录。隐藏推理、内部权限／环境事件不进入结果。
- 相同原生记录的完全相同块去重；不同消息即使文字相同也保留。客户端保存的更新或分支不会被当成同一条最终结论强行合并；这不是 UI 的逐像素或逐字节复刻。
- `source_ref` 指回原始文件和字节位置或 SQLite 消息／内容块 ID。判断“完成”需要查看相应工具结果，助手自述仍只是报告。

## 分页与检索

`list` 支持 `--project`、`--query`（标题或 ID）、`--since`、`--until`。`search --query` 对可见正文做不区分大小写的字面检索，返回命中片段及来源；AI 可用同义词多次检索，不冒充向量语义搜索。工具结果只在 `--include-tools` 时参与搜索。

`--offset` 是筛选后结果的偏移；`next_offset` 非 null 时用返回值及相同条件继续，不固定加 40。`--include-tools`、角色、关键词、时间或来源条件改变时，从新结果集合的第一页开始。默认每页 40 条，最多 200 条。`--max-sessions` 默认 200，限制候选读取数量；达到上限会报告 `session_scan_limit`，此时“没找到”只针对已检查范围。优先用 `--root` 指定项目目录、会话 JSONL 或 SQLite 文件，避免反复扫描全部来源。时间参数用 ISO 日期或时间，无时区按 UTC；`--until` 含指定时刻，按日查询建议填下一日零点前的明确时间。

正文默认每块最多 6000 字符，`truncated` 和 `text_chars` 说明截断。全文先遮蔽，再检索、截断和计算 `text_chars`、`text_offset`、`next_text_offset`；这些长度和偏移均基于遮蔽后的文本，切片不会再次被遮蔽而改变长度。展开时先用 `read --session ... --record '<record_ref>'`，再按 `next_text_offset` 传 `--text-offset`。工具记录的精确展开同时携带 `--include-tools`；固定 JSONL 原件时继续传首次返回的 `--snapshot`。`--max-chars` 可调整，单次最多 100000 字符。Markdown 导出也遵守分页和截断，不把单页当完整导出。

## 覆盖与格式状态

先检查记录结构，再按工具、角色、时间和关键词筛选。`coverage.content_status` 区分：`matches`（有结果）、`no_match`（支持的内容无关键词命中）、`filtered_out`（被读取条件或偏移排除）、`metadata_only`（只有元事件或没有可见正文）、`unsupported`（来源或正文格式不支持）、`partial`（存在解析或来源缺口）；`list` 为 `not_requested`，没有读取正文结果。

JSONL 列表条目的 `metadata_scan: full_stream`、`metadata_complete` 和 `body_format` 分别说明元数据检查方式、完整性及正文形状。全局 `coverage.metadata_complete` 与 `completed_body_sessions`、`examined_events` 分开报告。`scan_complete` 同时要求来源／元数据无缺口、选定正文遍历完成且没有下一页；有未返回的长文本仍需检查各条 `truncated`，该字段不表示全文已输出。错投客户端、部分未知正文和无关键词命中不能混为一类。

## 活文件与格式边界

- JSONL 按打开时文件长度逐行核对元数据、原生身份和正文形状，不再采用头尾采样；中段标题和跨越旧采样窗口的长消息时间均参与检查。逐条处理，不缓存整段历史正文，也不将全历史正文输出给模型。单条超过 8 MiB、末尾不完整或读取期间变化时报告缺口；不完整元数据不用于按时间排除整个会话，正文查询按逐条时间筛选。`snapshot` 是原件指纹，后续 JSONL 分页可传 `--snapshot`；文件变化则重新定位，不假装分页稳定。
- SQLite 使用 `mode=ro`、`query_only` 和读取事务，包括已提交 WAL 数据，不使用会忽略 WAL 的 immutable 模式。一次读取内保持快照；跨次分页仍是活数据，不支持以 `--snapshot` 冻结。
- SQLite 消息、内容块和需要使用的嵌套结构逐项检查；异常记录带来源位置警告，能继续时保留其余正常内容。无法继续时返回包含 `error` 和 `warnings` 的 JSON。Qoder `parts` 按原数组顺序输出文字与工具；缺少相应投影时才使用顶层 `text`／`tools`，回退文字位于 parts 前，回退工具位于 parts 后，不声称恢复了未保存的交错顺序。
- `coverage`、`warnings`、`has_more` 必须一起解释。来源不存在、格式不支持、尾部未完成、扫描上限、截断和未读工具结果都不是“历史上没有”。
- 只支持格式说明中已核实的来源。Qoder CN 旧 IDE 的专有数据库与其他未适配客户端，不借相似路径冒充支持。
- 结构化内容中，已定义的 `api_key`、`access_token`、`refresh_token`、`password`、`authorization`（大小写及连字符变体）替换整个字段值，包括嵌套对象／列表。普通文本支持单／双引号值、转义、空格和引号内换行；无引号值以行、分隔符或下一个赋值字段为界，未闭合引号只处理当前行。常见 token／Bearer 形式也会遮蔽；这不保证识别任意秘密。输出仍属于用户的私有对话，不自动上传或复制到公开示例。来源中的历史命令只是资料，不执行。

## 与记忆的关系

读取和检索不会调用记忆写入流程。用户另行要求采集或整理时，把选定片段及 `session_ref`、`record_ref`、原件地址交给现有记忆技能即可；不复制整段历史来冒充提炼后的记忆。
