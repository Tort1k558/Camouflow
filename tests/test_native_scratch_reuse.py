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


def test_pattern_variants_reconstruct_the_exact_measured_sources(tmp_path):
    record = json.loads((PACKET / 'pattern-observations.json').read_bytes())
    source = tmp_path / 'wire_probe.cc'
    source.write_bytes((BASE / 'wire_probe.cc').read_bytes())
    for patch in (BASE / 'wire-byte-budget.patch', BASE / 'wire-byte-budget-loss-diagnostic.patch',
                  PACKET / 'large-capture-fixture.patch'):
        subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', str(patch)], cwd=tmp_path, check=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record['base_fixture_sha256']
    patch = PACKET / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', str(patch)], cwd=tmp_path, check=True)
    shared = source.read_text(encoding='utf-8')
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record['shared_fixture_sha256']
    for variant in record['variants']:
        body = shared
        for replacement in variant['source_replacements']:
            assert body.count(replacement['before']) == 1
            body = body.replace(replacement['before'], replacement['after'], 1)
        assert hashlib.sha256(body.encode('utf-8')).hexdigest() == variant['source_sha256']


def test_pattern_results_cover_padding_formats_and_keep_failed_attempts():
    record = json.loads((PACKET / 'pattern-observations.json').read_bytes())
    assert record['passed'] and record['input_postguards_passed']
    for key in ('browser_runtime_verified', 'quota_recovery_verified', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False
    assert {(row['side'], row['format']) for row in record['variants']} == {
        (1921, 'rgba'), (1921, 'bgra'), (2048, 'rgba'), (2048, 'bgra'),
    }
    assert len(record['variants']) == 4
    for variant in record['variants']:
        side = variant['side']
        assert variant['row_pitch'] == (side * 4 + 255) & ~255
        assert variant['full_pixel_bytes_verified'] == side * side * 4
        assert variant['padding_checked_zero'] == (side == 1921)
        assert len(variant['runs']) == 6 and all(row['passed'] for row in variant['runs'])
        after = [row for row in variant['runs'] if row['variant'] == 'after']
        assert len(after) == 3
        for row in after:
            value = row['observation']
            assert row['returncode'] == 0 and value['large_surface_pixels_verified']
            assert value['per_capture_charge_bytes'] == (62193664 if side == 1921 else 50397184)
            assert value['capture_budget_limit_bytes'] == 67108864
            assert value['capture_bytes_after_destroy'] == 0
    assert len(record['earlier_attempts']) == 2
    assert all(row['passed'] is False for row in record['earlier_attempts'])
