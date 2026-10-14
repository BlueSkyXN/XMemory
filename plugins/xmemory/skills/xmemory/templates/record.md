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
# 归属未定时增加 project_status: "unresolved"，且 projects 保持为空；个人内容不加此标记。
day: "{{day}}"
day_basis: "{{day_basis}}"
# 跨日文件才增加非空 event_days 字符串数组；只列有依据的日期，captured 时省略。
# session_refs 使用 client:<已核实原生 ID>；读取器原始引用放 source_ref。
session_refs: []
coverage: "{{coverage}}"
---

# {{subject}}

来源范围：{{source_scope}}。来源更新时间依据：{{source_time_basis}}。
项目归属依据：{{project_paths_or_explicit_content_inference}}。

## 目标与用户原话

{{goal_and_user_words}}

## 经过与决定

{{history_and_decisions}}

## 结果与未决

{{observed_results_and_open_items}}

## 读取边界

{{coverage_details}}

<!-- 未读原件时写“按摘要所引的窗口、路径或会话定位，未读原件”；不把二手陈述写成本次核实、验证或确认。 -->
