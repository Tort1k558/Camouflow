import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'native/drafts/webgpu-scratch-reuse'
BASE = ROOT / 'native/drafts/webgpu-capture-retention'


def observation():
    return json.loads((PACKET / 'observations.json').read_bytes())


def test_scratch_reuse_source_and_scope_are_bound():
    record = observation()
    assert record['compiled'] and record['source_replay_reverse_passed']
    assert record['unchanged_source_postguards_passed']
    for key in ('browser_runtime_verified', 'quota_recovery_verified', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False
    for name, digest in record['public_inputs_sha256'].items():
        assert hashlib.sha256((PACKET / name).read_bytes()).hexdigest() == digest
    assert {row['file'] for row in record['engine_sources']} == {
        'src/dawn/native/d3d12/glint/projected_texture.cc',
        'src/dawn/native/d3d12/GlintEdgeProjectionShader.h',
    }
    matrix = record['matrix']
    assert matrix['passed'] and matrix['case_count'] == len(matrix['cases']) == 54
    assert all(row['passed'] for row in matrix['cases'])


def test_large_capture_fixture_replays_from_public_sources(tmp_path):
    record = observation()['large_capture']
    source = tmp_path / 'wire_probe.cc'
    source.write_bytes((BASE / 'wire_probe.cc').read_bytes())
    for patch in (BASE / 'wire-byte-budget.patch', BASE / 'wire-byte-budget-loss-diagnostic.patch'):
        subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', str(patch)], cwd=tmp_path, check=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record['base_fixture_sha256']
    patch = PACKET / 'large-capture-fixture.patch'
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', str(patch)], cwd=tmp_path, check=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record['fixture_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', str(patch)], cwd=tmp_path, check=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record['base_fixture_sha256']


def test_large_capture_preserves_original_failure_and_quota_limit():
    record = observation()['large_capture']
    assert record['passed']
    assert record['width'] == record['height'] == 2048
    assert record['full_rgba_bytes_verified'] == 2048 * 2048 * 4
    assert len(record['runs']) == 6
    for row in record['runs']:
        assert row['passed']
        if row['variant'] == 'before':
            assert row['returncode'] == 1 and 'observation' not in row
        else:
            assert row['variant'] == 'after' and row['returncode'] == 0
            value = row['observation']
            assert value['large_surface_pixels_verified']
            assert value['capture_budget_limit_bytes'] == 64 * 1024 * 1024
            assert value['per_capture_charge_bytes'] == 50397184
            assert value['retained_captures_before_fault'] == 1
            assert value['capture_bytes_after_destroy'] == 0
            assert value['device_lost_under_capture_budget_pressure']
            assert value['map_status'] == 'aborted'
