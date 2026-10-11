#!/usr/bin/env python3
"""Repository-only checks. Not part of the installed XMemory plugin."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import tomllib
from urllib.parse import unquote

from sync_skill_resources import sync

ROOT = Path(__file__).resolve().parents[1]
SKILLS = {"xmemory-setup", "xmemory-record", "xmemory-collect", "xmemory-curate", "xmemory-recall"}
ALLOWED = {".md", ".toml", ".json"}
LINK = re.compile(r"\[[^\]]*\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)")


def check(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    plugin = root / "plugins" / "xmemory"
    manifest_file = plugin / ".zcode-plugin" / "plugin.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("name") != plugin.name or not re.fullmatch(r"\d+\.\d+\.\d+", manifest.get("version", "")):
        errors.append("Plugin identity/version is invalid")
    if set(manifest) - {"name", "version", "description", "author", "skills"}:
        errors.append("Unexpected plugin component")
    if manifest.get("skills") != "./skills":
        errors.append("Skills directory is not ./skills")
    skills = plugin / "skills"
    if {p.name for p in skills.iterdir()} != SKILLS:
        errors.append("Expected exactly five named skills")
    for skill in sorted(SKILLS):
        path = skills / skill / "SKILL.md"
        if not path.is_file():
            errors.append(f"Missing skill: {skill}")
            continue
        text = path.read_text(encoding="utf-8")
        match = re.match(r'\A---\nname: ([a-z0-9-]+)\ndescription: ("[^\n]+")\n---\n', text)
        if not match or match[1] != skill:
            errors.append(f"Invalid canonical frontmatter: {skill}")
        else:
            try:
                description = json.loads(match[2])
                if not 20 <= len(description) <= 1024:
                    errors.append(f"Description size: {skill}")
            except json.JSONDecodeError:
                errors.append(f"Description quoting: {skill}")
        if len(text.splitlines()) > 150:
            errors.append(f"Skill is too long: {skill}")
        if "./references/contract.md" not in text:
            errors.append(f"Skill-local contract not linked: {skill}")
        if "../../" in text:
            errors.append(f"Skill depends on parent resources: {skill}")
    try:
        errors.extend("Skill resource drift: " + item for item in sync(root))
    except ValueError as exc:
        errors.append(str(exc))
    for path in sorted(plugin.rglob("*")):
        if path.is_symlink():
            errors.append(f"Symlink in payload: {path.relative_to(plugin)}")
        if not path.is_file():
            continue
        rel = path.relative_to(plugin)
        if path.suffix not in ALLOWED and path.name != "LICENSE":
            errors.append(f"Non-document payload: {rel}")
        text = path.read_text(encoding="utf-8")
        if re.search(r"/(?:Users|Volumes|home)/|(?i:[A-Z]:[\\/]+Users[\\/])", text):
            errors.append(f"Private absolute path in payload: {rel}")
        if re.search(r"\b(?:TODO|FIXME|YOUR_API_KEY)\b", text):
            errors.append(f"Unresolved scaffold: {rel}")
        if "{{" in text and "templates" not in rel.parts and not rel.as_posix().endswith("references/storage.md"):
            errors.append(f"Template token outside templates: {rel}")
        if any(line.rstrip() != line for line in text.splitlines()):
            errors.append(f"Trailing whitespace: {rel}")
        if path.suffix == ".json":
            json.loads(text)
        if path.suffix == ".toml":
            tomllib.loads(text)
        if path.suffix != ".md":
            continue
        if sum(line.startswith("```") for line in text.splitlines()) % 2:
            errors.append(f"Unclosed fence: {rel}")
        for raw in LINK.findall(text):
            if re.match(r"(?:[a-z][a-z0-9+.-]*:|#)", raw, re.I):
                continue
            # 模板中的占位链接（含 {{…}}）不是真实链接，由使用者替换。
            if "{{" in raw and "templates" in rel.parts:
                continue
            target = (path.parent / unquote(raw.split("#", 1)[0])).resolve()
            boundary = plugin / "skills" / rel.parts[1] if rel.parts[0] == "skills" else plugin
            if not target.is_relative_to(boundary.resolve()) or not target.exists():
                errors.append(f"Broken or escaping link: {rel}: {raw}")
    market_path = root / "plugins" / "marketplace.json"
    if not market_path.is_file():
        errors.append("Missing local marketplace")
    else:
        market = json.loads(market_path.read_text(encoding="utf-8"))
        entries = [entry for entry in market.get("plugins", []) if entry.get("name") == "xmemory"]
        if len(entries) != 1:
            errors.append("Expected one marketplace entry")
        else:
            entry = entries[0]
            for field in ("name", "version", "description"):
                if entry.get(field) != manifest.get(field):
                    errors.append(f"Marketplace mismatch: {field}")
            if entry.get("displayName") != "XMemory":
                errors.append("Marketplace display name must be XMemory")
            if (market_path.parent / entry["source"]).resolve() != plugin.resolve():
                errors.append("Marketplace source mismatch")
    for relative in (".claude-plugin/plugin.json", "plugin.json"):
        other = plugin / relative
        if not other.is_file():
            errors.append(f"Missing host manifest: {relative}")
            continue
        data = json.loads(other.read_text(encoding="utf-8"))
        fields = ("name", "version", "description", "skills") if relative.startswith(".") else ("name", "version", "description")
        for field in fields:
            if data.get(field) != manifest.get(field):
                errors.append(f"{relative} mismatch: {field}")
        allowed = {"name", "version", "description", "author", "skills"} if relative.startswith(".") else {"$schema", "name", "version", "description"}
        if set(data) - allowed:
            errors.append(f"Unexpected host component: {relative}")
        if relative == "plugin.json" and data.get("$schema") != "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json":
            errors.append("Missing Agent Plugins schema declaration")
    for host, relative in (("claude", ".claude-plugin/marketplace.json"), ("codex", ".agents/plugins/marketplace.json")):
        path = root / relative
        if not path.is_file():
            errors.append(f"Missing {host} marketplace")
            continue
        catalog = json.loads(path.read_text(encoding="utf-8"))
        if catalog.get("name") != f"xmemory-{host}":
            errors.append(f"Unexpected {host} marketplace identity")
        entries = catalog.get("plugins", [])
        if len(entries) != 1 or entries[0].get("name") != "xmemory":
            errors.append(f"Invalid {host} plugin entry")
            continue
        entry = entries[0]
        if host == "claude":
            if catalog.get("owner", {}).get("name") != "BlueSkyXN":
                errors.append("Missing Claude marketplace owner")
            source = entry.get("source")
            if entry.get("version") != manifest["version"]:
                errors.append("Claude marketplace version mismatch")
        else:
            value = entry.get("source", {})
            source = value.get("path") if isinstance(value, dict) and value.get("source") == "local" else None
            if entry.get("policy") != {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}:
                errors.append("Invalid Codex installation policy")
            if entry.get("category") != "Productivity":
                errors.append("Invalid Codex category")
        if source != "./plugins/xmemory" or (root / source).resolve() != plugin.resolve():
            errors.append(f"{host} marketplace source mismatch")
    cfg = tomllib.loads((plugin / "templates" / "config.toml").read_text(encoding="utf-8"))
    if cfg != {"format": "xmemory/v1", "capture": "milestone", "quiet_minutes": 60}:
        errors.append("Template must not enable example sources/projects")
    return errors


def payload_hashes(root: Path = ROOT) -> dict[str, str]:
    plugin = root / "plugins" / "xmemory"
    return {p.relative_to(plugin).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(plugin.rglob("*")) if p.is_file()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = check(args.root)
    print(json.dumps({"ok": not errors, "errors": errors,
                      "plugin_files": len(payload_hashes(args.root))}, ensure_ascii=False, indent=2))
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
