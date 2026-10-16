"""按会话 cwd 发现工作区；用户级与人设目录只纳入记忆文件。"""
from pathlib import Path
import re

from . import json_sessions
from ..memory import store, path_exists


def sessions(ctx):
    return json_sessions(ctx, ctx.root / 'projects')


def locate(ctx):
    actual = {cwd for row in ctx.sessions for cwd in row['cwds']}
    if getattr(ctx, 'command', None) != 'projects':
        ctx.warnings.extend(w for warnings in ctx.session_warnings.values() for w in warnings)
    result = []
    for cwd in sorted(actual | set(ctx.projects)):
        if (Path(cwd) / '.workbuddy').resolve() == ctx.root.resolve():
            continue
        path = Path(cwd) / '.workbuddy/memory'
        if path.is_dir() or path_exists(cwd) == 'unmounted':
            result.append(store(path, 'workbuddy-workspace', 'project', [cwd],
                                'session_cwd' if cwd in actual else 'project_arg'))
    user = [ctx.root / 'MEMORY.md'] + sorted((ctx.root / 'memory').glob('*'))
    user = [p for p in user if p.is_file()]
    if user:
        result.append(store(ctx.root, 'workbuddy-user', 'user', files=user))
    for path in sorted(ctx.root.glob('user-*')):
        if path.is_dir():
            files = [p for p in path.iterdir() if p.is_file() and (p.suffix == '.md' or p.name.endswith('.bak'))]
            result.append(store(path, 'workbuddy-persona', 'user', files=files))
    return result


def role(item, path):
    if path.name.endswith('.bak'):
        return 'backup'
    if item['layout'] == 'workbuddy-persona':
        if path.name == 'USER.md':
            return 'profile'
        if path.name in ('IDENTITY.md', 'SOUL.md'):
            return 'persona'
    if path.name == 'MEMORY.md' or re.fullmatch(r'[0-9a-fA-F-]+_memory\.md', path.name):
        return 'consolidated'
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}\.md', path.name):
        return 'daily'
    return 'unknown'
