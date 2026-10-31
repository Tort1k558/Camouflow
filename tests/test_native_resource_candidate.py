import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from scripts import native_build as build

ROOT = Path(__file__).resolve().parents[1]


def test_resource_candidate_preserves_revision_two_and_pinned_build_limits():
    before = build.load_candidate('upstream-156-webgpu-r2')
    after = build.load_candidate('upstream-156-webgpu-r3')
    manifest = after['manifest']
    assert len(manifest['patches']) == 120
    assert manifest['patches'][:118] == before['manifest']['patches']
    assert manifest['source_files'][:268] == before['manifest']['source_files']
    assert len(manifest['source_files']) == 270
    assert {row['path'] for row in manifest['source_files'][268:]} == {
        'third_party/dawn/src/dawn/native/d3d12/TextureD3D12.h',
        'third_party/dawn/src/dawn/native/d3d12/TextureD3D12.cpp',
    }
    for key in ('dependencies', 'build', 'target_revision', 'target_version', 'component_batch'):
        assert manifest[key] == before['manifest'][key]
    assert after['lock']['minimum_free_gib'] == 180 and after['lock']['build_jobs'] == 4
    assert all(row['directory'] == 'third_party/dawn' for row in manifest['patches'][118:])
    assert len(build.expected_candidate_patches(manifest)) == 120


def test_resource_candidate_binds_both_measured_source_packets():
    candidate = build.load_candidate('upstream-156-webgpu-r3')
    extension = candidate['manifest']['extension_batch']
    assert extension['base_candidate'] == 'upstream-156-webgpu-r2'
    assert extension['base_manifest_sha256'] == build.load_candidate('upstream-156-webgpu-r2')['manifest_sha256']
    assert extension['added_patches'] == len(extension['packets']) == 2
    for row in extension['packets']:
        packet = ROOT / row['packet']
        assert hashlib.sha256(packet.read_bytes()).hexdigest() == row['packet_sha256']
        assert len(row['patches']) == 1
        selected = candidate['directory'] / 'patches' / row['patches'][0]
        packaged = selected.read_bytes()
        assert b'diff --git ' in packaged
        assert b''.join(line for line in packaged.splitlines(keepends=True)
                        if not line.startswith(b'diff --git ')) == (packet.parent / 'next.patch').read_bytes()


def test_resource_candidate_source_preparation_is_not_runtime_admission():
    candidate = build.load_candidate('upstream-156-webgpu-r3')
    proof = json.loads((candidate['directory'] / 'preparation.json').read_bytes())
    assert proof['passed'] and proof['manifest_sha256'] == candidate['manifest_sha256']
    assert proof['forward_patches'] == proof['reverse_patches'] == 120
    assert proof['upstream_files_restored'] == 270
    assert proof['standalone_engine_sources_matched'] == 7
    assert proof['canonical_source_detector_passed'] and proof['canonical_source_detector_patches'] == 120
    assert proof['unwrapped_patch_control_rejected']
    for record in (proof, candidate['manifest']):
        for key in ('compiled', 'runtime_verified', 'production_admitted'):
            assert record[key] is False


def test_resource_candidate_shares_checkout_family_not_receipt_identity(tmp_path):
    before = build.load_candidate('upstream-156-webgpu-r2')
    after = build.load_candidate('upstream-156-webgpu-r3')
    build.candidate_workspace(tmp_path, before, claim=True)
    marker = tmp_path / 'glint-build-candidate.json'
    original = marker.read_bytes()
    build.candidate_workspace(tmp_path, after)
    assert marker.read_bytes() == original
    assert after['manifest_sha256'] != before['manifest_sha256']


def test_prior_host_tooling_is_reconstructed_without_rewriting_receipts(host_sources_before_webgpu_r3):
    assert hashlib.sha256(host_sources_before_webgpu_r3['scripts/native_build.py']).hexdigest() == (
        '62c46ec853ed07b796995c9574c45a98a63ab9b944e54db1716945858751f021'
    )


def test_resource_candidate_git_headers_cover_every_changed_file():
    candidate = build.load_candidate('upstream-156-webgpu-r3')
    for row, count in zip(candidate['manifest']['patches'][118:], (2, 5), strict=True):
        lines = (candidate['directory'] / 'patches' / row['file']).read_text(encoding='utf-8').splitlines()
        detected = [line.split(' b/', 1)[1] for line in lines if line.startswith('diff --git ')]
        unified = [line[6:] for line in lines if line.startswith('+++ b/')]
        assert detected == unified and len(detected) == count


def test_actual_source_detector_rejects_unwrapped_new_paths_and_accepts_git_headers(tmp_path):
    source = tmp_path / 'source'
    patches = tmp_path / 'patches'
    source.mkdir()
    patches.mkdir()
    env = {**os.environ, 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1',
           'GIT_OPTIONAL_LOCKS': '0', 'GIT_TERMINAL_PROMPT': '0'}
    env.pop('GIT_INDEX_FILE', None)

    def git(*args):
        return subprocess.check_output(['git', *args], cwd=source, env=env)

    git('init', '--quiet')
    git('config', 'core.autocrlf', 'false')
    (source / 'old.txt').write_bytes(b'before\n')
    (source / 'extra.txt').write_bytes(b'before\n')
    git('add', '--all')
    git('-c', 'commit.gpgsign=false', '-c', 'user.name=Glint fixture',
        '-c', 'user.email=fixture@example.invalid', 'commit', '--quiet', '-m', 'owned baseline')
    first = patches / '0001-existing.patch'
    second = patches / '0002-new-path.patch'
    first.write_bytes(b'diff --git a/old.txt b/old.txt\n--- a/old.txt\n+++ b/old.txt\n@@ -1 +1 @@\n-before\n+after\n')
    plain = b'--- a/extra.txt\n+++ b/extra.txt\n@@ -1 +1 @@\n-before\n+after\n'
    second.write_bytes(plain)
    (source / 'old.txt').write_bytes(b'after\n')
    (source / 'extra.txt').write_bytes(b'after\n')
    names = (first.name, second.name)
    with pytest.raises(ValueError, match='Unrecognized Chromium source changes'):
        build._source_patches(source, env, names, index_dir=tmp_path,
                              patch_directory=patches, complete_chain=True)
    second.write_bytes(b'diff --git a/extra.txt b/extra.txt\n' + plain)
    measured = build._source_patches(source, env, names, index_dir=tmp_path,
                                     patch_directory=patches, complete_chain=True)
    assert measured == [{'name': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                        for path in (first, second)]
