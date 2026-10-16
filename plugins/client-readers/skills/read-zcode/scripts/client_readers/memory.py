"""原生记忆的定位、元数据、字面检索与分段；不写任何来源。"""
import ast
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from .common import ReaderError, iso, redact, scrub, is_notice
from .sessions import match_start, project_matches
from . import runtime

LAYOUTS = ('zcode-project', 'claude-project', 'codex-v1', 'codex-v2', 'codex-automation',
           'workbuddy-workspace', 'workbuddy-user', 'workbuddy-persona', 'qodercn-cli-project',
           'qodercn-desktop', 'qodercn-legacy')
STATUSES = ('ok', 'empty', 'orphan', 'ambiguous', 'unmounted', 'unofficial', 'unsupported')
BASES = ('zcode_path_hash', 'zcode_identity_hash', 'encoded_cwd', 'session_cwd',
         'automation_cwds', 'project_arg', 'none')
ROLES = ('index', 'topic', 'consolidated', 'session_summary', 'raw_extract', 'daily',
         'note', 'profile', 'persona', 'skill', 'automation', 'process_log', 'instructions',
         'activity', 'backup', 'unknown')


def scalar(value):
    value = value.strip()
    if not value:
        return ''
    if value.startswith(('"', "'", '[')):
        try:
            item = json.loads(value)
        except ValueError:
            try:
                item = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                if value.startswith('[') and value.endswith(']') and not any(c in value[1:-1] for c in '[]{}'):
                    item = [scalar(x) for x in value[1:-1].split(',') if x.strip()]
                else:
                    raise ValueError('unsupported scalar')
        if isinstance(item, (str, int, float, bool)) or item is None:
            return item
        if isinstance(item, list) and all(isinstance(x, (str, int, float, bool)) or x is None for x in item):
            return item
        raise ValueError('unsupported nested value')
    if value in ('true', 'false', 'null', '~'):
        return {'true': True, 'false': False, 'null': None, '~': None}[value]
    if value.startswith(('|', '>', '{', '&', '*', '!')):
        raise ValueError('unsupported YAML construct')
    return value


def frontmatter(text, warnings=None, path='', partial=None):
    warnings = [] if warnings is None else warnings
    partial = [] if partial is None else partial
    if not text.startswith(('---\n', '---\r\n')):
        return {}
    lines = text.splitlines()
    try:
        end = lines.index('---', 1)
    except ValueError:
        partial.append('line:1')
        warnings.append('frontmatter_partial: ' + str(path) + '; missing_delimiter')
        return {}
    rows = []
    for number, line in enumerate(lines[1:end], 2):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        leading = line[:len(line) - len(line.lstrip(' \t'))]
        rows.append((number, len(leading.expandtabs(8)), line.strip(), '\t' in leading))
    invalid_lines = set()

    def reject(key, block):
        if key not in partial:
            partial.append(key)
        invalid_lines.update(row[0] for row in block)

    def mapping(block, indent, prefix='', depth=0):
        result, seen, position = {}, set(), 0
        while position < len(block):
            row = block[position]
            number, level, content, tab = row
            match = re.fullmatch(r'([\w.-]+):\s*(.*)', content)
            stop = position + 1
            while stop < len(block) and block[stop][1] > level:
                if (match and match[2] and block[stop][3] and
                        re.fullmatch(r'[\w.-]+:\s*.*', block[stop][2])):
                    break
                stop += 1
            children = block[position + 1:stop]
            key = prefix + match[1] if match else 'line:' + str(number)
            if not match or level != indent or tab:
                reject(key, block[position:stop])
            elif match[1] in seen:
                reject(key, block[position:stop])
            else:
                seen.add(match[1])
                try:
                    result[match[1]] = value_for(key, match[2], children, depth)
                except ValueError:
                    reject(key, block[position:stop])
            position = stop
        return result

    def value_for(key, value, children, depth):
        if value:
            parsed = scalar(value)
            if not children:
                return parsed
            if value.startswith(('"', "'", '[')) or any(row[3] or row[2].startswith('- ') for row in children):
                raise ValueError('unsupported continuation')
            return scalar(' '.join([value.strip(), *(row[2] for row in children)]))
        if not children:
            return ''
        level = children[0][1]
        if children[0][2].startswith('- '):
            values = []
            for _, indent, content, tab in children:
                if tab or indent != level or not content.startswith('- '):
                    raise ValueError('unsupported list indentation')
                raw = content[2:].strip()
                if not raw or raw.startswith('- ') or (not raw.startswith(('"', "'")) and re.search(r':(?:\s|$)', raw)):
                    raise ValueError('unsupported list mapping')
                parsed = scalar(raw)
                if isinstance(parsed, (list, dict)):
                    raise ValueError('unsupported nested list')
                values.append(parsed)
            return values
        if depth:
            raise ValueError('unsupported mapping depth')
        if not re.fullmatch(r'[\w.-]+:\s*.*', children[0][2]):
            raise ValueError('unsupported empty value block')
        return mapping(children, level, key + '.', depth + 1)

    result = mapping(rows, 0)
    if partial:
        warnings.append('frontmatter_partial: ' + str(path) + '; keys=' + ','.join(partial) +
                        '; lines=' + str(len(invalid_lines)))
    return result


def outline(text):
    """字符偏移基于完整遮蔽后的文本；代码围栏内的 # 不算标题。"""
    result, offset, fence = [], 0, None
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        marker = re.match(r'(`{3,}|~{3,})', stripped)
        if marker:
            if fence is None:
                fence = marker[1][0]
            elif marker[1][0] == fence:
                fence = None
        elif fence is None:
            match = re.match(r'^(#{1,6})\s+(.+?)\s*#*\s*$', line.rstrip('\r\n'))
            if match:
                result.append(dict(section=len(result), level=len(match[1]), title=match[2], text_offset=offset))
        offset += len(line)
    return result


def path_exists(path):
    path = Path(path)
    parts = path.parts
    if len(parts) >= 3 and parts[1] == 'Volumes' and not Path(*parts[:3]).exists():
        return 'unmounted'
    return path.exists()


def inode(path):
    try:
        value = Path(path).stat()
        return value.st_dev, value.st_ino
    except OSError:
        return None


def store(path, layout, scope, owners=(), basis='none', status=None, files=None, **extra):
    owners = sorted(set(str(x) for x in owners if x))
    project = dict(path=owners[0], basis=basis) if len(owners) == 1 else None
    if status is None:
        status = 'ambiguous' if len(owners) > 1 else ('orphan' if scope == 'project' and not owners else 'ok')
        if project and path_exists(project['path']) == 'unmounted':
            status = 'unmounted'
    return dict(path=str(path), layout=layout, scope=scope, project=project,
                candidates=owners if len(owners) > 1 else [], status=status, aliases=[],
                files=0, latest_mtime=None, near=[], recent_injection=None,
                _files=files, **extra)


def store_paths(item, warnings):
    root = Path(item['path'])
    paths = item['_files'] if item.get('_files') is not None else sorted(root.rglob('*'))
    excluded = item.get('_exclude', ())
    for path in paths:
        path = Path(path)
        if not path.is_file():
            continue
        try:
            relative = path.relative_to(root)
            if '.git' in relative.parts or '.DS_Store' in relative.parts or any(relative.parts[0] == x for x in excluded):
                continue
            if not path.resolve().is_relative_to(root.resolve()):
                warnings.append('outside_store_symlink: ' + str(path))
                continue
        except (OSError, ValueError):
            continue
        yield path


def deduplicate_stores(stores):
    result, seen = [], {}
    for item in stores:
        key = inode(item['path'])
        if key is not None and key in seen:
            original = seen[key]
            if item['path'] != original['path']:
                original['aliases'].append(item['path'])
            original['aliases'].extend(item['aliases'])
        else:
            result.append(item)
            if key is not None:
                seen[key] = item
    return result


def links(text, root, index):
    targets = []
    for raw in re.findall(r'\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)', text):
        try:
            parsed = urlsplit(raw)
        except ValueError:
            continue
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        targets.append(index.parent / unquote(parsed.path))
    for raw in re.findall(r'\[\[([^\]]+)\]\]', text):
        name = raw.split('|', 1)[0].split('#', 1)[0]
        if name:
            path = Path(name)
            targets.append(index.parent / (name if path.suffix else name + '.md'))
    return {str(p.resolve()) for p in targets if p.resolve().is_relative_to(root.resolve())}


def catalogue(ctx, include_outline=False, include_backups=False):
    stores = deduplicate_stores(ctx.adapter.locate(ctx))
    entries, hashes, sessions = [], defaultdict(list), defaultdict(list)
    for item in stores:
        own, indexed, indexes = [], set(), []
        item.setdefault('_warnings', [])
        paths = list(store_paths(item, item['_warnings']))
        for path in paths:
            try:
                stat = path.stat()
                role = ctx.adapter.role(item, path)
                text, digest, metadata = '', None, {}
                warnings, partial = list(item.get('_session_warnings', [])), []
                if role != 'backup' or include_backups:
                    raw = path.read_bytes()
                    digest = hashlib.sha256(raw).hexdigest()
                    if path.suffix.lower() == '.md' or role == 'backup':
                        text = raw.decode('utf-8')
                        metadata = frontmatter(text, warnings, path, partial)
                entry = dict(path=str(path), rel=path.relative_to(item['path']).as_posix(), role=role,
                             size=stat.st_size, mtime=iso(stat.st_mtime), sha256=digest,
                             frontmatter=metadata, frontmatter_partial=partial,
                             native_session=None, project=item['project'],
                             indexed=None, duplicate_of=[], same_session_as=[], migrated=None,
                             _store=item['path'], _candidates=item['candidates'], _warnings=warnings)
                native = metadata.get('metadata', {}).get('originSessionId') if isinstance(metadata.get('metadata'), dict) else None
                field = 'metadata.originSessionId'
                if not native:
                    native, field = metadata.get('originSessionId'), 'originSessionId'
                if isinstance(native, str) and native:
                    entry['native_session'] = dict(client=ctx.client, id=native, **{'from': field})
                if hasattr(ctx.adapter, 'annotate'):
                    ctx.adapter.annotate(ctx, item, entry, text)
                if include_outline:
                    entry['outline'] = outline(redact(text))
                if role == 'index':
                    targets = links(text, Path(item['path']), path)
                    indexes.append((entry, targets))
                    indexed.update(targets)
                if digest:
                    hashes[digest].append(entry)
                if entry['native_session']:
                    native = entry['native_session']
                    sessions[(native['client'], native['id'])].append(entry)
                entries.append(entry)
                own.append(entry)
            except (OSError, UnicodeError, ValueError) as exc:
                item['_warnings'].append('memory_read_error: ' + str(path) + '; ' + type(exc).__name__)
        if indexes:
            actual = {str(Path(e['path']).resolve()) for e in own}
            for entry in own:
                entry['indexed'] = str(Path(entry['path']).resolve()) in indexed
            for index, targets in indexes:
                index['_warnings'].extend('missing_index_target: ' + missing for missing in sorted(targets - actual))
        item['_file_warnings'] = [warning for entry in own for warning in entry['_warnings']]
        item['files'] = sum(e['role'] != 'backup' for e in own)
        item['latest_mtime'] = max((e['mtime'] for e in own if e['role'] != 'backup'), default=None)
        if item['layout'] in ('codex-v1', 'codex-v2'):
            item['last_written'] = item['latest_mtime']
        if not item['files'] and item['status'] == 'ok':
            item['status'] = 'empty'
    for group in hashes.values():
        for entry in group:
            entry['duplicate_of'] = sorted(set(e['path'] for e in group if e['path'] != entry['path']))
    for group in sessions.values():
        for entry in group:
            entry['same_session_as'] = sorted(e['path'] for e in group if e is not entry and e['role'] == 'session_summary')
    ctx._memory_warnings = {warning for item in stores for warning in
                            item['_warnings'] + item['_file_warnings']}
    return stores, entries


def public(item):
    return {key: value for key, value in item.items() if not key.startswith('_')}


def selected_project(item, projects):
    if not projects:
        return True
    candidates = ([item['project']['path']] if item.get('project') else []) + item.get('candidates', item.get('_candidates', []))
    return any(project_contains(path, wanted) for path in candidates for wanted in projects)


def project_contains(path, wanted):
    if project_matches(path, wanted):
        return True
    target = inode(Path(wanted).expanduser())
    actual = Path(path).expanduser()
    return target is not None and any(inode(parent) == target for parent in (actual, *actual.parents))


def envelope(ctx, action, items, offset=0, limit=40, schema='memory'):
    page = items[offset:offset + limit]
    more = offset + len(page) < len(items)
    local = {warning for item in page for warning in item.get('_warnings', []) +
             (item.get('_file_warnings', []) if action == 'locate' else [])}
    warnings = list(dict.fromkeys([*ctx.warnings, *sorted(local)]))
    outside = getattr(ctx, '_memory_warnings', set()) - local - set(ctx.warnings)
    result = dict(schema='client-readers/' + schema + '-v1', client=ctx.client, action=action,
                data_root=str(ctx.root), warnings=warnings,
                warnings_outside_filter=sum(not is_notice(w) for w in outside), runtime=runtime.describe(),
                coverage=dict(scan_complete=not any(not is_notice(w) for w in warnings) and not more, total_items=len(items)),
                has_more=more, next_offset=offset + len(page) if more else None,
                items=[scrub(public(item)) for item in page])
    if action == 'locate':
        summary = {}
        for item in items:
            counts = summary.setdefault(item['layout'], {})
            counts[item['status']] = counts.get(item['status'], 0) + 1
        result['summary'] = summary
    if hasattr(ctx, 'known_non_memory'):
        result['known_non_memory'] = ctx.known_non_memory
    return result


def run(ctx, args):
    ctx.command = 'memory'
    ctx.include_recent_injection = args.action == 'locate'
    target = args.path if args.action == 'read' else args.store
    ctx.memory_target = Path(target).expanduser().resolve() if ctx.client == 'claude' and target else None
    stores, files = catalogue(ctx, args.outline, args.include_backups)
    selected_stores = [s for s in stores if not s.get('_ownership_skipped')]
    if args.store:
        requested = Path(args.store).expanduser().resolve()
        selected_stores = [s for s in stores if Path(s['path']).resolve() == requested or
                           (inode(requested) is not None and inode(s['path']) == inode(requested))]
        if not selected_stores:
            raise ReaderError('not_in_store: 未知的客户端存储位置')
    selected_stores = [s for s in selected_stores if selected_project(s, ctx.projects) or
                       (ctx.client == 'codex' and s['layout'] in ('codex-v1', 'codex-v2') and
                        any(e['_store'] == s['path'] and selected_project(e, ctx.projects) for e in files))]
    allowed = {s['path'] for s in selected_stores}
    selected = [e for e in files if e['_store'] in allowed and (not args.role or e['role'] in args.role)]
    if ctx.client == 'codex' and ctx.projects:
        selected = [e for e in selected if selected_project(e, ctx.projects)]
    if args.action == 'locate':
        return envelope(ctx, args.action, selected_stores, args.offset, args.limit)
    if args.action == 'list':
        return envelope(ctx, args.action, selected, args.offset, args.limit)
    if args.action == 'read':
        requested = Path(args.path).expanduser().resolve()
        matches = [e for e in files if Path(e['path']).resolve() == requested]
        if not matches and inode(requested) is not None:
            matches = [e for e in files if inode(e['path']) == inode(requested) and
                       project_contains(str(requested), str(Path(e['_store']).resolve()))]
        if not matches:
            raise ReaderError('not_in_store: 文件不在本客户端已知 store 中')
        selected = matches[:1]
        if selected[0]['role'] == 'backup' and not args.include_backups:
            raise ReaderError('backup_skipped: 显式 --include-backups 才读取正文')
    results = []
    for entry in selected:
        if entry['role'] == 'backup' and not args.include_backups:
            continue
        if entry['role'] == 'unknown':
            if args.action == 'read':
                raise ReaderError('unsupported_memory_file')
            continue
        try:
            text = redact(Path(entry['path']).read_bytes().decode('utf-8'))
        except (OSError, UnicodeError):
            warning = 'memory_read_error: ' + entry['path']
            if args.action == 'search':
                ctx.warnings.append(warning)
            else:
                entry['_warnings'].append(warning)
                ctx._memory_warnings.add(warning)
                results.append(dict(entry))
            continue
        start, end = args.text_offset, len(text)
        if args.action == 'search':
            pos = match_start(text, args.query.casefold())
            if pos < 0:
                continue
            start = max(0, pos - args.max_chars // 3)
        if args.section is not None:
            headings = outline(text)
            if args.section >= len(headings):
                raise ReaderError('section_not_found')
            start = headings[args.section]['text_offset']
            if args.section + 1 < len(headings):
                end = headings[args.section + 1]['text_offset']
        stop = min(end, start + args.max_chars)
        result = dict(entry, source_ref=entry['path'], text=text[start:stop], text_offset=start,
                      text_chars=len(text), truncated=start > 0 or stop < len(text),
                      next_text_offset=stop if stop < end else None, section_end=end)
        results.append(result)
    output = envelope(ctx, args.action, results, args.offset, args.limit)
    # 完整文本已遮蔽；切片不再遮蔽，避免分页改变长度。
    for item, original in zip(output['items'], results[args.offset:args.offset + args.limit]):
        if 'text' in original:
            item['text'] = original['text']
    return output
