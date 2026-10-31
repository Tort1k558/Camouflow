"""Owned baseline WebGPU recovery after Browser.crashGpuProcess; never protected-policy admission."""
import argparse
import asyncio
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def main(argv=None):
    sys.path.insert(0, str(ROOT))
    from scripts.native_build import CANDIDATES

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--driver-stage', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--candidate', choices=CANDIDATES, required=True)
    args = parser.parse_args(argv)
    if not __debug__:
        parser.error('Run without Python optimization; native diagnostics require assertions')
    EXECUTABLE, DRIVER, OUTPUT = args.executable, args.driver_stage, args.work_dir
    paths = (EXECUTABLE, DRIVER, OUTPUT)
    if (sys.platform != 'win32' or any(not p.is_absolute() or p != p.resolve() or
            p.is_symlink() or p.is_junction() or p.drive.upper() != 'D:' for p in paths)
            or not EXECUTABLE.is_file() or not DRIVER.is_dir() or OUTPUT.exists()
            or not OUTPUT.parent.is_dir() or OUTPUT.is_relative_to(ROOT) or ROOT.is_relative_to(OUTPUT)
            or any(OUTPUT.is_relative_to(p) or p.is_relative_to(OUTPUT) for p in (EXECUTABLE.parent, DRIVER))
            or {'chromium', 'out'}.issubset({part.lower() for part in EXECUTABLE.parts})):
        parser.error('Use an independent canonical D: runtime, pinned D: driver and fresh external D: work directory')
    WATCH = Path(__file__).with_name('watch.js')
    PROBE = ROOT / 'native/drafts/environment/first-script/webgpu_shader_dataflow.js'
    MANIFEST = ROOT / 'native/drafts/environment/playwright-driver-stage-binding-close.json'
    OUTPUT.mkdir(exist_ok=False)
    owned = OUTPUT / 'profiles'
    owned.mkdir()
    os.environ.update(TEMP=str(OUTPUT), TMP=str(OUTPUT), PYTHONDONTWRITEBYTECODE='1',
                      PLAYWRIGHT_NODEJS_PATH=str(DRIVER / 'playwright/driver/node.exe'),
                      CAMOUFLOW_DATA_DIR=str(OUTPUT / 'workspace'), QT_QPA_PLATFORM='offscreen')
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(DRIVER), str(ROOT)]
    from app.core.native.runtime import NativeRuntime
    from scripts.native_driver_stage import verify as verify_driver
    from scripts.verify_native_gpu_readback import (
        ReadbackConfiguration,
        probe_inputs,
        validate_receipt,
    )
    from scripts.verify_native_runtime import FixtureServer, measure_runtime_core
    from scripts.verify_native_webgpu_consistency import (
        FixtureHandler,
        bounded_bytes,
        compare,
        decode_png,
    )


    def sha(path):
        with path.open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()


    def save():
        (OUTPUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')


    def unchanged(values):
        try:
            return bool(values) and all(sha(path) == value for path, value in values.items())
        except OSError:
            return False

    def runtime_assets():
        entries = list(EXECUTABLE.parent.rglob('*'))
        assert all(not p.is_symlink() and not p.is_junction() and p == p.resolve() for p in entries)
        files = [p for p in entries if p.is_file()]
        assert 0 < len(files) <= 4096 and sum(p.stat().st_size for p in files) <= 4 * 1024**3
        return {p: sha(p) for p in files}


    def owned_processes():
        runtime = str(EXECUTABLE.parent) + '\\'
        node = str(DRIVER / 'playwright/driver/node.exe')
        runtime, node = runtime.replace("'", "''"), node.replace("'", "''")
        command = ("Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and ("
                   f"$_.ExecutablePath.StartsWith('{runtime}', [StringComparison]::OrdinalIgnoreCase) -or "
                   f"$_.ExecutablePath -eq '{node}') "
                   "} | Select-Object ProcessId,Name | ConvertTo-Json -Compress")
        raw = subprocess.check_output(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                                      text=True, encoding='utf-8', timeout=30).strip()
        value = json.loads(raw) if raw else []
        return value if isinstance(value, list) else [value]


    def validate_baseline(value):
        assert all(value.get(name) is True for name in ('measured', 'commandValidationPassed',
            'referenceMatched', 'shaderReferenceMatched', 'directShaderMatched', 'exportStable'))
        raw = base64.b64decode(value['rgbaBase64'], validate=True)
        shader = bounded_bytes(value['shaderRGBA'], 1024)
        png = decode_png(value['png'])
        reference = bytes(channel for y in range(16) for x in range(16)
                          for channel in ((x * 17) % 256, (y * 29 + 31) % 256,
                                          (x * 43 + y * 11) % 256, 255))
        assert all(compare(data, reference) == {'changed_channels': 0, 'maximum_delta': 0}
                   for data in (raw, shader, png))
        return {'reference_matched': True, 'rgba_sha256': hashlib.sha256(raw).hexdigest(),
                'shader_sha256': hashlib.sha256(shader).hexdigest(), 'png_rgba_sha256': hashlib.sha256(png).hexdigest()}


    async def observe(server):
        context = await runtime.start(headless=True)
        page = await context.new_page()
        crashes = []
        page.on('crash', lambda *_: crashes.append(True))
        origin = f'http://127.0.0.1:{server.server_port}/'
        await page.goto(origin, wait_until='load')
        await page.evaluate('globalThis.__ownedRecoveryMarker = 731921')
        expression = 'async () => {' + PROBE.read_text(encoding='utf-8-sig') + '; return await probeWebGPU();}'
        report['before'] = validate_baseline(await asyncio.wait_for(page.evaluate(expression), 90))
        report['armed'] = await page.evaluate('async () => {' + WATCH.read_text(encoding='utf-8-sig') + '; return await armOwnedGPURecovery();}')
        assert report['armed'] == {'armed': True, 'initialCopyMatched': True, 'deviceLostCallbacks': 0}
        assert context.browser is not None
        session = await context.browser.new_browser_cdp_session()
        try:
            report['before_browser_version'] = await session.send('Browser.getVersion')
            report['crash_command_return'] = await session.send('Browser.crashGpuProcess')
            report['loss'] = await asyncio.wait_for(page.evaluate('async () => await globalThis.__glintOwnedGPURecovery.finish()'), 75)
            assert report['loss'] == {'initialCopyMatched': True, 'deviceLostCallbacks': 1,
                'reason': 'unknown', 'oldMapRejectedWith': 'AbortError', 'oldMapState': 'unmapped'}
            assert await page.evaluate('globalThis.__ownedRecoveryMarker') == 731921
            assert not crashes and not page.is_closed() and page.url == origin
            report['after'] = validate_baseline(await asyncio.wait_for(page.evaluate(expression), 90))
            report['after_browser_version'] = await session.send('Browser.getVersion')
            assert report['before_browser_version'] == report['after_browser_version']
            assert report['before'] == report['after']
            await page.evaluate('globalThis.__glintOwnedGPURecovery.close()')
            report.update(page_crashes=len(crashes), same_document_preserved=True,
                          actual_gpu_crash_command_completed=True, baseline_recovered=True)
        finally:
            await session.detach()


    async def run_owned(server):
        try:
            await asyncio.wait_for(observe(server), 240)
        finally:
            await runtime.close()


    report = {'schema': 1, 'passed': False, 'measurement_complete': False,
              'scope': __doc__, 'candidate': args.candidate, 'protected_policies_enabled': False,
              'complete_candidate_verified': False, 'protected_policy_recovery_verified': False, 'privacy_admitted': False, 'production_admitted': False}
    runtime = NativeRuntime(owned / 'baseline', EXECUTABLE,
                            ReadbackConfiguration(probe_mode='baseline'))
    server = thread = None
    inputs = assets = {}
    receipt = driver_receipt = None
    started = time.monotonic()
    try:
        assert shutil.disk_usage(OUTPUT).free > 2 * 1024**3
        assert not owned_processes(), 'Selected preserved runtime or driver is already in use'
        free = subprocess.check_output(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
            '(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory'], text=True, timeout=30)
        assert int(free.strip()) * 1024 >= 4 * 1024**3, 'Recovery calibration requires 4 GiB available RAM'
        assets = runtime_assets()
        assert unchanged(assets)
        driver_receipt = verify_driver(DRIVER, MANIFEST)
        core = measure_runtime_core(EXECUTABLE)
        receipt = validate_receipt(EXECUTABLE, core,
                                   derivation_mode='profile-identity', candidate_name=args.candidate)
        inputs = {ROOT / name: value for name, value in probe_inputs(candidate_name=args.candidate).items()}
        inputs.update({path: sha(path) for path in (Path(__file__), WATCH, PROBE, MANIFEST)})
        assert all(sha(path) == value for path, value in inputs.items())
        report.update(runtime_core_sha256_measured=core, receipt_sha256=hashlib.sha256(receipt).hexdigest(),
                      runtime_asset_count=len(assets), source_sha256={str(p): v for p, v in inputs.items()})
        save()
        server = FixtureServer(('127.0.0.1', 0), FixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        asyncio.run(run_owned(server))
        report['measurement_complete'] = True
    except Exception as error:  # noqa: BLE001 - retain failed diagnostic and cleanup evidence
        report.update(error_type=type(error).__name__, error=str(error))
    finally:
        try:
            if server:
                if thread and thread.is_alive():
                    server.shutdown()
                server.server_close()
            if thread:
                thread.join(timeout=5)
                assert not thread.is_alive()
            report['server_closed'] = True
        except Exception as error:  # noqa: BLE001 - retain cleanup failure independently
            report.update(server_cleanup_error=str(error), server_closed=False)
        try:
            assert not runtime.has_resources
            report['remaining_owned_processes'] = owned_processes()
            assert not report['remaining_owned_processes']
            report['runtime_resource_free'] = True
            assert owned == owned.resolve() and owned.parent == OUTPUT
            shutil.rmtree(owned)
            report['owned_profiles_removed'] = True
        except Exception as error:  # noqa: BLE001 - retain failed diagnostic and cleanup evidence
            report.update(cleanup_error=str(error), runtime_resource_free=False)
        report['input_postguards_passed'] = unchanged(inputs)
        try:
            report['runtime_assets_unchanged'] = bool(assets) and runtime_assets() == assets
            report['driver_unchanged'] = driver_receipt is not None and verify_driver(DRIVER, MANIFEST) == driver_receipt
            report['receipt_unchanged'] = receipt is not None and validate_receipt(EXECUTABLE,
                measure_runtime_core(EXECUTABLE), derivation_mode='profile-identity',
                candidate_name=args.candidate) == receipt
        except Exception as error:  # noqa: BLE001 - retain failed diagnostic and cleanup evidence
            report.update(postguard_error=str(error), receipt_unchanged=False)
        report['passed'] = all(report.get(name) is True for name in ('measurement_complete', 'baseline_recovered',
            'runtime_resource_free', 'owned_profiles_removed', 'input_postguards_passed',
            'runtime_assets_unchanged', 'driver_unchanged', 'receipt_unchanged', 'server_closed'))
        report['seconds'] = round(time.monotonic() - started, 3)
        save()
    print(json.dumps({k: report.get(k) for k in ('passed', 'measurement_complete', 'baseline_recovered',
        'runtime_resource_free', 'input_postguards_passed', 'runtime_assets_unchanged', 'error', 'cleanup_error')}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
