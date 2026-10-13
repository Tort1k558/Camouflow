"""Headless binary startup checks using owned disposable profiles."""

import tempfile
from pathlib import Path

from .configuration import NativeConfiguration
from .diagnostics import inspect_native_profile
from .runtime import NativeRuntime


async def _prepare_diagnostic_page(context):
    url = "http://127.0.0.1/glint-native-health"

    async def respond(route):
        if route.request.url != url:
            await route.abort("blockedbyclient")
            return
        await route.fulfill(
            status=200, content_type="text/html; charset=utf-8",
            body='<!doctype html><meta charset="utf-8"><title>Glint local diagnostics</title>',
            headers={"Content-Security-Policy": "default-src 'none'; worker-src blob:",
                     "Cache-Control": "no-store"})

    await context.route("**/*", respond)
    page = context.pages[0]
    await page.goto(url, wait_until="load", timeout=10000)
    return page


async def _probe(executable: Path, configuration: NativeConfiguration, work_dir: Path, *, inspect_values: bool) -> dict:
    configuration.validate()
    executable = executable.resolve(strict=True)
    if not executable.is_file():
        raise ValueError("Configure an installed Native Chromium executable")
    work_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="native-health-", dir=work_dir.resolve()) as owned:
        runtime = NativeRuntime(Path(owned), executable, configuration)
        try:
            context = await runtime.start(headless=True)
            version = context.browser.version
            if not isinstance(version, str) or not version.strip():
                raise ValueError("Native browser did not report its version")
            if inspect_values:
                page = await _prepare_diagnostic_page(context)
                return await inspect_native_profile(page, configuration, version)
            return {"browser_version": version}
        finally:
            await runtime.close()


async def probe_native_binary(executable: Path, configuration: NativeConfiguration, work_dir: Path) -> str:
    return (await _probe(executable, configuration, work_dir, inspect_values=False))["browser_version"]


async def probe_native_profile(executable: Path, configuration: NativeConfiguration, work_dir: Path) -> dict:
    return await _probe(executable, configuration, work_dir, inspect_values=True)
