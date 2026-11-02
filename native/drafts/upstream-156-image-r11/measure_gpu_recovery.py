"""Owned GPU-process crash recovery; not physical GPU reset or engine admission."""

import asyncio
from dataclasses import replace
from pathlib import Path
import runpy
import threading

ROOT = Path(__file__).resolve().parents[3]
WATCH = ROOT / 'native/drafts/environment/gpu-process-recovery/watch.js'
VALIDATOR = ROOT / 'native/drafts/protected-gpu-v2/validate.py'
INPUTS = {WATCH, VALIDATOR, *(ROOT / 'scripts' / name for name in (
    'verify_native_canvas.py', 'verify_native_gpu.py', 'verify_native_gpu_readback.py',
    'verify_native_hardware.py', 'verify_native_runtime.py', 'verify_native_worker_startup.py'))}
validation = runpy.run_path(str(VALIDATOR))
FRAME_IDS = {'same_origin_frame': 'owned-frame', 'cross_origin_frame': 'cross-origin',
             'about_blank_frame': 'owned-about-blank', 'srcdoc_frame': 'owned-srcdoc'}


def selfcheck():
    return dict(prepared_modes=['baseline', 'native', 'gamma-1400-contrast-300'],
                crash_command='Browser.crashGpuProcess', browser_started=False,
                physical_gpu_reset_tested=False, production_admitted=False)


async def existing_contexts(page, read):
    from scripts.verify_native_canvas import read_owned_context, WORKERS

    observed = {'document': await read_owned_context(page, read, 'document')}
    for name, frame_id in FRAME_IDS.items():
        element = await page.locator('#' + frame_id).element_handle()
        frame = await element.content_frame() if element is not None else None
        if frame is None:
            raise ValueError('Recovery lost an existing frame: ' + name)
        observed[name] = await read_owned_context(frame, read, name)
    observed.update(await read_owned_context(page, WORKERS, 'new-workers-after-recovery', timeout=40))
    return observed


async def measure(make, configuration):
    from scripts.verify_native_canvas import observe
    from scripts.verify_native_gpu_readback import ReadbackFixtureHandler, READBACK_READ
    from scripts.verify_native_runtime import FixtureServer
    from scripts.verify_native_worker_startup import StartupConfiguration, browser_arguments

    result = dict(passed=False, measurement_complete=False, phases=[], resources_closed=False,
                  physical_gpu_reset_tested=False, production_admitted=False)
    server = FixtureServer(('127.0.0.1', 0), ReadbackFixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    baseline = None
    try:
        for name in ('baseline', 'native', 'gamma-1400-contrast-300'):
            protected = name != 'baseline'
            selected = (replace(configuration, rendering_preset=name) if protected else
                        StartupConfiguration(bootstrap_policy='surfaces',
                            disabled_features_argument=configuration.disabled_features_argument,
                            ignored_driver_argument=configuration.ignored_driver_argument))
            phase = dict(name=name, protected=protected, passed=False, resources_closed=False)
            result['phases'].append(phase)
            runtime = session = None
            try:
                if protected and baseline is None:
                    raise ValueError('Protected recovery requires the validated matched baseline')
                runtime = make('gpu-recovery-' + name, selected)
                context = await runtime.start(headless=True)
                arguments = await browser_arguments(context)
                if any(value not in arguments for value in selected.launch_arguments()):
                    raise ValueError('Effective recovery configuration differs from requested arguments')
                phase['effective_arguments_verified'] = True
                phase['before'] = await asyncio.wait_for(observe(context,
                    'http://127.0.0.1:' + str(server.server_port), read=READBACK_READ), timeout=180)
                phase['before_validation'] = validation['validate'](phase['before'], pipeline_version=2,
                    protected=protected, baseline=baseline if protected else None)
                page = context.pages[0]
                frames = tuple(page.frames)
                for index, frame in enumerate(frames):
                    await frame.evaluate('value => {globalThis.__glintRecoveryDocument = value}', index + 731921)
                crashes = []
                page.on('crash', lambda *_: crashes.append(True))
                phase['armed'] = await page.evaluate('async () => {' + WATCH.read_text(encoding='utf-8')
                    + '; return await armOwnedGPURecovery();}')
                if phase['armed'] != dict(armed=True, initialCopyMatched=True, deviceLostCallbacks=0):
                    raise ValueError('Owned GPU loss fixture did not arm exactly')
                session = await context.browser.new_browser_cdp_session()
                phase['browser_before'] = await session.send('Browser.getVersion')
                phase['crash_command_return'] = await session.send('Browser.crashGpuProcess')
                phase['crash_command_completed'] = True
                phase['loss'] = await asyncio.wait_for(page.evaluate(
                    'async () => await globalThis.__glintOwnedGPURecovery.finish()'), timeout=75)
                expected_loss = dict(initialCopyMatched=True, deviceLostCallbacks=1, reason='unknown',
                                     oldMapRejectedWith='AbortError', oldMapState='unmapped')
                if phase['loss'] != expected_loss:
                    raise ValueError('Unexpected GPU device-loss or old-buffer behaviour')
                if crashes or page.is_closed() or tuple(page.frames) != frames:
                    raise ValueError('GPU-process crash replaced or closed an existing document')
                for index, frame in enumerate(frames):
                    if await frame.evaluate('globalThis.__glintRecoveryDocument') != index + 731921:
                        raise ValueError('A document identity changed during GPU recovery')
                phase['existing_documents_preserved'] = len(frames)
                phase['page_crashes'] = len(crashes)
                phase['after'] = await asyncio.wait_for(existing_contexts(page, READBACK_READ), timeout=180)
                phase['after_validation'] = validation['validate'](phase['after'], pipeline_version=2,
                    protected=protected, baseline=baseline if protected else None, previous=phase['before'])
                phase['browser_after'] = await session.send('Browser.getVersion')
                if phase['browser_before'] != phase['browser_after']:
                    raise ValueError('Browser identity changed during GPU recovery')
                await page.evaluate('globalThis.__glintOwnedGPURecovery.close()')
                if not protected:
                    baseline = phase['before']
                phase['passed'] = True
            except Exception as error:
                phase.update(error_type=type(error).__name__, error=str(error)[:3000])
            finally:
                if session is not None:
                    try:
                        await session.detach()
                    except Exception as error:
                        phase.update(passed=False, session_cleanup_error=str(error)[:1000])
                if runtime is not None:
                    try:
                        await runtime.close()
                        phase['resources_closed'] = not runtime.has_resources
                    except Exception as error:
                        phase.update(passed=False, runtime_cleanup_error=str(error)[:1000])
                else:
                    phase['resources_closed'] = True
                if not phase['resources_closed']:
                    phase['passed'] = False
            if not phase['resources_closed']:
                break
        result['measurement_complete'] = len(result['phases']) == 3 and all(
            'after' in phase for phase in result['phases'])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        result['fixture_thread_closed'] = not thread.is_alive()
        result['resources_closed'] = result['fixture_thread_closed'] and all(
            phase['resources_closed'] for phase in result['phases'])
        result['passed'] = result['measurement_complete'] and result['resources_closed'] and all(
            phase['passed'] for phase in result['phases'])
    return result
