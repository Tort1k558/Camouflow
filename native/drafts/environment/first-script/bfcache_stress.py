"""Owned Windows BFCache lifecycle gate; explicit application/driver copies only."""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import runpy
import threading
from urllib.parse import urlsplit

import sys

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
    helpers = runpy.run_path(str(ROOT / 'scripts/verify_native_runtime.py'))
    EXE = args.executable.resolve(strict=True)
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    bundle = Path(playwright.__file__).parent / 'driver/package/lib/coreBundle.js'
    assert sha(bundle) == args.driver_sha256
    paths = [Path(__file__), Path(runtime_module.__file__), bundle, *FIXTURE.glob('*.py'), FIXTURE / 'sample.js',
             ROOT / 'scripts/verify_native_runtime.py', *(EXE.parent / name for name in ('chrome.exe', 'chrome.dll', 'chrome_elf.dll'))]
    inputs = {path: sha(path) for path in paths}
    inputs.update({path: sha(path) for path in (application_root / 'app').rglob('*.py')})
    inputs.update({path: sha(path) for path in (ROOT / 'scripts').glob('*.py')})
    inputs[args.runtime_reference.resolve(strict=True)] = sha(args.runtime_reference)
    core = {name: sha(EXE.parent / name) for name in ('chrome.exe', 'chrome.dll', 'chrome_elf.dll')}
    reference = json.loads(args.runtime_reference.read_bytes())
    if core != reference['runtime_core_sha256_measured']:
        raise ValueError("Browser core differs from measured runtime reference")
    report = {'schema': 1, 'passed': False, 'measurement_complete': False, 'runs': [],
              'scope': 'Uninstrumented reply draft, 32 real BFCache cycles across desktop/mobile initial/restart; a Python result is released on native away-navigation, then awaited in its restored context; six role-verified echoes per cycle',
              'selected': False, 'privacy_admitted': False, 'production_admitted': False,
              'driver_test_instrumentation': False, 'measured_inputs_sha256': {str(path): value for path, value in inputs.items()}}
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

    async def run():
        for mode in ('manager-desktop', 'manager-mobile-web'):
            configuration = lifecycle['REFERENCE']['environment'].configuration_for_mode(mode)
            runtime = NativeRuntime(OUTPUT / ('profile-' + mode), EXE, configuration)
            identity = None
            for phase in ('initial', 'persistent-profile-restart'):
                row = {'mode': mode, 'phase': phase, 'passed': False, 'cycles': []}
                report['runs'].append(row)
                before = await asyncio.to_thread(helpers['process_snapshot'])
                owned = {}
                try:
                    context = await runtime.start(headless=True)
                    await context.route('**/*', route)
                    page = context.pages[0]
                    session = await context.new_cdp_session(page)
                    await session.send('Page.enable')
                    phase_key = (runtime.profile_dir / IDENTITY_FILE).read_bytes()
                    if identity is not None:
                        assert identity == phase_key
                        row['identity_stable_after_restart'] = True
                    identity = phase_key
                    release = asyncio.Event()
                    entered = asyncio.Event()
                    calls = []
                    expected_cycle = 0
                    async def echo(source, payload):
                        assert source['page'] == page
                        assert payload['role'] == (source['frame'].name or 'main')
                        assert payload['cycle'] == expected_cycle
                        calls.append(dict(payload))
                        if payload['kind'] == 'held':
                            entered.set()
                            await release.wait()
                        return payload
                    await context.expose_binding('ownedCycleEcho', echo)
                    for cycle in range(8):
                        expected_cycle = cycle
                        await page.goto(origin + f'/screen?role=main&cycle={cycle}', timeout=10000)
                        if phase == 'persistent-profile-restart' and cycle == 0:
                            assert await page.evaluate("localStorage.getItem('owned-cycle-mode')") == mode
                            row['storage_stable_after_restart'] = True
                        await page.evaluate("value => localStorage.setItem('owned-cycle-mode', value)", mode)
                        observed = await lifecycle['capture_page'](page)
                        release.clear()
                        entered.clear()
                        held_payload = {'kind': 'held', 'role': 'main', 'cycle': cycle}
                        await page.evaluate('payload => {window.glintHeldReply = window.ownedCycleEcho(payload)}', held_payload)
                        await asyncio.wait_for(entered.wait(), timeout=5)
                        release_seen = []
                        def navigated(event):
                            frame = event['frame']
                            if not frame.get('parentId') and frame['url'].endswith('navigation=2'):
                                release_seen.append(True)
                                release.set()
                        session.on('Page.frameNavigated', navigated)
                        state = {'fixture_port': server.server_port}
                        try:
                            history = await lifecycle['restore_history'](page, session, observed, state)
                        finally:
                            session.remove_listener('Page.frameNavigated', navigated)
                        lifecycle['restored_observations'](history)
                        assert state['history_navigation']['type'] == 'BackForwardCacheRestore'
                        assert release_seen
                        result = await asyncio.wait_for(page.evaluate('window.glintHeldReply'), timeout=5)
                        assert result == held_payload
                        assert sum(call == held_payload for call in calls) == 1
                        after = await lifecycle['capture_page'](page)
                        assert all(after[role]['snapshot'] == observed[role]['snapshot'] for role in lifecycle['ROLES'])
                        frames = {frame.name or 'main': frame for frame in page.frames}
                        assert set(frames) == lifecycle['ROLES'] and len(page.frames) == 6
                        for role, frame in frames.items():
                            payload = {'kind': 'echo', 'role': role, 'cycle': cycle}
                            assert await asyncio.wait_for(frame.evaluate('payload => window.ownedCycleEcho(payload)', payload), timeout=5) == payload
                        row['cycles'].append({'cycle': cycle, 'passed': True, 'native_bfcache_restored': True,
                                              'held_handler_calls': 1, 'held_reply_resolved': True,
                                              'result_released_on_native_away_navigation': True,
                                              'echo_roles': sorted(frames), 'screen_snapshots_unchanged': True})
                        save()
                    assert len(calls) == 56
                    row['binding_handler_calls'] = len(calls)
                    owned.update(helpers['controller_descendants'](before, await asyncio.to_thread(helpers['process_snapshot']), os.getpid()))
                finally:
                    await runtime.close()
                    row['native_runtime_resources_released'] = not runtime.has_resources
                    async def wait_owned():
                        while True:
                            current = await asyncio.to_thread(helpers['process_snapshot'])
                            if not any(helpers['same_process'](current.get(pid), process) for pid, process in owned.items()):
                                return
                            await asyncio.sleep(0.05)
                    await asyncio.wait_for(wait_owned(), timeout=15)
                    row['remaining_owned_processes'] = 0
                    row['owned_processes_observed'] = len(owned)
                    save()
                row['passed'] = len(row['cycles']) == 8 and row['native_runtime_resources_released']
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
