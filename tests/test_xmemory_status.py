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
from status import FORMAT, format_summary, frontmatter, report, summarize  # noqa: E402
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
        (self.root / "config.toml").write_text(CONFIG, encoding='utf-8')

    def write(self, path, kind, updated="2026-10-12T10:00:00+08:00", body="", **fields):
        data = dict(format=FORMAT, kind=kind, updated=updated, **fields)
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        header = "\n".join(k + ": " + json.dumps(v, ensure_ascii=False) for k, v in data.items())
        p.write_text("---\n" + header + "\n---\n" + body, encoding='utf-8')
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

    def test_unresolved_project_is_not_a_personal_candidate(self):
        path = "records/imported/claude/unresolved.md"
        self.record(path, projects=[], project_status="unresolved")
        before = snapshot(self.root)
        result = self.result()
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual([x for x in result["issues"] if x["code"] == "unresolved_project"],
                         [{"code": "unresolved_project", "path": path}])
        self.assertNotIn("personal/AWARENESS.md", self.objects(result))
        self.assertIn("daily/2026/2026-10-12.md", self.objects(result))
        self.assertIn(path, self.objects(result)["USER.md"]["newer_sources"])
        self.write("personal/AWARENESS.md", "awareness", "2026-10-11T10:00:00+08:00")
        self.write("personal/MEMORY.md", "project-index", "2026-10-11T10:00:00+08:00")
        for kind in ("AWARENESS", "MEMORY"):
            self.assertEqual(self.objects()[f"personal/{kind}.md"]["newer_sources"], [])
        self.record("records/imported/claude/personal.md", projects=[])
        self.assertEqual(self.objects()["personal/AWARENESS.md"]["newer_sources"],
                         ["records/imported/claude/personal.md"])

    def test_project_status_only_accepts_unresolved_with_empty_projects(self):
        for value, projects in (("resolved", []), ("", []), ([], []), ("unresolved", ["demo"])):
            with self.subTest(value=value, projects=projects):
                self.record("records/imported/claude/test.md", projects=projects, project_status=value)
                self.assertTrue(any(x["code"] == "invalid_field" and x.get("field") == "project_status"
                                    for x in self.result()["issues"]))

    def test_session_filename_matches_full_identity_suffix(self):
        cases = [
            ("records/sessions/claude/20261012-good-12345678.md", ["claude:session-12345678"], False),
            ("records/sessions/claude/20261012-good-12345678.md", ["claude:other-87654321", "claude:session-12345678"], False),
            ("records/sessions/claude/20261012-bad-87654321.md", ["claude:session-12345678"], True),
            ("records/sessions/claude/20261012-short-1234.md", ["claude:session-1234"], True),
            ("records/sessions/claude/unknown.md", [], False),
            ("records/imported/claude/summary.md", ["claude:session-12345678"], False),
        ]
        for path, refs, expected in cases:
            with self.subTest(path=path, refs=refs):
                self.record(path, session_refs=refs)
                found = [x for x in self.result()["issues"] if x["path"] == path and
                         x["code"] == "identity_review" and x.get("field") == "filename"]
                self.assertEqual(bool(found), expected)

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

    def test_summary_reports_pending_updates_older_than_itself(self):
        self.record(updated="2026-10-12T09:30:00+08:00")
        upstream = {"USER.md": "user", "projects/demo/AWARENESS.md": "awareness",
                    "projects/demo/MEMORY.md": "project-index"}
        for path, kind in upstream.items():
            self.write(path, kind, "2026-10-12T09:00:00+08:00")
        self.write("memory_summary.md", "summary", "2026-10-12T10:00:00+08:00")
        before = snapshot(self.root)
        out = self.objects()["memory_summary.md"]
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual(out["assessment"], "review")
        self.assertIn("upstream_newer_sources", out["reasons"])
        self.assertEqual(out["newer_sources"], [])
        self.assertEqual(out["upstream_updates"], [
            {"path": path, "newer_sources": ["records/sessions/claude/r.md"]}
            for path in sorted(upstream)])
        # 上游处理完成后，摘要仍须按真实文件更新时间更新；处理完可恢复 current。
        for path, kind in upstream.items():
            self.write(path, kind, "2026-10-12T11:00:00+08:00")
        out = self.objects()["memory_summary.md"]
        self.assertEqual(out["assessment"], "stale")
        self.assertEqual(out["upstream_updates"], [])
        self.write("memory_summary.md", "summary", "2026-10-12T12:00:00+08:00")
        self.assertEqual(self.objects()["memory_summary.md"]["assessment"], "current")

    def test_summary_does_not_inherit_unchecked_external_source_review(self):
        self.record(updated="2026-10-12T08:00:00+08:00")
        self.write("projects/demo/MEMORY.md", "project-index", "2026-10-12T09:00:00+08:00",
                   body="[source](../../records/sessions/claude/r.md)")
        self.write("memory_summary.md", "summary", body="[project](projects/demo/MEMORY.md)")
        out = self.objects()
        self.assertEqual(out["records/sessions/claude/r.md"]["assessment"], "review")
        self.assertEqual(out["memory_summary.md"]["assessment"], "current")
        self.assertEqual(out["memory_summary.md"]["upstream_updates"], [])
        # 没有画像依据时可以不建 USER.md，缺少候选对象不强制变成上游待办。
        self.assertEqual(out["USER.md"]["assessment"], "missing")

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
        self.write("daily/2026/2026-10-12.md", "daily", day="2026-10-12",
                   body="[source](../../records/sessions/claude/r.md)")
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
        p.write_text(CONFIG.replace('exclude_sessions = []', 'exclude_sessions = ["claude:fixture"]'), encoding='utf-8')
        result = self.result()
        excluded = {x["path"] for x in result["issues"] if x["code"] == "excluded_record"}
        self.assertEqual(excluded, {"records/sessions/claude/r.md", "records/imported/codex/copy.md"})
        # 本例核对完整身份与跨客户端排除；旧夹具文件名另由 filename 提示覆盖。
        self.assertNotIn("identity_review", {x["code"] for x in result["issues"] if x.get("field") != "filename"})

    def test_legacy_reader_identity_warns_and_matches_exactly_without_inference(self):
        legacy = "claude:jsonl:fixture"
        self.record(session_refs=[legacy])
        self.record("records/sessions/claude/native.md")
        p = self.root / "config.toml"
        p.write_text(CONFIG.replace('exclude_sessions = []', 'exclude_sessions = ["' + legacy + '"]'), encoding='utf-8')
        result = self.result()
        excluded = {x["path"] for x in result["issues"] if x["code"] == "excluded_record"}
        self.assertEqual(excluded, {"records/sessions/claude/r.md"})
        review = {x["path"] for x in result["issues"] if x["code"] == "identity_review" and x.get("field") != "filename"}
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

    def test_inventory_separates_files_candidates_and_configuration(self):
        config = self.root / "config.toml"
        config.write_text(CONFIG + '\n[sources.disabled]\nenabled = false\nkind = "files"\n'
                          'client = "filesystem"\npaths = []\n[projects.empty]\nroots = []\n')
        self.record("records/imported/claude/one.md", coverage="partial")
        self.record("records/notes/two.md", source="note", projects=[], project_status="unresolved")
        self.write("projects/demo/MEMORY.md", "project-index")
        before = snapshot(self.root)
        result = self.result()
        inventory = result["inventory"]
        self.assertEqual(inventory["configuration"], {"sources": 2, "enabled_sources": 1,
                                                       "projects": 2, "projects_with_records": 1})
        self.assertEqual(inventory["existing_objects"], 3)
        self.assertEqual(inventory["records"]["total"], 2)
        self.assertEqual(inventory["records"]["partial"], 1)
        self.assertEqual(inventory["records"]["unresolved_project"], 1)
        self.assertEqual(inventory["records"]["by_source"]["note"], 1)
        self.assertEqual(inventory["records"]["by_directory"]["imported"], 1)
        self.assertEqual(inventory["derived"]["by_kind"]["project-index"], 1)
        self.assertEqual(inventory["candidates"]["total"], result["counts"]["objects"]["missing"])
        self.assertEqual(sum(result["counts"]["objects"].values()),
                         inventory["existing_objects"] + inventory["candidates"]["total"])
        self.assertEqual(snapshot(self.root), before)

    def test_inventory_does_not_echo_invalid_source_values(self):
        value = "sk-" + "a" * 24
        self.record(source=value)
        result = self.result()
        self.assertNotIn(value, json.dumps(result))
        self.assertEqual(result["inventory"]["records"]["unconfigured_source"], 1)
        self.assertEqual(result["inventory"]["records"]["by_source"], {"claude": 0})

    def test_candidates_require_direct_inputs_and_existing_objects_remain(self):
        self.assertEqual(self.result()["objects"], [])
        self.record()
        self.assertNotIn("memory_summary.md", self.objects())
        self.write("projects/demo/topics/build.md", "topic")
        self.write("projects/empty/MEMORY.md", "project-index")
        self.assertIn("projects/empty/MEMORY.md", self.objects())
        self.assertIn("memory_summary.md", self.objects())
        self.assertNotIn("projects/empty/AWARENESS.md", self.objects())

    def test_unlinked_older_daily_record_stays_pending_until_linked(self):
        path = "records/imported/claude/old note.md"
        self.record(path, updated="2026-10-12T08:00:00+08:00")
        daily = "daily/2026/2026-10-12.md"
        self.write(daily, "daily", day="2026-10-12")
        item = self.objects()[daily]
        self.assertEqual(item["newer_sources"], [])
        self.assertEqual(item["unlinked_sources"], [path])
        self.assertEqual(item["assessment"], "stale")
        self.write(daily, "daily", day="2026-10-12",
                   body="[source][ref]\n[ref]: ../../records/imported/claude/old%20note.md#detail")
        self.assertEqual(self.objects()[daily]["unlinked_sources"], [])
        self.assertEqual(self.objects()[daily]["assessment"], "current")

    def test_links_in_examples_or_other_scopes_do_not_cover_records(self):
        path = "records/imported/claude/old.md"
        self.record(path, updated="2026-10-12T08:00:00+08:00")
        daily = "daily/2026/2026-10-12.md"
        self.write(daily, "daily", day="2026-10-12", body="```md\n[source](../../" + path + ")\n```")
        self.write("personal/topics/ref.md", "topic", body="[source](../../" + path + ")")
        self.write("projects/demo/MEMORY.md", "project-index")
        objects = self.objects()
        self.assertEqual(objects[daily]["unlinked_sources"], [path])
        self.assertEqual(objects["projects/demo/MEMORY.md"]["unlinked_sources"], [path])
        self.assertEqual(objects["projects/demo/MEMORY.md"]["assessment"], "current")

    def test_project_links_cover_older_records_without_changing_index_assessment(self):
        paths = ["records/imported/claude/" + name + ".md" for name in ("a", "b")]
        for path in paths:
            self.record(path, updated="2026-10-12T08:00:00+08:00")
        index = "projects/demo/MEMORY.md"
        self.write(index, "project-index", "2026-10-12T14:00:00+08:00")
        self.write("projects/demo/topics/a.md", "topic", body="[source](../../../" + paths[0] + ")")
        item = self.objects()[index]
        self.assertEqual(item["assessment"], "current")
        self.assertEqual(item["unlinked_sources"], [paths[1]])
        self.assertIn(index, {x["path"] for x in summarize(self.result())["objects"]})

    def test_multiday_unlinked_signals_are_independent_and_unresolved_stays_out_of_personal(self):
        path = "records/imported/claude/multiday.md"
        self.record(path, updated="2026-10-12T08:00:00+08:00", projects=[], project_status="unresolved",
                    event_days=["2026-10-11", "2026-10-12"])
        for day in ("2026-10-11", "2026-10-12"):
            self.write("daily/2026/" + day + ".md", "daily", day=day,
                       body="[source](../../" + path + ")" if day.endswith("11") else "")
        objects = self.objects()
        self.assertEqual(objects["daily/2026/2026-10-11.md"]["assessment"], "current")
        self.assertEqual(objects["daily/2026/2026-10-12.md"]["unlinked_sources"], [path])
        self.assertNotIn("personal/MEMORY.md", objects)

    def test_empty_source_time_is_record_warning_without_poisoning_derived_objects(self):
        path = "records/imported/claude/unknown.md"
        self.record(path, updated="2026-10-12T08:00:00+08:00", source_updated="")
        self.write("USER.md", "user")
        self.write("projects/demo/topics/build.md", "topic", body="[source](../../../" + path + ")")
        result = self.result()
        objects = self.objects(result)
        self.assertEqual(objects[path]["assessment"], "review")
        self.assertIn("unknown_source_time", objects[path]["reasons"])
        self.assertEqual(objects["USER.md"]["assessment"], "current")
        self.assertEqual(objects["projects/demo/topics/build.md"]["assessment"], "current")
        self.assertNotIn("invalid_time", self.codes())
        self.assertEqual(result["inventory"]["records"]["unknown_source_time"], 1)
        self.assertIn(path, {x["path"] for x in summarize(result)["objects"]})

    def test_invalid_source_times_and_missing_location_still_propagate_unknown(self):
        self.write("USER.md", "user", "2026-10-12T17:00:00+08:00")
        for value in ("bad", " ", "2026-10-12T10:00:00", "2027-01-01T00:00:00Z"):
            with self.subTest(source_updated=value):
                self.record(source_updated=value)
                self.assertEqual(self.objects()["USER.md"]["assessment"], "unknown")
        self.record(source_updated="", source_location="")
        self.assertEqual(self.objects()["USER.md"]["assessment"], "unknown")

    def test_summary_keeps_stale_topic_even_after_index_has_been_updated(self):
        path = "records/imported/claude/b.md"
        self.record(path, updated="2026-10-12T11:00:00+08:00")
        topic = "projects/demo/topics/b.md"
        self.write(topic, "topic", body="[source](../../../" + path + ")")
        self.write("projects/demo/MEMORY.md", "project-index", "2026-10-12T12:00:00+08:00",
                   body="[b](topics/b.md)")
        result = self.result()
        brief = summarize(result)
        self.assertEqual(self.objects(result)["projects/demo/MEMORY.md"]["assessment"], "current")
        self.assertEqual(self.objects(brief)[topic]["assessment"], "stale")
        self.assertNotIn(path, self.objects(brief))
        for key in ("inventory", "counts", "issues", "source_hints"):
            self.assertEqual(brief[key], result[key])

    def test_summary_cli_and_invalid_root_preserve_readonly_contract(self):
        self.record("records/imported/claude/normal.md")
        before = snapshot(self.root)
        result = subprocess.run([sys.executable, "-B", str(SCRIPTS / "xmemory.py"),
                                 "status", "--summary", "--root", str(self.root)],
                                capture_output=True, text=True, check=True)
        output = json.loads(result.stdout)
        lines = [line for line in result.stdout.splitlines() if line.startswith('    {"path"')]
        self.assertTrue(output["objects"])
        self.assertEqual([json.loads(line.rstrip(",")) for line in lines], output["objects"])
        self.assertLess(list(output).index("inventory"), list(output).index("objects"))
        self.assertLess(list(output).index("counts"), list(output).index("objects"))
        self.assertEqual(output["inventory"]["records"]["total"], 1)
        self.assertFalse(any(x["kind"] == "record" for x in output["objects"]))
        self.assertEqual(snapshot(self.root), before)
        invalid = summarize(report(self.base / "absent", NOW))
        self.assertEqual(json.loads(format_summary(invalid)), invalid)
        self.assertIsNone(invalid["inventory"])
        self.assertFalse(invalid["ok"])
        self.assertFalse((self.base / "absent").exists())

    def test_inventory_counts_existing_items_that_need_attention(self):
        self.record("records/imported/claude/a.md", updated="2026-10-12T08:00:00+08:00")
        self.record("records/imported/claude/bad.md", projects=[], day="2026-10-11", source_location="")
        self.write("projects/demo/MEMORY.md", "project-index", "2026-10-12T14:00:00+08:00")
        self.write("daily/2026/2026-10-12.md", "daily", "2026-10-12T14:00:00+08:00", day="2026-10-12")
        self.write("USER.md", "user", "2026-10-12T14:00:00+08:00")
        inventory = self.result()["inventory"]
        self.assertEqual(inventory["records"]["unknown"], 1)
        self.assertEqual(inventory["records"]["unlinked"], {"daily": 1, "projects": 1})
        self.assertEqual(inventory["derived"]["by_assessment"], {"current": 1, "stale": 1, "review": 0, "unknown": 1})

    def test_unlinked_hints_stay_on_existing_daily_and_index(self):
        path = "records/imported/claude/old.md"
        self.record(path, updated="2026-10-12T08:00:00+08:00")
        objects = self.objects()
        for missing in ("daily/2026/2026-10-12.md", "projects/demo/MEMORY.md", "projects/demo/AWARENESS.md"):
            self.assertEqual(objects[missing]["assessment"], "missing")
            self.assertEqual(objects[missing]["unlinked_sources"], [])
            self.assertIn(path, objects[missing]["newer_sources"])
        self.write("projects/demo/MEMORY.md", "project-index", "2026-10-12T14:00:00+08:00")
        self.write("projects/demo/AWARENESS.md", "awareness", "2026-10-12T14:00:00+08:00")
        objects = self.objects()
        self.assertEqual(objects["projects/demo/MEMORY.md"]["unlinked_sources"], [path])
        self.assertEqual(objects["projects/demo/AWARENESS.md"]["unlinked_sources"], [])
        self.assertEqual(objects["projects/demo/AWARENESS.md"]["assessment"], "current")
        self.assertNotIn("projects/demo/AWARENESS.md", {x["path"] for x in summarize(self.result())["objects"]})

    def test_time_values_parse_the_same_on_supported_python_versions(self):
        self.write("USER.md", "user", "2026-10-12T17:00:00+08:00")
        for value in ("2026-10-12T01:00:00Z", "2026-10-12T09:00:00+0800", "2026-10-12T09:00:00+08",
                      "2026-10-12T01:00:00.1234567z", "2026-10-12 09:00:00,5+08:00", "2026-10-12T09:00+08:00"):
            with self.subTest(source_updated=value):
                self.record(source_updated=value)
                self.assertNotIn("invalid_time", self.codes())
                self.assertEqual(self.objects()["USER.md"]["assessment"], "current")
        for value in ("20261012T090000+0800", "2026-10-12T09+08:00", "2026-10-12T09:00:00+08:00:00"):
            with self.subTest(source_updated=value):
                self.record(source_updated=value)
                self.assertIn("invalid_time", self.codes())
                self.assertEqual(self.objects()["USER.md"]["assessment"], "unknown")

    def test_wrong_metadata_types_report_without_crashing(self):
        self.record(source=[], evidence=[], coverage=[], projects="demo", session_refs="bad")
        self.assertIn("invalid_field", self.codes())
        self.assertEqual(self.objects()["records/sessions/claude/r.md"]["assessment"], "unknown")
        self.record(source_ref="", source_location="")
        self.assertIn("missing_field", self.codes())

    def test_future_timestamp_and_malformed_frontmatter(self):
        p = self.record(updated="2027-01-01T00:00:00+00:00")
        self.assertIn("future_time", self.codes())
        p.write_text('---\nupdated: "unfinished\n', encoding='utf-8')
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
        with (self.root / "config.toml").open("a", encoding='utf-8') as stream:
            stream.write("\n[limits]\nawareness_max_bytes = 100\n")
        sizes = [x["path"] for x in self.result()["issues"] if x["code"] == "oversize"]
        self.assertIn("projects/demo/AWARENESS.md", sizes)

    def test_source_hint_is_not_an_external_scan_or_import_time(self):
        self.record(source_updated="2026-01-01T09:00:00+08:00")
        hint = self.result()["source_hints"][0]
        self.assertFalse(hint["external_checked"])
        self.assertEqual(hint["latest_source_updated"], "2026-01-01T09:00:00+08:00")
        self.assertEqual(hint["latest_record_updated"], "2026-10-12T10:00:00+08:00")

    def test_user_links_do_not_duplicate_records_or_become_daily_inputs(self):
        self.record(coverage="partial")
        self.write("projects/demo/topics/preferences.md", "topic", "2026-10-12T13:00:00+08:00")
        self.write("USER.md", "user", "2026-10-12T12:00:00+08:00",
                   body="[record](records/sessions/claude/r.md)\n"
                        "[topic](projects/demo/topics/preferences.md)\n")
        self.write("daily/2026/2026-10-12.md", "daily", "2026-10-12T11:00:00+08:00",
                   day="2026-10-12")
        before = snapshot(self.root)
        result = self.result()
        hint = result["source_hints"][0]
        self.assertEqual(hint["records"], 1)
        self.assertEqual(hint["partial_records"], 1)
        objects = self.objects(result)
        self.assertIn("projects/demo/topics/preferences.md", objects["USER.md"]["newer_sources"])
        self.assertEqual(objects["daily/2026/2026-10-12.md"]["newer_sources"], [])
        self.assertEqual(snapshot(self.root), before)

    def test_exclusions_and_backup_ignored(self):
        self.record()
        p = self.root / "config.toml"
        p.write_text(CONFIG.replace('exclude_sessions = []', 'exclude_sessions = ["claude:fixture"]'), encoding='utf-8')
        self.write(".xmemory/backups/USER.md", "user", body="password = not-a-real-secret\n")
        result = self.result()
        self.assertIn("excluded_record", {x["code"] for x in result["issues"]})
        self.assertFalse(any(x["path"].startswith(".xmemory") for x in result["objects"] + result["issues"]))

    def test_symlinks_and_unreadable_format_keep_scan_gap(self):
        outside = self.base / "outside.md"
        outside.write_text("must not be read", encoding='utf-8')
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
        (self.root / "config.toml").write_text(CONFIG.replace(FORMAT, "xmemory/v1.4"), encoding='utf-8')
        before = snapshot(self.root)
        self.assertFalse(self.result()["ok"])
        self.assertEqual(before, snapshot(self.root))

    def test_bad_config_does_not_echo_input(self):
        (self.root / "config.toml").write_text('password = private-fixture-secret\n', encoding='utf-8')
        result = self.result()
        self.assertFalse(result["ok"])
        self.assertNotIn("private-fixture-secret", json.dumps(result))

    def test_timezone_and_readonly_cli_in_standalone_package(self):
        self.record()
        scripts = self.base / "scripts"
        shutil.copytree(SCRIPTS, scripts)
        before = snapshot(self.base)
        command = [sys.executable, str(scripts / "xmemory.py"), "status", "--root", str(self.root)]
        result = subprocess.run(command, text=True, capture_output=True, cwd=self.base, encoding='utf-8')
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
        result = subprocess.run(command, text=True, capture_output=True, encoding='utf-8')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, snapshot(self.root))

    def test_configuration_subset_and_templates(self):
        template = SCRIPTS.parent / "templates/config.toml"
        data = TomlSubset(template.read_text(encoding='utf-8')).parse()
        self.assertEqual(data["format"], FORMAT)
        self.assertTrue(all(not x["enabled"] for x in data["sources"].values()))
        text = '[projects."中文项目"]\nroots = ["/fixture",\n "/alias",]\n'
        self.assertEqual(TomlSubset(text).parse()["projects"]["中文项目"]["roots"], ["/fixture", "/alias"])
        for bad in ('x = 1\nx = 2', '[[sources]]\nx = true', 'x = {a = 1}', 'x = "unterminated'):
            with self.assertRaises(ValueError):
                TomlSubset(bad).parse()
        for path in template.parent.glob("*.md"):
            if path.read_text(encoding='utf-8').startswith("---\n"):
                self.assertEqual(frontmatter(path.read_text(encoding='utf-8'))["format"], FORMAT)


if __name__ == "__main__":
    unittest.main()
