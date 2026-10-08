#!/usr/bin/env python3
"""本技能专用脚本；无需安装命令或修改 PATH。"""
import sys
sys.dont_write_bytecode = True
from reader_runtime import main

if __name__ == "__main__":
    raise SystemExit(main("qodercn"))
