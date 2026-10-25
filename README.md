# XMemory

XMemory 是由 Agent 执行的跨客户端长期记忆扩展层。把选定会话、原生记忆、项目文件和明确反馈整理为有用知识，在后续任务中按需使用。当前版本为 **1.8.0**；下载见 [Releases](https://github.com/BlueSkyXN/XMemory/releases)，验证范围见 [验证记录](docs/validation.md)。

正式记忆固定在用户 home 下的 `~/.agents/memory/`。内容全部是 Markdown，基本使用不要求 Python、数据库或后台服务。

| Skill | 用途 |
|---|---|
| [xmemory-update](plugins/xmemory/skills/xmemory-update/SKILL.md) | 从指定来源采集并整理记忆，也可只整理已有内容 |
| [xmemory-recall](plugins/xmemory/skills/xmemory-recall/SKILL.md) | 只读查阅偏好、决定、项目背景与经验 |
| [xmemory-note](plugins/xmemory/skills/xmemory-note/SKILL.md) | 记录当前对话的明确要求、结论或更正 |

采集和整合是 update 内部可分别执行的步骤。用户只需说明来源、项目或主题及所需时间范围，例如“整理 ZCode 上周关于这个项目的对话”。维护对话不自动回流成为来源。

## 保存的内容

```text
~/.agents/memory/
├── memory_summary.md                 少量要点与阅读导航
├── MEMORY.md                         当前有效知识与必要条件
└── notes/YYYY-MM/
    └── YYYY-MM-DD-项目或范围-主题.md   有用工作、变化与反馈
```

有价值才记，同源合并，无变化允许不写。普通读取从入口进入相关主记忆，必要时再展开笔记和原件。明确更正当轮应用；中断时入口留下短待处理提示。完整职责见 [内容约定](plugins/xmemory/skills/xmemory/references/format.md)。

## 开始使用

按 [安装说明](docs/release-install.md)安装三个入口及共享资源，选择宿主支持的用户指令入口加入最小读取告知。然后在新对话中尝试：

- “整理这些选定材料，写入 XMemory。”
- “继续这个项目，先查过去的约定与未完成事项。”
- “记住：这个要求只适用于当前项目。”

[Client Readers 0.2.1](plugins/client-readers/README.md) 是独立可选插件，用于读取已适配的客户端私有存储。普通文件、Markdown 和当前上下文可由宿主直接处理。外部定时、后台和异步发起由客户端负责。

可选机械检查需要 Python 3.9+ 标准库，输出只读 Markdown 报告：

```bash
python3 -B plugins/xmemory/skills/xmemory/scripts/xmemory.py status
```

固定根中的旧试验内容不自动迁移或覆盖；使用 1.8 前先明确既有文件的处置。多客户端顺序共用同一目录，本版不协调并发写入。

## 开发

[开发指南](docs/development.md) · [使用指南](plugins/xmemory/docs/usage.md) · [1.8 版本说明](docs/v1.8/README.md) · [历史文档导航](docs/README.md)

开发工具使用 Python 3.11+，客户端运行的可选脚本兼容 Python 3.9+。

```bash
python3 -B tools/check_package.py
python3 -B tools/build_client_readers.py --check
python3 -B -m unittest discover -s tests -v
python3 -B tools/build_release.py --output dist/new-build
```

构建仅生成本地归档。许可证：[GNU GPL v3](LICENSE)。
