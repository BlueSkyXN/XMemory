#!/usr/bin/env python3
"""检查及构建独立对话读取扩展；不注册市场、不安装、不发布。"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote
import zipfile

from sync_conversation_readers import ROOT, SKILLS, sync

PLUGIN = ROOT / "plugins/conversation-readers"
LINK = re.compile(r"\[[^\]]*\]\(([^\s)]+)\)")


def check(plugin=PLUGIN):
    errors = []
    manifest = json.loads((plugin / "plugin.json").read_text(encoding="utf-8"))
    if manifest.get("name") != "conversation-readers" or not re.fullmatch(r"\d+\.\d+\.\d+", manifest.get("version", "")):
        errors.append("Invalid identity/version")
    for rel in [".claude-plugin/plugin.json", ".zcode-plugin/plugin.json"]:
        data = json.loads((plugin / rel).read_text(encoding="utf-8"))
        if any(data.get(k) != manifest.get(k) for k in ["name", "version", "description"]) or data.get("skills") != "./skills":
            errors.append(f"Manifest mismatch: {rel}")
    if {p.name for p in (plugin / "skills").iterdir()} != set(SKILLS.values()):
        errors.append("Expected five client reader skills")
    for client, name in SKILLS.items():
        folder = plugin / "skills" / name
        text = (folder / "SKILL.md").read_text(encoding="utf-8")
        if not text.startswith(f"---\nname: {name}\ndescription: "):
            errors.append(f"Invalid skill metadata: {name}")
        for rel in ["scripts/read_conversations.py", "scripts/reader_runtime.py", "references/output.md", "references/formats.md"]:
            if not (folder / rel).is_file():
                errors.append(f"Missing {name}/{rel}")
        wrapper = (folder / "scripts/read_conversations.py").read_text(encoding="utf-8")
        if f'main("{client}")' not in wrapper:
            errors.append(f"Wrong client wrapper: {name}")
    for path in sorted(plugin.rglob("*")):
        if path.is_symlink():
            errors.append(f"Symlink: {path.relative_to(plugin)}")
        if not path.is_file():
            continue
        rel = path.relative_to(plugin)
        if path.suffix not in {".md", ".py", ".json"} and path.name != "LICENSE" and path != plugin / "SHA256SUMS":
            errors.append(f"Unexpected payload: {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"/(?:Users|Volumes|home)/|(?i:[A-Z]:[\\/]+Users[\\/])", text):
            errors.append(f"Private path: {rel}")
        if any(line.rstrip() != line for line in text.splitlines()):
            errors.append(f"Whitespace: {rel}")
        if path.suffix == ".py":
            ast.parse(text, filename=str(rel))
        if path.suffix == ".json":
            json.loads(text)
        if path.suffix == ".md":
            for raw in LINK.findall(text):
                if re.match(r"(?:[a-z][a-z0-9+.-]*:|#)", raw, re.I):
                    continue
                target = (path.parent / unquote(raw.split("#", 1)[0])).resolve()
                boundary = plugin / "skills" / rel.parts[1] if rel.parts[0] == "skills" else plugin
                if not target.is_relative_to(boundary.resolve()) or not target.is_file():
                    errors.append(f"Broken or escaping link: {rel}: {raw}")
    return errors


def build(output, portable=False, plugin=PLUGIN):
    errors = check(plugin)
    if errors:
        raise ValueError("; ".join(errors))
    version = json.loads((plugin / "plugin.json").read_text(encoding="utf-8"))["version"]
    label = f"ConversationReaders-{version}" + ("-skills" if portable else "")
    paths = sorted(plugin.rglob("*")) if not portable else [*sorted((plugin / "skills").rglob("*")), plugin / "LICENSE", plugin / "README.md"]
    files = {p.relative_to(plugin).as_posix(): p.read_bytes() for p in paths if p.is_file()}
    if portable:
        # 技能包不含插件层验证文档；README 中的本地链接需有对应文件。
        files["docs/validation.md"] = (plugin / "docs/validation.md").read_bytes()
    files["SHA256SUMS"] = "".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())).encode()
    output.mkdir(parents=True, exist_ok=True)
    target = output / f"{label}.zip"
    checksum = target.with_suffix(".zip.sha256")
    if target.exists() or checksum.exists():
        raise FileExistsError(f"Refusing to overwrite: {target}; use a new output directory")
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(f"{label}/{name}", (2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    with checksum.open("x") as stream:
        stream.write(f"{digest}  {target.name}\n")
    return target, digest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="默认 dist/conversation-readers-<清单版本>")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    errors = sync() + check()
    if errors or args.check:
        print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False, indent=2))
        raise SystemExit(bool(errors))
    version = json.loads((PLUGIN / "plugin.json").read_text(encoding="utf-8"))["version"]
    output = args.output or ROOT / f"dist/conversation-readers-{version}"
    print(json.dumps([dict(archive=str(p), sha256=h) for p, h in [build(output), build(output, portable=True)]], indent=2))
