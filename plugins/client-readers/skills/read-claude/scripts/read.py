#!/usr/bin/env python3
"""本技能专用脚本；无需安装命令或修改 PATH。"""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from client_readers.cli import main

if __name__ == "__main__":
    raise SystemExit(main("claude"))
