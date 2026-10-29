"""Owned NativeRuntime storage/lock/restart control, separate from screen admission."""

from __future__ import annotations

from pathlib import Path
import runpy
import time
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
MANAGER = runpy.run_path(str(HERE / "manager.py"))
REFERENCE = MANAGER["REFERENCE"]

from app.core.native.identity import IDENTITY_FILE
from app.core.native.runtime import NativeRuntime, NativeRuntimeError


def validate_storage(value: dict, name: str) -> None:
    expected = "owned-" + name
    if value != {"local": expected, "cookie": "glint-owned=" + expected}:
        raise ValueError("Owned profile storage is missing or crossed profile boundaries")


async def capture(executable: Path, owned: Path, server, report: dict, save) -> None:
    origin = f"http://127.0.0.1:{server.server_port}"
    configurations = {"A": REFERENCE["environment"].configuration_for_mode("manager-desktop"),
                      "B": REFERENCE["environment"].configuration_for_mode("manager-mobile-web")}
    runtimes = {name: NativeRuntime(owned / ("profile-" + name), executable, configuration)
                for name, configuration in configurations.items()}
    report.update(stages=[], lifecycle_checks={}, lifecycle_passed=False,
                  screen_consistency_passed=False, bfcache_verified=False,
                  process_swap_verified=False,
                  scope="Actual NativeRuntime.start/close, two simultaneous profiles, native ownership lock, isolated persistent cookies/localStorage and restarts; privacy policies disabled")
    pages, identities, baselines = {}, {}, {}
    cleanup = []
    primary = None

    async def start(name):
        runtime = runtimes[name]
        context = await runtime.start(headless=True)
        if runtime.native_policy_capabilities:
            raise ValueError("Unprotected NativeRuntime control unexpectedly admitted a privacy capability")
        session = await context.browser.new_browser_cdp_session()
        try:
            version = await session.send("Browser.getVersion")
            if (version["revision"] != "@" + report["chromium_revision"]
                    or version["product"] != "Chrome/" + report["chromium_version"]):
                raise ValueError("NativeRuntime browser differs from pinned version/revision")
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
        await page.goto(origin + "/screen?role=main", timeout=10000)
        pages[name] = page
        identity = (runtime.profile_dir / IDENTITY_FILE).read_bytes()
        if name in identities and identity != identities[name]:
            raise ValueError("NativeRuntime profile identity changed during restart")
        identities[name] = identity
        return page

    async def storage(name):
        value = await pages[name].evaluate("""() => ({
          local: localStorage.getItem('glint-owned'),
          cookie: document.cookie.split('; ').filter(value => value.startsWith('glint-owned=')).join('; ')
        })""")
        validate_storage(value, name)

    async def stage(label):
        row = {"name": label, "profiles": {}, "errors": [], "passed": False}
        report["stages"].append(row)
        for name, page in pages.items():
            await storage(name)
            observed = await MANAGER["LIFECYCLE"]["capture_page"](page)
            first = await page.evaluate("glintFirstScreen")
            REFERENCE["validate_snapshot"](first)
            if name not in baselines:
                baselines[name] = first["screen"]
            errors = MANAGER["validate_capture"](observed, configurations[name],
                configurations[name].context_options()["viewport"], baselines[name])
            if first["screen"] != baselines[name]:
                errors.append("Main first-script screen changed during profile lifecycle")
            row["profiles"][name] = {"observed": observed, "first_main": first,
                "storage_matches_owned_profile": True, "errors": errors}
            row["errors"].extend(name + "/" + error for error in errors)
            save()
        row["passed"] = not row["errors"]
        save()

    try:
        for name in runtimes:
            page = await start(name)
            empty = await page.evaluate("localStorage.getItem('glint-owned')")
            cookies = await runtimes[name].context.cookies(origin)
            if empty is not None or any(value["name"] == "glint-owned" for value in cookies):
                raise ValueError("Fresh NativeRuntime profile unexpectedly inherited owned storage")
            await page.evaluate("value => localStorage.setItem('glint-owned', value)", "owned-" + name)
            await runtimes[name].context.add_cookies([{"name": "glint-owned", "value": "owned-" + name,
                "url": origin, "expires": int(time.time()) + 3600}])
        if identities["A"] == identities["B"]:
            raise ValueError("Independent NativeRuntime profiles share a private identity")
        report["lifecycle_checks"].update(fresh_storage_empty=True, independent_private_identities=True)
        challenger = NativeRuntime(runtimes["A"].profile_dir, executable, configurations["A"])
        try:
            try:
                await challenger.start(headless=True)
            except NativeRuntimeError as error:
                if str(error) != "Another process owns this Native profile" or challenger.has_resources:
                    raise ValueError("Concurrent-profile rejection did not leave challenger resource-free") from error
                report["lifecycle_checks"]["duplicate_profile_lock_rejected"] = True
            else:
                raise ValueError("NativeRuntime allowed duplicate ownership of a running profile")
        finally:
            await challenger.close()
        try:
            await runtimes["A"].start(headless=True)
        except NativeRuntimeError as error:
            if str(error) != "Native profile is already running":
                raise
            report["lifecycle_checks"]["same_runtime_double_start_rejected"] = True
        else:
            raise ValueError("NativeRuntime accepted a second start on the same owner")
        await stage("simultaneous-profiles")
        for name, peer in (("A", "B"), ("B", "A")):
            await runtimes[name].close()
            del pages[name]
            if runtimes[name].has_resources:
                raise ValueError("Closed NativeRuntime retained resources")
            await storage(peer)
            report["lifecycle_checks"]["close_" + name + "_keeps_peer_storage"] = True
            await start(name)
            await storage(name)
            report["lifecycle_checks"]["restart_" + name + "_keeps_storage_and_identity"] = True
            await stage("restart-" + name)
        report["measurement_complete"] = True
        report["lifecycle_passed"] = all(report["lifecycle_checks"].values())
        report["screen_consistency_passed"] = all(row["passed"] for row in report["stages"])
    except BaseException as error:
        primary = error
        raise
    finally:
        for name, runtime in runtimes.items():
            try:
                await runtime.close()
                if runtime.has_resources:
                    raise ValueError("Owned NativeRuntime retained resources after final close")
            except Exception as error:
                cleanup.append(name + ": " + type(error).__name__ + ": " + str(error))
        report["cleanup_errors"].extend(cleanup)
        report["owned_runtimes_resource_free"] = not any(runtime.has_resources for runtime in runtimes.values())
        report["passed"] = (report.get("measurement_complete", False) and report["lifecycle_passed"]
            and report["screen_consistency_passed"] and report["owned_runtimes_resource_free"] and not cleanup)
        save()
        if cleanup and primary is None:
            raise ValueError("Owned NativeRuntime cleanup failed")
