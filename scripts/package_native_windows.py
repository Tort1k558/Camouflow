"""Package verified own-fork Windows files staged by Chromium's mini-installer."""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.native.distribution import (  # noqa: E402
    MAX_ARCHIVE_BYTES, MAX_FILES, MAX_UNPACKED_BYTES, checked_archive_name,
    host_architecture, sha256_file,
)
from scripts.native_build import LOCK, load_candidate  # noqa: E402
from scripts.verify_native_runtime import measure_runtime_core  # noqa: E402

RELEASE_VOLUME = "D:"
REQUIRED_RUNTIME_CHECKS = frozenset({
    "concurrent-profile-isolation", "cross-process-owner-exclusion",
    "navigation-tabs-fill-click-extract-screenshot", "mobile-web-viewport-dpr-touch",
    "native-document-worker-configuration-diagnostics",
    "cookie-localstorage-indexeddb-cache-serviceworker-restart",
    "configured-permissions-isolation-revocation-and-restart", "dead-owner-profile-lock-recovery",
    "browser-crash-restart-preserves-committed-storage", "authenticated-http-proxy-no-direct-dns-route",
    "existing-browser-interface-and-scenario-executor", "existing-recorder-capture-and-replay",
    "native-profile-backup-restore-storage-and-engine-isolation",
    "native-binary-headless-health-and-disposable-profile-cleanup",
    "cancelled-teardown-preserves-driver-stop-and-cross-process-profile-owner",
    "controller-kill-exits-observed-process-tree-and-restores-five-stores",
    "cancelled-driver-start-cleans-pending-operation-and-restarts-profile",
    "three-profile-restarts-isolate-crashes-five-stores-and-exit-owned-processes",
})


def read_record(path: Path) -> dict:
    if not path.is_file() or path != path.resolve() or path.stat().st_size > 1024 * 1024:
        raise ValueError("Missing or unsafe Native packaging record")
    record = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(record, dict):
        raise ValueError("Native packaging record must be an object")
    return record


def validate_build_receipt(receipt: dict, lock: dict, *, candidate: dict | None = None) -> None:
    if not isinstance(receipt, dict):
        raise ValueError("Native build receipt must be an object")
    for key, expected in {"schema": 1, "platform": "win32", "binary": "chrome.exe",
                          "native_version": lock["native_version"],
                          "chromium_revision": lock["chromium_revision"],
                          "depot_tools_revision": lock["depot_tools_revision"]}.items():
        if type(receipt.get(key)) is not type(expected) or receipt[key] != expected:
            raise ValueError("Native build receipt differs from the pinned build: " + key)
    if candidate is not None:
        manifest = candidate["manifest"]
        expected_patches = []
        for repository in (".", "v8"):
            for row in manifest["patches"]:
                if row.get("directory", ".") == repository:
                    expected_patches.append({"name": row["file"], "sha256": row["sha256"],
                        **({"repository": "v8", "revision": manifest["dependencies"]["v8"]["revision"]}
                           if repository == "v8" else {})})
        if (receipt.get("candidate_manifest_sha256") != candidate["manifest_sha256"]
                or receipt.get("patches") != expected_patches):
            raise ValueError("Native candidate receipt must bind the complete manifest and patch chain")


def package(build_output: Path, staged: Path, runtime_report: Path, destination: Path,
            *, candidate_name: str | None = None) -> dict:
    if sys.platform != "win32":
        raise ValueError("Own-fork packaging currently supports Windows only")
    candidate = None if candidate_name is None else load_candidate(candidate_name)
    lock = LOCK if candidate is None else candidate["lock"]
    for directory in (build_output, staged):
        if not directory.is_absolute() or not directory.is_dir() or directory != directory.resolve():
            raise ValueError("Packaging directories must be absolute and not linked")
    if (not destination.is_absolute() or destination != destination.resolve()
            or not destination.parent.is_dir() or destination.drive.upper() != RELEASE_VOLUME
            or destination.is_relative_to(build_output) or destination.is_relative_to(staged)
            or destination.is_relative_to(ROOT)):
        raise ValueError("Archive must stay in a separate existing directory on D:")
    if destination.exists():
        raise ValueError("Refusing to overwrite an existing Native archive")
    if build_output.name != "CamouFlowNative" or build_output.parent.name != "out":
        raise ValueError("Expected the owned out/CamouFlowNative build directory")
    receipt_path = build_output / "camouflow-build.json"
    args_path = build_output / "args.gn"
    input_hashes = {path: sha256_file(path) for path in (receipt_path, args_path, runtime_report)}
    receipt = read_record(receipt_path)
    report = read_record(runtime_report)
    validate_build_receipt(receipt, lock, candidate=candidate)
    if candidate is not None:
        manifest = candidate["manifest"]
        input_hashes[candidate["directory"] / "manifest.json"] = candidate["manifest_sha256"]
        input_hashes.update({candidate["directory"] / "patches" / row["file"]: row["sha256"]
                             for row in manifest["patches"]})
    binary_hash = sha256_file(build_output / "chrome.exe")
    if receipt.get("binary_sha256_measured") != binary_hash:
        raise ValueError("Native build executable changed after compilation")
    if receipt.get("args_sha256") != input_hashes[args_path]:
        raise ValueError("Native build arguments changed after compilation")
    core = measure_runtime_core(build_output / "chrome.exe")
    if receipt.get("runtime_core_sha256_measured") != core:
        raise ValueError("Native build receipt does not match the complete browser core")
    if (report.get("passed") is not True or report.get("platform") != "Windows"
            or report.get("version") != lock["chromium_version"]
            or report.get("binary_sha256_measured") != binary_hash
            or report.get("runtime_core_sha256_measured") != core
            or not isinstance(report.get("checks"), list)
            or any(not isinstance(check, str) for check in report["checks"])
            or not REQUIRED_RUNTIME_CHECKS.issubset(report["checks"])):
        raise ValueError("A passing runtime report for this exact Windows binary is required")
    files = []
    names = set()
    total = 0
    for path in sorted(staged.rglob("*")):
        if path != path.resolve():
            raise ValueError("Staged Native files must not contain links")
        if path.is_dir():
            continue
        relative = checked_archive_name(path.relative_to(staged).as_posix())
        name = relative.as_posix()
        if (not path.is_file() or name.casefold() in names or name.casefold() == "native-release.json"
                or path.suffix.lower() == ".pdb" or relative.parts[0].casefold() in {"obj", "gen", "pyproto", ".git"}):
            raise ValueError("Unsafe or colliding Native staged file")
        names.add(name.casefold())
        source_relative = Path(*relative.parts[1:]) if relative.parts[0] == lock["chromium_version"] else Path(*relative.parts)
        # chrome.release stages these two root-output assets in VisualElements.
        if relative.parts[0] == lock["chromium_version"] and source_relative.parts in {
                ("VisualElements", "Logo.png"), ("VisualElements", "SmallLogo.png")}:
            source_relative = Path(source_relative.name)
        source = build_output / source_relative
        checksum = sha256_file(path)
        if not source.is_file() or source != source.resolve() or checksum != sha256_file(source):
            raise ValueError("Staged file differs from the compiled output: " + name)
        input_hashes[source] = checksum
        total += path.stat().st_size
        if len(files) + 1 >= MAX_FILES or total > MAX_UNPACKED_BYTES:
            raise ValueError("Native staged files exceed installation limits")
        files.append((name, path, checksum))
    required = {"chrome.exe", lock["chromium_version"] + "/chrome.dll",
                lock["chromium_version"] + "/chrome_elf.dll", lock["chromium_version"] + "/locales/en-us.pak"}
    if not required.issubset(names):
        raise ValueError("Expected Chromium mini-installer Chrome-bin layout")
    for name, path in (("licenses/Chromium-LICENSE", build_output.parent.parent / "LICENSE"),
                       ("licenses/CamouFlow-LICENSE", ROOT / "LICENSE")):
        if (name.casefold() in names or not path.is_file() or path != path.resolve()
                or not 0 < path.stat().st_size <= 1024 * 1024):
            raise ValueError("Missing or unsafe source license notice")
        total += path.stat().st_size
        checksum = sha256_file(path)
        files.append((name, path, checksum))
        input_hashes[path] = checksum
        names.add(name.casefold())
    if len(files) + 1 > MAX_FILES:
        raise ValueError("Native staged files exceed installation limits")
    metadata = {"schema": 1, "native_version": lock["native_version"],
                "chromium_version": lock["chromium_version"], "platform": "win32",
                "architecture": host_architecture(), "build_kind": "chromium-fork",
                "executable": "chrome.exe", "executable_sha256": binary_hash,
                "build_receipt": receipt, "native_patch_runtime_verified": False,
                **({"candidate": candidate["name"], "candidate_manifest_sha256": candidate["manifest_sha256"]}
                   if candidate is not None else {}),
                "build_receipt_sha256": input_hashes[receipt_path],
                "runtime_report_sha256": input_hashes[runtime_report],
                "files_sha256": {name: checksum for name, _, checksum in files}}
    encoded = json.dumps(metadata, sort_keys=True, indent=2).encode("utf-8")
    if len(encoded) > 1024 * 1024 or total + len(encoded) > MAX_UNPACKED_BYTES:
        raise ValueError("Native release metadata exceeds installation limits")
    with tempfile.TemporaryDirectory(prefix="native-package-", dir=destination.parent) as owned:
        archive = Path(owned) / "bundle.tar.gz"
        with archive.open("xb") as stream, gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as bundle:
                for name, path, checksum in files:
                    info = tarfile.TarInfo(name)
                    info.size = path.stat().st_size
                    info.mode = 0o755 if path.suffix.lower() == ".exe" else 0o644
                    with path.open("rb") as content:
                        bundle.addfile(info, content)
                    if sha256_file(path) != checksum:
                        raise ValueError("Native staged file changed while packaging: " + name)
                info = tarfile.TarInfo("native-release.json")
                info.size, info.mode = len(encoded), 0o644
                bundle.addfile(info, io.BytesIO(encoded))
        if archive.stat().st_size > MAX_ARCHIVE_BYTES:
            raise ValueError("Native release archive exceeds installation limits")
        digest = sha256_file(archive)
        for path, checksum in input_hashes.items():
            if path != path.resolve() or not path.is_file() or sha256_file(path) != checksum:
                raise ValueError("Native packaging input changed while archiving: " + path.name)
        os.link(archive, destination)
    return {"archive": str(destination), "sha256": digest, "files": len(files),
            "native_patch_runtime_verified": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-output", required=True, type=Path)
    parser.add_argument("--staged", required=True, type=Path, help="Official mini-installer staged Chrome-bin directory")
    parser.add_argument("--runtime-report", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--candidate", choices=("upstream-156",))
    args = parser.parse_args()
    try:
        result = package(args.build_output, args.staged, args.runtime_report, args.archive, candidate_name=args.candidate)
    except Exception as error:
        print(f"Native packaging failed ({type(error).__name__}): {error}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
