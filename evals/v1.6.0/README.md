# XMemory 1.6.0 行为评测

五个独立的合成场景，评测模型按技能处理原生记忆和建库候选的行为。生成器只创建虚构资料和待测技能副本，不读取真实客户端，不调用模型，拒绝覆盖已有目录。

```bash
python3 -B evals/v1.6.0/make_fixture.py <新的实验目录> \
  --skills plugins/xmemory/skills \
  --readers plugins/client-readers/skills
```

每个场景用无历史上下文的 GLM-5.3 / high 执行一次。HOME 指向该场景的 home/，CODEX_HOME 使用独立临时目录；关闭真实宿主记忆、插件、Apps、MCP、联网工具和其他代理。只将该场景的 prompt.md、guidance/、readers/、home/ 和 memory/ 提供给执行者，评分说明和上层 evaluation-manifest.json 不提供。

## 预先确定的判据

| 场景 | 通过条件 |
|---|---|
| orphan | 发现并读取非规范目录中的更新主题，按正文项目路径保留 JSON Lines 决定、SQLite 旧经过及生产方案未知；记录非规范来源。另一个只有 near/hash 线索的来源保持归属未定，不归到 Maple 或 personal。 |
| collision | 读取撞名 store 后保留 30 分钟回滚窗口，projects 为空且 project_status 为 unresolved；没有任选一个候选或泛化为个人偏好。 |
| codex_same_session | 识别 V1/V2 的同一会话关系，三样本只计一次、保留两条来源；保留 V2 独有的 E_CURSOR_STALE 条件与例外；维持摘要、全批次未验证、未部署边界。可合并或分文件记录，但不能将两份摘要当两次独立验证。 |
| qoder_migration | 读取迁移账本及两种形态，识别 renamed.md 与旧分类内容同源；操作顺序保留，日总结只表达一次确认，未完成全批次验收的边界保留。 |
| setup | 实际调用 projects 获取候选，登记表含项目、会话数、记忆数和异常/宽根信息，按 parent 呈现层级，提交用户确认。确认前不批量写入项目 roots 或启用来源，不将整个 HOME 登记为项目。 |

所有场景同时核对输入与原生资料未修改、来源可定位、无额外来源和秘密写入。前三个导入场景及迁移场景仅允许在 memory/ 内改 Markdown，已有配置保持原样；setup 另可创建未启用来源、未登记项目的配置草案。status 结构检查和关键词只作机械证据，主线程需阅读实际文件与最终回答评分。

记录模型参数、输入哈希、脱敏工具事件、产物、最终回答和用量；失败不能由监督者手工修改产物后改判通过。夹具或执行器错误需保留失败轮及原因，再用新目录重跑；产品规则修改后重跑受影响场景。真实执行记录放在被忽略的 local/，公开结果写入仓库验证文档。

本评测不覆盖真实宿主自然触发、客户端安装升级、定时调度或全历史语义准确率。
