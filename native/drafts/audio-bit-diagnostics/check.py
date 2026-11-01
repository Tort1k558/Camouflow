import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


BASE = Path(__file__).resolve().parent


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description='Check descriptive Audio metrics without launching a browser')
    parser.add_argument('--node', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    args = parser.parse_args()
    node, output = args.node.absolute(), args.work_dir.absolute()
    if node != node.resolve() or not node.is_file():
        parser.error('Expected an existing canonical Node executable')
    if (output != output.resolve() or output.drive.upper() != 'D:' or output.exists()
            or not output.parent.is_dir() or output.is_relative_to(BASE.parents[2])):
        parser.error('Expected a fresh canonical directory on D: outside the checkout')
    paths = [BASE / name for name in ('difference.js', 'check-difference.js', 'summarize.py', 'check-summary.py', 'check.py')]
    inputs = {path: sha(path) for path in [*paths, node]}
    output.mkdir()
    report = dict(schema=1, passed=False, browser_executed=False, production_admitted=False, checks=[])
    try:
        commands = [
            ('float-differences', [str(node), str(BASE / 'check-difference.js')]),
            ('summary', [sys.executable, '-B', str(BASE / 'check-summary.py'), '--report', str(output / 'summary.json')]),
        ]
        for name, command in commands:
            with (output / (name + '.log')).open('xb') as log:
                result = subprocess.run(command, cwd=BASE, stdout=log, stderr=subprocess.STDOUT, check=False, timeout=60)
            report['checks'].append(dict(name=name, returncode=result.returncode, passed=result.returncode == 0))
            if result.returncode:
                raise RuntimeError('Diagnostic tool check failed: ' + name)
        report['input_postguards_passed'] = all(sha(path) == digest for path, digest in inputs.items())
        if not report['input_postguards_passed']:
            raise ValueError('Diagnostic tool inputs changed')
        report.update(passed=True, input_sha256={str(path): digest for path, digest in inputs.items()})
    except BaseException as error:
        report.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'passed': report['passed'], 'report': str(output / 'report.json')}))


if __name__ == '__main__':
    main()
