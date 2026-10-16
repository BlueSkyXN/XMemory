"""自动化 TOML 的合成结构；不包含本机配置或提示词。"""
import json

KEYS = ('cwds', 'name', 'rrule')


def automation(project='/fixture/project'):
    return ('version = 1\nid = "fixture"\nname = "合成自动化"\n'
            'prompt = "先核对清单\\n再记录状态"\nstatus = "ACTIVE"\n'
            'rrule = "FREQ=DAILY;BYHOUR=8"\n'
            'cwds = ' + json.dumps([project], ensure_ascii=False) + '\n'
            'created_at = 1790000000000\nupdated_at = 1790000000001\n'
            'execution_environment = "local"\n'
            'target = { type = "project", project_id = "fixture-project" }\n')


def cases():
    decoys = ('prompt_basic = """\n引号与转义 \\"\n'
              'cwds = ["/decoy-basic"]\nname = "诱饵"\n"""\n'
              "prompt_literal = '''\ncwds = [\"/decoy-literal\"]\nrrule = \"诱饵\"\n'''\n")
    nested = ('ratio = 1.25\nstamp = 2026-10-16T08:00:00+08:00\n'
              'target = { inner = { keys = ["}", "#", "["] }, active = true }\n'
              'future = [\n { name = "cwds", nested = [1, 2] }, # ] ignored\n'
              ' """\ncwds = ["/decoy-array"]\n""",\n]\n')
    return {
        'real_structure': automation(),
        'multiline_decoys': decoys + automation(),
        'unrelated_types': nested + automation().replace('target = { type = "project", project_id = "fixture-project" }\n', ''),
        'subtable': automation() + '[child]\ncwds = ["/decoy-table"]\nname = "子表"\n',
    }
