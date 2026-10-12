---
name: xmemory-consolidate
description: "XMemory 管线的整合阶段：在全局锁下，把某个项目（或 personal）新增、修改、删除的会话摘要和笔记并入项目意识 AWARENESS.md、项目手册 MEMORY.md、主题和全局摘要，再交运行时校验并写入。只要做整合时使用；完整一轮请用 xmemory-run。"
---

# XMemory 整合

命令和共同规则见 [xmemory 工具](../xmemory/SKILL.md)。下文 `XM` 指 `"$SKILL_DIR/../xmemory/scripts/xmemory.py"`。同一时间只有一处在整合。

## 步骤

1. 开始：

   ```bash
   python3 "$XM" consolidate begin --scope <项目名|personal> --client <客户端> [--max-inputs 12]
   ```

   返回 `changed: false` 表示本范围没有新输入，结束。否则得到整合 ID、`input` 文件、允许改动的产物范围，以及 `remaining_after_this_batch`。`recovered_interrupted` 不为空表示上一次整合中断、租约已过，运行时已把它的半成品恢复到整合前（旧版本在返回的 `backup` 目录），在汇报里说明。
2. 按 [整合方法](./references/consolidate.md) 读 `input` 和现有产物，修改：
   - `projects/<项目>/AWARENESS.md`（整篇重写，五节固定）；
   - `projects/<项目>/MEMORY.md`（任务组手册）；
   - 必要时 `projects/<项目>/topics/`、`projects/<项目>/daily/`；
   - 全局 `memory_summary.md` 中与本项目有关的部分。

   personal 范围对应 `personal/`。
3. 完成：`python3 "$XM" consolidate finish <ID>`。
   - 校验失败会列出原因（越界改动、缺小节、旧待办没有着落、链接无效、疑似密钥），修正后再 finish；
   - 确实无法完成：`python3 "$XM" consolidate abort <ID>`，产物恢复到整合前。
4. `remaining_after_this_batch` 大于 0 时，finish 后继续下一批。

## 不要做

- 不改 `sessions/`、`inbox/`、`timeline/`（运行时生成）和 `config.toml`。
- 不写时间戳；finish 时运行时会写入。
- 不在另一处整合进行中时强行开始；`begin` 报锁冲突就等它结束或租约过期。

## 回报

报告整合的范围和批次数、意识里当前认识和待处理的主要变化、新增或改动的任务组、仍剩余的输入数，以及校验结果。
