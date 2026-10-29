"""Cross-process NativeRuntime ownership control; never crash/privacy admission."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import runpy
import sys

HERE = Path(__file__).resolve().parent
REFERENCE = runpy.run_path(str(HERE / "verify.py"))

from app.core.native.configuration import NativeConfiguration
from app.core.native.identity import IDENTITY_FILE
from app.core.native.runtime import NativeRuntime, NativeRuntimeError


async def probe(profile: Path, executable: Path) -> dict:
    runtime = NativeRuntime(profile, executable, NativeConfiguration())
    result = {"started": False, "rejected_by_lock": False, "resource_free": False}
    try:
        await runtime.start(headless=True)
        result["started"] = True
    except NativeRuntimeError as error:
        if str(error) != "Another process owns this Native profile":
            raise
        result["rejected_by_lock"] = True
    finally:
        await runtime.close()
        result["resource_free"] = not runtime.has_resources
    return result


def validate_probe(value: object, *, blocked: bool) -> None:
    expected = {"started": not blocked, "rejected_by_lock": blocked, "resource_free": True}
    if (not isinstance(value, dict) or value != expected
            or any(type(flag) is not bool for flag in value.values())):
        raise ValueError("Cross-process owner result differs from the required lock state")


async def child_probe(profile: Path, executable: Path, report: dict) -> dict:
    process = await asyncio.create_subprocess_exec(sys.executable, str(Path(__file__).resolve()),
        "--probe", str(profile), str(executable), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    row = {"returncode": None, "completed": False}
    report["child_processes"].append(row)
    try:
        output, error = await asyncio.wait_for(process.communicate(), timeout=90)
    except BaseException:
        if process.returncode is None:
            process.terminate()
        await process.wait()
        row.update(returncode=process.returncode, terminated=True)
        raise
    row.update(returncode=process.returncode, completed=True)
    if process.returncode != 0:
        row["stderr"] = error.decode("utf-8", errors="replace")
        raise ValueError("Owned NativeRuntime child failed")
    result = json.loads(output)
    row["result"] = result
    return result


async def capture(executable: Path, owned: Path, server, report: dict, save) -> None:
    profile = owned / "profile"
    runtime = NativeRuntime(profile, executable, NativeConfiguration())
    report.update(child_processes=[], cross_process_owner_rejection_verified=False,
                  released_lock_reacquired_by_child=False, owner_unchanged_after_rejection=False,
                  private_identity_unchanged=False, crash_recovery_verified=False,
                  scope="Actual NativeRuntime owner plus separate Python processes: reject while owned, then acquire after orderly close; unprotected headless control only")
    try:
        context = await runtime.start(headless=True)
        session = await context.browser.new_browser_cdp_session()
        try:
            version = await session.send("Browser.getVersion")
            if (version["revision"] != "@" + report["chromium_revision"]
                    or version["product"] != "Chrome/" + report["chromium_version"]):
                raise ValueError("Owned runtime differs from pinned Chromium version/revision")
        finally:
            await session.detach()
        identity = (profile / IDENTITY_FILE).read_bytes()
        validate_probe(await child_probe(profile, executable, report), blocked=True)
        report["cross_process_owner_rejection_verified"] = True
        page = context.pages[0] if context.pages else await context.new_page()
        if not context.browser.is_connected() or await page.evaluate("1 + 1") != 2:
            raise ValueError("Rejected challenger disrupted the existing browser owner")
        report["owner_unchanged_after_rejection"] = True
        save()
        await runtime.close()
        if runtime.has_resources:
            raise ValueError("Parent retained runtime resources after close")
        validate_probe(await child_probe(profile, executable, report), blocked=False)
        report["released_lock_reacquired_by_child"] = True
        if (profile / IDENTITY_FILE).read_bytes() != identity:
            raise ValueError("Private identity changed across process ownership handoff")
        report["private_identity_unchanged"] = True
        report["measurement_complete"] = True
        report["passed"] = True
    finally:
        await runtime.close()
        report["parent_resource_free"] = not runtime.has_resources
        report["passed"] = report.get("passed", False) and report["parent_resource_free"]
        save()


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "--probe":
        raise SystemExit("Use through the owned runtime-control harness")
    print(json.dumps(asyncio.run(probe(Path(sys.argv[2]), Path(sys.argv[3])))))
