"""Source-bound crash/reopen checks; compiled provenance remains a caller gate."""
import hashlib
import json
import math
import re
import stat
import subprocess
import time
from pathlib import Path

from scripts.native_checkpoint_contract import (
    CRASH_POST_CASE as RECOVERY_CASE,
)
from scripts.native_checkpoint_contract import (
    CRASH_PRE_CASE as PRE_CASE,
)
from scripts.native_checkpoint_contract import (
    CRASH_SUITE as SUITE,
)
from scripts.native_checkpoint_contract import (
    validate_browser_contract,
)
from scripts.native_checkpoint_crash import (
    _OwnedJob,
    _unique_object,
    checksum,
    run_acknowledged_crash,
    validate_ack,
)
from scripts.native_checkpoint_process import OwnedJobProcess, terminate_owned_job

from scripts.verify_native_checkpoint_units import validate_results


def validate_source_contract(source, plan_path):
    before = plan_path.lstat()
    if (not plan_path.is_absolute() or plan_path.resolve(strict=True) != plan_path
            or not stat.S_ISREG(before.st_mode)
            or getattr(before, 'st_file_attributes', 0) & 0x400
            or not 0 < before.st_size <= 4 * 1024 * 1024):
        raise ValueError('Browser case plan must be a bounded canonical regular file')
    with plan_path.open('rb') as stream:
        raw = stream.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('Browser case plan exceeds its size limit')
    plan = json.loads(raw, object_pairs_hook=_unique_object)
    bindings = validate_browser_contract(source, plan)
    after = plan_path.lstat()
    if (plan_path.resolve(strict=True) != plan_path
            or any(getattr(before, key) != getattr(after, key)
                   for key in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns'))):
        raise ValueError('Browser case plan identity changed during validation')
    bindings[str(plan_path)] = hashlib.sha256(raw).hexdigest()
    return bindings


def _run_recovery_process(command, *, source, env, log, timeout):
    """Keep recovery descendants owned even if their parent exits first."""
    job, child = None, None
    try:
        with log.open('xb') as stream:
            job = _OwnedJob()
            child = OwnedJobProcess(command, cwd=source, env=env, stdout=stream, job=job)
            code = child.wait(timeout=timeout)
            if code:
                raise subprocess.CalledProcessError(code, command)
    finally:
        try:
            if job:
                terminate_owned_job(job)
            if child:
                child.wait(timeout=5)
            if job and job.active():
                raise RuntimeError('Recovery job still contains owned processes')
        finally:
            try:
                if job:
                    job.close()
            finally:
                if child:
                    child.close()


def run_crash_recovery(prefix, *, source, plan_path, owner_root, output, cwd, env,
                       expected_binary_sha256, timeout_seconds=120):
    if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 300):
        raise ValueError('Shared crash/recovery budget must be finite and within 300 seconds')
    bindings = validate_source_contract(source, plan_path)
    for name in (Path(__file__).name, 'native_checkpoint_crash.py', 'native_checkpoint_process.py',
                 'native_checkpoint_contract.py'):
        path = Path(__file__).parent / name
        bindings[str(path)] = checksum(path)
    if (not isinstance(prefix, list) or not prefix or
            any(not isinstance(arg, str) for arg in prefix) or
            any(arg.startswith(('--gtest', '--single-process-tests', '--user-data-dir', '--glint-crash-'))
                for arg in prefix[1:])):
        raise ValueError('Crash/recovery runner owns its exact test/profile switches')
    started = time.monotonic()
    measured = {'schema': 1, 'passed': False,
        'scope': 'Owned source-bound crash/reopen process protocol; not standalone browser admission',
        'expected_crash_case': SUITE + '.' + PRE_CASE,
        'recovery_case': SUITE + '.' + RECOVERY_CASE,
        'completed_gtest_cases': 0, 'qualified_forced_termination_cases': 0,
        'post_profile_reopen_validated': False, 'browser_durability_admitted': False,
        'production_admitted': False, 'source_contract_sha256': bindings}
    forced = None
    try:
        pre_json = output / 'pre-tests.json'
        forced = run_acknowledged_crash(
            [*prefix, '--gtest_filter=' + SUITE + '.' + PRE_CASE,
             '--single-process-tests', '--gtest_output=json:' + str(pre_json)],
            owner_root=owner_root, output=output, cwd=cwd, env=env,
            expected_binary_sha256=expected_binary_sha256, timeout_seconds=timeout_seconds)
        measured['forced_phase_passed'] = forced['passed']
        if not forced['passed'] or not forced['qualified_termination']:
            raise ValueError('Intentional forced phase was not qualified')
        measured['qualified_forced_termination_cases'] = 1
        if pre_json.exists():
            raise ValueError('Intentional crash phase unexpectedly produced a completed gtest result')
        if checksum(Path(prefix[0])) != expected_binary_sha256:
            raise ValueError('Executable binding changed before recovery')
        if any(checksum(Path(path)) != digest for path, digest in bindings.items()):
            raise ValueError('Source contract changed before recovery')
        profile = Path(forced['profile'])
        if profile.parent != output or profile.resolve() != profile or not profile.is_dir():
            raise ValueError('Owned profile changed before recovery')
        stat = profile.stat()
        profile_identity = (stat.st_dev, stat.st_ino)
        ack_path = output / 'ack.json'
        if ack_path.resolve() != ack_path:
            raise ValueError('Qualified acknowledgment became linked before recovery')
        with ack_path.open('rb') as stream:
            raw = stream.read(16385)
        if len(raw) > 16384 or hashlib.sha256(raw).hexdigest() != forced['ack_sha256']:
            raise ValueError('Qualified acknowledgment changed before recovery')
        ack = json.loads(raw, object_pairs_hook=_unique_object)
        validate_ack(ack, pid=forced['owned_pid'], challenge=ack['challenge'], profile=profile)
        if not re.fullmatch(r'[a-f0-9]{64}', ack['challenge']):
            raise ValueError('Qualified challenge is not the required invocation nonce')
        remaining = timeout_seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError('Shared crash/recovery budget exhausted')
        results = output / 'recovery-tests.json'
        if results.exists():
            raise ValueError('Recovery result file must be fresh')
        environment = dict(env, TEMP=str(output / 'temp'), TMP=str(output / 'temp'),
                           PYTHONDONTWRITEBYTECODE='1')
        command = [*prefix, '--gtest_filter=' + SUITE + '.' + RECOVERY_CASE,
                   '--single-process-tests', '--gtest_output=json:' + str(results),
                   '--user-data-dir=' + str(profile), '--glint-crash-challenge=' + ack['challenge']]
        _run_recovery_process(command, source=cwd, env=environment,
                              log=output / 'recovery.log', timeout=remaining)
        validate_results(json.loads(results.read_bytes(), object_pairs_hook=_unique_object),
                         {SUITE: {RECOVERY_CASE}})
        stat = profile.stat()
        if (profile.resolve() != profile or (stat.st_dev, stat.st_ino) != profile_identity
                or checksum(Path(prefix[0])) != expected_binary_sha256
                or any(checksum(Path(path)) != digest for path, digest in bindings.items())):
            raise ValueError('Profile, executable or source contract changed during recovery')
        measured.update(passed=True, completed_gtest_cases=1,
                        post_profile_reopen_validated=True, recovery_results_sha256=checksum(results))
    except Exception as error:  # noqa: BLE001 - report a failed pair without admitting recovery
        measured['error'] = f'{type(error).__name__}: {error}'
    finally:
        measured['seconds'] = time.monotonic() - started
        if forced is not None:
            measured['forced_phase_report_sha256'] = checksum(output / 'report.json')
            (output / 'pair-report.json').write_text(json.dumps(measured, indent=2) + '\n',
                                                    encoding='utf-8', newline='\n')
    return measured
