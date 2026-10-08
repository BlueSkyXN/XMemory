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
from check_package import SKILLS, check
from build_release import build


class PackageTests(unittest.TestCase):
    def test_package_contract(self):
        self.assertEqual(check(), [])

    def test_no_runtime_code_or_components(self):
        plugin = ROOT / "plugins" / "xmemory"
        self.assertFalse(any(p.suffix in {".py", ".js", ".mjs", ".sh", ".db"} for p in plugin.rglob("*")))
        for name in ("scripts", "hooks", "commands", "node_modules"):
            self.assertFalse((plugin / name).exists())

    def test_skill_descriptions_are_distinct(self):
        descriptions = []
        for name in SKILLS:
            lines = (ROOT / "plugins/xmemory/skills" / name / "SKILL.md").read_text().splitlines()
            descriptions.append(next(line for line in lines if line.startswith("description:")))
        self.assertEqual(len(set(descriptions)), 5)

    def test_broken_link_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for directory in ("plugins", ".claude-plugin", ".agents"):
                shutil.copytree(ROOT / directory, root / directory)
            path = root / "plugins/xmemory/skills/xmemory-recall/SKILL.md"
            with path.open("a") as stream:
                stream.write("\n[missing](missing.md)\n")
            self.assertTrue(any("Broken or escaping link" in error for error in check(root)))

    def test_unexpected_runtime_script_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for directory in ("plugins", ".claude-plugin", ".agents"):
                shutil.copytree(ROOT / directory, root / directory)
            (root / "plugins/xmemory/run.py").write_text("print('unexpected')\n")
            self.assertTrue(any("Non-document payload" in error for error in check(root)))

    def test_private_absolute_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for directory in ("plugins", ".claude-plugin", ".agents"):
                shutil.copytree(ROOT / directory, root / directory)
            path = root / "plugins/xmemory/README.md"
            original = path.read_text()
            self.assertEqual(check(root), [])
            # 仅使用虚构目录，覆盖原始路径和 JSON 转义形式。
            windows = "\\".join(("C:", "Users", "fixture-user", "notes.md"))
            paths = ["/".join(("", base, "fixture-user", "notes.md"))
                     for base in ("Users", "Volumes", "home")]
            paths += [windows, json.dumps(windows), windows.replace("\\", "/"),
                      windows.replace("Users", "users")]
            for private_path in paths:
                with self.subTest(path=private_path):
                    path.write_text(original + "\n" + private_path + "\n")
                    self.assertIn("Private absolute path in payload: README.md", check(root))

    def test_disabled_example_config(self):
        import tomllib
        config = tomllib.loads((ROOT / "plugins/xmemory/templates/config.toml").read_text())
        self.assertNotIn("sources", config)
        self.assertNotIn("projects", config)

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
                sums = archive.read(f"{label}/SHA256SUMS").decode().splitlines()
                for line in sums:
                    sha, name = line.split("  ", 1)
                    self.assertEqual(hashlib.sha256(archive.read(f"{label}/{name}")).hexdigest(), sha)
                payload_names = {name.removeprefix(f"{label}/plugins/xmemory/") for name in archive.namelist()
                                 if name.startswith(f"{label}/plugins/xmemory/")}
                actual = {p.relative_to(ROOT / "plugins/xmemory").as_posix()
                          for p in (ROOT / "plugins/xmemory").rglob("*") if p.is_file()}
                self.assertEqual(payload_names, actual)
                self.assertFalse(any("local/" in name or "tools/" in name or "__pycache__" in name
                                     for name in archive.namelist()))

    def test_portable_skills_are_self_contained(self):
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
            for skill in skills.iterdir():
                self.assertNotIn("](../../", (skill / "SKILL.md").read_text())
                for path in skill.rglob("*.md"):
                    for raw in LINK.findall(path.read_text()):
                        if re.match(r"(?:[a-z][a-z0-9+.-]*:|#)", raw, re.I):
                            continue
                        target = (path.parent / unquote(raw.split("#", 1)[0])).resolve()
                        self.assertTrue(target.is_relative_to(skill.resolve()), (path, raw))
                        self.assertTrue(target.is_file(), (path, raw))
                self.assertFalse(any(path.suffix in {".py", ".js", ".mjs", ".sh"}
                                     for path in skill.rglob("*")))

    def test_all_host_catalogs_are_in_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive_path, _ = build(ROOT, Path(tmp))
            with zipfile.ZipFile(archive_path) as archive:
                for relative in ("plugins/marketplace.json", ".claude-plugin/marketplace.json",
                                 ".agents/plugins/marketplace.json", "plugins/xmemory/plugin.json",
                                 "plugins/xmemory/.zcode-plugin/plugin.json",
                                 "plugins/xmemory/.claude-plugin/plugin.json"):
                    self.assertIn(f"{archive_path.stem}/{relative}", archive.namelist())

    def test_resource_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for directory in ("plugins", ".claude-plugin", ".agents"):
                shutil.copytree(ROOT / directory, root / directory)
            path = root / "plugins/xmemory/skills/xmemory-recall/references/contract.md"
            with path.open("a") as stream:
                stream.write("\nUnexpected independent edit.\n")
            self.assertTrue(any("Skill resource drift" in error for error in check(root)))

    def test_central_user_root_document_contract(self):
        plugin = ROOT / "plugins/xmemory"
        for name in ("references/contract.md", "references/storage.md",
                     "skills/xmemory-setup/SKILL.md", "integrations/entry.md",
                     "templates/config.toml", "docs/requirements.md"):
            text = (plugin / name).read_text()
            self.assertIn("~/.agents/memory/", text, name)
        for path in plugin.rglob("*.md"):
            text = path.read_text()
            self.assertNotIn("~/.xmemory/", text, str(path))
            self.assertNotIn("项目内 `.agents/xmemory/`", text, str(path))
        contract = (plugin / "references/contract.md").read_text()
        self.assertIn("不在项目中自动创建记忆目录或软链接", contract)
        self.assertIn("projects/<id>/", contract)
        existing = (plugin / "docs/existing-data.md").read_text()
        self.assertIn("迁入用户级集中库并停用旧流程", existing)

    def test_two_layer_write_contract(self):
        plugin = ROOT / "plugins/xmemory"
        for name in ("day.md", "BACKLOG.md", "note.md", "record.md", "CURRENT.md", "WITHDRAWN.md"):
            self.assertTrue((plugin / "templates" / name).is_file(), name)
        contract = (plugin / "references/contract.md").read_text()
        for phrase in ("采集只新建", "修改已有文件的只有整理", "记账类", "判断类", "不登记设备"):
            self.assertIn(phrase, contract)
        storage = (plugin / "references/storage.md").read_text()
        for phrase in ("YYYY-MM-DDTHHMM-<短名>-<4位随机串>.md", "YYYY-MM-DD.md", "近 30 天", "project:<ID>/"):
            self.assertIn(phrase, storage)
        record = (plugin / "skills/xmemory-record/SKILL.md").read_text()
        self.assertIn("只新建文件", record)
        self.assertIn("supersedes", record)
        curate = (plugin / "skills/xmemory-curate/SKILL.md").read_text()
        self.assertIn("./templates/day.md", curate)
        self.assertIn("待确认建议", curate)
        setup = (plugin / "skills/xmemory-setup/SKILL.md").read_text()
        self.assertIn("./integrations/scheduled-curate.md", setup)
        prompt = (plugin / "integrations/scheduled-curate.md").read_text()
        self.assertIn("本次无变化", prompt)
        self.assertIn("XMemory 读取协议", (plugin / "integrations/entry.md").read_text())

    def test_no_device_fields_in_templates(self):
        for path in (ROOT / "plugins/xmemory/templates").iterdir():
            text = path.read_text()
            self.assertNotRegex(text, r"(?m)^\s*device\s*[:=]", path.name)
            self.assertNotIn("hostname", text, path.name)

    def test_build_does_not_overwrite_existing_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(ROOT, Path(tmp))
            with self.assertRaises(FileExistsError):
                build(ROOT, Path(tmp))


if __name__ == "__main__":
    unittest.main()
