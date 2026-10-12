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
