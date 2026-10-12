# Conversation Readers 验证记录

版本 0.1.4，最新核对日期 2026-10-12。验证范围为技能入口、脚本读取行为、本地包装与隔离安装；未在真实客户端会话中触发。

## 0.1.4 Python 3.9 兼容

- **起因**：客户端执行命令的 shell 不一定读用户的 shell 配置，`python3` 可能落到 macOS 自带的 3.9.6（Xcode Command Line Tools）。本机历史会话里，Codex、Claude Code、ZCode 都出现过 3.9.6。
- **改动**：新增 `parse_iso`，在 3.9/3.10 上先把 `Z`、非 3/6 位小数秒、`+0000` / `+00` 时区规整成 `fromisoformat` 认的写法；`epoch` 与 `--since` / `--until` 都改用它。此前 3.9 遇到这类时间会得到 0，会话的创建、更新时间和排序随之出错。
- **验证**：全部读取器测试在 Python 3.11 与系统 3.9.6 上各跑一遍，均通过；新增时间解析测试覆盖上述写法，两版结果一致。

## 0.1.3 格式演进与引用归一化

- **Codex 遥测/状态信封归入元数据**：实测 0.162.1 rollout 顶层存在 `token_usage_record`、`world_state`、`inter_agent_communication_metadata`（信封均为 timestamp/ordinal/type/payload，无对话正文），原被通用规则误判 `unsupported_body` 致警告刷屏与 `metadata_complete=false`。现按元数据处理；`json_events` 读取路径本就只认 `response_item`，行为不变。
- **`.jsonl.zst` 支持**：Codex `local_thread_store_compression` 会把冷 rollout 改写为 `.jsonl.zst`（0.162.1 二进制含该 feature flag 与 `--max-mib-per-second` 限速；AgentLedger `codex_zstd.go` 交叉证实）。读取器发现即处理：系统有 `zstd` 命令时流式解压（byte 偏移基于解压后字节流），无则按 `zstd_missing` 报告未读数量，不静默漏掉。本机当前 0 个 `.zst`，未开启该设置。
- **`--session` 归一化**：客户端界面复制的虚拟引用 `<工作区>/<ID>.<客户端>-session`（ZCode 实测格式，磁盘无此文件）按文件名确定性剥壳，客户端必须匹配；ZCode 裸 UUID 确定性补全 `sess_` 前缀。不做模糊匹配。
- **ZCode 生命周期 part 归入内部事件**：实测 part 表存在 `step-start`/`step-finish`（token 遥测）、`timeline`（模型切换分隔）、`compaction`（压缩操作记录，摘要本体在 `summaryMessageId` 所指的独立 message 中，正常路径已读取），0.1.2 曾对每条误报 `unsupported_body`（单会话可达约 90 条）。现静默跳过，与隐藏推理同等对待。
- **文档**：ZCode SKILL.md 新增「标识与界面引用」；其余四端 SKILL.md 各补「标识与线索」（两种标识与线索不全定位法）；五端 formats.md 各补「项目根与存储位置」映射；输出约定同步上述行为。
- 以上均有虚构原始记录上的回归测试；真实会话抽查为只读冒烟（本机 db.sqlite 以界面虚拟路径定位并读取成功；修复后重读同会话 `unsupported_body` 归零）。

## 0.1.2 加入三端市场

读取脚本与技能正文未改动。本版只调整分发：
- 新增 Codex 清单 `.codex-plugin/plugin.json`；
- 本插件与 XMemory 一起列入 ZCode、Claude Code、Codex 三份市场清单，各自独立安装；
- 完整插件改由 XMemory 市场完整包分发，单独只发技能包 `ConversationReaders-0.1.2-skills.zip`。

隔离安装用的是市场完整包解压目录，在一次性 `CODEX_HOME`／`CLAUDE_CONFIG_DIR` 中进行，结束后删除，没有发起模型调用：
- Codex CLI 0.162.1：`conversation-readers@xmemory-codex` 安装为 0.1.2 并启用，`codex debug prompt-input` 中出现全部五个 `conversation-readers:read-*` 技能；
- Claude Code 2.1.296：`plugin validate --strict` 通过，`conversation-readers@xmemory-claude` 安装为 0.1.2 并启用，`plugin details` 列出五个技能。

## XR-005 JSONL 消息 uuid 补修

复评基准为 `a4586b3`（PR #3 合并后）。该版本的工具关联 ID 检查有效，但 Claude／Qoder CN JSONL 把消息 `uuid` 放入 `record_id`，公共去重键包含该字段；`uuid` 为列表或对象时默认正文和含工具读取都会抛出 `TypeError`，正常消息一并丢失。该缺陷在基线已存在，不是 PR #3 引入的回归。

- 在进入正文解析前检查消息 `uuid`：异常时跳过整条记录（含其正常文本块），继续后续消息，与 SQLite 消息级 ID（`parentID`／`turnId`）的处理粒度一致。
- 保留字符串；缺失／null 沿用现有输出契约（`record_id` 为 null，不参与去重比较）；错误类型不转成字符串。
- `invalid_id` warning 包含源文件、字节偏移和字段名；两种读取模式均返回 `content_status=partial`、`scan_complete=false`。
- 新增 2 项回归（Claude、Qoder CN 各一），使用虚构 JSONL 并调用实际分发脚本，覆盖缺失／null／正常字符串／列表／对象／数字／布尔 × 两种读取模式；消息级粒度（异常记录整条跳过、前后消息保留）为显式断言。

评审复现的两条虚构记录先在复评基准包（`xr005-jsonl-r2` 解压脚本）上崩溃（列表与对象两种错误类型 × 两端 × 两种模式共 8 种组合全部退出码 1）。补修后本地 **63/63** 测试通过（读取扩展 48 项、记忆包装 15 项）；公共运行时与五份脚本逐字节同步。四包校验值记录在源码仓库 `docs/validation.md`，本文件不包含自身归档哈希。

## XR-005 JSONL 关联 ID 补修

复评基准为 `3e96411ba8f73323c35226b6c294bc417d136c4f`（PR #2 合并后）。该版本的 SQLite 路径检查有效，但四条 JSONL 路径的工具关联 ID 未经检查：`blocks()` 将原始 `tool_use.id`／`tool_result.tool_use_id` 直接放入 `call_id`，公共去重集合将其作为键元素，列表或对象在默认正文和含工具读取都会抛出 `TypeError`，正常正文一并丢失。该缺陷在基准已存在，不是 PR #2 引入的回归。

- 在生成工具事件前检查关联 ID，覆盖 Claude／Qoder CN JSONL 消息内容块、Codex JSONL 的 `function_call`／`custom_tool_call` 及其输出、WorkBuddy JSONL 的 `function_call`／`function_call_result`。
- 保留字符串 ID；沿用缺失／null ID 契约，不强制生成原生 ID，也不将错误类型转成字符串。异常工具只跳过对应内容块或记录，同消息其他块与前后消息正文继续返回。
- `invalid_id` warning 包含源文件、字节偏移、内容块序号及字段名；默认正文模式因先解析后过滤，同样报告异常工具造成的解析缺口，两种读取模式均返回 `content_status=partial`、`scan_complete=false`。
- 新增 4 项回归（四端各一项），使用虚构 JSONL 并调用实际分发脚本，覆盖工具调用与工具结果两种记录（Codex 覆盖 `function_call`／`function_call_output` 与 `custom_tool_call`／`custom_tool_call_output` 四种记录，自定义工具用 `input` 字段、普通工具用 `arguments` 字段）、两种读取模式、列表／对象／数字／布尔 ID、正常字符串和允许缺失／null 的控制用例。同一消息中异常工具前后的正文块与前后消息正文均须保留。

评审复现的两条虚构记录先在复评基准脚本上崩溃。补修后本地 **61/61** 测试通过（读取扩展 46 项、记忆包装 15 项）；公共运行时与五份脚本逐字节同步。读取器包解压后以分发技能目录完整重跑 61 项测试通过。四包校验值记录在源码仓库 `docs/validation.md`，本文件不包含自身归档哈希。真实客户端接续和长历史成本仍属后续验收范围。

## XR-005 关联 ID 补修

复评基准为 `7e915493729b50a27d1598de6993b2501e1a4dca`。该版本对 SQLite 外围对象的检查有效，但 Qoder `tool.id` 和 ZCode `callID` 为列表或对象时，默认正文和含工具读取都会在公共去重处抛出 `TypeError`。

- 在生成工具事件前检查关联 ID；Qoder 同时覆盖 `parts` 和顶层 `tools` 回退，定位所用的 `parts[].id`、消息的 `turnId`，以及 ZCode 消息的 `parentID` 一并检查。
- 保留字符串 ID；沿用读取器的缺失／null ID 契约，不强制生成原生 ID，也不将错误类型转成字符串。异常工具只跳过对应块，消息级 ID 异常跳过对应消息，其余正常正文继续返回。
- `invalid_id` warning 包含源文件、消息、内容块及字段位置；两种读取模式均返回 `content_status=partial`、`scan_complete=false`。
- 新增 4 项回归，使用虚构 SQLite 并调用实际分发脚本，覆盖两端、两种读取模式、列表／对象／数字／布尔 ID、正常字符串和允许缺失／null 的控制用例。同一消息中异常工具前后的正文也须保留。

工具 ID 用例已先在复评基准脚本复现崩溃。补修后本地 **57/57** 测试通过（读取扩展 42 项、记忆包装 15 项）；原有 53 项测试和 CI 工作流未修改。公共运行时与五份脚本逐字节同步。四包校验值记录在源码仓库 `docs/validation.md`，本文件不包含自身归档哈希。真实客户端接续和长历史成本仍属后续验收范围。

## PR #1 补修：XR-001 至 XR-006

评审基准为 `9d0d43900eea7f65dd39515078fe6ba31bb1560c`。保留未发布的 0.1.1 版本号与现有同步、打包方式，公共实现先修改，再同步五份技能副本。下方初版记录属于历史验证，不能替代本节的补修结果。

- XR-001：结构化敏感字段替换整个值；文本按引号、转义、换行与字段边界遮蔽。检索、长度和偏移基于遮蔽后的完整文本，序列化与切片后不再次修改正文。
- XR-002：逐行核对原生会话 ID；混合身份文件明确拒绝，文件身份与逐条 `native_session_id` 分开，已支持的子代理和消息父子关系继续保留。
- XR-003：查询过滤前核对正文结构，区分无命中、条件排除、元事件、格式不支持和部分解析；元数据完整性、正文遍历及分页边界分别报告。
- XR-004：JSONL 元数据改为逐行完整核对，中段标题和跨旧采样窗口的长消息时间恢复命中；不缓存或输出整段历史正文。长历史成本仍待试用测量。
- XR-005：SQLite JSON 对象、角色及 semantics、parts、state、tool 等结构逐项检查，异常记录给出位置并保留其他可读记录；无法继续时返回结构化错误。
- XR-006：Qoder parts 按原数组顺序输出正文与工具；顶层 text/tools 仅在对应投影缺失时回退，避免重复。

新增 16 项读取回归与控制测试（XR-001 四项、XR-002 两项、XR-003 四项、XR-004 两项、XR-005 两项、XR-006 两项），均使用虚构数据。六类原始反例已先在评审基准实现上复现；补修后本地全仓库 **53/53** 测试通过，其中读取扩展 38 项、原记忆包装 15 项。分页回归包含真实脚本入口，验证 JSON 可解析及遮蔽后切片连续展开；异常记录检查不依赖个人历史。

新包使用单独输出目录 `dist/pr-1-review-20261009/`，旧归档保留；四个包的最终 SHA-256 记录在源码仓库 `docs/validation.md` 与 PR 说明中。本文件随读取扩展分发，不记录自身归档哈希。宿主安装、自然语言触发、跨客户端接续和长历史成本仍未验收。

## 0.1.1 初版修复（历史记录）

- 0.1.0 的脚本在 JSON 序列化后对整段文本再次遮蔽，正文含 `password="…"`、`KEY: "…"` 等带引号键值时会破坏转义，输出非法 JSON 且退出码为 0；0.1.0 的本机抽查未覆盖这类检索。现改为序列化前逐个字符串值遮蔽，覆盖范围不变；新增经脚本入口解析 JSON 的回归，该用例在 0.1.0 代码上失败。修复后在本机五端以 `password`、`authorization` 检索，输出均可解析；复查只记录可否解析与条数。
- 各技能 `formats.md` 按实际支持的来源分别说明 `--root`；构建工具读取文件显式使用 UTF-8，默认输出目录随清单版本变化。
- 本地包构建到 `dist/conversation-readers-0.1.1/`，校验值见同目录 `.zip.sha256` 和包内 `SHA256SUMS`；本文件随包分发，不记录所在归档的哈希。0.1.0 的两个本地构建目录保留不覆盖，均不含本修复。

## 初版已执行（历史记录）

- 五个技能均通过 `skill-creator/scripts/quick_validate.py` 元信息检查。
- 22 项读取扩展测试通过，使用虚构 JSONL / SQLite：五端解析、原生 ID、父消息和工具关联、重复投影、隐藏推理排除、常见凭据遮蔽、脚本入口 JSON 在遮蔽后仍可解析、分页及长记录展开、活文件指纹、残缺尾行、扫描上限、未知 schema、只读数据库、已提交 WAL 可见性、私有绝对路径拒绝及解压后包装复查。
- 独立验证 Agent 通过五端虚构数据实际调用各 Skill 脚本，执行 list、search、read、两页读取及精确记录展开；Qoder CN 同时检查 JSONL 和桌面 SQLite。原件前后字节一致。
- 独立验证发现的三个问题已修复、加入回归，并由原验证 Agent 重新执行最小复现确认通过：文件名不能遮住原生 ID 别名、Unicode casefold 命中位置映射回原文、SQLite 父目录识别已知数据库文件名。
- 在本机现有数据上，Codex、Claude Code、WorkBuddy、ZCode、Qoder CN 桌面及 Qoder CN JSONL 六个来源分别通过列出 → 精确选定来源 → 读取 → 关键词检索的只读抽查。对话正文与原生 ID 不写进本报告或测试样例。
- 全仓库单元测试 **37/37** 通过（读取扩展 22 项，原记忆插件 15 项）；独立扩展包装检查与原记忆包装检查均通过。归档检查器已修正对根目录生成文件 `SHA256SUMS` 的识别，并加入解压回归。
- Claude Code 2.1.292 对扩展清单的 strict 校验成功，无错误或警告；其 `contents` 为空，不代表自然语言触发已验收。
- 原 XMemory 插件载荷及现有市场清单共 100 个文件与本轮修改前 SHA-256 一致；原 1.1.0 r2 两个归档哈希不变。扩展未加入原市场，构建工具独立。

## 边界

- 本机抽查验证了当前样本，不证明所有历史版本和所有操作系统兼容。Qoder CN 旧 IDE 专有数据库未适配，不能以桌面或 CLI 的成功代替。
- JSONL 进入公共去重键的字段（`call_id`、`record_id`）均已按类型校验；不进入去重键的字段（如 `parentUuid`、`native_id`）类型异常不会中断读取，按原样输出或忽略，不做额外约束。
- 独立脚本测试不证明安装后的自然语言自动选择、新会话发现或整个客户端 UI 与导出逐字一致。
- 默认最多检查 200 个候选会话，达到上限会报告覆盖缺口；已知文件可用 `--root` 精确读取。二进制附件不在本版的全文解析范围。
- JSONL 读取快照只固定打开时的文件长度；跨请求可用指纹发现变化。SQLite 每次只读事务内一致，跨页仍是活数据。
- 隐藏推理排除与常见凭据遮蔽不等于任意敏感信息自动识别。原始对话及导出仍属于本机私有资料。
- 原 XMemory 记忆五技能、规则及三端市场清单按修改前哈希核对，不因读取扩展改变；扩展本身不读写真实记忆库。
