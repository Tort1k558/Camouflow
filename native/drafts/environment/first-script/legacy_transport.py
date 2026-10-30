"""Cached-provider transport regression; no browser downloads or driver selection."""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import threading
from urllib.parse import urlsplit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=('camoufox', 'cloakbrowser'), required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--driver-root', type=Path, required=True)
    parser.add_argument('--driver-sha256', required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    args = parser.parse_args()
    ROOT = Path(__file__).resolve().parents[4]
    provider, mode = args.provider, args.label
    OUTPUT = args.work_dir.resolve()
    if OUTPUT.is_relative_to(ROOT):
        raise ValueError("Use an owned work directory outside the checkout")
    driver_root = args.driver_root.resolve(strict=True)
    driver = driver_root / 'playwright/driver/package/lib/coreBundle.js'
    if hashlib.sha256(driver.read_bytes()).hexdigest() != args.driver_sha256:
        raise ValueError("Driver differs from the explicitly pinned bundle")
    sys.path.insert(0, str(driver_root))
    sys.dont_write_bytecode = True
    OUTPUT.mkdir(exist_ok=False)
    (OUTPUT / 'temp').mkdir()
    os.environ.update(CAMOUFLOW_DATA_DIR=str(OUTPUT / 'workspace'), TMP=str(OUTPUT / 'temp'), TEMP=str(OUTPUT / 'temp'),
                      PLAYWRIGHT_NODEJS_PATH=str(driver_root / 'playwright/driver/node.exe'), PYTHONDONTWRITEBYTECODE='1')
    import playwright
    driver = Path(playwright.__file__).parent / 'driver/package/lib/coreBundle.js'
    assert Path(playwright.__file__).resolve() == driver_root / 'playwright/__init__.py'
    sys.path.insert(0, str(ROOT))
    helpers = runpy.run_path(str(ROOT / 'scripts/verify_native_runtime.py'))
    executable = args.executable.resolve(strict=True)
    assert executable.is_file()
    core_files = [executable, executable.parent / ('xul.dll' if provider == 'camoufox' else 'chrome.dll')]
    assert all(path.is_file() for path in core_files)
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    inputs = {path: sha(path) for path in [Path(__file__), driver, driver_root / 'playwright/driver/node.exe', ROOT / 'scripts/verify_native_runtime.py', *core_files]}
    report = {'schema': 1, 'passed': False, 'measurement_complete': False, 'provider': provider, 'mode': mode,
              'driver_sha256': sha(driver), 'browser_core_sha256': {path.name: sha(path) for path in core_files},
              'scope': 'Existing cached provider binaries with original versus explicit-opt-in-capable driver, no Native BFCache opt-in; local form/frame/binding and five-store persistent restart controls',
              'runs': [], 'automatic_downloads_enabled': False, 'privacy_admitted': False, 'production_admitted': False}
    def save():
        (OUTPUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    server = helpers['FixtureServer'](('127.0.0.1', 0), helpers['FixtureHandler'])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    async def route(request):
        url = urlsplit(request.request.url)
        if url.scheme == 'http' and url.hostname == '127.0.0.1' and url.port == server.server_port:
            await request.continue_()
        else:
            await request.abort('blockedbyclient')

    async def run():
        before = await asyncio.to_thread(helpers['process_snapshot'])
        owned = {}
        for phase in ('initial', 'persistent-profile-restart'):
            row = {'phase': phase, 'passed': False}
            report['runs'].append(row)
            save()
            manager, context = None, None
            try:
                if provider == 'camoufox':
                    from camoufox import AsyncCamoufox, DefaultAddons
                    manager = AsyncCamoufox(executable_path=str(executable), headless=True, humanize=False,
                        os='windows', geoip=False, locale='en-US', window=(1280, 720), i_know_what_im_doing=True,
                        exclude_addons=list(DefaultAddons), persistent_context=True, user_data_dir=str(OUTPUT / 'profile'))
                    context = await manager.__aenter__()
                else:
                    os.environ.update(CLOAKBROWSER_BINARY_PATH=str(executable), CLOAKBROWSER_AUTO_UPDATE='false',
                                      CLOAKBROWSER_CACHE_DIR=str(OUTPUT / 'cloak-cache'))
                    from cloakbrowser import launch_persistent_context_async
                    context = await launch_persistent_context_async(str(OUTPUT / 'profile'), headless=True,
                        humanize=False, geoip=False, locale='en-US', timezone='UTC')
                await context.route('**/*', route)
                page = context.pages[0] if context.pages else await context.new_page()
                if provider == 'cloakbrowser':
                    await context.unroute('**/*', route)
                    await page.goto('chrome://version', timeout=10000)
                    line = await page.locator('#command_line').inner_text(timeout=10000)
                    row['default_bfcache_disable_flag'] = '--disable-back-forward-cache' in line.split()
                    assert row['default_bfcache_disable_flag']
                    await context.route('**/*', route)
                await page.goto(origin, timeout=10000)
                calls = []
                async def echo(source, value):
                    assert source['page'] == page
                    if source['frame'] == page.main_frame:
                        role = 'main'
                    else:
                        element = await source['frame'].frame_element()
                        assert await element.get_attribute('id') == 'owned-frame'
                        role = 'child'
                    calls.append(role)
                    return {'role': role, 'value': value}
                await context.expose_binding('ownedLegacyEcho', echo)
                assert await page.evaluate("window.ownedLegacyEcho('owned')") == {'role': 'main', 'value': 'owned'}
                await page.get_by_label('Value', exact=True).fill(provider)
                await page.get_by_role('button', name='Apply', exact=True).click()
                assert await page.locator('output').text_content() == provider
                frame = page.frame_locator('#owned-frame')
                await frame.get_by_label('Value', exact=True).fill('child-' + provider)
                await frame.get_by_role('button', name='Apply', exact=True).click()
                assert await frame.locator('output').text_content() == 'child-' + provider
                child = next(frame for frame in page.frames if frame != page.main_frame)
                assert await child.evaluate("window.ownedLegacyEcho('owned-child')") == {'role': 'child', 'value': 'owned-child'}
                expected = {'cookie': 'owned=' + provider, 'local': provider, 'indexed': provider, 'cached': provider, 'workers': 1}
                if phase == 'initial':
                    assert await page.evaluate(helpers['STORAGE'], None) == {'cookie': '', 'local': None, 'indexed': None, 'cached': None, 'workers': 0}
                    assert await page.evaluate(helpers['STORAGE'], provider) == expected
                else:
                    assert await page.evaluate(helpers['STORAGE'], None) == expected
                png = await page.screenshot(path=str(OUTPUT / (phase + '.png')), timeout=10000)
                assert png[:8] == b'\x89PNG\r\n\x1a\n'
                row.update(passed=True, form_and_frame_actions=True, binding_roles=calls, five_stores=True, screenshot_png=True)
                owned.update(helpers['controller_descendants'](before, await asyncio.to_thread(helpers['process_snapshot']), os.getpid()))
            finally:
                if manager is not None:
                    await manager.__aexit__(None, None, None)
                elif context is not None:
                    await context.close()
                save()
        async def wait_owned():
            while True:
                current = await asyncio.to_thread(helpers['process_snapshot'])
                if not any(helpers['same_process'](current.get(pid), process) for pid, process in owned.items()):
                    return
                await asyncio.sleep(0.05)
        await asyncio.wait_for(wait_owned(), timeout=15)
        report.update(passed=all(row['passed'] for row in report['runs']), measurement_complete=True,
                      owned_processes_observed=len(owned), remaining_owned_processes=0)

    try:
        asyncio.run(asyncio.wait_for(run(), timeout=120))
    except Exception as error:
        report.update(passed=False, error_type=type(error).__name__, error=str(error))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        report['postguards_passed'] = not thread.is_alive() and all(sha(path) == value for path, value in inputs.items())
        report['passed'] = report['passed'] and report['postguards_passed']
        save()
    print(json.dumps({key: report.get(key) for key in ('provider', 'mode', 'passed', 'measurement_complete', 'error', 'postguards_passed')}))
    return 0 if report['passed'] else 1


if __name__ == "__main__":
    raise SystemExit(main())
