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
from app.core.native.runtime import NativeRuntimeError
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

REQUIRED_GPU_READBACK_TESTS = {
    **REQUIRED_GPU_PACK_TESTS,
    "GlintRgba8ReadbackRegionTest": {
        "TinyCropUsesHaloNotWholeLargeFramebuffer", "ExactFullFrameNeedsOnePrivateAllocation",
        "CanvasBoundaryClipsHalo", "OutsideOnlyKeepsPrivateDriverPixels",
        "ExtremeCoordinatesDoNotOverflowClipping", "InvalidDimensionsAndUnboundedMemoryReject",
        "EmptyReadHasNoTileOrStorage", "OverlayCannotSilentlySkipFullFrameTransform",
        "ForgedPlanAndWrongStorageNeverWrite", "AliasedStorageRejectsBeforeWrite",
        "HaloMatchesFullCanvasForEverySmallCrop",
    },
    "GlintRgba8ClippedPublicationTest": {
        "PreservesClippedPixelsPaddingAndOffsets", "EntirelyOutsideDestinationRemainsExact",
        "InvalidCopyRegionNeverWrites", "ClipDoesNotRelaxOriginalBufferValidation",
        "AliasesRejectBeforeClippedWrites", "FullRegionRetainsExistingPackContract",
    },
}

NEW_TARGETS = ("surface-navigation", "window-transport", "gpu-pack-copy", "gpu-readback", "gpu-metadata", "worker-surfaces", "font-rasterization")
IDENTITY_TARGETS = ("identity-keys", "identity-contexts", "identity-transport", "identity-handoff")

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
    if target == "font-rasterization":
        return {"GlintWindowsFontRasterizationTest": {
            "ParsesEveryNamedMode", "RejectsInvalidNamesWithoutNormalization",
            "NativePreservesAllHostFields", "InvalidEnumPreservesAllHostFields",
            "ModesOnlyChangeRasterizationFields",
        }}
    if target == "gpu-metadata":
        return {
            **required_tests("gpu-metadata-codec"),
            "GLES2DecoderPassthroughTest": {
                "GlintMetadataInvalidSharedMemoryDoesNotWrite", "GlintMetadataOverflowingOffsetDoesNotWrite",
                "GlintMetadataTruncatedResultStorageDoesNotWrite", "GlintMetadataInitializedResultDoesNotWrite",
                "GlintMetadataFeatureOffPublishesOnlyUnavailable",
            },
            "GlintPassthroughAttachmentTest": {
                "ActualRgba8ExtentsPreserveRenderbufferBinding", "RedefinedAttachmentUsesCurrentNativeDimensions",
                "IntegerAttachmentIsNotByteColourCompatible", "MetadataQueryPreservesPendingClientError",
                "TextureAttachmentUsesNativeExtentsAndPreservesBinding", "TextureReattachmentUsesSelectedObjectNotBoundTexture",
                "TextureMipAttachmentReportsSelectedLevel", "CubeFaceAttachmentReportsNativeExtentsAndPreservesBinding",
                "ArrayLayerAttachmentReportsNativeExtentsAndPreservesBinding", "ThreeDimensionalLayerReportsNativeExtentsAndPreservesBinding",
                "SelectedReadAttachmentControlsNativeMetadata", "NoReadBufferRemainsUnavailableWithoutClientErrors",
                "IncompleteFramebufferRemainsUnavailableWithoutClientErrors", "MultisampleMetadataMatchesActualRenderbufferSamples",
            },
        }
    if target in IDENTITY_TARGETS:
        from scripts import verify_native_profile_identity_draft as identity
        if target == "identity-keys":
            return {**REQUIRED_TESTS,
                    "NativePrivacyKeyServiceTest": REQUIRED_TESTS["NativePrivacyKeyServiceTest"]
                    | set(identity.SERVICE_FIXTURES) | set(identity.MODE_FIXTURES),
                    "NativeProfileIdentityKeyTest": set(identity.DERIVATION_FIXTURES)}
        if target == "identity-contexts":
            return {"NativePrivacyBrowserContextTest": REQUIRED_CONTEXT_TESTS["NativePrivacyBrowserContextTest"]
                    | set(identity.CONTEXT_FIXTURES) | set(identity.LAUNCH_FIXTURES)}
        if target == "identity-handoff":
            document, worker = identity.HANDOFF_FIXTURES.values()
            return {"DocumentLoaderTest/DocumentLoaderTest": {f"{case}/{index}" for case in document for index in range(4)},
                    "GlintWorkerSurfaceThreadTest": set(worker)}
        return {
            "GlintSurfacePolicyProducerTest": {
                "MissingAndUnreadyContextRejectsSnapshot", "ReadySnapshotUsesFourIndependentDomains",
                "ChangingReturnedSnapshotDoesNotChangeIdentity", "ShutdownRejectsSnapshot",
            } | set(identity.TRANSPORT_FIXTURES[identity.PRODUCER + "surface_policy_producer_unittest.cc"]),
            "GlintSurfacePolicyPreflightTest": {
                "ReturnsOwnedSnapshot", "RejectsEveryShortAndLongSeedBeforeCopy", "RejectsWrongVersionAndHugeEncoding",
                "ResolvesInheritedProvisionalOrigin", "RejectsWrongBrowserOriginAndReusedSurface",
                "WireRoundtripRetainsBinaryEncodingAndOwnedSeeds", "WireRejectsMalformedSeedAndWrongPartition",
                "WorkerDecoderPreservesExactOpaqueIdentity", "WorkerDecoderCannotReplaceNoncePartition",
                "BrowserOwnedWorkerPartitionMatchesFinalOrigin", "WirePartitionCannotDisagreeWithBinaryCommitment",
            } | set(identity.TRANSPORT_FIXTURES[identity.COMMON + "surface_policy_preflight_unittest.cc"]),
        }
    if target == "gpu-metadata-codec":
        return {"GlintReadbackMetadataTest": {
            "ByteColourRoundTripPreservesNativeDimensions", "NonByteAndMultisampleInformationIsNotFabricated",
            "UnavailableCannotBecomeReady", "TruncatedWireNeverReadsMissingFields",
            "ExtraFieldsAreNotSilentlyAccepted", "SchemaIsExact", "ReadyStatusIsExact",
            "DimensionsMustBePositive", "InvalidFormatIsNotGuessed", "NegativeSamplesAreRejected",
            "ByteColourClassificationIsAnExactBoolean", "ByteColourClaimCannotPromoteFloatIntegerOrUnknownFormat",
            "ByteColourEligibilityPreservesAllSupportedFormats", "ProducerRejectsInvalidRepresentations",
        }}
    if target == "gpu-readback":
        return REQUIRED_GPU_READBACK_TESTS
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
           target: str = "keys", candidate_name: str | None = None,
           git_ssl_backend: str = "openssl", local_toolchain: bool = False) -> dict:
    required = required_tests(target)
    if sys.platform != "win32":
        raise ValueError("The owned-profile key loader verification currently supports Windows only")
    candidate = None if candidate_name is None else build.load_candidate(candidate_name)
    if type(local_toolchain) is not bool or (local_toolchain and candidate is None):
        raise ValueError("Local Windows toolchain verification requires an explicit candidate")
    lock = build.LOCK if candidate is None else candidate["lock"]
    if type(jobs) is not int or not 1 <= jobs <= min(4, lock["build_jobs"]):
        raise ValueError("Native privacy verification requires 1..4 jobs")
    if candidate is None:
        build.preflight(workspace)
    else:
        build.preflight(workspace, lock=lock)
    build.candidate_workspace(workspace, candidate)
    source = workspace / "chromium/src"
    if source != source.resolve() or not source.is_dir():
        raise ValueError("A canonical pinned Chromium checkout is required")
    if (not report.is_absolute() or report != report.resolve() or not report.parent.is_dir()
            or report.is_relative_to(source) or report.is_relative_to(ROOT)):
        raise ValueError("A canonical new report outside the source/application repositories is required")
    results = report.with_name(report.stem + "-tests.json")
    log_path = report.with_name(report.stem + "-build.log")
    if any(path.exists() or path.is_symlink() for path in (report, results, log_path)):
        raise ValueError("Refusing to overwrite native verification evidence")
    with build.workspace_lock(workspace):
        return _verify_locked(workspace, report, vs_installation=vs_installation, jobs=jobs, target=target,
                              required=required, candidate=candidate, lock=lock, git_ssl_backend=git_ssl_backend,
                              local_toolchain=local_toolchain)


def _verify_locked(workspace: Path, report: Path, *, vs_installation: Path | None, jobs: int,
                   target: str, required: dict, candidate: dict | None, lock: dict,
                   git_ssl_backend: str, local_toolchain: bool = False) -> dict:
    source = workspace / "chromium/src"
    output = source / "out/CamouFlowNative"
    results = report.with_name(report.stem + "-tests.json")
    log_path = report.with_name(report.stem + "-build.log")
    require_idle_builder()
    env = build.environment(workspace, git_ssl_backend=git_ssl_backend, local_toolchain=local_toolchain)
    env.update(GOMEMLIMIT="3GiB", PYTHONIOENCODING="utf-8")
    if vs_installation is not None:
        if vs_installation != vs_installation.resolve() or not vs_installation.is_dir():
            raise ValueError("Visual Studio installation must be an existing canonical directory")
        if local_toolchain and str(vs_installation) != env.get("vs2026_install"):
            raise ValueError("Visual Studio selection differs from the prepared local toolchain")
        env["vs2026_install"] = str(vs_installation)
    def source_state():
        build.candidate_workspace(workspace, candidate)
        if build.run(["git", "rev-parse", "HEAD"], source, env, capture=True) != lock["chromium_revision"]:
            raise ValueError("Chromium revision differs from the pinned build lock")
        if candidate is not None:
            build.require_stage(workspace / "chromium", "sync", candidate)
            build.require_stage(workspace / "chromium", "hooks", candidate)
            return build.candidate_source_patches(source, env, candidate)
        build.require_stage(workspace / "chromium", "sync")
        build.require_stage(workspace / "chromium", "hooks")
        return build.source_patches(source, env) + build.v8_source_patches(source, env)

    patches = source_state()
    required_patches = {"0015-native-browser-context-key-ownership.patch", "0016-native-private-key-readiness.patch"}
    if target == "font-rasterization":
        required_patches.add("0062-native-windows-font-rasterization.patch")
    if target in IDENTITY_TARGETS:
        required_patches.update({"0049-native-profile-identity-derivation.patch",
                                 "0050-native-immutable-fingerprint-mode.patch",
                                 "0051-native-identity-context-tests.patch",
                                 "0052-native-surface-identity-v3-transport.patch",
                                 "0053-native-identity-handoff-tests.patch",
                                 "0054-native-profile-identity-launch.patch"})
    if target == "identity-handoff":
        from scripts.verify_native_profile_identity_draft import require_document_identity_parameters
        require_document_identity_parameters((source / "third_party/blink/renderer/core/loader/document_loader_test.cc").read_text(encoding="utf-8-sig"))
    if (any(item["name"] == "0032-native-document-surface-policy.patch" for item in patches)
            and target in {"contexts", "delivery", "document-navigation", "surface-navigation", "window-transport", "worker-surfaces"}):
        required_patches.add("0042-native-initial-policy-fixture-scheme-lifetime.patch")
    if target in {"contexts", "delivery"}:
        required_patches.add("0017-native-browser-context-tests.patch")
    if target == "contexts":
        required_patches.add("0032-native-document-surface-policy.patch")
    if target in {"surface-navigation", "window-transport"}:
        required_patches.update({"0031-native-worker-surface-policy.patch", "0032-native-document-surface-policy.patch",
                                 "0041-native-child-transport-fixture-interface.patch"})
    if target == "surface-navigation":
        required_patches.update({"0039-native-document-ready-commit-cancellation.patch",
                                 "0040-native-ready-commit-observer-lifetime.patch",
                                 "0043-native-surface-navigation-throttle-registration.patch",
                                 "0044-native-inline-navigation-rejection-fixture.patch",
                                 "0045-native-navigation-observer-fixture-lifetime.patch"})
    if target == "worker-surfaces":
        required_patches.update({"0017-native-browser-context-tests.patch",
                                 "0018-native-document-policy-delivery.patch",
                                 "0019-native-worker-policy-delivery.patch",
                                 "0020-native-worker-policy-consumer.patch",
                                 "0031-native-worker-surface-policy.patch",
                                 "0036-native-worker-complete-surface-type.patch"})
    if target in {"gpu-pack-copy", "gpu-readback"}:
        required_patches.add("0034-native-gpu-metadata-minimization.patch")
    if target == "gpu-readback":
        required_patches.update({"0046-native-webgl-bounded-readback.patch",
                                 "0047-native-webgl-clipped-publication.patch",
                                 "0048-native-readback-fixture-result-api.patch"})
    if target == "gpu-metadata":
        required_patches.update({"0055-native-gpu-readback-metadata-transport.patch",
                                 "0056-native-gpu-metadata-protocol-tests.patch",
                                 "0058-native-gpu-passthrough-attachment-tests.patch"})
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
    scope = ("Windows font policy parsing/field-preservation units; not renderer startup, visual output or capability admission"
             if target == "font-rasterization" else
             "Selected identity and legacy policy units; not an enabled browser identity or capability admission"
             if target in IDENTITY_TARGETS else
             "Chromium GPU codec and passthrough command/attachment units; not validating decoder, WebGPU or browser readback admission"
             if target == "gpu-metadata" else
             "Surface NavigationSimulator/readiness units; not actual Blink or browser admission"
             if target == "surface-navigation" else
             "Canvas and surface worker Mojo endpoints/bootstrap units; not worker-host startup, first-script delivery or admission"
             if target == "worker-surfaces" else
             "Window readiness and authenticated child RFH transport units; not actual renderer IPC or admission"
             if target == "window-transport" else
             "Native RGBA8 pack-copy/region arithmetic units; not GPU/driver readback or admission"
             if target in {"gpu-pack-copy", "gpu-readback"} else
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
    build_target = ("gfx_unittests" if target == "font-rasterization" else
                    "gpu_unittests" if target == "gpu-metadata" else
                    "blink_unittests" if target in {"worker-handoff", "gpu-pack-copy", "gpu-readback", "identity-handoff"} else
                    "content_unittests" if target in {"contexts", "delivery", "document-navigation", "surface-navigation", "window-transport", "worker-surfaces", "identity-contexts", "identity-transport"} else "camouflow_native_privacy_unittests")
    proof = {"passed": False, "scope": scope, "target": target,
             **({"local_windows_toolchain_sha256": env["GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256"]}
                if local_toolchain else {}),
             "jobs": jobs, "patches": patches, "results": str(results), "log": str(log_path),
             "source_chromium_revision": lock["chromium_revision"], "browser_runtime_verified": False,
             "privacy_admitted": False,
             **({"candidate": candidate["name"], "candidate_manifest_sha256": candidate["manifest_sha256"]}
                if candidate is not None else {})}
    with log_path.open("x", encoding="utf-8", newline="\n") as log:
        try:
            build.check_patch_dependencies(source, env)
            subprocess.run(build.depot_command("autoninja", workspace) +
                           ["-C", "out/CamouFlowNative", "-j", str(jobs), build_target],
                           cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            executable = output / (build_target + ".exe")
            test_filter = ":".join(f"{suite}.{case}" for suite, cases in required.items() for case in sorted(cases))
            subprocess.run([str(executable), "--gtest_filter=" + test_filter,
                            "--single-process-tests", "--gtest_output=json:" + str(results)],
                           cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            validate_results(json.loads(results.read_text(encoding="utf-8-sig")), target=target)
            with executable.open("rb") as stream:
                test_checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        except (ValueError, OSError, subprocess.SubprocessError, NativeRuntimeError) as error:
            proof["error"] = str(error)
            log.write(f"\nVerification failed: {error}\n")
        finally:
            try:
                if local_toolchain and (build.local_windows_toolchain(workspace)["GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256"]
                                       != env["GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256"]):
                    raise ValueError("Local Windows toolchain changed during native test compilation")
                if delivery_sources is not None and require_delivery_sources(source) != delivery_sources:
                    raise ValueError("Delivery source inputs changed during verification")
                if (measure_runtime_core(output / "chrome.exe") != core
                        or (output / "args.gn").read_bytes() != arguments
                        or (output / "camouflow-build.json").read_bytes() != receipt
                        or source_state() != patches):
                    raise ValueError("Verification changed baseline browser code, receipt or source inputs")
                proof["postguards_passed"] = True
            except (ValueError, OSError, subprocess.SubprocessError, NativeRuntimeError) as error:
                proof["postguards_passed"] = False
                proof["postguard_error"] = str(error)
                proof.setdefault("error", str(error))
                log.write(f"\nPost-verification guard failed: {error}\n")
        if "error" not in proof:
            proof.update(passed=True, tests=sum(map(len, required.values())),
                         test_binary_sha256=test_checksum,
                         baseline_browser_code_unchanged=True, baseline_runtime_core_sha256_measured=core,
                         args_sha256=hashlib.sha256(arguments).hexdigest(),
                         browser_receipt_sha256=hashlib.sha256(receipt).hexdigest())
            if delivery_sources is not None:
                proof["delivery_source_sha256"] = delivery_sources
    with report.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(proof, stream, indent=2)
    return proof


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--vs-installation", type=Path)
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=4)
    parser.add_argument("--candidate", choices=("upstream-156",), help="Explicit candidate source/manifest; not runtime admission")
    parser.add_argument("--git-ssl-backend", choices=("openssl", "schannel"), default="openssl")
    parser.add_argument("--local-windows-toolchain", action="store_true")
    parser.add_argument("--target", choices=("keys", "contexts", "delivery", "worker-handoff", "document-partition", "document-navigation", *NEW_TARGETS, *IDENTITY_TARGETS), default="keys")
    args = parser.parse_args()
    try:
        report = verify(args.workspace, args.report, vs_installation=args.vs_installation, jobs=args.jobs, target=args.target,
                        candidate_name=args.candidate, git_ssl_backend=args.git_ssl_backend,
                        local_toolchain=args.local_windows_toolchain)
    except (ValueError, OSError, subprocess.SubprocessError, NativeRuntimeError) as error:
        print(f"Native privacy verification failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"passed": report["passed"], "report": str(args.report)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
