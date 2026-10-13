"""Replay stable profile-identity derivation without changing the active build."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import native_build as build
from scripts.verify_native_document_drafts import digest, patch_paths

PATCH = ROOT / "native/drafts/profile-identity/profile_identity_derivation_candidate.patch"
MODE_PATCH = ROOT / "native/drafts/profile-identity/immutable_identity_mode_candidate.patch"
CONTEXT_PATCH = ROOT / "native/drafts/profile-identity/identity_context_tests_candidate.patch"
TRANSPORT_PATCH = ROOT / "native/drafts/profile-identity/identity_transport_v3_candidate.patch"
HANDOFF_PATCH = ROOT / "native/drafts/profile-identity/identity_handoff_tests_candidate.patch"
LAUNCH_PATCH = ROOT / "native/drafts/profile-identity/identity_launch_candidate.patch"
PREFIX = "content/browser/camouflow_native/"
DERIVATION_FIXTURES = (
    "CanvasMatchesIndependentVector", "WebglMatchesIndependentVector",
    "WebgpuMatchesIndependentVector", "AudioMatchesIndependentVector",
    "DifferentPartitionsShareIdentityNotPrivacy", "IndependentRootsAndSurfacesDoNotShareKeys",
    "UnsupportedSurfacesAreRejected",
)
SERVICE_FIXTURES = (
    "ProfileIdentityRequiresReadyAndRejectsShutdown",
    "ProfileIdentityFailureDoesNotRegenerateAKey",
    "ProfileIdentityEphemeralOwnersAreIndependent", "ProfileIdentityOwnedReloadPreservesTheKey",
)
PATHS = {PREFIX + name for name in (
    "privacy_partition.h", "privacy_key_derivation.h", "privacy_key_derivation.cc",
    "privacy_key_derivation_unittest.cc", "privacy_profile_key.h", "privacy_profile_key.cc",
    "privacy_key_service.h", "privacy_key_service.cc", "privacy_key_service_unittest.cc", "privacy_context.cc")}
PATHS.add("content/public/browser/native_privacy_context.h")
MODE_PATHS = {PREFIX + name for name in (
    "privacy_context.cc", "privacy_key_service.h", "privacy_key_service.cc",
    "privacy_key_service_unittest.cc")}
MODE_PATHS.add("content/public/browser/native_privacy_context.h")
MODE_FIXTURES = (
    "SelectedDefaultPreservesPartitionedPrivacy",
    "SelectedIdentityIsStableAcrossPartitions",
    "SelectedModeRejectsUntilReadyAndAfterShutdown",
    "InvalidModeRejectsBothInitializers",
    "InvalidModeDoesNotInstallAnOwnerService",
    "InstalledModeCannotBeReplaced",
    "SelectedIdentityReloadPreservesModeAndKey",
    "SelectedEphemeralIdentityOwnersStayIndependent",
)
CONTEXT_PATH = PREFIX + "privacy_context_unittest.cc"
CONTEXT_FIXTURES = (
    "SelectedModesBelongToTheirContextOwners",
    "SelectedIdentityRejectsLoadingAndContextShutdown",
    "InvalidSelectedModeDoesNotOwnTheContext",
    "SelectedModeCannotReplaceLoadingOwner",
    "SelectedIdentitySurvivesNewContextWithSameRoot",
    "SelectedIncognitoIdentityRejectsPersistentRoot",
    "SelectedNullAndFailedContextsNeverExposeMode",
)
COMMON = "third_party/blink/public/common/native_privacy/glint/"
PRODUCER = PREFIX + "glint/"
TRANSPORT_PATHS = {COMMON + name for name in (
    "surface_policy.h", "surface_policy_validation.h", "surface_policy_preflight.h",
    "surface_policy_wire.h", "surface_policy_preflight_unittest.cc")}
TRANSPORT_PATHS.update({PRODUCER + "surface_policy_producer.cc",
                        PRODUCER + "surface_policy_producer_unittest.cc",
                        "third_party/blink/public/mojom/native_privacy/native_privacy_surface_policy.mojom"})
TRANSPORT_FIXTURES = {
    PRODUCER + "surface_policy_producer_unittest.cc": (
        "IdentityModeSelectsStableSeedsWithExactPartition",
        "DefaultModeRetainsPartitionDependentSeeds"),
    COMMON + "surface_policy_preflight_unittest.cc": (
        "IdentityModeRoundtripSurvivesDocumentAndWorkerDecode",
        "UnknownModeAndLegacyVersionRejectBeforeCopy",
        "StableIdentityDoesNotAuthorizeAnotherPartition"),
}
HANDOFF_FIXTURES = {
    "third_party/blink/renderer/core/loader/document_loader_test.cc": (
        "GlintIdentityModeOwnedBeforeFirstInlineScript",
        "GlintIdentityModeCloneCannotMutateInstalledDocument",
        "GlintUnknownIdentityModeCannotRunInlineScript"),
    "third_party/blink/renderer/core/workers/worker_thread_test.cc": (
        "IdentityModeOwnedBeforeFirstEvaluation",
        "UnknownIdentityModeRejectsEvaluation",
        "StableIdentityModeCannotReplaceFinalOrigin"),
}
LAUNCH_PATHS = {"content/public/browser/native_privacy_context.h",
                PREFIX + "privacy_context.cc", CONTEXT_PATH,
                "chrome/browser/profiles/profile_impl.cc",
                "chrome/browser/profiles/off_the_record_profile_impl.cc"}
LAUNCH_FIXTURES = (
    "LaunchWithoutModePreservesCompatibilityDefault",
    "ExplicitLaunchModeRequiresEnabledKeyService",
    "IdentityLaunchRequiresBothFullSurfacePolicies",
    "IdentityLaunchRejectsEitherLegacyCanvasConflict",
)
PROMOTED_PATCHES = (
    ("0049-native-profile-identity-derivation.patch", PATCH),
    ("0050-native-immutable-fingerprint-mode.patch", MODE_PATCH),
    ("0051-native-identity-context-tests.patch", CONTEXT_PATCH),
    ("0052-native-surface-identity-v3-transport.patch", TRANSPORT_PATCH),
    ("0053-native-identity-handoff-tests.patch", HANDOFF_PATCH),
    ("0054-native-profile-identity-launch.patch", LAUNCH_PATCH),
)


def registered_identity_patches(registered: list[dict]) -> list[Path]:
    installed = {item["name"]: item["sha256"] for item in registered}
    patches = []
    for name, canonical in PROMOTED_PATCHES:
        if name not in installed:
            continue
        public = ROOT / "native/patches" / name
        if (digest(public) != installed[name] or digest(public) != digest(canonical)
                or public.is_symlink() or public != public.resolve()):
            raise ValueError("Registered identity patch differs from its canonical candidate")
        patches.append(public)
    return patches


def restore_registered_identity(overlay: Path, registered: list[dict], env: dict) -> None:
    for patch in reversed(registered_identity_patches(registered)):
        build.run(["git", "apply", "--reverse", "--check", str(patch)], overlay, env)
        build.run(["git", "apply", "--reverse", str(patch)], overlay, env)


def require_fixture_definitions(text: str, suite: str, names: tuple[str, ...], *,
                                macro: str = "TEST_F") -> None:
    if macro not in {"TEST", "TEST_F", "TEST_P"}:
        raise ValueError("Unsupported native test definition macro")
    pattern = re.compile(r"^" + macro + r"\s*\(\s*" + re.escape(suite)
                         + r"\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*\{", re.MULTILINE)
    observed = pattern.findall(text)
    if any(observed.count(name) != 1 for name in names):
        raise ValueError(f"Native fixture definitions differ for {suite}")


def require_document_identity_parameters(text: str) -> int:
    pattern = re.compile(
        r"^INSTANTIATE_TEST_SUITE_P\(\s*DocumentLoaderTest\s*,\s*DocumentLoaderTest\s*,"
        r"\s*testing::Values\(([^()]+)\)\s*\);", re.MULTILINE)
    matches = pattern.findall(text)
    expected = ("TestMode::kUnpartitionedStorageAndLinks",
                "TestMode::kUnpartitionedStorageParttionedWithSelfLinks",
                "TestMode::kPartitionedStorageUnpartitionedLinks",
                "TestMode::kPartitionedStorageAndLinksWithSelfLinks")
    if len(matches) != 1 or tuple(value.strip() for value in matches[0].split(",")) != expected:
        raise ValueError("Identity DocumentLoader parameter coverage changed")
    return len(expected)


def verify_bindings(source: Path, overlay: Path, env: dict) -> dict:
    output = source / "out/CamouFlowNative"
    schema = "third_party/blink/public/mojom/native_privacy/native_privacy_surface_policy.mojom"
    mapping = output / "gen/third_party/blink/public/mojom/mojom_core__type_mappings"
    parser = source / "mojo/public/tools/mojom/mojom_parser.py"
    generator = source / "mojo/public/tools/bindings/mojom_bindings_generator.py"
    inputs = {str(path): digest(path) for path in (mapping, parser, generator)}
    if any(value is None for value in inputs.values()):
        raise ValueError("Pinned parser, generator and existing build typemap are required")
    typemap = json.loads(mapping.read_text(encoding="utf-8-sig"))
    for language in typemap["_metadata"]["module_typemaps"]:
        typemap["_metadata"]["module_typemaps"][language] = []
    typemap_path = overlay / "single-module-typemap.json"
    typemap_path.write_text(json.dumps(typemap), encoding="utf-8")
    generated = overlay / "bindings-gen"
    build.run([sys.executable, str(parser), "--input-root", str(overlay),
               "--input-root", str(source), "--input-root", str(output / "gen"),
               "--output-root", str(generated), "--module-root", str(output / "gen"),
               "--mojoms", str(overlay / schema)], overlay, env)
    command = [sys.executable, str(generator), "--use_bundled_pylibs", "-o", str(generated),
               "generate", str(overlay / schema), "-d", str(overlay), "--generators", "c++",
               "--bytecode_path", str(output / "gen/mojo/public/tools/bindings"),
               "--typemap", str(typemap_path)]
    for options in (["--generate_non_variant_code"], [],
                    ["--generate_non_variant_code", "--generate_message_ids"]):
        build.run(command + options, overlay, env)
    header = (generated / (schema + ".h")).read_text(encoding="utf-8-sig")
    if not all(value in header for value in (
            "uint32_t identity_mode", "blink::StorageKey partition", "std::string partition_encoding",
            *("std::vector<uint8_t> " + surface + "_seed"
              for surface in ("canvas", "webgl", "webgpu", "audio")))):
        raise ValueError("Generated v3 policy binding types differ")
    if inputs != {name: digest(Path(name)) for name in inputs}:
        raise ValueError("Pinned binding inputs changed during generation")
    return {"passed": True, "compiled": False, "inputs": inputs,
            "generated": {path.relative_to(generated).as_posix(): digest(path)
                          for path in generated.rglob("*") if path.is_file()}}


def reference_vectors() -> dict[str, str]:
    values = {}
    for surface in ("canvas", "webgl", "webgpu", "audio"):
        encoded = surface.encode("ascii")
        message = b"Glint/profile-identity/v1\0" + len(encoded).to_bytes(4, "big") + encoded
        values[surface] = hmac.new(bytes(range(32)), message, hashlib.sha256).hexdigest()
    return values


def verify(workspace: Path, report: Path, *, include_mode: bool = False,
           include_transport: bool = False, check_bindings: bool = False,
           include_handoff: bool = False, include_launch: bool = False, check_cpp: bool = False) -> dict:
    include_launch = include_launch or check_cpp
    check_bindings = check_bindings or check_cpp
    include_handoff = include_handoff or include_launch
    include_transport = include_transport or check_bindings or include_handoff
    include_mode = include_mode or include_transport
    source = workspace / "chromium/src"
    if source != source.resolve() or not source.is_dir():
        raise ValueError("A canonical Chromium checkout is required")
    if (not report.is_absolute() or report != report.resolve() or not report.parent.is_dir()
            or report.exists() or report.is_symlink() or report.is_relative_to(source)
            or report.is_relative_to(ROOT)):
        raise ValueError("A new private report outside both repositories is required")
    env = build.environment(workspace)
    registered = build.source_patches(source, env) + build.v8_source_patches(source, env)
    if "0034-native-gpu-metadata-minimization.patch" not in {item["name"] for item in registered}:
        raise ValueError("The exact registered 001-034 baseline is required")
    if patch_paths(PATCH.read_text(encoding="utf-8-sig")) != PATHS:
        raise ValueError("Profile identity candidate source coverage differs")
    patches = [PATCH]
    paths = set(PATHS)
    if include_mode:
        if patch_paths(MODE_PATCH.read_text(encoding="utf-8-sig")) != MODE_PATHS:
            raise ValueError("Immutable mode candidate source coverage differs")
        if patch_paths(CONTEXT_PATCH.read_text(encoding="utf-8-sig")) != {CONTEXT_PATH}:
            raise ValueError("Context fixture candidate source coverage differs")
        patches.extend((MODE_PATCH, CONTEXT_PATCH))
        paths.add(CONTEXT_PATH)
    if include_transport:
        if patch_paths(TRANSPORT_PATCH.read_text(encoding="utf-8-sig")) != TRANSPORT_PATHS:
            raise ValueError("Identity transport candidate source coverage differs")
        patches.append(TRANSPORT_PATCH)
        paths.update(TRANSPORT_PATHS)
    if include_handoff:
        if patch_paths(HANDOFF_PATCH.read_text(encoding="utf-8-sig")) != set(HANDOFF_FIXTURES):
            raise ValueError("Identity handoff candidate source coverage differs")
        patches.append(HANDOFF_PATCH)
        paths.update(HANDOFF_FIXTURES)
    if include_launch:
        if patch_paths(LAUNCH_PATCH.read_text(encoding="utf-8-sig")) != LAUNCH_PATHS:
            raise ValueError("Identity launch candidate source coverage differs")
        patches.append(LAUNCH_PATCH)
        paths.update(LAUNCH_PATHS)
    if check_cpp:
        from scripts.verify_native_identity_cpp import source_paths
        paths.update(source_paths(source))
    promoted = registered_identity_patches(registered)
    for patch in promoted:
        paths.update(patch_paths(patch.read_text(encoding="utf-8-sig")))
    if any((source / name).resolve() != source / name for name in paths):
        raise ValueError("Profile identity inputs must not follow links")
    before = {name: digest(source / name) for name in paths}
    if any(value is None for value in before.values()):
        raise ValueError("A profile identity baseline input is missing")
    extra_candidates = [canonical for name, canonical in PROMOTED_PATCHES if any(path.name == name for path in promoted)]
    inputs = {str(path.relative_to(ROOT)): digest(path) for path in (*patches, *promoted, *extra_candidates, Path(__file__))}
    if check_cpp:
        inputs["scripts/verify_native_identity_cpp.py"] = digest(ROOT / "scripts/verify_native_identity_cpp.py")
        inputs["scripts/verify_native_gpu_cpp.py"] = digest(ROOT / "scripts/verify_native_gpu_cpp.py")
    vectors = reference_vectors()
    bindings = None
    cpp = None
    with tempfile.TemporaryDirectory(prefix="glint-profile-identity-replay-", dir=report.parent) as owned:
        overlay = Path(owned)
        for name in paths:
            target = overlay / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text((source / name).read_text(encoding="utf-8-sig"), encoding="utf-8", newline="\n")
        build.run(["git", "init", "-q"], overlay, env)
        build.run(["git", "config", "core.autocrlf", "false"], overlay, env)
        restore_registered_identity(overlay, registered, env)
        for patch in patches:
            build.run(["git", "apply", "--check", str(patch)], overlay, env)
            build.run(["git", "apply", str(patch)], overlay, env)
        fixtures = (overlay / (PREFIX + "privacy_key_derivation_unittest.cc")).read_text(encoding="utf-8-sig")
        if any(value not in fixtures for value in vectors.values()):
            raise ValueError("Independent profile identity vectors differ from native fixtures")
        require_fixture_definitions(fixtures, "NativeProfileIdentityKeyTest", DERIVATION_FIXTURES, macro="TEST")
        service_fixtures = (overlay / (PREFIX + "privacy_key_service_unittest.cc")).read_text(encoding="utf-8-sig")
        require_fixture_definitions(service_fixtures, "NativePrivacyKeyServiceTest", SERVICE_FIXTURES)
        fixture_count = len(DERIVATION_FIXTURES) + len(SERVICE_FIXTURES)
        parameter_expansion = 0
        if include_mode:
            require_fixture_definitions(service_fixtures, "NativePrivacyKeyServiceTest", MODE_FIXTURES)
            context_fixtures = (overlay / CONTEXT_PATH).read_text(encoding="utf-8-sig")
            require_fixture_definitions(context_fixtures, "NativePrivacyBrowserContextTest", CONTEXT_FIXTURES)
            fixture_count += len(MODE_FIXTURES) + len(CONTEXT_FIXTURES)
        if include_transport:
            for name, expected in TRANSPORT_FIXTURES.items():
                text = (overlay / name).read_text(encoding="utf-8-sig")
                suite = ("GlintSurfacePolicyProducerTest" if name.startswith(PRODUCER)
                         else "GlintSurfacePolicyPreflightTest")
                require_fixture_definitions(text, suite, expected)
                fixture_count += len(expected)
        if include_handoff:
            for name, expected in HANDOFF_FIXTURES.items():
                text = (overlay / name).read_text(encoding="utf-8-sig")
                document = name.endswith("document_loader_test.cc")
                require_fixture_definitions(text, "DocumentLoaderTest" if document else "GlintWorkerSurfaceThreadTest",
                                            expected, macro="TEST_P" if document else "TEST_F")
                if document:
                    parameter_expansion = len(expected) * (require_document_identity_parameters(text) - 1)
                fixture_count += len(expected)
        if include_launch:
            context_fixtures = (overlay / CONTEXT_PATH).read_text(encoding="utf-8-sig")
            require_fixture_definitions(context_fixtures, "NativePrivacyBrowserContextTest", LAUNCH_FIXTURES)
            fixture_count += len(LAUNCH_FIXTURES)
        if check_bindings:
            bindings = verify_bindings(source, overlay, env)
        if check_cpp:
            from scripts.verify_native_identity_cpp import verify_cpp
            cpp = verify_cpp(source, overlay, Path(str(report) + ".cpp.log"), env)
        composed = {name: digest(overlay / name) for name in paths}
    if before != {name: digest(source / name) for name in paths}:
        raise ValueError("Active profile identity source changed during replay")
    if inputs != {name: digest(ROOT / name) for name in inputs}:
        raise ValueError("Canonical identity candidate inputs changed during replay")
    result = {"passed": cpp is None or cpp["passed"], "compiled": False, "mode_enabled": False, "privacy_admitted": False,
              "immutable_mode_candidate_replayed": include_mode,
              "context_mode_fixtures_replayed": include_mode,
              "identity_transport_candidate_replayed": include_transport,
              "identity_handoff_fixtures_replayed": include_handoff,
              "identity_launch_candidate_replayed": include_launch,
              "native_fixture_definitions": fixture_count,
              "native_fixture_cases_expected": fixture_count + parameter_expansion,
              "native_fixture_cases_executed": False,
              "bindings": bindings,
              "cpp_syntax": cpp,
              "active_source_unchanged": True, "inputs": inputs, "composed_source": composed,
              "independent_reference_vectors": vectors, "registered_patches": registered}
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--include-mode", action="store_true",
                        help="Replay the dependent immutable browser-mode candidate as well")
    parser.add_argument("--include-transport", action="store_true",
                        help="Replay mode, context and v3 producer/transport candidates in order")
    parser.add_argument("--check-bindings", action="store_true",
                        help="Also generate isolated pinned Mojo C++ bindings; no native compilation")
    parser.add_argument("--include-handoff", action="store_true",
                        help="Also replay Blink mode handoff fixtures after the v3 candidate")
    parser.add_argument("--include-launch", action="store_true",
                        help="Also replay strict Chrome launch selection and all preceding candidates")
    parser.add_argument("--check-cpp", action="store_true",
                        help="Check all 22 actual target translation units with fresh v3 Mojo bindings; no execution")
    args = parser.parse_args()
    result = verify(args.workspace, args.report, include_mode=args.include_mode,
                    include_transport=args.include_transport, check_bindings=args.check_bindings,
                    include_handoff=args.include_handoff, include_launch=args.include_launch, check_cpp=args.check_cpp)
    print(json.dumps({key: result[key] for key in ("passed", "compiled", "mode_enabled")}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
