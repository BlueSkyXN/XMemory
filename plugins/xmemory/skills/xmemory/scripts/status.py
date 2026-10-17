"""从记忆文件计算检查报告。无写入、客户端适配器或运行状态。"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
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
TIME = re.compile(r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2})(?::(\d{2})(?:[.,](\d+))?)?([Zz]|[+-]\d{2}(?::?\d{2})?)")


def timestamp(value):
    """带时区的 ISO 时间。按读取器的写法规整后再解析，Python 3.9 与新版本结果一致。"""
    match = TIME.fullmatch(value) if isinstance(value, str) else None
    if not match:
        return None
    base, seconds, fraction, zone = match.groups()
    zone = "+00:00" if zone in {"Z", "z"} else zone[:3] + ":" + (zone[3:].lstrip(":") or "00")
    text = base + (":" + seconds if seconds else "") + ("." + (fraction + "00000")[:6] if fraction else "") + zone
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def valid_day(value):
    try:
        return isinstance(value, str) and date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def record_days(metadata):
    """兼容 1.5.0 单日记录；新字段只列材料实际支持的日期，不展开猜测的范围。"""
    if "event_days" in metadata:
        values = metadata["event_days"]
        if not isinstance(values, list) or not values or not all(valid_day(x) for x in values):
            return []
        return sorted(set(values))
    return [metadata["day"]] if valid_day(metadata.get("day")) else []


def canonical_identity(value):
    if not isinstance(value, str) or re.search(r"\s", value):
        return False
    client, sep, native = value.partition(":")
    return bool(sep and re.fullmatch(r"[a-z][a-z0-9_-]*", client) and native
                and not re.match(r"(?:jsonl|sqlite|desktop|subagent):", native))


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
              "now": now.isoformat(), "inventory": None, "counts": {}, "issues": issues,
              "source_hints": [], "objects": []}

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
    if any(not canonical_identity(ref) for ref in excluded):
        issue("identity_review", "config.toml", field="exclude_sessions")
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
                if "event_days" in fm and not record_days(fm):
                    issue("invalid_field", rel, field="event_days")
                if fm.get("day_basis") == "captured" and "event_days" in fm:
                    issue("invalid_field", rel, field="event_days/day_basis")
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
                if "project_status" in fm and (fm["project_status"] != "unresolved" or fm["projects"]):
                    issue("invalid_field", rel, field="project_status")
                source_time = timestamp(fm.get("source_updated"))
                if fm.get("source_updated") != "" and source_time is None:
                    issue("invalid_time", rel, field="source_updated")
                elif source_time and source_time > now:
                    issue("future_time", rel, field="source_updated")
            if kind == "daily":
                if not valid_day(fm.get("day")) or Path(rel).stem != fm.get("day"):
                    issue("invalid_field", rel, field="day")
            bad = len(issues) != start
            # 空值是格式允许的未知来源时间，保留记录级提示，不污染下游元数据。
            if kind == "record" and fm.get("source_updated") == "":
                issue("unknown_source_time", rel, field="source_updated")
            if kind == "record" and any(not canonical_identity(ref) for ref in fm.get("session_refs", [])):
                issue("identity_review", rel, field="session_refs")
            if kind == "record" and fm.get("project_status") == "unresolved":
                issue("unresolved_project", rel)
            if kind == "record" and Path(rel).parts[:2] == ("records", "sessions") and fm.get("session_refs"):
                suffix = Path(rel).stem.rsplit("-", 1)[-1]
                identities = [ref.split(":", 1)[1] for ref in fm["session_refs"] if canonical_identity(ref)]
                if len(suffix) != 8 or not any(suffix == identity[-8:] for identity in identities):
                    issue("identity_review", rel, field="filename")
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
        if not projects and record["fm"].get("project_status") != "unresolved":
            scopes.add("personal")
        for day in record_days(record["fm"]):
            targets[f"daily/{day[:4]}/{day}.md"] = "daily"
    for scope in scopes:
        targets.setdefault(scope + "/MEMORY.md", "project-index")
        targets.setdefault(scope + "/AWARENESS.md", "awareness")
    if records or docs:
        targets.setdefault("USER.md", "user")
        targets.setdefault("memory_summary.md", "summary")
    incomplete_scan = any(x["code"] in {"read_error", "unsupported_format"} for x in issues)
    scope_links = {scope: {link for path, doc in docs.items() if path.startswith(scope + "/")
                           for link in doc["links"]} for scope in scopes}
    for rel, kind in sorted(targets.items()):
        doc = docs.get(rel)
        inputs = []
        unlinked = []
        if kind in {"daily", "user"}:
            inputs = list(records) if kind == "user" else [
                r for r in records if Path(rel).stem in record_days(r["fm"]) or not record_days(r["fm"])
                or (r["fm"].get("day_basis") == "captured" and "event_days" in r["fm"])]
            if kind == "daily" and doc:
                unlinked = [r["path"] for r in inputs if Path(rel).stem in record_days(r["fm"])
                            and r["path"] not in doc["links"]]
        elif kind in {"project-index", "awareness"}:
            scope = rel.rsplit("/", 1)[0]
            project = scope.split("/", 1)[1] if scope.startswith("projects/") else None
            inputs = [r for r in records if (project in r["fm"].get("projects", []) if project else
                                              not r["fm"].get("projects", []) and
                                              r["fm"].get("project_status") != "unresolved")]
            # 范围提示只挂在已有索引上；意识与缺失对象不重复列出，缺失对象的输入见 newer_sources。
            if kind == "project-index" and doc:
                unlinked = [r["path"] for r in inputs if r["path"] not in scope_links.get(scope, set())]
            if kind == "project-index":
                inputs += [d for p, d in docs.items() if p.startswith(scope + "/topics/")]
        elif kind == "summary":
            inputs = [d for d in docs.values() if d["kind"] in {"awareness", "project-index", "user"}]
        elif kind == "topic" and doc:
            inputs = [docs[p] for p in doc["links"] if p in docs]
        if doc and kind != "record":
            # 已有引用也参与复查，避免日期或项目更正后旧对象失去变化信号。
            inputs += [docs[p] for p in doc["links"] if p in docs and p != rel]
            inputs = list({d["path"]: d for d in inputs}.values())
        # 已有文件始终检查；缺失对象只有存在直接输入时才作为候选。
        if doc is None and not inputs:
            continue
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
        if unlinked and kind == "daily":
            if state == "current":
                state = "stale"
            reasons.append("unlinked_sources")
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
                                  "unlinked_sources": sorted(set(unlinked)),
                                  "size_bytes": doc["size_bytes"] if doc else None})
    summary = next((item for item in output["objects"] if item["kind"] == "summary"), None)
    if summary is not None:
        # 摘要可能晚于新记录，但它所依赖的画像/项目入口尚未处理该记录。
        # 只传播明确的库内更新；不传播记录固定的 external_source_not_checked。
        summary["upstream_updates"] = [
            {"path": item["path"], "newer_sources": item["newer_sources"]}
            for item in output["objects"]
            if item["path"] in docs and item["kind"] in {"awareness", "project-index", "user"}
            and item["assessment"] in {"stale", "review"} and item["newer_sources"]
        ]
        if summary["upstream_updates"]:
            if summary["assessment"] == "current":
                summary["assessment"] = "review"
            summary["reasons"].append("upstream_newer_sources")
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
    derived = [d for d in docs.values() if d["kind"] != "record"]
    candidates = [d for d in output["objects"] if d["assessment"] == "missing"]
    record_projects = {project for r in records for project in r["fm"].get("projects", [])}
    directories = ("sessions", "imported", "files", "notes")
    by_directory = Counter(Path(r["path"]).parts[1] if Path(r["path"]).parts[1] in directories
                           else "other" for r in records)
    by_source = Counter({name: 0 for name in cfg.get("sources", {})})
    known_sources = set(by_source) | {"note"}
    by_source.update(r["fm"]["source"] for r in records if r["fm"].get("source") in known_sources)
    # 需要处理的已有内容也放进清点，汇报时与配置和文件数量一起读到。
    assessed = {item["path"]: item["assessment"] for item in output["objects"]}
    unlinked_by_kind = {kind: {p for item in output["objects"] if item["kind"] == kind for p in item["unlinked_sources"]}
                        for kind in ("daily", "project-index")}
    output["inventory"] = {
        "scan_complete": not incomplete_scan,
        "configuration": {"sources": len(cfg.get("sources", {})),
                          "enabled_sources": sum(s["enabled"] for s in cfg.get("sources", {}).values()),
                          "projects": len(cfg.get("projects", {})),
                          "projects_with_records": len(record_projects.intersection(cfg.get("projects", {})))},
        "existing_objects": len(docs),
        "records": {"total": len(records),
                    "by_directory": {name: by_directory[name] for name in (*directories, "other")},
                    "by_source": dict(sorted(by_source.items())),
                    "unconfigured_source": sum(r["fm"].get("source") not in known_sources for r in records),
                    "partial": sum(r["fm"].get("coverage") == "partial" for r in records),
                    "unresolved_project": sum(r["fm"].get("project_status") == "unresolved" for r in records),
                    "unknown_source_time": sum(r["fm"].get("source_updated") == "" for r in records),
                    "unknown": sum(assessed.get(r["path"]) == "unknown" for r in records),
                    "unlinked": {"daily": len(unlinked_by_kind["daily"]),
                                 "projects": len(unlinked_by_kind["project-index"])}},
        "derived": {"total": len(derived),
                    "by_kind": {kind: sum(d["kind"] == kind for d in derived) for kind in sorted(KINDS - {"record"})},
                    "by_assessment": {state: sum(assessed.get(d["path"]) == state for d in derived)
                                      for state in ("current", "stale", "review", "unknown")}},
        "candidates": {"total": len(candidates),
                       "by_kind": {kind: sum(d["kind"] == kind for d in candidates) for kind in sorted(KINDS - {"record"})}},
    }
    return output


def summarize(result):
    """保留全库计数与问题，省略正常对象及记录固定的外部复查提示。"""
    return {**result, "objects": [item for item in result["objects"]
                                 if item["unlinked_sources"] or
                                 (item["kind"] != "record" and item["assessment"] != "current") or
                                 (item["kind"] == "record" and
                                  set(item["reasons"]) - {"external_source_not_checked"})]}


def format_summary(result):
    """精简报告的文本形式：报告头保持缩进，对象每条一行，按行读取也能看全清点。"""
    head = json.dumps({k: v for k, v in result.items() if k != "objects"}, ensure_ascii=False, indent=2)
    items = ",\n".join("    " + json.dumps(item, ensure_ascii=False) for item in result["objects"])
    return head[:-2] + ',\n  "objects": [' + ("\n" + items + "\n  " if items else "") + "]\n}"


def main(argv=None):
    parser = argparse.ArgumentParser(description="XMemory 只读检查；不读客户端，不写任何文件。")
    parser.add_argument("--root", default=os.environ.get("XMEMORY_ROOT", "~/.agents/memory"))
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status", help="报告库内更新线索与结构问题")
    status.add_argument("--root", default=argparse.SUPPRESS)
    status.add_argument("--summary", action="store_true", help="精简对象列表，保留全库清点与问题")
    args = parser.parse_args(argv)
    result = report(args.root)
    print(format_summary(summarize(result)) if args.summary else json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2
