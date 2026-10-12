---
name: xmemory-setup
description: "设置 XMemory 时使用：在 ~/.agents/memory 建库、登记或启停项目、逐字导入 Office Memory、生成并合并“XMemory 可用”的告知段落到各客户端用户级规则文件、准备定时运行提示词。只改配置和入口，不提取会话。"
---

# XMemory 设置

命令和共同规则见 [xmemory 工具](../xmemory/SKILL.md)。下文 `XM` 指 `"$SKILL_DIR/../xmemory/scripts/xmemory.py"`。

## 建库

```bash
python3 "$XM" init --timezone <IANA 时区，如 Asia/Shanghai>
```

未指定时区时用本机时区。目标目录已存在且不是 `xmemory/v1.4` 库时，运行时会拒绝；不要替用户移动或删除旧目录，先说明情况、等用户决定。

## 登记项目

```bash
python3 "$XM" project add <项目名> --path <项目根>   # 可多次 --path
python3 "$XM" project list
python3 "$XM" project disable <项目名>
```

- 项目名用平台项目根目录名，原样保留（可含中文）。
- 只有登记且启用的项目会生成提取任务；会话按工作目录归属，linked worktree 归主仓库。
- 回填深度由 `config.toml` 的 `backfill_days` 决定（默认 7 天）。
- 客户端开关在 `[clients]`：`extract`、`import`、`off`；`[restrict]` 可限制某来源只在指定客户端处理，默认不限制。

## 导入 Office Memory

```bash
python3 "$XM" import office-memory --project <项目名> --path <项目根>/.agents
```

长期条目转为 `topics/<key>.md`，日期记录转为 `daily/`，意识转为 `AWARENESS.md`，正文逐字保留。目标已存在时会拒绝，确认后才加 `--force`。

## 告知各客户端

```bash
python3 "$XM" notice
```

只有用户明确要求时，才把输出的段落合并进各客户端的用户级规则文件，例如 Codex 的全局 AGENTS.md、Claude Code 的全局 CLAUDE.md、ZCode 的全局 AGENTS.md。合并前先读现有内容，不覆盖已有规则，不重复添加；已有旧版 XMemory 段落时替换它，并告诉用户改了哪些文件。

## 定时运行

XMemory 没有后台进程。需要定期运行时，把 [定时提示词](./templates/automation-prompt.md) 里的占位填好，交给用户挂到客户端自己的自动化功能上。不要替用户创建定时任务。

## 回报

报告记忆根、时区、登记的项目、导入结果、改动了哪些规则文件；未做的步骤写明原因。
