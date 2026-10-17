---
format: "xmemory/v1.5"
kind: "daily"
updated: "{{updated}}"
day: "{{day}}"
---

# {{day}}

## {{project}}

<!-- session:{{session_ref}} -->
### {{subject}}

- {{point}}
- 来源：[{{record_label}}]({{record_link}})

<!-- 无会话身份时改用 record:<根内记录相对路径> 标记。每块最多八条要点。 -->
<!-- 重叠活动在会话块补一条 Skysight 活动线索及覆盖时段，出处归入文末；以下块仅用于独立活动。 -->
<!-- activity:codex-skysight:{{day}} -->
### {{activity_subject}}

- {{activity_point}}
- 覆盖：{{activity_window}}

## 历史资料归档（事件日期未核实）

- [{{record_label}}]({{record_link}})：{{record_scope}}

<!-- 当天采集、没有事件日期的导入记录（day_basis: captured）每条一行，写范围和链接；具体内容归入项目主题或画像。没有时省略本节。 -->

## 来源与覆盖

Skysight 来源目录：{{activity_source_directory}}。活动来自二手摘要。

- {{project_and_block_marker}}：{{activity_window}}；原件 {{activity_source_filenames}}

<!-- 没有 Skysight 时省略来源与覆盖节。按块保留全部实际原件身份；归属推断和影响理解的缺口各说明一次。按记录更新时保留已有活动内容及出处，直到重读或明确更正、删除。 -->
