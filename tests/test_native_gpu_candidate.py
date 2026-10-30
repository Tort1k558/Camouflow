import hashlib
import json

import pytest

from scripts import verify_native_gpu as gpu

def supported_contexts():
    return {name: {"webgpu": {"available": name in gpu.WEBGPU_CONTEXTS}} for name in gpu.CONTEXTS}


def test_stock_gpu_calibration_matches_executed_sources_without_admitting_glint(historical_surface_source_sha256):
    record = json.loads((gpu.ROOT / "native/drafts/gpu/stock156-runtime-observations.json").read_bytes())
    assert record["source_sha256"] == {name: historical_surface_source_sha256(name) for name in gpu.probe_inputs()}
    assert record["passed"] is True and record["postguards_passed"] is True
    assert record["all_eight_contexts_required"] is True
    assert record["effective_feature_arguments_verified"] is True
    assert [row["name"] for row in record["phases"]] == ["feature-off", "feature-off-restart"]
    assert all(row["passed"] is True and row["coverage"] == {"webgl": 8, "webgl2": 8, "webgpu": 8}
               for row in record["phases"])
    for field in ("glint_candidate_runtime_verified", "device_cohort_verified", "privacy_admitted", "production_admitted"):
        assert record[field] is False


def test_webgpu_requires_all_eight_realms_observed_on_pinned_chromium156():
    assert gpu.WEBGPU_CONTEXTS == gpu.CONTEXTS and len(gpu.WEBGPU_CONTEXTS) == 8
    gpu.require_webgpu_coverage(supported_contexts())


@pytest.mark.parametrize("case", ["missing-context", "unavailable-window", "unavailable-shared", "truthy", "empty"])
def test_required_webgpu_cannot_pass_with_missing_or_unexpected_availability(case):
    observed = supported_contexts()
    if case == "missing-context":
        observed.pop("document")
    elif case == "unavailable-window":
        observed["document"]["webgpu"]["available"] = False
    elif case == "unavailable-shared":
        observed["shared"]["webgpu"]["available"] = False
    elif case == "truthy":
        observed["document"]["webgpu"]["available"] = 1
    else:
        observed = {}
    with pytest.raises(ValueError):
        gpu.require_webgpu_coverage(observed)


@pytest.mark.parametrize("mutation", [None, "hash", "missing", "patch-missing"])
def test_candidate_gpu_reuses_full_receipt_validation_and_requires_exact_patch(tmp_path, monkeypatch, mutation):
    from scripts import native_build as build
    from scripts import verify_native_worker_startup as workers

    directory = tmp_path / "candidate"
    (directory / "patches").mkdir(parents=True)
    name = "0034-native-gpu-metadata-minimization.patch"
    patch = directory / "patches" / name
    patch.write_bytes(b"owned GPU patch\n")
    row = {"name": name, "sha256": hashlib.sha256(patch.read_bytes()).hexdigest()}
    if mutation == "hash":
        row["sha256"] = "0" * 64
    raw = json.dumps({"patches": [] if mutation == "missing" else [row]}).encode()
    if mutation == "patch-missing":
        patch.unlink()
    monkeypatch.setattr(build, "load_candidate", lambda name: {"directory": directory})
    calls = []
    def validate(executable, core, **kwargs):
        calls.append((executable, core, kwargs))
        return raw
    monkeypatch.setattr(workers, "validate_receipt", validate)
    executable, core = tmp_path / "chrome.exe", {"chrome.exe": "a" * 64}
    if mutation is None:
        assert gpu.validate_candidate_receipt(executable, core, candidate_name="upstream-156") == raw
    else:
        with pytest.raises(ValueError):
            gpu.validate_candidate_receipt(executable, core, candidate_name="upstream-156")
    assert calls == [(executable, core, {"bootstrap_policy": "surfaces", "candidate_name": "upstream-156"})]


@pytest.mark.parametrize("minimized", [False, True])
def test_gpu_phase_coverage_is_complete_for_generic_and_candidate_runs(minimized):
    names = ["feature-off", "feature-off-restart"]
    if minimized:
        names.extend(["feature-on", "feature-on-restart"])
    report = {"checks": [{"name": name, "passed": True} for name in names],
              "browser_versions": {name: {"product": "Chrome/156", "revision": "@owned"} for name in names}}
    gpu.require_complete_phases(report, minimized=minimized)
    gpu.require_complete_phases(report, minimized=minimized, candidate_name="upstream-156")


@pytest.mark.parametrize("mutation", ["empty", "duplicate", "failed", "truthy", "foreign", "missing-version", "malformed-version"])
def test_gpu_phase_coverage_cannot_be_faked(mutation):
    report = {"checks": [{"name": name, "passed": True} for name in ("feature-off", "feature-off-restart")],
              "browser_versions": {name: {"product": "Chrome/156", "revision": "@owned"}
                                   for name in ("feature-off", "feature-off-restart")}}
    if mutation == "empty":
        report["checks"] = []
    elif mutation == "duplicate":
        report["checks"][1] = report["checks"][0]
    elif mutation in {"failed", "truthy"}:
        report["checks"][0]["passed"] = False if mutation == "failed" else 1
    elif mutation == "foreign":
        report["checks"][0]["name"] = []
    elif mutation == "missing-version":
        report["browser_versions"].pop("feature-off")
    else:
        report["browser_versions"]["feature-off"]["revision"] = True
    with pytest.raises(ValueError):
        gpu.require_complete_phases(report, minimized=False, candidate_name="upstream-156")


@pytest.mark.parametrize("enabled", [False, True])
def test_gpu_feature_switches_preserve_every_unrelated_default(enabled):
    original = ["--enable-features=One,Two:mode/value", "--disable-features=Three,Four", "--headless"]
    requested, ignored = gpu.feature_arguments(original, enabled=enabled)
    assert ignored == [original[0 if enabled else 1]]
    assert requested[0].startswith("--enable-features=One,Two:mode/value")
    assert requested[1].startswith("--disable-features=Three,Four")
    target = "GlintGpuMetadataMinimization"
    assert (target in requested[0]) is enabled
    assert (target in requested[1]) is not enabled
    assert original == ["--enable-features=One,Two:mode/value", "--disable-features=Three,Four", "--headless"]


@pytest.mark.parametrize("enabled", [False, True])
def test_gpu_feature_switches_move_existing_target_without_touching_other_flags(enabled):
    target = "GlintGpuMetadataMinimization"
    requested, ignored = gpu.feature_arguments(["--disable-features=Other," + target], enabled=enabled)
    assert sum(value.count(target) for value in requested) == 1
    assert any(value.startswith("--disable-features=Other") for value in requested)
    assert ignored == (["--disable-features=Other," + target] if enabled else [])


@pytest.mark.parametrize("arguments", [["--enable-features=One", "--enable-features=Two"],
    ["--disable-features=One,"], ["--enable-features=GlintGpuMetadataMinimization:mode/value"], [None]])
def test_gpu_feature_switches_reject_ambiguous_or_parameterized_target_configuration(arguments):
    with pytest.raises(ValueError):
        gpu.feature_arguments(arguments, enabled=True)


@pytest.mark.parametrize("minimized", [False, True])
def test_gpu_launch_preserves_defaults_when_driver_filters_explicit_and_default_arguments(tmp_path, monkeypatch, minimized):
    import asyncio
    from types import SimpleNamespace
    from scripts import verify_native_worker_startup as workers

    defaults = ["--enable-features=Screenshot", "--disable-features=Partitioning,Other"]
    launched = []

    class Context:
        browser = SimpleNamespace(version="156")

        def __init__(self, arguments):
            self.arguments = arguments
            self.closed = False

        async def close(self):
            self.closed = True

    class Driver:
        async def __aenter__(self):
            return SimpleNamespace(chromium=self)

        async def __aexit__(self, *args):
            pass

        async def launch_persistent_context(self, profile, **options):
            arguments = defaults + options.get("args", [])
            arguments = [value for value in arguments if value not in options.get("ignore_default_args", [])]
            context = Context(arguments)
            launched.append(context)
            return context

    async def arguments(context):
        assert "--enable-automation" in context.arguments
        return context.arguments

    async def observe(*args, **kwargs):
        return supported_contexts()

    monkeypatch.setattr(gpu, "async_playwright", Driver)
    monkeypatch.setattr(workers, "browser_arguments", arguments)
    monkeypatch.setattr(gpu, "observe", observe)
    monkeypatch.setattr(gpu, "validate_observations", lambda *args, **kwargs: {"webgpu": 8})
    report = {"checks": []}
    asyncio.run(gpu.verify(tmp_path / "chrome.exe", tmp_path / "profile", "http://owned", report,
                           minimized, require_webgpu=True))
    gpu.require_complete_phases(report, minimized=minimized)
    assert len(launched) == (5 if minimized else 3)
    assert all(context.closed for context in launched)
    for context in launched[1:]:
        enable, disable = [next(value for value in context.arguments if value.startswith(prefix))
                           for prefix in ("--enable-features=", "--disable-features=")]
        assert enable.startswith(defaults[0]) and disable.startswith(defaults[1])
        assert sum(value.count("GlintGpuMetadataMinimization") for value in context.arguments) == 1


def test_candidate_gpu_rejects_busy_builder_before_touching_runtime_or_profiles(tmp_path, monkeypatch):
    import sys
    from contextlib import contextmanager
    from scripts import native_build as build
    from scripts import verify_native_privacy_units as units

    events = []
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    report = tmp_path / "gpu.json"
    profiles = tmp_path / "profiles"
    monkeypatch.setattr(sys, "argv", ["gpu", "--candidate", "upstream-156", "--workspace", str(workspace),
                                     "--executable", str(tmp_path / "missing.exe"),
                                     "--work-dir", str(profiles), "--report", str(report)])
    monkeypatch.setattr(build, "load_candidate", lambda name: {"manifest_sha256": "a" * 64})
    monkeypatch.setattr(build, "candidate_workspace", lambda *args: events.append("validated"))

    @contextmanager
    def lock(path):
        assert path == workspace.resolve()
        events.append("locked")
        try:
            yield
        finally:
            events.append("released")

    def reject(path):
        events.append("idle-check")
        raise RuntimeError("owned builder is active")

    monkeypatch.setattr(build, "workspace_lock", lock)
    monkeypatch.setattr(units, "require_idle_builder", reject)
    assert gpu.main() == 1
    evidence = json.loads(report.read_text(encoding="utf-8"))
    assert evidence["error"] == "owned builder is active"
    assert evidence["passed"] is False and evidence["checks"] == []
    assert not profiles.exists()
    assert events == ["validated", "locked", "idle-check", "released"]
