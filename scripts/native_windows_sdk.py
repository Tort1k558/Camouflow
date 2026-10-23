"""Assemble the pinned candidate SDK without changing Windows' installed SDK."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.native_build import workspace_lock

SPEC = ROOT / "native/toolchain/windows-sdk-28000.json"
MAX_UNPACKED_BYTES = 8 * 1024 ** 3


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def sdk_relative_path(name: str, *, common: bool, version: str) -> Path:
    parts = name.split("/")
    if (not name.startswith("c/") or any(part in {"", ".", ".."} for part in parts)
            or any(":" in part or "\\" in part for part in parts)):
        raise ValueError("Unsafe SDK archive path")
    relative = PurePosixPath(*parts[1:])
    if not common:
        if relative.parts[0] not in {"um", "ucrt", "ucrt_enclave"}:
            raise ValueError("Unexpected architecture library layout")
        relative = PurePosixPath("Lib", version) / relative
    return Path(*relative.parts)


def extract_package(archive_path: Path, output: Path, *, common: bool, version: str,
                    remaining: int) -> tuple[list[dict], int]:
    import zipfile

    files = []
    with zipfile.ZipFile(archive_path) as archive:
        for entry in archive.infolist():
            if not entry.filename.startswith("c/") or entry.is_dir():
                continue
            if stat.S_IFMT(entry.external_attr >> 16) == stat.S_IFLNK:
                raise ValueError("Linked SDK archive entry")
            relative = sdk_relative_path(entry.filename, common=common, version=version)
            target = output / relative
            if not target.resolve().is_relative_to(output) or target.exists():
                raise ValueError("Linked or conflicting SDK destination")
            remaining -= entry.file_size
            if remaining < 0:
                raise ValueError("SDK extraction exceeds its size bound")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as source, target.open("xb") as destination:
                shutil.copyfileobj(source, destination, length=1024 * 1024)
            files.append({"path": relative.as_posix(), "archive_path": entry.filename,
                          "sha256": sha256(target)})
    return files, remaining


def validate_inputs(packages: Path, output: Path, debuggers: Path) -> None:
    for path in (packages, debuggers):
        if not path.is_absolute() or path != path.resolve() or not path.is_dir():
            raise ValueError("Input roots must be canonical existing directories")
    if (not output.is_absolute() or output != output.resolve() or output.exists()
            or output.is_relative_to(ROOT) or output.is_relative_to(packages)
            or output.is_relative_to(debuggers) or not output.parent.is_dir()):
        raise ValueError("SDK output must be new, external, canonical and have an existing parent")
    if os.name == "nt" and output.drive.upper() != "D:":
        raise ValueError("Use the approved D: drive for the SDK assembly")


def verify_debugger(path: Path, minimum: str) -> dict:
    if not path.is_file() or path != path.resolve():
        raise ValueError("Debugger DLL is missing or linked")
    quoted = str(path).replace("'", "''")
    script = (f"$p='{quoted}'; $s=Get-AuthenticodeSignature -LiteralPath $p; "
              "[pscustomobject]@{Status=$s.Status.ToString();"
              "Version=(Get-Item -LiteralPath $p).VersionInfo.FileVersion}|ConvertTo-Json")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", script], check=True,
                            capture_output=True, text=True, encoding="utf-8", timeout=60)
    metadata = json.loads(result.stdout)
    version = tuple(map(int, metadata["Version"].split(" ")[0].split(".")))
    if metadata["Status"] != "Valid" or version < tuple(map(int, minimum.split("."))):
        raise ValueError("Debugger DLL signature or servicing version is not acceptable")
    return {**metadata, "sha256": sha256(path)}


def assemble(packages: Path, output: Path, debuggers: Path) -> dict:
    validate_inputs(packages, output, debuggers)
    if sys.platform != "win32":
        raise ValueError("Signature-verified SDK assembly requires Windows")
    dotnet = shutil.which("dotnet")
    if dotnet is None:
        raise ValueError("The .NET SDK NuGet signature verifier is required")
    spec = json.loads(SPEC.read_text(encoding="utf-8-sig"))
    inputs = []
    for package in spec["packages"]:
        archive = packages / package["url"].rsplit("/", 1)[1]
        if (not archive.is_file() or archive != archive.resolve()
                or archive.stat().st_size != package["bytes"] or sha256(archive) != package["sha256"]):
            raise ValueError("Missing or changed pinned SDK package: " + package["package"])
        inputs.append((package, archive))
    debugger_inputs = []
    for arch in ("x64", "x86"):
        for name in ("dbghelp.dll", "dbgcore.dll", "symsrv.dll"):
            source = debuggers / arch / name
            metadata = verify_debugger(source, spec["minimum_debugger_version"])
            debugger_inputs.append((source, Path("Debuggers", arch, name), metadata))
    output.mkdir()
    configuration = output / "NuGet.Config"
    configuration.write_text(
        '<configuration><packageSources><clear /></packageSources><config>'
        '<add key="signatureValidationMode" value="require" /></config><trustedSigners>'
        '<repository name="nuget.org" serviceIndex="https://api.nuget.org/v3/index.json">'
        f'<certificate fingerprint="{spec["repository_signer_sha256"]}" hashAlgorithm="SHA256" '
        'allowUntrustedRoot="false" /></repository></trustedSigners></configuration>', encoding="utf-8")
    env = {**os.environ, "DOTNET_CLI_HOME": str(output / "dotnet-home"),
           "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
           "DOTNET_GENERATE_ASPNET_CERTIFICATE": "false", "DOTNET_CLI_UI_LANGUAGE": "en-US",
           "NUGET_PACKAGES": str(output / "nuget-cache"), "NUGET_HTTP_CACHE_PATH": str(output / "http-cache"),
           "TEMP": str(output), "TMP": str(output)}
    report = {"schema": 1, "sdk_package_version": spec["version"], "files": [], "packages": [],
              "debuggers": [], "layout_verified": False, "compiled": False, "runtime_verified": False}
    report_path = output / "glint-sdk-provenance.json"
    with workspace_lock(output):
        remaining = MAX_UNPACKED_BYTES
        try:
            # Verify all packages before extracting executable tools from any of them.
            for package, archive in inputs:
                result = subprocess.run([dotnet, "nuget", "verify", str(archive), "--all", "--configfile", str(configuration)],
                                        env=env, cwd=output, capture_output=True, timeout=180, check=False)
                log = output / (archive.name + ".verify.log")
                log.write_bytes(result.stdout + result.stderr)
                if result.returncode:
                    raise ValueError("NuGet signature verification failed: " + package["package"])
                report["packages"].append({**package, "verification_exit_code": result.returncode,
                                            "verification_log_sha256": sha256(log)})
            for package, archive in inputs:
                if sha256(archive) != package["sha256"]:
                    raise ValueError("SDK package changed during signature verification")
                files, remaining = extract_package(archive, output, common=package["package"] == "Microsoft.Windows.SDK.CPP",
                                                   version=spec["directory_version"], remaining=remaining)
                report["files"].extend({**file, "package": package["package"]} for file in files)
                print("Extracted " + package["package"], flush=True)
            for source, relative, metadata in debugger_inputs:
                if sha256(source) != metadata["sha256"]:
                    raise ValueError("Debugger DLL changed after signature verification")
                target = output / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                if sha256(target) != metadata["sha256"]:
                    raise ValueError("Copied debugger DLL differs")
                report["debuggers"].append({"source": str(source), "path": relative.as_posix(), **metadata})
            for arch in ("x64", "x86", "arm64"):
                for relative in (f"Lib/{spec['directory_version']}/um/{arch}/kernel32.Lib",
                                 f"Lib/{spec['directory_version']}/ucrt/{arch}/ucrt.lib",
                                 f"bin/{spec['directory_version']}/{arch}/midl.exe",
                                 f"bin/{spec['directory_version']}/{arch}/rc.exe"):
                    if not (output / relative).is_file():
                        raise ValueError("Incomplete SDK layout: " + relative)
            for relative in ("um/Windows.h", "ucrt/stdio.h", "shared/sdkddkver.h", "winrt/windows.foundation.h"):
                if not (output / "Include" / spec["directory_version"] / relative).is_file():
                    raise ValueError("Incomplete SDK headers: " + relative)
            report["layout_verified"] = True
        except Exception as error:
            report["error"] = str(error)
            raise
        finally:
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packages", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--debuggers", type=Path, required=True)
    args = parser.parse_args()
    assemble(args.packages, args.output, args.debuggers)
    print("SDK layout verified; Chromium compilation/runtime are not verified.")


if __name__ == "__main__":
    main()
