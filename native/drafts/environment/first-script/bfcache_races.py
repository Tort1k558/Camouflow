"""Owned Windows BFCache lifecycle gate; explicit application/driver copies only."""

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
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--runtime-reference', type=Path, required=True)
    parser.add_argument('--application-root', type=Path, required=True)
    parser.add_argument('--driver-root', type=Path, required=True)
    parser.add_argument('--driver-sha256', required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    args = parser.parse_args()
    ROOT = Path(__file__).resolve().parents[4]
    application_root = args.application_root.resolve(strict=True)
    driver_root = args.driver_root.resolve(strict=True)
    OUTPUT = args.work_dir.resolve()
    if OUTPUT.is_relative_to(ROOT):
        raise ValueError("Use an owned work directory outside the source checkout")
    bundle_path = driver_root / 'playwright/driver/package/lib/coreBundle.js'
    if hashlib.sha256(bundle_path.read_bytes()).hexdigest() != args.driver_sha256:
        raise ValueError("Driver differs from the explicitly pinned bundle")
    sys.path[:0] = [str(application_root), str(driver_root)]
    OUTPUT.mkdir(exist_ok=False)
    os.environ['CAMOUFLOW_DATA_DIR'] = str(OUTPUT / 'workspace')
    from app.core.native.runtime import NativeRuntime
    from app.core.native.identity import IDENTITY_FILE
    import app.core.native.runtime as runtime_module
    import playwright

    assert Path(runtime_module.__file__).resolve() == application_root / 'app/core/native/runtime.py'
    assert Path(playwright.__file__).resolve() == driver_root / 'playwright/__init__.py'
    FIXTURE = ROOT / 'native/drafts/environment/first-script'
    lifecycle = runpy.run_path(str(FIXTURE / 'lifecycle.py'))
    runtime_helpers = runpy.run_path(str(ROOT / 'scripts/verify_native_runtime.py'))
    EXE = args.executable.resolve(strict=True)
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    paths = [Path(__file__), Path(runtime_module.__file__), Path(playwright.__file__).parent / 'driver/package/lib/coreBundle.js',
             *FIXTURE.glob('*.py'), FIXTURE / 'sample.js', ROOT / 'scripts/verify_native_runtime.py',
             *(EXE.parent / name for name in ('chrome.exe', 'chrome.dll', 'chrome_elf.dll'))]
    inputs = {path: sha(path) for path in paths}
    inputs.update({path: sha(path) for path in (application_root / 'app').rglob('*.py')})
    inputs.update({path: sha(path) for path in (ROOT / 'scripts').glob('*.py')})
    inputs[args.runtime_reference.resolve(strict=True)] = sha(args.runtime_reference)
    core = {name: sha(EXE.parent / name) for name in ('chrome.exe', 'chrome.dll', 'chrome_elf.dll')}
    reference = json.loads(args.runtime_reference.read_bytes())
    if core != reference['runtime_core_sha256_measured']:
        raise ValueError("Browser core differs from measured runtime reference")
    report = {'schema': 1, 'passed': False, 'measurement_complete': False, 'runs': [],
              'scope': 'Real browser and protocol replies with an instrumented D driver holding one actual restored main-target frame-tree response; navigation/page close/runtime close while held, then same-profile restart',
              'selected': False, 'privacy_admitted': False, 'production_admitted': False,
              'test_only_driver_instrumentation': True, 'measured_inputs_sha256': {str(path): value for path, value in inputs.items()}}
    report.update(driver_sha256=sha(bundle_path), runtime_core_sha256_measured=core, source_input_count=len(inputs))
    def save():
        (OUTPUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')

    server = lifecycle['create_server']()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'

    async def route(request):
        url = urlsplit(request.request.url)
        if url.scheme == 'http' and url.hostname in {'127.0.0.1', 'localhost'} and url.port == server.server_port:
            await request.continue_()
        else:
            await request.abort('blockedbyclient')

    async def wait_ready(path):
        async def wait():
            while not path.exists():
                await asyncio.sleep(0.01)
        await asyncio.wait_for(wait(), timeout=5)

    async def remaining_owned(owned):
        current = await asyncio.to_thread(runtime_helpers['process_snapshot'])
        return [pid for pid, row in owned.items() if runtime_helpers['same_process'](current.get(pid), row)]

    async def run():
        for mode in ('manager-desktop', 'manager-mobile-web'):
            configuration = lifecycle['REFERENCE']['environment'].configuration_for_mode(mode)
            for case in ('navigate', 'close-page', 'close-runtime'):
                row = {'mode': mode, 'case': case, 'passed': False}
                report['runs'].append(row)
                save()
                before = await asyncio.to_thread(runtime_helpers['process_snapshot'])
                owned = {}
                gate = OUTPUT / (mode + '-' + case + '-gate')
                os.environ['GLINT_OWNED_BFCACHE_GATE'] = str(gate)
                profile = OUTPUT / ('profile-' + mode + '-' + case)
                runtime = NativeRuntime(profile, EXE, configuration)
                session = None
                restore = None
                try:
                    context = await runtime.start(headless=True)
                    await context.route('**/*', route)
                    page = context.pages[0]
                    await page.goto(origin + '/screen?role=main', timeout=10000)
                    observed = await lifecycle['capture_page'](page)
                    await page.evaluate("value => localStorage.setItem('owned-race-state', value)", mode + '-' + case)
                    identity = (profile / IDENTITY_FILE).read_bytes()
                    session = await context.new_cdp_session(page)
                    await session.send('Page.enable')
                    state = {'fixture_port': server.server_port}
                    restore = asyncio.create_task(lifecycle['restore_history'](page, session, observed, state))
                    await wait_ready(Path(str(gate) + '.ready'))
                    history = await restore
                    lifecycle['restored_observations'](history)
                    row['native_bfcache_restored'] = state['history_navigation']['type'] == 'BackForwardCacheRestore'
                    assert row['native_bfcache_restored']
                    owned.update(runtime_helpers['controller_descendants'](before, await asyncio.to_thread(runtime_helpers['process_snapshot']), os.getpid()))
                    assert len(owned) > 2
                    assert not Path(str(gate) + '.timeout').exists()
                    assert not Path(str(gate) + '.continued').exists()
                    row['barrier_held_before_action'] = True
                    if case == 'navigate':
                        target = origin + '/screen?role=main&after-race=1'
                        await page.goto(target, timeout=10000)
                        assert not Path(str(gate) + '.timeout').exists()
                        assert not Path(str(gate) + '.continued').exists()
                        row['barrier_held_until_action_finished'] = True
                        Path(str(gate) + '.release').write_text('owned', encoding='utf-8')
                        after = await lifecycle['capture_page'](page)
                        assert len(page.frames) == 6 and set(after) == lifecycle['ROLES'] and page.url == target
                        row['replacement_document_preserved'] = True
                    elif case == 'close-page':
                        peer = await context.new_page()
                        await peer.goto(origin + '/screen?role=main&peer=1', timeout=10000)
                        await page.close()
                        assert not Path(str(gate) + '.timeout').exists()
                        assert not Path(str(gate) + '.continued').exists()
                        row['barrier_held_until_action_finished'] = True
                        Path(str(gate) + '.release').write_text('owned', encoding='utf-8')
                        after = await lifecycle['capture_page'](peer)
                        assert page.is_closed() and len(peer.frames) == 6 and set(after) == lifecycle['ROLES']
                        row['closed_page_and_peer_intact'] = True
                    else:
                        await runtime.close()
                        assert not Path(str(gate) + '.timeout').exists()
                        assert not Path(str(gate) + '.continued').exists()
                        row['barrier_held_until_action_finished'] = True
                        Path(str(gate) + '.release').write_text('owned', encoding='utf-8')
                        row['runtime_resources_released_while_held'] = not runtime.has_resources
                        assert row['runtime_resources_released_while_held']
                    await runtime.close()
                    assert not runtime.has_resources
                    os.environ.pop('GLINT_OWNED_BFCACHE_GATE')
                    # Same owned profile must remain restartable, with its key and committed storage.
                    context = await runtime.start(headless=True)
                    await context.route('**/*', route)
                    page = context.pages[0]
                    await page.goto(origin + '/screen?role=main&restart=1', timeout=10000)
                    assert (profile / IDENTITY_FILE).read_bytes() == identity
                    assert await page.evaluate("localStorage.getItem('owned-race-state')") == mode + '-' + case
                    row['same_profile_identity_and_storage_restored'] = True
                    owned.update(runtime_helpers['controller_descendants'](before, await asyncio.to_thread(runtime_helpers['process_snapshot']), os.getpid()))
                finally:
                    Path(str(gate) + '.release').write_text('owned', encoding='utf-8')
                    if restore is not None and not restore.done():
                        restore.cancel()
                        await asyncio.gather(restore, return_exceptions=True)
                    os.environ.pop('GLINT_OWNED_BFCACHE_GATE', None)
                    await runtime.close()
                    row['native_runtime_resources_released'] = not runtime.has_resources
                    async def wait_owned():
                        while await remaining_owned(owned):
                            await asyncio.sleep(0.05)
                    await asyncio.wait_for(wait_owned(), timeout=15)
                    row['remaining_owned_processes'] = len(await remaining_owned(owned))
                    row['owned_processes_observed'] = len(owned)
                    save()
                assert not Path(str(gate) + '.timeout').exists()
                row['passed'] = row['native_runtime_resources_released'] and row['remaining_owned_processes'] == 0
                save()
        report.update(passed=all(row['passed'] for row in report['runs']), measurement_complete=True)

    try:
        asyncio.run(run())
    except Exception as error:
        report.update(passed=False, error_type=type(error).__name__, error=str(error))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        report['postguards_passed'] = not thread.is_alive() and all(sha(path) == value for path, value in inputs.items())
        report['passed'] = report['passed'] and report['postguards_passed']
        save()
    print(json.dumps({key: report.get(key) for key in ('passed', 'measurement_complete', 'postguards_passed', 'error_type', 'error')}))
    return 0 if report['passed'] else 1


if __name__ == "__main__":
    raise SystemExit(main())
