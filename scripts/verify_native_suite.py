"""Run Native Windows runtime gates against one explicit, unchanged executable."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.package_native_windows import REQUIRED_RUNTIME_CHECKS
from scripts.verify_native_combined import ARGUMENTS, REQUIRED_CHECKS as REQUIRED_COMBINED_CHECKS


GATES = ("runtime", "hardware", "webrtc", "automation", "fonts", "identity", "cdp", "combined")


def checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_report(name: str, report: dict, expected_checksum: str) -> None:
    if not isinstance(report, dict) or report.get("passed") is not True:
        raise ValueError("Gate did not produce a passing report")
    if report.get("binary_sha256_measured") != expected_checksum:
        raise ValueError("Gate report does not match the measured executable")
    checks = report.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError("Gate report has no checks")
    if name == "runtime":
        if any(not isinstance(check, str) for check in checks) or not REQUIRED_RUNTIME_CHECKS.issubset(checks):
            raise ValueError("Runtime report is missing required lifecycle checks")
    elif any(not isinstance(check, dict) or check.get("passed") is not True for check in checks):
        raise ValueError("Gate contains incomplete or failed checks")
    if name == "combined":
        names = [check.get("name") for check in checks]
        if (any(not isinstance(value, str) for value in names)
                or len(names) != len(REQUIRED_COMBINED_CHECKS) or set(names) != REQUIRED_COMBINED_CHECKS
                or report.get("arguments") != ARGUMENTS):
            raise ValueError("Combined report is missing required policy checks")
        core = report.get("runtime_core_sha256_measured")
        if (not isinstance(core, dict) or set(core) != {"chrome.exe", "chrome.dll", "chrome_elf.dll"}
                or core["chrome.exe"] != expected_checksum
                or any(not isinstance(value, str) or len(value) != 64
                       or any(c not in "0123456789abcdef" for c in value) for value in core.values())):
            raise ValueError("Combined report is missing its runtime code measurement")


def verify(executable: Path, destination: Path, gates: list[str]) -> dict:
    if sys.platform != "win32":
        raise ValueError("This suite currently supports Windows only")
    if (not executable.is_absolute() or executable != executable.resolve()
            or not executable.is_file()):
        raise ValueError("An explicit canonical browser executable is required")
    if (not destination.is_absolute() or destination != destination.resolve()
            or not destination.parent.is_dir()):
        raise ValueError("An absolute new report directory with an existing parent is required")
    if not gates or len(set(gates)) != len(gates) or any(name not in GATES for name in gates):
        raise ValueError("Select unique known Native gates")
    measured = checksum(executable)
    # A fresh directory prevents stale reports from being admitted after a failed child.
    destination.mkdir(exist_ok=False)
    report = {"schema": 1, "platform": "Windows", "executable": str(executable),
              "binary_sha256_measured": measured, "requested_gates": gates,
              "full_suite": set(gates) == set(GATES), "passed": False, "gates": [],
              "scope": "Owned runtime fixtures only; not release provenance or third-party anti-bot acceptance"}
    try:
        for name in gates:
            entry = {"name": name, "passed": False}
            report["gates"].append(entry)
            try:
                if checksum(executable) != measured:
                    raise ValueError("Executable changed before gate execution")
                child_report = destination / (name + ".json")
                log = destination / (name + ".log")
                command = [sys.executable, str(ROOT / "scripts" / ("verify_native_" + name + ".py")),
                           "--executable", str(executable), "--work-dir", str(destination),
                           "--report", str(child_report)]
                with log.open("wb") as output:
                    result = subprocess.run(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT,
                                            check=False)
                entry.update(returncode=result.returncode, report=child_report.name, log=log.name)
                if checksum(executable) != measured:
                    raise ValueError("Executable changed during gate execution")
                if result.returncode != 0:
                    raise ValueError("Gate process failed; inspect its report and log")
                if child_report.is_symlink() or child_report.stat().st_size > 8 * 1024 * 1024:
                    raise ValueError("Gate report is unsafe or exceeds the size limit")
                observed = json.loads(child_report.read_text(encoding="utf-8-sig"))
                validate_report(name, observed, measured)
                entry.update(passed=True, checks=len(observed["checks"]), report_sha256=checksum(child_report))
            except (OSError, ValueError) as error:
                entry["error"] = str(error)
            # Persist partial evidence even if a later gate is interrupted.
            (destination / "suite.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            if checksum(executable) != measured:
                raise ValueError("Executable changed; remaining gates were not run")
        report["passed"] = all(entry["passed"] for entry in report["gates"])
    except (OSError, ValueError) as error:
        report["error"] = str(error)
    finally:
        (destination / "suite.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--gates", nargs="+", choices=GATES, default=list(GATES))
    args = parser.parse_args()
    try:
        report = verify(args.executable, args.report_dir, args.gates)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + "\n")
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
