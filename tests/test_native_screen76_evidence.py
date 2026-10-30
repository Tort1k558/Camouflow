from collections import Counter
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'


def evidence():
    return json.loads((ENV / 'screen76-runtime-observations.json').read_bytes())


def test_compiled_76_and_all_native_cases_bind_to_the_selected_sources():
    record = evidence()
    checkpoint = ROOT / 'native/drafts/upstream-156' / record['required_manifest']
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == record['checkpoint_sha256']
    assert len(json.loads(checkpoint.read_bytes())['patches']) == 76
    assert record['passed'] and record['measurement_complete'] and record['platform'] == 'win32'
    assert record['native_batch']['passed'] and record['native_batch']['postguards_passed']
    targets = record['native_batch']['targets']
    assert len(targets) == len({row['target'] for row in targets}) == 24
    assert all(row['native_cases_passed'] and row['returncode'] == 0 for row in targets)
    assert sum(row['tests'] for row in targets) == record['native_batch']['tests_passed'] == 506
    screenshot = next(row for row in targets if row['target'] == 'screenshot-transaction')
    assert screenshot['tests'] == len(set(record['native_batch']['screenshot_cases'])) == 12
    selection = json.loads((ENV / 'screenshot76-selection-observations.json').read_bytes())
    assert record['native_sources_sha256'] == {row['source']: row['staged_sha256'] for row in selection['sources']}
    assert record['preservation']['assets'] == 269 and record['preservation']['postguards_passed']


def test_cached_build_is_bounded_and_does_not_replace_historical_failure():
    record = evidence()
    build = record['build']
    assert build['jobs'] == 4 and build['baseline_planned_steps'] == 0
    assert build['conservative_append_steps'] == 69
    assert build['browser']['steps'] == 61 and build['native']['steps'] == 6
    assert build['browser']['steps'] + build['native']['steps'] <= build['conservative_append_steps'] <= 256
    assert build['browser']['seconds'] == 849.29 and build['native']['seconds'] == 681.04
    assert not any(build[key] for key in ('sync_rerun', 'hooks_rerun', 'objects_cleaned'))
    old = json.loads((ENV / record['diagnosis']['previous_negative']).read_bytes())
    assert old['diagnosis']['cross_session_capture_fixed'] is False
    assert old['runtime_core_sha256_measured']['chrome.dll'] != record['runtime_core_sha256_measured']['chrome.dll']
    assert record['diagnosis']['cross_session_capture_fixed_for_owned_matrix'] is True
    assert record['privacy_admitted'] is record['production_admitted'] is False


def test_six_factorial_controls_retain_screens_png_bounds_and_bfcache():
    controls = evidence()['capture_controls']
    assert len(controls) == 6
    assert {row['mode'] for row in controls} == {'none', 'cdp', 'playwright-postcheck', 'own-clip', 'other-no-clip', 'other-clip'}
    for row in controls:
        assert row['passed'] and row['postguards_passed'] and row['bfcache_restored']
        assert row['cleanup_errors'] == [] and row['phases']
        for phase in row['phases']:
            assert phase['passed'] and phase['pages']
            for page in phase['pages'].values():
                assert page['documents'] == 6 and page['errors'] == page['post_capture_errors'] == []
                if 'png_size' in page:
                    assert len(page['png_size']) == 2 and all(type(value) is int and value > 0 for value in page['png_size'])
                    assert len(page['png_sha256']) == 64
                    if row['mode'] == 'other-clip':
                        assert page['post_capture_documents'] == 6


def test_twelve_stress_phases_observe_cancellations_without_guaranteeing_race_timing():
    stress = evidence()['stress']
    assert stress['passed'] and stress['postguards_passed'] and stress['browser_connection_closed']
    assert stress['cleanup_errors'] == []
    assert stress['race_timing_guaranteed'] is stress['bfcache_verified'] is False
    phases = stress['phases']
    assert len(phases) == len({row['name'] for row in phases}) == 12
    assert {'same-value-protocol-update', 'full-page-restore', 'cross-document-navigation',
            'stale-owner-detach-keeps-new-owner', 'invalid-request-does-not-poison-queue'} <= {row['name'] for row in phases}
    assert all(row['passed'] and row['documents'] == row['other_documents'] == 6 for row in phases)
    counts = Counter(outcome['result'] for row in phases for outcome in row['outcomes'])
    assert dict(counts) == stress['outcomes']
    assert counts['protocol-cancelled'] > 0 and counts['expected-protocol-validation-error'] == 1


def test_staged_gpu_proof_does_not_claim_public_integration_workers_or_release():
    record = evidence()
    stage = record['staged_retained_gpu_objects']
    assert stage['passed'] and stage['postguards_passed'] and stage['public_cli_integrated'] is False
    assert hashlib.sha256((ENV / stage['preparation']).read_bytes()).hexdigest() == stage['source_preparation_sha256']
    validation = stage['validation']
    assert validation['passed'] and validation['retained_gpu_objects_verified']
    assert {row['mode'] for row in validation['runs']} == {'manager-desktop', 'manager-mobile-web'}
    assert all(row['document_contexts'] == 6 and row['webgl_apis'] == 2 for row in validation['runs'])
    for field in ('workers_verified', 'webgpu_readback_verified', 'cross_profile_isolation_verified',
                  'privacy_admitted', 'production_admitted'):
        assert validation[field] is False
    python = record['python_regression']
    assert python['passed'] and python['postguards_passed']
    assert python['git_head'].startswith('5f9f6ca')
    assert python['counts'] == dict(tests=4814, passed=4813, skipped=1, failures=0, errors=0)
    assert 'before retained-GPU preparation' in python['scope']
