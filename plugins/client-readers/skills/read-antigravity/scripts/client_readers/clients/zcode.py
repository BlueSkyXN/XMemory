"""ZCode 3.14.3 / CLI 0.16.9 的路径与 identity 映射。"""
import hashlib
import os
from pathlib import Path
import re
import sqlite3

from ..common import database, columns, iso, ReaderError
from ..memory import store


def key(directory, identity=None):
    identity = identity.strip() if isinstance(identity, str) else ''
    directory = os.path.abspath(directory)
    source = identity or (directory.lower() if os.name == 'nt' else directory)
    slug = re.sub(r'[^a-z0-9._-]+', '-', Path(directory).name.lower()).strip('-')[:48] or 'project'
    return ('project' if identity else slug) + '-' + hashlib.sha256(source.encode()).hexdigest()[:16]


def sessions(ctx):
    path = ctx.root / 'db/db.sqlite'
    if not path.is_file():
        return []
    try:
        with database(path) as con:
            names = columns(con, 'session', ['id', 'directory', 'time_created', 'time_updated'])
            identity = 'workspace_id' if 'workspace_id' in names else 'NULL AS workspace_id'
            return [dict(id=r['id'], source=str(path), cwds=[r['directory']],
                         workspace_id=r['workspace_id'], first=iso(r['time_created']), last=iso(r['time_updated']))
                    for r in con.execute('SELECT id,directory,time_created,time_updated,' + identity + ' FROM session')
                    if isinstance(r['directory'], str) and r['directory']]
    except (sqlite3.Error, ReaderError):
        ctx.warnings.append('session_metadata_unreadable: ' + str(path))
        return []


def locate(ctx):
    owners, bases = {}, {}
    for row in ctx.sessions:
        for cwd in row['cwds']:
            name = key(cwd, row.get('workspace_id'))
            owners.setdefault(name, set()).add(cwd)
            bases[name] = 'zcode_identity_hash' if (row.get('workspace_id') or '').strip() else 'zcode_path_hash'
    for cwd in ctx.projects:
        name = key(cwd)
        owners.setdefault(name, set()).add(cwd)
        bases.setdefault(name, 'project_arg')
    root = ctx.root / 'memories/projects'
    paths = {p for p in root.iterdir() if p.is_dir()} if root.is_dir() else set()
    paths.update(root / key(p) for p in ctx.projects if (root / key(p)).is_dir())
    result = [store(p / 'memory', 'zcode-project', 'project', owners.get(p.name, ()),
                    bases.get(p.name, 'none')) for p in sorted(paths)]
    known = [p for p in paths if p.name in owners]
    for item in result:
        if item['status'] == 'orphan':
            name = Path(item['path']).parent.name
            slug, _, tail = name.rpartition('-')
            item['near'] = sorted(str(p / 'memory') for p in known if
                                  (slug != 'project' and p.name.rpartition('-')[0] == slug) or
                                  tail.startswith(p.name.rpartition('-')[2]))
    ctx.known_non_memory = [str(p) for p in (ctx.root.parent / 'db.sqlite', ctx.root / 'db/sqlite.sqlite',
                                           ctx.root.parent / 'v2/tasks-index.sqlite') if p.exists()]
    ctx.known_non_memory.append(str(ctx.root / 'rollout/model-io-*'))
    return result


def role(item, path):
    return 'index' if path.name == 'MEMORY.md' else ('topic' if path.suffix == '.md' else 'unknown')
