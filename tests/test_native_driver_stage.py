import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import native_driver_stage as driver


def sha(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def package(tmp_path):
    source = tmp_path / "source" / "playwright"
    files = {
        "__init__.py": b"", "async_api/__init__.py": b"", driver.NODE: b"owned node",
        driver.BUNDLE: b"old\n", "driver/package/package.json": b'{"version":"1.60.0"}',
        **{name: b"third party notice" for name in driver.LEGAL_FILES},
    }
    for name, data in files.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    relative = "playwright/" + driver.BUNDLE
    patch = tmp_path / "owned.patch"
    patch.write_text("diff --git a/" + relative + " b/" + relative + "\n" + "".join(difflib.unified_diff(
        ["old\n"], ["new\n"], fromfile="a/" + relative, tofile="b/" + relative)), encoding="utf-8", newline="\n")
    manifest = json.loads(driver.DEFAULT_MANIFEST.read_bytes())
    manifest.update(base_bundle_sha256=sha(b"old\n"), bundle_sha256=sha(b"new\n"), node_sha256=sha(b"owned node"),
                    patch=patch.name, patch_sha256=sha(patch.read_bytes()))
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return source, tmp_path / "stage", path


def test_stage_preserves_source_and_licenses_without_selecting_a_driver(package):
    source, output, manifest = package
    before = driver.inventory(source, source=True)
    receipt = driver.stage(source, output, manifest)
    assert driver.inventory(source, source=True) == before
    assert (output / "playwright" / driver.BUNDLE).read_bytes() == b"new\n"
    assert receipt == driver.verify(output, manifest)
    assert receipt["file_count"] == len(before) and receipt["source_unchanged"]
    assert all(receipt[name] is False for name in ("selected", "privacy_admitted", "production_admitted", "runtime_admitted", "cryptographically_signed"))
    for name in driver.LEGAL_FILES:
        assert (output / "playwright" / name).read_bytes() == (source / name).read_bytes()


def test_existing_output_is_not_overwritten(package):
    source, output, manifest = package
    output.mkdir()
    marker = output / "customer-data"
    marker.write_bytes(b"keep")
    with pytest.raises(driver.DriverStageError, match="must be new"):
        driver.stage(source, output, manifest)
    assert marker.read_bytes() == b"keep"


def test_source_installation_cannot_be_the_stage(package):
    source, _, manifest = package
    with pytest.raises(driver.DriverStageError, match="outside"):
        driver.stage(source, source / "stage", manifest)
    assert not (source / "stage").exists()


@pytest.mark.parametrize("name", [driver.BUNDLE, driver.NODE])
def test_unknown_code_is_rejected_before_output_creation(package, name):
    source, output, manifest = package
    (source / name).write_bytes(b"unknown")
    with pytest.raises(driver.DriverStageError, match="differs from the pin"):
        driver.stage(source, output, manifest)
    assert not output.exists()


def test_patch_path_cannot_escape_manifest_directory(package):
    _, _, manifest = package
    record = json.loads(manifest.read_bytes())
    record["patch"] = "../outside.patch"
    manifest.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(driver.DriverStageError, match="patch path"):
        driver.load_manifest(manifest)


def test_manifest_cannot_claim_production_admission(package):
    source, output, manifest = package
    record = json.loads(manifest.read_bytes())
    record["production_admitted"] = True
    manifest.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(driver.DriverStageError, match="cannot admit"):
        driver.stage(source, output, manifest)
    assert not output.exists()


def test_source_caches_are_not_bundled_and_cannot_be_added_to_stage(package):
    source, output, manifest = package
    cache = source / ".local-browsers"
    cache.mkdir()
    (cache / "browser.exe").write_bytes(b"not bundled")
    driver.stage(source, output, manifest)
    assert not (output / "playwright/.local-browsers").exists()
    (output / "playwright/.local-browsers").mkdir()
    with pytest.raises(driver.DriverStageError, match="Source caches"):
        driver.verify(output, manifest)


@pytest.mark.parametrize("name", [".env", ".ENV", ".env.private", "local.env"])
def test_private_source_environment_file_is_rejected(package, name):
    source, output, manifest = package
    (source / name).write_text("PRIVATE=do-not-copy", encoding="utf-8")
    with pytest.raises(driver.DriverStageError, match="Private environment"):
        driver.stage(source, output, manifest)
    assert not output.exists()


def test_payload_and_root_tampering_are_rejected(package):
    source, output, manifest = package
    driver.stage(source, output, manifest)
    (output / "outside-package").write_text("unknown", encoding="utf-8")
    with pytest.raises(driver.DriverStageError, match="only its package"):
        driver.verify(output, manifest)
    (output / "outside-package").unlink()
    (output / "playwright/__init__.py").write_bytes(b"tampered")
    with pytest.raises(driver.DriverStageError, match="inventory differs"):
        driver.verify(output, manifest)


def test_receipt_cannot_select_a_release(package):
    source, output, manifest = package
    driver.stage(source, output, manifest)
    path = output / driver.RECEIPT
    receipt = json.loads(path.read_bytes())
    receipt["selected"] = True
    path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(driver.DriverStageError, match="unselected manifest"):
        driver.verify(output, manifest)


def test_concurrent_source_change_never_produces_a_valid_receipt(package, monkeypatch):
    source, output, manifest = package
    copy = driver.shutil.copy2
    def mutate(original, target):
        result = copy(original, target)
        if Path(original) == source / driver.BUNDLE:
            (source / "__init__.py").write_bytes(b"changed during copy")
        return result
    monkeypatch.setattr(driver.shutil, "copy2", mutate)
    with pytest.raises(driver.DriverStageError, match="Unexpected driver asset"):
        driver.stage(source, output, manifest)
    assert not (output / driver.RECEIPT).exists()


def test_modeled_linked_asset_is_rejected_before_copy(package, monkeypatch):
    source, output, manifest = package
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == source / driver.NODE or original(path))
    with pytest.raises(driver.DriverStageError, match="Linked driver assets"):
        driver.stage(source, output, manifest)
    assert not output.exists()


def test_non_object_manifest_is_rejected(package):
    _, _, manifest = package
    manifest.write_text("[]", encoding="utf-8")
    with pytest.raises(driver.DriverStageError, match="Unsupported"):
        driver.load_manifest(manifest)


def test_oversized_manifest_is_rejected_before_json_parsing(package):
    _, _, manifest = package
    manifest.write_bytes(b" " * 65537)
    with pytest.raises(driver.DriverStageError, match="too large"):
        driver.load_manifest(manifest)


def test_oversized_patch_is_rejected_before_hashing_or_execution(package):
    _, _, manifest = package
    record = json.loads(manifest.read_bytes())
    (manifest.parent / record["patch"]).write_bytes(b" " * (1024 * 1024 + 1))
    with pytest.raises(driver.DriverStageError, match="bounded regular"):
        driver.load_manifest(manifest)


def test_pyinstaller_override_changes_only_the_matching_js_data_source(package):
    source, output, manifest = package
    driver.stage(source, output, manifest)
    core = ("playwright/" + driver.BUNDLE, str(source / driver.BUNDLE), "DATA")
    untouched = ("app/qml/Main.qml", "owned/Main.qml", "DATA")
    entries = [untouched, core]
    result = driver.bundle_datas(entries, source, output, manifest)
    assert entries == [untouched, core] and result[0] == untouched
    assert result[1] == (core[0], str((output / "playwright" / driver.BUNDLE).resolve()), "DATA")


@pytest.mark.parametrize("kind", ["missing", "duplicate", "binary", "foreign-source"])
def test_pyinstaller_override_rejects_ambiguous_or_foreign_analysis(package, kind):
    source, output, manifest = package
    driver.stage(source, output, manifest)
    entry = ("playwright/" + driver.BUNDLE, str(source / driver.BUNDLE), "DATA")
    entries = {"missing": [], "duplicate": [entry, entry], "binary": [(entry[0], entry[1], "BINARY")],
               "foreign-source": [(entry[0], "foreign/coreBundle.js", "DATA")]}[kind]
    with pytest.raises(driver.DriverStageError):
        driver.bundle_datas(entries, source, output, manifest)


def test_pyinstaller_override_rejects_drift_in_an_unpatched_python_asset(package):
    source, output, manifest = package
    driver.stage(source, output, manifest)
    (source / "__init__.py").write_bytes(b"changed Python API")
    entry = ("playwright/" + driver.BUNDLE, str(source / driver.BUNDLE), "DATA")
    with pytest.raises(driver.DriverStageError, match="differs from the stage source"):
        driver.bundle_datas([entry], source, output, manifest)


@pytest.fixture
def measured_stage():
    return json.loads((driver.ROOT / "native/drafts/environment/driver-stage70-observations.json").read_bytes())


def test_measured_stage_binds_public_sources_without_release_admission(measured_stage, stage_before_python_overlay_sources):
    assert measured_stage["passed"] and measured_stage["measurement_complete"]
    for name in ("selected", "privacy_admitted", "production_admitted", "cryptographically_signed", "main_manager_bfcache_enabled"):
        assert measured_stage[name] is False
    for name, expected in measured_stage["public_sources_normalized_utf8_lf_sha256"].items():
        source = (stage_before_python_overlay_sources[name] if name in stage_before_python_overlay_sources
                  else (driver.ROOT / name).read_text(encoding="utf-8-sig").replace("\r\n", "\n"))
        assert sha(source.encode("utf-8")) == expected, name
    manifest, _ = driver.load_manifest(driver.DEFAULT_MANIFEST)
    assert measured_stage["prepared_driver_sha256"] == manifest["bundle_sha256"]
    assert measured_stage["desktop_build"]["frozen_driver_sha256"] == manifest["bundle_sha256"]
    assert measured_stage["desktop_build"]["frozen_node_sha256"] == manifest["node_sha256"]


def test_measured_optin_controls_and_default_runtime_are_distinct(measured_stage):
    model = measured_stage["model"]
    assert model["passed"] and model["tests"] == len(model["results"]) == 30
    assert all(row["passed"] for row in model["results"])
    assert sum(row["name"].startswith("default-launch-path-") for row in model["results"]) == 4
    default = measured_stage["default_native_runtime"]
    assert default["passed"] and len(default["checks"]) == 18
    assert default["probe"] == {"default_launch_bfcache_disabled": True, "resources_released": True, "driver_import_verified": True}
    assert default["source_unchanged"] and default["installed_driver_unchanged"]


def test_measured_replay_covers_both_modes_and_restarts(measured_stage):
    replay = measured_stage["recorder_replay"]
    assert replay["postguards_passed"]
    assert {(row["mode"], row["phase"]) for row in replay["runs"]} == {
        (mode, phase) for mode in ("manager-desktop", "manager-mobile-web")
        for phase in ("initial", "persistent-profile-restart")
    }
    for row in replay["runs"]:
        assert row["passed"] and row["replay_passed"]
        assert row["history_navigation_type"] == "BackForwardCacheRestore"
        assert len(row["restored_roles"]) == len(row["pending_counts"]) == 6
        assert set(row["pending_counts"].values()) == {0} and row["warnings"] == []


def test_measured_legacy_provider_comparison_covers_original_and_staged(measured_stage):
    rows = measured_stage["provider_comparisons"]
    assert {(row["provider"], row["mode"]) for row in rows} == {
        (provider, mode) for provider in ("camoufox", "cloakbrowser") for mode in ("original", "staged")
    }
    manifest, _ = driver.load_manifest(driver.DEFAULT_MANIFEST)
    for row in rows:
        assert row["passed"] and row["postguards_passed"] and row["remaining_owned_processes"] == 0
        assert row["driver_sha256"] == manifest["base_bundle_sha256" if row["mode"] == "original" else "bundle_sha256"]
        assert row["automatic_downloads_enabled"] is row["production_admitted"] is False
        assert len(row["runs"]) == 2
        assert all(run["passed"] and run["form_and_frame_actions"] and run["five_stores"] and run["screenshot_png"]
                   for run in row["runs"])


def test_measured_frozen_checks_preserve_expected_timeout_semantics(measured_stage):
    rows = measured_stage["frozen_provider_checks"]
    assert {row["runtime"]["engine"] for row in rows} == {"camoufox", "cloakbrowser"}
    for row in rows:
        assert row["passed"] and row["files_unchanged"] and row["returncode"] == 0
        checks = {check["name"]: check for check in row["runtime"]["checks"]}
        assert checks["browser-and-imports"]["status"] == "success"
        assert checks["hard-timeout"]["status"] == "failed"
        assert checks["hard-timeout"]["error"] == "Python timeout"
        assert all(check["passed"] for check in checks.values())
    comparison = measured_stage["desktop_build"]["repeat_distribution"]
    assert comparison["identical"] and comparison["first_files"] == comparison["second_files"] == 2521
    assert comparison["differences"] == []


def test_python_binding_outcome_draft_reconstructs_exact_source_and_passes_model(tmp_path):
    import playwright

    environment = driver.ROOT / "native/drafts/environment"
    evidence = json.loads((environment / "binding-close70-observations.json").read_bytes())
    original = Path(playwright.__file__).parent / "_impl/_page.py"
    assert sha(original.read_bytes()) == evidence["base_python_sha256"]
    patch = environment / evidence["patch"]
    assert sha(patch.read_bytes()) == evidence["patch_sha256"]
    prepared = tmp_path / "playwright/_impl/_page.py"
    prepared.parent.mkdir(parents=True)
    prepared.write_bytes(original.read_bytes())
    subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--whitespace=error", str(patch)],
                   cwd=tmp_path, capture_output=True, check=True, timeout=15)
    assert sha(prepared.read_bytes()) == evidence["prepared_python_sha256"]
    runner = environment / "first-script/binding_outcome_model.py"
    assert sha(runner.read_bytes()) == evidence["model_runner_sha256"]
    report = tmp_path / "model.json"
    subprocess.run([sys.executable, str(runner), "--source", str(prepared), "--report", str(report)],
                   capture_output=True, check=True, timeout=15)
    model = json.loads(report.read_bytes())
    assert model["passed"] and model["tests"] == len(model["results"]) == 10
    assert all(row["passed"] for row in model["results"])
    assert model == evidence["model"]
    assert evidence["selected"] is evidence["included_in_desktop_stage"] is False
    assert evidence["baseline"]["passed"] is False and len(evidence["baseline"]["asyncio_errors"]) == 3
    assert evidence["candidate"]["passed"] is True and evidence["candidate"]["asyncio_errors"] == []


def test_strict_gate_patch_reconstructs_the_portable_runner(tmp_path):
    environment = driver.ROOT / "native/drafts/environment"
    evidence = json.loads((environment / "binding-close70-observations.json").read_bytes())
    source = environment / "first-script/bfcache_stress.py"
    assert sha(source.read_bytes()) == evidence["strict_gate_base_source_sha256"]
    target = tmp_path / source.relative_to(driver.ROOT)
    target.parent.mkdir(parents=True)
    target.write_bytes(source.read_bytes())
    patch = environment / evidence["strict_gate_patch"]
    assert sha(patch.read_bytes()) == evidence["strict_gate_patch_sha256"]
    subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--whitespace=error", str(patch)],
                   cwd=tmp_path, capture_output=True, check=True, timeout=15)
    assert sha(target.read_bytes()) == evidence["strict_gate_portable_source_sha256"]
    compile(target.read_text(encoding="utf-8"), str(target), "exec")

@pytest.fixture
def python_package(package):
    source, output, manifest = package
    relative = "_impl/_page.py"
    original = source / relative
    original.parent.mkdir(parents=True)
    original.write_bytes(b"old python\n")
    patch = manifest.parent / "python.patch"
    name = "playwright/" + relative
    patch.write_text("diff --git a/" + name + " b/" + name + "\n" + "".join(difflib.unified_diff(
        ["old python\n"], ["new python\n"], fromfile="a/" + name, tofile="b/" + name)), encoding="utf-8", newline="\n")
    record = json.loads(manifest.read_bytes())
    record["python_overlay"] = {"file": relative, "base_sha256": sha(b"old python\n"), "sha256": sha(b"new python\n"),
                                "patch": patch.name, "patch_sha256": sha(patch.read_bytes())}
    manifest.write_text(json.dumps(record), encoding="utf-8")
    return source, output, manifest


def test_python_js_stage_preserves_source_and_replaces_both_analysis_assets(python_package):
    source, output, manifest = python_package
    before = driver.inventory(source, source=True)
    receipt = driver.stage(source, output, manifest)
    assert driver.inventory(source, source=True) == before
    assert receipt["assets"] == {**before, driver.BUNDLE: sha(b"new\n"), "_impl/_page.py": sha(b"new python\n")}
    pure = [("playwright._impl._page", str(source / "_impl/_page.py"), "PYMODULE"), ("app.main", "untouched.py", "PYMODULE")]
    result = driver.bundle_pure(pure, source, output, manifest)
    assert result[1] == pure[1] and pure[0][1] == str(source / "_impl/_page.py")
    assert result[0] == (pure[0][0], str((output / "playwright/_impl/_page.py").resolve()), "PYMODULE")
    data = [("playwright/" + driver.BUNDLE, str(source / driver.BUNDLE), "DATA")]
    assert driver.bundle_datas(data, source, output, manifest)[0][1] == str((output / "playwright" / driver.BUNDLE).resolve())


@pytest.mark.parametrize("field,value", [("file", "_impl/_connection.py"), ("base_sha256", True), ("patch", "../outside.patch"), ("patch_sha256", "0" * 64)])
def test_python_overlay_rejects_invalid_selection_before_copy(python_package, field, value):
    source, output, manifest = python_package
    record = json.loads(manifest.read_bytes())
    record["python_overlay"][field] = value
    manifest.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(driver.DriverStageError):
        driver.stage(source, output, manifest)
    assert not output.exists()


def test_python_overlay_checks_original_module_before_copy(python_package):
    source, output, manifest = python_package
    (source / "_impl/_page.py").write_bytes(b"unknown Python source")
    with pytest.raises(driver.DriverStageError, match="module differs from the pin"):
        driver.stage(source, output, manifest)
    assert not output.exists()


@pytest.mark.parametrize("kind", ["missing", "duplicate", "data", "foreign"])
def test_python_analysis_rejects_wrong_or_ambiguous_module(python_package, kind):
    source, output, manifest = python_package
    driver.stage(source, output, manifest)
    module = ("playwright._impl._page", str(source / "_impl/_page.py"), "PYMODULE")
    entries = {"missing": [], "duplicate": [module, module], "data": [(module[0], module[1], "DATA")],
               "foreign": [(module[0], "foreign.py", "PYMODULE")]}[kind]
    with pytest.raises(driver.DriverStageError):
        driver.bundle_pure(entries, source, output, manifest)


def test_js_only_stage_does_not_override_python_analysis(package):
    source, output, manifest = package
    driver.stage(source, output, manifest)
    entries = [("app.main", "owned.py", "PYMODULE")]
    result = driver.bundle_pure(entries, source, output, manifest)
    assert result == entries and result is not entries


def test_measured_python_js_package_binds_current_sources_and_embedded_python():
    environment = driver.ROOT / "native/drafts/environment"
    record = json.loads((environment / "python-js-stage70-observations.json").read_bytes())
    manifest, _ = driver.load_manifest(environment / record["manifest"])
    assert record["passed"] and record["measurement_complete"] and record["file_count"] == 176
    assert record["python_binding_fix_included"] and record["js_bfcache_optin_included"]
    for field in ("selected", "privacy_admitted", "production_admitted", "cryptographically_signed",
                  "default_driver_replaced", "main_manager_bfcache_enabled", "frozen_native_bfcache_verified"):
        assert record[field] is False
    for name, expected in record["source_normalized_utf8_lf_sha256"].items():
        assert sha((driver.ROOT / name).read_text(encoding="utf-8-sig").encode("utf-8")) == expected
    code = record["frozen_binding_code"]
    assert code["passed"] and code["executable_sha256"] == record["desktop_build"]["executable_sha256"]
    assert code["prepared_python_sha256"] == manifest["python_overlay"]["sha256"]
    assert record["desktop_build"]["frozen_driver_sha256"] == manifest["bundle_sha256"]
    assert record["desktop_build"]["frozen_node_sha256"] == manifest["node_sha256"]
    assert record["js_only_stage_still_verifies"]


def test_measured_python_js_runtime_and_races_keep_their_admission_boundaries():
    record = json.loads((driver.ROOT / "native/drafts/environment/python-js-stage70-observations.json").read_bytes())
    baseline = record["default_native_runtime"]
    assert baseline["passed"] and len(baseline["checks"]) == 18
    assert baseline["probe"]["default_launch_bfcache_disabled"]
    assert baseline["source_unchanged"] and baseline["installed_driver_unchanged"]
    replay = record["recorder_replay"]
    assert replay["postguards_passed"] and len(replay["runs"]) == 4
    assert all(row["passed"] and row["replay_passed"] and not row["warnings"]
               and set(row["pending_counts"].values()) == {0} for row in replay["runs"])
    strict = record["strict_cancelled_stop"]
    assert strict["passed"] and strict["asyncio_errors"] == [] and len(strict["runs"]) == 4
    assert all(row["close_cancellation_observed"] and row["cross_process_profile_owner_retained"]
               and row["second_close_completed_original_driver_stop"] and row["remaining_owned_processes"] == 0 for row in strict["runs"])
    races = record["restoration_races"]
    assert races["passed"] and races["test_only_driver_instrumentation"] and len(races["runs"]) == 6
    assert races["driver_sha256"] != record["desktop_build"]["frozen_driver_sha256"]
    assert all(row["passed"] and row["barrier_held_until_action_finished"] and row["remaining_owned_processes"] == 0 for row in races["runs"])
    assert {row["provider"] for row in record["provider_transport"]} == {"camoufox", "cloakbrowser"}
    assert all(row["passed"] and row["postguards_passed"] for row in record["provider_transport"])
    assert {row["runtime"]["engine"] for row in record["frozen_provider_checks"]} == {"camoufox", "cloakbrowser"}
    assert all(row["passed"] and row["files_unchanged"] for row in record["frozen_provider_checks"])
