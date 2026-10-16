"""技能内只读脚本的维护源；由 sync_client_readers.py 分发，不安装统一 CLI。Python 3.9+ 标准库。"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
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

MAX_LINE = 8 * 1024 * 1024
TEXT_TYPES = {"text", "input_text", "output_text"}
CLIENTS = {"codex", "claude", "zcode", "qodercn", "workbuddy"}
SENSITIVE_KEYS = {"apikey", "accesstoken", "refreshtoken", "password", "authorization"}
SENSITIVE_FIELD = re.compile(
    r'''(?i)(?<![\w-])["']?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|authorization)["']?[ \t]*[:=][ \t]*''')


def is_notice(warning):
    return warning.startswith('compressed_twin:')


class ReaderError(Exception):
    def __init__(self, message, warnings=None):
        super().__init__(message)
        self.warnings = warnings or []


def redact(text):
    # 先按字段边界读取整个值；引号内的空格、转义及换行不能截断敏感值。
    pieces, cursor = [], 0
    while match := SENSITIVE_FIELD.search(text, cursor):
        begin = match.end()
        pieces.append(text[cursor:begin])
        if begin == len(text) or text[begin] in "\r\n":
            cursor = begin
            continue
        quote = text[begin] if text[begin] in "\"'" else None
        if quote:
            end = begin + 1
            while end < len(text):
                if text[end] == "\\":
                    end += 2
                elif text[end] == quote:
                    break
                else:
                    end += 1
            if end < len(text):
                pieces.append(quote + "[REDACTED]" + quote)
                cursor = end + 1
                continue
            # 未闭合引号只遮蔽当前行，不吞掉其后的正常段落。
            stop = re.search(r"[\r\n]", text[begin:])
            end = begin + stop.start() if stop else len(text)
            pieces.append(quote + "[REDACTED]")
        else:
            # 无引号的字段以行、分隔符或下一个赋值字段为界，允许值内含空格。
            stop = re.search(r'''[\r\n,;}\]]|[ \t]+(?=[A-Za-z_][\w-]*[ \t]*[:=])''', text[begin:])
            end = begin + stop.start() if stop else len(text)
            if text.startswith("[REDACTED]", begin):
                end = begin + len("[REDACTED]")
            pieces.append("[REDACTED]")
        cursor = end
    pieces.append(text[cursor:])
    text = "".join(pieces)
    text = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,})\b", "[REDACTED]", text)
    return re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", text)


def scrub(value):
    """结构化敏感字段替换整个值，其余字符串按文本规则遮蔽。"""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [scrub(x) for x in value]
    if isinstance(value, dict):
        return {k: "[REDACTED]" if isinstance(k, str) and re.sub(r"[_-]", "", k).lower() in SENSITIVE_KEYS
                else scrub(x) for k, x in value.items()}
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
        try:
            decoded = json.loads(value)
        except ValueError:
            return redact(value)
        if not isinstance(decoded, (dict, list)):
            return redact(value)
        value = decoded
    # 工具的结构化返回可包含业务 JSON；移除明确的隐藏推理键。
    def clean(v):
        if isinstance(v, dict):
            return {k: clean(x) for k, x in v.items()
                    if k.lower() not in {"reasoning", "thinking", "encrypted_content", "signature"}}
        if isinstance(v, list):
            return [clean(x) for x in v if not isinstance(x, dict)
                    or x.get("type") not in ("reasoning", "thinking", "redacted_thinking")]
        return v
    return json.dumps(scrub(clean(value)), ensure_ascii=False)


def iso(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000 if value > 100000000000 else value,
                                      timezone.utc).isoformat()
    return str(value)


ISO_PARTS = re.compile(r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?)(?:[.,](\d+))?(?:([+-])(\d{2}):?(\d{2})?)?")


def parse_iso(value):
    """ISO 时间；Python 3.9/3.10 的 fromisoformat 不认 Z、非 3/6 位小数秒和 +0000，先规整成它认的写法。"""
    text = str(value).strip()
    if text[-1:] in ("Z", "z"):
        text = text[:-1] + "+00:00"
    m = ISO_PARTS.fullmatch(text)
    if m:
        base, fraction, sign, hours, minutes = m.groups()
        text = base + ("." + (fraction + "00000")[:6] if fraction else "")
        text += f"{sign}{hours}:{minutes or '00'}" if sign else ""
    return datetime.fromisoformat(text)


def epoch(value):
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return value / 1000 if value > 100000000000 else value
    try:
        d = parse_iso(value)
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


def jsonl_stem(path):
    """Codex 冷会话会被改写为 .jsonl.zst；文件名身份按去掉两层后缀后的主干计算。"""
    name = path.name
    if name.lower().endswith(".zst"):
        name = name[:-4]
    if name.lower().endswith(".jsonl"):
        name = name[:-6]
    return name


def zstd_rows(path, warnings):
    """流式解压读取 .jsonl.zst；byte 偏移基于解压后字节流，重放需按序解压。"""
    from . import runtime
    if not runtime.backend():
        warnings.append(f"zstd_missing: {path}; " + runtime.REGISTRY['zstd']['missing'])
        return
    offset = 0
    try:
        with runtime.open_zstd(path) as stream:
            while True:
                raw = stream.readline(MAX_LINE + 1)
                if not raw:
                    break
                if len(raw) > MAX_LINE:
                    warnings.append(f"oversized_record: {path}#byte:{offset}")
                    while raw:
                        offset += len(raw)
                        if raw.endswith(b"\n"):
                            break
                        raw = stream.readline(MAX_LINE + 1)
                    continue
                try:
                    item = json.loads(raw)
                    if not isinstance(item, dict):
                        raise ValueError("not an object")
                except (ValueError, UnicodeDecodeError):
                    warnings.append(f"invalid_or_partial_record: {path}#byte:{offset}")
                    offset += len(raw)
                    continue
                yield offset, item
                offset += len(raw)
    except Exception as exc:
        # 后端有各自的解码异常类型；只报告类型与路径，不回显原始输入。
        warnings.append(f"zstd_stream_error: {path}; {type(exc).__name__}")


def json_rows(path, warnings):
    """按打开时长度逐行读取；完整检查元数据，不缓存整段历史正文。"""
    if path.name.lower().endswith(".zst"):
        yield from zstd_rows(path, warnings)
        return
    start = path.stat()
    with path.open("rb") as stream:
        while stream.tell() < start.st_size:
            offset = stream.tell()
            raw = stream.readline(min(MAX_LINE + 1, start.st_size - offset))
            if not raw:
                break
            if len(raw) > MAX_LINE:
                warnings.append(f"oversized_record: {path}#byte:{offset}")
                while raw and not raw.endswith(b"\n") and stream.tell() < start.st_size:
                    raw = stream.readline(min(MAX_LINE + 1, start.st_size - stream.tell()))
                continue
            try:
                item = json.loads(raw)
                if not isinstance(item, dict):
                    raise ValueError("not an object")
            except (ValueError, UnicodeDecodeError):
                warnings.append(f"invalid_or_partial_record: {path}#byte:{offset}")
                continue
            yield offset, item
    finish = path.stat()
    if (start.st_size, start.st_mtime_ns) != (finish.st_size, finish.st_mtime_ns):
        warnings.append("source_changed_during_read")
