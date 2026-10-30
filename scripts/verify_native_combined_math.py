"""Combined native Canvas/WebGL/AudioMath compatibility collector; no privacy admission."""

import argparse
import asyncio
from dataclasses import dataclass
import gc
import hashlib
from itertools import combinations
import json
import math
import os
from pathlib import Path
import runpy
import struct
import sys
import threading
import traceback
import uuid


ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_CONTEXTS = frozenset({'document', 'same_origin_frame', 'cross_origin_frame', 'about_blank_frame', 'srcdoc_frame'})


def validate_compressor_effect(observed: dict, *, baseline: dict | None = None,
                               previous: dict | None = None, selector: int | None = None) -> dict:
    if (not isinstance(observed, dict) or set(observed) != DOCUMENT_CONTEXTS
            or any(not isinstance(value, bytes) or not value or len(value) > 1024 * 1024 or len(value) % 4
                   for value in observed.values())):
        raise ValueError('Long compressor requires bounded float32 captures in all five documents')
    if selector is not None and (type(selector) is not int or selector not in (0, 1)):
        raise ValueError('Unknown AudioMath reference selector')
    if any(not math.isfinite(sample[0]) for raw in observed.values() for sample in struct.iter_unpack('<f', raw)):
        raise ValueError('Long compressor output contains a non-finite sample')
    if baseline is not None and selector is None:
        raise ValueError('AudioMath baseline comparison requires a reference selector')
    if any(value != observed['document'] for value in observed.values()):
        raise ValueError('AudioMath compressor output differs across profile-identity documents')
    if previous is not None and observed != previous:
        raise ValueError('Long compressor output changed across restart')
    if baseline is not None:
        validate_compressor_effect(baseline)
        for slot, value in observed.items():
            if len(value) != len(baseline[slot]):
                raise ValueError('Long compressor output extent differs from baseline')
            if (value == baseline[slot]) != (selector == 0):
                raise ValueError('Long compressor output contradicts the reference math selector: ' + slot)
    elif selector is not None:
        raise ValueError('AudioMath effect requires an explicit unprotected baseline')
    return {slot: {'sha256': hashlib.sha256(value).hexdigest(), 'bytes': len(value),
                   'matches_baseline': None if baseline is None else value == baseline[slot]}
            for slot, value in observed.items()}


def validate_audio_completion(observed: dict) -> None:
    probes = {'fidelity', 'analyser', 'worklet', 'realtime'}
    if (not isinstance(observed, dict) or observed.get('passed') is not True
            or any(field in observed for field in ('cleanup_error', 'cleanup_error_type'))
            or not isinstance(observed.get('probes'), dict) or set(observed['probes']) != probes
            or any(not isinstance(value, dict) or value.get('passed') is not True for value in observed['probes'].values())):
        raise ValueError('Audio compatibility collection or route cleanup did not complete')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--driver-stage', type=Path, required=True)
    parser.add_argument('--driver-manifest', type=Path, default=ROOT / 'native/drafts/environment/playwright-driver-stage-binding-close.json')
    parser.add_argument('--candidate', choices=('upstream-156',), required=True)
    parser.add_argument('--profiles', type=int, default=2, help='Protected profile cohort size (2..16), each with a persistent restart')
    args = parser.parse_args()
    if not 2 <= args.profiles <= 16:
        parser.error('Choose 2..16 protected profiles')
    OUTPUT = args.work_dir
    executable = args.executable
    if (sys.platform != 'win32' or not OUTPUT.is_absolute() or OUTPUT.drive.upper() != 'D:'
            or OUTPUT != OUTPUT.resolve() or not OUTPUT.parent.is_dir() or OUTPUT.exists()
            or OUTPUT.is_symlink() or OUTPUT.is_junction() or OUTPUT.is_relative_to(ROOT)):
        parser.error('Use a fresh canonical Windows D: output outside the source checkout')
    if (not executable.is_absolute() or executable != executable.resolve() or not executable.is_file()
            or executable.name != 'chrome.exe' or OUTPUT.is_relative_to(executable.parent)):
        parser.error('Choose an explicit canonical chrome.exe outside the output directory')
    if any(name == 'playwright' or name.startswith('playwright.') for name in sys.modules):
        parser.error('Run this collector in a fresh interpreter before importing Playwright')
    sys.path.insert(0, str(ROOT))
    from scripts.native_driver_stage import verify
    STAGE = args.driver_stage
    try:
        verify(STAGE, args.driver_manifest)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    OUTPUT.mkdir(exist_ok=False)
    (OUTPUT / 'temp').mkdir()
    PROFILE_ROOT = OUTPUT
    os.environ.update(CAMOUFLOW_DATA_DIR=str(OUTPUT / 'workspace'), TMP=str(OUTPUT / 'temp'), TEMP=str(OUTPUT / 'temp'),
                      PLAYWRIGHT_NODEJS_PATH=str(STAGE / 'playwright/driver/node.exe'), PYTHONDONTWRITEBYTECODE='1')
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(ROOT), str(STAGE)]
    from app.core.native.runtime import NativeRuntime
    from app.core.native.identity import IDENTITY_FILE, load_or_create_identity
    from scripts import native_build as build
    from scripts import verify_native_audio as audio
    from scripts import verify_native_audio_compatibility as compatibility
    from scripts import verify_native_audio_quality as quality
    from scripts import verify_native_canvas as canvas
    from scripts import verify_native_gpu_readback as gpu
    from scripts import verify_native_runtime as helpers
    from scripts import verify_native_surfaces as surfaces
    from scripts import verify_native_worker_startup as workers

    EXE = executable
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    FIDELITY_PATH = ROOT / 'native/fixtures/audio/fidelity.js'
    FIDELITY = FIDELITY_PATH.read_text(encoding='utf-8-sig')
    core = helpers.measure_runtime_core(EXE)
    receipt = gpu.validate_receipt(EXE, core, derivation_mode='profile-identity', candidate_name=args.candidate)
    candidate = build.load_candidate(args.candidate)
    compiled = json.loads(receipt)
    for name in ('0067-native-audio-math-context-candidate.patch', '0068-native-audio-math-fixture-readiness.patch'):
        if {'name': name, 'sha256': sha(candidate['directory'] / 'patches' / name)} not in compiled['patches']:
            raise ValueError('Receipt lacks the compiled AudioMath patch: ' + name)
    math_fixtures = ROOT / 'native/drafts/audio-dsp-math-v2'
    matrix_module = runpy.run_path(str(math_fixtures / 'matrix.py'))
    matrix_cases = matrix_module['load_cases'](math_fixtures / 'cases.json')[1]
    compressor_case = next(row for row in matrix_cases if row['id'] == 'random-default')
    compressor_read = (math_fixtures / 'compressor-matrix-control.js').read_text(encoding='utf-8-sig')
    decode_capture = runpy.run_path(str(math_fixtures / 'browser_matrix.py'))['decode_capture']
    paths = {Path(__file__), FIDELITY_PATH, *[ROOT / name for name in gpu.probe_inputs()],
             *[ROOT / name for name in audio.probe_inputs()], ROOT / 'scripts/verify_native_audio_compatibility.py',
             *[ROOT / name for name in ('app/core/native/runtime.py', 'app/core/native/configuration.py', 'app/core/native/identity.py')],
             STAGE / 'playwright/driver/package/lib/coreBundle.js', STAGE / 'playwright/_impl/_page.py', STAGE / 'playwright/driver/node.exe'}
    paths.update((ROOT / 'native/fixtures/audio').glob('*.js'))
    paths.update(math_fixtures / name for name in ('matrix.py', 'browser_matrix.py', 'cases.json', 'compressor-matrix-control.js'))
    inputs = {path: sha(path) for path in paths}
    report = {'schema': 1, 'passed': False, 'measurement_complete': False, 'checks': [], 'errors': [], 'asyncio_errors': [],
              'scope': __doc__, 'candidate': args.candidate, 'candidate_manifest_sha256': candidate['manifest_sha256'],
              'runtime_core_sha256_measured': core, 'receipt_sha256': hashlib.sha256(receipt).hexdigest(),
              'derivation_mode': 'profile-identity', 'privacy_admitted': False, 'production_admitted': False,
              'device_cohort_verified': False, 'measured_inputs_sha256': {str(path): value for path, value in inputs.items()}}
    protected_names = tuple(f'profile-{index:02d}' for index in range(args.profiles))
    profile_names = ('baseline', *protected_names)
    report['protected_profile_count'] = args.profiles

    def save():
        (OUTPUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')

    @dataclass(frozen=True)
    class CombinedConfiguration(gpu.ReadbackConfiguration):
        def launch_arguments(self):
            arguments = super().launch_arguments()
            if self.probe_mode == 'ready':
                indices = [index for index, value in enumerate(arguments) if value.startswith('--enable-features=')]
                if len(indices) != 1:
                    raise ValueError('Combined AudioMath requires one explicit feature list')
                arguments[indices[0]] += ',GlintAudioMathCandidate'
            return arguments

    def check(row, name, function):
        try:
            result = function()
            row.setdefault('validations', {})[name] = {'passed': True, 'result': result}
            return result
        except Exception as error:
            row.setdefault('validations', {})[name] = {'passed': False, 'error_type': type(error).__name__, 'error': str(error)}
            return None

    async def run(server, audio_server):
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
            assert not discovery.has_resources
        origin = f'http://127.0.0.1:{server.server_port}'
        captures, previous_gpu, previous_canvas, previous_audio = {}, {}, {}, {}
        previous_fidelity, previous_compressor, compressor_baseline = {}, {}, None
        identities = {}
        for name in profile_names:
            configuration = CombinedConfiguration(probe_mode='baseline' if name == 'baseline' else 'ready',
                derivation_mode='profile-identity', disabled_features_argument=replacement, ignored_driver_argument=original)
            runtime = NativeRuntime(PROFILE_ROOT / name, EXE, configuration)
            for phase in ('initial', 'restart'):
                row = {'profile': name, 'phase': phase, 'passed': False, 'validations': {}}
                report['checks'].append(row)
                save()
                before = await asyncio.to_thread(helpers.process_snapshot)
                owned = {}
                try:
                    context = await runtime.start(headless=True)
                    owned.update(helpers.controller_descendants(before, await asyncio.to_thread(helpers.process_snapshot), os.getpid()))
                    effective = await workers.browser_arguments(context)
                    if (any(argument not in effective for argument in configuration.launch_arguments())
                            or workers.partitioning_argument(effective) != replacement):
                        raise ValueError('Effective arguments do not request the combined policies and partitioning')
                    row['effective_features'] = [value for value in effective if value.startswith('--enable-features=')]
                    digest = sha(runtime.profile_dir / IDENTITY_FILE)
                    if name in identities:
                        if identities[name] != digest:
                            raise ValueError('Owned profile identity changed across restart')
                    identities[name] = digest
                    row['identity_stable'] = True
                    if name != 'baseline':
                        row['audio_reference_selector'] = compatibility.profile_math_selector(load_or_create_identity(runtime.profile_dir))
                    observed = await canvas.observe(context, origin, read=surfaces.combined_read(True))
                    row['observed'] = observed
                    canvas_values = {slot: value['canvas'] for slot, value in observed.items()}
                    audio_values = {slot: value['audio'] for slot, value in observed.items()}
                    gpu_values = {slot: value['gpu'] for slot, value in observed.items()}
                    check(row, 'canvas-paths-contexts-restart', lambda: canvas.validate_observations(canvas_values, previous_canvas.get(name)))
                    clean_audio = check(row, 'audio-sample-digests', lambda: quality.strip_quality(audio_values))
                    if clean_audio is not None:
                        check(row, 'audio-api-contexts-restart', lambda: audio.validate_observations(clean_audio, previous_audio.get(name)))
                        previous_audio[name] = clean_audio
                    baseline_gpu = captures.get('baseline', {}).get('normalized_gpu')
                    normalized = check(row, 'gpu-readback-export-contexts-restart', lambda: gpu.validate_readback(gpu_values,
                        protected=name != 'baseline', baseline=baseline_gpu, previous=previous_gpu.get(name), derivation_mode='profile-identity'))
                    row['fidelity'] = {}
                    page = context.pages[0]
                    frames = {'document': page.main_frame}
                    for slot, identifier in (('same_origin_frame', 'owned-frame'), ('cross_origin_frame', 'cross-origin'),
                                              ('about_blank_frame', 'owned-about-blank'), ('srcdoc_frame', 'owned-srcdoc')):
                        element = await page.locator('#' + identifier).element_handle()
                        frames[slot] = await element.content_frame()
                    for slot, frame in frames.items():
                        fidelity = await asyncio.wait_for(frame.evaluate(FIDELITY), timeout=90)
                        row['fidelity'][slot] = fidelity
                        check(row, 'audio-fidelity-' + slot, lambda value=fidelity: compatibility.validate_observation(value, 'fidelity'))
                    fidelity_hashes = {slot: compatibility.fidelity_hashes({'probes': {'fidelity': {'observed': value}}})
                                       for slot, value in row['fidelity'].items()}
                    def fidelity_restart():
                        if name in previous_fidelity and fidelity_hashes != previous_fidelity[name]:
                            raise ValueError('Five-document fidelity hashes changed across restart')
                    check(row, 'audio-fidelity-restart', fidelity_restart)
                    previous_fidelity[name] = fidelity_hashes
                    compressor_captures = {}
                    for slot, frame in frames.items():
                        rendered = await asyncio.wait_for(frame.evaluate(compressor_read, compressor_case), timeout=30)
                        compressor_captures[slot] = decode_capture(rendered, compressor_case)
                    row['compressor_effect'] = check(row, 'audio-long-compressor-effect-contexts-restart', lambda:
                        validate_compressor_effect(compressor_captures, baseline=compressor_baseline if name != 'baseline' else None,
                            previous=previous_compressor.get(name), selector=row.get('audio_reference_selector')))
                    previous_compressor[name] = compressor_captures
                    if name == 'baseline':
                        compressor_baseline = compressor_captures
                    security = {}
                    for slot, frame in (await canvas.security_frames(page)).items():
                        security[slot] = await asyncio.wait_for(frame.evaluate(canvas.SECURITY_READ), timeout=30)
                    row['security'] = security
                    check(row, 'canvas-origin-clean-errors', lambda: canvas.validate_security(security))
                    def audio_context_identity():
                        if clean_audio is None:
                            raise ValueError('Audio digest validation did not complete')
                        reference = clean_audio['document']
                        for slot in surfaces.DOCUMENT_CONTEXTS:
                            if clean_audio[slot] != reference:
                                raise ValueError('Audio profile identity context differs: ' + slot)
                    check(row, 'audio-profile-identity-context-consistency', audio_context_identity)
                    identifier = uuid.uuid4().hex
                    await page.goto(origin + '/surface-first-script?id=' + identifier, timeout=20000)
                    first = await asyncio.wait_for(page.evaluate('() => window.__glintFirstSurfaceRead'), timeout=30)
                    row['first_script'] = first
                    row['first_script_counts'] = server.counts(identifier)
                    check(row, 'canvas-audio-parser-and-initial-child', lambda: surfaces.validate_first_script(
                        first, {'canvas': canvas_values['document'], 'audio': audio_values['document']}, row['first_script_counts']))
                    row['audio_compatibility'] = await compatibility.measure(context, audio_server)
                    check(row, 'full-audio-collection-and-cleanup', lambda: validate_audio_completion(row['audio_compatibility']))
                    for probe in compatibility.PROBES:
                        check(row, 'full-audio-' + probe, lambda name=probe: compatibility.validate_observation(
                            row['audio_compatibility']['probes'][name]['observed'], name))
                    previous_canvas[name], previous_gpu[name] = canvas_values, gpu_values
                    captures[name] = {'canvas': canvas_values, 'audio': clean_audio, 'gpu': gpu_values, 'normalized_gpu': normalized}
                    owned.update(helpers.controller_descendants(before, await asyncio.to_thread(helpers.process_snapshot), os.getpid()))
                except Exception as error:
                    row['error'] = str(error)
                    row['traceback'] = traceback.format_exc()
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
                    row['remaining_observed_processes'] = 0
                    row['observed_processes'] = len(owned)
                    row['passed'] = bool(row['validations']) and not row.get('error') and all(value['passed'] for value in row['validations'].values()) and row['resources_released']
                    save()
        if set(captures) == set(profile_names):
            aggregate = {'validations': {}}
            def gpu_isolation():
                for first, second in combinations(protected_names, 2):
                    gpu.validate_profile_isolation(captures['baseline']['gpu'], captures[first]['gpu'], captures[second]['gpu'],
                                                   derivation_mode='profile-identity')
            check(aggregate, 'gpu-cross-profile-isolation', gpu_isolation)
            def canvas_isolation():
                for slot in canvas.CONTEXTS:
                    if len({captures[name]['canvas'][slot]['pixels'] for name in captures}) != len(profile_names):
                        raise ValueError('Canvas profiles are not isolated: ' + slot)
            check(aggregate, 'canvas-cross-profile-isolation', canvas_isolation)
            report['aggregate'] = aggregate
        await asyncio.sleep(0.1)
        gc.collect()
        await asyncio.sleep(0.1)
        report['audio_reference_selectors_observed'] = sorted({row['audio_reference_selector'] for row in report['checks'] if 'audio_reference_selector' in row})
        report['both_audio_math_selectors_observed'] = report['audio_reference_selectors_observed'] == [0, 1]
        report['measurement_complete'] = True
        report['passed'] = (len(report['checks']) == len(profile_names) * 2 and all(row['passed'] for row in report['checks'])
                            and not report['asyncio_errors'] and set(report.get('aggregate', {}).get('validations', {})) ==
                            {'gpu-cross-profile-isolation', 'canvas-cross-profile-isolation'}
                            and all(value['passed'] for value in report['aggregate']['validations'].values()))

    save()
    server = audio_server = thread = audio_thread = None
    try:
        server = surfaces.SurfaceFixtureServer(('127.0.0.1', 0), include_gpu_readback=True)
        audio_server = compatibility.AudioFixtureServer(compatibility.fixture_sources())
        audio_thread = threading.Thread(target=audio_server.serve_forever, daemon=True)
        audio_thread.start()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        asyncio.run(run(server, audio_server))
    except Exception as error:
        report['errors'].append({'type': type(error).__name__, 'error': str(error), 'traceback': traceback.format_exc()})
    finally:
        for fixture, fixture_thread in ((audio_server, audio_thread), (server, thread)):
            try:
                if fixture is not None:
                    if fixture_thread is not None and fixture_thread.is_alive():
                        fixture.shutdown()
                    fixture.server_close()
                if fixture_thread is not None:
                    fixture_thread.join(timeout=5)
            except Exception as error:
                report['errors'].append({'type': type(error).__name__, 'error': str(error), 'scope': 'fixture-cleanup'})
        try:
            verify(STAGE, args.driver_manifest)
            report['postguards_passed'] = (all(value is None or not value.is_alive() for value in (thread, audio_thread))
                and helpers.measure_runtime_core(EXE) == core and all(sha(path) == value for path, value in inputs.items())
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
