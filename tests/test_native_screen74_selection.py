import hashlib
import json
from pathlib import Path

import pytest

from scripts import native_build as build
from scripts import verify_native_privacy_units as units


ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'


def test_selected_74_preserves_compiled_73_and_binds_all_five_changes():
    candidate = build.load_candidate('upstream-156')
    record = json.loads((ENV / 'screen74-selection-observations.json').read_bytes())
    before = (candidate['directory'] / 'checkpoints/001-073.json').read_bytes()
    assert hashlib.sha256(before).hexdigest() == record['base_manifest_sha256']
    historical = (candidate['directory'] / 'checkpoints/001-074.json').read_bytes()
    assert hashlib.sha256(historical).hexdigest() == record['selected_manifest_sha256']
    patches = json.loads(historical)['patches']
    assert len(patches) == 74 and patches[:73] == json.loads(before)['patches']
    assert candidate['manifest']['patches'][:74] == patches
    assert patches[-1] == dict(file=record['patch'], sha256=record['patch_sha256'])
    assert len(record['source_paths']) == 5 and record['jobs'] == 4
    assert all(row['before_sha256'] != row['after_sha256'] for row in record['source_paths'])
    assert record['source_preflight']['passed'] and record['source_preflight']['source_unchanged']
    assert all(record[key] is False for key in ('compiled_into_browser', 'native_tests_executed', 'runtime_verified',
                                               'privacy_admitted', 'production_admitted'))


def test_both_native_binaries_require_all_six_cases_without_removing_old_gates(native_units_before_orientation):
    assert units.SUPPORTED_TARGETS[-2:] == ('screen-live-main', 'screen-dispatch')
    assert len(units.SUPPORTED_TARGETS) == 23
    record = json.loads((ENV / 'screen74-selection-observations.json').read_bytes())
    cases = {suite + '.' + name for target in units.LIVE_SCREEN_TESTS
             for suite, names in units.required_tests(target).items() for name in names}
    assert cases == set(record['prepared_cases']) and len(cases) == 6
    assert units.unit_binary_target('screen-live-main') == 'blink_unittests'
    assert units.unit_binary_target('screen-dispatch') == 'content_unittests'
    for target in native_units_before_orientation['namespace']['SUPPORTED_TARGETS']:
        assert units.required_tests(target) == native_units_before_orientation['namespace']['required_tests'](target)


@pytest.mark.parametrize('target', ['screen-live-main', 'screen-dispatch'])
def test_live_screen_gates_reject_missing_compiled_patch_and_implicit_candidate(tmp_path, target):
    with pytest.raises(ValueError, match='exact context'):
        units.require_target_sources(tmp_path, [], target)
    patches = [{'name': name} for name in ('0015-native-browser-context-key-ownership.patch',
        '0016-native-private-key-readiness.patch', '0069-native-logical-screen-inheritance.patch',
        '0073-native-main-screen-exposure.patch', '0074-native-live-screen-updates.patch')]
    assert units.require_target_sources(tmp_path, patches, target) is None
    with pytest.raises(ValueError, match='explicit upstream-156'):
        units.verify(tmp_path, tmp_path / 'report.json', target=target)


def test_full_regression_retains_history_failure_without_claiming_a_runtime_failure():
    record = json.loads((ENV / 'canonical-python74-history-failure-observations.json').read_bytes())
    assert record['passed'] is False and record['measurement_complete'] and record['postguards_passed']
    assert record['counts'] == dict(tests=4577, passed=4575, failures=1, errors=0, skipped=1)
    assert record['failed_tests'] == ['tests.test_native_environment_capture::test_historical_0070_is_exact_prefix_with_strict_gate_not_runtime_admission']
    assert record['native_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
