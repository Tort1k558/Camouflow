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


def main(*, module=MODULE, record_name='webgpu-buffer-scatter-observations.json',
         expected_result=None, extension_required=False, fixture_base=None,
         additional_native_sources=(), shader_paths=None, source_gate_path=None,
         source_record_path=None, fixture_preparer=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('chromium-root', 'sdk-root', 'work-dir'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    chromium, sdk, out = args.chromium_root, args.sdk_root, args.work_dir
    if (sys.platform != 'win32' or any(not p.is_absolute() or p != p.resolve()
            or p.is_symlink() or p.is_junction() or p.drive.upper() != 'D:'
            for p in (chromium, sdk, out)) or not chromium.is_dir() or not sdk.is_dir()
            or out.exists() or not out.parent.is_dir()
            or any(out.is_relative_to(p) or p.is_relative_to(out) for p in (module, MODULE, chromium, sdk))):
        parser.error('Use canonical D: checkout/SDK and a fresh external D: output')
    if shutil.disk_usage(out.parent).free < 1024**3:
        parser.error('At least 1 GiB free on D: is required')
    record_path = ENV / record_name
    record = json.loads(record_path.read_bytes())
    source_gate = source_gate_path if source_gate_path is not None else MODULE.parent / 'webgpu-execution-inputs/check.py'
    source_record = source_record_path if source_record_path is not None else ENV / 'webgpu-execution-inputs-preparation.json'
    edge_shader = MODULE.parent / 'webgpu-edge-compute/edge_compute.hlsl'
    expected = [(module / name, value) for name, value in record['sources_sha256'].items()]
    expected += [(module / 'check.py', record['checker_sha256']),
                 (source_gate, record['source_gate_checker_sha256']),
                 (source_record, record['source_gate_record_sha256']),
                 (edge_shader, record['edge_shader_sha256'])]
    if module != MODULE:
        expected.append((Path(__file__), record['shared_checker_sha256']))
    expected += [(MODULE / name, value) for name, value in record.get('dependency_sources_sha256', {}).items()]
    expected += [(MODULE.parent / name, value) for name, value in record.get('dependency_files_sha256', {}).items()]
    fixture_base = fixture_base if fixture_base is not None else MODULE / 'compute_test.cc'
    shader_paths = shader_paths if shader_paths is not None else (edge_shader, MODULE / 'buffer_scatter.hlsl')
    if any(path not in dict(expected) for path in (fixture_base, *shader_paths)):
        parser.error('Hardware fixture/shader is not bound to measured dependencies')
    extension = record.get('source_extension')
    if extension_required and not extension:
        parser.error('Missing required native shadow source extension')
    if extension:
        expected.append((ENV / extension['patch'], extension['patch_sha256']))
        expected += [(ENV / row['patch'], row['sha256']) for row in extension.get('prerequisites', [])]
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
        'scope': record['scope'], 'hardware_execution_verified': False,
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
        fixture = fixture_base
        if extension:
            for row in extension['sources']:
                relative = Path(row['source'])
                path = native / relative
                if relative.is_absolute() or '..' in relative.parts or path != path.resolve():
                    raise ValueError('Unsafe native shadow source path')
                actual = digest(path) if path.is_file() else None
                if actual != row['before_sha256'] or (actual is None and path.exists()):
                    raise ValueError('Native shadow source preimage differs')
            packets = [*(row['patch'] for row in extension.get('prerequisites', [])), extension['patch']]
            for packet in packets:
                subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error',
                                str(ENV / packet)], cwd=native, capture_output=True, check=True)
            for row in extension['sources']:
                path = native / row['source']
                if not path.is_file() or digest(path) != row['after_sha256']:
                    raise ValueError('Native shadow source result differs')
                guards[path] = row['after_sha256']
            fixture_dir = out / 'fixture'
            fixture_dir.mkdir()
            fixture = fixture_dir / 'compute_test.cc'
            shutil.copyfile(fixture_base, fixture)
            if record.get('fixture_patch'):
                subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error',
                                str(module / record['fixture_patch'])], cwd=fixture_dir, capture_output=True, check=True)
            if digest(fixture) != record['composed_fixture_sha256']:
                raise ValueError('Native shadow hardware fixture differs')
            guards[fixture] = digest(fixture)
            if fixture_preparer is not None:
                generated = fixture_preparer(native, fixture_dir)
                if set(generated) != set(record['generated_sources_sha256']):
                    raise ValueError('Generated native hardware fixture set differs')
                for name, path in generated.items():
                    if path.parent != fixture_dir or digest(path) != record['generated_sources_sha256'][name]:
                        raise ValueError('Generated native hardware fixture differs')
                    guards[path] = digest(path)
            abi = native / 'third_party/dawn/src/dawn/native/d3d12/glint/buffer_scatter_parameters.h'
            if digest(abi) != digest(MODULE / 'buffer_scatter_parameters.h'):
                raise ValueError('Native and shared scatter parameter ABI differ')
            report['native_source_extension_verified'] = True
        math = native / 'gpu/command_buffer/common/glint'
        sources = [math / (name + '.cc') for name in (
            'canvas_readback_candidate', 'webgpu_readback_layout', 'webgpu_readback_provenance')]
        sources.append(fixture)
        if extension:
            sources += [native / 'third_party/dawn/src/dawn/native/d3d12/glint' / name
                        for name in ('projected_buffer.cc', 'texture_capture.cc', *additional_native_sources)]
        guards.update({path: digest(path) for path in sources})
        flags = [str(compiler), '/nologo', '/std:c++20', '/W4', '/WX', '/EHsc', '/MT',
                 '/Od', '/Z7', '/DNOMINMAX', '/DWIN32_LEAN_AND_MEAN', '/winsysroot:' + str(sdk)]
        flags += ['/imsvc' + str(sdk / 'VC/Tools/MSVC/14.51.36231/include')]
        flags += ['/imsvc' + str(sdk / 'Windows Kits/10/Include/10.0.28000.0' / kind)
                  for kind in ('ucrt', 'shared', 'um', 'winrt')]
        flags += ['/I' + str(p) for p in (fixture.parent, module, MODULE,
                  native / 'third_party/dawn/src/dawn/native/d3d12/glint',
                  native, chromium, chromium / 'third_party/boringssl/src/include')]
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
            result = subprocess.run([str(directory / 'check.exe'), *(str(path) for path in shader_paths)],
                cwd=directory, env=run_environment, capture_output=True, text=True, timeout=180, check=False)
            (directory / 'test.log').write_text(result.stdout + result.stderr, encoding='utf-8')
            row['test_returncode'] = result.returncode
            if result.returncode:
                raise RuntimeError('Buffer-scatter hardware fixture execution failed')
            value = row['result'] = json.loads(result.stdout)
            required = expected_result if expected_result is not None else {
                'passed': True, 'hardware_adapter': True, 'cases': 58, 'assertions': 176704,
                'rejected_parameters': 696, 'gpu_projection_scatter_consumer_verified': True,
                'split_only_scatter_verified': True, 'duplicate_scatter_verified': True,
                'protected_source_unchanged': True, 'native_binding_routing_installed': False,
                'browser_integrated': False,
            }
            if not isinstance(value, dict) or any(
                    name not in value or type(value[name]) is not type(field) or value[name] != field
                    for name, field in required.items()):
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
