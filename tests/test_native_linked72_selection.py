import hashlib
import json
from pathlib import Path

from scripts import native_build as build
from scripts import verify_native_privacy_units as units


ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / "native/drafts/environment"


def test_selected_72_preserves_exact_70_prefix_and_binds_both_native_patches():
    candidate = build.load_candidate("upstream-156")
    record = json.loads((ENV / "linked72-selection-observations.json").read_bytes())
    baseline = json.loads((candidate["directory"] / "checkpoints/001-070.json").read_bytes())
    first = json.loads((candidate["directory"] / "checkpoints/001-071.json").read_bytes())
    final = (candidate["directory"] / "checkpoints/001-072.json").read_bytes()
    assert record["selected"] and record["preserved_baseline"] == "001-070"
    assert candidate["manifest_sha256"] == hashlib.sha256(final).hexdigest() == record["selected_manifest_sha256"]
    assert json.loads(final) == candidate["manifest"]
    assert {**candidate["manifest"], "patches": candidate["manifest"]["patches"][:70]} == baseline
    assert {**candidate["manifest"], "patches": candidate["manifest"]["patches"][:71]} == first
    assert len(candidate["manifest"]["patches"]) == 72
    sources = [ENV / "orientation-visibility71.patch", ENV / "canvas-formats-next/canvas-formats-next.patch"]
    assert [row["file"] for row in candidate["manifest"]["patches"][-2:]] == record["patches"]
    for row, source in zip(candidate["manifest"]["patches"][-2:], sources, strict=True):
        registered = candidate["directory"] / "patches" / row["file"]
        assert registered.read_bytes() == source.read_bytes()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == row["sha256"]
    assert record["jobs"] == 4 and len(record["source_paths"]) == 9
    assert len({row["path"] for row in record["source_paths"]}) == 9
    assert all(row["before_sha256"] != row["after_sha256"] for row in record["source_paths"])


def test_current_orientation_gate_extends_all_twenty_historical_targets(native_units_before_orientation):
    historical = native_units_before_orientation["namespace"]
    assert units.SUPPORTED_TARGETS == (*historical["SUPPORTED_TARGETS"], "screen-orientation")
    assert len(units.SUPPORTED_TARGETS) == 21
    for target in historical["SUPPORTED_TARGETS"]:
        assert units.required_tests(target) == historical["required_tests"](target)
        assert units.unit_binary_target(target) == historical["unit_binary_target"](target)
    cases = {suite + "." + name for suite, names in units.required_tests("screen-orientation").items() for name in names}
    preparation = json.loads((ENV / "orientation-visibility71-preparation.json").read_bytes())
    assert cases == set(preparation["prepared_cases"]) and len(cases) == 4
    assert units.unit_binary_target("screen-orientation") == "blink_unittests"


def test_source_selection_and_syntax_are_not_browser_or_case_execution():
    record = json.loads((ENV / "linked72-selection-observations.json").read_bytes())
    assert record["native_target_groups"] == 21 and record["native_orientation_cases_required"] == 4
    assert record["isolated_transform_controls"] == 12 and record["isolated_copy_controls"] == 283
    assert record["source_preflight"]["passed"] and len(record["source_preflight"]["checks"]) == 3
    assert all(row["returncode"] == 0 for row in record["source_preflight"]["checks"])
    assert all(record[name] is False for name in ("compiled_into_browser", "native_tests_executed", "runtime_verified",
                                                "privacy_admitted", "production_admitted"))
