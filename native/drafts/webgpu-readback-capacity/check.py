"""Check the R6 readback-capacity packet on D: without editing Chromium."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium-root', type=Path, required=True)
    parser.add_argument('--sdk-root', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    args = parser.parse_args()
    source, sdk, out = args.chromium_root, args.sdk_root, args.work_dir
    if not __debug__:
        parser.error('Run without Python optimization; evidence guards require assertions')
    if (sys.platform != 'win32' or any(not path.is_absolute() or path != path.resolve()
            or path.is_symlink() or path.is_junction() or path.drive.upper() != 'D:'
            for path in (source, sdk, out)) or not source.is_dir() or not sdk.is_dir()
            or out.exists() or not out.parent.is_dir()
            or any(out.is_relative_to(path) or path.is_relative_to(out) for path in (HERE, source, sdk))):
        parser.error('Use canonical existing D: sources/SDK and fresh external D: output')
    if shutil.disk_usage(out.parent).free < 1024**3:
        parser.error('At least 1 GiB free is required for these small isolated checks')
    os.environ.update(PYTHONDONTWRITEBYTECODE='1', CAMOUFLOW_DATA_DIR=str(out / 'workspace'))
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    from scripts.native_build import load_candidate
    from scripts.verify_native_gpu_cpp import syntax_flags
    from scripts.verify_native_privacy_units import require_idle_builder

    require_idle_builder(source.parents[1])
    out.mkdir(exist_ok=False)
    (out / 'temp').mkdir()
    packet_path = HERE / 'packet.json'
    packet = json.loads(packet_path.read_text(encoding='utf-8-sig'))
    candidate = load_candidate(packet['base_candidate'])
    assert candidate['manifest_sha256'] == packet['base_candidate_manifest_sha256']
    patch, fixture = HERE / packet['patch'], HERE / 'fixture.cc'
    assert digest(patch) == packet['patch_sha256'] and digest(fixture) == packet['fixture_sha256']
    inputs = {path: digest(path) for path in (Path(__file__), packet_path, patch, fixture)}
    build = source / 'out/CamouFlowNative'
    compiler = source / 'third_party/llvm-build/Release+Asserts/bin/clang-cl.exe'
    toolchain = build / 'toolchain.ninja'
    libraries = [build / 'obj/third_party/boringssl' / name for name in ('boringssl.lib', 'boringssl_asm.lib')]
    libraries.append(build / 'obj/buildtools/third_party/libc++/libc++/verbose_abort.obj')
    inputs.update({path: digest(path) for path in (compiler, toolchain, *libraries)})
    staging = out / 'sources'
    report = {'schema': 1, 'passed': False, 'runs': [], 'native_syntax': [],
              'scope': __doc__, 'canonical_sources_modified': False,
              'browser_integrated': False, 'privacy_admitted': False, 'production_admitted': False}
    env = dict(os.environ, TEMP=str(out / 'temp'), TMP=str(out / 'temp'))
    env['PATH'] = str(source / 'third_party/llvm-build/Release+Asserts/lib/clang/24/lib/windows') + os.pathsep + env.get('PATH', '')
    try:
        for relative, expected in packet['source_inputs_sha256'].items():
            original, target = source / relative, staging / relative
            assert original == original.resolve() and original.is_file() and digest(original) == expected
            assert target.resolve().is_relative_to(staging.resolve())
            inputs[original] = expected
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
        applied = subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error', str(patch)],
                                 cwd=staging, capture_output=True, text=True)
        if applied.returncode:
            raise RuntimeError('Owned packet composition failed: ' + applied.stderr)
        for relative, values in packet['source_files'].items():
            assert digest(staging / relative) == values['after_sha256']
        prepared = {path: digest(path) for path in staging.rglob('*') if path.is_file()}
        inputs.update(prepared)
        report['prepared_source_sha256'] = {path.relative_to(staging).as_posix(): value for path, value in prepared.items()}
        common = staging / 'gpu/command_buffer/common/glint'
        for mode in ('normal', 'address'):
            output = out / mode
            output.mkdir()
            command = [str(compiler), '/nologo', '/std:c++20', '/W4', '/WX', '/EHsc', '/MT', '/Od',
                       '/winsysroot:' + str(sdk), '/I' + str(staging), '/I' + str(source),
                       '/I' + str(source / 'third_party/boringssl/src/include'),
                       '/imsvc' + str(sdk / 'VC/Tools/MSVC/14.51.36231/include'),
                       '/imsvc' + str(sdk / 'Windows Kits/10/Include/10.0.28000.0/ucrt')]
            if mode == 'address':
                command.append('/fsanitize=address')
            command += [str(fixture), *[str(common / name) for name in (
                'webgpu_readback_layout.cc', 'webgpu_readback_provenance.cc',
                'webgpu_readback_snapshot.cc', 'canvas_readback_candidate.cc')],
                '/Fo' + str(output) + '/', '/Fe' + str(output / 'check.exe'), '-fuse-ld=lld', '/link',
                '/LIBPATH:' + str(sdk / 'VC/Tools/MSVC/14.51.36231/lib/x64'),
                '/LIBPATH:' + str(sdk / 'Windows Kits/10/Lib/10.0.28000.0/ucrt/x64'),
                '/LIBPATH:' + str(sdk / 'Windows Kits/10/Lib/10.0.28000.0/um/x64'),
                *[str(path) for path in libraries], 'kernel32.lib', 'bcrypt.lib', 'advapi32.lib']
            with (output / 'compile.log').open('x', encoding='utf-8') as log:
                compiled = subprocess.run(command, cwd=output, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180)
            row = {'sanitizer': mode, 'compile_returncode': compiled.returncode}
            report['runs'].append(row)
            if compiled.returncode:
                raise RuntimeError('Standalone compilation failed: ' + mode)
            with (output / 'run.log').open('x', encoding='utf-8') as log:
                ran = subprocess.run([str(output / 'check.exe')], cwd=output, env=env,
                                     stdout=log, stderr=subprocess.STDOUT, timeout=180)
            row.update(returncode=ran.returncode, log_sha256=digest(output / 'run.log'))
            if ran.returncode:
                raise RuntimeError('Standalone fixture failed: ' + mode)
        vfs = out / 'overlay.json'
        vfs.write_text(json.dumps({'version': 0, 'case-sensitive': False, 'use-external-names': False,
            'roots': [{'type': 'file', 'name': str(source / path.relative_to(staging)),
                       'external-contents': str(path)} for path in prepared]}), encoding='utf-8', newline='\n')
        inputs[vfs] = digest(vfs)
        toolchain_text = toolchain.read_text(encoding='utf-8-sig')
        targets = [('gpu/command_buffer/common/glint/webgpu_readback_provenance.cc', 'common/common_sources'),
                   ('gpu/command_buffer/common/glint/webgpu_readback_snapshot.cc', 'common/common_sources'),
                   ('gpu/command_buffer/service/glint_webgpu_readback_observer.cc', 'service/gles2_sources')]
        for relative, target in targets:
            ninja_path = build / ('obj/gpu/command_buffer/' + target + '.ninja')
            inputs[ninja_path] = digest(ninja_path)
            ninja = ninja_path.read_text(encoding='utf-8-sig')
            variables = dict(re.findall(r'^(\w+) = (.*)$', ninja, re.M))
            modules = variables.get('module_deps', '').replace('$:', ':').replace('$$', '$')
            assert '$' not in modules
            for values in re.findall(r'-fmodule-file=[^= ]+=(\S+)|-fmodule-map-file=(\S+)', modules):
                path = build / next(part for part in values if part)
                inputs[path] = digest(path)
            flags = syntax_flags(ninja, toolchain_text, relative)
            response = out / (Path(relative).stem + '.rsp')
            response.write_text(flags + ' ' + modules + ' -fmodule-name=GlintReadbackCapacity_Private /nologo /Zs /TP '
                '-vfsoverlay "' + str(vfs) + '" "/winsysroot' + str(sdk) + '" '
                '-fcrash-diagnostics-dir="' + str(out / 'temp') + '" "../../' + relative + '"\n',
                encoding='utf-8', newline='\n')
            log_path = response.with_suffix('.log')
            with log_path.open('x', encoding='utf-8') as log:
                result = subprocess.run([str(compiler), '@' + str(response)], cwd=build, env=env,
                                        stdout=log, stderr=subprocess.STDOUT, timeout=180)
            report['native_syntax'].append({'source': relative, 'returncode': result.returncode,
                                           'log_sha256': digest(log_path), 'response_sha256': digest(response)})
            if result.returncode:
                raise RuntimeError('Generated-target syntax failed: ' + relative)
        report['passed'] = True
    except (OSError, ValueError, RuntimeError, AssertionError, subprocess.SubprocessError) as error:
        report.update(error_type=type(error).__name__, error=str(error))
    finally:
        report['postguards_passed'] = all(path.is_file() and digest(path) == value for path, value in inputs.items())
        report['passed'] = report['passed'] and report['postguards_passed']
        report['inputs_sha256'] = {str(path): value for path, value in inputs.items()}
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({key: value for key, value in report.items() if key not in {'inputs_sha256', 'prepared_source_sha256'}}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
