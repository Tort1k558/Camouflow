import asyncio
import copy
import hashlib
import json
from pathlib import Path
import runpy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def managed_history():
    path = Path(__file__).resolve().parents[1] / "native/drafts/environment/first-script/managed_history.py"
    return runpy.run_path(str(path))


@pytest.mark.parametrize("mode,size,dpr,orientation", [
    ("manager-desktop", (1366, 768), 1, "landscape-primary"),
    ("manager-mobile-web", (390, 844), 3, "portrait-primary"),
])
def test_managed_history_expected_screen_uses_actual_configuration_without_mutation(managed_history, mode, size, dpr, orientation):
    configuration = managed_history["REFERENCE"]["environment"].configuration_for_mode(mode)
    baseline = {"width": 800, "height": 600, "dpr": 1, "colorDepth": 24, "pixelDepth": 24}
    original = copy.deepcopy(baseline)
    expected = managed_history["expected_screen"](configuration, baseline)
    assert baseline == original
    assert (expected["width"], expected["height"], expected["dpr"]) == (*size, dpr)
    assert expected["orientation"] == {"type": orientation, "angle": 0}
    assert expected["colorDepth"] == expected["pixelDepth"] == 24


@pytest.mark.parametrize("close_fails", [False, True])
def test_managed_history_cleans_failed_start_without_hiding_primary_error(managed_history, tmp_path, monkeypatch, close_fails):
    runtime = SimpleNamespace(context=None, playwright=None,
        start=AsyncMock(side_effect=ValueError("owned startup failure")),
        close=AsyncMock(side_effect=RuntimeError("owned close failure") if close_fails else None))
    capture = managed_history["capture"]
    monkeypatch.setitem(capture.__globals__, "NativeRuntime", lambda *_: runtime)
    report = {"passed": False, "measurement_complete": False}
    with pytest.raises(ValueError, match="owned startup failure") as raised:
        asyncio.run(capture(tmp_path / "chrome.exe", tmp_path, SimpleNamespace(server_port=1), report, lambda: None))
    runtime.close.assert_awaited_once()
    assert report["passed"] is False and report["measurement_complete"] is False
    assert report["runs"][0]["passed"] is False
    assert bool(report["runs"][0]["cleanup_errors"]) is close_fails
    if close_fails:
        assert any("owned close failure" in note for note in raised.value.__notes__)
    assert all(report[name] is False for name in ("device_metrics_commands_sent", "protected_policies_enabled",
                                                 "full_lifecycle_admitted", "privacy_admitted", "production_admitted"))


def test_actual_managed_history_retains_disabled_bfcache_without_hiding_consistent_screens():
    root = Path(__file__).resolve().parents[1]
    record = json.loads((root / "native/drafts/environment/managed-history70-observations.json").read_bytes())
    assert record["passed"] is False and record["measurement_complete"] and record["postguards_passed"]
    assert [(run["mode"], run["phase"]) for run in record["runs"]] == [
        (mode, phase) for mode in ("manager-desktop", "manager-mobile-web")
        for phase in ("initial", "persistent-profile-restart")]
    assert len(record["retained_calibration_attempts"]) == 3
    count = 0
    for run in record["runs"]:
        assert run["measurement_complete"] and run["runtime_handles_released"] and not run["cleanup_errors"]
        assert run["passed"] is False and run["bfcache_restored"] is False and run["bfcache_disabled_by_driver"]
        assert run["history_navigation_type"] == "Navigation" and run["history_reload_screen_passed"]
        assert "BackForwardCacheDisabledByCommandLine" in run["bfcache_not_used_reasons"]
        assert [stage["passed"] for stage in run["stages"]] == [True, True, True, False]
        mobile = run["mode"] == "manager-mobile-web"
        for stage in run["stages"]:
            for page in stage["pages"].values():
                assert len(page["roles"]) == len(set(page["roles"])) == 6
                assert page["same_screen_all_roles"] and page["css_media_consistent"] and page["embedded_viewports_consistent"]
                assert (page["screen"]["width"], page["screen"]["height"], page["screen"]["dpr"]) == (
                    (390, 844, 3) if mobile else (1366, 768, 1))
                count += len(page["roles"])
    assert count == record["observed_document_snapshots"] == 144
    assert all(hashlib.sha256((root / name).read_bytes()).hexdigest() == value
               for name, value in record["source_sha256"].items())
    assert all(record[name] is False for name in ("device_metrics_commands_sent", "all_frame_input_verified",
        "process_swap_verified", "protected_policies_enabled", "full_lifecycle_admitted", "privacy_admitted", "production_admitted"))
