"""只探测已有能力；不切换解释器、不改变环境、不安装任何依赖。"""
from contextlib import contextmanager
import importlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import sysconfig
import threading

PREFIXES = (Path('/opt/homebrew/bin'), Path('/usr/local/bin'),
            Path('/home/linuxbrew/.linuxbrew/bin'), Path('/opt/local/bin'))
REGISTRY = {
    'zstd': {'purpose': '读取 Codex .jsonl.zst',
             'order': ('compression.zstd', 'backports.zstd', 'zstandard', 'PATH:zstd', 'prefix:zstd'),
             'missing': 'zstd_missing: 压缩会话未读；已有 Python 3.14+ 时可指定它；或 python3 -m pip install --user backports.zstd；或 macOS brew install zstd。由用户自行选择执行。'},
}
_capabilities = None


def module_backend(name):
    try:
        module = importlib.import_module(name)
        if name == 'zstandard':
            with module.ZstdDecompressor().stream_reader(io.BytesIO(b''), read_across_frames=True):
                pass
        if name == 'compression.zstd':
            version = 'stdlib'
        else:
            try:
                version = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                version = str(getattr(module, '__version__', 'unknown'))
        return dict(name=name, version=version, module=module, path=None)
    except Exception as exc:
        if name == 'zstandard' or isinstance(exc, (ImportError, OSError)):
            return None
        raise


def external_tools(name, prefixes=PREFIXES):
    found, seen = [], set()
    on_path = shutil.which(name)
    directories = {Path(p).resolve() for p in os.get_exec_path() if Path(p).is_absolute()}
    if on_path and Path(on_path).absolute().parent.resolve() not in directories:
        on_path = None
    candidates = ([('PATH:' + name, Path(on_path))] if on_path else [])
    candidates += [('prefix:' + name, prefix / name) for prefix in prefixes]
    for kind, path in candidates:
        if not path.is_file() or not os.access(str(path), os.X_OK):
            continue
        real = str(path.resolve())
        if real in seen:
            continue
        seen.add(real)
        try:
            run = subprocess.run([str(path), '--version'], capture_output=True, text=True,
                                 timeout=5, check=False)
            if run.returncode:
                continue
            version = run.stdout.strip().splitlines()[0][:160] if run.stdout.strip() else 'unknown'
        except (OSError, subprocess.TimeoutExpired):
            continue
        found.append(dict(name=kind, version=version, module=None, path=str(path.absolute())))
    return found


def capabilities(include_external=False):
    global _capabilities
    if _capabilities is None:
        backends = [b for b in (module_backend(n) for n in REGISTRY['zstd']['order'][:3]) if b]
        _capabilities = {'zstd': backends, '_external_probed': False}
    if not _capabilities.get('_external_probed', True) and (include_external or not _capabilities['zstd']):
        _capabilities['zstd'].extend(external_tools('zstd'))
        _capabilities['_external_probed'] = True
    return _capabilities


def backend():
    available = capabilities()['zstd']
    return available[0] if available else None


def public_backend(item):
    return {key: item[key] for key in ('name', 'version', 'path')} if item else None


def describe():
    selected = backend()
    return {'python': sys.version.split()[0], 'executable': sys.executable,
            'zstd': (selected['name'] + ' ' + selected['version']) if selected else None}


def read_toml(path, keys=None):
    try:
        toml = importlib.import_module('tomllib')
    except ImportError:
        from .toml_subset import TomlSubset
        text = Path(path).read_text(encoding='utf-8')
        try:
            return TomlSubset(text).parse()
        except ValueError:
            if keys is None:
                raise
            return TomlSubset(text).top_level(keys)
    with Path(path).open('rb') as stream:
        return toml.load(stream)


class ProcessStream:
    def __init__(self, stream):
        self.stream = stream
        self.eof = False

    def readline(self, size=-1):
        data = self.stream.readline(size)
        self.eof = not data
        return data

    def read(self, size=-1):
        data = self.stream.read(size)
        self.eof = not data or size < 0
        return data


@contextmanager
def open_zstd(path, selected=None, timeout=30):
    chosen = backend() if selected is None else selected
    if not chosen:
        raise OSError(REGISTRY['zstd']['missing'])
    if chosen['name'] in ('compression.zstd', 'backports.zstd'):
        with chosen['module'].open(path, 'rb') as stream:
            yield stream
    elif chosen['name'] == 'zstandard':
        with Path(path).open('rb') as raw:
            with chosen['module'].ZstdDecompressor().stream_reader(raw, read_across_frames=True) as decoded:
                with io.BufferedReader(decoded) as stream:
                    yield stream
    else:
        process = subprocess.Popen([chosen['path'], '-dcq', '--', str(path)],
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        expired = threading.Event()
        def expire():
            expired.set()
            if process.poll() is None:
                process.kill()
        timer = threading.Timer(timeout, expire)
        timer.daemon = True
        timer.start()
        stream = ProcessStream(process.stdout)
        try:
            yield stream
        finally:
            if stream.eof:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    expire()
            elif process.poll() is None:
                process.kill()
            process.stdout.close()
            process.wait(timeout=5)
            timer.cancel()
            if expired.is_set():
                raise OSError('zstd_timeout')
            if stream.eof and process.returncode:
                raise OSError('zstd_exit_code:' + str(process.returncode))


def origin(path, virtual=False):
    parts = str(path).replace('\\', '/').lower()
    if virtual:
        return 'virtualenv'
    if '/.local/share/uv/' in parts:
        return 'uv'
    if '/.pyenv/' in parts:
        return 'pyenv'
    if any(x in parts for x in ('conda', 'miniforge', 'mambaforge')):
        return 'conda'
    if '/.venv/' in parts or '/venv/' in parts:
        return 'virtualenv'
    if '/python.framework/' in parts and '/cellar/' not in parts:
        return 'python.org'
    if '/homebrew/' in parts or '/cellar/' in parts or '/linuxbrew/' in parts:
        return 'Homebrew'
    if str(path) == '/usr/bin/python3' or '/commandlinetools/' in parts or '/xcode.app/' in parts:
        return 'Apple command line tools' if sys.platform == 'darwin' else 'system'
    return 'unknown'


def alias_target(home=None):
    """只识别 shell 文件里的字面 alias，不执行 shell 配置。"""
    home = Path.home() if home is None else Path(home)
    for name in ('.zshrc', '.bashrc', '.bash_profile'):
        try:
            text = (home / name).read_text(encoding='utf-8')
        except OSError:
            continue
        matches = re.findall(r'''(?m)^\s*alias\s+python3=['"]([^'"\n]+)['"]\s*(?:#.*)?$''', text)
        for value in reversed(matches):
            value = os.path.expanduser(value)
            if os.path.isabs(value) and Path(value).is_file():
                return value
    return None


def profile():
    marker = Path(sysconfig.get_path('stdlib')) / 'EXTERNALLY-MANAGED'
    return dict(path=sys.executable, version=sys.version.split()[0],
                source=origin(Path(sys.executable).resolve(), sys.prefix != sys.base_prefix),
                packages=sum(1 for _ in importlib.metadata.distributions()),
                externally_managed=marker.is_file())


def path_position(path, paths=None):
    paths = os.get_exec_path() if paths is None else paths
    real = Path(path).resolve()
    for i, directory in enumerate(paths):
        for name in ('python3', Path(path).name):
            if (Path(directory) / name).is_file() and (Path(directory) / name).resolve() == real:
                return i
    return None


def interpreter_paths(home=None, paths=None, prefixes=PREFIXES):
    home = Path.home() if home is None else Path(home)
    paths = os.get_exec_path() if paths is None else paths
    directories = [Path(p) for p in paths] + list(prefixes) + [Path('/usr/bin')]
    directories += list(Path('/Library/Frameworks/Python.framework/Versions').glob('*/bin'))
    directories += list((home / '.local/share/uv/python').glob('*/bin'))
    directories += list((home / '.pyenv/versions').glob('*/bin'))
    directories += [home / p / 'bin' for p in ('miniconda3', 'anaconda3', 'miniforge3')]
    found, seen = [], set()
    alias = alias_target(home)
    candidates = [Path(alias)] if alias else []
    candidates += [p for directory in directories for p in sorted(directory.glob('python3*'))
                   if re.fullmatch(r'python3(?:\.\d+)?', p.name)]
    for path in candidates:
        if not path.is_file() or not os.access(str(path), os.X_OK):
            continue
        real = str(path.resolve())
        if real not in seen:
            seen.add(real)
            found.append(path)
    return found


PROBE = '''import sys,sysconfig,pathlib,json,importlib.util,importlib.metadata
def available(name):
    try: return importlib.util.find_spec(name) is not None
    except (ImportError,ValueError,AttributeError): return False
print(json.dumps(dict(path=sys.executable,version=sys.version.split()[0],
packages=sum(1 for _ in importlib.metadata.distributions()),virtual=sys.prefix!=sys.base_prefix,
externally_managed=(pathlib.Path(sysconfig.get_path('stdlib'))/'EXTERNALLY-MANAGED').is_file(),
capabilities={name:available(name) for name in ('compression.zstd','backports.zstd','zstandard')})))
'''


def candidates():
    alias = alias_target()
    result = []
    for path in interpreter_paths():
        try:
            run = subprocess.run([str(path), '-I', '-B', '-c', PROBE], capture_output=True,
                                 text=True, timeout=5, check=False)
            item = json.loads(run.stdout) if run.returncode == 0 else {'error': 'probe_failed'}
        except (OSError, ValueError, subprocess.TimeoutExpired):
            item = {'error': 'probe_unavailable'}
        item.update(path=str(path), source=origin(path.resolve(), item.pop('virtual', False)),
                    path_position=path_position(path), alias_target=bool(alias and Path(alias).resolve() == path.resolve()))
        result.append(item)
    return result


def doctor(ctx, include_candidates=False):
    current = profile()
    alias = alias_target(ctx.home)
    specified = os.environ.get('CLIENT_READERS_PYTHON')
    reason = 'explicit' if specified and Path(specified).expanduser().resolve() == Path(sys.executable).resolve() else (
        'alias' if alias and Path(alias).resolve() == Path(sys.executable).resolve() else 'PATH')
    current.update(reason=reason, path_position=path_position(sys.executable), alias_target=alias)
    cap = capabilities(include_external=True)['zstd']
    missing = sum(1 for root in (ctx.root / 'sessions', ctx.root / 'archived_sessions')
                  for p in root.rglob('*.jsonl.zst') if not p.with_suffix('').is_file()) if ctx.client == 'codex' and not cap else 0
    output = dict(schema='client-readers/doctor-v1', client=ctx.client, data_root=str(ctx.root),
                  data_root_exists=ctx.root.exists(), interpreter=current, runtime=describe(),
                  capabilities={'zstd': dict(selected=public_backend(cap[0]) if cap else None,
                      available=[public_backend(b) for b in cap], unread_compressed_sessions=missing,
                      advice=REGISTRY['zstd']['missing'] if not cap else None)}, warnings=list(ctx.warnings))
    if include_candidates:
        output['candidates'] = candidates()
        if current['source'] in ('Homebrew', 'Apple command line tools', 'system'):
            others = [p for p in output['candidates'] if p.get('packages', 0) > current['packages'] and
                      p.get('path_position') is not None and
                      (current['path_position'] is None or p['path_position'] < current['path_position'])]
            if others:
                output['warnings'].append('python_choice_review: 有排序更靠前且已有包更多的解释器；是否指定由用户决定')
    return output
