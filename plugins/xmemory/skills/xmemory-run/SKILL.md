---
name: xmemory-run
description: "运行一轮完整的 XMemory 记忆管线时使用：用户说“更新记忆”“跑一下 XMemory”“整理记忆”，或定时任务的提示词要求运行一轮。按顺序完成清点、导入、逐会话提取、各范围整合和校验，并汇报结果。"
---

# XMemory 运行一轮

命令和共同规则见 [xmemory 工具](../xmemory/SKILL.md)。下文 `XM` 指 `"$SKILL_DIR/../xmemory/scripts/xmemory.py"`。

## 步骤

1. `python3 "$XM" status`：确认记忆库存在。报“状态库不存在”时先 `rebuild`（见 [xmemory-maintain](../xmemory-maintain/SKILL.md)）。如果有未过期的整合锁，本轮只做提取，不做整合。
2. 提取：按 [xmemory-extract](../xmemory-extract/SKILL.md) 执行 `scan`、`import codex`，然后循环 `next` → 提取 → `submit`。用户或定时提示词给了本轮任务上限时，到上限就停；没给就处理完全部待处理任务。
3. 整合：对 `status` 中 `unconsolidated_inputs` 不为零的每个范围（新增、修改、删除都计入），按 [xmemory-consolidate](../xmemory-consolidate/SKILL.md) 执行 `consolidate begin` → 修改产物 → `consolidate finish`，有剩余批次就继续。
4. `python3 "$XM" check`。

## 中断与失败

- 单个提取任务失败：用 `next` 返回的 `release` 命令放回，继续下一个。
- 整合校验失败且无法修正：`consolidate abort`，在汇报里说明原因。
- 运行时报“另一处正在整合”：跳过整合，只汇报。

## 汇报

用三五行说明：处理了多少提取任务（有内容 / 无可记）、`scan` 的读取不完整与读取失败（有就列出）、导入了多少 Codex 会话、Codex 尚未覆盖的会话数、更新了哪些范围、还剩多少待处理、`check` 有无错误。`import codex` 有 `warnings` 时原样列出。
