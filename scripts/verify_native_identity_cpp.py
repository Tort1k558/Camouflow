"""Check identity candidates with real target flags; never runtime admission."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from scripts.verify_native_document_drafts import digest
from scripts.verify_native_gpu_cpp import syntax_flags
from scripts.verify_native_runtime import measure_runtime_core

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "content/browser/camouflow_native/"
TARGETS = {
    **{PREFIX + name: "content/browser/camouflow_native_privacy" for name in (
        "privacy_key_derivation.cc", "privacy_profile_key.cc", "privacy_key_service.cc")},
    PREFIX + "privacy_context.cc": "content/browser/browser",
    **{PREFIX + name: "content/browser/camouflow_native_privacy_unittests" for name in (
        "privacy_key_derivation_unittest.cc", "privacy_key_service_unittest.cc")},
    PREFIX + "privacy_context_unittest.cc": "content/test/content_unittests",
    PREFIX + "glint/surface_policy_producer.cc": "content/browser/browser",
    PREFIX + "glint/surface_policy_producer_unittest.cc": "content/test/content_unittests",
    "third_party/blink/public/common/native_privacy/glint/surface_policy_preflight_unittest.cc": "content/test/content_unittests",
    **{name: "third_party/blink/renderer/core/unit_tests" for name in (
        "third_party/blink/renderer/core/loader/document_loader_test.cc",
        "third_party/blink/renderer/core/workers/worker_thread_test.cc")},
    **{name: "chrome/browser/browser" for name in (
        "chrome/browser/profiles/profile_impl.cc", "chrome/browser/profiles/off_the_record_profile_impl.cc")},
    PREFIX + "privacy_worker_service.cc": "content/browser/browser",
    "content/renderer/worker/privacy_worker_bootstrap.cc": "content/renderer/renderer",
    "content/renderer/render_frame_impl.cc": "content/renderer/renderer",
    **{name: "third_party/blink/renderer/core/core" for name in (
        "third_party/blink/renderer/core/loader/document_loader.cc",
        "third_party/blink/renderer/core/workers/worker_thread.cc")},
    "third_party/blink/renderer/modules/service_worker/service_worker_global_scope.cc": "third_party/blink/renderer/modules/service_worker/service_worker",
}
GENERATED_TARGETS = {
    "third_party/blink/public/mojom/native_privacy/native_privacy_surface_policy.mojom.cc": "third_party/blink/public/mojom/mojom_platform",
    "third_party/blink/public/mojom/native_privacy/native_privacy_surface_policy.mojom-shared.cc": "third_party/blink/public/mojom/mojom_platform_shared_cpp_sources",
}


def source_paths(source: Path) -> set[str]:
    paths = set(TARGETS)
    for directory in ("content/browser/camouflow_native/glint",
                      "third_party/blink/public/common/native_privacy/glint"):
        paths.update(path.relative_to(source).as_posix() for path in (source / directory).glob("*.h"))
    return paths


def verify_cpp(source: Path, overlay: Path, log: Path, env: dict) -> dict:
    if sys.platform != "win32":
        raise ValueError("Identity C++ checking currently supports Windows only")
    output = source / "out/CamouFlowNative"
    compiler = source / "third_party/llvm-build/Release+Asserts/bin/clang-cl.exe"
    toolchain = output / "toolchain.ninja"
    targets = TARGETS | GENERATED_TARGETS
    inputs = {compiler, toolchain, Path(__file__), ROOT / "scripts/verify_native_gpu_cpp.py"}
    inputs.update(output / "obj" / (target + ".ninja") for target in targets.values())
    if any(path != path.resolve() or not path.is_file() for path in inputs):
        raise ValueError("Canonical compiler and actual generated target files are required")
    if log.exists() or log.is_symlink():
        raise ValueError("Refusing to overwrite identity C++ evidence")
    before = {str(path): digest(path) for path in inputs}
    core = measure_runtime_core(output / "chrome.exe")
    arguments = digest(output / "args.gn")
    checks = overlay / "cpp-checks"
    checks.mkdir()
    generated = checks / "gen"
    for original in (overlay / "bindings-gen").rglob("*"):
        if original.is_file():
            destination = generated / original.relative_to(overlay / "bindings-gen")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(original.read_bytes())
    candidates = {relative: (generated if relative in GENERATED_TARGETS else overlay) / relative for relative in targets}
    if any(path != path.resolve() or not path.is_file() for path in candidates.values()):
        raise ValueError("Identity candidate source or fresh generated implementation is missing")
    candidate_hashes = {relative: digest(path) for relative, path in candidates.items()}
    units = {}
    with log.open("x", encoding="utf-8") as stream:
        for index, (relative, target) in enumerate(targets.items()):
            flags = syntax_flags((output / "obj" / (target + ".ninja")).read_text(encoding="utf-8-sig"),
                                 toolchain.read_text(encoding="utf-8-sig"), relative,
                                 generated=relative in GENERATED_TARGETS)
            response = checks / f"unit-{index}.rsp"
            response.write_text(f'/nologo -I"{generated}" -I"{overlay}" {flags} '
                                f'-fcrash-diagnostics-dir="{checks}" /clang:-fsyntax-only /TP '
                                f'"{candidates[relative]}"\n', encoding="utf-8", newline="\n")
            stream.write("\n=== " + relative + " ===\n")
            stream.flush()
            try:
                result = subprocess.run([str(compiler), "@" + str(response)], cwd=output, env=env,
                                        stdout=stream, stderr=subprocess.STDOUT, timeout=180, check=False)
                units[relative] = {"exit_code": result.returncode, "response_sha256": digest(response)}
            except subprocess.TimeoutExpired:
                units[relative] = {"exit_code": None, "error": "C++ checker timed out", "response_sha256": digest(response)}
            if units[relative]["exit_code"] != 0:
                break
    unchanged = (before == {str(path): digest(path) for path in inputs}
                 and candidate_hashes == {relative: digest(path) for relative, path in candidates.items()}
                 and measure_runtime_core(output / "chrome.exe") == core
                 and digest(output / "args.gn") == arguments)
    return {"passed": unchanged and len(units) == len(targets) and all(unit["exit_code"] == 0 for unit in units.values()),
            "compiled": False, "privacy_admitted": False,
            "scope": "Actual target C++ parsing/type checks; not optimizer, linker, fixture or browser execution",
            "units": units, "inputs": before, "candidate_sources": candidate_hashes,
            "active_core_and_inputs_unchanged": unchanged, "baseline_runtime_core_sha256": core}
