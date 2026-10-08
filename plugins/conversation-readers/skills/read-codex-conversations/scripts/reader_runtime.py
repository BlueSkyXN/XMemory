"""技能内只读脚本的维护源；由 sync_conversation_readers.py 分发，不安装统一 CLI。"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys

MAX_LINE = 8 * 1024 * 1024
TEXT_TYPES = {"text", "input_text", "output_text"}
CLIENTS = {"codex", "claude", "zcode", "qodercn", "workbuddy"}


class ReaderError(Exception):
    pass


def redact(text):
    text = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,})\b", "[REDACTED]", text)
    text = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", text)
    return re.sub(r'''(?i)((?:["']?)(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|authorization)(?:["']?)\s*[:=]\s*["']?)([^\s,;"'}]+)''', r"\1[REDACTED]", text)


def scrub(value):
    """在序列化前逐个遮蔽字符串值；对 JSON 文本整体替换会破坏转义。"""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [scrub(x) for x in value]
    if isinstance(value, dict):
        return {k: scrub(x) for k, x in value.items()}
    return value


def visible_text(value):
    """白名单提取正文；永不递归展开 reasoning、providerData 或任意未知对象。"""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(visible_text(x) for x in value if isinstance(x, (str, dict)))
    if isinstance(value, dict) and value.get("type") in TEXT_TYPES:
        return str(value.get("text", ""))
    return ""


def tool_text(value):
    if isinstance(value, str):
        return value
    # 工具的结构化返回可包含业务 JSON；移除明确的隐藏推理键。
    def clean(v):
        if isinstance(v, dict):
            return {k: clean(x) for k, x in v.items()
                    if k.lower() not in {"reasoning", "thinking", "encrypted_content", "signature"}}
        if isinstance(v, list):
            return [clean(x) for x in v if not isinstance(x, dict)
                    or x.get("type") not in {"reasoning", "thinking", "redacted_thinking"}]
        return v
    return json.dumps(clean(value), ensure_ascii=False)


def iso(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000 if value > 100000000000 else value,
                                      timezone.utc).isoformat()
    return str(value)


def epoch(value):
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return value / 1000 if value > 100000000000 else value
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp()
    except (ValueError, OverflowError):
        return 0


def fingerprint(path):
    s = path.stat()
    return hashlib.sha256(f"{path}:{s.st_ino}:{s.st_size}:{s.st_mtime_ns}".encode()).hexdigest()[:24]


@contextmanager
def database(path):
    # 不使用 immutable=1：活库的 WAL 也必须可见；不做 checkpoint/迁移。
    con = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
    try:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only=ON")
        con.execute("BEGIN")
        yield con
    finally:
        con.close()


def columns(con, table, required):
    names = {r[1] for r in con.execute(f'PRAGMA table_info("{table}")')}
    if not set(required) <= names:
        raise ReaderError(f"unsupported_schema: {table} 缺少必要字段")
    return names


def json_rows(path, warnings, metadata_only=False):
    """按打开时长度读快照；元数据只取文件头和尾，不载入整段历史。"""
    start = path.stat()
    with path.open("rb") as stream:
        if metadata_only and start.st_size > 192 * 1024:
            regions = [(0, 128 * 1024), (max(0, start.st_size - 64 * 1024), start.st_size)]
        else:
            regions = [(0, start.st_size)]
        for begin, end in regions:
            stream.seek(begin)
            if begin:
                stream.readline(MAX_LINE + 1)  # 舍弃从中间开始的第一条。
            while stream.tell() < end:
                offset = stream.tell()
                raw = stream.readline(min(MAX_LINE + 1, start.st_size - offset))
                if not raw:
                    break
                if len(raw) > MAX_LINE:
                    warnings.append(f"oversized_record: byte {offset}")
                    while raw and not raw.endswith(b"\n") and stream.tell() < start.st_size:
                        raw = stream.readline(min(MAX_LINE + 1, start.st_size - stream.tell()))
                    continue
                try:
                    item = json.loads(raw)
                    if not isinstance(item, dict):
                        raise ValueError("not an object")
                except (ValueError, UnicodeDecodeError):
                    if not metadata_only:
                        warnings.append(f"invalid_or_partial_record: byte {offset}")
                    continue
                yield offset, item
    finish = path.stat()
    if (start.st_size, start.st_mtime_ns) != (finish.st_size, finish.st_mtime_ns):
        warnings.append("source_changed_during_read")


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


def json_summary(client, path, warnings):
    if client == "zcode":
        raise ReaderError("unsupported_source: ZCode 使用已核实的 SQLite 对话表")
    match = re.search(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$", path.stem)
    sid = match[0] if match else path.stem
    result = summary(client, "jsonl", sid, path, title=None, title_origin=None,
                     project=None, parent_session_id=None, created_at=None, updated_at=None,
                     archived="archived_sessions" in path.parts, id_origin="filename")
    recognized = False
    for _, row in json_rows(path, warnings, metadata_only=True):
        typ = row.get("type")
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        if client == "codex" and typ == "session_meta":
            recognized = True
            result["session_id"] = str(payload.get("id") or payload.get("session_id") or sid)
            result["project"] = payload.get("cwd")
            result["created_at"] = iso(payload.get("timestamp") or row.get("timestamp"))
            result["id_origin"] = "session_meta"
        elif row.get("sessionId"):
            recognized = client != "codex"
            result["session_id"] = str(row["sessionId"])
            result["id_origin"] = "sessionId"
        if row.get("cwd"):
            result["project"] = row["cwd"]
        if row.get("agentId"):
            result["agent_id"] = row["agentId"]
        if typ in {"ai-title", "custom-title"}:
            title = row.get("aiTitle") or row.get("customTitle") or row.get("title")
            if title:
                result.update(title=title, title_origin=typ)
        stamp = row.get("timestamp")
        if stamp:
            result["created_at"] = result["created_at"] or iso(stamp)
            if epoch(stamp) >= epoch(result["updated_at"]):
                result["updated_at"] = iso(stamp)
    if not recognized:
        raise ReaderError("unsupported_or_incomplete_jsonl_metadata")
    result["updated_at"] = result["updated_at"] or iso(path.stat().st_mtime)
    result["session_ref"] = f'{client}:jsonl:{result["session_id"]}'
    if "subagents" in path.parts:
        result["variant"] = "subagent"
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


def catalogue(client, args, warnings):
    roots = [Path(p).expanduser().resolve() for p in args.root] if args.root else defaults(client)
    files, dbs = set(), set()
    for root in roots:
        if not root.exists():
            warnings.append(f"source_unavailable: {root}")
            continue
        if root.is_file():
            if root.suffix == ".jsonl":
                files.add(root)
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
    # 文件名只决定优先检查顺序，不能取代原生元数据或排除别名文件。
    sid = args.session.split(":")[-1] if args.session else None
    ordered = sorted(files, key=lambda p: (bool(sid and (p.stem == sid or p.stem.endswith("-" + sid))),
                                          p.stat().st_mtime_ns, str(p)), reverse=True)
    if len(ordered) > args.max_sessions:
        warnings.append("session_scan_limit: JSONL 仍有未检查的会话；缩小 --root 或增大 --max-sessions")
    result = []
    for p in ordered[:args.max_sessions]:
        try:
            result.append(json_summary(client, p, warnings))
        except (OSError, ValueError, ReaderError) as exc:
            warnings.append(f"source_error: {p}: {type(exc).__name__}")
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
    result = [s for s in result if project_matches(s.get("project"), args.project)
              and (not args.since or epoch(s.get("updated_at")) >= args.since)
              and (not args.until or epoch(s.get("created_at")) <= args.until)]
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
          record_id=None, call_id=None, name=None, stamp=None, turn_id=None):
    return dict(session_ref=s["session_ref"], session_id=s["session_id"],
                message_id=native_id, record_id=record_id, parent_id=parent_id, turn_id=turn_id,
                role=role, kind=kind, timestamp=iso(stamp), call_id=call_id, tool_name=name,
                text=redact(text), source_ref=f'{s["source"]}#{locator}',
                record_ref=f'{s["session_ref"]}@{locator}')


def blocks(s, content, locator, base, include_tools):
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]
    if not isinstance(content, list):
        return
    for i, b in enumerate(content):
        if not isinstance(b, dict):
            continue
        typ = b.get("type")
        loc = f"{locator}/block:{i}"
        if typ in TEXT_TYPES:
            text = visible_text(b)
            if text:
                kind = "summary" if text.startswith("This session is being continued") else "message"
                yield event(s, loc, text=text, kind=kind, **base)
        elif include_tools and typ == "tool_use":
            yield event(s, loc, text=tool_text(b.get("input", {})), kind="tool_call",
                        call_id=b.get("id"), name=b.get("name"), **base)
        elif include_tools and typ == "tool_result":
            values = dict(base, role="tool")
            yield event(s, loc, text=tool_text(b.get("content", "")), kind="tool_result",
                        call_id=b.get("tool_use_id"), **values)
        elif typ in {"image", "input_image", "file", "document"}:
            yield event(s, loc, text="[附件：本读取器未展开二进制内容]", kind="attachment", **base)


def json_events(s, warnings, include_tools):
    for offset, o in json_rows(Path(s["source"]), warnings):
        typ = o.get("type")
        p = o.get("payload") if isinstance(o.get("payload"), dict) else {}
        loc = f"byte:{offset}"
        if s["client"] == "codex":
            # event_msg 是重复投影；只读 response_item，避免一条回复显示两次。
            if typ == "compacted":
                text = p.get("message")
                if isinstance(text, str):
                    yield event(s, loc, "context", text, kind="summary", stamp=o.get("timestamp"))
            if typ != "response_item":
                continue
            kind, role = p.get("type"), p.get("role")
            base = dict(role=role, native_id=p.get("id"), stamp=o.get("timestamp"))
            if kind == "message" and role in {"user", "assistant"} and p.get("channel") != "analysis":
                yield from blocks(s, p.get("content"), loc, base, include_tools)
            elif include_tools and kind in {"function_call", "custom_tool_call"}:
                yield event(s, loc, "assistant", tool_text(p.get("arguments", p.get("input", ""))),
                            kind="tool_call", native_id=p.get("id"), call_id=p.get("call_id"),
                            name=p.get("name"), stamp=o.get("timestamp"))
            elif include_tools and kind in {"function_call_output", "custom_tool_call_output"}:
                yield event(s, loc, "tool", tool_text(p.get("output", "")), kind="tool_result",
                            native_id=p.get("id"), call_id=p.get("call_id"), stamp=o.get("timestamp"))
        elif s["client"] in {"claude", "qodercn"}:
            if typ not in {"user", "assistant"} or o.get("isMeta"):
                continue
            m = o.get("message", {})
            if not isinstance(m, dict):
                warnings.append(f"unsupported_message_shape: {loc}")
                continue
            yield from blocks(s, m.get("content"), loc,
                              dict(role=typ, native_id=m.get("id") or o.get("uuid"),
                                   record_id=o.get("uuid"), parent_id=o.get("parentUuid"),
                                   stamp=o.get("timestamp")), include_tools)
        elif s["client"] == "workbuddy":
            base = dict(native_id=o.get("id"), parent_id=o.get("parentId"), stamp=o.get("timestamp"))
            if typ == "message" and o.get("role") in {"user", "assistant"}:
                yield from blocks(s, o.get("content"), loc, dict(base, role=o["role"]), include_tools)
            elif include_tools and typ in {"function_call", "function_call_result"}:
                call = typ == "function_call"
                yield event(s, loc, "assistant" if call else "tool",
                            tool_text(o.get("arguments" if call else "output", "")),
                            kind="tool_call" if call else "tool_result", call_id=o.get("callId"),
                            name=o.get("name"), **base)


def sqlite_events(s, warnings, include_tools):
    with database(Path(s["source"])) as con:
        sid = s["session_id"]
        if s["client"] == "zcode":
            mc = columns(con, "message", ["id", "session_id", "data", "time_created"])
            pc = columns(con, "part", ["id", "message_id", "session_id", "data", "time_created"])
            order = 'COALESCE(sequence, time_created), time_created, id' if "sequence" in mc else 'time_created, id'
            po = 'COALESCE(sequence, time_created), time_created, id' if "sequence" in pc else 'time_created, id'
            for row in con.execute(f'SELECT * FROM message WHERE session_id=? ORDER BY {order}', (sid,)):
                try:
                    m = json.loads(row["data"])
                except (ValueError, TypeError):
                    warnings.append(f'invalid_message: {row["id"]}'); continue
                role = m.get("role")
                semantics = m.get("semantics") or {}
                if role not in {"user", "assistant"} or semantics.get("uiVisibility") == "hidden":
                    continue
                for part in con.execute(f'SELECT * FROM part WHERE session_id=? AND message_id=? ORDER BY {po}', (sid, row["id"])):
                    try:
                        b = json.loads(part["data"])
                    except (ValueError, TypeError):
                        warnings.append(f'invalid_part: {part["id"]}'); continue
                    loc = f'message:{row["id"]}/part:{part["id"]}'
                    base = dict(native_id=row["id"], record_id=part["id"], parent_id=m.get("parentID"),
                                stamp=row["time_created"])
                    if b.get("type") == "text" and not b.get("synthetic") and not b.get("ignored"):
                        yield event(s, loc, role, str(b.get("text", "")), **base)
                    elif include_tools and b.get("type") == "tool":
                        state = b.get("state") or {}
                        yield event(s, loc + "/call", "assistant", tool_text(state.get("input", {})),
                                    kind="tool_call", call_id=b.get("callID"), name=b.get("tool"), **base)
                        if "output" in state:
                            yield event(s, loc + "/result", "tool", tool_text(state["output"]),
                                        kind="tool_result", call_id=b.get("callID"), name=b.get("tool"), **base)
        elif s["client"] == "qodercn":
            columns(con, "chat_session_messages", ["session_id", "message_id", "sequence", "payload_json", "created_at"])
            for row in con.execute('SELECT * FROM chat_session_messages WHERE session_id=? ORDER BY sequence, message_id', (sid,)):
                try:
                    m = json.loads(row["payload_json"])
                except (ValueError, TypeError):
                    warnings.append(f'invalid_message: {row["message_id"]}'); continue
                role = m.get("role")
                if role not in {"user", "assistant"}:
                    continue
                loc = f'message:{row["message_id"]}'
                base = dict(native_id=row["message_id"], turn_id=m.get("turnId"),
                            stamp=m.get("timestamp") or row["created_at"])
                # parts 与 text/tools 是双份投影，优先读取 parts，避免重复。
                parts = m.get("parts") or []
                texts = [(i, b) for i, b in enumerate(parts) if isinstance(b, dict) and b.get("type") == "text"]
                if texts:
                    for i, b in texts:
                        yield event(s, loc + f"/part:{b.get('id') or i}", role, str(b.get("text", "")), **base)
                elif m.get("text"):
                    yield event(s, loc, role, str(m["text"]), **base)
                if include_tools:
                    tools = [b["tool"] for b in parts if isinstance(b, dict) and b.get("type") == "tool" and isinstance(b.get("tool"), dict)] or m.get("tools") or []
                    for i, t in enumerate(tools):
                        if not isinstance(t, dict):
                            continue
                        tl = loc + f"/tool:{t.get('id') or i}"
                        yield event(s, tl + "/call", "assistant", tool_text(t.get("input", {})),
                                    kind="tool_call", call_id=t.get("id"), name=t.get("name"), **base)
                        if "response" in t:
                            yield event(s, tl + "/result", "tool", tool_text(t["response"]),
                                        kind="tool_result", call_id=t.get("id"), name=t.get("name"), **base)


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


def run(client, args):
    warnings = []
    sessions = catalogue(client, args, warnings)
    if args.session:
        sessions = [s for s in sessions if args.session in {s["session_id"], s["session_ref"]}]
        if not sessions:
            raise ReaderError("session_not_found_in_checked_sources: 未找到；用 --root 指定项目、JSONL 文件或数据库")
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
    if args.action == "list":
        candidates = [s for s in sessions if not query or query in str(s.get("title") or "").casefold() or query in s["session_id"].casefold()]
        data = candidates[args.offset:args.offset + args.limit]
        has_more = len(candidates) > args.offset + args.limit
    else:
        for s in sessions:
            path = Path(s["source"])
            fp = fingerprint(path)
            snapshots[s["session_ref"]] = fp
            if args.snapshot and (s["variant"] in {"sqlite", "desktop"} or args.snapshot != fp):
                raise ReaderError("snapshot_changed_or_unsupported: JSONL 已变化，或 SQLite 不支持跨请求冻结；重新定位后读取")
            for e in read_events(s, warnings, args.include_tools):
                if args.role and e["role"] != args.role:
                    continue
                if args.since and e["timestamp"] and epoch(e["timestamp"]) < args.since:
                    continue
                if args.until and e["timestamp"] and epoch(e["timestamp"]) > args.until:
                    continue
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
    return dict(schema="conversation-readers/v1", client=client, action=args.action,
                items=data, next_offset=args.offset + len(data) if has_more else None,
                has_more=has_more, snapshot=snapshots,
                coverage=dict(checked_sessions=len(sessions), scan_complete=not warnings,
                              tools_included=args.include_tools,
                              view="visible_messages_and_selected_tools; hidden_reasoning_excluded",
                              sqlite_consistency="per_query_read_transaction; pagination_is_live"),
                warnings=list(dict.fromkeys(warnings)))


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
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
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
        output = scrub(run(client, args))
    except (ReaderError, OSError, sqlite3.Error, ValueError) as exc:
        print(json.dumps({"error": redact(str(exc)), "client": client}, ensure_ascii=False))
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
