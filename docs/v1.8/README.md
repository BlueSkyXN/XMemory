# XMemory 1.8

1.8.0 将核心入口收敛为 xmemory-update、xmemory-recall、xmemory-note，固定用户 home 下的 `.agents/memory/`，直接维护三层 Markdown：笔记、有效主记忆、紧凑入口。

采集和整合按需连续执行；来源无增量可以无产出。更正通过入口短提示衔接，普通查阅按需展开。Python status 为可选只读盘点，输出 Markdown，不再依赖旧 TOML 配置与对象元数据。

旧对象模板和八技能分流从新包移除；旧库不自动转换、覆盖或吸收。Client Readers 0.2.1 的读取逻辑保持独立。

## 从 1.7 升级

1. 先确认用户 home 下 `.agents/memory/` 中旧试验内容的保留位置或处置，再启用三层 Markdown；1.8 不读取旧 TOML 配置，也不执行旧对象库迁移。
2. 通过宿主更新插件，或整体替换独立技能包的三个入口和共享资源目录。在新对话确认只启用 xmemory-update、xmemory-recall、xmemory-note。
3. 如有脚本消费 status 输出，将旧 JSON 解析改为使用本版 Markdown 盘点报告。status 只检查本库文件及链接目标，不提供旧版来源处理状态。

本版包含异常外链、括号路径、引用式链接和行内代码的检查修复；更正提示仅在相关主记忆与入口同步并回读确认后移除。发布附件及对应 CI 见 [1.8.0 Release](https://github.com/BlueSkyXN/XMemory/releases/tag/v1.8.0)。真实双端自然触发、原生记忆共存和实际中断恢复仍待验收，详细范围见验证记录。

[安装](../release-install.md) · [开发](../development.md) · [验证记录](../validation.md)
