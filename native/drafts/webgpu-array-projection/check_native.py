"""Syntax-check array projection with generated Dawn flags, without editing Chromium."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
from scripts.verify_native_gpu_cpp import syntax_flags
from scripts.verify_native_privacy_units import require_idle_builder

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--chromium-root', type=Path, required=True)
parser.add_argument('--sdk-root', type=Path, required=True)
parser.add_argument('--work-dir', type=Path, required=True)
args = parser.parse_args()
SOURCE, SDK, OUT = args.chromium_root, args.sdk_root, args.work_dir
if (sys.platform != 'win32' or any(not p.is_absolute() or p != p.resolve() or p.is_symlink()
        or p.is_junction() or p.drive.upper() != 'D:' for p in (SOURCE, SDK, OUT))
        or not SOURCE.is_dir() or not SDK.is_dir() or OUT.exists() or not OUT.parent.is_dir()
        or any(OUT.is_relative_to(p) or p.is_relative_to(OUT) for p in (HERE, SOURCE, SDK))):
    parser.error('Use canonical existing D: source/SDK and fresh external D: output')
require_idle_builder(SOURCE.parents[1])
OUT.mkdir()
(OUT / 'temp').mkdir()
BUILD = SOURCE / 'out/CamouFlowNative'
COMPILER = SOURCE / 'third_party/llvm-build/Release+Asserts/bin/clang-cl.exe'
TARGET = BUILD / 'obj/third_party/dawn/src/dawn/native/sources.ninja'
TOOLCHAIN = BUILD / 'toolchain.ninja'
RELATIVE = Path('third_party/dawn/src/dawn/native/d3d12/glint')
capture = HERE.parent / 'webgpu-subresource-capture'
files = {SOURCE / RELATIVE / name: (HERE if name.startswith('projected') else capture) / name
         for name in ('projected_texture.cc', 'projected_texture.h', 'texture_capture.cc', 'texture_capture.h')}
overlay = OUT / 'overlay.json'
overlay.write_text(json.dumps({'version': 0, 'case-sensitive': False, 'use-external-names': False,
    'roots': [{'type': 'file', 'name': str(original), 'external-contents': str(candidate)}
              for original, candidate in files.items()]}), encoding='utf-8', newline='\n')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
inputs = {p: sha(p) for p in (COMPILER, TARGET, TOOLCHAIN, overlay, Path(__file__),
                             REPO / 'scripts/verify_native_gpu_cpp.py', *files, *files.values())}
report = {'schema': 1, 'passed': False, 'runs': [], 'scope': __doc__,
          'browser_integrated': False, 'privacy_admitted': False, 'production_admitted': False,
          'source_sha256': {str(p): value for p, value in inputs.items()}}
ninja = TARGET.read_text(encoding='utf-8-sig')
variables = dict(re.findall(r'^(\w+) = (.*)$', ninja, re.MULTILINE))
modules = variables['module_deps'].replace('$:', ':').replace('$$', '$')
if '$' in modules:
    raise ValueError('Unresolved module flags')
env = dict(os.environ, TEMP=str(OUT / 'temp'), TMP=str(OUT / 'temp'))
try:
    for name in ('projected_texture.cc', 'texture_capture.cc'):
        relative = (RELATIVE / name).as_posix()
        flags = syntax_flags(ninja, TOOLCHAIN.read_text(encoding='utf-8-sig'), relative)
        response = OUT / (Path(name).stem + '.rsp')
        response.write_text(flags + ' ' + modules + ' -fmodule-name=GlintArrayProjection_Private '
            + '/nologo /Zs /TP -vfsoverlay "' + str(overlay) + '" "/winsysroot' + str(SDK)
            + '" -fcrash-diagnostics-dir="' + str(OUT / 'temp') + '" "../../' + relative + '"\n',
            encoding='utf-8', newline='\n')
        log = response.with_suffix('.log')
        with log.open('xb') as stream:
            result = subprocess.run([str(COMPILER), '@' + str(response)], cwd=BUILD, env=env,
                                    stdout=stream, stderr=subprocess.STDOUT, timeout=180, check=False)
        report['runs'].append({'source': relative, 'returncode': result.returncode,
                               'log_sha256': sha(log), 'response_sha256': sha(response)})
        if result.returncode:
            raise RuntimeError('Native syntax failed: ' + name)
    report['passed'] = True
except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
    report['error'] = str(error)
finally:
    report['postguards_passed'] = all(sha(p) == expected for p, expected in inputs.items())
    report['passed'] = report['passed'] and report['postguards_passed']
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps({'passed': report['passed'], 'runs': report['runs'], 'error': report.get('error')}))
raise SystemExit(0 if report['passed'] else 1)
