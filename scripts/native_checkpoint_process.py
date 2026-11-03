"""Create a private Windows child inside its job before its entry point can run."""
import ctypes
import math
import os
import subprocess
import sys
import time
from contextlib import ExitStack
from ctypes import wintypes
from pathlib import Path

if sys.platform == "win32":
    import msvcrt


class _StartupInfo(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('reserved', wintypes.LPWSTR),
        ('desktop', wintypes.LPWSTR), ('title', wintypes.LPWSTR),
        *[(name, wintypes.DWORD) for name in ('x', 'y', 'width', 'height',
          'chars_x', 'chars_y', 'fill', 'flags')],
        ('show', wintypes.WORD), ('reserved_size', wintypes.WORD),
        ('reserved_bytes', ctypes.c_void_p), ('stdin', wintypes.HANDLE),
        ('stdout', wintypes.HANDLE), ('stderr', wintypes.HANDLE)]


class _StartupInfoEx(ctypes.Structure):
    _fields_ = [('startup', _StartupInfo), ('attributes', ctypes.c_void_p)]


class _ProcessInformation(ctypes.Structure):
    _fields_ = [('process', wintypes.HANDLE), ('thread', wintypes.HANDLE),
               ('pid', wintypes.DWORD), ('tid', wintypes.DWORD)]


class OwnedJobProcess:
    def __init__(self, argv, *, cwd, env, stdout, job):
        if sys.platform != 'win32' or ctypes.sizeof(ctypes.c_void_p) != 8:
            raise OSError('Atomic job launch currently requires 64-bit Windows')
        if (not isinstance(argv, list) or not argv
                or any(not isinstance(arg, str) or '\0' in arg for arg in argv)
                or not Path(argv[0]).is_absolute() or cwd.resolve() != cwd or not cwd.is_dir()
                or not isinstance(env, dict) or not env
                or any(not isinstance(k, str) or not k or '=' in k or '\0' in k
                       or not isinstance(v, str) or '\0' in v for k, v in env.items())
                or len({key.casefold() for key in env}) != len(env)):
            raise ValueError('Atomic job launch requires exact argv, cwd and unambiguous environment')
        self.args = argv
        self.returncode = None
        self._handle = None
        self.kernel = kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.InitializeProcThreadAttributeList.argtypes = [ctypes.c_void_p, wintypes.DWORD,
            wintypes.DWORD, ctypes.POINTER(ctypes.c_size_t)]
        kernel.InitializeProcThreadAttributeList.restype = wintypes.BOOL
        kernel.UpdateProcThreadAttribute.argtypes = [ctypes.c_void_p, wintypes.DWORD,
            ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p]
        kernel.UpdateProcThreadAttribute.restype = wintypes.BOOL
        kernel.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
        kernel.DeleteProcThreadAttributeList.restype = None
        kernel.GetCurrentProcess.argtypes = []
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.DuplicateHandle.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE,
            ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.DuplicateHandle.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        kernel.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR,
            ctypes.c_void_p, ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD,
            ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_void_p,
            ctypes.POINTER(_ProcessInformation)]
        kernel.CreateProcessW.restype = wintypes.BOOL
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetExitCodeProcess.restype = wintypes.BOOL
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.TerminateProcess.restype = wintypes.BOOL
        if (ctypes.sizeof(_StartupInfo) != 104 or ctypes.sizeof(_StartupInfoEx) != 112
                or ctypes.sizeof(_ProcessInformation) != 24):
            raise RuntimeError('Windows startup ABI size mismatch')

        def close(handle):
            if not kernel.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())

        try:
            with ExitStack() as cleanup:
                size = ctypes.c_size_t()
                if kernel.InitializeProcThreadAttributeList(None, 2, 0, ctypes.byref(size)):
                    raise RuntimeError('Unexpected successful attribute sizing probe')
                if ctypes.get_last_error() != 122 or not 0 < size.value <= 65536:
                    raise ctypes.WinError(ctypes.get_last_error())
                attributes = ctypes.create_string_buffer(size.value)
                if not kernel.InitializeProcThreadAttributeList(attributes, 2, 0, ctypes.byref(size)):
                    raise ctypes.WinError(ctypes.get_last_error())
                cleanup.callback(kernel.DeleteProcThreadAttributeList, attributes)
                current = kernel.GetCurrentProcess()

                def duplicate(file):
                    handle = wintypes.HANDLE()
                    if not kernel.DuplicateHandle(current, msvcrt.get_osfhandle(file.fileno()),
                            current, ctypes.byref(handle), 0, True, 2):
                        raise ctypes.WinError(ctypes.get_last_error())
                    cleanup.callback(close, handle)
                    return handle.value

                stdin_file = cleanup.enter_context(open(os.devnull, 'rb'))
                inherited = (wintypes.HANDLE * 2)(duplicate(stdin_file), duplicate(stdout))
                jobs = (wintypes.HANDLE * 1)(job.handle)
                # Exact SDK constants: HANDLE_LIST (2) and JOB_LIST (13), input bit.
                for kind, value in ((0x00020002, inherited), (0x0002000D, jobs)):
                    if not kernel.UpdateProcThreadAttribute(attributes, 0, kind, value,
                            ctypes.sizeof(value), None, None):
                        raise ctypes.WinError(ctypes.get_last_error())
                startup = _StartupInfoEx()
                startup.startup.cb = ctypes.sizeof(startup)
                startup.startup.flags = 0x00000100  # STARTF_USESTDHANDLES.
                startup.startup.stdin = inherited[0]
                startup.startup.stdout = startup.startup.stderr = inherited[1]
                startup.attributes = ctypes.cast(attributes, ctypes.c_void_p)
                command = ctypes.create_unicode_buffer(subprocess.list2cmdline(argv))
                environment = ctypes.create_unicode_buffer('\0'.join(
                    key + '=' + value for key, value in sorted(env.items(), key=lambda item: item[0].casefold())) + '\0\0')
                info = _ProcessInformation()
                # EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW.
                if not kernel.CreateProcessW(argv[0], command, None, None, True, 0x08080400,
                        environment, str(cwd), ctypes.byref(startup), ctypes.byref(info)):
                    raise ctypes.WinError(ctypes.get_last_error())
                self._handle, self.pid = info.process, info.pid
                close(info.thread)
        except BaseException:
            if self._handle:
                try:
                    self.kill()
                    self.wait(timeout=5)
                finally:
                    self.close()
            raise

    def poll(self):
        if self.returncode is not None:
            return self.returncode
        state = self.kernel.WaitForSingleObject(self._handle, 0)
        if state == 258:
            return None
        if state != 0:
            raise ctypes.WinError(ctypes.get_last_error())
        code = wintypes.DWORD()
        if not self.kernel.GetExitCodeProcess(self._handle, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        self.returncode = code.value
        return self.returncode

    def wait(self, timeout):
        milliseconds = min(math.ceil(max(0, timeout) * 1000), 0xFFFFFFFE)
        state = self.kernel.WaitForSingleObject(self._handle, milliseconds)
        if state == 258:
            raise subprocess.TimeoutExpired(self.args, timeout)
        if state != 0:
            raise ctypes.WinError(ctypes.get_last_error())
        return self.poll()

    def kill(self):
        if self.poll() is None and not self.kernel.TerminateProcess(self._handle, 1):
            if self.poll() is None:
                raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self._handle:
            if not self.kernel.CloseHandle(self._handle):
                raise ctypes.WinError(ctypes.get_last_error())
            self._handle = None


def _owned_job_handles(job):
    class ProcessList(ctypes.Structure):
        _fields_ = [('assigned', wintypes.DWORD), ('count', wintypes.DWORD),
                    ('pids', ctypes.c_size_t * 4096)]

    sample = ProcessList()
    if not job.kernel.QueryInformationJobObject(job.handle, 3, ctypes.byref(sample),
                                                ctypes.sizeof(sample), None):
        raise ctypes.WinError(ctypes.get_last_error())
    if sample.count > 4096 or sample.assigned != sample.count:
        raise ValueError('Owned job process list is incomplete')
    handles = []
    try:
        for pid in sample.pids[:sample.count]:
            handle = job.kernel.OpenProcess(0x101000, False, pid)
            if not handle:
                if ctypes.get_last_error() == 87:
                    continue
                raise ctypes.WinError(ctypes.get_last_error())
            handles.append(handle)
            present = wintypes.BOOL()
            if not job.kernel.IsProcessInJob(handle, job.handle, ctypes.byref(present)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not present.value:
                raise ValueError('Owned process identity changed outside its job')
        return handles
    except BaseException:
        for handle in handles:
            job.kernel.CloseHandle(handle)
        raise


def terminate_owned_job(job, *, timeout=5):
    """Terminate the exact owned job and await held member handles, never PIDs."""
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout) or not 0 < timeout <= 5):
        raise ValueError('Owned job cleanup deadline must be finite and within five seconds')
    handles = []
    try:
        try:
            handles = _owned_job_handles(job)
        finally:
            job.terminate()
        job.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        job.kernel.WaitForSingleObject.restype = wintypes.DWORD
        deadline = time.monotonic() + timeout
        for handle in handles:
            milliseconds = max(0, int((deadline - time.monotonic()) * 1000))
            if job.kernel.WaitForSingleObject(handle, milliseconds) != 0:
                raise RuntimeError('Owned job member did not finish termination')
        while job.active():
            if time.monotonic() >= deadline:
                raise TimeoutError('Owned job cleanup deadline exceeded')
            time.sleep(0.01)
    finally:
        with ExitStack() as cleanup:
            for handle in handles:
                cleanup.callback(_close_job_member_handle, job, handle)


def _close_job_member_handle(job, handle):
    if not job.kernel.CloseHandle(handle):
        raise ctypes.WinError(ctypes.get_last_error())


def sample_owned_job(job, reader, anchor):
    """Bind measurements to job membership, not reusable global parent PID links."""
    kernel = job.kernel
    kernel.GetProcessId.argtypes = [wintypes.HANDLE]
    kernel.GetProcessId.restype = wintypes.DWORD

    def identify(handles):
        pids = [kernel.GetProcessId(handle) for handle in handles]
        if not pids or len(pids) > 512 or 0 in pids or len(set(pids)) != len(pids):
            raise ValueError('Owned job measurement has invalid or unbounded process identities')
        if anchor.pid not in pids:
            raise ValueError('Owned measurement root is absent from its job')
        return set(pids)

    with ExitStack() as cleanup:
        handles = _owned_job_handles(job)
        for handle in handles:
            cleanup.callback(_close_job_member_handle, job, handle)
        pids = identify(handles)
        samples = [reader.read(pid, expected_created_100ns=(
            anchor.created_100ns if pid == anchor.pid else None)) for pid in sorted(pids)]
        if any(sample.created_100ns < anchor.created_100ns for sample in samples):
            raise ValueError('Owned job member predates the trusted root')
        measured = tuple(reader.read(sample.pid, expected_created_100ns=sample.created_100ns)
                         for sample in samples)
        final_handles = _owned_job_handles(job)
        for handle in final_handles:
            cleanup.callback(_close_job_member_handle, job, handle)
        if identify(final_handles) != pids:
            raise ValueError('Owned job membership changed during measurement')
        return measured
