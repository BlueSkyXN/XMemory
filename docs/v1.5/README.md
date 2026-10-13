# XMemory 1.5 版本线

## 1.5.0

[1.5.0 已发布](https://github.com/BlueSkyXN/XMemory/releases/tag/v1.5.0)，采用技能优先的产品定义：六类记忆对象分别更新，程序仅有只读 status。旧任务队列、整合锁、ledger 与内嵌读取器已经退役。格式为 `xmemory/v1.5`，Conversation Readers 独立可选。

技能稿已移入正式插件，不在此处维护重复副本：

- [技能入口](../../plugins/xmemory/skills/xmemory/SKILL.md)
- [对象工序](../../plugins/xmemory/skills/xmemory/references/objects.md)
- [目录与格式](../../plugins/xmemory/skills/xmemory/references/format.md)
- [来源参考](../../plugins/xmemory/skills/xmemory/references/sources.md)
- [status](../../plugins/xmemory/skills/xmemory/references/status.md)
- [设计与已知边界](../../plugins/xmemory/docs/design.md)

## 1.5.1

- 正文保存总是写真实 `updated`；未完成的派生对象不覆盖正式文件，partial 记录保留显式缺口。
- 日常增量与客户端每 7 天的完整整理分开，不增加库内状态。
- `event_days` 支持一份跨日文件关联多个有证据的日期，仍兼容单日 `day`。
- 用经核实的原生会话身份跨来源遗忘；旧引用继续精确匹配并提示复核，不自动猜测迁移。
- 来源参考补全 WorkBuddy 工作区和 Qoder CN CLI，另有 [合成验证案例](../../evals/v1.5.1/README.md)。

交付与验证以相应 Git 标签、Release 和 [验证报告](../validation.md) 为准。

## 1.5.2

- 当场明确更正长期偏好或项目决定时，同步相关画像/主题；查阅补查入口尚未吸收的相关更正，不把 updated 当吸收水位。
- 各层按用途取舍内容：记录保留必要经过，日总结突出当天变化，主题优先结论与条件；整理过程说明留在汇报。查阅保留更正检查，依据充分后停止扩读，普通回答给结论与关键来源，核查时再展开证据链。
- 全局摘要报告已有画像/项目入口的待处理新来源，兼容增加 `upstream_updates`，不传播固定的外部未检查提示。
- 独立读取器升级为 0.1.5，修正 Windows 形式的界面会话引用、压缩流跳过超长记录后的原件字节定位，以及跨项目 JSONL 会话的目录筛选遗漏；补充会话项目列表与事件项目上下文。
- 新增 [增量更正的独立验证场景](../../evals/v1.5.2/README.md)。文件格式保持 `xmemory/v1.5`；[发布与下载](https://github.com/BlueSkyXN/XMemory/releases)不代表已安装客户端自动更新。

## 1.5.3

- Codex 来源区分 V1/V2、汇总经验和原始会话；ZCode 区分项目索引、主题 origin 与后续更正。按来源范围填写证据类型，保留经验的条件与例外。
- 原生记忆与 XMemory 共同使用，原生读取、注入和维护继续按客户端机制执行；导入开关不限制原生日常使用。
- 联合查阅先检查 `exclude_sessions`，已知被遗忘会话的原生副本不用于回答或写回；保留其他会话的独立依据，原生副本的删除范围另行说明。
- 来源适配与双库行为场景见 [评测说明](../../evals/source-adaptation/README.md)。文件格式、只读 status 与 Conversation Readers 0.1.5 保持兼容。
