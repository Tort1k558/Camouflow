"""Replay prepared branding in an owned copy; never mutate Chromium sources."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.prepare_glint_branding import prepare


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(source: Path, patch: Path, output: Path) -> dict:
    source = source.resolve(strict=True)
    patch = patch.resolve(strict=True)
    if output != output.resolve() or output.exists() or output.is_symlink():
        raise ValueError("Branding evidence requires a new canonical output directory")
    if output.is_relative_to(source) or not patch.is_file():
        raise ValueError("Branding verification must stay outside Chromium sources")
    patch_bytes = patch.read_bytes()
    output.mkdir(parents=True)
    prepared = prepare(source, output / "regenerated.patch")
    records = prepared["assets"]
    paths = [record["path"] for record in records]
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate branding asset paths")
    expected_paths = {line.split(" b/", 1)[1] for line in patch_bytes.decode("utf-8-sig").splitlines()
                      if line.startswith("diff --git ")}
    if expected_paths != set(paths):
        raise ValueError("Prepared branding patch has unexpected source paths")
    with tempfile.TemporaryDirectory(prefix="branding-replay-", dir=output) as owned:
        tree = Path(owned)
        for record in records:
            original = source / record["path"]
            if (original.is_symlink() or original.resolve() != original or not original.is_file()
                    or not original.is_relative_to(source) or digest(original) != record["before_sha256"]):
                raise ValueError("Branding source changed or is not an ordinary owned file")
            target = tree / record["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original.read_bytes())
        for arguments in (("--check",), ()):
            subprocess.run(["git", "-c", "core.autocrlf=false", "apply", *arguments, str(patch)],
                           cwd=tree, check=True, capture_output=True, text=True)
        for record in records:
            target = tree / record["path"]
            if (target.is_symlink() or target.resolve() != target or not target.is_file()
                    or digest(target) != record["after_sha256"]):
                raise ValueError(f"Branding asset differs from fresh generation: {record['path']}")
        subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--reverse", str(patch)],
                       cwd=tree, check=True, capture_output=True, text=True)
        if any(digest(tree / record["path"]) != record["before_sha256"] for record in records):
            raise ValueError("Branding patch did not restore the owned source copy")
    if any(digest(source / record["path"]) != record["before_sha256"] for record in records):
        raise ValueError("Original Chromium branding sources changed during verification")
    if patch.read_bytes() != patch_bytes:
        raise ValueError("Branding patch changed during verification")
    report = {"passed": True, "scope": "Source/asset replay only; not compiled branding or UI admission",
              "source_revision": prepared["source_revision"], "patch_sha256": hashlib.sha256(patch_bytes).hexdigest(),
              "source_unchanged": True, "files": records}
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8", newline="\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--patch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        report = verify(arguments.source, arguments.patch, arguments.output)
    except (ValueError, OSError, subprocess.SubprocessError, RuntimeError) as error:
        parser.exit(1, f"Glint branding verification failed: {error}\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
