"""Qoder CN 的 CLI、桌面与旧分类布局；迁移只报告账本可核实字段。"""
from pathlib import Path
import sqlite3

from . import json_sessions
from .claude import project_stores
from ..common import database, columns, iso, ReaderError
from ..memory import store


def legacy_encode(path):
    return path.replace('/', '-').lstrip('-')


def sessions(ctx):
    result = json_sessions(ctx, ctx.root / 'projects')
    db = ctx.home / 'Library/Application Support/com.qodercn.app.stable/main.sqlite'
    if db.is_file():
        try:
            with database(db) as con:
                names = columns(con, 'chat_sessions', ['session_id', 'cwd', 'created_at', 'updated_at'])
                query = 'SELECT session_id,cwd,created_at,updated_at FROM chat_sessions'
                if 'deleted_at' in names:
                    query += ' WHERE deleted_at IS NULL'
                for row in con.execute(query):
                    if isinstance(row['cwd'], str) and row['cwd']:
                        result.append(dict(id=row['session_id'], source=str(db), cwds=[row['cwd']],
                                           first=iso(row['created_at']), last=iso(row['updated_at'])))
        except (sqlite3.Error, ReaderError):
            ctx.session_warnings[str(db)] = ['session_metadata_unreadable: ' + str(db)]
    return result


def migration(ctx):
    path = ctx.home / 'Library/Application Support/com.qodercn.app.stable/memoryMigration.sqlite'
    result = {}
    if path.is_file():
        try:
            with database(path) as con:
                columns(con, 'memory_import_target_files', ['target_file', 'content_sha256', 'imported_at'])
                for target, digest, stamp in con.execute('SELECT target_file,content_sha256,imported_at FROM memory_import_target_files'):
                    if isinstance(target, str):
                        result[str(Path(target).resolve())] = dict(sha256=digest, imported_at=iso(stamp))
        except (sqlite3.Error, ReaderError, ValueError):
            ctx.warnings.append('migration_ledger_unreadable: ' + str(path))
    return result


def locate(ctx):
    result = project_stores(ctx, 'qodercn-cli-project')
    if getattr(ctx, 'command', None) != 'projects':
        directories = [Path(item['path']).parent for item in result]
        ctx.warnings.extend(warning for source, warnings in ctx.session_warnings.items()
                            if not any(Path(source).is_relative_to(d) for d in directories) for warning in warnings)
    desktop = ctx.root / 'memory'
    if desktop.is_dir():
        result.append(store(desktop, 'qodercn-desktop', 'user'))
    actual = {cwd for row in ctx.sessions for cwd in row['cwds']}
    for project in sorted((ctx.root / 'memories').glob('*/projects/*')):
        if not project.is_dir():
            continue
        known = {cwd for cwd in actual if legacy_encode(cwd) == project.name}
        provided = {cwd for cwd in ctx.projects if legacy_encode(cwd) == project.name}
        for category in sorted(p for p in project.iterdir() if p.is_dir()):
            result.append(store(category, 'qodercn-legacy', 'project', known | provided,
                                'encoded_cwd' if known else ('project_arg' if provided else 'none'),
                                category=category.name))
    # 历史 global 分类也保留可读位置；不把未映射目录归给项目。
    for category in sorted((ctx.root / 'memories').glob('*/global/*')):
        if category.is_dir():
            result.append(store(category, 'qodercn-legacy', 'global', category=category.name))
    ctx.migration = migration(ctx)
    return result


def role(item, path):
    if path.name.endswith('.bak'):
        return 'backup'
    if path.suffix != '.md':
        return 'unknown'
    if item['layout'] == 'qodercn-legacy':
        return 'topic'
    if path.name == 'MEMORY.md':
        return 'index'
    if item['layout'] == 'qodercn-desktop' and path.name.startswith('qoderwork-daily-'):
        return 'daily'
    return 'topic'


def annotate(ctx, item, entry, text):
    if item['layout'] == 'qodercn-legacy':
        entry['frontmatter']['category'] = item['category']
    target = ctx.migration.get(str(Path(entry['path']).resolve()))
    if target:
        entry['migrated'] = dict(imported_at=target['imported_at'], unchanged=entry['sha256'] == target['sha256'])
