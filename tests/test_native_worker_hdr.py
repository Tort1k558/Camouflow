import base64
import copy
import json
from pathlib import Path
import runpy
import struct

import pytest


ROOT = Path(__file__).resolve().parents[1]
HDR = runpy.run_path(str(ROOT / 'native/drafts/environment/first-script/canvas_hdr.py'))
WORKERS = runpy.run_path(str(ROOT / 'native/drafts/environment/first-script/worker_formats.py'))
FIXTURE = runpy.run_path(str(ROOT / 'native/drafts/environment/first-script/worker_hdr.py'))


@pytest.fixture
def observations():
    record = json.loads((ROOT / 'native/drafts/environment/canvas-hdr72-observations.json').read_bytes())
    return tuple({'document': copy.deepcopy(row['observed']),
        'workers': {name: copy.deepcopy([value for value in row['observed'] if value['kind'] == 'offscreen'])
                    for name in WORKERS['CASES']}} for row in record['runs'])


def compare(*values):
    return FIXTURE['compare_worker_hdr'](*values, HDR['compare_hdr'], WORKERS['CASES'])


def replace_full(row, raw):
    value = base64.b64encode(raw).decode()
    row['full'] = row['repeat'] = row['afterReput'] = value
    row['crop'] = base64.b64encode(b''.join(raw[(y*16+3)*8:(y*16+12)*8] for y in range(4, 11))).decode()


def test_complete_worker_fidelity_matrix_preserves_input_and_has_twelve_real_contexts(observations):
    before = copy.deepcopy(observations)
    result = compare(*observations)
    assert result['passed'] and observations == before
    assert result['worker_contexts_per_profile'] == 12 and result['document_contexts_per_profile'] == 4
    assert not result['document_worker_mismatches']
    assert result['privacy_admitted'] is result['production_admitted'] is False


@pytest.mark.parametrize('fault', ['missing-worker', 'unknown-worker', 'missing-context', 'duplicate-context', 'wrong-kind', 'malformed-color'])
def test_worker_matrix_never_silently_skips_missing_or_malformed_cases(observations, fault):
    baseline, protected = observations
    rows = protected['workers']['service-module']
    if fault == 'missing-worker':
        protected['workers'].pop('dedicated-classic')
    elif fault == 'unknown-worker':
        protected['workers']['unknown'] = protected['workers'].pop('dedicated-classic')
    elif fault == 'missing-context':
        rows.pop()
    elif fault == 'duplicate-context':
        rows[0] = copy.deepcopy(rows[1])
    elif fault == 'wrong-kind':
        rows[0]['kind'] = 'html'
    else:
        rows[0]['colorSpace'] = []
    with pytest.raises(ValueError):
        compare(baseline, protected)


def test_individually_bounded_but_different_worker_output_fails_context_coherence(observations):
    baseline, protected = observations
    row = protected['workers']['shared-module'][0]
    words = list(struct.unpack('<1024H', base64.b64decode(row['full'])))
    exponent = (words[512] & 0x7c00) >> 10
    assert 0 < exponent < 31
    words[512] ^= 1 << min(9, max(0, 17 - exponent))
    replace_full(row, struct.pack('<1024H', *words))
    result = compare(baseline, protected)
    assert result['worker_results_with_document_html_controls']['shared-module']['passed']
    assert not result['passed'] and result['document_worker_mismatches']


def test_worker_alpha_change_fails_fidelity(observations):
    baseline, protected = observations
    row = protected['workers']['dedicated-module'][0]
    words = list(struct.unpack('<1024H', base64.b64decode(row['full'])))
    words[515] ^= 1
    replace_full(row, struct.pack('<1024H', *words))
    result = compare(baseline, protected)
    assert not result['passed']
    assert not result['worker_results_with_document_html_controls']['dedicated-module']['passed']


def test_worker_api_error_is_not_protection_success(observations):
    baseline, protected = observations
    protected['workers']['service-classic'][0]['error'] = {'name': 'NotReadableError'}
    result = compare(baseline, protected)
    assert not result['passed']
    assert result['worker_results_with_document_html_controls']['service-classic']['protected_errors']


def test_unchanged_worker_pixels_fail_the_effect_gate(observations):
    baseline, protected = observations
    protected['workers']['service-module'] = copy.deepcopy(baseline['workers']['service-module'])
    result = compare(baseline, protected)
    assert not result['passed'] and not result['worker_results_with_document_html_controls']['service-module']['passed']


def test_empty_worker_set_is_rejected(observations):
    with pytest.raises(ValueError):
        FIXTURE['compare_worker_hdr'](*observations, HDR['compare_hdr'], set())
