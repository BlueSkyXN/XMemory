"""合成客户端目录上的记忆、项目、只读边界测试；不使用个人材料。"""
import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from client_readers import cli, memory, projects
from client_readers.clients import Context
from client_readers.clients import zcode, claude, qodercn


class MemoryFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.project = self.home / 'workspace/Maple'
        self.project.mkdir(parents=True)

    def put(self, path, text):
        path = self.home / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def jsonl(self, path, rows):
        return self.put(path, ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))

    def session(self, client, cwd=None, directory=None, later=()):
        cwd = str(cwd or self.project)
        folder = '.claude' if client == 'claude' else '.qoder-cn' if client == 'qodercn' else '.workbuddy'
        directory = directory or claude.encode(cwd)
        rows = [dict(type='user', sessionId='fixture-session', cwd=p, timestamp='2026-10-01T00:00:00Z',
                     message={'content': 'synthetic'}) for p in [cwd, *map(str, later)]]
        self.jsonl(folder + '/projects/' + directory + '/session.jsonl', rows)
        return Path(folder) / 'projects' / directory / 'memory'

    def ctx(self, client, selected=()):
        return Context(client, [str(p) for p in selected], self.home)

    def run_memory(self, client, *arguments):
        args = cli.parser(client).parse_args(['memory', *map(str, arguments)])
        return memory.run(self.ctx(client, args.project), args)

    def zdb(self, rows):
        path = self.home / '.zcode/cli/db/db.sqlite'
        path.parent.mkdir(parents=True)
        with sqlite3.connect(path) as con:
            con.execute('CREATE TABLE session(id TEXT,directory TEXT,workspace_id TEXT,time_created INTEGER,time_updated INTEGER)')
            con.executemany('INSERT INTO session VALUES(?,?,?,1,2)', rows)

    def snapshot(self):
        return {str(p): (p.stat().st_size, p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
                for p in self.home.rglob('*') if p.is_file() and not p.is_symlink()}

    def codex_session(self, name, text='', source='user', extra=()):
        stamp = datetime.now(timezone.utc).isoformat()
        rows = [{'type': 'session_meta', 'timestamp': stamp,
                 'payload': {'id': name, 'cwd': str(self.project), 'thread_source': source}},
                {'type': 'response_item', 'payload': {'type': 'message', 'role': 'developer', 'content': text}}, *extra]
        return self.jsonl('.codex/sessions/' + name + '.jsonl', rows)


class MemoryTests(MemoryFixture):
    def test_frontmatter_subset_and_failures_keep_safe_fields(self):
        warnings = []
        data = memory.frontmatter('---\nname: demo\nkeywords: [one, two]\nmetadata:\n  type: project\n  originSessionId: sid\nbad: {nested: value}\nname: duplicate\n---\n', warnings)
        self.assertEqual(data, {'name': 'demo', 'keywords': ['one', 'two'],
                                'metadata': {'type': 'project', 'originSessionId': 'sid'}})
        self.assertEqual(len(warnings), 1)
        self.assertEqual(memory.frontmatter('---\nname: unfinished', warnings), {})
        self.assertEqual(len(warnings), 2)

    def test_index_links_missing_target_duplicate_and_no_index(self):
        folder = self.session('claude')
        self.put(folder / 'MEMORY.md', '[Topic](topic.md) [[other]] [gone](gone.md)')
        topic = self.put(folder / 'topic.md', '# Knowledge\nOriginal conditions\n')
        self.put(folder / 'other.md', topic.read_text())
        self.put(folder / 'unlinked.md', '# Unlinked\n')
        out = self.run_memory('claude', 'list', '--store', topic.parent)
        items = {e['rel']: e for e in out['items']}
        self.assertTrue(items['topic.md']['indexed'])
        self.assertTrue(items['other.md']['indexed'])
        self.assertFalse(items['unlinked.md']['indexed'])
        self.assertEqual(items['topic.md']['duplicate_of'], [str(topic.parent / 'other.md')])
        self.assertTrue(any('missing_index_target:' in w for w in out['warnings']))
        (topic.parent / 'MEMORY.md').unlink()
        self.assertTrue(all(e['indexed'] is None for e in self.run_memory('claude', 'list', '--store', topic.parent)['items']))

    def test_section_and_redacted_offsets_reassemble_long_file(self):
        folder = self.session('claude')
        original = '# First\n' + 'before password="synthetic secret with spaces" after\n' * 300 + '# Second\nTail\n'
        path = self.put(folder / 'large.md', original)
        before = self.snapshot()
        listed = self.run_memory('claude', 'list', '--store', path.parent, '--outline')['items'][0]
        self.assertEqual([h['title'] for h in listed['outline']], ['First', 'Second'])
        second = self.run_memory('claude', 'read', '--path', path, '--section', 1)['items'][0]
        self.assertEqual(second['text'], '# Second\nTail\n')
        offset, fragments = 0, []
        while offset is not None:
            part = self.run_memory('claude', 'read', '--path', path, '--text-offset', offset, '--max-chars', 4096)['items'][0]
            self.assertEqual(part['text_offset'], offset)
            fragments.append(part['text'])
            offset = part['next_text_offset']
        self.assertEqual(''.join(fragments), memory.redact(original))
        self.assertNotIn('synthetic secret', ''.join(fragments))
        self.assertEqual(self.snapshot(), before)

    def test_outline_ignores_fenced_code(self):
        text = '# One\n```python\n# code\n```\n## Two\n'
        self.assertEqual([x['title'] for x in memory.outline(text)], ['One', 'Two'])

    def test_store_boundary_and_symlink_escape(self):
        folder = self.session('claude')
        known = self.put(folder / 'topic.md', '# Known\n')
        outsider = self.put('outside/private.md', 'not a client memory')
        (known.parent / 'escape.md').symlink_to(outsider)
        with self.assertRaisesRegex(memory.ReaderError, 'not_in_store'):
            self.run_memory('claude', 'read', '--path', outsider)
        out = self.run_memory('claude', 'list', '--store', known.parent)
        self.assertEqual([e['rel'] for e in out['items']], ['topic.md'])
        self.assertEqual(out['warnings'], [])
        self.assertEqual(out['warnings_outside_filter'], 1)
        with self.assertRaisesRegex(memory.ReaderError, 'not_in_store'):
            self.run_memory('claude', 'list', '--store', self.home)

    def test_search_unicode_roles_and_pagination(self):
        folder = self.session('claude')
        for i in range(3):
            self.put(folder / (str(i) + '.md'), 'ß' * 30 + 'TARGET' + str(i) + '尾' * 40)
        first = self.run_memory('claude', 'search', '--query', 'target', '--role', 'topic', '--limit', 1, '--max-chars', 12)
        self.assertTrue(first['has_more'])
        self.assertIn('TARGET', first['items'][0]['text'])
        self.assertEqual(first['next_offset'], 1)
        second = self.run_memory('claude', 'search', '--query', 'target', '--offset', 1, '--limit', 1)
        self.assertNotEqual(first['items'][0]['path'], second['items'][0]['path'])

    def test_zcode_path_identity_slug_orphan_and_empty(self):
        long = str(self.project.parent / ('a' * 47 + '-tail'))
        chinese = str(self.project.parent / '中文')
        self.zdb([('s1', str(self.project), None), ('s2', long, ''), ('s3', chinese, None),
                  ('s4', str(self.project / 'identity'), ' workspace-identity ')])
        root = Path('.zcode/cli/memories/projects')
        regular = zcode.key(str(self.project))
        for name in (regular, zcode.key(long), zcode.key(chinese), zcode.key(str(self.project / 'identity'), 'workspace-identity'), regular + '1e'):
            (self.home / root / name / 'memory').mkdir(parents=True)
        self.put(root / regular / 'memory/topic.md', '---\nmetadata:\n  originSessionId: sess_fixture\n---\nTopic')
        self.put(root / (regular + '1e') / 'memory/topic.md', 'Different source')
        out = self.run_memory('zcode', 'locate')
        by_name = {Path(s['path']).parent.name: s for s in out['items']}
        self.assertEqual(by_name[regular]['project']['basis'], 'zcode_path_hash')
        self.assertEqual(by_name[regular + '1e']['status'], 'orphan')
        self.assertEqual(by_name[regular + '1e']['near'], [by_name[regular]['path']])
        self.assertEqual(len(zcode.key(long).rsplit('-', 1)[0]), 48)
        self.assertTrue(zcode.key(long).rsplit('-', 1)[0].endswith('-'))
        self.assertTrue(zcode.key(chinese).startswith('project-'))
        identity = by_name[zcode.key(str(self.project / 'identity'), 'workspace-identity')]
        self.assertEqual(identity['project']['basis'], 'zcode_identity_hash')
        self.assertEqual(identity['status'], 'empty')
        entry = self.run_memory('zcode', 'list', '--store', by_name[regular]['path'])['items'][0]
        self.assertEqual(entry['native_session']['id'], 'sess_fixture')

    def test_zcode_symlink_project_keys_stay_distinct(self):
        alias = self.home / 'workspace/Alias'
        alias.symlink_to(self.project, target_is_directory=True)
        self.zdb([('s1', str(self.project), None), ('s2', str(alias), None)])
        self.assertNotEqual(zcode.key(str(alias)), zcode.key(str(self.project)))
        for path in (alias, self.project):
            self.put(Path('.zcode/cli/memories/projects') / zcode.key(str(path)) / 'memory/topic.md', 'text')
        self.assertEqual(len(self.run_memory('zcode', 'locate')['items']), 2)

    def test_claude_later_cwd_is_owner_and_legacy_origin(self):
        folder = self.session('claude', self.home, claude.encode(str(self.project)), [self.project])
        path = self.put(folder / 'topic.md', '---\noriginSessionId: old-style\ntype: user\n---\nMemory')
        item = self.run_memory('claude', 'locate')['items'][0]
        self.assertEqual(item['project'], {'path': str(self.project), 'basis': 'encoded_cwd'})
        entry = self.run_memory('claude', 'list', '--store', path.parent)['items'][0]
        self.assertEqual(entry['native_session']['from'], 'originSessionId')

    def test_claude_collision_no_session_and_project_argument(self):
        a, b = self.project.parent / '甲乙', self.project.parent / '丙丁'
        folder = self.session('claude', a, later=[b])
        self.put(folder / 'topic.md', 'unresolved ownership')
        item = self.run_memory('claude', 'locate')['items'][0]
        self.assertEqual(item['status'], 'ambiguous')
        self.assertIsNone(item['project'])
        self.assertEqual(item['candidates'], sorted([str(a), str(b)]))
        isolated = Path('.claude/projects') / claude.encode(str(self.project)) / 'memory'
        path = self.put(isolated / 'solo.md', '# memory without sessions')
        out = self.run_memory('claude', 'locate', '--project', self.project)
        self.assertEqual(out['items'][0]['project']['basis'], 'project_arg')
        self.assertEqual(len(out['items']), 1)

    def test_unmounted_is_distinct_from_missing_project(self):
        path = Path(os.sep) / 'Volumes/fixture-unmounted/project'
        folder = self.session('claude', path)
        self.put(folder / 'topic.md', 'data remains on home disk')
        self.assertEqual(self.run_memory('claude', 'locate')['items'][0]['status'], 'unmounted')
        self.assertFalse(memory.path_exists(self.home / 'missing'))

    def test_codex_versions_roles_shared_session_unofficial_and_git(self):
        header = 'thread_id: same-thread\ncwd: ' + str(self.project) + '\nrollout_path: /fixture/rollout.jsonl\n\n'
        for root in ('memories', 'memories_v2'):
            self.put('.codex/' + root + '/memory_summary.md', '# Navigation')
            self.put('.codex/' + root + '/rollout_summaries/one.md', header + root)
            self.put('.codex/' + root + '/.git/config', 'must be ignored')
        for name, text in [('MEMORY.md', 'Consolidated'), ('raw_memories.md', 'Extracts'),
                           ('skills/demo/SKILL.md', 'Procedure'), ('extensions/ad_hoc/notes/one.md', 'Note'),
                           ('extensions/ad_hoc/instructions.md', 'Guide'), ('extensions/skysight/resources/day.md', 'Activity'),
                           ('automations/demo/memory.md', 'Old log'), ('local/log.md', 'Process log')]:
            self.put('.codex/memories/' + name, text)
        ctx = self.ctx('codex')
        before = self.snapshot()
        stores, entries = memory.catalogue(ctx)
        summaries = [e for e in entries if e['role'] == 'session_summary']
        self.assertEqual(summaries[0]['same_session_as'], [summaries[1]['path']])
        self.assertEqual(summaries[1]['same_session_as'], [summaries[0]['path']])
        self.assertEqual(sum(s['status'] == 'unofficial' for s in stores), 2)
        self.assertEqual(sum(e['role'] == 'process_log' for e in entries), 2)
        self.assertIn('skill', {e['role'] for e in entries})
        self.assertFalse(any('/.git/' in e['path'] for e in entries))
        self.assertEqual(ctx.warnings, [])
        self.assertEqual(self.snapshot(), before)

    def test_codex_recent_injection_counts_main_user_and_automation(self):
        for root in ('memories', 'memories_v2'):
            self.put('.codex/' + root + '/memory_summary.md', '# Index')
        v1, v2 = str(self.home / '.codex/memories/'), str(self.home / '.codex/memories_v2/')
        v1 += '/'; v2 += '/'
        self.codex_session('user-v1', v1)
        self.codex_session('user-v2', v2)
        self.codex_session('both', v1 + ' ' + v2)
        self.codex_session('auto', v1, 'automation')
        self.codex_session('child', v2, 'subagent')
        by_layout = {s['layout']: s for s in self.run_memory('codex', 'locate')['items']}
        self.assertEqual(by_layout['codex-v1']['recent_injection']['user'], 2)
        self.assertEqual(by_layout['codex-v1']['recent_injection']['automation'], 1)
        self.assertEqual(by_layout['codex-v2']['recent_injection']['user'], 2)
        self.assertEqual(by_layout['codex-v2']['recent_injection']['automation'], 0)

    def test_codex_no_sessions_is_null_and_project_filter_is_file_level(self):
        self.put('.codex/memories_v2/memory_summary.md', '# index')
        self.put('.codex/memories_v2/rollout_summaries/a.md', 'thread_id: a\ncwd: ' + str(self.project) + '\n\nSummary')
        self.put('.codex/memories_v2/rollout_summaries/b.md', 'thread_id: b\ncwd: /fixture/other\n\nOther')
        self.assertIsNone(self.run_memory('codex', 'locate')['items'][0]['recent_injection'])
        result = self.run_memory('codex', 'list', '--project', self.project)
        self.assertEqual([i['native_session']['id'] for i in result['items']], ['a'])

    def test_codex_automation_single_and_multiple_cwds(self):
        for name, paths in [('one', [str(self.project)]), ('many', [str(self.project), '/fixture/other'])]:
            self.put('.codex/automations/' + name + '/automation.toml', 'name = "Synthetic"\nrrule = "FREQ=DAILY"\ncwds = ' + json.dumps(paths) + '\n')
            self.put('.codex/automations/' + name + '/memory.md', 'Execution history')
        items = {Path(s['path']).name: s for s in self.run_memory('codex', 'locate')['items']}
        self.assertEqual(items['one']['project']['basis'], 'automation_cwds')
        self.assertEqual(items['many']['status'], 'ambiguous')
        self.assertEqual(items['one']['files'], 1)

    def test_workbuddy_inode_alias_persona_duplicate_and_backup(self):
        alias = self.project.parent / 'maple'
        if not alias.exists():
            alias.symlink_to(self.project, target_is_directory=True)
        self.session('workbuddy', self.project, later=[alias])
        self.put(self.project / '.workbuddy/memory/2026-10-01.md', 'Daily activity')
        self.put('.workbuddy/MEMORY.md', 'Same memory')
        self.put('.workbuddy/user-fixture/MEMORY.md', 'Same memory')
        self.put('.workbuddy/user-fixture/USER.md', 'Preference')
        self.put('.workbuddy/user-fixture/SOUL.md', 'Persona')
        backup = self.put('.workbuddy/memory/fixture_memory.md.bak', 'Old backup')
        stores, entries = memory.catalogue(self.ctx('workbuddy'))
        workspace = [s for s in stores if s['layout'] == 'workbuddy-workspace']
        self.assertEqual(len(workspace), 1)
        self.assertEqual(len(workspace[0]['aliases']), 1)
        shared = [e for e in entries if e['role'] == 'consolidated']
        self.assertTrue(all(len(e['duplicate_of']) == 1 for e in shared))
        self.assertEqual({e['role'] for e in entries}, {'daily', 'consolidated', 'profile', 'persona', 'backup'})
        with self.assertRaisesRegex(memory.ReaderError, 'backup_skipped'):
            self.run_memory('workbuddy', 'read', '--path', backup)
        self.assertEqual(self.run_memory('workbuddy', 'read', '--path', backup, '--include-backups')['items'][0]['text'], 'Old backup')

    def test_qodercn_three_layouts_migration_and_changed_detection(self):
        project = self.project.parent / '中文.v1'
        folder = self.session('qodercn', project)
        target = self.put(folder / 'topic.md', '---\nmetadata:\n  type: project\n---\nMigrated')
        self.put('.qoder-cn/memory/MEMORY.md', '[Daily](qoderwork-daily-demo.md)')
        self.put('.qoder-cn/memory/qoderwork-daily-demo.md', 'Daily')
        self.put(Path('.qoder-cn/memories/user/projects') / qodercn.legacy_encode(str(project)) / 'task_flow/old.md', 'Old topic')
        self.put('.qoder-cn/memories/user/projects/Qoder-Chats/task_flow/old.md', 'Unmapped')
        db = self.home / 'Library/Application Support/com.qodercn.app.stable/memoryMigration.sqlite'
        db.parent.mkdir(parents=True)
        with sqlite3.connect(db) as con:
            con.execute('CREATE TABLE memory_import_target_files(target_file TEXT,content_sha256 TEXT,imported_at INTEGER)')
            con.execute('INSERT INTO memory_import_target_files VALUES(?,?,?)', (str(target), hashlib.sha256(target.read_bytes()).hexdigest(), 1790000000000))
        ctx = self.ctx('qodercn')
        stores, entries = memory.catalogue(ctx)
        self.assertEqual({s['layout'] for s in stores}, {'qodercn-cli-project', 'qodercn-desktop', 'qodercn-legacy'})
        marked = next(e for e in entries if e['path'] == str(target))
        self.assertTrue(marked['migrated']['unchanged'])
        legacy = [s for s in stores if s['layout'] == 'qodercn-legacy']
        self.assertEqual({s['status'] for s in legacy}, {'ok', 'orphan'})
        old = next(e for e in entries if e['role'] == 'topic' and '/task_flow/' in e['path'])
        self.assertEqual(old['frontmatter']['category'], 'task_flow')
        target.write_text(target.read_text() + '\nChanged')
        changed = self.run_memory('qodercn', 'list', '--store', target.parent)['items'][0]
        self.assertFalse(changed['migrated']['unchanged'])

    def test_cli_runs_with_synthetic_home_and_does_not_create_cache(self):
        folder = self.session('claude')
        self.put(folder / 'topic.md', 'Synthetic text')
        before = self.snapshot()
        script = ROOT / 'plugins/client-readers/skills/read-claude/scripts/read.py'
        env = dict(os.environ, HOME=str(self.home))
        for command in (['memory', 'locate'], ['projects'], ['doctor']):
            proc = subprocess.run([sys.executable, '-B', str(script), *command], env=env, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)['client'], 'claude')
        self.assertEqual(self.snapshot(), before)

    def test_project_alias_filter_finds_memory_and_read_rejects_outside_hardlink(self):
        alias = self.project.parent / 'Alias'
        alias.symlink_to(self.project, target_is_directory=True)
        self.session('workbuddy', self.project, later=[alias])
        path = self.put(self.project / '.workbuddy/memory/MEMORY.md', 'Alias-visible memory')
        output = self.run_memory('workbuddy', 'list', '--project', alias)
        self.assertEqual(len(output['items']), 1)
        self.assertEqual(self.run_memory('workbuddy', 'read', '--path', alias / '.workbuddy/memory/MEMORY.md')['items'][0]['text'], 'Alias-visible memory')
        outside = self.home / 'outside.md'
        os.link(path, outside)
        with self.assertRaisesRegex(memory.ReaderError, 'not_in_store'):
            self.run_memory('workbuddy', 'read', '--path', outside)

    def test_missing_root_and_backups_remain_read_only(self):
        before = self.snapshot()
        empty = self.run_memory('zcode', 'locate')
        self.assertFalse(empty['coverage']['scan_complete'])
        self.assertTrue(empty['warnings'][0].startswith('source_unavailable:'))
        self.assertEqual(self.snapshot(), before)
        backup = self.put('.workbuddy/memory/fixture_memory.md.bak', 'Do not read by default')
        read_bytes = Path.read_bytes
        def guarded(path):
            if path == backup:
                raise AssertionError('default list must not read backup content')
            return read_bytes(path)
        with mock.patch.object(Path, 'read_bytes', guarded):
            _, entries = memory.catalogue(self.ctx('workbuddy'))
        self.assertIsNone(entries[0]['sha256'])


class MemoryFixTests(MemoryFixture):
    def test_frontmatter_supported_values_and_nested_fields(self):
        text = '''---
name: "demo"
inline: [one, two]
description: first line
  continuation: with colon
    final line
empty:
keywords:
  - one
  - "two"
  - true
  - null
custom:
  name: nested
    continued: text
  list:
    - alpha
    - beta
  empty:
# ignored comment
metadata:
  originSessionId: fixture-session
---
'''
        warnings, partial = [], []
        data = memory.frontmatter(text, warnings, 'fixture.md', partial)
        self.assertEqual(data, dict(name='demo', inline=['one', 'two'],
                                   description='first line continuation: with colon final line', empty='',
                                   keywords=['one', 'two', True, None],
                                   custom=dict(name='nested continued: text', list=['alpha', 'beta'], empty=''),
                                   metadata=dict(originSessionId='fixture-session')))
        self.assertEqual((warnings, partial), ([], []))

    def test_frontmatter_unsupported_values_are_omitted(self):
        cases = [
            ('bad: |\n  multiline', 'bad'), ('bad: >\n  folded', 'bad'),
            ('bad: {child: value}', 'bad'), ('bad: &anchor value', 'bad'),
            ('bad: *alias', 'bad'), ('bad: !tag value', 'bad'),
            ('parent:\n  bad:\n    child: value', 'parent.bad'),
            ('bad:\n  - child: value', 'bad'),
            ('bad: "first\n  second"', 'bad'), ("bad: 'first\n  second'", 'bad'),
            ('\tbad: value', 'bad'), ('parent:\n\tbad: value', 'parent.bad'),
            ('bad:\n  - one\n   - two', 'bad'), ('bad:\n  - [nested]', 'bad'),
            ('bad: [one, two]\n  more', 'bad'), ('bad:\n  unknown', 'bad'),
            ('unowned line', 'line:3'),
        ]
        for body, key in cases:
            with self.subTest(body=body):
                warnings, partial = [], []
                data = memory.frontmatter('---\ngood: kept\n' + body + '\n---\n', warnings, 'fixture.md', partial)
                self.assertEqual(data['good'], 'kept')
                self.assertEqual(partial, [key])
                self.assertNotIn('bad', data.get('parent', data))
                self.assertEqual(len(warnings), 1)
                self.assertRegex(warnings[0], r'^frontmatter_partial: fixture.md; keys=' + key + r'; lines=\d+$')

    def test_frontmatter_duplicate_keys_keep_first_and_warn_once(self):
        warnings, partial = [], []
        data = memory.frontmatter('---\nname: first\nname: second\nname: third\ncustom:\n  type: first\n  type: second\n---\n', warnings, 'fixture.md', partial)
        self.assertEqual(data, {'name': 'first', 'custom': {'type': 'first'}})
        self.assertEqual(partial, ['name', 'custom.type'])
        self.assertEqual(warnings, ['frontmatter_partial: fixture.md; keys=name,custom.type; lines=3'])

    def test_frontmatter_missing_delimiter_and_file_marker(self):
        folder = self.session('claude')
        path = self.put(folder / 'topic.md', '---\nname: unfinished\n')
        output = self.run_memory('claude', 'list', '--store', path.parent)
        self.assertEqual(output['items'][0]['frontmatter'], {})
        self.assertEqual(output['items'][0]['frontmatter_partial'], ['line:1'])
        self.assertEqual(output['warnings'], ['frontmatter_partial: ' + str(path) + '; missing_delimiter'])
        self.assertFalse(output['coverage']['scan_complete'])

    def test_local_warnings_follow_file_filter_and_pagination(self):
        folder_a = self.session('claude')
        folder_b = self.session('claude', self.project.parent / 'Birch')
        a = self.put(folder_a / 'a.md', '---\nbad: |\n  omitted\n---\nTarget A')
        clean = self.put(folder_a / 'b.md', 'Clean match')
        b = self.put(folder_b / 'b.md', '---\nbad: {nested: value}\n---\nTarget B')
        listed = self.run_memory('claude', 'list', '--store', a.parent, '--limit', 1)
        self.assertEqual(len(listed['warnings']), 1)
        self.assertIn(str(a), listed['warnings'][0])
        self.assertNotIn(str(b), ''.join(listed['warnings']))
        self.assertEqual(listed['warnings_outside_filter'], 1)
        self.assertFalse(listed['coverage']['scan_complete'])
        tail = self.run_memory('claude', 'list', '--store', a.parent, '--offset', 1)
        self.assertEqual(tail['warnings'], [])
        self.assertEqual(tail['warnings_outside_filter'], 2)
        self.assertTrue(tail['coverage']['scan_complete'])
        for args in [('read', '--path', clean), ('search', '--query', 'Clean')]:
            output = self.run_memory('claude', *args)
            self.assertEqual(output['warnings'], [])
            self.assertEqual(output['warnings_outside_filter'], 2)
            self.assertTrue(output['coverage']['scan_complete'])
            self.assertEqual(output['items'][0]['frontmatter_partial'], [])
            self.assertFalse(any(k.startswith('_') for k in output['items'][0]))

    def test_locate_summary_and_store_warnings_use_selected_stores_before_page(self):
        a = self.put(self.session('claude') / 'topic.md', '---\nbad: |\n  text\n---\nA')
        b = self.put(self.session('claude', self.project.parent / 'Birch') / 'topic.md', '---\nbad: !tag value\n---\nB')
        outside = self.put('outside.md', 'Not memory')
        (a.parent / 'escape.md').symlink_to(outside)
        all_stores = self.run_memory('claude', 'locate', '--limit', 1)
        self.assertEqual(all_stores['summary'], {'claude-project': {'ok': 2}})
        self.assertTrue(all_stores['has_more'])
        one = self.run_memory('claude', 'locate', '--project', self.project)
        self.assertEqual(one['summary'], {'claude-project': {'ok': 1}})
        self.assertEqual(len(one['warnings']), 2)
        self.assertEqual(one['warnings_outside_filter'], 1)
        self.assertFalse(one['coverage']['scan_complete'])
        self.assertNotIn(str(b), ''.join(one['warnings']))

    def test_global_warning_still_blocks_clean_selected_file(self):
        path = self.put(self.session('claude') / 'topic.md', 'Clean')
        ctx = self.ctx('claude')
        ctx.warnings.append('session_metadata_unreadable: fixture')
        args = cli.parser('claude').parse_args(['memory', 'read', '--path', str(path)])
        out = memory.run(ctx, args)
        self.assertEqual(out['warnings'], ['session_metadata_unreadable: fixture'])
        self.assertFalse(out['coverage']['scan_complete'])

    def test_index_warning_follows_index_file_not_other_file(self):
        folder = self.session('claude')
        index = self.put(folder / 'MEMORY.md', '[missing](gone.md)')
        topic = self.put(folder / 'topic.md', 'Clean')
        read = self.run_memory('claude', 'read', '--path', topic)
        self.assertEqual(read['warnings'], [])
        self.assertEqual(read['warnings_outside_filter'], 1)
        self.assertTrue(read['coverage']['scan_complete'])
        self.assertTrue(self.run_memory('claude', 'read', '--path', index)['warnings'][0].startswith('missing_index_target:'))

    def test_read_failure_remains_a_visible_gap(self):
        path = self.put(self.session('claude') / 'topic.md', 'Clean')
        real_read, reads = Path.read_bytes, []
        def fail_second(target):
            if target == path:
                reads.append(target)
                if len(reads) == 2:
                    raise OSError('synthetic changed permissions')
            return real_read(target)
        with mock.patch.object(Path, 'read_bytes', fail_second):
            output = self.run_memory('claude', 'read', '--path', path)
        self.assertFalse(output['coverage']['scan_complete'])
        self.assertEqual(output['warnings'], ['memory_read_error: ' + str(path)])
        self.assertNotIn('text', output['items'][0])

    def test_codex_multiple_cwds_file_filter_and_no_session_access(self):
        paths = [str(self.project), '/fixture/other']
        self.put('.codex/automations/many/automation.toml', 'cwds = ' + json.dumps(paths))
        path = self.put('.codex/automations/many/memory.md', 'Synthetic history')
        with mock.patch.object(Context, 'sessions', new_callable=mock.PropertyMock,
                               side_effect=AssertionError('list/read/search must not scan sessions')):
            listed = self.run_memory('codex', 'list', '--project', self.project)
            self.assertEqual([e['path'] for e in listed['items']], [str(path)])
            self.assertEqual(self.run_memory('codex', 'list', '--project', '/fixture/unrelated')['items'], [])
            self.assertEqual(len(self.run_memory('codex', 'read', '--path', path)['items']), 1)
            self.assertEqual(len(self.run_memory('codex', 'search', '--query', 'history', '--project', self.project)['items']), 1)

    def test_codex_automation_config_warning_is_store_local(self):
        path = self.put('.codex/automations/bad/memory.md', 'History')
        other = self.put('.codex/memories_v2/memory_summary.md', 'Clean')
        output = self.run_memory('codex', 'read', '--path', other)
        self.assertEqual(output['warnings'], [])
        self.assertEqual(output['warnings_outside_filter'], 1)
        self.assertTrue(output['coverage']['scan_complete'])
        located = self.run_memory('codex', 'locate', '--store', path.parent)
        self.assertTrue(located['warnings'][0].startswith('automation_config_unreadable:'))
        self.put('.codex/automations/bad/automation.toml', 'cwds = "invalid"')
        self.assertTrue(self.run_memory('codex', 'locate', '--store', path.parent)['warnings'][0].startswith('automation_cwds_invalid:'))

    def test_zcode_generic_project_slug_does_not_match_other_projects(self):
        paths = [str(self.project.parent / name) for name in ('甲', '乙', '丙')]
        self.zdb([(str(i), path, None) for i, path in enumerate(paths)])
        for path in paths:
            self.put(Path('.zcode/cli/memories/projects') / zcode.key(path) / 'memory/topic.md', 'Known')
        self.put('.zcode/cli/memories/projects/project-0000000000000000/memory/topic.md', 'Orphan')
        orphan = next(s for s in self.run_memory('zcode', 'locate')['items'] if s['status'] == 'orphan')
        self.assertEqual(orphan['near'], [])

    def test_crlf_section_offsets_match_outline_and_preserve_newlines(self):
        path = self.put(self.session('claude') / 'topic.md', '')
        text = '# First\r\nBefore\r\n## Second\r\nAfter\r\n'
        path.write_bytes(text.encode())
        outline = self.run_memory('claude', 'list', '--store', path.parent, '--outline')['items'][0]['outline']
        item = self.run_memory('claude', 'read', '--path', path, '--section', 1)['items'][0]
        self.assertEqual(item['text_offset'], outline[1]['text_offset'])
        self.assertEqual(item['text'], '## Second\r\nAfter\r\n')
        self.assertEqual(item['text_chars'], len(text))

    def test_workbuddy_home_workspace_is_only_user_store(self):
        self.session('workbuddy', self.home)
        path = self.put('.workbuddy/memory/1234_memory.md', 'Shared history')
        stores, files = memory.catalogue(self.ctx('workbuddy'))
        self.assertEqual([s['layout'] for s in stores], ['workbuddy-user'])
        self.assertEqual([e['path'] for e in files], [str(path)])
        self.assertEqual(files[0]['duplicate_of'], [])


class ProjectTests(MemoryFixture):
    def test_broad_roots_do_not_make_all_projects_nested(self):
        child = self.project / 'Child'
        child.mkdir()
        alone = self.project.parent / 'Alone'
        volume = Path('/Volumes/fixture-volume')
        self.session('claude', '/', later=[self.home, self.project, child, alone, volume, volume / 'Only'])
        out = projects.run(self.ctx('claude'), argparse.Namespace(since=None, offset=0, limit=200))
        rows = {r['path']: r for r in out['items']}
        self.assertEqual({p for p, r in rows.items() if 'broad_root' in r['flags']}, {'/', str(self.home), str(volume)})
        self.assertEqual({p for p, r in rows.items() if 'nested' in r['flags']}, {str(self.project), str(child)})

    def test_projects_alias_nested_memory_without_sessions_and_collisions(self):
        child = self.project / 'child'
        child.mkdir()
        alias = self.project.parent / 'maple'
        if not alias.exists():
            alias.symlink_to(self.project, target_is_directory=True)
        self.session('claude', self.project, later=[alias, child])
        folder = Path('.claude/projects') / claude.encode(str(self.project)) / 'memory'
        self.put(folder / 'topic.md', 'Known')
        alone = self.project.parent / 'Alone'
        self.put(Path('.claude/projects') / claude.encode(str(alone)) / 'memory/topic.md', 'No sessions')
        ctx = self.ctx('claude', [alone, self.project])
        args = argparse.Namespace(since=None, offset=0, limit=200)
        result = projects.run(ctx, args)
        by_path = {r['path']: r for r in result['items']}
        main = by_path[str(self.project)]
        self.assertEqual(main['sessions']['count'], 1)
        self.assertEqual(main['memory']['files'], 1)
        self.assertTrue({'alias', 'case_variant', 'nested'} <= set(main['flags']))
        self.assertEqual(main['aliases'], [str(alias)])
        self.assertIn('memory_without_sessions', by_path[str(alone)]['flags'])

    def test_codex_projects_metadata_reader_only_consumes_first_line(self):
        self.codex_session('one', '', extra=[{'type': 'turn_context', 'payload': {'cwd': '/fixture/later'}}])
        ctx = self.ctx('codex')
        self.assertEqual(ctx.sessions[0]['cwds'], [str(self.project)])
        self.assertNotIn('/fixture/later', json.dumps(ctx.sessions))
        from client_readers.clients import codex
        with mock.patch.object(codex, 'recent_injection', side_effect=AssertionError('projects 不得读会话正文')):
            out = projects.run(ctx, argparse.Namespace(since=None, offset=0, limit=200))
        self.assertEqual([r['path'] for r in out['items']], [str(self.project)])

    def test_codex_projects_unknown_first_line_is_a_gap(self):
        self.jsonl('.codex/sessions/unsupported.jsonl', [
            {'type': 'message', 'cwd': '/fixture/not-session-meta'},
            {'type': 'session_meta', 'payload': {'id': 'later', 'cwd': str(self.project)}}])
        ctx = self.ctx('codex')
        out = projects.run(ctx, argparse.Namespace(since=None, offset=0, limit=200))
        self.assertEqual(out['items'], [])
        self.assertFalse(out['coverage']['scan_complete'])
        self.assertTrue(out['warnings'][0].startswith('unsupported_session_header:'))

    def test_codex_projects_reports_compressed_unread_count(self):
        from client_readers import runtime
        for name in ('one', 'two'):
            self.put('.codex/sessions/' + name + '.jsonl.zst', 'synthetic unread compressed source')
        with mock.patch.object(runtime, '_capabilities', {'zstd': []}):
            output = projects.run(self.ctx('codex'), argparse.Namespace(since=None, offset=0, limit=200))
        self.assertEqual(output['items'], [])
        self.assertEqual(len(output['warnings']), 1)
        self.assertIn('2 个 .jsonl.zst 会话未读', output['warnings'][0])

    def test_codex_missing_backend_summaries_follow_roots_and_store_scope(self):
        from client_readers import runtime
        roots = [self.home / '.codex' / name for name in ('sessions', 'archived_sessions')]
        for index, root in enumerate(roots):
            for name in ('one', 'two'):
                self.put(root / 'nested' / (name + '.jsonl.zst'), 'synthetic unread compressed source')
            self.jsonl(root / 'plain.jsonl', [{'type': 'session_meta', 'payload': {
                'id': 'plain-' + str(index), 'cwd': str(self.project / str(index))}}])
            self.put(root / 'plain.jsonl.zst', 'plain twin remains readable')
        for name in ('memories', 'memories_v2', 'memories/local'):
            self.put('.codex/' + name + '/memory_summary.md', 'Memory')
        with mock.patch.object(runtime, '_capabilities', {'zstd': []}):
            for offset in (0, 1):
                ctx = self.ctx('codex')
                output = projects.run(ctx, argparse.Namespace(since=None, offset=offset, limit=1))
                self.assertEqual(len(output['items']), 1)
                self.assertEqual(output['coverage']['total_items'], 2)
                self.assertFalse(output['coverage']['scan_complete'])
                self.assertEqual(output['warnings_outside_filter'], 0)
                self.assertEqual(len(output['warnings']), 2)
                self.assertEqual(output['warnings'], ctx.warnings)
                self.assertEqual({source for source, warnings in ctx.session_warnings.items() if warnings},
                                 {str(root) for root in roots})
                for root in roots:
                    self.assertEqual(len(ctx.session_warnings[str(root)]), 1)
                    self.assertIn('2 个 .jsonl.zst 会话未读', ctx.session_warnings[str(root)][0])
                    self.assertIn(str(root), ctx.session_warnings[str(root)][0])
            for name in ('memories', 'memories_v2'):
                located = self.run_memory('codex', 'locate', '--store', self.home / '.codex' / name)
                self.assertCountEqual(located['warnings'], output['warnings'])
                self.assertFalse(located['coverage']['scan_complete'])
            unofficial = self.run_memory('codex', 'locate', '--store', self.home / '.codex/memories/local')
            self.assertEqual(unofficial['warnings'], [])


class MemorySecondFixTests(MemoryFixture):
    def corrupt_session(self, folder):
        path = self.home / folder.parent / 'session.jsonl'
        with path.open('a') as stream:
            stream.write('{"partial":\n')
        return path

    def project_output(self, client, selected=(), offset=0, limit=200):
        return projects.run(self.ctx(client, selected), argparse.Namespace(since=None, offset=offset, limit=limit))

    def test_json_session_warnings_are_retained_by_source(self):
        from client_readers.clients import json_sessions
        folder = self.session('claude')
        source = self.corrupt_session(folder)
        ctx = self.ctx('claude')
        rows = json_sessions(ctx, source.parent)
        self.assertEqual(ctx.warnings, [])
        self.assertEqual(len(ctx.session_warnings[str(source)]), 1)
        self.assertEqual(rows[0]['cwds'], [str(self.project)])

    def test_claude_memory_ignores_bad_directory_without_memory(self):
        folder = self.session('claude')
        path = self.put(folder / 'topic.md', 'Clean memory')
        other = self.project.parent / 'Other'
        bad = self.corrupt_session(self.session('claude', other))
        for args in [('locate',), ('list', '--store', path.parent), ('read', '--path', path)]:
            with self.subTest(args=args):
                output = self.run_memory('claude', *args)
                self.assertEqual(output['warnings'], [])
                self.assertTrue(output['coverage']['scan_complete'])
        full = self.project_output('claude')
        self.assertEqual(len(full['warnings']), 1)
        self.assertIn(str(bad), full['warnings'][0])
        only_a = self.project_output('claude', [self.project])
        self.assertEqual(only_a['warnings'], [])
        self.assertEqual(only_a['warnings_outside_filter'], 1)
        self.assertTrue(only_a['coverage']['scan_complete'])
        only_b = self.project_output('claude', [other])
        self.assertEqual(only_b['warnings'], full['warnings'])
        self.assertFalse(only_b['coverage']['scan_complete'])

    def test_claude_store_ownership_warnings_follow_its_files(self):
        folder = self.session('claude')
        path = self.put(folder / 'topic.md', 'Memory')
        source = self.corrupt_session(folder)
        for args in [('locate',), ('list', '--store', path.parent), ('read', '--path', path)]:
            output = self.run_memory('claude', *args)
            self.assertEqual(len(output['warnings']), 1)
            self.assertIn(str(source), output['warnings'][0])
            self.assertFalse(output['coverage']['scan_complete'])
            self.assertEqual(output['warnings_outside_filter'], 0)

    def test_claude_target_scan_keeps_duplicates_and_matches_project_items(self):
        path = self.put(self.session('claude') / 'topic.md', 'Same content')
        other = self.put(self.session('claude', self.project.parent / 'Other') / 'topic.md', 'Same content')
        original = claude.json_sessions
        for args in [('read', '--path', path), ('list', '--store', path.parent)]:
            with mock.patch.object(claude, 'json_sessions', wraps=original) as scan, \
                 mock.patch.object(Context, 'sessions', new_callable=mock.PropertyMock,
                                   side_effect=AssertionError('Claude memory must not access ctx.sessions')):
                output = self.run_memory('claude', *args)
                self.assertEqual([call.args[1] for call in scan.call_args_list], [path.parent.parent])
                self.assertEqual(output['items'][0]['duplicate_of'], [str(other)])
        target = self.run_memory('claude', 'list', '--store', path.parent)
        by_project = self.run_memory('claude', 'list', '--project', self.project)
        self.assertEqual(target['items'], by_project['items'])

    def test_claude_case_variant_target_keeps_project_and_scans_only_its_directory(self):
        folder = self.home / self.session('claude')
        path = self.put(folder / 'nested/topic.md', 'Same content')
        self.put(self.session('claude', self.project.parent / 'Other') / 'topic.md', 'Same content')
        resolved = folder.resolve()
        variant = resolved.parent.with_name(resolved.parent.name.swapcase()) / resolved.name
        original_stat = Path.stat

        def variant_stat(candidate, *args, **kwargs):
            try:
                candidate = resolved / candidate.relative_to(variant)
            except ValueError:
                pass
            return original_stat(candidate, *args, **kwargs)

        cases = [('list', '--store', folder, variant),
                 ('read', '--path', path, variant / 'nested/topic.md')]
        # 本机支持时走真实大小写别名；mock 分支始终运行，供区分大小写的文件系统验证。
        for simulated in ([False, True] if variant.is_dir() else [True]):
            for action, flag, original, alternate in cases:
                with self.subTest(action=action, simulated=simulated):
                    expected = self.run_memory('claude', action, flag, original)
                    self.assertEqual(expected['items'][0]['project'],
                                     {'path': str(self.project), 'basis': 'encoded_cwd'})
                    with (mock.patch.object(Path, 'stat', variant_stat) if simulated else nullcontext()), \
                         mock.patch.object(claude, 'json_sessions', wraps=claude.json_sessions) as scan:
                        actual = self.run_memory('claude', action, flag, alternate)
                    self.assertEqual(actual, expected)
                    self.assertEqual([call.args[1] for call in scan.call_args_list], [folder.parent])

    def test_claude_directory_scan_is_cached_only_in_context(self):
        self.put(self.session('claude') / 'topic.md', 'Memory')
        ctx = self.ctx('claude')
        with mock.patch.object(claude, 'json_sessions', wraps=claude.json_sessions) as scan:
            first = claude.locate(ctx)
            self.assertEqual(claude.locate(ctx), first)
            self.assertEqual(scan.call_count, 1)
            claude.locate(self.ctx('claude'))
            self.assertEqual(scan.call_count, 2)

    def test_qodercn_cli_warning_local_other_sources_global(self):
        folder = self.session('qodercn')
        path = self.put(folder / 'topic.md', 'CLI memory')
        cli_bad = self.corrupt_session(folder)
        desktop = self.put('.qoder-cn/memory/MEMORY.md', 'Desktop memory')
        cli_out = self.run_memory('qodercn', 'list', '--store', path.parent)
        self.assertEqual(len(cli_out['warnings']), 1)
        self.assertIn(str(cli_bad), cli_out['warnings'][0])
        desk_out = self.run_memory('qodercn', 'read', '--path', desktop)
        self.assertEqual(desk_out['warnings'], [])
        self.assertEqual(desk_out['warnings_outside_filter'], 1)
        other_bad = self.corrupt_session(self.session('qodercn', self.project.parent / 'Other'))
        desk_out = self.run_memory('qodercn', 'read', '--path', desktop)
        self.assertEqual(len(desk_out['warnings']), 1)
        self.assertIn(str(other_bad), desk_out['warnings'][0])
        self.assertFalse(desk_out['coverage']['scan_complete'])
        db = self.home / 'Library/Application Support/com.qodercn.app.stable/main.sqlite'
        db.parent.mkdir(parents=True)
        with sqlite3.connect(db) as con:
            con.execute('CREATE TABLE unsupported(id TEXT)')
        desk_out = self.run_memory('qodercn', 'read', '--path', desktop)
        self.assertTrue(any('session_metadata_unreadable: ' + str(db) == w for w in desk_out['warnings']))

    def test_workbuddy_memory_warnings_remain_global_projects_are_scoped(self):
        folder = self.session('workbuddy')
        self.put(self.project / '.workbuddy/memory/MEMORY.md', 'Memory')
        self.corrupt_session(folder)
        other = self.project.parent / 'Other'
        self.session('workbuddy', other)
        output = self.run_memory('workbuddy', 'locate')
        self.assertEqual(len(output['warnings']), 1)
        self.assertFalse(output['coverage']['scan_complete'])
        projects_out = self.project_output('workbuddy', [other])
        self.assertEqual(projects_out['warnings'], [])
        self.assertEqual(projects_out['warnings_outside_filter'], 1)

    def test_codex_injection_warnings_only_attach_regular_memory_stores(self):
        path = self.put('.codex/memories_v2/memory_summary.md', 'Memory')
        self.put('.codex/memories/memory_summary.md', 'Memory V1')
        old = self.put('.codex/memories/local/process.md', 'Old process')
        source = self.codex_session('bad-header')
        with source.open('a') as stream:
            stream.write('{"partial":\n')
        located = self.run_memory('codex', 'locate')
        self.assertEqual(len(located['warnings']), 1)
        self.assertEqual(self.run_memory('codex', 'locate', '--store', old.parent)['warnings'], [])
        self.assertEqual(self.run_memory('codex', 'read', '--path', path)['warnings'], [])
        for root in ('memories', 'memories_v2'):
            out = self.run_memory('codex', 'locate', '--store', self.home / '.codex' / root)
            self.assertEqual(out['warnings'], located['warnings'])
            self.assertFalse(out['coverage']['scan_complete'])

    def test_projects_unowned_session_warning_stays_global(self):
        self.put(self.session('claude') / 'topic.md', 'Memory')
        self.put('.claude/projects/no-cwd/bad.jsonl', '{"partial":\n')
        out = self.project_output('claude', [self.project])
        self.assertEqual(len(out['warnings']), 1)
        self.assertEqual(out['warnings_outside_filter'], 0)
        self.assertFalse(out['coverage']['scan_complete'])

    def test_search_read_failure_is_global_and_not_a_result(self):
        folder = self.session('claude')
        failed = self.put(folder / 'a.md', 'Needle')
        good = self.put(folder / 'b.md', 'Needle')
        real_read = Path.read_bytes
        for action in ('search', 'read'):
            reads = []
            def fail_second(path):
                if path == failed:
                    reads.append(path)
                    if len(reads) == 2:
                        raise OSError('synthetic changed permissions')
                return real_read(path)
            args = ['--query', 'Needle'] if action == 'search' else ['--path', failed]
            with mock.patch.object(Path, 'read_bytes', fail_second):
                output = self.run_memory('claude', action, *args)
            self.assertEqual([e['path'] for e in output['items']], [str(good if action == 'search' else failed)])
            self.assertEqual(output['warnings'], ['memory_read_error: ' + str(failed)])
            self.assertEqual(output['warnings_outside_filter'], 0)
            self.assertFalse(output['coverage']['scan_complete'])
            if action == 'read':
                self.assertNotIn('text', output['items'][0])

    def test_parent_children_use_nearest_alias_ancestor_before_filter(self):
        a = self.home / 'A'
        b, c, d = a / 'b', a / 'b/c', a / 'd'
        c.mkdir(parents=True)
        d.mkdir()
        alias = self.home / 'a'
        if not alias.exists():
            alias.symlink_to(a, target_is_directory=True)
        self.session('claude', self.home, later=[a, b, c, d, alias, alias / 'b', alias / 'd'])
        full = self.project_output('claude')
        rows = {r['path']: r for r in full['items']}
        self.assertEqual(rows[str(self.home)]['parent'], None)
        self.assertEqual(rows[str(a)]['parent'], None)
        self.assertEqual(rows[str(b)]['parent'], str(a))
        self.assertEqual(rows[str(d)]['parent'], str(a))
        self.assertEqual(rows[str(c)]['parent'], str(b))
        self.assertEqual(rows[str(a)]['children'], 2)
        self.assertEqual(rows[str(b)]['children'], 1)
        filtered = self.project_output('claude', [b])
        self.assertEqual([(r['path'], r['parent'], r['children']) for r in filtered['items']],
                         [(r['path'], rows[r['path']]['parent'], rows[r['path']]['children']) for r in filtered['items']])
        page = self.project_output('claude', limit=1, offset=1)['items'][0]
        self.assertEqual((page['parent'], page['children']), (rows[page['path']]['parent'], rows[page['path']]['children']))

    def test_parent_resolves_alias_when_child_only_uses_alias_path(self):
        main = self.home / 'Parent'
        main.mkdir()
        alias = self.home / 'Shortcut'
        alias.symlink_to(main, target_is_directory=True)
        child = alias / 'Child'
        child.mkdir()
        self.session('claude', main, later=[alias, child])
        rows = {r['path']: r for r in self.project_output('claude')['items']}
        self.assertEqual(rows[str(child)]['parent'], str(main))
        self.assertEqual(rows[str(main)]['children'], 1)
