"""Compile isolated WebGPU component checks, never Chromium or a privacy gate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium-root', type=Path, required=True)
    parser.add_argument('--sdk-root', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    args = parser.parse_args()
    chromium, sdk, output = args.chromium_root, args.sdk_root, args.work_dir
    if (sys.platform != 'win32' or any(not path.is_absolute() or path != path.resolve()
            or path.is_symlink() or path.is_junction() or path.drive.upper() != 'D:'
            for path in (chromium, sdk, output)) or not chromium.is_dir() or not sdk.is_dir()
            or output.exists() or not output.parent.is_dir()
            or any(output.is_relative_to(path) or path.is_relative_to(output)
                   for path in (ROOT, chromium, sdk))):
        parser.error('Use Windows, canonical existing D: sources/SDK and fresh external D: output')
    if shutil.disk_usage(output.parent).free < 1024**3:
        parser.error('Isolated component checks require at least 1 GiB free on D:')
    tools = chromium / 'third_party/llvm-build/Release+Asserts/bin'
    compiler, linker = tools / 'clang-cl.exe', tools / 'lld-link.exe'
    asan = tools.parent / 'lib/clang/24/lib/windows/clang_rt.asan_dynamic-x86_64.dll'
    candidate = chromium / 'third_party/blink/renderer/core/html/canvas/glint/canvas_readback_candidate.cc'
    libraries = [chromium / 'out/CamouFlowNative/obj/third_party/boringssl' / name
        for name in ('boringssl.lib', 'boringssl_asm.lib')]
    libraries.append(chromium / 'out/CamouFlowNative/obj/buildtools/third_party/libc++/libc++/verbose_abort.obj')
    dependencies = [compiler, linker, asan, candidate, candidate.with_suffix('.h'), *libraries]
    if not all(path.is_file() and path == path.resolve() for path in dependencies):
        parser.error('Pinned compiler, ASan runtime, Canvas source and existing native crypto objects required')
    output.mkdir(exist_ok=False)
    (output / 'temp').mkdir()
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    inputs = {path: digest(path) for path in [*ROOT.glob('*.h'), *ROOT.glob('*.cc'), Path(__file__)]}
    bound = {path: digest(path) for path in dependencies}
    report = dict(schema=1, passed=False, measurement_complete=False, runs=[],
        scope=__doc__, source_sha256={path.name: value for path, value in inputs.items()},
        dependency_sha256={str(path): value for path, value in bound.items()},
        browser_integrated=False, native_queue_hooks_installed=False,
        native_webgpu_readback_protection=False, canvas_gpu_export_mismatch_resolved=False,
        privacy_admitted=False, production_admitted=False)

    def save():
        temporary = output / 'report.tmp'
        temporary.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        temporary.replace(output / 'report.json')

    save()
    try:
        for sanitizer in ('none', 'address'):
            for name in ('layout', 'provenance', 'snapshot', 'callback'):
                directory = output / (name + '-' + sanitizer)
                directory.mkdir()
                sources = [ROOT / 'webgpu_readback_layout.cc', ROOT / (name + '_test.cc')]
                if name in ('provenance', 'snapshot', 'callback'):
                    sources.insert(1, ROOT / 'webgpu_readback_provenance.cc')
                command = [str(compiler), '/nologo', '/std:c++20', '/W4', '/WX', '/EHsc', '/MT',
                    '/Zc:__cplusplus', '/Od', '/Z7', '/winsysroot:' + str(sdk),
                    '/imsvc' + str(sdk / 'VC/Tools/MSVC/14.51.36231/include'),
                    '/imsvc' + str(sdk / 'Windows Kits/10/Include/10.0.28000.0/ucrt'),
                    '/imsvc' + str(sdk / 'Windows Kits/10/Include/10.0.28000.0/shared'),
                    '/imsvc' + str(sdk / 'Windows Kits/10/Include/10.0.28000.0/um')]
                if sanitizer == 'address':
                    command.append('/fsanitize=address')
                if name in ('snapshot', 'callback'):
                    sources.extend([ROOT / 'webgpu_readback_snapshot.cc', candidate])
                    command.extend(['/I' + str(chromium), '/I' + str(chromium / 'third_party/boringssl/src/include')])
                command.extend(str(path) for path in sources)
                command.extend(['/Fo' + str(directory) + '/', '/Fe' + str(directory / 'check.exe'), '-fuse-ld=lld',
                    '/link', '/LIBPATH:' + str(sdk / 'VC/Tools/MSVC/14.51.36231/lib/x64'),
                    '/LIBPATH:' + str(sdk / 'Windows Kits/10/Lib/10.0.28000.0/ucrt/x64'),
                    '/LIBPATH:' + str(sdk / 'Windows Kits/10/Lib/10.0.28000.0/um/x64')])
                if name in ('snapshot', 'callback'):
                    command.extend([*(str(path) for path in libraries), 'bcrypt.lib', 'advapi32.lib'])
                environment = {**os.environ, 'TMP': str(output / 'temp'), 'TEMP': str(output / 'temp')}
                started = time.monotonic()
                with (directory / 'compile.log').open('xb') as log:
                    result = subprocess.run(command, cwd=directory, env=environment, stdout=log, stderr=subprocess.STDOUT)
                row = dict(name=name, sanitizer=sanitizer, compile_returncode=result.returncode,
                    compile_seconds=round(time.monotonic() - started, 3))
                report['runs'].append(row)
                save()
                if result.returncode:
                    raise ValueError('Native compile failed: ' + str(directory))
                if sanitizer == 'address':
                    environment.update(PATH=str(asan.parent) + os.pathsep + environment.get('PATH', ''),
                        ASAN_OPTIONS='halt_on_error=1:abort_on_error=1:exitcode=99')
                result = subprocess.run([str(directory / 'check.exe')], cwd=directory,
                    capture_output=True, text=True, env=environment)
                (directory / 'test.log').write_text(result.stdout + result.stderr, encoding='utf-8', newline='\n')
                row['test_returncode'] = result.returncode
                if result.returncode:
                    raise ValueError('Native check failed: ' + str(directory))
                row['result'] = json.loads(result.stdout)
                if row['result'].get('passed') is not True:
                    raise ValueError('Native check did not report success')
                row['executable_sha256'] = digest(directory / 'check.exe')
                save()
                print(name, sanitizer, json.dumps(row['result']), flush=True)
        report.update(passed=True, measurement_complete=True)
    except Exception as error:
        report.update(error=str(error), passed=False)
    finally:
        report['postguards_passed'] = all(path.is_file() and digest(path) == value
            for path, value in {**inputs, **bound}.items())
        report['passed'] = report['passed'] and report['postguards_passed']
        save()
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
