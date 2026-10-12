# XMemory

**跨客户端记忆库：把各客户端的会话逐个提炼，整合成按项目、按时间组织的项目意识和项目手册，任何客户端都能查阅。**

当前版本 **1.4.1**，文件格式 `xmemory/v1.4`。1.4 是一次重做：参照 Codex 原生记忆的两阶段管线，机械工作交给内置运行时，模型只做逐会话提取和单写者整合。1.x 旧库（`xmemory/v1`）不兼容，需要归档后重建。

下一版的 [1.5 技能稿](docs/v1.5/README.md) 已进入审阅：以技能定义六类记忆对象的独立工序，程序计划只保留只读 `status`。该稿尚未接入插件，下面的安装与命令仍对应 1.4.1。

## 怎么工作

```text
各客户端会话（只读）→ scan：代码判定项目、按本地日期切分 → 提取任务
Codex 已有逐会话记忆（只读）→ import codex
            ↓
next / submit：执行技能的代理逐个提取（带租约），运行时校验、脱敏、写入 sessions/
            ↓
consolidate：加锁的单写者整合 → memory_summary.md、projects/<项目>/AWARENESS.md、MEMORY.md、topics/、timeline/
            ↓
各客户端通过用户级规则文件得知 XMemory 可用，由 AI 自己决定何时查阅
```

| 由代码完成 | 由执行技能的代理完成 |
|---|---|
| 清点会话、项目归属（含 worktree）、按本地日期切分、内容指纹 | 读一个会话一天的消息，写会话摘要与原始记忆（JSON） |
| 任务认领与租约、失败计次与重试、整合锁 | 把新增、修改、删除的输入并入项目意识、手册与全局摘要 |
| 时间戳、会话 ID、来源指针、时间线；原子写入、状态账本、中断恢复与 rebuild（不需要 git） | 按调取方法查阅记忆 |
| 校验：越界改动、意识五节、旧待办着落、链接、疑似密钥 | |

设计说明见 [设计](plugins/xmemory/docs/design.md)，安装见 [安装](plugins/xmemory/docs/install.md)。

## 仓库结构

```text
.claude-plugin/marketplace.json       Claude 市场，根为本仓库
.agents/plugins/marketplace.json      Codex 市场，根为本仓库
plugins/
├── marketplace.json                  ZCode 市场，根为 plugins/
├── xmemory/                          记忆插件：一个运行时 CLI + 八个技能（查阅、记一条、运行一轮、提取、整合、设置、维护、工具本体）
└── conversation-readers/             会话读取插件：五个客户端各一个只读读取技能
tools/                                仓库检查、同步与构建脚本（不进入插件）
tests/                                单元测试
```

| 客户端 | 添加的市场根 | 插件 ID |
|---|---|---|
| ZCode | 本仓库 `plugins/` | `xmemory@xmemory`、`conversation-readers@xmemory` |
| Claude Code | 本仓库根 | `xmemory@xmemory-claude`、`conversation-readers@xmemory-claude` |
| Codex | 本仓库根 | `xmemory@xmemory-codex`、`conversation-readers@xmemory-codex` |

XMemory 是“一个工具、多个技能”：运行时 CLI 只有一份，放在 `xmemory` 技能里，其余七个技能各管一类活并调用它。运行时内置会话读取（与 Conversation Readers 同源，由同步脚本保持一致），不依赖另装读取插件。

## 开发检查与构建

开发检查与构建需要 Python 3.11+ 和 git（测试用它构造 worktree 夹具）；技能运行时只需 Python 3.9+，不需要 git。

```bash
python3 -B tools/sync_conversation_readers.py --apply   # 同步读取运行时到各读取技能与 XMemory 技能
python3 -B tools/check_package.py
python3 -B tools/build_conversation_readers.py --check
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
python3 -B tools/build_release.py --output dist/<新目录>
```

构建输出三端市场完整包（含两个插件）、XMemory 技能包、Conversation Readers 技能包及各自的 SHA-256；已有同名归档拒绝覆盖。GitHub Actions 在 PR、`main` 更新和手动触发时运行同样的检查、测试和构建；自动检查不执行真实客户端安装或真实会话提取。

## 边界

- 1.4 默认只提取 ZCode 会话、只读导入 Codex 逐会话记忆；其他客户端可在 `config.toml` 开启。
- 会话正文由执行技能的客户端模型处理；可按来源限制，默认不限制。
- 只支持单机；不修改任何客户端原生数据；不保存原始会话副本、密钥或令牌。
- 运行时校验结构、指针、时间和待办着落；记忆内容是否准确，需要评测和人工抽查。

验证记录见 [验证报告](docs/validation.md)，分发包说明见 [安装包](docs/release-install.md)。

许可证：[GNU GPL v3](LICENSE)。
