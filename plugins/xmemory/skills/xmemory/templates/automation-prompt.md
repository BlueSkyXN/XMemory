使用 `xmemory-run` 在 `{{memory_root}}` 执行一轮记忆更新。

模式：{{incremental_or_backfill_or_library_only}}。
范围：{{sources_projects_dates_and_objects}}。
优先项目：{{priority_projects_or_none}}。
工作量限制：{{work_limit_or_full_requested_scope}}。

先完整读取 `xmemory-run` 技能，按其清点、分批、写入并汇报；技能不可用时停止并报告。选定对象全部完成后报告完成；选定对象仍有缺口时报告具体剩余范围。
