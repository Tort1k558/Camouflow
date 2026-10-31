"""Exercise the actual CPU controller using synthetic native tickets, not Dawn runtime."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--chromium-root', type=Path, required=True)
parser.add_argument('--sdk-root', type=Path, required=True)
parser.add_argument('--work-dir', type=Path, required=True)
args = parser.parse_args()
ROOT, SDK, OUT = args.chromium_root, args.sdk_root, args.work_dir
if (sys.platform != 'win32' or any(not p.is_absolute() or p != p.resolve() or p.is_symlink() or p.is_junction() or p.drive.upper() != 'D:' for p in (ROOT, SDK, OUT))
        or not ROOT.is_dir() or not SDK.is_dir() or OUT.exists() or not OUT.parent.is_dir()
        or any(OUT.is_relative_to(p) or p.is_relative_to(OUT) for p in (REPO, ROOT, SDK))):
    parser.error('Use canonical existing D: sources/SDK and fresh external D: output')
if shutil.disk_usage(OUT.parent).free < 1024**3:
    parser.error('At least 1 GiB free on D: is required')
ENV = REPO / 'native/drafts/environment'
record = json.loads((ENV / 'webgpu-readback-controller-preparation.json').read_bytes())
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
for row in record['prerequisites']:
    if digest(ENV / row['patch']) != row['sha256']:
        parser.error('Prerequisite source hash differs')
if digest(ENV / record['patch']) != record['patch_sha256']:
    parser.error('Controller packet hash differs')
OUT.mkdir(exist_ok=False)
(OUT / 'temp').mkdir()
SOURCE = OUT / 'sources'
SOURCE.mkdir()
header = 'third_party/dawn/include/dawn/native/DawnNative.h'
parent = json.loads((ENV / 'webgpu-native-copy-hook-preparation.json').read_bytes())
row = next(r for r in parent['sources'] if r['source'] == header)
if digest(ROOT / header) != row['before_sha256']:
    parser.error('Existing Dawn header is not the pinned unselected baseline')
(SOURCE / header).parent.mkdir(parents=True)
shutil.copyfile(ROOT / header, SOURCE / header)
def apply(name, includes):
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error', *('--include=' + p for p in includes), str(ENV / name)], cwd=SOURCE, check=True, capture_output=True)
apply('webgpu-native-copy-hook-next.patch', [header])
apply(record['patch'], [header, 'gpu/command_buffer/service/glint_webgpu_readback_observer.*'])
apply('shared-gpu-readback-core-next.patch', ['gpu/command_buffer/common/glint/*'])
dest = SOURCE / 'gpu/command_buffer/common/glint'
codec = SOURCE / 'gpu/command_buffer/common'
for p in (REPO / 'native/drafts/webgpu-private-policy').glob('glint_webgpu_device_policy.*'):
    shutil.copyfile(p, codec / p.name)
test = Path(__file__).with_name('controller_test.cc')
if digest(test) != record['test_sha256']:
    parser.error('Controller test source hash differs')
shutil.copyfile(test, SOURCE / 'controller_test.cc')
for row in record['sources']:
    path = SOURCE / row['source']
    if path.exists() and digest(path) != row['staged_sha256']:
        parser.error('Extracted controller source differs')
for relative, expected in record['cpu_sources_sha256'].items():
    if digest(SOURCE / relative) != expected:
        parser.error('Measured CPU source differs: ' + relative)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
inputs = {str(p): sha(p) for p in SOURCE.rglob('*') if p.is_file() and p.suffix in ('.h', '.cc')}
inputs[str(Path(__file__))] = sha(Path(__file__))
tools = ROOT / 'third_party/llvm-build/Release+Asserts'
compiler = tools / 'bin/clang-cl.exe'
asan = tools / 'lib/clang/24/lib/windows/clang_rt.asan_dynamic-x86_64.dll'
libs = [ROOT / 'out/CamouFlowNative/obj/third_party/boringssl' / n for n in ('boringssl.lib', 'boringssl_asm.lib')]
libs.append(ROOT / 'out/CamouFlowNative/obj/buildtools/third_party/libc++/libc++/verbose_abort.obj')
inputs.update({str(p): sha(p) for p in (compiler, asan, *libs)})
report = {'passed': False, 'runs': [],
          'scope': 'CPU controller, synthetic native tickets and opaque handles only',
          'browser_integrated': False, 'privacy_admitted': False, 'source_sha256': inputs}
common = [str(compiler), '/nologo', '/std:c++20', '/W4', '/WX', '/EHsc', '/MT', '/Od', '/Z7',
          '/I' + str(SOURCE), '/I' + str(SOURCE / 'third_party/dawn/include'),
          '/I' + str(ROOT / 'third_party/dawn/include'),
          '/I' + str(ROOT / 'out/CamouFlowNative/gen/third_party/dawn/include'),
          '/I' + str(ROOT), '/I' + str(ROOT / 'third_party/boringssl/src/include'),
          '/winsysroot:' + str(SDK)]
for p in (SDK / 'VC/Tools/MSVC/14.51.36231/include', *(SDK / 'Windows Kits/10/Include/10.0.28000.0' / k for k in ('ucrt', 'shared', 'um'))):
    common.append('/imsvc' + str(p))
sources = [dest / (n + '.cc') for n in ('canvas_readback_candidate', 'webgpu_readback_layout', 'webgpu_readback_provenance', 'webgpu_readback_snapshot')]
sources += [codec / 'glint_webgpu_device_policy.cc', SOURCE / 'gpu/command_buffer/service/glint_webgpu_readback_observer.cc', SOURCE / 'controller_test.cc']
env = {**os.environ, 'TEMP': str(OUT / 'temp'), 'TMP': str(OUT / 'temp')}
try:
    for mode in ('none', 'address'):
        directory = OUT / mode
        directory.mkdir()
        if mode == 'address': shutil.copyfile(asan, directory / asan.name)
        command = common + (['/fsanitize=address'] if mode == 'address' else []) + [str(p) for p in sources]
        command += ['/Fe' + str(directory / 'check.exe'), '-fuse-ld=lld', '/link']
        command += ['/LIBPATH:' + str(p) for p in (SDK / 'VC/Tools/MSVC/14.51.36231/lib/x64', SDK / 'Windows Kits/10/Lib/10.0.28000.0/ucrt/x64', SDK / 'Windows Kits/10/Lib/10.0.28000.0/um/x64')]
        command += [*(str(p) for p in libs), 'bcrypt.lib', 'advapi32.lib']
        with (directory / 'compile.log').open('xb') as log:
            result = subprocess.run(command, cwd=directory, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
        row = {'sanitizer': mode, 'compile_returncode': result.returncode}
        report['runs'].append(row)
        if result.returncode: raise RuntimeError('Compile failed: ' + str(directory))
        result = subprocess.run([str(directory / 'check.exe')], cwd=directory, env={**env, 'ASAN_OPTIONS': 'halt_on_error=1:abort_on_error=1:exitcode=99'}, capture_output=True, text=True, timeout=180, check=False)
        (directory / 'test.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        row['test_returncode'] = result.returncode
        if result.returncode: raise RuntimeError('Test failed: ' + str(directory))
        row['result'] = json.loads(result.stdout)
        assert row['result']['passed']
        print(mode, result.stdout, flush=True)
    report['passed'] = True
except (OSError, ValueError, RuntimeError, AssertionError, subprocess.SubprocessError) as e:
    report['error'] = str(e)
finally:
    report['postguards_passed'] = all(sha(Path(p)) == v for p,v in inputs.items())
    report['passed'] &= report['postguards_passed']
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
raise SystemExit(0 if report['passed'] else 1)
