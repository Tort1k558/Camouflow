import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'native/drafts/webgpu-projection-cache'
SCRATCH = ROOT / 'native/drafts/webgpu-scratch-reuse'
BASE = ROOT / 'native/drafts/webgpu-capture-retention'


def observation():
    return json.loads((PACKET / 'observations.json').read_bytes())


def test_cache_packet_binds_sources_without_runtime_admission():
    record = observation()
    assert record['compiled'] and record['source_replay_reverse_passed'] and record['resource_guards_passed']
    assert len(record['engine_sources']) == 5
    assert record['base_packet_sha256'] == hashlib.sha256((SCRATCH / 'observations.json').read_bytes()).hexdigest()
    for name, digest in record['public_inputs_sha256'].items():
        assert hashlib.sha256((PACKET / name).read_bytes()).hexdigest() == digest
    for key in ('browser_runtime_verified', 'quota_recovery_verified', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False
    assert len(record['matrix']['cases']) == 54
    assert all(row['passed'] for row in record['matrix']['cases'])
    assert record['retained_failure']['passed'] is False
    assert sum(not row['passed'] for row in record['retained_failure']['cases']) == 3


def test_cache_fixtures_reconstruct_exact_measured_sources(tmp_path):
    record = observation()
    source = tmp_path / 'wire_probe.cc'
    source.write_bytes((BASE / 'wire_probe.cc').read_bytes())
    for patch in (BASE / 'wire-byte-budget.patch', BASE / 'wire-byte-budget-loss-diagnostic.patch',
                  SCRATCH / 'large-capture-fixture.patch', SCRATCH / 'pattern-fixture.patch'):
        subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', str(patch)], cwd=tmp_path, check=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record['shader_fixture']['base_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', str(PACKET / 'shader-consumer-fixture.patch')],
                   cwd=tmp_path, check=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record['shader_fixture']['source_sha256']
    shared = source.read_text(encoding='utf-8')
    patterns = json.loads((SCRATCH / 'pattern-observations.json').read_bytes())
    for variant in record['large_shader_variants']:
        recipe = next(row for row in patterns['variants']
                      if (row['side'], row['format']) == (variant['side'], variant['format']))
        body = shared
        for replacement in recipe['source_replacements']:
            assert body.count(replacement['before']) == 1
            body = body.replace(replacement['before'], replacement['after'], 1)
        assert hashlib.sha256(body.encode('utf-8')).hexdigest() == variant['fixture_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', str(PACKET / 'mutation-fixture.patch')],
                   cwd=tmp_path, check=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record['mutation_fixture_sha256']


def test_cache_mutations_and_negative_controls_are_real_and_bounded():
    record = observation()
    assert len(record['large_shader_variants']) == 4
    for variant in record['large_shader_variants']:
        assert variant['passed'] and len(variant['runs']) == 6
        for row in variant['runs']:
            assert row['passed']
            if row['variant'] == 'after':
                value = row['observation']
                assert value['large_shader_samples_verified'] and value['large_surface_pixels_verified']
                assert value['capture_budget_limit_bytes'] == 67108864
                assert value['capture_bytes_after_destroy'] == 0
    assert len(record['mutation']['runs']) == 12
    for row in record['mutation']['runs']:
        assert row['passed'] and row['returncode'] == 0
        value = row['observation']
        assert value['old_snapshot_unchanged'] and value['new_cpu_reference_matched']
        assert value['new_gpu_reference_matched'] and value['budget_drained_before_device_destroy']
    assert len(record['negative_control']['runs']) == 6
    for row in record['negative_control']['runs']:
        assert row['passed'] and row['returncode'] == 1 and row['stale_gpu_marker_observed']


def test_storage_fixture_reconstructs_the_exact_measured_source(tmp_path):
    record = json.loads((PACKET / 'storage-observations.json').read_bytes())
    source = tmp_path / 'wire_probe.cc'
    source.write_bytes((BASE / 'wire_probe.cc').read_bytes())
    for patch in (BASE / 'wire-byte-budget.patch', BASE / 'wire-byte-budget-loss-diagnostic.patch',
                  SCRATCH / 'large-capture-fixture.patch', SCRATCH / 'pattern-fixture.patch',
                  PACKET / 'shader-consumer-fixture.patch', PACKET / 'mutation-fixture.patch'):
        subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', str(patch)], cwd=tmp_path, check=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record['base_fixture_sha256']
    patch = PACKET / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', str(patch)], cwd=tmp_path, check=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record['source_sha256']


def test_storage_writes_preserve_snapshots_and_detect_stale_gpu_results():
    record = json.loads((PACKET / 'storage-observations.json').read_bytes())
    assert record['passed'] and record['input_postguards_passed']
    assert record['base_packet_sha256'] == hashlib.sha256((PACKET / 'observations.json').read_bytes()).hexdigest()
    assert len(record['runs']) == 27
    assert {(row['variant'], row['mode'], row['attempt']) for row in record['runs']} == {
        (variant, mode, attempt) for variant in ('cached', 'uncached', 'stale')
        for mode in ('--mutation-render', '--mutation-copy', '--mutation-storage') for attempt in (1, 2, 3)
    }
    for row in record['runs']:
        assert row['passed']
        if row['variant'] == 'stale':
            assert row['returncode'] == 1 and row['stale_gpu_marker_observed']
        else:
            assert row['returncode'] == 0
            value = row['observation']
            assert value['old_snapshot_unchanged'] and value['new_cpu_reference_matched']
            assert value['new_gpu_reference_matched'] and value['budget_drained_before_device_destroy']
    for key in ('browser_runtime_verified', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False
