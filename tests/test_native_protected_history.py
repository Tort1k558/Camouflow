import copy
import hashlib
import json
from pathlib import Path
import runpy

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'native/drafts/environment/first-script'
HISTORY = runpy.run_path(str(FIXTURE / 'protected_history.py'))
SCREEN = runpy.run_path(str(FIXTURE / 'lifecycle.py'))
FORMATS = runpy.run_path(str(FIXTURE / 'canvas_formats.py'))


@pytest.fixture
def runs():
    canvas = {'float16Available': True, 'rows': []}
    for kind, color, storage, read_color, pixel_format in sorted(FORMATS['CASE_KEYS']):
        canvas['rows'].append(dict(kind=kind, colorSpace=color, colorType=storage,
            readColorSpace=read_color, pixelFormat=pixel_format, observed=dict(
                arrayType='Float16Array' if pixel_format == 'rgba-float16' else 'Uint8ClampedArray',
                length=1024, bytes=2048 if pixel_format == 'rgba-float16' else 1024,
                colorSpace=read_color, pixelFormat=pixel_format, finite=True, hash='a' * 64, repeat='a' * 64)))
    result = []
    for mode, (width, height, dpr, orientation) in HISTORY['EXPECTED'].items():
        screen = dict(width=width, height=height, availWidth=width, availHeight=height,
            availLeft=0, availTop=0, dpr=dpr, colorDepth=24, pixelDepth=24,
            orientation=dict(type=orientation, angle=0))
        documents = {role: dict(snapshot=dict(screen=copy.deepcopy(screen),
            viewport=dict(width=320, height=140), media=dict(width=True, height=True, resolution=True)),
            embedding_size=dict(width=320, height=140)) for role in SCREEN['ROLES']}
        result.append(dict(mode=mode, passed=True, protected_arguments_verified=True,
            bfcache_restored=True, browser_connection_closed=True, runtime_resources_released=True,
            canvas_stable_across_bfcache=True, observed_processes=12, remaining_observed_processes=0,
            history_navigation=dict(type='BackForwardCacheRestore'),
            canvas_before=copy.deepcopy(canvas), canvas_after=copy.deepcopy(canvas),
            phases=[dict(phase=name, observed=copy.deepcopy(documents), errors=[]) for name in HISTORY['PHASES']]))
    return result


def validate(runs):
    return HISTORY['validate_runs'](runs, SCREEN['validate_page'], FORMATS['compare_formats'])


def test_complete_matrix_has_both_requested_manager_modes_and_bounded_canvas(runs):
    before = copy.deepcopy(runs)
    result = validate(runs)
    assert result['passed'] and runs == before
    assert all(row['screen_phases'] == 6 and row['canvas_cases'] == 32 for row in result['runs'])
    assert result['privacy_admitted'] is result['production_admitted'] is False


@pytest.mark.parametrize('flag', ['protected_arguments_verified', 'bfcache_restored',
    'browser_connection_closed', 'runtime_resources_released', 'canvas_stable_across_bfcache'])
def test_unverified_runtime_or_history_is_not_a_pass(runs, flag):
    runs[0][flag] = False
    assert not validate(runs)['passed']


@pytest.mark.parametrize('fault', ['missing-mode', 'duplicate-mode', 'missing-phase', 'malformed-phase'])
def test_missing_or_malformed_coverage_is_rejected(runs, fault):
    if fault == 'missing-mode':
        runs.pop()
    elif fault == 'duplicate-mode':
        runs[1] = copy.deepcopy(runs[0])
    elif fault == 'missing-phase':
        runs[0]['phases'].pop()
    else:
        runs[0]['phases'][0] = None
    with pytest.raises(ValueError):
        validate(runs)


def test_consistently_wrong_screen_is_not_accepted_as_its_own_baseline(runs):
    for phase in runs[1]['phases']:
        for document in phase['observed'].values():
            document['snapshot']['screen']['width'] = 800
    assert not validate(runs)['passed']


@pytest.mark.parametrize('fault', ['changed', 'unavailable', 'not-finite', 'missing', 'leak', 'no-processes', 'reload'])
def test_stability_flags_cannot_override_bad_pixels_cleanup_or_navigation(runs, fault):
    row = runs[0]
    if fault == 'changed':
        row['canvas_after']['rows'][0]['observed'].update(hash='b' * 64, repeat='b' * 64)
    elif fault == 'unavailable':
        for name in ('canvas_before', 'canvas_after'):
            row[name]['rows'][0]['observed'] = None
    elif fault == 'not-finite':
        row['canvas_after']['rows'][0]['observed']['finite'] = False
    elif fault == 'missing':
        row['canvas_after']['rows'].pop()
        with pytest.raises(ValueError):
            validate(runs)
        return
    elif fault == 'leak':
        row['remaining_observed_processes'] = 1
    elif fault == 'no-processes':
        row['observed_processes'] = 0
    else:
        row['history_navigation']['type'] = 'Navigation'
    assert not validate(runs)['passed']


def test_public_browser_probe_binds_exact_sources_and_revalidates_actual_observations(protected_runtime_before_surfaces_sha256):
    record = json.loads((ROOT / 'native/drafts/environment/protected-history73-observations.json').read_bytes())
    build = json.loads((ROOT / 'native/drafts/upstream-156/build73-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['runtime_core_sha256_measured'] == build['runtime_core_sha256_measured']
    assert record['receipt_sha256'] == build['build_receipt_sha256']
    assert validate(record['runs']) == record['validation']
    for relative, expected in record['measured_inputs_sha256'].items():
        measured = (protected_runtime_before_surfaces_sha256
                    if relative == 'native/drafts/environment/first-script/protected_history_runtime.py'
                    else hashlib.sha256((ROOT / relative).read_bytes()).hexdigest())
        assert measured == expected, relative
    assert record['privacy_admitted'] is record['production_admitted'] is False
