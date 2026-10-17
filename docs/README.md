# 文档导航

本导航对应 XMemory **1.6.1**、Client Readers **0.2.1**，记忆文件格式为 `xmemory/v1.5`。从[项目首页](../README.md)了解整体用途，再按当前任务选择下面的文档。

## 安装与使用

| 你要做什么 | 阅读位置 |
|---|---|
| 选择下载包、安装或升级 | [安装包说明](release-install.md) |
| 设置记忆根、时区、来源和项目 | [安装与首次使用](../plugins/xmemory/docs/install.md) |
| 更新、查阅、记笔记、纠正或遗忘 | [使用指南](../plugins/xmemory/docs/usage.md) |
| 读懂 `status`、处理常见问题 | [使用指南：状态与排障](../plugins/xmemory/docs/usage.md#读懂-status) |
| 单独查会话或原生记忆 | [Client Readers 命令与示例](../plugins/client-readers/README.md) |
| 理解对象依赖、联合查阅与职责 | [设计说明](../plugins/xmemory/docs/design.md) |

文档中的图使用 Markdown 内嵌 Mermaid。支持 Mermaid 的阅读器会显示流程图；纯文本阅读器可直接查看图源与旁边的表格说明。

## 格式与技能参考

| 参考 | 说明 |
|---|---|
| [八个 XMemory 技能入口](../plugins/xmemory/skills/xmemory/SKILL.md) | Agent 执行时的共同规则及任务分流 |
| [目录、配置与字段](../plugins/xmemory/skills/xmemory/references/format.md) | 路径、frontmatter、会话身份、来源链接与兼容约定 |
| [六类对象工序](../plugins/xmemory/skills/xmemory/references/objects.md) | 每类对象的来源、更新条件与完成结果 |
| [status 输出契约](../plugins/xmemory/skills/xmemory/references/status.md) | JSON 字段、assessment 与 issue 含义 |
| [来源总览](../plugins/xmemory/skills/xmemory/references/sources.md) | 各客户端及文件来源的查找线索 |
| [Codex 来源](../plugins/xmemory/skills/xmemory/references/sources-codex.md) | V1/V2、自动化、Skysight 与子代理材料 |
| [ZCode 来源](../plugins/xmemory/skills/xmemory/references/sources-zcode.md) | 项目目录映射、主题来源与会话引用 |
| [整理示例](../plugins/xmemory/skills/xmemory/references/curation-example.md) | 从虚构材料提取有条件、有出处的记忆 |
| [会话读取契约](../tools/client_readers/contract-sessions.md) | 标识、分页、快照、工具记录与覆盖信息 |
| [原生记忆与项目契约](../tools/client_readers/contract-memory.md) | 角色、归属、文件关系、分页与运行环境 |

模板保存在 [`plugins/xmemory/skills/xmemory/templates/`](../plugins/xmemory/skills/xmemory/templates/)。使用时替换路径、来源、时间与项目占位；模板日期仅说明格式。

## 开发、版本与证据

- [开发指南](development.md)：源码所有权、同步副本、测试、构建与 CI。
- [1.6 版本线](v1.6/README.md)：当前能力与升级影响。
- [1.5 历史版本线](v1.5/README.md)：早期格式与行为变更。
- [验证报告](validation.md)：当前验证摘要和按版本保留的历史证据。
- [读取器验证记录](../plugins/client-readers/docs/validation.md)：随读取器包分发的验证范围。
- [Releases](https://github.com/BlueSkyXN/XMemory/releases)：正式版本及 ZIP、SHA256 附件。

| 评测材料 | 关注点 |
|---|---|
| [v1.5.1](../evals/v1.5.1/README.md) | 基础记忆问答、来源与遗忘 |
| [v1.5.2](../evals/v1.5.2/README.md) | 增量更正、入口过期与只读查阅 |
| [来源适配](../evals/source-adaptation/README.md) | Codex/ZCode 来源与原生记忆共同使用 |
| [v1.5.4](../evals/v1.5.4/README.md) | Skysight、项目归属与活动保留 |
| [v1.6.0](../evals/v1.6.0/README.md) | 孤儿、撞名、同会话、迁移与建库候选 |
| [v1.6.1](../evals/v1.6.1/README.md) | 去提示与转换迁移的补充场景；模型执行状态见验证报告 |
| [v1.7.0](../evals/v1.7.0/README.md) | 自然请求、冷启动与规模变体、补全覆盖、共享日文件与主题保护、短笔记 |

评测 README 定义输入、运行方法和判据。是否执行、执行次数及结果以验证记录为准。
