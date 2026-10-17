#!/usr/bin/env python3
"""生成 1.7 合成行为案例；不读真实记忆，不调用模型，不覆盖已有目录。"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import shutil

PROJECTS = ('Maple', 'Willow', 'Cedar', 'Empty')
# 规模变体的虚构项目与来源，数量仿照实际使用中的库，名称与内容均为合成数据。
TREES = ('Alder', 'Aspen', 'Birch', 'Cedar', 'Cherry', 'Cypress', 'Elm', 'Fir', 'Ginkgo', 'Hazel',
         'Hemlock', 'Holly', 'Juniper', 'Larch', 'Laurel', 'Linden', 'Locust', 'Magnolia', 'Maple', 'Mulberry',
         'Oak', 'Olive', 'Palm', 'Pear', 'Pecan', 'Pine', 'Plum', 'Poplar', 'Redwood', 'Rowan',
         'Sequoia', 'Spruce', 'Sumac', 'Sycamore', 'Teak', 'Walnut', 'Willow', 'Yew', 'Banyan')
SCALE_SOURCES = (('claude_memory', 'memory', 'claude', 36), ('codex_sessions', 'sessions', 'codex', 3),
                 ('codex_skysight', 'memory', 'codex', 0), ('codex_v1_memory', 'memory', 'codex', 15),
                 ('qoderworkcn_memory', 'memory', 'qoderworkcn', 21), ('traecn_memory', 'memory', 'traecn', 6),
                 ('zcode_memory', 'memory', 'zcode', 2), ('zcode_sessions', 'sessions', 'zcode', 1))


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def document(path, kind, updated, body='', **fields):
    metadata = dict(format='xmemory/v1.5', kind=kind, updated=updated, **fields)
    write(path, '---\n' + '\n'.join(k + ': ' + json.dumps(v, ensure_ascii=False)
                                  for k, v in metadata.items()) + '\n---\n' + body + '\n')


def source(job, name, body, stamp, folder='sources'):
    path = job / folder / (name + '.md')
    write(path, body)
    when = datetime.fromisoformat(stamp).timestamp()
    os.utime(path, (when, when))
    return path


def record(job, name, stamp, *, body='', project='Maple', day=None,
           source_path=None, source_stamp=None, coverage='complete', **extra):
    original = source_path or job / 'sources' / (name + '.md')
    fields = dict(source='files', client='filesystem', source_ref=str(original),
                  source_location=str(original), source_updated=source_stamp or stamp,
                  evidence='primary', projects=[project], day=day or stamp[:10], day_basis='event',
                  session_refs=[], coverage=coverage)
    fields.update(extra)
    path = 'records/imported/files/' + name + '.md'
    document(job / 'memory' / path, 'record', stamp, body, **fields)
    return path


def default_sources(job):
    return [('files', 'files', 'filesystem', job / 'sources', True),
            ('sessions', 'sessions', 'codex', job / 'home/.codex/sessions', True),
            ('codex_skysight', 'memory', 'codex', job / 'home/.codex/memories/extensions/skysight/resources', True),
            ('disabled', 'files', 'filesystem', job / 'not-selected', False)]


def scale_sources(job):
    paths = {'codex_sessions': job / 'home/.codex/sessions', 'zcode_sessions': job / 'home/.zcode/cli/db',
             'codex_skysight': job / 'home/.codex/memories/extensions/skysight/resources'}
    return [(name, kind, client, paths.get(name, job / 'sources' / name), name != 'codex_skysight')
            for name, kind, client, _ in SCALE_SOURCES]


def prepare(root, repo, case, day, projects=PROJECTS, sources=default_sources):
    job = root / case
    (job / 'home').mkdir(parents=True)
    for name in projects:
        (job / 'workspace' / name).mkdir(parents=True)
    lines = ['format = "xmemory/v1.5"', 'timezone = "Asia/Shanghai"', 'exclude_sessions = []']
    for name, kind, client, path, enabled in sources(job):
        path.mkdir(parents=True, exist_ok=True)
        lines += [f'\n[sources.{name}]', 'enabled = ' + str(enabled).lower(),
                  'kind = ' + json.dumps(kind), 'client = ' + json.dumps(client),
                  'paths = [' + json.dumps(str(path)) + ']']
    for name in projects:
        lines += [f'\n[projects.{name}]', 'roots = [' + json.dumps(str(job / 'workspace' / name)) + ']']
    lines += ['\n[limits]', 'awareness_max_bytes = 10000']
    write(job / 'memory/config.toml', '\n'.join(lines) + '\n')
    # 模型只看到安装后的技能描述和自然请求；评分清单放在 job 外。
    return job


def scale_library(job, day):
    """仿实际规模的虚构库：多来源、无记录项目、无日文件日期、按采集日归档的导入、未链接记录与空字段笔记。"""
    base = datetime.fromisoformat(day)
    days = [(base - timedelta(days=n)).date().isoformat() for n in range(7, 0, -1)]
    older = [(base - timedelta(days=n)).date().isoformat() for n in range(20, 10, -1)]
    plan = [(name, kind, client) for name, kind, client, count in SCALE_SOURCES for _ in range(count)]
    owners = ['Alder'] * 17 + ['Aspen'] * 6 + [TREES[2 + n % 25] for n in range(60)] + [None]
    captured = [n for n, item in enumerate(plan) if item[1] == 'memory' and n >= 23][:26]
    facts = ('导出前保留原始文件', '失败后最多重试三次', '发布前核对版本号', '空值保留为空，不填零', '日志按天归档')
    records = []
    for n, ((name, kind, client), project) in enumerate(zip(plan, owners)):
        if n in captured:
            when = days[6] if n == captured[-1] else days[3]
        else:
            when = days[n % 7] if n < 23 else (days + older)[n % 17]
        stamp = f'{when}T{8 + n % 10:02d}:{n % 60:02d}:00+08:00'
        title = f'{project or "归属未定"} 资料 {n:02d}'
        fields = dict(source=name, client=client, evidence='secondary' if kind == 'memory' else 'primary',
                      projects=[project] if project else [], day=when,
                      day_basis='captured' if n in captured else 'event', session_refs=[], coverage='complete')
        if project is None:
            fields['project_status'] = 'unresolved'
        if n < 6:
            fields['event_days'] = [days[n], days[n + 1]]
        if kind == 'sessions':
            sid = f'{n:08x}-0000-4000-8000-{n:012x}'
            origin = job / ('home/.codex/sessions/' + sid + '.jsonl' if client == 'codex' else 'home/.zcode/cli/db/db.sqlite')
            if client == 'codex':
                rows = [{'type': 'session_meta', 'payload': {'id': sid, 'cwd': str(job / 'workspace' / (project or 'Alder')), 'source': 'cli'}},
                        {'timestamp': stamp, 'type': 'response_item', 'payload': {'type': 'message', 'role': 'user',
                         'content': [{'type': 'input_text', 'text': f'{title}：{facts[n % 5]}。'}]}}]
                write(origin, ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
            fields.update(source_ref=f'{client}:{"jsonl" if client == "codex" else "sqlite"}:{sid}', session_refs=[f'{client}:{sid}'])
            path = f'records/sessions/{client}/{when}-session-{sid[-8:]}.md'
        else:
            origin = source(job, f'{name}-{n:02d}', f'# {title}\n{facts[n % 5]}。\n', stamp, 'sources/' + name)
            fields['source_ref'] = str(origin)
            path = f'records/imported/{client}/{name}-{n:02d}.md'
        document(job / 'memory' / path, 'record', stamp, f'# {title}\n\n{facts[n % 5]}。',
                 source_location=str(origin), source_updated=stamp, **fields)
        records.append({'path': path, 'project': project, 'title': title, 'captured': n in captured,
                        'days': fields.get('event_days', [when]), 'note': False})
    notes = []
    for project, when, clock, slug, location, quote in (
            ('Aspen', day, '09:15:00', 'aspen-upstream', '', '上游仓库位置以项目说明为准。'),
            ('Alder', days[2], '14:00:00', 'alder-export', 'current-conversation', 'Alder 导出默认 CSV。')):
        stamp = f'{when}T{clock}+08:00'
        path = f'records/notes/{when.replace("-", "")}T{clock.replace(":", "")}-{slug}.md'
        document(job / 'memory' / path, 'record', stamp, f'用户原话：“{quote}”', source='note', client='codex',
                 source_ref='current-conversation', source_location=location, source_updated=stamp if location else '',
                 evidence='primary', projects=[project], day=when, day_basis='event', session_refs=[], coverage='complete')
        notes.append(path)
        records.append({'path': path, 'project': project, 'title': '笔记 ' + slug, 'captured': False,
                        'days': [when], 'note': True})
    final = day + 'T23:30:00+08:00'
    alder = [r for r in records if r['project'] == 'Alder' and not r['note']]
    for k, chunk in enumerate((alder[0:4], alder[4:8], alder[8:11], alder[11:14])):
        document(job / f'memory/projects/Alder/topics/topic-{k + 1}.md', 'topic', final,
                 f'# Alder 主题 {k + 1}\n\n' + '\n'.join(f'- 来源：[{r["title"]}](../../../{r["path"]})' for r in chunk))
    document(job / 'memory/projects/Alder/MEMORY.md', 'project-index', final, '# Alder 记忆索引\n\n' + '\n'.join(
        f'- [主题 {k + 1}](topics/topic-{k + 1}.md) — 处理第 {k + 1} 类问题时' for k in range(4)))
    document(job / 'memory/projects/Alder/AWARENESS.md', 'awareness', final, '# Alder 项目意识\n\n## 当前认识\n\n' +
             '\n'.join(f'- [{r["title"]}](../../{r["path"]})' for r in alder[:3]))
    document(job / 'memory/projects/Aspen/topics/upstream.md', 'topic', final, f'# 上游位置\n\n- 来源：[笔记](../../../{notes[0]})')
    document(job / 'memory/projects/Aspen/MEMORY.md', 'project-index', final,
             '# Aspen 记忆索引\n\n- [上游位置](topics/upstream.md) — 查上游仓库时')
    document(job / 'memory/USER.md', 'user', final, '# 偏好\n\n' + '\n'.join(f'- [笔记]({path})' for path in notes))
    document(job / 'memory/memory_summary.md', 'summary', final, '# 全局摘要\n\n'
             '- Alder：[索引](projects/Alder/MEMORY.md)、[意识](projects/Alder/AWARENESS.md)\n'
             '- Aspen：[索引](projects/Aspen/MEMORY.md)\n- [用户画像](USER.md)')
    for when in days:
        today = [r for r in records if when in r['days']]
        groups = {}
        for r in today:
            if not r['captured']:
                groups.setdefault(r['project'] or '归属未定', []).append(r)
        body = [f'# {when}']
        for project, items in groups.items():
            body += ['', f'## {project}', ''] + [f'- {r["title"]}：[来源](../../{r["path"]})' for r in items]
        archive = [r for r in today if r['captured']]
        if archive:
            body += ['', '## 历史资料归档（事件日期未核实）', ''] + [
                f'- [{r["title"]}](../../{r["path"]})：采集日导入，事件日期未核实' for r in archive]
        document(job / f'memory/daily/{when[:4]}/{when}.md', 'daily', when + 'T23:30:00+08:00', '\n'.join(body), day=when)
    derived = sum(1 for p in (job / 'memory').rglob('*.md') if 'records' not in p.relative_to(job / 'memory').parts)
    return {'sources': len(SCALE_SOURCES), 'enabled_sources': len(SCALE_SOURCES) - 1, 'projects': len(TREES),
            'projects_with_records': len({r['project'] for r in records} - {None}), 'records': len(records),
            'derived': derived, 'existing_objects': len(records) + derived, 'captured_records': len(captured),
            'unlinked_on_indexes': {'Alder': 4, 'Aspen': 6}, 'first_three_readonly': True,
            'candidates': '以该版本 status 输出和实际文件为准'}


def make_fixture(root, repo, day='2026-10-15'):
    root.mkdir(parents=True, exist_ok=False)
    early = day + 'T08:00:00+08:00'
    middle = day + 'T10:00:00+08:00'
    later = day + 'T12:00:00+08:00'
    next_day = (datetime.fromisoformat(day) + timedelta(days=1)).date().isoformat()
    manifest = {'day': day, 'cases': {}}
    ignore = shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store')
    shutil.copytree(repo / 'plugins', root / 'marketplace/plugins', ignore=ignore)
    shutil.copytree(repo / '.agents/plugins', root / 'marketplace/.agents/plugins', ignore=ignore)
    for case in ('e1', 'e1_repo', 'e1_cold', 'e1_scale', 'e2', 'e3', 'e3_same_source', 'e4', 'e4_topic', 'e5'):
        job = prepare(root, repo, case, day, *((TREES, scale_sources) if case == 'e1_scale' else ()))
        prompts = []
        if case == 'e1_scale':
            manifest['cases'][case] = scale_library(job, day)
            prompts = ['搞懂当前程序怎么用了嘛', '你知道怎么跑起来吗，目前数据如何', '初始化是否到位，文件记录了什么']
        elif case in ('e1', 'e1_repo', 'e1_cold'):
            for name, project, fact in [('export', 'Maple', '默认使用 CSV，ZIP 仅用于本次附件。'),
                                         ('retry', 'Willow', '重试前保留原游标；超过三次交给人工。')]:
                source(job, name, f'# {project}\n项目路径：{job / "workspace" / project}\n{day} 用户决定：{fact}\n', early)
            note = record(job, 'note', middle, body='Maple 的入口是 export.md。',
                          source='note', source_updated='', source_location='',
                          source_ref='current-conversation')
            document(job / 'memory/USER.md', 'user', later, f'# 偏好\n[笔记]({note})')
            activity = job / 'home/.codex/memories/extensions/skysight/resources' / (day + '-fixture.md')
            write(activity, f'# 活动摘要\n{day} 13:00–13:10：在 Maple 目录查看导出预览，尚未取得导出成功证据。\n项目路径：{job / "workspace/Maple"}\n')
            prompts = ['搞懂当前程序怎么用了嘛', '你知道怎么跑起来吗，目前数据如何',
                       '初始化是否到位，文件记录了什么', '现在要补全，你知道怎么搞吗',
                       '那就开始补全，先完成一批，并报告各来源的剩余范围。']
            if case == 'e1_repo':
                write(job / 'README.md', (repo / 'README.md').read_text(encoding='utf-8'))
                if (repo / 'AGENTS.md').exists():
                    shutil.copyfile(repo / 'AGENTS.md', job / 'AGENTS.md')
            manifest['cases'][case] = {'sources': 4, 'enabled_sources': 3, 'projects': 4,
                                       'existing_records': 1, 'first_three_readonly': True}
            if case == 'e1_cold':
                # 工作目录是待测源码副本，记忆库在默认位置；评测判据、验证记录与私有材料不进副本。
                shutil.copytree(repo, job / 'repo', ignore=shutil.ignore_patterns(
                    '.git', 'local', 'evals', 'dist', 'validation.md', 'test_eval_fixture.py',
                    '__pycache__', '*.pyc', '.DS_Store'))
                for relative in ('docs/validation.md', 'plugins/client-readers/docs/validation.md'):
                    write(job / 'repo' / relative, '# 验证记录\n\n本实验副本不包含历史验证记录。\n')
                (job / 'home/.agents').mkdir()
                (job / 'memory').rename(job / 'home/.agents/memory')
                manifest['cases'][case].update(workdir='repo', memory_root='home/.agents/memory')
        elif case == 'e2':
            source(job, 'export', f'# Maple\n项目路径：{job / "workspace/Maple"}\n{day} 用户决定：导出默认 CSV，保留原始时区。\n', middle)
            prompts = ['更新一轮 XMemory，处理已配置来源。', '再更新一轮，范围相同。']
            manifest['cases'][case] = {'unique_source': 'export.md', 'no_duplicate_records_or_facts': True}
        elif case == 'e3_same_source':
            sid = '22222222-2222-4222-8222-222222222222'
            for index in (1, 2):
                body = (f'client: codex\nthread_id: {sid}\ncwd: {job / "workspace/Maple"}\n'
                        f'updated_at: {middle}\n\n# Maple 会话摘要\n'
                        f'{day}：一次离线校验的三个小样本通过，完整批次未验证，尚未部署。\n')
                if index == 2:
                    body += '仅在增量导出出现 E_CURSOR_STALE 时清理游标缓存，清理前保留原游标。\n'
                source(job, 'summary-' + str(index), body, middle)
            prompts = ['补全已配置范围的 XMemory，保留有用决定、经验和出处，报告完成及剩余范围。']
            manifest['cases'][case] = {'source_files': 2, 'event_count': 1, 'samples': 3,
                                       'unique_fact': 'E_CURSOR_STALE', 'not_verified': '完整批次',
                                       'not_deployed': True}
        elif case == 'e3':
            for name, content, stamp in [('partial', '先备份游标，再重试；最多三次。', middle),
                                          ('changed', '默认格式已从 XML 更正为 JSON Lines。', later),
                                          ('unknown', '离线包保留七天。', middle),
                                          ('unreadable', '不可读夹具', middle)]:
                source(job, name, f'# Maple\n项目路径：{job / "workspace/Maple"}\n{day} 用户决定：{content}\n', stamp)
            record(job, 'partial', early, body='先备份游标。缺口：后半部分未读取。', coverage='partial')
            record(job, 'changed', early, body='默认格式 XML。')
            record(job, 'unknown', early, body='尚待确认。', source_updated='')
            (job / 'sources/unreadable.md').write_bytes(b'\xff\xfe\x00invalid-utf8')
            for n in range(6):
                path = source(job, f'old-{n}', f'# Maple\n{day} 已确定：验证步骤 {n} 需要保留样本。\n项目路径：{job / "workspace/Maple"}\n', early)
                record(job, f'old-{n}', early, source_path=path, body=f'验证步骤 {n} 需要保留样本。')
            document(job / 'memory/projects/Maple/topics/entry.md', 'topic', later, '# 当前入口\n入口待补。')
            document(job / 'memory/projects/Maple/MEMORY.md', 'project-index', later, '[入口](topics/entry.md)')
            sid = '11111111-1111-4111-8111-111111111111'
            session = job / 'home/.codex/sessions' / (sid + '.jsonl')
            rows = [{'type': 'session_meta', 'payload': {'id': sid, 'cwd': str(job / 'workspace/Maple'), 'source': 'cli'}},
                    {'timestamp': middle, 'type': 'response_item', 'payload': {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'Maple 导出以 CSV 为默认。'}]}},
                    {'timestamp': next_day + 'T09:00:00+08:00', 'type': 'response_item', 'payload': {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': '补充：导出保留空值，不能填成零。'}]}}]
            write(session, ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
            document(job / ('memory/records/sessions/codex/' + day + '-export-11111111.md'), 'record', middle,
                     'Maple 导出以 CSV 为默认。', source='sessions', client='codex', source_ref='codex:jsonl:' + sid,
                     source_location=str(session), source_updated=middle, evidence='primary', projects=['Maple'],
                     day=day, day_basis='event', session_refs=['codex:' + sid], coverage='complete')
            prompts = ['补全已配置范围的 XMemory。能处理的完成，读不到的说明原因，最后列出剩余范围。']
            manifest['cases'][case] = {'partial': '最多三次', 'changed': 'JSON Lines',
                                       'next_day': next_day, 'next_day_fact': '不能填成零', 'old_records': 6,
                                       'unreadable': 'unreadable.md'}
        elif case in ('e4', 'e4_topic'):
            for name, project, stamp, body in [('a', 'Maple', later, 'Maple 默认 CSV，新增保留空值。'),
                                              ('b', 'Willow' if case == 'e4' else 'Maple', later, 'B 的回滚窗口更正为 30 分钟。')]:
                path = source(job, name, f'# {project}\n项目路径：{job / "workspace" / project}\n{day} {body}\n', stamp)
                record(job, name, stamp, body=body, project=project, source_path=path)
            if case == 'e4':
                target = f'daily/{day[:4]}/{day}.md'
                document(job / 'memory' / target, 'daily', middle,
                         '# 当天\n## Maple\n默认 CSV。\n[A](../../records/imported/files/a.md)\n'
                         '## Willow\n回滚窗口 10 分钟。\n[B](../../records/imported/files/b.md)', day=day)
                prompts = ['只更新 Maple 的记忆对象，Willow 暂时不处理。']
            else:
                target = 'projects/Maple/topics/export.md'
                document(job / 'memory' / target, 'topic', middle,
                         '# 导出\n## A\n默认 CSV。\n[A](../../../records/imported/files/a.md)\n'
                         '## B\n回滚窗口 10 分钟。\n[B](../../../records/imported/files/b.md)')
                document(job / 'memory/projects/Maple/MEMORY.md', 'project-index', middle, '[导出](topics/export.md)')
                prompts = ['只把 A 的保留空值要求同步到导出主题，B 的回滚窗口先不处理。']
            manifest['cases'][case] = {'must_preserve_file': target, 'must_report_pending': True}
        else:
            prompts = ['记住：Maple 项目以后默认 CSV；这次附 ZIP 只是本次要求。']
            manifest['cases'][case] = {'max_note_body_lines': 5, 'scope': 'Maple', 'one_time': 'ZIP'}
        write(root / (case + '-prompts.json'), json.dumps(prompts, ensure_ascii=False, indent=2) + '\n')
    write(root / 'evaluation-manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--day', default='2026-10-15')
    args = parser.parse_args()
    make_fixture(args.output.resolve(), args.repo.resolve(), args.day)
