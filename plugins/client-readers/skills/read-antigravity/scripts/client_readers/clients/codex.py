"""Codex V1/V2 与自动化记忆；项目总览只读 rollout 首行。"""
from datetime import datetime, timezone
from pathlib import Path
import re

from . import json_sessions
from ..common import epoch, json_rows
from ..memory import store
from .. import runtime


def sessions(ctx):
    return json_sessions(ctx, ctx.root / 'sessions', True) + json_sessions(ctx, ctx.root / 'archived_sessions', True)


def recent_injection(ctx):
    cutoff = datetime.now(timezone.utc).timestamp() - 7 * 86400
    counts = {name: {'user': 0, 'automation': 0} for name in ('memories', 'memories_v2')}
    eligible = 0
    for session in ctx.sessions:
        if epoch(session['last']) < cutoff or session.get('thread_source') in ('subagent', 'guardian_review'):
            continue
        metadata = session.get('metadata', {})
        source = metadata.get('source')
        if isinstance(source, dict) and 'subagent' in source:
            continue
        eligible += 1
        kind = 'automation' if session.get('thread_source') == 'automation' else 'user'
        found = set()
        warnings = []
        rows = json_rows(Path(session['source']), warnings)
        try:
            for index, (_, row) in enumerate(rows):
                payload = row.get('payload')
                texts = []
                if row.get('type') == 'session_meta' and isinstance(payload, dict):
                    base = payload.get('base_instructions')
                    if isinstance(base, dict) and isinstance(base.get('text'), str):
                        texts.append(base['text'])
                if row.get('type') == 'response_item' and isinstance(payload, dict) and payload.get('type') == 'message':
                    if payload.get('role') not in ('developer', 'system', 'user'):
                        break
                    content = payload.get('content')
                    if isinstance(content, str):
                        texts.append(content)
                    elif isinstance(content, list):
                        texts.extend(b['text'] for b in content if isinstance(b, dict) and
                                     b.get('type') in ('text', 'input_text', 'output_text') and isinstance(b.get('text'), str))
                for text in texts:
                    if 'Automation memory:' in text or text.lstrip().startswith('Automation:'):
                        kind = 'automation'
                    # 只识别头部注入的库根；后续工具结果、普通助手正文不参与。
                    if row.get('type') != 'session_meta' and payload.get('role') not in ('developer', 'system'):
                        continue
                    header = text.split('========= MEMORY_SUMMARY BEGINS', 1)[0]
                    for name in counts:
                        if any(prefix + '/' in header for prefix in (str(ctx.root / name), '~/.codex/' + name, '$CODEX_HOME/' + name)):
                            found.add(name)
                if index >= 63:
                    break
        except (OSError, ValueError) as exc:
            warnings.append('session_metadata_unreadable: ' + session['source'] + '; ' + type(exc).__name__)
        finally:
            rows.close()
        ctx.session_warnings.setdefault(session['source'], []).extend(warnings)
        for name in found:
            counts[name][kind] += 1
    return {name: dict(values, days=7, checked_main_sessions=eligible) if eligible else None
            for name, values in counts.items()}


def locate(ctx):
    result = []
    injection = recent_injection(ctx) if getattr(ctx, 'include_recent_injection', False) else {}
    for name, layout in (('memories', 'codex-v1'), ('memories_v2', 'codex-v2')):
        path = ctx.root / name
        if path.is_dir():
            item = store(path, layout, 'global', _exclude=('automations', 'local') if name == 'memories' else ())
            item['recent_injection'] = injection.get(name)
            if getattr(ctx, 'include_recent_injection', False):
                item['_warnings'] = [w for warnings in ctx.session_warnings.values() for w in warnings]
            result.append(item)
    for name in ('automations', 'local'):
        path = ctx.root / 'memories' / name
        if path.is_dir():
            result.append(store(path, 'codex-v1', 'global', status='unofficial', _unofficial=True))
    for path in sorted((ctx.root / 'automations').glob('*')):
        if not path.is_dir():
            continue
        config = {}
        warnings = []
        try:
            config = runtime.read_toml(path / 'automation.toml', keys=('cwds', 'name', 'rrule'))
        except (OSError, ValueError):
            warnings.append('automation_config_unreadable: ' + str(path / 'automation.toml'))
        cwds = config.get('cwds', [])
        if not isinstance(cwds, list) or any(not isinstance(p, str) for p in cwds):
            warnings.append('automation_cwds_invalid: ' + str(path))
            cwds = []
        result.append(store(path, 'codex-automation', 'project', cwds, 'automation_cwds',
                            files=[path / 'memory.md'], _warnings=warnings,
                            automation={key: config.get(key) for key in ('name', 'rrule')}))
    return result


def role(item, path):
    rel = path.relative_to(item['path']).as_posix()
    if item.get('_unofficial'):
        return 'process_log' if path.suffix == '.md' else 'unknown'
    if item['layout'] == 'codex-automation':
        return 'automation' if path.name == 'memory.md' else 'unknown'
    exact = {'memory_summary.md': 'index', 'MEMORY.md': 'consolidated', 'raw_memories.md': 'raw_extract'}
    if rel in exact:
        return exact[rel]
    for prefix, category in (('rollout_summaries/', 'session_summary'), ('extensions/skysight/resources/', 'activity'),
                             ('extensions/ad_hoc/notes/', 'note')):
        if rel.startswith(prefix):
            return category
    if rel.startswith('extensions/') and path.name == 'instructions.md':
        return 'instructions'
    if rel.startswith('skills/') and path.name == 'SKILL.md':
        return 'skill'
    return 'backup' if path.name.endswith('.bak') else 'unknown'


def annotate(ctx, item, entry, text):
    if entry['role'] != 'session_summary':
        return
    header = {}
    for line in text.splitlines()[:12]:
        match = re.fullmatch(r'(thread_id|cwd|rollout_path|updated_at):\s*(.*)', line)
        if match:
            header[match[1]] = match[2].strip()
    if header.get('thread_id'):
        entry['native_session'] = {'client': 'codex', 'id': header['thread_id'], 'from': 'thread_id'}
    if header.get('cwd'):
        entry['project'] = {'path': header['cwd'], 'basis': 'session_cwd'}
    if header.get('rollout_path'):
        entry['rollout_path'] = header['rollout_path']
