"""Screen lifecycle through manager context options and one Playwright controller."""

from __future__ import annotations

import asyncio
from pathlib import Path
import runpy
import struct
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
LIFECYCLE = runpy.run_path(str(HERE / "lifecycle.py"))
REFERENCE = LIFECYCLE["REFERENCE"]
ROLES = REFERENCE["ROLES"]
MODES = ("manager-desktop", "manager-mobile-web")


def validate_capture(observed: dict, configuration, viewport: dict, baseline: dict) -> list[str]:
    errors = LIFECYCLE["validate_page"](observed, baseline)
    root = observed["main"]["snapshot"]
    if root["viewport"] != viewport:
        errors.append("Main viewport differs from the requested Playwright viewport")
    if (baseline["width"], baseline["height"], baseline["dpr"]) != (
            configuration.width, configuration.height, configuration.device_scale_factor):
        errors.append("Initial main screen differs from manager context options")
    return errors


async def capture(executable: Path, owned: Path, server, report: dict, save) -> None:
    report.update(stages=[], scope="Manager context_options/launch_arguments, two tabs per persistent profile, viewport updates and restart; no policy or package admission",
                  extra_page_cdp_sessions=False, full_native_runtime_lifecycle_verified=False,
                  bfcache_verified=False, process_swap_verified=False)
    origin = f"http://127.0.0.1:{server.server_port}"
    alternate = f"http://localhost:{server.server_port}"
    async with REFERENCE["async_playwright"]() as driver:
        for mode in MODES:
            configuration = REFERENCE["environment"].configuration_for_mode(mode)
            options = configuration.context_options()
            arguments = configuration.launch_arguments()
            baseline = None
            for phase in ("initial", "restart"):
                context = await driver.chromium.launch_persistent_context(
                    str(owned / mode), executable_path=str(executable), headless=True,
                    chromium_sandbox=True, timeout=30000, args=arguments, **options)
                browser = context.browser
                try:
                    session = await browser.new_browser_cdp_session()
                    try:
                        version = await session.send("Browser.getVersion")
                        if (version["revision"] != "@" + report["chromium_revision"]
                                or version["product"] != "Chrome/" + report["chromium_version"]):
                            raise ValueError("Manager browser differs from pinned version/revision")
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
                    pages = {"A": context.pages[0] if context.pages else await context.new_page(),
                             "B": await context.new_page()}
                    for page in tuple(context.pages):
                        if page not in pages.values():
                            await page.close()
                    viewports = {name: dict(options["viewport"]) for name in pages}
                    for page in pages.values():
                        await page.goto(origin + "/screen?role=main", timeout=10000)

                    async def stage(name, changed=None):
                        nonlocal baseline
                        row = {"mode": mode, "phase": phase, "name": name,
                               "pages": {}, "errors": [], "passed": False}
                        report["stages"].append(row)
                        for key, page in pages.items():
                            observed = await LIFECYCLE["capture_page"](page)
                            first = await page.evaluate("glintFirstScreen")
                            REFERENCE["validate_snapshot"](first)
                            if baseline is None:
                                baseline = first["screen"]
                            errors = validate_capture(observed, configuration, viewports[key], baseline)
                            if first["screen"] != baseline:
                                errors.append("Main first-script identity changed across tabs/navigation/restart")
                            frames = {frame.name or "main": frame for frame in page.frames}
                            trusted_clicks = {}
                            for role, frame in frames.items():
                                await frame.locator("#probe").click(timeout=10000)
                                clicks = await frame.evaluate("glintTrustedClicks")
                                trusted_clicks[role] = clicks
                                if not clicks or clicks[-1] != {"trusted": True, "x": 52, "y": 38, "inside": True}:
                                    errors.append(role + ": trusted click differs from local coordinates")
                            touch = await page.evaluate("navigator.maxTouchPoints")
                            if (touch > 0) != (configuration.environment == "mobile_web"):
                                errors.append("Touch capability differs from manager context options")
                            png = await page.screenshot()
                            if len(png) < 24 or png[:8] != b"\x89PNG\r\n\x1a\n":
                                raise ValueError("Manager screenshot is not PNG")
                            dimensions = list(struct.unpack(">II", png[16:24]))
                            expected_size = [round(viewports[key][axis] * configuration.device_scale_factor)
                                             for axis in ("width", "height")]
                            if dimensions != expected_size:
                                errors.append("Screenshot differs from requested viewport and DPR")
                            item = {"observed": observed, "first_main": first, "errors": errors,
                                    "trusted_clicks": trusted_clicks,
                                    "screenshot_size": dimensions, "touch_points": touch,
                                    "requested_viewport": dict(viewports[key])}
                            if changed is not None and key != changed:
                                previous = report["stages"][-2]["pages"][key]["observed"]
                                stable = all(previous[role]["snapshot"] == observed[role]["snapshot"] for role in ROLES)
                                item["unchanged_by_other_page"] = stable
                                if not stable:
                                    errors.append("Other tab operation changed screen/viewport/CSS")
                            row["pages"][key] = item
                            row["errors"].extend(key + "/" + error for error in errors)
                            (owned / (mode + "-" + phase + "-" + name + "-" + key + ".png")).write_bytes(png)
                            save()
                        row["passed"] = not row["errors"]
                        save()

                    await stage("baseline")
                    for key, viewport in (("A", {"width": 1000, "height": 700}),
                                          ("B", {"width": 420, "height": 900})):
                        await pages[key].set_viewport_size(viewport)
                        viewports[key] = viewport
                        await stage("resize-" + key, key)
                    await pages["B"].goto(alternate + "/screen?role=main&navigation=1", timeout=10000)
                    await stage("cross-site-navigation", "B")
                    await pages["A"].close()
                    del pages["A"]
                    await stage("close-peer")
                finally:
                    await context.close()
                    if browser.is_connected():
                        raise ValueError("Manager browser remained connected after context close")
        report["measurement_complete"] = True
        report["passed"] = all(row["passed"] for row in report["stages"])
        save()
