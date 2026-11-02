import copy
import json
from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest

from scripts import native_build as build
from scripts import verify_native_checkpoint_units as units


def body(fixture='StoreTest', case='Checkpoint', kind='TEST_F'):
    return dict(fixture=fixture, case=case, kind=kind)


def result(required):
    return dict(tests=sum(map(len, required.values())), failures=0, disabled=0,
                testsuites=[dict(name=suite, testsuite=[
                    dict(name=case, status='RUN', result='COMPLETED') for case in sorted(cases)])
                    for suite, cases in required.items()])


@pytest.mark.parametrize('candidate_name,count', [
    ('upstream-156-checkpoint-r12', 85), ('upstream-156-checkpoint-r13', 85),
    ('upstream-156-producer-r14', 163),
])
def test_native_plan_is_derived_from_every_registered_packet(candidate_name, count):
    candidate = build.load_candidate(candidate_name)
    plan = units.load_plan(candidate)
    assert len(plan['cases']) == count and plan['binaries'] == list(units.BINARIES)


@pytest.mark.parametrize('change', ('missing', 'duplicate', 'binary', 'source', 'hash', 'count-type'))
@pytest.mark.parametrize('candidate_name', tuple(units.PLAN_SPECS))
def test_native_plan_rejects_weakened_or_foreign_coverage(monkeypatch, change, candidate_name):
    candidate = build.load_candidate(candidate_name)
    plan = units.load_plan(candidate)
    if change == 'missing':
        plan['cases'].pop()
    elif change == 'duplicate':
        plan['cases'][-1] = plan['cases'][0]
    elif change == 'binary':
        plan['cases'][0]['binary'] = 'content_unittests'
    elif change == 'source':
        plan['cases'][0]['source'] = 'foreign.cc'
    elif change == 'count-type':
        plan['native_case_bodies_prepared'] = float(len(plan['cases']))
    else:
        plan['candidate_manifest_sha256'] = '0' * 64
    monkeypatch.setattr(units, 'read_record', lambda _: plan)
    with pytest.raises(ValueError, match='plan'):
        units.load_plan(candidate)


def test_native_plan_rejects_unknown_candidates_before_reading_files(monkeypatch):
    read = Mock()
    monkeypatch.setattr(units, 'read_record', read)
    with pytest.raises(ValueError, match='Unknown checkpoint candidate plan'):
        units.load_plan({'name': 'unregistered'})
    read.assert_not_called()


def test_listing_discovers_every_parameter_and_ignores_unrelated_cases():
    listing = ('startup log\nAll/DatabaseTest.\n'
               '  Checkpoint/0  # GetParam() = false\n'
               '  Checkpoint/1  # GetParam() = true\n'
               '  Unrelated/0\nStoreTest.\n  Checkpoint\n')
    required = units.discover_cases(listing, [body('DatabaseTest', kind='TEST_P'), body()])
    assert required == {'All/DatabaseTest': {'Checkpoint/0', 'Checkpoint/1'},
                        'StoreTest': {'Checkpoint'}}
    units.validate_results(result(required), required)


@pytest.mark.parametrize('listing,planned', [
    ('StoreTest.\n  Other\n', body()),
    ('StoreTest.\n  Checkpoint\n  Checkpoint\n', body()),
    ('DISABLED_StoreTest.\n  Checkpoint\n', body()),
    ('StoreTest.\n  DISABLED_Checkpoint\n', body()),
    ('All/StoreTest.\n  Checkpoint/0\n  DISABLED_Checkpoint/1\n', body(kind='TEST_P')),
    ('All/StoreTest.\n  Checkpoint/0\n', body()),
    ('StoreTest.\n  Checkpoint\n', body(kind='TEST_P')),
    ('startup log\n', body()),
])
def test_listing_cannot_pass_missing_disabled_duplicate_or_wrong_kind(listing, planned):
    with pytest.raises(ValueError):
        units.discover_cases(listing, [planned])


@pytest.mark.parametrize('change', ('total', 'bool', 'failure', 'disabled', 'missing',
                                   'duplicate', 'foreign', 'skipped', 'not-run', 'case-failure'))
def test_results_require_exact_successful_cases(change):
    required = {'StoreTest': {'Checkpoint', 'Commit'}}
    observed = result(required)
    cases = observed['testsuites'][0]['testsuite']
    if change == 'total':
        observed['tests'] = 1
    elif change == 'bool':
        observed['failures'] = False
    elif change in ('failure', 'disabled'):
        observed['failures' if change == 'failure' else 'disabled'] = 1
    elif change == 'missing':
        cases.pop()
    elif change == 'duplicate':
        cases[1] = cases[0]
    elif change == 'foreign':
        observed['testsuites'][0]['name'] = 'Other'
    elif change == 'skipped':
        cases[0]['result'] = 'SKIPPED'
    elif change == 'not-run':
        cases[0]['status'] = 'NOTRUN'
    else:
        cases[0]['failures'] = [{'failure': 'SQL failed'}]
    with pytest.raises(ValueError):
        units.validate_results(observed, required)


def test_results_reject_duplicate_suites_and_empty_selection():
    required = {'StoreTest': {'Checkpoint'}}
    observed = result(required)
    observed['testsuites'].append(copy.deepcopy(observed['testsuites'][0]))
    with pytest.raises(ValueError):
        units.validate_results(observed, required)
    with pytest.raises(ValueError):
        units.validate_results(result({}), {})


@pytest.mark.parametrize('name', [None, [], {}, 1])
def test_results_reject_malformed_suite_names(name):
    required = {'StoreTest': {'Checkpoint'}}
    observed = result(required)
    observed['testsuites'][0]['name'] = name
    with pytest.raises(ValueError):
        units.validate_results(observed, required)


def test_timeout_terminates_only_the_owned_test_tree(monkeypatch, tmp_path):
    process = Mock(pid=12345)
    process.wait.side_effect = [subprocess.TimeoutExpired('test', 1), 0]
    process.poll.side_effect = [None, 0]
    monkeypatch.setattr(units.subprocess, 'Popen', lambda *a, **k: process)
    terminate = Mock()
    monkeypatch.setattr(units.subprocess, 'run', terminate)
    with pytest.raises(subprocess.TimeoutExpired):
        units.run_tests(['test'], source=tmp_path, env={}, log=tmp_path / 'run.log', timeout=1)
    assert terminate.call_args.args[0] == ['taskkill', '/PID', '12345', '/T', '/F']
    process.kill.assert_not_called()
    assert process.wait.call_count == 2


def test_failed_tree_cleanup_still_reaps_the_owned_root(monkeypatch, tmp_path):
    process = Mock(pid=12345)
    process.wait.side_effect = [subprocess.TimeoutExpired('test', 1), 0]
    process.poll.return_value = None
    monkeypatch.setattr(units.subprocess, 'Popen', lambda *a, **k: process)
    monkeypatch.setattr(units.subprocess, 'run',
                        Mock(side_effect=subprocess.CalledProcessError(1, 'taskkill')))
    with pytest.raises(subprocess.CalledProcessError):
        units.run_tests(['test'], source=tmp_path, env={}, log=tmp_path / 'run.log', timeout=1)
    process.kill.assert_called_once_with()
    assert process.wait.call_count == 2


@pytest.mark.parametrize('jobs,deadline', [(0, 900), (5, 900), (True, 900), (4, 0), (4, 901), (4, True)])
def test_invalid_resource_limits_fail_before_workspace_access(monkeypatch, jobs, deadline):
    monkeypatch.setattr(units.sys, 'platform', 'win32')
    workspace = Mock(spec=Path)
    with pytest.raises(ValueError):
        units.verify(workspace, workspace, jobs=jobs, timeout_seconds=deadline)
    workspace.resolve.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'case', 'listing', 'input', 'binary', 'receipt', 'build'])
def test_native_batch_pipeline_retains_failures_and_checks_postguards(monkeypatch, tmp_path, fault):
    candidate = build.load_candidate(units.CANDIDATE)
    plan = units.load_plan(candidate)
    source = tmp_path / 'workspace/chromium/src'
    output = source / 'out/CamouFlowNative'
    output.mkdir(parents=True)
    report_dir = tmp_path / 'report'
    report_dir.mkdir()
    args = (units.ROOT / 'native/args.gn').read_bytes()
    (output / 'args.gn').write_bytes(args)
    watched = tmp_path / 'guarded-input'
    watched.write_text('original', encoding='utf-8')
    core = {'chrome.exe': 'chrome', 'chrome.dll': 'library', 'chrome_elf.dll': 'elf'}
    receipt = dict(runtime_core_sha256_measured=core, binary_sha256_measured='chrome',
                   args_sha256=units.hashlib.sha256(args).hexdigest(), local_windows_toolchain_sha256='sdk')
    if fault == 'receipt':
        receipt['binary_sha256_measured'] = 'foreign'
    (output / 'camouflow-build.json').write_text(json.dumps(receipt), encoding='utf-8')
    monkeypatch.setattr(units, 'source_inputs', lambda _: {watched})
    monkeypatch.setattr(units, 'measure_runtime_core', lambda _: core)
    monkeypatch.setattr(units, 'validate_build_receipt', lambda *a, **k: None)
    monkeypatch.setattr(units.units, 'verification_environment',
                        lambda *a: {'GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256': 'sdk'})
    monkeypatch.setattr(units.units, 'verified_source_chain', lambda *a: ['pinned-chain'])
    monkeypatch.setattr(units.build, 'local_windows_toolchain',
                        lambda _: {'GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256': 'sdk'})
    monkeypatch.setattr(units.build, 'depot_command', lambda *a: ['autoninja'])

    def compile_binaries(command, **kwargs):
        assert command[-6:] == list(units.BINARIES)
        assert command[command.index('-j') + 1] == '4'
        if fault == 'build':
            raise subprocess.CalledProcessError(1, command)
        for name in units.BINARIES:
            (output / (name + '.exe')).write_bytes(name.encode())
        if fault == 'input':
            watched.write_text('changed', encoding='utf-8')

    monkeypatch.setattr(units.subprocess, 'run', compile_binaries)

    def execute(command, *, source, env, log, timeout):
        binary = Path(command[0]).stem
        log.write_text('isolated fake native process', encoding='utf-8')
        if '--gtest_list_tests' in command:
            required = {}
            for row in plan['cases']:
                if row['binary'] != binary:
                    continue
                suite = ('All/' if row['kind'] == 'TEST_P' else '') + row['fixture']
                cases = [row['case'] + '/0', row['case'] + '/1'] if row['kind'] == 'TEST_P' else [row['case']]
                required.setdefault(suite, set()).update(cases)
            if fault == 'listing' and binary == units.BINARIES[0]:
                required[next(iter(required))].pop()
            log.write_text(''.join(suite + '.\n' + ''.join('  ' + case + '\n' for case in sorted(cases))
                                   for suite, cases in required.items()), encoding='utf-8')
            return
        selected = next(arg.split('=', 1)[1] for arg in command if arg.startswith('--gtest_filter='))
        required = {}
        for name in selected.split(':'):
            suite, case = name.split('.', 1)
            required.setdefault(suite, set()).add(case)
        observed = result(required)
        if fault == 'case' and binary == units.BINARIES[0]:
            observed['failures'] = 1
        if fault == 'binary' and binary == units.BINARIES[0]:
            (output / (binary + '.exe')).write_bytes(b'changed after execution')
        destination = Path(next(arg.split('json:', 1)[1] for arg in command if arg.startswith('--gtest_output=')))
        destination.write_text(json.dumps(observed), encoding='utf-8')

    monkeypatch.setattr(units, 'run_tests', execute)
    report = units._verify_locked(tmp_path / 'workspace', report_dir, candidate, plan, 4, 900)
    assert report['passed'] is (fault is None)
    assert report['postguards_passed'] is (fault not in ('input', 'binary', 'receipt'))
    assert not report['browser_runtime_verified'] and not report['production_admitted']
    assert json.loads((report_dir / 'report.json').read_bytes()) == report
    if fault in ('receipt', 'build'):
        assert report['targets'] == []
    else:
        assert len(report['targets']) == 6
    if fault in ('case', 'listing'):
        assert not report['targets'][0]['passed']
        assert all(row['passed'] for row in report['targets'][1:])
    if fault is None:
        assert sum(r['prepared_bodies'] for r in report['targets']) == 85
        assert sum(r['executed_cases'] for r in report['targets']) > 85


@pytest.mark.parametrize('failed', (None, 'A'))
def test_browser_cases_use_separate_processes_and_continue_after_failure(tmp_path, monkeypatch, failed):
    commands = []

    def execute(command, *, source, env, log, timeout):
        commands.append(command)
        selected = next(s.split('=', 1)[1] for s in command if s.startswith('--gtest_filter='))
        assert ':' not in selected
        assert '--single-process-tests' in command
        suite, case = selected.split('.', 1)
        if case == failed:
            raise subprocess.CalledProcessError(1, command)
        observed = result({suite: {case}})
        destination = Path(next(s.split('json:', 1)[1] for s in command
                                if s.startswith('--gtest_output=')))
        destination.write_text(json.dumps(observed), encoding='utf-8')

    monkeypatch.setattr(units, 'run_tests', execute)
    runs = units.run_browser_cases(tmp_path / 'content_browsertests.exe', {'BrowserTest': {'B', 'A'}},
                                   source=tmp_path, env={}, report_dir=tmp_path, timeout=900)
    assert len(commands) == len(runs) == 2
    assert [r['case'] for r in runs] == ['BrowserTest.A', 'BrowserTest.B']
    assert [r['passed'] for r in runs] == [failed is None, True]
    assert runs[-1]['results_file'] == 'content_browsertests-001-tests.json'


def test_browser_case_budget_is_shared_across_processes(tmp_path, monkeypatch):
    monkeypatch.setattr(units.time, 'monotonic', Mock(side_effect=[0, 10, 901]))
    execute = Mock(side_effect=subprocess.TimeoutExpired(['browser'], 890))
    monkeypatch.setattr(units, 'run_tests', execute)
    runs = units.run_browser_cases(tmp_path / 'content_browsertests.exe', {'BrowserTest': {'A', 'B'}},
                                   source=tmp_path, env={}, report_dir=tmp_path, timeout=900)
    assert execute.call_count == 1
    assert execute.call_args.kwargs['timeout'] == 890
    assert not any(r['passed'] for r in runs)
    assert 'budget exhausted' in runs[-1]['error']


def test_browser_case_requires_its_exact_native_json(tmp_path, monkeypatch):
    def execute(command, **kwargs):
        destination = Path(next(s.split('json:', 1)[1] for s in command
                                if s.startswith('--gtest_output=')))
        destination.write_text(json.dumps(result({'OtherTest': {'A'}})), encoding='utf-8')

    monkeypatch.setattr(units, 'run_tests', execute)
    runs = units.run_browser_cases(tmp_path / 'content_browsertests.exe', {'BrowserTest': {'A'}},
                                   source=tmp_path, env={}, report_dir=tmp_path, timeout=900)
    assert not runs[0]['passed'] and 'error' in runs[0]


def test_fixture_corrected_candidate_preserves_the_derived_checkpoint_cases():
    original = build.load_candidate('upstream-156-checkpoint-r12')
    corrected = build.load_candidate('upstream-156-checkpoint-r13')
    assert len(corrected['manifest']['patches']) == 144
    assert corrected['manifest']['patches'][:-1] == original['manifest']['patches']
    assert units.load_plan(corrected)['cases'] == units.load_plan(original)['cases']
    assert corrected['manifest_sha256'] != original['manifest_sha256']


@pytest.mark.parametrize('candidate', ('upstream-156-checkpoint-r12', 'upstream-156-checkpoint-r13'))
def test_checkpoint_cli_forwards_explicit_candidate(tmp_path, monkeypatch, candidate):
    execute = Mock(return_value={'passed': True})
    monkeypatch.setattr(units, 'verify', execute)
    monkeypatch.setattr(units.sys, 'argv', ['checkpoint', '--workspace', str(tmp_path),
                                           '--report-dir', str(tmp_path / 'reports'),
                                           '--candidate', candidate])
    assert units.main() == 0
    assert execute.call_args.kwargs['candidate_name'] == candidate
