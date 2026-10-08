#!/usr/bin/env python3
"""Make every published skill self-contained; build-time only."""
from __future__ import annotations

import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^\]]*\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)")
RESOURCE_DIRS = {"references", "templates", "examples", "integrations", "docs"}


def expected_resources(root: Path = ROOT) -> dict[Path, bytes]:
    plugin = root / "plugins/xmemory"
    result: dict[Path, bytes] = {}
    for skill in sorted((plugin / "skills").iterdir()):
        queue = [raw.removeprefix("./").split("#", 1)[0]
                 for raw in LINK.findall((skill / "SKILL.md").read_text())
                 if raw.removeprefix("./").split("/", 1)[0] in RESOURCE_DIRS]
        visited: set[Path] = set()
        while queue:
            relative = Path(queue.pop())
            source = (plugin / relative).resolve()
            if not source.is_relative_to(plugin.resolve()) or not source.is_file():
                raise ValueError(f"Missing or escaping resource: {relative}")
            if source in visited:
                continue
            visited.add(source)
            relative = source.relative_to(plugin.resolve())
            if relative.parts[0] not in RESOURCE_DIRS:
                raise ValueError(f"Unexpected skill resource: {relative}")
            content = source.read_bytes()
            result[skill / relative] = content
            if source.suffix == ".md":
                for raw in LINK.findall(content.decode("utf-8")):
                    if re.match(r"(?:[a-z][a-z0-9+.-]*:|#)", raw, re.I):
                        continue
                    target = (source.parent / raw.split("#", 1)[0]).resolve()
                    if not target.is_relative_to(plugin.resolve()):
                        raise ValueError(f"Escaping resource link: {raw}")
                    queue.append(target.relative_to(plugin.resolve()).as_posix())
    return result


def sync(root: Path = ROOT, apply: bool = False) -> list[str]:
    expected = expected_resources(root)
    mismatches: list[str] = []
    for path, content in expected.items():
        if path.exists() and path.read_bytes() == content:
            continue
        mismatches.append(path.relative_to(root).as_posix())
        if apply:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    for skill in (root / "plugins/xmemory/skills").iterdir():
        for directory in RESOURCE_DIRS:
            for path in (skill / directory).rglob("*"):
                if path.is_file() and path not in expected:
                    mismatches.append("Unexpected resource: " + path.relative_to(root).as_posix())
    return mismatches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    mismatches = sync(apply=args.apply)
    for item in mismatches:
        print(item)
    if args.apply:
        return bool(sync())
    return bool(mismatches)


if __name__ == "__main__":
    raise SystemExit(main())
