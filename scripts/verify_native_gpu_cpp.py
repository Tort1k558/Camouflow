"""Isolated GPU candidate syntax checks using actual generated target flags."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys

from scripts.verify_native_document_drafts import digest
from scripts.verify_native_runtime import measure_runtime_core

TARGETS = {
    "validating": ("service/gles2_cmd_decoder.cc", "command_buffer/service/gles2_sources"),
    "passthrough": ("service/gles2_cmd_decoder_passthrough_doers.cc", "command_buffer/service/gles2_sources"),
    "handlers": ("service/gles2_cmd_decoder_passthrough_handlers.cc", "command_buffer/service/gles2_sources"),
    "client": ("client/gles2_implementation.cc", "command_buffer/client/gles2_implementation"),
    "attachment-fixtures": ("service/gles2_cmd_decoder_passthrough_unittest_framebuffers.cc", "gpu_unittests"),
    "protocol-fixtures": ("service/gles2_cmd_decoder_passthrough_unittest_commands.cc", "gpu_unittests"),
}


def evidence_directory(log: Path) -> Path:
    if log != log.resolve() or not log.parent.is_dir() or log.exists() or log.is_symlink():
        raise ValueError("A fresh canonical C++ diagnostic log is required")
    checks = log.with_name(log.name + ".artifacts")
    if checks != checks.resolve() or checks.exists() or checks.is_symlink():
        raise ValueError("Refusing to overwrite C++ diagnostic artifacts")
    checks.mkdir()
    return checks


def compiler_failure_is_fatal(log: Path, offset: int, exit_code: int | None) -> bool:
    if exit_code not in {0, 1}:
        return True
    markers = (b"LLVM ERROR:", b"Allocation failed", b"Exception Code:",
               b"clang frontend command failed due to signal")
    with log.open("rb") as stream:
        stream.seek(offset)
        tail = b""
        while chunk := stream.read(65536):
            diagnostic = tail + chunk
            if any(marker in diagnostic for marker in markers):
                return True
            tail = diagnostic[-128:]
    return False


def syntax_flags(ninja: str, toolchain: str, relative: str, *, generated: bool = False) -> str:
    prefix = "gen/" if generated else "../../"
    if not re.search(r"^build [^\n]+: cxx " + re.escape(prefix + relative) + r"(?: \||$)", ninja, re.M):
        raise ValueError("Requested source is absent from its generated C++ target")
    variables = dict(re.findall(r"^(\w+) = (.*)$", ninja, re.M))
    if not all(key in variables for key in ("defines", "include_dirs", "cflags", "cflags_cc")):
        raise ValueError("Generated C++ target is missing required flags")
    match = re.search(r"^rule cxx\n  command = ([^\n]+)", toolchain, re.M)
    if not match or "/showIncludes:user " not in match[1] or "${defines}" not in match[1]:
        raise ValueError("Unsupported generated C++ compiler rule")
    prefix = match[1].split("/showIncludes:user ", 1)[1].split("${defines}", 1)[0]
    flags = " ".join(variables[key] for key in ("defines", "include_dirs", "cflags", "cflags_cc"))
    flags = flags.replace("$:", ":").replace("$$", "$")
    if "$" in flags or "$" in prefix:
        raise ValueError("Generated C++ flags contain unresolved Ninja substitutions")
    # Parse the candidate headers, not the active build's old precompiled header.
    flags = re.sub(r"/Fp\S+|/Yu\S+", "", flags)
    flags = re.sub(r"-fcrash-diagnostics-dir=\S+", "", flags)
    return prefix + flags


def verify_cpp(source: Path, overlay: Path, log: Path, env: dict, *, collect_errors: bool = False) -> dict:
    if sys.platform != "win32":
        raise ValueError("GPU candidate C++ syntax checking currently supports Windows only")
    output = source / "out/CamouFlowNative"
    compiler = source / "third_party/llvm-build/Release+Asserts/bin/clang-cl.exe"
    toolchain = output / "toolchain.ninja"
    inputs = [compiler, toolchain, Path(__file__)]
    inputs += [output / "obj/gpu" / (target + ".ninja") for _, target in TARGETS.values()]
    if any(path != path.resolve() or not path.is_file() for path in inputs):
        raise ValueError("C++ checker requires canonical existing compiler/target files")
    before = {str(path): digest(path) for path in inputs}
    core = measure_runtime_core(output / "chrome.exe")
    arguments = digest(output / "args.gn")
    checks = evidence_directory(log)
    units = {}
    aborted = False
    with log.open("x", encoding="utf-8") as stream:
        for name, (unit, target) in TARGETS.items():
            relative = "gpu/command_buffer/" + unit
            candidate = overlay / relative
            if candidate != candidate.resolve() or not candidate.is_file():
                raise ValueError("Candidate C++ source is missing or linked")
            flags = syntax_flags((output / "obj/gpu" / (target + ".ninja")).read_text(encoding="utf-8-sig"),
                                 toolchain.read_text(encoding="utf-8-sig"), relative)
            response = checks / (name + ".rsp")
            response.write_text(f'/nologo -I"{overlay}" {flags} -fcrash-diagnostics-dir="{checks}" '
                                f'/clang:-fsyntax-only /TP "{candidate}"\n',
                                encoding="utf-8", newline="\n")
            stream.write(f"\n=== {name}: {relative} ===\n")
            stream.flush()
            offset = stream.tell()
            try:
                result = subprocess.run([str(compiler), "@" + str(response)], cwd=output, env=env,
                                        stdout=stream, stderr=subprocess.STDOUT, timeout=180)
                exit_code = result.returncode
            except subprocess.TimeoutExpired:
                if not collect_errors:
                    raise
                exit_code = None
            stream.flush()
            units[name] = {"source": relative, "exit_code": exit_code,
                           "response_sha256": digest(response), "candidate_sha256": digest(candidate)}
            if exit_code != 0:
                if not collect_errors:
                    raise ValueError(f"GPU candidate C++ syntax failed: {name}; see {log}")
                if compiler_failure_is_fatal(log, offset, exit_code):
                    aborted = True
                    break
    if before != {str(path): digest(path) for path in inputs}:
        raise ValueError("Generated compiler/target inputs changed during syntax checking")
    if measure_runtime_core(output / "chrome.exe") != core or digest(output / "args.gn") != arguments:
        raise ValueError("Active browser/GN changed during C++ syntax checking")
    return {"passed": len(units) == len(TARGETS) and all(unit["exit_code"] == 0 for unit in units.values()),
            "compiled": False, "privacy_admitted": False,
            "scope": "C++ parsing/type-checking only; no optimization, link, native test or browser execution",
            "units": units, "inputs": before, "baseline_runtime_core_sha256": core,
            "active_core_and_gn_unchanged": True, "args_sha256": arguments,
            "diagnostic_artifacts": str(checks), "collect_errors": collect_errors,
            "aborted": aborted, "not_checked": [name for name in TARGETS if name not in units]}
