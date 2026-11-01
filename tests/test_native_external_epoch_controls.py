import hashlib
import json
import subprocess
from pathlib import Path

import pytest

PACKET = Path(__file__).resolve().parents[1] / 'native/drafts/webgpu-external-access-cache'


def observations():
    return json.loads((PACKET / 'epoch-resource-observations.json').read_bytes())


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize('variant', ['producer', '1921-rgba', '1921-bgra', '2048-rgba', '2048-bgra'])
def test_epoch_fixture_variants_apply_independently_and_reverse(tmp_path, variant):
    record = observations()
    row = (record['producer_mutation'] if variant == 'producer' else
           next(item for item in record['large_imports'] if f"{item['size']}-{item['format']}" == variant))
    fixture = PACKET / 'wire-import-probe.cc'
    assert sha256(fixture) == record['fixture_base_sha256']
    patch = PACKET / row['patch']
    assert sha256(patch) == row['patch_sha256']
    target = tmp_path / 'wire_probe.cc'
    target.write_bytes(fixture.read_bytes())
    command = ['git', '-c', 'core.autocrlf=false', 'apply']
    subprocess.run([*command, str(patch)], cwd=tmp_path, check=True, capture_output=True, timeout=15)
    assert sha256(target) == row['fixture_sha256']
    subprocess.run([*command, '--reverse', str(patch)], cwd=tmp_path, check=True,
                   capture_output=True, timeout=15)
    assert target.read_bytes() == fixture.read_bytes()


def test_actual_epoch_gpu_negative_controls_and_large_import_scope_are_preserved():
    record = observations()
    assert record['native_forward_reverse_verified'] and record['native_sources_restored'] == 2
    producer = record['producer_mutation']
    assert producer['passed'] and len(producer['runs']) == 3
    for row in producer['runs']:
        assert row['producer_epoch_mutation'] and row['old_cpu_snapshot_immutable']
        assert row['projected_compute_values'] == 64 and row['capture_bytes_after_destroy'] == 0
    negative = record['negative_control']
    assert sha256(PACKET / negative['patch']) == negative['patch_sha256']
    assert negative['passed'] and negative['only_epoch_clear_calls_removed']
    assert len(negative['runs']) == 3
    for row in negative['runs']:
        assert row['returncode'] == 1 and not row['stdout']
        assert 'SHARED_EPOCH_STALE_GPU index=' in row['stderr']
        assert 'E_OUTOFMEMORY' not in row['stderr']
    assert {(row['size'], row['format']) for row in record['large_imports']} == {
        (1921, 'rgba'), (1921, 'bgra'), (2048, 'rgba'), (2048, 'bgra')}
    for row in record['large_imports']:
        assert row['passed'] and row['full_cpu_readback'] and row['spatial_gpu_samples'] == 16
        result = row['observed']
        assert result['large_import_size'] == row['size'] and result['projected_compute_values'] == 16
        assert result['capture_bytes_after_first_map'] <= result['capture_budget_limit_bytes'] == 67108864
        assert result['capture_bytes_after_destroy'] == 0 and not result['browser_integrated']
    assert record['selected'] is record['browser_integrated'] is False
    assert record['privacy_admitted'] is record['production_admitted'] is False


@pytest.mark.parametrize('name', ['single-reader', 'two-readers'])
def test_shared_read_fixtures_apply_to_the_exact_published_import_probe(tmp_path, name):
    packet = PACKET.parent / 'webgpu-shared-read-epoch'
    record = json.loads((packet / 'observations.json').read_bytes())
    row = next(item for item in record['variants'] if item['name'] == name)
    assert sha256(PACKET / 'wire-import-probe.cc') == record['fixture_base_sha256']
    patch = packet / row['patch']
    assert sha256(patch) == row['patch_sha256']
    target = tmp_path / 'wire_probe.cc'
    target.write_bytes((PACKET / 'wire-import-probe.cc').read_bytes())
    command = ['git', '-c', 'core.autocrlf=false', 'apply']
    subprocess.run([*command, str(patch)], cwd=tmp_path, check=True, capture_output=True, timeout=15)
    assert sha256(target) == row['fixture_sha256']
    subprocess.run([*command, '--reverse', str(patch)], cwd=tmp_path, check=True,
                   capture_output=True, timeout=15)
    assert target.read_bytes() == (PACKET / 'wire-import-probe.cc').read_bytes()


def test_shared_read_results_do_not_inherit_exclusive_mutation_or_large_admission():
    packet = PACKET.parent / 'webgpu-shared-read-epoch'
    record = json.loads((packet / 'observations.json').read_bytes())
    previous = json.loads((PACKET / 'observations.json').read_bytes())
    assert record['source_before_sha256'] == previous['changed_sources']['src/dawn/native/d3d12/TextureD3D12.cpp']
    assert sha256(packet / 'next.patch') == record['patch_sha256']
    assert record['compiled_standalone'] and record['internal_control_runs'] == 54
    assert record['native_two_patch_forward_reverse_verified']
    assert record['native_sources_restored'] == 2
    assert len(record['variants']) == 2
    for variant in record['variants']:
        assert len(variant['runs']) == 3
        for row in variant['runs']:
            assert row['passed'] and row['initialized_concurrent_read']
            assert row['projected_compute_values'] == 64 and row['capture_bytes_after_destroy'] == 0
            if variant['name'] == 'two-readers':
                assert row['two_gpu_readers'] and row['writer_excluded_until_both_end']
                assert row['no_access_cache_excluded']
    assert record['remaining_checks']
    assert record['selected'] is record['browser_integrated'] is False
    assert record['privacy_admitted'] is record['production_admitted'] is False
