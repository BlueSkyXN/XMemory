---
name: xmemory-maintain
description: "维护 XMemory 时使用：查看提取任务与整合状态、只读校验记忆库、忘记某个会话（删除其全部输入并留撤回标识）、处理中断或卡住的整合与失败任务。"
---

# XMemory 维护

命令和共同规则见 [xmemory 工具](../xmemory/SKILL.md)。下文 `XM` 指 `"$SKILL_DIR/../xmemory/scripts/xmemory.py"`。

## 状态与检查

```bash
python3 "$XM" status   # 各项目任务状态、待整合输入、整合锁
python3 "$XM" check    # 只读：状态库与文件是否一致、链接、疑似密钥、未提交改动、过期租约、失败任务
```

`check` 只报告，不自动修复。发现“输入文件被手工改动”时，不要再改那个文件，向用户说明。

## 忘记

用户明确要求忘记某个会话时：

```bash
python3 "$XM" forget --session <session_ref> --reason "<原因>"
```

运行时删除该会话的全部会话摘要并留下撤回标识，以后清点和导入都不再收录。随后对受影响的范围运行整合（`xmemory-consolidate`），删除只由这些输入支撑的内容。说明边界：这只清除本记忆库的内容，不删除客户端原件或外部备份；git 历史里仍有旧版本。

## 中断与失败

- `status` 显示整合锁但没有人在整合：等租约过期后重新开始；确认是本机中断的整合时，用 `consolidate abort <ID>` 恢复。
- 任务失败次数达到上限（`check` 会提示）：读任务的 `input` 看原因，能处理就重新 `scan --force`，不能处理就 `release --skip`。
- 某个会话内容在清点后变化，运行时会把任务标为失效：重新 `scan` 即可。

## 扩展回填

把 `config.toml` 的 `backfill_days` 调大，或运行 `scan --days N`，再运行一轮管线（`xmemory-run`）。
