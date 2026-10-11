from __future__ import annotations

from datetime import timedelta
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import behavior_fixtures  # noqa: E402


class BehaviorFixtureTests(unittest.TestCase):
    """The checker must reject untouched fixtures and accept a genuinely unchanged root."""

    def build(self, tmp: str, case: str) -> Path:
        base = Path(tmp) / case
        behavior_fixtures.build(case, base)
        return base

    def failed(self, case: str, base: Path) -> set[str]:
        return {item["check"] for item in behavior_fixtures.check(case, base) if not item["ok"]}

    def test_no_change_fixture_is_zero_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self.build(tmp, "curate-no-change")
            self.assertEqual(self.failed("curate-no-change", base), {"回报本次无变化"})
            (base / "step1.last.md").write_text("本次无变化，零写入。", encoding="utf-8")
            self.assertEqual(self.failed("curate-no-change", base), set())
            (base / "memroot/state/curation/extra.md").write_text("x", encoding="utf-8")
            self.assertIn("零写入", self.failed("curate-no-change", base))

    def test_untouched_fixtures_fail_their_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            for case in ("collect-gap", "curate-second-pass", "curate-pending-resume", "curate-legacy-1.2"):
                base = self.build(tmp, case)
                failed = self.failed(case, base)
                self.assertTrue(failed, case)
                self.assertNotIn("撤回来源零足迹", failed)
                self.assertNotIn("足迹未被修改", failed)
            base = self.build(tmp, "collect-sessions")
            failed = self.failed("collect-sessions", base)
            self.assertIn("长会话按事件日拆成三份", failed)
            self.assertIn("活跃会话跳过并需回补", failed)
            self.assertNotIn("撤回会话零足迹", failed)
            base = self.build(tmp, "record-handoff")
            self.assertIn("只新增一份足迹和一份主题草稿", self.failed("record-handoff", base))

    def test_zero_write_record_and_owner_cases_need_the_right_report(self):
        reports = {"record-nothing": "无需记录。", "record-duplicate": "已有足迹 0930-retry-policy-handoff-x7k2.md，零写入。",
                   "record-withdrawn": "该会话已撤回，不重新收录。", "curate-active-owner": "另一个 Agent 正在整理 personal，本次停止。"}
        with tempfile.TemporaryDirectory() as tmp:
            for case, report in reports.items():
                base = self.build(tmp, case)
                self.assertTrue(self.failed(case, base), case)
                (base / "step1.last.md").write_text(report, encoding="utf-8")
                self.assertEqual(self.failed(case, base), set(), case)

    def test_legacy_fixture_uses_the_1_2_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self.build(tmp, "curate-legacy-1.2")
            project = base / "memroot/projects/demo-api"
            deploy = (project / "daily/2026-10-09/1500-staging-deploy-c3d4.md").read_text(encoding="utf-8")
            self.assertNotIn("time_basis:", deploy)
            self.assertNotIn("origin:", deploy)
            self.assertNotIn("批次：", (project / "daily/2026-10-08.md").read_text(encoding="utf-8"))
            names = sorted(p.name for p in (base / "memroot/state/curation").glob("*.md"))
            self.assertEqual(names, ["2026-10.md"])

    def test_session_restore_waits_for_quiet_period(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self.build(tmp, "collect-sessions")
            built = behavior_fixtures.datetime.fromisoformat(
                json.loads((base / "fixture.json").read_text(encoding="utf-8"))["built_at"])
            active = next((base / behavior_fixtures.SESSIONS).rglob(f"*{behavior_fixtures.ACTIVE_ID}.jsonl"))
            lines = len(active.read_text(encoding="utf-8").splitlines())
            with self.assertRaises(SystemExit):
                behavior_fixtures.restore(base, now=built + timedelta(minutes=30))
            behavior_fixtures.restore(base, now=built + timedelta(minutes=61))
            self.assertEqual(len(active.read_text(encoding="utf-8").splitlines()), lines + 2)

    @unittest.skipUnless(hasattr(os, "chflags"), "needs os.chflags")
    def test_write_failure_fixture_locks_awareness(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self.build(tmp, "curate-write-failure")
            try:
                awareness = base / "memroot/projects/demo-api/AWARENESS.md"
                with self.assertRaises(PermissionError):
                    awareness.write_text("x", encoding="utf-8")
                failed = self.failed("curate-write-failure", base)
                self.assertNotIn("AWARENESS.md 未被改写", failed)
                self.assertNotIn("写保护未被解除", failed)
                self.assertIn("新建批次停在 pending", failed)
            finally:
                behavior_fixtures.release(base)

    def test_restore_replaces_unavailable_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self.build(tmp, "collect-gap")
            link = base / "fixtures/codex-memories/rollout_summaries" / behavior_fixtures.RETRY
            self.assertTrue(link.is_symlink())
            self.assertFalse(link.exists())
            behavior_fixtures.restore(base)
            self.assertFalse(link.is_symlink())
            self.assertIn("thread_id:", link.read_text(encoding="utf-8"))

    def test_home_access_in_logs_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self.build(tmp, "curate-no-change")
            (base / "step1.last.md").write_text("本次无变化", encoding="utf-8")
            (base / "step1.log").write_text("exec\n/bin/zsh -lc 'cat ~/.agents/memory/MEMORY.md' in /tmp\n",
                                            encoding="utf-8")
            self.assertIn("命令未触及用户主目录", self.failed("curate-no-change", base))


if __name__ == "__main__":
    unittest.main()
