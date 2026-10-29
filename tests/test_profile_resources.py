from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core import browser_lifecycle
from app.ui.bridge.profiles import ProfilesBridge
from app.ui.profile_resources import resource_presentation


def tree_resource(**overrides):
    return {"state": "ready", "working_set_sum_bytes": 512 * 1048576,
            "private_commit_sum_bytes": 256 * 1048576, "process_count": 8,
            "cpu": {"state": "ready", "mean_cpu_cores": 0.125}, **overrides}


def test_tree_label_and_tooltip_do_not_claim_unique_ram_or_cpu_percent():
    label, tooltip = resource_presentation({"memory_mb": 32.5, "memory_limit_mb": 1536,
                                           "process_tree": tree_resource()})
    assert label == "Tree 512 MiB"
    assert "shared pages" in tooltip and "Private commit: 256.0 MiB" in tooltip
    assert "0.12 cores" in tooltip and "not host-normalized percent" in tooltip
    assert "Limit-process working set: 32.5 MiB" in tooltip and "Process memory limit: 1536 MiB" in tooltip


@pytest.mark.parametrize("cpu", [{"state": "warming"}, {"state": "unavailable"}, None,
                                  {"state": "ready", "mean_cpu_cores": float("nan")}])
def test_cpu_unavailability_is_not_rendered_as_zero(cpu):
    label, tooltip = resource_presentation({"process_tree": tree_resource(cpu=cpu)})
    assert label == "Tree 512 MiB" and "interval unavailable" in tooltip and "0.00 cores" not in tooltip


@pytest.mark.parametrize("tree", [None, {"state": "warming"}, {"state": "unavailable"},
    tree_resource(process_count=0), tree_resource(working_set_sum_bytes=True)])
def test_incomplete_tree_is_never_presented_as_complete_memory(tree):
    label, tooltip = resource_presentation({"memory_mb": 12.5, "process_tree": tree})
    assert "Tree " not in label and "12.5" in label
    if tree is not None:
        assert label.startswith("Process ") and "Process-tree measurement" in tooltip


@pytest.mark.parametrize("root", [True, -1, float("nan"), float("inf"), 10 ** 1000, "12"])
def test_invalid_root_metrics_do_not_leak_nan_or_raise(root):
    assert resource_presentation({"memory_mb": root}) == ("", "")


@pytest.mark.parametrize("memory_mb", [1, 20])
@pytest.mark.parametrize("tree", [tree_resource(working_set_sum_bytes=2000 * 1048576),
                                  {"state": "unavailable"}, None])
def test_watchdog_keeps_existing_process_limit_semantics(monkeypatch, tmp_path, memory_mb, tree):
    reports = []
    manager = browser_lifecycle.BrowserLifecycleManager("owned", lambda: tmp_path, lambda: None,
        lambda: None, lambda: None, Mock(), resource_provider=None if tree is None else lambda: tree)
    manager._memory_limit_mb = 10
    manager._lookup_profile_processes = lambda: [{"pid": 10, "memory": memory_mb * 1048576}]
    manager.notify_resource = reports.append
    manager.kill_profile_processes = Mock()
    monkeypatch.setattr(browser_lifecycle.sys, "platform", "win32")
    monkeypatch.setattr(browser_lifecycle.time, "sleep", lambda _: setattr(manager, "_process_exited_notified", True))
    monkeypatch.setattr(browser_lifecycle.threading, "Thread", lambda *, target, daemon: SimpleNamespace(start=target))
    manager.start_process_watchdog()
    assert len(reports) == 1 and reports[0]["memory_mb"] == memory_mb
    assert reports[0]["over_limit"] is (memory_mb > 10)
    assert manager.kill_profile_processes.call_count == int(memory_mb > 10)
    if tree is not None:
        assert reports[0]["process_tree"] == tree
    else:
        assert "process_tree" not in reports[0]


def test_watchdog_exposes_telemetry_failure_without_disabling_root_limit(monkeypatch, tmp_path):
    def unavailable():
        raise OSError("Owned denied telemetry")
    reports = []
    manager = browser_lifecycle.BrowserLifecycleManager("owned", lambda: tmp_path, lambda: None,
        lambda: None, lambda: None, Mock(), resource_provider=unavailable)
    manager._memory_limit_mb = 10
    manager._lookup_profile_processes = lambda: [{"pid": 10, "memory": 20 * 1048576}]
    manager.notify_resource = reports.append
    manager.kill_profile_processes = Mock()
    monkeypatch.setattr(browser_lifecycle.sys, "platform", "win32")
    monkeypatch.setattr(browser_lifecycle.time, "sleep", lambda _: setattr(manager, "_process_exited_notified", True))
    monkeypatch.setattr(browser_lifecycle.threading, "Thread", lambda *, target, daemon: SimpleNamespace(start=target))
    manager.start_process_watchdog()
    assert reports[0]["process_tree"] == {"state": "unavailable", "error_type": "OSError"}
    manager.kill_profile_processes.assert_called_once()


def test_resource_events_from_previous_profile_instance_are_ignored():
    current, previous = object(), object()
    bridge = SimpleNamespace(_live_browsers={"owned": current}, _browser_resources={},
        _emit_message=Mock(), _resource_render_timer=SimpleNamespace(isActive=lambda: False, start=Mock()))
    ProfilesBridge._on_browser_resource_updated(bridge, "owned", (previous, {"memory_mb": 99}))
    ProfilesBridge._on_browser_resource_updated(bridge, "missing", (None, {"memory_mb": 99}))
    assert bridge._browser_resources == {}
    ProfilesBridge._on_browser_resource_updated(bridge, "owned", (current, {"memory_mb": 12}))
    assert bridge._browser_resources == {"owned": {"memory_mb": 12}}
    bridge._resource_render_timer.start.assert_called_once()
