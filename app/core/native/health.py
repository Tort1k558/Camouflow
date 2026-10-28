"""Headless binary startup checks using owned disposable profiles."""

import shutil
import tempfile
from pathlib import Path

from .configuration import NativeConfiguration
from .diagnostics import compare_document_identity, inspect_native_profile
from .runtime import NativeRuntime

DIAGNOSTIC_URL = "http://127.0.0.1/glint-native-health"
DIAGNOSTIC_FRAME_URL = DIAGNOSTIC_URL + "/frame"


async def _prepare_diagnostic_page(context, *, page=None, configuration=None):
    url = DIAGNOSTIC_URL

    async def respond(route):
        allowed = {url, DIAGNOSTIC_FRAME_URL} if configuration is not None else {url}
        if route.request.url not in allowed:
            await route.abort("blockedbyclient")
            return
        body = ('<!doctype html><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                '<title>Glint local diagnostics</title>')
        policy = "default-src 'none'; worker-src blob:"
        if configuration is not None:
            policy += "; frame-src 'self'; style-src 'unsafe-inline'"
            body += '<style>body{margin:0}</style>'
            if route.request.url == url:
                body += (f'<iframe src="{DIAGNOSTIC_FRAME_URL}" '
                         f'width="{configuration.width}" height="{configuration.height}" '
                         'style="border:0;display:block"></iframe>')
        await route.fulfill(
            status=200, content_type="text/html; charset=utf-8",
            body=body,
            headers={"Content-Security-Policy": policy,
                     "Cache-Control": "no-store"})

    target = context if page is None else page
    await target.route("**/*", respond)
    if page is None:
        page = context.pages[0]
    await page.goto(url, wait_until="load", timeout=10000)
    return page


async def inspect_native_context(context, configuration: NativeConfiguration, browser_version: str) -> dict:
    configuration.validate()
    page = await context.new_page()
    try:
        session = await context.new_cdp_session(page)
        await session.send("Network.enable", {})
        await session.send("Network.setBypassServiceWorker", {"bypass": True})
        await _prepare_diagnostic_page(context, page=page, configuration=configuration)
        report = await inspect_native_profile(page, configuration, browser_version)
        frame = page.frame(url=DIAGNOSTIC_FRAME_URL)
        if frame is None:
            raise RuntimeError("Glint diagnostic iframe did not load")
        frame_report = await inspect_native_profile(frame, configuration, browser_version)
        return {**report, "contexts": {"same_origin_frame": frame_report},
                "mismatches": [*report["mismatches"],
                               *compare_document_identity(report["observed"]["document"],
                                                          frame_report["observed"]["document"]),
                               *("Same-origin iframe: " + value for value in frame_report["mismatches"])]}
    finally:
        await page.close()


async def _probe(executable: Path, configuration: NativeConfiguration, work_dir: Path, *, inspect_values: bool) -> dict:
    configuration.validate()
    executable = executable.resolve(strict=True)
    if not executable.is_file():
        raise ValueError("Configure an installed Native Chromium executable")
    work_dir.mkdir(parents=True, exist_ok=True)
    owned = Path(tempfile.mkdtemp(prefix="native-health-", dir=work_dir.resolve()))
    runtime = NativeRuntime(owned, executable, configuration)
    try:
        context = await runtime.start(headless=True)
        version = context.browser.version
        if not isinstance(version, str) or not version.strip():
            raise ValueError("Native browser did not report its version")
        if inspect_values:
            page = await _prepare_diagnostic_page(context)
            report = await inspect_native_profile(page, configuration, version)
            if configuration.privacy_policy.required_capabilities():
                report["native_patch_capabilities"] = runtime.native_policy_capabilities
            return report
        return {"browser_version": version}
    finally:
        try:
            await runtime.close()
            if runtime.has_resources:
                raise RuntimeError("Native health runtime still owns resources after close")
        except Exception as error:
            if runtime.has_resources:
                raise RuntimeError(f"Native health cleanup failed; owned profile retained: {owned}") from error
            raise
        finally:
            if not runtime.has_resources:
                if owned != owned.resolve() or not owned.is_relative_to(work_dir.resolve()):
                    raise ValueError("Refusing Native health cleanup outside its owned workspace")
                shutil.rmtree(owned)


async def probe_native_binary(executable: Path, configuration: NativeConfiguration, work_dir: Path) -> str:
    return (await _probe(executable, configuration, work_dir, inspect_values=False))["browser_version"]


async def probe_native_profile(executable: Path, configuration: NativeConfiguration, work_dir: Path) -> dict:
    return await _probe(executable, configuration, work_dir, inspect_values=True)
