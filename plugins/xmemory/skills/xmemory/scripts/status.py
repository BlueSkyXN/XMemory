"""只读盘点 Markdown 记忆；不读取原生客户端或维护处理状态。"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import string
from urllib.parse import unquote

LABEL = re.compile(r'(?<!\\)\[((?:\\.|[^\]\\\n])*)\]')
REFERENCE = re.compile(r'^ {0,3}\[((?:\\.|[^\]\\\n])+)\]:[ \t]*(.*)$', re.M)
CODE_SPAN = re.compile(r'(?<![\\`])(`+)(?!`)(.*?)(?<!`)\1(?!`)', re.S)
ESCAPE = re.compile(r'\\([' + re.escape(string.punctuation) + r'])')
TITLE = r'''(?:"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|\((?:\\.|[^)\\\n])*\))'''
INLINE_END = re.compile(r'\s*(?:' + TITLE + r'\s*)?\)')


def markdown_body(text):
    """检查导航时跳过围栏代码及成对反引号包围的行内代码。"""
    lines = []
    fence = None
    for line in text.splitlines():
        match = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if match:
            token = match[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is None:
            lines.append(line)
    return CODE_SPAN.sub(lambda match: re.sub(r'[^\n]', ' ', match[0]), '\n'.join(lines))


def link_destination(text, start):
    """读取目标部分，保留转义并配对路径中的括号。"""
    index = start
    angled = text[index:index + 1] == '<'
    if angled:
        index += 1
        start = index
    depth = 0
    while index < len(text):
        char = text[index]
        if char == '\\' and index + 1 < len(text):
            index += 2
            continue
        if angled:
            if char == '>':
                return text[start:index], index + 1
            if char in '<\n\r':
                return None, index
        elif char.isspace() or char == ')' and depth == 0:
            break
        elif char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        index += 1
    if angled or depth:
        return None, index
    return text[start:index], index


def reference_key(label):
    return ' '.join(ESCAPE.sub(r'\1', label).split()).casefold()


def markdown_links(text):
    """提取行内链接和已定义的完整、折叠、简写引用式链接。"""
    definitions = {}

    def definition(match):
        raw, end = link_destination(match[2], 0)
        if raw is None or not re.fullmatch(r'[ \t]*(?:' + TITLE + r'[ \t]*)?', match[2][end:]):
            return match[0]
        definitions.setdefault(reference_key(match[1]), raw)
        return ' ' * len(match[0])

    body = REFERENCE.sub(definition, markdown_body(text))
    position = 0
    while True:
        label = LABEL.search(body, position)
        if label is None:
            return
        position = label.end()
        if body[position:position + 1] == '(':
            start = position + 1
            while start < len(body) and body[start].isspace():
                start += 1
            raw, end = link_destination(body, start)
            closing = INLINE_END.match(body, end) if raw is not None else None
            if closing:
                yield ESCAPE.sub(r'\1', raw)
                position = closing.end()
                continue
        reference = LABEL.match(body, position)
        key = (reference[1] or label[1]) if reference else label[1]
        if reference:
            position = reference.end()
        raw = definitions.get(reference_key(key))
        if raw is not None:
            yield ESCAPE.sub(r'\1', raw)


def is_inside(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def local_target(root, source, raw):
    """External provenance links are not probed, including escaped relative paths."""
    raw = raw.strip('<>')
    if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', raw):
        return None
    decoded = unquote(re.split(r'[?#]', raw, maxsplit=1)[0])
    if not decoded or decoded.startswith(('/', '~', '\\')) or re.match(r'^[A-Za-z]:', decoded):
        return None
    target = Path(os.path.abspath(str(source.parent / decoded)))
    return target if is_inside(target, root) else None


def has_symlink(root, path):
    current = root
    for part in path.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def inspect(root):
    root = Path(os.path.abspath(str(Path(root).expanduser())))
    report = {'root': str(root), 'ok': True, 'files': [], 'issues': [], 'entry': False, 'memory': False}
    if root.is_symlink() or not root.is_dir():
        report['ok'] = False
        report['issues'].append('记忆根不存在、不可读或是符号链接；请检查指定目录。')
        return report

    def unreadable(error):
        report['ok'] = False
        report['issues'].append('目录无法读取：' + str(error.filename))

    for folder, directories, names in os.walk(str(root), followlinks=False, onerror=unreadable):
        current = Path(folder)
        for name in list(directories):
            path = current / name
            if path.is_symlink():
                directories.remove(name)
                report['issues'].append('跳过符号链接：' + path.relative_to(root).as_posix())
            elif name.startswith('.'):
                directories.remove(name)
        for name in sorted(names):
            path = current / name
            relative = path.relative_to(root).as_posix()
            if name.startswith('.'):
                continue
            if path.is_symlink():
                report['issues'].append('跳过符号链接：' + relative)
                continue
            if path.suffix.lower() != '.md':
                continue
            try:
                data = path.read_bytes()
                text = data.decode('utf-8')
            except (OSError, UnicodeError):
                report['ok'] = False
                report['issues'].append('Markdown 无法读取：' + relative)
                continue
            report['files'].append({'path': relative, 'bytes': len(data)})
            if relative == 'memory_summary.md':
                report['entry'] = True
                if len(data) >= 10000:
                    report['issues'].append('入口达到 10,000 字节，建议检查重复内容和导航：' + relative)
            elif relative == 'MEMORY.md':
                report['memory'] = True
            for raw in markdown_links(text):
                target = local_target(root, path, raw)
                if target is None:
                    continue
                if has_symlink(root, target):
                    report['issues'].append('链接经过符号链接，未读取：' + relative)
                elif not target.is_file():
                    report['issues'].append('内部链接目标缺失：' + relative + ' → ' + target.relative_to(root).as_posix())
    report['files'].sort(key=lambda item: item['path'])
    return report


def escaped(value):
    return str(value).replace('\n', ' ').replace('\r', ' ').replace('|', '\\|')


def render(report, summary=False):
    lines = ['# XMemory 只读检查', '', '- 目录：' + escaped(report['root']),
             '- 入口：' + ('存在' if report['entry'] else '未创建'),
             '- 主记忆：' + ('存在' if report['memory'] else '未创建'),
             '- Markdown：{} 个，共 {} 字节'.format(len(report['files']), sum(item['bytes'] for item in report['files']))]
    if not summary and report['files']:
        lines += ['', '| 文件 | 字节 |', '|---|---:|']
        lines += ['| {} | {} |'.format(escaped(item['path']), item['bytes']) for item in report['files']]
    lines += ['', '## 检查结果', '']
    lines += ['- ' + escaped(issue) for issue in report['issues']] or ['未发现内部文件结构问题。']
    lines += ['', '本报告仅盘点文件和内部链接的文件目标，不校验标题锚点，不判断记忆正确性、来源覆盖或整理完成情况。']
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description='XMemory Markdown 记忆的可选只读检查')
    parser.add_argument('--root', type=Path, help='仅用于明确的测试或诊断根')
    sub = parser.add_subparsers(dest='command', required=True)
    status = sub.add_parser('status', help='只读盘点，不创建任何文件')
    status.add_argument('--root', type=Path, default=argparse.SUPPRESS, help='仅用于明确的测试或诊断根')
    status.add_argument('--summary', action='store_true', help='省略逐文件清单')
    args = parser.parse_args(argv)
    root = args.root if args.root is not None else Path.home() / '.agents' / 'memory'
    report = inspect(root)
    print(render(report, args.summary), end='')
    return 0 if report['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
