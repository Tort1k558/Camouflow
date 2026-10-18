"""Replay a draft patch batch against checksummed upstream files without changing sources."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
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
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != row["sha256"]:
            raise ValueError("Draft patch checksum differs: " + row["file"])
        if b"\r" in content or content.startswith(b"\xef\xbb\xbf"):
            raise ValueError("Draft patches require UTF-8 without BOM and LF line endings")
        if row.get("directory", ".") not in {".", "v8"}:
            raise ValueError("Unsupported draft repository directory")
        patches.append(path)
    v8 = manifest.get("dependencies", {}).get("v8")
    if v8 is not None:
        dependencies = inputs.get("DEPS", b"").decode("utf-8-sig")
        revisions = re.findall(r"'v8_revision':\s*'([0-9a-f]{40})'", dependencies)
        if revisions != [v8.get("revision")]:
            raise ValueError("Draft V8 revision does not match Chromium DEPS")
    if any(row.get("directory") == "v8" for row in manifest["patches"]) and v8 is None:
        raise ValueError("V8 drafts require a pinned Chromium DEPS dependency")
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
