---
format: "xmemory/v1.5"
kind: "record"
updated: "{{updated}}"
source: "{{source_name}}"
client: "{{client}}"
source_ref: "{{source_ref}}"
source_location: "{{source_location}}"
source_updated: "{{source_updated}}"
evidence: "{{evidence}}"
projects: []
# 归属未定时增加 project_status: "unresolved"，此时 projects 保持为空；个人内容不加此标记。
day: "{{day}}"
day_basis: "{{day_basis}}"
# 跨日文件用 event_days 列出有依据的日期，day_basis 为 captured 时不写；原始会话按会话与日分记录。
# session_refs 只放核实过的 client:<原生 ID>，读取器原始引用放 source_ref。
session_refs: []
coverage: "{{coverage}}"
---

# {{subject}}

{{content_by_material_type}}

<!-- 会话写目标、关键经过与决定、结果与未决；导入主题按主题组织；项目文件写事实及条件。笔记按笔记技能写三到五行。 -->
<!-- 只有 partial 或缺口影响结论时写一行“缺口”；来源时间依据、推断的项目归属和同源关系在文末补充一次，其余出处使用 frontmatter。 -->
