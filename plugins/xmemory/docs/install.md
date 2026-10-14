# 安装与首次使用

当前源码版本 **1.5.4**（[发布与下载](https://github.com/BlueSkyXN/XMemory/releases)），格式 `xmemory/v1.5`，需要 Python 3.9+。安装仅提供技能和只读程序，不建库、不采集、不修改客户端配置。

## 市场安装

| 客户端 | 市场根 | XMemory 插件 ID |
|---|---|---|
| ZCode | 源码或完整包的 `plugins/` | `xmemory@xmemory-marketplace` |
| Claude Code | 源码或完整包根 | `xmemory@xmemory-marketplace` |
| Codex | 源码或完整包根 | `xmemory@xmemory-marketplace` |

三个客户端统一使用市场名 `xmemory-marketplace`；清单格式和市场根仍按各客户端要求保留。市场同时列出 `conversation-readers@xmemory-marketplace`，可单独安装。XMemory 不内嵌读取器，没有强制插件依赖。

以下新名称适用于当前源码。已发布的 v1.5.3 包仍使用旧名称，不能仅凭插件版本判断市场名称；以所用包内清单的 `name` 为准。

Claude Code：

```bash
claude plugin marketplace add /absolute/path/to/XMemory
claude plugin install xmemory@xmemory-marketplace
```

Codex：

```bash
codex plugin marketplace add /absolute/path/to/XMemory
codex plugin add xmemory@xmemory-marketplace
```

ZCode 在插件市场添加 `plugins/` 的实际绝对路径。已添加同名市场时更新已有安装。不同 CLI 版本先看实际 help。

独立技能包把 `skills/` 下八个目录一起放进客户端的技能目录，保留相对位置；同一客户端避免同时启用插件与同名独立技能。

## 旧市场名迁移

旧名称分别为 ZCode 的 `xmemory`、Claude Code 的 `xmemory-claude`、Codex 的 `xmemory-codex`。市场名属于插件 ID，改名不会自动迁移已安装插件。

1. 记录旧插件的启用状态、配置、插件数据目录和实际记忆根；保留记忆库及客户端原生记忆规则。
2. 使用客户端支持的卸载方式移除旧 ID，保留需要的数据；先检查实际 CLI 的 help，不能假定卸载会保留插件数据。ZCode 支持 `plugins uninstall <旧插件 ID> --keep-data --force`。
3. 移除旧市场注册，再按上表的市场根添加新市场，只安装此前使用的插件。恢复原来的启用状态；有按旧 ID 保存的配置或数据时，按客户端支持的方式迁移，不能只改市场清单或缓存目录名。
4. 确认只剩新市场及新插件 ID，在新会话验证技能。市场改名不要求重建、转换或删除 XMemory 记忆库。

## 首次使用

让代理按 [设置技能](../skills/xmemory-setup/SKILL.md) 选择新的空目录、实际时区、来源和项目，并从模板创建配置。来源默认关闭；可以只启用项目文件，也可以使用可选读取器。

保留客户端原生记忆的入口、读取和维护机制，与 XMemory 同时使用。这里的来源开关仅控制导入 XMemory 的材料；原生记忆无需先导入便可按客户端协议使用。隔离实验中的关闭记忆参数不属于安装或日常运行要求。

```bash
python3 <插件目录>/skills/xmemory/scripts/xmemory.py --root <记忆根> status
```

再让代理“运行一轮”或只更新某个对象。时间与来源照抄实际结果，文件直接编辑；没有 init、scan、submit、consolidate 或 forget 程序命令。

已有 1.4 库先保留，确认新目录或归档位置后重建。不要把它的 config 格式名直接改成 1.5。

已有 1.5.0 / 1.5.1 库无需转换格式。新增跨日材料可补 `event_days`；旧会话身份会收到复核提示，先回查原件再映射，status 不会自动改写。1.5.2 仅在 status 报告的 summary 对象增加 `upstream_updates`，不新增记忆文件字段。

1.5.3 继续使用相同格式，升级技能即可。已有客户端告知使用旧模板时，按用户要求合并新版告知，保留原生记忆规则；库内 `exclude_sessions` 也用于过滤联合召回中的已知原生副本，不代表原生副本已删除。

1.5.4 仍兼容已有 1.5.x 库。新版本会提示归属未定的记录，以及会话文件名与原生身份尾八位不符的记录，不自动改写；旧版 1.5.3 可读取带新字段的库，但不会识别未定归属，仍按旧语义把空项目列表算作 personal。已存在的 Skysight 记录不会随安装转换；整理历史内容需另行确定范围。

需要 Skysight 时按来源规则单独登记为 memory 类来源，活动只进入日总结；运行一轮会独立检查未覆盖窗口。仅安装插件不会启用来源、补读历史或创建定时任务。

## 告知与定时

告知和定时模板在 `skills/xmemory/templates/`。`automation-prompt.md` 用于日常增量，`organization-prompt.md` 用于每 7 天的完整整理，两者的调度都交给客户端。按用户要求合并告知段落到指定客户端规则文件。当前宿主必须能读取来源并写入选定记忆根，不能用“已安装”代替一次实际调用验证。

程序报告与 [已知边界](design.md) 分开阅读。status 不写文件，也不会修复报告中的问题。
