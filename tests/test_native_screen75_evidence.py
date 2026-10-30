import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'native/drafts/environment/screen75-runtime-observations.json'


def record():
    return json.loads(EVIDENCE.read_bytes())


def test_completed_75_native_package_is_bound_to_exact_checkpoint_and_core():
    data = record()
    checkpoint = ROOT / 'native/drafts/upstream-156' / data['required_manifest']
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == data['checkpoint_sha256']
    assert len(json.loads(checkpoint.read_bytes())['patches']) == 75
    assert data['measurement_complete'] and data['platform'] == 'win32'
    assert set(data['runtime_core_sha256_measured']) == {'chrome.exe', 'chrome.dll', 'chrome_elf.dll'}
    batch = data['native_batch']
    assert batch['passed'] and batch['postguards_passed']
    assert len(batch['targets']) == batch['groups'] == 23
    assert len({row['target'] for row in batch['targets']}) == 23
    assert all(row['native_cases_passed'] and row['returncode'] == 0 for row in batch['targets'])
    assert sum(row['tests'] for row in batch['targets']) == batch['tests_passed'] == 494
    assert data['preservation']['assets'] == 269
    assert data['preservation']['postguards_passed']
    assert not data['build']['sync_rerun'] and not data['build']['hooks_rerun']
    assert not data['build']['objects_cleaned'] and data['build']['jobs'] == 4
    assert data['build']['baseline_planned_steps'] == 0
    assert not data['privacy_admitted'] and not data['production_admitted']


def test_full_python_repeat_is_separate_from_runtime_proof():
    python = record()['python_regression']
    assert python['passed'] and python['postguards_passed']
    assert python['counts'] == dict(tests=4710, passed=4709, skipped=1, errors=0, failures=0)
    assert python['git_head'] == '6ad4ff9cd393f2a31aa22587414313565ddb6978'


def test_first_script_covers_three_modes_restart_and_six_real_document_roles():
    rows = {row['kind']: row for row in record()['browser_runs']}
    run = rows['first-script']
    assert run['passed'] and run['postguards_passed']
    phases = run['phases']
    assert {(row['mode'], row['phase']) for row in phases} == {
        (mode, phase) for mode in ('manager-desktop', 'manager-mobile-web', 'native-control')
        for phase in ('initial', 'persistent-profile-restart')}
    assert len(phases) == 6
    roles = {'main', 'same', 'cross', 'nested-return', 'srcdoc', 'about-blank'}
    assert all(row['passed'] and row['browser_connection_closed']
               and set(row['document_roles']) == roles for row in phases)


def test_combined_history_does_not_claim_worker_or_webgpu_readback_coverage():
    runs = {row['kind']: row for row in record()['browser_runs']}
    for kind in ('protected-history', 'protected-combined'):
        row = runs[kind]
        assert row['passed'] and row['measurement_complete'] and row['postguards_passed']
        validation = row['validation']
        assert validation['passed'] and len(validation['runs']) == 2
        assert {run['mode'] for run in validation['runs']} == {'manager-desktop', 'manager-mobile-web'}
        assert all(run['passed'] and run['screen_phases'] == 6 and run['canvas_cases'] == 32
                   for run in validation['runs'])
    surfaces = runs['protected-combined']['surface_validation']
    assert surfaces['passed']
    assert all(row['passed'] and row['document_contexts'] == 1 and row['webgl_apis'] == 2
               and row['audio_phases'] == 3 and row['webgpu_readback_verified'] is False
               for row in surfaces['runs'])


def test_capture_factorial_preserves_failure_and_distinguishes_screen_from_png():
    data = record()
    runs = {row['kind']: row for row in data['browser_runs']}
    controls = ('no-capture', 'same-session-no-clip', 'same-session-clip-postcheck',
                'original-mixed-client', 'playwright-postcheck',
                'other-session-no-clip-postcheck', 'other-session-clip-postcheck')
    for kind in controls:
        row = runs[kind]
        assert row['measurement_complete'] and row['postguards_passed'] and row['bfcache_restored']
        assert row['browser_connection_closed'] and not row['cleanup_errors']
        assert len(row['stages']) == 7
    assert all(runs[kind]['passed'] for kind in controls[:3])
    assert all(not runs[kind]['passed'] for kind in controls[3:])
    clipped = runs['other-session-clip-postcheck']
    set_a = next(row for row in clipped['stages'] if row['name'] == 'set-a')
    assert len(set_a['pages']['A']['post_capture_errors']) == 6
    assert not set_a['pages']['B']['post_capture_errors']
    without_clip = runs['other-session-no-clip-postcheck']
    assert all(not page.get('post_capture_errors') for stage in without_clip['stages']
               for page in stage['pages'].values())
    assert any('screenshot dimensions' in error for stage in without_clip['stages'] for error in stage['errors'])
    assert not data['diagnosis']['cross_session_capture_fixed']
    assert data['diagnosis']['stock_comparison_executed']


def test_stock_controls_use_identical_collectors_but_do_not_claim_equal_build_flags():
    data = record()
    stock = data['stock_controls']
    glint = {row['kind']: row for row in data['browser_runs']}
    matched = {'own-clip': 'same-session-clip-postcheck',
               'other-no-clip': 'other-session-no-clip-postcheck',
               'other-clip': 'other-session-clip-postcheck'}
    assert {row['mode'] for row in stock} == {'own-clip', 'other-no-clip', 'other-clip'}
    reference = ROOT / 'native/drafts/upstream-156/stock-control-observations.json'
    expected = json.loads(reference.read_bytes())
    assert expected['same_build_flags_verified'] is False
    for row in stock:
        assert row['same_diagnostic_module_as_glint']
        assert row['diagnostic_module_sha256'] == glint[matched[row['mode']]][
            'diagnostic_source_sha256'][row['mode'] + '-module.py']
        assert row['runtime_core_sha256_measured'] == expected['stock_core_sha256']
        assert row['reference_record_sha256'] == hashlib.sha256(reference.read_bytes()).hexdigest()
        assert row['measurement_complete'] and row['postguards_passed']
        assert not row['cleanup_errors'] and row['browser_connection_closed']
        assert not row['passed'] and row['bfcache_restored']
    clipped = next(row for row in stock if row['mode'] == 'other-clip')
    stage = next(row for row in clipped['stages'] if row['name'] == 'set-a')
    assert len(stage['pages']['A']['post_capture_errors']) == 6
    assert not stage['pages']['B']['post_capture_errors']


def test_evidence_still_binds_the_measured_public_collectors(surface_sources_before_retained):
    for name, expected in record()['public_collector_sources_sha256'].items():
        actual = (surface_sources_before_retained['sha256'][name]
                  if name in surface_sources_before_retained['sha256']
                  else hashlib.sha256((ROOT / name).read_bytes()).hexdigest())
        assert actual == expected
