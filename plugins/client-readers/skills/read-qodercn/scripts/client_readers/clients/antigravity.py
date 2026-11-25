"""Antigravity CLI 1.5.x：conversation_summaries.db 提供会话元数据，brain/<id> 下的 transcript JSONL 提供正文。

正文以 transcript_full.jsonl 为准；只有截断版 transcript.jsonl 时降级读取并报告缺口。
conversations/<id>.db 的步骤是无公开 schema 的 protobuf，不解析。未发现原生记忆存储。
"""
import json
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import urlparse
from urllib.request import url2pathname

from ..common import ReaderError, columns, database, epoch, iso, json_rows, tool_text
from ..sessions import event, summary

INDEX = 'conversation_summaries.db'
FULL, TRUNCATED = 'transcript_full.jsonl', 'transcript.jsonl'
UUID = re.compile(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}')
USER = ('USER_EXPLICIT', 'USER_INPUT')
PLANNER = ('MODEL', 'PLANNER_RESPONSE')
TOOL_RESULT = ('MODEL', 'GENERIC')
CHECKPOINT = ('SYSTEM', 'CHECKPOINT')
SYSTEM_MESSAGES = {('SYSTEM', 'SYSTEM_MESSAGE'), ('SYSTEM_SDK', 'SYSTEM_MESSAGE')}
# API 重试与失败通知，不含对话正文。
METADATA = {('SYSTEM', 'ERROR_MESSAGE')}
BODY = {USER, PLANNER, TOOL_RESULT, CHECKPOINT} | SYSTEM_MESSAGES
ATTACHMENT = '[附件：本读取器未展开二进制内容]'


def workspace_paths(raw, locator, warnings):
    """workspace_uris 是 file:// URI 的 JSON 数组；中文等路径经百分号编码。"""
    try:
        values = json.loads(raw) if raw else []
    except ValueError:
        warnings.append(f'invalid_json: {locator}/workspace_uris')
        return []
    if not isinstance(values, list):
        warnings.append(f'invalid_shape: {locator}/workspace_uris; 预期列表')
        return []
    result = []
    for value in values:
        parsed = urlparse(value) if isinstance(value, str) else None
        if parsed is None or parsed.scheme != 'file' or parsed.netloc not in ('', 'localhost'):
            warnings.append(f'unsupported_workspace_uri: {locator}; 只识别本机 file:// 路径')
            continue
        # url2pathname 解码百分号，并在 Windows 上处理盘符与分隔符。
        path = url2pathname(parsed.path)
        if path and path not in result:
            result.append(path)
    return result


def index_rows(root, warnings):
    path = root / INDEX
    if not path.is_file():
        warnings.append(f'index_unavailable: {path}; 标题、项目与父会话未知')
        return None
    for attempt in range(3):
        try:
            with database(path) as con:
                columns(con, 'conversation_summaries', ['conversation_id', 'title', 'workspace_uris',
                                                        'last_modified_time', 'parent_conversation_id'])
                return {r['conversation_id']: {k: r[k] for k in r.keys()}
                        for r in con.execute('SELECT * FROM conversation_summaries')}
        except sqlite3.OperationalError as exc:
            # 客户端运行中重置 WAL 时，只读连接可能短暂无法打开；有限重试后再报告缺口。
            if attempt == 2:
                warnings.append(f'index_unavailable: {path}; {exc}')
                return None
            time.sleep(0.2)
        except (sqlite3.Error, ReaderError) as exc:
            warnings.append(f'index_unavailable: {path}; {exc}')
            return None


def transcript(directory):
    for name in (FULL, TRUNCATED):
        path = directory / '.system_generated/logs' / name
        if path.is_file() and not path.is_symlink():
            return path
    return None


def resolve(root, warnings):
    """返回 (数据根, [(会话目录, 正文文件或 None, 是否显式指定)])；数据根用于定位索引库。"""
    if root.is_file():
        if root.name in (FULL, TRUNCATED) and root.parent.name == 'logs' and \
                root.parent.parent.name == '.system_generated':
            directory = root.parents[2]
            base = directory.parent.parent if directory.parent.name == 'brain' else None
            return base, [(directory, root, True)]
        warnings.append(f'unsupported_source: {root}')
        return None, []
    if root.name != 'brain' and ((root / 'brain').is_dir() or (root / INDEX).is_file()):
        if not (root / 'brain').is_dir():
            return root, []
        root = root / 'brain'
    if root.name == 'brain':
        return root.parent, [(p, None, False) for p in root.iterdir() if p.is_dir() and UUID.fullmatch(p.name)]
    if (root / '.system_generated').is_dir():
        base = root.parent.parent if root.parent.name == 'brain' else None
        return base, [(root, None, True)]
    warnings.append(f'unsupported_source: {root}')
    return None, []


def record_kind(row):
    """先检查记录形状；未知来源或类型报告缺口，不当作空历史。"""
    source, typ = row.get('source'), row.get('type')
    if not isinstance(source, str) or not isinstance(typ, str) or not isinstance(row.get('step_index'), int):
        return 'unsupported'
    key = (source, typ)
    if key in METADATA:
        return 'metadata'
    if key not in BODY:
        return 'unsupported'
    if any(row.get(k) is not None and not isinstance(row[k], str)
           for k in ('content', 'thinking', 'error', 'created_at', 'status')):
        return 'unsupported'
    calls, media = row.get('tool_calls'), row.get('media')
    if calls is not None and not (isinstance(calls, list) and all(
            isinstance(c, dict) and isinstance(c.get('name'), str) and
            (c.get('args') is None or isinstance(c['args'], dict)) for c in calls)):
        return 'unsupported'
    if media is not None and not (isinstance(media, list) and all(isinstance(m, dict) for m in media)):
        return 'unsupported'
    # 只有隐藏推理或失败信息的规划步骤没有可见正文。
    if key == PLANNER and not row.get('content') and not calls:
        return 'metadata'
    return 'body'


def session_summary(directory, path, meta, warnings):
    sid = directory.name
    meta_warnings = []
    projects = workspace_paths(meta.get('workspace_uris'), f'{INDEX}#{sid}', meta_warnings) if meta else []
    meta = meta or {}
    result = summary('antigravity', 'subagent' if meta.get('parent_conversation_id') else 'jsonl', sid, path,
                     title=meta.get('title') or None, title_origin='native_index' if meta.get('title') else None,
                     project=projects[0] if projects else None, projects=projects,
                     parent_session_id=meta.get('parent_conversation_id') or None,
                     agent_name=meta.get('agent_name') or None,
                     created_at=None, updated_at=None, archived=None, id_origin='brain_directory',
                     transcript='full' if path.name == FULL else 'truncated')
    if path.name != FULL:
        warnings.append(f'truncated_transcript: {path}; 缺少 {FULL}，部分正文可能被截断')
    counts = {'body': 0, 'metadata': 0, 'unsupported': 0}
    for offset, row in json_rows(path, meta_warnings):
        kind = record_kind(row)
        counts[kind] += 1
        if kind == 'unsupported':
            warnings.append(f'unsupported_body: {path}#byte:{offset}; 不符合 antigravity 正文格式')
        stamp = row.get('created_at')
        if isinstance(stamp, str) and epoch(stamp):
            if result['created_at'] is None or epoch(stamp) < epoch(result['created_at']):
                result['created_at'] = iso(stamp)
            if epoch(stamp) >= epoch(result['updated_at']):
                result['updated_at'] = iso(stamp)
    warnings.extend(meta_warnings)
    result['updated_at'] = result['updated_at'] or iso(meta.get('last_modified_time')) or iso(path.stat().st_mtime)
    result['metadata_complete'] = bool(meta) and not meta_warnings
    result['metadata_scan'] = 'full_stream'
    result['body_records'] = counts['body']
    result['body_format'] = ('partial' if counts['body'] else 'unsupported') if counts['unsupported'] else (
        'supported' if counts['body'] else 'metadata_only')
    return result


def catalogue(args, warnings, source_warnings=None):
    roots = [Path(p).expanduser().resolve() for p in args.root] if args.root else \
        [Path.home() / '.gemini/antigravity-cli']
    sid = args.session.split(':')[-1] if args.session else None
    candidates, indexes = [], {}
    for root in roots:
        if not root.exists():
            warnings.append(f'source_unavailable: {root}')
            continue
        base, directories = resolve(root, warnings)
        if base is not None and base not in indexes:
            indexes[base] = index_rows(base, warnings)
        elif base is None and directories:
            warnings.append(f'index_unavailable: {root}; 不在 Antigravity 数据根内，标题、项目与父会话未知')
        meta = indexes.get(base) if base is not None else None
        for directory, path, explicit in directories:
            if sid and directory.name != sid:
                continue
            row = meta.get(directory.name) if meta else None
            # 子会话只在列表范围内默认隐藏；按 ID 点名或直接指定来源时照常读取。
            if row and row.get('parent_conversation_id') and not (explicit or sid or args.include_subagents):
                continue
            path = path or transcript(directory)
            if path is None:
                # 未运行过的空会话只有上传和草稿目录；有步骤却缺正文才是缺口。
                if row and (row.get('step_count') or 0) > 0:
                    warnings.append(f'transcript_missing: {directory}; 索引记录 {row["step_count"]} 步')
                continue
            stamp = epoch(row.get('last_modified_time')) if row else 0
            candidates.append((stamp or path.stat().st_mtime, str(path), directory, path, row, meta is not None))
    candidates.sort(reverse=True)
    if len(candidates) > args.max_sessions:
        warnings.append('session_scan_limit: Antigravity 仍有未检查的会话；缩小 --root 或增大 --max-sessions')
    result = []
    for _, _, directory, path, row, indexed in candidates[:args.max_sessions]:
        local = []
        if indexed and row is None:
            local.append(f'index_entry_missing: {directory.name}; 标题、项目与父会话未知')
        try:
            item = session_summary(directory, path, row, local)
        except (OSError, ValueError, ReaderError) as exc:
            warnings.extend(local)
            warnings.append(f'source_error: {path}: {exc}')
            continue
        result.append(item)
        if source_warnings is None:
            warnings.extend(local)
        else:
            source_warnings[str(path)] = local
    return result


def events(s, warnings, include_tools=True):
    source = s['source']
    for offset, row in json_rows(Path(source), warnings):
        loc = f'byte:{offset}'
        kind = record_kind(row)
        if kind == 'unsupported':
            warnings.append(f'unsupported_body: {source}#{loc}; 不符合 antigravity 正文格式')
            continue
        if kind == 'metadata':
            continue
        if row.get('truncated_fields'):
            warnings.append(f'truncated_record: {source}#{loc}; 原件已截断字段 ' +
                            ','.join(str(x) for x in row['truncated_fields']))
        key = (row['source'], row['type'])
        base = dict(record_id=str(row['step_index']), stamp=row.get('created_at'))
        content = row.get('content') or ''
        media = row.get('media') or []
        if key == USER:
            if content:
                yield event(s, loc, 'user', content, **base)
            for i, _ in enumerate(media):
                yield event(s, f'{loc}/block:{i}', 'user', ATTACHMENT, kind='attachment', **base)
        elif key == PLANNER:
            if content:
                yield event(s, loc, 'assistant', content, **base)
            for i, call in enumerate(row.get('tool_calls') or []):
                yield event(s, f'{loc}/block:{i}', 'assistant', tool_text(call.get('args')),
                            kind='tool_call', name=call['name'], **base)
        elif key == TOOL_RESULT:
            # 工具结果按步骤顺序跟随调用，原件不保存 call_id，不补造关联。
            item = event(s, loc, 'tool', tool_text(content), kind='tool_result', **base)
            item['status'] = row.get('status')
            if media:
                item['attachments'] = len(media)
            yield item
        elif key == CHECKPOINT:
            if content:
                yield event(s, loc, 'context', content, kind='summary', **base)
        elif content:
            # 系统注入的提醒、看板与成员消息；属于工具层，按需展开。
            yield event(s, loc, 'context', content, kind='system_message', **base)


def sessions(ctx):
    """项目总览用的顶层会话；子会话与 sessions list 默认范围一致，不计入。"""
    meta = index_rows(ctx.root, ctx.warnings) if ctx.root.exists() else None
    result = []
    for sid, row in sorted((meta or {}).items()):
        if row.get('parent_conversation_id'):
            continue
        local = []
        cwds = workspace_paths(row.get('workspace_uris'), f'{INDEX}#{sid}', local)
        path = transcript(ctx.root / 'brain' / sid)
        first = None
        if path is not None:
            rows = json_rows(path, local)
            try:
                for _, item in rows:
                    first = iso(item.get('created_at')) if isinstance(item.get('created_at'), str) else None
                    break
            except OSError as exc:
                local.append(f'session_metadata_unreadable: {path}; {type(exc).__name__}')
            finally:
                rows.close()
        source = str(path or ctx.root / 'brain' / sid)
        ctx.session_warnings[source] = local
        if cwds:
            result.append(dict(source=source, container=str(ctx.root / 'brain'), cwds=cwds, id=sid,
                               first=first, last=iso(row.get('last_modified_time'))))
    return result


def locate(ctx):
    """没有原生记忆存储；列出已知的非记忆数据，避免把空结果误读为未检查。"""
    ctx.known_non_memory = [str(ctx.root / name) for name in ('brain', 'conversations', 'implicit', 'annotations')
                            if (ctx.root / name).exists()]
    return []


def role(item, path):
    return 'unknown'
