#!/usr/bin/env python3
"""创建虚构的 Codex/ZCode 来源供独立 Skill 行为验证；不读取本机客户端。"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sqlite3


def make_fixture(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=False)
    project = root / "workspace" / "Maple"
    project.mkdir(parents=True)
    sources = root / "sources"
    cid = "11111111-1111-4111-8111-111111111111"
    zid_a = "sess_22222222-2222-4222-8222-222222222222"
    zid_b = "sess_33333333-3333-4333-8333-333333333333"

    def write(relative: str, content: str) -> Path:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def stamp(value: str) -> int:
        return int(datetime.fromisoformat(value).timestamp() * 1000)

    for version in ("codex-v1", "codex-v2"):
        write(f"sources/{version}/memory_summary.md", "# Maple\n\n"
              "导出格式与验证进度见 rollout_summaries/export.md。\n")
        # 保存时间较新的 V1 故意包含错误的执行归纳。
        text = ("2026-10-08 用户确定 JSON Lines 导出。\n"
                "2026-10-09 全部测试通过，已部署。\n") if version == "codex-v1" else (
                "2026-10-08 用户确定 JSON Lines 导出。\n"
                "2026-10-09 三个小样本通过；完整批次失败，尚未部署。\n")
        hour = "16" if version == "codex-v1" else "14"
        write(f"sources/{version}/rollout_summaries/export.md",
              f"thread_id: {cid}\nupdated_at: 2026-10-12T{hour}:00:00+08:00\n"
              f"rollout_path: {sources / 'missing-old-location' / ('rollout-' + cid + '.jsonl')}\n"
              f"cwd: {project}\ngit_branch: experiment\n\n# Maple 导出\n\n{text}")
    write("sources/codex-v1/MEMORY.md", "# Maple 导出经验\n\n"
          "## 游标失效\n\n"
          "2026-09-25 已有经验：增量导出遇到 E_CURSOR_STALE 时，先重新获取服务端游标，"
          "再用 maple export --cursor <fresh-cursor> 重试。本做法只适用于增量导出，"
          "全量导出不传游标。这个条件在逐会话摘要中未保留。\n")

    rows = [
        {"timestamp": "2026-10-08T02:00:00Z", "type": "session_meta", "payload": {
            "id": cid, "timestamp": "2026-10-08T02:00:00Z", "cwd": str(project)}},
        {"timestamp": "2026-10-08T02:01:00Z", "type": "response_item", "payload": {
            "type": "message", "role": "user", "content": [{"type": "input_text", "text":
                "Maple 导出确定用 JSON Lines，便于逐行审核差异。"}]}},
        {"timestamp": "2026-10-09T02:00:00Z", "type": "turn_context", "payload": {"cwd": str(project)}},
        {"timestamp": "2026-10-09T02:01:00Z", "type": "response_item", "payload": {
            "type": "function_call", "call_id": "call-export", "name": "exec_command",
            "arguments": json.dumps({"cmd": "maple test-export"})}},
        {"timestamp": "2026-10-09T02:02:00Z", "type": "response_item", "payload": {
            "type": "function_call_output", "call_id": "call-export", "output":
                "small_cases: 3 passed; full_batch: failed E_CURSOR_STALE; deployment: not_started"}},
        {"timestamp": "2026-10-09T02:03:00Z", "type": "response_item", "payload": {
            "type": "message", "role": "assistant", "content": [{"type": "output_text", "text":
                "三个小样本通过，完整批次失败，尚未部署，需要先修游标再重测。"}]}},
    ]
    write(f"sources/archived_sessions/rollout-2026-10-08T10-00-00-{cid}.jsonl",
          "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))

    topic_root = "sources/zcode/projects/project-0123456789abcdef/memory"
    write(f"{topic_root}/MEMORY.md", "# Memory Index\n\n"
          "- [导出格式](export.md) — 曾考虑 SQLite；全部部署完成。\n"
          "- [排错线索](undated.md) — 尚缺日期的检查建议。\n")
    write(f"{topic_root}/export.md", "---\nname: maple-export\n"
          "description: Maple 导出格式与说明约定\nmetadata:\n  node_type: memory\n"
          f"  type: user\n  originSessionId: {zid_a}\n---\n\n"
          "2026-10-08：讨论过 SQLite，尚未决定，来源为 origin 会话。\n\n"
          f"2026-10-09：用户确定 JSON Lines。之后在 {zid_b} 更正："
          "以后 Maple 的导出说明先写限制与适用条件，再给命令；仅适用于 Maple 导出说明。"
          "本次演示只给命令是一次性安排。原文标记仍保留早期 origin，不代表新增段落来自它。\n\n"
          "本文件没有部署执行证据。\n")
    write(f"{topic_root}/undated.md", "# 导出排错线索\n\n"
          "以前有人建议先检查分页游标是否失效，但日期和会话来源未保留；"
          "仅作为待核实线索。\n")

    db = sources / "zcode" / "db" / "db.sqlite"
    db.parent.mkdir(parents=True)
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE session (id TEXT PRIMARY KEY, title TEXT, directory TEXT,
            time_created INTEGER, time_updated INTEGER, parent_id TEXT);
        CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, data TEXT,
            time_created INTEGER, sequence INTEGER);
        CREATE TABLE part (id TEXT PRIMARY KEY, message_id TEXT, session_id TEXT,
            data TEXT, time_created INTEGER, sequence INTEGER);
    """)
    messages = [
        (zid_a, "2026-10-08T11:00:00+08:00", "可以先比较 SQLite 和 JSON Lines，先不要把方案写成已经决定。"),
        (zid_b, "2026-10-09T15:00:00+08:00", "Maple 确定 JSON Lines。以后 Maple 导出说明先写限制与适用条件，再给命令，"
         "仅适用于这个项目的导出说明。本次演示只给命令就好。"),
    ]
    for i, (sid, time, text) in enumerate(messages):
        ms = stamp(time)
        con.execute("INSERT INTO session VALUES (?,?,?,?,?,?)",
                    (sid, f"Maple 讨论 {i + 1}", str(project), ms, ms, None))
        con.execute("INSERT INTO message VALUES (?,?,?,?,?)",
                    (f"msg-{i}", sid, json.dumps({"role": "user"}), ms, 1))
        con.execute("INSERT INTO part VALUES (?,?,?,?,?,?)", (f"part-{i}", f"msg-{i}", sid,
                    json.dumps({"type": "text", "text": text}, ensure_ascii=False), ms, 1))
    con.commit()
    con.close()

    config = ['format = "xmemory/v1.5"', 'timezone = "Asia/Shanghai"', 'exclude_sessions = []', '']
    selections = [
        ("codex_v1", "memory", "codex", sources / "codex-v1"),
        ("codex_v2", "memory", "codex", sources / "codex-v2"),
        ("codex_sessions", "sessions", "codex", sources / "archived_sessions"),
        ("zcode_memory", "memory", "zcode", root / topic_root),
        ("zcode_sessions", "sessions", "zcode", db),
    ]
    for name, kind, client, path in selections:
        config.extend([f"[sources.{name}]", "enabled = true", f'kind = "{kind}"',
                       f'client = "{client}"', f"paths = [{json.dumps(str(path))}]", ""])
    config.extend(["[projects.Maple]", f"roots = [{json.dumps(str(project))}]", ""])
    write("memory/config.toml", "\n".join(config))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="必须尚不存在的独立实验目录")
    args = parser.parse_args()
    make_fixture(args.destination.resolve())
    print(args.destination.resolve())
