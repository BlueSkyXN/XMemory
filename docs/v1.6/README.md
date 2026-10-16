# XMemory 1.6 版本线

源码版本为 XMemory 1.6.1 与 Client Readers 0.2.1。文件格式沿用 `xmemory/v1.5`，已有 1.5.x 库无需转换。安装步骤见 [安装与升级](../release-install.md)，各阶段检查结果见 [验证报告](../validation.md)，正式附件见 [Releases](https://github.com/BlueSkyXN/XMemory/releases)。

## 1.6.0：原生记忆与项目候选

- Conversation Readers 改名为 Client Readers，五端统一提供 `projects`、`sessions`、`memory`、`doctor`。升级时先通过客户端移除 `conversation-readers`，再安装 `client-readers@xmemory-marketplace`。
- 原生记忆按角色、项目归属、重复文件、同会话和迁移关系返回；XMemory 按来源关系采集，保留归属未定与读取缺口。
- Claude 指定 store 或文件时只扫描对应会话目录，并支持路径别名；项目总览提供 `parent` 与 `children`。
- Codex 压缩会话按已有 zstd 后端顺序回退，支持多 frame；缺失后端时按根目录汇总未读数。输出使用 UTF-8，项目筛选统一路径规范化。

以上对应 [v1.6.0 Release](https://github.com/BlueSkyXN/XMemory/releases/tag/v1.6.0) 的功能范围。

## 1.6.1：读取兼容与一致性

- Python 3.9/3.10 读取自动化配置时，无关内联表、多行字符串等值不再阻断顶层 `cwds`、`name`、`rrule` 的解析。
- `projects --since` 按全部会话判断 `memory_without_sessions`，包括同 inode 的别名。
- `memory read/search` 的 SHA256 对应实际读取的原始字节；编目后变化以局部告警记录，未返回的变化文件计入范围外告警数。
- 已有 Python zstd 后端时普通命令不探测外部工具；`doctor` 仍列出全部后端。PATH 探测只接受绝对目录项，常见前缀保留。
- 读取器与 XMemory 程序入口支持 Python `-I` 隔离调用。记忆、项目总览及自检仍使用主目录下的默认数据根，异地会话原件可用 `sessions --root` 选择。

补充场景与判据见 [1.6.1 评测准备](../../evals/v1.6.1/README.md)，1.5.x 变更见 [历史版本说明](../v1.5/README.md)。
