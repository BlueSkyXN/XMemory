# 合成原始会话：Cedar 导出格式

client: claude
native_id: sample-001
reader_ref: claude:jsonl:sample-001
source_updated: 2026-10-12T09:30:00+00:00
project: cedar

## 2026-10-10

09:00 用户：这个项目的工具默认先 dry-run，查看影响后再显式执行。

09:10 助手：导出清单可以选 SQLite 或 JSON Lines。

09:12 用户：选 JSON Lines，因为评审者需要逐行查看 diff，这一版也用不到跨文件事务。

09:20 工具结果：在临时数据上生成导出样本，逐行解析通过。

## 2026-10-12

09:00 用户：这次排障先别写长解释，先给复现命令。这个要求只限这次排障。

09:15 工具结果：本地冒烟通过；只处理了合成数据。

09:30 用户：先留在 review 分支，等我看完再发布；当前还没发布。
