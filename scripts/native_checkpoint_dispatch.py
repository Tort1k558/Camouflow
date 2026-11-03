"""Complete source-bound browser routing; not compiled/runtime admission."""
import hashlib
import json
import time
from pathlib import Path

from scripts.native_checkpoint_crash import _unique_object, checksum

from scripts import native_checkpoint_browser as pairs
from scripts import native_checkpoint_contract as contract
from scripts import native_checkpoint_crash as ack
from scripts import native_checkpoint_process as process
from scripts import native_checkpoint_recovery as crash

ROOT = Path(__file__).resolve().parents[1]


def classify_cases(required, plan, source):
    bindings = contract.validate_browser_contract(source, plan)
    rows = [row for row in plan['cases'] if row['binary'] == 'browser_tests']
    declared = [(row['fixture'], row['case']) for row in rows]
    if (not rows or len(set(declared)) != len(declared)
            or any(row['kind'] != 'IN_PROC_BROWSER_TEST_F' for row in rows)):
        raise ValueError('Browser plan has duplicate, empty or unbound declarations')
    groups = pairs.browser_case_groups(required)
    discovered = {(suite, case) for suite, phases in groups for case in phases}
    if discovered != set(declared):
        raise ValueError('Discovered browser cases differ from the complete declared selection')
    expected = {(crash.SUITE, crash.PRE_CASE), (crash.SUITE, crash.RECOVERY_CASE)}
    if not expected <= discovered:
        raise ValueError('The complete expected-crash pair is required')
    ordinary = {suite: set(cases) for suite, cases in required.items()}
    ordinary[crash.SUITE].difference_update((crash.PRE_CASE, crash.RECOVERY_CASE))
    ordinary = {suite: cases for suite, cases in ordinary.items() if cases}
    pairs.browser_case_groups(ordinary)
    return ordinary, bindings


def run_browser_dispatch(executable, required, *, plan_path, source, owner_root,
                         output, cwd, env, expected_binary_sha256, timeout_seconds=900):
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 900:
        raise ValueError('Shared browser budget must be an integer in 1..900 seconds')
    if (owner_root.resolve() != owner_root or not owner_root.is_dir()
            or output.parent != owner_root or output.resolve() != output or output.exists()
            or output.drive.upper() != 'D:' or output.is_relative_to(ROOT)
            or output.is_relative_to(source)):
        raise ValueError('Browser dispatch requires a fresh owned canonical D: report outside sources')
    bindings = crash.validate_source_contract(source, plan_path)
    with plan_path.open('rb') as stream:
        raw = stream.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != bindings[str(plan_path)]:
        raise ValueError('Browser case plan changed after bounded validation')
    plan = json.loads(raw, object_pairs_hook=_unique_object)
    ordinary, fixture_bindings = classify_cases(required, plan, source)
    bindings.update(fixture_bindings)
    bindings.update({plan_path: checksum(plan_path), Path(pairs.__file__): checksum(Path(pairs.__file__)),
        Path(__file__): checksum(Path(__file__)),
        Path(crash.__file__): checksum(Path(crash.__file__)),
        Path(ack.__file__): checksum(Path(ack.__file__)),
        Path(process.__file__): checksum(Path(process.__file__)),
        Path(contract.__file__): checksum(Path(contract.__file__))})

    def guard():
        if (checksum(executable) != expected_binary_sha256
                or any(checksum(Path(path)) != digest for path, digest in bindings.items())):
            raise ValueError('Browser binary, plan or bound runner/source changed')

    guard()
    expected_normal = {suite + '.' + case for suite, cases in ordinary.items() for case in cases}
    output.mkdir(exist_ok=False)
    report = {'schema': 1, 'passed': False, 'scope': 'Complete browser case dispatch; not runtime admission',
        'declared_cases': len(expected_normal) + 2, 'completed_gtest_cases': 0,
        'maximum_crash_phase_seconds': 300,
        'qualified_forced_termination_cases': 0, 'ordinary_runs': [],
        'native_provenance_verified': False, 'browser_durability_admitted': False, 'production_admitted': False,
        'executable_sha256': expected_binary_sha256,
        'input_sha256': {str(path): digest for path, digest in bindings.items()}}
    started = time.monotonic()

    def remaining():
        seconds = timeout_seconds - (time.monotonic() - started)
        if seconds <= 0:
            raise TimeoutError('Shared ordinary/crash browser execution budget exhausted')
        return seconds

    try:
        normal_dir = output / 'ordinary'
        normal_dir.mkdir()
        report['ordinary_runs'] = pairs.run_browser_cases(executable, ordinary,
            source=cwd, env=env, report_dir=normal_dir, timeout=remaining())
        rows = report['ordinary_runs']
        names = [row['case'] for row in rows]
        if (len(names) != len(expected_normal) or set(names) != expected_normal
                or any(row['passed'] is not True for row in rows)):
            raise ValueError('Ordinary browser execution is missing, duplicated, foreign or failed')
        report['completed_gtest_cases'] = len(rows)
        guard()
        forced = crash.run_crash_recovery([str(executable)], source=source, plan_path=plan_path,
            owner_root=output, output=output / 'acknowledged-crash', cwd=cwd, env=env,
            expected_binary_sha256=expected_binary_sha256, timeout_seconds=min(remaining(), 300))
        report['crash_recovery'] = forced
        if (forced['passed'] is not True or type(forced['completed_gtest_cases']) is not int
                or forced['completed_gtest_cases'] != 1
                or type(forced['qualified_forced_termination_cases']) is not int
                or forced['qualified_forced_termination_cases'] != 1
                or forced['post_profile_reopen_validated'] is not True):
            raise ValueError('Expected-crash termination and separate completed recovery were not both verified')
        report['completed_gtest_cases'] += 1
        report['qualified_forced_termination_cases'] = 1
        remaining()
        guard()
        report['passed'] = True
    except Exception as error:  # noqa: BLE001 - persist a failed dispatch receipt, never admission
        report['error'] = f'{type(error).__name__}: {error}'
    finally:
        report['seconds'] = time.monotonic() - started
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n',
                                           encoding='utf-8', newline='\n')
    return report
