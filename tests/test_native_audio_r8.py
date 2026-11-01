import hashlib
import json
from pathlib import Path

import pytest

from scripts import native_build as build
from scripts import verify_native_privacy_units as units


ROOT = Path(__file__).resolve().parents[1]


def test_audio_r8_preserves_exact_r7_recipe_and_adds_two_chromium_packets():
    previous = build.load_candidate('upstream-156-webgpu-r7')
    candidate = build.load_candidate('upstream-156-audio-r8')
    manifest = candidate['manifest']
    assert manifest['patches'][:129] == previous['manifest']['patches']
    assert len(manifest['patches']) == 131
    for name in ('source_files', 'dependencies', 'build', 'target_revision', 'target_version'):
        assert manifest[name] == previous['manifest'][name]
    assert manifest['extension_batch']['base_manifest_sha256'] == previous['manifest_sha256']
    assert manifest['compiled'] is manifest['runtime_verified'] is manifest['production_admitted'] is False
    assert candidate['lock']['build_jobs'] == 4 and candidate['lock']['minimum_free_gib'] == 180
    for patch, packet in zip(manifest['patches'][129:], manifest['extension_batch']['packets'], strict=True):
        assert patch['directory'] == '.'
        prototype = ROOT / Path(packet['packet']).parent / 'next.patch'
        assert (candidate['directory'] / 'patches' / patch['file']).read_bytes() == prototype.read_bytes()
        assert hashlib.sha256((ROOT / packet['packet']).read_bytes()).hexdigest() == packet['packet_sha256']


def test_audio_r8_source_replay_does_not_claim_native_execution():
    candidate = build.load_candidate('upstream-156-audio-r8')
    record = json.loads((candidate['directory'] / 'preparation.json').read_bytes())
    assert record['passed'] and record['manifest_sha256'] == candidate['manifest_sha256']
    assert record['forward_patches'] == record['reverse_patches'] == 131
    assert record['final_owned_files_matched'] == 400 and record['upstream_files_restored'] == 270
    assert record['compiled'] is record['native_tests_executed'] is False
    assert record['canonical_sources_modified'] is record['production_admitted'] is False


def test_audio_r8_archived_host_sources_are_exactly_restorable(host_sources_before_audio_r8):
    for name, raw in host_sources_before_audio_r8.items():
        assert b'upstream-156-audio-r8' not in raw
        assert b'upstream-156-webgpu-r7' in raw


def test_audio_lifecycle_requires_exact_candidate_before_workspace_access(tmp_path):
    for candidate in (None, 'upstream-156-webgpu-r7'):
        with pytest.raises(ValueError, match='exact upstream-156-audio-r8'):
            units.verify(tmp_path, tmp_path / 'not-created.json', target='audio-lifecycle', candidate_name=candidate)
    assert not (tmp_path / 'not-created.json').exists()


def test_audio_lifecycle_exact_r8_reaches_resource_preflight(monkeypatch, tmp_path):
    class PreflightReached(Exception):
        pass

    def preflight(workspace, *, lock):
        assert workspace == tmp_path and lock['build_jobs'] == 4
        assert lock['minimum_free_gib'] == 180
        raise PreflightReached

    monkeypatch.setattr(units.sys, 'platform', 'win32')
    monkeypatch.setattr(build, 'preflight', preflight)
    with pytest.raises(PreflightReached):
        units.verify(tmp_path, tmp_path / 'not-created.json', target='audio-lifecycle',
                     candidate_name='upstream-156-audio-r8')


def test_audio_lifecycle_targets_linked_blink_and_exact_seven_cases():
    required = units.required_tests('audio-lifecycle')
    assert 'audio-lifecycle' in units.SUPPORTED_TARGETS
    assert units.unit_binary_target('audio-lifecycle') == 'blink_unittests'
    assert sum(map(len, required.values())) == 7
    assert 'GlintCopyBudgetRejectsBeforeAllocationOrRenderThread' in required['OfflineAudioContextTest']
    report = dict(tests=7, failures=0, disabled=0, testsuites=[
        dict(name=suite, testsuite=[dict(name=case, status='RUN', result='COMPLETED') for case in sorted(cases)])
        for suite, cases in required.items()])
    units.validate_results(report, target='audio-lifecycle')
    report['testsuites'][0]['testsuite'][0]['name'] = 'UnrelatedPassingTest'
    with pytest.raises(ValueError, match='names differ'):
        units.validate_results(report, target='audio-lifecycle')


def test_audio_lifecycle_registration_keeps_all_historical_target_prefixes(
        tmp_path, monkeypatch, host_sources_before_audio_r8):
    import runpy
    import sys

    path = tmp_path / 'before_audio_r8_units.py'
    path.write_bytes(host_sources_before_audio_r8['scripts/verify_native_privacy_units.py'])
    monkeypatch.setattr(sys, 'path', sys.path.copy())
    previous = runpy.run_path(str(path))
    assert units.SUPPORTED_TARGETS == (*previous['SUPPORTED_TARGETS'], 'audio-lifecycle')
    for target in previous['SUPPORTED_TARGETS']:
        assert units.required_tests(target) == previous['required_tests'](target)
        assert units.unit_binary_target(target) == previous['unit_binary_target'](target)


def test_audio_r8_full_host_record_preserves_failures_and_later_tooling_boundary():
    candidate = build.load_candidate('upstream-156-audio-r8')
    record = json.loads((candidate['directory'] / 'host-regression.json').read_bytes())
    assert record['passed'] and record['input_postguards_passed']
    assert record['counts'] == dict(passed=5581, failed=0, skipped=1)
    assert record['original_failed_run']['counts']['failed'] == 4
    assert record['interrupted_retry']['interrupted'] and not record['interrupted_retry']['passed']
    assert record['later_public_lifecycle_cli_included'] is False
    assert record['native_runtime_verified'] is record['production_admitted'] is False


def test_audio_r8_windows_build_is_not_native_test_or_browser_admission():
    candidate = build.load_candidate('upstream-156-audio-r8')
    record = json.loads((candidate['directory'] / 'windows-build.json').read_bytes())
    assert record['compiled'] and record['candidate_manifest_sha256'] == candidate['manifest_sha256']
    assert record['build']['jobs'] == 4 and record['build']['configured_link_pool_depth'] == 1
    assert record['build']['siso_steps'] == 60 and record['build']['siso_duration_seconds'] == 965.31
    assert record['build']['stage_duration_seconds'] == 1295.009
    assert len(record['build']['completed_cpp_objects']) == 8
    assert record['build']['changed_owned_files'] == 6
    assert all(stage['returncode'] == 0 for stage in record['build']['stages'])
    assert record['sampled_resources']['observer_still_running']
    assert record['sampled_resources']['max_observed_linkers'] == 2
    for flag in ('native_tests_verified_in_this_record', 'browser_runtime_verified',
                 'legacy_audio_repaired', 'third_party_antibot_verified', 'production_admitted'):
        assert record[flag] is False


def test_audio_r8_selected_native_record_binds_exact_cases_without_browser_admission():
    candidate = build.load_candidate('upstream-156-audio-r8')
    record = json.loads((candidate['directory'] / 'native-selected-observations.json').read_bytes())
    browser = json.loads((candidate['directory'] / 'windows-build.json').read_bytes())
    assert record['passed'] and record['native_postguards_passed']
    assert record['candidate_manifest_sha256'] == candidate['manifest_sha256']
    assert record['runtime_core_sha256_measured'] == browser['runtime_core_sha256_measured']
    assert record['build_receipt_sha256'] == browser['receipt_sha256']
    assert record['native_cases'] == 135
    assert [row['target'] for row in record['targets']] == [
        'audio-lifecycle', 'audio-math', 'surface-launch', 'identity-transport', 'worker-surfaces']
    assert [row['tests'] for row in record['targets']] == [7, 12, 41, 20, 55]
    for row in record['targets']:
        assert row['passed']
        assert row['required_cases'] == {suite: sorted(cases)
                                         for suite, cases in units.required_tests(row['target']).items()}
    for name, digest in record['source_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    assert record['unit_binary_build'] == dict(siso_steps=1034, siso_duration_seconds=4424.78,
                                               configured_jobs=4, build_invocations=1)
    assert record['sampled_controller_resources']['state'] == 'controller-terminal'
    for flag in ('all_native_targets_verified', 'independent_browser_runtime_verified',
                 'native_seed_erasure_proved_for_all_future_scheduling', 'legacy_audio_repaired',
                 'privacy_admitted', 'production_admitted'):
        assert record[flag] is False


def test_audio_r8_public_lifecycle_run_is_separate_from_r7_and_full_admission():
    candidate = build.load_candidate('upstream-156-audio-r8')
    record = json.loads((candidate['directory'] / 'audio-lifecycle-observations.json').read_bytes())
    compiled = json.loads((candidate['directory'] / 'windows-build.json').read_bytes())
    assert record['passed'] and record['public_cli_executed']
    assert record['candidate_manifest_sha256'] == candidate['manifest_sha256']
    assert record['runtime_core_sha256_measured'] == compiled['runtime_core_sha256_measured']
    assert record['receipt_sha256'] == compiled['receipt_sha256']
    assert record['total_cases'] == 74 and record['total_checks'] == 346
    assert {name: (row['cases'], row['checks']) for name, row in record['modes'].items()} == {
        'baseline': (24, 114), 'legacy': (26, 118), 'math': (24, 114)}
    assert all(row['passed'] and row['resources_closed'] and row['pending_detach_window_ms'] == 150
               for row in record['modes'].values())
    assert record['r7_comparison_record_sha256'] == hashlib.sha256(
        (ROOT / 'native/drafts/audio-lifecycle-runtime/r7-observations.json').read_bytes()).hexdigest()
    for name, digest in record['source_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    for flag in ('postguards_passed', 'driver_postguard_passed', 'runtime_asset_postguards_passed', 'resources_closed'):
        assert record[flag] is True
    for flag in ('native_seed_erasure_proven', 'all_future_scheduling_verified', 'legacy_audio_repaired',
                 'full_runtime_suite_admitted', 'privacy_admitted', 'production_admitted'):
        assert record[flag] is False


def test_audio_r8_first_qa_attempt_preserves_failures_and_the_exact_history_fix():
    candidate = build.load_candidate('upstream-156-audio-r8')
    record = json.loads((candidate['directory'] / 'qa-attempt1.json').read_bytes())
    assert record['measurement_complete'] and record['passed'] is False
    assert record['candidate_manifest_sha256'] == candidate['manifest_sha256']
    assert record['native_selected_cases_passed'] == 135
    assert record['public_audio_lifecycle_cases_passed'] == 74
    assert record['baseline_suite']['checks_in_passing_groups'] == 151
    assert record['baseline_suite']['failed_group'] == 'hardware'
    assert record['baseline_suite']['matched_hardware_observations_before_failure'] == 4
    assert record['baseline_suite']['hardware_failure_root_cause_confirmed'] is False
    assert record['baseline_suite']['close_deadline_relaxed'] is False
    assert record['audio_compatibility']['modes'] == {'baseline': True, 'legacy': False, 'math': True}
    assert record['ai_workflow']['returncode'] == 2
    assert record['ai_workflow']['actual_workflow_measured'] is False
    assert record['full_host']['counts'] == dict(passed=5694, failed=2, skipped=1)
    assert record['full_host']['measured_expected_input_count_preserved'] == 226
    assert record['full_host']['original_observation_digests_preserved'] is True
    assert record['full_host']['focused_history_tests_passed'] == 10
    assert record['full_host']['full_suite_after_repair_executed'] is False
    assert record['all_native_target_attempt']['executed'] is False
    assert record['all_native_target_attempt']['requested_groups'] == 26
    for flag in ('legacy_audio_repaired', 'full_qa_admitted', 'privacy_admitted', 'production_admitted'):
        assert record[flag] is False
