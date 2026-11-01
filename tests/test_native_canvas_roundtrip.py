import copy
import hashlib
import json
from pathlib import Path
import runpy

import pytest


PACKET = Path(__file__).resolve().parents[1] / 'native/drafts/canvas-roundtrip'
TOOL = runpy.run_path(str(PACKET / 'validate.py'))


def observation():
    return dict(schema=1, passed=True, rows=[dict(name=name, pixels=64, passed=True,
        **{count: 0 for count in TOOL['COUNTS']}) for name in TOOL['CONTEXTS']])


def test_canvas_copy_contract_requires_all_contexts_and_keeps_input_unchanged():
    measured = observation()
    before = copy.deepcopy(measured)
    result = TOOL['validate'](measured)
    assert measured == before and result['measurement_complete'] and result['passed']
    assert result['contexts'] == 5 and result['production_admitted'] is False


@pytest.mark.parametrize('count', TOOL['COUNTS'])
def test_canvas_one_changed_channel_remains_a_failed_exact_match(count):
    measured = observation()
    measured['rows'][0].update({count: 1, 'passed': False})
    measured['passed'] = False
    result = TOOL['validate'](measured)
    assert result['measurement_complete'] and result['passed'] is False


@pytest.mark.parametrize('value', [True, -1, 257, 1.0, None])
def test_canvas_copy_contract_rejects_invalid_counts(value):
    measured = observation()
    measured['rows'][0]['immediateCopyChangedChannels'] = value
    with pytest.raises(ValueError):
        TOOL['validate'](measured)


def test_canvas_worker_failure_is_incomplete_not_an_invented_zero_difference():
    measured = observation()
    measured['rows'][-1] = dict(name='worker-module', passed=False, error='Owned worker deadline')
    measured['passed'] = False
    result = TOOL['validate'](measured)
    assert result['measurement_complete'] is result['passed'] is False


def test_canvas_copy_contract_rejects_contradictory_verdict():
    measured = observation()
    measured['rows'][0]['sourceFillChangedChannels'] = 1
    with pytest.raises(ValueError, match='contradicts'):
        TOOL['validate'](measured)


def test_canvas_roundtrip_measured_record_does_not_hide_colour_changes_behind_copy_stability():
    record = json.loads((PACKET / 'observations.json').read_bytes())
    assert record['measurement_complete'] and record['resources_closed'] and record['fixture_thread_closed']
    assert record['source_core_driver_asset_postguards_passed']
    assert record['probe_sha256'] == hashlib.sha256((PACKET / 'probe.js').read_bytes()).hexdigest()
    assert record['validator_sha256'] == hashlib.sha256((PACKET / 'validate.py').read_bytes()).hexdigest()
    baseline, protected = record['phases']
    assert baseline['name'] == 'baseline' and baseline['passed']
    assert protected['name'] == 'experimental' and protected['passed'] is False
    assert all(row['sourceFillChangedChannels'] == 0 for row in baseline['contexts'])
    assert all(row['sourceFillChangedChannels'] == 101 for row in protected['contexts'])
    for phase in record['phases']:
        assert [row['name'] for row in phase['contexts']] == list(TOOL['CONTEXTS'])
        assert all(row[name] == 0 for row in phase['contexts'] for name in TOOL['COUNTS'][1:])
    for name in ('compatibility_passed', 'known_multicolour_fill_exact_in_experimental', 'tolerance_relaxed',
                 'canvas_policy_repaired', 'privacy_admitted', 'production_admitted'):
        assert record[name] is False


def test_public_site_observations_keep_canvas_and_remaining_automation_signals_visible():
    path = PACKET.parent / 'upstream-156-audio-r8/public-sites-observations.json'
    record = json.loads(path.read_bytes())
    assert record['measurement_complete'] and record['reported_ui_metrics_checked']
    assert record['local_canvas_contract_record_sha256'] == hashlib.sha256((PACKET / 'observations.json').read_bytes()).hexdigest()
    assert [row['mode'] for row in record['observations']] == ['baseline', 'experimental', 'stock']
    baseline, protected, stock = record['observations']
    assert [row['creepjs']['reported_percentages']['headless'] for row in record['observations']] == [100, 0, 100]
    assert all(row['creepjs']['reported_percentages']['like_headless'] == 44 for row in record['observations'])
    assert protected['creepjs']['rgba_noise_percent'] == 14
    assert protected['sannysoft']['webdriver'] == 'missing (passed)'
    assert protected['sannysoft']['scanner_failures'] == []
    assert protected['sannysoft']['scanner_warnings'] == ['VIDEO_CODECS']
    assert baseline['sannysoft']['scanner_failures'] == stock['sannysoft']['scanner_failures'] == ['HEADCHR_UA', 'CHR_MEMORY']
    assert record['headless'] and record['proxy_used'] is False
    for name in ('full_detector_pass', 'repeated_campaign_verified', 'captcha_interacted',
                 'recaptcha_server_score_verified', 'turnstile_verified', 'manager_admission_changed',
                 'canvas_policy_repaired', 'privacy_admitted', 'production_admitted'):
        assert record[name] is False
