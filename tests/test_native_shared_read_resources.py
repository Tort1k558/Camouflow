import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts import native_build as build

PACKET = Path(__file__).resolve().parents[1] / 'native/drafts/webgpu-shared-read-epoch'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize('name', ['producer-mutation', 'live-device-drain',
                                 '1921-rgba', '1921-bgra', '2048-rgba', '2048-bgra'])
def test_shared_read_resource_fixtures_reconstruct_and_reverse_exact_sources(tmp_path, name):
    record = json.loads((PACKET / 'resource-observations.json').read_bytes())
    baseline = json.loads((PACKET / 'observations.json').read_bytes())
    row = (next(item for item in record['variants'] if item['name'] == name)
           if name in {'producer-mutation', 'live-device-drain'} else
           next(item for item in record['large_imports'] if f"{item['size']}-{item['format']}" == name))
    source = PACKET.parent / 'webgpu-external-access-cache/wire-import-probe.cc'
    target = tmp_path / 'wire_probe.cc'
    target.write_bytes(source.read_bytes())
    base_patch = PACKET / 'single-reader-fixture.patch'
    resource_patch = PACKET / row['patch']
    assert sha256(source) == baseline['fixture_base_sha256']
    assert sha256(resource_patch) == row['patch_sha256']
    command = ['git', '-c', 'core.autocrlf=false', 'apply']
    subprocess.run([*command, str(base_patch)], cwd=tmp_path, check=True, capture_output=True, timeout=15)
    assert sha256(target) == record['fixture_base_sha256']
    subprocess.run([*command, str(resource_patch)], cwd=tmp_path, check=True, capture_output=True, timeout=15)
    assert sha256(target) == row['fixture_sha256']
    subprocess.run([*command, '--reverse', str(resource_patch)], cwd=tmp_path, check=True,
                   capture_output=True, timeout=15)
    assert sha256(target) == record['fixture_base_sha256']
    subprocess.run([*command, '--reverse', str(base_patch)], cwd=tmp_path, check=True,
                   capture_output=True, timeout=15)
    assert target.read_bytes() == source.read_bytes()


def test_shared_read_resource_results_keep_native_and_browser_admission_separate():
    record = json.loads((PACKET / 'resource-observations.json').read_bytes())
    assert {row['name'] for row in record['variants']} == {'producer-mutation', 'live-device-drain'}
    for variant in record['variants']:
        assert variant['passed'] and len(variant['runs']) == 3
        for row in variant['runs']:
            assert row['passed'] and row['initialized_concurrent_read']
            assert row['producer_epoch_mutation'] and row['old_cpu_snapshot_immutable']
            assert row['capture_bytes_after_destroy'] == 0
            if variant['name'] == 'live-device-drain':
                assert row['live_device_budget_drained'] and row['device_usable_after_drain']
                assert row['swapchain_flag_cache_excluded']
    negative = record['negative_control']
    assert negative['passed'] and negative['only_epoch_clear_calls_removed']
    assert sha256(PACKET / negative['patch']) == negative['patch_sha256']
    assert len(negative['runs']) == 3
    for row in negative['runs']:
        assert row['returncode'] == 1 and 'SHARED_EPOCH_STALE_GPU index=' in row['stderr']
        assert 'E_OUTOFMEMORY' not in row['stderr']
    assert {(row['size'], row['format']) for row in record['large_imports']} == {
        (1921, 'rgba'), (1921, 'bgra'), (2048, 'rgba'), (2048, 'bgra')}
    for row in record['large_imports']:
        observed = row['observed']
        assert row['passed'] and row['full_cpu_readback'] and row['spatial_gpu_samples'] == 16
        assert observed['initialized_concurrent_read'] and observed['projected_compute_values'] == 16
        assert observed['capture_bytes_after_first_map'] <= observed['capture_budget_limit_bytes'] == 67108864
        assert observed['capture_bytes_after_destroy'] == 0 and not observed['browser_integrated']
    assert record['selected'] is record['browser_integrated'] is False
    assert record['privacy_admitted'] is record['production_admitted'] is False


def test_access_epoch_candidate_preserves_the_complete_r3_prefix_and_limits():
    before = build.load_candidate('upstream-156-webgpu-r3')
    after = build.load_candidate('upstream-156-webgpu-r4')
    manifest = after['manifest']
    assert manifest['patches'][:120] == before['manifest']['patches']
    assert len(manifest['patches']) == 122 and len(manifest['source_files']) == 270
    for key in ('source_files', 'dependencies', 'build', 'target_revision', 'target_version', 'component_batch'):
        assert manifest[key] == before['manifest'][key]
    assert after['lock']['minimum_free_gib'] == 180 and after['lock']['build_jobs'] == 4
    extension = manifest['extension_batch']
    assert extension['base_candidate'] == before['name']
    assert extension['base_manifest_sha256'] == before['manifest_sha256']
    assert extension['added_patches'] == len(extension['packets']) == 2
    root = PACKET.parents[2]
    for row in extension['packets']:
        source = root / row['packet']
        assert sha256(source) == row['packet_sha256']
        assert sha256(root / row['resource_observations']) == row['resource_observations_sha256']
        assert len(row['patches']) == 1
        assert (after['directory'] / 'patches' / row['patches'][0]).read_bytes() == (source.parent / 'next.patch').read_bytes()


def test_access_epoch_candidate_replay_proof_does_not_admit_a_browser():
    candidate = build.load_candidate('upstream-156-webgpu-r4')
    proof = json.loads((candidate['directory'] / 'preparation.json').read_bytes())
    assert proof['passed'] and proof['manifest_sha256'] == candidate['manifest_sha256']
    assert proof['forward_patches'] == proof['reverse_patches'] == proof['canonical_source_detector_patches'] == 122
    assert proof['canonical_source_detector_passed'] and proof['upstream_files_restored'] == 270
    assert proof['standalone_engine_sources_matched'] == len(proof['engine_sources']) == 7
    assert proof['engine_sources']['src/dawn/native/d3d12/TextureD3D12.cpp'] == (
        json.loads((PACKET / 'observations.json').read_bytes())['source_after_sha256'])
    for record in (proof, candidate['manifest']):
        assert record['compiled'] is record['runtime_verified'] is record['production_admitted'] is False


def test_access_epoch_registration_keeps_previous_tooling_reconstructible(host_sources_before_webgpu_r4):
    assert hashlib.sha256(host_sources_before_webgpu_r4['scripts/native_build.py']).hexdigest() == (
        '3458d158778cb3ea2efedcf83415c3706ef9385e226404dff6c2cf040bfe2c83')
