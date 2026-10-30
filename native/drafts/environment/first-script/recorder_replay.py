"""Owned UI-ordered Recorder/BFCache/replay gate; never installs or selects a driver."""

import argparse
import asyncio
import hashlib
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import runpy
import secrets
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
    OUTPUT = args.work_dir.resolve()
    if OUTPUT.is_relative_to(ROOT):
        raise ValueError("Use an owned work directory outside the source checkout")
    application_root = args.application_root.resolve(strict=True)
    driver_root = args.driver_root.resolve(strict=True)
    bundle_path = driver_root / 'playwright/driver/package/lib/coreBundle.js'
    if hashlib.sha256(bundle_path.read_bytes()).hexdigest() != args.driver_sha256:
        raise ValueError("Driver differs from the explicitly pinned bundle")
    sys.path[:0] = [str(application_root), str(driver_root)]
    OUTPUT.mkdir(exist_ok=False)
    os.environ['CAMOUFLOW_DATA_DIR'] = str(OUTPUT / 'workspace')
    FIXTURE = ROOT / 'native/drafts/environment/first-script'
    from app.services.scenario_engine import ScenarioExecutor
    from app.services.scenario_recorder import ScenarioRecorder
    from app.storage import db
    import app.core.native.runtime as runtime_module
    import playwright
    fixture = runpy.run_path(str(FIXTURE / 'server.py'))
    lifecycle = runpy.run_path(str(FIXTURE / 'lifecycle.py'))

    assert Path(runtime_module.__file__).resolve() == application_root / 'app/core/native/runtime.py'
    assert Path(playwright.__file__).resolve() == driver_root / 'playwright/__init__.py'
    EXE = args.executable.resolve(strict=True)
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    inputs = {path: sha(path) for path in [Path(__file__), Path(runtime_module.__file__),
        Path(playwright.__file__).parent / 'driver/package/lib/coreBundle.js',
        *FIXTURE.glob('*.py'), FIXTURE / 'sample.js', EXE.parent / 'chrome.dll', EXE]}
    source_root = Path(runtime_module.__file__).resolve().parents[3]
    inputs.update({path: sha(path) for path in (source_root / 'app').rglob('*.py')})
    inputs.update({path: sha(path) for path in (ROOT / 'scripts').glob('*.py')})
    import app.services.scenario_recorder as recorder_module
    import app.services.scenario_engine as scenario_module
    assert Path(recorder_module.__file__).resolve() == source_root / 'app/services/scenario_recorder.py'
    assert Path(scenario_module.__file__).resolve() == source_root / 'app/services/scenario_engine.py'
    core = {name: sha(EXE.parent / name) for name in ('chrome.exe', 'chrome.dll', 'chrome_elf.dll')}
    build = json.loads(args.runtime_reference.read_bytes())
    assert core == build['runtime_core_sha256_measured']
    for name in core:
        inputs[EXE.parent / name] = core[name]
    report = {'schema': 1, 'passed': False, 'measurement_complete': False, 'runs': [],
              'scope': 'Attach before initial navigation, trusted link out/back, genuine BFCache, six-frame Recorder and unchanged ScenarioExecutor draft replay in an unselected D source/driver overlay',
              'selected': False, 'privacy_admitted': False, 'production_admitted': False}
    report.update(runtime_core_sha256_measured=core, measured_inputs_sha256={str(path): value for path, value in inputs.items()},
                  source_input_count=len(inputs),
                  recorder_source_sha256=sha(Path(recorder_module.__file__)),
                  recorder_normalized_utf8_lf_sha256=hashlib.sha256(Path(recorder_module.__file__).read_text(encoding='utf-8-sig').encode('utf-8')).hexdigest(),
                  prepared_driver_sha256=sha(Path(playwright.__file__).parent / 'driver/package/lib/coreBundle.js'))

    def save():
        (OUTPUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')

    base_document = fixture['document']
    port = None
    def linked_document(role, children=''):
        markup = base_document(role, children)
        if role == 'main':
            markup = markup.replace('</body>', f'<a id="depart" style="position:fixed;left:112px;top:24px;z-index:4" href="http://localhost:{port}/away">Continue</a></body>')
        return markup
    fixture['Handler'].do_GET.__globals__['document'] = linked_document

    class Handler(fixture['Handler']):
        def do_GET(self):
            if urlsplit(self.path).path != '/away':
                return super().do_GET()
            body = b'<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><title>Owned away page</title><button id="return" onclick="history.back()">Back</button>'
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    async def owned_route(route):
        url = urlsplit(route.request.url)
        if url.scheme == 'http' and url.hostname in {'127.0.0.1', 'localhost'} and url.port == port:
            await route.continue_()
        else:
            await route.abort('blockedbyclient')

    async def click_count(recorder, expected):
        async def wait():
            while sum(step['action'] == 'click' for step in recorder.snapshot()[0]) < expected:
                await asyncio.sleep(0.01)
        await asyncio.wait_for(wait(), timeout=5)

    async def run():
        db.init_db()
        assert db.DATA_ROOT.resolve() == (OUTPUT / 'workspace').resolve()
        for mode in ('manager-desktop', 'manager-mobile-web'):
            configuration = lifecycle['REFERENCE']['environment'].configuration_for_mode(mode)
            account = {'name': 'Owned history ' + mode, 'browser_engine': 'native', 'native_settings': {
                **configuration.environment_settings(), 'executable_path': str(EXE), 'headless': True, 'humanize': False}}
            db.db_add_account(account)
            for phase in ('initial', 'persistent-profile-restart'):
                evidence = {'mode': mode, 'phase': phase, 'passed': False}
                report['runs'].append(evidence)
                save()
                browser = ScenarioExecutor(account, '', db.Scenario('Owned recording', [{'action': 'start'}], ''), keep_browser_open=False)
                recorder = ScenarioRecorder()
                session = None
                try:
                    await browser.start()
                    await browser.context.route('**/*', owned_route)
                    page = browser.page
                    await recorder.attach(page)
                    evidence['attached_before_initial_navigation'] = True
                    url = f'http://127.0.0.1:{port}/screen?role=main'
                    await page.goto(url, timeout=10000)
                    observed = await lifecycle['capture_page'](page)
                    frames = {frame.name or 'main': frame for frame in page.frames}
                    token = secrets.token_hex(16)
                    origins = {role: row['origin'] for role, row in observed.items()}
                    for role, frame in frames.items():
                        await frame.evaluate(lifecycle['INSTALL_HISTORY'], {'token': token, 'role': role,
                            'rootOrigin': origins['main'], 'parent': frame.parent_frame.name or 'main' if frame.parent_frame else None,
                            'allowedOrigins': sorted(set(origins.values()))})
                    session = await browser.context.new_cdp_session(page)
                    await session.send('Page.enable')
                    await page.locator('#probe').click(timeout=10000)
                    await click_count(recorder, 1)
                    await page.locator('#depart').click(timeout=10000)
                    await page.wait_for_url(f'http://localhost:{port}/away', wait_until='load', timeout=10000)
                    navigation = asyncio.get_running_loop().create_future()
                    def navigated(event):
                        if event['frame'].get('url') == url and not event['frame'].get('parentId') and not navigation.done():
                            navigation.set_result(event)
                    session.on('Page.frameNavigated', navigated)
                    try:
                        await page.locator('#return').click(no_wait_after=True, timeout=10000)
                        event = await asyncio.wait_for(navigation, timeout=10)
                    finally:
                        session.remove_listener('Page.frameNavigated', navigated)
                    evidence['history_navigation_type'] = event['type']
                    if event['type'] != 'BackForwardCacheRestore':
                        raise ValueError('History navigation did not restore BFCache')
                    expression = '(' + lifecycle['COLLECT_HISTORY'] + ')(' + json.dumps({'token': token, 'origins': origins}) + ')'
                    response = await session.send('Runtime.evaluate', {'expression': expression, 'returnByValue': True, 'awaitPromise': True})
                    state = response['result']['value']
                    lifecycle['restored_observations'](state)
                    frames = {frame.name or 'main': frame for frame in page.frames}
                    evidence['restored_roles'] = sorted(frames)
                    assert set(frames) == fixture['ROLES'] and len(page.frames) == 6
                    for role in sorted(frames):
                        await frames[role].locator('#probe').click(timeout=10000)
                    await click_count(recorder, 9)
                    evidence['pending_counts'] = {role: await frame.evaluate('window.__camouflowRecorderState.pending.size') for role, frame in frames.items()}
                finally:
                    try:
                        await recorder.stop()
                        evidence['steps'], evidence['warnings'] = recorder.snapshot()
                        save()
                    finally:
                        try:
                            if session is not None:
                                await session.detach()
                        finally:
                            await browser.close(force=True)
                assert not evidence['warnings'], evidence['warnings']
                assert evidence['steps'][1]['action'] == 'goto' and evidence['steps'][1]['url'] == url
                replay = ScenarioExecutor(account, '', db.Scenario('Owned complete history replay', evidence['steps'], ''), keep_browser_open=False)
                session = None
                try:
                    await replay.start()
                    await replay.context.route('**/*', owned_route)
                    session = await replay.context.new_cdp_session(replay.page)
                    await session.send('Page.enable')
                    events = []
                    session.on('Page.frameNavigated', lambda event: events.append(event['type']))
                    evidence['replay_passed'] = await asyncio.wait_for(replay.run(), timeout=75)
                    evidence['replay_navigation_types'] = events
                    assert evidence['replay_passed'], 'Unchanged recorded scenario failed replay'
                    assert 'BackForwardCacheRestore' in events
                    frames = {frame.name or 'main': frame for frame in replay.page.frames}
                    assert set(frames) == fixture['ROLES'] and len(replay.page.frames) == 6
                    evidence['replay_click_counts'] = {}
                    for role, frame in frames.items():
                        clicks = await frame.evaluate('glintTrustedClicks')
                        assert len(clicks) == (2 if role == 'main' else 1)
                        assert all(click['trusted'] and click['inside'] for click in clicks)
                        evidence['replay_click_counts'][role] = len(clicks)
                    evidence['passed'] = True
                    save()
                finally:
                    try:
                        if session is not None:
                            await session.detach()
                    finally:
                        await replay.close(force=True)
        report.update(passed=all(row['passed'] for row in report['runs']), measurement_complete=True)

    try:
        asyncio.run(run())
    except Exception as error:
        report.update(error_type=type(error).__name__, error=str(error), passed=False)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        report['postguards_passed'] = not thread.is_alive() and all(sha(path) == value for path, value in inputs.items())
        report['passed'] = report['passed'] and report['postguards_passed']
        save()
    print(json.dumps({key: report.get(key) for key in ('passed', 'measurement_complete', 'error', 'postguards_passed')}))
    return 0 if report['passed'] else 1


if __name__ == "__main__":
    raise SystemExit(main())
