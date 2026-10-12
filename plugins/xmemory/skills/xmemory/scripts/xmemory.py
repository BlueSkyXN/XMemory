#!/usr/bin/env python3
"""XMemory 的唯一程序入口：只读 status。"""
import json
import sys

sys.dont_write_bytecode = True
if sys.version_info < (3, 9):
    print(json.dumps({"ok": False, "error": "XMemory 需要 Python 3.9+"}, ensure_ascii=False))
    raise SystemExit(2)

from status import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
