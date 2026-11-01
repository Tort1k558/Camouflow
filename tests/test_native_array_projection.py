import hashlib
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / 'native/drafts/webgpu-array-projection'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def observations():
    return json.loads((DRAFT / 'observations.json').read_bytes())


def test_array_projection_source_chain_and_roundtrip(tmp_path):
    record = observations()
    assert record['hardware_projection_passed'] and record['patch_roundtrip_passed']
    assert record['selected'] is record['browser_integrated'] is record['privacy_admitted'] is False
    assert record['production_admitted'] is False
    assert record['capture_budget_limit_bytes'] == 64 * 1024 * 1024
    for name, value in record['source_sha256'].items():
        assert digest(DRAFT / name) == value
    previous = ROOT / 'native/drafts/webgpu-subresource-projection'
    assert digest(previous / 'observations.json') == record['previous_projection_observations_sha256']
    for relative, hashes in record['source_files'].items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((DRAFT / Path(relative).name).read_bytes())
        assert digest(target) == hashes['after_sha256']
        assert digest(previous / Path(relative).name) == hashes['before_sha256']
    for reverse, key in ((True, 'before_sha256'), (False, 'after_sha256')):
        subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', *(['--reverse'] if reverse else []),
                        str(DRAFT / 'next.patch')], cwd=tmp_path, check=True, capture_output=True)
        assert all(digest(tmp_path / path) == value[key] for path, value in record['source_files'].items())


@pytest.mark.parametrize('case,count,assertions', [
    ('arrays', 12, 338090), ('single', 32, 99158), ('fastpath', 8, 19206), ('atomic-positive', 12, 338090)])
def test_array_projection_hardware_controls_have_exact_scope(case, count, assertions):
    row = observations()['cases'][case]
    assert row['passed'] and row['postguards_passed'] and row['hardware_execution_verified']
    assert {run['sanitizer'] for run in row['runs']} == {'none', 'address'}
    for run in row['runs']:
        assert run['compile_returncode'] == run['test_returncode'] == 0
        result = run['result']
        assert result['passed'] and result['hardware_adapter'] and not result['browser_integrated']
        assert result['cases'] == count and result['assertions'] == assertions
        if case in ('arrays', 'atomic-positive'):
            assert result['subresources_per_case'] == 6
            assert result['array_shader_verified'] and result['narrow_views_verified']
            assert result['canonical_bytes_verified'] and result['late_quota_denial_drained']
        assert result['original_unchanged']


@pytest.mark.parametrize('case', ['atomic-positive', 'atomic-negative'])
def test_array_projection_atomicity_patches_reconstruct_measured_sources(tmp_path, case):
    for name in ('projected_texture.cc', 'projected_texture.h', 'shadow_test.cc', 'texture_consumer.hlsl'):
        (tmp_path / name).write_bytes((DRAFT / name).read_bytes())
    for name in (case + '-library.patch', 'atomic-fixture.patch'):
        subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', str(DRAFT / name)],
                       cwd=tmp_path, check=True, capture_output=True)
    measured = observations()['cases'][case]
    assert all(digest(tmp_path / name) == value for name, value in measured['measured_sources_sha256'].items())
    if case == 'atomic-negative':
        assert measured['passed'] and not measured['hardware_execution_verified']
        assert len(measured['runs']) == 1
        assert measured['runs'][0]['test_returncode'] == 23
        assert measured['runs'][0]['expected_rejection_before_gpu_submit']
        fixture = (tmp_path / 'shadow_test.cc').read_text(encoding='utf-8-sig')
        assert fixture.index('PARTIAL_RECORDING_BEFORE_QUOTA_DENIAL') < fixture.index('queue->ExecuteCommandLists')


def test_array_projection_native_flags_failure_and_fix_are_not_runtime_admission():
    record = observations()
    previous = record['earlier_native_target_failure']
    current = record['native_target_syntax']
    assert not previous['passed'] and previous['postguards_passed']
    assert 'exceptions-disabled' in previous['reason']
    assert current['passed'] and current['postguards_passed']
    assert digest(DRAFT / 'check_native.py') == current['checker_sha256']
    assert len(current['runs']) == 2 and all(row['returncode'] == 0 for row in current['runs'])
    source = (DRAFT / 'projected_texture.cc').read_text(encoding='utf-8-sig')
    assert 'try {' not in source and 'catch (' not in source and 'std::vector' not in source
    assert 'new (std::nothrow) std::unique_ptr<Prepared>[count]' in source
    assert 'new (std::nothrow) ID3D12Resource*[count]' in source
    assert len(record['unresolved']) == 4 and len(record['limitations']) == 3
