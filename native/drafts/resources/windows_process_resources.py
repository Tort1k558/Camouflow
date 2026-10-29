"""Read-only Windows process metrics; not a profile enumerator or memory limiter."""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import sys
import time


class _MemoryCounters(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("page_faults", wintypes.DWORD),
                *[(name, ctypes.c_size_t) for name in (
                    "peak_working_set", "working_set", "peak_paged_pool", "paged_pool",
                    "peak_nonpaged_pool", "nonpaged_pool", "pagefile", "peak_pagefile", "private_usage")]]


def _ticks(value: wintypes.FILETIME) -> int:
    return (value.dwHighDateTime << 32) | value.dwLowDateTime


@dataclass(frozen=True)
class ProcessSample:
    pid: int
    created_100ns: int
    measured_ns: int
    kernel_100ns: int
    user_100ns: int
    working_set_bytes: int
    peak_working_set_bytes: int
    private_commit_bytes: int

    def __post_init__(self):
        for name, value in vars(self).items():
            if type(value) is not int or not 0 <= value <= 0xffffffffffffffff:
                raise ValueError("Invalid process sample field: " + name)
        if not 0 < self.pid <= 0xffffffff or not self.created_100ns or not self.measured_ns:
            raise ValueError("Process sample requires a PID, creation identity and monotonic timestamp")


def cpu_interval(previous: ProcessSample, current: ProcessSample) -> dict[str, float]:
    if (previous.pid, previous.created_100ns) != (current.pid, current.created_100ns):
        raise ValueError("Cannot compare different process identities or a reused PID")
    elapsed_ns = current.measured_ns - previous.measured_ns
    kernel = current.kernel_100ns - previous.kernel_100ns
    user = current.user_100ns - previous.user_100ns
    if elapsed_ns <= 0 or kernel < 0 or user < 0:
        raise ValueError("Process sample time and CPU counters must be monotonic")
    elapsed = elapsed_ns / 1_000_000_000
    cpu = (kernel + user) / 10_000_000
    return {"elapsed_seconds": elapsed, "cpu_seconds": cpu, "mean_cpu_cores": cpu / elapsed}


class WindowsProcessReader:
    def __init__(self):
        if sys.platform != "win32":
            raise OSError("Windows process resource measurement is not implemented on this platform")
        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self._kernel.OpenProcess.restype = wintypes.HANDLE
        self._kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *[ctypes.POINTER(wintypes.FILETIME)] * 4]
        self._kernel.GetProcessTimes.restype = wintypes.BOOL
        self._kernel.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_MemoryCounters), wintypes.DWORD]
        self._kernel.K32GetProcessMemoryInfo.restype = wintypes.BOOL
        self._kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self._kernel.WaitForSingleObject.restype = wintypes.DWORD
        self._kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel.CloseHandle.restype = wintypes.BOOL

    def _require_live(self, handle):
        status = self._kernel.WaitForSingleObject(handle, 0)
        if status == 0:
            raise ProcessLookupError("Process exited during resource measurement")
        if status == 0xffffffff:
            raise ctypes.WinError(ctypes.get_last_error())
        if status != 0x102:
            raise OSError("Unexpected process wait status")

    def read(self, pid: int, *, expected_created_100ns: int | None = None) -> ProcessSample:
        if type(pid) is not int or not 0 < pid <= 0xffffffff:
            raise ValueError("Expected a positive Windows PID")
        if expected_created_100ns is not None and (
                type(expected_created_100ns) is not int or expected_created_100ns <= 0):
            raise ValueError("Expected a positive process creation identity")
        # Query and zero-time liveness checks only: no VM writes or termination rights.
        handle = self._kernel.OpenProcess(0x1000 | 0x00100000, False, pid)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        failure = None
        try:
            self._require_live(handle)
            created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
            if not self._kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                                ctypes.byref(kernel), ctypes.byref(user)):
                raise ctypes.WinError(ctypes.get_last_error())
            identity = _ticks(created)
            if expected_created_100ns is not None and identity != expected_created_100ns:
                raise ValueError("Process creation identity changed; refusing a reused PID")
            counters = _MemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            if not self._kernel.K32GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                raise ctypes.WinError(ctypes.get_last_error())
            measured = time.monotonic_ns()
            self._require_live(handle)
            return ProcessSample(pid, identity, measured, _ticks(kernel), _ticks(user),
                                 counters.working_set, counters.peak_working_set, counters.private_usage)
        except BaseException as error:
            failure = error
            raise
        finally:
            if not self._kernel.CloseHandle(handle):
                error = ctypes.WinError(ctypes.get_last_error())
                if failure is None:
                    raise error
                failure.add_note("Process query handle cleanup failed: " + str(error))
