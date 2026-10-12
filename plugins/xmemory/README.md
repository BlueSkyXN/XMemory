# XMemory 1.5.1

以技能维护跨客户端 Markdown 记忆。六类对象分别更新，唯一程序是只读 `status`；定时由客户端负责，Conversation Readers 另装、可选。

## 开始使用

- [技能入口](skills/xmemory/SKILL.md)：查阅、记一条、运行一轮、制作记录、更新对象、设置、维护。
- [安装](docs/install.md)：选择记忆根、来源、项目和时区。
- [目录与格式](skills/xmemory/references/format.md)：`xmemory/v1.5` 模板。
- [设计与边界](docs/design.md)：职责、已知限制与旧库关系。

```bash
python3 <本插件目录>/skills/xmemory/scripts/xmemory.py --root <记忆根> status
```

程序需要 Python 3.9+ 标准库；不需要 git，不读客户端，不写文件。记录、总结、意识、画像、入口均由执行技能的 AI 使用普通文件工具维护。

只有用户选定的来源才会被处理。没有读取器时，AI 按 [来源参考](skills/xmemory/references/sources.md) 只读探索。

1.5.1 统一真实更新时间，分开日常增量与每 7 天的客户端整理任务，支持跨日导入关联，并明确原生会话身份与读取器引用的区别。1.5.0 库可以直接读取；可选字段与旧身份的兼容边界见设计文档。

库内状态报告不证明外部来源已经同步，结构检查不证明语义正确。当前源码为 1.5.1，已发布稳定版为 [1.5.0](https://github.com/BlueSkyXN/XMemory/releases/tag/v1.5.0)。

许可证：GNU GPL v3。
