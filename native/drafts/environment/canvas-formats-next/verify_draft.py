"""Compile an isolated Canvas draft, never patch or rebuild the active Chromium tree."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PREFIX = 'third_party/blink/renderer/core/html/canvas/glint/'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def compiler_flags(ninja):
    variables = dict(line.split(' = ', 1) for line in ninja.read_text(encoding='utf-8').splitlines()
                     if ' = ' in line and not line.startswith(' '))
    names = ('defines', 'include_dirs', 'cflags', 'cflags_cc', 'module_deps')
    text = ' '.join(variables[name] for name in names)
    text += ' "-fmodule-name=' + variables['cc_module_name'] + '_Private"'
    return text.replace('$:', ':').replace('$$', '$').replace('$ ', ' ')


def validate_paths(source, build, output):
    if os.name != 'nt':
        raise ValueError('This diagnostic requires the pinned Windows build.')
    for path in (source, build, output):
        if not path.is_absolute() or path.drive.upper() != 'D:' or path.resolve() != path:
            raise ValueError('Use canonical absolute paths on D without linked components.')
        if path == ROOT or ROOT in path.parents or path in ROOT.parents:
            raise ValueError('Diagnostic paths must stay outside the public repository.')
    if not source.is_dir() or source not in build.parents or not build.is_dir():
        raise ValueError('Use an existing build directory inside the pinned source tree.')
    if output.exists() or source == output or source in output.parents or output in source.parents:
        raise ValueError('Use a new output directory outside the source tree.')


def run(source, build, output):
    validate_paths(source, build, output)
    manifest = json.loads((HERE / 'observations.json').read_text(encoding='utf-8'))
    patch = HERE / 'canvas-formats-next.patch'
    fixture = HERE / 'half_diagnostic.cc'
    copy_fixture = HERE / 'copy_diagnostic.cc'
    if (digest(patch) != manifest['patch_sha256'] or digest(fixture) != manifest['fixture_sha256']
            or digest(copy_fixture) != manifest['copy_fixture_sha256']):
        raise ValueError('Public patch or fixture hash differs from the measured draft.')
    inputs = {source / name: value for name, value in manifest['base_source_sha256'].items()}
    for path, value in inputs.items():
        if not path.is_file() or digest(path) != value:
            raise ValueError('Pinned source mismatch: ' + str(path))
    core_ninja = build / 'obj/third_party/blink/renderer/core/core.ninja'
    canvas_ninja = build / 'obj/third_party/blink/renderer/modules/canvas/canvas.ninja'
    toolchain = build / 'toolchain.ninja'
    production_ninja = build / 'obj/chrome/chrome_dll.ninja'
    compiler = source / 'third_party/llvm-build/Release+Asserts/bin/clang-cl.exe'
    linker = compiler.with_name('lld-link.exe')
    libraries = [build / 'obj/third_party/boringssl/boringssl.lib',
                 build / 'obj/third_party/boringssl/boringssl_asm.lib',
                 build / 'obj/buildtools/third_party/libc++/libc++/verbose_abort.obj']
    for path in [core_ninja, canvas_ninja, toolchain, production_ninja, compiler, linker, patch, fixture, copy_fixture,
                 HERE / 'verify_draft.py', HERE / 'observations.json', *libraries]:
        inputs[path] = digest(path)
    match = re.search(r'/winsysroot:([^\s"]+)', toolchain.read_text(encoding='utf-8'))
    if match is None:
        raise ValueError('Pinned linker rule has no explicit Windows sysroot.')
    sysroot = (build / match[1]).resolve(strict=True)
    core_flags = compiler_flags(core_ninja)
    canvas_flags = compiler_flags(canvas_ninja)
    output.mkdir(parents=True, exist_ok=False)
    overlay = output / 'source'
    report = {'schema': 1, 'passed': False, 'measurement_complete': False, 'steps': [],
              'scope': 'Isolated C++ syntax and linked transform/copy/projection diagnostics, not a browser build.',
              'native_browser_runtime_verified': False, 'privacy_admitted': False,
              'production_admitted': False, 'inputs': {str(p): h for p, h in inputs.items()},
              'limitations': ['Existing generated modules and transitive thin-archive objects are not a full hermetic build.']}

    def command(arguments, name, cwd=build):
        with (output / (name + '.log')).open('wb') as log:
            result = subprocess.run(arguments, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, timeout=240)
        report['steps'].append({'name': name, 'returncode': result.returncode,
                                'log_sha256': digest(output / (name + '.log'))})
        if result.returncode:
            raise RuntimeError(name + ' failed; inspect its private log.')

    try:
        for name in manifest['base_source_sha256']:
            target = overlay / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((source / name).read_bytes())
        command(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error', str(patch)],
                'apply-isolated-draft', overlay)
        for name, value in manifest['prepared_source_sha256'].items():
            if digest(overlay / name) != value:
                raise ValueError('Prepared source mismatch: ' + name)
        candidate = overlay / (PREFIX + 'canvas_readback_candidate.cc')

        def compile_source(path, name, flags, syntax):
            rsp = output / (name + '.rsp')
            action = '/clang:-fsyntax-only' if syntax else '/c /Fo"' + str(output / (name + '.obj')) + '"'
            rsp.write_text('/nologo /TP ' + action + ' "/winsysroot' + str(sysroot) + '" '
                           + '"-I' + str(overlay) + '" ' + flags + ' "' + str(path) + '"', encoding='utf-8')
            command([str(compiler), '@' + str(rsp)], name)

        for stem in ('canvas_readback_candidate', 'canvas_readback_copy', 'canvas_readback_image'):
            compile_source(overlay / (PREFIX + stem + '.cc'), stem + '-syntax', core_flags, True)
        integration = overlay / 'third_party/blink/renderer/modules/canvas/canvas2d/base_rendering_context_2d.cc'
        compile_source(integration, 'canvas2d-integration-syntax', canvas_flags, True)
        compile_source(candidate, 'half-transform', core_flags, False)
        compile_source(fixture, 'half-diagnostic', core_flags, False)
        executable = output / 'half-diagnostic.exe'
        link_args = ['/nologo', '/subsystem:console', '/machine:x64', '/opt:ref',
                     '/winsysroot:' + str(sysroot), '/out:' + str(executable),
                     '-libpath:' + str(compiler.parent.parent / 'lib/clang/24/lib/windows'),
                     str(output / 'half-transform.obj'), str(output / 'half-diagnostic.obj'),
                     *map(str, libraries), 'advapi32.lib', 'bcrypt.lib', 'user32.lib']
        rsp = output / 'half-diagnostic-link.rsp'
        rsp.write_text('\n'.join('"' + arg + '"' for arg in link_args), encoding='utf-8')
        command([str(linker), '@' + str(rsp)], 'half-diagnostic-link')
        command([str(executable)], 'half-diagnostic-run')
        observed = json.loads((output / 'half-diagnostic-run.log').read_text(encoding='utf-8'))
        if observed != manifest['half_diagnostic']['observed']:
            raise ValueError('Linked fixture output differs from the measured diagnostic.')
        report['observed'] = observed
        report['executable_sha256'] = digest(executable)

        # Borrow the production link closure, not incomplete/unbuilt test targets.
        # Source-set objects are archived lazily; original output files stay read-only.
        lines = production_ninja.read_text(encoding='utf-8').splitlines()
        edge = next(line for line in lines if line.startswith('build ./chrome.dll '))
        linked_inputs = edge.split(': solink ', 1)[1].split(' | ', 1)[0].split()
        variables = dict(line.strip().split(' = ', 1) for line in lines if line.startswith('  ') and ' = ' in line)
        objects = [build / path for path in linked_inputs if path.endswith('.obj')]
        groups = {name: [path for path in objects if path.parent == build / 'obj/skia' / name]
                  for name in ('skia_core_and_effects', 'skia_opts_ml3', 'skia_opts_ml4',
                               'skcms_TransformBaseline_and_public', 'skcms_TransformHsw', 'skcms_TransformSkx')}
        groups['libcpp'] = [path for path in objects
                            if path.parent == build / 'obj/buildtools/third_party/libc++/libc++']
        prefixes = ('obj/base/', 'obj/third_party/perfetto/', 'obj/third_party/abseil-cpp/',
                    'obj/third_party/zlib/', 'obj/skia/rust')
        groups['raster-support'] = [path for path in objects if path.relative_to(build).as_posix().startswith(prefixes)]
        if any(not paths for paths in groups.values()):
            raise ValueError('Pinned production source-set closure is incomplete.')
        for paths in groups.values():
            for path in paths:
                inputs[path] = digest(path)
        compile_source(overlay / (PREFIX + 'canvas_readback_copy.cc'), 'canvas-copy', core_flags, False)
        compile_source(copy_fixture, 'copy-diagnostic', core_flags, False)
        private_libraries = []
        for name, paths in groups.items():
            archive = output / (name + '.lib')
            rsp = output / (name + '-archive.rsp')
            rsp.write_text('\n'.join('"' + str(path) + '"' for path in paths), encoding='utf-8')
            command([str(linker), '/lib', '/llvmlibthin', '/nologo', '/out:' + str(archive), '@' + str(rsp)], name + '-archive')
            private_libraries.append(archive)
        production_libraries = [build / path for path in linked_inputs if path.endswith('.lib')]
        for path in production_libraries:
            inputs[path] = digest(path)
        borrowed_flags = ' '.join(variables[name] for name in ('libs', 'rlibs')).replace('$:', ':')
        for token in variables['rlibs'].split():
            if token.endswith('.rlib'):
                path = build / token
                inputs[path] = digest(path)
        copy_executable = output / 'copy-diagnostic.exe'
        copy_link_args = [arg for arg in link_args if not arg.startswith('/out:') and not arg.endswith('half-diagnostic.obj')]
        copy_link_args += ['/out:' + str(copy_executable), str(output / 'canvas-copy.obj'),
                           str(output / 'copy-diagnostic.obj'), *map(str, private_libraries), *map(str, production_libraries)]
        rsp = output / 'copy-diagnostic-link.rsp'
        rsp.write_text('\n'.join('"' + arg + '"' for arg in copy_link_args) + '\n' + borrowed_flags, encoding='utf-8')
        command([str(linker), '@' + str(rsp)], 'copy-diagnostic-link')
        command([str(copy_executable)], 'copy-diagnostic-run')
        copy_observed = json.loads((output / 'copy-diagnostic-run.log').read_text(encoding='utf-8'))
        if copy_observed != manifest['copy_diagnostic']['observed']:
            raise ValueError('Native copy/projection output differs from the measured fixture.')
        report['copy_observed'] = copy_observed
        report['copy_executable_sha256'] = digest(copy_executable)
        report['borrowed_source_set_objects'] = sum(map(len, groups.values()))
        report['passed'] = True
    except Exception as error:
        report['error'] = {'type': type(error).__name__, 'message': str(error)}
    finally:
        report['changed_inputs'] = [str(p) for p, h in inputs.items() if not p.is_file() or digest(p) != h]
        report['postguards_passed'] = not report['changed_inputs']
        report['passed'] &= report['postguards_passed']
        report['measurement_complete'] = True
        report['inputs'] = {str(path): value for path, value in inputs.items()}
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source-root', 'build-dir', 'work-dir'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    try:
        report = run(args.source_root, args.build_dir, args.work_dir)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, str(error) + '\n')
    print(json.dumps({key: report.get(key) for key in ('passed', 'postguards_passed', 'observed', 'error')}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
