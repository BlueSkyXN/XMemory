# 库结构与文件格式（xmemory/v1.4）

```text
~/.agents/memory/
├── .xmemory/state.sqlite      会话清单、提取任务、租约、整合锁、输入登记（可用 rebuild 从文件重建，不必备份）
├── .xmemory/recovered/        被恢复或覆盖前的旧版本，本机临时备份，保留 14 天
├── ledger/state.json          库标识与写入代数，用来发现中断的写操作
├── ledger/forgotten.jsonl     撤回记录（forget），只增不减
├── ledger/consolidated/<范围>.json
│                              各范围已整合的输入及其版本；状态库丢失后据此恢复整合进度
├── config.toml                格式名、时区、回填天数、客户端开关、来源路径、来源限制、项目登记
├── memory_summary.md          全局入口：用户画像与偏好、各项目入口
├── sessions/<客户端>/<年-月>/<日期>-<slug>-<会话ID尾8位>[-pN].md
│                              逐会话摘要（Phase 1 产物，含原始记忆）
├── inbox/notes/<时间>-<slug>-<随机>.md
│                              当场记下的笔记，下次整合吸收
├── projects/<项目名>/
│   ├── AWARENESS.md           当前状态：五节，整合时整篇重写
│   ├── MEMORY.md              项目手册：任务组
│   ├── topics/<key>.md        有稳定 key 的条目（如 Office Memory 导入）
│   ├── daily/<日期>.md        某天的叙述（可选；Office Memory 导入的日期记录也在这里）
│   └── timeline/<年-月>.md    按日期列出会话摘要，运行时生成
└── personal/                  不属于任何项目的内容，结构同上
```

## 会话摘要

frontmatter 全部由运行时写入：`session_ref`、`client`、`project`、`cwd`、`day`、`part`、`event_window`、`source`、`origin`（`xmemory-extract` 或 `codex-memory`），以及提取或导入的时间和执行客户端；提取的摘要另有任务 `job` 和内容指纹 `fingerprint`，状态库重建时据此恢复已完成的任务。导入的 Codex 摘要另有 `codex_memory`（`v1` 或 `v2`）和 `codex_summary_file`，被 Codex 截断时有 `codex_truncated_chars`。正文有两节：`## 会话摘要`、`## 原始记忆`。

## 项目归属

由运行时判定，依次是：

1. `config.toml` 中项目 `roots` 的最长目录匹配；
2. 会话目录所在 git 仓库的主仓库根（linked worktree 归主仓库；直接读 `.git`，不调用 git）再匹配一次；
3. 家目录本身归 personal；
4. 其余记为 `unassigned`，不生成任务。

只有登记并启用的项目会生成提取任务。

## 时间

全部由运行时写入：日期按 `config.toml` 的 `timezone` 换算；跨天会话按本地日期切成多个任务；整合完成时在改动过的产物开头写一行 `<!-- xmemory: updated … -->`，主题文件则更新 frontmatter 的 `updated`。

## 容量

存储不设上限，内容按可检索性组织。只有 `memory_summary.md` 和各项目的 `AWARENESS.md` 是“建议先读”的入口，应保持紧凑。不为了容量删除条件、来源或未决问题。

## 写入与恢复

不需要 git。运行时的每次写操作是一个写事务：改文件前先把 `ledger/state.json` 的写入代数加一，文件用“写临时文件再改名”原子替换，最后状态库记下同一代数。中途失败或进程被杀，两边代数不一致，下一个写命令开始时按文件对账：已写出的摘要登记为完成，撤回账本里的会话补删，同一任务的重复摘要移到 `recovered/`。整合在 `begin` 时给本范围产物留一份副本，`abort` 或中断后的下一次 `begin` 据此恢复到整合前。

记忆根可以用任何方式备份（Time Machine、同步盘、自建 git 仓库等），运行时不依赖也不操作这些工具。
