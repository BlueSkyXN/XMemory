# XMemory

跨客户端记忆库：把各客户端的会话逐个提炼成摘要，再整合成按项目、按时间组织的项目意识和项目手册，任何客户端都能查阅。

当前版本 **1.4.0**，文件格式 `xmemory/v1.4`。

## 怎么工作

```text
各客户端会话（只读）──清点、按“会话 × 本地日期”切分──▶ 提取任务
Codex 已有逐会话记忆（只读）──导入──────────────────▶ 会话摘要
                                  │
           当前代理逐个提取，运行时校验后写入 sessions/
                                  │
           单写者整合（加锁、git 基线、校验、可放弃回滚）
                                  ▼
   memory_summary.md、projects/<项目>/AWARENESS.md、MEMORY.md、topics/、timeline/
```

- **代码管机械，模型管语义**：清点、项目归属、日期切分、任务认领与租约、时间戳、文件写入、git 提交、校验都由内置运行时完成；逐会话提取和整合由执行技能的客户端代理完成，输出经运行时校验才落盘。
- **一手输入**：从原始会话提取，用户消息是主要证据；Codex 已从原始会话提取过的逐会话记忆直接复用；Office Memory 可逐字转录。
- **任何客户端效果相同**：一个技能、同一套任务、模板和校验；记忆根固定在 `~/.agents/memory/`，与当前目录无关。
- **不常驻**：没有后台进程。需要定时，就在 Codex 自动化、ZCode 定时任务等客户端功能里挂一条提示词（`templates/automation-prompt.md`）。
- **不强制读写**：只在各客户端的用户级规则文件里告知 XMemory 可用（`notice` 生成告知段落），什么时候查、什么时候记由 AI 自己判断。
- **存储不设上限**：内容按可检索性组织；只有 `memory_summary.md` 和项目 `AWARENESS.md` 作为入口保持紧凑。

## 组成

```text
skills/xmemory/
├── SKILL.md                    何时用、各模式怎么做
├── scripts/xmemory.py          运行时入口（Python 3.11+ 标准库，需要 git）
├── scripts/xmemory_runtime.py
├── scripts/reader_runtime.py   各客户端会话只读读取（与 Conversation Readers 同源）
├── references/                 提取、整合、调取方法与库结构
└── templates/                  告知段落、定时提示词
```

## 快速开始

```bash
S=<技能目录>/scripts/xmemory.py
python3 "$S" init --timezone Asia/Shanghai
python3 "$S" project add <项目名> --path <项目根>
python3 "$S" scan && python3 "$S" import codex
python3 "$S" next --client codex      # 领取一个提取任务，按 references/extract.md 处理后 submit
```

完整流程见 [设计](docs/design.md) 与 [安装](docs/install.md)。

## 边界

- 默认只提取 ZCode 会话、只读导入 Codex 记忆；其他客户端可在 `config.toml` 的 `[clients]` 开启（需要对应读取器支持）。
- 会话正文由执行技能的客户端模型处理；`[restrict]` 可限制某来源只在指定客户端处理，默认不限制。
- 1.4 只支持单机；记忆根是 git 仓库，多设备同步以后再加。
- 不修改任何客户端的原生数据，不保存原始会话副本、密钥或令牌。

许可证：GNU GPL v3。
