# XMemory 1.7.0

以技能维护跨客户端 Markdown 记忆。AI 处理选定来源、核对证据并直接编辑文件；只读 `status` 提供库内结构和更新线索。定时调度由客户端负责，Client Readers 可按需要独立安装。

文件格式为 `xmemory/v1.5`，已有 1.5.x 库可以继续使用。当前发布见 [v1.7.0](https://github.com/BlueSkyXN/XMemory/releases/tag/v1.7.0)。

## 从这里开始

1. 按[安装与首次使用](docs/install.md)安装八个技能，选择记忆根、时区、来源和项目。
2. 告诉代理“更新一轮记忆”“补全这个项目的记忆”“只更新这个项目的意识”或“查一下上次的决定”。按用户指定范围选择对象。
3. 问“现在记忆什么情况”查看现状，或按[使用指南](docs/usage.md)核对产物、来源和 `status` 提示。

```bash
python3 -B "/absolute/path/to/xmemory/skills/xmemory/scripts/xmemory.py" --root "/absolute/path/to/memory" status --summary
```

将脚本路径替换为本插件的实际安装位置。程序需要 Python 3.9+ 标准库；默认记忆根为 `~/.agents/memory/`，可用 `--root` 或 `XMEMORY_ROOT` 指定。`status` 只读配置和库内 Markdown；记录与对象的写入由执行技能的 AI 完成。

## 技能与结果

| 技能 | 用途 | 结果 |
|---|---|---|
| [xmemory](skills/xmemory/SKILL.md) | 共同规则、格式与任务入口 | 确定根目录和执行规则 |
| [xmemory-setup](skills/xmemory-setup/SKILL.md) | 设置库、来源、项目与告知 | 配置和初始入口 |
| [xmemory-run](skills/xmemory-run/SKILL.md) | 完成一轮更新或补全：定范围、清点、分批写入 | 记录、相关对象与按来源的完成和剩余报告 |
| [xmemory-extract](skills/xmemory-extract/SKILL.md) | 从选定材料制作记录 | 带来源、日期、归属与覆盖信息的记录 |
| [xmemory-consolidate](skills/xmemory-consolidate/SKILL.md) | 把已有记录整理进任意派生对象 | 日总结、项目总结、意识、画像或全局摘要 |
| [xmemory-recall](skills/xmemory-recall/SKILL.md) | 查历史、接续工作与核对更正 | 带关键来源的回答，保持 XMemory 只读 |
| [xmemory-note](skills/xmemory-note/SKILL.md) | 保存当场新的偏好、决定或纠正 | 三到五行的短笔记，必要时同步相关画像或主题 |
| [xmemory-maintain](skills/xmemory-maintain/SKILL.md) | 检查现状、修正结构或按要求遗忘 | 只读的现状汇报、修复文件，或排除会话并清理其支持关系 |

## 继续阅读

| 文档 | 内容 |
|---|---|
| [使用指南](docs/usage.md) | 常见请求、更新流程、状态与排障 |
| [设计说明](docs/design.md) | 组件职责、对象关系图与联合查阅流程 |
| [目录与格式](skills/xmemory/references/format.md) | `xmemory/v1.5` 配置、字段和来源身份 |
| [对象工序](skills/xmemory/references/objects.md) | 六类对象独立更新的规则 |
| [来源参考](skills/xmemory/references/sources.md) | 有读取器与手工读取时的来源定位 |
| [status 契约](skills/xmemory/references/status.md) | 输出字段、问题类型和检查范围 |

客户端原生记忆继续按原有机制使用和维护。XMemory 的来源开关控制导入范围；联合查阅会应用本库的会话排除配置。库内检查、程序测试和客户端行为的验证范围见[仓库验证报告](https://github.com/BlueSkyXN/XMemory/blob/main/docs/validation.md)。

许可证：[GNU GPL v3](LICENSE)。
