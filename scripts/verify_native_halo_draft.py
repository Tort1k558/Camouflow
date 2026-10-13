"""Replay the next halo candidate without changing the active 001-034 build."""

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

DRAFTS = ROOT / "native/drafts/next-readback"
PATCH = DRAFTS / "webgl_halo_readback_candidate.patch"
PREFIX = "third_party/blink/renderer/modules/webgl/glint/"
CANONICAL = {name: PREFIX + name for name in (
    "rgba8_readback_region.h", "rgba8_readback_region.cc", "rgba8_readback_region_unittest.cc")}
EXISTING = {"third_party/blink/renderer/modules/webgl/BUILD.gn", "third_party/blink/renderer/modules/BUILD.gn",
            "third_party/blink/renderer/modules/webgl/webgl_rendering_context_base.cc"}


def verify(workspace: Path, report: Path) -> dict:
    source = workspace / "chromium/src"
    if source != source.resolve() or not source.is_dir():
        raise ValueError("A canonical Chromium checkout is required")
    if (not report.is_absolute() or report != report.resolve() or not report.parent.is_dir()
            or report.exists() or report.is_symlink() or report.is_relative_to(source) or report.is_relative_to(ROOT)):
        raise ValueError("A new canonical private report outside both repositories is required")
    env = build.environment(workspace)
    registered = build.source_patches(source, env) + build.v8_source_patches(source, env)
    if "0034-native-gpu-metadata-minimization.patch" not in {item["name"] for item in registered}:
        raise ValueError("The exact registered 001-034 baseline is required")
    paths = EXISTING | set(CANONICAL.values())
    if patch_paths(PATCH.read_text(encoding="utf-8-sig")) != paths:
        raise ValueError("Halo candidate source coverage is incomplete or contains unknown paths")
    inputs = {name: digest(DRAFTS / name) for name in (*CANONICAL, PATCH.name)}
    verifier_hash = digest(Path(__file__))
    if any(value is None for value in inputs.values()):
        raise ValueError("A canonical halo input is missing")
    before = {name: digest(source / name) for name in paths}
    for name in paths:
        if (source / name).resolve() != source / name:
            raise ValueError("Halo inputs must not follow source links")
    with tempfile.TemporaryDirectory(prefix="glint-halo-replay-", dir=report.parent) as owned:
        overlay = Path(owned)
        for name in EXISTING:
            target = overlay / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text((source / name).read_text(encoding="utf-8-sig"), encoding="utf-8", newline="\n")
        build.run(["git", "init", "-q"], overlay, env)
        build.run(["git", "config", "core.autocrlf", "false"], overlay, env)
        build.run(["git", "apply", "--check", str(PATCH)], overlay, env)
        build.run(["git", "apply", str(PATCH)], overlay, env)
        for name, relative in CANONICAL.items():
            if (overlay / relative).read_bytes() != (DRAFTS / name).read_bytes():
                raise ValueError("Composed halo source differs from its canonical helper")
        composed = {name: digest(overlay / name) for name in paths}
    if (before != {name: digest(source / name) for name in paths}
            or inputs != {name: digest(DRAFTS / name) for name in inputs}
            or verifier_hash != digest(Path(__file__))):
        raise ValueError("Active or canonical source changed during halo replay")
    result = {"passed": True, "compiled": False, "privacy_admitted": False,
              "scope": __doc__, "registered_patches": registered, "candidate_sha256": inputs,
              "verifier_sha256": verifier_hash,
              "active_source_sha256": before, "composed_sha256": composed, "active_sources_unchanged": True}
    with report.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.workspace, args.report)
    print(json.dumps({"passed": result["passed"], "paths": len(result["composed_sha256"]), "compiled": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
