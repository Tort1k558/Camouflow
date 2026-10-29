"""Replay a draft patch batch against checksummed upstream files without changing sources."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DRAFT = ROOT / "native/drafts/upstream-156"


def verify_source_invariants(inputs: dict[str, bytes], work: Path) -> dict:
    from scripts.verify_native_gpu_transport_draft import command_ids

    result = {}
    ids = "gpu/command_buffer/common/gles2_cmd_ids_autogen.h"
    if ids in inputs:
        before = command_ids(inputs[ids].decode("utf-8-sig"))
        after = command_ids(checked_child(work, ids).read_text(encoding="utf-8-sig"))
        expected = [("GetGlintReadFramebufferMetadataCHROMIUM", before[-1][1] + 1)] if before else []
        if (not before or after[:len(before)] != before or after[len(before):] != expected
                or len({name for name, _ in after}) != len(after)
                or len({number for _, number in after}) != len(after)):
            raise ValueError("GPU command ordinals must be preserved with one append-only metadata command")
        result["gpu_commands"] = {"preserved": len(before), "appended": expected[0][1]}
    resources = "chrome/app/chromium_strings.grd"
    if resources in inputs:
        def structure(content: bytes) -> list:
            return [(node.tag, node.attrib) for node in ET.fromstring(content).iter()]

        if structure(inputs[resources]) != structure(checked_child(work, resources).read_bytes()):
            raise ValueError("Branding must preserve GRIT resource structure and attributes")
        result["grit_structure_preserved"] = True
    return result


def checked_relative_path(name: str) -> PurePosixPath:
    if not isinstance(name, str):
        raise ValueError("Unsafe rebase input path")
    relative = PurePosixPath(name)
    if not relative.parts or relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name:
        raise ValueError("Unsafe rebase input path")
    return relative


def checked_child(root: Path, name: str) -> Path:
    relative = checked_relative_path(name)
    path = root.joinpath(*relative.parts)
    if path != path.resolve() or not path.is_file():
        raise ValueError("Missing or linked rebase input: " + name)
    return path


def load_manifest(path: Path) -> tuple[bytes, dict]:
    if (not path.is_absolute() or path != path.resolve() or not path.is_file()
            or path.stat().st_size > 4 * 1024**2):
        raise ValueError("Use a bounded canonical replay manifest")
    with path.open("rb") as stream:
        raw = stream.read(4 * 1024**2 + 1)
    if len(raw) > 4 * 1024**2:
        raise ValueError("Draft manifest exceeds the replay safety limit")
    manifest = json.loads(raw)
    if (not isinstance(manifest, dict) or type(manifest.get("schema")) is not int or manifest.get("schema") != 1
            or not isinstance(manifest.get("target_revision"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", manifest["target_revision"])
            or not isinstance(manifest.get("source_files"), list) or not manifest["source_files"]
            or not isinstance(manifest.get("patches"), list) or not manifest["patches"]):
        raise ValueError("Draft manifest requires nonempty versioned source and patch lists")
    if "target_version" in manifest and (not isinstance(manifest["target_version"], str)
            or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+", manifest["target_version"])):
        raise ValueError("Invalid draft target version")
    return raw, manifest


def verify(source: Path, output: Path, *, formatter: Path | None = None,
           manifest_path: Path | None = None, patch_directory: Path | None = None) -> dict:
    if (not source.is_absolute() or source != source.resolve() or not source.is_dir()
            or not output.is_absolute() or output != output.resolve() or not output.parent.is_dir()
            or output.exists() or output.is_relative_to(source) or output.is_relative_to(ROOT)):
        raise ValueError("Use canonical source files and a new external output directory")
    if (manifest_path is None) != (patch_directory is None):
        raise ValueError("Explicit replay requires both manifest and patch directory")
    if manifest_path is None:
        manifest_path = DRAFT / "manifest.json"
        patch_directory = DRAFT / "patches"
    if (not manifest_path.is_absolute() or manifest_path != manifest_path.resolve() or not manifest_path.is_file()
            or manifest_path.stat().st_size > 4 * 1024**2
            or not patch_directory.is_absolute() or patch_directory != patch_directory.resolve() or not patch_directory.is_dir()):
        raise ValueError("Use a bounded canonical manifest and canonical patch directory")
    if output.is_relative_to(patch_directory) or output == manifest_path:
        raise ValueError("Replay evidence must not overwrite its manifest or patch directory")
    manifest_bytes, manifest = load_manifest(manifest_path)
    inputs = {}
    patches = []
    for row in manifest["source_files"]:
        if (not isinstance(row, dict) or not isinstance(row.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])):
            raise ValueError("Invalid checksummed source entry")
        path = checked_child(source, row.get("path"))
        if row["path"] in inputs:
            raise ValueError("Duplicate source input")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != row["sha256"]:
            raise ValueError("Upstream source checksum differs: " + row["path"])
        inputs[row["path"]] = content
    for row in manifest["patches"]:
        if (not isinstance(row, dict) or not isinstance(row.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])):
            raise ValueError("Invalid checksummed patch entry")
        path = checked_child(patch_directory, row.get("file"))
        if path in patches:
            raise ValueError("Duplicate draft patch")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != row["sha256"]:
            raise ValueError("Draft patch checksum differs: " + row["file"])
        if b"\r" in content or content.startswith(b"\xef\xbb\xbf"):
            raise ValueError("Draft patches require UTF-8 without BOM and LF line endings")
        if not isinstance(row.get("directory", "."), str) or row.get("directory", ".") not in {".", "v8"}:
            raise ValueError("Unsupported draft repository directory")
        patches.append(path)
    dependencies = manifest.get("dependencies", {})
    if not isinstance(dependencies, dict):
        raise ValueError("Invalid draft dependency map")
    v8 = dependencies.get("v8")
    if v8 is not None:
        if not isinstance(v8, dict) or not isinstance(v8.get("revision"), str) or not re.fullmatch(r"[0-9a-f]{40}", v8["revision"]):
            raise ValueError("Invalid pinned V8 dependency")
        dependencies = inputs.get("DEPS", b"").decode("utf-8-sig")
        revisions = re.findall(r"'v8_revision':\s*'([0-9a-f]{40})'", dependencies)
        if revisions != [v8.get("revision")]:
            raise ValueError("Draft V8 revision does not match Chromium DEPS")
    if any(row.get("directory") == "v8" for row in manifest["patches"]) and v8 is None:
        raise ValueError("V8 drafts require a pinned Chromium DEPS dependency")
    formatter_hash = None
    if formatter is not None:
        if not formatter.is_absolute() or formatter != formatter.resolve() or not formatter.is_file():
            raise ValueError("Use an existing canonical formatter executable")
        required = {".clang-format", "gpu/command_buffer/build_cmd_buffer_lib.py",
                    "gpu/command_buffer/build_gles2_cmd_buffer.py",
                    "gpu/command_buffer/gles2_cmd_buffer_functions.txt"}
        if not required.issubset(inputs):
            raise ValueError("GPU generation requires checksummed upstream generator inputs")
        formatter_hash = hashlib.sha256(formatter.read_bytes()).hexdigest()
    output.mkdir()
    work = output / "src"
    work.mkdir()
    report = {"passed": False, "scope": "Source-context replay only; not compilation or runtime admission",
              "target_revision": manifest["target_revision"], "checks": [], "compiled": False,
              "target_version": manifest.get("target_version"),
              "manifest_path": str(manifest_path), "patch_directory": str(patch_directory),
              "runtime_verified": False, "production_admitted": False,
              "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest()}
    try:
        for name, content in inputs.items():
            path = work / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        for directory in sorted({row.get("directory", ".") for row in manifest["patches"]}):
            subprocess.run(["git", "init", "--quiet"], cwd=work / directory, check=True, capture_output=True)
        for patch, row in zip(patches, manifest["patches"], strict=True):
            directory = row.get("directory", ".")
            for arguments in (("--check",), ()):
                result = subprocess.run(["git", "-c", "core.autocrlf=false", "apply", *arguments, str(patch)], cwd=work / directory,
                                        capture_output=True, text=True, check=False)
                if result.returncode:
                    raise ValueError("Draft application failed: " + patch.name + ": " + result.stderr)
            report["checks"].append({"patch": patch.name, "directory": directory, "applied": True})
        for path in work.rglob("*"):
            if path.is_file() and ".git" not in path.parts and (path.suffix == ".py" or path.name == "DEPS"):
                ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path.relative_to(work)))
        report["source_invariants"] = verify_source_invariants(inputs, work)
        if formatter is not None:
            from scripts.verify_native_gpu_transport_draft import verify_codegen

            report["codegen"] = {"passed": False, "formatter_sha256": formatter_hash,
                                 "formatter_target_dependency_verified": False}
            report["codegen"]["compared_files"] = verify_codegen(work, formatter, dict(os.environ))
            if hashlib.sha256(formatter.read_bytes()).hexdigest() != formatter_hash:
                raise ValueError("Formatter changed during source generation")
            report["codegen"]["passed"] = True
        report["passed"] = True
    except (OSError, ValueError, SyntaxError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
    finally:
        try:
            report["inputs_unchanged"] = (manifest_path.stat().st_size == len(manifest_bytes)
                and manifest_path.read_bytes() == manifest_bytes
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
    parser.add_argument("--formatter", type=Path,
                        help="Also regenerate/compare all GPU outputs using this measured formatter; not a compiler or toolchain-admission gate")
    parser.add_argument("--manifest", type=Path,
                        help="Explicit immutable-input manifest; requires --patch-directory, never changes the active candidate")
    parser.add_argument("--patch-directory", type=Path, help="Canonical directory holding exactly the manifest-selected patch bytes")
    args = parser.parse_args()
    try:
        report = verify(args.source, args.output, formatter=args.formatter,
                        manifest_path=args.manifest, patch_directory=args.patch_directory)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Rebase draft verification failed: {error}\n")
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
