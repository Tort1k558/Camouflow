"""Prepare an owned local MSVC/SDK layout without modifying installed tools."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import native_build as build
from scripts.native_windows_sdk import sha256

APPROVED_DRIVE = "D:"
MAX_BYTES = 12 * 1024**3
MAX_FILES = 25000


def validate_paths(workspace: Path, installation: Path, sdk: Path, output: Path) -> Path:
    if os.name != "nt":
        raise ValueError("Local Windows toolchain preparation requires Windows")
    for path in (workspace, installation, sdk):
        if (not path.is_absolute() or path != path.resolve() or not path.is_dir()
                or path.drive.upper() != APPROVED_DRIVE):
            raise ValueError("Toolchain inputs must be canonical directories on the approved drive")
    if (installation / "VC") != (installation / "VC").resolve() or not (installation / "VC").is_dir():
        raise ValueError("The installed VC source must be a canonical regular directory")
    config = workspace / "chromium/src/build/win_toolchain.json"
    if (config != config.resolve() or config.exists() or not config.parent.is_dir()
            or not output.is_absolute() or output != output.resolve() or output.exists()
            or output.drive.upper() != APPROVED_DRIVE or not output.parent.is_dir()
            or not output.is_relative_to(workspace / "toolchain") or output.is_relative_to(ROOT)
            or any(output.is_relative_to(path) or path.is_relative_to(output) for path in (installation, sdk))):
        raise ValueError("A new owned toolchain directory and absent Chromium toolchain config are required")
    for path in (installation, sdk, output):
        if not str(path).isascii() or any(char in str(path) for char in '%!^&|";\r\n'):
            raise ValueError("Toolchain paths cannot be represented safely in SetEnv.cmd")
    return config


def write_environments(root: Path, version: str, sdk_version: str) -> None:
    sdk = root / "Windows Kits/10"
    vc = root / "VC/Tools/MSVC" / version
    script = ['@echo off', 'if /I "%~1"=="/x86" goto x86', 'if /I "%~1"=="/x64" goto x64', 'exit /b 2']
    for cpu in ("x86", "x64"):
        entries = {
            "VSINSTALLDIR": [root],
            "PATH": [vc / "bin/Hostx64" / cpu, sdk / "bin" / sdk_version / "x64"],
            "INCLUDE": [vc / "include", *(sdk / "Include" / sdk_version / name
                                          for name in ("ucrt", "shared", "um", "winrt", "cppwinrt"))],
            "LIB": [vc / "lib" / cpu, sdk / "Lib" / sdk_version / "ucrt" / cpu,
                    sdk / "Lib" / sdk_version / "um" / cpu],
            "LIBPATH": [vc / "lib" / cpu, sdk / "UnionMetadata" / sdk_version, sdk / "References" / sdk_version],
        }
        for key in ("PATH", "INCLUDE", "LIB", "LIBPATH"):
            if any(not path.is_dir() for path in entries[key]):
                raise ValueError("Incomplete local compiler environment: " + cpu + "/" + key)
        path = sdk / "bin" / f"SetEnv.{cpu}.json"
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump({"env": {key: [[str(path)] for path in paths] for key, paths in entries.items()}}, stream, indent=2)
        script.append(":" + cpu)
        for key, paths in entries.items():
            value = ";".join(map(str, paths)) + (";%PATH%" if key == "PATH" else "")
            script.append(f'set "{key}={value}"')
        script.append("exit /b 0")
    with (sdk / "bin/SetEnv.cmd").open("x", encoding="utf-8", newline="\r\n") as stream:
        stream.write("\n".join(script) + "\n")


def prepare(workspace: Path, installation: Path, sdk: Path, output: Path, *, candidate_name: str) -> dict:
    config = validate_paths(workspace, installation, sdk, output)
    candidate = build.load_candidate(candidate_name)
    build.candidate_workspace(workspace, candidate)
    version = (installation / "VC/Auxiliary/Build/Microsoft.VCToolsVersion.default.txt").read_text(encoding="utf-8-sig").strip()
    if not re.fullmatch(r"14\.51\.[0-9]+", version):
        raise ValueError("The candidate requires the selected VS 2026 MSVC toolset")
    if any((sdk / "bin" / name).exists() for name in ("SetEnv.cmd", "SetEnv.x86.json", "SetEnv.x64.json")):
        raise ValueError("Use the original verified SDK assembly, not an already prepared environment")
    spec = json.loads((ROOT / "native/toolchain/windows-sdk-28000.json").read_text(encoding="utf-8-sig"))
    report = {"layout_verified": False, "compiled": False, "runtime_verified": False,
              "candidate_manifest_sha256": candidate["manifest_sha256"],
              "installation": str(installation), "sdk": str(sdk), "files": []}
    config_bytes = None
    config_created = False
    remaining = MAX_BYTES

    def copy_regular(source, destination):
        nonlocal remaining
        source, destination = Path(source), Path(destination)
        if source != source.resolve() or not source.is_file():
            raise ValueError("Toolchain inputs must contain regular files only")
        remaining -= source.stat().st_size
        if remaining < 0 or len(report["files"]) >= MAX_FILES:
            raise ValueError("Toolchain materialization exceeds its size/file bound")
        measured = sha256(source)
        shutil.copy2(source, destination)
        if sha256(source) != measured or sha256(destination) != measured:
            raise ValueError("Toolchain input changed during materialization")
        report["files"].append({"path": destination.relative_to(output).as_posix(), "sha256": measured})
        return str(destination)

    with build.workspace_lock(workspace):
        validate_paths(workspace, installation, sdk, output)
        build.candidate_workspace(workspace, candidate)
        if shutil.disk_usage(output.parent).free < MAX_BYTES + 8 * 1024**3:
            raise ValueError("At least 20 GiB free is required for local toolchain preparation")
        output.mkdir()
        try:
            for source, target in ((installation / "VC", output / "VC"), (sdk, output / "Windows Kits/10")):
                for parent, directories, _ in os.walk(source, followlinks=False):
                    if any((Path(parent) / name) != (Path(parent) / name).resolve() for name in directories):
                        raise ValueError("Toolchain input contains a linked directory")
                shutil.copytree(source, target, copy_function=copy_regular)
            write_environments(output, version, spec["directory_version"])
            for name in ("SetEnv.cmd", "SetEnv.x86.json", "SetEnv.x64.json"):
                path = output / "Windows Kits/10/bin" / name
                report["files"].append({"path": path.relative_to(output).as_posix(), "sha256": sha256(path)})
            data = {"path": str(output), "version": "2026", "win_sdk": str(output / "Windows Kits/10"), "wdk": "",
                    "runtime_dirs": [str(output / "VC/Redist/MSVC" / version / cpu / "Microsoft.VC145.CRT")
                                     for cpu in ("x64", "x86")] + ["Arm64Unused"]}
            config_bytes = json.dumps(data, indent=2).encode("utf-8")
            with config.open("xb") as stream:
                config_created = True
                stream.write(config_bytes)
            report["toolchain_sha256"] = build.local_windows_toolchain(workspace)["GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256"]
            for row in report["files"]:
                if sha256(output / row["path"]) != row["sha256"]:
                    raise ValueError("Materialized toolchain changed before admission")
            if config != config.resolve() or config.read_bytes() != config_bytes:
                raise ValueError("Chromium toolchain config changed during preparation")
            if build.load_candidate(candidate_name)["manifest_sha256"] != candidate["manifest_sha256"]:
                raise ValueError("Candidate inputs changed during toolchain preparation")
            report["config_sha256"] = sha256(config)
            report["layout_verified"] = True
        except Exception as error:
            report["error"] = str(error)
            if config_created and config.is_file() and config == config.resolve() and config.read_bytes() == config_bytes:
                config.unlink()
            raise
        finally:
            (output / "glint-toolchain-provenance.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--vs-installation", type=Path, required=True)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate", choices=("upstream-156",), required=True)
    args = parser.parse_args()
    try:
        prepare(args.workspace, args.vs_installation, args.sdk, args.output, candidate_name=args.candidate)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Local toolchain preparation failed: {error}\n")
    print("Local toolchain layout verified; Chromium compilation/runtime are not verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
