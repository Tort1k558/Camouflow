import copy
import hashlib
import json
from pathlib import Path
import runpy
import subprocess

import pytest


@pytest.fixture
def format_helpers():
    root = Path(__file__).resolve().parents[1]
    return runpy.run_path(str(root / 'native/drafts/environment/first-script/canvas_formats.py'))


@pytest.fixture
def format_observations(format_helpers):
    def build(digest):
        rows = []
        for key in sorted(format_helpers['CASE_KEYS']):
            row = dict(zip(format_helpers['FIELDS'], key))
            floating = row['pixelFormat'] == 'rgba-float16'
            row['observed'] = {'arrayType': 'Float16Array' if floating else 'Uint8ClampedArray',
                'length': 1024, 'bytes': 2048 if floating else 1024, 'colorSpace': row['readColorSpace'],
                'pixelFormat': row['pixelFormat'], 'finite': True, 'hash': digest, 'repeat': digest}
            rows.append(row)
        return {'rows': rows, 'float16Available': True}
    return build('a' * 64), build('b' * 64)


def test_all_format_cases_require_compatibility_and_a_real_effect(format_helpers, format_observations):
    before = copy.deepcopy(format_observations)
    result = format_helpers['compare_formats'](*format_observations)
    assert format_observations == before
    assert result['cases'] == result['baseline_supported'] == result['protected_supported'] == 32
    assert result['compatibility_passed'] and result['protection_effect_observed']


def test_unsupported_protected_format_is_a_regression_not_a_successful_block(format_helpers, format_observations):
    baseline, protected = format_observations
    protected['rows'][0].pop('observed')
    protected['rows'][0]['error'] = {'name': 'NotReadableError', 'message': 'candidate format unavailable'}
    result = format_helpers['compare_formats'](baseline, protected)
    assert result['protected_supported'] == 31 and len(result['compatibility_regressions']) == 1
    assert not result['compatibility_passed'] and not result['protection_effect_observed']


def test_unchanged_native_pixels_do_not_pass_as_protection(format_helpers, format_observations):
    baseline, protected = format_observations
    protected['rows'][0]['observed'] = copy.deepcopy(baseline['rows'][0]['observed'])
    result = format_helpers['compare_formats'](baseline, protected)
    assert result['compatibility_passed'] and not result['protection_effect_observed']
    assert len(result['no_effect']) == 1


@pytest.mark.parametrize('field,value', [('arrayType', 'Uint16Array'), ('length', 1000), ('bytes', 10),
                                        ('finite', False), ('repeat', 'c' * 64), ('colorSpace', 'unknown')])
def test_format_shape_and_repeated_bytes_are_not_ignored(format_helpers, format_observations, field, value):
    baseline, protected = format_observations
    protected['rows'][0]['observed'][field] = value
    result = format_helpers['compare_formats'](baseline, protected)
    assert not result['compatibility_passed']


@pytest.mark.parametrize('kind', ['missing', 'duplicate', 'unknown', 'malformed'])
def test_format_matrix_cannot_silently_skip_cases(format_helpers, format_observations, kind):
    baseline, protected = format_observations
    if kind == 'missing':
        protected['rows'].pop()
    elif kind == 'duplicate':
        protected['rows'][-1] = copy.deepcopy(protected['rows'][0])
    elif kind == 'unknown':
        protected['rows'][0]['colorType'] = 'unknown'
    else:
        protected['rows'][0]['kind'] = []
    with pytest.raises(ValueError):
        format_helpers['compare_formats'](baseline, protected)


def test_measured_canvas_failure_is_retained_and_binds_the_public_runner(format_helpers):
    root = Path(__file__).resolve().parents[1]
    record = json.loads((root / 'native/drafts/environment/canvas-formats70-observations.json').read_bytes())
    assert record['passed'] is False and record['measurement_complete'] and record['postguards_passed']
    assert record['native_fix_implemented'] is record['native_fix_compiled'] is record['production_admitted'] is False
    assert format_helpers['compare_formats'](*(run['observed'] for run in record['runs'])) == record['comparison']
    assert record['comparison']['baseline_supported'] == 32 and record['comparison']['protected_supported'] == 2
    assert len(record['comparison']['compatibility_regressions']) == 30
    runner = root / record['public_runner']
    assert hashlib.sha256(runner.read_text(encoding='utf-8-sig').encode()).hexdigest() == record['public_runner_normalized_utf8_lf_sha256']


def test_compiled_72_formats_close_the_measured_compatibility_regression(format_helpers):
    root = Path(__file__).resolve().parents[1]
    record = json.loads((root / 'native/drafts/environment/canvas-formats72-observations.json').read_bytes())
    build = json.loads((root / 'native/drafts/upstream-156/build72-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['native_fix_implemented'] and record['native_fix_compiled']
    assert record['privacy_admitted'] is record['production_admitted'] is False
    assert record['runtime_core_sha256_measured'] == build['runtime_core_sha256_measured']
    assert record['receipt_sha256'] == build['build_receipt_sha256']
    assert record['candidate_manifest_sha256'] == build['candidate_manifest_sha256']
    assert format_helpers['compare_formats'](*(row['observed'] for row in record['runs'])) == record['comparison']
    comparison = record['comparison']
    assert comparison['cases'] == comparison['baseline_supported'] == comparison['protected_supported'] == 32
    assert comparison['compatibility_passed'] and comparison['protection_effect_observed']
    assert not comparison['baseline_unavailable'] and not comparison['compatibility_regressions'] and not comparison['no_effect']
    runner = root / record['public_runner']
    assert hashlib.sha256(runner.read_text(encoding='utf-8-sig').encode()).hexdigest() == record['public_runner_normalized_utf8_lf_sha256']


@pytest.mark.parametrize('version', ('70', '72'))
def test_mobile_patch_reconstructs_the_measured_portable_variant(tmp_path, version):
    root = Path(__file__).resolve().parents[1]
    environment = root / 'native/drafts/environment'
    record = json.loads((environment / f'combined-mobile{version}-observations.json').read_bytes())
    relative = Path('scripts/verify_native_combined_math.py')
    assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == record['base_source_sha256']
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_bytes((root / relative).read_bytes())
    patch = environment / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error', str(patch)],
                   cwd=tmp_path, capture_output=True, check=True, timeout=15)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == record['prepared_portable_source_sha256']
    compile(target.read_text(encoding='utf-8'), str(target), 'exec')
    assert record['passed'] and record['protected_profile_count'] == 8 and len(record['checks']) == 18
    assert record['both_audio_math_selectors_observed'] and record['real_android_ios_verified'] is False
    for row in record['checks']:
        values = row['environment_observed']
        assert (values['width'], values['height'], values['dpr']) == (390, 844, 3) and values['touch'] >= 1
        assert row['passed'] and row['resources_released'] and row['remaining_observed_processes'] == 0


def test_mobile_72_timeout_is_retained_without_calling_it_a_policy_failure():
    root = Path(__file__).resolve().parents[1]
    record = json.loads((root / 'native/drafts/environment/combined-mobile72-timeout-observations.json').read_bytes())
    assert record['passed'] is False and record['measurement_complete'] is False and record['postguards_passed']
    assert record['completed_phases'] == 0 and record['failed_profile'] == 'baseline'
    assert record['failed_phase'] == 'initial'
    assert record['measured_protected_policy_failure'] is record['owned_process_cleanup_verified'] is False
    assert record['automatic_retry_performed'] is record['production_admitted'] is False
    assert record['observation_after_failure']['disk_D_queue_length'] == 249
