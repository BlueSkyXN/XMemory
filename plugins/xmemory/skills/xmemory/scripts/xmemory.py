#!/usr/bin/env python3
"""XMemory 技能入口；无需安装命令或修改 PATH。用法见同技能的 SKILL.md。"""
import sys

sys.dont_write_bytecode = True
from xmemory_runtime import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
