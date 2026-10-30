"""Differential Canvas sRGB/Display-P3/unorm8/float16 compatibility and effect gate."""
import argparse
import asyncio
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import re
import runpy
import sys
import threading

ROOT = Path(__file__).resolve().parents[4]

COLOR_SPACES = ('srgb', 'display-p3')
COLOR_TYPES = ('unorm8', 'float16')
PIXEL_FORMATS = ('rgba-unorm8', 'rgba-float16')
FIELDS = ('kind', 'colorSpace', 'colorType', 'readColorSpace', 'pixelFormat')
CASE_KEYS = frozenset(product(('html', 'offscreen'), COLOR_SPACES, COLOR_TYPES, COLOR_SPACES, PIXEL_FORMATS))


def compare_formats(baseline: dict, protected: dict) -> dict:
    def index(record):
        rows = record.get('rows') if isinstance(record, dict) else None
        if not isinstance(rows, list) or len(rows) != len(CASE_KEYS):
            raise ValueError('Canvas format probe requires all 32 cases')
        indexed = {}
        for row in rows:
            if not isinstance(row, dict) or any(not isinstance(row.get(field), str) for field in FIELDS):
                raise ValueError('Canvas format case is malformed')
            key = tuple(row[field] for field in FIELDS)
            if key not in CASE_KEYS or key in indexed:
                raise ValueError('Canvas format cases are unknown or duplicated')
            indexed[key] = row
        return indexed
    def valid(row):
        value = row.get('observed')
        array_type, byte_count = ('Uint8ClampedArray', 1024) if row['pixelFormat'] == 'rgba-unorm8' else ('Float16Array', 2048)
        return (isinstance(value, dict) and value.get('arrayType') == array_type
            and value.get('length') == 1024 and value.get('bytes') == byte_count
            and value.get('colorSpace') == row['readColorSpace'] and value.get('pixelFormat') == row['pixelFormat']
            and value.get('finite') is True and isinstance(value.get('hash'), str)
            and re.fullmatch('[0-9a-f]{64}', value['hash']) is not None and value.get('repeat') == value['hash'])
    base, guarded = index(baseline), index(protected)
    result = {'cases': len(CASE_KEYS), 'baseline_supported': 0, 'protected_supported': 0,
              'compatibility_regressions': [], 'baseline_unavailable': [], 'no_effect': []}
    for key in sorted(CASE_KEYS):
        reference, candidate = base[key], guarded[key]
        if not valid(reference):
            result['baseline_unavailable'].append(dict(zip(FIELDS, key)))
            continue
        result['baseline_supported'] += 1
        if not valid(candidate):
            result['compatibility_regressions'].append({**dict(zip(FIELDS, key)),
                'error': candidate.get('error') or candidate.get('setupError') or {'name': 'InvalidObservation'}})
            continue
        result['protected_supported'] += 1
        if candidate['observed']['hash'] == reference['observed']['hash']:
            result['no_effect'].append(dict(zip(FIELDS, key)))
    result['compatibility_passed'] = not result['baseline_unavailable'] and not result['compatibility_regressions']
    result['protection_effect_observed'] = result['compatibility_passed'] and not result['no_effect']
    return result


READ = '''async () => {
 const hash = async data => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',
    data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength))), b => b.toString(16).padStart(2, '0')).join('');
 const rows = [];
 for (const kind of ['html', 'offscreen']) for (const colorSpace of ['srgb', 'display-p3']) for (const colorType of ['unorm8', 'float16']) {
  const canvas = kind === 'html' ? document.createElement('canvas') : new OffscreenCanvas(16, 16);
  canvas.width = canvas.height = 16;
  const parent = {kind, colorSpace, colorType};
  let ctx;
  try { ctx = canvas.getContext('2d', {colorSpace, colorType}); parent.attributes = ctx.getContextAttributes(); }
  catch (error) { for (const readColorSpace of ['srgb','display-p3']) for (const pixelFormat of ['rgba-unorm8','rgba-float16']) rows.push({...parent,readColorSpace,pixelFormat,setupError:{name:error.name,message:error.message}}); continue; }
  for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) {
   ctx.fillStyle = `rgb(${x*17} ${y*13} ${((x+y)*11)%256})`; ctx.fillRect(x,y,1,1);
  }
  for (const readColorSpace of ['srgb','display-p3']) for (const pixelFormat of ['rgba-unorm8','rgba-float16']) {
   const row = {...parent, readColorSpace, pixelFormat};
   try {
    const image = ctx.getImageData(0,0,16,16,{colorSpace:readColorSpace,pixelFormat});
    const repeat = ctx.getImageData(0,0,16,16,{colorSpace:readColorSpace,pixelFormat});
    row.observed = {arrayType:image.data.constructor.name, colorSpace:image.colorSpace, pixelFormat:image.pixelFormat??null,
      length:image.data.length, bytes:image.data.byteLength, hash:await hash(image.data), repeat:await hash(repeat.data),
      finite:Array.from(image.data).every(Number.isFinite)};
   } catch (error) { row.error = {name:error.name, message:error.message}; }
   rows.push(row);
  }
 }
 return {float16Available:typeof Float16Array !== 'undefined', rows};
}'''

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
    choose = runpy.run_path(str(Path(__file__).with_name('combined_concurrent.py')))['choose_cohort_profiles']
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
    from scripts import verify_native_gpu_readback as gpu
    from scripts import verify_native_surfaces as surfaces
    from scripts import verify_native_worker_startup as workers
    from scripts import verify_native_runtime as helpers

    EXE = args.executable
    sha = digest
    core = helpers.measure_runtime_core(EXE)
    receipt = gpu.validate_receipt(EXE, core, derivation_mode='profile-identity', candidate_name=args.candidate)
    if core != prior['runtime_core_sha256_measured']:
        raise ValueError('Cohort and selected runtime core differ')
    paths = {Path(__file__), Path(__file__).with_name('combined_concurrent.py'), COHORT / 'report.json', args.driver_manifest,
             ROOT / 'scripts/native_driver_stage.py', *[ROOT / name for name in gpu.probe_inputs()],
             STAGE / 'playwright/driver/package/lib/coreBundle.js', STAGE / 'playwright/_impl/_page.py', STAGE / 'playwright/driver/node.exe'}
    inputs = {path: sha(path) for path in paths}
    report = {'schema': 1, 'measurement_complete': False, 'scope': __doc__, 'runs': [],
              'privacy_admitted': False, 'production_admitted': False, 'passed': False, 'errors': [],
              'runtime_core_sha256_measured': core, 'receipt_sha256': hashlib.sha256(receipt).hexdigest(),
              'measured_inputs_sha256': {str(path): value for path, value in inputs.items()}}

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
        for name, profile_name in (('baseline', 'baseline'), ('protected', target_profile)):
            configuration = gpu.ReadbackConfiguration(probe_mode='baseline' if name == 'baseline' else 'ready',
                derivation_mode='profile-identity', disabled_features_argument=replacement, ignored_driver_argument=original)
            runtime = NativeRuntime(COHORT / profile_name, EXE, configuration)
            row = {'profile': name}
            report['runs'].append(row)
            try:
                context = await runtime.start(headless=True)
                page = context.pages[0]
                await page.goto(f'http://127.0.0.1:{server.server_port}')
                row['observed'] = await asyncio.wait_for(page.evaluate(READ), timeout=30)
            finally:
                await runtime.close()
                row['resources_released'] = not runtime.has_resources
                save()
        report['comparison'] = compare_formats(report['runs'][0]['observed'], report['runs'][1]['observed'])
        report['passed'] = report['comparison']['compatibility_passed'] and report['comparison']['protection_effect_observed']
        report['measurement_complete'] = True

    server = thread = None
    save()
    try:
        server = surfaces.SurfaceFixtureServer(('127.0.0.1', 0))
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
        'postguards_passed': report['postguards_passed'], 'baseline_supported': comparison.get('baseline_supported'),
        'protected_supported': comparison.get('protected_supported'),
        'compatibility_regressions': len(comparison.get('compatibility_regressions', []))}))
    return 0 if report['passed'] else 1


if __name__ == "__main__":
    raise SystemExit(main())
