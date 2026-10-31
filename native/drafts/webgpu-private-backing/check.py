"""Replay the unselected backing-policy batch and test extracted predicates, not native imports."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parent
ENV = MODULE.parent / 'environment'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_predicates(staging):
    native = staging / 'third_party/dawn/src/dawn/native/d3d12'
    header = (native / 'BufferD3D12.h').read_text(encoding='utf-8-sig')
    start = header.index('    bool HasPrivateGlintReadbackBacking() const {')
    getter = header[start:header.index('\n    }', start) + 6]
    command = (native / 'CommandBufferD3D12.cpp').read_text(encoding='utf-8-sig')
    start = command.index('            if (!buffer || !ToBackend(buffer)->HasPrivateGlintReadbackBacking()')
    binding = command[start:command.index('            uses.push_back', start)]
    capture = (native / 'GlintTextureReadbackD3D12.cpp').read_text(encoding='utf-8-sig')
    clauses = []
    for text, pattern in (
        (command, r'DAWN_INTERNAL_ERROR_IF\(!ToBackend\(indirectBuffer\)->HasPrivateGlintReadbackBacking\(\),\s*"Glint compute capture requires private indirect-buffer backing\."\);'),
        (capture, r'DAWN_INTERNAL_ERROR_IF\(!source->HasPrivateGlintReadbackBacking\(\),\s*"Glint byte capture requires private buffer backing\."\);'),
    ):
        matches = re.findall(pattern, text)
        if len(matches) != 1:
            raise ValueError('Expected one native backing predicate')
        clauses.append(matches[0])
    return {'getter': getter, 'binding': binding, 'indirect': clauses[0], 'capture': clauses[1]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('chromium-root', 'sdk-root', 'work-dir'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    chromium, sdk, out = args.chromium_root, args.sdk_root, args.work_dir
    if (sys.platform != 'win32' or any(not p.is_absolute() or p != p.resolve()
            or p.is_symlink() or p.is_junction() or p.drive.upper() != 'D:'
            for p in (chromium, sdk, out)) or not chromium.is_dir() or not sdk.is_dir()
            or out.exists() or not out.parent.is_dir()
            or any(out.is_relative_to(p) or p.is_relative_to(out) for p in (MODULE, chromium, sdk))):
        parser.error('Use canonical D: checkout/SDK and a fresh external D: output')
    if shutil.disk_usage(out.parent).free < 1024**3:
        parser.error('At least 1 GiB free on D: is required')
    record_path = ENV / 'webgpu-private-backing-preparation.json'
    record = json.loads(record_path.read_bytes())
    template_path = MODULE / 'predicates-template.cc'
    for path, expected in ((Path(__file__), record['checker_sha256']),
                           (template_path, record['template_sha256'])):
        if digest(path) != expected:
            parser.error('Measured predicate checker/template differs')
    packets = [*(ENV / row['patch'] for row in record['prerequisites']), ENV / record['patch']]
    for row, path in zip([*record['prerequisites'], {'sha256': record['patch_sha256']}], packets):
        if digest(path) != row['sha256']:
            parser.error('Public backing-policy source packet differs')
    tools = chromium / 'third_party/llvm-build/Release+Asserts'
    compiler = tools / 'bin/clang-cl.exe'
    asan = tools / 'lib/clang/24/lib/windows/clang_rt.asan_dynamic-x86_64.dll'
    linker = tools / 'bin/lld-link.exe'
    guards = {p: digest(p) for p in (Path(__file__), record_path, template_path, compiler,
                                    linker, asan, *packets)}
    missing = []
    out.mkdir(exist_ok=False)
    staging = out / 'sources'
    staging.mkdir()
    report = {
        'passed': False, 'measurement_complete': False, 'runs': [],
        'source_extracted_predicates_only': True, 'backend_mocked': True,
        'actual_shared_or_host_mapped_import_executed': False,
        'actual_native_device_queue_executed': False, 'runtime_verified': False,
        'privacy_admitted': False, 'production_admitted': False,
    }
    try:
        for row in record['composed_sources']:
            source = chromium / row['source']
            if row['before_sha256'] is None:
                if source.exists():
                    raise ValueError('Expected unselected source: ' + row['source'])
                missing.append(source)
            else:
                if digest(source) != row['before_sha256']:
                    raise ValueError('Pinned source baseline differs: ' + row['source'])
                guards[source] = digest(source)
                target = staging / row['source']
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        for packet in packets:
            subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error', str(packet)],
                           cwd=staging, capture_output=True, check=True)
        for row in record['composed_sources']:
            path = staging / row['source']
            actual = digest(path) if path.is_file() else None
            if actual != row['after_sha256']:
                raise ValueError('Composed backing-policy source differs: ' + row['source'])
            if path.is_file():
                guards[path] = actual
        fixture = template_path.read_text(encoding='utf-8-sig')
        for name, text in extract_predicates(staging).items():
            marker = '/* GLINT_' + name.upper() + ' */'
            if (fixture.count(marker) != 1 or hashlib.sha256(text.encode()).hexdigest()
                    != record['extracted_predicates_sha256'][name]):
                raise ValueError('Extracted backing predicate/template marker differs')
            fixture = fixture.replace(marker, text)
        test = staging / 'predicates_test.cc'
        test.write_text(fixture, encoding='utf-8', newline='\n')
        if digest(test) != record['generated_fixture_sha256']:
            raise ValueError('Generated backing predicate fixture differs')
        guards[test] = digest(test)
        temp = out / 'temp'
        temp.mkdir()
        environment = dict(os.environ, TMP=str(temp), TEMP=str(temp))
        flags = [str(compiler), '/nologo', '/std:c++20', '/W4', '/WX', '/EHsc', '/MT',
                 '/Od', '/Z7', '/winsysroot:' + str(sdk)]
        flags += ['/imsvc' + str(sdk / 'VC/Tools/MSVC/14.51.36231/include')]
        flags += ['/imsvc' + str(sdk / 'Windows Kits/10/Include/10.0.28000.0' / kind)
                  for kind in ('ucrt', 'shared', 'um')]
        flags += ['/I' + str(p) for p in (staging / 'third_party/dawn/include',
                  chromium / 'third_party/dawn/include',
                  chromium / 'out/CamouFlowNative/gen/third_party/dawn/include')]
        for mode in ('none', 'address'):
            directory = out / mode
            directory.mkdir()
            command = [*flags, *(['/fsanitize=address'] if mode == 'address' else []),
                       str(test), '/Fe' + str(directory / 'check.exe'), '-fuse-ld=lld']
            with (directory / 'compile.log').open('xb') as log:
                result = subprocess.run(command, cwd=directory, env=environment,
                                        stdout=log, stderr=subprocess.STDOUT, timeout=180, check=False)
            row = {'sanitizer': mode, 'compile_returncode': result.returncode}
            report['runs'].append(row)
            if result.returncode:
                raise RuntimeError('Predicate compilation failed')
            run_environment = dict(environment, PATH=str(asan.parent) + os.pathsep + environment.get('PATH', ''),
                                   ASAN_OPTIONS='halt_on_error=1:abort_on_error=1:exitcode=99')
            result = subprocess.run([str(directory / 'check.exe')], cwd=directory, env=run_environment,
                                    capture_output=True, text=True, timeout=180, check=False)
            (directory / 'test.log').write_text(result.stdout + result.stderr, encoding='utf-8')
            row.update(test_returncode=result.returncode)
            if result.returncode:
                raise RuntimeError('Predicate execution failed')
            value = row['result'] = json.loads(result.stdout)
            if not (value.get('passed') is True and value.get('assertions') == 216
                    and value.get('origin_combinations') == 16
                    and value.get('source_extracted_predicates_only') is True
                    and value.get('actual_shared_or_host_mapped_import_executed') is False):
                raise ValueError('Missing explicit synthetic predicate scope')
            print(mode, result.stdout.strip(), flush=True)
        report.update(passed=True, measurement_complete=True)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        report['error'] = str(error)
    finally:
        report['input_sha256'] = {str(p): value for p, value in guards.items()}
        report['postguards_passed'] = (all(p.is_file() and digest(p) == value for p, value in guards.items())
                                      and all(not p.exists() for p in missing))
        report['passed'] = report['passed'] and report['postguards_passed']
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
