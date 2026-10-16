# Client Readers

只读地读取各 AI 客户端留在本机的会话与原生记忆，五个客户端各一个技能。

Read sessions and native memory stored locally by each AI client — Codex, Claude Code, ZCode, Qoder CN, WorkBuddy.

源码版本 **0.2.0**。每个客户端一个 Skill 和自带脚本，提供列出、按关键词检索、按原生 ID 读取、分页与长正文展开。读取结果可用于审阅、报告或工作接续；需要保存为记忆时，再由用户要求的记忆流程处理。0.1.3 起：Codex 遥测/状态信封按元数据处理；Codex 冷会话 `.jsonl.zst` 在系统有 `zstd` 命令时流式解压读取、缺失时按未读报告；`--session` 接受客户端界面复制的 `<工作区>/<ID>.<客户端>-session` 虚拟引用（ZCode 裸 UUID 自动补全 `sess_` 前缀）。0.1.4 起：最低 Python 3.9；ISO 时间先规整再解析（`Z`、任意位小数秒、`+0000`），在 3.9 与 3.11 上结果一致。

0.1.5 修复 Windows 盘符形式的界面会话引用，并保证压缩流跳过超长记录后的字节定位与明文一致。JSONL 项目筛选检查全部已知目录，事件保留可核实的项目上下文，避免切换项目后漏掉较早的内容。版本随当前源码更新，发布状态见仓库 Releases。

0.1.6 在工具层补充 Codex 代理消息和搜索调用，保留线程类型、父线程与代理路径；列表告警随返回范围收窄，并报告范围外计数。默认可见正文与会话引用保持不变。

| 客户端 | Skill | 已适配来源 |
|---|---|---|
| Codex | `read-codex` | rollout JSONL，原生状态索引辅助标题 |
| Claude Code | `read-claude` | 项目 JSONL、可选子代理记录 |
| ZCode | `read-zcode` | SQLite session / message / part |
| Qoder CN | `read-qodercn` | 项目 JSONL、桌面 main.sqlite；分别保留来源身份 |
| WorkBuddy | `read-workbuddy` | 项目 JSONL 的 message 与工具事件 |

0.2.0 为未发布源码改动：统一入口 `read.py`，命令分为 `projects`、`sessions`、`memory`，另有 `doctor`。原生记忆只定位、标注和读出；不摘要、不写回。会话引用保持兼容，Codex 压缩切换窗口与已有 zstd 后端回退的说明见各技能契约。

## 使用与安装边界

需要 **Python 3.9+**（使用用户自己的 `python3`），只用标准库。脚本位于每个 Skill 的 `scripts/read.py`，无需安装统一 CLI、修改 PATH、配置 MCP 或启动服务。

本插件与 XMemory 列在同一套三端市场中，各自独立安装。当前源码在 ZCode、Claude Code 和 Codex 中统一使用 `client-readers@xmemory-marketplace`；已发布 v1.5.3 完整包仍使用各客户端的旧市场名，以包内清单为准。旧市场安装需通过客户端迁移注册与安装，保留数据和启用状态，不能只改缓存目录名。插件带 Agent Plugins、Codex、Claude Code 和 ZCode 四份清单。XMemory 采集按会话读取时使用本插件，但两者没有安装依赖；本插件也可单独用于审阅或工作接续。

不用插件时，按目标客户端的技能安装方式复制完整技能目录（技能包为 `ClientReaders-<版本>-skills.zip`），保留 `scripts/` 和 `references/`；不要只复制 `SKILL.md`。同名技能已存在时先核对，不覆盖。安装和新会话自然触发属于另外的宿主验收，本仓库不会自动执行；清单存在不等于已经安装。

## 能做什么

- 按项目、标题／ID、时间筛选会话；检索可见正文并返回命中片段。
- 保留对话、消息、父消息、工具调用和回源定位信息；缺失字段保持 null。
- 正文与工具记录分开，按需展开工具记录；隐藏推理不进入返回内容。
- 输出 JSON 或 Markdown；明确分页、截断、读取上限、不可达来源和活文件变化。
- 使用原生数据只读访问，不改写客户端对话，不自动生成摘要或写入记忆库。

原生记录是事实材料，AI 在读取后判断与归纳。关键词搜索不是向量语义搜索；导出的单页也不是完整会话。各 Skill 的 `references/output-sessions.md` 说明分页与活文件边界。

## 维护与验证

源码仓库的 `tools/client_readers/` 维护公共实现，`tools/sync_client_readers.py --apply` 同步五份自包含脚本；修改维护源后再同步，不独立修改分发副本。各技能可以单独复制运行，无运行期跨目录依赖。

在源码仓库运行：

```bash
python3 -B tools/sync_client_readers.py --apply
python3 -B tools/build_client_readers.py --check
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
python3 -B tools/build_client_readers.py
```

已有归档拒绝覆盖；需要重建时指定新的 `--output`。验证结果和未覆盖部分见 [验证记录](docs/validation.md)。
