"""Owned 4K RGBA8 diagnostic; incomplete process samples never admit resources."""

import asyncio
import hashlib
from pathlib import Path
import runpy
import threading
import time

ROOT = Path(__file__).resolve().parents[3]
PROBE = Path(__file__).with_name('large-rgba-probe.js')
VALIDATOR = Path(__file__).with_name('validate_large_rgba.py')
INPUTS = {PROBE, VALIDATOR, *(ROOT/'app/core/native'/name for name in (
    'process_monitor.py','windows_process_tree.py','windows_process_resources.py'))}


validate = runpy.run_path(str(VALIDATOR))['validate']


def selfcheck():
    return dict(prepared_size=[4096,4096],prepared_full_image_copies=6,rgba8_bytes=67108864,
                probe_sha256=hashlib.sha256(PROBE.read_bytes()).hexdigest(),browser_started=False,
                resource_scope='Sampled owned process-tree private commit and summed working sets, not exact peaks or GPU VRAM')


async def measure(make, configuration):
    from app.core.native.process_monitor import BrowserProcessMonitor
    from scripts.verify_native_runtime import FixtureHandler, FixtureServer

    runtime = make('large-opaque-rgba',configuration)
    server = FixtureServer(('127.0.0.1',0),FixtureHandler)
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    monitor = task = None
    stop = asyncio.Event()
    report = dict(passed=False,measurement_complete=False,samples=[],sampling_errors=[])
    phase = 'navigation'
    report['phase_events'] = [dict(phase=phase, at_ns=time.monotonic_ns())]

    def set_phase(value):
        nonlocal phase
        phase = value
        report['phase_events'].append(dict(phase=value, at_ns=time.monotonic_ns()))

    async def capture(stage):
        started = time.monotonic_ns()
        try:
            measured = await asyncio.to_thread(monitor.sample)
        except Exception as error:
            report['sampling_errors'].append(dict(phase=stage, started_ns=started,
                finished_ns=time.monotonic_ns(), type=type(error).__name__, error=str(error)[:1000]))
            return False
        report['samples'].append(dict(phase=stage, started_ns=started,
            finished_ns=time.monotonic_ns(), **measured))
        return True

    async def sample():
        while not stop.is_set():
            await capture(phase)
            try:
                await asyncio.wait_for(stop.wait(),timeout=0.25)
            except asyncio.TimeoutError:
                pass
    try:
        context = await runtime.start(headless=True)
        monitor = await BrowserProcessMonitor.bind(context)
        if not await capture('before'):
            raise ValueError('Initial resource capture is unavailable')
        task = asyncio.create_task(sample())
        page = await context.new_page()
        await page.goto('http://127.0.0.1:'+str(server.server_port)+'/',timeout=20000)
        set_phase('measurement')
        observed = await asyncio.wait_for(page.evaluate(PROBE.read_text(encoding='utf-8')),timeout=180)
        set_phase('after')
        report['observations'] = observed
        report.update(validate(observed))
    except Exception as error:
        report.update(passed=False,error_type=type(error).__name__,error=str(error)[:3000])
    finally:
        stop.set()
        cleanup_errors = []
        if task is not None:
            try:
                await task
            except Exception as error:
                cleanup_errors.append(dict(stage='sampler',type=type(error).__name__,error=str(error)))
        if monitor is not None:
            await capture('after')
            try:
                await monitor.close()
            except Exception as error:
                cleanup_errors.append(dict(stage='monitor',type=type(error).__name__,error=str(error)))
        try:
            await runtime.close()
        except Exception as error:
            cleanup_errors.append(dict(stage='runtime',type=type(error).__name__,error=str(error)))
        try:
            server.shutdown()
        finally:
            server.server_close()
            thread.join(timeout=5)
        report['cleanup_errors'] = cleanup_errors
        report['sampling_finished_ns'] = time.monotonic_ns()
        report['resource_scope'] = 'Sampled process-tree totals only; missing captures remain errors, not zero, retries or exact peaks'
        report['resources_closed'] = not runtime.has_resources and not thread.is_alive()
        report['resource_measurement_complete'] = (len(report['samples']) >= 3 and not report['sampling_errors']
            and any(row['phase'] == 'measurement' for row in report['samples']))
        if report['samples']:
            report['maximum_sampled_private_commit_bytes'] = max(row['private_commit_sum_bytes'] for row in report['samples'])
            report['maximum_sampled_summed_working_set_bytes'] = max(row['working_set_sum_bytes'] for row in report['samples'])
        report['passed'] = report['passed'] and report['resources_closed'] and report['resource_measurement_complete'] and not cleanup_errors
        if not report['resources_closed']:
            raise ValueError('Large-image runtime or fixture resources remain live')
    return report
