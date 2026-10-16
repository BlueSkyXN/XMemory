# XMemory

跨客户端 Markdown 记忆库：AI 按技能把会话、别家记忆、项目文件和笔记整理成记录、日总结、项目总结、意识、用户画像与全局入口。

与客户端原生记忆共同使用：客户端继续按自身机制读取和维护记忆，XMemory 补充跨客户端信息。两套记忆按问题取用、核对来源和更正，接入 XMemory 不替换或关闭原生记忆。

当前源码版本 **1.6.1**（[发布与下载](https://github.com/BlueSkyXN/XMemory/releases)），文件格式 `xmemory/v1.5`。程序提供只读 `status`，记忆库不依赖 git。Client Readers 0.2.1 是同一市场中的另一个可选插件。

通过 Client Readers 定位五端原生记忆、生成项目候选并按角色采集；关联同会话、重复文件和迁移副本，保留归属未定与读取缺口。升级前先卸载旧插件 `conversation-readers`，再安装 `client-readers`，步骤见 [安装与升级](docs/release-install.md)。已有 1.5.x 记忆库沿用原格式；[1.5.x 版本说明](docs/v1.5/README.md)保留历史变更。

## 使用方式

安装后告诉代理：“设置 XMemory，选择这些来源和项目”，或“更新记忆”“只更新这个项目的意识”“查一下上次的决定”。八个技能入口见 [XMemory 技能](plugins/xmemory/skills/xmemory/SKILL.md)，各对象可以单独执行。

```bash
python3 <插件目录>/skills/xmemory/scripts/xmemory.py --root <记忆根> status
```

默认记忆根 `~/.agents/memory/`，可用 `--root` 或 `XMEMORY_ROOT` 指定。程序只用 Python 3.9+ 标准库；不读取客户端、不写文件、不调用模型。配置与对象由 AI 按模板直接编辑。来源默认关闭，按用户选择启用。

[安装与首次使用](plugins/xmemory/docs/install.md) · [设计与边界](plugins/xmemory/docs/design.md) · [版本说明](docs/v1.6/README.md) · [验证报告](docs/validation.md)

## 组成

| 内容 | 位置 |
|---|---|
| 八个 XMemory 技能、只读 status、格式与模板 | `plugins/xmemory/` |
| 五端独立会话与原生记忆读取技能 | `plugins/client-readers/` |
| 构建与仓库检查 | `tools/` |
| 程序与分发包测试 | `tests/` |
| 有依据的记忆问答、遗忘、增量更正与来源适配验证案例 | `evals/v1.5.1/`、`evals/v1.5.2/`、`evals/v1.5.4/`、`evals/v1.6.0/`、`evals/v1.6.1/`、`evals/source-adaptation/` |

三个客户端统一使用市场名 `xmemory-marketplace`，同时列出两个插件，可分别安装：ZCode 市场根为 `plugins/`，Claude Code 与 Codex 市场根为仓库根。市场名称统一已在当前源码中完成，已发布的 v1.5.3 包仍使用旧名；旧安装迁移见 [安装与首次使用](plugins/xmemory/docs/install.md#旧市场名迁移)。完整市场包、XMemory 独立技能包及 Client Readers 技能包见 [安装包说明](docs/release-install.md)。

## 开发检查

开发检查需 Python 3.11+，安装后的程序支持 Python 3.9+。

```bash
python3 -B tools/check_package.py
python3 -B tools/build_client_readers.py --check
python3 -B -m unittest discover -s tests -v
python3 -B tools/build_release.py --output dist/<新目录>
```

`tools/sync_client_readers.py --apply` 只同步独立读取插件，不向 XMemory 复制代码。发布包不包含本机 `local/` 材料。许可证：[GNU GPL v3](LICENSE)。
