import hashlib
import json
from pathlib import Path
import re

import pytest

from scripts import native_build as build
from scripts import verify_native_privacy_units as units


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = 'upstream-156-canvas-r9'
R9_MEASURED_TARGETS = tuple(row['target'] for row in json.loads(
    (ROOT / 'native/drafts/upstream-156-canvas-r9/native-all-observations.json').read_bytes())['targets'])


def test_canvas_r9_extends_exact_r8_recipe_and_retains_resource_limits():
    candidate = build.load_candidate(CANDIDATE)
    previous = build.load_candidate('upstream-156-audio-r8')
    manifest = candidate['manifest']
    assert len(manifest['patches']) == 132
    assert manifest['patches'][:131] == previous['manifest']['patches']
    for field in ('source_files', 'dependencies', 'build', 'target_revision', 'target_version'):
        assert manifest[field] == previous['manifest'][field]
    assert manifest['extension_batch']['base_manifest_sha256'] == previous['manifest_sha256']
    packet = manifest['extension_batch']['packets'][0]
    assert packet['packet_sha256'] == hashlib.sha256((ROOT / packet['packet']).read_bytes()).hexdigest()
    added = manifest['patches'][-1]
    assert added['file'] == '0132-canvas-rendering-v2.patch' and added['directory'] == '.'
    assert (candidate['directory'] / 'patches' / added['file']).read_bytes() == (
        ROOT / 'native/drafts/canvas-rendering-v2/canvas-rendering-v2.patch').read_bytes()
    assert candidate['lock']['build_jobs'] == 4 and candidate['lock']['minimum_free_gib'] == 180
    assert manifest['compiled'] is manifest['runtime_verified'] is manifest['production_admitted'] is False


def test_canvas_r9_source_replay_is_not_a_browser_or_native_test_result():
    candidate = build.load_candidate(CANDIDATE)
    record = json.loads((candidate['directory'] / 'preparation.json').read_bytes())
    assert record['passed'] and record['manifest_sha256'] == candidate['manifest_sha256']
    assert record['forward_patches'] == record['reverse_patches'] == 132
    assert record['final_owned_files_matched'] == 403 and record['upstream_files_restored'] == 270
    assert record['canonical_sources_modified'] is record['compiled'] is False
    assert record['native_tests_executed'] is record['production_admitted'] is False


def test_canvas_r9_unit_registration_matches_all_six_actual_native_test_names():
    candidate = build.load_candidate(CANDIDATE)
    patch = (candidate['directory'] / 'patches/0132-canvas-rendering-v2.patch').read_text(encoding='utf-8-sig')
    cases = set(re.findall(r'TEST\(GlintCanvasRenderingPolicyTest,\s*(\w+)\)', patch))
    assert len(cases) == 6
    assert units.required_tests('canvas-rendering') == {'GlintCanvasRenderingPolicyTest': cases}
    assert units.unit_binary_target('canvas-rendering') == 'blink_common_unittests'


def test_canvas_r9_preserves_all_r8_unit_groups_and_their_exact_archived_source(
        native_units_before_canvas_r9, native_units_before_image_r10):
    previous = native_units_before_canvas_r9
    assert native_units_before_image_r10['SUPPORTED_TARGETS'] == (*previous['SUPPORTED_TARGETS'], 'canvas-rendering')
    assert units.SUPPORTED_TARGETS[:len(R9_MEASURED_TARGETS)] == R9_MEASURED_TARGETS
    assert len(previous['SUPPORTED_TARGETS']) == 26
    for target in previous['SUPPORTED_TARGETS']:
        assert units.required_tests(target) == previous['required_tests'](target)
        assert units.unit_binary_target(target) == previous['unit_binary_target'](target)


@pytest.mark.parametrize('candidate', [None, 'upstream-156', 'upstream-156-audio-r8'])
def test_canvas_units_reject_the_wrong_candidate_before_workspace_access(tmp_path, candidate):
    with pytest.raises(ValueError, match='exact upstream-156-canvas-r9'):
        units.verify(tmp_path / 'absent', tmp_path / 'not-created.json', target='canvas-rendering',
                     candidate_name=candidate)
    assert not (tmp_path / 'absent').exists() and not (tmp_path / 'not-created.json').exists()


@pytest.mark.parametrize('target', ['canvas-rendering', 'audio-lifecycle', 'surface-launch'])
def test_canvas_r9_uses_the_unchanged_resource_preflight(monkeypatch, tmp_path, target):
    class ReachedPreflight(Exception):
        pass

    def preflight(workspace, *, lock):
        assert workspace == tmp_path and lock['build_jobs'] == 4 and lock['minimum_free_gib'] == 180
        raise ReachedPreflight

    monkeypatch.setattr(units.sys, 'platform', 'win32')
    monkeypatch.setattr(build, 'preflight', preflight)
    with pytest.raises(ReachedPreflight):
        units.verify(tmp_path, tmp_path / 'not-created.json', target=target, candidate_name=CANDIDATE)
    assert not (tmp_path / 'not-created.json').exists()


def test_canvas_r9_requires_the_actual_canvas_and_bootstrap_patches(tmp_path):
    required = {'0015-native-browser-context-key-ownership.patch', '0016-native-private-key-readiness.patch',
                '0123-profile-surface-launch.patch', '0132-canvas-rendering-v2.patch'}
    assert units.require_target_sources(tmp_path, [{'name': name} for name in required], 'canvas-rendering') is None
    for missing in required:
        with pytest.raises(ValueError, match='exact context ownership'):
            units.require_target_sources(tmp_path, [{'name': name} for name in required - {missing}], 'canvas-rendering')


def test_canvas_r9_host_archive_binds_both_registration_sources(
        host_sources_before_canvas_r9, host_sources_before_image_r10):
    packet = ROOT / 'native/drafts/environment/canvas-r9-host-source-upgrade.json'
    record = json.loads(packet.read_bytes())
    assert set(host_sources_before_canvas_r9) == {row['source'] for row in record['sources']}
    for row in record['sources']:
        assert hashlib.sha256(host_sources_before_image_r10[row['source']]).hexdigest() == row['after_sha256']
        assert hashlib.sha256(host_sources_before_canvas_r9[row['source']]).hexdigest() == row['before_sha256']
        assert b'upstream-156-canvas-r9' not in host_sources_before_canvas_r9[row['source']]


def test_canvas_r9_measured_build_and_native_batch_bind_the_same_binary():
    candidate = build.load_candidate(CANDIDATE)
    browser = json.loads((candidate['directory'] / 'windows-build.json').read_bytes())
    native = json.loads((candidate['directory'] / 'native-all-observations.json').read_bytes())
    assert browser['compiled'] and native['passed'] and native['postguards_passed']
    for record in (browser, native):
        assert record['candidate'] == CANDIDATE
        assert record['candidate_manifest_sha256'] == candidate['manifest_sha256']
        assert record['privacy_admitted'] is record['production_admitted'] is False
        assert record['third_party_antibot_verified'] is False
    assert browser['receipt_sha256'] == native['receipt_sha256']
    assert browser['runtime_core_sha256_measured'] == native['runtime_core_sha256_measured']
    assert browser['build']['jobs'] == native['unit_binary_build']['configured_jobs'] == 4
    assert browser['build']['configured_link_pool_depth'] == 1
    assert browser['build']['siso_steps'] == 68
    assert browser['build']['siso_duration_seconds'] == 1687.12
    assert native['unit_binary_build']['siso_steps'] == 8
    assert native['unit_binary_build']['siso_duration_seconds'] == 1029.43
    assert browser['source_postguards_passed'] and browser['native_source_postguards_passed']


@pytest.mark.parametrize('target', R9_MEASURED_TARGETS)
def test_canvas_r9_measured_native_groups_keep_exact_registered_cases(target):
    candidate = build.load_candidate(CANDIDATE)
    record = json.loads((candidate['directory'] / 'native-all-observations.json').read_bytes())
    rows = [row for row in record['targets'] if row['target'] == target]
    assert len(rows) == 1
    row = rows[0]
    assert row['passed'] and row['build_target'] == units.unit_binary_target(target)
    assert {suite: set(cases) for suite, cases in row['required_cases'].items()} == units.required_tests(target)
    assert row['case_executions'] == sum(map(len, row['required_cases'].values()))
    for field in ('test_binary_sha256', 'result_sha256', 'log_sha256'):
        assert re.fullmatch('[0-9a-f]{64}', row[field])


def test_canvas_r9_native_execution_counts_do_not_inflate_distinct_coverage(host_sources_before_image_r10):
    candidate = build.load_candidate(CANDIDATE)
    record = json.loads((candidate['directory'] / 'native-all-observations.json').read_bytes())
    assert [row['target'] for row in record['targets']] == list(R9_MEASURED_TARGETS)
    distinct = {(row['build_target'], suite, case) for row in record['targets']
                for suite, cases in row['required_cases'].items() for case in cases}
    assert record['native_groups'] == len(record['targets']) == 27
    assert record['native_case_executions'] == sum(row['case_executions'] for row in record['targets']) == 560
    assert record['distinct_binary_suite_cases'] == len(distinct) == 403
    assert record['shared_case_reexecutions'] == 560 - 403
    for name, digest in record['source_sha256'].items():
        value = host_sources_before_image_r10[name] if name in host_sources_before_image_r10 else (ROOT / name).read_bytes()
        assert hashlib.sha256(value).hexdigest() == digest


def test_canvas_r9_real_runtime_retains_failed_interop_and_closed_admission():
    candidate = build.load_candidate(CANDIDATE)
    record = json.loads((candidate['directory'] / 'runtime-observations.json').read_bytes())
    native = json.loads((candidate['directory'] / 'native-all-observations.json').read_bytes())
    assert record['candidate_manifest_sha256'] == candidate['manifest_sha256']
    assert record['runtime_core_sha256_measured'] == native['runtime_core_sha256_measured']
    assert record['receipt_sha256'] == native['receipt_sha256']
    assert record['native_batch_sha256'] == native['batch_report_sha256']
    assert record['measurement_complete'] and record['passed'] is False
    assert record['source_core_driver_asset_postguards_passed'] and record['owned_resources_closed']
    assert len(record['phases']) == 14 and record['measured_runtime_assets'] == 269
    assert [(row['preset'], row['restart']) for row in record['phases']] == [
        (preset, restart) for preset in record['rendering_presets'] for restart in (False, True)]
    assert record['canvas_document_worker_observations'] == 154
    assert record['canvas_security_observations'] == 42
    assert record['expanded_images'] == 280 and record['decoded_png_exports'] == 392
    assert record['verified_same_profile_restart_pairs'] == 7
    assert record['native_invalid_launches_rejected'] == 11
    assert record['invalid_launch_positive_control_passed'] and record['invalid_launch_postguards_passed']
    for row in record['phases']:
        assert row['passed'] is False and row['canvas_contexts_passed'] and row['expanded_rendering_passed']
        assert row['combined_canvas_audio_passed'] and row['first_script_passed']
        assert {error['stage'] for error in row['validation_errors']} == {'gpu-existing-validator', 'interop'}
        if row['restart']:
            assert row['private_identity_unchanged'] and row['gpu_observed_restart_equal']
        for api in row['interop']:
            assert api['known_fill_changed_channels'] > 0
            assert len(api['copies']) == 6
            for copy in api['copies']:
                assert (copy['changed_channels'] == 0) == (copy['path'] == 'png')
    for field in ('external_sites_tested', 'real_device_cohorts_verified', 'cross_profile_uniqueness_verified',
                  'manager_admission_changed', 'legacy_audio_repaired', 'third_party_antibot_verified',
                  'privacy_admitted', 'production_admitted'):
        assert record[field] is False
    assert record['earlier_failures_preserved']
