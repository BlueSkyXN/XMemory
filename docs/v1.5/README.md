# XMemory 1.5 版本线

## 1.5.0

当前实现采用技能优先的产品定义：六类记忆对象分别更新，程序仅有只读 status。旧任务队列、整合锁、ledger 与内嵌读取器已经退役。格式为 `xmemory/v1.5`，Conversation Readers 独立可选。

技能稿已移入正式插件，不在此处维护重复副本：

- [技能入口](../../plugins/xmemory/skills/xmemory/SKILL.md)
- [对象工序](../../plugins/xmemory/skills/xmemory/references/objects.md)
- [目录与格式](../../plugins/xmemory/skills/xmemory/references/format.md)
- [来源参考](../../plugins/xmemory/skills/xmemory/references/sources.md)
- [status](../../plugins/xmemory/skills/xmemory/references/status.md)
- [设计与已知边界](../../plugins/xmemory/docs/design.md)

## 后续改进

1.5.1 将完善更新时间语义，拆开增量更新与周期整理，补齐跨日来源关联、遗忘身份与来源参考，并加入带标准答案的最小效用验证案例。版本交付与验证以相应 Git 标签、Release 和验证报告为准。
