"""Release smoke checks for the desktop package.

Default mode is fast and local: compile app code and run the test suite.
Use --build to create a clean PyInstaller build, and --runtime to run the
packaged browser/Python checks against the built executable.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def run(command: list[str], *, cwd: Path = ROOT) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def require_venv(python: Path = PYTHON) -> Path:
    if not python.is_file():
        raise SystemExit(f"Missing Python interpreter: {python}")
    return python


def build(python: Path = PYTHON) -> Path:
    build_id = "release-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dist_path = ROOT / "dist" / build_id
    work_path = ROOT / "build" / build_id
    run(
        [
            str(require_venv(python)),
            "-m",
            "PyInstaller",
            "--clean",
            "camouflow.spec",
            "--distpath",
            str(dist_path),
            "--workpath",
            str(work_path),
        ]
    )
    if sys.platform == "darwin":
        exe = dist_path / "CamouFlow.app" / "Contents" / "MacOS" / "CamouFlow"
    else:
        exe = dist_path / "CamouFlow" / ("CamouFlow.exe" if sys.platform == "win32" else "CamouFlow")
    if not exe.exists():
        raise SystemExit(f"Build finished but executable was not found: {exe}")
    return exe


def runtime_check(exe: Path, engines: list[str]) -> None:
    reports = ROOT / "outputs" / "release-smoke"
    reports.mkdir(parents=True, exist_ok=True)
    for engine in engines:
        report = reports / f"{engine}.json"
        report.unlink(missing_ok=True)
        run([str(exe), "--check-python-runtime", engine, str(report)])
        if not report.exists():
            raise SystemExit(f"Runtime check did not write report: {report}")
        payload = json.loads(report.read_text(encoding="utf-8"))
        if not payload.get("passed"):
            raise SystemExit(f"Runtime check failed: {report}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="create a clean PyInstaller build")
    parser.add_argument("--runtime", action="store_true", help="run packaged runtime checks")
    parser.add_argument("--python", type=Path, default=PYTHON, help="Python interpreter with installed build/test dependencies")
    parser.add_argument(
        "--engine",
        action="append",
        choices=("camoufox", "cloakbrowser"),
        help="browser engine for --runtime; can be passed twice",
    )
    args = parser.parse_args()

    python = require_venv(args.python.resolve())
    run([str(python), "-m", "compileall", "-q", "app", "main.py", "scripts"])
    run([str(python), "-m", "pytest", "-q"])

    exe: Path | None = None
    if args.build or args.runtime:
        exe = build(python)
        print(f"Build done: {exe}")

    if args.runtime:
        runtime_check(exe, args.engine or ["camoufox", "cloakbrowser"])

    print("Release smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
