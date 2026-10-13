"""Replay the GPU/Audio/surface-policy batch without changing active build sources."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import native_build as build
from scripts.verify_native_document_drafts import digest, patch_paths
from scripts.verify_native_runtime import measure_runtime_core

DRAFTS = ROOT / "native/drafts"
PATCHES = ("gpu/gpu_metadata_minimization.patch", "audio/audio_helpers_integration.patch",
           "policy/surface_policy_helpers_integration.patch", "policy/surface_policy_wire_schema.patch",
           "policy/surface_worker_endpoint.patch", "policy/surface_worker_bootstrap.patch",
           "policy/worker_surface_handoff.patch", "policy/worker_surface_launchers.patch",
           "policy/document_surface_validation.patch", "policy/surface_bootstrap_switches.patch",
           "policy/document_surface_transport.patch", "policy/document_surface_handoff.patch",
           "policy/document_surface_handoff_tests.patch", "policy/document_surface_navigation_tests.patch",
           "policy/worker_surface_scope_state.patch", "canvas/core_helpers_integration.patch",
           "canvas/get_image_data_candidate_hook.patch", "canvas/html_export_candidate_hook.patch",
           "canvas/offscreen_candidate_hook.patch", "canvas/surface_seed_reader_tests.patch",
           "audio/offline_audio_surface_hook.patch", "audio/offline_audio_surface_guard_tests.patch",
           "policy/initial_main_surface_transport.patch", "policy/window_privacy_readiness.patch",
           "policy/startup_privacy_preload.patch", "policy/child_surface_transport.patch",
           "gpu/gpu_shader_metadata_minimization.patch", "gpu/rgba8_pack_copy_integration.patch")
CANONICAL = {
    **{"gpu/" + name: "third_party/blink/renderer/modules/webgl/glint/" + name for name in (
        "rgba8_pack_copy.h", "rgba8_pack_copy.cc", "rgba8_pack_copy_unittest.cc")},
    **{"canvas/" + name: "third_party/blink/renderer/core/html/canvas/glint/" + name for name in (
        "canvas_partition_seed.h", "canvas_partition_seed.cc", "canvas_readback_candidate.h",
        "canvas_readback_candidate.cc", "canvas_readback_copy.h", "canvas_readback_copy.cc",
        "canvas_readback_image.h", "canvas_readback_image.cc")},
    **{"audio/" + name: "third_party/blink/renderer/modules/webaudio/glint/" + name for name in (
        "offline_audio_candidate.h", "offline_audio_candidate.cc", "offline_audio_limits.h",
        "offline_audio_buffer.h", "offline_audio_buffer.cc", "offline_audio_candidate_unittest.cc",
        "offline_audio_buffer_unittest.cc")},
    **{"policy/" + name: "third_party/blink/public/common/native_privacy/glint/" + name for name in (
        "surface_policy.h", "surface_policy_validation.h", "surface_policy_validation_unittest.cc",
        "surface_policy_preflight.h", "surface_policy_preflight_unittest.cc", "surface_policy_wire.h",
        "worker_surface_policy.h", "worker_surface_policy_validation.h",
        "document_surface_policy.h", "document_surface_policy_unittest.cc",
        "initial_document_surface_policy.h", "initial_document_surface_policy_unittest.cc")},
    **{"policy/" + name: "content/browser/camouflow_native/glint/" + name for name in (
        "surface_policy_producer.h", "surface_policy_producer.cc", "surface_policy_producer_unittest.cc",
        "document_surface_commit_producer.h", "document_surface_commit_producer.cc",
        "document_surface_commit_producer_unittest.cc", "window_privacy_readiness.h",
        "window_privacy_readiness.cc", "window_privacy_readiness_unittest.cc",
        "child_surface_transport_unittest.cc")},
    "policy/native_privacy_surface_policy.mojom": "third_party/blink/public/mojom/native_privacy/native_privacy_surface_policy.mojom",
}
EXISTING_PATHS = {
    "chrome/browser/profiles/profile_impl.cc",
    "content/browser/camouflow_native/privacy_key_service.h",
    "content/browser/camouflow_native/privacy_key_service.cc",
    "content/browser/camouflow_native/privacy_context.cc",
    "content/browser/camouflow_native/privacy_context_unittest.cc",
    "content/public/browser/native_privacy_context.h",
    "content/common/frame.mojom",
    "content/test/test_render_frame.cc",
    "content/browser/renderer_host/render_view_host_impl.cc",
    "content/browser/renderer_host/render_frame_host_impl.h",
    "content/renderer/render_frame_impl.h",
    "third_party/blink/public/web/web_local_frame_client.h",
    "third_party/blink/renderer/core/frame/local_frame_client.h",
    "third_party/blink/renderer/core/frame/local_frame_client_impl.h",
    "third_party/blink/renderer/core/frame/local_frame_client_impl.cc",
    "third_party/blink/renderer/core/loader/frame_loader.cc",
    "third_party/blink/public/common/features.h", "third_party/blink/common/features.cc",
    "third_party/blink/renderer/modules/webgl/webgl_debug_renderer_info.cc",
    "third_party/blink/renderer/modules/webgl/webgl_debug_shaders.cc",
    "third_party/blink/renderer/modules/webgl/BUILD.gn",
    "third_party/blink/renderer/modules/webgpu/gpu_adapter.cc",
    "third_party/blink/renderer/modules/webaudio/BUILD.gn", "third_party/blink/renderer/modules/BUILD.gn",
    "content/browser/BUILD.gn", "content/test/BUILD.gn",
    "third_party/blink/public/mojom/BUILD.gn",
    "third_party/blink/public/mojom/native_privacy/native_privacy_document.mojom",
    "content/browser/camouflow_native/privacy_worker_service.h",
    "content/browser/camouflow_native/privacy_worker_service.cc",
    "content/browser/camouflow_native/privacy_worker_service_unittest.cc",
    "content/renderer/worker/privacy_worker_bootstrap_unittest.cc",
    "content/renderer/worker/privacy_worker_bootstrap.h",
    "content/renderer/worker/privacy_worker_bootstrap.cc",
    "third_party/blink/renderer/core/workers/global_scope_creation_params.h",
    "third_party/blink/renderer/core/workers/worker_global_scope.h",
    "third_party/blink/renderer/core/workers/worker_global_scope.cc",
    "third_party/blink/renderer/core/workers/worker_thread_test_helper.h",
    "third_party/blink/renderer/core/workers/worker_thread_test.cc",
    "third_party/blink/public/common/loader/worker_main_script_load_parameters.h",
    "third_party/blink/public/web/web_embedded_worker_start_data.h",
    "third_party/blink/renderer/core/workers/dedicated_worker.cc",
    "third_party/blink/renderer/core/exported/web_shared_worker_impl.cc",
    "third_party/blink/renderer/modules/exported/web_embedded_worker_impl.cc",
    "content/renderer/worker/dedicated_worker_host_factory_client.h",
    "content/renderer/worker/dedicated_worker_host_factory_client.cc",
    "content/renderer/service_worker/embedded_worker_instance_client_impl.h",
    "content/renderer/service_worker/embedded_worker_instance_client_impl.cc",
    "content/renderer/worker/embedded_shared_worker_stub.cc",
    "content/browser/renderer_host/render_process_host_impl.cc",
    "content/browser/camouflow_native/privacy_navigation_throttle.h",
    "content/browser/camouflow_native/privacy_navigation_throttle.cc",
    "content/browser/renderer_host/navigation_request.cc",
    "content/browser/renderer_host/navigation_entry_impl.cc",
    "content/browser/renderer_host/navigation_controller_impl.cc",
    "content/browser/renderer_host/render_frame_host_impl.cc",
    "content/renderer/render_frame_impl.cc",
    "third_party/blink/public/mojom/navigation/navigation_params.mojom",
    "third_party/blink/public/web/web_navigation_params.h",
    "third_party/blink/renderer/core/dom/document_init.h",
    "third_party/blink/renderer/core/dom/document_init.cc",
    "third_party/blink/renderer/core/dom/document.h",
    "third_party/blink/renderer/core/dom/document.cc",
    "third_party/blink/renderer/core/frame/local_dom_window.cc",
    "third_party/blink/renderer/core/loader/document_loader.h",
    "third_party/blink/renderer/core/loader/document_loader.cc",
    "third_party/blink/renderer/core/loader/document_loader_test.cc",
    "content/browser/camouflow_native/privacy_navigation_throttle_unittest.cc",
    "content/browser/camouflow_native/privacy_navigation_integration_unittest.cc",
    "third_party/blink/renderer/core/BUILD.gn",
    "third_party/blink/renderer/core/html/build.gni",
    "third_party/blink/renderer/modules/canvas/canvas2d/base_rendering_context_2d.cc",
    "third_party/blink/renderer/core/html/canvas/html_canvas_element.h",
    "third_party/blink/renderer/core/html/canvas/html_canvas_element.cc",
    "third_party/blink/renderer/core/offscreencanvas/offscreen_canvas.cc",
    "third_party/blink/renderer/modules/webaudio/offline_audio_context.h",
    "third_party/blink/renderer/modules/webaudio/offline_audio_context.cc",
    "third_party/blink/renderer/modules/webaudio/offline_audio_context_test.cc",
}


def validate_patch_paths(text: str) -> set[str]:
    paths = patch_paths(text)
    if not paths.issubset(EXISTING_PATHS | set(CANONICAL.values())):
        raise ValueError("Next-batch candidate contains unknown paths")
    return paths


def verify(workspace: Path, report: Path) -> dict:
    source = workspace / "chromium/src"
    if source != source.resolve() or not source.is_dir():
        raise ValueError("A canonical Chromium checkout is required")
    if (not report.is_absolute() or report != report.resolve() or not report.parent.is_dir()
            or report.is_relative_to(source) or report.is_relative_to(ROOT)):
        raise ValueError("A canonical report outside both repositories is required")
    if report.exists() or report.is_symlink():
        raise ValueError("Refusing to overwrite verification evidence")
    env = build.environment(workspace)
    revision = build.run(["git", "rev-parse", "HEAD"], source, env, capture=True)
    if revision != build.LOCK["chromium_revision"]:
        raise ValueError("Chromium revision differs from the pinned build lock")
    registered = build.source_patches(source, env) + build.v8_source_patches(source, env)
    inputs = {name: digest(DRAFTS / name) for name in (*PATCHES, *CANONICAL)}
    if any(value is None for value in inputs.values()):
        raise ValueError("A required public candidate file is missing")
    paths = sorted(set().union(*(validate_patch_paths((DRAFTS / name).read_text(encoding="utf-8-sig"))
                                for name in PATCHES)))
    if set(paths) != EXISTING_PATHS | set(CANONICAL.values()):
        raise ValueError("Next-batch candidate source coverage is incomplete")
    for relative in paths:
        if (source / relative).resolve() != source / relative:
            raise ValueError("Candidate inputs must not follow source symlinks")
    before = {relative: digest(source / relative) for relative in paths}
    output = source / "out/CamouFlowNative"
    core = measure_runtime_core(output / "chrome.exe")
    build_inputs = {name: digest(output / name) for name in ("args.gn", "camouflow-build.json")}
    verifier_hash = digest(Path(__file__))
    with tempfile.TemporaryDirectory(prefix="glint-next-batch-replay-", dir=report.parent) as owned:
        overlay = Path(owned).resolve()
        if not overlay.is_relative_to(report.parent):
            raise ValueError("Replay directory escaped its owned report directory")
        for relative in paths:
            original = source / relative
            if original.exists():
                if not original.is_file():
                    raise ValueError("Draft input must be an ordinary source file")
                destination = overlay / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(original.read_text(encoding="utf-8-sig"), encoding="utf-8", newline="\n")
        build.run(["git", "init", "-q"], overlay, env)
        build.run(["git", "config", "core.autocrlf", "false"], overlay, env)
        for name in PATCHES:
            build.run(["git", "apply", "--check", str(DRAFTS / name)], overlay, env)
            build.run(["git", "apply", str(DRAFTS / name)], overlay, env)
        for name, relative in CANONICAL.items():
            if (overlay / relative).read_text(encoding="utf-8-sig") != (DRAFTS / name).read_text(encoding="utf-8-sig"):
                raise ValueError(f"Composed source differs from canonical candidate: {name}")
        composed = {relative: digest(overlay / relative) for relative in paths}
    if before != {relative: digest(source / relative) for relative in paths}:
        raise ValueError("Active Chromium inputs changed during verification")
    if inputs != {name: digest(DRAFTS / name) for name in inputs} or digest(Path(__file__)) != verifier_hash:
        raise ValueError("Public verification inputs changed during replay")
    if build_inputs != {name: digest(output / name) for name in build_inputs}:
        raise ValueError("GN arguments or build receipt changed during replay")
    if measure_runtime_core(output / "chrome.exe") != core:
        raise ValueError("Browser runtime core changed during replay")
    result = {"passed": True, "privacy_admitted": False,
              "scope": "Ordered public next-batch source replay only; no compilation/link/runtime admission",
              "chromium_revision": revision, "registered_patches": registered,
              "candidate_sha256": inputs, "patch_order": list(PATCHES),
              "verifier_sha256": verifier_hash, "active_source_sha256": before,
              "composed_sha256": composed, "baseline_runtime_core_sha256": core,
              "build_inputs_sha256": build_inputs, "active_sources_unchanged": True}
    with report.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.workspace, args.report)
    print(json.dumps({"passed": result["passed"], "paths": len(result["composed_sha256"]),
                      "report": str(args.report), "scope": result["scope"]}))


if __name__ == "__main__":
    main()
