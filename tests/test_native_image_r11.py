import copy
import hashlib
import json
from pathlib import Path
import re
import runpy

import pytest

from scripts import native_build as build
from scripts import verify_native_privacy_units as units

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = 'upstream-156-image-r11'


def test_r11_measured_subsets_do_not_admit_resources_or_release():
    candidate = build.load_candidate(CANDIDATE)
    records = {name: json.loads((candidate['directory'] / (name + '.json')).read_bytes())
               for name in ('windows-build', 'native-all-observations', 'runtime-observations',
                            'large-image-resources')}
    for record in records.values():
        assert record['candidate_manifest_sha256'] == candidate['manifest_sha256']
        assert record['privacy_admitted'] is record['production_admitted'] is False
    native = records['native-all-observations']
    assert native['passed'] and native['postguards_passed']
    assert native['native_groups'] == len(native['targets']) == 29
    assert native['native_case_executions'] == sum(row['case_executions'] for row in native['targets']) == 586
    distinct = {(row['build_target'], suite, case) for row in native['targets']
                for suite, cases in row['required_cases'].items() for case in cases}
    assert len(distinct) == native['distinct_binary_suite_cases'] == 429
    assert all(record['runtime_core_sha256_measured'] == native['runtime_core_sha256_measured'] for record in records.values())
    runtime = records['runtime-observations']
    assert runtime['passed'] and runtime['measurement_complete'] and len(runtime['phases']) == 14
    assert all(row['passed'] and row['resources_closed'] for row in runtime['phases'])
    assert runtime['direct_copy_variants'] == 32 and runtime['worker_frame_copy_variants'] == 40
    assert runtime['matched_gpu_contexts'] == 40 and runtime['matched_gpu_texture_observations'] == 240
    assert runtime['invalid_launches_rejected'] == 11 and not runtime['external_sites_tested']
    resources = records['large-image-resources']
    assert resources['graphics_passed'] and resources['graphics_measurement_complete']
    assert resources['full_image_copies'] == 6 and resources['rgba8_bytes'] == 64*1024*1024
    assert all(copy['passed'] for copy in resources['observations']['copies'])
    assert not resources['passed'] and not resources['resource_measurement_complete']
    assert not resources['full_resource_gate_passed'] and resources['sampling_errors']
    assert resources['original_unavailable_sample_preserved'] and resources['owned_resources_closed']
    probe = candidate['directory'] / 'large-rgba-probe.js'
    assert hashlib.sha256(probe.read_bytes()).hexdigest() == resources['probe_sha256']
    validator = runpy.run_path(str(candidate['directory'] / 'validate_large_rgba.py'))['validate']
    assert validator(resources['observations'])['passed']


def test_r11_host_record_identifies_the_measured_commit_not_future_changes():
    candidate = build.load_candidate(CANDIDATE)
    record = json.loads((candidate['directory'] / 'host-observations.json').read_bytes())
    assert record['passed'] and record['full_suite_executed'] and record['input_postguards_passed']
    assert record['measured_commit'] == '21465d92693f2c686f81dedee4cf5fa2ba6910b4'
    assert record['counts'] == {'passed': 5937, 'failed': 0, 'skipped': 1}


@pytest.mark.parametrize('field,value', [('width', 4095), ('height', 4097), ('byteLength', True),
                                       ('fixtureChangedChannels', 0), ('directSha256', None)])
def test_r11_large_image_evidence_cannot_be_downgraded_or_forged(field, value):
    candidate = build.load_candidate(CANDIDATE)
    record = json.loads((candidate['directory'] / 'large-image-resources.json').read_bytes())
    observed = copy.deepcopy(record['observations'])
    observed[field] = value
    validator = runpy.run_path(str(candidate['directory'] / 'validate_large_rgba.py'))['validate']
    with pytest.raises(ValueError):
        validator(observed)


def test_r11_keeps_the_complete_r10_prefix_and_unchanged_build_inputs():
    candidate = build.load_candidate(CANDIDATE)
    previous = build.load_candidate('upstream-156-image-r10')
    manifest = candidate['manifest']
    assert manifest['patches'][:135] == previous['manifest']['patches']
    assert len(manifest['patches']) == 136
    for row in manifest['patches']:
        assert hashlib.sha256((candidate['directory'] / 'patches' / row['file']).read_bytes()).hexdigest() == row['sha256']
    for name in ('source_files', 'dependencies', 'build', 'target_revision', 'target_version'):
        assert manifest[name] == previous['manifest'][name]
    assert manifest['extension_batch']['base_manifest_sha256'] == previous['manifest_sha256']
    packet = manifest['extension_batch']['packets'][0]
    assert hashlib.sha256((ROOT / packet['packet']).read_bytes()).hexdigest() == packet['packet_sha256']
    assert candidate['lock']['build_jobs'] == 4 and candidate['lock']['minimum_free_gib'] == 180
    assert not manifest['compiled'] and not manifest['runtime_verified'] and not manifest['production_admitted']


def test_r11_replay_and_case_registration_are_not_execution_results():
    candidate = build.load_candidate(CANDIDATE)
    proof = json.loads((candidate['directory'] / 'preparation.json').read_bytes())
    assert proof['passed'] and proof['manifest_sha256'] == candidate['manifest_sha256']
    assert proof['forward_patches'] == proof['reverse_patches'] == 136
    assert proof['final_owned_files_matched'] == 406 and proof['upstream_files_restored'] == 273
    assert not proof['compiled'] and not proof['native_tests_executed'] and not proof['canonical_sources_modified']
    patch = (candidate['directory'] / 'patches/0136-native-opaque-gpu-image-sources.patch').read_text(encoding='utf-8-sig')
    cases = set(re.findall(r'TEST\(GlintOpaqueCanvasImageSourceTest,\s*(\w+)\)', patch))
    assert len(cases) == 5
    assert units.required_tests('gpu-opaque-sources') == {'GlintOpaqueCanvasImageSourceTest': cases}
    assert units.unit_binary_target('gpu-opaque-sources') == 'blink_unittests'


def test_r11_retains_all_28_old_groups_and_exact_measured_host_sources(native_units_before_image_r11,
                                                                   host_sources_before_image_r11):
    previous = native_units_before_image_r11
    assert len(previous['SUPPORTED_TARGETS']) == 28
    assert units.SUPPORTED_TARGETS == (*previous['SUPPORTED_TARGETS'], 'gpu-opaque-sources')
    for target in previous['SUPPORTED_TARGETS']:
        assert units.required_tests(target) == previous['required_tests'](target)
        assert units.unit_binary_target(target) == previous['unit_binary_target'](target)
    record = json.loads((ROOT / 'native/drafts/environment/image-r11-host-source-upgrade.json').read_bytes())
    native = json.loads((ROOT / 'native/drafts/upstream-156-image-r10/native-all-observations.json').read_bytes())
    for row in record['sources']:
        assert hashlib.sha256((ROOT / row['source']).read_bytes()).hexdigest() == row['after_sha256']
        assert hashlib.sha256(host_sources_before_image_r11[row['source']]).hexdigest() == row['before_sha256']
        assert row['before_sha256'] == native['source_sha256'][row['source']]


@pytest.mark.parametrize('candidate', [None, 'upstream-156', 'upstream-156-canvas-r9', 'upstream-156-image-r10'])
def test_r11_new_group_requires_explicit_candidate_before_workspace_access(tmp_path, candidate):
    with pytest.raises(ValueError, match='exact upstream-156-image-r11'):
        units.verify(tmp_path / 'absent', tmp_path / 'not-created.json', target='gpu-opaque-sources',
                     candidate_name=candidate)
    assert not (tmp_path / 'absent').exists() and not (tmp_path / 'not-created.json').exists()


@pytest.mark.parametrize('target', ['gpu-opaque-sources', 'gpu-image-sources', 'canvas-rendering',
                                   'audio-lifecycle', 'surface-launch'])
def test_r11_uses_the_existing_resource_gate(monkeypatch, tmp_path, target):
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


def test_r11_requires_ownership_readiness_and_every_source_extension(tmp_path):
    required = {'0015-native-browser-context-key-ownership.patch', '0016-native-private-key-readiness.patch',
                '0033-native-surface-readback.patch', '0123-profile-surface-launch.patch',
                '0132-canvas-rendering-v2.patch', '0133-native-gpu-image-sources.patch',
                '0134-native-canvas-frame-provenance.patch', '0135-native-canvas-owned-raster.patch',
                '0136-native-opaque-gpu-image-sources.patch'}
    units.require_target_sources(tmp_path, [{'name': name} for name in required], 'gpu-opaque-sources')
    for missing in required:
        with pytest.raises(ValueError, match='exact context ownership'):
            units.require_target_sources(tmp_path, [{'name': name} for name in required - {missing}], 'gpu-opaque-sources')
