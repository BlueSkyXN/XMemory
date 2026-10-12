from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins/xmemory/skills/xmemory/scripts"))
import xmemory_runtime as xm  # noqa: E402

TZ = ZoneInfo("Asia/Shanghai")


def ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / "memory"
        self.work = self.base / "work"
        (self.work / "demo").mkdir(parents=True)
        (self.work / "other").mkdir(parents=True)
        self.db = self.base / "zcode.sqlite"
        self.make_zcode()
        self.run_ok("init", "--timezone", "Asia/Shanghai")
        cfg = (self.root / "config.toml").read_text(encoding="utf-8")
        cfg += f'\n[sources]\nzcode = [{json.dumps(str(self.db))}]\ncodex_memories = {json.dumps(str(self.base / "codex"))}\n'
        (self.root / "config.toml").write_text(cfg, encoding="utf-8")
        self.run_ok("project", "add", "demo", "--path", str(self.work / "demo"))

    def tearDown(self):
        self.tmp.cleanup()

    # ---------- helpers ----------
    def cli(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = xm.main(["--root", str(self.root), *argv])
        return code, json.loads(buf.getvalue())

    def run_ok(self, *argv):
        code, out = self.cli(*argv)
        self.assertEqual(code, 0, out)
        return out

    def make_zcode(self):
        now = datetime.now(TZ)
        self.night = (now - timedelta(days=2)).replace(hour=23, minute=30, second=0, microsecond=0)
        with sqlite3.connect(self.db) as c:
            c.execute("CREATE TABLE session(id TEXT, title TEXT, directory TEXT, time_created INTEGER, time_updated INTEGER, parent_id TEXT)")
            c.execute("CREATE TABLE message(id TEXT, session_id TEXT, time_created INTEGER, sequence INTEGER, data TEXT)")
            c.execute("CREATE TABLE part(id TEXT, message_id TEXT, session_id TEXT, time_created INTEGER, sequence INTEGER, data TEXT)")
            self.add_session(c, "sess_a", "跨午夜的会话", str(self.work / "demo" / "sub"),
                             [("user", self.night, "以后发布前先等我确认，不要直接推送"),
                              ("assistant", self.night + timedelta(minutes=5), "好的，已改为等待确认"),
                              ("user", self.night + timedelta(hours=1), "第二天继续：把发布清单补全")])
            self.add_session(c, "sess_active", "仍在进行", str(self.work / "demo"),
                             [("user", datetime.now(TZ) - timedelta(minutes=5), "正在进行的工作")])
            self.add_session(c, "sess_other", "未登记项目", str(self.work / "other"),
                             [("user", self.night, "别的项目")])
            self.add_session(c, "sess_child", "子代理", str(self.work / "demo"),
                             [("user", self.night, "子代理内容")], parent="sess_a")

    def add_session(self, c, sid, title, directory, messages, parent=None):
        stamps = [m[1] for m in messages]
        c.execute("INSERT INTO session VALUES(?,?,?,?,?,?)", (sid, title, directory, ms(min(stamps)), ms(max(stamps)), parent))
        for i, (role, when, text) in enumerate(messages, 1):
            mid = f"{sid}-m{i}"
            c.execute("INSERT INTO message VALUES(?,?,?,?,?)", (mid, sid, ms(when), i, json.dumps({"role": role})))
            c.execute("INSERT INTO part VALUES(?,?,?,?,?,?)", (f"{mid}-p", mid, sid, ms(when), 1,
                                                               json.dumps({"type": "text", "text": text})))

    def submit(self, job, summary="# 发布前确认\n\n用户要求发布前先确认，不要直接推送；已改为等待确认。",
               raw="- 偏好信号：发布时，用户说“以后发布前先等我确认，不要直接推送” → 默认先确认", slug="release-confirm"):
        out = Path(self.root / ".xmemory" / "tasks" / job / "output.json")
        out.write_text(json.dumps({"slug": slug, "summary": summary, "raw_memory": raw}, ensure_ascii=False), encoding="utf-8")
        return self.cli("submit", job, "--client", "codex")

    def extract_all(self):
        digests = []
        while True:
            job = self.run_ok("next", "--client", "codex")["job"]
            if not job:
                return digests
            digests.append(self.submit(job)[1]["digest"])

    def codex_summary(self, root, tid, updated, body, started=None):
        mem = root / "rollout_summaries"
        mem.mkdir(parents=True, exist_ok=True)
        name = (started or updated).strftime("%Y-%m-%dT%H-%M-%S") + f"-AbCd-task_{tid[-2:]}.md"
        (mem / name).write_text(f"thread_id: {tid}\nupdated_at: {updated.isoformat()}\nrollout_path: /tmp/{tid}.jsonl\n"
                                f"cwd: {self.work / 'demo'}\ngit_branch: main\n\n{body}\n", encoding="utf-8")
        return mem / name

    def codex_roots(self, *roots):
        cfg = xm.load_config(self.root / "config.toml")
        if roots:
            cfg["sources"]["codex_memories"] = [str(r) for r in roots]
        else:
            del cfg["sources"]["codex_memories"]
        (self.root / "config.toml").write_text(xm.dump_config(cfg), encoding="utf-8")

    def git_log(self):
        return subprocess.run(["git", "-C", str(self.root), "log", "--format=%s"], capture_output=True, text=True).stdout

    def write_outputs(self, awareness=None):
        p = self.root / "projects" / "demo"
        p.mkdir(parents=True, exist_ok=True)
        (p / "AWARENESS.md").write_text(awareness or (
            "# demo 意识\n\n## 当前认识\n- 发布前需确认\n\n## 近期变化\n- 无\n\n## 冲突与未知\n- 无\n\n"
            "## 待处理\n- [ ] release-checklist：补全发布清单；状态：进行中\n\n## 记忆候选\n- 无\n"), encoding="utf-8")
        (p / "MEMORY.md").write_text("# 任务组：发布流程\n\n范围：发布\n\n## 用户偏好\n- 发布前先确认\n", encoding="utf-8")
        (self.root / "memory_summary.md").write_text("# XMemory 全局摘要\n\n## 项目入口\n- demo：发布流程整理中\n", encoding="utf-8")

    # ---------- tests ----------
    def test_init_refuses_foreign_directory(self):
        foreign = self.base / "foreign"
        foreign.mkdir()
        (foreign / "MEMORY.md").write_text("old", encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = xm.main(["--root", str(foreign), "init"])
        self.assertEqual(code, 2)
        self.assertIn("不自动接管", json.loads(buf.getvalue())["error"])

    def test_scan_splits_by_local_day_and_respects_scope(self):
        report = self.run_ok("scan")["clients"]["zcode"]
        self.assertEqual(report["subagent_skipped"], 1)
        self.assertEqual(report["active"], 1)
        con = sqlite3.connect(self.root / ".xmemory/state.sqlite")
        days = sorted(r[0] for r in con.execute("SELECT day FROM segments WHERE ref='zcode:sqlite:sess_a'"))
        first = self.night.date()
        self.assertEqual(days, [first.isoformat(), (first + timedelta(days=1)).isoformat()])
        self.assertEqual(con.execute("SELECT COUNT(*) FROM segments WHERE ref LIKE '%sess_other'").fetchone()[0], 0)
        self.assertEqual(con.execute("SELECT project FROM sessions WHERE ref='zcode:sqlite:sess_other'").fetchone()[0], "unassigned")

    def test_window_excludes_old_days(self):
        self.run_ok("scan", "--days", "1")
        con = sqlite3.connect(self.root / ".xmemory/state.sqlite")
        self.assertEqual(con.execute("SELECT COUNT(*) FROM segments").fetchone()[0], 0)

    def test_extract_submit_writes_code_owned_metadata(self):
        self.run_ok("scan")
        nxt = self.run_ok("next", "--client", "codex")
        text = Path(nxt["input"]).read_text(encoding="utf-8")
        self.assertIn("会话：zcode:sqlite:sess_a", text)
        code, out = self.submit(nxt["job"])
        self.assertEqual(code, 0, out)
        digest = (self.root / out["digest"]).read_text(encoding="utf-8")
        meta = xm.frontmatter(digest)
        self.assertEqual(meta["session_ref"], "zcode:sqlite:sess_a")
        self.assertEqual(meta["project"], "demo")
        self.assertEqual(meta["extracted_by"], "codex")
        self.assertTrue(meta["extracted_at"].endswith("+08:00"))
        self.assertIn("extract", self.git_log())
        code, out = self.submit(nxt["job"])
        self.assertEqual(code, 2)
        self.assertIn("不是已领取", out["error"])

    def test_submit_validation_and_empty_and_redaction(self):
        self.run_ok("scan")
        job = self.run_ok("next", "--client", "codex")["job"]
        out = self.root / ".xmemory/tasks" / job / "output.json"
        out.write_text(json.dumps({"slug": "x", "summary": "s"}), encoding="utf-8")
        self.assertEqual(self.cli("submit", job, "--client", "codex")[0], 2)
        code, res = self.submit(job, raw="- 令牌 sk-" + "a" * 30 + " 已轮换，记得以后先确认再发布再继续工作")
        self.assertEqual(code, 0, res)
        self.assertTrue(res["redacted"])
        self.assertNotIn("sk-aaaa", (self.root / res["digest"]).read_text(encoding="utf-8"))
        job = self.run_ok("next", "--client", "codex")["job"]
        code, res = self.submit(job, summary="", raw="", slug="")
        self.assertEqual((code, res["status"], res["digest"]), (0, "empty", None))

    def test_changed_session_is_reextracted_as_modification(self):
        self.run_ok("scan")
        self.extract_all()
        with sqlite3.connect(self.db) as c:
            later = self.night + timedelta(hours=1, minutes=10)
            c.execute("INSERT INTO message VALUES('sess_a-m9','sess_a',?,9,?)", (ms(later), json.dumps({"role": "user"})))
            c.execute("INSERT INTO part VALUES('sess_a-m9-p','sess_a-m9','sess_a',?,1,?)",
                      (ms(later), json.dumps({"type": "text", "text": "清单里加上回滚步骤"})))
            c.execute("UPDATE session SET time_updated=? WHERE id='sess_a'", (ms(later),))
        report = self.run_ok("scan")["clients"]["zcode"]
        self.assertEqual(report["changed_jobs"], 1)
        self.assertEqual(len(self.extract_all()), 1)

    def test_codex_import_is_read_only_and_idempotent(self):
        mem = self.base / "codex" / "rollout_summaries"
        mem.mkdir(parents=True)
        started = datetime.now(timezone.utc) - timedelta(days=1)
        name = started.strftime("%Y-%m-%dT%H-%M-%S") + "-AbCd-demo_task.md"
        tid = "019e0000-0000-7000-8000-000000000001"
        summary = (f"thread_id: {tid}\nupdated_at: {started.isoformat()}\nrollout_path: /tmp/r.jsonl\n"
                   f"cwd: {self.work / 'demo'}\n\n# 完成演示任务\n\n## Task 1: 演示\n- 结果：成功\n")
        (mem / name).write_text(summary, encoding="utf-8")
        (self.base / "codex" / "raw_memories.md").write_text(
            f"# Raw\n\n## Thread `{tid}`\nupdated_at: {started.isoformat()}\ncwd: {self.work / 'demo'}\n\n### Task 1: 演示\n- 偏好\n",
            encoding="utf-8")
        before = (mem / name).read_bytes()
        out = self.run_ok("import", "codex")
        self.assertEqual(out["imported"], 1)
        self.assertEqual(self.run_ok("import", "codex")["unchanged"], 1)
        self.assertEqual((mem / name).read_bytes(), before)
        digest = next((self.root / "sessions" / "codex").rglob("*.md")).read_text(encoding="utf-8")
        self.assertIn("origin: codex-memory", digest)
        self.assertIn("### Task 1: 演示", digest)

    def test_codex_import_merges_v1_and_v2(self):
        v1, v2 = self.base / "codex-home" / "memories", self.base / "codex-home" / "memories_v2"
        self.codex_roots(v1, v2)
        t1 = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=2)
        t2 = t1 + timedelta(hours=5)
        a, b, c = (f"019e0000-0000-7000-8000-0000000000{n}" for n in ("a1", "b2", "c3"))
        self.codex_summary(v1, a, t1, "# A 任务（V1）\n\n- 结果：完成")
        self.codex_summary(v1, b, t1, "# B 任务（V1 旧快照）\n\n- 结果：进行中")
        (v1 / "raw_memories.md").write_text("# Raw\n\n" + "".join(
            f"## Thread `{t}`\nupdated_at: {t1.isoformat()}\ncwd: {self.work / 'demo'}\n\n- {t[-2:]} 原始要点\n\n"
            for t in (a, b)), encoding="utf-8")
        self.codex_summary(v2, a, t1, "# A 任务（V2）\n\n- 结果：完成")
        self.codex_summary(v2, b, t2, "# B 任务（V2 新快照）\n\n- 结果：已合并")
        self.codex_summary(v2, c, t2, "# C 任务\n\n前半段…1234 chars truncated…后半段")
        sources = {p: p.read_bytes() for p in (self.base / "codex-home").rglob("*") if p.is_file()}
        out = self.run_ok("import", "codex")
        self.assertEqual((out["threads"], out["imported"], out["summary_only"], out["truncated"]), (3, 3, 2, 1), out)
        self.assertEqual([r["version"] for r in out["roots"]], ["v1", "v2"])
        self.assertEqual(out["warnings"], [])
        digests = {xm.frontmatter(p.read_text(encoding="utf-8"))["session_ref"]: p.read_text(encoding="utf-8")
                   for p in (self.root / "sessions" / "codex").rglob("*.md")}
        self.assertIn("codex_memory: v1", digests[f"codex:jsonl:{a}"])
        self.assertIn("a1 原始要点", digests[f"codex:jsonl:{a}"])
        self.assertIn("codex_memory: v2", digests[f"codex:jsonl:{b}"])
        self.assertIn("V2 新快照", digests[f"codex:jsonl:{b}"])
        self.assertIn("不单独保存原始记忆块", digests[f"codex:jsonl:{b}"])
        self.assertIn("codex_truncated_chars: 1234", digests[f"codex:jsonl:{c}"])
        self.assertEqual({p: p.read_bytes() for p in sources}, sources)
        again = self.run_ok("import", "codex")
        self.assertEqual((again["imported"], again["unchanged"]), (0, 3))
        self.assertEqual(self.run_ok("status")["last_codex_import"]["summary_only"], 2)
        # Codex 按保留上限删掉旧摘要后，已导入的副本不受影响
        for path in (self.base / "codex-home").rglob("*task_a1.md"):
            path.unlink()
        self.run_ok("import", "codex")
        self.assertTrue(any("a1 原始要点" in p.read_text(encoding="utf-8")
                            for p in (self.root / "sessions" / "codex").rglob("*.md")))

    def test_codex_import_reports_thinning(self):
        v1, v2 = self.base / "codex-home" / "memories", self.base / "codex-home" / "memories_v2"
        self.codex_roots(v1, v2, self.base / "missing-root")
        now = datetime.now(timezone.utc).replace(microsecond=0)
        self.codex_summary(v1, "019e0000-0000-7000-8000-0000000000d4", now - timedelta(days=10), "# 旧任务\n\n- 完成")
        self.codex_summary(v2, "019e0000-0000-7000-8000-0000000000e5", now - timedelta(days=1), "# 新任务\n\n- 完成")
        (v2 / "rollout_summaries" / "broken.md").write_text("没有文件头的摘要\n", encoding="utf-8")
        warnings = "\n".join(self.run_ok("import", "codex")["warnings"])
        self.assertIn("missing-root", warnings)
        self.assertIn("认不出格式", warnings)
        self.assertIn("没有 raw_memories.md", warnings)
        self.assertIn("Codex V1 记忆最新只到", warnings)
        self.assertIn("认不出格式", "\n".join(self.run_ok("status")["last_codex_import"]["warnings"]))

    def test_codex_import_defaults_flag_unknown_versions(self):
        home = self.base / "home"
        self.codex_summary(home / ".codex" / "memories", "019e0000-0000-7000-8000-0000000000f6",
                           datetime.now(timezone.utc) - timedelta(days=1), "# 任务\n\n- 完成")
        (home / ".codex" / "memories_v3" / "rollout_summaries").mkdir(parents=True)
        (home / ".codex" / "memories_v2_1.sqlite").write_text("", encoding="utf-8")
        self.codex_roots()
        with mock.patch.dict(os.environ, {"HOME": str(home)}):
            out = self.run_ok("import", "codex")
        self.assertEqual(out["imported"], 1)
        self.assertEqual([w for w in out["warnings"] if "不认识" in w],
                         ["发现本版不认识的 Codex 记忆目录 memories_v3，未导入；需要升级 XMemory"])

    def test_config_parser_round_trips_and_matches_toml(self):
        cfg = {"format": xm.FORMAT, "timezone": "Asia/Shanghai", "quiet_minutes": 60, "flag": False,
               "clients": {"zcode": "extract", "codex": "import"},
               "sources": {"zcode": ["/tmp/a b/zcode.db", "C:\\Users\\x\\db"], "codex_memories": "/tmp/m"},
               "restrict": {"zcode": ["codex", "claude"]},
               "projects": {"演示 \"项目\"\t\u007f😀": {"roots": ["/tmp/演示"], "enabled": True}, "plain": {"roots": [], "enabled": False}}}
        text = xm.dump_config(cfg)
        self.assertEqual(xm.TomlSubset(text).parse(), cfg)
        hand = (
            "# 注释\nformat = 'xmemory/v1.4'  # 行尾注释\nbackfill_days = 1_000\nneg = -3\n"
            "[ projects . \"甲\" ]\nroots = [\n  \"/tmp/甲\",  # 第一个\n  '/tmp/乙',\n]\nenabled = true\n"
            "[projects]\n[clients]\n\"zcode\" = \"\\u4e2d\\U0001F600\"\nempty = []\n")
        expected = {"format": "xmemory/v1.4", "backfill_days": 1000, "neg": -3,
                    "projects": {"甲": {"roots": ["/tmp/甲", "/tmp/乙"], "enabled": True}},
                    "clients": {"zcode": "中😀", "empty": []}}
        self.assertEqual(xm.TomlSubset(hand).parse(), expected)
        try:
            import tomllib
        except ImportError:
            tomllib = None
        if tomllib:
            self.assertEqual(tomllib.loads(text), cfg)
            self.assertEqual(tomllib.loads(hand), expected)
        # 合法 TOML 但超出子集：明确报错，不去猜
        unsupported = ("a = {x = 1}", "a = 1.5", "a = 2026-10-12", "a.b = 1", 'a = """x"""', "[[t]]")
        # 本身就不合法的 TOML
        invalid = ("a = 1\na = 2", "[t]\n[t]", 'a = "x', "a = 1 b = 2", "a = [1 2]", 'a = "\\q"', "a = 01", "= 1")
        for bad in unsupported + invalid:
            with self.subTest(bad=bad):
                with self.assertRaises(xm.XMemoryError) as ctx:
                    xm.TomlSubset(bad).parse()
                self.assertIn("行", str(ctx.exception))
                if tomllib and bad in invalid:
                    with self.assertRaises(tomllib.TOMLDecodeError):
                        tomllib.loads(bad)
                elif tomllib:
                    tomllib.loads(bad)

    def test_consolidation_lifecycle(self):
        self.run_ok("scan")
        self.extract_all()
        begin = self.run_ok("consolidate", "begin", "--scope", "demo", "--client", "codex")
        self.assertTrue(begin["changed"])
        self.assertIn("[新增] sessions/zcode/", Path(begin["input"]).read_text(encoding="utf-8"))
        code, out = self.cli("consolidate", "begin", "--scope", "demo", "--client", "claude")
        self.assertEqual(code, 2, out)
        self.write_outputs()
        done = self.run_ok("consolidate", "finish", begin["id"])
        self.assertTrue(done["committed"])
        self.assertTrue(done["timeline"])
        aware = (self.root / "projects/demo/AWARENESS.md").read_text(encoding="utf-8")
        self.assertTrue(aware.startswith("<!-- xmemory: updated "))
        timeline = (self.root / done["timeline"][0]).read_text(encoding="utf-8")
        self.assertIn("../../../sessions/zcode/", timeline)
        self.assertEqual(self.run_ok("check")["errors"], [])
        self.assertFalse(self.run_ok("consolidate", "begin", "--scope", "demo")["changed"])

    def test_finish_rejects_bad_outputs_and_abort_restores(self):
        self.run_ok("scan")
        self.extract_all()
        begin = self.run_ok("consolidate", "begin", "--scope", "demo", "--client", "codex")
        self.write_outputs()
        self.run_ok("consolidate", "finish", begin["id"])
        note = self.run_ok("note", "清单要包含回滚", "--project", "demo", "--client", "zcode")
        begin = self.run_ok("consolidate", "begin", "--scope", "demo", "--client", "codex")
        self.assertIn(note["note"], Path(begin["input"]).read_text(encoding="utf-8"))
        self.write_outputs(awareness="# demo\n\n## 当前认识\n- x\n\n## 近期变化\n\n## 冲突与未知\n\n## 待处理\n\n## 记忆候选\n")
        digest = next((self.root / "sessions").rglob("*.md"))
        digest.write_text(digest.read_text(encoding="utf-8") + "\n手改\n", encoding="utf-8")
        code, out = self.cli("consolidate", "finish", begin["id"])
        self.assertEqual(code, 1)
        joined = "\n".join(out["errors"])
        self.assertIn("越界改动", joined)
        self.assertIn("release-checklist", joined)
        subprocess.run(["git", "-C", str(self.root), "checkout", "--", "sessions"], check=True)
        self.run_ok("consolidate", "abort", begin["id"])
        self.assertIn("release-checklist", (self.root / "projects/demo/AWARENESS.md").read_text(encoding="utf-8"))
        self.assertIsNone(self.run_ok("status")["consolidation_lock"])

    def test_consolidation_batches_oldest_first(self):
        self.run_ok("scan")
        digests = sorted(self.extract_all())
        self.assertEqual(len(digests), 2)
        begin = self.run_ok("consolidate", "begin", "--scope", "demo", "--max-inputs", "1")
        self.assertEqual((begin["inputs"], begin["remaining_after_this_batch"]), (1, 1))
        text = Path(begin["input"]).read_text(encoding="utf-8")
        self.assertIn(self.night.date().isoformat(), text.split("## [", 2)[1])
        self.assertIn("（输入结束", text)
        self.write_outputs()
        self.run_ok("consolidate", "finish", begin["id"])
        again = self.run_ok("consolidate", "begin", "--scope", "demo", "--max-inputs", "1")
        self.assertEqual((again["inputs"], again["remaining_after_this_batch"]), (1, 0))

    def set_config(self, key, value):
        path = self.root / "config.toml"
        text = path.read_text(encoding="utf-8")
        import re as _re
        path.write_text(_re.sub(rf"(?m)^{key} = .*$", f"{key} = {value}", text), encoding="utf-8")

    def test_shrinking_parts_become_obsolete_without_loop(self):
        self.set_config("max_job_chars", 30)
        self.run_ok("scan")
        con = sqlite3.connect(self.root / ".xmemory/state.sqlite")
        self.assertGreater(con.execute("SELECT MAX(parts) FROM segments").fetchone()[0], 1)
        self.extract_all()
        before = len(list((self.root / "sessions").rglob("*.md")))
        self.set_config("max_job_chars", 60000)
        report = self.run_ok("scan", "--force")
        self.assertGreater(report["clients"]["zcode"]["obsolete_jobs"], 0)
        self.assertTrue(report["removed_digests"])
        self.assertLess(len(list((self.root / "sessions").rglob("*.md"))), before)
        jobs = 0
        while self.run_ok("next", "--client", "codex")["job"]:
            jobs += 1
            self.assertLess(jobs, 10)
            con2 = sqlite3.connect(self.root / ".xmemory/state.sqlite")
            job = con2.execute("SELECT job_id FROM segments WHERE status='leased'").fetchone()[0]
            self.submit(job)
        self.assertEqual(self.run_ok("check")["errors"], [])

    def test_chinese_project_name_round_trip(self):
        self.run_ok("project", "add", "演示项目", "--path", str(self.work / "other"))
        self.run_ok("scan")
        while (job := self.run_ok("next", "--client", "codex", "--project", "演示项目")["job"]):
            self.submit(job)
        begin = self.run_ok("consolidate", "begin", "--scope", "演示项目", "--client", "codex")
        p = self.root / "projects" / "演示项目"
        p.mkdir(parents=True)
        (p / "AWARENESS.md").write_text("# 演示项目\n\n## 当前认识\n- x\n\n## 近期变化\n\n## 冲突与未知\n\n"
                                        "## 待处理\n\n## 记忆候选\n", encoding="utf-8")
        (p / "MEMORY.md").write_text("# 任务组：演示\n", encoding="utf-8")
        done = self.run_ok("consolidate", "finish", begin["id"])
        self.assertTrue(done["committed"])
        self.assertTrue(any("演示项目" in t for t in done["timeline"]))
        self.assertEqual(self.run_ok("check")["errors"], [])

    def test_missing_section_rejected(self):
        self.run_ok("scan")
        self.extract_all()
        begin = self.run_ok("consolidate", "begin", "--scope", "demo")
        self.write_outputs(awareness="# demo\n\n## 当前认识\n- x\n")
        code, out = self.cli("consolidate", "finish", begin["id"])
        self.assertEqual(code, 1)
        self.assertTrue(any("缺少小节" in e for e in out["errors"]))

    def test_forget_removes_inputs_and_blocks_recollection(self):
        self.run_ok("scan")
        self.extract_all()
        out = self.run_ok("forget", "--session", "zcode:sqlite:sess_a", "--reason", "用户要求")
        self.assertEqual(len(out["removed_digests"]), 2)
        self.assertFalse(list((self.root / "sessions").rglob("*.md")))
        self.run_ok("scan", "--force")
        self.assertIsNone(self.run_ok("next", "--client", "codex")["job"])

    def test_check_detects_hand_edit(self):
        self.run_ok("scan")
        self.extract_all()
        digest = next((self.root / "sessions").rglob("*.md"))
        digest.write_text(digest.read_text(encoding="utf-8") + "x", encoding="utf-8")
        result = self.cli("check")[1]
        self.assertFalse(result["ok"])
        self.assertTrue(any("手工改动" in e for e in result["errors"]))

    def test_office_memory_import_is_verbatim(self):
        om = self.base / "om"
        (om / "memory").mkdir(parents=True)
        (om / "awareness").mkdir()
        body = "第一句结论。后面的条件与例外保持原样。"
        (om / "memory" / "MEMORY.md").write_text(
            "# Project Memory\n\n## release.confirm-first\n- Scope: project\n- Kind: preference\n"
            "- Sources: project#README.md:L1-L2\n- Observed: 2026-09-01\n- Review: 2026-12-01\n\n" + body + "\n",
            encoding="utf-8")
        (om / "memory" / "2026-09-01.md").write_text(
            "# Daily Project Memory — 2026-09-01\n- Focus: project\n\n## Meaningful changes\n\n- 变化 A\n\n"
            "## Decisions and constraints\n\n- 决定 B\n", encoding="utf-8")
        (om / "awareness" / "AWARENESS.md").write_text(
            "# Project Awareness\n- Updated: 2026-09-01\n\n## Current understanding\n\n- 认识\n\n## Relevant changes\n\n- 变化\n\n"
            "## Conflicts and unknowns\n\n- 无\n\n## Needs attention\n\n- 待办\n\n## Memory candidates\n\n- 候选\n",
            encoding="utf-8")
        out = self.run_ok("import", "office-memory", "--project", "demo", "--path", str(om))
        self.assertEqual(out["topics"], 1)
        topic = (self.root / "projects/demo/topics/release.confirm-first.md").read_text(encoding="utf-8")
        self.assertIn(body, topic)
        self.assertIn("type: 偏好", topic)
        aware = (self.root / "projects/demo/AWARENESS.md").read_text(encoding="utf-8")
        for name in xm.AWARENESS_SECTIONS:
            self.assertIn(f"## {name}", aware)
        self.assertIn("## 决定与约束", (self.root / "projects/demo/daily/2026-09-01.md").read_text(encoding="utf-8"))

    def test_worktree_resolves_to_main_project(self):
        repo = self.work / "demo"
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                        "--allow-empty", "-m", "i"], check=True)
        wt = self.base / "wt-demo"
        subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", str(wt)], check=True)
        lib = xm.Library(self.root)
        self.assertEqual(lib.resolve_project(str(wt)), "demo")
        self.assertEqual(lib.resolve_project(str(self.work / "other")), "unassigned")

    def test_method_paths_exist(self):
        self.run_ok("scan")
        nxt = self.run_ok("next", "--client", "codex")
        self.assertTrue(Path(nxt["instructions"]).is_file(), nxt["instructions"])
        self.assertIn("（输入结束", Path(nxt["input"]).read_text(encoding="utf-8"))
        self.submit(nxt["job"])
        begin = self.run_ok("consolidate", "begin", "--scope", "demo")
        self.assertTrue(Path(begin["instructions"]).is_file(), begin["instructions"])

    def test_session_command_reads_original(self):
        out = self.run_ok("session", "zcode:sqlite:sess_a", "--limit", "2")
        self.assertEqual(len(out["items"]), 2)
        self.assertIn("以后发布前先等我确认", out["items"][0]["text"])
        self.assertTrue(out["has_more"])
        rest = self.run_ok("session", "zcode:sqlite:sess_a", "--offset", str(out["next_offset"]))
        self.assertFalse(rest["has_more"])
        code, missing = self.cli("session", "zcode:sqlite:sess_missing")
        self.assertEqual(code, 2)
        self.assertIn("本机找不到", missing["error"])

    def test_keyless_pending_items_are_protected(self):
        self.run_ok("scan")
        self.extract_all()
        begin = self.run_ok("consolidate", "begin", "--scope", "demo")
        self.write_outputs(awareness="# demo\n\n## 当前认识\n- x\n\n## 近期变化\n\n## 冲突与未知\n\n"
                                     "## 待处理\n\n- **洞察研究线**：例会反馈回收\n- NoteToFilm 收尾（三分叉）\n\n## 记忆候选\n")
        self.run_ok("consolidate", "finish", begin["id"])
        self.run_ok("note", "补充一条", "--project", "demo", "--client", "codex")
        begin = self.run_ok("consolidate", "begin", "--scope", "demo")
        self.write_outputs(awareness="# demo\n\n## 当前认识\n- x\n\n## 近期变化\n\n## 冲突与未知\n\n"
                                     "## 待处理\n\n- **洞察研究线**：继续\n\n## 记忆候选\n")
        code, out = self.cli("consolidate", "finish", begin["id"])
        self.assertEqual(code, 1)
        self.assertTrue(any("NoteToFilm" in e for e in out["errors"]), out)

    def test_codex_coverage_reports_unextracted_sessions(self):
        mem = self.base / "codex" / "rollout_summaries"
        mem.mkdir(parents=True)
        sessions = self.base / "codex-sessions" / "2026"
        sessions.mkdir(parents=True)
        for tid in ("019e0000-0000-7000-8000-00000000000a", "019e0000-0000-7000-8000-00000000000b"):
            (sessions / f"rollout-x-{tid}.jsonl").write_text(json.dumps(
                {"type": "session_meta", "payload": {"id": tid, "cwd": str(self.work / "demo")}}) + "\n", encoding="utf-8")
        child = "019e0000-0000-7000-8000-00000000000c"
        (sessions / f"rollout-x-{child}.jsonl").write_text(json.dumps(
            {"type": "session_meta", "payload": {"id": child, "cwd": str(self.work / "demo"),
                                                 "source": {"subagent": {"thread_spawn": {}}}}}) + "\n", encoding="utf-8")
        cfg = (self.root / "config.toml").read_text(encoding="utf-8")
        cfg = cfg.replace("[sources]\n", f"[sources]\ncodex = [{json.dumps(str(self.base / 'codex-sessions'))}]\n")
        (self.root / "config.toml").write_text(cfg, encoding="utf-8")
        out = self.run_ok("import", "codex")
        self.assertEqual((out["codex_sessions_in_scope"], out["not_extracted_by_codex"]), (2, 2))

    def test_notice_uses_template(self):
        notice = self.run_ok("notice")["notice"]
        self.assertIn(str(self.root), notice)
        self.assertNotIn("{{root}}", notice)


if __name__ == "__main__":
    unittest.main()
