import copy
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKERS = runpy.run_path(str(ROOT / 'native/drafts/environment/first-script/worker_formats.py'))
EXPORTS = runpy.run_path(str(ROOT / 'native/drafts/environment/first-script/canvas_export.py'))
FIXTURE = runpy.run_path(str(ROOT / 'native/drafts/environment/first-script/worker_exports.py'))


@pytest.fixture
def observations():
    record = json.loads((ROOT / 'native/drafts/environment/canvas-export72-observations.json').read_bytes())
    return tuple({'document': copy.deepcopy(row['observed']),
                  'workers': {name: copy.deepcopy([value for value in row['observed'] if value['kind'] == 'offscreen'])
                              for name in WORKERS['CASES']}} for row in record['runs'])


def validate(*values):
    return FIXTURE['validate_worker_exports'](*values, EXPORTS['validate_exports'], WORKERS['CASES'])


def test_worker_png_validation_reuses_independent_decoder_and_preserves_input(observations):
    before = copy.deepcopy(observations)
    result = validate(*observations)
    assert result['passed'] and observations == before
    assert result['worker_cases_per_profile'] == result['worker_carriers_per_profile'] == 24
    assert result['document_cases_per_profile'] == 8 and result['document_carriers_per_profile'] == 12
    assert not result['document_worker_mismatches'] and len(result['effect']) == 24
    assert all(row['changed_from_baseline'] for row in result['effect'])
    assert result['privacy_admitted'] is result['production_admitted'] is False


@pytest.mark.parametrize('failure', ['missing-class', 'unknown-class', 'missing-case', 'duplicate-case', 'wrong-kind', 'wrong-metadata'])
def test_worker_png_matrix_rejects_missing_or_malformed_data(observations, failure):
    baseline, protected = observations
    rows = protected['workers']['service-module']
    if failure == 'missing-class':
        protected['workers'].pop('dedicated-classic')
    elif failure == 'unknown-class':
        protected['workers']['unknown'] = protected['workers'].pop('dedicated-classic')
    elif failure == 'missing-case':
        rows.pop()
    elif failure == 'duplicate-case':
        rows[0] = copy.deepcopy(rows[1])
    elif failure == 'wrong-kind':
        rows[0]['kind'] = 'html'
    else:
        rows[0]['attributes']['colorType'] = 'unknown'
    with pytest.raises(ValueError):
        validate(baseline, protected)


def test_worker_png_read_error_is_not_a_successful_protection(observations):
    baseline, protected = observations
    protected['workers']['shared-classic'][0]['error'] = {'name': 'NotReadableError'}
    result = validate(baseline, protected)
    assert not result['passed'] and result['document_worker_mismatches']


def test_worker_png_export_of_post_mutation_pixels_fails(observations):
    baseline, protected = observations
    row = protected['workers']['dedicated-module'][0]
    row['before'] = row['after']
    result = validate(baseline, protected)
    assert not result['passed']


def test_worker_png_baseline_pixels_are_not_a_protected_effect(observations):
    baseline, protected = observations
    protected['workers']['service-classic'] = copy.deepcopy(baseline['workers']['service-classic'])
    result = validate(baseline, protected)
    assert not result['passed']
    assert sum(not row['changed_from_baseline'] for row in result['effect']) == 4


def test_empty_worker_set_cannot_silently_pass(observations):
    with pytest.raises(ValueError):
        FIXTURE['validate_worker_exports'](*observations, EXPORTS['validate_exports'], set())


def test_public_worker_png_capture_binds_preserved_72_and_frozen_source_layout():
    record = json.loads((ROOT / 'native/drafts/environment/worker-export72-observations.json').read_bytes())
    build = json.loads((ROOT / 'native/drafts/upstream-156/build72-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['runtime_core_sha256_measured'] == build['runtime_core_sha256_measured']
    assert record['receipt_sha256'] == build['build_receipt_sha256']
    assert record['candidate_manifest_sha256'] == build['candidate_manifest_sha256']
    assert record['current_checkout_manifest_used_for_runtime'] is False
    snapshot = record['runtime_source_snapshot']
    assert snapshot['candidate_manifest_sha256'] == build['candidate_manifest_sha256']
    assert snapshot['git_source'] == '4e838f480ea325c14ea304b130d068c56ef3fa6e'
    assert snapshot['network_clone_performed'] is False and snapshot['tracked_files'] == 909
    assert [row['profile'] for row in record['runs']] == ['baseline', 'protected']
    assert all(row['resources_released'] for row in record['runs'])
    assert validate(*(row['observed'] for row in record['runs'])) == record['comparison']
    assert record['comparison']['passed'] and not record['comparison']['document_worker_mismatches']
    assert record['privacy_admitted'] is record['production_admitted'] is False
    for name, expected in record['public_sources'].items():
        assert hashlib.sha256((ROOT / name).read_text(encoding='utf-8-sig').encode()).hexdigest() == expected


def test_worker_export_help_has_no_browser_or_profile_side_effects(tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / 'native/drafts/environment/first-script/worker_exports_runtime.py'), '--help'],
                            cwd=tmp_path, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0 and '--cohort-directory' in result.stdout
    assert list(tmp_path.iterdir()) == []
