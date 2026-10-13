"""Replay the private GPU metadata command candidate; not a runtime gate."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import native_build as build
from scripts.verify_native_document_drafts import digest, patch_paths
from scripts.verify_native_halo_draft import (
    CANONICAL,
    CLIPPED_CANONICAL,
    CLIPPED_PATCH,
    restore_registered_baseline,
)
from scripts.verify_native_halo_draft import (
    DRAFTS as READBACK,
)
from scripts.verify_native_halo_draft import (
    PATCH as HALO_PATCH,
)

DRAFTS = ROOT / "native/drafts/gpu-transport"
PATCH = DRAFTS / "gpu_readback_metadata_candidate.patch"
PROTOCOL_PATCH = DRAFTS / "gpu_readback_metadata_protocol_tests.patch"
ATTACHMENT_PATCH = DRAFTS / "gpu_readback_metadata_attachment_tests.patch"
PASSTHROUGH_ATTACHMENT_PATCH = DRAFTS / "gpu_readback_metadata_passthrough_attachment_tests.patch"
PASSTHROUGH_ATTACHMENT_PATHS = {
    "gpu/command_buffer/service/gles2_cmd_decoder_passthrough_unittest_framebuffers.cc"}
ATTACHMENT_PATHS = {"gpu/command_buffer/service/gles2_cmd_decoder_unittest_framebuffers.cc"}
PROTOCOL_PATHS = {"gpu/command_buffer/service/" + name for name in (
    "gles2_cmd_decoder_unittest_extensions.cc",
    "gles2_cmd_decoder_passthrough_unittest_commands.cc")}
COMMON = "gpu/command_buffer/common/"
RAW = {name: COMMON + name for name in (
    "glint_readback_metadata.h", "glint_readback_metadata_unittest.cc")}
EXPECTED = {
    "gpu/BUILD.gn", "gpu/GLES2/gl2chromium_autogen.h",
    "gpu/command_buffer/build_gles2_cmd_buffer.py",
    "gpu/command_buffer/gles2_cmd_buffer_functions.txt",
    "gpu/config/gpu_finch_features.cc", "gpu/config/gpu_finch_features.h",
    COMMON + "BUILD.gn", COMMON + "gles2_cmd_format_autogen.h",
    COMMON + "gles2_cmd_format_test_autogen.h", COMMON + "gles2_cmd_ids_autogen.h",
    *RAW.values(),
    *("gpu/command_buffer/client/" + name for name in (
        "gles2_c_lib_autogen.h", "gles2_cmd_helper_autogen.h", "gles2_implementation.cc",
        "gles2_implementation_autogen.h", "gles2_interface_autogen.h",
        "gles2_interface_stub_autogen.h", "gles2_interface_stub_impl_autogen.h",
        "gles2_trace_implementation_autogen.h", "gles2_trace_implementation_impl_autogen.h")),
    *("gpu/command_buffer/service/" + name for name in (
        "gles2_cmd_decoder.cc", "gles2_cmd_decoder_passthrough.h",
        "gles2_cmd_decoder_passthrough_doers.cc", "gles2_cmd_decoder_passthrough_handlers.cc")),
    *("third_party/blink/renderer/modules/webgl/" + name for name in (
        "webgl_rendering_context_base.cc", "webgl2_rendering_context_base.cc")),
}


def command_ids(text: str) -> list[tuple[str, int]]:
    return [(name, int(number)) for name, number in re.findall(
        r"^\s*OP\((\w+)\).*?/\*\s*(\d+)\s*\*/", text, re.MULTILINE)]


def verify_codegen(overlay: Path, formatter: Path, env: dict) -> int:
    generated = {path.relative_to(overlay).as_posix(): digest(path)
                 for path in (overlay / "gpu").rglob("*autogen*") if path.is_file()}
    command = """
import importlib.util
import subprocess
import sys
from pathlib import Path
owned = Path(sys.argv[1])
formatter = Path(sys.argv[2])
sys.path.insert(0, str(owned / 'gpu/command_buffer'))
import build_cmd_buffer_lib
def format_owned(files, output_dir, chromium_root_dir):
    if Path(output_dir).resolve() != owned or Path(chromium_root_dir).resolve() != owned:
        raise ValueError('Generator output escaped the owned source tree')
    for name in files:
        path = owned / name
        if not path.resolve().is_relative_to(owned):
            raise ValueError('Formatter target escaped the owned source tree')
        subprocess.run([str(formatter), '-i', '-style=file:' + str(owned / '.clang-format'),
                        str(path)], check=True, timeout=60)
build_cmd_buffer_lib.Format = format_owned
spec = importlib.util.spec_from_file_location('owned_gpu_generator',
    owned / 'gpu/command_buffer/build_gles2_cmd_buffer.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
if module.main(['--output-dir', str(owned)]) != 0:
    raise SystemExit('Owned GPU source generation failed')
"""
    build.run([sys.executable, "-c", command, str(overlay), str(formatter)], overlay, env)
    if not generated or generated != {name: digest(overlay / name) for name in generated}:
        raise ValueError("Regenerated GPU source differs from the candidate")
    return len(generated)


def verify(workspace: Path, report: Path, *, check_codegen: bool = False, check_cpp: bool = False) -> dict:
    check_codegen = check_codegen or check_cpp
    source = workspace / "chromium/src"
    if source != source.resolve() or not source.is_dir():
        raise ValueError("A canonical Chromium checkout is required")
    if (not report.is_absolute() or report != report.resolve() or not report.parent.is_dir()
            or report.exists() or report.is_symlink() or report.is_relative_to(source)
            or report.is_relative_to(ROOT)):
        raise ValueError("A new canonical private report outside both repositories is required")
    env = build.environment(workspace)
    registered = build.source_patches(source, env) + build.v8_source_patches(source, env)
    if "0034-native-gpu-metadata-minimization.patch" not in {item["name"] for item in registered}:
        raise ValueError("The exact registered 001-034 baseline is required")
    patches = (HALO_PATCH, CLIPPED_PATCH, PATCH, PROTOCOL_PATCH, ATTACHMENT_PATCH,
               PASSTHROUGH_ATTACHMENT_PATCH)
    if patch_paths(PATCH.read_text(encoding="utf-8-sig")) != EXPECTED:
        raise ValueError("GPU transport source coverage differs from the reviewed candidate")
    if patch_paths(PROTOCOL_PATCH.read_text(encoding="utf-8-sig")) != PROTOCOL_PATHS:
        raise ValueError("GPU decoder fixture coverage differs from the reviewed candidate")
    if patch_paths(ATTACHMENT_PATCH.read_text(encoding="utf-8-sig")) != ATTACHMENT_PATHS:
        raise ValueError("GPU attachment fixture coverage differs from the reviewed candidate")
    if patch_paths(PASSTHROUGH_ATTACHMENT_PATCH.read_text(encoding="utf-8-sig")) != PASSTHROUGH_ATTACHMENT_PATHS:
        raise ValueError("GPU passthrough attachment fixture coverage differs from the reviewed candidate")
    paths = set().union(*(patch_paths(item.read_text(encoding="utf-8-sig")) for item in patches))
    formatter = source / "buildtools/win-format/clang-format.exe"
    if check_codegen:
        if not formatter.is_file() or formatter.resolve() != formatter:
            raise ValueError("The pinned checkout's Windows formatter is required")
        paths.update(path.relative_to(source).as_posix()
                     for path in (source / "gpu").rglob("*autogen*") if path.is_file())
        paths.update({".clang-format", "gpu/command_buffer/build_cmd_buffer_lib.py"})
    if any((source / name).resolve() != source / name for name in paths):
        raise ValueError("Source inputs must not follow links")
    before = {name: digest(source / name) for name in paths}
    inputs = {str(item.relative_to(ROOT)): digest(item) for item in (
        *patches, *(DRAFTS / name for name in RAW),
        *(READBACK / name for name in CANONICAL | CLIPPED_CANONICAL), Path(__file__))}
    if any(value is None for value in inputs.values()):
        raise ValueError("A canonical candidate input is missing")
    ids_path = COMMON + "gles2_cmd_ids_autogen.h"
    previous_ids = command_ids((source / ids_path).read_text(encoding="utf-8-sig"))
    formatter_hash = digest(formatter) if check_codegen else None
    generated_count = None
    cpp_proof = None
    cpp_log = Path(str(report) + ".cpp.log")
    if check_cpp and (cpp_log.exists() or cpp_log.is_symlink()):
        raise ValueError("Refusing to overwrite C++ verification evidence")
    if check_cpp:
        inputs["scripts/verify_native_gpu_cpp.py"] = digest(ROOT / "scripts/verify_native_gpu_cpp.py")
    with tempfile.TemporaryDirectory(prefix="glint-gpu-transport-replay-", dir=report.parent) as owned:
        overlay = Path(owned) / "chromium/src"
        overlay.mkdir(parents=True)
        for name in paths:
            if (source / name).is_file():
                target = overlay / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text((source / name).read_text(encoding="utf-8-sig"),
                                  encoding="utf-8", newline="\n")
        build.run(["git", "init", "-q"], overlay, env)
        build.run(["git", "config", "core.autocrlf", "false"], overlay, env)
        restore_registered_baseline(overlay, registered, env)
        for patch in patches:
            build.run(["git", "apply", "--check", str(patch)], overlay, env)
            build.run(["git", "apply", str(patch)], overlay, env)
        for directory, canonical in ((READBACK, CANONICAL | CLIPPED_CANONICAL), (DRAFTS, RAW)):
            for name, relative in canonical.items():
                if (overlay / relative).read_bytes() != (directory / name).read_bytes():
                    raise ValueError("Composed source differs from its canonical helper")
        current_ids = command_ids((overlay / ids_path).read_text(encoding="utf-8-sig"))
        if (len(previous_ids) != 324 or current_ids[:-1] != previous_ids
                or current_ids[-1] != ("GetGlintReadFramebufferMetadataCHROMIUM", 580)):
            raise ValueError("GPU command ABI changed outside the appended private command")
        if check_codegen:
            generated_count = verify_codegen(overlay, formatter, env)
        if check_cpp:
            from scripts.verify_native_gpu_cpp import verify_cpp
            cpp_proof = verify_cpp(source, overlay, cpp_log, env)
        composed = {name: digest(overlay / name) for name in paths}
    if before != {name: digest(source / name) for name in paths}:
        raise ValueError("Active Chromium inputs changed during candidate replay")
    if inputs != {name: digest(ROOT / name) for name in inputs}:
        raise ValueError("Canonical candidate inputs changed during replay")
    if check_codegen and formatter_hash != digest(formatter):
        raise ValueError("The pinned formatter changed during source generation")
    result = {"passed": True, "compiled": False, "privacy_admitted": False,
              "active_source_unchanged": True, "legacy_command_ids_preserved": len(previous_ids),
              "new_command_id": 580, "inputs": inputs, "composed_source": composed,
              "generated_headers_checked": generated_count, "formatter_sha256": formatter_hash,
              "cpp_syntax": cpp_proof,
              "registered_patches": registered}
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--check-codegen", action="store_true",
                        help="Regenerate GPU source in the isolated copy; no native compilation")
    parser.add_argument("--check-cpp", action="store_true",
                        help="Also type-check six C++ units with actual target flags; no linking or runtime")
    args = parser.parse_args()
    result = verify(args.workspace, args.report, check_codegen=args.check_codegen, check_cpp=args.check_cpp)
    print(json.dumps({key: result[key] for key in (
        "passed", "compiled", "privacy_admitted", "legacy_command_ids_preserved")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
