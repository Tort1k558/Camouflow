"""Check CPU range/error-invalidation callbacks with synthetic handles, not actual native draw/queue failure execution."""
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
parser.add_argument('--suite', choices=('controller', 'queue-controlflow'), default='controller')
args = parser.parse_args()
ROOT, SDK, OUT = args.chromium_root, args.sdk_root, args.work_dir
if (sys.platform != 'win32' or any(not p.is_absolute() or p != p.resolve()
        or p.is_symlink() or p.is_junction() or p.drive.upper() != 'D:' for p in (ROOT, SDK, OUT))
        or not ROOT.is_dir() or not SDK.is_dir() or OUT.exists() or not OUT.parent.is_dir()
        or any(OUT.is_relative_to(p) or p.is_relative_to(OUT) for p in (REPO, ROOT, SDK))):
    parser.error('Use existing canonical D: sources/SDK and fresh external D: output')
if shutil.disk_usage(OUT.parent).free < 1024**3:
    parser.error('At least 1 GiB free on D: is required')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


ENV = REPO / 'native/drafts/environment'
record_path = ENV / 'webgpu-render-ranges-preparation.json'
record = json.loads(record_path.read_bytes())
packets = [*(ENV / row['patch'] for row in record['prerequisites']), ENV / record['patch']]
for row, packet in zip([*record['prerequisites'], {'sha256': record['patch_sha256']}], packets):
    if digest(packet) != row['sha256']:
        parser.error('Public source packet hash differs')
baseline = {}
for row in record['composed_sources']:
    source = ROOT / row['source']
    if row['before_sha256'] is None:
        if source.exists():
            parser.error('Expected unselected baseline without: ' + row['source'])
    else:
        if not source.is_file() or digest(source) != row['before_sha256']:
            parser.error('Pinned source baseline differs: ' + row['source'])
        baseline[row['source']] = source.read_bytes()
OUT.mkdir(exist_ok=False)
(OUT / 'temp').mkdir()
SOURCE = OUT / 'sources'
SOURCE.mkdir()
for relative, data in baseline.items():
    target = SOURCE / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
for packet in packets:
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error', str(packet)],
                   cwd=SOURCE, check=True, capture_output=True)
for row in record['composed_sources']:
    target = SOURCE / row['source']
    if row['after_sha256'] is None:
        valid = not target.exists()
    else:
        valid = target.is_file() and digest(target) == row['after_sha256']
    if not valid:
        parser.error('Composed source differs: ' + row['source'])
additional_inputs = []
test = Path(__file__).with_name('render_ranges_test.cc')
expected_test = record['test_sha256']
if args.suite == 'queue-controlflow':
    observation_path = ENV / 'webgpu-queue-controlflow-observations.json'
    observation = json.loads(observation_path.read_bytes())
    test = Path(__file__).with_name('queue_controlflow_test.cc')
    expected_test = observation['test_sha256']
    native_queue = SOURCE / 'third_party/dawn/src/dawn/native/d3d12/QueueD3D12.cpp'
    error_header = ROOT / 'third_party/dawn/src/dawn/native/Error.h'
    additional_inputs = [observation_path, error_header]
    if (observation['parent_patch_sha256'] != record['patch_sha256']
            or digest(native_queue) != observation['native_queue_source_sha256']
            or digest(error_header) != observation['error_header_sha256']):
        parser.error('Measured queue/macro source differs')
    native_text = native_queue.read_text(encoding='utf-8-sig')
    test_text = test.read_text(encoding='utf-8-sig')
    signatures = ('void NotifyGlintExecutionError(', 'MaybeError Queue::SubmitImpl(',
                  'MaybeError Queue::SubmitPendingCommandsImpl(')
    if len(observation['extracted_functions_sha256']) != len(signatures):
        parser.error('Expected exactly three extracted queue functions')
    for signature, expected in zip(signatures, observation['extracted_functions_sha256'], strict=True):
        start = native_text.index(signature)
        opening = native_text.index('{', start)
        depth, end = 1, opening + 1
        while depth:
            depth += (native_text[end] == '{') - (native_text[end] == '}')
            end += 1
        fragment = native_text[start:end]
        if (hashlib.sha256(fragment.encode('utf-8')).hexdigest() != expected
                or test_text.count(fragment) != 1):
            parser.error('Extracted queue function differs')
    macro_text = error_header.read_text(encoding='utf-8-sig')
    start = macro_text.index('#define DAWN_TRY_WITH_CLEANUP(')
    macro = macro_text[start:macro_text.index('\n\n', start)]
    if (hashlib.sha256(macro.encode('utf-8')).hexdigest() != observation['macro_sha256']
            or test_text.count(macro) != 1):
        parser.error('Extracted cleanup macro differs')
if digest(test) != expected_test:
    parser.error('Measured CPU test differs')
shutil.copyfile(test, SOURCE / test.name)

TOOLS = ROOT / 'third_party/llvm-build/Release+Asserts'
COMPILER = TOOLS / 'bin/clang-cl.exe'
ASAN = TOOLS / 'lib/clang/24/lib/windows/clang_rt.asan_dynamic-x86_64.dll'
LIBS = [ROOT / 'out/CamouFlowNative/obj/third_party/boringssl' / name
        for name in ('boringssl.lib', 'boringssl_asm.lib')]
LIBS.append(ROOT / 'out/CamouFlowNative/obj/buildtools/third_party/libc++/libc++/verbose_abort.obj')
sources = [SOURCE / 'gpu/command_buffer/common/glint' / (name + '.cc') for name in (
    'canvas_readback_candidate', 'webgpu_readback_layout', 'webgpu_readback_provenance',
    'webgpu_readback_snapshot')]
sources += [SOURCE / relative for relative in (
    'gpu/command_buffer/common/glint_webgpu_device_policy.cc',
    'gpu/command_buffer/service/glint_webgpu_readback_observer.cc',
    test.name)]
bound = {str(p): digest(p) for p in (*packets, record_path, Path(__file__), COMPILER, ASAN, *LIBS, *additional_inputs,
    *(p for p in SOURCE.rglob('*') if p.is_file()))}
report = {'passed': False, 'postguards_passed': False, 'runs': [], 'source_sha256': bound,
          'scope': __doc__, 'suite': args.suite, 'native_handles_synthetic': True,
          'backend_mocked': args.suite == 'queue-controlflow', 'native_gpu_queue_executed': False,
          'wire_roundtrip_tests_executed': False, 'runtime_verified': False,
          'privacy_admitted': False, 'production_admitted': False}
environment = {**os.environ, 'TEMP': str(OUT / 'temp'), 'TMP': str(OUT / 'temp')}
flags = [str(COMPILER), '/nologo', '/std:c++20', '/W4', '/WX', '/EHsc', '/MT', '/Od', '/Z7']
flags += ['/I' + str(p) for p in (SOURCE, SOURCE / 'third_party/dawn/include',
    ROOT / 'third_party/dawn/include', ROOT / 'out/CamouFlowNative/gen/third_party/dawn/include',
    ROOT / 'out/CamouFlowNative/gen', ROOT, ROOT / 'third_party/boringssl/src/include')]
flags.append('/winsysroot:' + str(SDK))
flags += ['/imsvc' + str(p) for p in (SDK / 'VC/Tools/MSVC/14.51.36231/include',
    *(SDK / 'Windows Kits/10/Include/10.0.28000.0' / kind for kind in ('ucrt', 'shared', 'um')))]
link = ['-fuse-ld=lld', '/link', *('/LIBPATH:' + str(p) for p in (
    SDK / 'VC/Tools/MSVC/14.51.36231/lib/x64',
    SDK / 'Windows Kits/10/Lib/10.0.28000.0/ucrt/x64',
    SDK / 'Windows Kits/10/Lib/10.0.28000.0/um/x64')), *(str(p) for p in LIBS), 'bcrypt.lib', 'advapi32.lib']
try:
    for sanitizer in ('none', 'address'):
        directory = OUT / sanitizer
        directory.mkdir()
        if sanitizer == 'address':
            shutil.copyfile(ASAN, directory / ASAN.name)
        command = flags + (['/fsanitize=address'] if sanitizer == 'address' else [])
        command += [*(str(p) for p in sources), '/Fe' + str(directory / 'check.exe'), *link]
        with (directory / 'compile.log').open('xb') as log:
            result = subprocess.run(command, cwd=directory, env=environment,
                                    stdout=log, stderr=subprocess.STDOUT, check=False)
        row = {'sanitizer': sanitizer, 'compile_returncode': result.returncode}
        report['runs'].append(row)
        if result.returncode:
            raise RuntimeError('Compile failed: ' + str(directory))
        result = subprocess.run([str(directory / 'check.exe')], cwd=directory,
            env={**environment, 'ASAN_OPTIONS': 'halt_on_error=1:abort_on_error=1:exitcode=99'},
            capture_output=True, text=True, timeout=180, check=False)
        (directory / 'test.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        row['test_returncode'] = result.returncode
        if result.returncode:
            raise RuntimeError('CPU range check failed: ' + str(directory))
        row['result'] = json.loads(result.stdout)
        if args.suite == 'controller':
            valid = (row['result']['passed'] and row['result']['controller_scopes'] == 1000
                     and row['result']['shader_transformation_implemented'] is False)
        else:
            valid = (row['result']['passed'] and row['result']['scenarios'] == 26
                     and row['result']['source_extracted_queue_control_flow_only'] is True
                     and row['result']['backend_mocked'] is True
                     and row['result']['native_gpu_queue_executed'] is False)
        if not valid:
            raise RuntimeError('Missing explicit CPU-only suite scope')
        print(sanitizer, result.stdout.strip(), flush=True)
    report['passed'] = True
except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
    report['error'] = str(error)
finally:
    report['postguards_passed'] = all(digest(Path(path)) == value for path,value in bound.items())
    report['passed'] = report['passed'] and report['postguards_passed']
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
raise SystemExit(0 if report['passed'] else 1)
