"""Execute the actual candidate metadata codec fixtures with pinned GoogleTest.

Standalone MSVC/standard-library execution, not Chromium target or GPU proof.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import native_build as build
from scripts.verify_native_privacy_units import required_tests, validate_results


def checksum(path: Path) -> str:
    if not path.is_file() or path != path.resolve():
        raise ValueError("Codec input must be an ordinary canonical file")
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify(workspace: Path, report: Path, vs_installation: Path) -> dict:
    if sys.platform != "win32":
        raise ValueError("The standalone codec gate currently requires Windows MSVC")
    source = workspace / "chromium/src"
    developer = vs_installation / "Common7/Tools/VsDevCmd.bat"
    if source != source.resolve() or not source.is_dir() or not developer.is_file():
        raise ValueError("Canonical Chromium and explicit Visual Studio installation required")
    if (not report.is_absolute() or report != report.resolve() or not report.parent.is_dir()
            or report.is_relative_to(ROOT) or report.is_relative_to(source)):
        raise ValueError("A new private report outside both repositories is required")
    artifacts = report.with_name(report.stem + "-artifacts")
    if any(path.exists() or path.is_symlink() for path in (report, artifacts)):
        raise ValueError("Refusing to overwrite codec evidence")
    env = build.environment(workspace)
    if build.run(["git", "rev-parse", "HEAD"], source, env, capture=True) != build.LOCK["chromium_revision"]:
        raise ValueError("Chromium revision differs from the build lock")
    candidate = ROOT / "native/drafts/gpu-transport"
    names = ("glint_readback_metadata.h", "glint_readback_metadata_unittest.cc")
    gtest = source / "third_party/googletest/src/googletest"
    angle = source / "third_party/angle/include"
    inputs = [candidate / name for name in names]
    inputs += [path for directory in (gtest / "include", gtest / "src", angle / "KHR", angle / "GLES3")
               for path in directory.rglob("*") if path.is_file()]
    inputs += [developer, source / "gpu/command_buffer/common/gl2_types.h",
               source / "testing/gtest/include/gtest/gtest.h", Path(__file__),
               ROOT / "scripts/verify_native_privacy_units.py"]
    before = {str(path): checksum(path) for path in inputs}
    output = source / "out/CamouFlowNative"
    core = build.measure_runtime_core(output / "chrome.exe")
    baseline = {name: checksum(output / name) for name in ("args.gn", "camouflow-build.json")}
    artifacts.mkdir()
    proof = {"passed": False, "scope": __doc__, "privacy_admitted": False,
             "chromium_target_built": False, "inputs_sha256": before, "artifacts": str(artifacts)}
    try:
        for name in names:
            (artifacts / name).write_bytes((candidate / name).read_bytes())
        executable = artifacts / "metadata-codec-tests.exe"
        results = artifacts / "tests.json"
        arguments = ["/nologo", "/std:c++20", "/EHsc", "/O2", "/W4", "/WX", "/MD", "/utf-8"]
        arguments += [f'/I"{path}"' for path in (source, gtest / "include", gtest, angle)]
        arguments += [f'"{path}"' for path in (artifacts / names[1], gtest / "src/gtest-all.cc", gtest / "src/gtest_main.cc")]
        arguments += [f'/Fe:"{executable}"']
        response = artifacts / "compile.rsp"
        response.write_text("\n".join(arguments), encoding="utf-8")
        installer = Path(os.environ["ProgramFiles(x86)"]) / "Microsoft Visual Studio/Installer"
        for path in (developer, installer, artifacts):
            if any(character in str(path) for character in '%!\r\n"'):
                raise ValueError("Unsupported batch path characters")
        script = artifacts / "compile.cmd"
        script.write_text(f'@echo off\nchcp 65001 >nul\nset "PATH={installer};%PATH%"\ncall "{developer}" -arch=x64 -host_arch=x64\n'
                          'if errorlevel 1 exit /b 1\ncl @compile.rsp\nexit /b %errorlevel%\n', encoding="utf-8")
        with (artifacts / "compile.log").open("x", encoding="utf-8") as log:
            subprocess.run(["cmd.exe", "/d", "/c", str(script)], cwd=artifacts, env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
        with (artifacts / "tests.log").open("x", encoding="utf-8") as log:
            subprocess.run([str(executable), "--gtest_filter=GlintReadbackMetadataTest.*", "--gtest_output=json:" + str(results)],
                           cwd=artifacts, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=30)
        validate_results(json.loads(results.read_text(encoding="utf-8-sig")), target="gpu-metadata-codec")
        if before != {str(path): checksum(path) for path in inputs}:
            raise ValueError("Codec or pinned test inputs changed during execution")
        if (core != build.measure_runtime_core(output / "chrome.exe")
                or baseline != {name: checksum(output / name) for name in baseline}):
            raise ValueError("Browser core, GN or receipt changed during codec execution")
        proof.update(passed=True, tests=sum(map(len, required_tests("gpu-metadata-codec").values())),
                     executable_sha256=checksum(executable), browser_core_unchanged=True,
                     browser_core_sha256=core)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        proof["error"] = str(error)
    with report.open("x", encoding="utf-8") as stream:
        json.dump(proof, stream, indent=2)
    return proof


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--vs-installation", type=Path, required=True)
    args = parser.parse_args()
    try:
        proof = verify(args.workspace, args.report, args.vs_installation)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"Standalone metadata codec verification failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"passed": proof["passed"], "report": str(args.report)}))
    return 0 if proof["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
