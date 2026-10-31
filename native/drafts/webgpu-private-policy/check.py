"""Compile only the isolated private policy codec, never Chromium."""
import argparse
import shutil
import sys
import hashlib
import json
import os
from pathlib import Path
import subprocess

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
environment = dict(os.environ, TMP=str(OUT / 'temp'), TEMP=str(OUT / 'temp'))
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
inputs = {path: sha(path) for path in [*ROOT.glob('*.h'), *ROOT.glob('*.cc'), Path(__file__)]}
compiler, linker = TOOLS / 'clang-cl.exe', TOOLS / 'lld-link.exe'
asan = TOOLS.parent / 'lib/clang/24/lib/windows/clang_rt.asan_dynamic-x86_64.dll'
libs = [CHROMIUM / 'out/CamouFlowNative/obj/third_party/boringssl' / name for name in ('boringssl.lib', 'boringssl_asm.lib')]
libs.append(CHROMIUM / 'out/CamouFlowNative/obj/buildtools/third_party/libc++/libc++/verbose_abort.obj')
dependencies = {path: sha(path) for path in [compiler, linker, asan, *libs]}
report = dict(schema=1, passed=False, measurement_complete=False, runs=[],
    source_sha256={path.name: value for path, value in inputs.items()},
    dependency_sha256={str(path): value for path, value in dependencies.items()},
    scope='Private fixed-size policy codec only; no renderer/GPU transport or protection admission',
    transport_installed=False, privacy_admitted=False, production_admitted=False)
try:
    for mode in ('none', 'address'):
        output = OUT / mode
        output.mkdir()
        command = [str(compiler), '/nologo', '/std:c++20', '/W4', '/WX', '/EHsc', '/MT', '/Zc:__cplusplus', '/Od',
            '/winsysroot:' + str(SDK), '/I' + str(CHROMIUM), '/I' + str(CHROMIUM / 'third_party/boringssl/src/include'),
            '/imsvc' + str(SDK / 'VC/Tools/MSVC/14.51.36231/include'),
            '/imsvc' + str(SDK / 'Windows Kits/10/Include/10.0.28000.0/ucrt'),
            '/imsvc' + str(SDK / 'Windows Kits/10/Include/10.0.28000.0/shared'),
            '/imsvc' + str(SDK / 'Windows Kits/10/Include/10.0.28000.0/um')]
        if mode == 'address': command.append('/fsanitize=address')
        command.extend([str(ROOT / 'glint_webgpu_device_policy.cc'), str(ROOT / 'policy_test.cc'),
            '/Fo' + str(output) + '/', '/Fe' + str(output / 'check.exe'), '-fuse-ld=lld', '/link',
            '/LIBPATH:' + str(SDK / 'VC/Tools/MSVC/14.51.36231/lib/x64'),
            '/LIBPATH:' + str(SDK / 'Windows Kits/10/Lib/10.0.28000.0/ucrt/x64'),
            '/LIBPATH:' + str(SDK / 'Windows Kits/10/Lib/10.0.28000.0/um/x64'),
            *(str(path) for path in libs), 'bcrypt.lib', 'advapi32.lib'])
        with (output / 'compile.log').open('xb') as log:
            compile_result = subprocess.run(command, cwd=output, env=environment, stdout=log, stderr=subprocess.STDOUT)
        row = dict(mode=mode, compile_returncode=compile_result.returncode)
        report['runs'].append(row)
        if compile_result.returncode: raise ValueError('Codec compile failed')
        env = dict(environment)
        if mode == 'address':
            env.update(PATH=str(asan.parent) + os.pathsep + env.get('PATH', ''), ASAN_OPTIONS='halt_on_error=1:abort_on_error=1:exitcode=99')
        result = subprocess.run([str(output / 'check.exe')], cwd=output, env=env, capture_output=True, text=True)
        (output / 'test.log').write_text(result.stdout + result.stderr, encoding='utf-8', newline='\n')
        row['test_returncode'] = result.returncode
        if result.returncode: raise ValueError('Codec check failed')
        row['result'] = json.loads(result.stdout)
        print(mode, result.stdout.strip(), flush=True)
    report.update(passed=True, measurement_complete=True)
except Exception as error:
    report['error'] = str(error)
finally:
    report['postguards_passed'] = all(sha(path) == value for path, value in {**inputs, **dependencies}.items())
    report['passed'] = report['passed'] and report['postguards_passed']
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
raise SystemExit(0 if report['passed'] else 1)
