from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins/xmemory/skills/xmemory/scripts"
sys.path.insert(0, str(SCRIPTS))
from status import FORMAT, frontmatter, report  # noqa: E402
from toml_subset import TomlSubset  # noqa: E402

NOW = datetime.fromisoformat("2026-10-12T18:00:00+08:00")
CONFIG = '''format = "xmemory/v1.5"
timezone = "Asia/Shanghai"
exclude_sessions = []
[sources.claude]
enabled = true
kind = "sessions"
client = "claude"
paths = ["/unread-external-source"]
[projects.demo]
roots = ["/unread-project"]
'''


def snapshot(root):
    return {p.relative_to(root).as_posix(): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
            for p in root.rglob("*") if p.is_file() and not p.is_symlink()}


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "memory"
        self.root.mkdir()
        (self.root / "config.toml").write_text(CONFIG)

    def write(self, path, kind, updated="2026-10-12T10:00:00+08:00", body="", **fields):
        data = dict(format=FORMAT, kind=kind, updated=updated, **fields)
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        header = "\n".join(k + ": " + json.dumps(v, ensure_ascii=False) for k, v in data.items())
        p.write_text("---\n" + header + "\n---\n" + body)
        return p

    def record(self, path="records/sessions/claude/r.md", **overrides):
        fields = dict(source="claude", client="claude", source_ref="claude:jsonl:fixture",
                      source_location="/unread-external-source#byte:1", source_updated="2026-10-12T09:00:00+08:00",
                      evidence="primary", projects=["demo"], day="2026-10-12", day_basis="event",
                      session_refs=["claude:fixture"], coverage="complete")
        fields.update(overrides)
        return self.write(path, "record", **fields)

    def result(self):
        return report(self.root, NOW)

    def objects(self, result=None):
        return {x["path"]: x for x in (result or self.result())["objects"]}

    def codes(self):
        return {x["code"] for x in self.result()["issues"]}

    def test_unlinked_record_and_missing_outputs_are_discovered(self):
        self.record()
        self.write("projects/demo/MEMORY.md", "project-index", "2026-10-11T10:00:00+08:00")
        out = self.objects()
        self.assertEqual(out["projects/demo/MEMORY.md"]["assessment"], "stale")
        self.assertEqual(out["projects/demo/MEMORY.md"]["newer_sources"], ["records/sessions/claude/r.md"])
        self.assertEqual(out["daily/2026/2026-10-12.md"]["assessment"], "missing")

    def test_user_change_invalidates_global_summary(self):
        self.write("USER.md", "user", "2026-10-12T12:00:00+08:00")
        self.write("memory_summary.md", "summary")
        out = self.objects()["memory_summary.md"]
        self.assertEqual(out["assessment"], "stale")
        self.assertIn("USER.md", out["newer_sources"])

    def test_topic_change_is_incremental_but_old_index_is_not_a_schedule(self):
        self.write("projects/demo/MEMORY.md", "project-index", "2026-09-01T18:00:00+08:00")
        self.assertEqual(self.objects()["projects/demo/MEMORY.md"]["assessment"], "current")
        self.assertNotIn("review_due", self.objects()["projects/demo/MEMORY.md"]["reasons"])
        self.write("projects/demo/topics/build.md", "topic")
        self.assertIn("projects/demo/topics/build.md", self.objects()["projects/demo/MEMORY.md"]["newer_sources"])

    def test_multiday_record_discovers_only_evidenced_days(self):
        self.record(day="2026-10-10", event_days=["2026-10-12", "2026-10-10", "2026-10-12"])
        out = self.objects()
        days = {p for p in out if p.startswith("daily/")}
        self.assertEqual(days, {"daily/2026/2026-10-10.md", "daily/2026/2026-10-12.md"})
        self.assertTrue(all(out[p]["assessment"] == "missing" for p in days))
        for day in ("2026-10-10", "2026-10-12"):
            self.write("daily/2026/" + day + ".md", "daily", "2026-10-12T09:00:00+08:00", day=day)
        out = self.objects()
        self.assertTrue(all(out[p]["assessment"] == "stale" for p in days))
        self.assertTrue(all(out[p]["newer_sources"] == ["records/sessions/claude/r.md"] for p in days))

    def test_legacy_day_and_unknown_event_time_remain_supported(self):
        self.record(day_basis="captured")
        out = self.objects()
        self.assertEqual([p for p in out if p.startswith("daily/")], ["daily/2026/2026-10-12.md"])
        self.assertNotIn("invalid_field", self.codes())

    def test_corrected_date_or_project_still_invalidates_existing_citation(self):
        self.record(updated="2026-10-12T08:00:00+08:00", day="2026-10-10")
        citation = "[source](../../records/sessions/claude/r.md)"
        self.write("daily/2026/2026-10-10.md", "daily", day="2026-10-10", body=citation)
        self.write("projects/demo/AWARENESS.md", "awareness", body=citation)
        self.record(updated="2026-10-12T12:00:00+08:00", projects=[], day="2026-10-12")
        out = self.objects()
        self.assertEqual(out["daily/2026/2026-10-10.md"]["assessment"], "stale")
        self.assertEqual(out["projects/demo/AWARENESS.md"]["assessment"], "review")
        self.assertEqual(out["daily/2026/2026-10-10.md"]["newer_sources"], ["records/sessions/claude/r.md"])

    def test_invalid_event_days_preserve_unknown_scope(self):
        self.write("daily/2026/2026-10-11.md", "daily", "2026-10-12T17:00:00+08:00", day="2026-10-11")
        for value in ([], "2026-10-12", ["not-a-day"], ["2026-02-30"], ["2026-10-10", 12]):
            with self.subTest(value=value):
                self.record(event_days=value)
                self.assertIn("invalid_field", self.codes())
                out = self.objects()
                self.assertEqual(out["records/sessions/claude/r.md"]["assessment"], "unknown")
                self.assertEqual(out["daily/2026/2026-10-11.md"]["assessment"], "unknown")
        self.record(day_basis="captured", event_days=["2026-10-12"])
        self.assertIn("invalid_field", self.codes())
        self.assertEqual(self.objects()["daily/2026/2026-10-11.md"]["assessment"], "unknown")

    def test_partial_record_real_update_invalidates_derived_content(self):
        self.record(updated="2026-10-12T08:00:00+08:00")
        self.write("daily/2026/2026-10-12.md", "daily", day="2026-10-12")
        self.write("projects/demo/MEMORY.md", "project-index")
        self.write("projects/demo/topics/build.md", "topic", body="[source](../../../records/sessions/claude/r.md)")
        paths = ("daily/2026/2026-10-12.md", "projects/demo/MEMORY.md", "projects/demo/topics/build.md")
        self.assertTrue(all(self.objects()[p]["assessment"] == "current" for p in paths))
        self.record(updated="2026-10-12T12:00:00+08:00", coverage="partial", body="已读取的新事实；后一页暂不可读。")
        out = self.objects()
        for path in paths:
            self.assertEqual(out[path]["assessment"], "stale")
            self.assertIn("partial_source", out[path]["reasons"])
            self.assertIn("records/sessions/claude/r.md", out[path]["newer_sources"])

    def test_project_partial_topic_work_keeps_index_pending(self):
        self.write("projects/demo/MEMORY.md", "project-index", "2026-10-12T08:00:00+08:00")
        self.record("records/sessions/claude/one.md", updated="2026-10-12T09:00:00+08:00")
        self.record("records/sessions/claude/two.md", updated="2026-10-12T10:00:00+08:00")
        self.write("projects/demo/topics/one.md", "topic", "2026-10-12T11:00:00+08:00",
                   body="[source](../../../records/sessions/claude/one.md)")
        out = self.objects()["projects/demo/MEMORY.md"]
        self.assertEqual(out["assessment"], "stale")
        self.assertIn("records/sessions/claude/two.md", out["newer_sources"])
        self.assertIn("projects/demo/topics/one.md", out["newer_sources"])

    def test_native_identity_matches_imported_copy_without_cross_client_conflation(self):
        self.record()
        self.record("records/imported/codex/copy.md", source_ref="/fixture/native-summary.md", evidence="secondary")
        self.record("records/sessions/codex/other.md", source_ref="codex:jsonl:fixture", client="codex",
                    session_refs=["codex:fixture"])
        p = self.root / "config.toml"
        p.write_text(CONFIG.replace('exclude_sessions = []', 'exclude_sessions = ["claude:fixture"]'))
        result = self.result()
        excluded = {x["path"] for x in result["issues"] if x["code"] == "excluded_record"}
        self.assertEqual(excluded, {"records/sessions/claude/r.md", "records/imported/codex/copy.md"})
        self.assertNotIn("identity_review", {x["code"] for x in result["issues"]})

    def test_legacy_reader_identity_warns_and_matches_exactly_without_inference(self):
        legacy = "claude:jsonl:fixture"
        self.record(session_refs=[legacy])
        self.record("records/sessions/claude/native.md")
        p = self.root / "config.toml"
        p.write_text(CONFIG.replace('exclude_sessions = []', 'exclude_sessions = ["' + legacy + '"]'))
        result = self.result()
        excluded = {x["path"] for x in result["issues"] if x["code"] == "excluded_record"}
        self.assertEqual(excluded, {"records/sessions/claude/r.md"})
        review = {x["path"] for x in result["issues"] if x["code"] == "identity_review"}
        self.assertEqual(review, {"config.toml", "records/sessions/claude/r.md"})
        for identity in ("zcode:sqlite:fixture", "qodercn:desktop:fixture", "claude:subagent:parent:child"):
            self.record(session_refs=[identity])
            self.assertIn("identity_review", self.objects()["records/sessions/claude/r.md"]["reasons"])

    def test_invalid_and_partial_records_do_not_look_current(self):
        self.record(coverage="partial")
        self.write("projects/demo/AWARENESS.md", "awareness", "2026-10-12T17:00:00+08:00")
        self.assertEqual(self.objects()["projects/demo/AWARENESS.md"]["assessment"], "review")
        self.assertIn("partial_source", self.codes())
        self.record(updated="not-a-time", source_updated="")
        self.assertEqual(self.objects()["projects/demo/AWARENESS.md"]["assessment"], "unknown")

    def test_wrong_metadata_types_report_without_crashing(self):
        self.record(source=[], evidence=[], coverage=[], projects="demo", session_refs="bad")
        self.assertIn("invalid_field", self.codes())
        self.assertEqual(self.objects()["records/sessions/claude/r.md"]["assessment"], "unknown")
        self.record(source_ref="", source_location="")
        self.assertIn("missing_field", self.codes())

    def test_future_timestamp_and_malformed_frontmatter(self):
        p = self.record(updated="2027-01-01T00:00:00+00:00")
        self.assertIn("future_time", self.codes())
        p.write_text('---\nupdated: "unfinished\n')
        self.assertIn("invalid_field", self.codes())
        self.assertIn("missing_field", self.codes())

    def test_links_are_root_scoped_and_encoded_paths_work(self):
        self.record("records/notes/a b.md")
        self.write("USER.md", "user", body='[ok](records/notes/a%20b.md)\n[bad](records/missing.md)\n'
                   '[external](https://example.invalid/)\n[malformed-external](http://[bad)\n[outside](../not-checked.md)\n'
                   '[ref]: records/missing-two.md\n')
        broken = [x for x in self.result()["issues"] if x["code"] == "broken_link"]
        self.assertEqual(len(broken), 2)
        self.assertTrue(all(x["path"] == "USER.md" and "line" in x for x in broken))

    def test_secrets_are_located_without_echoing_values(self):
        secret = "fixture-secret-value-12345"
        self.write("USER.md", "user", updated=secret, body='api_key = "' + secret + '"\n')
        result = self.result()
        self.assertNotIn(secret, json.dumps(result))
        self.assertIn("suspected_secret", {x["code"] for x in result["issues"]})

    def test_utf8_limits_and_unconfigured_awareness_limit(self):
        self.write("memory_summary.md", "summary", body="记" * 3400)
        self.write("projects/demo/AWARENESS.md", "awareness", body="x" * 200)
        self.assertIn("oversize", self.codes())
        self.assertIn("limit_unset", self.codes())
        with (self.root / "config.toml").open("a") as stream:
            stream.write("\n[limits]\nawareness_max_bytes = 100\n")
        sizes = [x["path"] for x in self.result()["issues"] if x["code"] == "oversize"]
        self.assertIn("projects/demo/AWARENESS.md", sizes)

    def test_source_hint_is_not_an_external_scan_or_import_time(self):
        self.record(source_updated="2026-01-01T09:00:00+08:00")
        hint = self.result()["source_hints"][0]
        self.assertFalse(hint["external_checked"])
        self.assertEqual(hint["latest_source_updated"], "2026-01-01T09:00:00+08:00")
        self.assertEqual(hint["latest_record_updated"], "2026-10-12T10:00:00+08:00")

    def test_exclusions_and_backup_ignored(self):
        self.record()
        p = self.root / "config.toml"
        p.write_text(CONFIG.replace('exclude_sessions = []', 'exclude_sessions = ["claude:fixture"]'))
        self.write(".xmemory/backups/USER.md", "user", body="password = not-a-real-secret\n")
        result = self.result()
        self.assertIn("excluded_record", {x["code"] for x in result["issues"]})
        self.assertFalse(any(x["path"].startswith(".xmemory") for x in result["objects"] + result["issues"]))

    def test_symlinks_and_unreadable_format_keep_scan_gap(self):
        outside = self.base / "outside.md"
        outside.write_text("must not be read")
        (self.root / "USER.md").symlink_to(outside)
        self.write("memory_summary.md", "summary")
        self.assertIn("unsupported_format", self.codes())
        self.assertEqual(self.objects()["memory_summary.md"]["assessment"], "unknown")
        (self.root / "USER.md").unlink()
        (self.root / "USER.md").write_bytes(b"\xff\xfe")
        self.assertIn("read_error", self.codes())

    def test_missing_root_and_legacy_config_do_not_create_files(self):
        missing = self.base / "does-not-exist"
        self.assertFalse(report(missing, NOW)["ok"])
        self.assertFalse(missing.exists())
        (self.root / "config.toml").write_text(CONFIG.replace(FORMAT, "xmemory/v1.4"))
        before = snapshot(self.root)
        self.assertFalse(self.result()["ok"])
        self.assertEqual(before, snapshot(self.root))

    def test_bad_config_does_not_echo_input(self):
        (self.root / "config.toml").write_text('password = private-fixture-secret\n')
        result = self.result()
        self.assertFalse(result["ok"])
        self.assertNotIn("private-fixture-secret", json.dumps(result))

    def test_timezone_and_readonly_cli_in_standalone_package(self):
        self.record()
        scripts = self.base / "scripts"
        shutil.copytree(SCRIPTS, scripts)
        before = snapshot(self.base)
        command = [sys.executable, str(scripts / "xmemory.py"), "status", "--root", str(self.root)]
        result = subprocess.run(command, text=True, capture_output=True, cwd=self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["timezone"], "Asia/Shanghai")
        self.assertEqual(before, snapshot(self.base))
        self.assertFalse(list(self.base.rglob("__pycache__")))
        self.assertFalse((self.root / ".xmemory").exists())
        utc = datetime.fromisoformat("2026-10-12T23:00:00+00:00")
        self.assertTrue(report(self.root, utc)["now"].startswith("2026-10-13T07:00:00+08:00"))

    def test_old_write_commands_are_not_exposed(self):
        command = [sys.executable, "-B", str(SCRIPTS / "xmemory.py"), "init", "--root", str(self.root)]
        before = snapshot(self.root)
        result = subprocess.run(command, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, snapshot(self.root))

    def test_configuration_subset_and_templates(self):
        template = SCRIPTS.parent / "templates/config.toml"
        data = TomlSubset(template.read_text()).parse()
        self.assertEqual(data["format"], FORMAT)
        self.assertTrue(all(not x["enabled"] for x in data["sources"].values()))
        text = '[projects."中文项目"]\nroots = ["/fixture",\n "/alias",]\n'
        self.assertEqual(TomlSubset(text).parse()["projects"]["中文项目"]["roots"], ["/fixture", "/alias"])
        for bad in ('x = 1\nx = 2', '[[sources]]\nx = true', 'x = {a = 1}', 'x = "unterminated'):
            with self.assertRaises(ValueError):
                TomlSubset(bad).parse()
        for path in template.parent.glob("*.md"):
            if path.read_text().startswith("---\n"):
                self.assertEqual(frontmatter(path.read_text())["format"], FORMAT)


if __name__ == "__main__":
    unittest.main()
