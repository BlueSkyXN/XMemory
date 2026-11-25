"""技能内的只读入口；会话参数仍交给原解析器。"""
import argparse
import json
import sys

from . import sessions
from .common import ReaderError, redact, scrub
from . import memory, projects, runtime
from .clients import Context


def parser(client):
    root = argparse.ArgumentParser(description=f"{client} 本机会话、原生记忆与项目总览（只读）")
    commands = root.add_subparsers(dest='command', required=True)
    commands.add_parser('sessions', help='原会话 list / read / search；用 sessions --help 查看参数')
    for name in ('projects', 'doctor', 'memory'):
        command = commands.add_parser(name)
        if name == 'doctor':
            command.add_argument('--candidates', action='store_true')
            continue
        command.add_argument('--project', nargs='+', action='extend', default=[])
        command.add_argument('--offset', type=sessions.nonnegative, default=0)
        command.add_argument('--limit', type=sessions.positive, default=40)
        command.add_argument('--format', choices=('json', 'markdown'), default='json')
        if name == 'projects':
            command.add_argument('--since', type=sessions.date_arg)
        else:
            command.add_argument('action', choices=('locate', 'list', 'read', 'search'))
            command.add_argument('--store')
            command.add_argument('--path')
            command.add_argument('--role', choices=memory.ROLES, nargs='+', action='extend')
            command.add_argument('--outline', action='store_true')
            command.add_argument('--include-backups', action='store_true')
            command.add_argument('--query')
            position = command.add_mutually_exclusive_group()
            position.add_argument('--section', type=sessions.nonnegative)
            position.add_argument('--text-offset', type=sessions.nonnegative, default=0)
            command.add_argument('--max-chars', type=sessions.positive, default=6000)
    return root


def main(client, argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    if sys.version_info < (3, 9):
        print(json.dumps({'error': 'python_requires_3_9', 'client': client}))
        return 2
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "sessions":
        return sessions.main(client, argv[1:])
    args = parser(client).parse_args(argv)
    ctx = Context(client, getattr(args, 'project', []))
    try:
        if args.command == 'doctor':
            output = runtime.doctor(ctx, args.candidates)
        else:
            if args.limit > 200 or getattr(args, 'max_chars', 0) > 100000:
                raise ReaderError('limit_exceeded: --limit <= 200，--max-chars <= 100000')
            if args.command == 'projects':
                output = projects.run(ctx, args)
            else:
                if args.store and args.project:
                    raise ReaderError('choose_store_or_project')
                if args.action == 'list' and not (args.store or args.project):
                    raise ReaderError('list_requires_store_or_project')
                if args.action == 'read' and not args.path:
                    raise ReaderError('read_requires_path')
                if args.action == 'search' and not args.query:
                    raise ReaderError('search_requires_query')
                if args.action != 'read' and (args.section is not None or args.text_offset or args.path):
                    raise ReaderError('text_expansion_requires_read')
                output = memory.run(ctx, args)
    except (ReaderError, OSError, ValueError) as exc:
        print(json.dumps({'error': redact(str(exc)), 'client': client,
                          'warnings': scrub(ctx.warnings), 'runtime': runtime.describe()}, ensure_ascii=False))
        return 2
    if getattr(args, 'format', 'json') == 'json':
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f'# {client} · {args.command}\n')
        for item in output.get('items', []):
            print('## ' + item.get('path', '') + '\n')
            if 'text' in item:
                print(item['text'] + '\n')
            print(json.dumps({k: v for k, v in item.items() if k != 'text'}, ensure_ascii=False, indent=2))
        print('\n读取边界：' + json.dumps({k: v for k, v in output.items() if k != 'items'}, ensure_ascii=False))
    return 0
