"""Check the pinned builder overlay on D: without changing the real builder."""

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True)
    args = parser.parse_args()
    work = args.work_dir
    if (not work.is_absolute() or work.drive.upper() != 'D:' or work != work.resolve()
            or work.exists() or not work.parent.is_dir() or work.is_symlink() or work.is_junction()
            or work.is_relative_to(ROOT) or ROOT.is_relative_to(work)):
        parser.error('Use a fresh canonical D: directory outside the project')
    record = json.loads((PACKET / 'packet.json').read_bytes())
    source = ROOT / record['source']
    patch = PACKET / 'next.patch'
    if (record['source'] != 'scripts/native_build.py' or sha(source) != record['before_sha256']
            or sha(patch) != record['patch_sha256'] or sha(Path(__file__)) != record['checker_sha256']
            or any(sha(ROOT / name) != digest for name, digest in record['test_inputs_sha256'].items())):
        parser.error('Pinned source, checker, patch or host tests differ; no overlay prepared')
    headers = [line for line in patch.read_text(encoding='utf-8-sig').splitlines() if line.startswith('diff --git ')]
    if headers != ['diff --git a/scripts/native_build.py b/scripts/native_build.py']:
        parser.error('The packet must change only the explicit builder source')
    work.mkdir()
    temporary = work / 'temp'
    temporary.mkdir()
    os.environ.update(PYTHONDONTWRITEBYTECODE='1', QT_QPA_PLATFORM='offscreen',
                      TEMP=str(temporary), TMP=str(temporary), CAMOUFLOW_DATA_DIR=str(work / 'workspace'))
    sys.dont_write_bytecode = True
    target = work / 'scripts/native_build.py'
    target.parent.mkdir()
    target.write_bytes(source.read_bytes())
    report = {'schema': 1, 'passed': False, 'counts': {'passed': 0, 'failed': 0, 'skipped': 0},
              'packet_sha256': sha(PACKET / 'packet.json'), 'checker_sha256': sha(Path(__file__)),
              'canonical_builder_modified': False, 'compiled': False, 'runtime_verified': False,
              'production_admitted': False, 'scope': 'Detached pinned host regression only; not native speed or browser evidence'}
    started = time.monotonic()
    try:
        for check in (True, False):
            subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply',
                            *(['--check'] if check else []), str(patch)], cwd=work, check=True)
        assert sha(target) == record['after_sha256'], 'Unexpected functional postimage'
        text = target.read_text(encoding='utf-8-sig')
        assignment = 'ROOT = Path(__file__).resolve().parents[1]'
        assert text.count(assignment) == 1
        target.write_text(text.replace(assignment, 'ROOT = Path(' + repr(str(ROOT)) + ')'),
                          encoding='utf-8', newline='\n')
        assert 'scripts.native_build' not in sys.modules, 'Use a fresh checker process'
        sys.path.insert(0, str(ROOT))
        import scripts
        scripts.__path__ = [str(target.parent), *scripts.__path__]
        from scripts import native_build as build
        from scripts.verify_native_privacy_batch import source_inputs
        assert Path(build.__file__).resolve() == target and build.ROOT == ROOT
        candidate = build.load_candidate(record['base_candidate'])
        assert candidate['manifest_sha256'] == record['base_candidate_manifest_sha256']
        paths = source_inputs(candidate) | {source, target, patch, PACKET / 'packet.json', Path(__file__)}
        paths.update(ROOT / name for name in record['test_inputs_sha256'])
        inputs = {str(path): sha(path) for path in paths}
        import pytest
        counts = report['counts']

        class Progress:
            def pytest_runtest_logreport(self, report):
                if report.when == 'call' or report.failed or report.skipped:
                    counts[report.outcome] += 1

        with (work / 'pytest.log').open('x', encoding='utf-8') as log:
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                code = pytest.main(['-q', '-o', 'cache_dir=' + str(work / 'cache'),
                                    '--basetemp', str(work / 'pytest'),
                                    *[str(ROOT / name) for name in record['test_inputs_sha256']]],
                                   plugins=[Progress()])
        unchanged = all(Path(name).is_file() and sha(Path(name)) == digest for name, digest in inputs.items())
        report.update(returncode=int(code), passed=code == 0 and unchanged,
                      input_postguards_passed=unchanged, inputs_sha256=inputs,
                      log_sha256=sha(work / 'pytest.log'))
    except BaseException as error:
        report.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        report['canonical_builder_modified'] = sha(source) != record['before_sha256']
        report['duration_seconds'] = round(time.monotonic() - started, 3)
        (work / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'inputs_sha256'}, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
