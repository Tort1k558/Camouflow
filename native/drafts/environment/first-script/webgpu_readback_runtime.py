"""Owned staged-driver WebGPU compatibility, not native readback protection."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[4]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--driver-stage', type=Path, required=True)
    args = parser.parse_args()
    output, executable, stage = args.work_dir, args.executable, args.driver_stage
    paths = (output, executable, stage)
    if (sys.platform != 'win32' or any(not path.is_absolute() or path != path.resolve()
            or path.is_symlink() or path.is_junction() or path.drive.upper() != 'D:' for path in paths)
            or output.exists() or not output.parent.is_dir() or not executable.is_file()
            or executable.name != 'chrome.exe' or not stage.is_dir()
            or any(output.is_relative_to(path) or path.is_relative_to(output)
                   for path in (ROOT, executable.parent, stage))):
        parser.error('Use canonical preserved Windows runtime, staged driver and fresh external D: output')
    output.mkdir(exist_ok=False)
    (output / 'temp').mkdir()
    os.environ.update(PYTHONDONTWRITEBYTECODE='1', TMP=str(output / 'temp'), TEMP=str(output / 'temp'),
        CAMOUFLOW_DATA_DIR=str(output / 'workspace'), PLAYWRIGHT_NODEJS_PATH=str(stage / 'playwright/driver/node.exe'))
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(ROOT), str(stage)]
    from scripts.native_driver_stage import verify

    manifest = ROOT / 'native/drafts/environment/playwright-driver-stage-binding-close.json'
    report = dict(schema=1, passed=False, measurement_complete=False, rows=[], runs=[], errors=[],
        scope=__doc__, privacy_admitted=False, production_admitted=False)
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    server = thread = None
    core = receipt = inputs = None

    def save():
        temporary = output / 'report.tmp'
        temporary.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        temporary.replace(output / 'report.json')

    try:
        verify(stage, manifest)
        from scripts.verify_native_gpu_readback import ReadbackConfiguration, validate_receipt, probe_inputs
        from scripts import verify_native_runtime as helpers
        from scripts.verify_native_worker_startup import browser_arguments, partitioning_argument
        from app.core.native.runtime import NativeRuntime
        import webgpu_readback as probe

        core = helpers.measure_runtime_core(executable)
        receipt = validate_receipt(executable, core, derivation_mode='profile-identity', candidate_name='upstream-156')
        measured = {Path(__file__), Path(probe.__file__), probe.SOURCE, manifest,
            ROOT / 'app/core/native/runtime.py', *(ROOT / name for name in probe_inputs())}
        inputs = {path: digest(path) for path in measured}
        source = probe.SOURCE.read_text(encoding='utf-8-sig')
        report.update(runtime_core_sha256_measured=core, receipt_sha256=hashlib.sha256(receipt).hexdigest(),
            measured_inputs_sha256={str(path): value for path, value in inputs.items()})

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/':
                    body, content_type = '<!doctype html><title>Owned WebGPU fixture</title>', 'text/html; charset=utf-8'
                elif self.path in {'/' + kind + '.js' for kind in ('dedicated', 'shared', 'service')}:
                    body = probe.worker_source(source, self.path[1:-3])
                    content_type = 'text/javascript; charset=utf-8'
                else:
                    self.send_error(404)
                    return
                payload = body.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        async def capture():
            discovery = NativeRuntime(output / 'discovery', executable, ReadbackConfiguration(probe_mode='baseline'))
            try:
                context = await discovery.start(headless=True)
                disabled = [value for value in await browser_arguments(context) if value.startswith('--disable-features=')]
                if len(disabled) != 1:
                    raise ValueError('Expected exactly one measured driver exclusion argument')
                original = disabled[0]
                replacement = partitioning_argument([original])
                report['driver_partitioning'] = dict(original=original, replacement=replacement)
            finally:
                await discovery.close()
            for mode in ('baseline', 'ready'):
                config = ReadbackConfiguration(probe_mode=mode, derivation_mode='profile-identity',
                    disabled_features_argument=replacement, ignored_driver_argument=original)
                runtime = NativeRuntime(output / mode, executable, config)
                before = await asyncio.to_thread(helpers.process_snapshot)
                owned = {}
                browser = None
                row = dict(mode=mode, passed=False)
                report['runs'].append(row)
                try:
                    context = await runtime.start(headless=True)
                    browser = context.browser
                    effective = await browser_arguments(context)
                    if any(value not in effective for value in config.launch_arguments()):
                        raise ValueError('Requested protected/partitioning arguments not effective')
                    row['arguments_verified'] = True
                    owned.update(helpers.controller_descendants(before, await asyncio.to_thread(helpers.process_snapshot), os.getpid()))
                    page = await context.new_page()
                    await page.goto(f'http://127.0.0.1:{server.server_port}/', wait_until='load')
                    value = await asyncio.wait_for(page.evaluate('async () => {' + source + '; return await probeWebGPU();}'), 90)
                    report['rows'].append(dict(mode=mode, context='document', value=value))
                    probe.validate_observation(value)
                    save()
                    for kind in ('dedicated', 'shared', 'service'):
                        for script_type in ('classic', 'module'):
                            value = await asyncio.wait_for(page.evaluate(probe.WORKER_READ,
                                dict(kind=kind, scriptType=script_type, url='/' + kind + '.js')), 105)
                            report['rows'].append(dict(mode=mode, context=script_type + '-' + kind + '-worker', value=value))
                            probe.validate_observation(value)
                            save()
                    if await page.evaluate('async () => (await navigator.serviceWorker.getRegistrations()).length') != 0:
                        raise ValueError('Owned service registrations remain')
                    row['service_registrations_released'] = True
                    row['passed'] = True
                finally:
                    try:
                        owned.update(helpers.controller_descendants(before, await asyncio.to_thread(helpers.process_snapshot), os.getpid()))
                    finally:
                        await runtime.close()
                    async def wait_owned():
                        while True:
                            current = await asyncio.to_thread(helpers.process_snapshot)
                            if not any(helpers.same_process(current.get(pid), value) for pid, value in owned.items()):
                                return
                            await asyncio.sleep(0.05)
                    await asyncio.wait_for(wait_owned(), 15)
                    row.update(observed_processes=len(owned), remaining_observed_processes=0,
                        runtime_resources_released=not runtime.has_resources,
                        browser_connection_closed=browser is not None and not browser.is_connected())
                    if runtime.has_resources or browser is None or browser.is_connected() or len(owned) <= 1:
                        raise ValueError('Owned runtime/process cleanup not verified')
                    save()
            report['validation'] = probe.validate_rows(report['rows'])
            report.update(passed=True, measurement_complete=True)

        save()
        asyncio.run(capture())
    except Exception as error:
        report['errors'].append(dict(type=type(error).__name__, error=str(error)))
        report['passed'] = False
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)
        try:
            verify(stage, manifest)
            report['postguards_passed'] = (core is not None and inputs is not None
                and (thread is None or not thread.is_alive())
                and helpers.measure_runtime_core(executable) == core
                and validate_receipt(executable, core, derivation_mode='profile-identity', candidate_name='upstream-156') == receipt
                and all(path.is_file() and digest(path) == value for path, value in inputs.items()))
        except Exception as error:
            report['postguards_passed'] = False
            report['errors'].append(dict(type=type(error).__name__, error=str(error)))
        report['passed'] = report['passed'] and report.get('postguards_passed') is True and not report['errors']
        save()
    print(json.dumps({key: report.get(key) for key in ('passed', 'measurement_complete', 'postguards_passed', 'errors')}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
