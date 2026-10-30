"""Prepare an unselected, hash-pinned Playwright copy; never modify an installation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "native/drafts/environment/playwright-driver-stage.json"
RECEIPT = "glint-driver-stage.json"
BUNDLE = "driver/package/lib/coreBundle.js"
NODE = "driver/node.exe"
LEGAL_FILES = ("driver/package/LICENSE", "driver/package/NOTICE", "driver/package/ThirdPartyNotices.txt")
IGNORED = frozenset({"__pycache__", ".local-browsers", ".git"})
MAX_FILES = 20000
MAX_BYTES = 512 * 1024 * 1024


class DriverStageError(ValueError):
    pass


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_metadata(path: Path, limit: int) -> bytes:
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise DriverStageError("Driver metadata is too large")
    return raw


def inventory(directory: Path, *, source: bool = False) -> dict[str, str]:
    if directory.is_symlink() or directory.is_junction() or not directory.is_dir():
        raise DriverStageError("Driver package must be a regular directory")
    result = {}
    total = 0
    for parent, directories, files in os.walk(directory, followlinks=False):
        parent = Path(parent)
        for name in directories + files:
            path = parent / name
            if path.is_symlink() or path.is_junction():
                raise DriverStageError("Linked driver assets are not allowed")
        if not source and any(name in IGNORED for name in directories):
            raise DriverStageError("Source caches are not allowed in a staged payload")
        directories[:] = sorted(name for name in directories if not source or name not in IGNORED)
        for name in sorted(files):
            if source and name.endswith((".pyc", ".pyo")):
                continue
            lower_name = name.casefold()
            if lower_name == ".env" or lower_name.startswith(".env.") or lower_name.endswith(".env"):
                raise DriverStageError("Private environment files are not driver assets")
            path = parent / name
            if not path.is_file():
                raise DriverStageError("Driver assets must be regular files")
            total += path.stat().st_size
            if total > MAX_BYTES or len(result) >= MAX_FILES:
                raise DriverStageError("Driver package exceeds staging limits")
            result[path.relative_to(directory).as_posix()] = digest(path)
    return dict(sorted(result.items()))


def load_manifest(path: Path) -> tuple[dict, Path]:
    raw = read_metadata(path, 65536)
    record = json.loads(raw)
    if (not isinstance(record, dict) or type(record.get("schema")) is not int or record["schema"] != 1
            or record.get("package") != "playwright" or record.get("version") != "1.60.0"
            or record.get("platform") != "win32"
            or record.get("optin_ignored_default") != "--disable-back-forward-cache"):
        raise DriverStageError("Unsupported driver staging manifest")
    if any(record.get(name) is not False for name in ("selected", "privacy_admitted", "production_admitted")):
        raise DriverStageError("Staging manifest cannot admit or select a release")
    for name in ("base_bundle_sha256", "bundle_sha256", "node_sha256", "patch_sha256"):
        if not isinstance(record.get(name), str) or not re.fullmatch(r"[0-9a-f]{64}", record[name]):
            raise DriverStageError("Invalid pinned driver digest")
    relative = record.get("patch")
    if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise DriverStageError("Invalid driver patch path")
    patch = path.parent / relative
    if patch.is_symlink() or patch.is_junction() or not patch.resolve().is_relative_to(path.parent.resolve()):
        raise DriverStageError("Driver patch must stay within its manifest directory")
    if not patch.is_file() or patch.stat().st_size > 1024 * 1024:
        raise DriverStageError("Driver patch must be a bounded regular file")
    if digest(patch) != record["patch_sha256"]:
        raise DriverStageError("Driver patch digest mismatch")
    overlay = record.get("python_overlay")
    if overlay is not None:
        if not isinstance(overlay, dict) or set(overlay) != {"file", "base_sha256", "sha256", "patch", "patch_sha256"} or overlay["file"] != "_impl/_page.py":
            raise DriverStageError("Unsupported Python driver overlay")
        for name in ("base_sha256", "sha256", "patch_sha256"):
            if not isinstance(overlay[name], str) or not re.fullmatch(r"[0-9a-f]{64}", overlay[name]):
                raise DriverStageError("Invalid Python driver overlay digest")
        python_patch = overlay["patch"]
        if not isinstance(python_patch, str) or Path(python_patch).name != python_patch:
            raise DriverStageError("Python driver patch must be a sibling filename")
        python_patch = path.parent / python_patch
        if python_patch.is_symlink() or not python_patch.is_file() or python_patch.stat().st_size > 1024 * 1024:
            raise DriverStageError("Python driver patch must be a bounded regular file")
        if digest(python_patch) != overlay["patch_sha256"]:
            raise DriverStageError("Python driver patch digest mismatch")
    return record, patch.resolve()


def validate_payload(directory: Path, assets: dict, manifest: dict, *, prepared: bool) -> None:
    for name in ("__init__.py", "async_api/__init__.py", "driver/package/package.json", BUNDLE, NODE, *LEGAL_FILES):
        if name not in assets:
            raise DriverStageError("Driver package is missing required API, code or license assets")
    metadata = json.loads(read_metadata(directory / "driver/package/package.json", 65536))
    expected_bundle = manifest["bundle_sha256" if prepared else "base_bundle_sha256"]
    if not isinstance(metadata, dict) or metadata.get("version") != manifest["version"] or assets[BUNDLE] != expected_bundle or assets[NODE] != manifest["node_sha256"]:
        raise DriverStageError("Driver version, bundle or Node executable differs from the pin")
    overlay = manifest.get("python_overlay")
    if overlay is not None and assets.get(overlay["file"]) != overlay["sha256" if prepared else "base_sha256"]:
        raise DriverStageError("Python driver module differs from the pin")
    if any((directory / name).stat().st_size == 0 for name in LEGAL_FILES):
        raise DriverStageError("Third-party license notices cannot be empty")


def verify(directory: Path, manifest_path: Path = DEFAULT_MANIFEST) -> dict:
    manifest, _ = load_manifest(manifest_path)
    if directory.is_symlink() or directory.is_junction():
        raise DriverStageError("Stage directory cannot be linked")
    if not directory.is_dir() or {path.name for path in directory.iterdir()} != {"playwright", RECEIPT}:
        raise DriverStageError("Stage must contain only its package and receipt")
    receipt_path = directory / RECEIPT
    if receipt_path.is_symlink() or not receipt_path.is_file() or receipt_path.stat().st_size > 8 * 1024 * 1024:
        raise DriverStageError("Missing or invalid staging receipt")
    receipt = json.loads(read_metadata(receipt_path, 8 * 1024 * 1024))
    if (not isinstance(receipt, dict) or type(receipt.get("schema")) is not int or receipt["schema"] != 1
            or receipt.get("state") != "staged-unselected"
            or receipt.get("manifest_sha256") != digest(manifest_path)
            or receipt.get("excluded_directories") != sorted(IGNORED)
            or any(receipt.get(name) is not False for name in ("selected", "privacy_admitted", "production_admitted", "runtime_admitted", "cryptographically_signed"))):
        raise DriverStageError("Staging receipt does not match the unselected manifest")
    assets = inventory(directory / "playwright")
    validate_payload(directory / "playwright", assets, manifest, prepared=True)
    if assets != receipt.get("assets") or type(receipt.get("file_count")) is not int or receipt["file_count"] != len(assets):
        raise DriverStageError("Staged asset inventory differs from its receipt")
    return receipt


def stage(source: Path, output: Path, manifest_path: Path = DEFAULT_MANIFEST) -> dict:
    manifest, patch = load_manifest(manifest_path)
    if source.is_symlink() or source.is_junction() or output.is_symlink() or output.is_junction():
        raise DriverStageError("Source and stage paths cannot be linked")
    source = source.resolve(strict=True)
    output = output.resolve()
    if output.is_relative_to(ROOT) or output.is_relative_to(source) or source.is_relative_to(output):
        raise DriverStageError("Stage must be outside the checkout and source installation")
    if output.exists():
        raise DriverStageError("Stage directory must be new")
    before = inventory(source, source=True)
    validate_payload(source, before, manifest, prepared=False)
    output.mkdir(exist_ok=False)
    package = output / "playwright"
    for name in before:
        target = package / name
        if not target.resolve().is_relative_to(output):
            raise DriverStageError("Driver copy escaped its new stage")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, target)
    if inventory(package) != before:
        raise DriverStageError("Driver copy differs from the measured source")
    patches = [patch]
    if manifest.get("python_overlay") is not None:
        patches.append(manifest_path.parent / manifest["python_overlay"]["patch"])
    for candidate in patches:
        for options in (("--check",), ("--whitespace=error",)):
            try:
                subprocess.run(["git", "-c", "core.autocrlf=false", "apply", *options, str(candidate.resolve())],
                               cwd=output, check=True, capture_output=True, timeout=30)
            except subprocess.CalledProcessError as error:
                raise DriverStageError("Pinned driver patch could not be applied") from error
    assets = inventory(package)
    validate_payload(package, assets, manifest, prepared=True)
    expected = prepared_assets(before, manifest)
    if assets != expected or inventory(source, source=True) != before:
        raise DriverStageError("Unexpected driver asset changes during staging")
    receipt = {
        "schema": 1, "state": "staged-unselected", "package": "playwright", "version": manifest["version"],
        "manifest_sha256": digest(manifest_path), "source_unchanged": True,
        "source_tree_sha256": hashlib.sha256(json.dumps(before, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "assets": assets, "file_count": len(assets), "selected": False, "privacy_admitted": False,
        "production_admitted": False, "runtime_admitted": False, "cryptographically_signed": False,
        "excluded_directories": sorted(IGNORED),
    }
    with (output / RECEIPT).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(receipt, indent=2) + "\n")
    return verify(output, manifest_path)


def prepared_assets(assets: dict, manifest: dict) -> dict:
    expected = {**assets, BUNDLE: manifest["bundle_sha256"]}
    overlay = manifest.get("python_overlay")
    if overlay is not None:
        expected[overlay["file"]] = overlay["sha256"]
    return expected


def bundle_datas(entries: list, source: Path, directory: Path, manifest_path: Path = DEFAULT_MANIFEST) -> list:
    """Override only the analyzed JS bundle; all Python/Node assets must match."""
    receipt = verify(directory, manifest_path)
    manifest, _ = load_manifest(manifest_path)
    assets = inventory(source, source=True)
    validate_payload(source, assets, manifest, prepared=False)
    tree = hashlib.sha256(json.dumps(assets, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if tree != receipt["source_tree_sha256"] or receipt["assets"] != prepared_assets(assets, manifest):
        raise DriverStageError("Analyzed Playwright installation differs from the stage source")
    target = "playwright/" + BUNDLE
    matches = [entry for entry in entries if entry[0].replace("\\", "/") == target]
    if len(matches) != 1 or len(matches[0]) != 3 or matches[0][2] != "DATA":
        raise DriverStageError("Expected one analyzed Playwright JS data asset")
    if Path(matches[0][1]).resolve() != (source / BUNDLE).resolve():
        raise DriverStageError("Analyzed Playwright bundle has an unexpected source")
    replacement = str((directory / "playwright" / BUNDLE).resolve())
    return [(entry[0], replacement, entry[2]) if entry[0].replace("\\", "/") == target else entry for entry in entries]


def bundle_pure(entries: list, source: Path, directory: Path, manifest_path: Path = DEFAULT_MANIFEST) -> list:
    """Replace the single measured Python module only when explicitly declared."""
    receipt = verify(directory, manifest_path)
    manifest, _ = load_manifest(manifest_path)
    overlay = manifest.get("python_overlay")
    if overlay is None:
        return list(entries)
    assets = inventory(source, source=True)
    validate_payload(source, assets, manifest, prepared=False)
    tree = hashlib.sha256(json.dumps(assets, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if tree != receipt["source_tree_sha256"] or receipt["assets"] != prepared_assets(assets, manifest):
        raise DriverStageError("Analyzed Playwright installation differs from the stage source")
    target = "playwright._impl._page"
    matches = [entry for entry in entries if entry[0] == target]
    if len(matches) != 1 or len(matches[0]) != 3 or matches[0][2] not in {"PYMODULE", "PYMODULE-1", "PYMODULE-2"}:
        raise DriverStageError("Expected one analyzed Playwright Python module")
    if Path(matches[0][1]).resolve() != (source / overlay["file"]).resolve():
        raise DriverStageError("Analyzed Playwright Python module has an unexpected source")
    replacement = str((directory / "playwright" / overlay["file"]).resolve())
    return [(entry[0], replacement, entry[2]) if entry[0] == target else entry for entry in entries]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("stage")
    prepare.add_argument("--source-package", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    check = commands.add_parser("verify")
    check.add_argument("--directory", type=Path, required=True)
    check.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    try:
        result = (stage(args.source_package, args.output, args.manifest) if args.command == "stage"
                  else verify(args.directory, args.manifest))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Driver stage failed: {error}\n")
    print(json.dumps({key: result[key] for key in ("state", "version", "file_count", "selected", "production_admitted")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
