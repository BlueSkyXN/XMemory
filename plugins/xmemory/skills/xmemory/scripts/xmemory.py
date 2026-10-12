#!/usr/bin/env python3
"""XMemory 技能入口；无需安装命令或修改 PATH。用法见同技能的 SKILL.md。"""
import json
import sys

sys.dont_write_bytecode = True
if sys.version_info < (3, 9):
    # 客户端里拿到的 python3 可能很旧；给出明确提示，而不是导入时报一串栈信息。
    print(json.dumps({"ok": False, "error": "XMemory 需要 Python 3.9+，当前 python3 是 %s（%s）"
                      % (sys.version.split()[0], sys.executable)}, ensure_ascii=False))
    raise SystemExit(2)
from xmemory_runtime import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
