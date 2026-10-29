"""Connection-bound, read-only browser telemetry. No process control or limits."""

import asyncio
import threading

from .windows_process_resources import ProcessSample
from .windows_process_tree import ProcessTreeSample, WindowsProcessTreeReader, tree_cpu_interval


def browser_pid(response):
    rows = response.get("processInfo") if isinstance(response, dict) else None
    if not isinstance(rows, list) or not 1 <= len(rows) <= 512:
        raise ValueError("Expected a bounded browser process report")
    roots = [row for row in rows if isinstance(row, dict) and row.get("type") == "browser"]
    if len(roots) != 1:
        raise ValueError("Expected exactly one owned browser process")
    pid = roots[0].get("id")
    if type(pid) is not int or not 0 < pid <= 0xffffffff:
        raise ValueError("Invalid browser-reported root PID")
    return pid


class BrowserProcessMonitor:
    def __init__(self, reader, anchor):
        if not isinstance(anchor, ProcessSample):
            raise ValueError("Telemetry requires a creation-bound root sample")
        self._reader = reader
        self._anchor = anchor
        self._previous = None
        self._active = True
        self._generation = 0
        self._state_lock = threading.Lock()
        self._sampling_lock = threading.Lock()
        self._bindings = ()
        self._loop = None

    @classmethod
    async def bind(cls, context):
        browser = context.browser
        if browser is None or not browser.is_connected():
            raise RuntimeError("A live owned browser connection is required")
        reader = WindowsProcessTreeReader()
        session = await browser.new_browser_cdp_session()
        primary = None
        try:
            pid = browser_pid(await session.send("SystemInfo.getProcessInfo"))
            anchor = await asyncio.to_thread(reader.read, pid)
            if not isinstance(anchor, ProcessSample) or anchor.pid != pid:
                raise ValueError("Process reader returned a different browser root")
            if browser_pid(await session.send("SystemInfo.getProcessInfo")) != pid or not browser.is_connected():
                raise RuntimeError("Browser connection changed while binding telemetry")
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                await session.detach()
            except Exception as error:
                if primary is None:
                    raise
                primary.add_note("Telemetry session cleanup failed: " + str(error))
        monitor = cls(reader, anchor)
        monitor._loop = asyncio.get_running_loop()
        callback = lambda *_: monitor.invalidate()
        monitor._bindings = ((context, "close", callback), (browser, "disconnected", callback))
        try:
            for emitter, event, listener in monitor._bindings:
                emitter.on(event, listener)
            if not browser.is_connected():
                raise RuntimeError("Browser disconnected before telemetry binding completed")
        except BaseException as primary:
            try:
                await monitor.close()
            except Exception as error:
                primary.add_note("Telemetry binding cleanup failed: " + str(error))
            raise
        return monitor

    def invalidate(self):
        with self._state_lock:
            self._active = False
            self._generation += 1
            self._previous = None

    async def close(self):
        self.invalidate()
        if self._loop is not None and asyncio.get_running_loop() is not self._loop:
            raise RuntimeError("Telemetry listeners must close on their owning event loop")
        bindings, self._bindings = self._bindings, ()
        failures = []
        retained = []
        for emitter, event, listener in bindings:
            try:
                emitter.remove_listener(event, listener)
            except Exception as error:
                failures.append(error)
                retained.append((emitter, event, listener))
        self._bindings = tuple(retained)
        if failures:
            raise ExceptionGroup("Browser telemetry listener cleanup failed", failures)

    def sample(self):
        if not self._sampling_lock.acquire(blocking=False):
            raise RuntimeError("A browser telemetry capture is already running")
        try:
            with self._state_lock:
                if not self._active:
                    raise RuntimeError("Browser telemetry ownership has ended")
                generation = self._generation
                previous = self._previous
            current = self._reader.read_tree(self._anchor)
            if not isinstance(current, ProcessTreeSample) or (
                    current.root_pid, current.root_created_100ns) != (self._anchor.pid, self._anchor.created_100ns):
                raise ValueError("Telemetry root differs from its bound browser identity")
            cpu = {"state": "warming"}
            if previous is not None:
                try:
                    cpu = {"state": "ready", **tree_cpu_interval(previous, current)}
                except ValueError as error:
                    cpu = {"state": "unavailable", "reason": str(error)}
            with self._state_lock:
                if not self._active or generation != self._generation:
                    raise RuntimeError("Browser telemetry ownership ended during capture")
                self._previous = current
            return {"schema": 1, "root_pid": current.root_pid, "process_count": len(current.processes),
                    "working_set_sum_bytes": current.summed_working_set_bytes,
                    "private_commit_sum_bytes": current.summed_private_commit_bytes,
                    "capture_duration_ns": current.measured_ns - current.capture_started_ns,
                    "cpu": cpu}
        finally:
            self._sampling_lock.release()
