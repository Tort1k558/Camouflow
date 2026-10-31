import hashlib
import json
from pathlib import Path

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
        assert selected.read_bytes() == (packet.parent / 'next.patch').read_bytes()


def test_resource_candidate_source_preparation_is_not_runtime_admission():
    candidate = build.load_candidate('upstream-156-webgpu-r3')
    proof = json.loads((candidate['directory'] / 'preparation.json').read_bytes())
    assert proof['passed'] and proof['manifest_sha256'] == candidate['manifest_sha256']
    assert proof['forward_patches'] == proof['reverse_patches'] == 120
    assert proof['upstream_files_restored'] == 270
    assert proof['standalone_engine_sources_matched'] == 7
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
