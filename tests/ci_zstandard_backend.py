"""仅由独立 CI 任务执行；缺少真实 zstandard 时直接失败。"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import zstandard

from tests.test_client_runtime import MULTIFRAME_PACKED, MULTIFRAME_PLAIN
from client_readers import common, runtime


class ZstandardBackendTests(unittest.TestCase):
    def test_real_zstandard_multiframe_records_and_offsets(self):
        original = runtime.module_backend
        with mock.patch.object(runtime, '_capabilities', None), \
             mock.patch.object(runtime, 'module_backend', side_effect=lambda name: original(name) if name == 'zstandard' else None), \
             mock.patch.object(runtime, 'external_tools', return_value=[]), \
             tempfile.TemporaryDirectory() as directory:
            selected = runtime.backend()
            self.assertIsNotNone(selected)
            self.assertEqual(selected['name'], 'zstandard')
            self.assertIs(selected['module'], zstandard)
            root = Path(directory)
            packed, plain = root / 'fixture.jsonl.zst', root / 'fixture.jsonl'
            packed.write_bytes(MULTIFRAME_PACKED)
            plain.write_bytes(MULTIFRAME_PLAIN)
            warnings = []
            rows = list(common.json_rows(packed, warnings))
            self.assertEqual(rows, list(common.json_rows(plain, [])))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[1][0], len(MULTIFRAME_PLAIN.splitlines(keepends=True)[0]))
            self.assertEqual(warnings, [])
