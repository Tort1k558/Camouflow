"""Replay the shader capture source batch and run one bounded standalone suite; no actual Dawn device/queue, Wire server or browser admission."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RASTER = ROOT.parent / 'webgpu-raster-routing'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--chromium-root', type=Path, required=True)
parser.add_argument('--sdk-root', type=Path, required=True)
parser.add_argument('--work-dir', type=Path, required=True)
parser.add_argument('--suite', choices=('hardware','controller','core','legacy','texture-compat'), default='hardware')
args = parser.parse_args()
CHROMIUM, SDK, OUT = args.chromium_root, args.sdk_root, args.work_dir
if (sys.platform != 'win32' or any(not path.is_absolute() or path != path.resolve()
        or path.is_symlink() or path.is_junction() or path.drive.upper() != 'D:'
        for path in (CHROMIUM, SDK, OUT)) or not CHROMIUM.is_dir() or not SDK.is_dir()
        or OUT.exists() or not OUT.parent.is_dir()
        or any(OUT.is_relative_to(path) or path.is_relative_to(OUT)
               for path in (ROOT, CHROMIUM, SDK))):
    parser.error('Use existing canonical D: sources/SDK and fresh external D: output')
if shutil.disk_usage(OUT.parent).free < 1024**3:
    parser.error('At least 1 GiB free on D: is required')
TOOLS = CHROMIUM / 'third_party/llvm-build/Release+Asserts/bin'
OUT.mkdir(exist_ok=False)
(OUT / 'temp').mkdir()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
compiler, linker = TOOLS / 'clang-cl.exe', TOOLS / 'lld-link.exe'
asan = TOOLS.parent / 'lib/clang/24/lib/windows/clang_rt.asan_dynamic-x86_64.dll'
inputs = {path: sha(path) for path in [*ROOT.glob('*.hlsl'), *ROOT.glob('*.cc'), *ROOT.glob('*.h'), *ROOT.glob('*.inc'), Path(__file__)]}
dependencies = {path: sha(path) for path in (compiler, linker, asan, *(SDK / 'Windows Kits/10/Lib/10.0.28000.0/um/x64' / name for name in ('d3d12.lib', 'dxgi.lib', 'dxguid.lib', 'd3dcompiler.lib')))}
report = {'schema': 1, 'passed': False, 'measurement_complete': False, 'runs': [],
    'source_sha256': {path.name: value for path, value in inputs.items()},
    'dependency_sha256': {str(path): value for path, value in dependencies.items()},
    'scope': __doc__, 'browser_integrated': False, 'native_shader_input_routing_installed': False,
    'hardware_execution_verified': False, 'privacy_admitted': False, 'production_admitted': False}
environment = dict(os.environ, TMP=str(OUT / 'temp'), TEMP=str(OUT / 'temp'))
REPO = ROOT.parents[2]
ENV = REPO / 'native/drafts/environment'
record_path = ENV / 'webgpu-shader-capture-preparation.json'
record = json.loads(record_path.read_bytes())
packets = [*(ENV / row['patch'] for row in record['prerequisites']), ENV / record['patch']]
for row, packet in zip([*record['prerequisites'], {'sha256': record['patch_sha256']}], packets):
    if sha(packet) != row['sha256']:
        parser.error('Public source packet hash differs')
staging = OUT / 'sources'
staging.mkdir()
missing_baseline = []
for row in record['composed_sources']:
    path = CHROMIUM / row['source']
    if row['before_sha256'] is None:
        if path.exists(): parser.error('Expected an unselected source baseline')
        missing_baseline.append(path)
    else:
        if not path.is_file() or sha(path) != row['before_sha256']:
            parser.error('Pinned Chromium baseline differs: ' + row['source'])
        target = staging / row['source']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        inputs[path] = sha(path)
for packet in packets:
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error', str(packet)],
                   cwd=staging, check=True, capture_output=True)
for row in record['composed_sources']:
    path = staging / row['source']
    if row['after_sha256'] is None:
        valid = not path.exists()
    else:
        valid = path.is_file() and sha(path) == row['after_sha256']
    if not valid: parser.error('Composed source differs: ' + row['source'])
HELPER = ROOT.parent / 'webgpu-shadow-texture'
base_test = HELPER / 'shadow_test.cc'
fixture_patch = RASTER / 'hardware-fixture.patch'
for path, expected in ((base_test, record['base_hardware_test_sha256']),
                       (fixture_patch, record['fixture_patch_sha256']),
                       (RASTER / 'descriptor_fixture.h', record['descriptor_fixture_sha256']),
                       (RASTER / 'raster_consumer.hlsl', record['raster_shader_sha256'])):
    if sha(path) != expected: parser.error('Measured descriptor/raster fixture differs')
shutil.copyfile(base_test, staging / 'shadow_test.cc')
subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error', str(fixture_patch)],
               cwd=staging, check=True, capture_output=True)
extra_patch = ROOT / 'hardware.patch'
if sha(extra_patch) != record['hardware_patch_sha256']:
    parser.error('Measured shader capture hardware delta differs')
subprocess.run(['git','-c','core.autocrlf=false','apply','--whitespace=error',str(extra_patch)],
               cwd=staging,check=True,capture_output=True)
if sha(staging / 'shadow_test.cc') != record['hardware_test_sha256']:
    parser.error('Composed shader capture fixture differs')
adapter_source = staging / 'third_party/dawn/src/dawn/native/d3d12/GlintTextureReadbackD3D12.cpp'
text = adapter_source.read_text(encoding='utf-8-sig')
begin = text.index('class NativeGlintByteReadbackSnapshot final')
adapter = text[begin:text.index('\n}  // namespace',begin)]
wire_source = staging / 'gpu/command_buffer/service/glint_webgpu_wire_filter.cc'
text = wire_source.read_text(encoding='utf-8-sig')
begin = text.index('using dawn::wire::BufferReadbackDisposition;')
wire = text[begin:text.index('class NativeReadbackFilterFactory final',begin)]
if (hashlib.sha256(adapter.encode()).hexdigest() != record['byte_adapter_sha256']
        or hashlib.sha256(wire.encode()).hexdigest() != record['wire_filter_sha256']):
    parser.error('Extracted snapshot adapter/filter differs')
template = ROOT / 'bridge-template.h'
if sha(template) != record['bridge_template_sha256']:
    parser.error('Measured bridge template differs')
bridge = template.read_text(encoding='utf-8-sig')
if bridge.count('/* GLINT_BYTE_ADAPTER */') != 1 or bridge.count('/* GLINT_WIRE_FILTER */') != 1:
    parser.error('Expected exactly one insertion per extracted component')
bridge = bridge.replace('/* GLINT_BYTE_ADAPTER */',adapter).replace('/* GLINT_WIRE_FILTER */',wire)
generated = staging / 'bridge_extracts.h'
generated.write_text(bridge,encoding='utf-8',newline='\n')
if sha(generated) != record['generated_bridge_sha256']:
    parser.error('Generated adapter/filter bridge differs')
inputs.update({p:sha(p) for p in (extra_patch,template,adapter_source,wire_source,generated)})
native = staging / 'third_party/dawn/src/dawn/native/d3d12/BindGroupD3D12.cpp'
if sha(native) != record['extracted_descriptor_source_sha256']:
    parser.error('Descriptor native source differs')
code = native.read_text(encoding='utf-8-sig')
start = code.index('ResultOrError<bool> BindGroup::PopulateGlintViews(')
end = code.index('\nD3D12_GPU_DESCRIPTOR_HANDLE BindGroup::GetBaseViewDescriptor()', start)
method = staging / 'native_method.inc'
method.write_text(code[start:end], encoding='utf-8', newline='\n')
if sha(method) != record['extracted_descriptor_method_sha256']:
    parser.error('Source-extracted descriptor method differs')
MATH = staging / 'gpu/command_buffer/common/glint'
capture = staging / 'third_party/dawn/src/dawn/native/d3d12/glint'
for name in ('texture_capture.h','texture_capture.cc'):
    shutil.copyfile(capture / name, staging / name)
shadow_record_path = ENV / 'webgpu-shadow-texture-observations.json'
shadow_record = json.loads(shadow_record_path.read_bytes())
for name in ('projected_texture.h','projected_texture.cc','texture_consumer.hlsl'):
    if sha(HELPER / name) != shadow_record['sources_sha256'][name]:
        parser.error('Shared shadow resource helper differs')
edge_shader = ROOT.parent / 'webgpu-edge-compute/edge_compute.hlsl'
if sha(edge_shader) != shadow_record['edge_shader_sha256']:
    parser.error('Measured edge kernel differs')
inputs.update({p:sha(p) for p in (*packets, record_path, shadow_record_path, base_test,
    fixture_patch, HELPER / 'projected_texture.h', HELPER / 'projected_texture.cc',
    HELPER / 'texture_consumer.hlsl', edge_shader,
    RASTER / 'descriptor_fixture.h', *(p for p in staging.rglob('*') if p.is_file()))})
report.update(suite=args.suite, native_dawn_types_mocked=args.suite == 'hardware', source_extracted_descriptor_method=True,
              actual_native_dawn_dispatch_executed=False, actual_native_state_tracker_executed=False)
NATIVE = staging
extra_sources = [NATIVE / 'gpu/command_buffer/common/glint' / (name+'.cc') for name in (
    'webgpu_readback_layout','webgpu_readback_provenance','webgpu_readback_snapshot')]
extra_sources += [NATIVE / path for path in ('gpu/command_buffer/common/glint_webgpu_device_policy.cc',
    'gpu/command_buffer/service/glint_webgpu_readback_observer.cc')]
tests = {
    'controller': (ROOT / 'controller_test.cc','controller_test_sha256'),
    'core': (ROOT / 'core_test.cc','core_test_sha256'),
    'legacy': (ROOT.parent / 'webgpu-render-ranges/render_ranges_test.cc','legacy_test_sha256'),
    'texture-compat': (ROOT.parent / 'webgpu-d3d12-capture/capture_test.cc','texture_test_sha256'),
}
if args.suite != 'hardware':
    test,expected = tests[args.suite]
    if sha(test) != record[expected]: parser.error('Measured standalone CPU/compatibility fixture differs')
    inputs[test] = sha(test)
    shutil.copyfile(test,staging / 'selected_test.cc')
    inputs[staging / 'selected_test.cc'] = sha(staging / 'selected_test.cc')
LIBS = [CHROMIUM / 'out/CamouFlowNative/obj/third_party/boringssl' / n for n in ('boringssl.lib', 'boringssl_asm.lib')]
LIBS.append(CHROMIUM / 'out/CamouFlowNative/obj/buildtools/third_party/libc++/libc++/verbose_abort.obj')
inputs.update({p:sha(p) for p in (MATH/'canvas_readback_candidate.cc', MATH/'canvas_readback_candidate.h', *LIBS, Path('C:/Windows/System32/d3dcompiler_47.dll'))})
report['source_sha256'] = {str(path): value for path, value in inputs.items()}
try:
    for mode in ('none', 'address'):
        output = OUT / mode
        output.mkdir()
        command = [str(compiler), '/nologo', '/std:c++20', '/W4', '/WX', '/EHsc', '/MT', '/Od', '/Z7',
            '/DNOMINMAX', '/DWIN32_LEAN_AND_MEAN', '/winsysroot:' + str(SDK),
            '/imsvc' + str(SDK / 'VC/Tools/MSVC/14.51.36231/include'),
            '/imsvc' + str(SDK / 'Windows Kits/10/Include/10.0.28000.0/ucrt'),
            '/imsvc' + str(SDK / 'Windows Kits/10/Include/10.0.28000.0/shared'),
            '/imsvc' + str(SDK / 'Windows Kits/10/Include/10.0.28000.0/um'),
            '/imsvc' + str(SDK / 'Windows Kits/10/Include/10.0.28000.0/winrt')]
        command.extend(['/I' + str(ROOT), '/I' + str(RASTER), '/I' + str(NATIVE / 'third_party/dawn/include'), '/I' + str(CHROMIUM / 'third_party/dawn/include'), '/I' + str(CHROMIUM / 'out/CamouFlowNative/gen/third_party/dawn/include'), '/I' + str(CHROMIUM / 'out/CamouFlowNative/gen'), '/I' + str(HELPER), '/I' + str(MATH.parents[3]), '/I' + str(CHROMIUM), '/I' + str(CHROMIUM / 'third_party/boringssl/src/include')])
        if mode == 'address':
            command.append('/fsanitize=address')
        sources = [MATH / 'canvas_readback_candidate.cc', *extra_sources]
        sources += [HELPER / 'projected_texture.cc', staging / 'texture_capture.cc', staging / 'shadow_test.cc'] if args.suite == 'hardware' else [staging / 'selected_test.cc']
        if args.suite == 'texture-compat': sources.append(staging / 'texture_capture.cc')
        command.extend([*(str(path) for path in sources),
            '/Fo' + str(output) + '/', '/Fe' + str(output / 'check.exe'), '-fuse-ld=lld', '/link',
            '/LIBPATH:' + str(SDK / 'VC/Tools/MSVC/14.51.36231/lib/x64'),
            '/LIBPATH:' + str(SDK / 'Windows Kits/10/Lib/10.0.28000.0/ucrt/x64'),
            '/LIBPATH:' + str(SDK / 'Windows Kits/10/Lib/10.0.28000.0/um/x64'),
            'd3d12.lib', 'dxgi.lib', 'dxguid.lib', 'd3dcompiler.lib', *(str(p) for p in LIBS), 'bcrypt.lib', 'advapi32.lib'])
        shutil.copyfile(RASTER / 'raster_consumer.hlsl', output / 'raster_consumer.hlsl')
        with (output / 'compile.log').open('xb') as log:
            result = subprocess.run(command, cwd=output, env=environment,
                stdout=log, stderr=subprocess.STDOUT, check=False)
        row = {'sanitizer': mode, 'compile_returncode': result.returncode}
        report['runs'].append(row)
        if result.returncode:
            raise RuntimeError('Edge compute harness compile failed')
        environment_run = dict(environment)
        if mode == 'address':
            environment_run.update(PATH=str(asan.parent) + os.pathsep + environment.get('PATH', ''),
                ASAN_OPTIONS='halt_on_error=1:abort_on_error=1:exitcode=99')
        arguments = [str(output / 'check.exe')]
        if args.suite == 'hardware': arguments += [str(edge_shader),str(HELPER / 'texture_consumer.hlsl')]
        result = subprocess.run(arguments, cwd=output,
            env=environment_run, capture_output=True, text=True, timeout=180, check=False)
        (output / 'test.log').write_text(result.stdout + result.stderr, encoding='utf-8', newline='\n')
        row['test_returncode'] = result.returncode
        if result.returncode:
            raise RuntimeError('Edge compute check failed')
        row['result'] = json.loads(result.stdout)
        value = row['result']
        valid = value.get('passed') is True
        if args.suite == 'hardware':
            valid &= (value.get('assertions') == 47613 and value.get('hardware_adapter') is True
                      and value.get('cases') == 8 and value.get('raster_cases') == 8
                      and value.get('native_render_pass_cases') == 4
                      and value.get('gpu_controller_filter_prepare_verified') is True
                      and value.get('actual_wire_server_roundtrip_executed') is False
                      and value.get('actual_native_device_queue_executed') is False)
        elif args.suite == 'controller':
            valid &= (value.get('assertions') == 10154 and value.get('scope_cycles') == 2000
                      and value.get('actual_native_gpu_hook_executed') is False)
        elif args.suite == 'core':
            valid &= (value.get('assertions') == 4886 and value.get('oracle_cases') == 1000
                      and value.get('native_controller_eligibility_executed') is False)
        elif args.suite == 'legacy':
            valid &= (value.get('assertions') == 4969123 and value.get('controller_scopes') == 1000
                      and value.get('shader_transformation_implemented') is False)
        else:
            valid &= (value.get('assertions') == 22720 and value.get('cases') == 8
                      and value.get('hardware_adapter') is True)
        if not valid: raise RuntimeError('Missing explicitly requested standalone suite scope')
        print(mode, result.stdout.strip(), flush=True)
    report.update(passed=True, measurement_complete=True, hardware_execution_verified=args.suite in ('hardware','texture-compat'))
except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
    report['error'] = str(error)
finally:
    report['postguards_passed'] = (all(sha(path) == value for path, value in {**inputs, **dependencies}.items())
                                  and all(not path.exists() for path in missing_baseline))
    report['passed'] = report['passed'] and report['postguards_passed']
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
raise SystemExit(0 if report['passed'] else 1)
