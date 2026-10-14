#!/usr/bin/env python3
"""Repository-only checks. Not part of the installed XMemory plugin."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import tomllib
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
TOOL = "xmemory"
SKILLS = {TOOL, "xmemory-recall", "xmemory-note", "xmemory-run", "xmemory-extract", "xmemory-consolidate",
          "xmemory-setup", "xmemory-maintain"}
# 市场中的插件及其显示名；conversation-readers 自身的载荷检查在 build_conversation_readers.check。
PLUGINS = {"xmemory": "XMemory", "conversation-readers": "Conversation Readers"}
ALLOWED = {".md", ".toml", ".json"}
SCRIPTS = {"xmemory.py", "status.py", "toml_subset.py"}
# 每个技能必须链接的本地资源；任务技能还必须链接工具技能。
REQUIRED_LINKS = {
    TOOL: ("./references/format.md", "./references/status.md"),
    "xmemory-extract": ("../xmemory/references/sources.md",),
    "xmemory-consolidate": ("../xmemory/references/objects.md",),
    "xmemory-run": ("../xmemory-extract/SKILL.md",),
    "xmemory-setup": ("../xmemory/templates/automation-prompt.md", "../xmemory/templates/organization-prompt.md"),
}
# 运行时直接引用的兄弟技能文件。
RUNTIME_ASSETS = ("xmemory/references/objects.md", "xmemory/references/sources.md",
                  "xmemory/templates/config.toml", "xmemory/templates/agents-notice.md")
LINK = re.compile(r"\[[^\]]*\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)")
PRIVATE = re.compile(r"/(?:Users|Volumes|home)/|(?i:[A-Z]:[\\/]+Users[\\/])")


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
    if {p.name for p in skills.iterdir() if p.name != ".DS_Store"} != SKILLS:
        errors.append(f"Expected exactly the skills {sorted(SKILLS)}")
    descriptions = []
    for asset in RUNTIME_ASSETS:
        if not (skills / asset).is_file():
            errors.append(f"Missing runtime asset: {asset}")
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
                descriptions.append(description)
                if not 20 <= len(description) <= 1024:
                    errors.append(f"Description size: {skill}")
            except json.JSONDecodeError:
                errors.append(f"Description quoting: {skill}")
        if len(text.splitlines()) > 150:
            errors.append(f"Skill is too long: {skill}")
        for ref in REQUIRED_LINKS.get(skill, ()) + (() if skill == TOOL else ("../xmemory/SKILL.md",)):
            if f"]({ref})" not in text:
                errors.append(f"Skill does not link {ref}: {skill}")
        if "../../" in text:
            errors.append(f"Skill reaches outside the skills directory: {skill}")
    if len(set(descriptions)) != len(descriptions):
        errors.append("Skill descriptions must be distinct")
    scripts = skills / TOOL / "scripts"
    if not scripts.is_dir() or {p.name for p in scripts.iterdir() if p.is_file() and p.name != ".DS_Store"} != SCRIPTS:
        errors.append(f"Unexpected script set: {sorted(p.name for p in scripts.iterdir()) if scripts.is_dir() else []}")
    for path in sorted(plugin.rglob("*")):
        if ".DS_Store" in path.relative_to(plugin).parts:
            continue
        if path.is_symlink():
            errors.append(f"Symlink in payload: {path.relative_to(plugin)}")
        if not path.is_file():
            continue
        rel = path.relative_to(plugin)
        is_script = rel.parts[:3] == ("skills", TOOL, "scripts") and path.suffix == ".py"
        if path.suffix not in ALLOWED and path.name != "LICENSE" and not is_script:
            errors.append(f"Non-document payload: {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        if PRIVATE.search(text):
            errors.append(f"Private absolute path in payload: {rel}")
        if re.search(r"\b(?:TODO|FIXME|YOUR_API_KEY)\b", text):
            errors.append(f"Unresolved scaffold: {rel}")
        if "{{" in text and "templates" not in rel.parts and not is_script:
            errors.append(f"Template token outside templates: {rel}")
        if any(line.rstrip() != line for line in text.splitlines()):
            errors.append(f"Trailing whitespace: {rel}")
        if is_script:
            ast.parse(text, filename=str(rel))
            continue
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
            # 模板和格式示例中的占位链接（含 <…> 或 {{…}}）不是真实链接，由使用者替换。
            if "{{" in raw or "<" in raw:
                continue
            target = (path.parent / unquote(raw.split("#", 1)[0])).resolve()
            # 技能之间可以互相链接（同一插件的 skills/ 目录内），但不能链接到插件其他位置。
            boundary = plugin / "skills" if rel.parts[0] == "skills" else plugin
            if not target.is_relative_to(boundary.resolve()) or not target.exists():
                errors.append(f"Broken or escaping link: {rel}: {raw}")
    for relative in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json", "plugin.json"):
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
        if relative.startswith(".codex"):
            allowed |= {"interface"}
            if data.get("interface", {}).get("displayName") != PLUGINS[plugin.name]:
                errors.append("Codex manifest display name mismatch")
        if set(data) - allowed:
            errors.append(f"Unexpected host component: {relative}")
        if relative == "plugin.json" and data.get("$schema") != "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json":
            errors.append("Missing Agent Plugins schema declaration")
    errors.extend(check_markets(root))
    return errors


def check_markets(root: Path = ROOT) -> list[str]:
    """Each host marketplace lists every plugin exactly once, matching its own manifest."""
    errors: list[str] = []
    manifests = {}
    for name in PLUGINS:
        path = root / "plugins" / name / ".zcode-plugin" / "plugin.json"
        if not path.is_file():
            errors.append(f"Missing plugin manifest: {name}")
            continue
        manifests[name] = json.loads(path.read_text(encoding="utf-8"))
    for host, relative in (("zcode", "plugins/marketplace.json"), ("claude", ".claude-plugin/marketplace.json"),
                           ("codex", ".agents/plugins/marketplace.json")):
        path = root / relative
        if not path.is_file():
            errors.append(f"Missing {host} marketplace")
            continue
        catalog = json.loads(path.read_text(encoding="utf-8"))
        if catalog.get("name") != "xmemory-marketplace":
            errors.append(f"Unexpected {host} marketplace identity")
        if host == "claude" and catalog.get("owner", {}).get("name") != "BlueSkyXN":
            errors.append("Missing Claude marketplace owner")
        names = [entry.get("name") for entry in catalog.get("plugins", [])]
        if sorted(names) != sorted(PLUGINS):
            errors.append(f"{host} marketplace must list {sorted(PLUGINS)} once each: {names}")
            continue
        for entry in catalog["plugins"]:
            name = entry["name"]
            manifest = manifests.get(name, {})
            if host == "codex":
                value = entry.get("source", {})
                source = value.get("path") if isinstance(value, dict) and value.get("source") == "local" else None
                if entry.get("policy") != {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}:
                    errors.append(f"Invalid Codex installation policy: {name}")
                if entry.get("category") != "Productivity":
                    errors.append(f"Invalid Codex category: {name}")
            else:
                source = entry.get("source")
                fields = ("version", "description") + (("displayName",) if host == "zcode" else ())
                expected = dict(manifest, displayName=PLUGINS[name])
                for field in fields:
                    if entry.get(field) != expected.get(field):
                        errors.append(f"{host} marketplace mismatch: {name}.{field}")
            if not isinstance(source, str) or (path.parent / source if host == "zcode" else root / source).resolve() \
                    != (root / "plugins" / name).resolve():
                errors.append(f"{host} marketplace source mismatch: {name}")
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
