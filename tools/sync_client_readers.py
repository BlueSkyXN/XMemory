#!/usr/bin/env python3
"""同步独立读取技能的公共运行文件；不触碰 XMemory 技能和客户端数据。"""
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]
SKILLS = {
    "codex": "read-codex",
    "claude": "read-claude",
    "zcode": "read-zcode",
    "qodercn": "read-qodercn",
    "workbuddy": "read-workbuddy",
}


def sync(root=ROOT, apply=False):
    source = root / "tools/client_readers"
    payload = {"scripts/client_readers/" + path.relative_to(source).as_posix(): path.read_bytes()
               for path in sorted(source.rglob("*.py"))}
    payload["references/output-sessions.md"] = (source / "contract-sessions.md").read_bytes()
    if (source / "contract-memory.md").is_file():
        payload["references/output-memory.md"] = (source / "contract-memory.md").read_bytes()
    errors = []
    for client, skill in SKILLS.items():
        base = root / "plugins/client-readers/skills" / skill
        wrapper = ("#!/usr/bin/env python3\n"
                   '"""本技能专用脚本；无需安装命令或修改 PATH。"""\n'
                   "import sys\nsys.dont_write_bytecode = True\n"
                   "from client_readers.cli import main\n\n"
                   f'if __name__ == "__main__":\n    raise SystemExit(main("{client}"))\n').encode()
        for rel, data in dict(payload, **{"scripts/read.py": wrapper}).items():
            path = base / rel
            if not path.is_file() or path.read_bytes() != data:
                errors.append(str(path.relative_to(root)))
                if apply:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
        expected = {rel for rel in payload if rel.endswith('.py')}
        for path in (base / 'scripts/client_readers').rglob('*.py'):
            if path.relative_to(base).as_posix() not in expected:
                errors.append('Unexpected runtime file: ' + str(path.relative_to(root)))
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    differences = sync(apply=args.apply)
    for item in differences:
        print(item)
    raise SystemExit(bool(sync()) if args.apply else bool(differences))
