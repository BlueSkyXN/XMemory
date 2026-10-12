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
day: "{{day}}"
day_basis: "{{day_basis}}"
# 跨日文件才增加非空 event_days 字符串数组；只列有依据的日期，captured 时省略。
# session_refs 使用 client:<已核实原生 ID>；读取器原始引用放 source_ref。
session_refs: []
coverage: "{{coverage}}"
---

# {{subject}}

来源范围：{{source_scope}}。来源更新时间依据：{{source_time_basis}}。

## 目标与用户原话

{{goal_and_user_words}}

## 经过与决定

{{history_and_decisions}}

## 结果与未决

{{observed_results_and_open_items}}

## 读取边界

{{coverage_details}}
