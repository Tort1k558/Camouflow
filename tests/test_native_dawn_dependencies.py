"""Dawn dependency pins must not become arbitrary source/repository access."""
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from scripts import fetch_native_rebase_sources as fetch
from scripts import native_build as build
from scripts import package_native_windows as packaging
from scripts import verify_native_rebase_draft as replay


@pytest.mark.parametrize('failure', [None, 'missing', 'null', 'repository', 'revision',
                                      'host', 'url-revision', 'query', 'path'])
def test_dawn_sparse_sources_require_exact_official_pin_and_path(failure):
    revision = 'b' * 40
    row = dict(path='third_party/dawn/src/dawn/native/Device.cpp', bytes=1, sha256='0' * 64,
               url=f'https://dawn.googlesource.com/dawn/+/{revision}/src/dawn/native/Device.cpp?format=TEXT')
    manifest = dict(target_revision='a' * 40, source_files=[row], dependencies={
        'dawn': {'repository': 'https://dawn.googlesource.com/dawn', 'revision': revision}})
    if failure == 'missing':
        manifest['dependencies'] = {}
    elif failure == 'null':
        manifest['dependencies']['dawn'] = None
    elif failure == 'repository':
        manifest['dependencies']['dawn']['repository'] = 'https://untrusted.invalid/dawn'
    elif failure == 'revision':
        manifest['dependencies']['dawn']['revision'] = 'HEAD'
    elif failure == 'host':
        row['url'] = row['url'].replace('dawn.googlesource.com', 'untrusted.invalid')
    elif failure == 'url-revision':
        row['url'] = row['url'].replace(revision, 'c' * 40)
    elif failure == 'query':
        row['url'] += '&other=1'
    elif failure == 'path':
        row['path'] = 'third_party/dawn/../Device.cpp'
    if failure:
        with pytest.raises(ValueError):
            fetch.source_plan(manifest)
    else:
        assert fetch.source_plan(manifest) == [row]


@pytest.mark.parametrize('failure', [None, 'missing', 'revision', 'repository', 'duplicate-deps'])
@pytest.mark.parametrize('with_v8', [False, True])
def test_dawn_sparse_patch_replay_binds_chromium_deps_and_preserves_inputs(tmp_path, failure, with_v8):
    source = tmp_path / 'source'
    (source / 'third_party/dawn').mkdir(parents=True)
    original = b'original\n'
    (source / 'third_party/dawn/file.txt').write_bytes(original)
    revision = 'b' * 40
    deps = "vars = {'dawn_revision': '" + revision + "'}\n"
    if failure == 'duplicate-deps':
        deps += "other = {'dawn_revision': '" + revision + "'}\n"
    if with_v8:
        deps += "vars.update({'v8_revision': '" + 'a' * 40 + "'})\n"
    (source / 'DEPS').write_text(deps, encoding='utf-8', newline='\n')
    patches = tmp_path / 'patches'
    patches.mkdir()
    patch = patches / '0001-dawn.patch'
    patch.write_bytes(b'diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt\n'
                      b'@@ -1 +1 @@\n-original\n+updated\n')
    manifest = dict(schema=1, target_revision='a' * 40, source_files=[],
        dependencies={'dawn': {'repository': 'https://dawn.googlesource.com/dawn', 'revision': revision}},
        patches=[dict(file=patch.name, directory='third_party/dawn',
                      sha256=hashlib.sha256(patch.read_bytes()).hexdigest())])
    if with_v8:
        manifest['dependencies']['v8'] = {'repository': 'https://chromium.googlesource.com/v8/v8.git',
                                         'revision': 'a' * 40}
    for name in ('DEPS', 'third_party/dawn/file.txt'):
        manifest['source_files'].append(dict(path=name, sha256=hashlib.sha256((source / name).read_bytes()).hexdigest()))
    if failure == 'missing':
        manifest['dependencies'] = {}
    elif failure == 'revision':
        manifest['dependencies']['dawn']['revision'] = 'c' * 40
    elif failure == 'repository':
        manifest['dependencies']['dawn']['repository'] = 'https://untrusted.invalid/dawn'
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(manifest), encoding='utf-8', newline='\n')
    before = path.read_bytes()
    if failure:
        with pytest.raises(ValueError, match='Dawn'):
            replay.verify(source, tmp_path / 'evidence', manifest_path=path, patch_directory=patches)
    else:
        result = replay.verify(source, tmp_path / 'evidence', manifest_path=path, patch_directory=patches)
        assert result['passed'] and result['inputs_unchanged']
        assert result['checks'] == [dict(patch=patch.name, directory='third_party/dawn', applied=True)]
    assert path.read_bytes() == before
    assert (source / 'third_party/dawn/file.txt').read_bytes() == original
    assert (source / 'DEPS').read_text(encoding='utf-8') == deps


@pytest.mark.parametrize('failure', [None, 'missing', 'revision', 'repository', 'hash', 'duplicate'])
def test_dawn_build_receipt_requires_complete_ordered_dependency_identity(failure):
    manifest = dict(dependencies={'v8': {'revision': 'b' * 40}, 'dawn': {'revision': 'c' * 40}},
        patches=[dict(file='0001-root.patch', sha256='1' * 64),
                 dict(file='0002-v8.patch', sha256='2' * 64, directory='v8'),
                 dict(file='0003-dawn.patch', sha256='3' * 64, directory='third_party/dawn')])
    expected = [dict(name='0001-root.patch', sha256='1' * 64),
                dict(name='0002-v8.patch', sha256='2' * 64, repository='v8', revision='b' * 40),
                dict(name='0003-dawn.patch', sha256='3' * 64, repository='third_party/dawn', revision='c' * 40)]
    assert build.expected_candidate_patches(manifest) == expected
    candidate = dict(manifest=manifest, manifest_sha256='d' * 64)
    receipt = dict(schema=1, platform='win32', binary='chrome.exe',
        **{key: build.LOCK[key] for key in ('native_version', 'chromium_revision', 'depot_tools_revision')},
        candidate_manifest_sha256=candidate['manifest_sha256'], patches=expected)
    if failure == 'missing':
        receipt['patches'].pop()
    elif failure == 'revision':
        receipt['patches'][-1]['revision'] = 'e' * 40
    elif failure == 'repository':
        receipt['patches'][-1]['repository'] = 'v8'
    elif failure == 'hash':
        receipt['patches'][-1]['sha256'] = '0' * 64
    elif failure == 'duplicate':
        receipt['patches'].append(receipt['patches'][-1].copy())
    if failure:
        with pytest.raises(ValueError, match='complete manifest'):
            packaging.validate_build_receipt(receipt, build.LOCK, candidate=candidate)
    else:
        packaging.validate_build_receipt(receipt, build.LOCK, candidate=candidate)


def test_receipt_generation_cannot_silently_drop_unknown_repository():
    with pytest.raises(ValueError, match='unsupported patch repository'):
        build.expected_candidate_patches(dict(patches=[dict(file='unknown.patch', sha256='0' * 64,
                                                           directory='third_party/unknown')]))


def test_capture_python_baseline_predates_dawn_tooling_changes():
    path = Path(__file__).resolve().parents[1] / 'native/drafts/environment/canonical-python76-d3d12-capture-observations.json'
    record = json.loads(path.read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['git_head'].startswith('55522f2')
    assert record['counts'] == dict(tests=4977, passed=4976, skipped=1, failures=0, errors=0)
    assert record['native_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False


def test_tooling_history_recovers_measured_tls_sources_and_round_trips(native_tooling_before_dawn, tmp_path):
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'dawn-tooling-source-upgrade.json').read_bytes())
    old_tls = root / 'native/drafts/network/negotiation68-observations.json'
    assert hashlib.sha256(old_tls.read_bytes()).hexdigest() == record['historical_observation_sha256']
    tls = json.loads(old_tls.read_bytes())
    assert len(record['sources']) == 6 and record['historical_tls_sources_matched'] == 4
    assert record['exact_roundtrip_verified'] and record['runtime_verified'] is False
    assert record['privacy_admitted'] is record['production_admitted'] is False
    base = tmp_path / 'history-roundtrip'
    for relative, content in native_tooling_before_dawn['sources'].items():
        target = base / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        if relative in tls['source_sha256']:
            assert hashlib.sha256(content).hexdigest() == tls['source_sha256'][relative]
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error',
                    str(directory / record['patch'])], cwd=base, check=True, capture_output=True, timeout=15)
    for row in record['sources']:
        current = (root / row['source']).read_text(encoding='utf-8-sig').encode('utf-8')
        assert (base / row['source']).read_bytes() == current
        assert hashlib.sha256(current).hexdigest() == row['after_sha256']
