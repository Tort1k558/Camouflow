import copy
import hashlib
import json
from pathlib import Path
import runpy

import pytest


ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
FIXTURE = runpy.run_path(str(ENV / 'first-script/nested_hdr.py'))
HDR = runpy.run_path(str(ENV / 'first-script/canvas_hdr.py'))


@pytest.fixture
def observations():
    """Place recorded document controls in synthetic nested worker slots for validator tests."""
    raw = json.loads((ENV / 'canvas-hdr72-observations.json').read_bytes())
    result = []
    for row in raw['runs']:
        document = copy.deepcopy(row['observed'])
        values = [value for value in document if value['kind'] == 'offscreen']
        result.append({'document': document, 'workers': {name: dict(initial=copy.deepcopy(values),
            recreated=copy.deepcopy(values)) for name in FIXTURE['CASES']}})
    return result


def compare(values):
    return FIXTURE['compare_nested_hdr'](*values, HDR['compare_hdr'], FIXTURE['CASES'])


def test_eight_real_nested_cases_and_separate_document_controls(observations):
    before = copy.deepcopy(observations)
    value = compare(observations)
    assert value['passed'] and observations == before
    assert value['worker_cases_per_profile'] == 8 and value['worker_paths_per_profile'] == 4
    assert value['document_contexts_per_profile'] == 4 and value['recreation_samples_per_path'] == 2
    assert not value['document_worker_mismatches']


@pytest.mark.parametrize('fault', ['missing-path', 'unknown-path', 'missing-instance', 'extra-instance',
                                  'missing-color', 'duplicate-color', 'malformed-color', 'html-not-offscreen'])
def test_missing_or_malformed_finite_hdr_coverage_is_rejected(observations, fault):
    rows = observations[1]['workers']
    pair = rows['classic-module']
    if fault == 'missing-path':
        rows.pop('module-classic')
    elif fault == 'unknown-path':
        rows['unknown'] = rows.pop('module-classic')
    elif fault == 'missing-instance':
        pair.pop('recreated')
    elif fault == 'extra-instance':
        pair['unknown'] = copy.deepcopy(pair['initial'])
    elif fault == 'missing-color':
        pair['initial'].pop()
    elif fault == 'duplicate-color':
        pair['initial'][0] = copy.deepcopy(pair['initial'][1])
    elif fault == 'malformed-color':
        pair['initial'][0]['colorSpace'] = []
    else:
        pair['initial'][0]['kind'] = 'html'
    with pytest.raises(ValueError):
        compare(observations)


def test_api_error_is_not_finite_hdr_protection_success(observations):
    observations[1]['workers']['module-classic']['initial'][0]['error'] = {'name': 'NotReadableError'}
    assert not compare(observations)['passed']


def test_different_recreated_pixels_fail_even_with_valid_payloads(observations):
    observations[1]['workers']['module-module']['recreated'] = copy.deepcopy(observations[0]['workers']['module-module']['initial'])
    assert not compare(observations)['passed']


def test_unchanged_baseline_is_not_an_effect_pass(observations):
    assert not compare([observations[0], copy.deepcopy(observations[0])])['passed']


def test_exact_finite_hdr_probe_qualifies_frozen_73_and_binds_public_sources(historical_surface_source_sha256):
    record = json.loads((ENV / 'nested-hdr73-observations.json').read_bytes())
    assert record['probe'] == 'finite-hdr' and record['passed'] and record['postguards_passed']
    assert record['measurement_complete'] and record['comparison']['restart_stable']
    assert record['comparison']['worker_cases_per_profile'] == 8 and len(record['runs']) == 4
    assert record['current_selected_74_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
    for row in record['runs']:
        assert row['worker_recreation_verified'] and row['resources_released']
        assert row['observed_processes'] > 0 and row['remaining_observed_processes'] == 0
    for name, binding in record['source_bindings'].items():
        actual = historical_surface_source_sha256(name, normalized=True)
        assert actual == binding['normalized_utf8_lf_sha256'], name


def test_full_python_storage_repair_pass_precedes_the_new_hdr_probe():
    record = json.loads((ENV / 'canonical-python74-storage-repair-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['counts'] == dict(tests=4594, passed=4593, failures=0, errors=0, skipped=1)
    assert record['native_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False


def test_full_python_with_the_nested_hdr_selector_is_green_without_runtime_admission():
    record = json.loads((ENV / 'canonical-python74-nested-hdr-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['git_head'].startswith('1c9afd2')
    assert record['counts'] == dict(tests=4609, passed=4608, failures=0, errors=0, skipped=1)
    assert record['changed_tracked_files'] == [] and record['before_status'] == record['after_status']
    assert record['native_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
