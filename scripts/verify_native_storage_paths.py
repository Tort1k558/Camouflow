"""Owned Windows storage path regression matrix; never use customer profiles."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import threading
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.native.configuration import NativeConfiguration  # noqa: E402
from app.core.native.runtime import NativeRuntime  # noqa: E402
from scripts.verify_native_runtime import FixtureHandler, FixtureServer, STORAGE, measure_runtime_core  # noqa: E402

LENGTHS = (90, 130, 150, 170)


def profile_for_length(root: Path, length: int, name: str) -> Path:
    suffix = Path(name) / "native"
    padding = length - len(str(root)) - len(str(suffix)) - 2
    if padding < 1 or padding > 200:
        raise ValueError("Work directory cannot accommodate the requested path matrix")
    profile = root / ("p" * padding) / suffix
    if len(str(profile)) != length:
        raise ValueError("Profile path length differs from the requested case")
    return profile


def expected_storage(value: str) -> dict:
    return {"cookie": "owned=" + value, "local": value, "indexed": value,
            "cached": value, "workers": 1}


async def verify(executable: Path, root: Path, origin: str, report: dict) -> None:
    # Validate every path before opening a browser; never silently skip a case.
    profiles = {(length, mobile): profile_for_length(root, length, "mobile" if mobile else "desktop")
                for length in LENGTHS for mobile in (False, True)}
    for (length, mobile), profile in profiles.items():
        config = (NativeConfiguration(environment="mobile_web", width=390, height=844,
                                      device_scale_factor=3, locale="de-DE", timezone="Europe/Berlin")
                  if mobile else NativeConfiguration())
        runtime = NativeRuntime(profile, executable, config)
        entry = {"profile_length": length, "environment": config.environment,
                 "passed": False, "phases": []}
        report["checks"].append(entry)
        try:
            for phase, value in (("create", "first"), ("replace", "replacement"), ("restart", None)):
                context = await runtime.start(headless=True)
                try:
                    page = context.pages[0]
                    await page.goto(origin, timeout=30000)
                    observed = await asyncio.wait_for(page.evaluate(STORAGE, value), timeout=30)
                    if observed != expected_storage(value or "replacement"):
                        raise ValueError("Storage readback differs from committed content")
                    if phase == "restart":
                        deleted = await asyncio.wait_for(page.evaluate("""async () => {
                          const cache = await caches.open('owned-native');
                          const entry = await cache.delete('/owned-value');
                          const absent = !(await cache.match('/owned-value'));
                          const removed = await caches.delete('owned-native');
                          return entry && absent && removed && !(await caches.has('owned-native'));
                        }"""), timeout=30)
                        if deleted is not True:
                            raise ValueError("Cache entry or directory deletion failed")
                    entry["phases"].append({"name": phase, "passed": True})
                finally:
                    await runtime.close()
            entry["passed"] = True
        except Exception as error:
            entry.update(error=str(error), traceback=traceback.format_exc())
        finally:
            await runtime.close()
    report["passed"] = len(report["checks"]) == len(LENGTHS) * 2 and all(
        check["passed"] for check in report["checks"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.report.is_symlink():
        parser.error("Use a new report path to preserve previous evidence")
    report = {"schema": 1, "platform": sys.platform, "passed": False, "checks": [],
              "scope": "Owned storage path compatibility; not fingerprint capability admission"}
    server = None
    thread = None
    try:
        if sys.platform != "win32":
            raise ValueError("This storage path matrix currently supports Windows only")
        executable = args.executable.resolve(strict=True)
        work = args.work_dir.resolve(strict=True)
        if not work.is_dir() or not executable.is_file():
            raise ValueError("Existing work directory and browser executable are required")
        core = measure_runtime_core(executable)
        report["runtime_core_sha256_measured"] = core
        report["binary_sha256_measured"] = core[executable.name]
        server = FixtureServer(("127.0.0.1", 0), FixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        with tempfile.TemporaryDirectory(prefix="np-", dir=work) as owned:
            asyncio.run(verify(executable, Path(owned), f"http://127.0.0.1:{server.server_port}", report))
        if measure_runtime_core(executable) != core:
            raise ValueError("Native runtime code changed during storage verification")
    except Exception as error:
        report.update(passed=False, error=str(error), traceback=traceback.format_exc())
    finally:
        if server is not None:
            if thread is not None and thread.is_alive():
                server.shutdown()
                thread.join()
            server.server_close()
    with args.report.open("x", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(report, indent=2))
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
