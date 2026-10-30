"""Concurrent protected profiles from a completed owned cohort; no privacy admission."""

import argparse
import asyncio
from dataclasses import dataclass
import gc
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import threading
import traceback


ROOT = Path(__file__).resolve().parents[4]
COHORT_SCOPE = 'Combined native Canvas/WebGL/AudioMath compatibility collector; no privacy admission.'


def choose_cohort_profiles(record: dict) -> dict:
    if (not isinstance(record, dict) or record.get('passed') is not True
            or record.get('measurement_complete') is not True or record.get('postguards_passed') is not True
            or record.get('both_audio_math_selectors_observed') is not True):
        raise ValueError('Select a completed successful cohort covering both AudioMath selectors')
    if record.get('scope') != COHORT_SCOPE:
        raise ValueError('This lifecycle gate requires the desktop combined cohort, not another environment')
    count = record.get('protected_profile_count')
    if type(count) is not int or not 2 <= count <= 16:
        raise ValueError('Invalid cohort profile count')
    names = {'baseline', *(f'profile-{index:02d}' for index in range(count))}
    rows = record.get('checks')
    if not isinstance(rows, list) or len(rows) != (count + 1) * 2:
        raise ValueError('Incomplete cohort phases')
    seen, modes, selected = set(), {}, {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid cohort row')
        name, phase = row.get('profile'), row.get('phase')
        if (not isinstance(name, str) or name not in names or phase not in ('initial', 'restart')
                or (name, phase) in seen or row.get('passed') is not True or row.get('resources_released') is not True
                or type(row.get('remaining_observed_processes')) is not int or row['remaining_observed_processes'] != 0):
            raise ValueError('Cohort profile path, phase or cleanup is invalid')
        seen.add((name, phase))
        if name == 'baseline':
            continue
        selector = row.get('audio_reference_selector')
        if type(selector) is not int or selector not in (0, 1) or (name in modes and modes[name] != selector):
            raise ValueError('Cohort AudioMath selector is invalid or changed across restart')
        modes[name] = selector
        if phase == 'restart' and selector not in selected:
            selected[selector] = row
    if set(selected) != {0, 1}:
        raise ValueError('Cohort has no opposite AudioMath selectors')
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--cohort-directory', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--driver-stage', type=Path, required=True)
    parser.add_argument('--driver-manifest', type=Path, default=ROOT / 'native/drafts/environment/playwright-driver-stage-binding-close.json')
    parser.add_argument('--candidate', choices=('upstream-156',), required=True)
    args = parser.parse_args()
    OUTPUT, COHORT, STAGE = args.work_dir, args.cohort_directory, args.driver_stage
    for path in (OUTPUT, COHORT, STAGE, args.executable):
        if not path.is_absolute() or path != path.resolve() or path.is_symlink() or path.is_junction():
            parser.error('All paths must be canonical, absolute and unlinked')
    if (sys.platform != 'win32' or OUTPUT.drive.upper() != 'D:' or OUTPUT.exists() or not OUTPUT.parent.is_dir()
            or OUTPUT.is_relative_to(ROOT) or OUTPUT.is_relative_to(COHORT) or OUTPUT.is_relative_to(args.executable.parent)
            or COHORT.drive.upper() != 'D:' or COHORT.is_relative_to(ROOT)
            or not args.executable.is_file() or args.executable.name != 'chrome.exe'):
        parser.error('Use a fresh D: output, an owned external D: cohort and an explicit Windows chrome.exe')
    if any(name == 'playwright' or name.startswith('playwright.') for name in sys.modules):
        parser.error('Use a fresh interpreter before importing Playwright')
    sys.path.insert(0, str(ROOT))
    from scripts.native_driver_stage import read_metadata, verify
    verify(STAGE, args.driver_manifest)
    try:
        prior = json.loads(read_metadata(COHORT / 'report.json', 512 * 1024 * 1024))
    except (OSError, ValueError) as error:
        parser.error('Cohort report rejected: ' + str(error))
    selected = choose_cohort_profiles(prior)
    for row in selected.values():
        profile = COHORT / row['profile']
        if profile != profile.resolve() or profile.is_symlink() or profile.is_junction() or not profile.is_dir():
            parser.error('Selected cohort profiles must already exist and must not be linked')
    OUTPUT.mkdir(exist_ok=False)
    (OUTPUT / 'temp').mkdir()
    os.environ.update(CAMOUFLOW_DATA_DIR=str(OUTPUT / 'workspace'), TMP=str(OUTPUT / 'temp'), TEMP=str(OUTPUT / 'temp'),
                      PLAYWRIGHT_NODEJS_PATH=str(STAGE / 'playwright/driver/node.exe'), PYTHONDONTWRITEBYTECODE='1')
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(ROOT), str(STAGE)]
    from app.core.native.runtime import NativeRuntime
    from app.core.native.identity import IDENTITY_FILE
    from scripts.native_driver_stage import digest, verify as verify_stage
    from scripts import verify_native_combined_math as combined
    from scripts import verify_native_canvas as canvas
    from scripts import verify_native_audio as audio
    from scripts import verify_native_audio_quality as quality
    from scripts import verify_native_gpu_readback as gpu
    from scripts import verify_native_runtime as helpers
    from scripts import verify_native_surfaces as surfaces
    from scripts import verify_native_worker_startup as workers

    sha = digest
    verify_stage(STAGE, args.driver_manifest)
    chosen = choose_cohort_profiles(prior)
    EXE = args.executable
    core = helpers.measure_runtime_core(EXE)
    if core != prior.get('runtime_core_sha256_measured'):
        raise ValueError('Cohort runtime core differs from the selected browser')
    receipt = gpu.validate_receipt(EXE, core, derivation_mode='profile-identity', candidate_name=args.candidate)
    if hashlib.sha256(receipt).hexdigest() != prior.get('receipt_sha256'):
        raise ValueError('Cohort receipt differs from the current browser')
    if prior.get('measured_inputs_sha256', {}).get(str(Path(combined.__file__))) != sha(Path(combined.__file__)):
        raise ValueError('Cohort must come from the current combined collector')
    MATH = ROOT / 'native/drafts/audio-dsp-math-v2'
    case = next(row for row in runpy.run_path(str(MATH / 'matrix.py'))['load_cases'](MATH / 'cases.json')[1] if row['id'] == 'random-default')
    read_compressor = (MATH / 'compressor-matrix-control.js').read_text(encoding='utf-8-sig')
    decode = runpy.run_path(str(MATH / 'browser_matrix.py'))['decode_capture']
    paths = {Path(__file__), Path(combined.__file__), COHORT / 'report.json', args.driver_manifest,
             ROOT / 'scripts/native_driver_stage.py', STAGE / 'glint-driver-stage.json', STAGE / 'playwright/driver/node.exe',
             *(ROOT / name for name in gpu.probe_inputs()), *(ROOT / name for name in audio.probe_inputs()),
             *(MATH / name for name in ('matrix.py', 'cases.json', 'browser_matrix.py', 'compressor-matrix-control.js')),
             *(COHORT / row['profile'] / IDENTITY_FILE for row in chosen.values()),
             STAGE / 'playwright/driver/package/lib/coreBundle.js', STAGE / 'playwright/_impl/_page.py'}
    inputs = {path: sha(path) for path in paths}
    report = {'schema': 1, 'passed': False, 'measurement_complete': False, 'scope': __doc__, 'checks': [],
              'errors': [], 'asyncio_errors': [], 'privacy_admitted': False, 'production_admitted': False,
              'runtime_core_sha256_measured': core, 'receipt_sha256': hashlib.sha256(receipt).hexdigest(),
              'cohort_sha256': sha(COHORT / 'report.json'), 'chosen_profiles': {str(key): value['profile'] for key, value in chosen.items()},
              'measured_inputs_sha256': {str(path): value for path, value in inputs.items()}}
    def save():
        (OUTPUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')

    @dataclass(frozen=True)
    class Configuration(gpu.ReadbackConfiguration):
        def launch_arguments(self):
            arguments = super().launch_arguments()
            if self.probe_mode == 'ready':
                indices = [index for index, value in enumerate(arguments) if value.startswith('--enable-features=')]
                if len(indices) != 1:
                    raise ValueError('Expected one feature list')
                arguments[indices[0]] += ',GlintAudioMathCandidate'
            return arguments

    async def run(server):
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(lambda loop, context: report['asyncio_errors'].append({
            'message': context.get('message'), 'type': type(context.get('exception')).__name__, 'error': str(context.get('exception'))}))
        discovery = NativeRuntime(OUTPUT / 'discovery', EXE, surfaces.SurfaceConfiguration())
        try:
            context = await discovery.start(headless=True)
            arguments = await workers.browser_arguments(context)
            original = next(value for value in arguments if value.startswith('--disable-features='))
            replacement = workers.partitioning_argument(arguments)
        finally:
            await discovery.close()
            if discovery.has_resources:
                raise RuntimeError('Discovery retained Native resources')
        runtimes = {selector: NativeRuntime(COHORT / row['profile'], EXE,
            Configuration(probe_mode='ready', derivation_mode='profile-identity',
                disabled_features_argument=replacement, ignored_driver_argument=original)) for selector, row in chosen.items()}
        before = await asyncio.to_thread(helpers.process_snapshot)
        owned = {}
        contexts = {}
        snapshots = {}
        async def start(selector):
            context = await runtimes[selector].start(headless=True)
            contexts[selector] = context
            effective = await workers.browser_arguments(context)
            if any(value not in effective for value in runtimes[selector].configuration.launch_arguments()):
                raise ValueError('Effective arguments do not request the combined policies')
            owned.update(helpers.controller_descendants(before, await asyncio.to_thread(helpers.process_snapshot), os.getpid()))

        async def capture(selector, phase):
            row = {'selector': selector, 'phase': phase, 'passed': False}
            report['checks'].append(row)
            save()
            context = contexts[selector]
            raw = await canvas.observe(context, f'http://127.0.0.1:{server.server_port}', read=surfaces.combined_read(True))
            old = chosen[selector]['observed']
            canvas_values = {name: value['canvas'] for name, value in raw.items()}
            gpu_values = {name: value['gpu'] for name, value in raw.items()}
            audio_values = quality.strip_quality({name: value['audio'] for name, value in raw.items()})
            canvas.validate_observations(canvas_values, {name: value['canvas'] for name, value in old.items()})
            baseline = next(row['observed'] for row in prior['checks'] if row['profile'] == 'baseline' and row['phase'] == 'restart')
            normalized = gpu.validate_readback({name: value['gpu'] for name, value in baseline.items()}, protected=False, derivation_mode='profile-identity')
            gpu.validate_readback(gpu_values, protected=True, baseline=normalized,
                previous={name: value['gpu'] for name, value in old.items()}, derivation_mode='profile-identity')
            audio.validate_observations(audio_values, quality.strip_quality({name: value['audio'] for name, value in old.items()}))
            frames = {'document': context.pages[0].main_frame}
            for slot, identifier in (('same_origin_frame', 'owned-frame'), ('cross_origin_frame', 'cross-origin'),
                                      ('about_blank_frame', 'owned-about-blank'), ('srcdoc_frame', 'owned-srcdoc')):
                element = await context.pages[0].locator('#' + identifier).element_handle()
                frames[slot] = await element.content_frame()
            captures = {slot: decode(await asyncio.wait_for(frame.evaluate(read_compressor, case), timeout=30), case)
                        for slot, frame in frames.items()}
            effect = combined.validate_compressor_effect(captures)
            if {slot: value['sha256'] for slot, value in effect.items()} != {
                    slot: value['sha256'] for slot, value in chosen[selector]['compressor_effect'].items()}:
                raise ValueError('Concurrent compressor output differs from its own cohort capture')
            snapshots[selector] = raw
            row.update(passed=True, document_contexts=sorted(captures), context_count=len(raw),
                       canvas_gpu_audio_match_prior_cohort=True, compressor_effect=effect)
            owned.update(helpers.controller_descendants(before, await asyncio.to_thread(helpers.process_snapshot), os.getpid()))
            save()
        try:
            await asyncio.gather(start(0), start(1))
            report['both_profiles_running'] = all(runtime.has_resources and runtime.context is contexts[key] for key, runtime in runtimes.items())
            if not report['both_profiles_running']:
                raise RuntimeError('Both protected profiles must be live before concurrent capture')
            await asyncio.gather(capture(0, 'both-running'), capture(1, 'both-running'))
            for selector in (0, 1):
                peer = 1 - selector
                await runtimes[selector].close()
                if runtimes[selector].has_resources or not runtimes[peer].has_resources:
                    raise RuntimeError('Closing one profile did not preserve its running peer')
                await capture(peer, 'peer-closed-' + str(selector))
                await start(selector)
                await capture(selector, 'same-profile-restarted-' + str(selector))
            report['measurement_complete'] = True
        finally:
            await asyncio.gather(*(runtime.close() for runtime in runtimes.values()))
            async def wait_owned():
                while True:
                    current = await asyncio.to_thread(helpers.process_snapshot)
                    if not any(helpers.same_process(current.get(pid), value) for pid, value in owned.items()):
                        return
                    await asyncio.sleep(0.05)
            await asyncio.wait_for(wait_owned(), timeout=15)
            report['remaining_observed_processes'] = 0
            report['observed_processes'] = len(owned)
            report['resources_released'] = all(not runtime.has_resources for runtime in runtimes.values())
        await asyncio.sleep(0.1)
        gc.collect()
        await asyncio.sleep(0.1)
        report['passed'] = report['measurement_complete'] and len(report['checks']) == 6 and all(row['passed'] for row in report['checks']) and not report['asyncio_errors']

    save()
    server = surfaces.SurfaceFixtureServer(('127.0.0.1', 0), include_gpu_readback=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        asyncio.run(run(server))
    except Exception as error:
        report['errors'].append({'type': type(error).__name__, 'error': str(error), 'traceback': traceback.format_exc()})
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        try:
            verify_stage(STAGE, args.driver_manifest)
            report['postguards_passed'] = (not thread.is_alive() and helpers.measure_runtime_core(EXE) == core
                and all(sha(path) == value for path, value in inputs.items())
                and gpu.validate_receipt(EXE, core, derivation_mode='profile-identity', candidate_name=args.candidate) == receipt)
        except Exception as error:
            report['postguards_passed'] = False
            report['errors'].append({'type': type(error).__name__, 'error': str(error), 'scope': 'postguards'})
        report['passed'] = report['passed'] and report['postguards_passed'] and not report['errors']
        save()
    print(json.dumps({key: report.get(key) for key in ('passed', 'measurement_complete', 'postguards_passed', 'errors')}))
    return 0 if report['passed'] else 1


if __name__ == "__main__":
    raise SystemExit(main())
