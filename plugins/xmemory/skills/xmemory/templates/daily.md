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

<!-- 与记录重叠的活动在上面的会话块内补充，不再另建活动块；多条线索和来源定位分别展开为多个列表项： -->
- Skysight 活动线索（二手）：
  - {{activity_hint}}
  - 库外定位：
    - {{activity_source_locations}}
  - 覆盖：{{activity_window}}
  - 归属依据：{{activity_attribution_basis}}
  - 缺口：{{activity_gaps}}

<!-- 以下示例仅用于未与记录重叠的独立活动；归属未定时改用“归属未定”节。 -->
<!-- activity:codex-skysight:{{day}} -->
### {{activity_subject}}

- {{activity_point}}
- 来源：Codex Skysight 活动摘要（库外，二手摘要，未读取原始事件流）。
- 库外定位：
  - {{activity_source_locations}}
- 覆盖：{{activity_window}}
- 归属依据：{{activity_attribution_basis}}
- 缺口：{{activity_gaps}}

<!-- 按记录更新时原样保留独立活动块及并入会话块的 Skysight 线索；只有重读同日来源或明确更正、删除要求才修改。活动不进入主题、意识或画像。 -->
