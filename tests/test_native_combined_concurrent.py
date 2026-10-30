import copy
import hashlib
import json
from pathlib import Path
import runpy

import pytest


@pytest.fixture
def concurrent_helpers():
    root = Path(__file__).resolve().parents[1]
    return runpy.run_path(str(root / 'native/drafts/environment/first-script/combined_concurrent.py'))


@pytest.fixture
def cohort():
    rows = []
    for name, mode in (('baseline', None), ('profile-00', 0), ('profile-01', 1)):
        for phase in ('initial', 'restart'):
            row = {'profile': name, 'phase': phase, 'passed': True, 'resources_released': True,
                   'remaining_observed_processes': 0}
            if mode is not None:
                row['audio_reference_selector'] = mode
            rows.append(row)
    return {'passed': True, 'measurement_complete': True, 'postguards_passed': True,
            'both_audio_math_selectors_observed': True, 'protected_profile_count': 2, 'checks': rows,
            'scope': 'Combined native Canvas/WebGL/AudioMath compatibility collector; no privacy admission.'}


def test_concurrent_selector_chooses_distinct_closed_profiles_without_mutating_cohort(concurrent_helpers, cohort):
    before = copy.deepcopy(cohort)
    selected = concurrent_helpers['choose_cohort_profiles'](cohort)
    assert cohort == before and set(selected) == {0, 1}
    assert {row['profile'] for row in selected.values()} == {'profile-00', 'profile-01'}
    assert all(row['phase'] == 'restart' for row in selected.values())


@pytest.mark.parametrize('field', ['passed', 'measurement_complete', 'postguards_passed', 'both_audio_math_selectors_observed'])
def test_concurrent_selector_rejects_incomplete_or_failed_cohort(concurrent_helpers, cohort, field):
    cohort[field] = False
    with pytest.raises(ValueError):
        concurrent_helpers['choose_cohort_profiles'](cohort)


def test_concurrent_selector_does_not_silently_compare_mobile_against_desktop(concurrent_helpers, cohort):
    cohort['scope'] = 'Owned Mobile Web compatibility experiment'
    with pytest.raises(ValueError, match='desktop'):
        concurrent_helpers['choose_cohort_profiles'](cohort)


@pytest.mark.parametrize('path', ['../profile-00', 'D:/external/profile-00', 'profile-99', '', None, []])
def test_concurrent_selector_never_accepts_foreign_profile_paths(concurrent_helpers, cohort, path):
    cohort['checks'][2]['profile'] = path
    with pytest.raises(ValueError):
        concurrent_helpers['choose_cohort_profiles'](cohort)


@pytest.mark.parametrize('kind', ['duplicate', 'missing', 'live', 'boolean-cleanup', 'failed-row', 'changed-mode', 'boolean-mode', 'same-modes'])
def test_concurrent_selector_rejects_ambiguous_or_unsafe_profile_state(concurrent_helpers, cohort, kind):
    rows = cohort['checks']
    if kind == 'duplicate':
        rows[-1] = copy.deepcopy(rows[-2])
    elif kind == 'missing':
        rows.pop()
    elif kind == 'live':
        rows[-1]['remaining_observed_processes'] = 1
    elif kind == 'boolean-cleanup':
        rows[-1]['remaining_observed_processes'] = False
    elif kind == 'failed-row':
        rows[-1]['passed'] = False
    elif kind == 'changed-mode':
        rows[-1]['audio_reference_selector'] = 0
    elif kind == 'boolean-mode':
        rows[-1]['audio_reference_selector'] = True
    else:
        for row in rows[4:]:
            row['audio_reference_selector'] = 0
    with pytest.raises(ValueError):
        concurrent_helpers['choose_cohort_profiles'](cohort)


@pytest.mark.parametrize('version', ('70', '72'))
def test_measured_concurrent_lifecycle_preserves_peer_and_restart_evidence(version):
    root = Path(__file__).resolve().parents[1]
    record = json.loads((root / f'native/drafts/environment/combined-concurrent{version}-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['both_profiles_running'] and record['resources_released'] and record['remaining_observed_processes'] == 0
    assert record['observed_processes'] > 2 and record['concurrent_protected_profiles_verified']
    assert record['mobile_web_verified'] is record['resource_limits_verified'] is record['production_admitted'] is False
    assert record['errors'] == record['asyncio_errors'] == []
    assert {(row['selector'], row['phase']) for row in record['checks']} == {
        (0, 'both-running'), (1, 'both-running'), (1, 'peer-closed-0'),
        (0, 'same-profile-restarted-0'), (0, 'peer-closed-1'), (1, 'same-profile-restarted-1')}
    assert all(row['passed'] and row['context_count'] == 8 and row['canvas_gpu_audio_match_prior_cohort'] for row in record['checks'])
    runner = root / record['public_runner']
    assert hashlib.sha256(runner.read_text(encoding='utf-8-sig').encode()).hexdigest() == record['public_runner_normalized_utf8_lf_sha256']
