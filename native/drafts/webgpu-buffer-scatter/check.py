"""Run GPU projection -> tagged-byte scatter -> shader consumer; no native binding/browser admission."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parent
REPO = MODULE.parents[2]
ENV = REPO / 'native/drafts/environment'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('chromium-root', 'sdk-root', 'work-dir'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    chromium, sdk, out = args.chromium_root, args.sdk_root, args.work_dir
    if (sys.platform != 'win32' or any(not p.is_absolute() or p != p.resolve()
            or p.is_symlink() or p.is_junction() or p.drive.upper() != 'D:'
            for p in (chromium, sdk, out)) or not chromium.is_dir() or not sdk.is_dir()
            or out.exists() or not out.parent.is_dir()
            or any(out.is_relative_to(p) or p.is_relative_to(out) for p in (MODULE, chromium, sdk))):
        parser.error('Use canonical D: checkout/SDK and a fresh external D: output')
    if shutil.disk_usage(out.parent).free < 1024**3:
        parser.error('At least 1 GiB free on D: is required')
    record_path = ENV / 'webgpu-buffer-scatter-observations.json'
    record = json.loads(record_path.read_bytes())
    source_gate = MODULE.parent / 'webgpu-execution-inputs/check.py'
    source_record = ENV / 'webgpu-execution-inputs-preparation.json'
    edge_shader = MODULE.parent / 'webgpu-edge-compute/edge_compute.hlsl'
    expected = [(MODULE / name, value) for name, value in record['sources_sha256'].items()]
    expected += [(Path(__file__), record['checker_sha256']),
                 (source_gate, record['source_gate_checker_sha256']),
                 (source_record, record['source_gate_record_sha256']),
                 (edge_shader, record['edge_shader_sha256'])]
    for path, value in expected:
        if digest(path) != value:
            parser.error('Measured buffer-scatter source/dependency differs')
    tools = chromium / 'third_party/llvm-build/Release+Asserts'
    compiler, linker = tools / 'bin/clang-cl.exe', tools / 'bin/lld-link.exe'
    asan = tools / 'lib/clang/24/lib/windows/clang_rt.asan_dynamic-x86_64.dll'
    libraries = [chromium / 'out/CamouFlowNative/obj/third_party/boringssl' / name
                 for name in ('boringssl.lib', 'boringssl_asm.lib')]
    libraries.append(chromium / 'out/CamouFlowNative/obj/buildtools/third_party/libc++/libc++/verbose_abort.obj')
    guards = {p: digest(p) for p in (record_path, compiler, linker, asan, *libraries,
              Path('C:/Windows/System32/d3dcompiler_47.dll'),
              *(sdk / 'Windows Kits/10/Lib/10.0.28000.0/um/x64' / name
                for name in ('d3d12.lib', 'dxgi.lib', 'dxguid.lib', 'd3dcompiler.lib')))}
    guards.update(dict(expected))
    out.mkdir(exist_ok=False)
    temp = out / 'temp'
    temp.mkdir()
    environment = dict(os.environ, TMP=str(temp), TEMP=str(temp))
    report = {
        'schema': 1, 'passed': False, 'measurement_complete': False, 'runs': [],
        'scope': __doc__, 'hardware_execution_verified': False,
        'native_binding_routing_installed': False, 'native_immutable_gpu_snapshot_registry_implemented': False,
        'native_budgeted_shadow_buffer_allocator_implemented': False,
        'actual_native_device_queue_executed': False, 'actual_wire_server_roundtrip_executed': False,
        'dxc_execution_verified': False, 'browser_integrated': False,
        'privacy_admitted': False, 'production_admitted': False,
    }
    try:
        gate_dir = out / 'source-gate'
        with (out / 'source-gate.log').open('xb') as log:
            gate = subprocess.run([sys.executable, str(source_gate),
                '--chromium-root', str(chromium), '--sdk-root', str(sdk), '--work-dir', str(gate_dir)],
                env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=300, check=False)
        if gate.returncode:
            raise RuntimeError('Execution-input source gate failed')
        gate_report = json.loads((gate_dir / 'report.json').read_bytes())
        if not all(gate_report.get(key) is True for key in ('passed', 'measurement_complete', 'postguards_passed')):
            raise ValueError('Incomplete execution-input source gate')
        report['source_gate'] = {key: gate_report[key] for key in ('passed', 'measurement_complete', 'postguards_passed', 'runs')}
        guards.update({Path(p): value for p, value in gate_report['input_sha256'].items()})
        native = gate_dir / 'sources'
        math = native / 'gpu/command_buffer/common/glint'
        sources = [math / (name + '.cc') for name in (
            'canvas_readback_candidate', 'webgpu_readback_layout', 'webgpu_readback_provenance')]
        sources.append(MODULE / 'compute_test.cc')
        flags = [str(compiler), '/nologo', '/std:c++20', '/W4', '/WX', '/EHsc', '/MT',
                 '/Od', '/Z7', '/DNOMINMAX', '/DWIN32_LEAN_AND_MEAN', '/winsysroot:' + str(sdk)]
        flags += ['/imsvc' + str(sdk / 'VC/Tools/MSVC/14.51.36231/include')]
        flags += ['/imsvc' + str(sdk / 'Windows Kits/10/Include/10.0.28000.0' / kind)
                  for kind in ('ucrt', 'shared', 'um', 'winrt')]
        flags += ['/I' + str(p) for p in (MODULE, native, chromium, chromium / 'third_party/boringssl/src/include')]
        link = ['-fuse-ld=lld', '/link', *('/LIBPATH:' + str(p) for p in (
            sdk / 'VC/Tools/MSVC/14.51.36231/lib/x64',
            sdk / 'Windows Kits/10/Lib/10.0.28000.0/ucrt/x64',
            sdk / 'Windows Kits/10/Lib/10.0.28000.0/um/x64')),
            'd3d12.lib', 'dxgi.lib', 'dxguid.lib', 'd3dcompiler.lib',
            *(str(p) for p in libraries), 'bcrypt.lib', 'advapi32.lib']
        for mode in ('none', 'address'):
            directory = out / mode
            directory.mkdir()
            command = [*flags, *(['/fsanitize=address'] if mode == 'address' else []),
                       *(str(p) for p in sources), '/Fe' + str(directory / 'check.exe'), *link]
            with (directory / 'compile.log').open('xb') as log:
                result = subprocess.run(command, cwd=directory, env=environment,
                    stdout=log, stderr=subprocess.STDOUT, timeout=180, check=False)
            row = {'sanitizer': mode, 'compile_returncode': result.returncode}
            report['runs'].append(row)
            if result.returncode:
                raise RuntimeError('Buffer-scatter hardware fixture compilation failed')
            run_environment = dict(environment, PATH=str(asan.parent) + os.pathsep + environment.get('PATH', ''),
                                   ASAN_OPTIONS='halt_on_error=1:abort_on_error=1:exitcode=99')
            result = subprocess.run([str(directory / 'check.exe'), str(edge_shader), str(MODULE / 'buffer_scatter.hlsl')],
                cwd=directory, env=run_environment, capture_output=True, text=True, timeout=180, check=False)
            (directory / 'test.log').write_text(result.stdout + result.stderr, encoding='utf-8')
            row['test_returncode'] = result.returncode
            if result.returncode:
                raise RuntimeError('Buffer-scatter hardware fixture execution failed')
            value = row['result'] = json.loads(result.stdout)
            if not (value.get('passed') is True and value.get('hardware_adapter') is True
                    and value.get('cases') == 58 and value.get('assertions') == 176704
                    and value.get('rejected_parameters') == 696
                    and value.get('gpu_projection_scatter_consumer_verified') is True
                    and value.get('split_only_scatter_verified') is True
                    and value.get('duplicate_scatter_verified') is True
                    and value.get('protected_source_unchanged') is True
                    and value.get('native_binding_routing_installed') is False
                    and value.get('browser_integrated') is False):
                raise ValueError('Missing explicit standalone GPU scope')
            print(mode, result.stdout.strip(), flush=True)
        report.update(passed=True, measurement_complete=True, hardware_execution_verified=True)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        report['error'] = str(error)
    finally:
        report['input_sha256'] = {str(p): value for p, value in guards.items()}
        report['postguards_passed'] = all(p.is_file() and digest(p) == value for p, value in guards.items())
        report['passed'] = report['passed'] and report['postguards_passed']
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
