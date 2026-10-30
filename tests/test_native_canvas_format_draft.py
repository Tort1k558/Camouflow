import hashlib
import json
from pathlib import Path
import runpy
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "native/drafts/environment/canvas-formats-next"


def test_compiler_flags_preserve_ninja_escaping_and_module_name(tmp_path):
    helpers = runpy.run_path(str(DRAFT / "verify_draft.py"))
    ninja = tmp_path / "target.ninja"
    ninja.write_text("\n".join([
        "defines = -DCHROMIUM", "include_dirs = -I../..", "cflags = /clang$:-ffp-contract=off",
        "cflags_cc = /std$:c++23preview", "module_deps = -fmodule-file=//build/modules$:system=system.pcm",
        "cc_module_name = //third_party/blink/renderer/core$:core", "  local = ignored",
    ]), encoding="utf-8")
    flags = helpers["compiler_flags"](ninja)
    assert "/clang:-ffp-contract=off" in flags and "/std:c++23preview" in flags
    assert "-fmodule-file=//build/modules:system=system.pcm" in flags
    assert '"-fmodule-name=//third_party/blink/renderer/core:core_Private"' in flags
    assert "ignored" not in flags and "$" not in flags


def test_missing_pinned_flags_are_not_silently_substituted(tmp_path):
    helpers = runpy.run_path(str(DRAFT / "verify_draft.py"))
    ninja = tmp_path / "empty.ninja"
    ninja.write_text("defines = -DCHROMIUM\n", encoding="utf-8")
    with pytest.raises(KeyError):
        helpers["compiler_flags"](ninja)


def test_isolated_native_evidence_does_not_admit_a_browser_fix():
    record = json.loads((DRAFT / "observations.json").read_text(encoding="utf-8"))
    for field in ("registered", "applied_to_active_checkout", "compiled_into_browser",
                  "native_browser_runtime_verified", "all_32_format_cases_passed",
                  "privacy_admitted", "production_admitted"):
        assert record[field] is False
    assert record["source_unchanged"] and record["existing_rgba8_transform_unchanged"]
    for filename, field in (("canvas-formats-next.patch", "patch_sha256"), ("half_diagnostic.cc", "fixture_sha256"),
                            ("copy_diagnostic.cc", "copy_fixture_sha256")):
        assert hashlib.sha256((DRAFT / filename).read_bytes()).hexdigest() == record[field]
    assert record["syntax"]["passed"] and len(record["syntax"]["checks"]) == 3
    assert record["canvas2d_integration_syntax"]["passed"]
    assert all(row["returncode"] == 0 for row in record["syntax"]["checks"])
    half = record["half_diagnostic"]
    assert half["passed"] and half["native_browser_runtime_verified"] is False
    assert all(row["returncode"] == 0 for row in half["steps"])
    assert half["observed"] == {"controls": 12, "failed": 0, "half_encodings": 65536,
                                 "changed_normal_channels": 92160, "runtime_verified": False}
    copy = record["copy_diagnostic"]
    assert copy["passed"] and copy["native_browser_runtime_verified"] is False
    assert copy["observed"]["controls"] == 283 and copy["observed"]["failed"] == 0
    assert copy["observed"]["lower_precision_effect_passed"]
    rows = copy["observed"]["projection"]
    assert {(row["color_space"], row["read_color_space"]) for row in rows} == {
        (source, read) for source in ("srgb", "display-p3") for read in ("srgb", "display-p3")}
    assert all(row["seed_controls"] == row["unique_f16"] == row["unique_rgba8"] == row["rgba8_affected"] == 32 for row in rows)
    assert any("not all possible images" in text for text in record["limitations"])


def test_actual_public_runner_repeat_is_bound_to_current_inputs():
    record = json.loads((DRAFT / "reproduction.json").read_text(encoding="utf-8"))
    assert record["passed"] and record["measurement_complete"] and record["postguards_passed"]
    assert record["changed_inputs"] == [] and len(record["steps"]) == 21
    assert all(step["returncode"] == 0 for step in record["steps"])
    assert record["native_browser_runtime_verified"] is record["privacy_admitted"] is record["production_admitted"] is False
    for filename, field in (("verify_draft.py", "runner_sha256"), ("half_diagnostic.cc", "fixture_sha256"),
                            ("copy_diagnostic.cc", "copy_fixture_sha256")):
        assert hashlib.sha256((DRAFT / filename).read_bytes()).hexdigest() == record[field]
    normalized = (DRAFT / "observations.json").read_text(encoding="utf-8-sig").encode("utf-8")
    assert hashlib.sha256(normalized).hexdigest() == record["observations_normalized_utf8_lf_sha256"]
    assert record["copy_observed"]["lower_precision_effect_passed"]


def test_legacy_f16_projection_failure_is_not_relabelled_as_browser_success():
    record = json.loads((DRAFT / "mantissa-lsb-failure.json").read_text(encoding="utf-8"))
    observed = record["observed"]
    assert observed["controls"] == 146 and observed["failed"] == 0
    assert observed["lower_precision_effect_passed"] is False
    assert record["native_browser_runtime_verified"] is record["privacy_admitted"] is False
    assert len(observed["projection"]) == 2
    for row in observed["projection"]:
        assert row["seed_controls"] == row["unique_f16"] == 32
        assert row["unique_rgba8"] == 1 and row["rgba8_affected"] == 0


def test_helper_patch_reconstructs_measured_sources_without_native_checkout(tmp_path):
    record = json.loads((DRAFT / "observations.json").read_text(encoding="utf-8"))
    initial = ROOT / "native/drafts/upstream-156/patches/0033-native-surface-readback.patch"
    files = {}
    name = None
    is_new = False
    body = []
    for line in initial.read_text(encoding="utf-8").splitlines(keepends=True) + ["diff --git END b/END\n"]:
        if line.startswith("diff --git "):
            if name and is_new:
                files[name] = "".join(body)
            name = line.rstrip().split(" b/", 1)[1]
            is_new = False
            body = []
        elif line.startswith("new file mode"):
            is_new = True
        elif is_new and line.startswith("+") and not line.startswith("+++"):
            body.append(line[1:])
    prefix = "third_party/blink/renderer/core/html/canvas/glint/"
    prepared = {p: h for p, h in record["prepared_source_sha256"].items() if p.startswith(prefix)}
    assert len(prepared) == 5
    for name in prepared:
        original = files[name].encode("utf-8")
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(original)
    for filename in ("0034-native-gpu-metadata-minimization.patch", "0063-native-safe-buffer-portability.patch"):
        subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--whitespace=error",
                        "--include=" + prefix + "*", str(initial.with_name(filename))],
                       cwd=tmp_path, capture_output=True, check=True, timeout=15)
    for name in prepared:
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == record["base_source_sha256"][name], name
    subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--whitespace=error",
                    "--include=" + prefix + "*", str(DRAFT / "canvas-formats-next.patch")],
                   cwd=tmp_path, capture_output=True, check=True, timeout=15)
    for name, expected in prepared.items():
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == expected
