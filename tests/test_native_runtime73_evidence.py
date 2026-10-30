import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'native/drafts/environment'
GATES = ('combined-math', 'canvas-formats', 'canvas-export', 'worker-formats',
         'worker-export', 'canvas-hdr', 'worker-hdr', 'combined-concurrent')


@pytest.mark.parametrize('gate', GATES)
def test_completed_runtime_gate_binds_compiled_73_and_current_probe_sources(gate):
    record = json.loads((EVIDENCE / f'{gate}73-observations.json').read_bytes())
    build = json.loads((ROOT / 'native/drafts/upstream-156/build73-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['runtime_core_sha256_measured'] == build['runtime_core_sha256_measured']
    assert record['receipt_sha256'] == build['build_receipt_sha256']
    assert record['candidate_manifest_sha256'] == build['candidate_manifest_sha256']
    assert len(record['raw_report_sha256']) == 64
    assert record['privacy_admitted'] is record['production_admitted'] is False
    assert record['measured_inputs_sha256']
    for relative, expected in record['measured_inputs_sha256'].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected, relative


def test_worker_hdr_has_twelve_real_contexts_and_observed_process_cleanup():
    record = json.loads((EVIDENCE / 'worker-hdr73-observations.json').read_bytes())
    result = record['comparison']
    assert result['passed'] and result['worker_contexts_per_profile'] == 12
    assert result['document_contexts_per_profile'] == 4
    assert not result['document_worker_mismatches']
    assert {row['profile'] for row in record['profile_runs']} == {'baseline', 'protected'}
    for row in record['profile_runs']:
        assert row['resources_released'] and row['observed_processes'] > 0
        assert row['remaining_observed_processes'] == 0


def test_combined_restart_and_concurrent_profiles_are_distinct_gates():
    combined = json.loads((EVIDENCE / 'combined-math73-observations.json').read_bytes())
    concurrent = json.loads((EVIDENCE / 'combined-concurrent73-observations.json').read_bytes())
    assert combined['completed_phase_count'] == 18
    assert combined['protected_profile_count'] == 8
    assert combined['both_audio_math_selectors_observed']
    assert concurrent['completed_phase_count'] == 6 and concurrent['both_profiles_running']
    assert concurrent['resources_released'] and concurrent['remaining_observed_processes'] == 0
    assert not combined['device_cohort_verified']


def test_baseline_runtime_does_not_imply_protected_policy_admission():
    record = json.loads((ROOT / 'native/drafts/upstream-156/runtime-baseline73-observations.json').read_bytes())
    build = json.loads((ROOT / 'native/drafts/upstream-156/build73-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['returncode'] == 0 and record['completed_check_count'] == 18
    assert record['runtime_core_sha256_measured'] == build['runtime_core_sha256_measured']
    assert record['receipt_sha256'] == build['build_receipt_sha256']
    assert record['fingerprint_patched'] is record['privacy_admitted'] is record['production_admitted'] is False


def test_mobile_repeat_covers_eighteen_phases_without_device_cohort_admission():
    record = json.loads((EVIDENCE / 'combined-mobile73-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['completed_phase_count'] == 18 and record['protected_profile_count'] == 8
    assert record['both_audio_math_selectors_observed'] and not record['device_cohort_verified']
    assert 'not Android/iOS' in record['scope']


def test_supported_screen_gates_do_not_hide_the_failed_per_page_stress():
    record = json.loads((EVIDENCE / 'screen73-browser-observations.json').read_bytes())
    assert record['passed'] is False and record['measurement_complete']
    first = record['first_script']
    assert first['passed'] and len(first['phases']) == 6
    assert all(row['passed'] and not row['errors'] for row in first['phases'])
    manager = record['manager_context_lifecycle']
    assert manager['passed'] and len(manager['runs']) == 2
    for row in manager['runs']:
        assert row['passed'] and row['bfcache_restored'] and row['browser_connection_closed']
        assert len(row['phases']) == 6 and all(not phase['errors'] for phase in row['phases'])
    stress = record['raw_per_page_cdp_stress']
    assert stress['passed'] is False and stress['postguards_passed'] and stress['bfcache_restored']
    assert any('other page update changed this screen' in error
               for stage in stress['stages'] for error in stage['errors'])
    for gate in (first, manager, stress):
        for relative, expected in gate['measured_inputs_sha256'].items():
            assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected


def test_full_runtime73_python_regression_covers_the_committed_worker_hdr_tests():
    record = json.loads((EVIDENCE / 'canonical-python73-runtime-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['git_head'] == 'd0de567740fc10ea61972b10e51905775bfbcf8e'
    assert record['counts'] == dict(tests=4547, passed=4546, failures=0, errors=0, skipped=1)
    assert record['native_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
