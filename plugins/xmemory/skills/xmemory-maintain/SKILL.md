---
name: xmemory-maintain
description: "维护 XMemory 时使用：查看提取任务与整合状态、只读校验记忆库、忘记某个会话（删除其全部输入并留撤回标识）、处理中断或卡住的整合与失败任务、状态库丢失后重建。"
---

# XMemory 维护

命令和共同规则见 [xmemory 工具](../xmemory/SKILL.md)。下文 `XM` 指 `"$SKILL_DIR/../xmemory/scripts/xmemory.py"`。

## 状态与检查

```bash
python3 "$XM" status   # 各项目任务状态、待整合输入、整合锁
python3 "$XM" check    # 只读：登记与文件是否一致、账本、链接、疑似密钥、中断的整合、过期租约、失败任务、读取不完整的会话
```

`check` 只报告，不自动修复。发现“输入文件被手工改动”“运行时生成的文件被改动”时，不要再改那个文件，向用户说明。提示“状态库落后于记忆文件”表示上次写操作中断，任一写命令（如 `scan`）会先自动对账，之后再 `check`。

## 忘记

用户明确要求忘记某个会话时：

```bash
python3 "$XM" forget --session <session_ref> --reason "<原因>"
```

运行时先把撤回记入 `ledger/forgotten.jsonl`，再删除该会话的全部会话摘要、重新生成时间线；以后清点和导入都不再收录，状态库丢失重建后也一样。随后对受影响的范围运行整合（`xmemory-consolidate`；`status` 的 `unconsolidated_inputs` 会列出），删除只由这些输入支撑的内容。说明边界：这只清除本记忆库的内容，不删除客户端原件、用户自己的备份（含用户自行建立的 git 历史），以及 `.xmemory/recovered/` 里最多保留 14 天的本机临时备份。

## 中断与失败

- `status` 显示整合锁但没有人在整合：确认是本机中断的整合时，用 `consolidate abort <ID>` 恢复到整合前；不处理也可以，租约过期后下一次 `consolidate begin` 会自动恢复再开始。被替换的版本备份在 `.xmemory/recovered/`。
- 任务状态为 `failed`（失败或租约过期满三次，`check` 会提示）：读 `.xmemory/tasks/<任务ID>/input.md` 看原因，能处理就 `retry <任务ID>`（或 `retry --failed` 全部重试，次数清零），不能处理就 `skip <任务ID> --reason <原因>`。
- 某个会话内容在清点后变化，运行时会把任务标为失效：重新 `scan` 即可。
- 会话读取不完整（`check` 会提示）：运行时不会因此删除或替换已有摘要。来源修好后运行 `scan --force` 重读。

## 状态库丢失或不一致

`.xmemory/state.sqlite` 只是索引和任务状态，事实都在记忆文件和 `ledger/` 里。状态库丢失（例如只恢复了记忆文件）、或提示 library_id 不一致时，所有命令都会拒绝运行并提示：

```bash
python3 "$XM" rebuild   # 旧状态库改名保留；输入登记、整合进度、撤回、已完成的提取任务从文件恢复
python3 "$XM" scan      # 待处理任务和租约不恢复，重新清点
```

备份记忆库时备份整个记忆根即可，`.xmemory/` 可以不备份。

## 扩展回填

把 `config.toml` 的 `backfill_days` 调大，或运行 `scan --days N`，再运行一轮管线（`xmemory-run`）。已经扫描过的会话也会补切新窗口内更早的日期，不需要 `--force`。
