"""Exercise budgeted GPU shadow textures and typed shader consumption without Dawn/browser integration."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--chromium-root', type=Path, required=True)
parser.add_argument('--sdk-root', type=Path, required=True)
parser.add_argument('--work-dir', type=Path, required=True)
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
inputs = {path: sha(path) for path in [*ROOT.glob('*.hlsl'), *ROOT.glob('*.cc'), *ROOT.glob('*.h'), Path(__file__)]}
dependencies = {path: sha(path) for path in (compiler, linker, asan, *(SDK / 'Windows Kits/10/Lib/10.0.28000.0/um/x64' / name for name in ('d3d12.lib', 'dxgi.lib', 'dxguid.lib', 'd3dcompiler.lib')))}
report = {'schema': 1, 'passed': False, 'measurement_complete': False, 'runs': [],
    'source_sha256': {path.name: value for path, value in inputs.items()},
    'dependency_sha256': {str(path): value for path, value in dependencies.items()},
    'scope': __doc__, 'browser_integrated': False, 'native_shader_input_routing_installed': False,
    'hardware_execution_verified': False, 'privacy_admitted': False, 'production_admitted': False}
environment = dict(os.environ, TMP=str(OUT / 'temp'), TEMP=str(OUT / 'temp'))
REPO = ROOT.parents[2]
ENV = REPO / 'native/drafts/environment'
record_path = ENV / 'shared-gpu-readback-core-preparation.json'
record = json.loads(record_path.read_bytes())
packet = ENV / record['patch']
if sha(packet) != record['patch_sha256']:
    parser.error('Shared CPU math packet differs')
staging = OUT / 'sources'
staging.mkdir()
subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error',
    '--include=gpu/command_buffer/common/glint/canvas_readback_candidate.*', str(packet)],
    cwd=staging, check=True, capture_output=True)
MATH = staging / 'gpu/command_buffer/common/glint'

observation_path = ENV / 'webgpu-shadow-texture-observations.json'
observation = json.loads(observation_path.read_bytes())
capture = ROOT.parent / 'webgpu-d3d12-capture'
for name, expected in observation['capture_base_sha256'].items():
    if sha(capture / name) != expected:
        parser.error('Capture budget base differs')
    shutil.copyfile(capture / name, staging / name)
budget_patch = ROOT / 'capture-budget-shadow-friends.patch'
if sha(budget_patch) != observation['budget_patch_sha256']:
    parser.error('Budget friendship extension differs')
subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error', str(budget_patch)],
               cwd=staging, check=True, capture_output=True)
if sha(staging / 'texture_capture.h') != observation['staged_capture_header_sha256']:
    parser.error('Staged capture budget header differs')
edge_shader = ROOT.parent / 'webgpu-edge-compute/edge_compute.hlsl'
if sha(edge_shader) != observation['edge_shader_sha256']:
    parser.error('Measured edge kernel differs')
inputs.update({p: sha(p) for p in (observation_path, budget_patch, edge_shader,
    capture / 'texture_capture.h', capture / 'texture_capture.cc',
    staging / 'texture_capture.h', staging / 'texture_capture.cc')})

for row in record['sources']:
    if (row['source'].startswith('gpu/command_buffer/common/glint/canvas_readback_candidate.')
            and sha(staging / row['source']) != row['after_sha256']):
        parser.error('Extracted CPU math differs')
inputs.update({p: sha(p) for p in (packet, record_path)})
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
        command.extend(['/I' + str(MATH.parents[3]), '/I' + str(CHROMIUM), '/I' + str(CHROMIUM / 'third_party/boringssl/src/include')])
        if mode == 'address':
            command.append('/fsanitize=address')
        command.extend([str(MATH / 'canvas_readback_candidate.cc'), str(ROOT / 'projected_texture.cc'), str(staging / 'texture_capture.cc'), str(ROOT / 'shadow_test.cc'),
            '/Fo' + str(output) + '/', '/Fe' + str(output / 'check.exe'), '-fuse-ld=lld', '/link',
            '/LIBPATH:' + str(SDK / 'VC/Tools/MSVC/14.51.36231/lib/x64'),
            '/LIBPATH:' + str(SDK / 'Windows Kits/10/Lib/10.0.28000.0/ucrt/x64'),
            '/LIBPATH:' + str(SDK / 'Windows Kits/10/Lib/10.0.28000.0/um/x64'),
            'd3d12.lib', 'dxgi.lib', 'dxguid.lib', 'd3dcompiler.lib', *(str(p) for p in LIBS), 'bcrypt.lib', 'advapi32.lib'])
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
        result = subprocess.run([str(output / 'check.exe'), str(edge_shader), str(ROOT / 'texture_consumer.hlsl')], cwd=output,
            env=environment_run, capture_output=True, text=True, timeout=180, check=False)
        (output / 'test.log').write_text(result.stdout + result.stderr, encoding='utf-8', newline='\n')
        row['test_returncode'] = result.returncode
        if result.returncode:
            raise RuntimeError('Edge compute check failed')
        row['result'] = json.loads(result.stdout)
        if not row['result']['passed'] or not row['result']['hardware_adapter']:
            raise RuntimeError('Requested compile/hardware scope was not verified')
        print(mode, result.stdout.strip(), flush=True)
    report.update(passed=True, measurement_complete=True, hardware_execution_verified=True)
except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
    report['error'] = str(error)
finally:
    report['postguards_passed'] = all(sha(path) == value for path, value in {**inputs, **dependencies}.items())
    report['passed'] = report['passed'] and report['postguards_passed']
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
raise SystemExit(0 if report['passed'] else 1)
