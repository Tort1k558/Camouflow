"""Owned document first-script screen/DPR checks; not privacy or release admission."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import runpy
import struct
import sys
import threading
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[4]
FIXTURE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright

from scripts import capture_native_environment as environment
from scripts import native_build as build
from scripts.package_native_windows import validate_build_receipt
from scripts.verify_native_runtime import measure_runtime_core

MODES = ("manager-desktop", "manager-mobile-web", "native-control")
ROLES = {"main", "same", "cross", "nested-return", "srcdoc", "about-blank"}
SCREEN_FIELDS = {"width", "height", "availWidth", "availHeight", "availLeft", "availTop",
                 "colorDepth", "pixelDepth", "dpr", "orientation"}


def checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_snapshot(value: object, *, allow_pending_viewport: bool = False) -> None:
    if not isinstance(value, dict) or set(value) != {"screen", "viewport", "media"}:
        raise ValueError("Missing or malformed first-script snapshot")
    screen = value["screen"]
    if not isinstance(screen, dict) or set(screen) != SCREEN_FIELDS:
        raise ValueError("Incomplete screen snapshot")
    for key in SCREEN_FIELDS - {"dpr", "orientation"}:
        if type(screen[key]) is not int or (key not in {"availLeft", "availTop"} and screen[key] < 0):
            raise ValueError("Invalid screen dimension or depth")
    try:
        valid_dpr = type(screen["dpr"]) in (int, float) and math.isfinite(screen["dpr"]) and screen["dpr"] > 0
    except OverflowError:
        valid_dpr = False
    if screen["width"] <= 0 or screen["height"] <= 0 or not valid_dpr:
        raise ValueError("Invalid screen size or DPR")
    orientation = screen["orientation"]
    if (not isinstance(orientation, dict) or set(orientation) != {"type", "angle"}
            or type(orientation["type"]) is not str
            or orientation["type"] not in {"portrait-primary", "portrait-secondary", "landscape-primary", "landscape-secondary"}
            or type(orientation["angle"]) is not int or not 0 <= orientation["angle"] < 360):
        raise ValueError("Invalid screen orientation")
    if (not isinstance(value["viewport"], dict) or set(value["viewport"]) != {"width", "height"}
            or any(type(size) is not int or size < (0 if allow_pending_viewport else 1)
                   for size in value["viewport"].values())):
        raise ValueError("Invalid measured viewport")
    media = value["media"]
    if (not isinstance(media, dict) or set(media) != {"width", "height", "resolution"}
            or any(type(flag) is not bool for flag in media.values())):
        raise ValueError("Incomplete CSS media observation")


def validate_phase(observations: dict, screenshot_size: list[int], configuration, previous: dict | None) -> list[str]:
    if set(observations) != ROLES:
        raise ValueError("All six document contexts are required")
    if (not isinstance(screenshot_size, list) or len(screenshot_size) != 2
            or any(type(size) is not int or size <= 0 for size in screenshot_size)):
        raise ValueError("Invalid screenshot pixel dimensions")
    errors = []
    for role, observed in observations.items():
        if not isinstance(observed, dict) or set(observed) != {"first", "settled", "events", "clicks"}:
            raise ValueError("Incomplete document observation: " + role)
        for phase in ("first", "settled"):
            validate_snapshot(observed[phase], allow_pending_viewport=phase == "first" and role != "main")
    root = observations["main"]["first"]["screen"]
    for role, observed in observations.items():
        for phase in ("first", "settled"):
            if observed[phase]["screen"] != root:
                errors.append(role + "/" + phase + ": screen differs from main first script")
            if not all(observed[phase]["media"].values()):
                errors.append(role + "/" + phase + ": CSS media differs from DOM")
        clicks = observed["clicks"]
        if (clicks != [{"trusted": True, "x": 52, "y": 38, "inside": True}]
                or type(clicks[0]["trusted"]) is not bool or type(clicks[0]["inside"]) is not bool
                or type(clicks[0]["x"]) not in (int, float) or type(clicks[0]["y"]) not in (int, float)):
            errors.append(role + ": trusted local click coordinates changed")
    if previous is not None and root != previous:
        errors.append("Root screen changed across persistent restart")
    if configuration is None:
        settled = observations["main"]["settled"]
        expected_size = [round(settled["viewport"][axis] * settled["screen"]["dpr"]) for axis in ("width", "height")]
    else:
        requested = (configuration.width, configuration.height, configuration.device_scale_factor)
        if (root["width"], root["height"], root["dpr"]) != requested:
            errors.append("Main first script differs from requested manager screen/DPR")
        expected_size = [round(configuration.width * configuration.device_scale_factor),
                         round(configuration.height * configuration.device_scale_factor)]
    if screenshot_size != expected_size:
        errors.append("Screenshot pixel dimensions differ from measured/requested viewport")
    return errors


def install_observers(page, row: dict, pending: Counter) -> None:
    page.on("pageerror", lambda error: row["page_errors"].append(str(error)))
    page.on("request", lambda request: pending.update([request.url]))

    def finished(request):
        pending.subtract([request.url])

    page.on("requestfinished", finished)
    page.on("requestfailed", finished)
    page.on("domcontentloaded", lambda _: row["lifecycle_events"].append("domcontentloaded"))
    page.on("load", lambda _: row["lifecycle_events"].append("load"))


async def capture(executable: Path, owned: Path, server, report: dict, save) -> None:
    async with async_playwright() as driver:
        for mode in MODES:
            configuration = environment.configuration_for_mode(mode)
            options = {"no_viewport": True} if configuration is None else configuration.context_options()
            arguments = ["--enable-automation"]
            if configuration is not None:
                arguments.extend(configuration.launch_arguments())
            previous = None
            for phase in ("initial", "persistent-profile-restart"):
                row = {"mode": mode, "phase": phase, "passed": False, "observations": {},
                       "page_errors": [], "lifecycle_events": []}
                report["phases"].append(row)
                save()
                context = await driver.chromium.launch_persistent_context(
                    str(owned / mode / "profile"), executable_path=str(executable), headless=True,
                    chromium_sandbox=True, timeout=30000, args=arguments, **options)
                browser = context.browser
                primary = None
                page = None
                pending = Counter()
                try:
                    session = await browser.new_browser_cdp_session()
                    try:
                        version = await session.send("Browser.getVersion")
                        if (version["revision"] != "@" + report["chromium_revision"]
                                or version["product"] != "Chrome/" + report["chromium_version"]):
                            raise ValueError("Browser version/revision differs from checkpoint")
                        row["browser_version"] = version
                    finally:
                        await session.detach()

                    async def route(request):
                        address = urlsplit(request.request.url)
                        if (address.scheme == "http" and address.hostname in {"127.0.0.1", "localhost"}
                                and address.port == server.server_port):
                            await request.continue_()
                        else:
                            await request.abort("blockedbyclient")

                    await context.route("**/*", route)
                    page = context.pages[0] if context.pages else await context.new_page()
                    install_observers(page, row, pending)
                    await page.goto(f"http://127.0.0.1:{server.server_port}/screen?role=main", timeout=10000)
                    frames = {frame.name or "main": frame for frame in page.frames}
                    if set(frames) != ROLES or len(page.frames) != len(ROLES):
                        raise ValueError("First-script fixture frame coverage differs")
                    for role in sorted(ROLES):
                        frame = frames[role]
                        await frame.locator("#probe").click(timeout=10000)
                        row["observations"][role] = await frame.evaluate("""() => ({
                          first: window.glintFirstScreen, settled: window.glintSampleScreen(),
                          events: window.glintScreenChanges, clicks: window.glintTrustedClicks
                        })""")
                        save()
                    png = await page.screenshot()
                    if png[:8] != b"\x89PNG\r\n\x1a\n" or len(png) < 24:
                        raise ValueError("Browser did not produce a PNG screenshot")
                    row["screenshot"] = {"size": list(struct.unpack(">II", png[16:24])),
                                         "sha256": hashlib.sha256(png).hexdigest()}
                    (owned / (mode + "-" + phase + ".png")).write_bytes(png)
                    row["first_viewport_pending"] = sorted(role for role, observed in row["observations"].items()
                        if 0 in observed["first"]["viewport"].values())
                    row["errors"] = validate_phase(row["observations"], row["screenshot"]["size"], configuration, previous)
                    previous = row["observations"]["main"]["first"]["screen"]
                    row["passed"] = not row["errors"] and not row["page_errors"]
                except BaseException as error:
                    primary = error
                    row.update(error_type=type(error).__name__, error=str(error))
                    row["pending_requests_at_error"] = {url: count for url, count in pending.items() if count > 0}
                    if page is not None:
                        row["frames_at_error"] = [{"name": frame.name, "url": frame.url,
                                                   "detached": frame.is_detached()} for frame in page.frames]
                    raise
                finally:
                    try:
                        await context.close()
                    except Exception as error:
                        row.update(passed=False, cleanup_error_type=type(error).__name__, cleanup_error=str(error))
                        if primary is None:
                            raise
                        primary.add_note("Owned context cleanup failed: " + str(error))
                    finally:
                        row["browser_connection_closed"] = not browser.is_connected()
                        row["passed"] = row["passed"] and row["browser_connection_closed"]
                        save()
    report["measurement_complete"] = True
    report["passed"] = all(row["passed"] for row in report["phases"])


def verify(executable: Path, owned: Path, checkpoint_name: str) -> dict:
    if sys.platform != "win32" or not re.fullmatch(r"001-\d{3}", checkpoint_name):
        raise ValueError("Use Windows and an explicit upstream-156 checkpoint name")
    if (not executable.is_absolute() or executable.drive.upper() != "D:" or executable != executable.resolve()
            or executable.name != "chrome.exe" or not executable.is_file()
            or any(parent.name.casefold() == "src" and parent.parent.name.casefold() == "chromium"
                   for parent in executable.parents)):
        raise ValueError("Select a preserved canonical D: runtime outside the active Chromium checkout")
    if (not owned.is_absolute() or owned.drive.upper() != "D:" or owned != owned.resolve()
            or not owned.parent.is_dir() or owned.exists() or owned.is_relative_to(ROOT)
            or owned.is_relative_to(executable.parent) or executable.is_relative_to(owned)):
        raise ValueError("Evidence requires a fresh canonical D: directory outside code and runtime")
    selected = build.load_candidate("upstream-156")
    checkpoint_path = selected["directory"] / "checkpoints" / (checkpoint_name + ".json")
    checkpoint = json.loads(checkpoint_path.read_bytes())
    if selected["manifest"]["patches"][:len(checkpoint["patches"])] != checkpoint["patches"]:
        raise ValueError("Checkpoint is not an exact prefix of selected sources")
    candidate = {**selected, "manifest": checkpoint, "manifest_sha256": checksum(checkpoint_path)}
    receipt_path = executable.parent / "camouflow-build.json"
    receipt_raw = receipt_path.read_bytes()
    receipt = json.loads(receipt_raw)
    validate_build_receipt(receipt, candidate["lock"], candidate=candidate)
    core = measure_runtime_core(executable)
    if receipt.get("runtime_core_sha256_measured") != core:
        raise ValueError("Runtime core differs from checkpoint receipt")
    paths = {Path(__file__).resolve(), FIXTURE / "server.py", FIXTURE / "sample.js", checkpoint_path,
             ROOT / "scripts/native_build.py", ROOT / "scripts/package_native_windows.py"}
    paths.update(ROOT / name for name in environment.source_inputs())
    inputs = {path: checksum(path) for path in paths}
    owned.mkdir(exist_ok=False)
    report = {"schema": 1, "passed": False, "measurement_complete": False, "phases": [],
              "scope": __doc__, "checkpoint": checkpoint_name,
              "checkpoint_sha256": candidate["manifest_sha256"],
              "chromium_revision": candidate["lock"]["chromium_revision"],
              "chromium_version": candidate["lock"]["chromium_version"],
              "runtime_core_sha256_measured": core, "receipt_sha256": hashlib.sha256(receipt_raw).hexdigest(),
              "source_sha256": {path.relative_to(ROOT).as_posix(): value for path, value in inputs.items()},
              "privacy_admitted": False, "production_admitted": False, "postguards_passed": False}

    def save():
        (owned / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")

    save()
    server = None
    thread = None
    try:
        server = runpy.run_path(str(FIXTURE / "server.py"))["create_server"]()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        asyncio.run(capture(executable, owned, server, report, save))
    except Exception as error:
        report.update(passed=False, error_type=type(error).__name__, error=str(error))
    finally:
        if server is not None:
            if thread is not None and thread.is_alive():
                server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)
        try:
            report["postguards_passed"] = ((thread is None or not thread.is_alive())
                and measure_runtime_core(executable) == core and receipt_path.read_bytes() == receipt_raw
                and all(checksum(path) == value for path, value in inputs.items()))
        except Exception as error:
            report.update(postguards_passed=False, postguard_error_type=type(error).__name__, postguard_error=str(error))
        report["passed"] = report["passed"] and report["postguards_passed"]
        save()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", required=True)
    args = parser.parse_args()
    try:
        report = verify(args.executable, args.work_dir, args.checkpoint)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({key: report.get(key) for key in ("passed", "measurement_complete", "postguards_passed", "error")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
