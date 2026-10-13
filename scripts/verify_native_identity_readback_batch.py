"""Compose owned identity and GPU readback drafts without native compilation."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import native_build as build
from scripts import verify_native_gpu_transport_draft as gpu
from scripts import verify_native_profile_identity_draft as identity
from scripts.verify_native_document_drafts import digest, patch_paths

PATCHES = (identity.PATCH, identity.MODE_PATCH, identity.CONTEXT_PATCH,
           identity.TRANSPORT_PATCH, identity.HANDOFF_PATCH, identity.LAUNCH_PATCH,
           gpu.HALO_PATCH, gpu.CLIPPED_PATCH, gpu.PATCH, gpu.PROTOCOL_PATCH,
           gpu.ATTACHMENT_PATCH)


def _merge_composed_sources(first: dict, second: dict) -> dict:
    if any(first[name] != second[name] for name in first.keys() & second.keys()):
        raise ValueError("Draft batches require reviewed integration for overlapping source edits")
    return first | second


def verify(workspace: Path, report: Path, *, check_codegen: bool = False) -> dict:
    source = workspace / "chromium/src"
    if source != source.resolve() or not source.is_dir():
        raise ValueError("A canonical Chromium checkout is required")
    if (not report.is_absolute() or report != report.resolve() or not report.parent.is_dir()
            or report.exists() or report.is_symlink() or report.is_relative_to(source)
            or report.is_relative_to(ROOT)):
        raise ValueError("A new private report outside both repositories is required")
    validators = (Path(__file__), Path(identity.__file__), Path(gpu.__file__),
                  ROOT / "scripts/verify_native_halo_draft.py", Path(build.__file__))
    helpers = (*(gpu.DRAFTS / name for name in gpu.RAW),
               *(gpu.READBACK / name for name in gpu.CANONICAL | gpu.CLIPPED_CANONICAL))
    inputs = {str(path.relative_to(ROOT)): digest(path) for path in (*PATCHES, *validators, *helpers)}
    paths = set().union(*(patch_paths(path.read_text(encoding="utf-8-sig")) for path in PATCHES))
    if check_codegen:
        paths.update(path.relative_to(source).as_posix()
                     for path in (source / "gpu").rglob("*autogen*") if path.is_file())
        paths.update({".clang-format", "gpu/command_buffer/build_cmd_buffer_lib.py"})
    if any((source / name).resolve() != source / name for name in paths):
        raise ValueError("Batch baseline inputs must not follow links")
    before = {name: digest(source / name) for name in paths}
    env = build.environment(workspace)
    with tempfile.TemporaryDirectory(prefix="glint-identity-readback-", dir=report.parent) as private:
        private = Path(private)
        identity_proof = identity.verify(workspace, private / "identity.json",
                                         include_launch=True, check_bindings=check_codegen)
        gpu_proof = gpu.verify(workspace, private / "gpu.json", check_codegen=check_codegen)
        if identity_proof["registered_patches"] != gpu_proof["registered_patches"]:
            raise ValueError("Registered baseline changed between component validations")
        expected = _merge_composed_sources(identity_proof["composed_source"], gpu_proof["composed_source"])
        if set(expected) != paths:
            raise ValueError("Component proofs do not cover the exact combined source scope")
        if before != {name: digest(source / name) for name in paths}:
            raise ValueError("Active source changed before combined replay")
        overlay = private / "combined"
        overlay.mkdir()
        for name, existing in before.items():
            if existing is not None:
                target = overlay / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text((source / name).read_text(encoding="utf-8-sig"),
                                  encoding="utf-8", newline="\n")
        build.run(["git", "init", "-q"], overlay, env)
        build.run(["git", "config", "core.autocrlf", "false"], overlay, env)
        for patch in PATCHES:
            build.run(["git", "apply", "--check", str(patch)], overlay, env)
            build.run(["git", "apply", str(patch)], overlay, env)
        composed = {name: digest(overlay / name) for name in paths}
        if composed != expected:
            raise ValueError("Combined replay differs from reviewed component source")
    if before != {name: digest(source / name) for name in paths}:
        raise ValueError("Active source changed during combined replay")
    if inputs != {name: digest(ROOT / name) for name in inputs}:
        raise ValueError("Canonical batch or validator inputs changed during replay")
    result = {"passed": True, "compiled": False, "mode_enabled": False,
              "privacy_admitted": False, "active_source_unchanged": True,
              "patch_order": [str(path.relative_to(ROOT)) for path in PATCHES],
              "inputs": inputs, "composed_source": composed,
              "identity": identity_proof, "gpu": gpu_proof}
    with report.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--check-codegen", action="store_true",
                        help="Also check pinned isolated Mojo bindings and GPU command generation")
    args = parser.parse_args()
    result = verify(args.workspace, args.report, check_codegen=args.check_codegen)
    print(json.dumps({key: result[key] for key in ("passed", "compiled", "mode_enabled")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
