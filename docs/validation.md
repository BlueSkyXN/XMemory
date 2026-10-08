# XMemory 验证报告

当前版本：**1.1.0**。核对日期：2026-10-08。正式文件格式仍为 `xmemory/v1`。研究 demo 不计入正式版本线。

本文保留各开发阶段的本地验证记录，下文“未提交／未发布”等表述对应各阶段的记录时点。Git 提交、PR 与 CI 的当前状态以 GitHub 为准。仓库自动检查由 `.github/workflows/validate.yml` 运行，覆盖包装、单元测试和分发包构建，不替代真实客户端与 Agent 行为验收。

## 1.1.0 本地修订 r2：失败恢复与未处理事件

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
- 当前 26 个行为场景、长期经验质量和搜索命中率尚未由新会话的独立执行验证。
- 不提供后台采集、Hook 程序、调度器、客户端数据库适配器、并发锁、事务、同步或组织权限。
- 默认用户级集中根为 `~/.agents/memory/`。已配置其他集中根的用户不会被自动迁移；无权访问时不回退到项目内另存一套。
- Office Memory 迁移按设计延后到试点之后。未改研究 demo、Office Memory、个人记忆或客户端规则；未提交、推送或对外发布。

当前结论以本文开头的本地修订 r2 验证状态为准。后续各节中的通过结果是对应阶段的历史记录，不能替代修订后源码或真实客户端行为验收。
