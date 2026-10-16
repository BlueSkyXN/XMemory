"""本机项目候选总览；只按原生路径和文件元数据汇总。"""
from collections import defaultdict
from pathlib import Path

from .common import epoch
from .memory import catalogue, envelope, inode, path_exists, project_contains
from .sessions import project_matches


def broad_root(path, home):
    path = Path(path)
    return (path == Path(path.anchor) or path == Path(home) or
            (len(path.parts) == 3 and path.parts[:2] == ('/', 'Volumes')))


def run(ctx, args):
    ctx.command = 'projects'
    ctx.memory_target = None
    ctx.include_recent_injection = False
    stores, files = catalogue(ctx)
    rows = {}
    def ensure(path):
        if path not in rows:
            rows[path] = dict(path=path, aliases=[], exists=path_exists(path), sessions=dict(count=0, first=None, last=None),
                              memory=dict(stores=0, files=0), flags=[], parent=None, children=0,
                              _sessions=set(), _stores=set(), _files=set(), _warnings=[])
        return rows[path]
    for path in ctx.projects:
        ensure(path)
    for session in ctx.sessions:
        if args.since and epoch(session.get('last')) < args.since:
            continue
        for path in session['cwds']:
            row = ensure(path)
            row['_sessions'].add((session['source'], session.get('id')))
            for field, operation in (('first', min), ('last', max)):
                values = [v for v in (row['sessions'][field], session.get(field)) if v]
                row['sessions'][field] = operation(values, key=epoch) if values else None
    for item in stores:
        owners = [item['project']['path']] if item['project'] else item['candidates']
        for owner in owners:
            ensure(owner)['_warnings'].extend(item['_warnings'] + item['_file_warnings'])
        if item['project']:
            ensure(item['project']['path'])['_stores'].add(item['path'])
        for candidate in item['candidates']:
            ensure(candidate)['flags'].append('collision')
        if item['near']:
            for target in stores:
                if target['path'] in item['near'] and target['project']:
                    ensure(target['project']['path'])['flags'].append('orphan_nearby')
    for entry in files:
        if entry['project'] and entry['role'] != 'backup':
            row = ensure(entry['project']['path'])
            row['_stores'].add(entry['_store'])
            row['_files'].add(entry['path'])
            row['_warnings'].extend(entry['_warnings'])
    if ctx.client in ('claude', 'qodercn'):
        from .clients.claude import encode, owners_by_directory
        for directory, paths in owners_by_directory(ctx).items():
            matches = [p for p in paths if encode(p) == directory]
            if len(matches) > 1:
                for path in matches:
                    ensure(path)['flags'].append('collision')
    source_projects = defaultdict(set)
    for session in ctx.sessions:
        source_projects[session['source']].update(session['cwds'])
    for source, warnings in ctx.session_warnings.items():
        owners = source_projects[source]
        if not owners:
            ctx.warnings.extend(warnings)
        else:
            ctx._memory_warnings.update(warnings)
            for path in owners:
                if path in rows:
                    rows[path]['_warnings'].extend(warnings)
    # 同 inode 的写法归为 aliases；不同 inode 的 worktree、父子目录保持独立。
    grouped, seen = [], {}
    for path, row in sorted(rows.items()):
        key = inode(path)
        if key is not None and key in seen:
            target = seen[key]
            target['aliases'].append(path)
            target['flags'].append('alias')
            if target['path'].casefold() == path.casefold():
                target['flags'].append('case_variant')
            target['flags'].extend(row['flags'])
            target['_warnings'].extend(row['_warnings'])
            for field in ('_sessions', '_stores', '_files'):
                target[field].update(row[field])
            for field, operation in (('first', min), ('last', max)):
                values = [v for v in (row['sessions'][field], target['sessions'][field]) if v]
                target['sessions'][field] = operation(values, key=epoch) if values else None
        else:
            if key is not None:
                seen[key] = row
            grouped.append(row)
    for row in grouped:
        path = row['path']
        row['sessions']['count'] = len(row['_sessions'])
        row['memory'].update(stores=len(row['_stores']), files=len(row['_files']))
        if row['memory']['stores'] and not row['sessions']['count']:
            row['flags'].append('memory_without_sessions')
        if row['exists'] == 'unmounted':
            row['flags'].append('unmounted')
        if broad_root(path, ctx.home):
            row['flags'].append('broad_root')
        elif any(path != p and not broad_root(p, ctx.home) and
                 (project_matches(path, p) or project_matches(p, path)) for p in rows):
            row['flags'].append('nested')
        if any(path != p and path.casefold() == p.casefold() for p in rows):
            row['flags'].append('case_variant')
        row['flags'] = sorted(set(row['flags']))
    by_path = {path: row for row in grouped for path in [row['path'], *row['aliases']]}
    for row in grouped:
        if broad_root(row['path'], ctx.home):
            continue
        candidates = []
        for path in [row['path'], *row['aliases']]:
            for ancestor in Path(path).parents:
                parent = by_path.get(str(ancestor))
                if parent is not None and parent is not row and not broad_root(parent['path'], ctx.home):
                    candidates.append((len(ancestor.parts), len(str(ancestor)), parent['path']))
        if candidates:
            row['parent'] = sorted(candidates, key=lambda c: (-c[0], -c[1], c[2]))[0][2]
            by_path[row['parent']]['children'] += 1
    grouped = [r for r in grouped if not ctx.projects or any(project_contains(p, q)
               for p in [r['path'], *r['aliases']] for q in ctx.projects)]
    grouped.sort(key=lambda r: (-epoch(r['sessions']['last']), r['path']))
    return envelope(ctx, 'projects', grouped, args.offset, args.limit, 'projects')
