"""Owned NativeRuntime history checks without competing device-metrics overrides."""

from __future__ import annotations

from pathlib import Path
import runpy
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
LIFECYCLE = runpy.run_path(str(HERE / "lifecycle.py"))
INTERACTION = runpy.run_path(str(HERE / "history_interaction.py"))
REFERENCE = LIFECYCLE["REFERENCE"]

from app.core.native.runtime import NativeRuntime


def expected_screen(configuration, baseline: dict) -> dict:
    return LIFECYCLE["expected_screen"](baseline, {
        "width": configuration.width, "height": configuration.height,
        "deviceScaleFactor": configuration.device_scale_factor,
        "mobile": configuration.environment == "mobile_web",
    })


async def capture(executable: Path, owned: Path, server, report: dict, save) -> None:
    report.update(runs=[], scope="Actual NativeRuntime desktop/mobile-web, two tabs, peer close, cross-site navigation and requested genuine BFCache, initial and persistent restart; disabled BFCache remains a failed gate",
                  device_metrics_commands_sent=False, all_frame_input_verified=False,
                  process_swap_verified=False, protected_policies_enabled=False,
                  full_lifecycle_admitted=False, privacy_admitted=False, production_admitted=False)
    origin = f"http://127.0.0.1:{server.server_port}"
    alternate = f"http://localhost:{server.server_port}"
    for mode in ("manager-desktop", "manager-mobile-web"):
        configuration = REFERENCE["environment"].configuration_for_mode(mode)
        baseline = None
        for phase in ("initial", "persistent-profile-restart"):
            run = {"mode": mode, "phase": phase, "stages": [], "passed": False,
                   "measurement_complete": False, "fixture_port": server.server_port,
                   "cleanup_errors": []}
            report["runs"].append(run)
            runtime = NativeRuntime(owned / mode, executable, configuration)
            session = None
            primary = None
            try:
                await runtime.start(headless=True)
                context = runtime.context
                metadata_page = context.pages[0] if context.pages else await context.new_page()
                await metadata_page.goto("chrome://version", timeout=10000)
                command_line = await metadata_page.locator("#command_line").inner_text(timeout=10000)
                if not command_line.strip():
                    raise ValueError("Owned browser command line could not be observed")
                run["bfcache_disabled_by_driver"] = "--disable-back-forward-cache" in command_line.split()
                run["driver_cache_policy_source"] = "chrome://version#command_line; only BFCache switch retained"
                browser_session = await context.browser.new_browser_cdp_session()
                try:
                    version = await browser_session.send("Browser.getVersion")
                    if (version["revision"] != "@" + report["chromium_revision"]
                            or version["product"] != "Chrome/" + report["chromium_version"]):
                        raise ValueError("Managed history runtime differs from pinned version/revision")
                finally:
                    await browser_session.detach()

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
                for page in pages.values():
                    await page.goto(origin + "/screen?role=main", timeout=10000)

                async def stage(name):
                    nonlocal baseline
                    row = {"name": name, "pages": {}, "errors": [], "passed": False}
                    run["stages"].append(row)
                    for key, page in pages.items():
                        observed = await LIFECYCLE["capture_page"](page)
                        first = await page.evaluate("glintFirstScreen")
                        REFERENCE["validate_snapshot"](first)
                        if baseline is None:
                            baseline = expected_screen(configuration, first["screen"])
                        errors = LIFECYCLE["validate_page"](observed, baseline)
                        if first["screen"] != baseline:
                            errors.append("First-script screen differs from configured persistent identity")
                        row["pages"][key] = {"observed": observed, "first_main": first, "errors": errors}
                        row["errors"].extend(key + "/" + error for error in errors)
                    row["passed"] = not row["errors"]
                    save()
                    return row

                await stage("baseline")
                await pages["B"].goto(alternate + "/screen?role=main&navigation=1", timeout=10000)
                await stage("cross-site-navigation")
                await pages["A"].close()
                del pages["A"]
                previous = await stage("close-peer")
                session = await context.new_cdp_session(pages["B"])
                await session.send("Page.enable")
                run["bfcache_not_used"] = []
                session.on("Page.backForwardCacheNotUsed", lambda event: run["bfcache_not_used"].append(event))
                state = await LIFECYCLE["restore_history"](
                    pages["B"], session, previous["pages"]["B"]["observed"], run)
                run["bfcache_state"] = state
                run["bfcache_restored"] = (LIFECYCLE["history_restored"](state)
                    and run["history_navigation"].get("type") == "BackForwardCacheRestore")
                if run["bfcache_restored"]:
                    observed = LIFECYCLE["restored_observations"](state)
                    errors = LIFECYCLE["validate_page"](observed, baseline)
                    screenshots = owned / (mode + "-" + phase)
                    screenshots.mkdir(exist_ok=False)
                    interaction = await INTERACTION["capture"](session, screenshots)
                    run["restored_main_interaction"] = interaction
                    if not interaction["passed"]:
                        errors.append("Restored main trusted input/screenshot failed")
                else:
                    # A replaced document permits normal Frame APIs, but cannot pass the BFCache gate.
                    await pages["B"].wait_for_load_state("load", timeout=10000)
                    observed = await LIFECYCLE["capture_page"](pages["B"])
                    errors = LIFECYCLE["validate_page"](observed, baseline)
                    run["history_reload_screen_passed"] = not errors
                    errors.append("Genuine BFCache restore required; driver explicitly disabled BFCache"
                        if run["bfcache_disabled_by_driver"] else "Genuine BFCache restore was not observed")
                run["stages"].append({"name": "history-return", "pages": {"B": {"observed": observed}},
                                      "errors": errors, "passed": not errors})
                run["measurement_complete"] = True
                run["passed"] = all(row["passed"] for row in run["stages"])
                save()
            except BaseException as error:
                primary = error
                raise
            finally:
                if session is not None:
                    try:
                        await session.detach()
                    except Exception as error:
                        run["cleanup_errors"].append(str(error))
                try:
                    await runtime.close()
                except Exception as error:
                    run["cleanup_errors"].append(str(error))
                    if primary is None:
                        raise
                    primary.add_note("Managed history cleanup failed: " + str(error))
                finally:
                    run["runtime_handles_released"] = runtime.context is None and runtime.playwright is None
                    run["passed"] = run["passed"] and run["runtime_handles_released"] and not run["cleanup_errors"]
                    save()
                if run["cleanup_errors"] and primary is None:
                    raise ValueError("Managed history session cleanup failed")
    report["measurement_complete"] = all(run["measurement_complete"] for run in report["runs"])
    report["passed"] = report["measurement_complete"] and all(run["passed"] for run in report["runs"])
    save()
