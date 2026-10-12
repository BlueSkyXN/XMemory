---
name: xmemory-extract
description: "XMemory 管线的提取阶段：清点各客户端会话、只读导入 Codex 逐会话记忆，并逐个领取“会话 × 日期”提取任务、读输入、写会话摘要与原始记忆（JSON）、提交给运行时校验。只要做提取、或回填更早的历史时使用；完整一轮请用 xmemory-run。"
---

# XMemory 提取

命令和共同规则见 [xmemory 工具](../xmemory/SKILL.md)。下文 `XM` 指 `"$SKILL_DIR/../xmemory/scripts/xmemory.py"`。

## 1. 清点与导入

```bash
python3 "$XM" scan            # 默认最近 backfill_days 天；--days N 覆盖；--force 重新切分
python3 "$XM" import codex    # 只读导入 Codex 已提取的逐会话记忆（V1、V2 两个记忆根）
```

- `scan` 只为已登记、已启用项目里的会话生成任务；仍在活跃（未过静默期）的会话下次再处理；子代理会话跳过。
- `scan` 的 `partial_sessions` 是读取时有内容被跳过的会话：运行时只新增任务，不删除也不替换已有摘要；`errors` 是读取失败的会话，下次会重试；`held_jobs` 是因读取不完整而暂不重新提取的任务。三者不为空时如实报告。
- 回填更早的历史：`scan --days N` 或调大 `backfill_days`，已扫描过的会话也会补切窗口内更早的日期。
- `import codex` 的结果：`not_extracted_by_codex` 是窗口内两版 Codex 记忆都没有的主会话数，本版不自行提取，向用户报告即可；`summary_only`、`truncated` 是只有摘要、被 Codex 截断的会话数；`warnings` 不为空时（根缺失、格式认不出、V1 停更、出现新版本目录）原样告诉用户。

## 2. 逐个提取

循环，直到没有任务或用户给的数量用完：

1. `python3 "$XM" next --client <客户端>`：返回任务 ID、本次租约 `lease`、`input` 文件、`input_chars`、`output` 路径，以及现成的 `submit`、`release` 命令。
2. 按 [提取方法](./references/extract.md) 完整读 `input`（较长时分段读，读到最后一行“输入结束”）。
3. 把结果 JSON 写进 `output`：`{"slug": "...", "summary": "...", "raw_memory": "..."}`；不值得记就三个字段都写空字符串。
4. 原样执行 `next` 返回的 `submit` 命令（形如 `python3 "$XM" submit <任务ID> --lease <租约> --client <客户端>`）。校验不通过会说明原因，修改 `output` 后再提交。报“租约不匹配”说明任务已被别处接管，放弃这一份，重新 `next`。
5. 做不完：`release <任务ID> --lease <租约> --reason <原因>`（计一次失败，满三次转为 failed）；内容无法使用：加 `--skip`。

每个任务都是一个会话在一天里的内容。不要合并多个任务，不要跳过 `input` 的后半部分。

## 3. 回报

报告：清点结果（新任务、变化任务、作废任务）、导入数、完成的任务数（有内容 / 无可记）、放回或跳过的任务和原因、剩余待处理数（`status`）。提取完成不等于记忆已更新，还需要整合（`xmemory-consolidate`）。
