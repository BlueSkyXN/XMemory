#!/usr/bin/env python3
"""Build an offline marketplace archive; never install or publish it."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from check_package import ROOT, check

FIXED_TIME = (2026, 1, 1, 0, 0, 0)


def build(root: Path, output: Path, portable: bool = False) -> tuple[Path, str]:
    errors = check(root)
    if errors:
        raise ValueError("Package checks failed: " + "; ".join(errors))
    plugin = root / "plugins" / "xmemory"
    version = json.loads((plugin / ".zcode-plugin" / "plugin.json").read_text())["version"]
    label = f"XMemory-{version}" + ("-skills" if portable else "")
    files: dict[str, bytes] = {}
    files["INSTALL.md"] = (root / "docs" / "release-install.md").read_bytes()
    if portable:
        for path in sorted((plugin / "skills").rglob("*")):
            if path.is_file():
                files[path.relative_to(plugin).as_posix()] = path.read_bytes()
        files["LICENSE"] = (plugin / "LICENSE").read_bytes()
    else:
        for name in ("plugins/marketplace.json", ".claude-plugin/marketplace.json",
                     ".agents/plugins/marketplace.json"):
            files[name] = (root / name).read_bytes()
        for path in sorted(plugin.rglob("*")):
            if path.is_file():
                files[f"plugins/xmemory/{path.relative_to(plugin).as_posix()}"] = path.read_bytes()
    hashes = "".join(f"{hashlib.sha256(value).hexdigest()}  {name}\n" for name, value in sorted(files.items()))
    files["SHA256SUMS"] = hashes.encode("utf-8")
    output.mkdir(parents=True, exist_ok=True)
    target = output / f"{label}.zip"
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite {target}; use a new output directory.")
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(f"{label}/{name}", FIXED_TIME)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    checksum_path = target.with_suffix(".zip.sha256")
    with checksum_path.open("x", encoding="utf-8") as stream:
        stream.write(f"{checksum}  {target.name}\n")
    return target, checksum


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    results = []
    for portable in (False, True):
        target, checksum = build(ROOT, args.output.resolve(), portable=portable)
        results.append({"archive": str(target), "sha256": checksum})
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
