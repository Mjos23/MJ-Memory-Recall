"""Local read/evaluate/lower interface. Outputs are created without overwriting."""
import argparse
import json
from pathlib import Path
import sys

from bangel.compiler import ElsaCompiler
from bangel.ir import JPIR
from bangel.diagnostics import BangelDiagnostic
from .engine import recall, source_files, project_selection
from .transport import MAX_BODY_BYTES, load_json_bytes


def read_json(path):
    with Path(path).open('rb') as stream:
        return load_json_bytes(stream.read(MAX_BODY_BYTES + 1))


def main(argv=None):
    parser = argparse.ArgumentParser(description='MJ Memory Recall — provisional Bangel profile')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('run', 'lower'):
        sub = commands.add_parser(name)
        sub.add_argument('request', type=Path)
        sub.add_argument('--review', type=Path)
        sub.add_argument('--output', required=True, type=Path)
    sub = commands.add_parser('project')
    sub.add_argument('selection_id')
    sub.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError('Output already exists')
        if args.command == 'project':
            result = project_selection(args.selection_id)
        else:
            request = read_json(args.request)
            review = read_json(args.review) if args.review else None
            if args.command == 'lower':
                sources = source_files(request, review=review)
                raw = ElsaCompiler().compile_project(sources, entry_source_name='main.bangel').to_bytes()
                JPIR.from_bytes(raw).verify()
                args.output.mkdir(parents=True, exist_ok=False)
                for name, source in sources.items():
                    (args.output / name).write_text(source, encoding='utf-8')
                (args.output / 'program.jp.json').write_bytes(raw)
                print('Lowered Bangel and independently admitted JP')
                return 0
            result = recall(request, review=review)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
        print(result.get('status', result['profile']))
        return 0 if args.command == 'project' or result['advisory_ready'] else 3
    except (ValueError, OSError, RecursionError, BangelDiagnostic) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
