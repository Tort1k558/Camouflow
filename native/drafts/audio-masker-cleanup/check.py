"""Standalone Windows Audio-masker cleanup checks; never modify the source checkout."""

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[2]
RELATIVE = Path('third_party/blink/renderer/modules/webaudio/glint')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def reference_outputs():
    inputs = [0, 0x80000000, 1, 0x807fffff, 0x7f800000, 0xff800000, 0x7fc00123,
              0x3f800000, 0xbf800000, 0x40800000, 0xc0800000, 0x3e800000, 0xbe800000]
    inputs.extend((0x3e800000 + index * 2) | (0x80000000 if index & 1 else 0) for index in range(4096))
    result = bytearray()
    for selected in (0, 27, 233):
        for value in inputs:
            magnitude = value & 0x7fffffff
            exponent = magnitude & 0x7f800000
            if exponent not in (0, 0x7f800000) and magnitude < 0x3f800000:
                normalized = value & ~1
                digest = hmac.digest(bytes([selected]) * 32,
                                     b'glint.audio.offline.f32.candidate.v1' + normalized.to_bytes(4, 'big'), 'sha256')
                value = normalized | (digest[0] & 1)
            result += struct.pack('<I', value)
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    args = parser.parse_args()
    workspace, output = args.workspace, args.work_dir
    if (os.name != 'nt' or any(not path.is_absolute() or path != path.resolve() or path.drive.upper() != 'D:'
                              for path in (workspace, output)) or not workspace.is_dir()
            or output.exists() or not output.parent.is_dir() or output.is_relative_to(ROOT)
            or output.is_relative_to(workspace)):
        parser.error('Use an existing canonical Windows D: workspace and fresh external D: work directory')
    if shutil.disk_usage(output.parent).free < 1024**3:
        parser.error('Standalone checks require at least 1 GiB free; full-browser build reserve is unchanged')
    sys.path.insert(0, str(ROOT))
    from scripts import native_build as build
    from scripts.verify_native_privacy_units import require_idle_builder

    source = workspace / 'chromium/src'
    candidate = build.load_candidate('upstream-156-webgpu-r7')
    record = json.loads((PACKET / 'packet.json').read_bytes())
    if record['base_manifest_sha256'] != candidate['manifest_sha256']:
        raise ValueError('R7 recipe changed')
    required = {str(RELATIVE / name).replace('\\', '/') for name in (
        'offline_audio_candidate.h', 'offline_audio_candidate.cc', 'offline_audio_candidate_unittest.cc')}
    if set(record['source_sha256']) != required:
        raise ValueError('Unexpected patch input paths')
    inputs = {PACKET / 'packet.json': sha(PACKET / 'packet.json')}
    for name, expected in record['artifacts_sha256'].items():
        path = PACKET / name
        if path.parent != PACKET or path != path.resolve() or sha(path) != expected:
            raise ValueError('Packet artifact changed: ' + name)
        inputs[path] = expected
    for name, expected in record['source_sha256'].items():
        path = source / name
        if path != path.resolve() or sha(path) != expected['before']:
            raise ValueError('Pinned R7 source changed: ' + name)
        inputs[path] = expected['before']
    for name, expected in record['dependency_sha256'].items():
        path = source / name
        if path != path.resolve() or not path.is_relative_to(source) or sha(path) != expected:
            raise ValueError('Pinned Audio dependency changed: ' + name)
        inputs[path] = expected
    compiler = source / 'third_party/llvm-build/Release+Asserts/bin/clang-cl.exe'
    crypto = source / 'out/CamouFlowNative/obj/third_party/boringssl/boringssl.lib'
    assembly = crypto.with_name('boringssl_asm.lib')
    abort_handler = source / 'out/CamouFlowNative/obj/buildtools/third_party/libc++/libc++/verbose_abort.obj'
    asan = compiler.parent.parent / 'lib/clang/24/lib/windows/clang_rt.asan_dynamic-x86_64.dll'
    for path in (compiler, crypto, assembly, abort_handler, asan):
        if path != path.resolve() or not path.is_file():
            raise ValueError('Required existing tool/object missing: ' + str(path))
        inputs[path] = sha(path)
    sdk = workspace / 'toolchain/local-msvc-sdk-28000-v1'
    msvc = sdk / 'VC/Tools/MSVC/14.51.36231'
    kits = sdk / 'Windows Kits/10'
    includes = [msvc / 'include', *[kits / 'Include/10.0.28000.0' / name for name in ('ucrt', 'shared', 'um', 'winrt')]]
    libraries = [msvc / 'lib/x64', *[kits / 'Lib/10.0.28000.0' / name / 'x64' for name in ('ucrt', 'um')]]
    if any(not path.is_dir() for path in [*includes, *libraries]):
        raise ValueError('Pinned local SDK layout is unavailable')
    output.mkdir()
    report = dict(schema=1, passed=False, selected=False, native_sources_modified=False,
                  compiled_browser=False, legacy_audio_repaired=False, production_admitted=False, runs=[])

    def run(command, directory, name, env):
        with (directory / (name + '.log')).open('xb') as log:
            result = subprocess.run(command, cwd=directory, env=env, stdout=log, stderr=subprocess.STDOUT,
                                    creationflags=subprocess.CREATE_NO_WINDOW, timeout=180, check=False)
        if result.returncode:
            raise RuntimeError(name + ' failed; inspect preserved log')
        return (directory / (name + '.log')).read_text(encoding='utf-8-sig')

    try:
        with build.workspace_lock(workspace):
            require_idle_builder(workspace)
            build.candidate_workspace(workspace, candidate)
            env = build.environment(workspace, local_toolchain=True)
            env.update(INCLUDE=os.pathsep.join(map(str, includes)), LIB=os.pathsep.join(map(str, libraries)),
                       TEMP=str(output), TMP=str(output), ASAN_OPTIONS='halt_on_error=1:abort_on_error=1')
            views = {}
            for label in ('before', 'after'):
                view = output / label
                view.mkdir()
                for name in record['source_sha256']:
                    target = view / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source / name, target)
                views[label] = view
            patch = PACKET / 'next.patch'
            run(['git', '-c', 'core.autocrlf=false', 'apply', '--check', str(patch)], views['after'], 'apply-check', env)
            run(['git', '-c', 'core.autocrlf=false', 'apply', str(patch)], views['after'], 'apply', env)
            if any(sha(views['after'] / name) != row['after'] for name, row in record['source_sha256'].items()):
                raise ValueError('Patched source does not match packet')
            for mode in ('real', 'asan', 'fault'):
                for label, view in views.items():
                    directory = output / (mode + '-' + label)
                    directory.mkdir()
                    implementation = view / RELATIVE / 'offline_audio_candidate.cc'
                    executable = directory / 'check.exe'
                    driver = PACKET / ('fault_driver.cc' if mode == 'fault' else 'driver.cc')
                    command = [str(compiler), '/nologo', '/std:c++20', '/EHsc', '/MD', '/O2', '-fuse-ld=lld',
                               '/I' + str(implementation.parent), '/I' + str(source),
                               '/I' + str(source / 'third_party/boringssl/src/include'), str(driver), str(implementation)]
                    if mode != 'fault':
                        command += [str(crypto), str(assembly), str(abort_handler)]
                    if mode == 'asan':
                        command.append('/fsanitize=address')
                        shutil.copyfile(asan, directory / asan.name)
                        if sha(directory / asan.name) != inputs[asan]:
                            raise ValueError('ASan runtime copy changed')
                    command += ['/Fe:' + str(executable), '/link', '/INCREMENTAL:NO', 'advapi32.lib', 'bcrypt.lib', 'ws2_32.lib']
                    run(command, directory, 'compile', env)
                    observed = json.loads(run([str(executable), str(directory / 'outputs.bin')], directory, 'run', env))
                    if mode == 'fault':
                        if (observed['injected_hmac_failures'] != 4 or not observed['failed_calls_not_cached']
                                or observed['digest_cleanses'] != (4 if label == 'after' else 0)
                                or observed['destroyed_storage_cleansed'] != (2 if label == 'after' else 0)):
                            raise ValueError('Fault cleanup expectations failed')
                    elif (observed['storage_cleansed'] != (label == 'after')
                          or (directory / 'outputs.bin').read_bytes() != reference_outputs()):
                        raise ValueError('Exact HMAC output or owned cleanup expectations failed')
                    report['runs'].append(dict(mode=mode, label=label, observed=observed,
                                               executable_sha256=sha(executable)))
            tests = views['after'] / RELATIVE / 'offline_audio_candidate_unittest.cc'
            command = [str(compiler), '/nologo', '/std:c++20', '/EHsc', '/MD', '-fsyntax-only',
                       '/I' + str(tests.parent), '/I' + str(source / RELATIVE), '/I' + str(source),
                       '/I' + str(source / 'out/CamouFlowNative/gen'),
                       '/I' + str(source / 'third_party/googletest/src/googletest/include'), str(tests)]
            run(command, output, 'gtest-syntax', env)
            run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', str(patch)], views['after'], 'reverse', env)
            report['reverse_restored'] = all(sha(views['after'] / name) == row['before'] for name, row in record['source_sha256'].items())
            report.update(passed=report['reverse_restored'], native_gtest_syntax_passed=True, native_gtest_executed=False,
                          asan_scope='helper/driver only; prebuilt crypto dependencies not rebuilt',
                          local_toolchain_sha256=env['GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256'])
    except BaseException as error:
        report.update(passed=False, error_type=type(error).__name__, error=str(error))
        raise
    finally:
        report['input_postguards_passed'] = all(path.is_file() and sha(path) == value for path, value in inputs.items())
        report['passed'] = report['passed'] and report['input_postguards_passed']
        report['input_sha256'] = {str(path): value for path, value in inputs.items()}
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'passed': report['passed'], 'report': str(output / 'report.json')}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
