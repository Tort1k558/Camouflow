"""Owned logical-screen lifecycle collector; no package/privacy admission."""

from __future__ import annotations

import asyncio
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import runpy
import secrets
import struct

HERE = Path(__file__).resolve().parent
REFERENCE = runpy.run_path(str(HERE / "verify.py"))
FIXTURE = runpy.run_path(str(HERE / "server.py"))
ROLES = REFERENCE["ROLES"]

STEPS = (
    ("set-a", "A", {"width": 1366, "height": 768, "deviceScaleFactor": 1, "mobile": False}),
    ("set-b", "B", {"width": 390, "height": 844, "deviceScaleFactor": 3, "mobile": True}),
    ("update-a", "A", {"width": 1280, "height": 720, "deviceScaleFactor": 2, "mobile": False}),
    ("clear-a", "A", None),
)

INSTALL_HISTORY = """spec => {
  if (Object.hasOwn(window, 'glintHistoryProbe')) throw new Error('History probe already installed');
  const state = {token: spec.token, events: []};
  window.glintHistoryProbe = state;
  addEventListener('pageshow', event => state.events.push(event.persisted));
  addEventListener('message', event => {
    const data = event.data;
    if (!data || data.kind !== 'owned-glint-history-request' || data.token !== spec.token ||
        event.source !== parent || !spec.allowedOrigins.includes(event.origin)) return;
    const respond = () => {
      const children = {};
      for (const frame of document.querySelectorAll('iframe')) {
        children[frame.name] = {width: frame.clientWidth, height: frame.clientHeight};
      }
      top.postMessage({kind: 'owned-glint-history-response', token: spec.token,
        role: spec.role, parent: spec.parent, origin: self.origin, location: location.href,
        persisted: state.events.some(value => value === true), snapshot: glintSampleScreen(),
        children_sizes: children}, spec.rootOrigin);
    };
    if (state.events.some(value => value === true)) respond();
    else addEventListener('pageshow', respond, {once: true});
    for (let index = 0; index < frames.length; index += 1) {
      frames[index].postMessage(data, '*');
    }
  });
}"""

COLLECT_HISTORY = """async spec => {
  const state = window.glintHistoryProbe;
  if (!state || state.token !== spec.token) {
    return {registered: false, events: null, snapshots: {}, protocolErrors: [], timedOut: false};
  }
  return await new Promise(resolve => {
    const snapshots = {};
    const errors = [];
    let timer;
    const finish = timedOut => {
      clearTimeout(timer);
      removeEventListener('message', receive);
      resolve({registered: true, events: state.events.slice(), snapshots,
               protocolErrors: errors, timedOut});
    };
    const receive = event => {
      const value = event.data;
      if (!value || value.kind !== 'owned-glint-history-response' || value.token !== spec.token) return;
      if (!Object.hasOwn(spec.origins, value.role) || event.origin !== spec.origins[value.role] ||
          value.origin !== event.origin) {
        errors.push('Response origin/role differs from owned pre-navigation document');
        return;
      }
      if (Object.hasOwn(snapshots, value.role)) {
        errors.push('Duplicate document response');
        return;
      }
      snapshots[value.role] = {snapshot: value.snapshot, origin: value.origin, location: value.location,
        parent: value.parent, persisted: value.persisted, children_sizes: value.children_sizes};
      if (Object.keys(snapshots).length === Object.keys(spec.origins).length) finish(false);
    };
    addEventListener('message', receive);
    timer = setTimeout(() => finish(true), 3000);
    postMessage({kind: 'owned-glint-history-request', token: spec.token}, self.origin);
  });
}"""


class CacheableHandler(FIXTURE["Handler"]):
    def send_header(self, keyword, value):
        if keyword.lower() == "cache-control":
            value = "public, max-age=60"
        super().send_header(keyword, value)


def create_server():
    return ThreadingHTTPServer(("127.0.0.1", 0), CacheableHandler)


def metrics_parameters(settings: dict) -> dict:
    return {**settings, "screenWidth": settings["width"], "screenHeight": settings["height"],
            "screenOrientation": {"type": "portraitPrimary" if settings["mobile"] else "landscapePrimary",
                                  "angle": 0}}


def expected_screen(baseline: dict, settings: dict | None) -> dict:
    if settings is None:
        return dict(baseline)
    return {**baseline, "width": settings["width"], "height": settings["height"],
            "availWidth": settings["width"], "availHeight": settings["height"],
            "availLeft": 0, "availTop": 0, "dpr": settings["deviceScaleFactor"],
            "orientation": {"type": "portrait-primary" if settings["mobile"] else "landscape-primary", "angle": 0}}


def validate_page(observed: dict, expected: dict) -> list[str]:
    if set(observed) != ROLES:
        raise ValueError("Lifecycle capture requires six named document slots")
    errors = []
    for role, row in observed.items():
        REFERENCE["validate_snapshot"](row["snapshot"])
        if row["snapshot"]["screen"] != expected:
            errors.append(role + ": logical screen differs from requested state")
        if not all(row["snapshot"]["media"].values()):
            errors.append(role + ": CSS media differs from DOM")
        if role != "main" and row["snapshot"]["viewport"] != row["embedding_size"]:
            errors.append(role + ": child viewport differs from its own embedding box")
    return errors


def history_restored(observed: object) -> bool:
    return (isinstance(observed, dict) and observed.get("registered") is True
            and isinstance(observed.get("events"), list)
            and all(type(event) is bool for event in observed["events"])
            and any(event is True for event in observed["events"]))


def restored_observations(state: dict) -> dict:
    if (not history_restored(state) or state.get("timedOut") is not False
            or state.get("protocolErrors") != [] or set(state.get("snapshots", {})) != ROLES):
        raise ValueError("Retained BFCache document coverage is incomplete")
    observed = {role: dict(row) for role, row in state["snapshots"].items()}
    for role, row in observed.items():
        if row.get("persisted") is not True:
            raise ValueError("BFCache pageshow.persisted missing for " + role)
        REFERENCE["validate_snapshot"](row["snapshot"])
        if role != "main":
            parent = observed.get(row.get("parent"))
            if parent is None or role not in parent["children_sizes"]:
                raise ValueError("Restored parent/embedding coverage is incomplete")
            row["embedding_size"] = dict(parent["children_sizes"][role])
    return observed


async def restore_history(page, session, expected: dict, report: dict) -> dict:
    # Playwright explicitly does not support BFCache navigation/Page state.
    # After restoration use CDP and ordinary owned postMessage responders only.
    frames = {frame.name or "main": frame for frame in page.frames}
    if set(frames) != ROLES or len(page.frames) != len(ROLES):
        raise ValueError("History probe requires all six owned documents")
    token = secrets.token_hex(16)
    root_origin = expected["main"]["origin"]
    origins = {role: row["origin"] for role, row in expected.items()}
    for role, frame in frames.items():
        await frame.evaluate(INSTALL_HISTORY, {"token": token, "role": role, "rootOrigin": root_origin,
            "parent": None if frame.parent_frame is None else (frame.parent_frame.name or "main"),
            "allowedOrigins": sorted(set(origins.values()))})
    history = await session.send("Page.getNavigationHistory")
    entry = history["entries"][history["currentIndex"]]
    await page.goto(f"http://127.0.0.1:{report['fixture_port']}/screen?role=main&navigation=2", timeout=10000)
    navigation = asyncio.get_running_loop().create_future()

    def navigated(event):
        frame = event["frame"]
        if not frame.get("parentId") and frame["url"] == entry["url"] and not navigation.done():
            navigation.set_result(event)

    session.on("Page.frameNavigated", navigated)
    try:
        await session.send("Page.navigateToHistoryEntry", {"entryId": entry["id"]})
        event = await asyncio.wait_for(navigation, timeout=10)
        report["history_navigation"] = event
        expression = "(" + COLLECT_HISTORY + ")(" + json.dumps({"token": token, "origins": origins}) + ")"
        result = await asyncio.wait_for(session.send("Runtime.evaluate", {
            "expression": expression, "awaitPromise": True, "returnByValue": True, "timeout": 5000}), timeout=8)
        if result.get("exceptionDetails") or "value" not in result.get("result", {}):
            report["history_evaluation_error"] = result
            raise ValueError("Restored root CDP evaluation failed")
        return result["result"]["value"]
    finally:
        session.remove_listener("Page.frameNavigated", navigated)


async def capture_page(page) -> dict:
    await page.bring_to_front()
    await asyncio.wait_for(page.evaluate("""() => new Promise(resolve =>
      requestAnimationFrame(() => requestAnimationFrame(resolve)))"""), timeout=5)
    frames = {frame.name or "main": frame for frame in page.frames}
    if set(frames) != ROLES or len(page.frames) != len(ROLES):
        raise ValueError("Lifecycle frame coverage differs from the owned fixture")
    observed = {}
    for role, frame in frames.items():
        row = await frame.evaluate("""() => ({snapshot: glintSampleScreen(),
          origin: self.origin, location: location.href})""")
        row["parent"] = None if frame.parent_frame is None else (frame.parent_frame.name or "main")
        if role != "main":
            element = await frame.frame_element()
            row["embedding_size"] = await element.evaluate("element => ({width: element.clientWidth, height: element.clientHeight})")
        observed[role] = row
    return observed


async def capture(executable: Path, owned: Path, server, report: dict, save) -> None:
    origin = f"http://127.0.0.1:{server.server_port}"
    alternate = f"http://localhost:{server.server_port}"
    configuration = REFERENCE["environment"].configuration_for_mode("native-control")
    if configuration is not None:
        raise ValueError("Lifecycle control must not inherit a manager viewport")
    report.update(stages=[], bfcache_not_used=[], fixture_port=server.server_port,
                  driver_arguments_explicitly_removed=["--disable-back-forward-cache"],
                  fixture_cache_control="public, max-age=60", process_swap_verified=False,
                  scope="Two owned pages, explicit CDP screen metrics, updates/clear, cross-site navigation and observed BFCache; not a complete mobile/device profile")
    async with REFERENCE["async_playwright"]() as driver:
        context = await driver.chromium.launch_persistent_context(
            str(owned / "profile"), executable_path=str(executable), headless=True,
            chromium_sandbox=True, timeout=30000, no_viewport=True,
            args=["--enable-automation"], ignore_default_args=["--disable-back-forward-cache"])
        browser = context.browser
        primary = None
        sessions = {}
        try:
            arguments = await REFERENCE["environment"].workers.browser_arguments(context)
            if "--disable-back-forward-cache" in arguments:
                raise ValueError("The driver still disabled BFCache")
            report["effective_arguments"] = arguments
            session = await browser.new_browser_cdp_session()
            try:
                version = await session.send("Browser.getVersion")
                if (version["revision"] != "@" + report["chromium_revision"]
                        or version["product"] != "Chrome/" + report["chromium_version"]):
                    raise ValueError("Lifecycle browser version/revision differs from receipt")
                report["browser_version"] = version
            finally:
                await session.detach()

            async def route(request):
                from urllib.parse import urlsplit
                address = urlsplit(request.request.url)
                if (address.scheme == "http" and address.hostname in {"127.0.0.1", "localhost"}
                        and address.port == server.server_port):
                    await request.continue_()
                else:
                    await request.abort("blockedbyclient")

            await context.route("**/*", route)
            pages = {"A": context.pages[0] if context.pages else await context.new_page(),
                     "B": await context.new_page()}
            for name, page in pages.items():
                sessions[name] = await context.new_cdp_session(page)
                await sessions[name].send("Page.enable")
                if name == "B":
                    sessions[name].on("Page.backForwardCacheNotUsed", lambda event: report["bfcache_not_used"].append(event))
                await page.goto(origin + "/screen?role=main", timeout=10000)
            baseline = {}
            settings = {"A": None, "B": None}

            async def stage(name, changed=None):
                row = {"name": name, "pages": {}, "errors": [], "passed": False}
                report["stages"].append(row)
                for key, page in pages.items():
                    observed = await capture_page(page)
                    if name == "baseline":
                        baseline[key] = observed["main"]["snapshot"]["screen"]
                    errors = validate_page(observed, expected_screen(baseline[key], settings[key]))
                    row["pages"][key] = {"observed": observed, "errors": errors}
                    row["errors"].extend(key + "/" + error for error in errors)
                    png = await page.screenshot()
                    if len(png) < 24 or png[:8] != b"\x89PNG\r\n\x1a\n":
                        raise ValueError("Lifecycle screenshot is not PNG")
                    dimensions = list(struct.unpack(">II", png[16:24]))
                    viewport = observed["main"]["snapshot"]["viewport"]
                    scale = expected_screen(baseline[key], settings[key])["dpr"]
                    row["pages"][key]["screenshot_size"] = dimensions
                    if dimensions != [round(viewport[axis] * scale) for axis in ("width", "height")]:
                        row["errors"].append(key + ": screenshot dimensions disagree with requested DPR")
                    (owned / (name + "-" + key + ".png")).write_bytes(png)
                    if changed is not None and key != changed:
                        previous = report["stages"][-2]["pages"][key]["observed"]
                        stable = all(previous[role]["snapshot"]["screen"] == observed[role]["snapshot"]["screen"] for role in ROLES)
                        row["pages"][key]["unchanged_by_other_page"] = stable
                        if not stable:
                            row["errors"].append(key + ": other page update changed this screen")
                    save()
                row["passed"] = not row["errors"]
                save()

            await stage("baseline")
            for name, changed, value in STEPS:
                if value is None:
                    await sessions[changed].send("Emulation.clearDeviceMetricsOverride")
                else:
                    await sessions[changed].send("Emulation.setDeviceMetricsOverride", metrics_parameters(value))
                settings[changed] = value
                await stage(name, changed)
            await pages["B"].goto(alternate + "/screen?role=main&navigation=1", timeout=10000)
            await stage("cross-site-navigation", "B")
            await sessions["A"].detach()
            del sessions["A"]
            await pages["A"].close()
            del pages["A"]
            state = await restore_history(pages["B"], sessions["B"],
                report["stages"][-1]["pages"]["B"]["observed"], report)
            report["bfcache_state"] = state
            report["bfcache_restored"] = (history_restored(state)
                and report["history_navigation"].get("type") == "BackForwardCacheRestore")
            row = {"name": "history-return", "pages": {}, "errors": [], "passed": False}
            report["stages"].append(row)
            try:
                observed = restored_observations(state)
                errors = validate_page(observed, expected_screen(baseline["B"], settings["B"]))
                row["pages"]["B"] = {"observed": observed, "errors": errors}
                row["errors"].extend(errors)
                if not report["bfcache_restored"]:
                    row["errors"].append("CDP did not identify BFCache restoration")
            except ValueError as error:
                row["errors"].append(str(error))
            row["passed"] = not row["errors"]
            save()
            report["measurement_complete"] = True
            report["passed"] = all(row["passed"] for row in report["stages"]) and report["bfcache_restored"]
        except BaseException as error:
            primary = error
            raise
        finally:
            for session in sessions.values():
                try:
                    await session.detach()
                except Exception as error:
                    report["cleanup_errors"].append(str(error))
            try:
                await context.close()
            except Exception as error:
                report["cleanup_errors"].append(str(error))
                if primary is None:
                    raise
                primary.add_note("Owned lifecycle cleanup failed: " + str(error))
            finally:
                report["browser_connection_closed"] = not browser.is_connected()
                report["passed"] = report["passed"] and report["browser_connection_closed"] and not report["cleanup_errors"]
                save()
