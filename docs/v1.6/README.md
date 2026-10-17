# XMemory 1.6 版本线

1.6 版本线的最后版本为 XMemory **1.6.1** 与 Client Readers **0.2.1**，于 **2026-10-16** 发布；当前版本见 [1.7 版本线](../v1.7/README.md)。记忆格式沿用 `xmemory/v1.5`，已有 1.5.x 库无需转换。

[下载 v1.6.1](https://github.com/BlueSkyXN/XMemory/releases/tag/v1.6.1) · [安装与升级](../release-install.md) · [使用指南](../../plugins/xmemory/docs/usage.md) · [验证报告](../validation.md)

## 1.6.1：读取兼容与一致性

| 改进 | 使用影响 |
|---|---|
| Python 3.9/3.10 自动化配置回退解析 | 无关内联表、多行字符串等值不再阻断顶层 `cwds`、`name`、`rrule` 的读取 |
| 项目候选时间过滤 | `memory_without_sessions` 按全部会话判断，包括同 inode 路径别名；较早会话不会被误报为不存在 |
| 正文与 SHA256 一致 | `memory read/search` 的 hash 对应实际读到的原始字节；编目后变化报告局部告警，未返回的变化文件计入范围外告警 |
| zstd 探测按需执行 | 已有 Python 后端时普通命令省去外部探测；`doctor` 仍列出全部后端，PATH 仅使用绝对目录项 |
| 隔离入口与输出编码 | 读取器与 XMemory 支持 `python3 -I`；输出使用 UTF-8 |

原生记忆、项目总览和自检继续使用主目录下的默认客户端数据根；异地会话通过 `sessions --root` 选择。补充场景与判据见 [1.6.1 评测准备](../../evals/v1.6.1/README.md)。

## 1.6.0：原生记忆与项目候选

- Conversation Readers 更名为 Client Readers。五端统一提供 `projects`、`sessions`、`memory`、`doctor`；会话命令改为 `read.py sessions list/read/search`。
- 原生记忆按角色、项目归属、重复文件、同会话和迁移关系返回；XMemory 按来源关系采集，保留未定归属与读取缺口。
- Claude 指定 store 或文件时只扫描对应会话目录，并支持路径别名；项目总览提供 `parent` 与 `children`。
- Codex 压缩会话按已有 zstd 后端回退并支持多 frame，缺失后端时按根目录汇总未读数；项目筛选统一路径规范化。

以上对应 [v1.6.0 Release](https://github.com/BlueSkyXN/XMemory/releases/tag/v1.6.0) 的功能范围，合成行为场景见 [1.6.0 评测](../../evals/v1.6.0/README.md)。

## 升级时核对什么

| 原有安装或数据 | 当前处理 |
|---|---|
| `conversation-readers` 插件 | 保留需要的数据，通过宿主卸载旧插件后安装 `client-readers@xmemory-marketplace` |
| `read-*-conversations` 独立技能 | 确认并移除旧目录，再放入 `read-<client>` 自包含技能 |
| 旧的三端市场名 | 按[迁移说明](../../plugins/xmemory/docs/install.md#旧市场名迁移)更新注册、插件 ID 与启用状态 |
| `xmemory/v1.5` 记忆库 | 原地沿用格式，安装过程不改写记录与来源开关 |
| 会话输出消费者 | 继续识别 `conversation-readers/v1` 与原 `session_ref`，历史 schema 为兼容保留 |
| 1.4 及更早运行时库 | 保留原库，确定新目录或归档位置后按当前模板重建 |

1.5.x 的跨日来源、明确更正、原生记忆共同使用、Skysight 和未定归属规则继续有效，详见[历史版本说明](../v1.5/README.md)。

程序、CI、模型行为与实际客户端运行的验证状态分别保存在[验证报告](../validation.md)。补充夹具准备完成的场景以其中记录的实际模型执行次数为准。
