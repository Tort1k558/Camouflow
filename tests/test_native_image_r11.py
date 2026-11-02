import hashlib
import json
from pathlib import Path
import re

import pytest

from scripts import native_build as build
from scripts import verify_native_privacy_units as units

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = 'upstream-156-image-r11'


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
