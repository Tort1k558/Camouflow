"""Replay stable profile-identity derivation without changing the active build."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import native_build as build
from scripts.verify_native_document_drafts import digest, patch_paths

PATCH = ROOT / "native/drafts/profile-identity/profile_identity_derivation_candidate.patch"
PREFIX = "content/browser/camouflow_native/"
PATHS = {PREFIX + name for name in (
    "privacy_partition.h", "privacy_key_derivation.h", "privacy_key_derivation.cc",
    "privacy_key_derivation_unittest.cc", "privacy_profile_key.h", "privacy_profile_key.cc",
    "privacy_key_service.h", "privacy_key_service.cc", "privacy_key_service_unittest.cc", "privacy_context.cc")}
PATHS.add("content/public/browser/native_privacy_context.h")


def reference_vectors() -> dict[str, str]:
    values = {}
    for surface in ("canvas", "webgl", "webgpu", "audio"):
        encoded = surface.encode("ascii")
        message = b"Glint/profile-identity/v1\0" + len(encoded).to_bytes(4, "big") + encoded
        values[surface] = hmac.new(bytes(range(32)), message, hashlib.sha256).hexdigest()
    return values


def verify(workspace: Path, report: Path) -> dict:
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
    if any((source / name).resolve() != source / name for name in PATHS):
        raise ValueError("Profile identity inputs must not follow links")
    before = {name: digest(source / name) for name in PATHS}
    if any(value is None for value in before.values()):
        raise ValueError("A profile identity baseline input is missing")
    inputs = {str(path.relative_to(ROOT)): digest(path) for path in (PATCH, Path(__file__))}
    vectors = reference_vectors()
    with tempfile.TemporaryDirectory(prefix="glint-profile-identity-replay-", dir=report.parent) as owned:
        overlay = Path(owned)
        for name in PATHS:
            target = overlay / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text((source / name).read_text(encoding="utf-8-sig"), encoding="utf-8", newline="\n")
        build.run(["git", "init", "-q"], overlay, env)
        build.run(["git", "config", "core.autocrlf", "false"], overlay, env)
        build.run(["git", "apply", "--check", str(PATCH)], overlay, env)
        build.run(["git", "apply", str(PATCH)], overlay, env)
        fixtures = (overlay / (PREFIX + "privacy_key_derivation_unittest.cc")).read_text(encoding="utf-8-sig")
        if any(value not in fixtures for value in vectors.values()):
            raise ValueError("Independent profile identity vectors differ from native fixtures")
        composed = {name: digest(overlay / name) for name in PATHS}
    if before != {name: digest(source / name) for name in PATHS}:
        raise ValueError("Active profile identity source changed during replay")
    if inputs != {name: digest(ROOT / name) for name in inputs}:
        raise ValueError("Canonical identity candidate inputs changed during replay")
    result = {"passed": True, "compiled": False, "mode_enabled": False, "privacy_admitted": False,
              "active_source_unchanged": True, "inputs": inputs, "composed_source": composed,
              "independent_reference_vectors": vectors, "registered_patches": registered}
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.workspace, args.report)
    print(json.dumps({key: result[key] for key in ("passed", "compiled", "mode_enabled")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
