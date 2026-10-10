# XMemory 验证报告

当前版本：**1.1.0**。最新核对日期：2026-10-09。正式文件格式仍为 `xmemory/v1`。研究 demo 不计入正式版本线。

本文保留各开发阶段的本地验证记录，下文“未提交／未发布”等表述对应各阶段的记录时点。Git 提交、PR 与 CI 的当前状态以 GitHub 为准。仓库自动检查由 `.github/workflows/validate.yml` 运行，覆盖包装、单元测试和分发包构建，不替代真实客户端与 Agent 行为验收。

## XR-005 JSONL 关联 ID 补修（2026-10-09）

复评基准为 `3e96411ba8f73323c35226b6c294bc417d136c4f`（PR #2 合并后）。本次保留未发布的 XMemory 1.1.0、Conversation Readers 0.1.1 版本号。PR #2 覆盖了 Qoder 桌面 SQLite 与 ZCode SQLite；本次补齐评审复现的 JSONL 同类缺陷，它在本基准已存在，不是 PR #2 引入的回归。

- Claude／Qoder CN JSONL 的 `tool_use.id`、`tool_result.tool_use_id`，Codex JSONL 的 `function_call*`／`custom_tool_call*` 的 `call_id`，以及 WorkBuddy JSONL 的 `function_call`／`function_call_result` 的 `callId`，在生成事件前进行类型检查，异常块不会进入公共去重集合。错误类型不转成字符串；缺失／null ID 继续遵守现有输出契约。
- 默认正文和含工具读取均保留异常块所在消息内的其他正常内容块与前后消息正文，并给出带文件、字节偏移、内容块及字段位置的 `invalid_id` warning，标记 `content_status=partial`、`scan_complete=false`。默认模式因先解析后过滤，同样报告异常工具造成的解析缺口。
- 先在复评基准复现评审给出的两条虚构记录：Claude 与 Qoder CN JSONL 在默认正文和 `--include-tools` 共 4 种组合均抛 `TypeError: unhashable type`、退出码 1、无正文返回；补修后均返回正常前后文并报告解析缺口。

新增 4 项读取器回归（Claude、Qoder CN、Codex、WorkBuddy），通过真实分发脚本覆盖工具调用与工具结果两种记录（Codex 覆盖 `function_call`／`function_call_output` 与 `custom_tool_call`／`custom_tool_call_output` 四种记录，自定义工具用 `input` 字段、普通工具用 `arguments` 字段）、两种读取模式，以及列表、对象、数字、布尔、正常字符串、缺失和 null ID，合计 140 次分发脚本调用。补修后 **61/61** 测试通过（读取扩展 46 项、记忆包装 15 项）；公共运行时及五份分发脚本逐字节同步，两个包装检查通过。

**哈希勘误（评审复核发现）**：初版记录的读取器包哈希来自"代码已补、包内 validation 文档尚未更新"时的构建——读取器完整包收录整个插件目录、skills 包也显式收录该文档，文档更新后未重建归档。初版 `dist/xr005-jsonl-20261009/` 保留作废，不作为分发依据。本节记录从完成全部入包修改（含 Codex 自定义工具用例与包内文档）后的源码状态重建，输出到新目录 `dist/xr005-jsonl-r2-20261010/`；临时目录重复构建与四个交付包逐字节一致，读取器包解压后以其分发技能目录替换仓库技能目录完整重跑 61 项测试通过。两个 XMemory 包不含任何 docs/validation.md，SHA-256 与上一轮 `xr005-followup` 输出逐项一致，本轮未触碰其载荷。

| 归档 | SHA-256 |
|---|---|
| `XMemory-1.1.0.zip` | `b1ed9224709345e9465a0f74c7d5adbbe884f88a77efc86f8499d7f21bd2a59e` |
| `XMemory-1.1.0-skills.zip` | `01da3e2de53c73d0ad79a21ea45a3e05894f98d6921c95ca42dd104f9bf45fa2` |
| `ConversationReaders-0.1.1.zip` | `56e533db93d6b0119bcc57d99cebffabf1ccd6914516352a58cd4b4672578da3` |
| `ConversationReaders-0.1.1-skills.zip` | `0507ee1c6b777fe3bfc7fa01285ea6f2973fed9e5bac8e2c11189732d264e810` |

本轮使用虚构数据验证读取器与本地包，不改变真实客户端配置或记忆库。本轮只处理工具关联 ID：Claude／Qoder CN JSONL 消息的 `uuid` 为列表或对象时仍会使读取中断（进入公共去重键的 `record_id`），该缺陷在本轮基线已存在，列为下一项单独补修，不能将"JSONL 关联 ID 已全部解决"作为当前结论。新提交的远端 CI、GitHub Release、真实客户端接续、31 个记忆行为场景与长历史成本均须分别验证，不能由本地测试结果替代。

## XR-005 关联 ID 补修（2026-10-09）

复评基准为 `7e915493729b50a27d1598de6993b2501e1a4dca`。本次保留未发布的 XMemory 1.1.0、Conversation Readers 0.1.1 版本号。

- Qoder `tool.id`／ZCode `callID` 在生成事件前进行类型检查，异常块不会进入公共去重；Qoder 的 `parts[].id`、`turnId` 和 ZCode 的 `parentID` 同时检查。错误类型不会被强制转成字符串，缺失／null ID 继续遵守现有输出契约。
- 默认正文和含工具读取均保留异常块前后的正常内容，并给出带文件、消息、内容块和字段位置的 `invalid_id` warning，标记 `content_status=partial`、`scan_complete=false`。
- `storage.md` 入口摘要补齐标题及 `links`、`valid_from`、`status` 等关系头部；setup description 统一为同一逻辑记忆库和用户配置的跨设备同步方式。

新增 4 项读取器回归，通过真实分发脚本覆盖 Qoder parts／tools 回退、ZCode，两种读取模式，以及列表、对象、数字、布尔、正常字符串、缺失和 null ID。工具 ID 用例先在复评基准复现失败，补修后 **57/57** 测试通过（读取扩展 42 项、记忆包装 15 项）；原有 53 项测试与 CI 工作流保持原样。公共运行时及五份分发脚本、XMemory 静态资源均无漂移，两个包装检查通过。

四包输出到新目录 `dist/xr005-followup-20261009/`，旧包未覆盖。ZIP 完整性、外部 `.zip.sha256`、包内逐文件 `SHA256SUMS` 及两个完整包解压后的包装检查均通过；两个读取器包解压后分别重跑新增 4 项回归通过。临时目录重复构建与四个交付包逐字节一致。

| 归档 | SHA-256 |
|---|---|
| `XMemory-1.1.0.zip` | `b1ed9224709345e9465a0f74c7d5adbbe884f88a77efc86f8499d7f21bd2a59e` |
| `XMemory-1.1.0-skills.zip` | `01da3e2de53c73d0ad79a21ea45a3e05894f98d6921c95ca42dd104f9bf45fa2` |
| `ConversationReaders-0.1.1.zip` | `748b00c6f2675148b2a28514c9b14b45c9a6f3e0c1ce4cb6bf46a81a94b4f20f` |
| `ConversationReaders-0.1.1-skills.zip` | `a95a6e311fa7365060693036b39e9d20c9c6e647e58b0ebbc43f5796a1e94218` |

本轮使用虚构数据验证读取器与本地包，不改变真实客户端配置或记忆库。新提交的远端 CI、GitHub Release、真实客户端接续、31 个记忆行为场景与长历史成本均须分别验证，不能由本地测试结果替代。

## PR #1 补修（2026-10-09）

评审基准为 `9d0d43900eea7f65dd39515078fe6ba31bb1560c`。保留 XMemory 1.1.0、Conversation Readers 0.1.1 的未发布版本号，沿用公共源码、资源同步、单元测试和打包流程；旧包不覆盖。

### 修订与回归

- 六项读取器问题均补入回归：完整遮蔽及稳定字符偏移、原生会话身份、正文格式与覆盖说明、长 JSONL 标题和时间漏查、SQLite JSON 形状异常、Qoder parts 交错顺序。读取器详情见 [扩展验证记录](../plugins/conversation-readers/docs/validation.md)。
- 自动入口统一调用完整 `xmemory-recall`，未整理更正的关系、冲突和生效条件使用同一套更正规则；历史回顾按 `event_at`，覆盖晚记录和未整理事件，未知发生时间保持未知。
- 五个读取技能的正文分页、含工具分页及精确展开示例分开，使用返回的偏移并保持筛选条件一致。
- 跨设备表述统一为“同一逻辑记忆库”；定时整理按允许修改的内容界定，保留旧未完成项与待确认建议的去向。
- `tests/scenarios.json` 从 26 项扩充到 31 项，新增未整理更正的立即生效、未来生效、冲突，以及晚记录历史回顾和未知发生时间场景。它们是待宿主执行的验收定义。

原评审基准的 **37/37** 测试通过结果保留。六类反例先在原实现上复现，补修后本地 **53/53** 测试通过（读取扩展 38 项，其中新增 16 项；记忆包装 15 项）；两个包装检查和资源同步检查通过。现有 CI 自动发现这些新增回归，不将 Markdown 规则或场景定义当作已执行的 Agent 行为。

### 补修分发包

输出目录为 `dist/pr-1-review-20261009/`。四个 ZIP 完整性、外部校验文件及包内逐文件 `SHA256SUMS` 均通过，两个完整包解压后再次通过包装检查。在临时目录重新构建，四包逐字节一致。Claude Code 对两个插件及 XMemory 市场的 strict 校验通过，无错误或警告；该检查不执行技能正文。

| 归档 | SHA-256 |
|---|---|
| `XMemory-1.1.0.zip` | `aabb2c519be30f650c852158824f526de24eeff83354d6476ad90f47f2d70265` |
| `XMemory-1.1.0-skills.zip` | `458e1be00e751f98e6215607cb883b791d8f5590f0d6efeacfbb3ba3bf71ab86` |
| `ConversationReaders-0.1.1.zip` | `246d49b2836eabc78c9f6c24c22c1716e6e8d46c27e1f45fca1055b683ca1887` |
| `ConversationReaders-0.1.1-skills.zip` | `8a14db89c79e11f92111a5cc4c087dc74642f978d97b879bf25d61cacc832174` |

### 本轮范围

只读测试使用虚构 JSONL／SQLite 和临时目录。真实客户端安装、新会话接续、定时运行、跨设备同步及历史增长后的调用次数、耗时和遗漏率，按 [试用与行为验收](../plugins/xmemory/docs/acceptance.md) 后续观察。未迁移真实记忆、接入客户端规则或创建 Release。

## 1.1.0 本地修订 r2：失败恢复与未处理事件（历史记录）

本轮保留插件版本 `1.1.0`、文件格式 `xmemory/v1` 和五技能目录；修改的是未发布版本的行为约定，不迁移真实记忆。旧包 `dist/release-1.1.0/` 保留，不能代表本轮修订源码；修订包使用单独目录 `dist/release-1.1.0-r2/`。

### 改动

- 整理顺序改为“记忆、积压、墓碑 → 近况和入口 → 回读确认 → 当日文件”，只登记已保存结果；明确已处理不等于业务完成或建议获准。
- 必要文件持续冲突、写入失败或回读不符时停止当前范围的后续写入。重试核对事件地址、记忆 ID 和行动 key，只补缺失步骤；部分当日登记不重复完整条目，也不把残缺条目当成功。
- 未处理事件按指定范围的各月事件清单与全部当日处理登记核对，近 30 天只决定正文阅读优先级。其他段落提及不算处理；明确撤回内容不重收录；旧格式完整登记仍可使用。
- 定时整理只更新无冲突、已生效替代关系的状态、必要元信息和入口，不合并正文。未确认建议保留来源与去向；失败重试、残缺登记和零写入不累计积压轮次。
- 同步共同规则、整理／调取技能、读取协议、定时提示词、模板、设计、示例和验收标准。读取失败可以零写入，但不能声称“本次无变化”。
- `tests/scenarios.json` 从 16 项扩充到 26 项，新增 10 个故障恢复、旧事件、待确认建议和调取场景，包含执行者需准备的 `setup`。这些是行为验收用例，不是已经通过的自动化测试。

### 验证状态

| 检查 | 本轮结果 |
|---|---|
| `python3 -B tools/sync_skill_resources.py --apply` | 静态技能资源副本已同步，后续包装检查无漂移 |
| `python3 -B tools/check_package.py` | `ok: true`，插件载荷 97 个文件 |
| `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v` | 现有 **14/14** 测试通过；未增加仅断言新措辞的测试 |
| Claude Code 2.1.292 插件与市场 `plugin validate --strict --json` | 源码和解压后的完整包均成功，无错误、无警告；`contents` 为空，不代表执行技能正文 |
| `tests/scenarios.json` | 26 项可解析，ID 唯一、技能名有效；只检查用例定义，未执行 Agent 行为 |
| 变更文件 whitespace 检查 | 对修改前本地快照逐文件执行 `git diff --no-index --check`，包含未跟踪文件，无 whitespace 错误 |

### 修订包

执行 `python3 -B tools/build_release.py --output dist/release-1.1.0-r2`，生成两个本地包：

| 归档 | SHA-256 |
|---|---|
| `XMemory-1.1.0.zip` | `614bd72737aacc740dab8ce727b8bad61cc0a3d0383e069030ef6f2910aff7f7` |
| `XMemory-1.1.0-skills.zip` | `24cb14f772a683de7f9a0083bc065e0fc5ffb37a7787bdf535416c5539c2626c` |

- ZIP 完整性、外部 `.zip.sha256` 和包内 `SHA256SUMS` 逐文件核对均通过。完整包 102 个条目，其中 101 个受校验文件；技能包 73 个条目，其中 72 个受校验文件；其余条目均为 `SHA256SUMS` 自身。
- 解压后的完整包再次通过包装检查和 Claude strict 校验，技能包恰好包含五个技能。
- 在临时目录重新构建，两包与修订归档逐字节一致；临时目录自动清理。
- 旧 `dist/release-1.1.0/` 两包哈希与修订前一致，未被覆盖。`r2` 是本地构建目录标识，插件清单版本仍为 `1.1.0`，不表示另一个已发布版本。

本轮完成源码规则修订、用例补充及本地打包验证，没有注册市场、安装、发布或提交。真实客户端安装、新会话行为、故障注入和多设备同步尚未执行，不以手工写出预期文件或 JSON 用例通过解析替代行为验收。后续宿主验收按 `plugins/xmemory/docs/acceptance.md` 的方法保留实际输入、工具结果及文件变化。

## 1.1.0 初版实现检查（修订前历史结果）

### 改动范围

- 集中库分为记忆层（入口、记忆）和接续层（近况、事件文件、当日文件），另有积压、撤回墓碑和配置。新增 `day.md`、`BACKLOG.md` 模板，改写其余模板。
- 五技能按新写入分工改写：记录和采集只新建文件；除配置外只有整理修改已有文件；定时整理只做记账类改动，判断类改动写成待确认建议。
- 新增 `integrations/scheduled-curate.md` 定时提示词；`integrations/entry.md` 改为写进 AGENTS.md / CLAUDE.md 的读取协议。
- 三端插件清单和两份市场清单版本改为 1.1.0。`.gitignore` 补充例外，使 `plugins/xmemory/.zcode-plugin/` 不再被全局忽略规则屏蔽。
- `docs/release-install.md`（打包时成为 `INSTALL.md`）改为 1.1.0 说明。

### 检查命令与结果

| 命令 | 结果 |
|---|---|
| `python3 -B tools/sync_skill_resources.py --apply` | 技能资源副本已同步 |
| `python3 -B tools/check_package.py` | `ok: true`，插件载荷 97 个文件 |
| `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v` | **14/14 通过** |
| `claude plugin validate plugins/xmemory --strict --json`（Claude Code 2.1.292） | success，无错误、无警告 |
| `claude plugin validate .claude-plugin/marketplace.json --strict --json` | success，无错误、无警告 |

新增的两个测试是文档约定回归：`test_two_layer_write_contract` 锁住新模板、“采集只新建”、记账类与判断类、事件文件名、30 天窗口、读取协议和“本次无变化”；`test_no_device_fields_in_templates` 检查模板不含设备字段。它们不冒充 Agent 行为测试。Claude 校验的 `contents` 仍为空，不代表 CLI 逐个校验了技能正文。

`tests/scenarios.json` 换成 16 个 1.1 行为场景（只新建、替代声明、分级整理、晚到事件、无变化零写入、原件不在本机、主本与副本等），尚未由独立 Agent 执行。

### 当前 Agent 隔离演练

当前 Agent 在 `mktemp` 创建的临时目录中，按 1.1.0 技能与模板手工执行虚构 demo，结束后已删除该目录。文件由当前 Agent 自己写入，只能说明规则可执行、写入集合与约定一致，不能证明宿主模型会照做。

- 设置：只有 `config.toml`、根入口和项目入口；配置可解析，没有预建近况、事件或空目录。
- 记录交接：只新增一个事件文件，其他文件哈希不变。
- 手动整理：新增近况和当日文件，修改项目入口；随后按文件名检查，未处理事件为空。
- 晚到事件：另一处 09:50 记录、10:30 整理之后才同步进来的事件，按时间水位判断会漏掉；按“是否出现在当日文件中”判断能找出。
- 定时整理：近况保留旧待办并新增待办；当日文件只在末尾追加一节，10:30 一节逐字节不变。
- 纠正：同主题已有记忆时新建带随机串的文件并声明 `supersedes`，旧文件不变；随后定时整理把旧记忆标为已替代、把新记忆收进入口。
- 无变化的定时整理：没有未处理事件，也没有待收录记忆，不写任何文件。
- 所有事件和记忆的 `identifier` 等于文件名主干。

### 实现中修正的不一致

- 来源说明中“主本改过就在近况中记一条冲突”会让采集和调取改近况；改为采集新建事件、由整理写入，调取只在回答中说明。
- 定时提示词的退出条件拆开：配置缺失、库不可达或另一处正在整理时整次停止；单个文件被改时只停该文件。
- “整理是唯一修改已有文件的动作”与设置修改 `config.toml` 冲突；统一为“除配置外”，并写明之后登记的项目只新建项目入口，根入口列表由下次整理补上。

### 本版未重跑

- ZCode 清单官方校验、Codex CLI 市场识别与 Agent Plugins schema 校验：1.1.0 只改了版本字符串和插件正文，本次没有重跑，下方保留 1.0.x 的历史结果。

### 1.1.0 初版分发包（修订前历史结果）

`python3 -B tools/build_release.py --output dist/release-1.1.0` 生成两个本地归档（`dist/` 不进入 Git）：

| 归档 | SHA-256 |
|---|---|
| `XMemory-1.1.0.zip` | `27308b4b6c264523ecd9fc60efecf736ec41e388a710f8be90cc483c02cca5bd` |
| `XMemory-1.1.0-skills.zip` | `1d671e5fd0e8babb809be0b12e0cf61717f2f04e58d3f2461c06585d3acf4533` |

- `shasum -a 256 -c` 核对两个 `.zip.sha256` 通过；ZIP 完整性和包内 `SHA256SUMS` 逐文件核对通过（完整包 101 个文件，技能包 72 个）。
- 解压后的完整包重新通过仓库检查器；三份插件清单与两份带版本的市场清单均为 1.1.0；插件载荷 97 个文件；技能包恰好五个技能；两包的 `INSTALL.md` 均为 1.1.0 说明。
- 解压内容中未发现私有路径或常见密钥格式。
- 对解压后的插件和 Claude 市场再跑 `claude plugin validate --strict`：均成功，无错误、无警告。
- 在临时目录用当前源码重建，两个归档与 `dist/release-1.1.0/` 中的逐字节一致；临时目录已删除。

这只是本地构建产物，没有发布、上传或安装到任何客户端。

## 1.0.2 用户级集中存储修正（历史结果）

- 默认根统一为 `~/.agents/memory/`，所有客户端和工作区共用；项目是集中库内的分类，不在工作区建立记忆根或软链接。
- Office Memory 后续迁入并停用，当前只读过渡；没有初始化或搬动真实记忆。
- 五技能资源副本同步检查通过，包装检查通过，**12/12 测试通过**。新增的集中根检查是文档约定回归，不冒充 Agent 行为测试。
- Claude 插件和市场 strict 校验重新通过，ZCode 官方清单校验重新通过。
- Codex CLI 在一次性隔离配置中重新识别版本 1.0.2，installed/enabled 均为 false；未注册真实用户市场或安装插件。
- 分发包用修正后的源码重新构建。尚未完成真实客户端记忆根选择、安装触发或跨客户端接续验收。

## 1.0.1 包装与资源检查（历史结果）

- `tools/check_package.py` 检查三端插件身份和版本、市场 schema 必要字段、source 归属、五技能元信息、链接、模板、纯文档载荷以及静态资源副本一致性。
- `python3 -B -m unittest discover -s tests -v`：**11/11 通过**。新增三端清单入包和技能资源漂移拒绝测试。
- 每个正式技能均自包含引用资源；便携包直接分发相同技能目录，不再做第二种路径转换。
- 插件载荷 82 个文件，仅 Markdown、TOML、JSON 与许可证；其中资源副本按需加载，不要求一次读取。没有运行期脚本、MCP、Hook、数据库、网络工具或缓存。
- 完整包保留三种市场的目录基准：ZCode 从 `plugins/` 解析，Claude/Codex 从解压根解析。
- ZIP 完整性、逐文件校验与重复构建字节一致性在测试中检查。

## 官方工具与实际解析（1.0.x 历史结果）

### ZCode

使用已有本机 CLI 入口执行 `plugin-creator` 随附的 `validate-plugin.mjs`，结果 `Plugin manifest is valid`。未注册市场或安装插件。

### Claude Code 2.1.289

以下命令均通过 strict 校验，无警告：

```bash
claude plugin validate plugins/xmemory --strict --json
claude plugin validate .claude-plugin/marketplace.json --strict --json
```

首次市场校验提示缺少 description，已补充后重新通过。

技能目录校验命令返回成功，但 `contents` 为空，不能声称 CLI 逐个校验了技能正文。另尝试把单个 SKILL.md 作为目标时，CLI 将其当作 JSON 清单解析而失败；这不是技能格式失败。因此五技能 frontmatter、命名、长度和资源边界使用仓库检查器按官方 Agent Skills 规范验证，不冒充官方技能逐项执行。

### Codex CLI 0.160.0

- 从官方地址读取 Agent Plugins 1.0.0 JSON Schema，用已安装的 jsonschema 验证根 `plugin.json`：通过。
- 官方 schema SHA-256：`0a4aad95ce337878ad38802ebf0daa3fde76abe3f65400c86bcbb1ec0b3ab883`。
- 在两个未显式配置市场的隔离 CODEX_HOME 中（普通、trusted），只读列表均未发现仓库市场；未把空列表说成成功。
- 核对 Codex 官方配置 schema 后，仅在一次性临时 CODEX_HOME 中设置 `marketplaces.xmemory-codex` 的本地 source，执行只读 marketplace/list 与 plugin/list。
- CLI 实际识别 `xmemory@xmemory-codex`、版本 1.0.1、正确 source、AVAILABLE/ON_INSTALL，状态为 `installed: false`、`enabled: false`。

这验证了当前 CLI 能解析市场与插件身份，不证明安装、启用或技能调用。没有调用 add/install，没有修改真实用户配置。

## 1.0.0 阶段的隔离行为演练（历史结果）

执行日期为 2026-10-06。当前 Agent 在系统临时目录用虚构 demo 顺序演练，不是独立盲测或安装后的新会话。

- 设置：仅配置、根入口和项目入口，没有启用来源。
- 记录：保留“用户报告测试通过”和“尚未部署”的区别，不生成个人长期规则。
- 整理：旧未完成项 verify-rollback 与新增 verify-deployment 均保留。
- 调取：回答部署未验证，前后五个记忆文件哈希不变。
- 新记录晚于近况：读取后续报告，但不将报告当当前实测；六个文件前后不变。

这些场景按 1.0.0 的文件结构执行，不算作 1.1.0 的验证。

## 尚未验证或不提供

- 未在真实用户环境注册市场、安装插件、新建会话触发或跨客户端接续。
- 读取协议尚未合并到任何客户端规则，定时提示词尚未挂到任何客户端；定时运行、`capture = "milestone"` 的实际触发和自然语言触发率都未实测。
- 多台机器经同步盘或 GitHub 私有仓库共用一个库时的晚到事件、冲突副本和“一处整理”约定，只在文档和临时目录演练中检查，未在真实同步环境验证。
- 当前 31 个行为场景、长期经验质量和搜索命中率尚未由新会话的独立执行验证。
- 不提供后台采集、Hook 程序、调度器、客户端数据库适配器、并发锁、事务、同步或组织权限。
- 默认用户级集中根为 `~/.agents/memory/`。已配置其他集中根的用户不会被自动迁移；无权访问时不回退到项目内另存一套。
- Office Memory 迁移按设计延后到试点之后。未改研究 demo、Office Memory、个人记忆或客户端规则；未提交、推送或对外发布。

当前结论以本文开头的 PR #1 补修验证状态为准。后续各节中的通过结果是对应阶段的历史记录，不能替代修订后源码或真实客户端行为验收。
