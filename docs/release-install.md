# XMemory 1.7.0 安装与升级

本版包含 XMemory **1.7.0** 与可选 Client Readers **0.2.1**，记忆格式为 `xmemory/v1.5`。正式附件见 [v1.7.0 Release](https://github.com/BlueSkyXN/XMemory/releases/tag/v1.7.0)。本文也随 XMemory ZIP 分发为 `INSTALL.md`。

## 选择安装包

| 包 | 内容 | 适用方式 |
|---|---|---|
| `XMemory-1.7.0.zip` | 三端市场、XMemory 与 Client Readers 两个插件及各自文档 | 通过客户端插件市场安装 |
| `XMemory-1.7.0-skills.zip` | 八个 XMemory 技能、模板、只读 status、INSTALL 与许可证 | 复制到客户端支持的技能目录 |
| `ClientReaders-0.2.1-skills.zip` | 五端自包含读取技能、README、验证记录与许可证 | 独立安装所需的读取技能 |

每个 ZIP 都有同名 `.zip.sha256`，包内另有 `SHA256SUMS`。在下载目录先核对归档校验值，再解压；选择对应平台命令：

```bash
# macOS；其他两个包替换为对应文件名
shasum -a 256 -c XMemory-1.7.0.zip.sha256
```

```bash
# Linux
sha256sum -c XMemory-1.7.0.zip.sha256
```

```powershell
# Windows PowerShell：将结果与 .sha256 文件中的值比较
Get-FileHash .\XMemory-1.7.0.zip -Algorithm SHA256
Get-Content .\XMemory-1.7.0.zip.sha256
```

安装后的程序需要 Python 3.9+。`status` 与普通读取使用标准库；Codex 压缩会话还需已有 zstd 后端，读取器 `doctor` 会报告可用情况。

## 已有旧读取器时先卸载

已安装 `conversation-readers` 时，先记录实际插件 ID、启用状态和需保留数据，再通过客户端卸载。新安装可直接进入下一节。以下按当前市场名举例；旧市场用户使用实际 ID：

```bash
# Claude Code：保留插件持久化数据
claude plugin uninstall conversation-readers@xmemory-marketplace --keep-data
```

```bash
# Codex：卸载会移除本地缓存，先保留其中自行添加的文件
codex plugin remove conversation-readers@xmemory-marketplace
```

ZCode 在插件管理中卸载 Conversation Readers。独立技能安装先确认并移除旧的五个 `read-*-conversations` 目录，再放入新技能。已有记忆根与客户端原始数据沿用原位置。

## 完整市场包安装

三个客户端的市场名为 `xmemory-marketplace`。解压后，Claude Code 和 Codex 添加解压根，ZCode 添加其下 `plugins/`。下面路径替换为实际位置，只执行目标宿主的命令。

```bash
# Claude Code
claude plugin marketplace add /absolute/path/to/XMemory-1.7.0
claude plugin install xmemory@xmemory-marketplace
# 需要读取器时再安装
claude plugin install client-readers@xmemory-marketplace
```

```bash
# Codex
codex plugin marketplace add /absolute/path/to/XMemory-1.7.0
codex plugin add xmemory@xmemory-marketplace
# 需要读取器时再安装
codex plugin add client-readers@xmemory-marketplace
```

ZCode 在插件市场添加 `plugins/` 的绝对路径后，选择 XMemory 及需要的 Client Readers。已有同名市场时核对其来源并更新原安装。

旧 v1.5.3 包的市场名为 ZCode `xmemory`、Claude Code `xmemory-claude`、Codex `xmemory-codex`。旧安装需保留数据与配置，再通过客户端移除旧插件及旧市场、注册新市场并恢复启用状态；完整步骤见[旧市场名迁移](https://github.com/BlueSkyXN/XMemory/blob/main/plugins/xmemory/docs/install.md#旧市场名迁移)。

## 独立技能安装

XMemory 技能包需要将 `skills/` 下八个目录一起复制到目标客户端的技能目录，保留相对结构。Client Readers 每个 `read-<client>/` 自包含，可按需复制完整目录；保留 `scripts/` 和 `references/`。

同一客户端选择一种安装方式，避免插件与独立技能同时提供同名入口。安装后在新会话确认八个 XMemory 技能与实际安装的读取技能可用，并核对插件版本。

## 首轮使用与升级边界

让代理按 `xmemory-setup` 选择记忆根、实际时区、来源与项目，创建配置后按选定范围运行一轮。默认记忆根为 `~/.agents/memory/`；来源默认关闭。

唯一 XMemory 程序命令是只读检查，以下路径指向已安装的 `xmemory/` 技能目录：

```bash
python3 -B "/absolute/path/to/skills/xmemory/scripts/xmemory.py" --root "/absolute/path/to/memory" status
```

- 现有 1.5.x 库保持 `xmemory/v1.5`，无需格式转换。旧身份与项目归属提示在复查相应材料时处理；1.5.3 的 status 仍按旧语义解释空项目列表。
- 1.4 及更早运行时库先保留，确定新目录或归档位置后按当前模板重建。
- 客户端原生记忆继续使用和维护；告知保留原生入口，并包含联合查阅与会话排除规则。
- Skysight 活动只进入日总结，启用后独立核对覆盖窗口。来源原件通常约 7 天滚动清除，实际保留期需核实。
- 安装不采集历史、不改写已有记录、不创建定时任务。周期更新和每 7 天的完整整理需在客户端单独配置并验证。

完整包内可阅读 `plugins/xmemory/docs/install.md`、`plugins/xmemory/docs/usage.md` 和 `plugins/client-readers/README.md`。独立技能包用户可查阅[在线安装说明](https://github.com/BlueSkyXN/XMemory/blob/main/plugins/xmemory/docs/install.md)、[插件文档入口](https://github.com/BlueSkyXN/XMemory/blob/main/plugins/xmemory/README.md)与[验证记录](https://github.com/BlueSkyXN/XMemory/blob/main/docs/validation.md)。
