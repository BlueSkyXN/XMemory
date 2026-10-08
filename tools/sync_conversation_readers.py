#!/usr/bin/env python3
"""同步独立读取技能的公共运行文件；不触碰 XMemory 技能和客户端数据。"""
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]
SKILLS = {
    "codex": "read-codex-conversations",
    "claude": "read-claude-conversations",
    "zcode": "read-zcode-conversations",
    "qodercn": "read-qodercn-conversations",
    "workbuddy": "read-workbuddy-conversations",
}


def sync(root=ROOT, apply=False):
    source = (root / "tools/conversation_reader_runtime.py").read_bytes()
    contract = (root / "tools/conversation_reader_contract.md").read_bytes()
    errors = []
    for client, skill in SKILLS.items():
        base = root / "plugins/conversation-readers/skills" / skill
        wrapper = ("#!/usr/bin/env python3\n"
                   '"""本技能专用脚本；无需安装命令或修改 PATH。"""\n'
                   "import sys\nsys.dont_write_bytecode = True\n"
                   "from reader_runtime import main\n\n"
                   f'if __name__ == "__main__":\n    raise SystemExit(main("{client}"))\n').encode()
        for rel, data in {"scripts/read_conversations.py": wrapper,
                          "scripts/reader_runtime.py": source,
                          "references/output.md": contract}.items():
            path = base / rel
            if not path.is_file() or path.read_bytes() != data:
                errors.append(str(path.relative_to(root)))
                if apply:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    differences = sync(apply=args.apply)
    for item in differences:
        print(item)
    raise SystemExit(bool(sync()) if args.apply else bool(differences))
