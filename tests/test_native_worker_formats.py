import copy
import hashlib
import json
from pathlib import Path
import runpy

import pytest


ROOT = Path(__file__).resolve().parents[1]
FORMATS = runpy.run_path(str(ROOT / 'native/drafts/environment/first-script/canvas_formats.py'))
WORKERS = runpy.run_path(str(ROOT / 'native/drafts/environment/first-script/worker_formats.py'))


@pytest.fixture
def matrices():
    def matrix(digest):
        rows = []
        for case in sorted(FORMATS['CASE_KEYS']):
            row = dict(zip(FORMATS['FIELDS'], case))
            pixel_format = row['pixelFormat']
            row['observed'] = {'arrayType': 'Float16Array' if pixel_format == 'rgba-float16' else 'Uint8ClampedArray',
                'length': 1024, 'bytes': 2048 if pixel_format == 'rgba-float16' else 1024,
                'colorSpace': row['readColorSpace'], 'pixelFormat': pixel_format, 'finite': True,
                'hash': digest, 'repeat': digest}
            rows.append(row)
        return {'document': {'rows': rows},
                'workers': {name: {'rows': copy.deepcopy([row for row in rows if row['kind'] == 'offscreen'])}
                            for name in WORKERS['CASES']}}
    return matrix('a' * 64), matrix('b' * 64)


def compare(*values):
    return WORKERS['compare_worker_formats'](*values, FORMATS['compare_formats'])


def test_all_six_worker_classes_match_documents_and_isolate_profile(matrices):
    before = copy.deepcopy(matrices)
    result = compare(*matrices)
    assert result['cases'] == result['baseline_supported'] == result['protected_supported'] == 96
    assert result['compatibility_passed'] and result['protection_effect_observed']
    assert result['document_comparison']['cases'] == 32
    assert not result['document_worker_mismatches'] and not result['no_effect']
    assert matrices == before


@pytest.mark.parametrize('failure', ['missing-worker', 'unknown-worker', 'missing-document', 'wrong-kind', 'duplicate-format'])
def test_missing_or_malformed_cases_are_never_silently_skipped(matrices, failure):
    baseline, protected = matrices
    worker = protected['workers']['dedicated-classic']['rows']
    if failure == 'missing-worker':
        protected['workers'].pop('service-module')
    elif failure == 'unknown-worker':
        protected['workers']['other'] = protected['workers'].pop('service-module')
    elif failure == 'missing-document':
        protected['document']['rows'].pop()
    elif failure == 'wrong-kind':
        worker[0]['kind'] = 'html'
    else:
        worker[0] = copy.deepcopy(worker[1])
    with pytest.raises(ValueError):
        compare(baseline, protected)


def test_stable_but_different_worker_identity_does_not_pass(matrices):
    baseline, protected = matrices
    row = protected['workers']['shared-module']['rows'][0]['observed']
    row['hash'] = row['repeat'] = 'c' * 64
    result = compare(baseline, protected)
    assert result['compatibility_passed'] and not result['protection_effect_observed']
    assert result['document_worker_mismatches']


def test_native_read_error_is_compatibility_failure_not_protection(matrices):
    baseline, protected = matrices
    row = protected['workers']['service-classic']['rows'][0]
    row.pop('observed')
    row['error'] = {'name': 'NotReadableError'}
    result = compare(baseline, protected)
    assert result['protected_supported'] == 95 and len(result['compatibility_regressions']) == 1
    assert not result['compatibility_passed'] and not result['protection_effect_observed']


def test_unchanged_worker_is_not_mistaken_for_protection(matrices):
    baseline, protected = matrices
    protected['workers']['service-module'] = copy.deepcopy(baseline['workers']['service-module'])
    result = compare(baseline, protected)
    assert result['compatibility_passed'] and not result['protection_effect_observed']
    assert len(result['no_effect']) == 16


def test_actual_public_worker_matrix_binds_sources_without_broad_admission():
    record = json.loads((ROOT / 'native/drafts/environment/worker-formats72-observations.json').read_bytes())
    build = json.loads((ROOT / 'native/drafts/upstream-156/build72-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['runtime_core_sha256_measured'] == build['runtime_core_sha256_measured']
    assert record['receipt_sha256'] == build['build_receipt_sha256']
    assert record['candidate_manifest_sha256'] == build['candidate_manifest_sha256']
    assert record['privacy_admitted'] is record['production_admitted'] is False
    assert set(record['worker_classes']) == WORKERS['CASES']
    assert [row['profile'] for row in record['runs']] == ['baseline', 'protected']
    assert all(row['resources_released'] for row in record['runs'])
    assert compare(*(row['observed'] for row in record['runs'])) == record['comparison']
    result = record['comparison']
    assert result['cases'] == result['baseline_supported'] == result['protected_supported'] == 96
    assert not result['document_worker_mismatches']
    assert result['document_comparison']['cases'] == 32
    for name, expected in record['public_sources'].items():
        assert hashlib.sha256((ROOT / name).read_text(encoding='utf-8-sig').encode()).hexdigest() == expected
