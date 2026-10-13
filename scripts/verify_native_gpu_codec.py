"""Run actual standalone GPU metadata codec fixtures; not a decoder/runtime gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "ByteColourRoundTripPreservesNativeDimensions", "NonByteAndMultisampleInformationIsNotFabricated",
    "UnavailableCannotBecomeReady", "TruncatedWireNeverReadsMissingFields", "ExtraFieldsAreNotSilentlyAccepted",
    "SchemaIsExact", "ReadyStatusIsExact", "DimensionsMustBePositive", "InvalidFormatIsNotGuessed",
    "NegativeSamplesAreRejected", "ByteColourClassificationIsAnExactBoolean", "ProducerRejectsInvalidRepresentations",
}


def validate_results(results: dict) -> None:
    if (not isinstance(results, dict) or any(type(results.get(key)) is not int
                                           for key in ("tests", "failures", "disabled"))
            or results["tests"] != len(CASES) or results.get("failures") != 0 or results.get("disabled") != 0):
        raise ValueError("GPU codec test totals are incomplete or failed")
    suites = results.get("testsuites")
    if (not isinstance(suites, list) or len(suites) != 1 or not isinstance(suites[0], dict)
            or suites[0].get("name") != "GlintReadbackMetadataTest"):
        raise ValueError("GPU codec suite is missing or foreign")
    cases = suites[0].get("testsuite")
    if not isinstance(cases, list) or len(cases) != len(CASES):
        raise ValueError("GPU codec cases are incomplete")
    observed = []
    for case in cases:
        if (not isinstance(case, dict) or not isinstance(case.get("name"), str)
                or case.get("status") != "RUN" or case.get("result") != "COMPLETED" or case.get("failures")):
            raise ValueError("GPU codec case did not complete successfully")
        observed.append(case["name"])
    if len(set(observed)) != len(observed) or set(observed) != CASES:
        raise ValueError("GPU codec cases differ from the required fixtures")


def hashes(paths: list[Path]) -> dict[str, str]:
    result = {}
    for path in paths:
        with path.open("rb") as stream:
            result[str(path)] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


def verify(workspace: Path, report: Path, vs_installation: Path) -> dict:
    if sys.platform != "win32":
        raise ValueError("This isolated codec compiler currently supports Windows only")
    source = workspace / "chromium/src"
    log = report.with_suffix(".log")
    if (not report.is_absolute() or report != report.resolve() or not report.parent.is_dir()
            or report.is_relative_to(source) or report.is_relative_to(ROOT)
            or report == log or any(path.exists() or path.is_symlink() for path in (report, log))):
        raise ValueError("A new canonical private report outside both repositories is required")
    developer = vs_installation / "Common7/Tools/VsDevCmd.bat"
    compiler = source / "third_party/llvm-build/Release+Asserts/bin/clang-cl.exe"
    for path in (source, developer, compiler, report.parent, ROOT):
        if path != path.resolve() or not path.exists() or any(value in str(path) for value in '%!\r\n"'):
            raise ValueError("A canonical compiler/source/VS path safe for batch invocation is required")
    canonical = ROOT / "native/drafts/gpu-transport"
    gtest = source / "third_party/googletest/src/googletest"
    inputs = [canonical / name for name in ("glint_readback_metadata.h", "glint_readback_metadata_unittest.cc")]
    inputs += [source / "gpu/command_buffer/common/gl2_types.h", compiler, developer, Path(__file__)]
    inputs += sorted(path for path in gtest.rglob("*") if path.is_file() and path.suffix in {".cc", ".h"})
    inputs += sorted(path for path in (source / "third_party/khronos").rglob("*.h") if path.is_file())
    if any(path != path.resolve() or not path.is_file() for path in inputs):
        raise ValueError("Codec compiler inputs must be ordinary canonical files")
    before = hashes(inputs)
    core = [source / "out/CamouFlowNative" / name for name in ("chrome.exe", "chrome.dll", "chrome_elf.dll", "args.gn")]
    core_before = hashes(core)
    proof = {"passed": False, "compiled": False, "privacy_admitted": False, "inputs": before,
             "scope": "Standalone real C++ codec fixtures; not GPU decoder, Blink ABI, driver or browser admission"}
    with tempfile.TemporaryDirectory(prefix="glint-codec-native-", dir=report.parent) as temporary:
        owned = Path(temporary)
        for path in inputs[:2]:
            (owned / path.name).write_bytes(path.read_bytes())
        executable = owned / "metadata-test.exe"
        result = owned / "tests.json"
        commands = (f'@echo off\ncall "{developer}" -arch=x64 -host_arch=x64\n'
                    'if errorlevel 1 exit /b 1\n'
                    f'"{compiler}" /nologo /std:c++20 /EHsc /W4 /I"{owned}" /I"{source}" '
                    f'/I"{source / "third_party/khronos"}" /I"{gtest}" /I"{gtest / "include"}" '
                    f'"{owned / inputs[1].name}" "{gtest / "src/gtest-all.cc"}" "{gtest / "src/gtest_main.cc"}" '
                    f'/Fe:"{executable}"\nif errorlevel 1 exit /b 1\n'
                    f'"{executable}" --gtest_filter=GlintReadbackMetadataTest.* --gtest_output=json:"{result}"\n'
                    'exit /b %errorlevel%\n')
        script = owned / "check.cmd"
        script.write_text(commands, encoding="utf-8", newline="\n")
        with log.open("x", encoding="utf-8") as output:
            try:
                subprocess.run(["cmd.exe", "/d", "/c", str(script)], cwd=owned,
                               stdout=output, stderr=subprocess.STDOUT, check=True, timeout=180)
                proof["compiled"] = True
                tests = json.loads(result.read_text(encoding="utf-8-sig"))
                validate_results(tests)
                proof.update(results=tests, test_binary_sha256=hashes([executable])[str(executable)])
                if hashes(inputs) != before or hashes(core) != core_before:
                    raise ValueError("Codec verification changed inputs or active browser/GN")
                proof.update(passed=True, inputs_unchanged=True, active_runtime_core_and_gn_unchanged=True,
                             baseline_core_sha256=core_before)
            except (ValueError, OSError, subprocess.SubprocessError) as error:
                proof["error"] = str(error)
    with report.open("x", encoding="utf-8") as output:
        json.dump(proof, output, indent=2)
    return proof


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--vs-installation", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args.workspace, args.report, args.vs_installation)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"GPU codec verification failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({key: result[key] for key in ("passed", "compiled", "privacy_admitted")}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
