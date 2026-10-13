"""Compile actual Audio scalar fixtures in isolation; not a Blink/runtime gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.verify_native_gpu_codec import hashes, validate_results

CASES = {
    "PreservesSignedSilence", "PreservesNonFinitePayloadBits", "PreservesSubnormalBits",
    "PreservesUnitAmplitudeAndPeaks", "ChangesOnlyLeastMantissaBit", "RepeatedAndRemaskedValuesAreStable",
    "EqualStereoSamplesRemainEqual", "DifferentSeedsDoNotShareAllOutputBits", "CacheCollisionsDoNotAliasDifferentSamples",
    "RejectsEmptyAndOverflowingCopySizes", "CopyBudgetBoundaryIsExact", "MatchesIndependentHmacVectors",
    "MeasuredSignalMeetsNumericalErrorBudget",
}
SUITE = "GlintOfflineAudioCandidateTest"


def archive_member_path(crypto: Path, name: str) -> Path:
    relative = Path(name)
    original = crypto / relative
    if (not name or relative.is_absolute() or ".." in relative.parts or relative.drive
            or not original.is_file() or original != original.resolve()
            or not original.is_relative_to(crypto) or original.suffix not in {".obj", ".o"}
            or any(value in name for value in '%!\r\n"')):
        raise ValueError("BoringSSL archive member must be an ordinary owned object")
    return original


def verify(workspace: Path, report: Path, vs_installation: Path) -> dict:
    if sys.platform != "win32":
        raise ValueError("This isolated Audio compiler currently supports Windows only")
    source = workspace / "chromium/src"
    log = report.with_suffix(".log")
    if (not report.is_absolute() or report != report.resolve() or not report.parent.is_dir()
            or report.is_relative_to(source) or report.is_relative_to(ROOT) or report == log
            or any(path.exists() or path.is_symlink() for path in (report, log))):
        raise ValueError("A new canonical private report outside both repositories is required")
    tools = source / "third_party/llvm-build/Release+Asserts/bin"
    compiler, linker = tools / "clang-cl.exe", tools / "lld-link.exe"
    developer = vs_installation / "Common7/Tools/VsDevCmd.bat"
    for path in (source, compiler, linker, developer, report.parent, ROOT):
        if path != path.resolve() or not path.exists() or any(value in str(path) for value in '%!\r\n"'):
            raise ValueError("Canonical source/compiler/VS paths safe for batch invocation are required")
    canonical = ROOT / "native/drafts/audio"
    gtest = source / "third_party/googletest/src/googletest"
    crypto = source / "out/CamouFlowNative/obj/third_party/boringssl"
    abort = source / "out/CamouFlowNative/obj/buildtools/third_party/libc++/libc++/verbose_abort.obj"
    inputs = [canonical / name for name in ("offline_audio_candidate.h", "offline_audio_candidate.cc",
                                           "offline_audio_limits.h", "offline_audio_candidate_unittest.cc")]
    inputs += [compiler, linker, developer, abort, Path(__file__), ROOT / "scripts/verify_native_gpu_codec.py"]
    inputs += sorted(path for path in crypto.rglob("*") if path.is_file() and path.suffix in {".lib", ".obj", ".o"})
    for directory in (gtest, source / "third_party/boringssl/src/include"):
        inputs += sorted(path for path in directory.rglob("*") if path.is_file() and path.suffix in {".h", ".cc"})
    if any(path != path.resolve() or not path.is_file() for path in inputs):
        raise ValueError("Audio compiler inputs must be ordinary canonical files")
    before = hashes(inputs)
    core = [source / "out/CamouFlowNative" / name for name in ("chrome.exe", "chrome.dll", "chrome_elf.dll", "args.gn")]
    core_before = hashes(core)
    proof = {"passed": False, "compiled": False, "privacy_admitted": False, "inputs": before,
             "scope": "Standalone VS-STL scalar Gtest with actual Chromium BoringSSL objects; not Blink ABI or browser admission"}
    with tempfile.TemporaryDirectory(prefix="glint-audio-native-", dir=report.parent) as temporary:
        owned = Path(temporary)
        with log.open("x", encoding="utf-8") as output:
            try:
                for path in inputs[:4]:
                    (owned / path.name).write_bytes(path.read_bytes())
                members = []
                for library in ("boringssl.lib", "boringssl_asm.lib"):
                    listing = subprocess.run([str(linker), "/lib", "/list", str(crypto / library)],
                                             check=True, capture_output=True, text=True, timeout=30)
                    for name in listing.stdout.splitlines():
                        original = archive_member_path(crypto, name)
                        if str(original) not in before:
                            raise ValueError("Archive references an unmeasured object")
                        target = owned / "crypto" / original.relative_to(crypto)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(original.read_bytes())
                        members.append(target)
                if not members:
                    raise ValueError("BoringSSL snapshot is empty")
                snapshot = owned / "boringssl-snapshot.lib"
                response = owned / "members.rsp"
                response.write_text("\n".join(f'"{path}"' for path in members), encoding="utf-8")
                abort_snapshot = owned / "verbose_abort.obj"
                abort_snapshot.write_bytes(abort.read_bytes())
                executable, result = owned / "audio-test.exe", owned / "tests.json"
                commands = (f'@echo off\ncall "{developer}" -arch=x64 -host_arch=x64\n'
                            'if errorlevel 1 exit /b 1\n'
                            f'"{linker}" /lib /out:"{snapshot}" @"{response}"\n'
                            'if errorlevel 1 exit /b 1\n'
                            f'"{compiler}" /nologo /std:c++20 /EHsc /W4 -fuse-ld=lld /I"{owned}" /I"{source}" '
                            f'/I"{source / "third_party/boringssl/src/include"}" /I"{gtest}" /I"{gtest / "include"}" '
                            f'"{owned / "offline_audio_candidate.cc"}" "{owned / "offline_audio_candidate_unittest.cc"}" '
                            f'"{gtest / "src/gtest-all.cc"}" "{gtest / "src/gtest_main.cc"}" /Fe:"{executable}" '
                            f'/link "{snapshot}" "{abort_snapshot}" bcrypt.lib advapi32.lib crypt32.lib\n'
                            'if errorlevel 1 exit /b 1\n'
                            f'"{executable}" --gtest_filter={SUITE}.* --gtest_output=json:"{result}"\n'
                            'exit /b %errorlevel%\n')
                script = owned / "check.cmd"
                script.write_text(commands, encoding="utf-8", newline="\n")
                subprocess.run(["cmd.exe", "/d", "/c", str(script)], cwd=owned,
                               stdout=output, stderr=subprocess.STDOUT, check=True, timeout=180)
                proof["compiled"] = True
                tests = json.loads(result.read_text(encoding="utf-8-sig"))
                validate_results(tests, required_cases=CASES, suite_name=SUITE, label="Audio scalar")
                with snapshot.open("rb") as stream:
                    if stream.read(8) != b"!<arch>\n":
                        raise ValueError("Crypto snapshot is not a regular archive")
                if before != hashes(inputs) or core_before != hashes(core):
                    raise ValueError("Verification inputs or active runtime/GN changed")
                proof.update(passed=True, results=tests, inputs_unchanged=True,
                             active_runtime_core_and_gn_unchanged=True, baseline_core_sha256=core_before,
                             test_binary_sha256=hashes([executable])[str(executable)])
            except (ValueError, OSError, subprocess.SubprocessError) as error:
                proof["error"] = str(error)
    with report.open("x", encoding="utf-8") as output:
        json.dump(proof, output, indent=2)
    return proof


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--vs-installation", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.workspace, args.report, args.vs_installation)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"Audio scalar verification failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({key: result[key] for key in ("passed", "compiled", "privacy_admitted")}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
