"""虚构原始记录上的行为测试；不读取个人历史，也不启动模型。"""
from pathlib import Path
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import conversation_reader_runtime as reader
from sync_conversation_readers import SKILLS, sync


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, filename, rows):
        p = self.root / filename
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        return p

    def read(self, client, path, *args):
        parsed = reader.parser(client).parse_args([*args, "--root", str(path)])
        return reader.run(client, parsed)

    def claude(self, sid="session-demo", text="用户决定保留回滚检查", **extra):
        return dict(type="user", sessionId=sid, uuid="u1", timestamp="2026-10-01T08:00:00Z",
                    cwd="/work/demo", message={"role": "user", "content": text}, **extra)

    def qoder_db(self, sid="session-demo"):
        p = self.root / "main.sqlite"
        with sqlite3.connect(p) as c:
            c.execute("CREATE TABLE chat_sessions(session_id TEXT PRIMARY KEY, title TEXT, cwd TEXT, created_at TEXT, updated_at TEXT, deleted_at TEXT)")
            c.execute("CREATE TABLE chat_session_messages(session_id TEXT, message_id TEXT, sequence INTEGER, payload_json TEXT, created_at INTEGER)")
            c.execute("INSERT INTO chat_sessions VALUES(?,?,?,?,?,NULL)", (sid, "测试对话", "/work/demo", "2026-10-01", "2026-10-02"))
        return p

    def test_five_scripts_run_independently(self):
        self.assertEqual(sync(), [])
        for client, skill in SKILLS.items():
            script = ROOT / "plugins/conversation-readers/skills" / skill / "scripts/read_conversations.py"
            run = subprocess.run([sys.executable, "-B", str(script), "list", "--root", str(self.root / "absent")],
                                 cwd=self.root, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            out = json.loads(run.stdout)
            self.assertEqual(out["client"], client)
            self.assertFalse(out["coverage"]["scan_complete"])
        self.assertFalse(list(self.root.rglob("__pycache__")))

    def test_archive_can_be_checked_after_extraction(self):
        import zipfile
        from build_conversation_readers import build, check
        archive, _ = build(self.root / "package")
        with zipfile.ZipFile(archive) as z:
            self.assertIsNone(z.testzip())
            z.extractall(self.root / "extract")
        extracted = self.root / "extract" / archive.stem
        self.assertTrue((extracted / "SHA256SUMS").is_file())
        self.assertEqual(check(extracted), [])
        with self.assertRaises(FileExistsError):
            build(self.root / "package")

    def test_private_absolute_paths_are_rejected(self):
        from build_conversation_readers import check
        plugin = self.root / "conversation-readers"
        shutil.copytree(ROOT / "plugins/conversation-readers", plugin)
        path = plugin / "README.md"
        original = path.read_text()
        self.assertEqual(check(plugin), [])
        # 仅使用虚构目录，覆盖原始路径和 JSON 转义形式。
        windows = "\\".join(("C:", "Users", "fixture-user", "notes.md"))
        paths = ["/".join(("", base, "fixture-user", "notes.md"))
                 for base in ("Users", "Volumes", "home")]
        paths += [windows, json.dumps(windows), windows.replace("\\", "/"),
                  windows.replace("Users", "users")]
        for private_path in paths:
            with self.subTest(path=private_path):
                path.write_text(original + "\n" + private_path + "\n")
                self.assertIn("Private path: README.md", check(plugin))

    def test_native_id_title_and_scope(self):
        p = self.write("alias.jsonl", [self.claude(), {"type": "ai-title", "sessionId": "session-demo", "aiTitle": "回滚方案"}])
        out = self.read("claude", p, "list", "--project", "/work/demo", "--query", "回滚")
        self.assertEqual(out["items"][0]["session_id"], "session-demo")
        self.assertEqual(out["items"][0]["title"], "回滚方案")
        self.assertEqual(self.read("claude", p, "list", "--project", "/work/dem")["items"], [])

    def test_codex_projection_and_reasoning_exclusion(self):
        p = self.write("rollout.jsonl", [
            {"type": "session_meta", "payload": {"id": "codex-demo", "cwd": "/work/demo"}},
            {"type": "response_item", "payload": {"type": "message", "id": "u1", "role": "user", "content": [{"type": "input_text", "text": "部署核对"}]}},
            {"type": "event_msg", "payload": {"type": "user_message", "message": "部署核对"}},
            {"type": "response_item", "payload": {"type": "reasoning", "summary": "HIDDEN"}},
            {"type": "response_item", "payload": {"type": "message", "role": "assistant", "channel": "analysis", "content": [{"type": "output_text", "text": "HIDDEN"}]}},
            {"type": "response_item", "payload": {"type": "message", "id": "a1", "role": "assistant", "content": [{"type": "output_text", "text": "尚未部署"}]}},
            {"type": "response_item", "payload": {"type": "function_call", "call_id": "call1", "name": "test", "arguments": "{}"}},
            {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "call1", "output": "通过"}},
        ])
        items = self.read("codex", p, "read", "--session", "codex-demo")["items"]
        self.assertEqual([x["text"] for x in items], ["部署核对", "尚未部署"])
        tools = self.read("codex", p, "read", "--session", "codex-demo", "--include-tools")["items"]
        self.assertEqual([x["call_id"] for x in tools[-2:]], ["call1", "call1"])
        self.assertEqual(self.read("codex", p, "search", "--query", "HIDDEN", "--include-tools")["items"], [])

    def test_claude_blocks_parents_duplicates_and_meta(self):
        a = {"type": "assistant", "sessionId": "session-demo", "uuid": "record-a", "parentUuid": "u1",
             "message": {"id": "a1", "content": [{"type": "thinking", "thinking": "HIDDEN"},
                          {"type": "text", "text": "计划"}, {"type": "text", "text": "计划"},
                          {"type": "tool_use", "id": "call1", "name": "Read", "input": {"path": "/work/demo"}}]}}
        p = self.write("session-demo.jsonl", [self.claude(), a, a, self.claude(text="INTERNAL", isMeta=True),
                     {"type": "user", "sessionId": "session-demo", "uuid": "result", "message": {"content": [{"type": "tool_result", "tool_use_id": "call1", "content": "文件内容"}]}}])
        items = self.read("claude", p, "read", "--session", "session-demo", "--include-tools")["items"]
        self.assertEqual([x["text"] for x in items if x["kind"] == "message"], ["用户决定保留回滚检查", "计划", "计划"])
        self.assertEqual(items[1]["parent_id"], "u1")
        self.assertEqual(items[-1]["role"], "tool")
        self.assertNotIn("HIDDEN", json.dumps(items))

    def test_workbuddy_distinct_format(self):
        p = self.write("wb.jsonl", [
            {"type": "message", "id": "u1", "sessionId": "wb", "role": "user", "content": [{"type": "input_text", "text": "检查部署"}]},
            {"type": "reasoning", "sessionId": "wb", "content": "HIDDEN"},
            {"type": "function_call", "id": "c1", "sessionId": "wb", "callId": "call1", "name": "test", "arguments": {"mode": "read"}},
            {"type": "function_call_result", "id": "r1", "sessionId": "wb", "callId": "call1", "name": "test", "output": "未部署"},
        ])
        items = self.read("workbuddy", p, "read", "--session", "wb", "--include-tools")["items"]
        self.assertEqual([x["kind"] for x in items], ["message", "tool_call", "tool_result"])
        self.assertEqual(items[-1]["call_id"], items[-2]["call_id"])

    def test_redaction_and_hidden_tool_keys(self):
        p = self.write("s.jsonl", [self.claude(text='password="private-value" Bearer secret-token sk-12345678901234567890')])
        text = self.read("claude", p, "read", "--session", "session-demo")["items"][0]["text"]
        for token in ["private-value", "secret-token", "sk-12345678901234567890"]:
            self.assertNotIn(token, text)
        self.assertNotIn("hidden-value", reader.tool_text({"result": "ok", "thinking": "hidden-value"}))

    def test_script_json_stays_valid_after_redaction(self):
        # 经脚本入口输出；带引号的键值在 JSON 转义后不能被二次替换破坏结构。
        text = 'password="fixture-pass" 与 API_KEY: "fixture-key"'
        p = self.write("s.jsonl", [self.claude(text=text),
                                   {"type": "ai-title", "sessionId": "session-demo", "aiTitle": "access_token=fixture-title"}])
        script = ROOT / "plugins/conversation-readers/skills" / SKILLS["claude"] / "scripts/read_conversations.py"
        for args in (["read", "--session", "session-demo"], ["search", "--query", "password"], ["list"]):
            with self.subTest(action=args[0]):
                run = subprocess.run([sys.executable, "-B", str(script), *args, "--root", str(p)],
                                     capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stderr)
                out = json.loads(run.stdout)
                self.assertTrue(out["items"])
                for secret in ["fixture-pass", "fixture-key", "fixture-title"]:
                    self.assertNotIn(secret, run.stdout)
                if args[0] == "list":
                    self.assertEqual(out["items"][0]["title"], "access_token=[REDACTED]")

    def test_search_fragment_and_long_record_expansion(self):
        text = "前" * 300 + "检索目标" + "后" * 300
        p = self.write("s.jsonl", [self.claude(text=text)])
        item = self.read("claude", p, "search", "--query", "检索目标", "--max-chars", "50")["items"][0]
        self.assertIn("检索目标", item["text"])
        self.assertTrue(item["truncated"])
        expanded = self.read("claude", p, "read", "--session", "session-demo", "--record", item["record_ref"],
                             "--text-offset", "300", "--max-chars", "50")["items"][0]
        self.assertEqual(expanded["text"], text[300:350])
        self.assertEqual(expanded["next_text_offset"], 350)

    def test_pagination_and_fingerprint(self):
        rows = [dict(self.claude(text=str(i)), uuid=f"u{i}") for i in range(5)]
        p = self.write("s.jsonl", rows)
        first = self.read("claude", p, "read", "--session", "session-demo", "--limit", "2")
        self.assertEqual(first["next_offset"], 2)
        fp = next(iter(first["snapshot"].values()))
        second = self.read("claude", p, "read", "--session", "session-demo", "--limit", "2", "--offset", "2", "--snapshot", fp)
        self.assertEqual([x["text"] for x in second["items"]], ["2", "3"])
        with p.open("a") as f:
            f.write(json.dumps(self.claude(text="新增")) + "\n")
        with self.assertRaisesRegex(reader.ReaderError, "snapshot_changed"):
            self.read("claude", p, "read", "--session", "session-demo", "--snapshot", fp)

    def test_partial_tail_reports_boundary(self):
        p = self.write("s.jsonl", [self.claude()])
        with p.open("a") as f:
            f.write('{"unfinished":')
        out = self.read("claude", p, "read", "--session", "session-demo")
        self.assertEqual(len(out["items"]), 1)
        self.assertTrue(any("partial_record" in w for w in out["warnings"]))
        self.assertFalse(out["coverage"]["scan_complete"])

    def test_known_old_id_not_hidden_by_scan_cap(self):
        self.write("old.jsonl", [self.claude(sid="old")])
        self.write("new.jsonl", [self.claude(sid="new")])
        out = self.read("claude", self.root, "read", "--session", "old", "--max-sessions", "1")
        self.assertEqual(out["items"][0]["session_id"], "old")
        listed = self.read("claude", self.root, "list", "--max-sessions", "1")
        self.assertFalse(listed["coverage"]["scan_complete"])

    def test_filename_is_only_a_hint_for_native_id(self):
        self.write("target.jsonl", [self.claude(sid="unrelated")])
        self.write("alias.jsonl", [self.claude(sid="target")])
        out = self.read("claude", self.root, "read", "--session", "claude:jsonl:target")
        self.assertEqual(out["items"][0]["session_id"], "target")

    def test_unicode_search_fragment_uses_original_offsets(self):
        text = "ß" * 30 + "TARGET" + "尾" * 30
        p = self.write("s.jsonl", [self.claude(text=text)])
        item = self.read("claude", p, "search", "--query", "target", "--max-chars", "12")["items"][0]
        self.assertIn("TARGET", item["text"])
        self.assertEqual(item["text"], text[item["text_offset"]:item["text_offset"] + 12])

    def test_unknown_source_is_not_empty_success(self):
        p = self.write("unknown.jsonl", [{"arbitrary": "not a client transcript"}])
        out = self.read("claude", p, "list")
        self.assertEqual(out["items"], [])
        self.assertFalse(out["coverage"]["scan_complete"])

    def test_qodercn_desktop_projection_and_read_only(self):
        p = self.qoder_db()
        payload = {"role": "assistant", "text": "same", "parts": [
            {"id": "p1", "type": "text", "text": "same"},
            {"id": "p2", "type": "thinking", "text": "HIDDEN"},
            {"id": "p3", "type": "tool", "tool": {"id": "c1", "name": "test", "input": {}, "response": "ok"}}],
            "tools": [{"id": "c1", "name": "test", "input": {}, "response": "ok"}]}
        with sqlite3.connect(p) as c:
            c.execute("INSERT INTO chat_session_messages VALUES(?,?,?,?,?)", ("session-demo", "m1", 1, json.dumps(payload), 1))
        before = p.read_bytes()
        items = self.read("qodercn", p, "read", "--session", "session-demo", "--include-tools")["items"]
        self.assertEqual([x["text"] for x in items], ["same", "{}", "ok"])
        self.assertEqual(p.read_bytes(), before)
        with reader.database(p) as c:
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("DELETE FROM chat_sessions")

    def test_qodercn_migration_duplicates_remain_separate(self):
        p = self.qoder_db()
        j = self.write("session-demo.jsonl", [self.claude()])
        args = reader.parser("qodercn").parse_args(["read", "--session", "session-demo", "--root", str(p), "--root", str(j)])
        with self.assertRaisesRegex(reader.ReaderError, "ambiguous_session"):
            reader.run("qodercn", args)
        chosen = self.read("qodercn", j, "read", "--session", "qodercn:jsonl:session-demo")
        self.assertEqual(len(chosen["items"]), 1)

    def test_zcode_order_tools_and_synthetic_exclusion(self):
        p = self.root / "db.sqlite"
        with sqlite3.connect(p) as c:
            c.execute("CREATE TABLE session(id TEXT, title TEXT, directory TEXT, time_created INTEGER, time_updated INTEGER)")
            c.execute("CREATE TABLE message(id TEXT, session_id TEXT, time_created INTEGER, sequence INTEGER, data TEXT)")
            c.execute("CREATE TABLE part(id TEXT, message_id TEXT, session_id TEXT, time_created INTEGER, sequence INTEGER, data TEXT)")
            c.execute("INSERT INTO session VALUES('s','测试','/work/demo',1,2)")
            c.execute("INSERT INTO message VALUES('m','s',1,1,?)", (json.dumps({"role": "assistant", "parentID": "u"}),))
            parts = [(2, {"type": "text", "text": "第二段"}), (1, {"type": "text", "text": "第一段"}),
                     (3, {"type": "reasoning", "text": "HIDDEN"}),
                     (4, {"type": "text", "text": "INTERNAL", "synthetic": True}),
                     (5, {"type": "tool", "callID": "call1", "tool": "Read", "state": {"input": {}, "output": "ok"}})]
            for seq, data in parts:
                c.execute("INSERT INTO part VALUES(?,?,?,?,?,?)", (str(seq), "m", "s", 1, seq, json.dumps(data)))
        before = hashlib.sha256(p.read_bytes()).hexdigest()
        items = self.read("zcode", p, "read", "--session", "s", "--include-tools")["items"]
        self.assertEqual([x["text"] for x in items], ["第一段", "第二段", "{}", "ok"])
        self.assertEqual(items[0]["parent_id"], "u")
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), before)

    def test_sqlite_wal_committed_data_visible(self):
        p = self.qoder_db()
        c = sqlite3.connect(p)
        self.addCleanup(c.close)
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("INSERT INTO chat_session_messages VALUES(?,?,?,?,?)", ("session-demo", "wal-msg", 1, json.dumps({"role": "user", "text": "WAL 中已提交"}), 1))
        c.commit()
        self.assertTrue(Path(str(p) + "-wal").exists())
        items = self.read("qodercn", p, "read", "--session", "session-demo")["items"]
        self.assertEqual(items[0]["text"], "WAL 中已提交")

    def test_schema_mismatch_reported(self):
        p = self.root / "unknown.sqlite"
        with sqlite3.connect(p) as c:
            c.execute("CREATE TABLE other(id TEXT)")
        out = self.read("zcode", p, "list")
        self.assertFalse(out["coverage"]["scan_complete"])
        self.assertIn("unsupported_schema", out["warnings"][0])

    def test_sqlite_parent_directory_discovers_known_database(self):
        self.qoder_db()
        out = self.read("qodercn", self.root, "list")
        self.assertEqual(out["items"][0]["session_id"], "session-demo")
        self.assertEqual(out["items"][0]["variant"], "desktop")


if __name__ == "__main__":
    unittest.main()
