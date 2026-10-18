"""Replay a draft patch batch against checksummed upstream files without changing sources."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "native/drafts/upstream-156"


def checked_child(root: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if not relative.parts or relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name:
        raise ValueError("Unsafe rebase input path")
    path = root.joinpath(*relative.parts)
    if path != path.resolve() or not path.is_file():
        raise ValueError("Missing or linked rebase input: " + name)
    return path


def verify(source: Path, output: Path) -> dict:
    if (not source.is_absolute() or source != source.resolve() or not source.is_dir()
            or not output.is_absolute() or output != output.resolve() or not output.parent.is_dir()
            or output.exists() or output.is_relative_to(source) or output.is_relative_to(ROOT)):
        raise ValueError("Use canonical source files and a new external output directory")
    manifest_path = DRAFT / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if (not isinstance(manifest, dict) or manifest.get("schema") != 1
            or not isinstance(manifest.get("source_files"), list) or not manifest["source_files"]
            or not isinstance(manifest.get("patches"), list) or not manifest["patches"]):
        raise ValueError("Draft manifest requires nonempty versioned source and patch lists")
    inputs = {}
    patches = []
    for row in manifest["source_files"]:
        path = checked_child(source, row["path"])
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != row["sha256"]:
            raise ValueError("Upstream source checksum differs: " + row["path"])
        inputs[row["path"]] = content
    for row in manifest["patches"]:
        path = checked_child(DRAFT / "patches", row["file"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Draft patch checksum differs: " + row["file"])
        patches.append(path)
    output.mkdir()
    work = output / "src"
    work.mkdir()
    report = {"passed": False, "scope": "Source-context replay only; not compilation or runtime admission",
              "target_revision": manifest["target_revision"], "checks": [], "compiled": False,
              "runtime_verified": False, "production_admitted": False,
              "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest()}
    try:
        for name, content in inputs.items():
            path = work / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        subprocess.run(["git", "init", "--quiet"], cwd=work, check=True, capture_output=True)
        for patch in patches:
            for arguments in (("--check",), ()):
                result = subprocess.run(["git", "apply", *arguments, str(patch)], cwd=work,
                                        capture_output=True, text=True, check=False)
                if result.returncode:
                    raise ValueError("Draft application failed: " + patch.name + ": " + result.stderr)
            report["checks"].append({"patch": patch.name, "applied": True})
        for path in work.rglob("*"):
            if path.is_file() and ".git" not in path.parts and (path.suffix == ".py" or path.name == "DEPS"):
                ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path.relative_to(work)))
        report["passed"] = True
    except (OSError, ValueError, SyntaxError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
    finally:
        try:
            report["inputs_unchanged"] = (manifest_path.read_bytes() == manifest_bytes
                and all(checked_child(source, name).read_bytes() == content for name, content in inputs.items())
                and all(hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
                        for path, row in zip(patches, manifest["patches"], strict=True)))
        except (OSError, ValueError) as error:
            report["inputs_unchanged"] = False
            report["guard_error"] = str(error)
        report["passed"] = report["passed"] and report["inputs_unchanged"]
        (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = verify(args.source, args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Rebase draft verification failed: {error}\n")
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
