"""Renderer/browser crash observations without a pre-crash graceful checkpoint."""

import asyncio
from dataclasses import replace
import os
from pathlib import Path
import runpy
import threading
import time

ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = ROOT / 'native/drafts/protected-gpu-v2/validate.py'
INPUTS = {VALIDATOR, *(ROOT / 'scripts' / name for name in (
    'verify_native_runtime.py', 'verify_native_canvas.py', 'verify_native_gpu_readback.py',
    'verify_native_gpu.py', 'verify_native_hardware.py', 'verify_native_worker_startup.py'))}
validation = runpy.run_path(str(VALIDATOR))
STORES = ('cookie', 'local', 'indexed', 'cached', 'workers')
STORAGE_SCOPE = '/owned-crash-storage/'


def storage_script():
    from scripts.verify_native_runtime import STORAGE

    replacements = {
        "register('/worker.js')": "register('/worker.js', {scope: '/owned-crash-storage/'})",
        'workers: workers.length': "workers: workers.filter(worker => new URL(worker.scope).pathname === '/owned-crash-storage/').length",
    }
    for before, after in replacements.items():
        if STORAGE.count(before) != 1:
            raise ValueError('The exact existing storage fixture is required')
        STORAGE = STORAGE.replace(before, after)
    return STORAGE


def expected_storage(value):
    return dict(cookie='owned=' + value, local=value, indexed=value, cached=value, workers=1)


def storage_components(observed, expected):
    if not isinstance(observed, dict) or set(observed) != set(expected) or set(expected) != set(STORES):
        raise ValueError('All five exact persistent store observations are required')
    return {name: type(observed[name]) is type(expected[name]) and observed[name] == expected[name] for name in STORES}


def selfcheck():
    return dict(prepared_crash_kinds=['renderer', 'browser'],
                prepared_modes=['baseline', 'native', 'gamma-1400-contrast-300'],
                graceful_checkpoint_before_crash=False, browser_started=False, production_admitted=False)


async def wait_owned_exit(owned):
    from scripts.verify_native_runtime import process_snapshot, same_process

    deadline = asyncio.get_running_loop().time() + 30
    while True:
        current = await asyncio.to_thread(process_snapshot)
        remaining = [pid for pid, row in owned.items() if same_process(current.get(pid), row)]
        if not remaining:
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise RuntimeError('Observed owned processes survived crash cleanup')
        await asyncio.sleep(0.5)


async def settle_crash_request(task, *, timeout=5):
    if task.cancelled():
        raise RuntimeError('Crash command was cancelled instead of settled')
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
    except TimeoutError:
        raise RuntimeError('Crash command remains pending after owned runtime teardown') from None
    except Exception as error:
        return dict(settled=True, error_type=type(error).__name__)
    return dict(settled=True)


async def measure(make, configuration):
    from playwright.async_api import Error as PlaywrightError
    from app.core.native.process_monitor import browser_pid
    from scripts.verify_native_canvas import observe
    from scripts.verify_native_gpu_readback import READBACK_READ, ReadbackFixtureHandler
    from scripts.verify_native_runtime import (FixtureServer, check_lock,
        process_snapshot, controller_descendants)
    from scripts.verify_native_worker_startup import StartupConfiguration, browser_arguments

    STORAGE = storage_script()
    result = dict(passed=False, measurement_complete=False, phases=[], production_admitted=False,
                  graceful_checkpoint_before_crash=False, physical_gpu_reset_tested=False)
    server = FixtureServer(('127.0.0.1', 0), ReadbackFixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = 'http://127.0.0.1:' + str(server.server_port)
    storage_origin = origin + STORAGE_SCOPE
    baselines = {}
    try:
        for kind in ('renderer', 'browser'):
            for mode in ('baseline', 'native', 'gamma-1400-contrast-300'):
                protected = mode != 'baseline'
                selected = (replace(configuration, rendering_preset=mode) if protected else
                            StartupConfiguration(bootstrap_policy='surfaces',
                                disabled_features_argument=configuration.disabled_features_argument,
                                ignored_driver_argument=configuration.ignored_driver_argument))
                phase = dict(kind=kind, mode=mode, protected=protected, passed=False,
                             resources_closed=False, graceful_checkpoint_before_crash=False)
                result['phases'].append(phase)
                runtimes = []
                owned = {}
                snapshot = None
                crash_request = None
                try:
                    if protected and kind not in baselines:
                        raise ValueError('Protected recovery requires a validated matched GPU baseline')
                    snapshot = await asyncio.to_thread(process_snapshot)
                    contexts = []
                    for name in ('victim', 'survivor'):
                        runtime = make('-'.join((kind, mode, name)), selected)
                        runtimes.append(runtime)
                        contexts.append(await runtime.start(headless=True))
                    victim, survivor = runtimes
                    context, other = contexts
                    page, other_page = context.pages[0], other.pages[0]
                    for item in contexts:
                        arguments = await browser_arguments(item)
                        if any(value not in arguments for value in selected.launch_arguments()):
                            raise ValueError('Effective crash-test arguments differ from the selected policy')
                    phase['effective_arguments_verified'] = True
                    phase['before'] = await asyncio.wait_for(observe(context, origin, read=READBACK_READ), timeout=180)
                    phase['before_validation'] = validation['validate'](phase['before'], pipeline_version=2,
                        protected=protected, baseline=baselines.get(kind) if protected else None)
                    if not protected:
                        baselines[kind] = phase['before']
                    await page.goto(storage_origin)
                    await other_page.goto(storage_origin)
                    blank = dict(cookie='', local=None, indexed=None, cached=None, workers=0)
                    if await page.evaluate(STORAGE, None) != blank or await other_page.evaluate(STORAGE, None) != blank:
                        raise ValueError('Crash fixtures did not start with separate empty stores')
                    survivor_value = '-'.join((kind, mode, 'survivor'))
                    victim_value = '-'.join((kind, mode, 'victim'))
                    await other_page.evaluate(STORAGE, survivor_value)
                    browser = context.browser
                    root_session = await browser.new_browser_cdp_session()
                    before_pid = browser_pid(await root_session.send('SystemInfo.getProcessInfo'))
                    signal = asyncio.Event()
                    disconnects = []
                    crashes = []
                    def disconnected(*_, rows=disconnects, event=signal, notify=kind == 'browser'):
                        rows.append(True)
                        if notify:
                            event.set()
                    def crashed(*_, rows=crashes, event=signal, notify=kind == 'renderer'):
                        rows.append(True)
                        if notify:
                            event.set()
                    browser.on('disconnected', disconnected)
                    page.on('crash', crashed)
                    target = root_session if kind == 'browser' else await context.new_cdp_session(page)
                    owned.update(controller_descendants(snapshot, await asyncio.to_thread(process_snapshot), os.getpid()))
                    written = await page.evaluate(STORAGE, victim_value)
                    if not all(storage_components(written, expected_storage(victim_value)).values()):
                        raise ValueError('The victim write was not acknowledged by every storage API')
                    written_at = time.monotonic_ns()
                    phase['crash_command'] = 'Browser.crash' if kind == 'browser' else 'Page.crash'
                    started = time.monotonic_ns()
                    crash_request = asyncio.create_task(target.send(phase['crash_command']))
                    try:
                        await asyncio.wait_for(asyncio.shield(crash_request), timeout=10)
                        phase['crash_command_returned'] = True
                    except (PlaywrightError, TimeoutError) as error:
                        phase['crash_command_returned'] = False
                        phase['crash_transport_error_type'] = type(error).__name__
                    await asyncio.wait_for(signal.wait(), timeout=15)
                    phase.update(crash_signal_observed=True, write_to_command_start_ns=started-written_at,
                                 write_to_signal_observed_ns=time.monotonic_ns()-written_at)
                    if await check_lock(victim.profile_dir, victim.executable) != 0:
                        raise ValueError('Crash released the profile lock before owned runtime teardown')
                    phase['in_process_lock_retained_until_teardown'] = True
                    phase['survivor_after_crash'] = await other_page.evaluate(STORAGE, None)
                    if phase['survivor_after_crash'] != expected_storage(survivor_value):
                        raise ValueError('Victim crash affected the neighbouring profile')
                    owned.update(controller_descendants(snapshot, await asyncio.to_thread(process_snapshot), os.getpid()))
                    phase.update(browser_connected_after_crash=browser.is_connected(),
                                 browser_disconnect_notifications=len(disconnects),
                                 page_crash_notifications=len(crashes))
                    if kind == 'renderer':
                        if not browser.is_connected() or disconnects or not crashes:
                            raise ValueError('Renderer crash did not preserve the browser connection')
                        if browser_pid(await root_session.send('SystemInfo.getProcessInfo')) != before_pid:
                            raise ValueError('Renderer crash changed the owned browser root')
                        phase['same_browser_preserved'] = True
                        replacement = await context.new_page()
                        await page.close()
                    else:
                        if browser.is_connected() or len(disconnects) != 1:
                            raise ValueError('Browser crash did not terminate the owned browser connection')
                        await victim.close()
                        context = await victim.start(headless=True)
                        replacement = context.pages[0]
                        phase['browser_restarted'] = True
                    await replacement.goto(storage_origin)
                    phase['restored_storage'] = await replacement.evaluate(STORAGE, None)
                    phase['storage_components'] = storage_components(phase['restored_storage'], expected_storage(victim_value))
                    arguments = await browser_arguments(context)
                    if any(value not in arguments for value in selected.launch_arguments()):
                        raise ValueError('Recovered renderer/browser lost the requested policy arguments')
                    phase['after'] = await asyncio.wait_for(observe(context, origin, read=READBACK_READ), timeout=180)
                    phase['after_validation'] = validation['validate'](phase['after'], pipeline_version=2,
                        protected=protected, baseline=baselines.get(kind) if protected else None, previous=phase['before'])
                    phase['gpu_recovery_verified'] = True
                    if await other_page.evaluate(STORAGE, None) != expected_storage(survivor_value):
                        raise ValueError('Recovery affected the neighbouring profile')
                    phase['survivor_preserved'] = True
                    phase['passed'] = all(phase['storage_components'].values())
                    owned.update(controller_descendants(snapshot, await asyncio.to_thread(process_snapshot), os.getpid()))
                except Exception as error:
                    phase.update(error_type=type(error).__name__, error=str(error)[:3000])
                finally:
                    cleanup_errors = []
                    if snapshot is not None:
                        try:
                            owned.update(controller_descendants(snapshot, await asyncio.to_thread(process_snapshot), os.getpid()))
                        except Exception as error:
                            cleanup_errors.append(dict(type=type(error).__name__, error=str(error)[:1000]))
                    for runtime in reversed(runtimes):
                        try:
                            await runtime.close()
                        except Exception as error:
                            cleanup_errors.append(dict(type=type(error).__name__, error=str(error)[:1000]))
                    if crash_request is not None:
                        try:
                            phase['crash_request'] = await settle_crash_request(crash_request)
                        except Exception as error:
                            cleanup_errors.append(dict(type=type(error).__name__, error=str(error)[:1000]))
                    try:
                        await wait_owned_exit(owned)
                    except Exception as error:
                        cleanup_errors.append(dict(type=type(error).__name__, error=str(error)[:1000]))
                    phase['cleanup_errors'] = cleanup_errors
                    phase['resources_closed'] = not cleanup_errors and all(not runtime.has_resources for runtime in runtimes)
                    phase['passed'] = phase['passed'] and phase['resources_closed']
                if not phase['resources_closed']:
                    return result
        result['measurement_complete'] = len(result['phases']) == 6 and all(
            'after_validation' in phase and 'storage_components' in phase for phase in result['phases'])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        result['fixture_thread_closed'] = not thread.is_alive()
        result['resources_closed'] = result['fixture_thread_closed'] and all(phase['resources_closed'] for phase in result['phases'])
        result['passed'] = result['measurement_complete'] and result['resources_closed'] and all(phase['passed'] for phase in result['phases'])
    return result
