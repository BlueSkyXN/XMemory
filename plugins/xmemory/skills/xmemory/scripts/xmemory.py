#!/usr/bin/env python3
"""XMemory 的唯一程序入口：只读 status。"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8')
if sys.version_info < (3, 9):
    print("可选检查脚本需要 Python 3.9+；基本技能可直接使用宿主文件工具。")
    raise SystemExit(2)

from status import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
