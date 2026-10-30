import asyncio
import copy
import hashlib
import json
from pathlib import Path
import runpy
import struct
import subprocess
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


@pytest.mark.parametrize("mode,size", [("manager-desktop", (1366, 768)), ("manager-mobile-web", (1170, 2532))])
def test_owner_screenshot_uses_existing_playwright_page_and_configured_pixel_size(managed_history, tmp_path, mode, size):
    png = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", *size)
    page = SimpleNamespace(screenshot=AsyncMock(return_value=png))
    configuration = managed_history["REFERENCE"]["environment"].configuration_for_mode(mode)
    result = asyncio.run(managed_history["capture_owner_screenshot"](page, tmp_path, configuration))
    page.screenshot.assert_awaited_once_with(timeout=10000)
    assert result["passed"] and result["size"] == result["expected_size"] == list(size)
    assert (tmp_path / "history-return-owner.png").read_bytes() == png


def test_owner_screenshot_rejects_css_size_as_mobile_device_size(managed_history, tmp_path):
    png = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 390, 844)
    page = SimpleNamespace(screenshot=AsyncMock(return_value=png))
    configuration = managed_history["REFERENCE"]["environment"].configuration_for_mode("manager-mobile-web")
    result = asyncio.run(managed_history["capture_owner_screenshot"](page, tmp_path, configuration))
    assert result["passed"] is False and result["expected_size"] == [1170, 2532]


def test_owner_screenshot_rejects_invalid_png(managed_history, tmp_path):
    page = SimpleNamespace(screenshot=AsyncMock(return_value=b"invalid PNG"))
    configuration = managed_history["REFERENCE"]["environment"].configuration_for_mode("manager-desktop")
    with pytest.raises(ValueError, match="not PNG"):
        asyncio.run(managed_history["capture_owner_screenshot"](page, tmp_path, configuration))
    assert not (tmp_path / "history-return-owner.png").exists()


@pytest.mark.parametrize("token", [None, True, 7, "", "x" * 257])
def test_post_screenshot_history_requires_valid_owned_token(managed_history, token):
    session = SimpleNamespace(send=AsyncMock(return_value={"result": {"value": token}}))
    with pytest.raises(ValueError, match="protocol token"):
        asyncio.run(managed_history["recapture_retained_history"](session, {}))


@pytest.mark.parametrize("mutation", [None, "exception", "missing-value", "lost-document", "not-persisted"])
def test_post_screenshot_history_rechecks_all_retained_documents(managed_history, mutation):
    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "native/drafts/environment/screen-lifecycle70-observations.json").read_bytes())["bfcache_state"]
    changed = copy.deepcopy(state)
    if mutation == "lost-document":
        changed["snapshots"].pop("cross")
    elif mutation == "not-persisted":
        changed["snapshots"]["cross"]["persisted"] = False
    response = ({"exceptionDetails": {"text": "owned error"}} if mutation == "exception"
                else {"result": {"type": "undefined"}} if mutation == "missing-value"
                else {"result": {"value": changed}})
    session = SimpleNamespace(send=AsyncMock(side_effect=[{"result": {"value": "owned-history-token"}}, response]))
    operation = managed_history["recapture_retained_history"](session, state)
    if mutation is None:
        assert asyncio.run(operation) == state
    else:
        with pytest.raises(ValueError):
            asyncio.run(operation)
    assert session.send.await_args_list[-1].args[1]["awaitPromise"] is True


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


def test_bfcache_launch_experiment_replays_without_changing_active_runtime(tmp_path):
    root = Path(__file__).resolve().parents[1]
    folder = root / "native/drafts/environment"
    record = json.loads((folder / "managed-bfcache-optin70-observations.json").read_bytes())
    overlay = record["experimental_runtime_overlay"]
    source = root / overlay["base_source"]
    original = source.read_bytes()
    assert hashlib.sha256(original).hexdigest() == overlay["base_source_sha256"]
    patch = folder / record["patch"]
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record["patch_sha256"] == overlay["patch_sha256"]
    target = tmp_path / overlay["base_source"]
    target.parent.mkdir(parents=True)
    target.write_bytes(original)
    subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--whitespace=error", str(patch)],
                   cwd=tmp_path, check=True, capture_output=True)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == overlay["prepared_source_sha256"]
    assert source.read_bytes() == original
    assert overlay["selected"] is False and record["selected"] is False


def test_actual_bfcache_optin_uses_owner_screenshots_and_preserves_independent_cdp_findings():
    root = Path(__file__).resolve().parents[1]
    record = json.loads((root / "native/drafts/environment/managed-bfcache-optin70-observations.json").read_bytes())
    build = json.loads((root / "native/drafts/upstream-156/build70-observations.json").read_bytes())
    assert record["measurement_complete"] and record["postguards_passed"]
    glint, stock = (record["results"][kind] for kind in ("glint70", "stock156"))
    assert glint["passed"] is True and stock["passed"] is False
    assert glint["runtime_core_sha256_measured"] == build["runtime_core_sha256_measured"]
    for result in (glint, stock):
        assert result["measurement_complete"] and result["postguards_passed"] and len(result["runs"]) == 4
        for run in result["runs"]:
            assert run["bfcache_restored"] and run["persisted_documents_before_owner"] == run["persisted_documents_after_owner"] == 6
            assert run["owner_screenshot"]["passed"]
            expected = [1170, 2532] if run["mode"] == "manager-mobile-web" else [1366, 768]
            assert run["owner_screenshot"]["size"] == run["owner_screenshot"]["expected_size"] == expected
            assert run["independent_cdp_probe"]["trusted_input_passed"]
            if run["mode"] == "manager-mobile-web":
                assert run["independent_cdp_probe"]["passed"] is False
                assert run["independent_cdp_probe"]["screenshot_size"] == [390, 844]
    assert all(run["passed"] and run["post_owner_snapshots_unchanged"] for run in glint["runs"])
    assert record["paired_snapshot_comparison"] == {"snapshots_per_runtime": 168, "exact_snapshot_matches": 88,
                                                   "snapshot_differences": 80}
    assert all(run["same_before_after_history"] and run["before_size"] == run["after_size"]
               for run in record["independent_cdp_pre_post_control"])
    full = record["full_runtime_overlay"]
    assert full["passed"] and full["measurement_complete"] and full["original_source_unchanged"] and full["overlay_source_unchanged"]
    assert full["runtime_import_verified"] and full["check_count"] == len(full["checks"]) == 18
    assert all(hashlib.sha256((root / path).read_bytes()).hexdigest() == value
               for path, value in record["source_sha256"].items())
    assert all(record[name] is False for name in ("selected", "bfcache_enabled_in_current_manager",
        "bfcache_optin_ready_for_release", "privacy_admitted", "production_admitted"))


def test_repeated_recorder_bfcache_capture_keeps_silent_delivery_loss_as_failure(recorder_before_document_open_sha256):
    root = Path(__file__).resolve().parents[1]
    record = json.loads((root / "native/drafts/environment/managed-bfcache-recorder70-observations.json").read_bytes())
    assert record["passed"] is False and record["measurement_complete"] and record["postguards_passed"]
    assert record["geometry_gate_passed"] and record["recorder_history_gate_passed"] is False
    assert record["capture_phases_passed"] == sum(run["passed"] for run in record["runs"]) == 3
    assert record["silent_loss_observed"] and len(record["runs"]) == 4
    failed = [run for run in record["runs"] if not run["passed"]]
    assert len(failed) == 1 and failed[0]["mode"] == "manager-desktop"
    assert failed[0]["phase"] == "persistent-profile-restart" and failed[0]["after_click_recorded"] is False
    assert failed[0]["click_count"] == 1 and failed[0]["trusted_dom_clicks_before_final_probe"] == 2
    assert failed[0]["warnings"] == [] and failed[0]["browser_recording_error"] is False
    assert all(run["before_click_recorded"] and run["bfcache_restored"] for run in record["runs"])
    trace = record["trace_repeat"]
    assert trace["passed"] is False and trace["measurement_complete"] and trace["postguards_passed"]
    assert trace["capture_phases_passed"] == sum(run["passed"] for run in trace["runs"]) == 2
    for run in trace["runs"]:
        assert run["trusted_post_click_verified"] and run["all_observed_sources_match_page_and_main_frame"]
        assert run["browser_state_before_post_click"] == {"recording": True, "sameDocument": True,
                                                        "bindingPresent": True, "error": False}
        if not run["passed"]:
            assert run["bridge_actions"] == [None, "click"] and run["click_count"] == 1 and not run["warnings"]
    control = record["stock_trace_control"]
    assert control["passed"] is False and control["measurement_complete"] and control["postguards_passed"]
    assert control["capture_phases_passed"] == 0 and len(control["runs"]) == 4
    assert all(run["trusted_post_click_verified"] and run["bfcache_restored"] and run["click_count"] == 1
               and run["bridge_actions"] == [None, "click"] and run["warnings"] == [] for run in control["runs"])
    diagnostic = record["listener_binding_diagnostic"]
    assert diagnostic["measurement_complete"] and diagnostic["postguards_passed"]
    assert diagnostic["binding_pings_completed"] == 1 and len(diagnostic["runs"]) == 4
    for run in diagnostic["runs"]:
        assert run["document_click_listeners"] == {"available": True, "clicks": [{"capture": True, "recorderEmitter": True}]}
        ping = run["empty_binding_ping"]
        if not ping["measurement_complete"]:
            assert ping["error_type"] == "TimeoutError" and ping["bridge_calls_before"] == ping["bridge_calls_after"] == 2
    assert record["source_sha256"]["app/services/scenario_recorder.py"] == recorder_before_document_open_sha256
    assert all(hashlib.sha256((root / path).read_bytes()).hexdigest() == value
               for path, value in record["source_sha256"].items() if path != "app/services/scenario_recorder.py")
    assert all(record[name] is False for name in ("initial_navigation_included", "recorded_draft_replay_verified",
                                                "all_frame_input_verified", "selected", "privacy_admitted", "production_admitted"))


def test_driver_diagnosis_does_not_misattribute_received_bindings_to_v8_loss():
    root = Path(__file__).resolve().parents[1]
    record = json.loads((root / "native/drafts/environment/binding-driver70-diagnosis.json").read_bytes())
    assert record["measurement_complete"] and record["shared_driver_unchanged"] and record["instrumented_driver_unchanged"]
    counts = record["trace_counts"]
    assert counts == {"context": 268, "receive": 13, "before-python": 11, "after-python": 11}
    assert record["binding_events_with_unknown_context"] == counts["receive"] - counts["before-python"] == 2
    assert record["playwright_dropped_unknown_frame_context_demonstrated"]
    assert record["native_v8_binding_callback_loss_demonstrated"] is False
    assert len(record["missing_context_diagnostics"]) == 2
    assert all(item == {"default": True, "frameKnown": False, "stale": None}
               for item in record["missing_context_diagnostics"])
    assert all(record[name] is False for name in ("selected", "privacy_admitted", "production_admitted"))


def test_root_only_driver_prototype_does_not_admit_missing_cross_process_frames():
    root = Path(__file__).resolve().parents[1]
    folder = root / "native/drafts/environment"
    record = json.loads((folder / "binding-driver70-prototype-observations.json").read_bytes())
    assert record["measurement_complete"] and record["passed"] is False and record["shared_driver_unchanged"]
    patch = folder / record["patch"]
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record["patch_sha256"]
    positive, negative = record["root_only_repeat"], record["six_frame_capture"]
    assert positive["passed"] and positive["postguards_passed"]
    assert positive["phases"] == 4 and positive["recorded_clicks_per_phase"] == 2
    assert negative["passed"] is False and negative["measurement_complete"] is False and negative["postguards_passed"]
    assert negative["history_navigation_type"] == "BackForwardCacheRestore"
    assert negative["observed_roles"] == ["about-blank", "cross", "main", "srcdoc"]
    assert negative["missing_roles"] == ["nested-return", "same"]
    assert set(negative["observed_roles"]) | set(negative["missing_roles"]) == {
        "main", "same", "cross", "nested-return", "srcdoc", "about-blank"}
    assert all(record[name] is False for name in ("recorded_draft_replay_verified", "all_frame_input_verified",
                                                "selected", "privacy_admitted", "production_admitted"))


def test_multisession_driver_draft_covers_six_roles_without_admitting_full_history_replay(recorder_before_document_open_sha256):
    root = Path(__file__).resolve().parents[1]
    folder = root / "native/drafts/environment"
    record = json.loads((folder / "binding-driver70-multisession-observations.json").read_bytes())
    build = json.loads((root / "native/drafts/upstream-156/build70-observations.json").read_bytes())
    assert record["passed"] and record["measurement_complete"] and record["postguards_passed"]
    assert record["runtime_core_sha256_measured"] == build["runtime_core_sha256_measured"]
    assert record["patch_replay_verified"]
    for name in ("patch", "model"):
        assert hashlib.sha256((folder / record[name]).read_bytes()).hexdigest() == record[name + "_sha256"]
    assert record["source_sha256"]["app/services/scenario_recorder.py"] == recorder_before_document_open_sha256
    assert all(hashlib.sha256((root / path).read_bytes()).hexdigest() == value
               for path, value in record["source_sha256"].items() if path != "app/services/scenario_recorder.py")
    assert len(record["runs"]) == 4
    assert {(run["mode"], run["phase"]) for run in record["runs"]} == {
        (mode, phase) for mode in ("manager-desktop", "manager-mobile-web")
        for phase in ("initial", "persistent-profile-restart")}
    expected_selectors = [[], ['iframe[name="about-blank"]'], ['iframe[name="cross"]'],
                          ['iframe[name="cross"]', 'iframe[name="nested-return"]'],
                          ['iframe[name="same"]'], ['iframe[name="srcdoc"]'], []]
    for run in record["runs"]:
        assert run["passed"] and run["runtime_handles_released"] and run["warnings"] == []
        assert run["history_navigation_type"] == "BackForwardCacheRestore"
        assert run["playwright_frame_roles"] == ["about-blank", "cross", "main", "nested-return", "same", "srcdoc"]
        assert run["recorded_clicks"] == 7 and run["click_frame_selectors"] == expected_selectors
        assert set(run["child_trusted_clicks"]) == {"about-blank", "cross", "nested-return", "same", "srcdoc"}
        assert all(click == {"trusted": True, "x": 52, "y": 38, "inside": True}
                   for click in run["child_trusted_clicks"].values())
    model = record["modeled_controls"]
    assert model["passed"] and model["tests"] == len(model["results"]) == 13
    assert all(case["passed"] for case in model["results"])
    full = record["full_runtime_overlay"]
    assert all(full[key] for key in ("passed", "measurement_complete", "original_source_unchanged",
        "overlay_source_unchanged", "driver_import_verified", "runtime_import_verified", "driver_unchanged", "shared_driver_unchanged"))
    assert len(full["checks"]) == 18 and "existing-recorder-capture-and-replay" in full["checks"]
    assert full["baseline_recorded_draft_replay_verified"] and full["history_recorded_draft_replay_verified"] is False
    assert record["superseded_immediate_snapshot_attempt"]["passed"] is False
    assert all(record[name] is False for name in ("initial_navigation_included", "recorded_draft_replay_verified",
                                                "selected", "privacy_admitted", "production_admitted", "full_lifecycle_admitted"))


def test_binding_reply_draft_replays_complete_history_without_selecting_the_driver():
    root = Path(__file__).resolve().parents[1]
    folder = root / "native/drafts/environment"
    record = json.loads((folder / "binding-replies70-observations.json").read_bytes())
    build = json.loads((root / "native/drafts/upstream-156/build70-observations.json").read_bytes())
    assert record["passed"] and record["measurement_complete"] and record["postguards_passed"]
    assert record["patch_replay_verified"] and record["installed_driver_unchanged"]
    assert record["initial_navigation_included"] and record["history_recorded_draft_replay_verified"]
    assert record["runtime_core_sha256_measured"] == build["runtime_core_sha256_measured"]
    assert record["binding_reply_limit_per_session"] == 1024 and record["frozen_source_input_count"] >= 100
    for key in ("patch", "model", "runner"):
        assert hashlib.sha256((folder / record[key]).read_bytes()).hexdigest() == record[key + "_sha256"]
    recorder = (root / "app/services/scenario_recorder.py").read_text(encoding="utf-8-sig").encode("utf-8")
    assert hashlib.sha256(recorder).hexdigest() == record["recorder_normalized_utf8_lf_sha256"]
    models = record["modeled_controls"]
    assert models["passed"] and models["tests"] == len(models["results"]) == 25
    assert all(case["passed"] for case in models["results"])
    assert len(record["runs"]) == 4
    assert {(run["mode"], run["phase"]) for run in record["runs"]} == {
        (mode, phase) for mode in ("manager-desktop", "manager-mobile-web")
        for phase in ("initial", "persistent-profile-restart")}
    expected = {"main": 2, "same": 1, "cross": 1, "srcdoc": 1, "about-blank": 1, "nested-return": 1}
    for run in record["runs"]:
        assert run["passed"] and run["replay_passed"] and run["attached_before_initial_navigation"]
        assert run["recorded_clicks"] == 9 and run["recorded_step_count"] == len(run["recorded_actions"]) == 13
        assert run["recorded_actions"][:2] == ["start", "goto"] and run["recorded_actions"].count("wait_for_load_state") == 2
        assert run["history_navigation_type"] == "BackForwardCacheRestore"
        assert "BackForwardCacheRestore" in run["replay_navigation_types"] and run["warnings"] == []
        assert run["replay_click_counts"] == expected
        assert set(run["restored_roles"]) == set(run["pending_counts"]) == set(expected)
        assert not any(run["pending_counts"].values())
    full = record["full_runtime_overlay"]
    assert all(full[key] for key in ("passed", "measurement_complete", "original_source_unchanged", "overlay_source_unchanged", "driver_unchanged", "shared_driver_unchanged"))
    assert len(full["checks"]) == 18
    assert all(record[name] is False for name in ("selected", "privacy_admitted", "production_admitted", "full_lifecycle_admitted"))


def test_history_replay_cli_rejects_unknown_driver_before_creating_workspace(tmp_path):
    import sys

    root = Path(__file__).resolve().parents[1]
    script = root / "native/drafts/environment/first-script/recorder_replay.py"
    help_result = subprocess.run([sys.executable, str(script), "--help"], check=True, capture_output=True, text=True, timeout=15)
    assert "--driver-sha256" in help_result.stdout and "--application-root" in help_result.stdout
    driver = tmp_path / "driver"
    bundle = driver / "playwright/driver/package/lib/coreBundle.js"
    bundle.parent.mkdir(parents=True)
    bundle.write_text("unknown driver", encoding="utf-8")
    owned = tmp_path / "owned"
    result = subprocess.run([sys.executable, str(script), "--driver-root", str(driver), "--driver-sha256", "0" * 64,
        "--application-root", str(root), "--executable", str(tmp_path / "unknown.exe"), "--runtime-reference", str(tmp_path / "unknown.json"),
        "--work-dir", str(owned)], capture_output=True, text=True, timeout=15)
    assert result.returncode != 0 and "Driver differs from the explicitly pinned bundle" in result.stderr
    assert not owned.exists()


def test_document_open_full_regression_failure_remains_retained_until_complete_repeat():
    root = Path(__file__).resolve().parents[1]
    record = json.loads((root / "native/drafts/environment/canonical-python70-document-open-observations.json").read_bytes())
    assert record["passed"] is False and record["measurement_complete"] and record["postguards_passed"]
    assert record["counts"] == {"tests": 4328, "passed": 4325, "failures": 2, "errors": 0, "skipped": 1}
    assert len(record["failed_tests"]) == 2 and record["changed_tracked_files"] == []
    assert all(record[name] is False for name in ("native_runtime_verified", "privacy_admitted", "production_admitted"))
