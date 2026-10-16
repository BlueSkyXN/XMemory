# XMemory 1.6.0

以技能维护跨客户端 Markdown 记忆。六类对象分别更新，唯一程序是只读 `status`；定时由客户端负责，Client Readers 另装、可选。

1.6.0 使用 Client Readers 定位原生记忆、生成项目候选并按角色采集，核对同会话、重复与迁移关系；status 与 xmemory/v1.5 格式保持不变。升级读取器时先卸载 conversation-readers，再安装 client-readers，见安装说明。

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

1.5.2 补齐明确更正的即时同步与查阅路径；全局摘要会提示画像和项目入口尚未处理的新来源。文件更新时间不当作吸收水位，查阅保持只读。

1.5.3 补充 Codex/ZCode 来源适配，明确原生记忆与 XMemory 共同使用。联合查阅应用 `exclude_sessions`，已知来自被排除会话的原生副本也不参与回答或重新写回；原生库的物理删除仍由客户端处理。

1.5.4 将 Skysight 活动直接按天写入日总结，按记录重建时保留活动，并在日常更新中独立检查覆盖缺口。项目归属要求具体依据，未定内容使用可选标记；status 增加未定归属与会话文件名身份提示。格式保持 `xmemory/v1.5`，旧库无需转换；1.5.3 的 status 可读但不理解未定归属语义。

库内状态检查与行为评测的范围见仓库验证记录。当前源码为 **1.6.0**，发布状态见 [Releases](https://github.com/BlueSkyXN/XMemory/releases)。

许可证：GNU GPL v3。
