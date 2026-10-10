# XMemory

**跨客户端的记忆中心：五个技能把各客户端的记忆和对话，加工成一个按项目、按时间组织的集中记忆库。**

当前版本 **1.2.0**：用户级 `~/.agents/memory/` 集中库，分常驻层（画像、意识、主记忆）、主题与每日层、足迹层；提供读取协议、Hook 模板、定时提示词和首次回填提示词；保留 Claude Code、ZCode、Codex 三端插件与市场包装，文件格式名为 `xmemory/v1`。`local/xmemory/` 只是研究 demo，不属于正式产品版本线。

XMemory 是纯技能、文件式记忆插件。现有 AI 客户端负责执行，Markdown 保存结果，TOML 登记项目和来源。不依赖 Git，不带运行期独立工具、MCP、数据库、Hook 程序、后台任务、锁或额外模型服务。

## 一条流水线，五个技能

```text
各客户端原生记忆、会话、工作区（只读）
  → 记录 / 采集 → 足迹 daily/<日期>/（一个会话一份，带可回查地址）
  → 整理（一处单写）→ 意识、主记忆、主题、每日记忆、画像
  → 调取：先常驻层，再按需展开，最后回原件
```

| 技能 | 职责 | 写入 |
|---|---|---|
| `xmemory-setup` 设置 | 数据根、项目发现与别名、来源登记、读取协议、Hook、定时与首次回填 | 配置与入口 |
| `xmemory-record` 记录 | 当前对话中的纠正、偏好、决定和交接 | 只新建足迹（可加主题草稿） |
| `xmemory-collect` 采集 | 各客户端原生记忆、指定会话、工作区变化；首次回填 | 只新建足迹；写本批清单与来源进度 |
| `xmemory-curate` 整理 | 每日记忆、意识重写、主记忆与主题、画像、更正与忘记 | 唯一修改记忆正文；定时运行时判断类改动只写成候选 |
| `xmemory-recall` 调取 | 按读取协议检索与工作接续 | 不写 |

```text
~/.agents/memory/
├── config.toml   USER.md   AWARENESS.md   MEMORY.md
├── topics/<主题>.md                 主记忆的子文件
├── daily/YYYY-MM-DD.md              每日记忆
├── daily/YYYY-MM-DD/<时刻>-….md     足迹（按事件日期）
├── projects/<项目名>/               项目记忆，项目名等于平台项目根目录名
└── state/                           来源进度、采集清单、整理记录、意识副本、撤回标识
```

同一台机器上的客户端共用该用户的记忆根；多台机器使用**同一逻辑记忆库**，各机器默认位置为 **`~/.agents/memory/`**，通过用户选择的同步方式保持一致。项目记忆位于库内 `projects/<项目名>/`，同时登记各客户端对该项目的别名（ZCode 的 slug、Claude 和 Qoder 的路径编码、Codex 的 cwd），不分散存到各工作区，也不需要项目软链接。

采集先写逐项清单，核对后才推进来源进度；整理按“主题 → 主记忆、意识 → 每日记忆 → 回读核对 → 整理记录”的顺序写，意识每次整篇重写（常规改写 30%–70%），写后核对关键信息保全、已有条目损失和日期绝对化。失败时停止当前范围，重试只补缺失步骤。

Office Memory（此前的自有单项目实践）后续迁入集中库并停用旧流程；1.2.0 继承它的整理判断，并扩展到跨客户端、跨项目、时间轴和后台运行，差异见 [设计](plugins/xmemory/docs/design.md)。完整对照见 [需求覆盖](plugins/xmemory/docs/requirements.md)。

## 三端插件与市场

```text
.claude-plugin/marketplace.json       Claude 市场，根为本仓库
.agents/plugins/marketplace.json      Codex 市场，根为本仓库
plugins/
├── marketplace.json                 ZCode 市场，根为 plugins/
└── xmemory/
    ├── plugin.json                  Codex/Agent Plugins 清单
    ├── .claude-plugin/plugin.json    Claude 清单
    ├── .zcode-plugin/plugin.json     ZCode 清单
    ├── skills/                      五个自包含技能
    ├── references/                  共用文档源
    ├── templates/                   共用模板源
    ├── integrations/                读取协议、Hook、定时与首次回填提示词
    ├── examples/                    虚构闭环示例
    └── docs/                        设计、来源、安装、验收
```

每个正式技能的配套文件均在其自身目录内，没有跨目录资源依赖。开发工具维护静态副本一致性，不进入插件载荷。

| 客户端 | 添加的实际市场根 | 插件 ID |
|---|---|---|
| ZCode | 本仓库 `plugins/` | `xmemory@xmemory` |
| Claude Code | 本仓库根 | `xmemory@xmemory-claude` |
| Codex | 本仓库根 | `xmemory@xmemory-codex` |

[三端安装说明](plugins/xmemory/docs/install.md) 包含真实命令、版本边界和接入步骤。创建市场清单不等于注册或安装。独立技能包仍可用于上述客户端和 Qoder/QoderWork；同一客户端不要同时安装重复入口。

## 设计与验证

借鉴 Codex 的逐会话提取与单写者合并、QoderWork 的意识与反思、ZCode 和 Claude Code 的索引加主题、OpenClaw 的日记与有门槛的晋升、腾讯候选的四层粒度、Devin 与 AMR 的入口结构、OMPI 工作草案的生效时间与墓碑理念，以及 Office Memory 的整理判断。原生后台能力不会自动成为插件功能。

- [设计](plugins/xmemory/docs/design.md)
- [产品实现与官方规范依据](plugins/xmemory/docs/design-sources.md)
- [研究 demo 与已有资料](plugins/xmemory/docs/existing-data.md)
- [原始需求覆盖](plugins/xmemory/docs/requirements.md)
- [验收标准](plugins/xmemory/docs/acceptance.md)
- [本次验证结果](docs/validation.md)
- [分发包说明](docs/release-install.md)

## 开发检查与构建

独立的 [Conversation Readers 扩展](plugins/conversation-readers/README.md) 提供 Codex、Claude Code、ZCode、Qoder CN、WorkBuddy 各一个 `Skill + scripts`，用于对话列表、检索、按 ID 读取和分页展开。它需要 Python 3.11+，独立检查与打包，不自动写入记忆，也未加入现有 XMemory 市场。下述命令仍针对原记忆插件；扩展命令见其说明。

Python 3.11+ 仅供维护仓库使用，不是插件运行依赖。

```bash
python3 -B tools/sync_skill_resources.py --apply
python3 -B tools/check_package.py
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
python3 -B tools/build_release.py
```

修改共用文档后同步静态技能资源，检查器会拒绝漂移。构建输出三端完整包、五技能包和 SHA-256；已有同名归档拒绝覆盖，可指定新 `--output`。`tools/`、`tests/`、研究 demo 和个人资料不进入包。

GitHub Actions 在 PR、`main` 更新和手动触发时，使用 Ubuntu 与 Python 3.11 运行包装检查、全部单元测试和临时目录构建。自动检查不执行真实客户端安装、Agent 行为场景或跨设备同步验收。

## 边界

没有程序级锁、事务、跨设备同步或组织权限；靠“采集只新建、整理单写、写前确认、逐项清单”降低风险。原生来源与现有 Office Memory 只读；不自动采集完整历史或改写业务 Skill。可追溯摘要不等于防篡改审计，记忆增多不保证模型更准确。

许可证：[GNU GPL v3](LICENSE)。
