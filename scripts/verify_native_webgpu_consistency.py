"""Owned WebGPU copy/shader/PNG consistency gate; never full privacy admission."""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import shutil
import struct
import sys
import threading
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / 'native/drafts/environment/first-script/webgpu_shader_dataflow.js'
DRIVER_MANIFEST = ROOT / 'native/drafts/environment/playwright-driver-stage-binding-close.json'
PIXEL_BYTES = 16 * 16 * 4


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounded_bytes(value: object, size: int) -> bytes:
    if (not isinstance(value, list) or len(value) != size
            or any(type(byte) is not int or not 0 <= byte <= 255 for byte in value)):
        raise ValueError('Malformed bounded shader pixels')
    return bytes(value)


def decode_png(value: object) -> bytes:
    if not isinstance(value, str) or not value.startswith('data:image/png;base64,') or len(value) > 90000:
        raise ValueError('Malformed bounded PNG data URL')
    data = base64.b64decode(value.split(',', 1)[1], validate=True)
    if (len(data) < 33 or len(data) > 65536 or data[:16] != b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
            or data[16:24] != struct.pack('>II', 16, 16)):
        raise ValueError('PNG must declare the fixed 16x16 fixture before decoding')
    from PyQt6.QtGui import QImage

    image = QImage.fromData(data, 'PNG').convertToFormat(QImage.Format.Format_RGBA8888)
    if image.isNull() or image.width() != 16 or image.height() != 16 or image.bytesPerLine() != 64:
        raise ValueError('PNG fixture dimensions or format changed')
    return image.constBits().asstring(image.sizeInBytes())


def compare(first: bytes, second: bytes) -> dict:
    if len(first) != PIXEL_BYTES or len(second) != PIXEL_BYTES:
        raise ValueError('RGBA fixture length changed')
    delta = [abs(a-b) for a,b in zip(first, second, strict=True)]
    return {'changed_channels': sum(value != 0 for value in delta), 'maximum_delta': max(delta)}


def validate_rows(rows: list[dict]) -> dict:
    if (not isinstance(rows, list) or len(rows) != 2
            or any(not isinstance(row, dict) or type(row.get('mode')) is not str
                   or row['mode'] not in ('baseline', 'ready') for row in rows)
            or {row['mode'] for row in rows} != {'baseline', 'ready'}):
        raise ValueError('Exactly one baseline and ready document are required')
    reference = bytes(channel for y in range(16) for x in range(16)
                      for channel in ((x * 17) % 256, (y * 29 + 31) % 256,
                                      (x * 43 + y * 11) % 256, 255))
    measured = []
    for row in rows:
        value = row.get('value')
        if (row.get('context') != 'document' or not isinstance(value, dict)
                or value.get('measured') is not True or value.get('commandValidationPassed') is not True
                or value.get('exportStable') is not True
                or value.get('format') not in ('rgba8unorm', 'bgra8unorm')):
            raise ValueError('Missing successful owned document/GPU commands/export')
        encoded = value.get('rgbaBase64')
        if not isinstance(encoded, str) or len(encoded) > 2048:
            raise ValueError('Malformed bounded direct GPU pixels')
        direct = base64.b64decode(encoded, validate=True)
        shader = bounded_bytes(value.get('shaderRGBA'), PIXEL_BYTES)
        png = decode_png(value.get('png'))
        if any(any(alpha != 255 for alpha in pixels[3::4]) for pixels in (direct, shader, png)):
            raise ValueError('Opaque fixture alpha changed')
        deviations = {name: compare(data, reference) for name,data in (
            ('direct', direct), ('shader', shader), ('png', png))}
        if row['mode'] == 'baseline' and any(item['changed_channels'] for item in deviations.values()):
            raise ValueError('Unprotected fixture no longer matches exact integer colors')
        if any(item['maximum_delta'] > 1 for item in deviations.values()):
            raise ValueError('Fixture colors exceed the current one-level policy bound')
        measured.append({'mode': row['mode'], 'measured': True, 'deviation_from_reference': deviations,
            'direct_vs_shader': compare(direct, shader), 'png_vs_direct': compare(png, direct),
            'png_vs_shader': compare(png, shader), 'shader_rgba_sha256': hashlib.sha256(shader).hexdigest()})
    ready = next(row for row in measured if row['mode'] == 'ready')
    noise_observed = ready['deviation_from_reference']['png']['changed_channels'] > 0
    coherent = all(not row[name]['changed_channels'] for row in measured
                   for name in ('direct_vs_shader', 'png_vs_direct', 'png_vs_shader'))
    return {'fixture_validation_passed': True, 'surface_noise_observed': noise_observed,
            'readback_consistent': coherent, 'consistency_gate_passed': noise_observed and coherent,
            'rows': measured, 'privacy_admitted': False, 'production_admitted': False}


class FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'<!doctype html><title>Owned WebGPU consistency fixture</title>'
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


async def observe(executable: Path, owned: Path, server, source: str, report: dict, runtimes: list):
    from app.core.native.runtime import NativeRuntime
    from scripts.verify_native_gpu_readback import ReadbackConfiguration
    from scripts.verify_native_worker_startup import (
        browser_arguments,
        partitioning_argument,
    )

    discovery = NativeRuntime(owned / 'discovery', executable, ReadbackConfiguration(probe_mode='baseline'))
    runtimes.append(discovery)
    try:
        context = await discovery.start(headless=True)
        disabled = [value for value in await browser_arguments(context) if value.startswith('--disable-features=')]
        if len(disabled) != 1:
            raise ValueError('Expected exact measured driver feature exclusion')
        original = disabled[0]
        replacement = partitioning_argument([original])
    finally:
        await discovery.close()
    report['driver_partitioning'] = {'original': original, 'replacement': replacement}
    for mode in ('baseline', 'ready'):
        runtime = NativeRuntime(owned / mode, executable, ReadbackConfiguration(probe_mode=mode,
            derivation_mode='profile-identity', disabled_features_argument=replacement,
            ignored_driver_argument=original))
        runtimes.append(runtime)
        try:
            context = await runtime.start(headless=True)
            arguments = await browser_arguments(context)
            if replacement not in arguments or (original != replacement and original in arguments):
                raise ValueError('Requested partitioning arguments were not effective')
            page = await context.new_page()
            await page.goto(f'http://127.0.0.1:{server.server_port}/', wait_until='load')
            value = await asyncio.wait_for(page.evaluate('async () => {' + source + '; return await probeWebGPU();}'), 90)
            report['observations'].append({'mode': mode, 'context': 'document', 'value': value})
        finally:
            await runtime.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--driver-stage', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    paths = (args.executable, args.driver_stage, args.work_dir)
    if (sys.platform != 'win32' or any(not p.is_absolute() or p != p.resolve()
            or p.is_symlink() or p.is_junction() or p.drive.upper() != 'D:' for p in paths)
            or not args.executable.is_file() or not args.driver_stage.is_dir()
            or args.work_dir.exists() or not args.work_dir.parent.is_dir()
            or args.work_dir.is_relative_to(ROOT) or ROOT.is_relative_to(args.work_dir)
            or any(args.work_dir.is_relative_to(p) or p.is_relative_to(args.work_dir)
                   for p in (args.executable.parent, args.driver_stage))):
        parser.error('Use existing canonical D: runtime/driver and a fresh external D: work directory')
    if shutil.disk_usage(args.work_dir.parent).free < 1024**3:
        parser.error('At least 1 GiB free is required for owned browser profiles')
    args.work_dir.mkdir(exist_ok=False)
    owned = args.work_dir / 'profiles'
    owned.mkdir()
    report = {'schema': 1, 'passed': False, 'measurement_complete': False, 'postguards_passed': False,
              'scope': __doc__, 'observations': [], 'privacy_admitted': False, 'production_admitted': False}
    server = thread = None
    runtimes, inputs = [], {}
    core = receipt = None
    try:
        sys.path.insert(0, str(ROOT))
        from scripts.native_driver_stage import verify

        verify(args.driver_stage, DRIVER_MANIFEST)
        existing = sys.modules.get('playwright')
        if existing is not None and not Path(existing.__file__).resolve().is_relative_to(args.driver_stage):
            raise ValueError('An unrelated Playwright package was already imported')
        sys.path.insert(0, str(args.driver_stage))
        os.environ.update(PYTHONDONTWRITEBYTECODE='1', TMP=str(args.work_dir), TEMP=str(args.work_dir),
            CAMOUFLOW_DATA_DIR=str(args.work_dir / 'workspace'),
            PLAYWRIGHT_NODEJS_PATH=str(args.driver_stage / 'playwright/driver/node.exe'))
        sys.dont_write_bytecode = True
        from scripts.verify_native_gpu_readback import probe_inputs, validate_receipt
        from scripts.verify_native_runtime import FixtureServer, measure_runtime_core

        core = measure_runtime_core(args.executable)
        receipt = validate_receipt(args.executable, core, derivation_mode='profile-identity', candidate_name='upstream-156')
        probe_snapshot = probe_inputs()
        inputs = {str(ROOT / path): value for path,value in probe_snapshot.items()}
        inputs.update({str(path): digest(path) for path in (Path(__file__), PROBE, DRIVER_MANIFEST)})
        report.update(runtime_core_sha256_measured=core, receipt_sha256=hashlib.sha256(receipt).hexdigest(),
                      probe_inputs_sha256=inputs, javascript_sha256=digest(PROBE), candidate='upstream-156')
        server = FixtureServer(('127.0.0.1', 0), FixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        asyncio.run(observe(args.executable, owned, server, PROBE.read_text(encoding='utf-8-sig'), report, runtimes))
        report['result'] = validate_rows(report['observations'])
        report['measurement_complete'] = True
        report['postguards_passed'] = (measure_runtime_core(args.executable) == core
            and validate_receipt(args.executable, core, derivation_mode='profile-identity', candidate_name='upstream-156') == receipt
            and probe_inputs() == probe_snapshot
            and all(digest(Path(path)) == value for path,value in inputs.items()))
        verify(args.driver_stage, DRIVER_MANIFEST)
        report['passed'] = report['postguards_passed'] and report['result']['consistency_gate_passed']
    except Exception as error:  # noqa: BLE001 - retain failed native diagnostic evidence
        report.update(error_type=type(error).__name__, error=str(error))
    finally:
        if server is not None:
            if thread is not None and thread.is_alive():
                server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)
            if thread.is_alive():
                report.update(passed=False, cleanup_error='Owned fixture server still active')
        try:
            if any(runtime.has_resources for runtime in runtimes):
                raise ValueError('Owned runtime resources remain')
            if owned != owned.resolve() or not owned.is_relative_to(args.work_dir):
                raise ValueError('Refusing cleanup outside fresh owned work directory')
            shutil.rmtree(owned)
        except (OSError, ValueError) as error:
            report.update(passed=False, cleanup_error=str(error), retained_profile_directory=str(owned))
        with (args.work_dir / 'report.json').open('x', encoding='utf-8') as output:
            json.dump(report, output, indent=2)
    print(json.dumps({key: report.get(key) for key in ('passed', 'measurement_complete', 'postguards_passed', 'error')}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
