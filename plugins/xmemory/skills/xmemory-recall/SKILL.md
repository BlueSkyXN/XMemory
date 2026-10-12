---
name: xmemory-recall
description: "需要用 XMemory 记忆回答或接续工作时使用：继续上次的任务、查此前的决定和原因、找做法和踩过的坑、确认用户偏好、回看某段时间做了什么。按全局摘要、项目意识、项目手册、会话摘要、原会话的顺序只读查阅，一般 4–6 步内结束。"
---

# XMemory 查阅

只读，不写记忆。命令和共同规则见 [xmemory 工具](../xmemory/SKILL.md)；运行时为 `python3 "$SKILL_DIR/../xmemory/scripts/xmemory.py"`。

自包含的问题（当前时间、翻译、改一句话、与历史无关的改动）不用查。什么时候值得查、要不要现场核实、怎么回答，见 [查阅方法](./references/recall.md)。

## 步骤

记忆根默认 `~/.agents/memory/`。

1. 读 `memory_summary.md`，找到相关项目和关键词。
2. 读 `projects/<项目>/AWARENESS.md`：当前认识、冲突、待处理。
3. 用关键词 `rg -n` 搜 `projects/<项目>/MEMORY.md` 和 `projects/<项目>/topics/`，只读命中的任务组或条目。
4. 需要细节时，读命中条目链接的 `sessions/…` 会话摘要；按日期找事情时看 `projects/<项目>/timeline/<年-月>.md`。
5. 还需要原话或原始证据时，用会话摘要里的 `session_ref` 读原会话：

   ```bash
   python3 "$SKILL_DIR/../xmemory/scripts/xmemory.py" session <session_ref> [--offset N] [--include-tools]
   ```

   本机找不到原会话时，说明“本机找不到这个原件”，用摘要回答并注明截至时间。
6. 没有命中就停止查阅，正常完成任务。

## 回答

- 说明结论来自 XMemory，给出处：记忆根下的相对路径或 `session_ref`。
- 会漂移的事实（分支、版本、部署、数量）据此行动前先核实；没核实就说明可能过时。
- `status` 为待确认、已替代、已撤回的内容，不能去掉限定当作当前事实。
- 没找到时说“在本次查阅范围内没有找到”。
