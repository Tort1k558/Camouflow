"""Owned protected manager screen/BFCache and top-document Canvas continuity probe."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import threading

import argparse

ROOT = Path(__file__).resolve().parents[4]
async def read_restored_surfaces(session, read):
    result = await session.send('Runtime.evaluate', {
        'expression': '(' + read + ')()', 'awaitPromise': True,
        'returnByValue': True, 'timeout': 30000})
    if (not isinstance(result, dict) or 'exceptionDetails' in result
            or not isinstance(result.get('result', {}).get('value'), dict)):
        raise ValueError('Restored GPU/Audio evaluation failed')
    return result['result']['value']


def main() -> int:
    parser = argparse.ArgumentParser(description='Owned protected manager screen/BFCache and Canvas continuity probe')
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--driver-stage', type=Path, required=True)
    parser.add_argument('--probe', choices=('canvas', 'combined', 'retained-documents', 'retained-workers', 'retained-gpu-objects'), default='canvas')
    parser.add_argument('--verify-service-lifecycle', action='store_true',
                        help='Verify owned service-controlled BFCache and explicit per-version stop/restart')
    args = parser.parse_args()
    if args.verify_service_lifecycle and args.probe != 'retained-workers':
        parser.error('--verify-service-lifecycle requires --probe retained-workers')
    OUT, STAGE, EXE = args.work_dir, args.driver_stage, args.executable
    MANIFEST = ROOT / 'native/drafts/environment/playwright-driver-stage-binding-close.json'
    for path in (OUT, STAGE, EXE):
        if (not path.is_absolute() or path != path.resolve() or path.is_symlink() or path.is_junction()):
            parser.error('Use canonical absolute unlinked paths')
    if (sys.platform != 'win32' or OUT.drive.upper() != 'D:' or OUT.exists() or not OUT.parent.is_dir()
            or OUT.is_relative_to(ROOT) or OUT.is_relative_to(EXE.parent) or EXE.is_relative_to(OUT)
            or OUT.is_relative_to(STAGE) or STAGE.is_relative_to(OUT)
            or EXE.drive.upper() != 'D:' or not EXE.is_file() or EXE.name != 'chrome.exe'):
        parser.error('Select a fresh external D: output and preserved Windows runtime')
    OUT.mkdir(exist_ok=False)
    (OUT / 'temp').mkdir()
    os.environ.update(PYTHONDONTWRITEBYTECODE='1', CAMOUFLOW_DATA_DIR=str(OUT / 'workspace'),
                      TMP=str(OUT / 'temp'), TEMP=str(OUT / 'temp'),
                      PLAYWRIGHT_NODEJS_PATH=str(STAGE / 'playwright/driver/node.exe'))
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(ROOT), str(STAGE)]
    from scripts.native_driver_stage import verify
    verify(STAGE, MANIFEST)
    from app.core.native.runtime import NativeRuntime
    from scripts import verify_native_gpu_readback as gpu
    from scripts import verify_native_surfaces as surfaces
    from scripts import verify_native_worker_startup as workers
    from scripts import verify_native_runtime as helpers
    from dataclasses import dataclass


    @dataclass(frozen=True)
    class Configuration(gpu.ReadbackConfiguration):
        def context_options(self):
            options = super().context_options()
            options['ignore_default_args'] = [*options.get('ignore_default_args', []), '--disable-back-forward-cache']
            return options

        def launch_arguments(self):
            arguments = super().launch_arguments()
            indices = [index for index, value in enumerate(arguments) if value.startswith('--enable-features=')]
            if len(indices) != 1:
                raise ValueError('One explicit feature argument required')
            arguments[indices[0]] += ',GlintAudioMathCandidate'
            return arguments


    FIXTURE = ROOT / 'native/drafts/environment/first-script'
    probe = runpy.run_path(str(FIXTURE / 'lifecycle.py'))
    reference = probe['REFERENCE']
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    core = reference['measure_runtime_core'](EXE)
    receipt_path = EXE.parent / 'camouflow-build.json'
    receipt = receipt_path.read_bytes()
    candidate = reference['build'].load_candidate('upstream-156')
    reference['validate_build_receipt'](json.loads(receipt), candidate['lock'], candidate=candidate)
    if core != json.loads(receipt)['runtime_core_sha256_measured']:
        raise ValueError('Runtime core differs from receipt')
    if gpu.validate_receipt(EXE, core, derivation_mode='profile-identity', candidate_name='upstream-156') != receipt:
        raise ValueError('GPU receipt differs')
    canvas_path = FIXTURE / 'canvas_formats.py'
    canvas_fixture = runpy.run_path(str(canvas_path))
    canvas_read = canvas_fixture['READ']
    validator_path = FIXTURE / 'protected_history.py'
    validator = runpy.run_path(str(validator_path))['validate_runs']
    surface_validator = None
    surface_read = None
    recapture_surfaces_history = None
    if args.probe in {'combined', 'retained-documents', 'retained-workers'}:
        surface_validator = runpy.run_path(str(FIXTURE / 'protected_surface_history.py'))['validate_runs']
        recapture_surfaces_history = runpy.run_path(str(FIXTURE / 'managed_history.py'))['recapture_retained_history']
        surface_read = f"async () => ({{gpu: await ({gpu.READBACK_READ})(), audio: await ({surfaces.AUDIO_READ})(true)}})"
    if args.probe in {'retained-documents', 'retained-workers', 'retained-gpu-objects'}:
        import retained_document_surfaces as retained

    retained_objects = None
    if args.probe == 'retained-gpu-objects':
        import retained_gpu_objects as retained_objects
        surface_read = retained_objects.READ
        surface_validator = None
        recapture_surfaces_history = runpy.run_path(str(FIXTURE / 'managed_history.py'))['recapture_retained_history']

    worker_fixture = None
    worker_read = None
    if args.probe == 'retained-workers':
        import retained_worker_lifecycle as worker_fixture
        worker_canvas_read = runpy.run_path(str(FIXTURE / 'worker_formats.py'))['worker_read'](canvas_read)
        worker_read = f"async () => ({{canvas: await ({worker_canvas_read})(), gpu: await ({gpu.READBACK_READ})(), audio: await ({surfaces.AUDIO_READ})(true)}})"

    controlled_services = None
    if args.verify_service_lifecycle:
        import controlled_service_workers as controlled_services

    paths = {Path(__file__), MANIFEST, canvas_path, validator_path, *(ROOT / name for name in gpu.probe_inputs()), ROOT / 'app/core/native/runtime.py', ROOT / 'app/core/native/identity.py', *FIXTURE.glob('*.py'), FIXTURE / 'sample.js',
             STAGE / 'playwright/driver/package/lib/coreBundle.js', STAGE / 'playwright/_impl/_page.py',
             STAGE / 'playwright/driver/node.exe', *(ROOT / name for name in reference['environment'].source_inputs())}
    inputs = {path: sha(path) for path in paths}
    report = dict(schema=1, passed=False, measurement_complete=False, runs=[], errors=[],
                  scope='Protected Canvas/WebGL/AudioMath flags with manager viewport, two pages and BFCache; top-document Canvas format stability only, not full combined lifecycle admission',
                  privacy_admitted=False, production_admitted=False,
                  runtime_core_sha256_measured=core, receipt_sha256=hashlib.sha256(receipt).hexdigest(),
                  measured_inputs_sha256={str(path): value for path, value in inputs.items()})
    if args.probe in {'combined', 'retained-documents', 'retained-workers'}:
        report.update(probe=args.probe, scope='Protected manager BFCache with screen, Canvas formats and top-document recreated GPU/Audio readback continuity; not retained GPU objects, worker lifecycle, WebGPU readback or full policy admission')


    if args.probe in {'retained-documents', 'retained-workers', 'retained-gpu-objects'}:
        report['scope'] = 'Six registered real documents with recreated protected GPU/Audio reads before/after actual BFCache; source/window/origin/nonce/URL/timeOrigin checked; not retained GPU objects, workers, WebGPU readback or full policy admission'

    if retained_objects is not None:
        report['scope'] = 'Original WebGL1/2 resources, known textured draw, framebuffer/default reads and PNG across six genuine BFCache documents; not recreated Audio/GPU full coverage, workers, WebGPU, profile isolation or privacy/release admission'

    if worker_fixture is not None:
        report['scope'] += '; six actual classic/module worker policy observations around document BFCache; dedicated/shared instance retention, service restart classification; service does not control the primary restored document, no retained GPU objects or WebGPU readback admission'

    if controlled_services is not None:
        report['scope'] += '; additional classic/module service-controlled clients with genuine BFCache and confirmed per-version stop/restart'

    def save():
        (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


    async def capture():
        async with reference['async_playwright']() as driver:
            discovery = NativeRuntime(OUT / 'discovery', EXE, surfaces.SurfaceConfiguration())
            try:
                discovery_context = await discovery.start(headless=True)
                measured = await workers.browser_arguments(discovery_context)
                original = next(value for value in measured if value.startswith('--disable-features='))
                replacement = workers.partitioning_argument(measured)
            finally:
                await discovery.close()
            for mode in ('manager-desktop', 'manager-mobile-web'):
                requested = reference['environment'].configuration_for_mode(mode)
                config = Configuration(environment=requested.environment, width=requested.width,
                    height=requested.height, device_scale_factor=requested.device_scale_factor,
                    probe_mode='ready', derivation_mode='profile-identity',
                    disabled_features_argument=replacement, ignored_driver_argument=original)
                row = dict(mode=mode, passed=False, phases=[], fixture_port=server.server_port)
                report['runs'].append(row)
                before_processes = await asyncio.to_thread(helpers.process_snapshot)
                runtime = NativeRuntime(OUT / mode, EXE, config)
                context = await runtime.start(headless=True)
                effective = await workers.browser_arguments(context)
                if any(value not in effective for value in config.launch_arguments()):
                    await runtime.close()
                    raise ValueError('Protected launch arguments were not effective')
                row['protected_arguments_verified'] = True
                owned = {}
                browser = context.browser
                try:
                    owned.update(helpers.controller_descendants(before_processes, await asyncio.to_thread(helpers.process_snapshot), os.getpid()))
                    pages = [context.pages[0], await context.new_page()]
                    initial = []
                    for page in pages:
                        await page.goto(f'http://127.0.0.1:{server.server_port}/screen?role=main', timeout=10000)
                        observed = await probe['capture_page'](page)
                        expected = observed['main']['snapshot']['screen']
                        errors = probe['validate_page'](observed, expected)
                        initial.append(expected)
                        row['phases'].append(dict(phase='initial', observed=observed, errors=errors))
                    assert initial[0] == initial[1], 'Pages in one context disagree at initialization'
                    for index in (0, 1, 0):
                        observed = await probe['capture_page'](pages[index])
                        errors = probe['validate_page'](observed, initial[index])
                        row['phases'].append(dict(phase='focus-restore', page=index, observed=observed, errors=errors))
                    session = await context.new_cdp_session(pages[1])
                    try:
                        await session.send('Page.enable')
                        if controlled_services is not None:
                            service_versions = await controlled_services.subscribe(session)
                        before = await probe['capture_page'](pages[1])
                        canvas_before = await pages[1].evaluate(canvas_read)
                        assert canvas_before['float16Available'] and len(canvas_before['rows']) == 32
                        assert all('error' not in value and value['observed']['finite'] and
                            value['observed']['hash'] == value['observed']['repeat'] for value in canvas_before['rows'])
                        if surface_read is not None:
                            row['surfaces_before'] = await pages[1].evaluate(surface_read)
                            if worker_fixture is not None:
                                worker_token = await worker_fixture.install(pages[1])
                                row['worker_lifecycle_before'] = await worker_fixture.collect(session, worker_token, persisted=False)
                            if args.probe in {'retained-documents', 'retained-workers', 'retained-gpu-objects'}:
                                registration = await retained.install(pages[1], before, surface_read)
                                row['retained_documents_before'] = await retained.collect(session, registration, persisted=False)
                        state = await probe['restore_history'](pages[1], session, before, row)
                        observed = probe['restored_observations'](state)
                        restored = await session.send('Runtime.evaluate', {'expression': '(' + canvas_read + ')()',
                            'awaitPromise': True, 'returnByValue': True, 'timeout': 15000})
                        if restored.get('exceptionDetails'):
                            raise ValueError('Restored Canvas evaluation failed')
                        canvas_after = restored['result']['value']
                        row['canvas_stable_across_bfcache'] = canvas_before == canvas_after
                        if not row['canvas_stable_across_bfcache']:
                            raise ValueError('Canvas formats changed across BFCache restoration')
                        row['canvas_context_cases'] = len(canvas_before['rows'])
                        row['canvas_before'] = canvas_before
                        row['canvas_after'] = canvas_after
                        if surface_read is not None:
                            row['surfaces_after'] = await read_restored_surfaces(session, surface_read)
                            if args.probe in {'retained-documents', 'retained-workers', 'retained-gpu-objects'}:
                                row['retained_documents_after'] = await retained.collect(session, registration, persisted=True)
                                if retained_objects is not None:
                                    row['retained_gpu_object_validation'] = retained_objects.validate_pair(row['retained_documents_before'], row['retained_documents_after'])
                                else:
                                    row['retained_document_validation'] = retained.validate_pair(row['retained_documents_before'], row['retained_documents_after'])
                                if worker_fixture is not None:
                                    row['worker_lifecycle_after'] = await worker_fixture.collect(session, worker_token, persisted=True)
                                    row['worker_lifecycle_validation'] = worker_fixture.validate_pair(row['worker_lifecycle_before'], row['worker_lifecycle_after'], canvas_document=canvas_before, document_gpu=row['surfaces_before']['gpu'])
                                    if controlled_services is not None:
                                        row['controlled_service_validation'] = await controlled_services.capture(context, session, service_versions, row, probe, recapture_surfaces_history, initial[1])
                                    row['worker_lifecycle_cleanup'] = await read_restored_surfaces(session, 'async () => await window.glintRetainedWorkers.close()')
                            post_surfaces = await recapture_surfaces_history(session, state)
                            observed = probe['restored_observations'](post_surfaces)
                            row['post_surfaces_history'] = post_surfaces
                            row['post_surfaces_screen_verified'] = not probe['validate_page'](observed, initial[1])
                        errors = probe['validate_page'](observed, initial[1])
                        row['bfcache_restored'] = (probe['history_restored'](state) and
                            row['history_navigation'].get('type') == 'BackForwardCacheRestore')
                        if not row['bfcache_restored']:
                            errors.append('BFCache restoration not proven')
                        row['phases'].append(dict(phase='history-return', observed=observed, errors=errors))
                    finally:
                        await session.detach()
                    row['passed'] = all(not phase['errors'] for phase in row['phases'])
                finally:
                    try:
                        owned.update(helpers.controller_descendants(before_processes, await asyncio.to_thread(helpers.process_snapshot), os.getpid()))
                    finally:
                        await runtime.close()
                    async def wait_owned():
                        while True:
                            current = await asyncio.to_thread(helpers.process_snapshot)
                            if not any(helpers.same_process(current.get(pid), value) for pid, value in owned.items()):
                                return
                            await asyncio.sleep(0.05)
                    await asyncio.wait_for(wait_owned(), timeout=15)
                    row['observed_processes'] = len(owned)
                    row['remaining_observed_processes'] = 0
                    row['runtime_resources_released'] = not runtime.has_resources
                    row['browser_connection_closed'] = not browser.is_connected()
                    row['passed'] = row['passed'] and row['browser_connection_closed']
                    save()
            report['measurement_complete'] = True
            report['validation'] = validator(report['runs'], probe['validate_page'], canvas_fixture['compare_formats'])
            report['passed'] = report['validation']['passed']
            if retained_objects is not None:
                report['retained_gpu_object_validation'] = retained_objects.validate_runs(report['runs'])
                report['passed'] = report['passed'] and report['retained_gpu_object_validation']['passed']
            if args.probe in {'retained-documents', 'retained-workers'}:
                report['retained_document_coverage'] = all(row['retained_document_validation']['passed'] for row in report['runs'])
                report['passed'] = report['passed'] and report['retained_document_coverage']
            if surface_validator is not None:
                report['surface_validation'] = surface_validator(report['runs'])
                report['passed'] = report['passed'] and report['surface_validation']['passed']
            if worker_fixture is not None:
                report['worker_lifecycle_validation'] = worker_fixture.validate_runs(report['runs'])
                report['passed'] = report['passed'] and report['worker_lifecycle_validation']['passed']
            if controlled_services is not None:
                report['controlled_service_validation'] = controlled_services.validate_runs(report['runs'], probe['restored_observations'], probe['validate_page'])
                report['passed'] = report['passed'] and report['controlled_service_validation']['passed']


    server = (probe['create_server']() if worker_fixture is None else
              probe['ThreadingHTTPServer'](('127.0.0.1', 0), (worker_fixture.server_type(probe['CacheableHandler'], worker_read) if controlled_services is None else
               controlled_services.server_type(worker_fixture.server_type(probe['CacheableHandler'], worker_read)))))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    save()
    try:
        asyncio.run(capture())
    except Exception as error:
        report['errors'].append(dict(type=type(error).__name__, error=str(error)))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        verify(STAGE, MANIFEST)
        report['postguards_passed'] = (not thread.is_alive() and receipt_path.read_bytes() == receipt and
            reference['measure_runtime_core'](EXE) == core and all(sha(path) == value for path, value in inputs.items())
            and gpu.validate_receipt(EXE, core, derivation_mode='profile-identity', candidate_name='upstream-156') == receipt)
        report['passed'] = report['passed'] and report['postguards_passed'] and not report['errors']
        save()
    print(json.dumps({k: report[k] for k in ('passed', 'measurement_complete', 'postguards_passed', 'errors')}))
    return 0 if report['passed'] else 1


if __name__ == "__main__":
    raise SystemExit(main())
