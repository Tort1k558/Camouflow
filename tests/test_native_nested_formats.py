import copy
import hashlib
import json
from pathlib import Path
import runpy
import threading
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from scripts import verify_native_surfaces as surfaces


ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'native/drafts/environment/first-script'
FIXTURE = runpy.run_path(str(HERE / 'nested_formats.py'))
CANVAS = runpy.run_path(str(HERE / 'canvas_formats.py'))


@pytest.fixture
def observations():
    result = []
    for signature in ('a' * 64, 'b' * 64):
        rows = []
        for kind, color, storage, read_color, pixel_format in sorted(CANVAS['CASE_KEYS']):
            rows.append(dict(kind=kind, colorSpace=color, colorType=storage,
                readColorSpace=read_color, pixelFormat=pixel_format, observed=dict(
                    arrayType='Float16Array' if pixel_format == 'rgba-float16' else 'Uint8ClampedArray',
                    length=1024, bytes=2048 if pixel_format == 'rgba-float16' else 1024,
                    colorSpace=read_color, pixelFormat=pixel_format, finite=True, hash=signature, repeat=signature)))
        worker = {'float16Available': True, 'rows': [row for row in rows if row['kind'] == 'offscreen']}
        result.append(dict(document={'float16Available': True, 'rows': rows}, workers={name:
            dict(initial=copy.deepcopy(worker), recreated=copy.deepcopy(worker)) for name in FIXTURE['CASES']}))
    return result


def compare(rows):
    return FIXTURE['compare_nested_formats'](*rows, CANVAS['compare_formats'], FIXTURE['CASES'])


def test_complete_nested_matrix_counts_cases_not_contexts(observations):
    before = copy.deepcopy(observations)
    value = compare(observations)
    assert value['passed'] and observations == before
    assert value['worker_cases_per_profile'] == 64 and value['worker_paths_per_profile'] == 4
    assert value['recreation_samples_per_path'] == 2
    assert not value['document_worker_mismatches']


@pytest.mark.parametrize('fault', ['missing-path', 'unknown-path', 'missing-instance', 'extra-instance',
                                  'missing-case', 'duplicate-case', 'malformed-rows'])
def test_incomplete_nested_matrix_is_not_silently_counted(observations, fault):
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
    elif fault == 'missing-case':
        pair['initial']['rows'].pop()
    elif fault == 'duplicate-case':
        pair['initial']['rows'][0] = copy.deepcopy(pair['initial']['rows'][1])
    else:
        pair['initial']['rows'] = None
    with pytest.raises(ValueError):
        compare(observations)


def test_recreated_worker_with_changed_pixels_fails_even_when_reads_are_stable(observations):
    value = observations[1]['workers']['module-module']['recreated']['rows'][0]['observed']
    value['hash'] = value['repeat'] = 'c' * 64
    assert not compare(observations)['passed']


def test_api_rejection_is_not_protection_success(observations):
    observations[1]['workers']['module-classic']['initial']['rows'][0]['observed'] = None
    assert not compare(observations)['passed']


def test_no_protection_effect_is_not_a_pass(observations):
    assert not compare([observations[0], copy.deepcopy(observations[0])])['passed']


def test_owned_server_initializes_existing_fixture_state_and_serves_real_worker_types():
    server = FIXTURE['server_type'](surfaces, FIXTURE['worker_read'](CANVAS['READ']))(('127.0.0.1', 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        assert server.proxy_mode is False
        base = f'http://127.0.0.1:{server.server_port}'
        for parent in ('classic', 'module'):
            for child in ('classic', 'module'):
                for role, script_type in (('parent', parent), ('leaf', child)):
                    with urlopen(base + f'/owned-nested-{role}.js?parent={parent}&child={child}', timeout=3) as response:
                        body = response.read().decode('utf-8')
                        assert response.headers['Content-Type'] == 'application/javascript'
                    assert body.startswith('export {};') is (script_type == 'module')
                    assert ('new Worker(' if role == 'parent' else 'OffscreenCanvas') in body
        with pytest.raises(HTTPError) as error:
            urlopen(base + '/owned-nested-parent.js?parent=unknown&child=classic', timeout=3)
        assert error.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    assert not thread.is_alive()


def test_exact_public_probe_qualifies_frozen_73_not_selected_74():
    record = json.loads((ROOT / 'native/drafts/environment/nested-formats73-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['comparison']['restart_stable'] and record['comparison']['worker_cases_per_profile'] == 64
    assert record['comparison']['worker_paths_per_profile'] == 4
    assert record['source_layout']['manifest_checkpoint'] == '001-073'
    assert record['current_selected_74_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
    assert len(record['runs']) == 4
    for row in record['runs']:
        assert row['worker_recreation_verified'] and row['resources_released']
        assert row['observed_processes'] > 0 and row['remaining_observed_processes'] == 0
    for name, binding in record['source_bindings'].items():
        actual = hashlib.sha256((ROOT / name).read_text(encoding='utf-8-sig').encode('utf-8')).hexdigest()
        assert actual == binding['normalized_utf8_lf_sha256'], name
    assert record['runs'][0]['observations_sha256'] == record['runs'][2]['observations_sha256']
    assert record['runs'][1]['observations_sha256'] == record['runs'][3]['observations_sha256']
