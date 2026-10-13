#!/usr/bin/env python3
"""生成双库查阅及写入的虚构测试宿主；不访问真实客户端。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil


def make_fixture(root: Path, skills: Path) -> None:
    root.mkdir(parents=True, exist_ok=False)
    now = datetime.now(timezone.utc).isoformat()

    def write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def library(base: Path, body: str, refs: list[str], excluded: list[str], day: str = "2026-10-08") -> None:
        write(base / "config.toml", 'format = "xmemory/v1.5"\ntimezone = "UTC"\n'
              f'exclude_sessions = {json.dumps(excluded)}\n\n'
              '[sources.host_memory]\nenabled = false\nkind = "memory"\nclient = "codex"\n'
              'paths = []\n\n[projects.Maple]\nroots = []\n')
        if not body:
            return
        fields = dict(format="xmemory/v1.5", kind="record", updated=now, source="note", client="codex",
                      source_ref="fixture:project-decision", source_location="虚构测试原话",
                      source_updated=f"{day}T10:00:00+00:00", evidence="primary",
                      projects=["Maple"], day=day, day_basis="event",
                      session_refs=refs, coverage="complete")
        frontmatter = "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in fields.items())
        write(base / "records/notes/decision.md", f"---\n{frontmatter}\n---\n\n# Maple\n\n{body}\n")
        write(base / "memory_summary.md", '---\nformat: "xmemory/v1.5"\nkind: "summary"\n'
              f'updated: "{now}"\n---\n\n# Maple\n\n'
              '[项目决定](records/notes/decision.md)\n')

    cases = [
        ("complement", "用户原话：Maple 导出说明先写限制和适用条件，再给命令。来源 codex:style-101。",
         "用户原话：Maple 导出用 JSON Lines，便于逐行检查差异。", ["zcode:format-101"], [],
         "Maple 的导出格式和说明顺序是什么？"),
        ("native-correction", "2026-10-09 用户更正：Maple 仅生产环境改为 SQLite；离线比较仍用 JSON Lines。来源 codex:change-102。",
         "2026-10-08 用户决定 Maple 使用 JSON Lines。10 月 12 日重新保存的摘要仍复述该决定，未发现新的用户指令。",
         ["zcode:format-102"], [], "Maple 生产环境和离线比较分别使用什么格式？"),
        ("xmemory-correction", "2026-10-08 用户决定 Maple 使用 JSON Lines。10 月 12 日重新保存仍复述该决定。来源 codex:format-103。",
         "2026-10-09 用户更正：Maple 仅生产环境改为 SQLite；离线比较仍用 JSON Lines。",
         ["zcode:change-103"], [], "Maple 生产环境和离线比较分别使用什么格式？"),
        ("forgotten", "来源 codex:retired-104：用户曾规定 Maple 导出格式为 EXCLUDED_MAPLE_FORMAT。\n"
         "来源 zcode:retired-104：独立决定 Maple 每次执行前先预览影响。",
         "来源 zcode:retired-104 的独立用户决定：每次执行前先预览影响。",
         ["zcode:retired-104"], ["codex:retired-104"], "Maple 目前有哪些有依据的导出与执行约定？"),
        ("xmemory-empty", "用户原话：Maple 操作先预览再执行。来源 codex:preview-105。",
         "", [], [], "Maple 执行前有什么约定？"),
        ("native-unavailable", None, "用户原话：Maple 输出使用 UTF-8。", ["zcode:encoding-106"], [],
         "Maple 输出使用什么编码？"),
    ]
    recall = root / "recall"
    questions = []
    for name, native, body, refs, excluded, question in cases:
        base = recall / name
        library(base / "memory", body, refs, excluded,
                day="2026-10-09" if name == "xmemory-correction" else "2026-10-08")
        if native is not None:
            write(base / "native/MEMORY.md", f"# 原生项目记忆\n\n{native}\n")
        write(base / "host.md", "这是虚构测试宿主的原生记忆协议，不是生产客户端实现。\n"
              "原生记忆入口是本目录 native/MEMORY.md，按问题读取；入口不存在则该环境不可用。\n"
              "用户明确要求记住内容时，使用普通文件工具追加到 native/notes.md 并读回；不改写入口。\n")
        questions.append(f"- {name}：{question}")
    shutil.copytree(skills, recall / "guidance", ignore=shutil.ignore_patterns(".DS_Store", "__pycache__"))
    write(recall / "prompt.md", "使用 guidance 中的 XMemory Skill 回答下面六个独立环境的问题。"
          "每个环境内 host.md 是本次测试宿主提供的协议，memory 是其 XMemory 根；彼此不共享事实。"
          "按宿主协议和 Skill 自行取证，只读环境文件，不读本目录以外的材料、不运行联网或额外模型。"
          "按环境名给出简洁回答和关键来源，说明影响答案的缺口。\n\n" + "\n".join(questions) + "\n")

    remember = root / "remember"
    library(remember / "memory", "", [], [])
    write(remember / "native/MEMORY.md", "# Maple\n\n既有原生规则：执行前先预览。来源 codex:existing-201。\n")
    write(remember / "host.md", "这是虚构测试宿主支持的原生记忆协议。当前会话原生身份是 codex:remember-202。\n"
          "入口 native/MEMORY.md 用于读取。用户明确要求记住时，通过普通文件工具追加短笔记到 native/notes.md 并读回；"
          "保留既有入口，不直接重写它。此协议只适用于本次测试宿主。\n")
    shutil.copytree(skills, remember / "guidance", ignore=shutil.ignore_patterns(".DS_Store", "__pycache__"))
    write(remember / "prompt.md", "请按 host.md 的宿主协议与 guidance 中的 XMemory Skill 处理："
          "记住：以后 Maple 的上线说明先列回滚条件，再给操作命令，只适用于 Maple。"
          "XMemory 根是 memory。只允许在 memory/ 和 native/ 内写入，其他文件只读；"
          "不读目录外材料，不联网、不运行额外模型。完成后说明实际保存位置和未完成范围。\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--skills", type=Path, required=True)
    args = parser.parse_args()
    make_fixture(args.destination.resolve(), args.skills.resolve())
    print(args.destination.resolve())
