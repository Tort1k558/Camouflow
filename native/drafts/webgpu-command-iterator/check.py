"""Execute real Dawn command storage/pooling in its standalone no-op raw_ptr configuration."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parent
ENV = MODULE.parent / 'environment'
SOURCE_GATE = MODULE.parent / 'webgpu-render-buffer-routing/check.py'
SOURCE_RECORD = ENV / 'webgpu-render-buffer-routing-preparation.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('chromium-root', 'sdk-root', 'work-dir'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    chromium, sdk, out = args.chromium_root, args.sdk_root, args.work_dir
    if (sys.platform != 'win32' or any(not path.is_absolute() or path != path.resolve()
            or path.is_symlink() or path.is_junction() or path.drive.upper() != 'D:'
            for path in (chromium, sdk, out)) or not chromium.is_dir() or not sdk.is_dir()
            or out.exists() or not out.parent.is_dir()
            or any(out.is_relative_to(path) or path.is_relative_to(out)
                   for path in (MODULE, chromium, sdk))):
        parser.error('Use canonical D: checkout/SDK and a fresh external D: output')
    if shutil.disk_usage(out.parent).free < 1024**3:
        parser.error('At least 1 GiB free on D: is required')
    record_path = ENV / 'webgpu-command-iterator-observations.json'
    record = json.loads(record_path.read_bytes())
    fixture = MODULE / 'command_iterator_test.cc'
    expected = [(MODULE / 'check.py', record['checker_sha256']),
                (fixture, record['fixture_sha256']),
                (SOURCE_GATE, record['source_gate_checker_sha256']),
                (SOURCE_RECORD, record['source_gate_record_sha256'])]
    for relative, value in record['pinned_native_files'].items():
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts:
            parser.error('Native input must be checkout-relative')
        expected.append((chromium / path, value))
    if any(not path.is_file() or digest(path) != value for path, value in expected):
        parser.error('Measured native iterator source/dependency differs')
    sources = [fixture, *(chromium / path for path in record['native_translation_units'])]
    pinned = {path for path, _ in expected}
    if any(source not in pinned for source in sources):
        parser.error('Native translation unit is not pinned')
    tools = chromium / 'third_party/llvm-build/Release+Asserts'
    compiler = tools / 'bin/clang-cl.exe'
    linker = tools / 'bin/lld-link.exe'
    asan = tools / 'lib/clang/24/lib/windows/clang_rt.asan_dynamic-x86_64.dll'
    guards = {path: digest(path) for path in (record_path, compiler, linker, asan)}
    guards.update(dict(expected))
    out.mkdir(exist_ok=False)
    report = {
        'passed': False, 'measurement_complete': False, 'runs': [],
        'scope': 'Actual standalone Dawn command iterator/allocator/pool/refcounts; not Chromium BRP or GPU execution',
        'standalone_noop_raw_ptr': True, 'chromium_miracle_ptr_executed': False,
        'actual_native_device_queue_executed': False,
        'actual_native_render_bundle_decoder_executed': False,
        'runtime_verified': False, 'privacy_admitted': False, 'production_admitted': False,
    }
    try:
        gate_out = out / 'source-gate'
        with (out / 'source-gate.log').open('xb') as log:
            gate = subprocess.run([sys.executable, str(SOURCE_GATE), '--chromium-root', str(chromium),
                '--sdk-root', str(sdk), '--work-dir', str(gate_out)],
                stdout=log, stderr=subprocess.STDOUT, timeout=180, check=False)
        if gate.returncode:
            raise RuntimeError('Required render-buffer source gate failed')
        gate_report = json.loads((gate_out / 'report.json').read_bytes())
        if not gate_report['passed'] or not gate_report['postguards_passed']:
            raise RuntimeError('Required render-buffer source gate failed')
        staging = gate_out / 'sources'
        native = chromium / 'third_party/dawn'
        temp = out / 'temp'
        temp.mkdir()
        environment = {**os.environ, 'TMP': str(temp), 'TEMP': str(temp)}
        flags = [str(compiler), '/nologo', '/std:c++20', '/W4', '/WX', '/EHsc', '/MT', '/Od', '/Z7',
                 '/DDAWN_ENABLE_ASSERTS', '/DDAWN_ABORT_ON_ASSERT', '/DNOMINMAX',
                 '/DWIN32_LEAN_AND_MEAN', '/showIncludes', '/winsysroot:' + str(sdk)]
        flags += ['/imsvc' + str(sdk / 'VC/Tools/MSVC/14.51.36231/include')]
        flags += ['/imsvc' + str(sdk / 'Windows Kits/10/Include/10.0.28000.0' / name)
                  for name in ('ucrt', 'shared', 'um')]
        flags += ['/I' + str(path) for path in (staging / 'third_party/dawn', native,
                                              native / 'src/dawn/partition_alloc')]
        link = ['-fuse-ld=lld', '/link', *('/LIBPATH:' + str(path) for path in (
            sdk / 'VC/Tools/MSVC/14.51.36231/lib/x64',
            sdk / 'Windows Kits/10/Lib/10.0.28000.0/ucrt/x64',
            sdk / 'Windows Kits/10/Lib/10.0.28000.0/um/x64'))]
        header = staging / 'third_party/dawn/src/dawn/native/CommandAllocator.h'
        guards[header] = digest(header)
        for mode in ('none', 'address'):
            directory = out / mode
            directory.mkdir()
            command = [*flags, *(['/fsanitize=address'] if mode == 'address' else []),
                       *(str(path) for path in sources), '/Fe' + str(directory / 'check.exe'), *link]
            (directory / 'command.json').write_text(json.dumps(command, indent=2) + '\n', encoding='utf-8')
            with (directory / 'compile.log').open('xb') as log:
                compiled = subprocess.run(command, cwd=directory, env=environment,
                    stdout=log, stderr=subprocess.STDOUT, timeout=180, check=False)
            row = {'sanitizer': mode, 'compile_returncode': compiled.returncode, 'ownership_refusals': []}
            report['runs'].append(row)
            if compiled.returncode:
                raise RuntimeError('Actual native iterator compilation failed')
            include_log = (directory / 'compile.log').read_text(encoding='utf-8-sig').replace('\\', '/').casefold()
            included = (header, native / 'src/dawn/partition_alloc/partition_alloc/pointers/raw_ptr.h')
            if any(path.as_posix().casefold() not in include_log for path in included):
                raise RuntimeError('Expected patched header/official standalone raw_ptr was not included')
            run_env = {**environment, 'PATH': str(asan.parent) + os.pathsep + environment.get('PATH', ''),
                       'ASAN_OPTIONS': 'halt_on_error=1:abort_on_error=1:exitcode=99'}
            run = subprocess.run([str(directory / 'check.exe')], cwd=directory, env=run_env,
                                 capture_output=True, timeout=180, check=False)
            (directory / 'test.log').write_bytes(run.stdout + run.stderr)
            row['test_returncode'] = run.returncode
            if run.returncode:
                raise RuntimeError('Actual native iterator execution failed')
            value = row['result'] = json.loads(run.stdout)
            required = {'passed': True, 'position_cases': 182, 'destroyed': 9284,
                        'bundle_like_cases': 1, 'pool_reuse_cases': 1, 'merged_block_cases': 1,
                        'native_command_iterator_executed': True, 'native_memory_pool_executed': True,
                        'standalone_noop_raw_ptr': True, 'actual_native_device_queue_executed': False}
            if any(value.get(key) != expected for key, expected in required.items()) or value.get('checks', 0) < 1_000_000:
                raise ValueError('Missing actual native iterator/pool/refcount proof')
            for case in ('destroy', 'move'):
                refused = subprocess.run([str(directory / 'check.exe'), case], cwd=directory,
                    env=run_env, capture_output=True, timeout=30, check=False)
                body = refused.stdout + refused.stderr
                (directory / (case + '.log')).write_bytes(body)
                passed = (refused.returncode not in (0, 98, 99)
                          and b'iterator->mBlocks.data() == blocks' in body
                          and b'ERROR: AddressSanitizer' not in body)
                row['ownership_refusals'].append({'case': case, 'returncode': refused.returncode,
                                                  'native_restore_guard_observed': passed, 'passed': passed})
                if not passed:
                    raise RuntimeError('Native storage transfer/destruction was not refused by the restore guard')
            print(mode, json.dumps(value), flush=True)
        report.update(passed=True, measurement_complete=True)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        report['error'] = str(error)
    finally:
        report['input_sha256'] = {str(path): value for path, value in guards.items()}
        report['postguards_passed'] = all(path.is_file() and digest(path) == value for path, value in guards.items())
        report['passed'] = report['passed'] and report['postguards_passed']
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
