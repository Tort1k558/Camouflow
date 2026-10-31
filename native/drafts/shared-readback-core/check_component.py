"""Exercise real DLL exports/imports, not Chromium GN/component linkage."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[3]
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
        or any(OUT.is_relative_to(path) or path.is_relative_to(OUT) for path in (REPO, CHROMIUM, SDK))):
    parser.error('Use canonical existing Windows D: sources/SDK and a fresh external D: output')
if shutil.disk_usage(OUT.parent).free < 1024**3:
    parser.error('Isolated component checks require at least 1 GiB free on D:')
ENV = REPO / 'native/drafts/environment'
RECORD = ENV / 'shared-gpu-readback-core-preparation.json'
record = json.loads(RECORD.read_bytes())
PATCH = ENV / record['patch']
if hashlib.sha256(PATCH.read_bytes()).hexdigest() != record['patch_sha256']:
    parser.error('Shared source packet hash differs')
OUT.mkdir(exist_ok=False)
staging = OUT / 'sources'
staging.mkdir()
subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error',
    '--include=gpu/command_buffer/common/glint/*', str(PATCH)], cwd=staging, check=True)
SOURCE = staging / 'gpu/command_buffer/common/glint'
for row in record['sources']:
    if row['source'].startswith('gpu/command_buffer/common/glint/'):
        if hashlib.sha256((staging / row['source']).read_bytes()).hexdigest() != row['after_sha256']:
            parser.error('Extracted shared source hash differs')
for relative, expected in record['measured_test_sources_sha256'].items():
    path = REPO / relative
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        parser.error('Measured component test source hash differs')
    shutil.copyfile(path, SOURCE / path.name)
TOOLS = CHROMIUM / 'third_party/llvm-build/Release+Asserts'
COMPILER = TOOLS / 'bin/clang-cl.exe'
ASAN = TOOLS / 'lib/clang/24/lib/windows/clang_rt.asan_dynamic-x86_64.dll'
LIBS = [CHROMIUM / 'out/CamouFlowNative/obj/third_party/boringssl' / name
        for name in ('boringssl.lib', 'boringssl_asm.lib')]
LIBS.append(CHROMIUM / 'out/CamouFlowNative/obj/buildtools/third_party/libc++/libc++/verbose_abort.obj')
(OUT / 'temp').mkdir()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
files = [PATCH, RECORD, *(REPO / relative for relative in record['measured_test_sources_sha256']), *SOURCE.glob('*.cc'), *SOURCE.glob('*.h'), COMPILER, TOOLS / 'bin/lld-link.exe',
         ASAN, *LIBS, Path(__file__),
         CHROMIUM / 'gpu/command_buffer/common/gpu_command_buffer_common_export.h']
before = {str(path): sha(path) for path in files}
report = dict(passed=False, measurement_complete=False, inputs_sha256=before, runs=[],
    scope=__doc__, gn_generated=False, chromium_component_link_verified=False,
    browser_integrated=False, privacy_admitted=False, production_admitted=False)
environment = {**os.environ, 'TEMP': str(OUT / 'temp'), 'TMP': str(OUT / 'temp')}
common = [str(COMPILER), '/nologo', '/std:c++20', '/W4', '/WX', '/EHsc', '/MD', '/Od', '/Z7',
    '/DCOMPONENT_BUILD', '/DWIN32', '/I' + str(SOURCE), '/I' + str(CHROMIUM),
    '/I' + str(CHROMIUM / 'third_party/boringssl/src/include'), '/winsysroot:' + str(SDK)]
for path in (SDK / 'VC/Tools/MSVC/14.51.36231/include', *(
        SDK / 'Windows Kits/10/Include/10.0.28000.0' / kind for kind in ('ucrt', 'shared', 'um'))):
    common.append('/imsvc' + str(path))
link = ['-fuse-ld=lld', '/link', *('/LIBPATH:' + str(path) for path in (
    SDK / 'VC/Tools/MSVC/14.51.36231/lib/x64',
    SDK / 'Windows Kits/10/Lib/10.0.28000.0/ucrt/x64',
    SDK / 'Windows Kits/10/Lib/10.0.28000.0/um/x64'))]


def run(command, directory, name):
    with (directory / (name + '.log')).open('xb') as log:
        result = subprocess.run(command, cwd=directory, env=environment, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'{name}: {result.returncode}, see {directory}')


try:
    for sanitizer in ('none', 'address'):
        directory = OUT / sanitizer
        directory.mkdir()
        flags = common + (['/fsanitize=address'] if sanitizer == 'address' else [])
        if sanitizer == 'address':
            shutil.copyfile(ASAN, directory / ASAN.name)
        sources = [SOURCE / (name + '.cc') for name in ('canvas_readback_candidate',
            'webgpu_readback_layout', 'webgpu_readback_provenance', 'webgpu_readback_snapshot')]
        dll = directory / 'shared_core.dll'
        library = directory / 'shared_core.lib'
        run(flags + ['/DGPU_COMMAND_BUFFER_COMMON_IMPLEMENTATION', '/LD', *(str(path) for path in sources),
            '/Fe' + str(dll)] + link + ['/IMPLIB:' + str(library), *(str(path) for path in LIBS),
                'bcrypt.lib', 'advapi32.lib'], directory, 'component-build')
        for name in ('layout', 'provenance', 'snapshot', 'callback', 'uncertain'):
            executable = directory / (name + '.exe')
            run(flags + [str(SOURCE / (name + '_test.cc')), '/Fe' + str(executable)] + link + [str(library)],
                directory, name + '-build')
            result = subprocess.run([str(executable)], cwd=directory, env=environment,
                capture_output=True, text=True)
            (directory / (name + '-run.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
            assert result.returncode == 0, (name, result.stderr)
            value = json.loads(result.stdout)
            assert value['passed']
            report['runs'].append(dict(name=name, sanitizer=sanitizer, result=value,
                dll_sha256=sha(dll), executable_sha256=sha(executable)))
            print(name, sanitizer, value['assertions'], flush=True)
    report.update(passed=True, measurement_complete=True)
except Exception as error:
    report['error'] = str(error)
finally:
    report['postguards_passed'] = all(sha(Path(path)) == value for path, value in before.items())
    report['passed'] = report['passed'] and report['postguards_passed']
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
raise SystemExit(0 if report['passed'] else 1)
