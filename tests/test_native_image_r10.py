import hashlib
import json
from pathlib import Path
import re

import pytest

from scripts import native_build as build
from scripts import verify_native_privacy_units as units


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = 'upstream-156-image-r10'


def test_image_r10_measured_build_and_native_records_keep_runtime_admission_separate():
    candidate = build.load_candidate(CANDIDATE)
    records = {name: json.loads((candidate['directory'] / (name + '.json')).read_bytes())
               for name in ('windows-build', 'native-all-observations', 'runtime-observations')}
    for record in records.values():
        assert record['candidate'] == CANDIDATE
        assert record['candidate_manifest_sha256'] == candidate['manifest_sha256']
        assert record['privacy_admitted'] is record['production_admitted'] is False
    windows, native, runtime = (records[name] for name in records)
    assert windows['compiled'] and windows['build']['jobs'] == 4
    assert windows['build']['siso_steps'] == 66
    assert windows['build']['siso_duration_seconds'] == 957.96
    assert windows['final_owned_source_files_matched'] == 406
    assert windows['changed_source_files'] == 12
    assert windows['build_output_timestamps_modified'] is False
    assert native['passed'] and native['postguards_passed']
    assert native['native_groups'] == len(native['targets']) == 28
    assert native['native_case_executions'] == sum(row['case_executions'] for row in native['targets']) == 581
    actual = {(row['build_target'], suite, case) for row in native['targets']
              for suite, cases in row['required_cases'].items() for case in cases}
    assert len(actual) == native['distinct_binary_suite_cases'] == 424
    added = next(row for row in native['targets'] if row['target'] == 'gpu-image-sources')
    assert added['passed'] and added['case_executions'] == 21
    assert added['required_cases'] == {suite: sorted(cases) for suite, cases in units.GPU_IMAGE_SOURCE_TESTS.items()}
    assert runtime['passed'] is runtime['measurement_complete'] is False
    assert runtime['phases_attempted'] == len(runtime['phases']) == 14
    assert runtime['frame_measurement_complete'] is False
    assert runtime['invalid_launches_rejected'] == 11
    assert runtime['invalid_launch_positive_control_passed']
    assert runtime['new_gpu_validator_first_attempt']['passed'] is False
    assert runtime['source_core_driver_asset_postguards_passed'] and runtime['owned_resources_closed']
    assert not runtime['external_sites_tested'] and not runtime['third_party_antibot_verified']


def test_image_r10_full_host_record_names_the_exact_measured_commit():
    candidate = build.load_candidate(CANDIDATE)
    record = json.loads((candidate['directory'] / 'host-observations.json').read_bytes())
    assert record['passed'] and record['full_suite_executed'] and record['input_postguards_passed']
    assert record['measured_commit'] == 'b65851516c0f79acc12854da8c0a94f7ebb284ed'
    assert record['candidate_manifest_sha256'] == candidate['manifest_sha256']
    assert record['counts'] == {'passed': 5897, 'failed': 0, 'skipped': 1}
    assert record['production_admitted'] is False


def test_image_r10_keeps_exact_r9_prefix_and_explicit_new_upstream_inputs():
    candidate = build.load_candidate(CANDIDATE)
    previous = build.load_candidate('upstream-156-canvas-r9')
    manifest = candidate['manifest']
    assert len(manifest['patches']) == 135
    assert manifest['patches'][:132] == previous['manifest']['patches']
    for row in manifest['patches']:
        path = candidate['directory'] / 'patches' / row['file']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
    for key in ('build', 'dependencies', 'target_revision', 'target_version'):
        assert manifest[key] == previous['manifest'][key]
    assert manifest['source_files'][:270] == previous['manifest']['source_files']
    assert len(manifest['source_files']) == 273
    assert {row['path'] for row in manifest['source_files'][270:]} == {
        'third_party/blink/renderer/modules/webgpu/gpu_canvas_context.cc',
        'third_party/blink/renderer/platform/graphics/exported_canvas_resource.h',
        'third_party/blink/renderer/platform/graphics/exported_canvas_resource.cc',
    }
    assert candidate['lock']['build_jobs'] == 4 and candidate['lock']['minimum_free_gib'] == 180
    assert CANDIDATE in build.WEBGPU_CANDIDATES
    assert manifest['compiled'] is manifest['runtime_verified'] is manifest['production_admitted'] is False


def test_image_r10_recipe_binds_all_three_exact_source_packets():
    candidate = build.load_candidate(CANDIDATE)
    record = candidate['manifest']['extension_batch']
    previous = build.load_candidate('upstream-156-canvas-r9')
    assert record['base_candidate'] == previous['name']
    assert record['base_manifest_sha256'] == previous['manifest_sha256']
    assert record['added_patches'] == len(record['packets']) == 3
    assert [packet['patches'][0] for packet in record['packets']] == [
        row['file'] for row in candidate['manifest']['patches'][132:]]
    for packet in record['packets']:
        path = ROOT / packet['packet']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == packet['packet_sha256']
        proof = json.loads(path.read_bytes())
        row = next(row for row in candidate['manifest']['patches'] if row['file'] == packet['patches'][0])
        assert proof['patch_sha256'] == row['sha256']


def test_image_r10_full_replay_is_not_compilation_or_case_execution():
    candidate = build.load_candidate(CANDIDATE)
    record = json.loads((candidate['directory'] / 'preparation.json').read_bytes())
    original = json.loads((ROOT / 'native/drafts/canvas-owned-raster/full-composition-observations.json').read_bytes())
    assert record['manifest_sha256'] == candidate['manifest_sha256'] == original['manifest_sha256']
    assert record['passed'] and record['forward_patches'] == record['reverse_patches'] == 135
    assert record['final_owned_files_matched'] == 406 and record['upstream_files_restored'] == 273
    assert record['canonical_sources_modified'] is record['compiled'] is record['native_tests_executed'] is False
    assert record['production_admitted'] is False


def test_image_r10_registers_all_21_native_cases_from_the_composed_source():
    candidate = build.load_candidate(CANDIDATE)
    expected = json.loads((ROOT / 'native/drafts/canvas-owned-raster/source-observations.json').read_bytes())[
        'composed_native_cases']
    required = units.required_tests('gpu-image-sources')
    assert required == {suite: set(cases) for suite, cases in expected.items()}
    assert sum(map(len, required.values())) == 21
    assert units.unit_binary_target('gpu-image-sources') == 'blink_unittests'
    patches = '\n'.join((candidate['directory'] / 'patches' / row['file']).read_text(encoding='utf-8-sig')
                        for row in candidate['manifest']['patches'][132:])
    for suite, cases in required.items():
        actual = set(re.findall(r'TEST\('+suite+r',\s*(\w+)\)', patches))
        assert actual == cases


def test_image_r10_preserves_all_27_r9_groups_and_binary_mappings(native_units_before_image_r10):
    previous = native_units_before_image_r10
    assert len(previous['SUPPORTED_TARGETS']) == 27
    assert units.SUPPORTED_TARGETS == (*previous['SUPPORTED_TARGETS'], 'gpu-image-sources')
    for target in previous['SUPPORTED_TARGETS']:
        assert units.required_tests(target) == previous['required_tests'](target)
        assert units.unit_binary_target(target) == previous['unit_binary_target'](target)


@pytest.mark.parametrize('candidate', [None, 'upstream-156', 'upstream-156-canvas-r9', 'upstream-156-audio-r8'])
def test_image_r10_rejects_other_candidates_before_workspace_access(tmp_path, candidate):
    with pytest.raises(ValueError, match='exact upstream-156-image-r10'):
        units.verify(tmp_path / 'absent', tmp_path / 'not-created.json', target='gpu-image-sources',
                     candidate_name=candidate)
    assert not (tmp_path / 'absent').exists() and not (tmp_path / 'not-created.json').exists()


@pytest.mark.parametrize('target', ['gpu-image-sources', 'canvas-rendering', 'audio-lifecycle', 'surface-launch'])
def test_image_r10_reaches_unchanged_resource_preflight(monkeypatch, tmp_path, target):
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


def test_image_r10_requires_ownership_bootstrap_and_all_three_source_extensions(tmp_path):
    required = {'0015-native-browser-context-key-ownership.patch', '0016-native-private-key-readiness.patch',
        '0033-native-surface-readback.patch', '0123-profile-surface-launch.patch',
        '0132-canvas-rendering-v2.patch', '0133-native-gpu-image-sources.patch',
        '0134-native-canvas-frame-provenance.patch', '0135-native-canvas-owned-raster.patch'}
    assert units.require_target_sources(tmp_path, [{'name': name} for name in required], 'gpu-image-sources') is None
    for missing in required:
        with pytest.raises(ValueError, match='exact context ownership'):
            units.require_target_sources(tmp_path, [{'name': name} for name in required - {missing}], 'gpu-image-sources')


def test_image_r10_archive_binds_both_current_and_exact_before_registration_sources(host_sources_before_image_r10):
    record = json.loads((ROOT / 'native/drafts/environment/image-r10-host-source-upgrade.json').read_bytes())
    old_native = json.loads((ROOT / 'native/drafts/upstream-156-canvas-r9/native-all-observations.json').read_bytes())
    assert set(host_sources_before_image_r10) == {row['source'] for row in record['sources']}
    for row in record['sources']:
        assert hashlib.sha256((ROOT / row['source']).read_bytes()).hexdigest() == row['after_sha256']
        assert hashlib.sha256(host_sources_before_image_r10[row['source']]).hexdigest() == row['before_sha256']
        assert row['before_sha256'] == old_native['source_sha256'][row['source']]
        assert b'upstream-156-image-r10' not in host_sources_before_image_r10[row['source']]
