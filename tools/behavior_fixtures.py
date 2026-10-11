#!/usr/bin/env python3
"""Build isolated XMemory behavior fixtures and check the files an agent left behind.

Test-only: not part of the plugin payload. All content is fictional. ``build`` copies the
current skills into ``<dir>/skills`` and writes ``<dir>/memroot``, ``<dir>/fixtures`` and
``<dir>/work``; the agent run itself happens outside this tool.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import textwrap

ROOT = Path(__file__).resolve().parents[1]
CASES = ("collect-gap", "collect-retry", "curate-second-pass", "curate-pending-resume", "curate-no-change")
OLD_DISK = "/Volumes/XM-OldDisk/work/demo-api"
MISSING_TARGET = "/Volumes/XM-Unmounted/codex-memories/2026-10-09T03-00-00-c5d6-demo_retry_policy.md"
PARSER_FIX = "2026-10-08T02-00-00-a1b2-demo_config_parser_fix.md"
WITHDRAWN = "2026-10-08T15-40-00-b7c8-demo_scratch_experiment.md"
RETRY = "2026-10-09T03-00-00-c5d6-demo_retry_policy.md"
DEPLOY = "2026-10-09T07-00-00-c3d4-demo_staging_deploy.md"
UNDATED = "legacy_import_note.md"
OLD_BATCH = "2026-10-10-demo-api-a0b1"
PENDING_BATCH = "2026-10-11-demo-api-p7k2"


def _write(path: Path, text: str, base: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip("\n").replace("$T", str(base)), encoding="utf-8")


def _config(base: Path) -> None:
    _write(base / "memroot/config.toml", f"""
        format = "xmemory/v1"
        capture = "milestone"
        quiet_minutes = 60
        timezone = "Asia/Shanghai"

        [workspace]
        containers = ["$T/work"]

        [projects."demo-api"]
        roots = ["$T/work/demo-api", "{OLD_DISK}"]
        owner = "xmemory"

        [sources.codex-memory]
        client = "codex"
        kind = "native-memory"
        path = "$T/fixtures/codex-memories"
        route = "by-cwd"
        enabled = true
        """, base)
    _write(base / "memroot/MEMORY.md", """
        # 个人主记忆

        范围：personal

        ## 项目入口

        - demo-api：配置解析修复与 staging 验证 → [projects/demo-api/MEMORY.md](projects/demo-api/MEMORY.md)
        """, base)
    (base / "work/demo-api").mkdir(parents=True, exist_ok=True)


def _summary(base: Path, name: str, text: str) -> None:
    _write(base / "fixtures/codex-memories/rollout_summaries" / name, text, base)


def _retry_summary(base: Path) -> None:
    _summary(base, RETRY, """
        thread_id: 0199cccc-3333-7000-8000-000000000003
        updated_at: 2026-10-09T03:20:00+00:00
        rollout_path: fixtures/sessions/rollout-2026-10-09T11-00-00-0199cccc-3333-7000-8000-000000000003.jsonl
        cwd: $T/work/demo-api
        git_branch: fix/retry-policy

        # 统一 HTTP 客户端的重试策略

        Rollout context: 工作目录为 demo-api。用户要求给外部调用加重试。

        ## Task 1: 重试策略

        Outcome: success

        Preference signals:
        - 用户说“demo-api 的外部调用最多重试 3 次，用指数退避” -> 本项目重试上限为 3 次。

        Key steps:
        - 修改 src/http/client.py，最多重试 3 次，退避 0.5s/1s/2s。
        - 运行 pytest tests/test_client.py，输出 8 passed。

        Unfinished:
        - 尚未在 staging 观察重试日志。
        """)


def _collect_base(base: Path) -> None:
    _config(base)
    _write(base / "memroot/projects/demo-api/MEMORY.md", """
        # demo-api 主记忆

        范围：project:demo-api
        """, base)
    _write(base / "memroot/state/withdrawn.md", f"""
        # 撤回标识

        只保存阻止自动重新收录的最小标识，不保留原文。

        | 条目ID | 可安全保留的来源地址 | 撤回日期 | 执行者 | 原因（不含原文） |
        |---|---|---|---|---|
        | wd-0001 | codex-memory#rollout_summaries/{WITHDRAWN}；codex:jsonl:0199aaaa-7777-7000-8000-000000000007 | 2026-10-10 | 用户指示 | 用户要求忘记一次临时实验 |
        """, base)
    _summary(base, PARSER_FIX, """
        thread_id: 0199aaaa-1111-7000-8000-000000000001
        updated_at: 2026-10-08T03:10:00+00:00
        rollout_path: fixtures/sessions/rollout-2026-10-08T10-00-00-0199aaaa-1111-7000-8000-000000000001.jsonl
        cwd: $T/work/demo-api
        git_branch: fix/config-parser

        # 修复配置解析的空值处理并补回归测试

        Rollout context: 工作目录为 demo-api。用户要求修复配置文件中空字符串被当成默认值的问题。

        ## Task 1: 修复空值处理

        Outcome: success

        Preference signals:
        - 用户说“汇报先给结论，再给依据” -> 以后汇报时先写结论再写依据。

        Key steps:
        - 修改 src/config/parser.py 的 parse_value，空字符串保留为空，不再回落默认值。
        - 新增 tests/test_parser.py::test_empty_string，本地运行 pytest 通过（12 passed）。

        Reusable knowledge:
        - parse_value 的回落逻辑会缓存，修改后需要清理 .cache/config。

        Unfinished:
        - 尚未部署到测试环境；下一步 deploy-to-staging。
        """)
    _summary(base, WITHDRAWN, """
        thread_id: 0199aaaa-7777-7000-8000-000000000007
        updated_at: 2026-10-08T15:50:00+00:00
        rollout_path: fixtures/sessions/rollout-2026-10-08T23-40-00-0199aaaa-7777-7000-8000-000000000007.jsonl
        cwd: $T/work/demo-api

        # 临时压测实验 XM-WITHDRAWN-MARKER

        Rollout context: 一次临时压测实验，用户随后要求忘记。

        Key steps:
        - 在本地跑了压测脚本，记录了吞吐数字。
        """)
    link = base / "fixtures/codex-memories/rollout_summaries" / RETRY
    link.symlink_to(MISSING_TARGET)
    _summary(base, DEPLOY, f"""
        thread_id: 0199bbbb-2222-7000-8000-000000000002
        updated_at: 2026-10-09T08:30:00+00:00
        rollout_path: fixtures/sessions/rollout-2026-10-09T15-00-00-0199bbbb-2222-7000-8000-000000000002.jsonl
        cwd: {OLD_DISK}
        git_branch: main

        # 部署到测试环境并发现一个回归

        Rollout context: 在旧磁盘上的 demo-api 工作副本中工作。用户要求把修复部署到测试环境。

        ## Task 1: 部署到 staging

        Outcome: partial

        Key steps:
        - 执行 make deploy ENV=staging，助手汇报输出 deploy ok（version 1.4.2）。
        - 冒烟测试发现 /config 接口对旧格式配置返回 500。

        Unfinished:
        - fix-legacy-config：修复旧格式配置导致的 500，再部署验证。
        """)
    _summary(base, UNDATED, """
        updated_at: 2026-10-10T02:00:00+00:00
        cwd: $T/work/demo-api

        # 从旧笔记导入的日志位置

        这份摘要由旧笔记导入，没有原始会话，也没有记录事件发生时间。

        Reusable knowledge:
        - demo-api 的应用日志在 logs/app/，按天滚动，保留 14 份。
        """)


FOOTPRINT_1000 = """
    ---
    name: 1000-config-parser-fix-a1b2
    description: 修复配置解析空字符串回落默认值的问题，本地 pytest 12 passed（原生转述）
    event_at: 2026-10-08T10:00:00+08:00
    time_basis: rollout 文件名本地时间 2026-10-08T10-00-00
    recorded_at: 2026-10-10T20:30:00+08:00
    scope: project:demo-api
    cwd: $T/work/demo-api
    client: codex
    kind: native-memory
    source: codex-memory#rollout_summaries/2026-10-08T02-00-00-a1b2-demo_config_parser_fix.md
    read_level: full
    provenance: [原生转述, AI 汇报]
    origin: codex:jsonl:0199aaaa-1111-7000-8000-000000000001
    ---

    # 修复配置解析空值处理

    ## 做了什么

    修改 parse_value，空字符串保留为空，不再回落默认值；新增回归测试。

    ## 结果与证据

    - AI 汇报：本地 pytest 12 passed；本库未见实际输出。

    ## 失败与改法

    - 只改读取函数时测试仍失败 → 回落逻辑有缓存 → 改解析逻辑后先清 .cache/config（原生转述）。

    ## 未完成

    - deploy-to-staging：尚未部署到测试环境。

    ## 去哪找原件

    - codex-memory#rollout_summaries/2026-10-08T02-00-00-a1b2-demo_config_parser_fix.md（全文已读）
    """

FOOTPRINT_1500_REVIEW = """
    ---
    name: 1500-config-review-k9m3
    description: 评审空值修复时讨论 staging 回滚步骤，用户未表态（原生转述）
    event_at: 2026-10-08T15:00:00+08:00
    time_basis: rollout 文件名本地时间 2026-10-08T15-00-00
    recorded_at: 2026-10-10T20:31:00+08:00
    scope: project:demo-api
    cwd: $T/work/demo-api
    client: codex
    kind: native-memory
    source: codex-memory#rollout_summaries/2026-10-08T07-00-00-k9m3-demo_config_review.md
    read_level: full
    provenance: [原生转述, AI 汇报]
    ---

    # 空值修复评审

    ## 做了什么

    评审空值修复，助手建议 staging 出问题时回滚到 1.4.1；用户没有表态。

    ## 决定

    - 空字符串保留为空，不回落默认值（原生转述，未读到用户原话）。

    ## 未完成

    - confirm-rollback：确认 staging 出问题时的回滚步骤。

    ## 去哪找原件

    - codex-memory#rollout_summaries/2026-10-08T07-00-00-k9m3-demo_config_review.md（本机找不到）
    """

FOOTPRINT_1630 = """
    ---
    name: 1630-cache-cleanup-verified-q4w8
    description: 实际运行确认：不清 .cache/config 时 test_empty_string 失败，清理后 12 passed
    event_at: 2026-10-08T16:30:00+08:00
    time_basis: 测试输出文件头部的带时区时间
    recorded_at: 2026-10-11T09:00:00+08:00
    scope: project:demo-api
    client: codex
    kind: workspace
    source: project:demo-api/test-output/2026-10-08-cache.txt
    read_level: full
    provenance: [执行结果]
    ---

    # 清缓存前后的测试对比

    ## 做了什么

    读取项目内保存的两次 pytest 输出，对比清理 .cache/config 前后的结果。

    ## 结果与证据

    - 执行结果：未清缓存时 tests/test_parser.py::test_empty_string FAILED；执行 make clean-cache 后 12 passed。

    ## 去哪找原件

    - project:demo-api/test-output/2026-10-08-cache.txt（全文已读）
    """

FOOTPRINT_DEPLOY = """
    ---
    name: 1500-staging-deploy-c3d4
    description: 部署到 staging，助手汇报 deploy ok 1.4.2；/config 对旧格式配置返回 500（原生转述）
    event_at: 2026-10-09T15:00:00+08:00
    time_basis: rollout 文件名本地时间 2026-10-09T15-00-00
    recorded_at: 2026-10-11T09:01:00+08:00
    scope: project:demo-api
    cwd: /Volumes/XM-OldDisk/work/demo-api
    client: codex
    kind: native-memory
    source: codex-memory#rollout_summaries/2026-10-09T07-00-00-c3d4-demo_staging_deploy.md
    read_level: full
    provenance: [原生转述, AI 汇报]
    origin: codex:jsonl:0199bbbb-2222-7000-8000-000000000002
    ---

    # 部署到 staging 并发现回归

    ## 做了什么

    执行 staging 部署并做冒烟测试。

    ## 结果与证据

    - AI 汇报：make deploy ENV=staging 输出 deploy ok（version 1.4.2）；本库未见实际输出。
    - 原生转述：冒烟测试中 /config 对旧格式配置返回 500。

    ## 未完成

    - fix-legacy-config：修复旧格式配置导致的 500，再部署验证。

    ## 去哪找原件

    - codex-memory#rollout_summaries/2026-10-09T07-00-00-c3d4-demo_staging_deploy.md（全文已读）
    """

OLD_AWARENESS = """
    # demo-api 意识

    范围：project:demo-api
    截至：2026-10-10T21:00:00+08:00
    本次读过：daily/2026-10-08 的两份足迹；未读：无

    ## 当前认识

    ### 配置解析修复

    - [关键] 截至 2026-10-10：空字符串修复只有 AI 汇报的本地 pytest 12 passed，尚未部署到 staging；核实：daily/2026-10-08/1000-config-parser-fix-a1b2.md
    - 空字符串保留为空、不回落默认值（原生转述，待确认）；核实：daily/2026-10-08/1500-config-review-k9m3.md

    ## 近期变化

    - 2026-10-08：修复空值处理并补回归测试 → [每日记忆](daily/2026-10-08.md)

    ## 冲突与未知

    - staging 部署时间：未定；需要：用户决定

    ## 待处理

    - [ ] deploy-to-staging：把空值修复部署到 staging；状态：进行中；依据：daily/2026-10-08/1000-config-parser-fix-a1b2.md；决定人：用户
    - [ ] confirm-rollback：确认 staging 出问题时的回滚步骤（助手建议回滚到 1.4.1，用户未表态）；状态：待确认；依据：daily/2026-10-08/1500-config-review-k9m3.md；决定人：用户

    ### 搁置

    - 无

    ## 记忆候选

    - cand-report-conclusion-first：汇报先给结论再给依据；状态：待核实；建议与缺口：只有原生转述，缺用户原话，且不清楚是否跨项目；来源：codex-memory#rollout_summaries/2026-10-08T02-00-00-a1b2-demo_config_parser_fix.md
    """

OLD_DAILY_1008 = f"""
    # 2026-10-08 · demo-api

    更新于：2026-10-10T21:00:00+08:00

    ## 有意义的变化

    - 修复配置解析：空字符串保留为空，不再回落默认值；AI 汇报本地 pytest 12 passed，本库未见实际输出。
    - 评审时助手建议 staging 出问题回滚到 1.4.1，用户未表态。

    ## 决定与约束

    - 空字符串保留为空、不回落默认值（原生转述，未读到用户原话）。

    ## 冲突与未知

    - staging 部署时间未定。

    ## 长期候选

    - 改解析逻辑后先清 .cache/config（单一原生转述，待确认）。

    ## 已吸收足迹

    - [1000-config-parser-fix-a1b2.md](2026-10-08/1000-config-parser-fix-a1b2.md)：意识、主题 config.parser-cache（待确认）；批次：{OLD_BATCH}
    - [1500-config-review-k9m3.md](2026-10-08/1500-config-review-k9m3.md)：意识待处理 confirm-rollback；批次：{OLD_BATCH}
    """


def _topic(review: str, status: str = "待确认", extra_source: str = "", updated: str = "2026-10-10T21:00:00+08:00") -> str:
    description = "改配置解析逻辑后先清 .cache/config 再跑测试，否则仍按旧逻辑失败"
    if status == "待确认":
        description += "（待确认）"
    return f"""
    ---
    name: config.parser-cache
    description: {description}
    type: 坑
    scope: project:demo-api
    status: {status}
    applies_to: demo-api 的 src/config/parser.py 修改后
    sources:
      - ../daily/2026-10-08/1000-config-parser-fix-a1b2.md｜原生转述｜5{extra_source}
    created: 2026-10-10T21:00:00+08:00
    updated: {updated}
    valid_from: 未知
    review: {review}
    ---

    改 demo-api 的配置解析逻辑后，先清理 .cache/config 再跑测试；否则测试仍按旧回落逻辑失败。

    **Why：** 回落逻辑会缓存（单一原生转述）。

    **How to apply：** 修改 parse_value 等解析代码后先执行清缓存，再运行 tests/test_parser.py。

    ## 演变

    - 2026-10-10：从 Codex 原生摘要建立，待确认。
    """


def _project_memory(description: str) -> str:
    return f"""
    # demo-api 主记忆

    范围：project:demo-api

    ## 做法与坑

    - {description} → [config.parser-cache](topics/config.parser-cache.md)
    """


def _old_batch() -> str:
    return f"""
    ---
    run_id: {OLD_BATCH}
    scope: project:demo-api
    status: completed
    started_at: 2026-10-10T20:50:00+08:00
    updated_at: 2026-10-10T21:05:00+08:00
    ---

    # 整理批次 · {OLD_BATCH}

    模式：手动。剩余范围：无；中断原因：无。

    ## 冻结输入

    - daily/2026-10-08/1000-config-parser-fix-a1b2.md
    - daily/2026-10-08/1500-config-review-k9m3.md

    ## 回读核对

    - 关键信息保全：通过
    - 已有条目损失：通过（新建）
    - 日期绝对化：通过

    ## 吸收登记

    - daily/2026-10-08.md 两项，已回读
    """


def _curate_base(base: Path, *, new_footprints: bool, review: str) -> None:
    _config(base)
    project = base / "memroot/projects/demo-api"
    _write(project / "daily/2026-10-08/1000-config-parser-fix-a1b2.md", FOOTPRINT_1000, base)
    _write(project / "daily/2026-10-08/1500-config-review-k9m3.md", FOOTPRINT_1500_REVIEW, base)
    _write(project / "daily/2026-10-08.md", OLD_DAILY_1008, base)
    _write(project / "AWARENESS.md", OLD_AWARENESS, base)
    _write(project / "topics/config.parser-cache.md", _topic(review), base)
    _write(project / "MEMORY.md", _project_memory("改配置解析逻辑后先清 .cache/config 再跑测试，否则仍按旧逻辑失败（待确认）"), base)
    _write(base / f"memroot/state/curation/{OLD_BATCH}.md", _old_batch(), base)
    if new_footprints:
        _write(project / "daily/2026-10-08/1630-cache-cleanup-verified-q4w8.md", FOOTPRINT_1630, base)
        _write(project / "daily/2026-10-09/1500-staging-deploy-c3d4.md", FOOTPRINT_DEPLOY, base)
        _write(base / "work/demo-api/test-output/2026-10-08-cache.txt", """
            # recorded 2026-10-08T16:20:00+08:00
            $ pytest tests/test_parser.py
            FAILED tests/test_parser.py::test_empty_string - AssertionError: '' != 'default'
            1 failed, 11 passed

            # recorded 2026-10-08T16:30:00+08:00
            $ make clean-cache && pytest tests/test_parser.py
            12 passed
            """, base)


def _pending_batch(base: Path) -> None:
    _write(base / f"memroot/state/history/demo-api/AWARENESS-2026-10-11-{PENDING_BATCH}.md", OLD_AWARENESS, base)
    extra = "\n      - project:demo-api/test-output/2026-10-08-cache.txt｜执行结果｜2"
    description = "改配置解析逻辑后先清 .cache/config 再跑测试，否则仍按旧逻辑失败"
    project = base / "memroot/projects/demo-api"
    _write(project / "topics/config.parser-cache.md",
           _topic("2027-01-10", status="有效", extra_source=extra, updated="2026-10-11T09:20:00+08:00"), base)
    _write(project / "MEMORY.md", _project_memory(description), base)
    _write(base / f"memroot/state/curation/{PENDING_BATCH}.md", f"""
        ---
        run_id: {PENDING_BATCH}
        scope: project:demo-api
        status: pending
        started_at: 2026-10-11T09:10:00+08:00
        updated_at: 2026-10-11T09:21:00+08:00
        ---

        # 整理批次 · {PENDING_BATCH}

        模式：手动。状态 pending → verified → completed；未完成不是活跃锁。
        剩余范围：无；中断原因：写完主题与主记忆后会话中断，意识和每日记忆尚未写。

        ## 冻结输入

        - daily/2026-10-08/1630-cache-cleanup-verified-q4w8.md
        - daily/2026-10-09/1500-staging-deploy-c3d4.md
        - 旧候选 cand-report-conclusion-first；到期复查 config.parser-cache

        ## 基线与预期输出

        - 意识基线：state/history/demo-api/AWARENESS-2026-10-11-{PENDING_BATCH}.md
        - 输出：topics/config.parser-cache.md（已保存：执行结果支持，有效，复查延至 2027-01-10）；MEMORY.md（已保存）；AWARENESS.md、daily/2026-10-08.md、daily/2026-10-09.md（未写）

        ## 旧内容的去向

        - 待写

        ## 回读核对

        - 关键信息保全：待核对
        - 已有条目损失：待核对
        - 日期绝对化：待核对
        - 来源、范围、状态与链接：待核对
        - 意识改写比例：待核对

        ## 吸收登记

        - 未完成
        """, base)


def build(case: str, base: Path) -> None:
    if case not in CASES:
        raise SystemExit(f"unknown case: {case}")
    if base.exists() and any(base.iterdir()):
        raise SystemExit(f"target is not empty: {base}")
    base.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "plugins/xmemory/skills", base / "skills")
    if case == "collect-gap":
        _collect_base(base)
    elif case == "collect-retry":
        raise SystemExit("collect-retry reuses a finished collect-gap directory: run `restore` on it")
    elif case == "curate-second-pass":
        _curate_base(base, new_footprints=True, review="2026-10-10")
    elif case == "curate-pending-resume":
        _curate_base(base, new_footprints=True, review="2026-10-10")
        _pending_batch(base)
    elif case == "curate-no-change":
        _curate_base(base, new_footprints=False, review="2026-12-31")
    snapshot(base)


def restore(base: Path) -> None:
    """Make the temporarily unavailable summary readable for the second collect round."""
    link = base / "fixtures/codex-memories/rollout_summaries" / RETRY
    if link.is_symlink():
        link.unlink()
    _retry_summary(base)
    snapshot(base)


def snapshot(base: Path) -> dict[str, str]:
    files = {}
    for path in sorted((base / "memroot").rglob("*")):
        if path.is_file():
            files[path.relative_to(base).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    (base / "snapshot.before.json").write_text(json.dumps(files, ensure_ascii=False, indent=1), encoding="utf-8")
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("case", choices=CASES)
    b.add_argument("dir", type=Path)
    r = sub.add_parser("restore")
    r.add_argument("dir", type=Path)
    c = sub.add_parser("check")
    c.add_argument("case", choices=CASES)
    c.add_argument("dir", type=Path)
    args = parser.parse_args()
    if args.command == "build":
        build(args.case, args.dir.absolute())
        return 0
    if args.command == "restore":
        restore(args.dir.absolute())
        return 0
    results = check(args.case, args.dir.absolute())
    print(json.dumps(results, ensure_ascii=False, indent=1))
    return 0 if all(item["ok"] for item in results) else 1


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _field(text: str, key: str) -> str:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(.*)$", text)
    return match.group(1).strip() if match else ""


def _table(text: str, must_have: str) -> list[dict[str, str]]:
    """Rows of the first Markdown table whose header contains ``must_have``."""
    lines = [line.strip() for line in text.splitlines()]
    for index, line in enumerate(lines):
        if line.startswith("|") and must_have in line:
            header = [cell.strip() for cell in line.strip("|").split("|")]
            rows = []
            for row in lines[index + 2:]:
                if not row.startswith("|"):
                    break
                cells = [cell.strip() for cell in row.strip("|").split("|")]
                rows.append(dict(zip(header, cells)))
            return rows
    return []


def _changes(base: Path) -> dict[str, list[str]]:
    before = json.loads(_text(base / "snapshot.before.json") or "{}")
    after = {path.relative_to(base).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in (base / "memroot").rglob("*") if path.is_file()}
    return {"added": sorted(set(after) - set(before)),
            "removed": sorted(set(before) - set(after)),
            "changed": sorted(p for p in set(before) & set(after) if before[p] != after[p])}


def _footprints(memroot: Path) -> list[Path]:
    return sorted(p for p in memroot.rglob("daily/*/*.md") if p.parent.name != "daily")


def check(case: str, base: Path) -> list[dict]:
    results: list[dict] = []

    def ok(name: str, passed: bool, detail: object = "") -> None:
        results.append({"check": name, "ok": bool(passed), "detail": detail})

    commands = [line for log in sorted(base.glob("step*.log"))
                for line in _text(log).splitlines() if line.startswith("/bin/") and " -lc " in line]
    outside = [c[:160] for c in commands if re.search(r"/Users/|(?<![\w/])~/|\$HOME", c)]
    ok("命令未触及用户主目录", not outside, outside)

    memroot = base / "memroot"
    project = memroot / "projects/demo-api"
    changes = _changes(base)
    footprints = _footprints(memroot)
    rel = [p.relative_to(memroot).as_posix() for p in footprints]

    if case in ("collect-gap", "collect-retry"):
        ok("撤回来源零足迹", not any("XM-WITHDRAWN-MARKER" in _text(p) or "0199aaaa-7777" in _text(p) for p in footprints))
        ok("正文与配置未被采集修改", not [p for p in changes["changed"] + changes["removed"]
                                    if "/state/runs/" not in p and not p.endswith("state/sources.md")],
           changes["changed"] + changes["removed"])
        ok("没有足迹落在采集日", not [p for p in rel if "/2026-10-10/" in p or "/2026-10-11/" in p], rel)
        ok("根 daily 没有项目足迹", not [p for p in rel if p.startswith("daily/")], rel)
        expected = {"10-08 解析修复": r"projects/demo-api/daily/2026-10-08/1000-",
                    "10-09 旧磁盘路径的部署": r"projects/demo-api/daily/2026-10-09/1500-",
                    "未知日期": r"projects/demo-api/daily/undated/0000-"}
        if case == "collect-retry":
            expected["10-09 回补的重试策略"] = r"projects/demo-api/daily/2026-10-09/1100-"
        for label, prefix in expected.items():
            hits = [p for p in rel if p.startswith(prefix)]
            ok(f"足迹落位：{label}", len(hits) == 1, hits)
        undated = [p for p in footprints if p.parent.name == "undated"]
        ok("undated 足迹 event_at 为未知", bool(undated) and all("未知" in _field(_text(p), "event_at") for p in undated))
        sources = [_field(_text(p), "source") for p in footprints]
        ok("同一来源不重复建足迹", len(sources) == len(set(sources)), sources)
        runs = sorted((memroot / "state/runs").glob("*.md"))
        ok("有采集清单", bool(runs), [p.name for p in runs])
        rows = [row for run in runs for row in _table(_text(run), "状态")]
        latest = {}
        for row in rows:
            for key in ("a1b2", "b7c8", "c5d6", "c3d4", "legacy_import_note"):
                if key in " ".join(row.values()):
                    latest[key] = row
        ok("清单覆盖 5 项", len(latest) == 5, sorted(latest))
        withdrawn = latest.get("b7c8", {})
        ok("撤回项标跳过且不需回补", withdrawn.get("状态") == "跳过" and withdrawn.get("需回补") == "否", withdrawn)
        retry = latest.get("c5d6", {})
        progress_rows = _table(_text(memroot / "state/sources.md"), "连续完成至")
        progress = next((r for r in progress_rows if "codex-memory" in r.get("来源", "")), {})
        position = progress.get("连续完成至", "")
        pending = progress.get("未结清单", "")
        if case == "collect-gap":
            ok("不可访问项需回补", retry.get("状态") in ("失败", "跳过") and retry.get("需回补") == "是", retry)
            ok("进度不越过缺口", bool(position) and not re.search(r"c3d4|c5d6|legacy|07-00-00|03-00-00", position), position)
            ok("未结清单保留本批", bool(pending) and pending != "无" and ".md" in pending, pending)
        else:
            ok("回补项已提取", retry.get("状态") == "已提取" and retry.get("需回补") == "否", retry)
            ok("进度推进到末项", bool(re.search(r"legacy|全部|末|5", position)), position)
            ok("未结清单已关闭", pending in ("无", "", "—", "-"), pending)
            ok("首轮足迹未被修改", not [p for p in changes["changed"] if "/daily/" in p], changes["changed"])
        return results

    batches = sorted((memroot / "state/curation").glob("*.md"))
    awareness = _text(project / "AWARENESS.md")
    day8 = _text(project / "daily/2026-10-08.md")
    day9 = _text(project / "daily/2026-10-09.md")
    if case == "curate-no-change":
        ok("零写入", not any(changes.values()), changes)
        last = _text(base / "step1.last.md")
        ok("回报本次无变化", "本次无变化" in last, last[-300:])
        return results

    ok("足迹未被修改", not [p for p in changes["changed"] + changes["removed"]
                         if re.search(r"/daily/\d{4}-\d{2}-\d{2}/", p)], changes["changed"])
    ok("没有重复主题", sorted(p.name for p in (project / "topics").glob("*.md")) == ["config.parser-cache.md"],
       sorted(p.name for p in (project / "topics").glob("*.md")))
    ok("未新建 personal 规则", not (memroot / "USER.md").exists() and not (memroot / "topics").exists())
    if case == "curate-pending-resume":
        ok("复用 pending 批次，不新建批次", [p.name for p in batches] == [f"{OLD_BATCH}.md", f"{PENDING_BATCH}.md"],
           [p.name for p in batches])
        batch_id = PENDING_BATCH
        history = sorted((memroot / "state/history/demo-api").glob("*.md"))
        ok("沿用原意识基线", [p.name for p in history] == [f"AWARENESS-2026-10-11-{PENDING_BATCH}.md"]
           and f"memroot/state/history/demo-api/AWARENESS-2026-10-11-{PENDING_BATCH}.md" not in changes["changed"],
           [p.name for p in history])
    else:
        new = [p for p in batches if p.stem != OLD_BATCH]
        ok("新建一份整理批次", len(new) == 1, [p.name for p in batches])
        batch_id = new[0].stem if new else "<missing>"
        history = sorted((memroot / "state/history/demo-api").glob("*.md"))
        old = textwrap.dedent(OLD_AWARENESS).lstrip("\n")
        ok("保存旧意识原样副本", any(_text(p) == old for p in history), [p.name for p in history])
    batch = _text(memroot / f"state/curation/{batch_id}.md")
    ok("批次 completed", _field(batch, "status") == "completed", _field(batch, "status"))
    ok("意识保留固定五节", all(h in awareness for h in ("## 当前认识", "## 近期变化", "## 冲突与未知", "## 待处理", "## 记忆候选")))
    for key in ("confirm-rollback", "deploy-to-staging", "fix-legacy-config"):
        ok(f"行动 {key} 有去向", key in awareness or key in batch)
    ok("旧候选 key 不丢失", "cand-report-conclusion-first" in awareness or "cand-report-conclusion-first" in batch)
    for name in ("1000-config-parser-fix-a1b2", "1500-config-review-k9m3"):
        line = next((l for l in day8.splitlines() if name in l and l.lstrip().startswith("-")), "")
        ok(f"旧吸收项保留：{name}", OLD_BATCH in line, line)
    ok("旧决定保留", "空字符串保留为空" in day8)
    for text, name, label in ((day8, "1630-cache-cleanup-verified-q4w8", "10-08 新增"),
                              (day9, "1500-staging-deploy-c3d4", "10-09")):
        line = next((l for l in text.splitlines() if name in l and l.lstrip().startswith("-")), "")
        ok(f"吸收登记带批次：{label}", batch_id in line, line)
    topic = _text(project / "topics/config.parser-cache.md")
    memory = _text(project / "MEMORY.md")
    description = _field(topic, "description")
    ok("主记忆要点等于主题 description", bool(description) and description in memory, description)
    ok("到期复查已处理", _field(topic, "review") != "2026-10-10", _field(topic, "review"))
    return results


if __name__ == "__main__":
    raise SystemExit(main())
