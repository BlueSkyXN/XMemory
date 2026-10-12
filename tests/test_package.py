from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote
import shutil
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from check_package import SKILLS, check  # noqa: E402
from build_release import build  # noqa: E402

PLUGIN = ROOT / "plugins" / "xmemory"
SKILL = PLUGIN / "skills" / "xmemory"


def copy_repo(root: Path):
    for directory in ("plugins", ".claude-plugin", ".agents"):
        shutil.copytree(ROOT / directory, root / directory)


class PackageTests(unittest.TestCase):
    def test_package_contract(self):
        self.assertEqual(check(), [])

    def test_runtime_code_only_in_skill_scripts(self):
        code = {p.relative_to(PLUGIN).as_posix() for p in PLUGIN.rglob("*") if p.suffix in {".py", ".js", ".sh"}}
        self.assertEqual(code, {"skills/xmemory/scripts/xmemory.py", "skills/xmemory/scripts/xmemory_runtime.py",
                                "skills/xmemory/scripts/reader_runtime.py"})
        for name in ("hooks", "commands", "node_modules"):
            self.assertFalse((PLUGIN / name).exists())

    def test_single_skill_links_its_methods(self):
        self.assertEqual({p.name for p in (PLUGIN / "skills").iterdir()}, SKILLS)
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for ref in ("references/recall.md", "references/extract.md", "references/consolidate.md",
                    "references/layout.md"):
            self.assertIn(ref, text)
        for command in ("next --client", "submit", "consolidate begin", "consolidate finish", "note", "notice"):
            self.assertIn(command, text)

    def test_unexpected_script_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_repo(root)
            (root / "plugins/xmemory/run.py").write_text("print('unexpected')\n")
            self.assertTrue(any("Non-document payload" in error for error in check(root)))
            (root / "plugins/xmemory/run.py").unlink()
            (root / "plugins/xmemory/skills/xmemory/scripts/extra.py").write_text("x = 1\n")
            self.assertTrue(any("Unexpected script set" in error for error in check(root)))

    def test_reader_runtime_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_repo(root)
            path = root / "plugins/xmemory/skills/xmemory/scripts/reader_runtime.py"
            path.write_text(path.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
            self.assertTrue(any("Reader runtime drift" in error for error in check(root)))

    def test_broken_link_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_repo(root)
            with (root / "plugins/xmemory/skills/xmemory/SKILL.md").open("a") as stream:
                stream.write("\n[missing](missing.md)\n")
            self.assertTrue(any("Broken or escaping link" in error for error in check(root)))

    def test_private_absolute_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_repo(root)
            path = root / "plugins/xmemory/README.md"
            original = path.read_text()
            self.assertEqual(check(root), [])
            windows = "\\".join(("C:", "Users", "fixture-user", "notes.md"))
            paths = ["/".join(("", base, "fixture-user", "notes.md")) for base in ("Users", "Volumes", "home")]
            paths += [windows, json.dumps(windows), windows.replace("\\", "/")]
            for private_path in paths:
                with self.subTest(path=private_path):
                    path.write_text(original + "\n" + private_path + "\n")
                    self.assertIn("Private absolute path in payload: README.md", check(root))
            path.write_text(original)
            script = root / "plugins/xmemory/skills/xmemory/scripts/xmemory_runtime.py"
            script.write_text(script.read_text() + "\n# " + paths[0] + "\n")
            self.assertTrue(any("Private absolute path" in e for e in check(root)))

    def test_archive_is_reproducible_and_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            first, one = build(ROOT, base / "one")
            second, two = build(ROOT, base / "two")
            self.assertEqual(one, two)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertIsNone(archive.testzip())
                label = first.stem
                for line in archive.read(f"{label}/SHA256SUMS").decode().splitlines():
                    digest, name = line.split("  ", 1)
                    self.assertEqual(hashlib.sha256(archive.read(f"{label}/{name}")).hexdigest(), digest)
                for plugin in ("xmemory", "conversation-readers"):
                    payload = {name.removeprefix(f"{label}/plugins/{plugin}/") for name in archive.namelist()
                               if name.startswith(f"{label}/plugins/{plugin}/")}
                    actual = {p.relative_to(ROOT / "plugins" / plugin).as_posix()
                              for p in (ROOT / "plugins" / plugin).rglob("*") if p.is_file()}
                    self.assertEqual(payload, actual, plugin)
                self.assertFalse(any("local/" in name or "tools/" in name or "__pycache__" in name
                                     for name in archive.namelist()))

    def test_portable_skill_is_self_contained(self):
        from check_package import LINK
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            archive_path, first_hash = build(ROOT, base / "one", portable=True)
            _, second_hash = build(ROOT, base / "two", portable=True)
            self.assertEqual(first_hash, second_hash)
            with zipfile.ZipFile(archive_path) as archive:
                self.assertIsNone(archive.testzip())
                archive.extractall(base / "extracted")
            skills = base / "extracted" / archive_path.stem / "skills"
            self.assertEqual({p.name for p in skills.iterdir()}, SKILLS)
            skill = skills / "xmemory"
            for name in ("xmemory.py", "xmemory_runtime.py", "reader_runtime.py"):
                self.assertTrue((skill / "scripts" / name).is_file(), name)
            for path in skill.rglob("*.md"):
                for raw in LINK.findall(path.read_text()):
                    if re.match(r"(?:[a-z][a-z0-9+.-]*:|#)", raw, re.I) or "{{" in raw or "<" in raw:
                        continue
                    target = (path.parent / unquote(raw.split("#", 1)[0])).resolve()
                    self.assertTrue(target.is_relative_to(skill.resolve()), (path, raw))
                    self.assertTrue(target.is_file(), (path, raw))

    def test_all_host_catalogs_are_in_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive_path, _ = build(ROOT, Path(tmp))
            with zipfile.ZipFile(archive_path) as archive:
                manifests = [f"plugins/{plugin}/{name}" for plugin in ("xmemory", "conversation-readers")
                             for name in ("plugin.json", ".zcode-plugin/plugin.json", ".claude-plugin/plugin.json",
                                          ".codex-plugin/plugin.json")]
                for relative in ("plugins/marketplace.json", ".claude-plugin/marketplace.json",
                                 ".agents/plugins/marketplace.json", *manifests):
                    self.assertIn(f"{archive_path.stem}/{relative}", archive.namelist())

    def test_every_marketplace_lists_both_plugins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_repo(root)
            self.assertEqual(check(root), [])
            for relative in ("plugins/marketplace.json", ".claude-plugin/marketplace.json",
                             ".agents/plugins/marketplace.json"):
                with self.subTest(market=relative):
                    path = root / relative
                    original = path.read_text(encoding="utf-8")
                    data = json.loads(original)
                    data["plugins"] = [e for e in data["plugins"] if e["name"] != "conversation-readers"]
                    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                    self.assertTrue(any("must list" in error for error in check(root)))
                    path.write_text(original, encoding="utf-8")
            path = root / ".claude-plugin/marketplace.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            next(e for e in data["plugins"] if e["name"] == "xmemory")["version"] = "9.9.9"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            self.assertIn("claude marketplace mismatch: xmemory.version", check(root))

    def test_format_and_default_root_are_documented(self):
        runtime = (SKILL / "scripts" / "xmemory_runtime.py").read_text(encoding="utf-8")
        self.assertIn('FORMAT = "xmemory/v1.4"', runtime)
        for name in ("SKILL.md", "references/layout.md", "templates/agents-notice.md"):
            text = (SKILL / name).read_text(encoding="utf-8")
            self.assertTrue("~/.agents/memory" in text or "{{root}}" in text, name)
        manifest = json.loads((PLUGIN / ".zcode-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "1.4.0")

    def test_terminology_keeps_office_memory_spelled_out(self):
        for path in PLUGIN.rglob("*.md"):
            self.assertNotRegex(path.read_text(), r"(?<![A-Za-z])OM(?![A-Za-z])", str(path))

    def test_build_does_not_overwrite_existing_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(ROOT, Path(tmp))
            with self.assertRaises(FileExistsError):
                build(ROOT, Path(tmp))


if __name__ == "__main__":
    unittest.main()
