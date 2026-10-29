import asyncio
from types import SimpleNamespace

import pytest

from app.core.native import process_monitor as module
ProcessSample = module.ProcessSample


def anchor():
    return ProcessSample(10, 100, 1000, 0, 0, 10, 20, 30)


def tree(tick=1, child=False, pid=10):
    start = tick * 10000
    samples = [ProcessSample(pid, 100, start + 1, tick, tick, 10, 20, 30)]
    if child:
        samples.append(ProcessSample(11, 101, start + 2, tick, tick, 20, 30, 40))
    return module.ProcessTreeSample(pid, 100, start, start + 10, tuple(samples))


def monitor_with(*values):
    values = iter(values)
    return module.BrowserProcessMonitor(SimpleNamespace(read_tree=lambda root: next(values)), anchor())


def test_complete_samples_expose_unambiguous_units_and_cpu_warmup():
    monitor = monitor_with(tree(1), tree(2))
    first, second = monitor.sample(), monitor.sample()
    assert first["working_set_sum_bytes"] == 10 and first["private_commit_sum_bytes"] == 30
    assert first["cpu"] == {"state": "warming"}
    assert second["cpu"]["state"] == "ready" and second["cpu"]["mean_cpu_cores"] > 0
    assert "memory_mb" not in first and "over_limit" not in first


def test_membership_change_keeps_complete_memory_but_never_fabricates_cpu_zero():
    monitor = monitor_with(tree(1), tree(2, child=True), tree(3, child=True))
    monitor.sample()
    changed = monitor.sample()
    assert changed["process_count"] == 2 and changed["working_set_sum_bytes"] == 30
    assert changed["cpu"]["state"] == "unavailable" and "mean_cpu_cores" not in changed["cpu"]
    assert monitor.sample()["cpu"]["state"] == "ready"


def test_invalidated_owner_never_reads_native_state():
    monitor = monitor_with()
    monitor.invalidate()
    with pytest.raises(RuntimeError, match="ownership has ended"):
        monitor.sample()


def test_capture_finishing_after_invalidation_is_rejected():
    monitor = monitor_with()
    def capture(root):
        monitor.invalidate()
        return tree()
    monitor._reader.read_tree = capture
    with pytest.raises(RuntimeError, match="ended during capture"):
        monitor.sample()
    assert monitor._previous is None


def test_busy_sampler_does_not_queue_or_release_another_capture():
    monitor = monitor_with()
    monitor._sampling_lock.acquire()
    with pytest.raises(RuntimeError, match="already running"):
        monitor.sample()
    assert monitor._sampling_lock.locked()
    monitor._sampling_lock.release()


def test_unexpected_root_is_not_accepted_as_another_profile():
    monitor = monitor_with(tree(pid=12))
    with pytest.raises(ValueError, match="bound browser identity"):
        monitor.sample()
    assert monitor._previous is None


def test_exited_process_error_is_not_retried_or_replaced():
    count = []
    def capture(root):
        count.append(root.pid)
        raise ProcessLookupError("Owned exited process")
    monitor = module.BrowserProcessMonitor(SimpleNamespace(read_tree=capture), anchor())
    with pytest.raises(ProcessLookupError, match="Owned exited"):
        monitor.sample()
    assert count == [10] and not monitor._sampling_lock.locked()


@pytest.mark.parametrize("response", [None, {}, {"processInfo": []}, {"processInfo": [None]},
    {"processInfo": [{"type": "browser", "id": True}]}, {"processInfo": [{"type": "browser", "id": 0}]},
    {"processInfo": [{"type": "browser", "id": 10}] * 2}, {"processInfo": [{}] * 513}])
def test_browser_root_report_rejects_invalid_or_ambiguous_inputs(response):
    with pytest.raises(ValueError):
        module.browser_pid(response)


class Emitter:
    def __init__(self):
        self.events = {}
        self.remove_failure = None

    def on(self, event, callback):
        self.events.setdefault(event, []).append(callback)

    def remove_listener(self, event, callback):
        if event == self.remove_failure:
            raise OSError("Owned listener removal failure")
        if callback in self.events.get(event, []):
            self.events[event].remove(callback)


def owned_connection(monkeypatch, *, roots=(10, 10), detach_failure=False):
    roots = iter(roots)
    session = SimpleNamespace(detached=0)
    async def send(method):
        assert method == "SystemInfo.getProcessInfo"
        return {"processInfo": [{"type": "browser", "id": next(roots)}]}
    async def detach():
        session.detached += 1
        if detach_failure:
            raise OSError("Owned detach failure")
    session.send, session.detach = send, detach
    browser, context = Emitter(), Emitter()
    browser.is_connected = lambda: True
    async def connect():
        return session
    browser.new_browser_cdp_session = connect
    context.browser = browser
    monkeypatch.setattr(module, "WindowsProcessTreeReader", lambda: SimpleNamespace(read=lambda pid: anchor(), read_tree=lambda root: tree()))
    return context, browser, session


def test_real_binding_contract_closes_session_and_invalidates_on_context_close(monkeypatch):
    context, browser, session = owned_connection(monkeypatch)
    async def run():
        monitor = await module.BrowserProcessMonitor.bind(context)
        assert session.detached == 1 and monitor.sample()["root_pid"] == 10
        context.events["close"][0](context)
        with pytest.raises(RuntimeError, match="ownership has ended"):
            monitor.sample()
        await monitor.close()
        assert not monitor._bindings and not context.events["close"] and not browser.events["disconnected"]
    asyncio.run(run())


def test_changed_browser_root_rejects_binding_and_preserves_primary_cleanup_error(monkeypatch):
    context, browser, session = owned_connection(monkeypatch, roots=(10, 12), detach_failure=True)
    with pytest.raises(RuntimeError, match="changed while binding") as caught:
        asyncio.run(module.BrowserProcessMonitor.bind(context))
    assert session.detached == 1 and "Owned detach failure" in " ".join(caught.value.__notes__)
    assert not context.events and not browser.events


def test_reader_cannot_substitute_another_process_for_the_authenticated_root(monkeypatch):
    context, browser, session = owned_connection(monkeypatch, roots=(12, 12))
    with pytest.raises(ValueError, match="different browser root"):
        asyncio.run(module.BrowserProcessMonitor.bind(context))
    assert session.detached == 1 and not context.events and not browser.events


def test_failed_listener_cleanup_remains_retryable(monkeypatch):
    context, browser, _ = owned_connection(monkeypatch)
    async def run():
        monitor = await module.BrowserProcessMonitor.bind(context)
        context.remove_failure = "close"
        with pytest.raises(ExceptionGroup, match="listener cleanup failed"):
            await monitor.close()
        assert len(monitor._bindings) == 1 and not browser.events["disconnected"]
        context.remove_failure = None
        await monitor.close()
        assert not monitor._bindings and not context.events["close"]
    asyncio.run(run())


def test_native_interface_rechecks_runtime_after_closing_previous_telemetry(monkeypatch):
    from app.core.browser_interface import BrowserInterface
    from app.core.native import distribution
    from unittest.mock import AsyncMock

    browser = BrowserInterface.__new__(BrowserInterface)
    browser._native_runtime = None
    browser._browser_settings = {}
    owner = SimpleNamespace(has_resources=True)
    async def close():
        browser._native_runtime = owner
    monitor = SimpleNamespace(close=AsyncMock(side_effect=close))
    browser._native_process_monitor = monitor
    monkeypatch.setattr(distribution, "resolve_native_executable", lambda settings: __file__)
    with pytest.raises(RuntimeError, match="Previous Native runtime"):
        asyncio.run(browser._start_native())
    assert browser._native_runtime is owner
    monitor.close.assert_awaited_once()


@pytest.mark.parametrize("failure", [OSError("private error"), asyncio.CancelledError()])
def test_telemetry_cleanup_failure_does_not_skip_native_driver_cleanup(tmp_path, monkeypatch, failure):
    from app.core import browser_interface as interface
    from unittest.mock import AsyncMock, Mock

    monkeypatch.setattr(interface, "checked_profile_dir_for_email", lambda name: tmp_path / "profile")
    for name in ("db_get_native_defaults", "db_get_camoufox_defaults", "db_get_cloakbrowser_defaults"):
        monkeypatch.setattr(interface, name, lambda: {})
    monkeypatch.setattr(interface.BrowserInterface, "_init_proxy_logger", lambda self: Mock())
    browser = interface.BrowserInterface("owned", browser_engine="native", keep_browser_open=False)
    runtime = SimpleNamespace(has_resources=True, CLOSE_TIMEOUT_SECONDS=.1, close=AsyncMock())
    browser._native_runtime = runtime
    monitor = SimpleNamespace(close=AsyncMock(side_effect=failure))
    browser._native_process_monitor = monitor
    browser._teardown_browser = AsyncMock()
    if isinstance(failure, asyncio.CancelledError):
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(browser.close())
    else:
        asyncio.run(browser.close())
    runtime.close.assert_awaited_once()
    assert browser._native_runtime is None and browser._native_process_monitor is monitor
    report = browser.native_close_report
    assert report["resources_retained"] and "private" not in str(report)
    assert report["telemetry_cleanup_error"] == ("cancelled" if isinstance(failure, asyncio.CancelledError) else "OSError")
    monitor.close.side_effect = None
    asyncio.run(browser.close())
    assert browser._native_process_monitor is None and not browser.native_close_report["resources_retained"]
