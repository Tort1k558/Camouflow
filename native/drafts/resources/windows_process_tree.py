"""Creation-bound, read-only process-tree samples; no profile discovery or limits."""

from collections import deque
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import time

from .windows_process_resources import ProcessSample, WindowsProcessReader, cpu_interval


MAX_SNAPSHOT_PROCESSES = 65536
MAX_TREE_PROCESSES = 512


class _ProcessEntry(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD),
                ("heap", ctypes.c_size_t), ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
                ("parent_pid", wintypes.DWORD), ("priority", wintypes.LONG), ("flags", wintypes.DWORD),
                ("image", wintypes.WCHAR * 260)]


@dataclass(frozen=True)
class ProcessNode:
    pid: int
    parent_pid: int
    image: str

    def __post_init__(self):
        if any(type(value) is not int or not 0 <= value <= 0xffffffff for value in (self.pid, self.parent_pid)):
            raise ValueError("Invalid process snapshot PID")
        if not isinstance(self.image, str) or not self.image or len(self.image) > 260 or "\0" in self.image:
            raise ValueError("Invalid process snapshot image name")


def descendants(rows: tuple[ProcessNode, ...], root_pid: int) -> tuple[ProcessNode, ...]:
    if type(root_pid) is not int or not 0 < root_pid <= 0xffffffff:
        raise ValueError("Expected a positive process-tree root PID")
    if not isinstance(rows, tuple) or len(rows) > MAX_SNAPSHOT_PROCESSES:
        raise ValueError("Process snapshot must be a bounded tuple")
    indexed = {}
    children = {}
    for node in rows:
        if not isinstance(node, ProcessNode) or node.pid in indexed:
            raise ValueError("Invalid or duplicate process snapshot entry")
        indexed[node.pid] = node
        children.setdefault(node.parent_pid, []).append(node.pid)
    if root_pid not in indexed:
        raise ProcessLookupError("Process-tree root is absent from snapshot")
    pending = deque([root_pid])
    selected = {}
    while pending:
        pid = pending.popleft()
        if pid in selected:
            raise ValueError("Process snapshot contains a cycle in the selected tree")
        selected[pid] = indexed[pid]
        if len(selected) > MAX_TREE_PROCESSES:
            raise ValueError("Process tree exceeds its measurement bound")
        pending.extend(sorted(children.get(pid, ())))
    return tuple(selected.values())


@dataclass(frozen=True)
class ProcessTreeSample:
    root_pid: int
    root_created_100ns: int
    capture_started_ns: int
    measured_ns: int
    processes: tuple[ProcessSample, ...]

    def __post_init__(self):
        if (type(self.root_pid) is not int or not 0 < self.root_pid <= 0xffffffff
                or type(self.root_created_100ns) is not int or not 0 < self.root_created_100ns <= 0xffffffffffffffff):
            raise ValueError("Invalid process-tree root identity")
        if not isinstance(self.processes, tuple) or not 1 <= len(self.processes) <= MAX_TREE_PROCESSES:
            raise ValueError("Process-tree sample requires bounded process samples")
        if any(not isinstance(sample, ProcessSample) for sample in self.processes):
            raise ValueError("Invalid process-tree sample")
        indexed = {sample.pid: sample for sample in self.processes}
        if len(indexed) != len(self.processes) or self.root_pid not in indexed:
            raise ValueError("Process-tree sample has duplicate PIDs or no root")
        root = indexed[self.root_pid]
        if root.created_100ns != self.root_created_100ns:
            raise ValueError("Process-tree root identity does not match its sample")
        if (type(self.capture_started_ns) is not int or type(self.measured_ns) is not int
                or not 0 < self.capture_started_ns <= self.measured_ns <= 0xffffffffffffffff):
            raise ValueError("Invalid process-tree capture interval")
        if any(sample.created_100ns < root.created_100ns
               or not self.capture_started_ns <= sample.measured_ns <= self.measured_ns for sample in self.processes):
            raise ValueError("Process sample lies outside its root lifetime or capture interval")

    @property
    def summed_working_set_bytes(self) -> int:
        return sum(sample.working_set_bytes for sample in self.processes)

    @property
    def summed_private_commit_bytes(self) -> int:
        return sum(sample.private_commit_bytes for sample in self.processes)


def tree_cpu_interval(previous: ProcessTreeSample, current: ProcessTreeSample) -> dict[str, float]:
    if (previous.root_pid, previous.root_created_100ns) != (current.root_pid, current.root_created_100ns):
        raise ValueError("Cannot compare different process-tree roots")
    before = {sample.pid: sample for sample in previous.processes}
    after = {sample.pid: sample for sample in current.processes}
    if before.keys() != after.keys():
        raise ValueError("Process-tree membership changed; a complete CPU interval is unavailable")
    elapsed = (current.measured_ns - previous.measured_ns) / 1_000_000_000
    if elapsed <= 0:
        raise ValueError("Process-tree sample clock must increase")
    cpu = sum(cpu_interval(before[pid], sample)["cpu_seconds"] for pid, sample in after.items())
    return {"elapsed_seconds": elapsed, "cpu_seconds": cpu, "mean_cpu_cores": cpu / elapsed}


class WindowsProcessTreeReader(WindowsProcessReader):
    def __init__(self):
        super().__init__()
        self._kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        self._kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        for name in ("Process32FirstW", "Process32NextW"):
            function = getattr(self._kernel, name)
            function.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
            function.restype = wintypes.BOOL

    def snapshot(self) -> tuple[ProcessNode, ...]:
        handle = self._kernel.CreateToolhelp32Snapshot(0x2, 0)
        if handle == ctypes.c_void_p(-1).value or not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        failure = None
        try:
            entry = _ProcessEntry()
            entry.size = ctypes.sizeof(entry)
            rows = []
            succeeded = self._kernel.Process32FirstW(handle, ctypes.byref(entry))
            while succeeded:
                rows.append(ProcessNode(entry.pid, entry.parent_pid, entry.image))
                if len(rows) > MAX_SNAPSHOT_PROCESSES:
                    raise ValueError("Process snapshot exceeds its measurement bound")
                succeeded = self._kernel.Process32NextW(handle, ctypes.byref(entry))
            if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
                raise ctypes.WinError(ctypes.get_last_error())
            return tuple(rows)
        except BaseException as error:
            failure = error
            raise
        finally:
            self._close_handle(handle, failure)

    def read_tree(self, anchor: ProcessSample) -> ProcessTreeSample:
        if not isinstance(anchor, ProcessSample):
            raise ValueError("Process-tree measurement requires a trusted live root sample")
        started = time.monotonic_ns()
        before = descendants(self.snapshot(), anchor.pid)
        samples = {}
        for node in before:
            sample = self.read(node.pid, expected_created_100ns=anchor.created_100ns if node.pid == anchor.pid else None)
            if node.pid != anchor.pid and sample.created_100ns < samples[node.parent_pid].created_100ns:
                raise ValueError("Process snapshot references a reused parent PID")
            samples[node.pid] = sample
        # Recheck every identity, then require the same observed parent/name topology.
        measured = tuple(self.read(sample.pid, expected_created_100ns=sample.created_100ns) for sample in samples.values())
        after = descendants(self.snapshot(), anchor.pid)
        if before != after:
            raise ValueError("Process tree changed during measurement; no complete totals are returned")
        return ProcessTreeSample(anchor.pid, anchor.created_100ns, started, time.monotonic_ns(), measured)
