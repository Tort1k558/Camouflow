"""Compose and syntax-check the owned Dawn packet without changing Chromium."""
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
from scripts import native_build
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
packet = json.loads((HERE / 'packet.json').read_bytes())
candidate = native_build.load_candidate(packet['base_candidate'])
if candidate['manifest_sha256'] != packet['base_candidate_manifest_sha256']:
    parser.error('Base candidate manifest differs')
OUT.mkdir()
(OUT / 'temp').mkdir()
OVERLAY = OUT / 'overlay'
DAWN = OVERLAY / 'third_party/dawn'
DAWN.mkdir(parents=True)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
inputs = {HERE / 'packet.json': sha(HERE / 'packet.json'), Path(__file__): sha(Path(__file__)),
          REPO / 'scripts/native_build.py': sha(REPO / 'scripts/native_build.py'),
          REPO / 'scripts/verify_native_gpu_cpp.py': sha(REPO / 'scripts/verify_native_gpu_cpp.py')}
inputs.update({p: sha(p) for p in (candidate['directory'] / 'manifest.json',
                                 REPO / 'native/build-lock.json',
                                 REPO / 'scripts/verify_native_privacy_units.py')})
inputs.update({p: sha(p) for p in (candidate['directory'] / 'patches').glob('*.patch')})
groups = []
for row in packet['prerequisites']:
    patch, observations = REPO / row['patch'], REPO / row['observations']
    if sha(patch) != row['patch_sha256'] or sha(observations) != row['observations_sha256']:
        raise ValueError('Prerequisite source evidence differs')
    inputs.update({patch: sha(patch), observations: sha(observations)})
    groups.append((patch, json.loads(observations.read_bytes())['source_files']))
patch = HERE / packet['patch']
if sha(patch) != packet['patch_sha256']:
    raise ValueError('Integration packet differs')
inputs[patch] = sha(patch)
groups.append((patch, packet['source_files']))
base = {}
for _, sources in groups:
    for relative, row in sources.items():
        path = Path(relative)
        if path.is_absolute() or path.drive or '..' in path.parts or not relative.startswith('src/dawn/native/d3d12/'):
            raise ValueError('Packet path escapes its Dawn scope')
        base.setdefault(relative, row['before_sha256'])
for relative, expected in base.items():
    original, target = SOURCE / 'third_party/dawn' / relative, DAWN / relative
    if original != original.resolve() or sha(original) != expected:
        raise ValueError('Canonical R5 source differs: ' + relative)
    inputs[original] = sha(original)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(original.read_bytes())
report = {'schema': 1, 'passed': False, 'runs': [], 'scope': __doc__,
          'browser_integrated': False, 'runtime_verified': False, 'production_admitted': False}
BUILD = SOURCE / 'out/CamouFlowNative'
COMPILER = SOURCE / 'third_party/llvm-build/Release+Asserts/bin/clang-cl.exe'
TARGET = BUILD / 'obj/third_party/dawn/src/dawn/native/sources.ninja'
TOOLCHAIN = BUILD / 'toolchain.ninja'
inputs.update({p: sha(p) for p in (COMPILER, TARGET, TOOLCHAIN)})
env = dict(os.environ, TEMP=str(OUT / 'temp'), TMP=str(OUT / 'temp'))
try:
    for patch, sources in groups:
        if any(sha(DAWN / name) != row['before_sha256'] for name, row in sources.items()):
            raise ValueError('Staged packet preimage differs')
        subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error', str(patch)],
                       cwd=DAWN, check=True, capture_output=True, timeout=30)
        if any(sha(DAWN / name) != row['after_sha256'] for name, row in sources.items()):
            raise ValueError('Staged packet postimage differs')
    prepared = {p: sha(p) for p in OVERLAY.rglob('*') if p.is_file()}
    inputs.update(prepared)
    report['prepared_source_sha256'] = {p.relative_to(OVERLAY).as_posix(): value for p, value in prepared.items()}
    vfs = OUT / 'vfs.json'
    vfs.write_text(json.dumps({'version': 0, 'case-sensitive': False, 'use-external-names': False,
        'roots': [{'type': 'file', 'name': str(SOURCE / p.relative_to(OVERLAY)),
                   'external-contents': str(p)} for p in prepared]}), encoding='utf-8', newline='\n')
    inputs[vfs] = sha(vfs)
    ninja = TARGET.read_text(encoding='utf-8-sig')
    variables = dict(re.findall(r'^(\w+) = (.*)$', ninja, re.MULTILINE))
    modules = variables['module_deps'].replace('$:', ':').replace('$$', '$')
    if '$' in modules:
        raise ValueError('Unresolved module flags')
    for value in re.findall(r'-fmodule-file=[^= ]+=(\S+)|-fmodule-map-file=(\S+)', modules):
        path = BUILD / next(part for part in value if part)
        inputs[path] = sha(path)
    jobs = sorted(p for p in prepared if p.suffix in ('.cc', '.cpp'))
    for source in jobs:
        relative = source.relative_to(OVERLAY).as_posix()
        flags = syntax_flags(ninja, TOOLCHAIN.read_text(encoding='utf-8-sig'), relative)
        response = OUT / (source.stem + '.rsp')
        response.write_text(flags + ' ' + modules + ' -fmodule-name=GlintArrayIntegration_Private '
            + '/nologo /Zs /TP -vfsoverlay "' + str(vfs) + '" "/winsysroot' + str(SDK)
            + '" -fcrash-diagnostics-dir="' + str(OUT / 'temp') + '" "../../' + relative + '"\n',
            encoding='utf-8', newline='\n')
        log = response.with_suffix('.log')
        with log.open('xb') as stream:
            result = subprocess.run([str(COMPILER), '@' + str(response)], cwd=BUILD, env=env,
                                    stdout=stream, stderr=subprocess.STDOUT, timeout=180, check=False)
        report['runs'].append({'source': relative, 'returncode': result.returncode,
                               'log_sha256': sha(log), 'response_sha256': sha(response)})
        print(relative, result.returncode, flush=True)
        if result.returncode:
            raise RuntimeError('Native syntax failed: ' + relative)
    report.update(passed=True, packet_composition_passed=True)
except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
    report['error'] = str(error)
finally:
    report['postguards_passed'] = all(sha(p) == expected for p, expected in inputs.items())
    report['passed'] = report['passed'] and report['postguards_passed']
    report['input_sha256'] = {str(p): value for p, value in inputs.items()}
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
raise SystemExit(0 if report['passed'] else 1)
