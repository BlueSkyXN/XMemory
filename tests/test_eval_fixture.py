from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fixture_v17", ROOT / "evals/v1.7.0/make_fixture.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class EvalFixtureTests(unittest.TestCase):
    def test_cold_copy_keeps_document_targets_without_prior_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "source"
            for relative in ("plugins/client-readers", ".agents/plugins", "docs", "local", "evals", "tests"):
                (repo / relative).mkdir(parents=True)
            (repo / "README.md").write_text("# Source\n[validation](docs/validation.md)\n", encoding="utf-8")
            (repo / "AGENTS.md").write_text("# Repository instructions\n", encoding="utf-8")
            (repo / "tests/test_eval_fixture.py").write_text("private-fixture-criteria\n", encoding="utf-8")
            for relative in ("docs/validation.md", "plugins/client-readers/docs/validation.md"):
                path = repo / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# Prior evaluation results\nprivate-verdict\n", encoding="utf-8")
            root = base / "fixture"
            fixture.make_fixture(root, repo)
            cold = root / "e1_cold/repo"
            for relative in ("docs/validation.md", "plugins/client-readers/docs/validation.md"):
                self.assertTrue((cold / relative).is_file())
                self.assertNotIn("private-verdict", (cold / relative).read_text(encoding="utf-8"))
            self.assertEqual((cold / "AGENTS.md").read_bytes(), (repo / "AGENTS.md").read_bytes())
            self.assertFalse((cold / "evals").exists())
            self.assertFalse((cold / "tests/test_eval_fixture.py").exists())
            self.assertFalse((cold / "local").exists())
            self.assertTrue((root / "e1_cold/home/.agents/memory/config.toml").is_file())
            self.assertFalse((root / "e1_cold/memory").exists())


if __name__ == "__main__":
    unittest.main()
