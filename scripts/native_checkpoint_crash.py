"""Windows-only test controller. A qualified forced exit is not a gtest PASS."""
import ctypes
import hashlib
import json
import math
import re
import secrets
import sys
import time
from ctypes import wintypes
from pathlib import Path

from scripts.native_checkpoint_process import OwnedJobProcess, sample_owned_job, terminate_owned_job

from app.core.native.windows_process_tree import WindowsProcessTreeReader

FORCED_EXIT_CODE = 0x474C


class _BasicLimits(ctypes.Structure):
    _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                ('flags', wintypes.DWORD), ('min_working_set', ctypes.c_size_t),
                ('max_working_set', ctypes.c_size_t), ('active_limit', wintypes.DWORD),
                ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                ('scheduling', wintypes.DWORD)]


class _IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in
                ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [('basic', _BasicLimits), ('io', _IoCounters),
                ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]


class _Accounting(ctypes.Structure):
    _fields_ = [(name, ctypes.c_longlong) for name in
                ('user', 'kernel', 'period_user', 'period_kernel')] + [
                (name, wintypes.DWORD) for name in ('faults', 'total', 'active', 'terminated')]


class _OwnedJob:
    def __init__(self):
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                        ctypes.c_void_p, wintypes.DWORD]
        self.kernel.SetInformationJobObject.restype = wintypes.BOOL
        self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        self.kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel.TerminateJobObject.restype = wintypes.BOOL
        self.kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
            ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
        self.kernel.QueryInformationJobObject.restype = wintypes.BOOL
        self.kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE,
                                               ctypes.POINTER(wintypes.BOOL)]
        self.kernel.IsProcessInJob.restype = wintypes.BOOL
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = _ExtendedLimits()
        limits.basic.flags = 0x2000  # KILL_ON_JOB_CLOSE; no breakaway allowance.
        if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def assign(self, process):
        # Popen's held Windows process handle binds this exact owned child, not
        # a PID copied from an untrusted acknowledgment.
        if not self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def require_member(self, pid):
        handle = self.kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            present = wintypes.BOOL()
            if not self.kernel.IsProcessInJob(handle, self.handle, ctypes.byref(present)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not present.value:
                raise ValueError('Observed owned descendant is outside the crash-test job')
        finally:
            if not self.kernel.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())

    def active(self):
        sample = _Accounting()
        if not self.kernel.QueryInformationJobObject(self.handle, 1, ctypes.byref(sample),
                                                     ctypes.sizeof(sample), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return sample.active

    def terminate(self):
        if not self.kernel.TerminateJobObject(self.handle, FORCED_EXIT_CODE):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            handle, self.handle = self.handle, None
            if not self.kernel.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())


def checksum(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate acknowledgment field')
        result[key] = value
    return result


def validate_ack(record, *, pid, challenge, profile):
    if not isinstance(record, dict) or set(record) != {
            'schema', 'challenge', 'pid', 'profile', 'acknowledged', 'workers', 'scope'}:
        raise ValueError('Unexpected acknowledgment schema/fields')
    if type(record['schema']) is not int or record['schema'] != 1:
        raise ValueError('Invalid acknowledgment schema version')
    if type(record['pid']) is not int or record['pid'] != pid:
        raise ValueError('Acknowledgment PID is not the owned child')
    if record['challenge'] != challenge or not isinstance(record['challenge'], str):
        raise ValueError('Acknowledgment challenge did not match this invocation')
    if record['acknowledged'] is not True or record['scope'] != 'document-and-worker-cookie-prefix':
        raise ValueError('Acknowledgment does not certify the requested prefix')
    if type(record['workers']) is not int or not 1 <= record['workers'] <= 512:
        raise ValueError('Acknowledgment requires a bounded active worker cohort')
    if not isinstance(record['profile'], str):
        raise ValueError('Acknowledgment profile is not a path')  # noqa: TRY004 - untrusted receipt field
    supplied = Path(record['profile'])
    if not supplied.is_absolute() or supplied != profile or supplied.resolve() != profile:
        raise ValueError('Acknowledgment profile is not the owned test profile')


def run_acknowledged_crash(command, *, owner_root, output, cwd, env, expected_binary_sha256,
                           timeout_seconds=60.0, max_ack_to_kill_seconds=2.0):
    if sys.platform != 'win32':
        raise OSError('This crash controller requires Windows job/process identity checks')
    if any(type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 300
           for value in (timeout_seconds, max_ack_to_kill_seconds)):
        raise ValueError('Crash-test budgets must be finite and bounded')
    if (not isinstance(command, list) or not command or any(not isinstance(arg, str) for arg in command)
            or any(arg.startswith(('--user-data-dir', '--glint-crash-')) for arg in command[1:])):
        raise ValueError('Crash controller owns its profile/challenge/receipt switches')
    executable = Path(command[0])
    if (not executable.is_absolute() or executable.resolve() != executable or not executable.is_file()
            or not isinstance(expected_binary_sha256, str)
            or not re.fullmatch(r'[a-f0-9]{64}', expected_binary_sha256)
            or checksum(executable) != expected_binary_sha256):
        raise ValueError('Crash-test executable binding failed')
    if (owner_root != owner_root.resolve() or not owner_root.is_absolute() or not owner_root.is_dir()
            or output.parent != owner_root or output.resolve() != output or output.exists()):
        raise ValueError('Crash evidence requires a fresh child of its canonical owner directory')
    if (cwd != cwd.resolve() or not cwd.is_dir() or not isinstance(env, dict)
            or any(not isinstance(key, str) or not isinstance(value, str) for key, value in env.items())):
        raise ValueError('Crash test requires an explicit canonical cwd and string environment')
    output.mkdir(exist_ok=False)
    profile = output / 'profile'
    profile.mkdir()
    temporary = output / 'temp'
    temporary.mkdir()
    environment = dict(env, TEMP=str(temporary), TMP=str(temporary), PYTHONDONTWRITEBYTECODE='1')
    stat = profile.stat()
    profile_identity = (stat.st_dev, stat.st_ino)
    receipt = output / 'ack.json'
    challenge = secrets.token_hex(32)
    argv = [*command, '--user-data-dir=' + str(profile),
            '--glint-crash-challenge=' + challenge, '--glint-crash-ack=' + str(receipt)]
    record = {'schema': 1, 'passed': False, 'scope': 'Owned acknowledged forced-termination phase only',
        'executable_sha256': expected_binary_sha256, 'expected_exit_code': FORCED_EXIT_CODE,
        'output': str(output), 'profile': str(profile), 'qualified_termination': False,
        'gtest_completed': False, 'recovery_measured': False, 'production_admitted': False}
    child, job = None, None
    started = time.monotonic()
    try:
        job = _OwnedJob()
        with (output / 'process.log').open('xb') as log:
            child = OwnedJobProcess(argv, cwd=cwd, env=environment, stdout=log, job=job)
            record['owned_pid'] = child.pid
            record['job_assigned_at_creation'] = True
            job.require_member(child.pid)
            reader = WindowsProcessTreeReader()
            anchor = reader.read(child.pid)
            record['owned_created_100ns'] = anchor.created_100ns
            while not receipt.exists():
                if child.poll() is not None:
                    raise ValueError('Owned process exited before a qualified acknowledgment')
                if time.monotonic() - started >= timeout_seconds:
                    raise TimeoutError('Checkpoint acknowledgment deadline expired')
                time.sleep(0.02)
            if receipt.resolve() != receipt or receipt.stat().st_size > 16384:
                raise ValueError('Acknowledgment file is linked or oversized')
            with receipt.open('rb') as stream:
                raw = stream.read(16385)
            if len(raw) > 16384:
                raise ValueError('Acknowledgment exceeds the bounded payload size')
            acknowledged = json.loads(raw, object_pairs_hook=_unique_object)
            validate_ack(acknowledged, pid=child.pid, challenge=challenge, profile=profile)
            ack_time = time.monotonic()
            stat = profile.stat()
            if ((stat.st_dev, stat.st_ino) != profile_identity or profile.resolve() != profile
                    or not any(profile.iterdir())):
                raise ValueError('Requested profile identity/content was not retained')
            sample = sample_owned_job(job, reader, anchor)
            for process in sample:
                job.require_member(process.pid)
            reader.read(child.pid, expected_created_100ns=anchor.created_100ns)
            if child.poll() is not None or time.monotonic() - ack_time > max_ack_to_kill_seconds:
                raise ValueError('Acknowledged child exited or the bounded termination window elapsed')
            record['ack_sha256'] = hashlib.sha256(raw).hexdigest()
            record['observed_processes'] = [{'pid': p.pid, 'created_100ns': p.created_100ns}
                                       for p in sample]
            terminate_owned_job(job)
            record['exit_code'] = child.wait(timeout=5)
            deadline = time.monotonic() + 5
            while job.active():
                if time.monotonic() >= deadline:
                    raise TimeoutError('Owned crash-test job still has active descendants')
                time.sleep(0.02)
            delay = time.monotonic() - ack_time
            if record['exit_code'] != FORCED_EXIT_CODE or delay > max_ack_to_kill_seconds:
                raise ValueError('Forced exit outcome/time does not match the qualified test')
            if checksum(executable) != expected_binary_sha256:
                raise ValueError('Executable binding changed during crash test')
            record.update(passed=True, qualified_termination=True,
                          ack_to_exit_seconds=delay, remaining_job_processes=0)
    except Exception as error:  # noqa: BLE001 - retain a failed protocol receipt; cleanup is mandatory
        record['error'] = f'{type(error).__name__}: {error}'
    finally:
        try:
            if job:
                terminate_owned_job(job)
                if child:
                    child.wait(timeout=5)
                deadline = time.monotonic() + 5
                while job.active():
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Owned job cleanup did not finish')
                    time.sleep(0.02)
            record['owned_process_cleanup_complete'] = child is None or child.poll() is not None
        except Exception as error:  # noqa: BLE001 - cleanup failure must remain in the receipt
            record.update(passed=False, cleanup_error=f'{type(error).__name__}: {error}')
            if child and child.poll() is None:
                child.kill()
                child.wait(timeout=5)
        finally:
            if job:
                try:
                    job.close()
                except OSError as error:
                    record.update(passed=False, job_close_error=str(error))
        if child:
            try:
                child.close()
            except OSError as error:
                record.update(passed=False, process_handle_close_error=str(error))
        record['seconds'] = time.monotonic() - started
        (output / 'report.json').write_text(json.dumps(record, indent=2) + '\n',
                                          encoding='utf-8', newline='\n')
    return record
