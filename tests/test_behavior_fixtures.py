from __future__ import annotations

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
            for case in ("collect-gap", "curate-second-pass", "curate-pending-resume"):
                base = self.build(tmp, case)
                failed = self.failed(case, base)
                self.assertTrue(failed, case)
                self.assertNotIn("撤回来源零足迹", failed)
                self.assertNotIn("足迹未被修改", failed)

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
