"""Bind opted-in browser checkpoint cases to the actual fixture source bytes."""

import hashlib
from pathlib import Path
import re
import stat


BROWSER_TEST_SOURCE = "chrome/browser/net/glint_cookie_prefix_browsertest.cc"
CRASH_SUITE = "GlintCookiePrefixBrowserTest"
CRASH_PRE_CASE = "PRE_CrashAfterAcknowledgedPrefix"
CRASH_POST_CASE = "CrashAfterAcknowledgedPrefix"
MAX_CRASH_PHASE_SECONDS = 300
MAX_FIXTURE_BYTES = 2 * 1024 * 1024
_CASE_PATTERN = re.compile(r"\b(TEST(?:_F|_P)?|IN_PROC_BROWSER_TEST_F)\(\s*(\w+),\s*(\w+)")


def validate_browser_contract(source: Path, plan: dict) -> dict[str, str]:
    """Validate this fixture only; compiled provenance and discovery are separate gates."""
    if (not isinstance(source, Path) or not source.is_absolute()
            or source.resolve(strict=True) != source or not source.is_dir()):
        raise ValueError("Browser contract requires a canonical existing source directory")
    if not isinstance(plan, dict) or not isinstance(plan.get("browser_execution"), dict):
        raise ValueError("Browser execution requires its explicit versioned contract")
    contract = plan["browser_execution"]
    expected = {
        "schema": 1,
        "mode": "source-bound-acknowledged-crash-v1",
        "binary": "browser_tests",
        "source": BROWSER_TEST_SOURCE,
        "expected_termination_case": CRASH_SUITE + "." + CRASH_PRE_CASE,
        "recovery_case": CRASH_SUITE + "." + CRASH_POST_CASE,
        "ordinary_pre_chains_require_fresh_shared_profiles": True,
        "maximum_crash_phase_seconds": MAX_CRASH_PHASE_SECONDS,
        "forced_phase_is_gtest_pass": False,
    }
    if (set(contract) != set(expected) | {"source_sha256"}
            or any(type(contract[key]) is not type(value) or contract[key] != value
                   for key, value in expected.items())
            or not isinstance(contract["source_sha256"], str)
            or re.fullmatch(r"[a-f0-9]{64}", contract["source_sha256"]) is None):
        raise ValueError("Unsupported or mismatched browser execution contract")
    cases = plan.get("cases")
    binaries = plan.get("binaries")
    if (not isinstance(cases, list) or not cases or len(cases) > 50000
            or type(plan.get("native_case_bodies_prepared")) is not int
            or plan["native_case_bodies_prepared"] != len(cases)
            or not isinstance(binaries, list) or not binaries
            or any(not isinstance(binary, str) for binary in binaries)
            or len(set(binaries)) != len(binaries) or "browser_tests" not in binaries
            or any(not isinstance(row, dict) or row.get("binary") not in binaries for row in cases)):
        raise ValueError("Browser contract requires a complete structurally valid case plan")
    rows = [row for row in cases if row.get("source") == BROWSER_TEST_SOURCE]
    if (not rows or any(row.get("binary") != "browser_tests"
                       or row.get("kind") != "IN_PROC_BROWSER_TEST_F"
                       or not isinstance(row.get("fixture"), str)
                       or not isinstance(row.get("case"), str) for row in rows)):
        raise ValueError("Browser fixture declarations have the wrong source or test kind")
    declared = [(row["kind"], row["fixture"], row["case"]) for row in rows]
    fixture = source / BROWSER_TEST_SOURCE
    before = fixture.lstat()
    if (not stat.S_ISREG(before.st_mode) or fixture.resolve(strict=True) != fixture
            or not 0 < before.st_size <= MAX_FIXTURE_BYTES
            or (hasattr(before, "st_file_attributes") and before.st_file_attributes & 0x400)):
        raise ValueError("Browser fixture must be a bounded regular source file without links")
    with fixture.open("rb") as stream:
        raw = stream.read(MAX_FIXTURE_BYTES + 1)
    digest = hashlib.sha256(raw).hexdigest()
    if len(raw) > MAX_FIXTURE_BYTES or digest != contract["source_sha256"]:
        raise ValueError("Browser fixture source hash differs from the declared contract")
    actual = _CASE_PATTERN.findall(raw.decode("utf-8-sig"))
    if actual != declared or len(set(actual)) != len(actual):
        raise ValueError("Browser fixture cases are missing, duplicated or differ from source order")
    if any(("IN_PROC_BROWSER_TEST_F", CRASH_SUITE, case) not in actual
           for case in (CRASH_PRE_CASE, CRASH_POST_CASE)):
        raise ValueError("The exact expected-crash pair is not declared in the bound fixture")
    after = fixture.lstat()
    if (fixture.resolve(strict=True) != fixture
            or any(getattr(before, field) != getattr(after, field)
                   for field in ("st_dev", "st_ino", "st_size", "st_mtime_ns"))):
        raise ValueError("Browser fixture identity or content changed during validation")
    return {str(fixture): digest}
