"""客户端布局与元数据探测；不保存索引。"""
import importlib
import os
from pathlib import Path

from ..common import iso, json_rows, epoch
from ..sessions import json_project
from .. import runtime


class Context:
    def __init__(self, client, projects=(), home=None):
        self.client = client
        self.home = Path.home() if home is None else Path(home)
        folder = {'codex': '.codex', 'claude': '.claude', 'zcode': '.zcode/cli',
                  'workbuddy': '.workbuddy', 'qodercn': '.qoder-cn'}[client]
        self.root = self.home / folder
        self.projects = list(dict.fromkeys(os.path.abspath(os.path.expanduser(p)) for p in projects))
        self.warnings = []
        self.session_warnings = {}
        self._directory_sessions = {}
        if not self.root.exists():
            self.warnings.append('source_unavailable: ' + str(self.root))
        self._sessions = None
        self.adapter = importlib.import_module('.' + client, __package__)
        if client == 'zcode' and os.environ.get('ZCODE_DATA_BASE_DIR'):
            self.warnings.append('data_root_override_available: ZCODE_DATA_BASE_DIR 已设置；默认根仍为 ~/.zcode/cli，请核对实际来源')

    @property
    def sessions(self):
        if self._sessions is None:
            self._sessions = self.adapter.sessions(self)
        return self._sessions


def json_sessions(ctx, root, first_only=False):
    """只提取会话身份、cwd 和时间；Codex 总览在首行后关闭流。"""
    if not root.exists():
        return []
    paths = sorted(p for p in root.rglob('*.jsonl') if p.is_file() and 'subagents' not in p.parts)
    if first_only:
        packed = sorted(p for p in root.rglob('*.jsonl.zst') if p.is_file() and
                        'subagents' not in p.parts and not p.with_suffix('').is_file())
        if packed and not runtime.backend():
            ctx.session_warnings[str(root)] = [f'zstd_missing: {len(packed)} 个 .jsonl.zst 会话未读；' +
                                              str(root) + '; ' + runtime.REGISTRY['zstd']['missing']]
        else:
            paths += packed
    result = []
    for path in paths:
        cwds, identities, stamps, metadata = [], set(), [], {}
        warnings = []
        rows = json_rows(path, warnings)
        try:
            for _, row in rows:
                payload = row.get('payload')
                if first_only and (row.get('type') != 'session_meta' or not isinstance(payload, dict)):
                    warnings.append('unsupported_session_header: ' + str(path))
                    break
                if ctx.client == 'codex' and row.get('type') == 'session_meta' and isinstance(payload, dict):
                    metadata = payload
                    sid = payload.get('id') or payload.get('session_id')
                else:
                    sid = row.get('sessionId')
                if isinstance(sid, str) and sid:
                    identities.add(sid)
                cwd = json_project(ctx.client, row)
                if cwd and cwd not in cwds:
                    cwds.append(cwd)
                stamp = row.get('timestamp') or metadata.get('timestamp')
                if epoch(stamp):
                    stamps.append(epoch(stamp))
                if first_only:
                    if not cwd:
                        warnings.append('session_cwd_missing: ' + str(path))
                    break
        except (OSError, ValueError) as exc:
            warnings.append('session_metadata_unreadable: ' + str(path) + '; ' + type(exc).__name__)
        finally:
            rows.close()
        ctx.session_warnings[str(path)] = warnings
        if cwds:
            result.append(dict(source=str(path), container=str(path.parent), cwds=cwds,
                               id=next(iter(identities)) if len(identities) == 1 else None,
                               first=iso(min(stamps)) if stamps else None,
                               last=iso(max(stamps) if stamps else path.stat().st_mtime),
                               thread_source=metadata.get('thread_source'), metadata=metadata))
    return result
