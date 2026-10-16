"""会话读取契约的实现；W1 只搬迁，不改变解析行为。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys

from .common import (CLIENTS, MAX_LINE, TEXT_TYPES, ReaderError, columns, database,
                     epoch, fingerprint, iso, json_rows, jsonl_stem, parse_iso,
                     redact, scrub, tool_text, visible_text, zstd_rows, is_notice)
from . import runtime


def defaults(client):
    home = Path.home()
    return {
        "codex": [home / ".codex/sessions", home / ".codex/archived_sessions"],
        "claude": [home / ".claude/projects"],
        "workbuddy": [home / ".workbuddy/projects"],
        "zcode": [home / ".zcode/cli/db/db.sqlite"],
        "qodercn": [home / ".qoder-cn/projects",
                     home / "Library/Application Support/com.qodercn.app.stable/main.sqlite"],
    }[client]


def summary(client, variant, sid, path, **kw):
    return dict(client=client, variant=variant, session_id=str(sid),
                session_ref=f"{client}:{variant}:{sid}", source=str(path), **kw)


def content_supported(content, ignored_types=()):
    if isinstance(content, str):
        return True
    if not isinstance(content, list):
        return False
    for block in content:
        if not isinstance(block, dict):
            return False
        typ = block.get("type")
        if not isinstance(typ, str):
            return False
        if typ in TEXT_TYPES:
            if not isinstance(block.get("text"), str):
                return False
        elif typ not in {"tool_use", "tool_result", "image", "input_image", "file", "document",
                         "thinking", "reasoning", "redacted_thinking"} and typ not in ignored_types:
            return False
    return True


def json_record_kind(client, row):
    """先判断正文形状，再应用查询条件；未知正文不能伪装为元数据。"""
    typ = row.get("type")
    if not isinstance(typ, str):
        return "unsupported"
    if client == "codex":
        # token_usage_record/world_state/inter_agent_communication_metadata 实测为
        # 0.16x 的遥测与状态信封（timestamp/ordinal/type/payload），不含对话正文。
        if typ in {"session_meta", "turn_context", "event_msg", "token_usage_record",
                   "world_state", "inter_agent_communication_metadata"}:
            return "metadata"
        if typ in {"response_item", "compacted"}:
            p = row.get("payload")
            if not isinstance(p, dict):
                return "unsupported"
            if typ == "compacted":
                return "body" if isinstance(p.get("message"), str) else "unsupported"
            kind = p.get("type")
            if not isinstance(kind, str):
                return "unsupported"
            if kind == "reasoning" or (kind == "message" and
                    (p.get("channel") == "analysis" or p.get("role") in ("system", "developer"))):
                return "metadata"
            if kind == "message":
                return "body" if p.get("role") in ("user", "assistant") and content_supported(p.get("content")) else "unsupported"
            if kind == "agent_message":
                valid = content_supported(p.get("content"), {"encrypted_content"}) and all(
                    p.get(key) is None or isinstance(p[key], str) for key in ("id", "author", "recipient"))
                return "body" if valid else "unsupported"
            if kind == "web_search_call":
                action = p.get("action")
                valid = (action is None or (isinstance(action, dict) and
                         (action.get("query") is None or isinstance(action["query"], str))))
                valid = valid and all(p.get(key) is None or isinstance(p[key], str) for key in ("id", "status"))
                return "body" if valid else "unsupported"
            if kind in {"function_call", "custom_tool_call", "function_call_output", "custom_tool_call_output"}:
                return "body"
            return "unsupported"
    elif client in {"claude", "qodercn"}:
        if row.get("isMeta") or typ in {"system", "progress", "thinking", "reasoning", "redacted_thinking"}:
            return "metadata"
        if typ in {"user", "assistant"}:
            message = row.get("message")
            return "body" if isinstance(message, dict) and content_supported(message.get("content")) else "unsupported"
    elif client == "workbuddy":
        if typ in {"reasoning", "thinking", "redacted_thinking"}:
            return "metadata"
        if typ == "message":
            if row.get("role") in ("system", "developer"):
                return "metadata"
            return "body" if row.get("role") in ("user", "assistant") and content_supported(row.get("content")) else "unsupported"
        if typ in {"function_call", "function_call_result"}:
            return "body"
    if typ in {"ai-title", "custom-title", "queue-operation", "file-history-snapshot"}:
        return "metadata"
    if typ in {"response_item", "compacted", "user", "assistant", "message", "function_call",
               "custom_tool_call", "function_call_result", "function_call_output"} or any(
            key in row for key in ("message", "content", "text", "output", "arguments", "payload")):
        return "unsupported"
    return "metadata"


def native_session_id(client, row):
    if client == "codex" and row.get("type") == "session_meta":
        payload = row.get("payload")
        return (payload.get("id") or payload.get("session_id")) if isinstance(payload, dict) else None
    return row.get("sessionId")


def json_project(client, row):
    """只取原生 cwd；Codex 的轮次上下文位于 payload。"""
    value = row.get("cwd")
    if client == "codex" and row.get("type") in ("session_meta", "turn_context"):
        payload = row.get("payload")
        if not value and isinstance(payload, dict):
            value = payload.get("cwd")
    return value if isinstance(value, str) and value else None


def json_summary(client, path, warnings):
    if client == "zcode":
        raise ReaderError("unsupported_source: ZCode 使用已核实的 SQLite 对话表")
    stem = jsonl_stem(path)
    match = re.search(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$", stem)
    sid = match[0] if match else stem
    result = summary(client, "jsonl", sid, path, title=None, title_origin=None,
                     project=None, projects=[], parent_session_id=None, created_at=None, updated_at=None,
                     archived="archived_sessions" in path.parts, id_origin="filename")
    if client == "codex":
        result.update(thread_source=None, agent_path=None)
    recognized, identities = False, set()
    parse_warnings = []
    counts = {"body": 0, "metadata": 0, "unsupported": 0}
    for offset, row in json_rows(path, parse_warnings):
        typ = row.get("type")
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        native = native_session_id(client, row)
        if native:
            identities.add(str(native))
        kind = json_record_kind(client, row)
        counts[kind] += 1
        if kind == "unsupported":
            warnings.append(f"unsupported_body: {path}#byte:{offset}; 不符合 {client} 正文格式")
        if client == "codex" and typ == "session_meta":
            recognized = True
            result["session_id"] = str(payload.get("id") or payload.get("session_id") or sid)
            result["created_at"] = iso(payload.get("timestamp") or row.get("timestamp"))
            result["id_origin"] = "session_meta"
            for key, source_key in (("thread_source", "thread_source"), ("parent_session_id", "parent_thread_id"),
                                    ("agent_path", "agent_path")):
                value = payload.get(source_key)
                if value is not None and not isinstance(value, str):
                    parse_warnings.append(f"invalid_shape: {path}#byte:{offset}/{source_key}; 预期字符串或 null")
                    value = None
                result[key] = value
        elif client != "codex" and row.get("sessionId"):
            recognized = True
            result["session_id"] = str(row["sessionId"])
            result["id_origin"] = "sessionId"
        project = json_project(client, row)
        if project:
            result["project"] = project
            if project not in result["projects"]:
                result["projects"].append(project)
        if row.get("agentId"):
            result["agent_id"] = row["agentId"]
        if typ in ("ai-title", "custom-title"):
            title = row.get("aiTitle") or row.get("customTitle") or row.get("title")
            if title:
                result.update(title=title, title_origin=typ)
        stamp = row.get("timestamp")
        if stamp:
            if result["created_at"] is None or epoch(stamp) < epoch(result["created_at"]):
                result["created_at"] = iso(stamp)
            if epoch(stamp) >= epoch(result["updated_at"]):
                result["updated_at"] = iso(stamp)
    warnings.extend(parse_warnings)
    if len(identities) > 1:
        raise ReaderError("mixed_session_ids: 文件包含多个原生会话身份；未适配的继承或恢复组合不统一署名")
    if not recognized:
        raise ReaderError("unsupported_or_incomplete_jsonl_metadata")
    if identities:
        result["session_id"] = next(iter(identities))
    result["metadata_complete"] = not parse_warnings
    result["metadata_scan"] = "full_stream"
    result["body_records"] = counts["body"]
    result["body_format"] = ("partial" if counts["body"] else "unsupported") if counts["unsupported"] else (
        "supported" if counts["body"] else "metadata_only")
    result["updated_at"] = result["updated_at"] or iso(path.stat().st_mtime)
    result["session_ref"] = f'{client}:jsonl:{result["session_id"]}'
    if "subagents" in path.parts:
        result["variant"] = "subagent"
        if client != "codex":
            result["parent_session_id"] = result["session_id"]
        result["session_ref"] = f'{client}:subagent:{result["session_id"]}:{path.stem}'
    return result


def sqlite_summaries(client, path, cap, warnings):
    with database(path) as con:
        if client == "zcode":
            names = columns(con, "session", ["id", "title", "directory", "time_created", "time_updated"])
            rows = con.execute('SELECT * FROM session ORDER BY time_updated DESC, id LIMIT ?', (cap + 1,)).fetchall()
            result = [summary(client, "sqlite", r["id"], path, title=r["title"], title_origin="native",
                              project=r["directory"], created_at=iso(r["time_created"]),
                              updated_at=iso(r["time_updated"]),
                              parent_session_id=r["parent_id"] if "parent_id" in names else None,
                              archived=bool(r["time_archived"]) if "time_archived" in names else None)
                      for r in rows]
        elif client == "qodercn":
            names = columns(con, "chat_sessions", ["session_id", "title", "cwd", "created_at", "updated_at"])
            where = "WHERE deleted_at IS NULL" if "deleted_at" in names else ""
            rows = con.execute(f'SELECT * FROM chat_sessions {where} ORDER BY updated_at DESC, session_id LIMIT ?', (cap + 1,)).fetchall()
            result = [summary(client, "desktop", r["session_id"], path, title=r["title"], title_origin="native",
                              project=r["cwd"], created_at=iso(r["created_at"]), updated_at=iso(r["updated_at"]),
                              parent_session_id=r["owner_session_id"] if "owner_session_id" in names else None,
                              origin_session_id=r["origin_session_id"] if "origin_session_id" in names else None,
                              archived=bool(r["archived"]) if "archived" in names else None)
                      for r in rows]
        else:
            raise ReaderError("unsupported_source: 此技能不读取该 SQLite 来源")
    if len(result) > cap:
        warnings.append("session_scan_limit: SQLite 仍有未检查的会话；缩小来源或增大 --max-sessions")
    return result[:cap]


def project_matches(project, query):
    if not query:
        return True
    wanted = str(Path(query).expanduser()).rstrip("/\\")
    actual = str(project or "").rstrip("/\\")
    return actual == wanted or actual.startswith(wanted + os.sep)


def match_start(text, folded_query):
    """casefold 可能扩展字符（如 ß→ss），把命中位置映射回原文。"""
    folded = text.casefold()
    pos = folded.find(folded_query)
    if pos < 0 or len(folded) == len(text):
        return pos
    offset = 0
    for i, char in enumerate(text):
        offset += len(char.casefold())
        if offset > pos:
            return i
    return -1


def catalogue(client, args, warnings, source_warnings=None, compressed_twins=None):
    roots = [Path(p).expanduser().resolve() for p in args.root] if args.root else defaults(client)
    files, dbs, compressed = set(), set(), set()
    for root in roots:
        if not root.exists():
            warnings.append(f"source_unavailable: {root}")
            continue
        if root.is_file():
            name = root.name.lower()
            if name.endswith(".jsonl"):
                files.add(root)
            elif name.endswith(".jsonl.zst"):
                compressed.add(root)
            elif root.suffix in {".sqlite", ".db"}:
                dbs.add(root)
            else:
                warnings.append(f"unsupported_source: {root}")
        else:
            known_db = {"zcode": "db.sqlite", "qodercn": "main.sqlite"}.get(client)
            if known_db and (root / known_db).is_file():
                dbs.add(root / known_db)
            for p in root.rglob("*.jsonl"):
                if p.is_file() and not p.is_symlink() and (args.include_subagents or "subagents" not in p.parts):
                    files.add(p)
            # Codex local_thread_store_compression 会把冷 rollout 改写为 .jsonl.zst；
            # 发现即纳入或报告，不在文件匹配阶段静默漏掉。
            for p in root.rglob("*.jsonl.zst"):
                if p.is_file() and not p.is_symlink() and (args.include_subagents or "subagents" not in p.parts):
                    compressed.add(p)
    if client == "codex":
        for packed in sorted(compressed):
            plain = packed.with_suffix("")
            if plain in files:
                compressed.remove(packed)
                if compressed_twins is not None:
                    compressed_twins[str(plain)] = str(packed)
    if compressed:
        if runtime.backend():
            files.update(compressed)
        else:
            warnings.append(f"zstd_missing: {len(compressed)} 个 .jsonl.zst 会话未读；" + runtime.REGISTRY['zstd']['missing'])
    # 文件名只决定优先检查顺序，不能取代原生元数据或排除别名文件。
    sid = args.session.split(":")[-1] if args.session else None

    def name_hint(p):
        stem = jsonl_stem(p)
        return bool(sid and (stem == sid or stem.endswith("-" + sid)))

    ordered = sorted(files, key=lambda p: (name_hint(p), p.stat().st_mtime_ns, str(p)), reverse=True)
    if len(ordered) > args.max_sessions:
        warnings.append("session_scan_limit: JSONL 仍有未检查的会话；缩小 --root 或增大 --max-sessions")
    result = []
    for p in ordered[:args.max_sessions]:
        local_warnings = []
        try:
            result.append(json_summary(client, p, local_warnings))
        except (OSError, ValueError, ReaderError) as exc:
            # 无法取得会话元数据的错误仍是全局缺口，不能当作筛选范围外而隐藏。
            warnings.extend(local_warnings)
            warnings.append(f"source_error: {p}: {exc}")
        else:
            if source_warnings is None:
                warnings.extend(local_warnings)
            else:
                source_warnings[str(p)] = local_warnings
    for p in sorted(dbs):
        try:
            if args.session:
                result.extend(sqlite_one(client, p, args.session))
            else:
                result.extend(sqlite_summaries(client, p, args.max_sessions, warnings))
        except (sqlite3.Error, ReaderError) as exc:
            warnings.append(f"source_error: {p}: {exc}")
    # Codex 原生索引仅补充标题，不依赖它判断正文存在或读取原件之外的路径。
    if client == "codex" and not args.root:
        indexes = sorted((Path.home() / ".codex").glob("state_*.sqlite"), reverse=True)
        if indexes:
            try:
                with database(indexes[0]) as con:
                    columns(con, "threads", ["id", "title"])
                    for s in result:
                        row = con.execute("SELECT title FROM threads WHERE id=?", (s["session_id"],)).fetchone()
                        if row:
                            s.update(title=row[0], title_origin="native_index")
            except (sqlite3.Error, ReaderError):
                warnings.append("title_index_unavailable")
    result = [s for s in result if any(project_matches(project, args.project)
                                     for project in (s.get("projects") or [s.get("project")]))
              and (args.action != "list" or not s.get("metadata_complete", True) or (
                  (not args.since or not s.get("updated_at") or epoch(s["updated_at"]) >= args.since)
                  and (not args.until or not s.get("created_at") or epoch(s["created_at"]) <= args.until)))]
    return sorted(result, key=lambda s: (epoch(s.get("updated_at")), s["session_ref"], s["source"]), reverse=True)


def sqlite_one(client, path, requested):
    """已知 ID 直接查询，不能在最近 N 个会话中猜测不存在。"""
    sid = requested.split(":")[-1]
    with database(path) as con:
        if client == "zcode":
            columns(con, "session", ["id", "title", "directory", "time_created", "time_updated"])
            r = con.execute("SELECT * FROM session WHERE id=?", (sid,)).fetchone()
            return [] if r is None else [summary(client, "sqlite", sid, path, title=r["title"],
                    project=r["directory"], created_at=iso(r["time_created"]), updated_at=iso(r["time_updated"]))]
        if client == "qodercn":
            names = columns(con, "chat_sessions", ["session_id", "title", "cwd", "created_at", "updated_at"])
            r = con.execute("SELECT * FROM chat_sessions WHERE session_id=?", (sid,)).fetchone()
            if r is None or ("deleted_at" in names and r["deleted_at"] is not None):
                return []
            return [summary(client, "desktop", sid, path, title=r["title"], project=r["cwd"],
                            created_at=iso(r["created_at"]), updated_at=iso(r["updated_at"]))]
        raise ReaderError("unsupported_source")


def event(s, locator, role, text, *, kind="message", native_id=None, parent_id=None,
          record_id=None, call_id=None, name=None, stamp=None, turn_id=None, native_session_id=None,
          project=None):
    # 在截断和计算偏移之前遮蔽完整正文及元数据，切片后不再改变文本长度。
    result = scrub(dict(session_ref=s["session_ref"], session_id=s["session_id"],
                native_session_id=native_session_id, project=project,
                message_id=native_id, record_id=record_id, parent_id=parent_id, turn_id=turn_id,
                role=role, kind=kind, timestamp=iso(stamp), call_id=call_id, tool_name=name,
                source_ref=f'{s["source"]}#{locator}',
                record_ref=f'{s["session_ref"]}@{locator}'))
    if s["client"] == "codex":
        result.update(scrub({key: s.get(key) for key in ("thread_source", "parent_session_id", "agent_path")}))
    # 工具内容已按结构遮蔽并序列化，不能再用文本规则处理其 JSON 转义。
    result["text"] = text if kind in {"tool_call", "tool_result"} else redact(text)
    return result


def blocks(s, content, locator, base, include_tools, warnings):
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]
    if not isinstance(content, list):
        return
    for i, b in enumerate(content):
        if not isinstance(b, dict):
            continue
        typ = b.get("type")
        loc = f"{locator}/block:{i}"
        if not isinstance(typ, str):
            continue
        if typ in TEXT_TYPES:
            if not isinstance(b.get("text"), str):
                continue
            text = visible_text(b)
            if text:
                kind = "summary" if text.startswith("This session is being continued") else "message"
                yield event(s, loc, text=text, kind=kind, **base)
        elif include_tools and typ == "tool_use":
            if not valid_id(b, "id", f'{s["source"]}#{loc}', warnings):
                continue
            yield event(s, loc, text=tool_text(b.get("input", {})), kind="tool_call",
                        call_id=b.get("id"), name=b.get("name"), **base)
        elif include_tools and typ == "tool_result":
            if not valid_id(b, "tool_use_id", f'{s["source"]}#{loc}', warnings):
                continue
            values = dict(base, role="tool")
            yield event(s, loc, text=tool_text(b.get("content", "")), kind="tool_result",
                        call_id=b.get("tool_use_id"), **values)
        elif typ in {"image", "input_image", "file", "document"}:
            yield event(s, loc, text="[附件：本读取器未展开二进制内容]", kind="attachment", **base)


def json_events(s, warnings, include_tools):
    context_project = None
    for offset, o in json_rows(Path(s["source"]), warnings):
        typ = o.get("type")
        p = o.get("payload") if isinstance(o.get("payload"), dict) else {}
        loc = f"byte:{offset}"
        if not isinstance(typ, str):
            continue
        native = native_session_id(s["client"], o)
        if native and str(native) != s["session_id"]:
            warnings.append(f"session_identity_changed: {s['source']}#{loc}; 停止读取该来源")
            return
        project = json_project(s["client"], o)
        if s["client"] == "codex":
            if project:
                context_project = project
            # event_msg 是重复投影；只读 response_item，避免一条回复显示两次。
            if typ == "compacted":
                text = p.get("message")
                if isinstance(text, str):
                    yield event(s, loc, "context", text, kind="summary", stamp=o.get("timestamp"), native_session_id=native, project=context_project)
            if typ != "response_item":
                continue
            kind, role = p.get("type"), p.get("role")
            if not isinstance(kind, str):
                continue
            base = dict(role=role, native_id=p.get("id"), stamp=o.get("timestamp"), native_session_id=native, project=context_project)
            if kind == "message" and role in ("user", "assistant") and p.get("channel") != "analysis":
                yield from blocks(s, p.get("content"), loc, base, include_tools, warnings)
            elif kind in {"agent_message", "web_search_call"}:
                if json_record_kind("codex", o) != "body":
                    warnings.append(f"unsupported_body: {s['source']}#{loc}; 不符合 codex 正文格式")
                    continue
                if not include_tools:
                    continue
                if kind == "agent_message":
                    # 实际信封可同时保存 input_text 与 encrypted_content；只取可见文本。
                    text = visible_text(p["content"])
                    if not text:
                        continue
                    item = event(s, loc, "assistant", text, kind="agent_message",
                                 native_id=p.get("id"), record_id=p.get("id"), stamp=o.get("timestamp"),
                                 native_session_id=native, project=context_project)
                    item.update(scrub({key: p.get(key) for key in ("author", "recipient")}))
                else:
                    item = event(s, loc, "assistant", redact((p.get("action") or {}).get("query") or ""),
                                 kind="tool_call", name="web_search", native_id=p.get("id"),
                                 record_id=p.get("id"), stamp=o.get("timestamp"),
                                 native_session_id=native, project=context_project)
                    item["status"] = scrub(p.get("status"))
                yield item
            elif include_tools and kind in {"function_call", "custom_tool_call"}:
                if not valid_id(p, "call_id", f'{s["source"]}#{loc}', warnings):
                    continue
                yield event(s, loc, "assistant", tool_text(p.get("arguments", p.get("input", ""))),
                            kind="tool_call", native_id=p.get("id"), call_id=p.get("call_id"),
                            name=p.get("name"), stamp=o.get("timestamp"), native_session_id=native, project=context_project)
            elif include_tools and kind in {"function_call_output", "custom_tool_call_output"}:
                if not valid_id(p, "call_id", f'{s["source"]}#{loc}', warnings):
                    continue
                yield event(s, loc, "tool", tool_text(p.get("output", "")), kind="tool_result",
                            native_id=p.get("id"), call_id=p.get("call_id"), stamp=o.get("timestamp"), native_session_id=native, project=context_project)
        elif s["client"] in {"claude", "qodercn"}:
            if typ not in {"user", "assistant"} or o.get("isMeta"):
                continue
            m = o.get("message", {})
            if not isinstance(m, dict):
                warnings.append(f"unsupported_message_shape: {loc}")
                continue
            # uuid 进入公共去重键的 record_id；异常时跳过整条记录，与 SQLite 消息级 ID 的处理一致。
            if not valid_id(o, "uuid", f'{s["source"]}#{loc}', warnings):
                continue
            yield from blocks(s, m.get("content"), loc,
                              dict(role=typ, native_id=m.get("id") or o.get("uuid"),
                                   record_id=o.get("uuid"), parent_id=o.get("parentUuid"),
                                   stamp=o.get("timestamp"), native_session_id=native, project=project), include_tools, warnings)
        elif s["client"] == "workbuddy":
            base = dict(native_id=o.get("id"), parent_id=o.get("parentId"), stamp=o.get("timestamp"), native_session_id=native, project=project)
            if typ == "message" and o.get("role") in ("user", "assistant"):
                yield from blocks(s, o.get("content"), loc, dict(base, role=o["role"]), include_tools, warnings)
            elif include_tools and typ in {"function_call", "function_call_result"}:
                if not valid_id(o, "callId", f'{s["source"]}#{loc}', warnings):
                    continue
                call = typ == "function_call"
                yield event(s, loc, "assistant" if call else "tool",
                            tool_text(o.get("arguments" if call else "output", "")),
                            kind="tool_call" if call else "tool_result", call_id=o.get("callId"),
                            name=o.get("name"), **base)


def json_object(raw, locator, warnings):
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        warnings.append(f"invalid_json: {locator}")
        return None
    if not isinstance(value, dict):
        warnings.append(f"invalid_object: {locator}; 预期 JSON 对象")
        return None
    return value


def nested_value(value, key, expected, default, locator, warnings, required=False):
    item = value.get(key)
    if item is None:
        if required:
            warnings.append(f"invalid_shape: {locator}/{key}; 缺少 {expected.__name__}")
        return default
    if not isinstance(item, expected):
        warnings.append(f"invalid_shape: {locator}/{key}; 预期 {expected.__name__}")
        return default
    return item


def valid_id(value, key, locator, warnings):
    # 沿用缺失 ID 为 null 的契约；类型错误不能转成字符串冒充原生 ID。
    item = value.get(key)
    if item is None or isinstance(item, str):
        return True
    warnings.append(f"invalid_id: {locator}/{key}; 预期字符串或 null，跳过对应记录或内容块")
    return False


def qoder_tool_events(s, tool, locator, index, base, warnings):
    if not valid_id(tool, "id", f"{s['source']}#{locator}/tool:{index}", warnings):
        return
    locator += f"/tool:{tool.get('id') or index}"
    yield event(s, locator + "/call", "assistant", tool_text(tool.get("input", {})),
                kind="tool_call", call_id=tool.get("id"), name=tool.get("name"), **base)
    if "response" in tool:
        yield event(s, locator + "/result", "tool", tool_text(tool["response"]),
                    kind="tool_result", call_id=tool.get("id"), name=tool.get("name"), **base)


def sqlite_events(s, warnings, include_tools):
    with database(Path(s["source"])) as con:
        sid = s["session_id"]
        if s["client"] == "zcode":
            mc = columns(con, "message", ["id", "session_id", "data", "time_created"])
            pc = columns(con, "part", ["id", "message_id", "session_id", "data", "time_created"])
            order = 'COALESCE(sequence, time_created), time_created, id' if "sequence" in mc else 'time_created, id'
            po = 'COALESCE(sequence, time_created), time_created, id' if "sequence" in pc else 'time_created, id'
            for row in con.execute(f'SELECT * FROM message WHERE session_id=? ORDER BY {order}', (sid,)):
                message_loc = f'message:{row["id"]}'
                source_loc = f'{s["source"]}#{message_loc}'
                m = json_object(row["data"], source_loc, warnings)
                if m is None:
                    continue
                role = m.get("role")
                if not isinstance(role, str):
                    warnings.append(f"invalid_shape: {source_loc}/role; 预期字符串")
                    continue
                semantics = nested_value(m, "semantics", dict, None, source_loc, warnings)
                if m.get("semantics") is not None and semantics is None:
                    continue
                if role not in {"user", "assistant"} or (semantics or {}).get("uiVisibility") == "hidden":
                    continue
                if not valid_id(m, "parentID", source_loc, warnings):
                    continue
                for part in con.execute(f'SELECT * FROM part WHERE session_id=? AND message_id=? ORDER BY {po}', (sid, row["id"])):
                    loc = f'{message_loc}/part:{part["id"]}'
                    source_part = f'{s["source"]}#{loc}'
                    b = json_object(part["data"], source_part, warnings)
                    if b is None:
                        continue
                    base = dict(native_id=row["id"], record_id=part["id"], parent_id=m.get("parentID"),
                                stamp=row["time_created"], native_session_id=sid)
                    if b.get("type") == "text" and not b.get("synthetic") and not b.get("ignored"):
                        text = nested_value(b, "text", str, None, source_part, warnings, required=True)
                        if text is not None:
                            yield event(s, loc, role, text, **base)
                    elif include_tools and b.get("type") == "tool":
                        if not valid_id(b, "callID", source_part, warnings):
                            continue
                        state = nested_value(b, "state", dict, None, source_part, warnings, required=True)
                        if state is None:
                            continue
                        yield event(s, loc + "/call", "assistant", tool_text(state.get("input", {})),
                                    kind="tool_call", call_id=b.get("callID"), name=b.get("tool"), **base)
                        if "output" in state:
                            yield event(s, loc + "/result", "tool", tool_text(state["output"]),
                                        kind="tool_result", call_id=b.get("callID"), name=b.get("tool"), **base)
                    # step-start/step-finish/timeline/compaction 是 ZCode 的生命周期与
                    # 遥测事件（token 计数、模型切换分隔、压缩操作记录）；压缩摘要本体
                    # 存于独立 message（summaryMessageId 所指），不由 compaction part 携带。
                    elif b.get("type") not in ("text", "tool", "reasoning", "thinking", "redacted_thinking",
                                               "image", "file", "document", "step-start", "step-finish",
                                               "timeline", "compaction"):
                        warnings.append(f"unsupported_body: {source_part}; 未适配的内容块")
        elif s["client"] == "qodercn":
            columns(con, "chat_session_messages", ["session_id", "message_id", "sequence", "payload_json", "created_at"])
            for row in con.execute('SELECT * FROM chat_session_messages WHERE session_id=? ORDER BY sequence, message_id', (sid,)):
                loc = f'message:{row["message_id"]}'
                source_loc = f'{s["source"]}#{loc}'
                m = json_object(row["payload_json"], source_loc, warnings)
                if m is None:
                    continue
                role = m.get("role")
                if not isinstance(role, str):
                    warnings.append(f"invalid_shape: {source_loc}/role; 预期字符串")
                    continue
                if role not in {"user", "assistant"}:
                    continue
                if not valid_id(m, "turnId", source_loc, warnings):
                    continue
                base = dict(native_id=row["message_id"], turn_id=m.get("turnId"),
                            stamp=m.get("timestamp") or row["created_at"], native_session_id=sid)
                # parts 与 text/tools 是双份投影，优先读取 parts，避免重复。
                parts = nested_value(m, "parts", list, [], source_loc, warnings)
                has_text = any(isinstance(b, dict) and b.get("type") == "text" for b in parts)
                has_tools = any(isinstance(b, dict) and b.get("type") == "tool" for b in parts)
                if not has_text:
                    text = nested_value(m, "text", str, None, source_loc, warnings)
                    if text:
                        yield event(s, loc, role, text, **base)
                for i, b in enumerate(parts):
                    if not isinstance(b, dict):
                        warnings.append(f"invalid_shape: {source_loc}/part:{i}; 预期对象")
                        continue
                    if not valid_id(b, "id", f"{source_loc}/part:{i}", warnings):
                        continue
                    part_loc = loc + f"/part:{b.get('id') or i}"
                    source_part = f'{s["source"]}#{part_loc}'
                    if b.get("type") == "text":
                        text = nested_value(b, "text", str, None, source_part, warnings, required=True)
                        if text is not None:
                            yield event(s, part_loc, role, text, **base)
                    elif b.get("type") == "tool":
                        tool = nested_value(b, "tool", dict, None, source_part, warnings, required=True)
                        if tool is not None and include_tools:
                            yield from qoder_tool_events(s, tool, part_loc, i, base, warnings)
                    elif b.get("type") not in ("reasoning", "thinking", "redacted_thinking", "image", "file", "document"):
                        warnings.append(f"unsupported_body: {source_part}; 未适配的内容块")
                if not has_tools:
                    tools = nested_value(m, "tools", list, [], source_loc, warnings)
                    for i, tool in enumerate(tools):
                        if not isinstance(tool, dict):
                            warnings.append(f"invalid_shape: {source_loc}/tool:{i}; 预期对象")
                        elif include_tools:
                            yield from qoder_tool_events(s, tool, loc, i, base, warnings)


def read_events(s, warnings, include_tools):
    seen = set()
    events = sqlite_events if s["variant"] in {"sqlite", "desktop"} else json_events
    for e in events(s, warnings, include_tools):
        # 只去掉相同原生记录的完全相同重复块，不把同文不同消息合并。
        block = e["record_ref"].rsplit("/block:", 1)[-1] if "/block:" in e["record_ref"] else None
        key = (e["record_id"], e["kind"], e["call_id"], block, hashlib.sha256(e["text"].encode()).digest())
        if e["record_id"] and key in seen:
            continue
        seen.add(key)
        yield e


UI_REFERENCE = re.compile(r"(?i)^[\w.-]+\.(?:zcode|claude|codex|qodercn|workbuddy)-session$")
UUID_PLAIN = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")


def normalize_session(client, value):
    """客户端界面复制的会话引用是 <工作区>/<ID>.<客户端>-session 虚拟路径，磁盘上不存在；
    按文件名确定性剥壳（客户端必须匹配），不做模糊匹配。ZCode 原生 ID 带 sess_ 前缀，
    裸 UUID 同样确定性补全。"""
    if not value or (":" in value and not re.match(r"^[A-Za-z]:[\\/]", value)):
        return value
    name = str(value).replace("\\", "/").rsplit("/", 1)[-1]
    if UI_REFERENCE.fullmatch(name):
        stem, _, suffix = name.rpartition(".")
        client_name = suffix[:-len("-session")].lower()
        if client_name == client:
            value = stem
    if client == "zcode" and UUID_PLAIN.fullmatch(value):
        return "sess_" + value
    return value


def run(client, args):
    args.session = normalize_session(client, args.session)
    warnings = []
    source_warnings = {} if args.action == "list" else None
    compressed_twins = {}
    sessions = catalogue(client, args, warnings, source_warnings, compressed_twins)
    if args.session:
        sessions = [s for s in sessions if args.session in {s["session_id"], s["session_ref"]}]
        if not sessions:
            raise ReaderError("session_not_found_in_checked_sources: 未找到可读取的单会话来源；用 --root 指定原件并检查 warnings", warnings)
        if len(sessions) != 1:
            raise ReaderError("ambiguous_session: 同一 ID 有多个来源；用 --root 与完整 session_ref 选择，不能自动合并迁移副本")
    if args.action == "read" and not args.session:
        raise ReaderError("read_requires_session: 先 list，再提供 --session")
    if args.action == "search" and not args.query:
        raise ReaderError("search_requires_query")
    query = (args.query or "").casefold()
    data = []
    has_more = False
    matched = 0
    snapshots = {}
    examined = eligible = completed_sessions = 0
    if args.action == "list":
        candidates = [s for s in sessions if not query or query in str(s.get("title") or "").casefold() or query in s["session_id"].casefold()]
        data = candidates[args.offset:args.offset + args.limit]
        has_more = len(candidates) > args.offset + args.limit
        returned_sources = {s["source"] for s in data}
        warnings_outside_filter = sum(sum(not is_notice(w) for w in items) for source, items in source_warnings.items()
                                      if source not in returned_sources)
        for source in sorted(returned_sources):
            warnings.extend(source_warnings.get(source, []))
            if source in compressed_twins:
                warnings.append(f"compressed_twin: {compressed_twins[source]}; 优先读取 {source}")
    else:
        for s in sessions:
            path = Path(s["source"])
            if s['source'] in compressed_twins:
                warnings.append(f"compressed_twin: {compressed_twins[s['source']]}; 优先读取 {s['source']}")
            fp = fingerprint(path)
            snapshots[s["session_ref"]] = fp
            if args.snapshot and (s["variant"] in {"sqlite", "desktop"} or args.snapshot != fp):
                raise ReaderError("snapshot_changed_or_unsupported: JSONL 已变化，或 SQLite 不支持跨请求冻结；重新定位后读取")
            # 先解析形状，再按工具、角色、时间、查询条件筛选，不能隐藏解析缺口。
            for e in read_events(s, warnings, True):
                examined += 1
                if not args.include_tools and e["kind"] in {"tool_call", "tool_result", "agent_message"}:
                    continue
                if args.role and e["role"] != args.role:
                    continue
                if args.since and e["timestamp"] and epoch(e["timestamp"]) < args.since:
                    continue
                if args.until and e["timestamp"] and epoch(e["timestamp"]) > args.until:
                    continue
                eligible += 1
                if query and query not in e["text"].casefold():
                    continue
                if args.record and args.record not in {e["record_ref"], e["source_ref"]}:
                    continue
                if matched >= args.offset:
                    if len(data) == args.limit:
                        has_more = True; break
                    text = e["text"]
                    if args.action == "search":
                        pos = match_start(text, query)
                        begin = max(0, pos - args.max_chars // 3)
                    else:
                        begin = args.text_offset
                    e["text"] = text[begin:begin + args.max_chars]
                    e["text_offset"] = begin
                    e["text_chars"] = len(text)
                    e["truncated"] = begin > 0 or len(text) > args.max_chars
                    e["next_text_offset"] = begin + len(e["text"]) if begin + len(e["text"]) < len(text) else None
                    data.append(e)
                matched += 1
            if fingerprint(path) != fp:
                warnings.append("source_changed_during_read")
            if has_more:
                break
            completed_sessions += 1
    gaps = [warning for warning in warnings if not is_notice(warning)]
    metadata_complete = all(s.get("metadata_complete", True) for s in (data if args.action == "list" else sessions)) and not any(
        not warning.startswith("unsupported_body:") for warning in gaps)
    body_formats = {s.get("body_format") for s in sessions}
    if args.action == "list":
        content_status = "not_requested"
    elif not examined and "unsupported" in body_formats and "supported" not in body_formats:
        content_status = "unsupported"
    elif not sessions and any("unsupported" in w or "mixed_session_ids" in w for w in warnings):
        content_status = "unsupported"
    elif gaps or not metadata_complete:
        content_status = "partial"
    elif data:
        content_status = "matches"
    elif not sessions:
        content_status = "no_match" if args.query else "filtered_out"
    elif not examined and not any(s.get("body_records", 0) for s in sessions):
        content_status = "metadata_only"
    elif eligible and args.query and not matched:
        content_status = "no_match"
    else:
        content_status = "filtered_out"
    result = scrub(dict(schema="conversation-readers/v1", client=client, action=args.action,
                next_offset=args.offset + len(data) if has_more else None,
                has_more=has_more, snapshot=snapshots,
                coverage=dict(checked_sessions=len(sessions),
                              scan_complete=not gaps and metadata_complete and not has_more
                              and (args.action == "list" or completed_sessions == len(sessions)),
                              metadata_complete=metadata_complete,
                              jsonl_metadata_scan="full_stream",
                              content_status=content_status, examined_events=examined,
                              completed_body_sessions=completed_sessions,
                              tools_included=args.include_tools,
                              view="visible_messages_and_selected_tools; hidden_reasoning_excluded",
                              sqlite_consistency="per_query_read_transaction; pagination_is_live"),
                warnings=list(dict.fromkeys(warnings))))
    # 正文已在 event() 中完整遮蔽；不再次处理切片，以免改变分页偏移。
    result["items"] = scrub(data) if args.action == "list" else data
    if args.action == "list":
        result["warnings_outside_filter"] = warnings_outside_filter
    result["runtime"] = runtime.describe()
    return result


def parser(client):
    p = argparse.ArgumentParser(description=f"{client} Skill 内部只读脚本；不会写原始记录或记忆库。")
    p.add_argument("action", choices=["list", "search", "read"])
    p.add_argument("--root", action="append", help="明确来源目录、JSONL 或已支持的 SQLite；可重复")
    p.add_argument("--session", help="原生 ID 或 list 返回的 session_ref")
    p.add_argument("--project", help="项目目录，按路径边界匹配")
    p.add_argument("--query", help="正文关键词；list 时仅匹配标题或 ID")
    p.add_argument("--since", type=date_arg, help="ISO 日期/时间；无时区按 UTC")
    p.add_argument("--until", type=date_arg, help="ISO 日期/时间，上界含给定时刻")
    p.add_argument("--offset", type=nonnegative, default=0)
    p.add_argument("--limit", type=positive, default=40)
    p.add_argument("--max-sessions", type=positive, default=200)
    p.add_argument("--max-chars", type=positive, default=6000)
    p.add_argument("--role", choices=["user", "assistant", "tool", "context"])
    p.add_argument("--include-tools", action="store_true")
    p.add_argument("--include-subagents", action="store_true")
    p.add_argument("--snapshot", help="read 首次返回的 JSONL 指纹；变化时报错，不假装稳定分页")
    p.add_argument("--record", help="read 精确展开返回的 record_ref 或 source_ref")
    p.add_argument("--text-offset", type=nonnegative, default=0, help="与 --record 配合读取长正文后续字符")
    p.add_argument("--format", choices=["json", "markdown"], default="json")
    return p


def nonnegative(value):
    n = int(value)
    if n < 0:
        raise argparse.ArgumentTypeError("必须 >= 0")
    return n


def positive(value):
    n = nonnegative(value)
    if n == 0:
        raise argparse.ArgumentTypeError("必须 > 0")
    return n


def date_arg(value):
    try:
        d = parse_iso(value)
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("需要 ISO 日期或时间") from exc


def main(client, argv=None):
    if client not in CLIENTS:
        raise ReaderError("unknown_client")
    args = parser(client).parse_args(argv)
    try:
        if args.limit > 200 or args.max_chars > 100000:
            raise ReaderError("limit_exceeded: --limit <= 200，--max-chars <= 100000；用分页展开")
        if args.since and args.until and args.since > args.until:
            raise ReaderError("invalid_time_range")
        if (args.record or args.text_offset) and args.action != "read":
            raise ReaderError("record_expansion_requires_read")
        if args.text_offset and not args.record:
            raise ReaderError("text_offset_requires_record")
        output = run(client, args)
    except (ReaderError, OSError, sqlite3.Error, ValueError) as exc:
        print(json.dumps({"error": redact(str(exc)), "client": client,
                          "warnings": scrub(getattr(exc, "warnings", []))}, ensure_ascii=False))
        return 2
    if args.format == "json":
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"# {client} 对话读取\n")
        for item in output["items"]:
            if args.action == "list":
                print(f'- {item["session_ref"]} — {item.get("title") or "无原生标题"}')
            else:
                print(f'## {item["role"]} · {item["timestamp"] or "时间未知"}\n\n{item["text"]}\n')
                print(f'来源：`{item["record_ref"]}`；原件：`{item["source_ref"]}`；截断：{item["truncated"]}\n')
        print("\n读取边界：" + json.dumps({k: output[k] for k in ["next_offset", "has_more", "coverage", "warnings"]}, ensure_ascii=False))
    return 0
