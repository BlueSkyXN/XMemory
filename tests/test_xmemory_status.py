from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('xmemory_status', ROOT / 'plugins/xmemory/skills/xmemory/scripts/status.py')
status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(status)


def snapshot(root):
    return {p.relative_to(root).as_posix(): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
            for p in root.rglob('*') if p.is_file() and not p.is_symlink()}


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'memory'
        self.root.mkdir()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def test_plain_markdown_without_config_and_read_only(self):
        self.write('memory_summary.md', '# 入口\n[有效要求](MEMORY.md#协作)\n')
        self.write('MEMORY.md', '# 主记忆\n## 协作\n默认中文。\n[来源](notes/2026-10/2026-10-18-通用-语言.md)\n')
        self.write('notes/2026-10/2026-10-18-通用-语言.md', '# 语言\n- 来源：本次对话。\n')
        before = snapshot(self.root)
        report = status.inspect(self.root)
        self.assertTrue(report['ok'])
        self.assertTrue(report['entry'] and report['memory'])
        self.assertEqual(report['issues'], [])
        self.assertEqual(len(report['files']), 3)
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse((self.root / 'config.toml').exists())

    def test_missing_root_is_not_created(self):
        missing = self.root / 'missing'
        self.assertFalse(status.inspect(missing)['ok'])
        self.assertFalse(missing.exists())

    def test_empty_root_has_no_required_schema(self):
        report = status.inspect(self.root)
        self.assertTrue(report['ok'])
        self.assertFalse(report['entry'] or report['memory'])
        self.assertEqual(report['files'], [])

    def test_internal_links_checked_external_sources_and_examples_ignored(self):
        self.write('MEMORY.md', '''# 主记忆
[缺失](notes/missing.md)
[外部来源](../source.md)
[远程](https://example.invalid/source)
[绝对来源](/example/source.md)
[锚点](#主记忆)
```md
[占位](not-a-real-file.md)
```
''')
        report = status.inspect(self.root)
        self.assertEqual(len(report['issues']), 1)
        self.assertIn('notes/missing.md', report['issues'][0])

    def test_encoded_filename_and_fenced_links(self):
        self.write('notes/a b.md', '# 笔记\n')
        self.write('memory_summary.md', '[笔记](notes/a%20b.md)\n~~~md\n[示例](missing.md)\n~~~\n')
        self.assertEqual(status.inspect(self.root)['issues'], [])

    def test_parenthesized_and_escaped_link_destinations(self):
        self.write('notes/review(1).md', '# 笔记\n')
        self.write('notes/review(v1(2)).md', '# 笔记\n')
        self.write('notes/a b.md', '# 笔记\n')
        self.write('memory_summary.md', r'''# 入口
[笔记](notes/review(1).md)
[嵌套括号](notes/review(v1(2)).md "说明")
[转义括号](notes/review\(1\).md '说明')
[空格](<notes/a b.md> "说明")
[缺失](notes/missing(2).md)
''')
        before = snapshot(self.root)
        report = status.inspect(self.root)
        self.assertTrue(report['ok'])
        self.assertEqual(len(report['issues']), 1)
        self.assertIn('notes/missing(2).md', report['issues'][0])
        self.assertEqual(snapshot(self.root), before)

    def test_reference_links_resolve_used_definitions(self):
        self.write('notes/current(1).md', '# 当前要求\n')
        self.write('memory_summary.md', '''# 入口
[当前要求][Current Rule]
[CURRENT RULE][]
[current rule]
[缺失][missing]

[current   rule]: notes/current(1).md "当前版本"
[missing]: notes/missing.md
[unused]: notes/unused.md
''')
        before = snapshot(self.root)
        report = status.inspect(self.root)
        self.assertEqual(len(report['issues']), 1)
        self.assertIn('notes/missing.md', report['issues'][0])
        self.assertEqual(snapshot(self.root), before)

    def test_inline_code_links_and_definitions_are_ignored(self):
        self.write('memory_summary.md', '''# 入口
示例：`[标题](notes/example.md)`。
双反引号：``[标题](notes/example.md) ` [定义][rule]``。
跨行代码：`[标题](notes/example.md)
[rule]: notes/example.md
`。
[定义][rule]
```md
[rule]: notes/example.md
```
[真实缺失](notes/missing.md)
''')
        report = status.inspect(self.root)
        self.assertEqual(len(report['issues']), 1)
        self.assertIn('notes/missing.md', report['issues'][0])

    def test_unclosed_code_span_does_not_hide_following_links(self):
        self.write('memory_summary.md', '未闭合的 ` 只是文本。\n[缺失](notes/missing.md)\n')
        report = status.inspect(self.root)
        self.assertEqual(len(report['issues']), 1)
        self.assertIn('notes/missing.md', report['issues'][0])

    def test_malformed_external_links_do_not_abort_inspection(self):
        self.write('memory_summary.md', '''# 入口
[来源](http://[)
[来源](//[)
[缺失](notes/missing.md)
''')
        before = snapshot(self.root)
        with redirect_stdout(io.StringIO()) as output:
            code = status.main(['status', '--root', str(self.root), '--summary'])
        self.assertEqual(code, 0)
        self.assertIn('notes/missing.md', output.getvalue())
        self.assertEqual(snapshot(self.root), before)

    def test_unreadable_markdown_reports_failure_without_mutation(self):
        path = self.root / 'MEMORY.md'
        path.write_bytes(b'\xff\xfe')
        before = snapshot(self.root)
        report = status.inspect(self.root)
        self.assertFalse(report['ok'])
        self.assertIn('Markdown 无法读取', report['issues'][0])
        self.assertEqual(snapshot(self.root), before)

    def test_symlink_sources_are_never_read(self):
        outside = self.base / 'outside'
        outside.mkdir()
        (outside / 'secret.md').write_text('outside sentinel', encoding='utf-8')
        try:
            (self.root / 'linked').symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('symlinks unavailable')
        self.write('MEMORY.md', '[来源](linked/secret.md)\n')
        original = Path.read_bytes
        def guarded(path):
            self.assertNotIn('linked', path.parts)
            self.assertNotIn('outside', path.parts)
            return original(path)
        with mock.patch.object(Path, 'read_bytes', guarded):
            report = status.inspect(self.root)
        self.assertEqual(len(report['files']), 1)
        self.assertTrue(any('符号链接' in issue for issue in report['issues']))

    def test_summary_limit_and_markdown_output(self):
        self.write('memory_summary.md', '文' * 3400)
        report = status.inspect(self.root)
        self.assertTrue(any('10,000' in issue for issue in report['issues']))
        rendered = status.render(report, summary=True)
        self.assertTrue(rendered.startswith('# XMemory'))
        self.assertNotIn('| 文件 |', rendered)
        self.assertIn('不判断记忆正确性', rendered)

    def test_default_root_is_user_home_not_cwd_or_legacy_environment(self):
        with mock.patch.object(Path, 'home', return_value=self.base), \
             mock.patch.dict(os.environ, {'XMEMORY_ROOT': str(self.root)}), \
             redirect_stdout(io.StringIO()) as output:
            code = status.main(['status'])
        self.assertEqual(code, 2)
        self.assertIn(str(self.base / '.agents' / 'memory'), output.getvalue())
        self.assertFalse((self.base / '.agents').exists())

    def test_explicit_diagnostic_root_before_and_after_command(self):
        for args in (['--root', str(self.root), 'status'], ['status', '--root', str(self.root), '--summary']):
            with self.subTest(args=args), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(status.main(args), 0)
            self.assertIn(str(self.root), output.getvalue())


if __name__ == '__main__':
    unittest.main()
