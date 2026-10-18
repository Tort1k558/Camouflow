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


def build(python: Path = PYTHON, *, artifacts_dir: Path | None = None) -> Path:
    base = ROOT if artifacts_dir is None else artifacts_dir
    if not base.is_absolute() or base != base.resolve() or not base.is_dir():
        raise SystemExit("Build artifacts directory must be an existing canonical absolute directory")
    build_id = "release-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dist_path = base / "dist" / build_id
    work_path = base / "build" / build_id
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


def runtime_check(exe: Path, engines: list[str], *, native_store: Path | None = None, report_dir: Path | None = None) -> None:
    if "native" in engines and native_store is None:
        raise SystemExit("Native runtime checking requires --native-store")
    reports = ROOT / "outputs" / "release-smoke" if report_dir is None else report_dir
    reports.mkdir(parents=True, exist_ok=True)
    for engine in engines:
        report = reports / f"{engine}.json"
        if engine == "native" and report.exists():
            raise SystemExit("Refusing to overwrite Native packaged runtime evidence")
        report.unlink(missing_ok=True)
        command = ([str(exe), "--check-native-runtime", str(native_store), str(report)] if engine == "native" else
                   [str(exe), "--check-python-runtime", engine, str(report)])
        run(command)
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
    parser.add_argument("--artifacts-dir", type=Path, help="Existing absolute directory for build artifacts and reports")
    parser.add_argument("--native-store", type=Path, help="Managed store with an active reviewed Glint package")
    parser.add_argument(
        "--engine",
        action="append",
        choices=("camoufox", "cloakbrowser", "native"),
        help="browser engine for --runtime; repeat for multiple engines",
    )
    args = parser.parse_args()
    engines = args.engine or ["camoufox", "cloakbrowser"]
    if "native" in engines and args.native_store is None:
        parser.error("--engine native requires --native-store")
    if args.native_store is not None and "native" not in engines:
        parser.error("--native-store requires --engine native")

    python = require_venv(args.python.resolve())
    run([str(python), "-m", "compileall", "-q", "app", "main.py", "scripts"])
    run([str(python), "-m", "pytest", "-q"])

    exe: Path | None = None
    if args.build or args.runtime:
        exe = build(python, artifacts_dir=args.artifacts_dir)
        print(f"Build done: {exe}")

    if args.runtime:
        reports = (args.artifacts_dir / "reports" / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
                   if args.artifacts_dir is not None else None)
        runtime_check(exe, engines, native_store=args.native_store, report_dir=reports)

    print("Release smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
