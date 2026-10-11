"""Compile/run the Native C++ policy tests; not a Chromium runtime verification."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def verify(work_dir: Path, vs_installation: Path | None = None) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="native-cpp-owned-", dir=work_dir.resolve()) as owned:
        output = Path(owned)
        source = ROOT / "native/tests/hardware_limits_test.cc"
        include = ROOT / "native"
        if os.name == "nt":
            if vs_installation is None:
                raise ValueError("An explicit Visual Studio C++ installation is required")
            developer = vs_installation / "Common7/Tools/VsDevCmd.bat"
            if not developer.is_file():
                raise ValueError("Visual Studio developer command script is missing")
            for path in (developer, source, include, output):
                if any(character in str(path) for character in '%!\r\n"'):
                    raise ValueError("Build paths contain unsupported batch characters")
            executable = output / "native-cpp-test.exe"
            installer = Path(os.environ["ProgramFiles(x86)"]) / "Microsoft Visual Studio/Installer"
            commands = (f'@echo off\nset "PATH={installer};%PATH%"\n'
                        f'call "{developer}" -arch=x64 -host_arch=x64\n'
                        'if errorlevel 1 exit /b 1\n'
                        f'cl /nologo /std:c++20 /EHsc /W4 /WX /I"{include}" "{source}" '
                        f'/Fe:"{executable}" /Fo:"{output / "native-cpp-test.obj"}"\n'
                        'if errorlevel 1 exit /b 1\n'
                        f'"{executable}"\nexit /b %errorlevel%\n')
            script = output / "check.cmd"
            script.write_text(commands, encoding="utf-8")
            subprocess.run(["cmd.exe", "/d", "/c", str(script)], cwd=output, check=True, timeout=120)
        else:
            compiler = "clang++" if sys.platform == "darwin" else "g++"
            if shutil.which(compiler) is None:
                raise ValueError(f"Required compiler is missing: {compiler}")
            executable = output / "native-cpp-test"
            subprocess.run([compiler, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pedantic",
                            "-I", str(include), str(source), "-o", str(executable)],
                           cwd=output, check=True, timeout=120)
            subprocess.run([str(executable)], cwd=output, check=True, timeout=30)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--vs-installation", type=Path)
    args = parser.parse_args()
    try:
        verify(args.work_dir, args.vs_installation)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"Native C++ policy check failed: {error}", file=sys.stderr)
        return 1
    print("Native C++ policy tests passed; Chromium integration is not yet verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
