---
name: xmemory-setup
description: "设置 XMemory 的记忆根、时区、来源选择和项目映射，按模板建库，准备客户端告知与定时提示词。"
---

# 设置 XMemory

先读 [共同规则](../xmemory/SKILL.md) 和 [配置与格式](../xmemory/references/format.md)。建库用普通文件工具，不调用旧版 init、project、notice 或导入命令。

## 建库与来源

1. 确认目标根、时区、用户选定的来源与项目。能从当前请求和环境确定的直接使用；未指定的来源不要自动开启。
2. 新空目录按 [配置模板](../xmemory/templates/config.toml) 创建配置与目录。对象在有内容时创建，不预造空的每日文件。
3. 已有 `xmemory/v1.5` 库时按现有配置补充；已有 1.4 或其他库时，保持原目录，说明新格式直接重建，先确定新的空目录或旧库归档位置，不静默覆盖。
4. 根据 [来源参考](../xmemory/references/sources.md) 核实用户选择的路径。项目映射写用户确认的项目名与实际根路径；worktree 或别名可加入同一项目的 roots。
5. 初次回填范围由用户目标或已选日期决定。未指定且历史量大时先说明拟处理范围；不把“最新一份记录”当作已回填全部历史。

## 告知与调度

- 按 [告知模板](../xmemory/templates/agents-notice.md) 填实际记忆根。只有用户要求集成到客户端时才合并到相应规则文件，保留其他内容；不自动注入记忆正文。
- 按 [定时提示词](../xmemory/templates/automation-prompt.md) 填范围，交给客户端自动化。XMemory 不创建后台服务；用户已要求创建客户端定时任务时，可用该客户端的能力完成。
- Conversation Readers 可另装；设置 XMemory 不代表授权安装或启用读取器。

回报实际创建或修改的配置、项目、选定来源与告知文件。配置完成不代表已读过外部来源或生成记忆。
