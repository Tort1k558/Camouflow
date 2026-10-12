"""Replay document candidates without changing Chromium; not a runtime gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import native_build as build

DRAFTS = ROOT / "native/drafts/document_delivery"
PROTOTYPE = ROOT / "native/patches/0030-native-document-commit-prototype.patch"
PATCHES = (
    "document_canvas_seed_handoff.patch",
    "document_canvas_commit_transport.patch",
    "document_canvas_browser_producer.patch",
    "document_canvas_first_script_tests.patch",
    "document_navigation_integration_tests.patch",
    "document_storage_key_resolution.patch",
    "document_commit_rejection.patch",
)
CANONICAL = {
    **{name: "third_party/blink/public/common/native_privacy/" + name for name in (
        "document_canvas_commit.h", "document_canvas_policy_validation.h",
        "document_storage_key_resolution.h",
        "document_commit_preflight.h",
    )},
    **{name: "content/browser/camouflow_native/" + name for name in (
        "privacy_document_commit.h", "privacy_document_commit.cc",
        "privacy_document_commit_unittest.cc", "privacy_navigation_throttle.h",
        "privacy_navigation_throttle.cc", "privacy_navigation_throttle_unittest.cc",
        "privacy_navigation_integration_unittest.cc",
        "document_storage_key_resolution_unittest.cc",
        "document_commit_preflight_unittest.cc",
    )},
}


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def patch_paths(text: str) -> set[str]:
    paths = set()
    for line in text.splitlines():
        if line == "GIT binary patch" or line.startswith("Binary files "):
            raise ValueError("Binary document candidates are not supported")
        if line.startswith(("new file mode ", "new mode ")) and line.rsplit(" ", 1)[-1] != "100644":
            raise ValueError("Only ordinary source file modes are supported")
        if not line.startswith("diff --git "):
            continue
        left, separator, right = line.removeprefix("diff --git ").partition(" b/")
        if not separator or not left.startswith("a/") or left[2:] != right:
            raise ValueError("Only ordinary same-path source diffs are supported")
        path = PurePosixPath(right)
        if (path.is_absolute() or ".." in path.parts or path.as_posix() != right
                or "\\" in right or ":" in right or not right):
            raise ValueError("Unsafe draft patch path")
        paths.add(right)
    if not paths:
        raise ValueError("Draft patch contains no source paths")
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
    verifier_sha256 = digest(Path(__file__))
    revision = build.run(["git", "rev-parse", "HEAD"], source, env, capture=True)
    if revision != build.LOCK["chromium_revision"]:
        raise ValueError("Chromium revision differs from the pinned build lock")
    registered = build.source_patches(source, env) + build.v8_source_patches(source, env)
    prototype = next((item for item in registered if item["name"] == PROTOTYPE.name), None)
    if prototype is not None and digest(PROTOTYPE) != prototype["sha256"]:
        raise ValueError("Registered document prototype hash differs")
    inputs = {name: digest(DRAFTS / name) for name in (*PATCHES, *CANONICAL)}
    if any(value is None for value in inputs.values()):
        raise ValueError("A required public candidate file is missing")
    paths = sorted(set(CANONICAL.values()).union(
        *(patch_paths((DRAFTS / name).read_text(encoding="utf-8-sig")) for name in PATCHES)))
    if prototype is not None and not patch_paths(PROTOTYPE.read_text(encoding="utf-8-sig")).issubset(paths):
        raise ValueError("Registered document prototype contains unknown paths")
    for relative in paths:
        if (source / relative).resolve() != source / relative:
            raise ValueError("Candidate inputs must not follow source symlinks")
    before = {relative: digest(source / relative) for relative in paths}
    with tempfile.TemporaryDirectory(prefix="glint-document-replay-", dir=report.parent) as owned:
        overlay = Path(owned).resolve()
        if not overlay.is_relative_to(report.parent):
            raise ValueError("Replay directory escaped its owned report directory")
        for relative in paths:
            original = source / relative
            if original.exists():
                if not original.is_file():
                    raise ValueError("Draft input must be an ordinary source file")
                target = overlay / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(original.read_text(encoding="utf-8-sig"), encoding="utf-8", newline="\n")
        build.run(["git", "init", "-q"], overlay, env)
        if prototype is not None:
            build.run(["git", "apply", "--reverse", "--check", str(PROTOTYPE)], overlay, env)
            build.run(["git", "apply", "--reverse", str(PROTOTYPE)], overlay, env)
        for name in PATCHES:
            build.run(["git", "apply", "--check", str(DRAFTS / name)], overlay, env)
            build.run(["git", "apply", str(DRAFTS / name)], overlay, env)
        for name, relative in CANONICAL.items():
            if (overlay / relative).read_text(encoding="utf-8-sig") != (DRAFTS / name).read_text(encoding="utf-8-sig"):
                raise ValueError(f"Composed source differs from canonical candidate: {name}")
        composed = {relative: digest(overlay / relative) for relative in paths}
    if before != {relative: digest(source / relative) for relative in paths}:
        raise ValueError("Active Chromium inputs changed during verification")
    if inputs != {name: digest(DRAFTS / name) for name in inputs}:
        raise ValueError("Public candidate inputs changed during verification")
    if digest(Path(__file__)) != verifier_sha256:
        raise ValueError("Verifier changed during verification")
    if prototype is not None and digest(PROTOTYPE) != prototype["sha256"]:
        raise ValueError("Registered document prototype changed during verification")
    result = {"passed": True, "scope": "Ordered public draft replay only; no syntax/link/runtime/capability admission",
              "chromium_revision": revision, "registered_patches": registered,
              "candidate_sha256": inputs, "patch_order": list(PATCHES),
              "verifier_sha256": verifier_sha256,
              "active_source_sha256": before, "composed_sha256": composed,
              "prototype_unwrapped_in_owned_overlay": prototype,
              "active_sources_unchanged": True}
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
