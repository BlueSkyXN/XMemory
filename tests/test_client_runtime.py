"""已有 zstd 后端实测与缺失环境 mock；从不执行依赖安装。"""
import base64
from contextlib import contextmanager
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from client_readers import common, runtime, sessions

PLAIN = b'{"type":"session_meta","payload":{"id":"fixture-zstd","cwd":"/fixture/project"}}\n{"type":"response_item","payload":{"type":"message","role":"user","content":"synthetic text"}}\n'
PACKED = base64.b64decode('KLUv/SCwzQMAcogZGYDHOVD8WC2RIKF5bMRIQhAZ1/SwdDLouDrEe/3iA9S6CWdMFvXMZ6h66pxKUY2g66kHKdNJ4i/DybClHfFer1xA14rCoHp6PA8BO+XLEhT1WG1Qj4QIk1pP050YDFems6huzNsEBQB2ZEAV8lNBZ868idaEAg==')
MULTIFRAME_PLAIN = b'{"type":"session_meta","payload":{"id":"fixture-multiframe","cwd":"/fixture/project"}}\n{"type":"response_item","payload":{"type":"message","role":"user","content":"second frame"}}\n'
MULTIFRAME_PACKED = base64.b64decode('KLUv/SBXdQIAwsQQF5ClOlwEtTLtfpsUKktmd502SebzfDMIQYzvsoRiixBA+fgmZYcbuSQscx3g87zhw7xRhZ6uj2tvGgrFrW17ftfrwwIAP1O8WxMKKLUv/SBdbQIAQgURFqAXtgE24eVWi+Sfb0klAAZNWFIF4wqAlHxjOQiQw3F1ee97OCycV4PLL5gWPsFUb8rEsCA7FjbfguB6ePTp8g9aHwIBACqFegI=')


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plain = self.root / 'rollout.jsonl'
        self.packed = self.root / 'rollout.jsonl.zst'
        self.plain.write_bytes(PLAIN)
        self.packed.write_bytes(PACKED)
        patch = mock.patch.object(runtime, '_capabilities', None)
        patch.start()
        self.addCleanup(patch.stop)

    def read(self, *args):
        args = sessions.parser('codex').parse_args([*args, '--root', str(self.root)])
        return sessions.run('codex', args)

    def test_zstd_actual_available_backend_and_offsets(self):
        if not runtime.backend():
            self.skipTest('当前解释器与系统均无已有 zstd 能力；缺失路径另有 mock 覆盖')
        warnings = []
        expected = list(common.json_rows(self.plain, warnings))
        actual = list(common.json_rows(self.packed, warnings))
        self.assertEqual(actual, expected)
        self.assertEqual(actual[1][0], len(PLAIN.splitlines(keepends=True)[0]))
        self.assertEqual(warnings, [])
        # 由调用解释器确定后端，不重启到另一解释器。
        self.assertEqual(runtime.describe()['executable'], sys.executable)

    def test_multiframe_actual_backend_reads_all_records_and_offsets(self):
        self.assertIsNotNone(runtime.backend(), '多 frame 回归要求已有 zstd 后端')
        self.plain.write_bytes(MULTIFRAME_PLAIN)
        self.packed.write_bytes(MULTIFRAME_PACKED)
        warnings = []
        rows = list(common.json_rows(self.packed, warnings))
        self.assertEqual(rows, list(common.json_rows(self.plain, [])))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], len(MULTIFRAME_PLAIN.splitlines(keepends=True)[0]))
        self.assertEqual(warnings, [])

    def test_zstandard_probe_exceptions_fall_back_and_complete_read(self):
        for stage in ('import', 'stream', 'version'):
            with self.subTest(stage=stage), mock.patch.object(runtime, '_capabilities', None):
                error = RuntimeError('synthetic broken backend')
                reader = mock.Mock(side_effect=error if stage == 'stream' else lambda *a, **k: io.BytesIO())
                module = types.SimpleNamespace(ZstdDecompressor=lambda: types.SimpleNamespace(stream_reader=reader))
                def imported(name):
                    if name != 'zstandard':
                        raise ImportError(name)
                    if stage == 'import':
                        raise error
                    return module
                fallback = dict(name='PATH:zstd', version='mock', path='/fixture/zstd', module=None)
                with mock.patch.object(runtime.importlib, 'import_module', side_effect=imported), \
                     mock.patch.object(runtime.importlib.metadata, 'version', side_effect=error if stage == 'version' else None, return_value='mock'), \
                     mock.patch.object(runtime, 'external_tools', return_value=[fallback]), \
                     mock.patch.object(runtime.subprocess, 'Popen', side_effect=lambda *a, **k: self.process()):
                    self.assertEqual(runtime.backend(), fallback)
                    self.plain.unlink(missing_ok=True)
                    result = self.read('read', '--session', 'fixture-zstd')
                    self.assertEqual([i['text'] for i in result['items']], ['synthetic text'])
                    self.assertTrue(result['coverage']['scan_complete'])

    def test_compressed_twin_prefers_plain_with_new_append(self):
        with self.plain.open('ab') as stream:
            stream.write(b'{"type":"response_item","payload":{"type":"message","role":"assistant","content":"new append"}}\n')
        listed = self.read('list')
        self.assertEqual(len(listed['items']), 1)
        self.assertEqual(listed['items'][0]['source'], str(self.plain.resolve()))
        self.assertTrue(any(w.startswith('compressed_twin:') for w in listed['warnings']))
        self.assertEqual([i['text'] for i in self.read('read', '--session', 'fixture-zstd')['items']], ['synthetic text', 'new append'])

    def test_same_id_different_stems_remains_ambiguous(self):
        (self.root / 'other.jsonl').write_bytes(PLAIN)
        with self.assertRaisesRegex(common.ReaderError, 'ambiguous_session'):
            self.read('read', '--session', 'fixture-zstd')

    def test_compressed_twin_notice_follows_selected_session_and_keeps_coverage(self):
        other = self.root / 'other.jsonl'
        other.write_bytes(PLAIN.replace(b'fixture-zstd', b'other-session'))
        for arguments in [('read', '--session', 'other-session'),
                          ('search', '--session', 'other-session', '--query', 'synthetic')]:
            with self.subTest(arguments=arguments):
                output = self.read(*arguments)
                self.assertEqual(output['warnings'], [])
                self.assertTrue(output['coverage']['metadata_complete'])
                self.assertTrue(output['coverage']['scan_complete'])
                self.assertEqual(output['coverage']['content_status'], 'matches')
        twin = self.read('read', '--session', 'fixture-zstd')
        self.assertEqual(len(twin['warnings']), 1)
        self.assertTrue(twin['warnings'][0].startswith('compressed_twin:'))
        self.assertTrue(twin['coverage']['metadata_complete'])
        self.assertTrue(twin['coverage']['scan_complete'])
        self.assertEqual(twin['coverage']['content_status'], 'matches')
        listed = self.read('list', '--query', 'other-session')
        self.assertEqual(listed['warnings'], [])
        self.assertEqual(listed['warnings_outside_filter'], 0)
        self.assertTrue(listed['coverage']['scan_complete'])

    def test_compressed_twin_notice_follows_list_page_and_actual_search_reads(self):
        other = self.root / 'other.jsonl'
        other.write_bytes(PLAIN.replace(b'fixture-zstd', b'zz-first'))
        first = self.read('list', '--limit', '1')
        self.assertEqual(first['items'][0]['session_id'], 'zz-first')
        self.assertEqual(first['warnings'], [])
        self.assertEqual(first['warnings_outside_filter'], 0)
        last = self.read('list', '--limit', '1', '--offset', '1')
        self.assertEqual(len(last['warnings']), 1)
        self.assertTrue(last['coverage']['scan_complete'])
        searched = self.read('search', '--query', 'synthetic', '--limit', '1')
        # 第二个会话也实际读取了，才发现下一条命中；即使未输出，也需带它的提示。
        self.assertEqual(len(searched['warnings']), 1)
        self.assertTrue(searched['coverage']['metadata_complete'])
        self.assertEqual(searched['coverage']['content_status'], 'matches')
        self.assertTrue(searched['has_more'])

    def test_zstandard_cross_frame_probe_and_read_pass_argument(self):
        stream_reader = mock.Mock(side_effect=lambda source, **kwargs: io.BytesIO(b'' if not source.read() else PLAIN + PLAIN))
        module = types.SimpleNamespace(ZstdDecompressor=lambda: types.SimpleNamespace(stream_reader=stream_reader))
        with mock.patch.object(runtime.importlib, 'import_module', return_value=module), \
             mock.patch.object(runtime.importlib.metadata, 'version', return_value='mock'):
            selected = runtime.module_backend('zstandard')
        self.assertIsNotNone(selected)
        self.assertEqual(stream_reader.call_args.kwargs, {'read_across_frames': True})
        with runtime.open_zstd(self.packed, selected) as stream:
            self.assertEqual(stream.read(), PLAIN + PLAIN)
        self.assertEqual(stream_reader.call_count, 2)
        self.assertTrue(all(call.kwargs == {'read_across_frames': True} for call in stream_reader.call_args_list))

    def test_zstandard_without_cross_frame_support_falls_back(self):
        stream_reader = mock.Mock(side_effect=TypeError('unsupported read_across_frames'))
        module = types.SimpleNamespace(ZstdDecompressor=lambda: types.SimpleNamespace(stream_reader=stream_reader))
        def imported(name):
            if name == 'zstandard':
                return module
            raise ImportError(name)
        external = dict(name='PATH:zstd', version='mock', path='/fixture/zstd', module=None)
        with mock.patch.object(runtime.importlib, 'import_module', side_effect=imported), \
             mock.patch.object(runtime, 'external_tools', return_value=[external]):
            self.assertEqual(runtime.backend(), external)
        self.assertEqual(stream_reader.call_args.kwargs, {'read_across_frames': True})

    def test_zstd_missing_advice_never_executes_installation(self):
        self.plain.unlink()
        with mock.patch.object(runtime, '_capabilities', {'zstd': []}), \
             mock.patch.object(runtime.subprocess, 'run', side_effect=AssertionError('must not install')) as run, \
             mock.patch.object(runtime.subprocess, 'Popen', side_effect=AssertionError('must not install')) as spawn:
            output = self.read('list')
        advice = '\n'.join(output['warnings'])
        self.assertIn('python3 -m pip install --user backports.zstd', advice)
        self.assertIn('brew install zstd', advice)
        self.assertIn('Python 3.14+', advice)
        run.assert_not_called()
        spawn.assert_not_called()

    def test_zstd_all_missing_is_explicit_and_twin_still_readable(self):
        with mock.patch.object(runtime, '_capabilities', {'zstd': []}):
            self.assertEqual(len(self.read('list')['items']), 1)
            self.plain.unlink()
            result = self.read('list')
        self.assertEqual(result['items'], [])
        self.assertTrue(any('zstd_missing:' in w and '1 个' in w for w in result['warnings']))

    def test_zstd_registry_fallback_order_and_single_probe(self):
        names = runtime.REGISTRY['zstd']['order']
        for first in range(len(names)):
            with self.subTest(first=first), mock.patch.object(runtime, '_capabilities', None):
                def module(name):
                    return {'name': name, 'version': 'fixture', 'path': None, 'module': object()} if names.index(name) >= first else None
                external = [dict(name=name, version='fixture', path='/fixture/zstd', module=None)
                            for name in names[3:] if names.index(name) >= first]
                with mock.patch.object(runtime, 'module_backend', side_effect=module) as probe, \
                     mock.patch.object(runtime, 'external_tools', return_value=external):
                    self.assertEqual(runtime.backend()['name'], names[first])
                    runtime.backend()
                    self.assertEqual(probe.call_count, 3)

    def test_zstd_python_backend_adapters_match_byte_offsets(self):
        for name in ('compression.zstd', 'backports.zstd', 'zstandard'):
            with self.subTest(backend=name):
                module = types.SimpleNamespace(open=lambda *a, **k: io.BytesIO(PLAIN))
                module.ZstdDecompressor = lambda: types.SimpleNamespace(stream_reader=lambda source, **kwargs: io.BytesIO(PLAIN))
                chosen = dict(name=name, version='mock', module=module, path=None)
                with mock.patch.object(runtime, '_capabilities', {'zstd': [chosen]}):
                    warnings = []
                    actual = list(common.json_rows(self.packed, warnings))
                self.assertEqual(actual, list(common.json_rows(self.plain, [])))
                self.assertEqual(warnings, [])

    def process(self, returncode=0, content=PLAIN):
        process = mock.Mock()
        process.stdout = io.BytesIO(content)
        process.returncode = returncode
        process.poll.return_value = returncode
        process.wait.return_value = returncode
        return process

    def test_external_backend_streaming_argv_and_failure(self):
        selected = dict(name='PATH:zstd', version='mock', path='/fixture/zstd', module=None)
        for status in (0, 2):
            with self.subTest(status=status), mock.patch.object(runtime, '_capabilities', {'zstd': [selected]}), \
                 mock.patch.object(runtime.subprocess, 'Popen', return_value=self.process(status)) as spawn:
                warnings = []
                rows = list(common.json_rows(self.packed, warnings))
                self.assertEqual(len(rows), 2)
                self.assertEqual(bool(warnings), bool(status))
                self.assertEqual(spawn.call_args.args[0], ['/fixture/zstd', '-dcq', '--', str(self.packed)])
                self.assertNotIn('shell', spawn.call_args.kwargs)

    def test_external_prefix_discovery_and_no_install_calls(self):
        prefix = self.root / 'existing-bin'
        prefix.mkdir()
        binary = prefix / 'zstd'
        binary.write_text('synthetic placeholder, never executed')
        binary.chmod(0o700)
        with mock.patch.object(runtime.shutil, 'which', return_value=None), \
             mock.patch.object(runtime.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout='zstd fixture\n')) as run:
            result = runtime.external_tools('zstd', [prefix])
        self.assertEqual(result[0]['name'], 'prefix:zstd')
        self.assertEqual(result[0]['path'], str(binary))
        self.assertEqual(run.call_args.args[0], [str(binary), '--version'])
        self.assertEqual(run.call_args.kwargs['timeout'], 5)
        self.assertFalse(any(word in run.call_args.args[0] for word in ('pip', 'brew', 'uv', 'install', 'uninstall', 'upgrade')))

    def test_early_first_line_close_is_not_stream_failure(self):
        selected = dict(name='PATH:zstd', version='mock', path='/fixture/zstd', module=None)
        process = self.process()
        with mock.patch.object(runtime, '_capabilities', {'zstd': [selected]}), \
             mock.patch.object(runtime.subprocess, 'Popen', return_value=process):
            warnings = []
            rows = common.json_rows(self.packed, warnings)
            next(rows)
            rows.close()
        self.assertEqual(warnings, [])
        self.assertTrue(process.stdout.closed)

    def test_corrupt_existing_backend_reports_error_not_empty_success(self):
        chosen = dict(name='backports.zstd', version='mock', path=None,
                      module=types.SimpleNamespace(open=mock.Mock(side_effect=ValueError('synthetic invalid frame'))))
        with mock.patch.object(runtime, '_capabilities', {'zstd': [chosen]}):
            warnings = []
            self.assertEqual(list(common.json_rows(self.packed, warnings)), [])
        self.assertTrue(warnings[0].startswith('zstd_stream_error:'))

    def test_interpreter_source_and_candidate_probe_are_read_only(self):
        expected = {'/opt/homebrew/Cellar/python/3/bin/python3': 'Homebrew',
                    '/Library/Frameworks/Python.framework/Versions/3/bin/python3': 'python.org',
                    '/fixture/.pyenv/versions/3/bin/python3': 'pyenv',
                    '/fixture/.local/share/uv/python/cpython/bin/python3': 'uv',
                    '/fixture/miniconda3/bin/python3': 'conda', '/fixture/.venv/bin/python3': 'virtualenv'}
        for path, source in expected.items():
            self.assertEqual(runtime.origin(path), source)
        binary = self.root / 'python3'
        binary.write_text('placeholder')
        value = dict(path=str(binary), version='3.11.9', packages=42, virtual=False,
                     externally_managed=True, capabilities={'backports.zstd': True})
        with mock.patch.object(runtime, 'interpreter_paths', return_value=[binary]), \
             mock.patch.object(runtime, 'alias_target', return_value=str(binary)), \
             mock.patch.object(runtime.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout=json.dumps(value))) as run:
            result = runtime.candidates()
        self.assertTrue(result[0]['externally_managed'])
        self.assertTrue(result[0]['alias_target'])
        self.assertEqual(run.call_args.args[0][:4], [str(binary), '-I', '-B', '-c'])
        self.assertEqual(run.call_args.kwargs['timeout'], 5)

    def test_toml_existing_subset_fallback(self):
        path = self.root / 'automation.toml'
        path.write_text('name = "fixture"\ncwds = [\n"/fixture/one",\n"/fixture/two",\n]\n')
        with mock.patch.object(runtime.importlib, 'import_module', side_effect=ImportError):
            data = runtime.read_toml(path)
        self.assertEqual(data['cwds'], ['/fixture/one', '/fixture/two'])
