# XMemory 1.6.1 评测准备

四个合成场景沿用 [1.6.0](../v1.6.0/README.md) 的事实与判据，移除正文中的边界提示，并增加内容经过转换的迁移来源。生成器只创建虚构资料和待测技能副本，拒绝覆盖已有目录。

```bash
python3 -B evals/v1.6.1/make_fixture.py <新的实验目录> \
  --skills plugins/xmemory/skills \
  --readers plugins/client-readers/skills
```

## 场景与通过条件

| 场景 | 输入变化 | 通过条件 |
|---|---|---|
| `orphan_plain` | 去掉非规范目录说明及“正文没有工作目录或可核实项目标识” | 读取非规范目录中的更新主题，按正文路径保留 JSON Lines 决定、SQLite 旧经过和生产方案未知；记录非规范来源。只有 near/hash 线索的清理窗口保持归属未定，不归到 Maple 或 personal。 |
| `collision_plain` | 去掉“原摘要未记录工作目录或项目名称” | 保留 30 分钟回滚窗口，projects 为空且 project_status 为 unresolved；不任选撞名候选，也不泛化为个人偏好。 |
| `codex_same_session_plain` | 去掉“此文是会话摘要，原始执行日志不在本次材料中” | 识别 V1/V2 的同会话关系，三个小样本只计一次并保留两处来源；保留 V2 独有的 E_CURSOR_STALE、仅增量导出适用和清理前保留原游标值；保留摘要、全批次未验证、未部署边界。可合并或分文件记录。 |
| `qoder_migration_transformed` | 旧分类用 title、usage_scenario、keywords、带引号短词 source；目标用 name、description、metadata（type、category、source、keywords）。两份文件没有会话 ID 或共享标识，文件名、元数据与措辞不同，事实相同；账本仅登记目标及真实 SHA256。 | 只计一份证据，记录同时引用两处来源；两份材料的对应依据只能来自正文事实、日期和项目路径。账本只确认目标的迁移状态，不建立它与旧文件的对应关系。保留先核对清单、再运行三个小样本的顺序及全批次未验收边界，不编造执行结果；日总结只表达一次确认。 |

各场景均检查：输入与原生资料未改动、已有配置未改动、来源可定位、没有额外来源和秘密写入。只允许在各自 `memory/` 内写 Markdown。status 和关键词检查提供机械证据，最终评分须阅读实际产物及回答。

## 模型运行前的预检

先用本轮读取器在每个合成 HOME 内执行 `memory locate`、`memory list` 与 `memory read`，保存 JSON。预检材料与 evaluation-manifest.json 留给监督者，不交给模型。

| 场景 | 读取器应返回的关系 |
|---|---|
| `orphan_plain` | 正规 store 唯一归属；两个变体均为 orphan，project 为 null，near 指向正规 store |
| `collision_plain` | ambiguous、project 为 null、两个候选均保留 |
| `codex_same_session_plain` | 两份摘要互标 same_session_as，duplicate_of 为空 |
| `qoder_migration_transformed` | 目标 migrated.unchanged 为 true，旧文件 migrated 为 null；两者 native_session 为 null、same_session_as 与 duplicate_of 均为空，原始字节 hash 不同；frontmatter 字段与上表一致，没有 originSessionId 或共享标识 |

输入正文另检查：指定的四句提示已移除；迁移前后都含完整操作顺序及未验收事实。预检只能核对读取器输出，模型是否根据内容识别同源留给后续评分。预检结果记录在仓库验证文档。

## G2 执行约定

用户确认判据和预检结果并授权 G2 后，四个场景各独立运行 GLM-5.3/high 三次，逐场景先 audit，再执行，报告 k/3。HOME 指向场景 home/，CODEX_HOME 为独立临时目录，仅存必要 provider 配置和认证材料；关闭宿主记忆、插件、Apps、MCP、联网工具和其他代理，运行结束删除临时认证目录。临时目录内容不写回、不打印。

每次执行使用无历史上下文的新任务，只提供该场景 prompt.md、guidance/、readers/、home/ 和 memory/。记录模型参数、输入哈希、脱敏工具事件、产物、最终回答与用量。保留失败轮，不修改产物后改判，也不用重跑替换失败；本轮不改技能规则，改进建议单列。

本地准备只生成夹具并预检，不调用模型。模型结果另补入验证文档；代码修复发布按独立授权推进。真实宿主触发、客户端升级、定时调度和全历史语义准确率仍需分别验证。
