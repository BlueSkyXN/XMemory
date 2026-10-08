# Conversation Readers

版本 **0.1.1**。每个客户端一个 Skill 和自带脚本，提供列出、按关键词检索、按原生 ID 读取、分页与长正文展开。读取结果可用于审阅、报告或工作接续；需要保存为记忆时，再由用户要求的记忆流程处理。

| 客户端 | Skill | 已适配来源 |
|---|---|---|
| Codex | `read-codex-conversations` | rollout JSONL，原生状态索引辅助标题 |
| Claude Code | `read-claude-conversations` | 项目 JSONL、可选子代理记录 |
| ZCode | `read-zcode-conversations` | SQLite session / message / part |
| Qoder CN | `read-qodercn-conversations` | 项目 JSONL、桌面 main.sqlite；分别保留来源身份 |
| WorkBuddy | `read-workbuddy-conversations` | 项目 JSONL 的 message 与工具事件 |

## 使用与安装边界

需要 **Python 3.11+**，只用标准库。脚本位于每个 Skill 的 `scripts/read_conversations.py`，无需安装统一 CLI、修改 PATH、配置 MCP 或启动服务。

可以从源码选择对应 `SKILL.md`，按其说明调用脚本。需要安装时，按目标客户端的技能安装方式复制完整技能目录，保留 `scripts/` 和 `references/`；不要只复制 `SKILL.md`。同名技能已存在时先核对，不覆盖。安装和新会话自然触发属于另外的宿主验收，本仓库不会自动执行。

完整插件包包含 Agent Plugins、Claude Code 和 ZCode 清单；独立技能包可分发各技能。新扩展没有加入旧 XMemory 市场清单，旧记忆插件的五技能、纯文档载荷、规则和分发包保持独立。要通过某个宿主市场安装，需要用户指定后另行登记，不能把清单存在说成已经安装。

## 能做什么

- 按项目、标题／ID、时间筛选会话；检索可见正文并返回命中片段。
- 保留对话、消息、父消息、工具调用和回源定位信息；缺失字段保持 null。
- 正文与工具记录分开，按需展开工具记录；隐藏推理不进入返回内容。
- 输出 JSON 或 Markdown；明确分页、截断、读取上限、不可达来源和活文件变化。
- 使用原生数据只读访问，不改写客户端对话，不自动生成摘要或写入记忆库。

原生记录是事实材料，AI 在读取后判断与归纳。关键词搜索不是向量语义搜索；导出的单页也不是完整会话。各 Skill 的 `references/output.md` 说明分页与活文件边界。

## 维护与验证

源码仓库的 `tools/conversation_reader_runtime.py` 维护公共实现，`tools/sync_conversation_readers.py --apply` 同步五份自包含脚本；修改维护源后再同步，不独立修改分发副本。各技能可以单独复制运行，无运行期跨目录依赖。

在源码仓库运行：

```bash
python3 -B tools/sync_conversation_readers.py --apply
python3 -B tools/build_conversation_readers.py --check
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
python3 -B tools/build_conversation_readers.py
```

已有归档拒绝覆盖；需要重建时指定新的 `--output`。验证结果和未覆盖部分见 [验证记录](docs/validation.md)。
