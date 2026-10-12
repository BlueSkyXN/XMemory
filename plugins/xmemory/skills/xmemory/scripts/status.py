"""从记忆文件计算检查报告。无写入、客户端适配器或运行状态。"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from toml_subset import TomlSubset

FORMAT = "xmemory/v1.5"
SCHEMA = "xmemory/status-v1.5"
KINDS = {"record", "daily", "project-index", "topic", "awareness", "user", "summary"}
RECORD_FIELDS = {"source", "client", "source_ref", "source_location", "source_updated", "evidence",
                 "projects", "day", "day_basis", "session_refs", "coverage"}
LINK = re.compile(r'\[[^\]\n]*\]\((<[^>\n]+>|[^\s)]+)(?:\s+"[^"\n]*")?\)')
REFERENCE = re.compile(r'^\s{0,3}\[[^\]]+\]:\s*(<[^>\n]+>|\S+)')
SECRET = re.compile(r'(?i)(?:\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|authorization)'
                    r'\b["\x27]?\s*[:=]\s*["\x27]?[^\s"\x27{},]{8,}|'
                    r'\bBearer\s+[A-Za-z0-9._~+/-]{12,}|\bsk-[A-Za-z0-9_-]{16,})')


def timestamp(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except ValueError:
        return None


def valid_day(value):
    try:
        return isinstance(value, str) and date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("missing frontmatter")
    data = {}
    for line in lines[1:]:
        if line == "---":
            return data
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep or not re.fullmatch(r"[a-z_]+", key) or key in data:
            raise ValueError("invalid field")
        parsed = json.loads(value.strip())
        if not isinstance(parsed, (str, list)) or isinstance(parsed, list) and not all(
                isinstance(x, str) for x in parsed):
            raise ValueError("unsupported field value")
        data[key] = parsed
    raise ValueError("unclosed frontmatter")


def path_kind(relative):
    parts = Path(relative).parts
    if relative == "USER.md":
        return "user"
    if relative == "memory_summary.md":
        return "summary"
    if parts[0] == "records":
        return "record"
    if parts[0] == "daily":
        return "daily"
    scope = (parts[0] == "projects" and len(parts) >= 3) or parts[0] == "personal"
    if scope:
        if parts[-1] == "AWARENESS.md":
            return "awareness"
        if parts[-1] == "MEMORY.md":
            return "project-index"
        if "topics" in parts:
            return "topic"
    return None


def safe_target(root, source, target):
    """仅检查根内链接，拒绝通过任何 symlink 访问外部目标。"""
    raw = target.strip("<>")
    if raw.startswith("#") or re.match(r"[a-z][a-z0-9+.-]*:", raw, re.I) or raw.startswith(("/", "~")):
        return None
    decoded = unquote(raw.split("#", 1)[0].split("?", 1)[0])
    if not decoded:
        return None
    candidate = Path(os.path.abspath(str((root / source).parent / decoded)))
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return None
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            return None
    return candidate


def check_config(cfg):
    if cfg.get("format") != FORMAT or not isinstance(cfg.get("timezone"), str):
        raise ValueError("format/timezone")
    excluded = cfg.get("exclude_sessions", [])
    if not isinstance(excluded, list) or not all(isinstance(x, str) for x in excluded):
        raise ValueError("exclude_sessions")
    for section in ("sources", "projects", "limits"):
        if not isinstance(cfg.get(section, {}), dict):
            raise ValueError("section")
    for source in cfg.get("sources", {}).values():
        if not isinstance(source, dict) or type(source.get("enabled")) is not bool:
            raise ValueError("source")
        if source.get("kind") not in {"sessions", "memory", "files"} or not isinstance(source.get("client"), str):
            raise ValueError("source")
        if not isinstance(source.get("paths"), list) or not all(isinstance(p, str) for p in source["paths"]):
            raise ValueError("paths")
    for name, project in cfg.get("projects", {}).items():
        if not name or name in {".", ".."} or "/" in name or "\\" in name:
            raise ValueError("project name")
        if not isinstance(project, dict) or not isinstance(project.get("roots"), list) or not all(
                isinstance(p, str) for p in project["roots"]):
            raise ValueError("project")
    limit = cfg.get("limits", {}).get("awareness_max_bytes")
    if limit is not None and (type(limit) is not int or limit <= 0):
        raise ValueError("limit")


def report(root, now=None):
    root = Path(root).expanduser().resolve()
    now = now or datetime.now(timezone.utc)
    issues, docs, targets = [], {}, {}
    output = {"schema": SCHEMA, "ok": True, "root": str(root), "timezone": None,
              "now": now.isoformat(), "objects": [], "source_hints": [], "issues": issues, "counts": {}}

    def issue(code, path, line=None, field=None):
        entry = {"code": code, "path": path}
        if line is not None:
            entry["line"] = line
        if field is not None:
            entry["field"] = field
        issues.append(entry)

    config = root / "config.toml"
    try:
        if not root.is_dir() or config.is_symlink():
            raise ValueError("root/config")
        config_text = config.read_text(encoding="utf-8")
        cfg = TomlSubset(config_text).parse()
        check_config(cfg)
        zone = ZoneInfo(cfg["timezone"])
    except (OSError, UnicodeError, ValueError, ZoneInfoNotFoundError):
        issue("invalid_config", "config.toml")
        output["ok"] = False
        output["counts"] = {"objects": {}, "issues": {"invalid_config": 1}}
        return output
    now = now.astimezone(zone)
    output.update(timezone=cfg["timezone"], now=now.isoformat())
    excluded = set(cfg.get("exclude_sessions", []))
    for number, line in enumerate(config_text.splitlines(), 1):
        if SECRET.search(line):
            issue("suspected_secret", "config.toml", line=number)

    def walk_error(error):
        issue("read_error", ".")

    for folder, dirs, names in os.walk(root, followlinks=False, onerror=walk_error):
        for name in list(dirs):
            path = Path(folder) / name
            if name.startswith(".") or path.is_symlink():
                dirs.remove(name)
                if not name.startswith(".") and path.is_symlink():
                    issue("unsupported_format", path.relative_to(root).as_posix())
        for name in sorted(names):
            if not name.endswith(".md") or name.startswith("."):
                continue
            path = Path(folder) / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                issue("unsupported_format", rel)
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                issue("read_error", rel)
                continue
            kind = path_kind(rel)
            if kind is None:
                issue("unsupported_format", rel)
                continue
            start = len(issues)
            try:
                fm = frontmatter(text)
            except (ValueError, TypeError):
                fm = {}
                issue("invalid_field", rel, field="frontmatter")
            for key in sorted({"format", "kind", "updated"} | (RECORD_FIELDS if kind == "record" else set())):
                if key not in fm:
                    issue("missing_field", rel, field=key)
            if fm.get("format") != FORMAT or fm.get("kind") != kind:
                issue("invalid_field", rel, field="format/kind")
            updated = timestamp(fm.get("updated"))
            if updated is None:
                issue("invalid_time", rel, field="updated")
            elif updated > now:
                issue("future_time", rel, field="updated")
            if kind == "record":
                for key in RECORD_FIELDS - {"projects", "session_refs"}:
                    if key in fm and not isinstance(fm[key], str):
                        issue("invalid_field", rel, field=key)
                        fm[key] = ""
                for key in ("projects", "session_refs"):
                    if not isinstance(fm.get(key), list):
                        issue("invalid_field", rel, field=key)
                        fm[key] = []
                for key in ("client", "source_ref", "source_location"):
                    if not fm.get(key):
                        issue("missing_field", rel, field=key)
                if not valid_day(fm.get("day")):
                    issue("invalid_field", rel, field="day")
                if fm.get("coverage") not in {"complete", "partial"}:
                    issue("invalid_field", rel, field="coverage")
                if fm.get("evidence") not in {"primary", "primary-summary", "secondary"}:
                    issue("invalid_field", rel, field="evidence")
                if fm.get("day_basis") not in {"event", "captured"}:
                    issue("invalid_field", rel, field="day_basis")
                if fm.get("source") != "note" and fm.get("source") not in cfg.get("sources", {}):
                    issue("invalid_field", rel, field="source")
                for project in fm.get("projects", []):
                    if project not in cfg.get("projects", {}):
                        issue("invalid_field", rel, field="projects")
                if timestamp(fm.get("source_updated")) is None:
                    issue("invalid_time", rel, field="source_updated")
                elif timestamp(fm["source_updated"]) > now:
                    issue("future_time", rel, field="source_updated")
            if kind == "daily":
                if not valid_day(fm.get("day")) or Path(rel).stem != fm.get("day"):
                    issue("invalid_field", rel, field="day")
            bad = len(issues) != start
            if kind == "record" and fm.get("coverage") == "partial":
                issue("partial_source", rel)
            if kind == "record" and excluded.intersection(fm.get("session_refs", [])):
                issue("excluded_record", rel)
            links = []
            in_fence = False
            for number, line in enumerate(text.splitlines(), 1):
                if SECRET.search(line):
                    issue("suspected_secret", rel, line=number)
                if any(identity in line for identity in excluded if identity):
                    if kind != "record":
                        issue("excluded_record", rel, line=number)
                if re.match(r"^\s*(```|~~~)", line):
                    in_fence = not in_fence
                    continue
                if in_fence:
                    continue
                matches = LINK.findall(line)
                definition = REFERENCE.match(line)
                if definition:
                    matches.append(definition[1])
                for raw in matches:
                    target = safe_target(root, rel, raw)
                    if target is not None:
                        links.append(target.relative_to(root).as_posix())
                        if not target.exists():
                            issue("broken_link", rel, line=number)
            size = len(text.encode("utf-8"))
            limit = 10000 if kind == "summary" else cfg.get("limits", {}).get("awareness_max_bytes")
            if kind in {"summary", "awareness"}:
                if limit is None:
                    issue("limit_unset", rel)
                elif size > limit:
                    issue("oversize", rel)
            docs[rel] = {"path": rel, "kind": kind, "fm": fm, "time": updated, "bad": bad,
                         "links": links, "size_bytes": size}

    records = [x for x in docs.values() if x["kind"] == "record"]
    for doc in docs.values():
        targets[doc["path"]] = doc["kind"]
    scopes = {"projects/" + name for name in cfg.get("projects", {})}
    for record in records:
        projects = record["fm"].get("projects", [])
        if not projects:
            scopes.add("personal")
        day = record["fm"].get("day")
        if valid_day(day):
            targets[f"daily/{day[:4]}/{day}.md"] = "daily"
    for scope in scopes:
        targets.setdefault(scope + "/MEMORY.md", "project-index")
        targets.setdefault(scope + "/AWARENESS.md", "awareness")
    if records or docs:
        targets.setdefault("USER.md", "user")
        targets.setdefault("memory_summary.md", "summary")
    incomplete_scan = any(x["code"] in {"read_error", "unsupported_format"} for x in issues)
    for rel, kind in sorted(targets.items()):
        doc = docs.get(rel)
        inputs = []
        if kind in {"daily", "user"}:
            inputs = records if kind == "user" else [r for r in records if r["fm"].get("day") == Path(rel).stem]
        elif kind in {"project-index", "awareness"}:
            scope = rel.rsplit("/", 1)[0]
            project = scope.split("/", 1)[1] if scope.startswith("projects/") else None
            inputs = [r for r in records if (project in r["fm"].get("projects", []) if project else
                                              not r["fm"].get("projects", []))]
            if kind == "project-index":
                inputs += [d for p, d in docs.items() if p.startswith(scope + "/topics/")]
        elif kind == "summary":
            inputs = [d for d in docs.values() if d["kind"] in {"awareness", "project-index", "user"}]
        elif kind == "topic" and doc:
            inputs = [docs[p] for p in doc["links"] if p in docs]
        newer = [d["path"] for d in inputs if d["time"] and (not doc or not doc["time"] or d["time"] > doc["time"])]
        reasons = []
        state = "current"
        if doc is None:
            state = "missing"
            reasons.append("candidate_target")
        elif doc["bad"] or incomplete_scan or any(d["bad"] for d in inputs):
            state = "unknown"
            reasons.append("incomplete_metadata_or_scan")
        elif kind == "record":
            state = "review"
            reasons.append("external_source_not_checked")
        elif newer:
            state = "review" if kind in {"user", "awareness"} else "stale"
            reasons.append("newer_sources")
        if kind == "project-index" and doc and doc["time"] and now - doc["time"] > timedelta(days=7):
            if state != "unknown":
                state = "stale"
            reasons.append("review_due")
        if any(d["fm"].get("coverage") == "partial" for d in inputs + ([doc] if doc else [])):
            if state == "current":
                state = "review"
            reasons.append("partial_source")
        own_issues = [x["code"] for x in issues if x["path"] == rel and x["code"] != "limit_unset"]
        if own_issues:
            if state == "current":
                state = "review"
            reasons.extend(sorted(set(own_issues)))
        output["objects"].append({"path": rel, "kind": kind, "updated": doc["time"].isoformat() if doc and doc["time"] else None,
                                  "assessment": state, "reasons": reasons, "newer_sources": sorted(set(newer)),
                                  "size_bytes": doc["size_bytes"] if doc else None})
    for source, settings in sorted(cfg.get("sources", {}).items()):
        selected = [d for d in records if d["fm"].get("source") == source]
        def latest(key):
            values = [timestamp(d["fm"].get(key)) for d in selected]
            values = [x for x in values if x and x <= now]
            return max(values).isoformat() if values else None
        output["source_hints"].append({"source": source, "enabled": settings["enabled"], "records": len(selected),
                                       "latest_source_updated": latest("source_updated"),
                                       "latest_record_updated": latest("updated"),
                                       "partial_records": sum(d["fm"].get("coverage") == "partial" for d in selected),
                                       "external_checked": False})
    output["counts"] = {"objects": dict(Counter(d["assessment"] for d in output["objects"])),
                        "issues": dict(Counter(d["code"] for d in issues))}
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description="XMemory 只读检查；不读客户端，不写任何文件。")
    parser.add_argument("--root", default=os.environ.get("XMEMORY_ROOT", "~/.agents/memory"))
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status", help="报告库内更新线索与结构问题")
    status.add_argument("--root", default=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    result = report(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2
