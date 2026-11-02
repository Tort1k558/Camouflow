"""Build and execute the complete R12 checkpoint test plan; not runtime admission."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import native_build as build
from scripts import verify_native_privacy_units as units
from app.core.native.runtime import NativeRuntimeError
from scripts.package_native_windows import read_record, validate_build_receipt
from scripts.verify_native_gpu_codec import validate_results as validate_suite
from scripts.verify_native_privacy_batch import source_inputs
from scripts.verify_native_runtime import measure_runtime_core

CANDIDATE = 'upstream-156-checkpoint-r12'
BINARIES = ('blink_unittests', 'components_unittests', 'content_browsertests',
            'content_unittests', 'net_unittests', 'services_unittests')
CASE_PATTERN = re.compile(r'\b(TEST(?:_F|_P)?|IN_PROC_BROWSER_TEST_F)\(\s*(\w+),\s*(\w+)')


def checksum(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_plan(candidate: dict) -> dict:
    plan = read_record(candidate['directory'] / 'native-case-plan.json')
    if (plan.get('candidate_manifest_sha256') != candidate['manifest_sha256']
            or plan.get('binaries') != list(BINARIES)
            or plan.get('native_case_bodies_prepared') != 85
            or not isinstance(plan.get('cases'), list) or len(plan['cases']) != 85):
        raise ValueError('Checkpoint case plan differs from the complete candidate')
    expected = []
    for patch in candidate['manifest']['patches'][136:]:
        path = candidate['directory'] / 'patches' / patch['file']
        if checksum(path) != patch['sha256']:
            raise ValueError('Checkpoint source patch changed')
        source = None
        added = defaultdict(list)
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if line.startswith('diff --git a/'):
                source = line.split(' b/', 1)[1]
            elif source and line.startswith('+') and not line.startswith('+++'):
                added[source].append(line[1:])
        for source, lines in added.items():
            for kind, fixture, case in CASE_PATTERN.findall('\n'.join(lines)):
                binary = ('components_unittests' if source.startswith('components/services/storage/')
                          else 'net_unittests' if source.startswith('net/')
                          else 'services_unittests' if source.startswith('services/network/')
                          else 'blink_unittests' if source.startswith('third_party/blink/')
                          else 'content_browsertests' if source.endswith('_browsertest.cc')
                          else 'content_unittests' if source.startswith('content/') else None)
                if binary is None:
                    raise ValueError('Unrecognized checkpoint test source')
                expected.append(dict(binary=binary, source=source, fixture=fixture,
                                     case=case, kind=kind, patch=patch['file']))
    if plan['cases'] != expected or len(expected) != 85:
        raise ValueError('Checkpoint plan does not account for every source test body')
    return plan


def discover_cases(text: str, bodies: list[dict]) -> dict[str, set[str]]:
    listed = []
    suite = None
    for line in text.splitlines():
        match = re.fullmatch(r'([\w/]+)\.\s*(?:#.*)?', line)
        if match:
            suite = match[1]
            continue
        match = re.fullmatch(r'  ([\w/]+)\s*(?:#.*)?', line)
        if match and suite:
            listed.append((suite, match[1]))
        elif line and not line[0].isspace():
            suite = None
    if len(listed) != len(set(listed)):
        raise ValueError('Duplicate native test listing')
    selected = defaultdict(set)
    for body in bodies:
        matches = []
        for suite, case in listed:
            fixture = suite.rsplit('/', 1)[-1].removeprefix('DISABLED_')
            name = case.removeprefix('DISABLED_')
            if body['kind'] == 'TEST_P':
                matches_body = fixture == body['fixture'] and name.startswith(body['case'] + '/')
            else:
                matches_body = suite.removeprefix('DISABLED_') == body['fixture'] and name == body['case']
            if matches_body:
                matches.append((suite, case))
        if not matches or any('DISABLED_' in part for row in matches for part in row):
            raise ValueError('Missing or disabled native test body: ' + body['fixture'] + '.' + body['case'])
        for suite, case in matches:
            selected[suite].add(case)
    return dict(selected)


def validate_results(record: dict, required: dict[str, set[str]]) -> None:
    count = sum(map(len, required.values()))
    if (not isinstance(record, dict) or count == 0
            or any(type(record.get(k)) is not int for k in ('tests', 'failures', 'disabled'))
            or record['tests'] != count or record['failures'] != 0 or record['disabled'] != 0):
        raise ValueError('Checkpoint test totals are incomplete or failed')
    suites = record.get('testsuites')
    if (not isinstance(suites, list) or len(suites) != len(required)
            or any(not isinstance(s, dict) or not isinstance(s.get('name'), str) for s in suites)
            or {s.get('name') for s in suites} != set(required)):
        raise ValueError('Checkpoint suites are missing, repeated or foreign')
    for suite in suites:
        name = suite['name']
        validate_suite(dict(tests=len(required[name]), failures=0, disabled=0, testsuites=[suite]),
                       required_cases=required[name], suite_name=name, label='Checkpoint')


def run_tests(command: list[str], *, source: Path, env: dict, log: Path, timeout: int) -> None:
    with log.open('xb') as stream:
        process = subprocess.Popen(command, cwd=source, env=env, stdout=stream, stderr=subprocess.STDOUT)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                if process.poll() is None:
                    # Only the tree rooted at the process this invocation owns.
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                   stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=30)
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=30)
            raise
        if code:
            raise subprocess.CalledProcessError(code, command)


def run_browser_cases(executable: Path, required: dict, *, source: Path, env: dict,
                      report_dir: Path, timeout: int) -> list[dict]:
    if not required or any(not cases for cases in required.values()):
        raise ValueError('Browser execution requires a nonempty discovered selection')
    deadline = time.monotonic() + timeout
    runs = []
    for suite, cases in sorted(required.items()):
        for case in sorted(cases):
            selected = suite + '.' + case
            prefix = executable.stem + '-' + str(len(runs)).zfill(3)
            results = report_dir / (prefix + '-tests.json')
            row = dict(case=selected, passed=False)
            runs.append(row)
            try:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError('Browser test binary execution budget exhausted')
                run_tests([str(executable), '--gtest_filter=' + selected,
                           '--single-process-tests', '--gtest_output=json:' + str(results)],
                          source=source, env=env, log=report_dir / (prefix + '.log'),
                          timeout=remaining)
                validate_results(read_record(results), {suite: {case}})
                row.update(passed=True, results_file=results.name,
                           results_sha256=checksum(results))
            except (ValueError, OSError, subprocess.SubprocessError, NativeRuntimeError) as error:
                row['error'] = str(error)
    return runs


def verify(workspace: Path, report_dir: Path, *, jobs: int = 4, timeout_seconds: int = 900) -> dict:
    if sys.platform != 'win32':
        raise ValueError('Checkpoint native execution currently supports Windows only')
    if type(jobs) is not int or not 1 <= jobs <= 4:
        raise ValueError('Checkpoint compilation requires 1..4 jobs')
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 900:
        raise ValueError('Checkpoint case deadline must be between 1 and 900 seconds')
    candidate = build.load_candidate(CANDIDATE)
    plan = load_plan(candidate)
    source = workspace / 'chromium/src'
    if (workspace.drive.upper() != 'D:' or workspace != workspace.resolve()
            or not workspace.is_dir() or source != source.resolve() or not source.is_dir()):
        raise ValueError('A canonical existing Chromium workspace on D: is required')
    if (not report_dir.is_absolute() or report_dir.drive.upper() != 'D:'
            or report_dir != report_dir.resolve() or not report_dir.parent.is_dir()
            or report_dir.exists() or report_dir.is_relative_to(source) or report_dir.is_relative_to(ROOT)):
        raise ValueError('Use a new canonical report directory on D: outside both repositories')
    build.preflight(workspace, lock=candidate['lock'])
    build.candidate_workspace(workspace, candidate)
    with build.workspace_lock(workspace):
        units.require_idle_builder(workspace)
        report_dir.mkdir(exist_ok=False)
        return _verify_locked(workspace, report_dir, candidate, plan, jobs, timeout_seconds)


def _verify_locked(workspace: Path, report_dir: Path, candidate: dict, plan: dict,
                   jobs: int, timeout: int) -> dict:
    source = workspace / 'chromium/src'
    output = source / 'out/CamouFlowNative'
    report = dict(schema=1, passed=False, candidate=CANDIDATE,
                  scope='All discovered checkpoint test instances; not whole-profile durability or browser admission',
                  candidate_manifest_sha256=candidate['manifest_sha256'], jobs=jobs,
                  prepared_body_count=85, targets=[], build_invocations=0,
                  postguards_passed=False, browser_runtime_verified=False,
                  privacy_admitted=False, production_admitted=False)
    inputs, initial, binaries = {}, {}, {}

    def save():
        (report_dir / 'report.json').write_text(json.dumps(report, indent=2) + '\n',
                                              encoding='utf-8', newline='\n')

    save()
    try:
        env = units.verification_environment(workspace, None, 'openssl', True)
        temporary = report_dir / 'temp'
        temporary.mkdir()
        env.update(TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary))
        paths = source_inputs(candidate) | {Path(__file__).resolve(),
                ROOT / 'scripts/verify_native_gpu_codec.py',
                candidate['directory'] / 'native-case-plan.json'}
        if any(not p.is_file() or p != p.resolve() for p in paths):
            raise ValueError('Missing or linked checkpoint verification input')
        inputs = {p: checksum(p) for p in paths}
        patches = units.verified_source_chain(workspace, candidate, candidate['lock'], env)
        receipt = read_record(output / 'camouflow-build.json')
        validate_build_receipt(receipt, candidate['lock'], candidate=candidate)
        core = measure_runtime_core(output / 'chrome.exe')
        args = (output / 'args.gn').read_bytes()
        if (receipt.get('runtime_core_sha256_measured') != core
                or receipt.get('binary_sha256_measured') != core['chrome.exe']
                or receipt.get('args_sha256') != hashlib.sha256(args).hexdigest()
                or args.decode('utf-8-sig').replace('\r\n', '\n') !=
                    (ROOT / 'native/args.gn').read_text(encoding='utf-8-sig')
                or receipt.get('local_windows_toolchain_sha256') !=
                    env['GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256']):
            raise ValueError('Checkpoint browser/SDK/GN differs from its compiled receipt')
        initial = dict(core=core, args=args, receipt=(output / 'camouflow-build.json').read_bytes(),
                       patches=patches, sdk=env['GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256'])
        report['build_invocations'] = 1
        save()
        with (report_dir / 'build.log').open('xb') as log:
            subprocess.run(build.depot_command('autoninja', workspace) +
                           ['-C', 'out/CamouFlowNative', '-j', str(jobs), *BINARIES],
                           cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        binaries = {name: checksum(output / (name + '.exe')) for name in BINARIES}
        for binary in BINARIES:
            row = dict(binary=binary, passed=False, test_binary_sha256=binaries[binary])
            report['targets'].append(row)
            try:
                executable = output / (binary + '.exe')
                listing = report_dir / (binary + '-list.log')
                run_tests([str(executable), '--gtest_list_tests'], source=source, env=env,
                          log=listing, timeout=timeout)
                bodies = [r for r in plan['cases'] if r['binary'] == binary]
                required = discover_cases(listing.read_text(encoding='utf-8-sig'), bodies)
                row.update(prepared_bodies=len(bodies),
                           required_cases={suite: sorted(cases) for suite, cases in required.items()},
                           discovered_cases=sum(map(len, required.values())))
                save()
                if binary == 'content_browsertests':
                    runs = run_browser_cases(executable, required, source=source, env=env,
                                             report_dir=report_dir, timeout=timeout)
                    row.update(execution_runs=runs, passed=all(r['passed'] for r in runs),
                               listing_sha256=checksum(listing))
                    if row['passed']:
                        row['executed_cases'] = len(runs)
                    else:
                        row['error'] = 'Browser cases failed; inspect isolated execution runs'
                else:
                    selected = ':'.join(suite + '.' + case for suite, cases in sorted(required.items())
                                        for case in sorted(cases))
                    results = report_dir / (binary + '-tests.json')
                    run_tests([str(executable), '--gtest_filter=' + selected, '--single-process-tests',
                               '--gtest_output=json:' + str(results)],
                              source=source, env=env, log=report_dir / (binary + '.log'), timeout=timeout)
                    validate_results(read_record(results), required)
                    row.update(passed=True, executed_cases=row['discovered_cases'],
                               results_sha256=checksum(results), listing_sha256=checksum(listing))
            except (ValueError, OSError, subprocess.SubprocessError, NativeRuntimeError) as error:
                row['error'] = str(error)
            save()
        report['passed'] = len(report['targets']) == len(BINARIES) and all(r['passed'] for r in report['targets'])
    except (ValueError, OSError, subprocess.SubprocessError, NativeRuntimeError) as error:
        report['error'] = str(error)
    finally:
        try:
            if not initial or not inputs:
                raise ValueError('Checkpoint preflight was incomplete')
            if any(not p.is_file() or checksum(p) != value for p, value in inputs.items()):
                raise ValueError('Checkpoint verifier inputs changed')
            if (measure_runtime_core(output / 'chrome.exe') != initial['core']
                    or (output / 'args.gn').read_bytes() != initial['args']
                    or (output / 'camouflow-build.json').read_bytes() != initial['receipt']
                    or units.verified_source_chain(workspace, candidate, candidate['lock'], env) != initial['patches']
                    or build.local_windows_toolchain(workspace)['GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256'] != initial['sdk']
                    or any(checksum(output / (name + '.exe')) != value for name, value in binaries.items())):
                raise ValueError('Checkpoint source, SDK, browser or native binary changed')
            report['postguards_passed'] = True
        except (ValueError, OSError, subprocess.SubprocessError, NativeRuntimeError) as error:
            report['postguard_error'] = str(error)
        report['passed'] = report['passed'] and report['postguards_passed']
        save()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--report-dir', type=Path, required=True)
    parser.add_argument('--jobs', type=int, choices=range(1, 5), default=4)
    parser.add_argument('--timeout-seconds', type=int, default=900)
    args = parser.parse_args()
    try:
        result = verify(args.workspace, args.report_dir, jobs=args.jobs, timeout_seconds=args.timeout_seconds)
    except (ValueError, OSError, subprocess.SubprocessError, NativeRuntimeError) as error:
        print(f'Checkpoint verification failed: {error}', file=sys.stderr)
        return 1
    print(json.dumps(dict(passed=result['passed'], report=str(args.report_dir / 'report.json'))))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
