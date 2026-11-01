"""Exercise transactional array/mip projection without Dawn/browser admission."""
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
parser.add_argument('--case', choices=('arrays', 'single', 'fastpath', 'atomic-positive', 'atomic-negative'), required=True)
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
inputs = {path: sha(path) for path in [*ROOT.glob('*.hlsl'), *ROOT.glob('*.cc'), *ROOT.glob('*.h'),
                                    *ROOT.glob('*.patch'), Path(__file__)]}
dependencies = {path: sha(path) for path in (compiler, linker, asan, *(SDK / 'Windows Kits/10/Lib/10.0.28000.0/um/x64' / name for name in ('d3d12.lib', 'dxgi.lib', 'dxguid.lib', 'd3dcompiler.lib')))}
report = {'schema': 1, 'passed': False, 'measurement_complete': False, 'runs': [],
    'source_sha256': {path.name: value for path, value in inputs.items()},
    'dependency_sha256': {str(path): value for path, value in dependencies.items()},
    'scope': __doc__, 'browser_integrated': False, 'native_shader_input_routing_installed': False,
    'hardware_execution_verified': False, 'privacy_admitted': False, 'production_admitted': False,
    'case': args.case}
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

capture = REPO / 'native/drafts/webgpu-subresource-capture'
observation_path = capture / 'observations.json'
observation = json.loads(observation_path.read_bytes())
for name in ('texture_capture.h', 'texture_capture.cc'):
    expected = observation['report_source_sha256'][name]
    if sha(capture / name) != expected:
        parser.error('Measured selected-subresource capture differs')
    shutil.copyfile(capture / name, staging / name)
edge_shader = ROOT / 'edge_projection.hlsl'
inputs.update({p: sha(p) for p in (observation_path, edge_shader,
    capture / 'texture_capture.h', capture / 'texture_capture.cc',
    staging / 'texture_capture.h', staging / 'texture_capture.cc')})

CODE = ROOT
if args.case != 'arrays':
    CODE = staging / 'variant'
    CODE.mkdir()
    for name in ('projected_texture.cc', 'projected_texture.h', 'shadow_test.cc', 'texture_consumer.hlsl'):
        shutil.copyfile(ROOT / name, CODE / name)
    if args.case in ('single', 'fastpath'):
        fixture = REPO / ('native/drafts/webgpu-subresource-projection/shadow_test.cc' if args.case == 'single'
                          else 'native/drafts/webgpu-shadow-texture/shadow_test.cc')
        consumer = REPO / 'native/drafts/webgpu-subresource-projection/texture_consumer.hlsl'
        inputs.update({p: sha(p) for p in (fixture, consumer)})
        text = fixture.read_text(encoding='utf-8-sig')
        if args.case == 'fastpath':
            text = text.replace('ProjectedTexture::Record(', 'ProjectedTexture::RecordAll(')
        (CODE / 'shadow_test.cc').write_text(text, encoding='utf-8', newline='\n')
        shutil.copyfile(consumer, CODE / 'texture_consumer.hlsl')
    else:
        library_patch = ROOT / (args.case + '-library.patch')
        for packet_path in (library_patch, ROOT / 'atomic-fixture.patch'):
            subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error', str(packet_path)],
                           cwd=CODE, check=True, capture_output=True)
    inputs.update({p: sha(p) for p in CODE.iterdir() if p.is_file()})

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
    for mode in (('none',) if args.case == 'atomic-negative' else ('none', 'address')):
        output = OUT / mode
        output.mkdir()
        command = [str(compiler), '/nologo', '/std:c++20', '/W4', '/WX', '/EHsc', '/MT', '/Od', '/Z7',
            '/DNOMINMAX', '/DWIN32_LEAN_AND_MEAN', '/winsysroot:' + str(SDK),
            '/imsvc' + str(SDK / 'VC/Tools/MSVC/14.51.36231/include'),
            '/imsvc' + str(SDK / 'Windows Kits/10/Include/10.0.28000.0/ucrt'),
            '/imsvc' + str(SDK / 'Windows Kits/10/Include/10.0.28000.0/shared'),
            '/imsvc' + str(SDK / 'Windows Kits/10/Include/10.0.28000.0/um'),
            '/imsvc' + str(SDK / 'Windows Kits/10/Include/10.0.28000.0/winrt')]
        command.extend(['/I' + str(staging), '/I' + str(MATH.parents[3]), '/I' + str(CHROMIUM), '/I' + str(CHROMIUM / 'third_party/boringssl/src/include')])
        if mode == 'address':
            command.append('/fsanitize=address')
        command.extend([str(MATH / 'canvas_readback_candidate.cc'), str(CODE / 'projected_texture.cc'), str(staging / 'texture_capture.cc'), str(CODE / 'shadow_test.cc'),
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
        result = subprocess.run([str(output / 'check.exe'), str(edge_shader), str(CODE / 'texture_consumer.hlsl')], cwd=output,
            env=environment_run, capture_output=True, text=True, timeout=180, check=False)
        (output / 'test.log').write_text(result.stdout + result.stderr, encoding='utf-8', newline='\n')
        row['test_returncode'] = result.returncode
        if args.case == 'atomic-negative':
            if result.returncode != 23 or result.stdout or result.stderr.strip() != 'PARTIAL_RECORDING_BEFORE_QUOTA_DENIAL':
                raise RuntimeError('The injected partial recording did not trigger the exact pre-submit oracle')
            row['expected_rejection_before_gpu_submit'] = True
            continue
        if result.returncode:
            raise RuntimeError('Edge compute check failed')
        row['result'] = json.loads(result.stdout)
        if not row['result']['passed'] or not row['result']['hardware_adapter']:
            raise RuntimeError('Requested compile/hardware scope was not verified')
        print(mode, result.stdout.strip(), flush=True)
    report.update(passed=True, measurement_complete=True,
                  hardware_execution_verified=args.case != 'atomic-negative')
except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
    report['error'] = str(error)
finally:
    report['postguards_passed'] = all(sha(path) == value for path, value in {**inputs, **dependencies}.items())
    report['passed'] = report['passed'] and report['postguards_passed']
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
raise SystemExit(0 if report['passed'] else 1)
