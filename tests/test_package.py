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
        self.assertEqual(code, {"skills/xmemory/scripts/xmemory.py", "skills/xmemory/scripts/status.py",
                                "skills/xmemory/scripts/toml_subset.py"})
        for name in ("hooks", "commands", "node_modules"):
            self.assertFalse((PLUGIN / name).exists())

    def test_one_tool_many_skills(self):
        self.assertEqual({p.name for p in (PLUGIN / "skills").iterdir() if p.name != ".DS_Store"}, SKILLS)
        self.assertEqual(len(SKILLS), 8)
        for skill in SKILLS - {"xmemory"}:
            text = (PLUGIN / "skills" / skill / "SKILL.md").read_text()
            self.assertIn("](../xmemory/SKILL.md)", text, skill)

    def test_unexpected_script_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_repo(root)
            (root / "plugins/xmemory/run.py").write_text("print('unexpected')\n")
            self.assertTrue(any("Non-document payload" in error for error in check(root)))
            (root / "plugins/xmemory/run.py").unlink()
            (root / "plugins/xmemory/skills/xmemory/scripts/extra.py").write_text("x = 1\n")
            self.assertTrue(any("Unexpected script set" in error for error in check(root)))
            (root / "plugins/xmemory/skills/xmemory/scripts/extra.py").unlink()
            (root / "plugins/xmemory/skills/xmemory-note/helper.py").write_text("x = 1\n")
            self.assertTrue(any("Non-document payload" in error for error in check(root)))

    def test_xmemory_does_not_need_reader_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(PLUGIN / "skills", root / "skills")
            import subprocess
            command = [sys.executable, "-B", str(root / "skills/xmemory/scripts/xmemory.py"), "--help"]
            result = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("status", result.stdout)
            self.assertFalse(list((root / "skills").rglob("reader_runtime.py")))

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
            script = root / "plugins/xmemory/skills/xmemory/scripts/status.py"
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
                for plugin in ("xmemory", "client-readers"):
                    payload = {name.removeprefix(f"{label}/plugins/{plugin}/") for name in archive.namelist()
                               if name.startswith(f"{label}/plugins/{plugin}/")}
                    actual = {p.relative_to(ROOT / "plugins" / plugin).as_posix()
                              for p in (ROOT / "plugins" / plugin).rglob("*")
                              if p.is_file() and ".DS_Store" not in p.relative_to(ROOT / "plugins" / plugin).parts}
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
            for name in ("xmemory.py", "status.py", "toml_subset.py"):
                self.assertTrue((skills / "xmemory" / "scripts" / name).is_file(), name)
            self.assertEqual({p.relative_to(skills).parts[0] for p in skills.rglob("*.py")}, {"xmemory"})
            skill = skills
            for path in skills.rglob("*.md"):
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
                manifests = [f"plugins/{plugin}/{name}" for plugin in ("xmemory", "client-readers")
                             for name in ("plugin.json", ".zcode-plugin/plugin.json", ".claude-plugin/plugin.json",
                                          ".codex-plugin/plugin.json")]
                for relative in ("plugins/marketplace.json", ".claude-plugin/marketplace.json",
                                 ".agents/plugins/marketplace.json", *manifests):
                    self.assertIn(f"{archive_path.stem}/{relative}", archive.namelist())
                for relative in ("plugins/marketplace.json", ".claude-plugin/marketplace.json",
                                 ".agents/plugins/marketplace.json"):
                    catalog = json.loads(archive.read(f"{archive_path.stem}/{relative}"))
                    self.assertEqual(catalog["name"], "xmemory-marketplace")

    def test_marketplace_identity_is_shared_across_hosts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_repo(root)
            for host, relative, old_name in (
                ("zcode", "plugins/marketplace.json", "xmemory"),
                ("claude", ".claude-plugin/marketplace.json", "xmemory-claude"),
                ("codex", ".agents/plugins/marketplace.json", "xmemory-codex"),
            ):
                with self.subTest(host=host):
                    path = root / relative
                    original = path.read_text(encoding="utf-8")
                    data = json.loads(original)
                    self.assertEqual(data["name"], "xmemory-marketplace")
                    data["name"] = old_name
                    path.write_text(json.dumps(data), encoding="utf-8")
                    self.assertIn(f"Unexpected {host} marketplace identity", check(root))
                    path.write_text(original, encoding="utf-8")
            self.assertEqual(check(root), [])

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
                    data["plugins"] = [e for e in data["plugins"] if e["name"] != "client-readers"]
                    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                    self.assertTrue(any("must list" in error for error in check(root)))
                    path.write_text(original, encoding="utf-8")
            path = root / ".claude-plugin/marketplace.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            next(e for e in data["plugins"] if e["name"] == "xmemory")["version"] = "9.9.9"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            self.assertIn("claude marketplace mismatch: xmemory.version", check(root))

    def test_terminology_keeps_office_memory_spelled_out(self):
        for path in PLUGIN.rglob("*.md"):
            self.assertNotRegex(path.read_text(), r"(?<![A-Za-z])OM(?![A-Za-z])", str(path))

    def test_build_does_not_overwrite_existing_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(ROOT, Path(tmp))
            with self.assertRaises(FileExistsError):
                build(ROOT, Path(tmp))

    def test_finder_metadata_is_preserved_but_never_packaged(self):
        from build_client_readers import build as build_readers, check as check_readers
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            copy_repo(root)
            shutil.copytree(ROOT / "docs", root / "docs")
            metadata = []
            for plugin in ("xmemory", "client-readers"):
                base = root / "plugins" / plugin
                for folder in [base, *[p for p in base.rglob("*") if p.is_dir()]]:
                    path = folder / ".DS_Store"
                    path.write_bytes(b"synthetic finder metadata\x00\xff")
                    metadata.append((path, path.read_bytes(), path.stat().st_mtime_ns))
            self.assertEqual(check(root), [])
            self.assertEqual(check_readers(root / "plugins/client-readers"), [])
            for portable in (False, True):
                output = Path(tmp) / str(portable)
                archives = [build(root, output, portable=portable)[0],
                            build_readers(output, portable=portable, plugin=root / "plugins/client-readers")[0]]
                for path in archives:
                    with zipfile.ZipFile(path) as archive:
                        self.assertIsNone(archive.testzip())
                        self.assertFalse(any(".DS_Store" in Path(name).parts for name in archive.namelist()))
                        self.assertNotIn(".DS_Store", archive.read(f"{path.stem}/SHA256SUMS").decode())
            for path, data, mtime in metadata:
                self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), (data, mtime))


if __name__ == "__main__":
    unittest.main()
