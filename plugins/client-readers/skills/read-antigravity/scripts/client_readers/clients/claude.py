"""Claude Code 的有损目录编码；归属必须与该目录全部 cwd 比对。"""
from pathlib import Path
import re

from . import json_sessions
from ..memory import inode, store


def encode(path):
    return re.sub(r'[^A-Za-z0-9]', '-', path)


def sessions(ctx):
    return json_sessions(ctx, ctx.root / 'projects')


def owners_by_directory(ctx):
    result = {}
    root = ctx.root / 'projects'
    for row in ctx.sessions:
        try:
            directory = Path(row['source']).relative_to(root).parts[0]
        except (ValueError, IndexError):
            continue
        result.setdefault(directory, set()).update(row['cwds'])
    return result


def project_stores(ctx, layout):
    root = ctx.root / 'projects'
    for_projects = getattr(ctx, 'command', None) == 'projects'
    scoped = ctx.client == 'claude' and not for_projects
    directories = {} if scoped else owners_by_directory(ctx)
    target = getattr(ctx, 'memory_target', None) if scoped else None
    paths = sorted(p for p in root.glob('*/memory') if p.is_dir())
    result = []
    for path in paths:
        name = path.parent.name
        selected = target is None or target == path.resolve() or target.is_relative_to(path.resolve())
        if not selected:
            key = inode(path)
            selected = key is not None and any(inode(parent) == key for parent in (target, *target.parents))
        if scoped and selected:
            directory = str(path.parent)
            if directory not in ctx._directory_sessions:
                ctx._directory_sessions[directory] = json_sessions(ctx, path.parent)
            directories[name] = {cwd for row in ctx._directory_sessions[directory] for cwd in row['cwds']}
        actual = {cwd for cwd in directories.get(name, ()) if encode(cwd) == name} if selected else set()
        supplied = {cwd for cwd in ctx.projects if encode(cwd) == name}
        owners = actual | supplied
        # 仅在有 cwd 而已知编码无法解释目录时报告未知布局；无会话仍为 orphan。
        status = 'unsupported' if not owners and directories.get(name) else None
        warnings = [warning for source, values in ctx.session_warnings.items()
                    if Path(source).is_relative_to(path.parent) for warning in values] if not for_projects else []
        result.append(store(path, layout, 'project', owners,
                            'encoded_cwd' if actual else ('project_arg' if supplied else 'none'), status,
                            _warnings=list(warnings), _session_warnings=warnings, _ownership_skipped=not selected))
    return result


def locate(ctx):
    return project_stores(ctx, 'claude-project')


def role(item, path):
    return 'index' if path.name == 'MEMORY.md' else ('topic' if path.suffix == '.md' else 'unknown')
