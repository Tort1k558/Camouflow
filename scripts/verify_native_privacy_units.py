"""Build and verify native privacy units; not a browser runtime/capability gate."""

from __future__ import annotations

import argparse
import hashlib
import json
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


REQUIRED_CONTEXT_TESTS = {
    "NativePrivacyBrowserContextTest": {
        "PersistentLoadingGatesReadinessAndDerivation", "PersistentIdentitySurvivesActualContextRecreation",
        "PersistentProfilesHaveIndependentKeys", "OffTheRecordContextsDoNotShareOriginalOrEachOther",
        "OffTheRecordRejectsPersistentRootBeforeInstallation", "PersistentContextRejectsEmptyRoot",
        "MissingIdentityFailsWithoutRegeneration", "MalformedIdentityIsNotReplaced",
        "BrowserContextShutdownClearsReadyService", "ShutdownDuringLoadRejectsLateReply",
        "DestructionDuringLoadDoesNotUseDestroyedContext", "BrowserBridgeSeparatesSurfacesAndTopLevelSites",
        "NullContextIsRejected", "ContextReadinessRejectsMissingServiceAndNullContext",
        "ContextReadinessWaitsForKeyAndAllowsDerivation", "ContextReadinessSettlesFailedIdentity",
        "ContextShutdownSettlesQueuedReadinessOnce", "ContextDestructionNeverReportsReadinessSuccess",
        "ContextCallbackShutdownRejectsRemainingReadiness", "OffTheRecordReadinessCompletesInlineWithoutPersistentKey",
        "StartupKeyReadyBeforeEventLoop", "StartupMissingIdentityIsTerminalWithoutCreation",
        "StartupMalformedIdentityIsNotReplaced", "StartupCannotReplaceReadyOrLoadingOwner",
        "StartupOffTheRecordNeverReadsPersistentIdentity", "StartupRejectsInvalidRootWithoutInstallingOwner",
    },
}


REQUIRED_DELIVERY_TESTS = {
    "NativePrivacyDocumentServiceTest": {
        "MissingServiceReturnsUnavailable", "ReadyContextDeliversOnlyCanvasSubkey",
        "LoadingDoesNotReplyBeforeReadiness", "NativePartitionEncodingRetainsDisabledStoragePartitionFields",
        "ShutdownSettlesOnceWithoutSeed", "TimeoutRejectsLateReadyReply", "PipeDisconnectDropsLoadingReply",
        "DocumentDestructionDropsLoadingReply", "DuplicateRequestClosesLoadingPipe",
    },
    "NativePrivacyWorkerServiceTest": {
        "MissingServiceReturnsUnavailable", "ReadyPolicyMatchesTrustedPartition", "LoadingDoesNotReplyBeforeReadiness",
        "ShutdownSettlesLoadingOnce", "DeadlineRejectsLateReadiness", "ReceiverOwnerDestructionDropsLoadingReply",
        "PipeDisconnectDropsLoadingReply", "DestroyedContextCannotDeliverSeed", "UnpartitionedSharedAndServiceWorkersFail",
        "LegacyDataWorkerOriginMismatchIsRejected", "MatchingOpaqueDataWorkerUsesOwnedPartition",
        "DuplicateRequestCancelsPendingDelivery",
    },
    "NativePrivacyWorkerBootstrapTest": {
        "ReadyPolicyReturnsOwnedSurfaceSeedOnce", "UnavailableDoesNotReturnSeed", "BrowserTimeoutDoesNotReturnSeed",
        "UnknownVersionIsRejected", "ReadyWithoutPolicyIsRejected", "FailureWithSeedIsRejected",
        "PeerDisconnectSettlesOnce", "DeadlineRejectsLateReadyReply", "DestructionDropsPendingReply",
        "MissingPipeReturnsTypedFailure",
        "ReadyCallbackCanDestroyConsumer", "FailureCallbackCanDestroyConsumer", "DeadlineCallbackCanDestroyConsumer",
    },
}

REQUIRED_WORKER_HANDOFF_TESTS = {
    "WorkerThreadTest": {
        "GlintCanvasSeedArrivesBeforeEvaluation", "GlintCanvasSeedRemainsAbsentWithoutBootstrap",
        "GlintSequentialScopesDoNotReusePreviousCanvasSeed", "GlintImmediateTerminationRetainsOwnedCanvasSeed",
    },
}

REQUIRED_WORKER_SURFACE_TESTS = {
    **{suite: REQUIRED_DELIVERY_TESTS[suite] for suite in (
        "NativePrivacyWorkerServiceTest", "NativePrivacyWorkerBootstrapTest")},
    "NativePrivacyWorkerSurfaceServiceTest": {
        "MissingServiceReturnsNoSnapshot", "ReadySnapshotMatchesEveryDomainForAllWorkerKinds",
        "LoadingDoesNotReplyWithPrematureSnapshot", "WrongWorkerOriginCannotGetSnapshot",
        "ShutdownDuringReadinessReturnsNoSnapshot", "SurfaceThenCanvasCannotRequestTwice",
        "CanvasThenSurfaceCannotRequestTwice", "UnpartitionedSharedServiceWorkersRejectSnapshot",
    },
    "NativePrivacyWorkerSurfaceBootstrapTest": {
        "ReadyReturnsOwnedIndependentSnapshotOnce", "UnavailableReturnsNoSnapshot",
        "BrowserTimeoutReturnsNoSnapshot", "CanvasVersionCannotSatisfySurfaceRequest",
        "ReadyWithoutSnapshotIsRejected", "FailureWithSnapshotIsRejected",
        "DifferentPartitionCannotInstallSnapshot", "ReusedSurfaceSeedIsRejected",
        "PeerDisconnectSettlesOnce", "DeadlineRejectsLateSnapshot", "DestructionDropsPendingReply",
        "MissingPipeReturnsTypedFailure", "ReadyCallbackCanDestroyConsumer",
        "FailureCallbackCanDestroyConsumer", "DeadlineCallbackCanDestroyConsumer",
        "OpaquePartitionPreservesOwnedIdentity", "OriginOnlyRequestOwnsBrowserPartition",
        "FlagsSelectExactlyOneExplicitMode", "OffModeRejectsUnexpectedBootstrapData",
        "CanvasModeCannotUseSurfaceFallback", "SurfaceModeCannotUseCanvasFallback",
        "ConflictAndUnknownModeNeverBecomeReady",
    },
}

REQUIRED_DOCUMENT_PARTITION_TESTS = {
    "GlintDocumentCanvasPolicyTest": {
        "MatchingPartitionReturnsOwnedSeed", "UnknownVersionRejectsMatchingPartition",
        "MissingCommitmentRejectsPolicy", "OriginChangeRejectsPreviousCommitment",
        "RetainedTopLevelSiteMattersWithPartitioningOff", "RetainedAncestorChainMatters",
        "StorageNonceChangeRejectsCommitment", "OpaqueOriginRequiresExactOwnedIdentity",
        "EmbeddedNullAndTrailingDataAreNotIgnored",
    },
}

REQUIRED_DOCUMENT_NAVIGATION_TESTS = {
    "WithAndWithoutUrlLoader/NativeDocumentNavigationTest": {
        f"{case}/{index}" for index in range(2) for case in (
            "FlagOffKeepsUpstreamCommitWithoutKeyService",
            "MissingPolicyRejectsBeforeCommit",
            "ReadyRequestCarriesItsSelectedPartitionPolicy",
            "SelectedFrameRejectsExactPendingCommit",
            "UnknownTokenDoesNotCancelPendingCommit",
            "PolicyAbsentCannotUseRejectionProtocol",
        )
    },
}

REQUIRED_SURFACE_NAVIGATION_TESTS = {
    "WithAndWithoutUrlLoader/NativeDocumentNavigationTest": (
        REQUIRED_DOCUMENT_NAVIGATION_TESTS["WithAndWithoutUrlLoader/NativeDocumentNavigationTest"] | {
            f"{case}/{index}" for index in range(2) for case in (
                "SurfaceReadyRequestCarriesAllSelectedPartitionDomains", "SurfaceMissingPolicyRejectsBeforeCommitWithoutFallback",
                "SurfaceConflictingFlagsRejectEvenReadyContext", "SurfaceSelectedFrameRejectsOnlyItsExactPendingToken",
                "SurfaceUnknownTokenDoesNotCancelPendingCommit", "SurfaceStaleRejectedTokenCannotCancelNextNavigation",
                "SurfaceFlagOffCannotCarryPriorNavigationEnvelope", "SurfaceRejectionObserverMayDestroyWebContents",
                "LateCanvasPolicyLossCancelsAndAllowsNextNavigation", "LateCanvasPolicyLossObserverMayDestroyWebContents",
                "LateSurfacePolicyLossCancelsAndAllowsNextNavigation", "LateSurfacePolicyLossObserverMayDestroyWebContents")}),
    "NativeDocumentSurfaceReadinessTest": {
        "ReadyContextProceedsForBothCommitPaths", "LoadingDefersThenResumesOnlyOnce",
        "MissingContextCancelsAfterDeferInstalled", "DeadlineRejectsLateReplyWithoutCanvasFallback",
        "ConflictingFlagsRejectReadyContextWithoutWaiting", "ShutdownCancelsPendingReplyExactlyOnce"},
}

REQUIRED_WINDOW_TRANSPORT_TESTS = {
    "GlintWindowPrivacyReadinessTest": {
        "MissingContextRejectsInline", "UninitializedContextRejectsInline", "LoadingWaitsForActualProfileReadiness",
        "DuplicateStartDoesNotRequestTwice", "DestructionCancelsBeforeServiceReply", "ShutdownSettlesFailureOnce",
        "MalformedIdentityDoesNotOpenWindow", "InlineCallbackMayDestroyRequest"},
    "GlintChildSurfaceTransportTest": {
        "FeatureOffRejectsBeforeTokenConsumption", "FeatureOffNeverExposesReadyProfilePolicy",
        "FeatureOffCallbackCanDestroyFrameOwner", "ActualInitialChildKeyMatchesItsFourBrowserDerivations",
        "SamePartitionParentAndChildUseSamePolicyNotCopiedState"},
}

REQUIRED_GPU_PACK_TESTS = {
    "GlintRgba8PackCopyTest": {
        "TightLayoutCopiesRowsWithoutSourceMutation", "NonzeroOffsetPreservesPrefixAndSuffix",
        "SkipsAndPaddingAreNotWritten", "AlignmentEightPreservesInterRowPadding",
        "LastRowDoesNotRequireTrailingPadding", "OverlappingRowsUseUpstreamLayout",
        "ShortDestinationRejectsBeforeAnyWrite", "WrongSourceSizeRejectsBeforeAnyWrite",
        "AliasedStorageCannotMutateCanonicalSource", "NegativeDimensionsRejectBeforeAnyWrite",
        "InvalidPackFieldsRejectWithoutUpstreamDcheck", "RowStrideOverflowRejectsBeforeAnyWrite",
        "OversizedOffsetRejectsBeforeAnyWrite", "EmptyReadsDoNotTouchSourceOrDestination"},
}

NEW_TARGETS = ("surface-navigation", "window-transport", "gpu-pack-copy", "worker-surfaces")

DELIVERY_SOURCE_FILES = {
    f"{name}{suffix}": f"{directory}/{name}{suffix}"
    for name, directory in (
        ("privacy_document_service", "content/browser/camouflow_native"),
        ("privacy_worker_service", "content/browser/camouflow_native"),
        ("privacy_worker_bootstrap", "content/renderer/worker"),
    )
    for suffix in (".h", ".cc", "_unittest.cc")
}
DELIVERY_SOURCE_FILES["native_privacy_document.mojom"] = (
    "third_party/blink/public/mojom/native_privacy/native_privacy_document.mojom"
)


def require_delivery_sources(source: Path) -> dict[str, str]:
    checksums = {}
    for name, relative in DELIVERY_SOURCE_FILES.items():
        path = source / relative
        expected = ROOT / "native/drafts/document_delivery" / name
        if (path.is_symlink() or path != path.resolve() or not path.is_file()
                or path.read_text(encoding="utf-8-sig") != expected.read_text(encoding="utf-8-sig")):
            raise ValueError(f"Promote the exact delivery draft before verification: {relative}")
        checksums[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return checksums


def required_tests(target: str) -> dict[str, set[str]]:
    if target == "worker-surfaces":
        return REQUIRED_WORKER_SURFACE_TESTS
    if target == "surface-navigation":
        return REQUIRED_SURFACE_NAVIGATION_TESTS
    if target == "window-transport":
        return REQUIRED_WINDOW_TRANSPORT_TESTS
    if target == "gpu-pack-copy":
        return REQUIRED_GPU_PACK_TESTS
    if target == "document-navigation":
        return REQUIRED_DOCUMENT_NAVIGATION_TESTS
    if target == "keys":
        return REQUIRED_TESTS
    if target == "contexts":
        return REQUIRED_CONTEXT_TESTS
    if target == "delivery":
        return REQUIRED_DELIVERY_TESTS
    if target == "worker-handoff":
        return REQUIRED_WORKER_HANDOFF_TESTS
    if target == "document-partition":
        return REQUIRED_DOCUMENT_PARTITION_TESTS
    raise ValueError("Unknown native privacy test target")


def validate_results(report: dict, *, target: str = "keys") -> None:
    required = required_tests(target)
    expected = {(suite, case) for suite, cases in required.items() for case in cases}
    if (not isinstance(report, dict)
            or any(type(report.get(key)) is not int for key in ("tests", "failures", "disabled"))
            or report.get("tests") != len(expected)
            or report.get("failures") != 0 or report.get("disabled") != 0):
        raise ValueError("Native privacy test totals are incomplete or failed")
    observed = []
    suites = report.get("testsuites")
    if not isinstance(suites, list) or len(suites) != len(required):
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


def verify(workspace: Path, report: Path, *, vs_installation: Path | None = None, jobs: int = 4,
           target: str = "keys") -> dict:
    required = required_tests(target)
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
    if target in {"contexts", "delivery"}:
        required_patches.add("0017-native-browser-context-tests.patch")
    if target == "contexts":
        required_patches.add("0032-native-document-surface-policy.patch")
    if target in {"surface-navigation", "window-transport"}:
        required_patches.update({"0031-native-worker-surface-policy.patch", "0032-native-document-surface-policy.patch",
                                 "0041-native-child-transport-fixture-interface.patch"})
    if target == "surface-navigation":
        required_patches.update({"0039-native-document-ready-commit-cancellation.patch",
                                 "0040-native-ready-commit-observer-lifetime.patch"})
    if target == "worker-surfaces":
        required_patches.update({"0017-native-browser-context-tests.patch",
                                 "0018-native-document-policy-delivery.patch",
                                 "0019-native-worker-policy-delivery.patch",
                                 "0020-native-worker-policy-consumer.patch",
                                 "0031-native-worker-surface-policy.patch",
                                 "0036-native-worker-complete-surface-type.patch"})
    if target == "gpu-pack-copy":
        required_patches.add("0034-native-gpu-metadata-minimization.patch")
    if target == "delivery":
        required_patches.update({"0018-native-document-policy-delivery.patch",
                                 "0019-native-worker-policy-delivery.patch",
                                 "0020-native-worker-policy-consumer.patch"})
    if target == "worker-handoff":
        required_patches.update({"0022-native-worker-canvas-thread-handoff.patch",
                                 "0024-native-service-worker-canvas-thread-handoff.patch",
                                 "0026-native-worker-canvas-handoff-tests.patch"})
    if target == "document-partition":
        required_patches.add("0029-native-document-partition-validator-tests.patch")
    if target == "document-navigation":
        required_patches.add("0030-native-document-commit-prototype.patch")
    if not required_patches.issubset(item["name"] for item in patches):
        raise ValueError("The exact context ownership and readiness patches are required")
    delivery_sources = require_delivery_sources(source) if target == "delivery" else None
    arguments = (output / "args.gn").read_bytes()
    receipt = (output / "camouflow-build.json").read_bytes()
    core = measure_runtime_core(output / "chrome.exe")
    scope = ("Surface v2 NavigationSimulator/readiness units; not actual Blink or browser admission"
             if target == "surface-navigation" else
             "Canvas and surface worker Mojo endpoints/bootstrap units; not worker-host startup, first-script delivery or admission"
             if target == "worker-surfaces" else
             "Window readiness and authenticated child RFH transport units; not actual renderer IPC or admission"
             if target == "window-transport" else
             "Native RGBA8 pack-copy arithmetic units; not GPU/driver readback or admission"
             if target == "gpu-pack-copy" else
             "NavigationSimulator document commit/rejection units; simulated network/renderer, not actual Blink first-script delivery or admission"
             if target == "document-navigation" else
             "Native final-partition validator units; not navigation recovery, IPC, first-script delivery or admission"
             if target == "document-partition" else
             "Blink worker-scope seed ownership/thread handoff units; not browser-delivered seed bytes, Canvas or admission"
             if target == "worker-handoff" else
             "Document/worker Mojo endpoints and bootstrap consumer units; not actual worker-host lifecycle, first-script ordering, Canvas or admission"
             if target == "delivery" else
             "Actual content-layer BrowserContext bridge/lifecycle/readiness units; not Chrome ProfileImpl startup, IPC, Canvas or admission"
             if target == "contexts" else
             "Private key derivation/loading and owner units; not real Chrome contexts, IPC, Canvas or capability admission")
    build_target = ("blink_unittests" if target in {"worker-handoff", "gpu-pack-copy"} else
                    "content_unittests" if target in {"contexts", "delivery", "document-navigation", "surface-navigation", "window-transport", "worker-surfaces"} else "camouflow_native_privacy_unittests")
    proof = {"passed": False, "scope": scope, "target": target,
             "jobs": jobs, "patches": patches, "results": str(results), "log": str(log_path)}
    with log_path.open("x", encoding="utf-8", newline="\n") as log:
        try:
            build.check_patch_dependencies(source, env)
            subprocess.run(build.depot_command("autoninja", workspace) +
                           ["-C", "out/CamouFlowNative", "-j", str(jobs), build_target],
                           cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            executable = output / (build_target + ".exe")
            test_filter = (":".join(f"{suite}.{case}" for suite, cases in required.items() for case in sorted(cases))
                           if target in {"worker-handoff", "document-partition", "document-navigation", *NEW_TARGETS} else ":".join(name + ".*" for name in required))
            subprocess.run([str(executable), "--gtest_filter=" + test_filter,
                            "--single-process-tests", "--gtest_output=json:" + str(results)],
                           cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            validate_results(json.loads(results.read_text(encoding="utf-8-sig")), target=target)
            if delivery_sources is not None and require_delivery_sources(source) != delivery_sources:
                raise ValueError("Delivery source inputs changed during verification")
            if (measure_runtime_core(output / "chrome.exe") != core
                    or (output / "args.gn").read_bytes() != arguments
                    or (output / "camouflow-build.json").read_bytes() != receipt
                    or build.source_patches(source, env) + build.v8_source_patches(source, env) != patches):
                raise ValueError("Verification changed baseline browser code, receipt or source inputs")
            with executable.open("rb") as stream:
                test_checksum = hashlib.file_digest(stream, "sha256").hexdigest()
            proof.update(passed=True, tests=sum(map(len, required.values())),
                         test_binary_sha256=test_checksum,
                         baseline_browser_code_unchanged=True, baseline_runtime_core_sha256_measured=core,
                         args_sha256=hashlib.sha256(arguments).hexdigest(),
                         browser_receipt_sha256=hashlib.sha256(receipt).hexdigest())
            if delivery_sources is not None:
                proof["delivery_source_sha256"] = delivery_sources
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
    parser.add_argument("--target", choices=("keys", "contexts", "delivery", "worker-handoff", "document-partition", "document-navigation", *NEW_TARGETS), default="keys")
    args = parser.parse_args()
    try:
        report = verify(args.workspace, args.report, vs_installation=args.vs_installation, jobs=args.jobs, target=args.target)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"Native privacy verification failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"passed": report["passed"], "report": str(args.report)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
