"""Build and verify native privacy units; not a browser runtime/capability gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import native_build as build
from scripts.verify_native_runtime import measure_runtime_core


REQUIRED_TESTS = {
    "NativePrivacyKeyTest": {
        "RepeatedAndCopiedPartitionsAreStable", "ProfilesAreSeparated", "SurfacesAreSeparated",
        "TopLevelSitesAreSeparated", "OpaquePartitionsAreSeparatedAndCopyStable", "UnknownSurfaceIsRejected",
    },
    "NativePrivacyProfileKeyTest": {
        "ParsesExistingPythonIdentityAndDerivesKnownKey", "RejectsMalformedSchemaWithoutFallback",
        "RejectsUppercaseAndBom", "LoadsOwnedFileAndKeepsPrivateSnapshot", "MissingFileIsNotGenerated",
        "RejectsDirectoryAndOversizedFile", "RejectsHardLinkedIdentity",
    },
    "NativePrivacyKeyServiceTest": {
        "DoesNotDeriveUntilBackgroundLoadCompletes", "MissingIdentityFailsWithoutEphemeralFallback",
        "EphemeralInstancesAreIndependentAndStable", "ShutdownClearsReadyKeyAndRejectsReinitialization",
        "ShutdownCancelsLateLoadReply", "DestructionWhileLoadingDropsLateReply",
        "InitializationIsSingleUseAndRejectsRelativePath", "PersistentIdentitySurvivesServiceRecreation",
        "MalformedIdentityRemainsFailedAndUnchanged", "PersistentAndEphemeralInstancesDoNotShareKeys",
        "OwnerInstallationIsSingleUse", "OwnerDestructionDuringLoadDropsReply", "FailedOwnerCannotReplaceIdentity",
        "IndependentOwnersDoNotRedirectToOriginal", "InvalidOwnerInstallDoesNotOccupySlot",
        "OwnerDataCloneDoesNotCopyPrivateIdentity",
        "ReadinessWaitsForLoadingAndDerivesInsideCallback", "ReadyCallbacksCompleteInline",
        "UninitializedReadinessFailsInline", "FailedLoadingSettlesReadinessWithoutRegeneration",
        "ShutdownSettlesReadinessAndIgnoresLateLoad", "DestructionCancelsQueuedReadiness",
        "ReadyCallbackShutdownRejectsRemainingCallbacks", "ReadyCallbackDestructionRejectsRemainingCallbacks",
        "ReadinessCallbacksMayReenterTerminalService", "ReadinessQueueHasExplicitBound",
    },
    "All/NativePrivacyKeyVectorTest": {f"MatchesIndependentPythonVector/{index}" for index in range(4)},
}


def validate_results(report: dict) -> None:
    expected = {(suite, case) for suite, cases in REQUIRED_TESTS.items() for case in cases}
    if (not isinstance(report, dict)
            or any(type(report.get(key)) is not int for key in ("tests", "failures", "disabled"))
            or report.get("tests") != len(expected)
            or report.get("failures") != 0 or report.get("disabled") != 0):
        raise ValueError("Native privacy test totals are incomplete or failed")
    observed = []
    suites = report.get("testsuites")
    if not isinstance(suites, list) or len(suites) != len(REQUIRED_TESTS):
        raise ValueError("Native privacy test suites are missing")
    for suite in suites:
        if (not isinstance(suite, dict) or not isinstance(suite.get("name"), str)
                or not isinstance(suite.get("testsuite"), list)):
            raise ValueError("Invalid native privacy test suite")
        for case in suite["testsuite"]:
            if (not isinstance(case, dict) or not isinstance(case.get("name"), str) or case.get("status") != "RUN"
                    or case.get("result") != "COMPLETED" or case.get("failures")):
                raise ValueError("Native privacy test did not complete successfully")
            observed.append((suite.get("name"), case.get("name")))
    if len(observed) != len(expected) or set(observed) != expected:
        raise ValueError("Native privacy test names differ from required coverage")


def require_idle_builder() -> None:
    result = subprocess.run([
        "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
        "$ErrorActionPreference='Stop'; Get-Process | "
        "Where-Object { $_.ProcessName -in @('siso','ninja','clang-cl') } | "
        "Select-Object -ExpandProperty Id | ConvertTo-Json -Compress",
    ], check=True, capture_output=True, text=True)
    if result.stdout.strip():
        raise ValueError("A native compiler/build process is already running; wait for its terminal result")


def verify(workspace: Path, report: Path, *, vs_installation: Path | None = None, jobs: int = 4) -> dict:
    if sys.platform != "win32":
        raise ValueError("The owned-profile key loader verification currently supports Windows only")
    if type(jobs) is not int or not 1 <= jobs <= min(4, build.LOCK["build_jobs"]):
        raise ValueError("Native privacy verification requires 1..4 jobs")
    build.preflight(workspace)
    source = workspace / "chromium/src"
    output = source / "out/CamouFlowNative"
    if source != source.resolve() or not source.is_dir():
        raise ValueError("A canonical pinned Chromium checkout is required")
    if (not report.is_absolute() or report != report.resolve() or not report.parent.is_dir()
            or report.is_relative_to(source) or report.is_relative_to(ROOT)):
        raise ValueError("A canonical new report outside the source/application repositories is required")
    results = report.with_name(report.stem + "-tests.json")
    log_path = report.with_name(report.stem + "-build.log")
    if any(path.exists() or path.is_symlink() for path in (report, results, log_path)):
        raise ValueError("Refusing to overwrite native verification evidence")
    require_idle_builder()
    env = build.environment(workspace)
    env.update(GOMEMLIMIT="3GiB", PYTHONIOENCODING="utf-8")
    if vs_installation is not None:
        if vs_installation != vs_installation.resolve() or not vs_installation.is_dir():
            raise ValueError("Visual Studio installation must be an existing canonical directory")
        env["vs2026_install"] = str(vs_installation)
    if build.run(["git", "rev-parse", "HEAD"], source, env, capture=True) != build.LOCK["chromium_revision"]:
        raise ValueError("Chromium revision differs from the pinned build lock")
    build.require_stage(workspace / "chromium", "sync")
    build.require_stage(workspace / "chromium", "hooks")
    patches = build.source_patches(source, env) + build.v8_source_patches(source, env)
    required_patches = {"0015-native-browser-context-key-ownership.patch", "0016-native-private-key-readiness.patch"}
    if not required_patches.issubset(item["name"] for item in patches):
        raise ValueError("The exact context ownership and readiness patches are required")
    arguments = (output / "args.gn").read_bytes()
    receipt = (output / "camouflow-build.json").read_bytes()
    core = measure_runtime_core(output / "chrome.exe")
    proof = {"passed": False, "scope": "Private key derivation/loading and owner units; not real Chrome contexts, IPC, Canvas or capability admission",
             "jobs": jobs, "patches": patches, "results": str(results), "log": str(log_path)}
    with log_path.open("x", encoding="utf-8", newline="\n") as log:
        try:
            build.check_patch_dependencies(source, env)
            subprocess.run(build.depot_command("autoninja", workspace) +
                           ["-C", "out/CamouFlowNative", "-j", str(jobs), "camouflow_native_privacy_unittests"],
                           cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            executable = output / "camouflow_native_privacy_unittests.exe"
            subprocess.run([str(executable), "--gtest_filter=" + ":".join(name + ".*" for name in REQUIRED_TESTS),
                            "--single-process-tests", "--gtest_output=json:" + str(results)],
                           cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            validate_results(json.loads(results.read_text(encoding="utf-8-sig")))
            if (measure_runtime_core(output / "chrome.exe") != core
                    or (output / "args.gn").read_bytes() != arguments
                    or (output / "camouflow-build.json").read_bytes() != receipt
                    or build.source_patches(source, env) + build.v8_source_patches(source, env) != patches):
                raise ValueError("Verification changed baseline browser code, receipt or source inputs")
            with executable.open("rb") as stream:
                test_checksum = hashlib.file_digest(stream, "sha256").hexdigest()
            proof.update(passed=True, tests=sum(map(len, REQUIRED_TESTS.values())),
                         test_binary_sha256=test_checksum,
                         baseline_browser_code_unchanged=True, baseline_runtime_core_sha256_measured=core,
                         args_sha256=hashlib.sha256(arguments).hexdigest(),
                         browser_receipt_sha256=hashlib.sha256(receipt).hexdigest())
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            proof["error"] = str(error)
            log.write(f"\nVerification failed: {error}\n")
    with report.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(proof, stream, indent=2)
    return proof


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--vs-installation", type=Path)
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=4)
    args = parser.parse_args()
    try:
        report = verify(args.workspace, args.report, vs_installation=args.vs_installation, jobs=args.jobs)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"Native privacy verification failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"passed": report["passed"], "report": str(args.report)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
