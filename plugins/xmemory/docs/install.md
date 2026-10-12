# 安装与首次使用

当前源码 **1.5.1**，已发布稳定版为 [1.5.0](https://github.com/BlueSkyXN/XMemory/releases/tag/v1.5.0)，格式 `xmemory/v1.5`，需要 Python 3.9+。安装仅提供技能和只读程序，不建库、不采集、不修改客户端配置。

## 市场安装

| 客户端 | 市场根 | XMemory 插件 ID |
|---|---|---|
| ZCode | 源码或完整包的 `plugins/` | `xmemory@xmemory` |
| Claude Code | 源码或完整包根 | `xmemory@xmemory-claude` |
| Codex | 源码或完整包根 | `xmemory@xmemory-codex` |

三个市场同时列出 Conversation Readers，可单独安装。XMemory 不内嵌读取器，没有强制插件依赖。

Claude Code：

```bash
claude plugin marketplace add /absolute/path/to/XMemory
claude plugin install xmemory@xmemory-claude
```

Codex：

```bash
codex plugin marketplace add /absolute/path/to/XMemory
codex plugin add xmemory@xmemory-codex
```

ZCode 在插件市场添加 `plugins/` 的实际绝对路径。已添加同名市场时更新已有安装。不同 CLI 版本先看实际 help。

独立技能包把 `skills/` 下八个目录一起放进客户端的技能目录，保留相对位置；同一客户端避免同时启用插件与同名独立技能。

## 首次使用

让代理按 [设置技能](../skills/xmemory-setup/SKILL.md) 选择新的空目录、实际时区、来源和项目，并从模板创建配置。来源默认关闭；可以只启用项目文件，也可以使用可选读取器。

```bash
python3 <插件目录>/skills/xmemory/scripts/xmemory.py --root <记忆根> status
```

再让代理“运行一轮”或只更新某个对象。时间与来源照抄实际结果，文件直接编辑；没有 init、scan、submit、consolidate 或 forget 程序命令。

已有 1.4 库先保留，确认新目录或归档位置后重建。不要把它的 config 格式名直接改成 1.5。

已有 1.5.0 库无需转换格式。新增跨日材料可补 `event_days`；旧会话身份会收到复核提示，先回查原件再映射，status 不会自动改写。

## 告知与定时

告知和定时模板在 `skills/xmemory/templates/`。`automation-prompt.md` 用于日常增量，`organization-prompt.md` 用于每 7 天的完整整理，两者的调度都交给客户端。按用户要求合并告知段落到指定客户端规则文件。当前宿主必须能读取来源并写入选定记忆根，不能用“已安装”代替一次实际调用验证。

程序报告与 [已知边界](design.md) 分开阅读。status 不写文件，也不会修复报告中的问题。
