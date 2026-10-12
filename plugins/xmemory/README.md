# XMemory

跨客户端记忆库：把各客户端的会话逐个提炼成摘要，再整合成按项目、按时间组织的项目意识和项目手册，任何客户端都能查阅。

当前版本 **1.4.1**，文件格式 `xmemory/v1.4`。

## 怎么工作

```text
各客户端会话（只读）──清点、按“会话 × 本地日期”切分──▶ 提取任务
Codex 已有逐会话记忆（只读）──导入──────────────────▶ 会话摘要
                                  │
           当前代理逐个提取，运行时校验后写入 sessions/
                                  │
           单写者整合（加锁、产物副本、校验、可放弃恢复）
                                  ▼
   memory_summary.md、projects/<项目>/AWARENESS.md、MEMORY.md、topics/、timeline/
```

- **代码管机械，模型管语义**：清点、项目归属、日期切分、任务认领与租约、时间戳、原子写入、状态账本与中断恢复、校验都由内置运行时完成；逐会话提取和整合由执行技能的客户端代理完成，输出经运行时校验才落盘。
- **一手输入**：从原始会话提取，用户消息是主要证据；Codex 已从原始会话提取过的逐会话记忆直接复用；Office Memory 可逐字转录。
- **一个工具，多个技能**：运行时 CLI 只有一份，放在 `xmemory` 技能里；查阅、记一条、提取、整合、运行一轮、设置、维护各由一个技能负责，都调用这同一个 CLI。任何客户端、任何目录执行，任务、模板和校验都相同；记忆根固定在 `~/.agents/memory/`。
- **不常驻**：没有后台进程。需要定时，就在 Codex 自动化、ZCode 定时任务等客户端功能里挂一条提示词（`xmemory-setup/templates/automation-prompt.md`）。
- **不强制读写**：只在各客户端的用户级规则文件里告知 XMemory 可用（`notice` 生成告知段落），什么时候查、什么时候记由 AI 自己判断。
- **存储不设上限**：内容按可检索性组织；只有 `memory_summary.md` 和项目 `AWARENESS.md` 作为入口保持紧凑。

## 组成

```text
skills/
├── xmemory/               工具本体：运行时 CLI（scripts/）、命令总表、共同规则、库结构、告知段落模板
├── xmemory-recall/        查阅记忆（只读），必要时回到原会话
├── xmemory-note/          当场记一条
├── xmemory-run/           运行一轮完整管线（“更新记忆”、定时任务）
├── xmemory-extract/       清点会话、导入 Codex 记忆、逐会话提取（含提取方法）
├── xmemory-consolidate/   单写者整合（含整合方法与产物格式）
├── xmemory-setup/         建库、登记项目、导入 Office Memory、告知、定时提示词
└── xmemory-maintain/      状态、检查、忘记、处理中断
```

运行时需要 Python 3.9+（macOS 自带的 `python3` 即可），不需要 git；`scripts/reader_runtime.py` 与 Conversation Readers 同源。

## 快速开始

```bash
S=<插件>/skills/xmemory/scripts/xmemory.py
python3 "$S" init --timezone Asia/Shanghai
python3 "$S" project add <项目名> --path <项目根>
python3 "$S" scan && python3 "$S" import codex
python3 "$S" next --client codex      # 领取一个提取任务；按 xmemory-extract 技能的提取方法处理后执行返回的 submit 命令
```

完整流程见 [设计](docs/design.md) 与 [安装](docs/install.md)。

## 边界

- 默认只提取 ZCode 会话、只读导入 Codex 记忆；其他客户端可在 `config.toml` 的 `[clients]` 开启（需要对应读取器支持）。
- 会话正文由执行技能的客户端模型处理；`[restrict]` 可限制某来源只在指定客户端处理，默认不限制。
- 1.4 只支持单机，多设备同步以后再加。记忆根可以用任何方式备份；`.xmemory/` 状态库可用 `rebuild` 从记忆文件重建，不必备份。
- 不修改任何客户端的原生数据，不保存原始会话副本、密钥或令牌。

许可证：GNU GPL v3。
