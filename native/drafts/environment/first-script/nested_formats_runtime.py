"""Owned nested dedicated-worker Canvas formats or finite Float16 continuity; recreation and restart, not broad HDR, GPU/Audio or release admission."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import threading

ROOT = Path(__file__).resolve().parents[4]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--cohort-directory', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--driver-stage', type=Path, required=True)
    parser.add_argument('--driver-manifest', type=Path, default=ROOT / 'native/drafts/environment/playwright-driver-stage-binding-close.json')
    parser.add_argument('--candidate', choices=('upstream-156',), required=True)
    parser.add_argument('--probe', choices=('formats', 'finite-hdr'), default='formats')
    args = parser.parse_args()
    directory = ROOT / 'native/drafts/environment/first-script'
    CANVAS_PATH = directory / ('canvas_hdr.py' if args.probe == 'finite-hdr' else 'canvas_formats.py')
    CANVAS = runpy.run_path(str(CANVAS_PATH))
    WORKERS_PATH = directory / ('nested_hdr.py' if args.probe == 'finite-hdr' else 'nested_formats.py')
    WORKERS = runpy.run_path(str(WORKERS_PATH))
    WORKER_READ = WORKERS['worker_read'](CANVAS['READ'])
    READ = WORKERS['matrix_read'](CANVAS['READ'])
    compare = WORKERS['compare_nested_hdr'] if args.probe == 'finite-hdr' else WORKERS['compare_nested_formats']
    compare_canvas = CANVAS['compare_hdr'] if args.probe == 'finite-hdr' else CANVAS['compare_formats']
    OUTPUT, COHORT, STAGE = args.work_dir, args.cohort_directory, args.driver_stage
    for path in (OUTPUT, COHORT, STAGE, args.executable):
        if not path.is_absolute() or path != path.resolve() or path.is_symlink() or path.is_junction():
            parser.error('Use canonical absolute unlinked paths')
    if (sys.platform != 'win32' or OUTPUT.drive.upper() != 'D:' or OUTPUT.exists() or not OUTPUT.parent.is_dir()
            or OUTPUT.is_relative_to(ROOT) or OUTPUT.is_relative_to(COHORT) or OUTPUT.is_relative_to(args.executable.parent)
            or COHORT.drive.upper() != 'D:' or COHORT.is_relative_to(ROOT)
            or not args.executable.is_file() or args.executable.name != 'chrome.exe'):
        parser.error('Select a fresh D: output, an owned D: cohort and explicit Windows chrome.exe')
    if any(name == 'playwright' or name.startswith('playwright.') for name in sys.modules):
        parser.error('Use a fresh interpreter before importing Playwright')
    sys.path.insert(0, str(ROOT))
    from scripts.native_driver_stage import digest, read_metadata, verify
    verify(STAGE, args.driver_manifest)
    prior = json.loads(read_metadata(COHORT / 'report.json', 512 * 1024 * 1024))
    choose = runpy.run_path(str(ROOT / 'native/drafts/environment/first-script/combined_concurrent.py'))['choose_cohort_profiles']
    selected = choose(prior)
    target_profile = selected[0]['profile']
    for name in ('baseline', target_profile):
        path = COHORT / name
        if not path.is_dir() or path != path.resolve() or path.is_symlink() or path.is_junction():
            parser.error('Cohort profiles must already exist and be unlinked')
    OUTPUT.mkdir(exist_ok=False)
    (OUTPUT / 'temp').mkdir()
    os.environ.update(CAMOUFLOW_DATA_DIR=str(OUTPUT / 'workspace'), TMP=str(OUTPUT / 'temp'), TEMP=str(OUTPUT / 'temp'),
                      PLAYWRIGHT_NODEJS_PATH=str(STAGE / 'playwright/driver/node.exe'), PYTHONDONTWRITEBYTECODE='1')
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(ROOT), str(STAGE)]
    from app.core.native.runtime import NativeRuntime
    from app.core.native.identity import IDENTITY_FILE
    from scripts import verify_native_gpu_readback as gpu
    from scripts import verify_native_surfaces as surfaces
    from scripts import verify_native_worker_startup as workers
    from scripts import verify_native_runtime as helpers

    EXE = args.executable
    sha = digest
    core = helpers.measure_runtime_core(EXE)
    receipt = gpu.validate_receipt(EXE, core, derivation_mode='profile-identity', candidate_name=args.candidate)
    if (core != prior['runtime_core_sha256_measured']
            or hashlib.sha256(receipt).hexdigest() != prior.get('receipt_sha256')):
        raise ValueError('Cohort and selected runtime core differ')
    paths = {directory / 'nested_formats.py', CANVAS_PATH, WORKERS_PATH, COHORT / 'baseline' / IDENTITY_FILE, COHORT / target_profile / IDENTITY_FILE, WORKERS_PATH, Path(__file__), ROOT / 'native/drafts/environment/first-script/combined_concurrent.py', COHORT / 'report.json', args.driver_manifest,
             ROOT / 'scripts/native_driver_stage.py', *[ROOT / name for name in gpu.probe_inputs()],
             STAGE / 'playwright/driver/package/lib/coreBundle.js', STAGE / 'playwright/_impl/_page.py', STAGE / 'playwright/driver/node.exe'}
    inputs = {path: sha(path) for path in paths}
    report = {'schema': 1, 'measurement_complete': False, 'scope': __doc__, 'probe': args.probe, 'runs': [],
              'privacy_admitted': False, 'production_admitted': False, 'passed': False, 'errors': [],
              'runtime_core_sha256_measured': core, 'receipt_sha256': hashlib.sha256(receipt).hexdigest(),
              'candidate_manifest_sha256': prior['candidate_manifest_sha256'], 'measured_inputs_sha256': {str(path): value for path, value in inputs.items()}}

    def save():
        (OUTPUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')

    async def run():
        discovery = NativeRuntime(OUTPUT / 'discovery', EXE, surfaces.SurfaceConfiguration())
        try:
            context = await discovery.start(headless=True)
            arguments = await workers.browser_arguments(context)
            original = next(value for value in arguments if value.startswith('--disable-features='))
            replacement = workers.partitioning_argument(arguments)
        finally:
            await discovery.close()
        for name, profile_name, phase in (('baseline', 'baseline', 'initial'), ('protected', target_profile, 'initial'),
                                          ('baseline', 'baseline', 'restart'), ('protected', target_profile, 'restart')):
            configuration = gpu.ReadbackConfiguration(probe_mode='baseline' if name == 'baseline' else 'ready',
                derivation_mode='profile-identity', disabled_features_argument=replacement, ignored_driver_argument=original)
            runtime = NativeRuntime(COHORT / profile_name, EXE, configuration)
            row = {'profile': name, 'phase': phase}
            report['runs'].append(row)
            before = await asyncio.to_thread(helpers.process_snapshot)
            owned = {}
            try:
                context = await runtime.start(headless=True)
                owned.update(helpers.controller_descendants(before, await asyncio.to_thread(helpers.process_snapshot), os.getpid()))
                page = context.pages[0]
                await page.goto(f'http://127.0.0.1:{server.server_port}')
                row['observed'] = await asyncio.wait_for(page.evaluate(READ), timeout=150)
            finally:
                try:
                    owned.update(helpers.controller_descendants(before, await asyncio.to_thread(helpers.process_snapshot), os.getpid()))
                finally:
                    await runtime.close()
                    row['resources_released'] = not runtime.has_resources
                    async def wait_owned():
                        while True:
                            current = await asyncio.to_thread(helpers.process_snapshot)
                            if not any(helpers.same_process(current.get(pid), value) for pid, value in owned.items()):
                                return
                            await asyncio.sleep(0.05)
                    await asyncio.wait_for(wait_owned(), timeout=15)
                    row['observed_processes'] = len(owned)
                    row['remaining_observed_processes'] = 0
                    save()
        comparisons = [compare(
            *(row['observed'] for row in report['runs'][start:start+2]), compare_canvas, WORKERS['CASES'])
            for start in (0, 2)]
        stable = all(report['runs'][index]['observed'] == report['runs'][index+2]['observed'] for index in (0, 1))
        report['comparison'] = {'passed': stable and all(value['passed'] for value in comparisons),
            'initial': comparisons[0], 'restart': comparisons[1], 'restart_stable': stable,
            'worker_cases_per_profile': comparisons[0]['worker_cases_per_profile'], 'worker_paths_per_profile': 4, 'recreation_samples_per_path': 2}
        report['passed'] = report['comparison']['passed'] and all(row['resources_released'] and row['remaining_observed_processes'] == 0
                            and row['observed_processes'] > 0 for row in report['runs'])
        report['measurement_complete'] = True

    server = thread = None
    save()
    try:
        server = WORKERS['server_type'](surfaces, WORKER_READ)(('127.0.0.1', 0))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        asyncio.run(run())
    except Exception as error:
        report['errors'].append({'type': type(error).__name__, 'error': str(error)})
    finally:
        if server is not None:
            if thread is not None and thread.is_alive():
                server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)
        try:
            verify(STAGE, args.driver_manifest)
            report['postguards_passed'] = ((thread is None or not thread.is_alive())
                and helpers.measure_runtime_core(EXE) == core and all(sha(path) == value for path, value in inputs.items())
                and gpu.validate_receipt(EXE, core, derivation_mode='profile-identity', candidate_name=args.candidate) == receipt)
        except Exception as error:
            report['postguards_passed'] = False
            report['errors'].append({'type': type(error).__name__, 'error': str(error), 'scope': 'postguards'})
        report['passed'] = report['passed'] and report['postguards_passed'] and not report['errors']
        save()
    comparison = report.get('comparison', {})
    print(json.dumps({'passed': report['passed'], 'measurement_complete': report['measurement_complete'],
        'postguards_passed': report['postguards_passed'], 'worker_cases_per_profile': comparison.get('worker_cases_per_profile'),
        'compatibility_passed': comparison.get('passed'), 'restart_stable': comparison.get('restart_stable'),
        'document_worker_mismatches': len(comparison.get('document_worker_mismatches', [])), 'errors': report['errors']}))
    return 0 if report['passed'] else 1


if __name__ == "__main__":
    raise SystemExit(main())
