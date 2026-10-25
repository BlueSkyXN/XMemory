# 安装与首次使用

XMemory 1.8.0 提供三个 Skill；Client Readers 0.2.1 独立可选。基本使用需要宿主能够发现技能、读取和编辑文本文件，并定位当前用户 home。普通 Markdown 任务不需要 Python。

## 安装方式

完整市场包保留三个宿主市场：Codex、Claude Code 使用解压根，ZCode 使用其下的 `plugins/`。插件 ID 为 `xmemory@xmemory-marketplace`，可选读取器为 `client-readers@xmemory-marketplace`。按宿主当前支持的市场安装或更新流程操作。

独立技能包将 `skills/` 下四个目录一起复制到宿主支持的技能目录：三个 `xmemory-动作` 目录包含入口，`xmemory/` 只包含共享参考、模板和可选脚本。共享资源不是第四个 Skill。保留相对位置。

同一客户端选择一种安装方式，避免重复入口。更新旧安装时核对旧的八个入口已被本版三个入口替换，不直接改客户端缓存。先确认新对话能发现 xmemory-update、xmemory-recall、xmemory-note。

## 读取接入

按用户选择，将 [读取告知](../skills/xmemory/templates/agents-notice.md) 合并进宿主的用户指令入口。Skill 可发现并不意味着所有客户端已自动读取记忆；用一个需要历史的新任务检查实际调用。

正式根固定为用户 home 下的 `.agents/memory/`，与当前项目无关。Windows 同样在当前用户 home 定位此相对目录。无需根配置、来源全量清单或预先运行 status。

第一次可以说“整理这些选定材料，保存到 XMemory”。有实际内容才创建笔记、主记忆与入口。若该位置已有旧试验库，先明确旧文件的保留位置或处置，再启用新内容，不自动吸收、覆盖或迁移。

## 可选工具

Client Readers 适配客户端私有存储；无读取器时仍可处理当前上下文、普通文件与导出材料。专有格式无法读取时只报告该来源缺口。

Python 3.9+ 可运行 [只读检查](../skills/xmemory/references/status.md)。程序不采集来源、不写记忆。定时、后台、异步发起由外部宿主安排，多写入任务顺序执行。
